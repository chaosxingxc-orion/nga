import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import r3_control_dev_service as S

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name)
        self.b={'state_root':str(self.r),'poll_interval_seconds':600,'deployment':{'python':'/usr/bin/python3.11','service':{'path':str(Path(S.__file__).resolve())}}}
    def test_exact_detach_and_no_replay(self):
        with patch.object(S,'load',return_value=(self.b,None)),patch.object(S.subprocess,'run') as run:
            run.return_value.returncode=0
            self.assertEqual(S.start('/config','a')['status'],'start_requested_not_verified')
            self.assertEqual(run.call_args.args[0][:3],['/usr/bin/nohup','/usr/bin/setsid','--fork'])
            self.assertEqual(run.call_args.kwargs['stdin'],S.subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError,'reconciliation'):S.start('/config','a')
            self.assertEqual(run.call_count,1)
    def test_launch_failure_retains_intent_no_retry(self):
        with patch.object(S,'load',return_value=(self.b,None)),patch.object(S.subprocess,'run',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):S.start('/config','a')
            self.assertTrue((self.r/'START_INTENT.json').exists())
            with self.assertRaisesRegex(ValueError,'reconciliation'):S.start('/config','a')
    def test_status_requires_process_and_fresh_digest(self):
        actual={'pid':123,'start_ticks':'1','command':S.argv(self.b,'boot','/config','a'),'session':123}
        S.write(self.r/'SERVICE.json',dict(actual,config_sha256='a'))
        with patch.object(S,'load',return_value=(self.b,None)),patch.object(S,'process',return_value=actual):
            with self.assertRaisesRegex(ValueError,'digest absent'):S.status('/config','a')
            S.write(self.r/'digest.json',{'jobs':{}});S.write(self.r/'heartbeat.json',{})
            self.assertEqual(S.status('/config','a')['status'],'running_verified')
            os.utime(self.r/'heartbeat.json',(1,1))
            with self.assertRaisesRegex(ValueError,'stale'):S.status('/config','a')
    def test_pid_reuse_and_command_mismatch_reject(self):
        actual={'pid':123,'start_ticks':'1','command':S.argv(self.b,'boot','/config','a'),'session':123}
        S.write(self.r/'SERVICE.json',dict(actual,config_sha256='a'))
        with patch.object(S,'load',return_value=(self.b,None)),patch.object(S,'process',return_value=dict(actual,start_ticks='2')):
            with self.assertRaisesRegex(ValueError,'identity'):S.status('/config','a')
    def test_bootstrap_initialization_failure_writes_terminal(self):
        cfg=self.r/'config.json';cfg.write_text(json.dumps(self.b));pin=S.sha(cfg)
        S.write(self.r/'START_INTENT.json',{'config_sha256':pin})
        with patch.object(S,'load',side_effect=ValueError('bad controller')):
            with self.assertRaisesRegex(ValueError,'bad controller'):S.boot(str(cfg),pin)
        self.assertEqual(S.read(self.r/'EXIT.json')['status'],'bootstrap_failed')
    def test_duplicate_boot_does_not_publish_false_terminal(self):
        cfg=self.r/'config.json';cfg.write_text(json.dumps(self.b));pin=S.sha(cfg)
        S.write(self.r/'START_INTENT.json',{'config_sha256':pin});S.write(self.r/'SERVICE.json',{'existing':True})
        with self.assertRaisesRegex(ValueError,'replay forbidden'):S.boot(str(cfg),pin)
        self.assertFalse((self.r/'EXIT.json').exists())
    def test_actual_proc_start_ticks(self):
        self.assertEqual(S.process(os.getpid())['pid'],os.getpid());self.assertTrue(S.process(os.getpid())['start_ticks'].isdigit())
if __name__=='__main__':unittest.main()
