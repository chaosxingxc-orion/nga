"""CPU tests for convert_kev.py.  Run:  python3 -P -m unittest test_convert_kev -v   (from r1_code, no pytest needed)

Counts are checked against the raw Kev files (counted here independently of the converter) and against the counts
declared in the Kev manifests; every gold must be one of the item's level ids; item order must be preserved.
Set NGA_KEV_OUT to test another output directory.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/mnt/cephfs/xingchao/experiments/jev/r0_code")

import convert_kev as C  # noqa: E402

OUT = os.environ.get("NGA_KEV_OUT", C.DEFAULT_OUT)
SUITES_DIR = C.DEFAULT_SUITES_DIR
PARTS = [("decision-v7", "v7/decision-v7", "train", "train"), ("decision-v7", "v7/decision-v7", "calibration", "calibration"),
         ("decision-v7", "v7/decision-v7", "dev", "development"), ("decision-v7", "v7/decision-v7", "test", "test"),
         ("transfer-v4", "v4/transfer-v4", "dev", "development"), ("transfer-v4", "v4/transfer-v4", "test", "test")]


def raw_counts(path):
    """(records, questions, clean questions, per-source clean questions, ordered clean (id, qid) list), plain json."""
    recs = qs = clean = 0
    by_source, order = {}, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            recs += 1
            qs += len(r["questions"])
            if r["_meta"]["variant"] == "clean":
                for qid in r["questions"]:
                    clean += 1
                    by_source["kev-" + r["_meta"]["source"]] = by_source.get("kev-" + r["_meta"]["source"], 0) + 1
                    order.append((r["_meta"]["id"], qid))
    return recs, qs, clean, by_source, order


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


class TestUnits(unittest.TestCase):
    def test_option_text_matches_kev_rules(self):
        self.assertEqual(C.option_text("a", None), "a")
        self.assertEqual(C.option_text("a", ""), "a")
        self.assertEqual(C.option_text("a", "desc"), "a: desc")
        self.assertEqual(C.option_text("a", {"what": "x"}), "a: what: x")

    def test_levels_choice_noul_score(self):
        lv, gold, fb = C.build_levels({"type": "choice", "criteria": {"k1": None, "k2": "d2"}, "label": "k2"})
        self.assertEqual([l["id"] for l in lv], ["k1", "k2"])
        self.assertEqual((lv[0]["definition"], lv[0]["shown"], lv[1]["definition"], lv[1]["shown"]), ("k1", "k1", "d2", "k2: d2"))
        self.assertEqual((gold, fb), ("k2", 1))
        lv, gold, fb = C.build_levels({"type": "noul", "label": True})
        self.assertEqual([(l["id"], l["name"], l["shown"]) for l in lv], [("false", "no", "no"), ("true", "yes", "yes")])
        self.assertEqual((gold, fb), ("true", 2))
        lv, gold, fb = C.build_levels({"type": "score", "criteria": ["low", "high"], "label": 1})
        self.assertEqual(([l["id"] for l in lv], gold), (["0", "1"], "1"))

    def test_bad_labels_rejected(self):
        with self.assertRaises(ValueError):
            C.build_levels({"type": "noul", "label": 1})
        with self.assertRaises(ValueError):
            C.build_levels({"type": "score", "criteria": ["a"], "label": True})


@unittest.skipUnless(os.path.exists(os.path.join(OUT, "manifest.json")), "run convert_kev.py first")
class TestConverted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.load(open(os.path.join(OUT, "manifest.json")))

    def test_counts_equal_raw_kev_files_and_kev_manifest(self):
        for suite, rel, split, kev_file in PARTS:
            with self.subTest(suite=suite, split=split):
                recs, qs, clean, by_source, order = raw_counts(os.path.join(SUITES_DIR, rel, kev_file + ".jsonl"))
                declared = json.load(open(os.path.join(SUITES_DIR, rel, "manifest.json")))["files"][kev_file + ".jsonl"]
                self.assertEqual((recs, qs), (declared["records"], declared["questions"]))
                st = self.manifest["suites"][suite]["partitions"][split]
                self.assertEqual((st["input_records"], st["input_questions"], st["clean_questions"]), (recs, qs, clean))
                self.assertEqual(st["clean_questions"] + st["variant_questions"], qs)
                self.assertTrue(st["input_matches_kev_manifest"])
                rows = read_jsonl(os.path.join(OUT, suite, split + ".jsonl"))
                self.assertEqual(len(rows), clean)
                counts = {}
                for r in rows:
                    counts[r["source"]] = counts.get(r["source"], 0) + 1
                self.assertEqual(counts, by_source)
                self.assertEqual(st["by_source_clean_questions"], dict(sorted(by_source.items())))
                vpath = os.path.join(OUT, suite, split + ".variants.jsonl")
                nv = len(read_jsonl(vpath)) if os.path.exists(vpath) else 0
                self.assertEqual(nv, st["variant_questions"])

    def test_order_preserved(self):
        for suite, rel, split, kev_file in PARTS:
            with self.subTest(suite=suite, split=split):
                order = raw_counts(os.path.join(SUITES_DIR, rel, kev_file + ".jsonl"))[4]
                rows = read_jsonl(os.path.join(OUT, suite, split + ".jsonl"))
                self.assertEqual([(r["kev"]["id"], r["qname"]) for r in rows], order)

    def test_gold_in_levels_and_schema(self):
        for suite, rel, split, kev_file in PARTS:
            for name in (split + ".jsonl", split + ".variants.jsonl"):
                path = os.path.join(OUT, suite, name)
                if not os.path.exists(path):
                    continue
                with self.subTest(file=f"{suite}/{name}"):
                    for r in read_jsonl(path):
                        ids = [l["id"] for l in r["levels"]]
                        self.assertIn(r["gold"], ids)
                        self.assertEqual(len(set(ids)), len(ids))
                        self.assertGreaterEqual(len(ids), 2)
                        self.assertEqual(r["task"], "KEV")
                        self.assertTrue(r["source"].startswith("kev-"))
                        self.assertEqual(r["candidate_set"], "exclusive")
                        self.assertEqual(r["split"], split)
                        self.assertIn(r["level_type"], ("boolean", "nominal", "ordinal"))
                        self.assertEqual(r["variant"], "original" if name == split + ".jsonl" else r["kev"]["kev_variant"])
                        for l in r["levels"]:
                            fallback = l["definition"] == l["name"] and l["shown"] == l["name"]
                            self.assertTrue(fallback or l["shown"] == f"{l['name']}: {l['definition']}" or r["kev"]["qtype"] == "score")

    def test_sha256_in_manifest_match_files(self):
        for suite, entry in self.manifest["suites"].items():
            for split, st in entry["partitions"].items():
                for kind, o in st["outputs"].items():
                    with self.subTest(suite=suite, split=split, kind=kind):
                        self.assertEqual(C.file_sha256(os.path.join(OUT, o["path"])), o["sha256"])

    def test_prompt_builder_accepts_records(self):
        import prompt
        for suite, _, split, _ in PARTS[:1] + PARTS[3:5]:
            rows = read_jsonl(os.path.join(OUT, suite, split + ".jsonl"))
            for r in rows[:200]:
                p = prompt.build_prompt(r)
                self.assertTrue(p.text.endswith("Answer:"))
                self.assertEqual(len(p.labels), len(r["levels"]))


if __name__ == "__main__":
    unittest.main()
