"""Readout provenance (R3 sec 14.5 item 1 (ii), added 2026-10-30 after the erratum loader was found to accept another model's readouts).

What went wrong, and what this module is for. `harness_identity_r3.erratum()` used to gate its fp32 side on `RUN_IDENTITY.json`, a file the run itself
writes, and never looked inside the readout files. A directory of the Base model's readouts next to a RUN_IDENTITY.json naming the R0 model was
accepted and differenced (probe: `r3_runs/k0_fp32/analysis/k0_reuse_probe.py`; argmax_changed 142 / 210 / 203, max probability gap 0.79). A gate whose
only evidence is written by the thing being gated is no gate. So provenance now lives in three places that an accident cannot reproduce together:

  1. every readout ROW produced by `full_eval_r3` carries `"m"`, the first 16 hex of the sha256 of the model that produced it (stamp);
  2. every producing process writes `manifests/<unit tag or main>.json`: per readout file its sha256 and row count, the full model sha256 and the scorer
     descriptor (mode, dtype, hf32, token_budget, record_grade);
  3. the consumer computes the EXPECTED model sha256 itself from the weights on disk (testlock_r3.model_identity), not from RUN_IDENTITY.json, and
     `verify()` requires: RUN_IDENTITY's model sha == expected, every readout file listed in a manifest with matching sha256 and row count, the manifest's
     model sha == expected, the manifest's scorer is the scorer of record, every row stamped with the expected model, and no key twice in a role.

Limit, stated: this defends against ACCIDENT (a wrong directory, a copy, a stale shard layout, a partial run, a different scorer). It does not defend against
someone who deliberately rewrites rows, manifests and RUN_IDENTITY together; nothing on a shared filesystem can.
"""
import hashlib
import json
import os

STAMP = "m"
STAMP_LEN = 16
MANIFEST_DIR = "manifests"


class ProvenanceRefusal(RuntimeError):
    pass


def stamp(row, model_sha256):
    """Mark a readout row with the model that produced it. Returns the row."""
    if model_sha256:
        row[STAMP] = model_sha256[:STAMP_LEN]
    return row


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path):
    with open(path, "rb") as f:
        return sum(1 for line in f if line.strip())


