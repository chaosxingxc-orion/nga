"""CPU regression coverage for structured log counts and report alerts."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watchdog as wd


class StructuredMetrics(unittest.TestCase):
    def setUp(self):
        self.cfg = wd.make_cfg()

    def classify(self, value):
        return wd.classify_line(value if isinstance(value, str) else json.dumps(value), self.cfg)

    def test_zero_and_positive_counts(self):
        self.assertIsNone(self.classify({"report": {"failures": 0}}))
        self.assertEqual(self.classify({"report": {"failures": 1}}), "error")
        self.assertEqual(self.classify({"errors": 0, "failures": 1}), "error")
        self.assertEqual(self.classify({"errors": 1}), "error")
        self.assertEqual(self.classify({"failures": False}), "error")

    def test_nested_and_other_signals(self):
        self.assertIsNone(self.classify({"result": [{"report": {"failures": 0, "accuracy": 0.5}}]}))
        self.assertEqual(self.classify({"report": {"failures": 0}, "message": "RuntimeError: bad"}), "error")
        self.assertEqual(self.classify({"errors": 0, "message": "Traceback (most recent call last)"}), "error")
        self.assertEqual(self.classify({"failures": 0, "message": "warning: retry"}), "warning")
        self.assertEqual(self.classify({"failures": 0, "message": "worker failed"}), "error")

    def test_malformed_json_fails_closed(self):
        self.assertEqual(self.classify('{"failures": 0, "message": "RuntimeError"'), "error")
        self.assertEqual(self.classify('{"failures": 0'), "error")

    def test_duplicate_keys_cannot_hide_errors(self):
        self.assertEqual(self.classify('{"failures": 1, "failures": 0}'), "error")
        self.assertEqual(self.classify('{"result": {"errors": 2, "errors": 0}}'), "error")

    def test_nonzero_counts_cannot_underflow_to_zero(self):
        self.assertEqual(self.classify('{"errors": 1e-999}'), "error")
        self.assertIsNone(self.classify('{"errors": 0e-999, "failures": -0.0}'))
        self.assertEqual(self.classify('{"errors": 1e999999999999999999999999999999}'), "error")

    def test_suspicious_report_rates_remain_flagged(self):
        flags = wd.check_report({"accuracy": 0.0, "recall_rate": 1.0, "n": 100}, self.cfg)
        kinds = {item["kind"] for item in flags if not item["suppressed_by"]}
        self.assertIn("exact_zero", kinds)
        self.assertIn("exact_one", kinds)


if __name__ == "__main__":
    unittest.main()
