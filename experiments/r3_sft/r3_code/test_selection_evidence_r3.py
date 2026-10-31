"""Synthetic CPU tests of actual selection consumers; no real scores/test partitions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core_r3 as C
import provenance_r3 as PV
import selection_evidence_r3 as E
import select_r3 as S
import testlock_r3 as TL

SCORER = {"mode": "rightpad", "dtype": "float32", "token_budget": 16384,
          "record_grade": True, "hf32": {"hf32": False}}


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def task(i):
    return {"kev": {"id": str(i), "qindex": 0}, "source": "synthetic", "qname": "q",
            "level_type": "nominal", "gold": "b" if i % 2 else "a",
            "levels": [{"id": "a"}, {"id": "b"}]}


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kev = self.root / "kev"
        self.train = self.root / "train"
        self.adapter = self.train / "adapter"
        self.base = self.root / "base"
        self.run = self.root / "evaluation"
        self.base.mkdir()
        self.adapter.mkdir(parents=True)
        (self.base / ".complete").write_text("fixture-revision\n")
        (self.base / "model.safetensors").write_bytes(b"synthetic base bytes")
        (self.adapter / "adapter_model.safetensors").write_bytes(b"synthetic adapter bytes")
        write(self.adapter / "adapter_config.json", {"r": 16})
        self.identity = TL.model_identity(str(self.base), str(self.adapter), str(self.root / "cache"))
        self.training = {"arm": "k1", "kernel": "ref", "model_path": str(self.base), "total_steps": 3116,
                         "summary": {"final_step": 3116},
                         "args": {"arm": "k1", "seed": 2, "out": str(self.train), "drop_state": False}}
        write(self.train / "manifest.json", self.training)
        data_manifest = {"suites": {}}
        self.tasks = {}
        for suite, split, n in (("decision-v7", "train", 20), ("decision-v7", "dev", 1264), ("transfer-v4", "dev", 656)):
            rows = [task(i) for i in range(n)]
            self.tasks[(suite, split)] = rows
            path = Path(C.partition_path(suite, split, kev_dir=str(self.kev)))
            C.write_jsonl(str(path), rows)
            entry = data_manifest["suites"].setdefault(suite, {"partitions": {}})
            entry["partitions"][split] = {"outputs": {"clean": {"path": str(path.relative_to(self.kev)),
                                                                          "sha256": C.sha256_file(str(path))}}}
        write(self.kev / "manifest.json", data_manifest)
        self.paths = []
        for suite in C.SUITES:
            for kind in ("clean", "question_only", "empty_input"):
                rows = self.tasks[(suite, "dev")]
                readouts = [PV.stamp(C.readout_row(r, [0., 1.] if r["gold"] == "b" else [1., 0.]),
                                    self.identity["sha256"]) for r in rows]
                path = Path(C.k_readout_path(str(self.run), suite, "dev", kind))
                C.write_jsonl(str(path), readouts)
                self.paths.append(str(path))
        write(self.run / "RUN_IDENTITY.json", {"model_sha256": self.identity["sha256"], "arm": "K1", "track_t_config": "r3"})
        self.report = {"header": {"model": self.identity, "arm": "K1", "scorer": SCORER, "track_t_config": "r3",
                                   "limit": 0, "limit_groups": 0, "dry_run_warnings": []},
                       "track_k": {"partitions": {}}}
        write(self.run / "report.json", self.report)
        self.manifest()

    def manifest(self):
        PV.write_unit_manifest(str(self.run), "fixture", self.identity["sha256"], SCORER, self.paths)

    def load(self):
        return E.load_selection_report(str(self.run), kev_dir=str(self.kev))

    def change_rows(self, mutation, refresh=True):
        p = self.paths[0]
        rows = C.read_jsonl(p)
        mutation(rows)
        C.write_jsonl(p, rows)
        if refresh:
            self.manifest()

    def test_complete_population_recomputed_from_scores(self):
        # Report contains no accuracy at all. Only the stored scores may determine it.
        result = self.load()
        self.assertEqual(result["track_k"]["partitions"]["decision-v7/dev"]["headline"]["kev_rule_accuracy"], 1.)
        self.assertEqual(len(result["selection_evidence"]["correct"]), 1920)
        self.assertEqual(result["selection_evidence"]["seed"], 2)
        self.assertFalse(list(self.kev.glob("**/test*")))

    def test_same_count_wrong_questions_refused(self):
        self.change_rows(lambda rows: rows[0].update(k="foreign/0"))
        with self.assertRaisesRegex(E.SelectionRefusal, "population"):
            self.load()

    def test_missing_question_refused(self):
        self.change_rows(lambda rows: rows.pop())
        with self.assertRaisesRegex(E.SelectionRefusal, "population"):
            self.load()

    def test_duplicate_question_refused(self):
        self.change_rows(lambda rows: rows.__setitem__(0, rows[1]))
        with self.assertRaisesRegex(PV.ProvenanceRefusal, "twice"):
            self.load()

    def test_unstamped_rows_refused(self):
        self.change_rows(lambda rows: rows[0].pop("m"))
        with self.assertRaisesRegex(PV.ProvenanceRefusal, "no model stamp"):
            self.load()

    def test_modified_readout_without_manifest_refused(self):
        self.change_rows(lambda rows: rows[0].update(k="changed"), refresh=False)
        with self.assertRaisesRegex(PV.ProvenanceRefusal, "sha256 differs"):
            self.load()

    def test_changed_adapter_refused(self):
        (self.adapter / "adapter_model.safetensors").write_bytes(b"changed")
        with self.assertRaisesRegex(E.SelectionRefusal, "weights on disk"):
            self.load()

    def test_wrong_gold_or_stored_prediction_refused(self):
        self.change_rows(lambda rows: rows[0].update(gold_index=1))
        with self.assertRaisesRegex(E.SelectionRefusal, "stored decision"):
            self.load()

    def test_nonfinite_scores_refused(self):
        self.change_rows(lambda rows: rows[0].update(s=[float("nan"), 0.]))
        with self.assertRaisesRegex(E.SelectionRefusal, "nonfinite"):
            self.load()

    def test_deleted_manifested_directory_refused(self):
        import shutil
        shutil.rmtree(self.run / "trackk" / "transfer-v4__dev")
        with self.assertRaisesRegex(PV.ProvenanceRefusal, "absent"):
            self.load()

    def test_report_arm_cannot_relabel_training(self):
        self.report["header"]["arm"] = "K1-PT"
        write(self.run / "report.json", self.report)
        with self.assertRaisesRegex(E.SelectionRefusal, "RUN_IDENTITY"):
            self.load()

    def test_changed_frozen_dataset_refused(self):
        path = Path(C.partition_path("decision-v7", "dev", kev_dir=str(self.kev)))
        rows = C.read_jsonl(str(path))
        rows[0]["gold"] = "b"
        C.write_jsonl(str(path), rows)
        with self.assertRaisesRegex(Exception, "manifest"):
            self.load()

    def test_conflicting_manifests_refused(self):
        mpath = self.run / "manifests" / "fixture.json"
        manifest = json.loads(mpath.read_text())
        next(iter(manifest["files"].values()))["rows"] += 1
        write(self.run / "manifests" / "conflict.json", manifest)
        with self.assertRaisesRegex(PV.ProvenanceRefusal, "conflicting"):
            self.load()

    def test_track_t_gold_schema_and_population(self):
        source = {"key": "t1", "gold_id": "a", "levels": [{"id": "a"}, {"id": "b"}]}
        stored = {"k": "t1", "gold": "a", "ids": ["a", "b"], "s": [1., 0.]}
        self.assertEqual(E.validate_population([stored], [source], lambda r: r["key"]), [stored])
        with self.assertRaisesRegex(E.SelectionRefusal, "population"):
            E.validate_population([stored, stored], [source], lambda r: r["key"])

    def test_incomplete_training_refused(self):
        self.training["summary"]["final_step"] = 100
        write(self.train / "manifest.json", self.training)
        with self.assertRaisesRegex(E.SelectionRefusal, "not complete"):
            self.load()

    def test_wrong_objective_refused(self):
        self.training["arm"] = "k2"
        write(self.train / "manifest.json", self.training)
        with self.assertRaisesRegex(E.SelectionRefusal, "objective"):
            self.load()

    def test_partial_report_refused(self):
        self.report["header"]["limit"] = 10
        write(self.run / "report.json", self.report)
        with self.assertRaisesRegex(E.SelectionRefusal, "partial"):
            self.load()

    def test_one_seed_and_copied_seed_never_align(self):
        r = self.load()
        for reports in ([r], [r, copy.deepcopy(r)]):
            with self.assertRaises(E.SelectionRefusal):
                S.k_align(reports)
        second = copy.deepcopy(r)
        second["selection_evidence"].update(seed=3, adapter_path="independent-adapter")
        self.assertTrue(S.k_align([r, second])["passes"])
        second["selection_evidence"]["seed"] = 4
        with self.assertRaises(E.SelectionRefusal):
            S.k_align([r, second])

    def test_cli_loads_real_validation_not_raw_summary(self):
        # Missing all provenance: an optimistic JSON summary must not be enough for CLI.
        (self.run / "manifests" / "fixture.json").unlink()
        with self.assertRaises(PV.ProvenanceRefusal):
            S.main(["kalign", "--runs", str(self.run), str(self.run)])

    def seed_pair(self, second_args=None, second_manifest=None):
        first = E.train_identity(self.report)
        other = copy.deepcopy(self.training)
        other["args"].update(seed=3, out=str(self.root / "train3"))
        other["args"].update(second_args or {})
        other.update(second_manifest or {})
        write(self.root / "train3" / "manifest.json", other)
        report = copy.deepcopy(self.report)
        report["header"]["model"]["path"] = str(self.root / "train3" / "adapter")
        return [{"selection_evidence": first}, {"selection_evidence": E.train_identity(report)}]

    def test_same_recipe_independent_seeds_and_runtime_settings_accepted(self):
        pair = self.seed_pair({"save_every": 100, "perf_every": 20, "device": "npu:1"})
        E.validate_seed_reports(pair)
        self.assertEqual(pair[0]["selection_evidence"]["training_variant"],
                         pair[1]["selection_evidence"]["training_variant"])

    def test_k2_rows_and_shared_cannot_pool(self):
        self.training["arm"] = self.training["args"]["arm"] = "k2"
        self.report["header"]["arm"] = "K2"
        write(self.train / "manifest.json", self.training)
        with self.assertRaisesRegex(E.SelectionRefusal, "different training variants"):
            E.validate_seed_reports(self.seed_pair({"k2_impl": "shared"}))
        E.validate_seed_reports(self.seed_pair({"k2_impl": "rows"}))

    def test_recipe_and_code_changes_cannot_pool(self):
        for delta in ({"micro_tokens": 3000}, {"lora_dropout": 0.}, {"gdn_impl": "fast_ref"},
                      {"k2_rows": 48}, {"lr": 2e-4}, {"future_training_option": True}):
            with self.subTest(delta=delta), self.assertRaisesRegex(E.SelectionRefusal, "different training variants"):
                E.validate_seed_reports(self.seed_pair(delta))
        with self.assertRaisesRegex(E.SelectionRefusal, "different training variants"):
            E.validate_seed_reports(self.seed_pair(second_manifest={"code_sha256": {"train_r3.py": "changed"}}))

    def test_missing_variant_requires_revalidation(self):
        pair = self.seed_pair()
        for r in pair:
            r["selection_evidence"].pop("training_variant")
        with self.assertRaisesRegex(E.SelectionRefusal, "variant identity"):
            E.validate_seed_reports(pair)

    def test_builder_manifest_uses_line_payload_not_file_bytes(self):
        import hashlib
        path = self.root / 'task.jsonl'
        path.write_bytes(b'{"a":1}\n{"b":2}\n')
        entry = {"sha256": hashlib.sha256(b'{"a":1}{"b":2}').hexdigest(), "records": 2}
        self.assertEqual(E.verify_task_manifest(path, entry)["records"], 2)
        with self.assertRaises(E.SelectionRefusal):
            E.verify_task_manifest(path, dict(entry, records=3))
        path.write_bytes(b'{"a":2}\n{"b":2}\n')
        with self.assertRaises(E.SelectionRefusal): E.verify_task_manifest(path, entry)

    def test_compare_cannot_bypass_loader_with_summaries(self):
        (self.run / "manifests" / "fixture.json").unlink()
        with self.assertRaises(PV.ProvenanceRefusal):
            S.compare([str(self.run)] * 2, [str(self.run)] * 2)


class Gating(unittest.TestCase):
    def test_no_population_cannot_pass(self):
        self.assertFalse(S.condition_c([], [])["ok"])
        self.assertFalse(S.adopt_first({"passes": True}))
        with self.assertRaises(E.SelectionRefusal):
            S.k_floor([])

    def test_smoke_cannot_become_r0_adoption_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            write(Path(td) / "R0RESCORE_COMPLETE.json", {"exit_code": 0, "run_of_record": False, "limit_groups": 1})
            with self.assertRaisesRegex(E.SelectionRefusal, "smoke"):
                E.load_r0_gating(td)

    def test_first_adoption_cannot_trust_pass_flag(self):
        with self.assertRaisesRegex(E.SelectionRefusal, "verified seed reports"):
            S.adopt_first({"passes": True}, r0_run="unused")

    def test_first_adoption_has_positive_and_negative_paths(self):
        def report(seed):
            return {"selection_evidence": {"seed": seed, "arm": "K1", "adapter_path": str(seed),
                                           "training_variant": {"schema": 1, "args": {"arm": "k1"}}},
                    "track_k": {"partitions": {suite + "/dev": {
                        "headline": {"kev_rule_accuracy": .9}, "arms": {
                            "constant": {"kev_rule_accuracy": .4}, "question_only": {"kev_rule_accuracy": .4}}}
                        for suite in C.SUITES}}}
        with patch.object(E, "load_selection_report", side_effect=lambda d: report(int(d))), patch.object(E, "load_r0_gating", return_value={"statuses": {"boolean": "pass"}}):
            self.assertTrue(S.adopt_first({"seed_reports": ["2", "3"]}, "verified-r0"))
            with self.assertRaises(E.SelectionRefusal):
                S.adopt_first({"seed_reports": ["2", "2"]}, "verified-r0")

    def test_valid_gating_and_declared_void_cells(self):
        gating = {"statuses": {"boolean": "pass", "nominal": "void", "ordinal": "void"}}
        def sel(flip):
            return {"typed-decisions": {"boolean": {"b2_status": "pass", "flip_T1_argmax": flip,
                                                     "n_units": 50, "n_pairs_dropped_tie": 0}}}
        self.assertTrue(S.condition_c([sel(.1)] * 2, [sel(.1)] * 2, gating)["ok"])
        self.assertFalse(S.condition_c([sel(.13)] * 2, [sel(.1)] * 2, gating)["ok"])
        gating["statuses"]["boolean"] = "void"
        self.assertFalse(S.condition_c([sel(.1)] * 2, [sel(.1)] * 2, gating)["ok"])


if __name__ == "__main__":
    unittest.main()