def write_unit_manifest(run_dir, tag, model_sha256, scorer_desc, paths, utc=""):
    """Manifest of the readout files one producing process wrote or resumed. Atomic. Returns its path."""
    d = os.path.join(run_dir, MANIFEST_DIR)
    os.makedirs(d, exist_ok=True)
    files = {}
    for p in sorted(set(paths)):
        if os.path.exists(p):
            files[os.path.relpath(p, run_dir)] = {"sha256": sha256_file(p), "rows": count_rows(p)}
    doc = {"model_sha256": model_sha256, "stamp": model_sha256[:STAMP_LEN], "scorer": scorer_desc, "utc": utc, "tag": tag or "main", "files": files}
    path = os.path.join(d, (tag or "main") + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return path


def _scorer_problems(desc):
    p = []
    if not isinstance(desc, dict):
        return ["no scorer descriptor in the manifest"]
    if desc.get("record_grade") is not True:
        p.append(f"scorer is not record grade ({desc.get('record_grade_problems')})")
    for k, want in (("mode", "rightpad"), ("dtype", "float32"), ("token_budget", 16384)):
        if desc.get(k) != want:
            p.append(f"scorer {k} = {desc.get(k)!r}, scorer of record has {want!r}")
    hf = desc.get("hf32")
    if not isinstance(hf, dict) or hf.get("hf32") is not False:
        p.append(f"HF32 not recorded as off ({hf})")
    return p


def verify(run_dir, readouts_dir, expected_model_sha256, require_scorer_of_record=True, role_of=None):
    """Raise ProvenanceRefusal unless every readout file in `readouts_dir` provably comes from the model `expected_model_sha256`.
    At least one file and one verified row are required. Consumers must separately enforce the expected question population.
    `readouts_dir` may be a directory or a list of directories (all manifests are checked).
    `role_of(relative_path) -> role` groups files for duplicate checks; default uses the basename before '__'. Returns a summary dict."""
    directories = [os.fspath(d) for d in readouts_dir] if isinstance(readouts_dir, (list, tuple)) else [os.fspath(readouts_dir)]
    problems = []
    rid_path = os.path.join(run_dir, "RUN_IDENTITY.json")
    rid = {}
    if os.path.exists(rid_path):
        with open(rid_path, encoding="utf-8") as f:
            rid = json.load(f)
    if rid.get("model_sha256") != expected_model_sha256:
        problems.append(f"RUN_IDENTITY.json model_sha256 {str(rid.get('model_sha256'))[:12]} != the sha256 recomputed from the weights on disk {expected_model_sha256[:12]}")
    mdir = os.path.join(run_dir, MANIFEST_DIR)
    entries, manifests = {}, {}
    for fn in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(mdir, fn), encoding="utf-8") as f:
            m = json.load(f)
        manifests[fn] = {"tag": m.get("tag"), "scorer": m.get("scorer"), "model_sha256": m.get("model_sha256"), "files": len(m.get("files", {}))}
        if m.get("model_sha256") != expected_model_sha256:
            problems.append(f"manifest {fn}: model_sha256 {str(m.get('model_sha256'))[:12]} != expected {expected_model_sha256[:12]}")
        if require_scorer_of_record:
            problems += [f"manifest {fn}: {x}" for x in _scorer_problems(m.get("scorer"))]
        for rel, e in m.get("files", {}).items():
            if rel in entries and entries[rel] != e:
                problems.append(f"{rel}: conflicting producer manifests")
            entries[rel] = e
    if not manifests:
        problems.append(f"no manifest under {mdir}: the readouts have no producing run's record (copied or seeded files are refused)")
    files = sorted({os.path.join(d, f) for d in directories if os.path.isdir(d)
                    for f in os.listdir(d) if f.endswith(".jsonl")})
    if not files:
        problems.append("no readout files: provenance cannot verify an absent or empty result")
    stamp_want = expected_model_sha256[:STAMP_LEN]
    n_rows = n_unstamped = n_wrong = 0
    seen = {}
    dup = []
    for path in files:
        fn = os.path.basename(path)
        rel = os.path.relpath(path, run_dir)
        e = entries.get(rel)
        if e is None:
            problems.append(f"{rel}: not listed in any manifest")
            continue
        if sha256_file(path) != e["sha256"]:
            problems.append(f"{rel}: sha256 differs from its manifest (the file changed after its producer closed it)")
            continue
        role = role_of(os.path.relpath(path, run_dir)) if role_of else fn.split("__")[0]
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        if len(rows) != e["rows"]:
            problems.append(f"{rel}: {len(rows)} rows, manifest says {e['rows']}")
        for r in rows:
            n_rows += 1
            if r.get(STAMP) is None:
                n_unstamped += 1
            elif r[STAMP] != stamp_want:
                n_wrong += 1
            k = (role, r.get("k"))
            if k in seen:
                dup.append((k, seen[k], rel))
            seen[k] = rel
    if n_rows == 0:
        problems.append("no readout rows verified: empty evidence is not a verified result")
    if n_unstamped:
        problems.append(f"{n_unstamped} of {n_rows} rows carry no model stamp (produced before provenance stamping, or by a foreign writer)")
    if n_wrong:
        problems.append(f"{n_wrong} of {n_rows} rows are stamped with another model than {stamp_want}")
    if dup:
        problems.append(f"{len(dup)} keys appear twice within a role (e.g. {dup[0]}): two shard layouts or a copy in one directory")
    for rel in sorted(set(entries) - {os.path.relpath(f, run_dir) for f in files}):
        problems.append(f"{rel}: listed in a manifest but absent from {readouts_dir}")
    if problems:
        raise ProvenanceRefusal("readout provenance refused: " + "; ".join(problems[:12]) + (f" (+{len(problems) - 12} more)" if len(problems) > 12 else ""))
    return {"files_verified": len(files), "rows_verified": n_rows, "expected_model_sha256": expected_model_sha256, "manifests": manifests,
            "checked": ["RUN_IDENTITY model sha == sha recomputed from the weights", "per-file sha256 and row count vs manifest", "manifest model sha == expected",
                        "manifest scorer is the scorer of record" if require_scorer_of_record else "scorer not checked", "every row stamped with the expected model",
                        "no key twice within a role"]}
