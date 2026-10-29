"""Freeze the scoring sample (pre-registration 8.6) BEFORE anything is scored.

Writes one JSON file: {"seed", "rule", "full", "groups": {"T/source": [group ids] | null}}. ``null`` means the
source is taken whole. Whole group_ids are sampled, stratified per (task, source, level_type), with a fixed seed
(sha256(seed|group_id) rank), so the result does not depend on file order. Every scorer uses this one file.

    python3 -P freeze_sample.py --fraction 0.5 --seed 20261029 --out sample.json
    python3 -P freeze_sample.py --full --out sample_full.json
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=common.DEFAULT_DATA_ROOT)
    ap.add_argument("--fraction", type=float, default=1.0)
    ap.add_argument("--fractions", default="", help="per-source override, e.g. openjev-synth=0.1,akhilaaa3=1 (information-weighted cut)")
    ap.add_argument("--whole-sources", default="", help="comma list of task/source taken whole")
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    whole = set(filter(None, a.whole_sources.split(",")))
    frac = {k: float(v) for k, v in (kv.split("=") for kv in filter(None, a.fractions.split(",")))}
    groups, counts = {}, {}
    for task in common.TASKS:
        for src in common.SOURCE_FILES:
            path = common.task_path(a.data_root, task, src)
            if not os.path.exists(path):
                continue
            recs = common.load_records(path)
            key = f"{task}/{src}"
            fr = frac.get(src, a.fraction)
            if a.full or fr >= 1.0 or key in whole:
                groups[key] = None
                counts[key] = {"groups": len({r["group_id"] for r in recs}), "records": len(recs), "taken": "whole"}
                continue
            # a group's stratum is its level_type (constant within a group in these files; checked)
            lt = {}
            for r in recs:
                lt.setdefault(r["group_id"], set()).add(r["level_type"])
            by_stratum = {}
            for g, s in lt.items():
                by_stratum.setdefault(min(s), []).append(g)
            chosen = []
            for stratum, gs in sorted(by_stratum.items()):
                gs.sort(key=lambda g: hashlib.sha256(f"{a.seed}|{src}|{g}".encode()).hexdigest())
                chosen += sorted(gs[:max(1, round(len(gs) * fr))])
            groups[key] = sorted(chosen)
            nrec = sum(1 for r in recs if r["group_id"] in set(chosen))
            counts[key] = {"groups": len(chosen), "of_groups": len(lt), "records": nrec, "taken": f"{fr} stratified by level_type"}
    doc = {"seed": a.seed, "full": bool(a.full or (a.fraction >= 1.0 and not frac)), "fraction": a.fraction, "fractions": frac,
           "rule": "pre-reg 8.6: whole group_ids, fixed seed, stratified per source and level_type, one list for every scorer",
           "counts": counts, "groups": groups}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
