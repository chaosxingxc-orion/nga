"""Host-side tests for the R3 data path (no torch needed). Run: python3 -I test_r3_data.py

Clauses asserted (R3-SFT-PREREG): §3.1 (prompt identical to the evaluation renderer), §7.2 (response = " " + gold
name, one example per question), §3.3 c / open point 13.12 (Kev augmentation reproduced exactly), K1-QO (drop-state).
"""
import ast
import hashlib
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/mnt/cephfs/xingchao/experiments/jev/r0_code")

import build_kev_sft as B  # noqa: E402
import kev_aug as A  # noqa: E402
import prompt as P  # noqa: E402

KEV_DATA = "/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev/kev/data.py"
KEV_TRAIN = "/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites/v7/decision-v7/train.jsonl"
CONV_TRAIN = B.DEFAULT_TRAIN


def load_kev_originals():
    """Extract source_seed / augment / none_pair / NONE_OPTIONS / DISTRACTORS from Kev's own data.py by AST, so the
    comparison runs against Kev's actual code without importing the module (it needs `datasets`)."""
    src = open(KEV_DATA, encoding="utf-8").read()
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("source_seed", "augment", "none_pair"):
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("NONE_OPTIONS", "DISTRACTORS") for t in node.targets):
            keep.append(node)
    assert {getattr(n, "name", None) for n in keep if isinstance(n, ast.FunctionDef)} == {"source_seed", "augment", "none_pair"}
    ns = {"random": random, "hashlib": hashlib}
    exec(compile(ast.Module(body=keep, type_ignores=[]), KEV_DATA, "exec"), ns)
    return ns


def test_constants_and_functions_match_kev_source():
    ns = load_kev_originals()
    assert ns["NONE_OPTIONS"] == A.NONE_OPTIONS and ns["DISTRACTORS"] == A.DISTRACTORS
    for s, src in ((0, "a"), (2, "0:yelp/train/388287"), (7, "x:y")):
        assert ns["source_seed"](s, src) == A.source_seed(s, src)


def kev_variants(ns, req, seed, epoch, rid, p_pair=0.25):
    """kev/train.py:295-302 record_variants with pairs=None, run on Kev's own functions."""
    rng = random.Random(ns["source_seed"](seed, f"{epoch}:{rid}"))
    variants = [ns["augment"](req, rng, p_none=0.1, p_none_distract=0.12, p_distract=0.15)]
    if p_pair > 0 and rng.random() < p_pair:
        variants += ns["none_pair"](req, rng)
    return variants


def test_augmentation_matches_kev_on_every_train_record():
    ns = load_kev_originals()
    kev_recs = [json.loads(l) for l in open(KEV_TRAIN, encoding="utf-8") if l.strip()]
    conv = B.read_rows(CONV_TRAIN)
    recs = A.group_records(conv)
    assert len(recs) == len(kev_recs) == 12576
    n_checked = {"main": 0, "pair": 0, "none_correct": 0, "none_wrong": 0, "distractor": 0}
    for seed, epoch in ((2, 0), (2, 1), (5, 0)):
        for (key, rows), kev_rec in zip(recs, kev_recs):
            assert key[2] == rows[0]["kev"]["line"]
            rid = kev_rec["_meta"]["id"]
            assert rid == rows[0]["kev"]["id"]
            ours = A.augment_record(rows, seed, epoch)
            theirs = kev_variants(ns, kev_rec, seed, epoch, rid)
            # main variant: one question per original question, in order
            main = ours[:len(rows)]
            for r_out, (qid, q_kev) in zip(main, theirs[0]["questions"].items()):
                assert r_out["qname"] == qid
                if q_kev["type"] != "choice":
                    continue
                assert [l["id"] for l in r_out["levels"]] == list(q_kev["criteria"]), (key, seed, epoch)
                assert r_out["gold"] == q_kev["label"]
                for l in r_out["levels"]:
                    desc = q_kev["criteria"][l["id"]]
                    assert l["name"] == l["id"]
                    assert (l["shown"] == l["name"]) == (desc is None or desc == "")
                n_checked["main"] += 1
                n_checked[r_out["kev"]["aug"]["mode"]] = n_checked.get(r_out["kev"]["aug"]["mode"], 0) + 1
            # pair rows
            pair_rows = ours[len(rows):]
            assert len(pair_rows) == len(theirs) - 1, (key, seed, epoch)
            for r_out, kev_req in zip(pair_rows, theirs[1:]):
                (qid, q_kev), = kev_req["questions"].items()
                assert r_out["qname"] == qid
                assert [l["id"] for l in r_out["levels"]] == list(q_kev["criteria"])
                assert r_out["gold"] == q_kev["label"]
                n_checked["pair"] += 1
            # non-choice questions untouched
            for r_in, r_out in zip(rows, main):
                if r_in["kev"]["qtype"] != "choice":
                    assert r_out is r_in
    # every branch of augment was exercised
    for k in ("main", "pair", "none_correct", "none_wrong", "distractor"):
        assert n_checked[k] > 0, (k, n_checked)
    print("  augmentation == Kev:", n_checked)


