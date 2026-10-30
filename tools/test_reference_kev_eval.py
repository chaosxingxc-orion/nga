#!/usr/bin/env python3
"""CPU falsification tests for persisted native reference predictions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('reference_eval', Path(__file__).with_name('reference_kev_eval.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record = {'_meta': {'id': 'a'}, 'questions': {'q': {}}}
        self.pred = {'probabilities': {'q': {'a': .5, 'b': .5}},
                     'logits': {'q': {'a': 0., 'b': 0.}}, 'inference_temperature': 2.35}

    def test_valid_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'record.json'
            payload = {'stamp': 'expected', 'input_sha256': m.objhash(self.record), 'prediction': self.pred}
            m.atomic(path, {'payload': payload, 'sha256': m.objhash(payload)})
            self.assertEqual(m.read_record(path, self.record, 'expected'), payload)

    def test_modified_content_foreign_stamp_and_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'record.json'
            payload = {'stamp': 'expected', 'input_sha256': m.objhash(self.record), 'prediction': self.pred}
            obj = {'payload': payload, 'sha256': m.objhash(payload)}
            changed = copy.deepcopy(obj)
            changed['payload']['prediction']['probabilities']['q']['a'] = .7
            m.atomic(path, changed)
            with self.assertRaisesRegex(ValueError, 'Changed record'): m.read_record(path, self.record, 'expected')
            m.atomic(path, obj)
            with self.assertRaisesRegex(ValueError, 'Foreign'): m.read_record(path, self.record, 'other')
            other = copy.deepcopy(self.record)
            other['_meta']['id'] = 'different'
            with self.assertRaisesRegex(ValueError, 'Foreign'): m.read_record(path, other, 'expected')

    def test_semantic_corruption_even_with_recomputed_hash(self):
        changes = [lambda p: p['probabilities'].clear(),
                   lambda p: p['probabilities']['q'].update(a=.7),
                   lambda p: p['logits']['q'].update(a=4.),
                   lambda p: p['logits']['q'].update(c=0.),
                   lambda p: p.update(inference_temperature=0)]
        for change in changes:
            p = copy.deepcopy(self.pred)
            change(p)
            with self.assertRaises(ValueError): m.validate_prediction(self.record, p)

    def test_nonfinite(self):
        for key in ['logits', 'probabilities']:
            for value in [float('nan'), float('inf')]:
                p = copy.deepcopy(self.pred)
                p[key]['q']['a'] = value
                with self.assertRaises(ValueError): m.validate_prediction(self.record, p)

    def test_empty_duplicate_and_valid_expected_records(self):
        with self.assertRaises(ValueError): m.record_keys([])
        with self.assertRaises(ValueError): m.record_keys([self.record, self.record])
        self.assertEqual(m.record_keys([self.record]), ['a'])

    def test_frozen_input_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'weights'
            path.write_bytes(b'original')
            config = {'files': {str(path): m.sha(path)}}
            m.verify_files(config)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): m.verify_files(config)


if __name__ == '__main__':
    unittest.main()
