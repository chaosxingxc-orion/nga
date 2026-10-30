"""Pre-number checks (R3-SFT-PREREG sec 10.4), as code that runs before the first number of each model.

    (a) constant + uniform first, and the gold-position distribution per suite and partition; in decision-v7 train the gold is
        at position 0 on 5,416 of 15,576 questions.
    (b) for one record per source, the rendered prompts of the clean, permuted and both NOTA variants are hashed and all differ.
    (c) for 20 rows, the stored argmax is recomputed from the stored s_i.
    (pre-training) for 20 train records, the sec 3.4 augmentation output is byte-identical to Kev's own functions called directly.

Every check writes its result into <run_dir>/prechecks/<name>.json and a failure raises PrecheckFailure after writing
<run_dir>/prechecks/FAILED (the caller aborts the run).
"""
import os as _os
import sys as _sys

if _os.path.dirname(_os.path.abspath(__file__)) not in _sys.path:   # python3 -P does not put the script directory on sys.path
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ast
import hashlib
import json
import os
import random

import core_r3 as C
import degenerate_r3 as D
import prompt as P            # R0 prompt.py, the single locked renderer (sec 3.1)

TRAIN_GOLD_POS0 = 5416
TRAIN_N = 15576
N_ARGMAX_ROWS = 20
N_TRAIN_RECORDS = 20


class PrecheckFailure(RuntimeError):
    pass


def _write(run_dir, name, result):
    """Write the result under run_dir (when given) and raise PrecheckFailure if it did not pass."""
    if run_dir:
        d = os.path.join(run_dir, "prechecks")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, sort_keys=True)
    if not result["ok"]:
        if run_dir:
            with open(os.path.join(d, "FAILED"), "a", encoding="utf-8") as f:
                f.write(f"{name}: {result.get('failure')}\n")
        raise PrecheckFailure(f"sec 10.4 check {name} failed: {result.get('failure')}")
    return result


# ---- data integrity: the Kev partitions are the frozen, hash-pinned files of KEV/manifest.json (sec 2.2) -------------------------

def check_kev_manifest(paths, run_dir=None, hashes=None, kev_dir=C.KEV_DIR, name="d_kev_files_vs_manifest"):
    """Every Kev partition file this run reads (clean and variants) must hash to the sha256 in KEV/manifest.json (sec 2.2:
    'verified against KEV/manifest.json'). `hashes` is an optional {path: sha256} cache. Files the manifest does not list fail."""
    man = json.load(open(os.path.join(kev_dir, "manifest.json"), encoding="utf-8"))
    expected = {}
    for suite, entry in man["suites"].items():
        for split, st in entry.get("partitions", {}).items():
            for kind, o in st.get("outputs", {}).items():
                expected[os.path.join(kev_dir, o["path"])] = o["sha256"]
    out = {"clause": "sec 2.2 (data integrity)", "ok": True, "failure": None, "files": {}, "mismatches": []}
    for path in paths:
        got = (hashes or {}).get(path) or C.sha256_file(path)
        want = expected.get(path)
        out["files"][path] = {"sha256": got, "manifest": want}
        if want != got:
            out["mismatches"].append(path)
    if out["mismatches"]:
        out["ok"], out["failure"] = False, f"{len(out['mismatches'])} file(s) do not match KEV/manifest.json: {out['mismatches'][:3]}"
    return _write(run_dir, name, out)


# ---- (a) ----------------------------------------------------------------------------------------------------------------

