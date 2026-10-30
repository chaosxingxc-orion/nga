"""Fail-closed provenance and published-table regressions for the baseline exporter."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('matrix', Path(__file__).with_name('export_reference_baseline_matrix.py'))
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class MatrixTest(unittest.TestCase):
    def bound_fixture(self, temp):
        root = Path(temp) / 'inference'
        root.mkdir()
        (root / 'config.json').write_text('{"model": "fixture"}')
        (root / 'report.json').write_text('{"accuracy": 0.5}')
        finish = root.with_name(root.name + '_finish')
        finish.mkdir()
        ap = finish / 'INDEPENDENT_AUDIT.json'
        audit = {'status': 'VERIFIED_SCOPED', 'review_flags': [],
                 'config_sha256': matrix.sha(root / 'config.json'),
                 'report_sha256': matrix.sha(root / 'report.json')}
        ap.write_text(json.dumps(audit))
        tp = finish / 'FINISH_COMPLETE.json'
        terminal = {'rc': 0, 'status': 'COMPLETED_SCOPED',
                    'inference_run': str(root), 'config_sha256': audit['config_sha256'],
                    'review_flag_count': 0, 'outputs': {ap.name: matrix.sha(ap)}}
        tp.write_text(json.dumps(terminal))
        return root, ap, audit, tp, terminal

    def test_successful_finisher_binds_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ap, audit, tp, _ = self.bound_fixture(temp)
            self.assertEqual(matrix.audit_bound(root), (ap, audit, tp))

    def test_audit_without_finisher_terminal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _, _, tp, _ = self.bound_fixture(temp)
            tp.unlink()
            with self.assertRaises(FileNotFoundError):
                matrix.audit_bound(root)

    def test_nonzero_or_unsuccessful_terminal_rejected(self):
        for update in ({'rc': 1}, {'status': 'FAILED'}, {'status': 'COMPLETED_SCOPED_PENDING'}):
            with self.subTest(update=update), tempfile.TemporaryDirectory() as temp:
                root, _, _, tp, terminal = self.bound_fixture(temp)
                terminal.update(update)
                tp.write_text(json.dumps(terminal))
                with self.assertRaisesRegex(ValueError, 'not successfully completed'):
                    matrix.audit_bound(root)

    def test_changed_audit_rejected_even_with_unchanged_report_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ap, audit, _, _ = self.bound_fixture(temp)
            audit['scope'] = 'Changed after finisher completion'
            ap.write_text(json.dumps(audit))
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                matrix.audit_bound(root)

    def test_terminal_missing_audit_hash_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _, _, tp, terminal = self.bound_fixture(temp)
            terminal['outputs'] = {}
            tp.write_text(json.dumps(terminal))
            with self.assertRaisesRegex(ValueError, 'missing audit binding'):
                matrix.audit_bound(root)

    def test_terminal_wrong_run_or_config_rejected(self):
        for update, message in (({'inference_run': '/another/run'}, 'run mismatch'),
                                ({'config_sha256': '0' * 64}, 'Hash mismatch')):
            with self.subTest(update=update), tempfile.TemporaryDirectory() as temp:
                root, _, _, tp, terminal = self.bound_fixture(temp)
                terminal.update(update)
                tp.write_text(json.dumps(terminal))
                with self.assertRaisesRegex(ValueError, message):
                    matrix.audit_bound(root)

    def test_finisher_binding_supports_legacy_kev_audit_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ap, _, tp, terminal = self.bound_fixture(temp)
            audit = {'status': 'VERIFIED_SCOPED', 'stamp': 'legacy-stamp'}
            ap.write_text(json.dumps(audit))
            terminal.pop('review_flag_count')
            terminal['outputs'][ap.name] = matrix.sha(ap)
            tp.write_text(json.dumps(terminal))
            self.assertEqual(matrix.finish_bound(root, ap, audit), tp)

    def test_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            path.write_text('{}')
            original = matrix.sha(path)
            path.write_text('{"accuracy": 1.0}')
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                matrix.hash_matches(path, original)

    def test_denominator_mismatch_not_tolerated(self):
        with self.assertRaisesRegex(ValueError, 'value mismatch'):
            matrix.same({'n': 1073, 'accuracy': 0.5}, {'n': 1071, 'accuracy': 0.5})

    def test_audit_probability_change_rejected(self):
        matrix.same({'ece': .01234567890000001}, {'ece': .0123456789})
        with self.assertRaisesRegex(ValueError, 'metric mismatch'):
            matrix.same({'ece': .0123457}, {'ece': .0123456789})

    def test_upstream_table_selects_nimble_not_jev(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'PUBLIC_BENCHMARKS.md'
            path.write_text('| demo | score | 240 | 15 | 49.2% (42.9%–55.5%) | 35.0% (29.2%–41.2%) | 47.9% | 0.0004 |\n'
                            '| demo | 0/15 | 0/15 | 0.102 | 0.232 | 0.678 | 0.774 | 0.698 | 0.770 | — | — |\n')
            actual = matrix.nimble_upstream(path)['demo']
            self.assertAlmostEqual(actual['accuracy'], .492)
            self.assertEqual((actual['ece10'], actual['brier'], actual['expected_score_mae']), (.102, .678, .698))
            self.assertIsNone(actual['nll'])

    def test_missing_file_fails_instead_of_zero_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                matrix.load(Path(temp) / 'missing-report.json')


if __name__ == '__main__':
    unittest.main()
