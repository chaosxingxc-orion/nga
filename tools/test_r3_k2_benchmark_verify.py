"""Arithmetic tampering checks; synthetic values are not performance evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import r3_k2_benchmark_verify as V

PIN = 'a' * 64


def fixture():
    rows = []
    for step in range(13):
        row = {'step': step, 'order': list(V.ARMS if step % 2 == 0 else reversed(V.ARMS)), 'exact': True}
        for arm in V.ARMS:
            row[arm] = {'loss': .5 + step, 'seconds': 999 if step < 3 else (12 if arm == 'reference' else 10),
                        'reserved_gib': 99 if step < 3 else step,
                        'stats': {'tokens': 999 if step < 3 else 20, 'rows': 12, 'resp_tokens': 0}}
        rows.append(row)
    return {'schema': 'r3-k2-sync-benchmark-result-v1', 'rows': rows,
            'seconds': {'reference': 120, 'candidate': 100}, 'speedup': 1.2,
            'engineering_speed_candidate': True, 'chips': 1, 'exact_loss_and_gradients': True,
            'performance': {arm: {'questions_per_second_per_chip': 100 / sec,
                                 'tokens_per_second_per_chip': 200 / sec,
                                 'reserved_gib_peak': 12, 'chips': 1}
                            for arm, sec in [('reference', 120), ('candidate', 100)]},
            'plan_sha256': PIN, 'scientific_acceptance': False, 'test_read': False}


class Verify(unittest.TestCase):
    def test_warmups_excluded_and_base_questions_distinct_from_examples(self):
        result = V.verify(fixture(), PIN)
        self.assertEqual(result['seconds'], {'reference': 120, 'candidate': 100})
        self.assertEqual(result['performance']['candidate']['reserved_gib_peak'], 12)
        self.assertEqual(result['protocol_questions'], 100)
        self.assertFalse(result['gradient_equivalence_independently_verified'])
        self.assertFalse(result['completion_verified'])
        self.assertFalse(result['scientific_acceptance'])

    def test_tampering_rejected(self):
        def assign(path, value):
            def change(report):
                parent = report
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
            return change
        cases = [
            (['speedup'], 1.3), (['seconds', 'reference'], 121),
            (['performance', 'candidate', 'tokens_per_second_per_chip'], 20),
            (['performance', 'candidate', 'questions_per_second_per_chip'], 1.2),
            (['performance', 'candidate', 'reserved_gib_peak'], 99),
            (['performance', 'candidate', 'chips'], True),
            (['engineering_speed_candidate'], False), (['test_read'], True),
            (['scientific_acceptance'], True), (['chips'], 2),
            (['plan_sha256'], 'b' * 64), (['exact_loss_and_gradients'], False),
            (['rows', 0, 'step'], False), (['rows', 5, 'step'], 4),
            (['rows', 1, 'order'], ['reference', 'candidate']),
            (['rows', 0, 'exact'], False), (['rows', 4, 'candidate', 'loss'], .123),
            (['rows', 4, 'candidate', 'seconds'], -1),
            (['rows', 4, 'candidate', 'seconds'], float('inf')),
            (['rows', 4, 'candidate', 'loss'], float('nan')),
            (['rows', 4, 'candidate', 'stats', 'tokens'], True),
            (['rows', 4, 'candidate', 'stats', 'tokens'], 21),
            (['rows', 4, 'candidate', 'reserved_gib'], -1),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                report = fixture(); assign(path, value)(report)
                with self.assertRaises(ValueError): V.verify(report, PIN)
        report = fixture(); report['rows'].pop()
        with self.assertRaises(ValueError): V.verify(report, PIN)

    def test_short_measurement_rejected(self):
        report = fixture()
        for row in report['rows'][3:]: row['candidate']['seconds'] = 1
        with self.assertRaisesRegex(ValueError, 'window'): V.verify(report, PIN)

    def test_review_numeric_overflow_and_near_zero_summary(self):
        for field in ('seconds', 'tokens'):
            report = fixture()
            for arm in V.ARMS:
                target = report['rows'][3][arm]
                if field == 'tokens': target = target['stats']
                target[field] = 10 ** 400
            with self.subTest(field=field), self.assertRaises(ValueError): V.verify(report, PIN)
        report = fixture()
        for row in report['rows'][3:]: row['candidate']['seconds'] = 1e15
        report['seconds']['candidate'] = 1e16
        report['speedup'] = 120 / 1e16
        report['engineering_speed_candidate'] = False
        report['performance']['candidate']['questions_per_second_per_chip'] = 100 / 1e16
        report['performance']['candidate']['tokens_per_second_per_chip'] = 200 / 1e16
        self.assertTrue(V.verify(report, PIN)['arithmetic_verified'])
        for path in (['speedup'], ['performance', 'candidate', 'questions_per_second_per_chip'],
                     ['performance', 'candidate', 'tokens_per_second_per_chip']):
            for value in (-1e-13, 0):
                changed = copy.deepcopy(report); target = changed
                for key in path[:-1]: target = target[key]
                target[path[-1]] = value
                with self.subTest(path=path,value=value), self.assertRaises(ValueError): V.verify(changed, PIN)

    def test_valid_below_threshold_is_negative_evidence_not_failure(self):
        report = fixture()
        for row in report['rows']: row['reference'] = copy.deepcopy(row['candidate'])
        report['seconds']['reference'] = 100
        report['performance']['reference'] = copy.deepcopy(report['performance']['candidate'])
        report['speedup'] = 1; report['engineering_speed_candidate'] = False
        self.assertFalse(V.verify(report, PIN)['engineering_speed_candidate'])

    def test_file_hash_and_input_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'; path.write_text(json.dumps(fixture()))
            result = V.verify_file(path, PIN)
            self.assertEqual(result['result_sha256'], V.hashlib.sha256(path.read_bytes()).hexdigest())
            link = Path(directory) / 'link'; link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'unsafe'): V.verify_file(link, PIN)
            path.write_text('{"rows": [], "rows": []}')
            with self.assertRaisesRegex(ValueError, 'duplicate'): V.verify_file(path, PIN)
            path.write_bytes(b' ' * (V.LIMIT + 1))
            with self.assertRaisesRegex(ValueError, 'size'): V.verify_file(path, PIN)


if __name__ == '__main__': unittest.main()