def check_a(train_rows, partitions, run_dir=None):
    """`partitions`: {"decision-v7/dev": clean rows, ...}. Constant (fitted on `train_rows`) and uniform are computed first;
    the gold-position distribution is reported per partition and for train."""
    fit = D.fit_constant(train_rows)
    out = {"clause": "sec 10.4(a)", "ok": True, "failure": None, "partitions": {}}
    pos0 = sum(1 for r in train_rows if C.gold_index(r) == 0)
    out["train"] = {"n": len(train_rows), "gold_at_position_0": pos0, "gold_position_distribution": C.gold_position_distribution(train_rows)}
    if len(train_rows) == TRAIN_N and pos0 != TRAIN_GOLD_POS0:
        out["ok"], out["failure"] = False, f"decision-v7 train gold at position 0 on {pos0} of {TRAIN_N}, prereg says {TRAIN_GOLD_POS0}"
    for name, rows in partitions.items():
        cs, tiers = D.score_constant(fit, rows)
        us = D.score_uniform(rows)
        const, uni = C.headline(rows, cs), C.headline(rows, us)
        share0 = (sum(1 for r in rows if C.gold_index(r) == 0) / len(rows)) if rows else None
        entry = {"n": len(rows), "gold_position_distribution": C.gold_position_distribution(rows),
                 "constant": {**{k: const[k] for k in ("n", "kev_rule_accuracy", "r0_rule_accuracy", "tie_count")}, "tier_usage": tiers},
                 "uniform": {**{k: uni[k] for k in ("n", "kev_rule_accuracy", "r0_rule_accuracy", "tie_count")}},
                 "share_gold_at_position_0": share0, "flags": []}
        if rows and uni["kev_rule_accuracy"] != share0:    # sec 5.4: under sec 4.2 uniform picks position 0 on every row
            out["ok"], out["failure"] = False, f"{name}: uniform headline {uni['kev_rule_accuracy']} != share of gold at position 0 {share0}"
        if rows and uni["tie_count"] != len(rows):
            out["ok"], out["failure"] = False, f"{name}: uniform arm has {len(rows) - uni['tie_count']} rows that are not ties"
        for arm in ("constant", "uniform"):
            for key in ("kev_rule_accuracy", "r0_rule_accuracy"):
                if entry[arm][key] in (0.0, 1.0):
                    entry["flags"].append(f"{arm}.{key} is exactly {entry[arm][key]} (CLAUDE.md sec 7.1: explain before reporting)")
        out["partitions"][name] = entry
    return _write(run_dir, "a_constant_uniform_gold_position", out)


# ---- (b) ----------------------------------------------------------------------------------------------------------------

def prompt_hash(row):
    return hashlib.sha256(P.build_prompt(row, "record_name").text.encode("utf-8")).hexdigest()


def check_b(clean_rows, variant_rows, run_dir=None, name="b_prompt_hashes"):
    """For one record per source (the first parent, in file order, that has a `permuted` variant whose option order differs
    from its parent's AND both NOTA variants), hash the rendered prompts of the four rows; all four hashes must differ.
    A source with no variants in the partition, or no such parent, is listed (not a failure: there is nothing to compare)."""
    parents = {C.kev_key(r): r for r in clean_rows}
    by_parent = {}
    for v in variant_rows:
        by_parent.setdefault(C.parent_key(v), {})[v["variant"]] = v
    chosen = {}
    for r in clean_rows:                                   # file order
        if r["source"] in chosen:
            continue
        d = by_parent.get(C.kev_key(r))
        if d and all(k in d for k in C.KEV_VARIANTS) and C.level_ids(d["permuted"]) != C.level_ids(r):
            chosen[r["source"]] = (r, d)
    sources = sorted({r["source"] for r in clean_rows})
    with_variants = {C.parent_key(v) for v in variant_rows}
    has_var = {parents[k]["source"] for k in with_variants if k in parents}
    out = {"clause": "sec 10.4(b)", "ok": True, "failure": None, "records": {},
           "sources_without_variants_in_partition": [s for s in sources if s not in has_var],
           "no_eligible_parent": [s for s in sources if s in has_var and s not in chosen]}
    for src, (r, d) in sorted(chosen.items()):
        hashes = {"clean": prompt_hash(r), **{v: prompt_hash(d[v]) for v in C.KEV_VARIANTS}}
        distinct = len(set(hashes.values())) == len(hashes)
        out["records"][src] = {"parent": C.kev_key(r), "hashes": hashes, "all_distinct": distinct}
        if not distinct:
            out["ok"], out["failure"] = False, f"{src}: rendered prompt hashes collide: {hashes}"
    if not chosen:
        out["ok"], out["failure"] = False, "no source has a parent with all three variants and a changed option order"
    return _write(run_dir, name, out)


# ---- (c) ----------------------------------------------------------------------------------------------------------------

