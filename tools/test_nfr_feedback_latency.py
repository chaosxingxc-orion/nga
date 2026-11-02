import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('nfr_latency', Path(__file__).with_name('nfr_feedback_latency.py'))
N = importlib.util.module_from_spec(spec)
spec.loader.exec_module(N)


class LatencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.start = self.root / 'START_INTENT.json'
        self.end = self.root / 'EXIT.json'
        self.start.write_text(json.dumps({'utc_seconds': 10}))
        self.end.write_text(json.dumps({'utc_seconds': 25, 'exit_code': 0}))
        self.config = self.root / 'config.json'
        self.doc = {'schema': N.SCHEMA, 'receipts': [self.ref('start', self.start), self.ref('end', self.end)],
                    'events': [{'id': 'started', 'receipt': 'start', 'timestamp_field': 'utc_seconds', 'kind': 'start'},
                               {'id': 'completed', 'receipt': 'end', 'timestamp_field': 'utc_seconds', 'kind': 'terminal'}],
                    'intervals': [{'id': 'report', 'start_events': ['started'], 'end_event': 'completed',
                                   'required_terminals': ['completed']}]}

    def ref(self, name, path):
        return {'id': name, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'clock_domain': 'host-a', 'clock_basis': 'fixture producer clock'}

    def write_config(self):
        self.config.write_text(json.dumps(self.doc))
        return hashlib.sha256(self.config.read_bytes()).hexdigest()

    def run_analysis(self):
        return N.analyze(str(self.config), self.write_config())

    def mutate_receipt(self, index, value):
        path = Path(self.doc['receipts'][index]['path'])
        path.write_text(json.dumps(value))
        self.doc['receipts'][index]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()

    def interval(self):
        return self.run_analysis()['intervals'][0]

    def test_success_readonly_single_snapshot_and_runtime(self):
        before = {p: p.read_bytes() for p in [self.start, self.end]}
        with patch.object(N, 'read_snapshot', wraps=N.read_snapshot) as reads:
            report = self.run_analysis()
        self.assertEqual(report['intervals'][0]['elapsed_seconds'], 15)
        self.assertEqual(reads.call_count, 3)
        self.assertEqual(report['measurement']['files_read'], 3)
        self.assertGreaterEqual(report['measurement']['runtime_seconds'], 0)
        self.assertGreaterEqual(report['measurement']['cpu_seconds'], 0)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(report['production_speedup_claim'])

    def test_latest_dependency_controls_wait_start(self):
        directory = self.root / 'second'; directory.mkdir()
        other = directory / 'EXIT.json'; other.write_text(json.dumps({'utc_seconds': 20, 'exit_code': 0}))
        self.doc['receipts'].append(self.ref('second', other))
        self.doc['events'].append({'id': 'second_done', 'receipt': 'second', 'timestamp_field': 'utc_seconds', 'kind': 'terminal'})
        i = self.doc['intervals'][0]
        i['start_events'] = ['started', 'second_done']; i['required_terminals'].append('second_done')
        self.assertEqual(self.interval()['elapsed_seconds'], 5)

    def test_cross_clock_never_emits_elapsed(self):
        self.doc['receipts'][1]['clock_domain'] = 'host-b'
        i = self.interval()
        self.assertEqual(i['status'], 'incomparable_clock_domains')
        self.assertIsNone(i['elapsed_seconds'])

    def test_unknown_clock_never_emits_elapsed(self):
        self.doc['receipts'][1]['clock_domain'] = None
        i = self.interval()
        self.assertEqual(i['status'], 'unknown_clock_domain')
        self.assertIsNone(i['elapsed_seconds'])

    def test_negative_elapsed_is_not_clamped_to_zero(self):
        self.mutate_receipt(1, {'utc_seconds': 5, 'exit_code': 0})
        self.assertEqual(self.interval()['status'], 'clock_or_order_anomaly')
        self.assertIsNone(self.interval()['elapsed_seconds'])

    def test_real_zero_remains_zero(self):
        self.mutate_receipt(1, {'utc_seconds': 10, 'exit_code': 0})
        self.assertEqual(self.interval()['elapsed_seconds'], 0)

    def test_failed_or_missing_terminal_is_not_a_measured_interval(self):
        for value in [None, 1, False, '0']:
            with self.subTest(exit=value):
                self.mutate_receipt(1, {'utc_seconds': 25, 'exit_code': value})
                i = self.interval()
                self.assertEqual(i['status'], 'unavailable_event')
                self.assertIsNone(i['elapsed_seconds'])

    def test_missing_terminal_file_is_explicit_unknown(self):
        self.end.unlink()
        r = self.run_analysis()
        self.assertEqual(r['events'][1]['status'], 'missing_receipt')
        self.assertEqual(r['measurement']['files_read'], 2)
        self.assertIsNone(r['intervals'][0]['elapsed_seconds'])

    def test_missing_invalid_timestamp_is_not_zero(self):
        for value in [None, False, '2026-01-01T00:00:00', -1, 'wrong']:
            with self.subTest(value=value):
                self.mutate_receipt(1, {'utc_seconds': value, 'exit_code': 0})
                self.assertIsNone(self.interval()['elapsed_seconds'])
        self.mutate_receipt(1, {'exit_code': 0})
        self.assertEqual(self.run_analysis()['events'][1]['status'], 'missing_timestamp')

    def test_iso_timezone_and_epoch_compare(self):
        self.mutate_receipt(0, {'utc_seconds': '1970-01-01T08:00:10+08:00'})
        self.assertEqual(self.interval()['elapsed_seconds'], 15)

    def test_wrong_receipt_hash_rejects(self):
        self.end.write_text(json.dumps({'utc_seconds': 26, 'exit_code': 0}))
        with self.assertRaisesRegex(N.Invalid, 'receipt hash mismatch'):
            self.run_analysis()

    def test_wrong_config_hash_rejects_before_receipts(self):
        self.write_config()
        with patch.object(N, 'read_snapshot', wraps=N.read_snapshot) as reads:
            with self.assertRaisesRegex(N.Invalid, 'config hash mismatch'):
                N.analyze(str(self.config), '0'*64)
        self.assertEqual(reads.call_count, 1)

    def test_duplicate_identity_and_path_reject(self):
        original = copy.deepcopy(self.doc)
        for name in ['receipts', 'events', 'intervals']:
            with self.subTest(collection=name):
                self.doc = copy.deepcopy(original); self.doc[name].append(copy.deepcopy(self.doc[name][0]))
                with self.assertRaises(N.Invalid): self.run_analysis()
        self.doc = copy.deepcopy(original)
        duplicate = copy.deepcopy(self.doc['receipts'][0]); duplicate['id'] = 'another'
        self.doc['receipts'].append(duplicate)
        with self.assertRaisesRegex(N.Invalid, 'duplicate receipt path'): self.run_analysis()

    def test_raw_log_and_nonallowlisted_fields_reject(self):
        self.doc['receipts'][0]['path'] = str(self.root / 'run.log')
        with self.assertRaisesRegex(N.Invalid, 'permitted control receipt'): self.run_analysis()
        self.doc['receipts'][0]['path'] = str(self.start)
        self.doc['events'][0]['timestamp_field'] = 'command'
        with self.assertRaisesRegex(N.Invalid, 'timestamp field'): self.run_analysis()

    def test_symlink_rejects(self):
        original = self.root/'original'; self.end.rename(original); self.end.symlink_to(original)
        with self.assertRaisesRegex(N.Invalid, 'symlink'): self.run_analysis()

    def test_no_terminal_gate_is_rejected(self):
        self.doc['intervals'][0]['required_terminals'] = []
        with self.assertRaises(N.Invalid): self.run_analysis()

    def test_duplicate_json_and_nonfinite_are_rejected(self):
        for raw in [b'{"exit_code":0,"exit_code":1}', b'{"utc_seconds":NaN}']:
            self.end.write_bytes(raw)
            self.doc['receipts'][1]['sha256'] = hashlib.sha256(raw).hexdigest()
            with self.assertRaises(N.Invalid): self.run_analysis()

    def test_size_and_stage_caps(self):
        self.end.write_bytes(b' '* (N.MAX_RECEIPT_BYTES + 1))
        with self.assertRaisesRegex(N.Invalid, 'too large'): self.run_analysis()
        self.doc['intervals'] *= 33
        with self.assertRaisesRegex(N.Invalid, 'collection size'): self.run_analysis()

    def test_cli_success_and_bounded_failure(self):
        pin = self.write_config()
        cmd = [sys.executable, '-B', '-P', str(Path(N.__file__)), '--config', str(self.config), '--sha256', pin]
        good = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(good.returncode, 0); self.assertEqual(json.loads(good.stdout)['intervals'][0]['elapsed_seconds'], 15)
        bad = subprocess.run(cmd[:-1]+['0'*64], capture_output=True, text=True, timeout=10)
        self.assertEqual(bad.returncode, 2); self.assertEqual(bad.stderr, '')
        self.assertEqual(json.loads(bad.stdout)['status'], 'rejected')

    def test_report_size_is_explicitly_bounded(self):
        with patch.object(N, 'MAX_OUTPUT_BYTES', 100):
            with self.assertRaisesRegex(N.Invalid, 'bounded report size'): self.run_analysis()

    def test_cli_pathological_json_has_no_traceback(self):
        raw = (b'['*1500) + b'0' + (b']'*1500)
        self.config.write_bytes(raw)
        cmd = [sys.executable, '-B', '-P', str(Path(N.__file__)), '--config', str(self.config),
               '--sha256', hashlib.sha256(raw).hexdigest()]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2); self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
