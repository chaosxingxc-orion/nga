import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from test_r3_k2_benchmark_verify import fixture

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
        report = fixture()
        report['plan_sha256'] = self.bp
        digest = self.write('results/RESULT.json', report)
        self.write('results/EXIT.json', {'plan_sha256': self.bp, 'exit_code': 0})
        self.write('ENGINEERING_EVAL_EXIT.json', {'plan_sha256': self.pin, 'exit_code': 0,
            'benchmark_complete': True, 'result_sha256': digest})
        d = D.summarize(self.root, self.pin)
        self.assertEqual(d['reported_speedup'], 1.2); self.assertEqual(d['flags'], [])
        self.assertTrue(d['arithmetic']['arithmetic_verified'])
        self.assertFalse(d['completion_verified'])
        self.write('results/RESULT.json', dict(report, speedup=2))
        self.assertEqual(D.summarize(self.root, self.pin)['state'], 'needs_inspection')

    def test_bound_but_incorrect_arithmetic_is_not_displayed(self):
        report = fixture(); report['plan_sha256'] = self.bp; report['speedup'] = 3
        digest = self.write('results/RESULT.json', report)
        self.write('results/EXIT.json', {'plan_sha256': self.bp, 'exit_code': 0})
        self.write('ENGINEERING_EVAL_EXIT.json', {'plan_sha256': self.pin, 'exit_code': 0,
            'benchmark_complete': True, 'result_sha256': digest})
        d = D.summarize(self.root, self.pin)
        self.assertEqual(d['state'], 'needs_inspection')
        self.assertNotIn('reported_speedup', d)
        self.assertIn('summary differs', d['flags'][0])

    def test_malformed_progress_and_oversize_are_bounded(self):
        self.write('results/heartbeat.json', {'completed_pairs': True, 'total_pairs': 13})
        self.assertEqual(D.summarize(self.root, self.pin)['state'], 'needs_inspection')
        (self.root / 'results/heartbeat.json').write_bytes(b'x' * (D.LIMIT + 1))
        self.assertIn('size limit', D.summarize(self.root, self.pin)['flags'][0])

    def bind_report(self, report):
        digest = self.write('results/RESULT.json', report)
        self.write('results/EXIT.json', {'plan_sha256': self.bp, 'exit_code': 0})
        self.write('ENGINEERING_EVAL_EXIT.json', {'plan_sha256': self.pin, 'exit_code': 0,
            'benchmark_complete': True, 'result_sha256': digest})

    def test_review_nonobject_metadata_and_nested_json_are_bounded(self):
        for name in ('execution.json', 'plan.json', 'digest.json', 'results/heartbeat.json',
                     'ENGINEERING_EVAL_EXIT.json', 'results/EXIT.json', 'results/RESULT.json'):
            with self.subTest(name=name):
                report = fixture(); report['plan_sha256'] = self.bp; self.bind_report(report)
                path = self.root/name; old = path.read_bytes() if path.exists() else None
                try:
                    self.write(name, [])
                    self.assertEqual(D.summarize(self.root,self.pin)['state'],'needs_inspection')
                finally:
                    if old is None: path.unlink()
                    else: path.write_bytes(old)
        (self.root/'results/heartbeat.json').write_text('['*1100+'0'+']'*1100)
        self.assertEqual(D.summarize(self.root,self.pin)['state'],'needs_inspection')

    def test_review_overflow_duplicates_and_integer_types(self):
        for field in ('seconds', 'tokens'):
            report = fixture(); report['plan_sha256'] = self.bp
            for arm in ('reference','candidate'):
                target=report['rows'][3][arm]
                if field=='tokens': target=target['stats']
                target[field]=10**400
            self.bind_report(report)
            self.assertEqual(D.summarize(self.root,self.pin)['state'],'needs_inspection')
        report=fixture();report['plan_sha256']=self.bp;self.bind_report(report)
        path=self.root/'results/RESULT.json';raw=path.read_bytes();path.write_bytes(b'{"speedup":999,'+raw[1:])
        self.write('ENGINEERING_EVAL_EXIT.json',{'plan_sha256':self.pin,'exit_code':0,
            'benchmark_complete':True,'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        self.assertIn('duplicate',D.summarize(self.root,self.pin)['flags'][0])
        self.bind_report(report)
        for value in (False,0.0):
            self.write('results/EXIT.json',{'plan_sha256':self.bp,'exit_code':value})
            self.assertEqual(D.summarize(self.root,self.pin)['state'],'needs_inspection')
        self.bind_report(report)
        self.write('results/heartbeat.json',{'completed_pairs':13,'total_pairs':13.0})
        self.assertEqual(D.summarize(self.root,self.pin)['state'],'needs_inspection')


if __name__ == '__main__': unittest.main()