def check_c(readouts_path, n=N_ARGMAX_ROWS, run_dir=None, name="c_argmax_recompute"):
    """Read the STORED readouts back from disk and recompute, for `n` rows spread evenly over the file, the argmax (first
    maximal index, derived here with a sort so it is not the same code path as core_r3.argmax_first), the tie flag and the
    gold index from the stored `s`, `ids`, `gold`; every stored value must agree."""
    rows = C.read_jsonl(readouts_path)
    out = {"clause": "sec 10.4(c)", "ok": True, "failure": None, "readouts": readouts_path, "n_rows_in_file": len(rows),
           "n_checked": 0, "mismatches": []}
    if not rows:
        out["ok"], out["failure"] = False, "readouts file is empty"
        return _write(run_dir, name, out)
    take = sorted({(i * len(rows)) // min(n, len(rows)) for i in range(min(n, len(rows)))})
    for i in take:
        r = rows[i]
        s = r["s"]
        top = sorted(range(len(s)), key=lambda j: (-s[j], j))
        arg = top[0]
        tie = len(s) > 1 and s[top[0]] == s[top[1]]
        gi = r["ids"].index(r["gold"])
        out["n_checked"] += 1
        bad = [k for k, ok in (("argmax", arg == r["argmax"]), ("tie", tie == r["tie"]), ("gold_index", gi == r["gold_index"])) if not ok]
        if bad:
            out["mismatches"].append({"row": i, "k": r["k"], "fields": bad})
    if out["mismatches"]:
        out["ok"], out["failure"] = False, f"{len(out['mismatches'])} of {out['n_checked']} rows disagree with their stored s_i"
    return _write(run_dir, name, out)


# ---- pre-training: sec 3.4 augmentation against Kev's own functions -----------------------------------------------------

def load_kev_functions(kev_repo=C.KEV_REPO):
    """Kev's source_seed / augment / none_pair / NONE_OPTIONS / DISTRACTORS taken from kev/data.py of the pinned repository
    by AST (kev.data itself needs `datasets`), so the reference is Kev's own code, not a copy of ours."""
    path = os.path.join(kev_repo, "kev", "data.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("source_seed", "augment", "none_pair"):
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("NONE_OPTIONS", "DISTRACTORS") for t in node.targets):
            keep.append(node)
    ns = {"random": random, "hashlib": hashlib}
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    missing = {"source_seed", "augment", "none_pair", "NONE_OPTIONS", "DISTRACTORS"} - set(ns)
    if missing:
        raise PrecheckFailure(f"could not extract {sorted(missing)} from {path}")
    return ns


def kev_record_variants(ns, req, seed, epoch, p_none=0.1, p_none_distract=0.12, p_distract=0.15, p_none_pair=0.25):
    """kev/train.py record_variants with pairs=None, run on Kev's own functions (the sec 3.4 recipe)."""
    rng = random.Random(ns["source_seed"](seed, f"{epoch}:{req['_meta']['id']}"))
    variants = [ns["augment"](req, rng, p_none=p_none, p_none_distract=p_none_distract, p_distract=p_distract)]
    if p_none_pair > 0 and rng.random() < p_none_pair:
        variants += ns["none_pair"](req, rng)
    return variants


_CK = []


def _convert_kev_module():
    """r1_code/convert_kev.py, loaded by path (stdlib-only module): its `render` is how a Kev description (str, dict or list)
    becomes the text of a converted row, so the comparison must apply the same function to Kev's output."""
    if _CK:
        return _CK[0]
    import importlib.util
    spec = importlib.util.spec_from_file_location("convert_kev", os.path.join(os.path.dirname(C.R0_CODE), "r1_code", "convert_kev.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _CK.append(mod)
    return mod


def _crit_item(desc):
    return None if desc is None or desc == "" else _convert_kev_module().render(desc)


def serialize_kev(variants):
    """Canonical bytes of what Kev's functions produced: per variant, per question (id, type, ordered (key, description)
    pairs, label)."""
    out = []
    for v in variants:
        qs = []
        for qid, q in v["questions"].items():
            crit = [[k, _crit_item(d)] for k, d in q["criteria"].items()] if q["type"] == "choice" else None
            qs.append([qid, q["type"], crit, q["label"]])
        out.append(qs)
    return C.canonical_json(out).encode("utf-8")


def serialize_ours(rows_out, n_main):
    """The same canonical form from the converted rows kev_aug.augment_record returned: the first `n_main` are the augmented
    record (one variant), the rest are the pair siblings (one question each)."""
    def q_of(r):
        crit = None
        if r["kev"]["qtype"] == "choice":
            crit = [[l["id"], None if l["shown"] == l["name"] else l["definition"]] for l in r["levels"]]
        gold = r["gold"]
        if r["kev"]["qtype"] == "noul":
            gold = gold == "true"
        elif r["kev"]["qtype"] == "score":
            gold = int(gold)
        return [r["qname"], r["kev"]["qtype"], crit, gold]
    variants = [[q_of(r) for r in rows_out[:n_main]]] + [[q_of(r)] for r in rows_out[n_main:]]
    return C.canonical_json(variants).encode("utf-8")


def check_train_augmentation(run_dir=None, seeds=(2,), epochs=(0, 1), n_records=N_TRAIN_RECORDS,
                             raw_train=C.KEV_RAW_TRAIN, converted_train=None, kev_repo=C.KEV_REPO, aug_module=None,
                             name="pretrain_aug_byte_identical"):
    """Before the first training step (sec 10.4): for `n_records` train records spread evenly over decision-v7 train, the
    kev_aug.augment_record output must be byte-identical to Kev's own functions, for each seed and epoch given.
    `aug_module` lets a test substitute a deliberately wrong implementation."""
    if aug_module is None:
        import kev_aug as aug_module
    converted_train = converted_train or os.path.join(C.KEV_DIR, "decision-v7", "train.jsonl")
    ns = load_kev_functions(kev_repo)
    raw = C.read_jsonl(raw_train)
    conv = C.read_jsonl(converted_train)
    by_line = {}
    for r in conv:
        by_line.setdefault(r["kev"]["line"], []).append(r)
    take = sorted({(i * len(raw)) // n_records for i in range(n_records)})
    out = {"clause": "sec 10.4 (pre-training), sec 3.4", "ok": True, "failure": None, "kev_repo": kev_repo,
           "n_records": len(take), "seeds": list(seeds), "epochs": list(epochs), "comparisons": 0, "mismatches": [],
           "branches_exercised": {}, "pairs_exercised": 0}
    for idx in take:
        rec = raw[idx]
        rows = by_line[idx + 1]                       # converted rows carry the 1-based physical line number
        if rows[0]["kev"]["id"] != rec["_meta"]["id"]:
            out["ok"], out["failure"] = False, f"record {idx}: raw and converted ids disagree"
            continue
        for seed in seeds:
            for epoch in epochs:
                theirs = serialize_kev(kev_record_variants(ns, rec, seed, epoch))
                rows_out = aug_module.augment_record(rows, seed, epoch)
                ours = serialize_ours(rows_out, len(rows))
                out["comparisons"] += 1
                if theirs != ours:
                    out["mismatches"].append({"record": rec["_meta"]["id"], "seed": seed, "epoch": epoch,
                                              "kev_sha256": hashlib.sha256(theirs).hexdigest(), "ours_sha256": hashlib.sha256(ours).hexdigest()})
                for r in rows_out[:len(rows)]:
                    mode = (r["kev"].get("aug") or {}).get("mode")
                    if mode:
                        out["branches_exercised"][mode] = out["branches_exercised"].get(mode, 0) + 1
                out["pairs_exercised"] += int(len(rows_out) > len(rows))
    if out["mismatches"]:
        out["ok"], out["failure"] = False, f"{len(out['mismatches'])} of {out['comparisons']} comparisons are not byte-identical"
    return _write(run_dir, name, out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Before the first training step (sec 10.4): sec 3.4 augmentation byte-identical to Kev's own functions on 20 train records.")
    ap.add_argument("--out", required=True, help="run directory; the result goes to <out>/prechecks/pretrain_aug_byte_identical.json")
    ap.add_argument("--seeds", default="2,3")
    ap.add_argument("--epochs", default="0,1")
    a = ap.parse_args()
    res = check_train_augmentation(a.out, seeds=tuple(int(x) for x in a.seeds.split(",")), epochs=tuple(int(x) for x in a.epochs.split(",")))
    print(json.dumps({k: res[k] for k in ("ok", "n_records", "comparisons", "branches_exercised", "pairs_exercised")}))
