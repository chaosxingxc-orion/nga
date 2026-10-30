"""R0-configuration fp32 re-score: completeness + provenance verification of a finished run.   python3 -P r0rescore_verify.py --run <run dir>

The run is the R0 side of record (R3 sec 14.5 item 1, sec 8.2 (c) gating cells). It is accepted only if, for EVERY role (primary, empty_input, question_only):
  (1) the readout keys equal records_needed(R0) exactly (no key missing, none extra, none twice): 102,654 per role on the full task files;
  (2) provenance_r3.verify passes (model sha recomputed from the weights on disk, per-file manifest sha256 and row counts, per-row stamp, scorer of record);
  (3) the report.json it produced is track_t_config r0, arm K0, record-grade scorer, HF32 off.
Writes <run>/R0RESCORE_VERIFIED.json (exit 0) or <run>/R0RESCORE_REFUSED.json (exit 1). Partial-with-a-note does not exist: a refusal is the only other outcome.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import core_r3 as C            # noqa: E402
import provenance_r3 as PV     # noqa: E402
import testlock_r3 as TL       # noqa: E402
import track_t_r3 as T         # noqa: E402
import common as RC            # noqa: E402

ROLES = ("primary", "empty_input", "question_only")
R0_MODEL = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B"


def utc():
    return C.utc_now()


def check_executed_code(run):
    """The code that executes must be the code that was hashed: every line of <run>/SHA1SUMS is recomputed. Entries are the snapshot files <run>/code/<f> and the live
    r0_code / r1_code files the snapshot imports (core_r3 puts r0_code on sys.path, so those run LIVE; this is how a mid-run edit of them is caught)."""
    import hashlib
    probs = []
    path = os.path.join(run, "SHA1SUMS")
    if not os.path.exists(path):
        return [f"no SHA1SUMS in {run}"]
    live = {"r0_code": "/mnt/cephfs/xingchao/experiments/jev/r0_code", "r1_code": "/mnt/cephfs/xingchao/experiments/jev/r1_code"}
    n = 0
    for line in open(path):
        if not line.strip():
            continue
        want, name = line.split(None, 1)
        name = name.strip()
        head, _, rest = name.partition("/")
        p = os.path.join(live[head], rest) if head in live and rest else os.path.join(run, "code", name)
        n += 1
        try:
            got = hashlib.sha1(open(p, "rb").read()).hexdigest()
        except OSError as e:
            probs.append(f"{name}: unreadable ({e})")
            continue
        if got != want:
            probs.append(f"{name}: sha1 {got[:12]} != recorded {want[:12]}")
    if n == 0:
        probs.append("SHA1SUMS is empty")
    if not any(l.split(None, 1)[1].strip().startswith("r0_code/") for l in open(path) if l.strip()):
        probs.append("SHA1SUMS records no r0_code file")
    return probs


def check(run, model_dir="instruct", model_path=R0_MODEL, limit_groups=0, expected_sha=None, require_scorer=True, check_report=True, data_root=C.DATA_ROOT, check_code=True):
    out = os.path.join(run, model_dir)
    problems = []
    records = []
    for task in ("T1", "T2", "T3"):
        for src in RC.SOURCE_FILES:
            p = RC.task_path(data_root, task, src)
            if task == "T3" and not os.path.exists(p):
                continue
            recs = RC.load_records(p)
            records += T.limit_groups(recs, limit_groups) if limit_groups else recs
    need = {r["key"] for r in T.records_needed(records, T.CONFIG_R0)}
    rdir = os.path.join(out, "trackt", "readouts")
    per_role = {r: [] for r in ROLES}
    for fn in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        role = fn.split("__")[0]
        if role in per_role and fn.endswith(".jsonl"):
            per_role[role] += [x["k"] for x in C.read_jsonl(os.path.join(rdir, fn))]
    counts = {}
    for role, ks in per_role.items():
        have = set(ks)
        missing, extra = sorted(need - have), sorted(have - need)
        counts[role] = {"rows": len(ks), "distinct": len(have), "needed": len(need), "missing": len(missing), "extra": len(extra), "duplicated": len(ks) - len(have)}
        if missing or extra or len(ks) != len(have):
            problems.append(f"role {role}: {len(have & need)} of {len(need)} records_needed(R0) keys; missing {len(missing)} (e.g. {missing[:3]}), extra {len(extra)} (e.g. {extra[:3]}), duplicated {len(ks) - len(have)}")
    prov = None
    try:
        sha = expected_sha or TL.model_identity(model_path, None, C.ROUND_DIR)["sha256"]
        prov = PV.verify(out, rdir, sha, require_scorer_of_record=require_scorer)
    except PV.ProvenanceRefusal as e:
        problems.append(str(e))
    rep = {}
    if check_report:
        rp = os.path.join(out, "report.json")
        if not os.path.exists(rp):
            problems.append("no report.json: the report stage did not run")
        else:
            rep = json.load(open(rp, encoding="utf-8"))
            tt = rep.get("track_t") or {}
            h = rep.get("header", {})
            sc = h.get("scorer", {}) if isinstance(h.get("scorer"), dict) else {}
            if tt.get("config") != "r0":
                problems.append(f"report.json track_t config is {tt.get('config')!r}, not 'r0'")
            if h.get("arm") != "K0":
                problems.append(f"report.json arm is {h.get('arm')!r}")
            if require_scorer and (sc.get("record_grade") is not True or (sc.get("hf32") or {}).get("hf32") is not False):
                problems.append(f"report.json scorer descriptor is not the scorer of record: {sc}")
            if tt.get("missing_roles"):
                problems.append(f"report.json missing roles {tt['missing_roles']}")
    if check_code:        # tests with a throw-away run dir have no SHA1SUMS and pass check_code=False
        problems += [f"executed code: {x}" for x in check_executed_code(run)]
    doc = {"utc": utc(), "run": run, "records_needed_R0": len(need), "per_role": counts, "provenance": prov, "problems": problems}
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--limit-groups", type=int, default=0, help="dry runs only")
    ap.add_argument("--expected-model-sha256", default=None, help="tests only")
    ap.add_argument("--no-scorer-check", action="store_true", help="tests only (mock scorer)")
    ap.add_argument("--no-code-check", action="store_true", help="tests only (no SHA1SUMS)")
    ap.add_argument("--model-dir", default="instruct")
    ap.add_argument("--model-path", default=R0_MODEL)
    a = ap.parse_args()
    doc = check(a.run, a.model_dir, a.model_path, a.limit_groups, a.expected_model_sha256, not a.no_scorer_check, check_code=not a.no_code_check)
    ok = not doc["problems"]
    for stale in ("R0RESCORE_VERIFIED.json", "R0RESCORE_REFUSED.json"):
        if os.path.exists(os.path.join(a.run, stale)):
            os.replace(os.path.join(a.run, stale), os.path.join(a.run, stale + ".prev-" + utc()))
    with open(os.path.join(a.run, "R0RESCORE_VERIFIED.json" if ok else "R0RESCORE_REFUSED.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    print(json.dumps({"ok": ok, "per_role": doc["per_role"], "problems": [p[:300] for p in doc["problems"]]}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
