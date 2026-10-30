"""Acceptance run for the shared-prefix HFScorer (r1). One source per process, one NPU.

    python3 -P check_scorer.py --source typed-decisions --out-dir <dir> [--model-path ...]

Phases (each resumable at chunk granularity; results are appended to <out>/<source>/<phase>.jsonl):
  gt                    GROUND TRUTH: r0 HFScorer (r0_code, untouched) at token_budget=1 = batch of one, no padding
  old_16384             r0 HFScorer as published (left padding, default budget)
  eq_len                one row per candidate, right padding, batches of equal-length rows only (bf16 batch floor)
  new_16384/new_4096    r1 HFScorer: shared prefix, right padding (the candidate)
  new_noprefix          right padding, one row per candidate;  new_left: shared prefix with r0 left padding
  r1old_16384           r1 HFScorer(shared_prefix=False): regression check that the copy equals r0
  new_16384, new_4096   r1 HFScorer(shared_prefix=True)
  new_16384_c256        same with 256 items per scorer call instead of 64 (speed only)
  tr_old, tr_new        empty-input and question-only transforms over a subset, old vs new
Items are scored in chunks of 64 (run_baseline's default) except where stated. Each chunk is timed with a host
sync (the scorer returns host floats). The first chunk of every phase is scored once untimed (warm-up).
"""
import argparse, importlib.util, json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
import scorer as r1  # noqa: E402
from prompt import blank_input, drop_input  # noqa: E402

