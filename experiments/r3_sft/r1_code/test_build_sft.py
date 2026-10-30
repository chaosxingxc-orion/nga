"""CPU tests for build_sft.py.  Run:  python3 -P -m unittest test_build_sft -v   (from r1_code, no pytest needed)

Slow tests (full-file scans) use --limit-groups style slices of the real task files; the data root can
be overridden with NGA_JEV_DATA_ROOT.
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_sft as B  # noqa: E402
from prompt import build_prompt, PROMPT_VERSION  # noqa: E402
from split import GROUP70, QUESTION70, TRAIN, HELDOUT  # noqa: E402

DATA_ROOT = os.environ.get("NGA_JEV_DATA_ROOT", B.DEFAULT_DATA_ROOT)
R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"


def rec(levels, gold, gid="g", qname="q", source="typed-decisions", variant="original", task="T1", idx="T1:0"):
    r = {"source": source, "group_id": gid, "qname": qname, "input": "some input", "task_definition": "Do the task.",
         "question": "Which?", "levels": [{"id": i, "name": n, "definition": d} for i, n, d in levels],
         "level_type": "nominal", "candidate_set": "exclusive", "gold": gold, "task": task, "variant": variant}
    r["_task"], r["_rec_index"], r["_file"] = task, idx, "x"
    r["_gold_index"] = B.resolve_gold_index(r)
    return r


def find_gid(side, n=1):
    out, i = [], 0
    while len(out) < n:
        g = f"gid-{i}"
        i += 1
        if (GROUP70.assign({"group_id": g}) == TRAIN) == (side == TRAIN):
            out.append(g)
    return out


class TestSwapRule(unittest.TestCase):
    def test_definition_follow_handcrafted(self):
        base = rec([("a", "a", "Alpha def"), ("b", "b", "Beta def"), ("c", "c", "Gamma def")], "b")
        swapped = rec([("a", "a", "Alpha def"), ("b", "b", "Gamma def"), ("c", "c", "Beta def")], "b",
                      variant="swap_1_2", task="T2")
        gi = B.recompute_gold_by_definition(base, swapped)
        self.assertEqual(swapped["levels"][gi]["id"], "c")  # stored gold "b" is stale; Beta def now sits on c
        reversed_ = rec([("c", "c", "Alpha def"), ("b", "b", "Beta def"), ("a", "a", "Gamma def")], "b",
                        variant="reversed", task="T2")
        self.assertEqual(reversed_["levels"][B.recompute_gold_by_definition(base, reversed_)]["id"], "b")
        base2 = rec([("a", "a", "Alpha def"), ("b", "b", "Beta def"), ("c", "c", "Gamma def")], "a")
        self.assertEqual(reversed_["levels"][B.recompute_gold_by_definition(base2, reversed_)]["id"], "c")

    def test_non_unique_definition_is_refused(self):
        base = rec([("a", "a", "same"), ("b", "b", "same")], "a")
        var = rec([("a", "a", "same"), ("b", "b", "same")], "a", variant="swap_0_1", task="T2")
        self.assertIsNone(B.recompute_gold_by_definition(base, var))

    def test_casefolded_gold_resolves(self):
        r = rec([("true", "true", "T def"), ("false", "false", "F def")], "False")
        self.assertEqual(r["_gold_index"], 1)

    def test_augmented_swap_gold_follows_definition(self):
        levels = [("a", "a", "Alpha def"), ("b", "b", "Beta def"), ("c", "c", "Gamma def"), ("d", "d", "Delta def")]
        words = ["w%d" % i for i in range(40)]
        users = {w: {"other"} for w in words}
        for gold in "abcd":
            r = rec(levels, gold, gid="swap-gid")
            gdef = {"a": "Alpha def", "b": "Beta def", "c": "Gamma def", "d": "Delta def"}[gold]
            n_swapped = 0
            for a in range(60):
                new, info = B.augment_record(r, a, 1.0, words, users, force_swap=True)
                self.assertTrue(info["defs_permuted"])
                holder = [l["id"] for l in new["levels"] if l["definition"] == gdef]
                self.assertEqual(len(holder), 1)
                self.assertEqual(new["gold"], holder[0])
                row = B.make_row(new, "symbol", info, None)
                self.assertEqual(row["response"], " " + holder[0])
                self.assertEqual(sorted(l["definition"] for l in new["levels"]), sorted(d for _, _, d in levels))
                n_swapped += 1
            self.assertEqual(n_swapped, 60)

    def test_no_swap_keeps_definition_to_gold_pairing_in_original_terms(self):
        levels = [("a", "a", "Alpha def"), ("b", "b", "Beta def"), ("c", "c", "Gamma def")]
        words = ["w%d" % i for i in range(40)]
        users = {w: {"other"} for w in words}
        r = rec(levels, "b", gid="noswap")
        for a in range(40):
            new, info = B.augment_record(r, a, 0.0, words, users)
            self.assertFalse(info["defs_permuted"])
            self.assertEqual([l["definition"] for l in new["levels"] if l["id"] == new["gold"]], ["Beta def"])
            self.assertEqual(len({l["id"] for l in new["levels"]}), 3)


class TestAugmentationFamilies(unittest.TestCase):
    def test_families_and_word_pool_exclude_own_question(self):
        levels = [("a", "a", "Alpha def"), ("b", "b", "Beta def"), ("c", "c", "Gamma def")]
        pool = ["own1", "own2", "x1", "x2", "x3", "x4", "x5"]
        users = {"own1": {"qA"}, "own2": {"qA"}, "x1": {"qB"}, "x2": {"qB"}, "x3": {"qC"}, "x4": {"qC"}, "x5": {"qD"}}
        r = rec(levels, "a", qname="qA", gid="fam")
        seen = set()
        for a in range(400):
            new, info = B.augment_record(r, a, 0.25, pool, users)
            seen.add(info["augmentation"])
            ids = [l["id"] for l in new["levels"]]
            self.assertEqual(len(set(ids)), 3)
            if info["augmentation"] == "words":
                self.assertFalse({"own1", "own2"} & set(ids))
            if info["augmentation"] == "random":
                self.assertTrue(all(3 <= len(i) <= 6 for i in ids))
            if info["augmentation"] == "digits":
                self.assertTrue(all(i.isdigit() for i in ids))
            if info["augmentation"] == "letters":
                self.assertTrue(all(i.isalpha() for i in ids))
        self.assertEqual(seen, set(B.FAMILIES))

    def test_order_is_permuted_in_general(self):
        levels = [(c, c, c + " def") for c in "abcdef"]
        r = rec(levels, "a", gid="ord")
        orders = set()
        for a in range(50):
            new, _ = B.augment_record(r, a, 0.0, ["w%d" % i for i in range(40)], {"w%d" % i: {"z"} for i in range(40)})
            orders.add(tuple(l["definition"] for l in new["levels"]))
        self.assertGreater(len(orders), 10)

    def test_rng_is_pure_function_of_seed(self):
        a = [B.HashRng("g", "T1:3", 0).randbelow(1000) for _ in range(5)]
        b = [B.HashRng("g", "T1:3", 0).randbelow(1000) for _ in range(5)]
        c = [B.HashRng("g", "T1:3", 1).randbelow(1000) for _ in range(5)]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        # pinned value: protects byte-reproducibility across platforms and python versions
        self.assertEqual(B.HashRng("g", "T1:3", 0)._u64(),
                         int.from_bytes(hashlib.sha256(hashlib.sha256(b"g\x1fT1:3\x1f0").digest() + (0).to_bytes(8, "big")).digest()[:8], "big"))


class TestSourceCap(unittest.TestCase):
    def test_cap_enforced_and_deterministic(self):
        rows = [{"source_family": "A", "group_id": f"a{i}"} for i in range(900)] + \
               [{"source_family": "B", "group_id": f"b{i}"} for i in range(100)]
        out1, rep1 = B.apply_source_cap(rows, 0.6)
        out2, rep2 = B.apply_source_cap(rows, 0.6)
        self.assertEqual(out1, out2)
        a = sum(r["source_family"] == "A" for r in out1)
        self.assertLessEqual(a / len(out1), 0.6 + 1e-9)
        self.assertEqual(sum(r["source_family"] == "B" for r in out1), 100)


class TestCarveoutAndComposition(unittest.TestCase):
    def test_tau_predicate_matches_spec(self):
        for i in range(2000):
            g = f"grp-{i}"
            d = hashlib.sha256(("r3tau:" + g).encode()).digest()
            self.assertEqual(B.tau_carved(g), int.from_bytes(d[:8], "big") % 10000 < 1500)
        share = sum(B.tau_carved(f"grp-{i}") for i in range(20000)) / 20000
        self.assertAlmostEqual(share, 0.15, delta=0.02)

    def test_cap_per_family_openjev_040(self):
        rows = [{"source_family": "openjev-synth", "group_id": f"o{i}"} for i in range(700)] + \
               [{"source_family": "typed-decisions", "group_id": f"t{i}"} for i in range(400)] + \
               [{"source_family": "akhilaaa3", "group_id": f"a{i}"} for i in range(100)]
        out, rep = B.apply_source_cap(rows, 0.6, {"openjev-synth": 0.40})
        n = len(out)
        self.assertLessEqual(sum(r["source_family"] == "openjev-synth" for r in out) / n, 0.40 + 1e-9)
        self.assertEqual(sum(r["source_family"] == "typed-decisions" for r in out), 400)
        self.assertIn("openjev-synth", rep["capped"])
        self.assertEqual(out, B.apply_source_cap(rows, 0.6, {"openjev-synth": 0.40})[0])


@unittest.skipUnless(os.path.isdir(DATA_ROOT), "task files not mounted")
class TestOnRealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {}
        for arm in ("fixed", "symbol"):
            args = B.parse_args(["--arm", arm, "--limit-groups", "30", "--out-root", cls.tmp.name,
                                 "--data-root", DATA_ROOT, "--tokenizer", "/nonexistent"])
            assert B.build(args) == 0
            cls.paths[arm] = os.path.join(cls.tmp.name, arm, B.OUTPUT_NAME)
            cls.paths[arm + "_manifest"] = os.path.join(cls.tmp.name, arm, "manifest.json")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def rows(self, arm):
        with open(self.paths[arm], encoding="utf-8") as f:
            return [json.loads(l) for l in f]

    def test_prompt_version_and_r0_copies_identical(self):
        self.assertEqual(PROMPT_VERSION, "r0-prompt-v2")
        for n in ("prompt.py", "split.py"):
            a = open(os.path.join(HERE, n), "rb").read()
            b = open(os.path.join(R0_CODE, n), "rb").read()
            self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest(), n)

    def test_no_heldout_group_or_question_in_output(self):
        for arm in ("fixed", "symbol"):
            rows = self.rows(arm)
            self.assertTrue(rows)
            for r in rows:
                self.assertEqual(GROUP70.assign({"group_id": r["group_id"]}), TRAIN)
                if r["source_family"] == "akhilaaa3":
                    self.assertEqual(QUESTION70.assign({"qname": r["qname"]}), TRAIN)
                self.assertIn(r["task"], ("T1", "T2"))
                self.assertFalse(r["file"].startswith("T3"))
            self.assertTrue(any(r["source_family"] == "akhilaaa3" for r in rows) or arm == "x")

    def test_unaugmented_prompts_byte_match_build_prompt(self):
        cache = {}
        n = 0
        for arm in ("fixed", "symbol"):
            for r in self.rows(arm):
                self.assertTrue(r["prompt"].endswith("Answer:"))
                self.assertTrue(r["response"].startswith(" "))
                if r["augmentation"] != "none":
                    continue
                if r["file"] not in cache:
                    with open(os.path.join(DATA_ROOT, r["file"]), encoding="utf-8") as f:
                        cache[r["file"]] = f.readlines()
                src = json.loads(cache[r["file"]][int(r["rec_index"].split(":")[1])])
                self.assertEqual(r["prompt"], build_prompt(src, render="record_name").text)
                if not r["gold_recomputed"]:
                    gi = B.resolve_gold_index(src)
                    self.assertEqual(r["response"], " " + src["levels"][gi]["name"])
                n += 1
        self.assertGreater(n, 100)

    def test_fixed_arm_is_original_names_only(self):
        rows = self.rows("fixed")
        self.assertTrue(all(r["augmentation"] == "none" for r in rows))
        self.assertTrue(all((r["task"], r["variant"]) in (("T1", "original"), ("T2", "base")) for r in rows))
        keys = [(r["prompt"], r["response"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_symbol_arm_swap_rows_use_recomputed_gold_only(self):
        rows = self.rows("symbol")
        sw = [r for r in rows if r["task"] == "T2" and r["variant"] != "base"]
        self.assertTrue(sw)
        self.assertTrue(all(r["gold_recomputed"] for r in sw))
        cache = {}
        checked = 0
        for r in sw:
            if r["augmentation"] != "none":
                continue
            if r["file"] not in cache:
                with open(os.path.join(DATA_ROOT, r["file"]), encoding="utf-8") as f:
                    cache[r["file"]] = f.readlines()
            src = json.loads(cache[r["file"]][int(r["rec_index"].split(":")[1])])
            # find the base of the same unit and check the shown gold carries the base gold's definition
            bd = None
            for line in cache[r["file"]]:
                b = json.loads(line)
                if b["group_id"] == src["group_id"] and b["qname"] == src["qname"] and b["input"] == src["input"] and b["variant"] == "base":
                    bd = b
                    break
            gdef = bd["levels"][B.resolve_gold_index(bd)]["definition"]
            shown = r["response"][1:]
            holder = [l["definition"] for l in src["levels"] if l["name"] == shown]
            self.assertEqual(holder, [gdef])
            checked += 1
            if checked >= 60:
                break
        self.assertGreater(checked, 10)

    def test_no_tau_carved_group_and_flag_is_not_vacuous(self):
        carved_on = {}
        for arm in ("fixed", "symbol"):
            self.assertTrue(all(not B.tau_carved(r["group_id"]) for r in self.rows(arm)))
        # with the carve-out switched off, carved groups DO appear (so the check above is not vacuous)
        with tempfile.TemporaryDirectory() as t3:
            for arm in ("fixed", "symbol"):
                args = B.parse_args(["--arm", arm, "--limit-groups", "30", "--out-root", t3, "--data-root", DATA_ROOT,
                                     "--tokenizer", "/nonexistent", "--no-tau-carveout"])
                B.build(args)
                with open(os.path.join(t3, arm, B.OUTPUT_NAME), encoding="utf-8") as f:
                    carved_on[arm] = sum(B.tau_carved(json.loads(l)["group_id"]) for l in f)
        self.assertGreater(carved_on["fixed"], 0)
        self.assertGreater(carved_on["symbol"], 0)
        m = json.load(open(self.paths["symbol_manifest"]))
        self.assertTrue(m["args"]["tau_carveout"])
        self.assertGreater(m["load_stats"]["excluded_tau_carveout"], 0)
        self.assertEqual(m["verification"]["tau_carved_group"], 0)

    def test_symbol_arm_has_no_openjev_t1_digits_and_fixed_arm_unchanged_rule(self):
        sym = self.rows("symbol")
        self.assertFalse([r for r in sym if r["source_family"] == "openjev-synth" and r["task"] == "T1" and r["variant"] == "digits"])
        self.assertTrue([r for r in sym if r["source_family"] == "typed-decisions" and r["variant"] == "digits"])
        self.assertTrue([r for r in sym if r["source_family"] == "openjev-synth" and r["variant"] == "letters"])
        m = json.load(open(self.paths["symbol_manifest"]))
        self.assertIn("realized_mix", m)
        self.assertEqual(m["source_cap"]["per_family_max_share"], {"openjev-synth": 0.4})
        self.assertLessEqual(m["source_cap"]["row_share_after_cap"].get("openjev-synth", 0), 0.4 + 1e-9)
        fm = json.load(open(self.paths["fixed_manifest"]))
        self.assertEqual(fm["source_cap"]["per_family_max_share"], {})

    def test_no_digits_family_for_openjev_augmentations(self):
        sym = self.rows("symbol")
        oj = [r for r in sym if r["source_family"] == "openjev-synth" and r["augmentation"] != "none"]
        self.assertTrue(oj)
        self.assertEqual({r["augmentation"] for r in oj}, {"letters", "random", "words"})
        # other sources keep the digits family, so the exclusion is specific to openjev-synth
        self.assertTrue([r for r in sym if r["source_family"] == "typed-decisions" and r["augmentation"] == "digits"])
        m = json.load(open(self.paths["symbol_manifest"]))
        self.assertTrue(m["args"]["symbol_drop_openjev_digits_family"])
        self.assertEqual(m["verification"]["openjev_digits_family_augmentation"], 0)
        # no openjev symbol row carries purely numeric identifiers in its options
        for r in oj:
            opts = [ln[2:].split(":", 1)[0] for ln in r["prompt"].split("\nOptions:\n", 1)[1].split("\n\n", 1)[0].split("\n")]
            self.assertFalse(all(o.isdigit() for o in opts), opts)

    def test_augment_record_restricted_families(self):
        levels = [(c, c, c + " def") for c in "abcd"]
        r = rec(levels, "a", gid="fam2")
        pool = ["w%d" % i for i in range(40)]
        users = {w: {"z"} for w in pool}
        fams = tuple(f for f in B.FAMILIES if f != "digits")
        seen = {B.augment_record(r, a, 0.25, pool, users, families=fams)[1]["augmentation"] for a in range(300)}
        self.assertEqual(seen, {"letters", "random", "words"})

    def test_determinism_two_builds_hash_identical(self):
        with tempfile.TemporaryDirectory() as t2:
            args = B.parse_args(["--arm", "symbol", "--limit-groups", "30", "--out-root", t2, "--data-root", DATA_ROOT,
                                 "--tokenizer", "/nonexistent"])
            self.assertEqual(B.build(args), 0)
            h1 = B.sha256_file(self.paths["symbol"])
            h2 = B.sha256_file(os.path.join(t2, "symbol", B.OUTPUT_NAME))
            self.assertEqual(h1, h2)
            m1 = json.load(open(self.paths["symbol_manifest"]))
            m2 = json.load(open(os.path.join(t2, "symbol", "manifest.json")))
            self.assertEqual(m1["output_sha256"], m2["output_sha256"])
            # the manifest must not contain build-time or location-dependent fields beyond out_root
            self.assertEqual(m1["counts_by_source_family"], m2["counts_by_source_family"])

    def test_manifest_has_hashes_and_cap(self):
        m = json.load(open(self.paths["symbol_manifest"]))
        for key in ("output_sha256", "code_sha256", "source_cap", "counts_by_source_family_task_variant_augmentation", "verification"):
            self.assertIn(key, m)
        self.assertIn("build_sft.py", m["code_sha256"])
        self.assertIn("prompt.py", m["code_sha256"])
        self.assertTrue(m["verification"]["passed"])
        shares = m["source_cap"]["row_share_after_cap"]
        self.assertTrue(all(v <= 0.6 + 1e-9 for v in shares.values()), shares)


if __name__ == "__main__":
    unittest.main(verbosity=2)
