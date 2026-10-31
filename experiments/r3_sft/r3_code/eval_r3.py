"""R3 Track K scorer (R3-SFT-PREREG sec 4-5): score a checkpoint (or a degenerate baseline) on
decision-v7 / transfer-v4 partitions converted by r1_code/convert_kev.py, write readouts and a
report.json with the prereg's Track K metrics.

    python3 -P eval_r3.py --model-path <HF dir or 'constant'|'question_only'|'empty_input'|'uniform'> \\
        --suite decision-v7 --split dev --out <dir> [--limit N] [--device npu]

Scorer: r0_code/scorer.py's HFScorer with token_budget=1 (one row per forward, no padding, slow but exact; the default
here). r1_code/scorer.py is NOT used until the orchestrator accepts it. --scorer rightpad is a candidate replacement:
the same one-row-per-candidate layout but batched with RIGHT padding and logits gathered at the scored positions; it
exists to be compared against the exact scorer (see --compare-exact), not to produce reported numbers.

sec 4.1/4.2 headline: Kev's own argmax rule (first maximal index, numpy convention) on the raw
scores; sec 4.1 also reports the R0 tie convention (tie = not correct) and the tie count beside it.
sec 4.3/5: degenerate baselines (constant fitted on decision-v7 train per (source, qname) with the
position/then-0 fallback tiers of sec 5.1; question-only/empty-state as prompt transforms over the
SAME scored model; uniform). sec 10.4(a): the gold-position distribution and the constant/uniform
numbers are computed before any other Track K number.

Test partitions: refuses unless --read-test is given, logging to TEST_READS.log (sec 8.4); this
round has no FINAL.json yet, so --read-test always refuses (see note in main()).
"""
import argparse
import datetime
import json
import math
import os
import sys
from collections import Counter, defaultdict

R0_CODE = os.environ.get("NGA_R0_CODE", "/mnt/cephfs/xingchao/experiments/jev/r0_code")
if R0_CODE not in sys.path:
    sys.path.insert(0, R0_CODE)
import prompt as prompt_mod  # noqa: E402
import scorer as scorer_mod  # noqa: E402

KEV_DIR = "/mnt/cephfs/xingchao/experiments/jev/KEV"
TEST_READS_LOG = "/mnt/cephfs/xingchao/experiments/jev/r3_runs/TEST_READS.log"
DEGENERATE = ("constant", "question_only", "empty_input", "uniform")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_rows(suite, split, limit=0):
    path = os.path.join(KEV_DIR, suite, f"{split}.jsonl")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows, path


def gold_index(row):
    return [l["id"] for l in row["levels"]].index(row["gold"])


# ---- degenerate baselines (sec 5) ---------------------------------------------------------------

def fit_constant(train_rows):
    """sec 5.1: majority gold level per (source, qname) on decision-v7 train; fallback majority gold
    POSITION per (level_type, n_options); final fallback position 0. Returns a callable scorer."""
    by_q = defaultdict(Counter)
    by_pos = defaultdict(Counter)
    for r in train_rows:
        by_q[(r["source"], r["qname"])][r["gold"]] += 1
        by_pos[(r["level_type"], len(r["levels"]))][gold_index(r)] += 1
    maj_q = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_q.items()}
    maj_pos = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_pos.items()}

    def score_one(row):
        ids = [l["id"] for l in row["levels"]]
        key_q = (row["source"], row["qname"])
        if key_q in maj_q and maj_q[key_q] in ids:
            idx, tier = ids.index(maj_q[key_q]), "question"
        else:
            key_pos = (row["level_type"], len(row["levels"]))
            idx = maj_pos.get(key_pos, 0)
            idx = idx if idx < len(ids) else 0
            tier = "position" if key_pos in maj_pos else "position0"
        s = [0.0] * len(ids)
        s[idx] = 1.0
        return s, tier
    return score_one


def score_degenerate(name, rows, train_rows=None, inner_model_path=None, device="cpu", adapter=None):
    """Returns (list of raw-score lists, list of tier/notes)."""
    if name == "uniform":
        return [[1.0 / len(r["levels"])] * len(r["levels"]) for r in rows], ["uniform"] * len(rows)
    if name == "constant":
        f = fit_constant(train_rows)
        out, tiers = [], []
        for r in rows:
            s, t = f(r)
            out.append(s)
            tiers.append(t)
        return out, tiers
    if name in ("question_only", "empty_input"):
        if adapter:
            m, t = load_with_adapter(inner_model_path, adapter, device)
            base = scorer_mod.HFScorer(inner_model_path, device=device, dtype="bfloat16", token_budget=1, model=m, tokenizer=t)
        else:
            base = scorer_mod.HFScorer(inner_model_path, device=device, dtype="bfloat16", token_budget=1)
        transform = prompt_mod.drop_input if name == "question_only" else prompt_mod.blank_input
        cap = []
        orig = scorer_mod.softmax
        scorer_mod.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
        try:
            base.score([transform(r) for r in rows])
        finally:
            scorer_mod.softmax = orig
        return cap, [name] * len(rows)
    raise ValueError(name)


