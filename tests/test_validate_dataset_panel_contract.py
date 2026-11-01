import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_dataset_panel_contract", ROOT / "tools/validate_dataset_panel_contract.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def valid_docs():
    contract = {
        "schema": "dataset-expansion-contract-v2",
        "read_scope": {k: False for k in MODULE.READ_KEYS},
        "candidate_families": [{"dataset": "demo", "status": "ready_for_inference"}],
    }
    audit = {
        "schema": "dataset-expansion-v3-local-metadata-audit-v1",
        "read_scope": {k: False for k in MODULE.READ_KEYS},
        "entries": [{
            "dataset": "demo",
            "status": "ready_for_inference",
            "manifest_sha256": "a" * 64,
            "split": "test",
            "metric_rule": "accuracy by task",
            "source_overlap_audit_status": "checked",
        }],
    }
    return contract, audit


class DatasetPanelContractTests(unittest.TestCase):
    def test_valid_contract_is_admissible(self):
        contract, audit = valid_docs()
        result = MODULE.validate(contract, audit)
        self.assertTrue(result["valid"])
        self.assertEqual(result["admission"], "ready_for_inference")
        self.assertFalse(result["inference_authorized"])

    def test_current_v2_audit_is_fail_closed(self):
        contract = json.loads((ROOT / ".local/preparations/dataset-expansion-contract-20261102-v2/CONTRACT.json").read_text())
        audit = json.loads((ROOT / ".local/reports/dataset-expansion-v3-metadata-audit-20261102.json").read_text())
        result = MODULE.validate(contract, audit)
        self.assertFalse(result["valid"])
        self.assertEqual(result["admission"], "NO_FIFO_ADMISSION")
        self.assertEqual(result["counts"]["ready"], 0)
        self.assertTrue(any("no FIFO admission" in r for r in result["reasons"]))

    def test_read_scope_tampering_is_rejected(self):
        contract, audit = valid_docs()
        audit["read_scope"]["candidate_test_samples_read"] = True
        result = MODULE.validate(contract, audit)
        self.assertFalse(result["valid"])
        self.assertTrue(any("candidate_test_samples_read" in r for r in result["reasons"]))
        self.assertFalse(result["inference_authorized"])

    def test_ready_entry_missing_required_fields_is_rejected(self):
        contract, audit = valid_docs()
        del audit["entries"][0]["metric_rule"]
        del audit["entries"][0]["source_overlap_audit_status"]
        result = MODULE.validate(contract, audit)
        self.assertFalse(result["valid"])
        self.assertTrue(any("metric rule" in r for r in result["reasons"]))
        self.assertTrue(any("source overlap status" in r for r in result["reasons"]))

    def test_multimodal_ready_entry_requires_harness(self):
        contract, audit = valid_docs()
        contract["candidate_families"][0]["family"] = "multimodal image"
        audit["entries"][0]["dataset"] = "demo image"
        contract["candidate_families"][0]["dataset"] = "demo image"
        result = MODULE.validate(contract, audit)
        self.assertFalse(result["valid"])
        self.assertTrue(any("multimodal harness" in r for r in result["reasons"]))


if __name__ == "__main__":
    unittest.main()
