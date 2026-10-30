"""CPU-only provenance boundary regressions; synthetic files, no models or datasets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provenance_r3 as P

SHA = "a" * 64
SCORER = {"mode": "rightpad", "dtype": "float32", "token_budget": 16384,
          "record_grade": True, "hf32": {"hf32": False}}


class EvidenceBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = self.root / "readouts"
        self.rows.mkdir()
        (self.root / "RUN_IDENTITY.json").write_text(json.dumps({"model_sha256": SHA}))

    def manifest(self, files):
        P.write_unit_manifest(str(self.root), "main", SHA, SCORER, [str(p) for p in files])

    def verify(self):
        return P.verify(str(self.root), str(self.rows), SHA)

    def populated(self):
        p = self.rows / "primary__part0.jsonl"
        p.write_text(json.dumps({"k": "q1", "m": SHA[:16]}) + "\n")
        return p

    def test_missing_directory_refused(self):
        self.rows.rmdir()
        self.manifest([])
        with self.assertRaisesRegex(P.ProvenanceRefusal, "no readout files"):
            self.verify()

    def test_empty_directory_refused(self):
        self.manifest([])
        with self.assertRaisesRegex(P.ProvenanceRefusal, "no readout files"):
            self.verify()

    def test_only_empty_files_refused(self):
        p = self.rows / "primary__part0.jsonl"
        p.write_text("\n \n")
        self.manifest([p])
        with self.assertRaisesRegex(P.ProvenanceRefusal, "no readout rows"):
            self.verify()

    def test_populated_result_passes(self):
        p = self.populated()
        self.manifest([p])
        self.assertEqual(self.verify()["rows_verified"], 1)

    def test_empty_shard_beside_real_rows_is_allowed(self):
        p = self.populated()
        empty = self.rows / "primary__part1.jsonl"
        empty.write_text("")
        self.manifest([p, empty])
        self.assertEqual(self.verify()["files_verified"], 2)

    def test_content_changed_after_manifest_refused(self):
        p = self.populated()
        self.manifest([p])
        p.write_text(p.read_text().replace("q1", "q2"))
        with self.assertRaisesRegex(P.ProvenanceRefusal, "sha256 differs"):
            self.verify()

    def test_wrong_model_stamp_refused(self):
        p = self.populated()
        p.write_text(json.dumps({"k": "q1", "m": "b" * 16}) + "\n")
        self.manifest([p])
        with self.assertRaisesRegex(P.ProvenanceRefusal, "another model"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
