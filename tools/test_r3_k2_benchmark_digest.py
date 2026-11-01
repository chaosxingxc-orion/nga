import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

s = importlib.util.spec_from_file_location('digest', Path(__file__).with_name('r3_k2_benchmark_digest.py'))
D = importlib.util.module_from_spec(s); s.loader.exec_module(D)


class Digest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root / 'results').mkdir()
        self.bp = self.write('plan.json', {'out': str(self.root / 'results')})
        self.pin = self.write('execution.json', {'out': str(self.root),
            'benchmark_plan': str(self.root / 'plan.json'), 'benchmark_sha256': self.bp})

    def write(self, name, value):
        raw = json.dumps(value).encode(); (self.root / name).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_progress_without_completion_claim(self):
        self.write('results/heartbeat.json', {'completed_pairs': 4, 'total_pairs': 13})
        d = D.summarize(self.root, self.pin)
        self.assertEqual(d['completed_pairs'], 4)
        self.assertFalse(d['completion_verified']); self.assertFalse(d['scientific_acceptance'])

    def test_failure_without_result(self):
        self.write('ENGINEERING_EVAL_EXIT.json', {'plan_sha256': self.pin, 'exit_code': 125})
        self.assertIn('benchmark_failed', D.summarize(self.root, self.pin)['flags'])

    def test_bound_success_then_changed_result_refused(self):
        report = {'plan_sha256': self.bp, 'scientific_acceptance': False, 'test_read': False,
                  'speedup': 1.07, 'engineering_speed_candidate': True,
                  'exact_loss_and_gradients': True, 'rows': [{'exact': True}] * 13}
        digest = self.write('results/RESULT.json', report)
        self.write('results/EXIT.json', {'plan_sha256': self.bp, 'exit_code': 0})
        self.write('ENGINEERING_EVAL_EXIT.json', {'plan_sha256': self.pin, 'exit_code': 0,
            'benchmark_complete': True, 'result_sha256': digest})
        d = D.summarize(self.root, self.pin)
        self.assertEqual(d['reported_speedup'], 1.07); self.assertEqual(d['flags'], [])
        self.assertFalse(d['completion_verified'])
        self.write('results/RESULT.json', dict(report, speedup=2))
        self.assertEqual(D.summarize(self.root, self.pin)['state'], 'needs_inspection')

    def test_malformed_progress_and_oversize_are_bounded(self):
        self.write('results/heartbeat.json', {'completed_pairs': True, 'total_pairs': 13})
        self.assertEqual(D.summarize(self.root, self.pin)['state'], 'needs_inspection')
        (self.root / 'results/heartbeat.json').write_bytes(b'x' * (D.LIMIT + 1))
        self.assertIn('size limit', D.summarize(self.root, self.pin)['flags'][0])


if __name__ == '__main__': unittest.main()