# ---- model scoring --------------------------------------------------------------------------------

def load_with_adapter(model_path, adapter, device):
    """Model of record for a tuned arm: bf16 base + the UNMERGED LoRA adapter (peft at run time). Returns (model, tokenizer)."""
    import torch
    import transformers
    from peft import PeftModel
    if device.startswith("npu"):
        import torch_npu  # noqa: F401
    tok = transformers.AutoTokenizer.from_pretrained(model_path)
    base = transformers.AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.bfloat16)
    pm = PeftModel.from_pretrained(base, adapter)          # LoRA tensors stay fp32 (peft default); never merged
    n_lora = sum(1 for n, _ in pm.named_parameters() if "lora_A" in n)
    assert n_lora > 0, "adapter has no LoRA tensors"
    print(f"loaded base + unmerged adapter {adapter}: {n_lora} LoRA pairs", flush=True)
    return pm.to(device).eval(), tok


def score_model(model_path, rows, device, chunk=32, token_budget=1, scorer_kind="hf", adapter=None):
    if scorer_kind == "rightpad":
        return score_rightpad(model_path, rows, device, chunk, token_budget, adapter)
    if adapter:
        m, t = load_with_adapter(model_path, adapter, device)
        sc = scorer_mod.HFScorer(model_path, device=device, dtype="bfloat16", token_budget=token_budget, model=m, tokenizer=t)
    else:
        sc = scorer_mod.HFScorer(model_path, device=device, dtype="bfloat16", token_budget=token_budget)
    raw = []
    for i in range(0, len(rows), chunk):
        batch = rows[i:i + chunk]
        cap = []
        orig = scorer_mod.softmax
        scorer_mod.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
        try:
            sc.score(batch)
        finally:
            scorer_mod.softmax = orig
        raw.extend(cap)
        print(f"  scored {min(i + chunk, len(rows))}/{len(rows)}", flush=True)
    return raw


def score_rightpad(model_path, rows, device, chunk=32, token_budget=12000, adapter=None):
    """Candidate scorer: one row per candidate, RIGHT padded, logits gathered at the scored positions (train_r3.row_logprob_sums)."""
    import torch
    import transformers
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import train_r3 as T
    import torch_npu  # noqa: F401
    if adapter:
        pm, tok = load_with_adapter(model_path, adapter, device)
        model = pm.base_model.model          # the causal LM with the (unmerged) LoRA layers in place
    else:
        tok = transformers.AutoTokenizer.from_pretrained(model_path)
        model = transformers.AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.bfloat16, attn_implementation="sdpa").to(device).eval()
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    raw = []
    for i in range(0, len(rows), chunk):
        seqs, starts, owner = [], [], []
        for j, r in enumerate(rows[i:i + chunk]):
            p = prompt_mod.build_prompt(r, "record_name")
            pre = tok(p.text, add_special_tokens=False)["input_ids"]
            for c in p.candidates:
                cid = tok(c, add_special_tokens=False)["input_ids"]
                seqs.append(pre + cid)
                starts.append(len(pre))
                owner.append(j)
        with torch.no_grad():
            s = T.row_logprob_sums(torch, model, seqs, starts, pad, device, autocast=False, micro_tokens=token_budget).float().cpu().tolist()
        per = {}
        for o, v in zip(owner, s):
            per.setdefault(o, []).append(v)
        raw.extend(per[j] for j in range(len(rows[i:i + chunk])))
        print(f"  scored {min(i + chunk, len(rows))}/{len(rows)}", flush=True)
    return raw


# ---- metrics (sec 4) ------------------------------------------------------------------------------

def argmax_first(scores):
    """numpy argmax convention: first maximal index wins (sec 4.2)."""
    best_i, best_v = 0, scores[0]
    for i, v in enumerate(scores):
        if v > best_v:
            best_i, best_v = i, v
    return best_i


def is_tie(scores):
    m = max(scores)
    return sum(1 for s in scores if s == m) >= 2


