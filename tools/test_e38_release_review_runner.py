"""Review runner identity and terminal checks in isolated fixture directories."""
import importlib.util
import json
import sys
import subprocess
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('review_runner',Path(__file__).with_name('e38_release_review_runner.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


class ReviewRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bundle=self.root/'bundle';self.bundle.mkdir()
        self.member=self.bundle/'code.py';self.member.write_text('x = 1\n')
        r.durable(self.bundle/'MANIFEST.json',dict(files=[dict(path='code.py',size=self.member.stat().st_size,sha256=r.sha(self.member))]))
        self.hash=r.sha(self.bundle/'MANIFEST.json');self.out=self.root/'review'
    def test_manifest_rejects_extra_changed_and_symlink_files(self):
        r.verify(self.bundle,self.hash)
        self.member.write_text('x = 2\n')
        with self.assertRaises(ValueError):r.verify(self.bundle,self.hash)
        self.member.write_text('x = 1\n');extra=self.bundle/'extra';extra.write_text('x')
        with self.assertRaises(ValueError):r.verify(self.bundle,self.hash)
        extra.unlink();saved=self.root/'saved';self.member.rename(saved);self.member.symlink_to(saved)
        with self.assertRaises(ValueError):r.verify(self.bundle,self.hash)
    def test_prepare_is_no_launch_and_no_overwrite(self):
        r.prepare(self.out,self.bundle,self.hash)
        self.assertFalse((self.out/'PROCESS.json').exists())
        with self.assertRaises(FileExistsError):r.prepare(self.out,self.bundle,self.hash)
        r.verify(self.bundle,self.hash)
    def run_real_child(self, exit_code=0, sleep=0, timeout=5):
        # Only substitute the command. Popen, process-group creation, signals
        # and wait are real; no model CLI or network is used by these fixtures.
        original = subprocess.Popen
        code = ('import sys,time; from pathlib import Path; '
                'time.sleep(float(sys.argv[2])); '
                'Path(sys.argv[1]).write_text("Fixture review, no actual Astra verdict. "*20); '
                'sys.exit(int(sys.argv[3]))')
        children=[]
        def fixture_command(cmd, **kwargs):
            self.assertIn('gpt-6-astra',cmd)
            child=original([sys.executable,'-I','-c',code,str(self.out/'review.md'),str(sleep),str(exit_code)],**kwargs)
            children.append(child);return child
        with patch.object(r.subprocess,'Popen',side_effect=fixture_command), patch.object(r,'REVIEW_TIMEOUT_SECONDS',timeout), patch.object(r,'TERMINATE_GRACE_SECONDS',1):
            result=r.run(self.out)
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].returncode)
        recorded=json.loads((self.out/'CHILD_EXIT.json').read_text())
        self.assertEqual(recorded['pid'],children[0].pid)
        self.assertEqual(recorded['wait_returncode'],children[0].returncode)
        return result,children[0].returncode

    def test_runner_records_actual_wait_result_with_real_fixture_process(self):
        r.prepare(self.out,self.bundle,self.hash)
        result,child_rc=self.run_real_child()
        self.assertEqual((result,child_rc),(0,0))
        self.assertEqual(json.loads((self.out/'COMPLETE.json').read_text())['rc'],0)
        self.assertEqual(json.loads((self.out/'EXIT.json').read_text())['rc'],0)
        with self.assertRaises(ValueError):r.launch(self.out)

    def test_runner_real_child_failure_is_not_completed_success(self):
        r.prepare(self.out,self.bundle,self.hash)
        result,child_rc=self.run_real_child(exit_code=7)
        self.assertEqual((result,child_rc),(1,7))
        self.assertEqual(json.loads((self.out/'COMPLETE.json').read_text())['rc'],1)
        self.assertEqual(json.loads((self.out/'EXIT.json').read_text())['rc'],1)

    def test_runner_real_child_timeout_is_terminated_and_reaped(self):
        r.prepare(self.out,self.bundle,self.hash)
        result,child_rc=self.run_real_child(sleep=10,timeout=0.1)
        self.assertEqual(result,1);self.assertLess(child_rc,0)
        self.assertEqual(json.loads((self.out/'EXIT.json').read_text())['rc'],1)
        self.assertIn('timeout',json.loads((self.out/'COMPLETE.json').read_text())['reason'])

    def test_heartbeat_pending_failure_still_writes_failed_exit(self):
        r.prepare(self.out,self.bundle,self.hash)
        pending=self.out/'digest.json.pending';pending.write_text('uncertain heartbeat')
        result,child_rc=self.run_real_child(sleep=0.05)
        self.assertEqual((result,child_rc),(1,0))
        self.assertEqual(pending.read_text(),'uncertain heartbeat')
        terminal=json.loads((self.out/'COMPLETE.json').read_text())
        self.assertEqual(terminal['rc'],1);self.assertIn('Heartbeat failed',terminal['reason'])
        self.assertEqual(json.loads((self.out/'EXIT.json').read_text())['rc'],1)

    def test_complete_pending_failure_does_not_hide_exit(self):
        r.prepare(self.out,self.bundle,self.hash)
        pending=self.out/'COMPLETE.json.pending';pending.write_text('uncertain terminal')
        result,child_rc=self.run_real_child()
        self.assertEqual((result,child_rc),(1,0))
        self.assertFalse((self.out/'COMPLETE.json').exists())
        self.assertEqual(pending.read_text(),'uncertain terminal')
        terminal=json.loads((self.out/'EXIT.json').read_text())
        self.assertEqual(terminal['rc'],1);self.assertIn('Terminal publication failed',terminal['reason'])

if __name__=='__main__':unittest.main()
