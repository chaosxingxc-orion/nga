import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('owned_watchdog', Path(__file__).with_name('watchdog.py'))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class RecoveryAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'heartbeat.json'
        self.base = {'utc': '2026-11-06T13:26:10.137787+00:00', 'results': {}, 'total': 8}
    def read(self, obj):
        self.path.write_text(json.dumps(obj))
        return w.read_json_heartbeat(self.path)
    def test_actual_and_terminal_attempts(self):
        sample, err = self.read(self.base)
        self.assertIsNone(err); self.assertEqual((sample['done'], sample['total']), (0, 8))
        obj = dict(self.base, results={'lane1': 'complete', 'lane2': 'FAILED: failure'})
        sample, err = self.read(obj)
        self.assertIsNone(err); self.assertEqual(sample['done'], 2)
        cfg = w.make_cfg(root=[self.tmp.name], out_dir=self.tmp.name, no_npu=True)
        progress = w.summarize_progress([sample], self.tmp.name, cfg)
        self.assertIn('terminal lane attempts, including failures', progress['note'])
        self.assertIsNone(progress['eta_utc'])
    def test_invalid_and_unknown(self):
        for changes in ({'results': []}, {'results': None}, {'results': {'x': 'running'}},
                        {'results': {'x': 1}}, {'results': {'': 'complete'}},
                        {'results': {str(i): 'complete' for i in range(9)}},
                        {'total': True}, {'total': 9}, {'extra': 'unknown'}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.read(dict(self.base, **changes))[0])
    def test_explicit_completed_preserved_and_validated(self):
        sample, err = self.read(dict(self.base, completed=3, results={'x': 'complete'}))
        self.assertIsNone(err); self.assertEqual(sample['done'], 3)
        self.assertFalse(sample['recovery_attempts'])
        self.assertIsNone(self.read(dict(self.base, completed=True))[0])
        self.assertIsNone(self.read(dict(self.base, completed=9))[0])

if __name__ == '__main__': unittest.main()