def track_k_metrics(rows, raw_scores):
    """Kev-rule headline (sec 4.1), R0-rule accuracy, tie count, per-source n (sec 4.1, 4.2)."""
    n = len(rows)
    correct_kev = correct_r0 = ties = 0
    by_source = defaultdict(lambda: {"n": 0, "correct_kev": 0, "correct_r0": 0, "ties": 0})
    for row, s in zip(rows, raw_scores):
        gi = gold_index(row)
        pred = argmax_first(s)
        tie = is_tie(s)
        ck = int(pred == gi)
        cr = int(pred == gi and not tie)
        correct_kev += ck
        correct_r0 += cr
        ties += int(tie)
        b = by_source[row["source"]]
        b["n"] += 1
        b["correct_kev"] += ck
        b["correct_r0"] += cr
        b["ties"] += int(tie)
    return {
        "n": n,
        "kev_rule_accuracy": correct_kev / n if n else None,
        "r0_rule_accuracy": correct_r0 / n if n else None,
        "tie_count": ties,
        "by_source": {k: {"n": v["n"], "kev_rule_accuracy": v["correct_kev"] / v["n"],
                           "r0_rule_accuracy": v["correct_r0"] / v["n"], "tie_count": v["ties"]}
                      for k, v in sorted(by_source.items())},
    }


def gold_position_distribution(rows):
    c = Counter(gold_index(r) for r in rows)
    return {str(k): v for k, v in sorted(c.items())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-path", required=True, help="HF dir, or one of: " + ", ".join(DEGENERATE))
    ap.add_argument("--suite", default="decision-v7", choices=("decision-v7", "transfer-v4"))
    ap.add_argument("--split", default="dev", choices=("train", "calibration", "dev", "test"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="npu")
    ap.add_argument("--chunk", type=int, default=32)
    ap.add_argument("--token-budget", type=int, default=1, help="HFScorer token budget; 1 = one row per forward, exact (default)")
    ap.add_argument("--scorer", choices=("hf", "rightpad"), default="hf")
    ap.add_argument("--adapter", default=None, help="LoRA adapter dir: score base (--model-path) + UNMERGED adapter (the model of record)")
    ap.add_argument("--read-test", action="store_true")
    ap.add_argument("--inner-model-path", default=None, help="for question_only/empty_input: the model those transforms are applied to")
    a = ap.parse_args()

    if a.split == "test" and not a.read_test:
        raise SystemExit("refusing to read a test partition without --read-test (sec 8.4)")
    if a.read_test:
        # sec 8.4: the scorer refuses a test partition unless the model is named in FINAL.json;
        # no FINAL.json exists for this round yet (no arm has been adopted), so always refuse.
        raise SystemExit("sec 8.4: no FINAL.json for this round yet; test partitions stay locked")

    rows, path = load_rows(a.suite, a.split, a.limit)
    os.makedirs(a.out, exist_ok=True)

    if a.model_path in DEGENERATE:
        train_rows = None
        if a.model_path == "constant":
            train_rows, _ = load_rows("decision-v7", "train")
        raw, tiers = score_degenerate(a.model_path, rows, train_rows=train_rows,
                                       inner_model_path=a.inner_model_path, device=a.device, adapter=a.adapter)
        model_desc = {"kind": "degenerate", "name": a.model_path, "inner_model_path": a.inner_model_path}
    else:
        raw = score_model(a.model_path, rows, a.device, a.chunk, a.token_budget, a.scorer, a.adapter)
        tiers = None
        model_desc = {"kind": "model", "model_path": a.model_path, "adapter": a.adapter}

    metrics = track_k_metrics(rows, raw)
    report = {
        "header": {"utc": utc(), "suite": a.suite, "split": a.split, "n": len(rows), "task_file": path,
                   "model": model_desc, "prompt_version": prompt_mod.PROMPT_VERSION,
                   "declared_differences_from_kev": "see R3-SFT-PREREG sec 3.3",
                   "scorer": a.scorer, "token_budget": a.token_budget},
        "gold_position_distribution": gold_position_distribution(rows),
        "track_k": metrics,
    }
    with open(os.path.join(a.out, "readouts.jsonl"), "w", encoding="utf-8") as f:
        for row, s in zip(rows, raw):
            f.write(json.dumps({"k": row["kev"]["id"] + "/" + str(row["kev"]["qindex"]), "source": row["source"],
                                 "s": s, "gold_index": gold_index(row), "argmax": argmax_first(s),
                                 "tie": is_tie(s)}) + "\n")
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print(json.dumps(metrics, indent=1)[:2000])
    print(f"report: {os.path.join(a.out, 'report.json')}")


if __name__ == "__main__":
    main()
