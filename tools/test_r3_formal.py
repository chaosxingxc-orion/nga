import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('launch', HERE / 'r3_formal_launcher.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


class Formal(unittest.TestCase):
    def test_uncertain_observation_retries_same_generation(self):
        with tempfile.TemporaryDirectory() as td:
            heartbeat = Path(td) / 'heartbeat.json'
            actual = {'Id': 'same', 'State': {'Status': 'running'}}
            with patch.object(L, 'inspect', side_effect=[RuntimeError('daemon timeout'), None, actual]) as query:
                seen = L.observe_retained('retained', 'same', heartbeat, sleep=lambda _: None)
            self.assertEqual(seen, actual)
            self.assertEqual(query.call_count, 3)
            self.assertEqual(json.loads(heartbeat.read_text())['action'], 'retry_without_restart_or_release')

    def test_container_cannot_see_cephfs_or_test(self):
        p = {'container':'test','chip':1,'code':'/run/code','out':'/run', 'model':'/models/qwen',
             'train_file':'/data/train.jsonl','environment':{'NGA_R0_CODE':'/workspace/r0_code'},'image_sha256':L.IMAGE}
        cmd = L.docker_command(p, '/run/plan.json', 1)
        self.assertIn('--network=none', cmd)
        self.assertIn('--pull=never', cmd)
        self.assertNotIn('--rm', cmd)
        mounts = [cmd[i+1] for i,x in enumerate(cmd) if x=='--mount']
        self.assertEqual(len(mounts),5)
        self.assertTrue(all('test' not in x and 'src=/mnt/cephfs,' not in x for x in mounts))
        self.assertIn('type=bind,src=/run/code,dst=/workspace,readonly', mounts)

    def test_review_hash_does_not_cycle_plan_identity(self):
        p = {'schema':'fixture','review_sha256':'PENDING'}
        self.assertEqual(L.identity(p),L.identity(dict(p,review_sha256='abc')))
        self.assertNotEqual(L.identity(p),L.identity(dict(p,schema='changed')))

    def test_driver_startup_error_has_terminal_and_log(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'plan.json').write_text(json.dumps({'out':td,'command':['/missing/executable']}))
            r=subprocess.run([sys.executable,str(HERE/'r3_formal_driver.py'),'--plan',str(root/'plan.json'),'--attempt','1'])
            self.assertEqual(r.returncode,125)
            terminal=json.loads((root/'TRAIN_EXIT.json').read_text())
            self.assertEqual(terminal['exit_code'],125)
            self.assertFalse(terminal['scientific_acceptance'])
            self.assertTrue((root/'attempts/1/FAILED').exists())
            self.assertIn('FileNotFoundError',(root/'attempts/1/run.log').read_text())

    def test_driver_failure_and_success_markers_separate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for attempt,rc in ((1,3),(2,0)):
                (root/'plan.json').write_text(json.dumps({'out':td,'command':[sys.executable,'-c',f'raise SystemExit({rc})']}))
                r=subprocess.run([sys.executable,str(HERE/'r3_formal_driver.py'),'--plan',str(root/'plan.json'),'--attempt',str(attempt)])
                self.assertEqual(r.returncode,rc)
            self.assertTrue((root/'attempts/1/FAILED').exists())
            self.assertTrue((root/'attempts/2/DONE').exists())
            self.assertEqual(json.loads((root/'TRAIN_EXIT.json').read_text())['attempt'],2)


if __name__ == '__main__':
    unittest.main()
