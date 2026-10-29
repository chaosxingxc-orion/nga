"""Run a scorer over task files, write raw readouts to cephfs, and emit the baseline report.

Full run (real model; all five scorer roles; about 96k items per role):

    python3 -P run_baseline.py --base hf --scorers all --device npu --dtype bfloat16 \\
        --model-path /mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B --image-id <image id>

Smoke run first (a few groups, separate output directory, validates model loading and the readout):

    python3 -P run_baseline.py --base hf --scorers base --limit-groups 5 --tasks T1 --sources typed-decisions \\
        --device npu --model-path <same> --image-id <image id> --out-root /tmp/r0_smoke

Pipeline check without a model: ``--base mock-invariant`` (also mock-name-driven, mock-random, mock-oracle).
Rebuild only the report from existing readouts: add ``--report-only``.

Outputs under --out-root (default on cephfs, never committed):
    readouts/<scorer>__<task>__<source>.jsonl   header line + one raw readout per item
    report.json, report.md                      the pre-registered report

Resumable: a readout file is appended to, items already present (by item key) are skipped, and a
truncated last line from a killed run is dropped.  A resumed run must match the file header
(scorer, model path, task file hash, render mode, group limit) or it refuses to continue.

Sharding: one process per NPU, ``--shard i --num-shards n``; a group goes to shard sha256(group_id)[8:16] % n,
so no group is split. Each shard writes its own readout files; after all finish, merge with the same command
plus ``--report-only`` (duplicate keys across shards are an error, coverage is recorded in the header).
``--sample`` restricts every scorer to a frozen group list (freeze_sample.py).

Inside the CANN container use ``python3 -P``, not ``-I``: ``-I`` drops PYTHONPATH and the operator compiler (tbe)
is found only through it. Both keep the current directory off sys.path. This file adds its own directory (trusted
code) explicitly. The data directory is never added.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common  # noqa: E402
import metrics  # noqa: E402
import prompt as prompt_mod  # noqa: E402
import report as report_mod  # noqa: E402
import scorer as scorer_mod  # noqa: E402
import split as S  # noqa: E402
import thresholds  # noqa: E402

SCORER_CHOICES = ("base", "empty_input", "question_only", "constant", "uniform")
MOCKS = {
    "mock-invariant": scorer_mod.MockScorer.invariant,
    "mock-name-driven": scorer_mod.MockScorer.name_driven,
    "mock-prefix-driven": scorer_mod.MockScorer.prefix_driven,
    "mock-random": scorer_mod.MockScorer.random,
    "mock-oracle": scorer_mod.MockScorer.oracle,
}
HEADER_MATCH_KEYS = ("scorer", "model_path", "task_file_sha256", "render", "limit_groups", "prompt_version",
                     "shard", "num_shards", "sample_sha256")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_info():
    def run(*args):
        return subprocess.run(["git", "-C", HERE, *args], capture_output=True, text=True, check=False).stdout.strip()
    return {"git_commit": run("rev-parse", "HEAD") or "unknown",
            "git_dirty": bool(run("status", "--porcelain", "--", HERE))}


def harness_config():
    return {
        "tau_grid": list(thresholds.TAU_GRID), "min_fit_items": thresholds.MIN_FIT_ITEMS,
        "default_tau": thresholds.DEFAULT_TAU, "split_train_share": 0.70, "ece_bins": metrics.ECE_BINS,
        "swap_eligible_sides": list(metrics.SWAP_ELIGIBLE_SIDES),
    }


def shard_of(group_id, num_shards):
    """Shard index of a group. Hashes ``group_id`` only, so every record of a group (all variants, all
    tasks) lands in one shard. Uses digest bytes 8..16, independent of the train/held-out bucket
    (bytes 0..8, split.py)."""
    if num_shards <= 1:
        return 0
    digest = hashlib.sha256(group_id.encode("utf-8")).digest()
    return int.from_bytes(digest[8:16], "big") % num_shards


def select_shard(recs, shard, num_shards):
    return [r for r in recs if shard_of(r["group_id"], num_shards) == shard]


def load_sample(path):
    """Frozen sample file written by freeze_sample.py: returns (meta dict, {"T1/src": set of group ids | None})."""
    with open(path, "rb") as f:
        raw = f.read()
    doc = json.loads(raw)
    groups = {k: (None if v is None else set(v)) for k, v in doc["groups"].items()}
    meta = {"sample_file": path, "sample_sha256": hashlib.sha256(raw).hexdigest(), "seed": doc.get("seed"),
            "rule": doc.get("rule"), "full": bool(doc.get("full"))}
    return meta, groups


def load_task_files(args, sample=None):
    """{(task, source_file): (path, records)} with an optional deterministic group limit and frozen sample."""
    out = {}
    for task in args.tasks:
        for src in args.sources:
            path = common.task_path(args.data_root, task, src)
            if task == "T3" and not os.path.exists(path):
                continue  # T3 exists for typed-decisions only
            recs = common.load_records(path)
            if sample is not None:
                if f"{task}/{src}" not in sample:
                    raise SystemExit(f"sample file has no entry for {task}/{src}")
                keep = sample[f"{task}/{src}"]
                if keep is not None:  # None means: taken whole
                    recs = [r for r in recs if r["group_id"] in keep]
                    common._assign_tau_versions(recs)
            if args.limit_groups:
                groups = sorted({r["group_id"] for r in recs}, key=lambda g: (S.bucket(g), g))[:args.limit_groups]
                keep = set(groups)
                recs = [r for r in recs if r["group_id"] in keep]
                common._assign_tau_versions(recs)
            out[(task, src)] = (path, recs)
    return out


def build_scorers(args, files):
    """Return {output scorer name: scorer object} for the requested roles."""
    if args.base == "hf":
        base = scorer_mod.HFScorer(args.model_path, device=args.device, dtype=args.dtype, render=args.render,
                                   token_budget=args.token_budget, name="hf")
    else:
        base = MOCKS[args.base]()
    wanted = set(args.scorers.split(",")) if args.scorers != "all" else set(SCORER_CHOICES)
    unknown = wanted - set(SCORER_CHOICES)
    if unknown:
        raise SystemExit(f"unknown scorers {sorted(unknown)}; choose from {SCORER_CHOICES} or 'all'")
    out = {}
    if "base" in wanted:
        out[base.name] = base
    if "empty_input" in wanted:
        s = scorer_mod.EmptyInputScorer(base)
        out[s.name] = s
    if "question_only" in wanted:
        s = scorer_mod.QuestionOnlyScorer(base)
        out[s.name] = s
    if "uniform" in wanted:
        out["uniform"] = scorer_mod.UniformScorer()
    if "constant" in wanted:
        all_recs = [r for _, recs in files.values() for r in recs]
        for splitter in (S.GROUP70, S.QUESTION70):
            relevant = [r for r in all_recs if splitter in S.splitters_for_source(r["source"])]
            if not relevant:
                continue
            c = scorer_mod.ConstantClassifierScorer(splitter.name)
            c.fit(S.TrainView.of(relevant, splitter))  # train side only, by construction
            out[c.name] = c
    return out, base


def readout_path(out_root, scorer_name, task, src, shard=0, num_shards=1):
    safe = scorer_name.replace("@", "_at_").replace("+", "_")
    tail = f"__shard{shard}of{num_shards}" if num_shards > 1 else ""
    return os.path.join(out_root, "readouts", f"{safe}__{task}__{src}{tail}.jsonl")


def open_readouts(path, header):
    """Return (set of finished item keys, append handle). Creates the file with a header if new."""
    done = set()
    if os.path.exists(path):
        good_bytes = 0
        with open(path, "rb") as f:
            first = f.readline()
            old = json.loads(first)["_header"]
            for k in HEADER_MATCH_KEYS:
                if old.get(k) != header.get(k):
                    raise SystemExit(f"{path}: header mismatch on {k!r}: file has {old.get(k)!r}, run has {header.get(k)!r}")
            good_bytes = len(first)
            for line in f:
                try:
                    done.add(json.loads(line)["k"])
                except (ValueError, KeyError):
                    break  # truncated last line of a killed run
                good_bytes += len(line)
        with open(path, "r+b") as f:
            f.truncate(good_bytes)
        return done, open(path, "a", encoding="utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = open(path, "a", encoding="utf-8")
    handle.write(json.dumps({"_header": header}) + "\n")
    handle.flush()
    return done, handle


def score_file(scorer, recs, handle, done, chunk):
    todo = [r for r in recs if r["key"] not in done]
    for i in range(0, len(todo), chunk):
        batch = todo[i:i + chunk]
        for rec, probs in zip(batch, scorer.score(batch)):
            handle.write(json.dumps(common.make_row(rec, probs)) + "\n")
        handle.flush()
    return len(todo)


def load_all_readouts(out_root):
    """{scorer: rows}, {scorer: header}, {scorer: coverage} from every readout file (all shards) in the output dir."""
    rows, headers, coverage = {}, {}, {}
    rdir = os.path.join(out_root, "readouts")
    if not os.path.isdir(rdir):
        return rows, headers, coverage
    for fn in sorted(os.listdir(rdir)):
        if not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(rdir, fn), "r", encoding="utf-8") as f:
            header = json.loads(f.readline())["_header"]
            headers.setdefault(header["scorer"], header)
            bucket = rows.setdefault(header["scorer"], [])
            n_file = 0
            for line in f:
                try:
                    bucket.append(json.loads(line))
                    n_file += 1
                except ValueError:
                    break
            cov = coverage.setdefault(header["scorer"], {"expected": 0, "got": 0, "files": 0})
            cov["expected"] += header.get("n_shard_records", header.get("n_records", 0))
            cov["got"] += n_file
            cov["files"] += 1
    for scorer_name, bucket in rows.items():
        keys = [r["k"] for r in bucket]
        if len(set(keys)) != len(keys):
            raise SystemExit(f"{scorer_name}: duplicate item keys across readout files (overlapping shards?)")
    return rows, headers, coverage


def emit_report(out_root, primary):
    rows, headers, coverage = load_all_readouts(out_root)
    if primary not in rows:
        raise SystemExit(f"no readouts for primary scorer {primary!r} in {out_root}")
    rep = report_mod.build_report(rows, primary)
    ph = headers[primary]
    header = {k: ph.get(k) for k in ("scorer", "model_path", "image_id", "git_commit", "git_dirty", "render", "device",
                                      "dtype", "limit_groups", "prompt_version", "prompt_format", "transformers_version", "python")}
    header["report_utc"] = utc_now()
    header["amendment_level"] = common.AMENDMENT_LEVEL
    header["scorers_present"] = sorted(rows)
    header["rows_per_scorer"] = {k: len(v) for k, v in sorted(rows.items())}
    header["harness_config"] = harness_config()
    header["shard_layout"] = {"num_shards": ph.get("num_shards", 1), "readout_files_per_scorer": {k: v["files"] for k, v in sorted(coverage.items())}}
    header["coverage_expected_vs_got"] = {k: [v["expected"], v["got"]] for k, v in sorted(coverage.items())}
    header["incomplete_scorers"] = sorted(k for k, v in coverage.items() if v["expected"] != v["got"])
    for k in ("sample_file", "sample_sha256", "seed", "rule", "full"):
        if ph.get(k) is not None:
            header[k] = ph[k]
    sample_groups = None
    if ph.get("sample_file") and os.path.exists(ph["sample_file"]):
        with open(ph["sample_file"], "r", encoding="utf-8") as f:
            sample_groups = json.load(f)["groups"]  # full frozen list goes into report.json (pre-reg 8.6)
    with open(os.path.join(out_root, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"header": {**header, "sample_groups": sample_groups}, **rep}, f, indent=1, sort_keys=True)
    md_header = dict(header)
    if sample_groups is not None:
        md_header["sample_groups"] = {k: ("whole" if v is None else f"{len(v)} groups (ids in report.json)")
                                      for k, v in sample_groups.items()}
    with open(os.path.join(out_root, "report.md"), "w", encoding="utf-8") as f:
        f.write(report_mod.render_markdown(rep, md_header))


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="hf", choices=("hf",) + tuple(MOCKS), help="base scorer")
    ap.add_argument("--scorers", default="all", help=f"comma list of {SCORER_CHOICES} or 'all'")
    ap.add_argument("--tasks", default="T1,T2,T3", type=lambda s: s.split(","))
    ap.add_argument("--sources", default=",".join(common.SOURCE_FILES), type=lambda s: s.split(","))
    ap.add_argument("--data-root", default=common.DEFAULT_DATA_ROOT)
    ap.add_argument("--out-root", default=common.DEFAULT_OUT_ROOT)
    ap.add_argument("--model-path", help="HF model directory (required for --base hf)")
    ap.add_argument("--device", default="cpu", help="cpu | npu | npu:N")
    ap.add_argument("--dtype", default="auto", help="auto | float32 | bfloat16 | float16")
    ap.add_argument("--render", default="record_name", choices=("record_name", "neutral"))
    ap.add_argument("--token-budget", type=int, default=16384, help="max padded tokens per forward pass")
    ap.add_argument("--chunk", type=int, default=64, help="items scored and flushed per step")
    ap.add_argument("--image-id", default=os.environ.get("NGA_IMAGE_ID"), help="container image id (or env NGA_IMAGE_ID)")
    ap.add_argument("--limit-groups", type=int, default=0, help="smoke runs: keep only the first N groups (by split hash)")
    ap.add_argument("--shard", type=int, default=0, help="this process's shard index (0-based); one process per NPU")
    ap.add_argument("--num-shards", type=int, default=1, help="split the work by group_id hash into this many shards")
    ap.add_argument("--sample", default=None, help="frozen sample file from freeze_sample.py (whole group ids per task/source)")
    ap.add_argument("--report-only", action="store_true", help="skip scoring, rebuild the report from existing readouts")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not (args.num_shards >= 1 and 0 <= args.shard < args.num_shards):
        raise SystemExit("need 0 <= --shard < --num-shards")
    if args.base == "hf" and not args.report_only:
        if not args.model_path:
            raise SystemExit("--model-path is required for --base hf")
        if not args.image_id:
            raise SystemExit("--image-id (or env NGA_IMAGE_ID) is required for a real-model run")
    primary = "hf" if args.base == "hf" else args.base
    if not args.report_only:
        sample_meta, sample = ({}, None) if not args.sample else load_sample(args.sample)
        files = load_task_files(args, sample)
        scorers, base = build_scorers(args, files)
        info = git_info()
        try:
            import transformers
            tf_version = transformers.__version__
        except ImportError:
            tf_version = None
        for name, sc in scorers.items():
            for (task, src), (path, recs) in files.items():
                if name.startswith("constant@") and S.QUESTION70.name in name and not src.startswith("akhilaaa3"):
                    continue
                targets = select_shard(recs, args.shard, args.num_shards)  # constants were fitted on all of recs
                header = {
                    "scorer": name, "scorer_config": sc.describe(), "model_path": args.model_path if args.base == "hf" else "none (mock)",
                    "image_id": args.image_id or "none (mock)", **info, "utc": utc_now(), "task": task, "source_file": src,
                    "task_file": path, "task_file_sha256": common.file_sha256(path), "n_records": len(recs),
                    "limit_groups": args.limit_groups, "render": args.render,
                    "prompt_version": prompt_mod.PROMPT_VERSION, "prompt_format": prompt_mod.PROMPT_FORMAT, "device": args.device, "dtype": args.dtype,
                    "transformers_version": tf_version, "python": platform.python_version(),
                    "shard": args.shard, "num_shards": args.num_shards, "n_shard_records": len(targets),
                    "sample_sha256": sample_meta.get("sample_sha256"),
                    **{k: sample_meta.get(k) for k in ("sample_file", "seed", "rule", "full")},
                }
                done, handle = open_readouts(readout_path(args.out_root, name, task, src, args.shard, args.num_shards), header)
                t0 = time.time()
                with handle:
                    n = score_file(sc, targets, handle, done, args.chunk)
                dt = time.time() - t0
                print(f"{name:34s} {task} {src:16s} scored {n:7d} skipped {len(done):7d} {dt:8.1f}s {n / dt if dt > 0 else 0:7.2f} items/s",
                      flush=True)
    if args.num_shards > 1 and not args.report_only:
        print(f"shard {args.shard}/{args.num_shards} done; merge with --report-only after every shard has finished")
        return
    emit_report(args.out_root, primary)
    print("report:", os.path.join(args.out_root, "report.md"))


if __name__ == "__main__":
    main()