R0_SCORER = "/mnt/cephfs/xingchao/experiments/jev/r0_code/scorer.py"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_r0():
    spec = importlib.util.spec_from_file_location("scorer_r0", R0_SCORER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # its imports (split, common, prompt) resolve to the identical r1_code copies
    cap = []
    orig = mod.softmax
    mod.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
    return mod, cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sample", default="/mnt/cephfs/xingchao/experiments/jev/r1_scorer_check/sample.jsonl")
    ap.add_argument("--model-path", default="/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B")
    ap.add_argument("--chunk", type=int, default=64)
    ap.add_argument("--transform-items", type=int, default=128)
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N sample items")
    ap.add_argument("--phases", default="gt,eq_len,new_16384,new_noprefix,new_left,new_4096,new_16384_c256,tr_gt,tr_old,tr_new")
    args = ap.parse_args()
    out = os.path.join(args.out_dir, args.source)
    os.makedirs(out, exist_ok=True)
    hb = open(os.path.join(out, "heartbeat.log"), "a", buffering=1)

    def beat(msg):
        hb.write(f"{now()} {msg}\n")

    sample = [json.loads(l) for l in open(args.sample)]
    sample = [d for d in sample if d["source"] == args.source]
    if args.limit:
        sample = sample[:args.limit]
    want = {d["key"]: d for d in sample}
    recs = {}
    for task in common.TASKS:
        p = common.task_path(common.DEFAULT_DATA_ROOT, task, args.source)
        if os.path.exists(p):
            for r in common.load_records(p):
                if r["key"] in want:
                    recs[r["key"]] = r
    items = [recs[d["key"]] for d in sample]
    assert len(items) == len(sample)
    beat(f"loaded {len(items)} items")

    r0mod, cap = load_r0()
    kw = dict(device="npu", dtype="bfloat16")
    base = r0mod.HFScorer(args.model_path, **kw)
    base._load()
    shared = dict(model=base._model, tokenizer=base._tok)   # one model object for every scorer
    old = {16384: base, 4096: r0mod.HFScorer(args.model_path, token_budget=4096, **kw, **shared)}
    r1old = r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=False, padding="left", **kw, **shared)
    new = {16384: r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=True, **kw, **shared),
           4096: r1.HFScorer(args.model_path, token_budget=4096, shared_prefix=True, **kw, **shared)}

    def run_old(sc, batch):   # r0 returns probabilities; the raw summed log-probs are captured at its softmax call
        del cap[:]
        probs = sc.score(batch)
        return [list(c) for c in cap], probs

    def run_new(sc, batch):
        raw = sc.score_raw(batch)
        return raw, [r1.softmax(s) for s in raw]

    def phase(name, scorer_fn, sc, its, chunk, tag=None):
        path = os.path.join(out, f"{name}.jsonl")
        done = {}
        if os.path.exists(path):
            for l in open(path):
                try:
                    d = json.loads(l)
                except ValueError:
                    continue            # truncated last line of a killed run
                done[d["c"]] = d
        chunks = [its[i:i + chunk] for i in range(0, len(its), chunk)]
        with open(path, "a") as f:
            for c, batch in enumerate(chunks):
                if c in done:
                    continue
                if c == 0:
                    scorer_fn(sc, batch)                        # untimed warm-up
                st0 = dict(getattr(sc, "stats", {}))
                t0 = time.time()
                raw, probs = scorer_fn(sc, batch)
                dt = time.time() - t0
                st1 = getattr(sc, "stats", {})
                rec = {"c": c, "keys": [b["key"] for b in batch], "raw": raw, "p": probs, "s": dt,
                       "rows": st1.get("rows", 0) - st0.get("rows", 0),
                       "padded_tokens": st1.get("padded_tokens", 0) - st0.get("padded_tokens", 0),
                       "warmup_included": False}
                f.write(json.dumps(rec) + "\n")
                f.flush()
                beat(f"phase {name} chunk {c + 1}/{len(chunks)} {dt:.1f}s")
        beat(f"phase {name} complete")

    phases = args.phases.split(",")
    if any(p.startswith("fp32_") for p in phases):
        # Padding probe in fp32 (bf16 noise gone): batch of one vs r0 left padding vs right padding, same weights in fp32.
        f32 = dict(device="npu", dtype="float32")
        probes = {"fp32_gt": (run_old, r0mod.HFScorer(args.model_path, token_budget=1, **f32)),
                  "fp32_left": (run_old, r0mod.HFScorer(args.model_path, token_budget=16384, **f32)),
                  "fp32_right_noshare": (run_new, r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=False, padding="right", **f32)),
                  "fp32_right_shared": (run_new, r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=True, padding="right", **f32))}
        for nm, (fn, sc_) in probes.items():
            if nm in phases:
                phase(nm, fn, sc_, items, args.chunk)
        return
    # Ground truth = r0 class at token_budget=1: one row per candidate, batch of one, no padding at all.
    gt = r0mod.HFScorer(args.model_path, token_budget=1, **kw, **shared)
    eq = r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=False, padding="right", equal_length_only=True, **kw, **shared)
    new_np = r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=False, padding="right", **kw, **shared)
    new_left = r1.HFScorer(args.model_path, token_budget=16384, shared_prefix=True, padding="left", **kw, **shared)
    fns = {
        "old_16384": (run_old, old[16384], items, args.chunk),     # r0 as published (left padding)
        "r1old_16384": (run_new, r1old, items, args.chunk),       # r1 class in r0 mode: must equal old_16384 bit for bit
        "gt": (run_old, gt, items, args.chunk),                    # ground truth, unpadded batch 1
        "eq_len": (run_new, eq, items, args.chunk),                # unpadded, batched on equal-length rows only
        "new_16384": (run_new, new[16384], items, args.chunk),     # shared prefix + right padding (the candidate)
        "new_4096": (run_new, new[4096], items, args.chunk),
        "new_noprefix": (run_new, new_np, items, args.chunk),      # right padding, one row per candidate
        "new_left": (run_new, new_left, items, args.chunk),        # shared prefix but r0 left padding
        "new_16384_c256": (run_new, new[16384], items, 256),
    }
    for name in phases:
        if name in fns:
            fn, sc, its, ch = fns[name]
            phase(name, fn, sc, its, ch)
    if "speed" in phases:
        # Timing only (scores discarded): the whole sample, 3 repetitions of old / new / new with 256-item calls,
        # alternating on the same chip with warm models, 64-item calls unless stated. One line per pass.
        reps = int(os.environ.get("SPEED_REPS", "3"))
        sp = os.path.join(out, "speed.jsonl")
        done_sp = {(d["rep"], d["name"]) for d in map(json.loads, open(sp))} if os.path.exists(sp) else set()
        for rep in range(reps):
            for nm, fn, sc, ch in (("old", run_old, old[16384], 64), ("new", run_new, new[16384], 64),
                                   ("new_c256", run_new, new[16384], 256)):
                if (rep, nm) in done_sp:
                    continue
                st0 = dict(getattr(sc, "stats", {}))
                t0 = time.time()
                for i in range(0, len(items), ch):
                    fn(sc, items[i:i + ch])
                dt = time.time() - t0
                rows = getattr(sc, "stats", {}).get("rows", 0) - st0.get("rows", 0) if nm != "old" else \
                    sum(len(x["levels"]) for x in items)
                with open(sp, "a") as f:
                    f.write(json.dumps({"rep": rep, "name": nm, "items": len(items), "rows": rows, "s": dt}) + "\n")
                beat(f"speed rep {rep} {nm} {dt:.1f}s")
        return
    # Transform scorers over a subset (spread over the sample by stride so all tasks/variants appear).
    sub = items[::max(1, len(items) // args.transform_items)][:args.transform_items]
    for name, label, scs in (("tr_gt", "old", gt), ("tr_old", "old", old[16384]), ("tr_new", "new", new[16384])):
        if name not in phases:
            continue
        for tname, tf in (("empty_input", blank_input), ("question_only", drop_input)):
            if label == "old":
                fn = lambda s, b, tf=tf: run_old(s, [tf(x) for x in b])
            else:
                fn = lambda s, b, tf=tf: run_new(s, [tf(x) for x in b])
            phase(f"{name}__{tname}", fn, scs, sub, args.chunk)
    json.dump({"n_items": len(items), "source": args.source, "tr_keys": [x["key"] for x in sub],
               "new_stats": {str(k): dict(v.stats) for k, v in new.items()},
               "r1old_stats": dict(r1old.stats)}, open(os.path.join(out, "meta.json"), "w"))
    beat("ALL PHASES COMPLETE")


if __name__ == "__main__":
    main()
