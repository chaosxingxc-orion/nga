#!/usr/bin/env python3
"""Synthetic valid and corrupt artifact fixtures for the independent auditor."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('verify_reference_kev.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'source'
        source.mkdir()
        self.records = [{'state': str(i), '_meta': {'id': str(i), 'source': 'fixture', 'variant': 'clean'},
                         'questions': {'q': {'type': 'choice', 'criteria': {'a': None, 'b': None},
                                             'label': 'a' if i == 0 else 'b', 'src': 'fixture'}}}
                        for i in range(2)]
        (source / 'test.jsonl').write_text('\n'.join(json.dumps(r) for r in self.records))
        write(source / 'manifest.json', {'files': {'test.jsonl': {
            'sha256': m.digest(source / 'test.jsonl'), 'records': 2, 'questions': 2}}})
        self.config = {'out': str(self.root), 'checkpoint': 'fixture', 'runtime': {'fixture': '1'},
                       'files': {str(p): m.digest(p) for p in source.iterdir()},
                       'suites': [{'name': 'suite', 'path': str(source), 'records': 2,
                                   'questions': 2, 'clean_questions': 2}]}
        self.config_path = self.root / 'config.json'
        write(self.config_path, self.config)
        self.stamp = m.object_digest(self.config)
        write(self.root / 'CONFIG_RECEIPT.json', {'stamp': self.stamp})
        write(self.root / 'ENVIRONMENT.json', {'runtime': {'fixture': '1'}, 'temperature': 2.})
        d = self.root / 'suite'
        write(d / 'EXPECTED.json', {'stamp': self.stamp, 'ids': ['0', '1'],
                                   'input_hashes': [m.object_digest(r) for r in self.records]})
        rows = []
        for i, record in enumerate(self.records):
            prediction = {'probabilities': {'q': {'a': .75, 'b': .25}},
                          'logits': {'q': {'a': math.log(3), 'b': 0.}}, 'inference_temperature': 2.}
            payload = {'stamp': self.stamp, 'input_sha256': m.object_digest(record),
                       'prediction': prediction, 'seconds': .1}
            write(d / 'records' / f'{i:06d}.json', {'payload': payload, 'sha256': m.object_digest(payload)})
            rows.extend(m.build_rows(record, prediction, 2.))
        write(d / 'rows.json', rows)
        # Independently specified two-row expected values; ECE = confidence - accuracy.
        native = {'n': 2, 'acc': .5, 'brier': .625, 'ece': .25, 'nll': -math.log(.75*.25)/2}
        raw = {'n': 2, 'acc': .5, 'brier': .82, 'ece': .4, 'nll': -math.log(.9*.1)/2}
        write(d / 'report.json', {'stamp': self.stamp, 'split': 'test', 'reference_model': 'fixture',
                                 'records': 2, 'questions': 2, 'native_serving_temperature': 2.,
                                 'native': {'clean': native}, 'raw_temperature_one': {'clean': raw}})
        self.rebind()

    def rebind(self):
        d = self.root / 'suite'
        bindings = {'suite': {'report_sha256': m.digest(d / 'report.json'),
                              'rows_sha256': m.digest(d / 'rows.json')}}
        write(self.root / 'REFERENCE_COMPLETE.json', {'rc': 0, 'stamp': self.stamp, 'suites': bindings})
        write(self.root / 'report.json', {'stamp': self.stamp, 'run_of_record': True, 'suite_reports': bindings})

    def test_valid_complete_and_known_metrics(self):
        result = m.audit(self.config_path)
        self.assertEqual(result['status'], 'VERIFIED_SCOPED')
        self.assertAlmostEqual(result['suites']['suite']['native']['brier'], .625)
        self.assertAlmostEqual(result['suites']['suite']['raw_temperature_one']['ece'], .4)

    def test_missing_marker_is_not_complete(self):
        (self.root / 'REFERENCE_COMPLETE.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Terminal marker missing'):
            m.audit(self.config_path)
        self.assertEqual(m.audit(self.config_path, True)['status'], 'PARTIAL_NOT_ACCEPTED')

    def test_failed_or_boolean_terminal_rejected(self):
        for rc in [1, False]:
            terminal = m.read(self.root / 'REFERENCE_COMPLETE.json')
            terminal['rc'] = rc
            write(self.root / 'REFERENCE_COMPLETE.json', terminal)
            with self.assertRaisesRegex(ValueError, 'Terminal not successful'):
                m.audit(self.config_path)

    def test_missing_record(self):
        (self.root / 'suite/records/000001.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing persisted'):
            m.audit(self.config_path)
        self.assertEqual(m.audit(self.config_path, True)['suites']['suite']['records_verified'], 1)

    def test_extra_record(self):
        write(self.root / 'suite/records/000002.json', {})
        with self.assertRaisesRegex(ValueError, 'Unexpected record'):
            m.audit(self.config_path)

    def test_changed_source(self):
        source = self.root / 'source/test.jsonl'
        source.write_text(source.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Frozen file hash'):
            m.audit(self.config_path)

    def test_changed_payload(self):
        p = self.root / 'suite/records/000000.json'
        obj = m.read(p)
        obj['payload']['prediction']['probabilities']['q']['a'] = .1
        write(p, obj)
        with self.assertRaisesRegex(ValueError, 'payload hash'):
            m.audit(self.config_path)

    def test_forged_payload_with_wrong_options(self):
        p = self.root / 'suite/records/000000.json'
        obj = m.read(p)
        obj['payload']['prediction']['probabilities']['q'] = {'x': .75, 'y': .25}
        obj['payload']['prediction']['logits']['q'] = {'x': math.log(3), 'y': 0.}
        obj['sha256'] = m.object_digest(obj['payload'])
        write(p, obj)
        with self.assertRaisesRegex(ValueError, 'candidate coverage'):
            m.audit(self.config_path)

    def test_foreign_stamp_with_valid_payload_hash(self):
        p = self.root / 'suite/records/000000.json'
        obj = m.read(p)
        obj['payload']['stamp'] = 'foreign'
        obj['sha256'] = m.object_digest(obj['payload'])
        write(p, obj)
        with self.assertRaisesRegex(ValueError, 'Record provenance'):
            m.audit(self.config_path)

    def test_wrong_runtime(self):
        p = self.root / 'ENVIRONMENT.json'
        obj = m.read(p)
        obj['runtime']['fixture'] = '2'
        write(p, obj)
        with self.assertRaisesRegex(ValueError, 'Runtime version'):
            m.audit(self.config_path)

    def test_report_hash_rejects_unbound_mutation(self):
        p = self.root / 'suite/report.json'
        obj = m.read(p)
        obj['native']['clean']['acc'] = 1.
        write(p, obj)
        with self.assertRaisesRegex(ValueError, 'Report hash'):
            m.audit(self.config_path)

    def test_report_corruption_even_after_rebinding_hashes(self):
        p = self.root / 'suite/report.json'
        obj = m.read(p)
        obj['native']['clean']['acc'] = 1.
        write(p, obj)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'native.acc'):
            m.audit(self.config_path)

    def test_saved_row_corruption_after_rebinding(self):
        p = self.root / 'suite/rows.json'
        rows = m.read(p)
        rows[1]['label'] = 0
        write(p, rows)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'metadata mismatch'):
            m.audit(self.config_path)

    def test_duplicate_rows_after_rebinding(self):
        p = self.root / 'suite/rows.json'
        rows = m.read(p)
        rows[1] = rows[0]
        write(p, rows)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'Duplicate saved'):
            m.audit(self.config_path)

    def test_false_raw_temperature_metrics_after_rebinding(self):
        p = self.root / 'suite/report.json'
        obj = m.read(p)
        obj['raw_temperature_one']['clean'] = obj['native']['clean']
        write(p, obj)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'raw.brier'):
            m.audit(self.config_path)


if __name__ == '__main__':
    unittest.main()