def test_pair_semantics():
    conv = B.read_rows(CONV_TRAIN)
    recs = A.group_records(conv)
    seen = 0
    for _, rows in recs:
        out = A.augment_record(rows, 2, 0)
        pr = out[len(rows):]
        if pr:
            present, absent = pr
            seen += 1
            ids_p = [l["id"] for l in present["levels"]]
            ids_a = [l["id"] for l in absent["levels"]]
            assert absent["gold"] in ids_p and absent["gold"] not in [i for i in ids_a if i not in ids_p]
            assert len(ids_a) == len(ids_p) - 1
            assert present["gold"] in ids_p and present["gold"] not in ids_a
            assert present["kev"]["aug"]["mode"] == "none_present" and absent["kev"]["aug"]["mode"] == "none_absent"
            if seen > 300:
                break
    assert seen > 100


def test_build_outputs():
    prompt_mod = P
    with tempfile.TemporaryDirectory() as td:
        common = ["--seed", "2", "--epochs", "2", "--limit", "400"]
        B.main(["--out-dir", os.path.join(td, "a")] + common + ["--augment", "none"])
        B.main(["--out-dir", os.path.join(td, "a2")] + common + ["--augment", "none"])
        B.main(["--out-dir", os.path.join(td, "qo")] + common + ["--augment", "none", "--drop-state"])
        B.main(["--out-dir", os.path.join(td, "kev")] + common)           # default = kev (frozen prereg §3.4)
        B.main(["--out-dir", os.path.join(td, "kev2")] + common)
        for ep in (0, 1):  # deterministic
            assert B.file_sha256(os.path.join(td, "a", f"train.e{ep}.jsonl")) == B.file_sha256(os.path.join(td, "a2", f"train.e{ep}.jsonl"))
            assert B.file_sha256(os.path.join(td, "kev", f"train.e{ep}.jsonl")) == B.file_sha256(os.path.join(td, "kev2", f"train.e{ep}.jsonl"))
        e0 = [json.loads(l) for l in open(os.path.join(td, "a", "train.e0.jsonl"))]
        e1 = [json.loads(l) for l in open(os.path.join(td, "a", "train.e1.jsonl"))]
        assert len(e0) == len(e1) == 400
        assert [x["prov"]["id"] + str(x["prov"]["qindex"]) for x in e0] != [x["prov"]["id"] + str(x["prov"]["qindex"]) for x in e1]
        conv = {(r["kev"]["line"], r["kev"]["qindex"]): r for r in B.read_rows(CONV_TRAIN, 400)}
        for x in e0:
            r = conv[(x["prov"]["line"], x["prov"]["qindex"])]
            assert x["prompt"] == prompt_mod.build_prompt(r, "record_name").text           # §3.1 same renderer
            gold_name = [l["name"] for l in r["levels"] if l["id"] == r["gold"]][0]
            assert x["response"] == " " + gold_name                                         # §7.2
            assert x["candidates"][x["gold_index"]] == x["response"]
            assert x["prompt"].endswith("Answer:") and not x["response"].endswith("<|endoftext|>")
        qo = [json.loads(l) for l in open(os.path.join(td, "qo", "train.e0.jsonl"))]
        full = {(x["prov"]["line"], x["prov"]["qindex"]): x for x in e0}
        for x in qo:
            y = full[(x["prov"]["line"], x["prov"]["qindex"])]
            assert "Input:" not in x["prompt"] and "Input:" in y["prompt"] and x["response"] == y["response"]
            assert x["prompt"] == prompt_mod.build_prompt(prompt_mod.drop_input(conv[(x["prov"]["line"], x["prov"]["qindex"])]), "record_name").text
        kv0 = [json.loads(l) for l in open(os.path.join(td, "kev", "train.e0.jsonl"))]
        kv1 = [json.loads(l) for l in open(os.path.join(td, "kev", "train.e1.jsonl"))]
        assert sorted(x["prompt"] for x in kv0) != sorted(x["prompt"] for x in kv1)           # regenerated per epoch
        base = [x for x in kv0 if x["prov"]["role"] == "base"]
        assert len(base) == 400                                                               # one base example per question
        sib = [x for x in kv0 if x["prov"]["role"] == "sibling"]
        assert len(sib) > 0 and len(sib) % 2 == 0                                              # siblings come in pairs
        for x in sib:                                                                         # sibling rides with its base question's unit
            same_unit = [b for b in base if b["prov"]["unit"] == x["prov"]["unit"]]
            assert len(same_unit) == 1 and same_unit[0]["prov"]["qname"] == x["prov"]["qname"]
        m = json.load(open(os.path.join(td, "kev", "manifest.json")))
        assert m["prompt_version"] == "r0-prompt-v2"


def test_steps_per_epoch_match_prereg():
    rows = B.read_rows(CONV_TRAIN)
    units = B.epoch_units(rows, 2, 0, "kev", P)
    assert len(units) == 15576 and -(-len(units) // 10) == 1558      # prereg §7.2: 1,558 steps/epoch, 3,116 in total
    n_sib = sum(len(u) - 1 for u in units)
    assert 2000 < n_sib < 3200, n_sib                                 # prereg §3.4: about 2,612 expected


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name, flush=True)
    print(f"{n} tests passed")
