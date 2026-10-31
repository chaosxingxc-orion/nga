import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('handoff',Path(__file__).with_name('r3_engineering_handoff.py'))
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)


class HandoffTests(unittest.TestCase):
    def test_release_required_and_failed_run_can_release_without_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);attempt=out/'attempts/1';attempt.mkdir(parents=True)
            job={'previous_out':td,'previous_container':'old','chip':6}
            self.assertFalse(H.ready(job))
            (attempt/'RELEASE.json').write_text(json.dumps({'container_id':'cid','exit_code':1,'chip':6,'scientific_acceptance':False}))
            (attempt/'LAUNCH_RECEIPT.json').write_text(json.dumps({'id':'cid'}))
            (out/'TRAIN_EXIT.json').write_text(json.dumps({'exit_code':1}))
            actual={'Id':'cid','State':{'Status':'running','ExitCode':1}}
            with patch.object(H,'inspect',return_value=actual):
                with self.assertRaises(RuntimeError):H.ready(job)
                actual['State']['Status']='exited'
                self.assertTrue(H.ready(job))
                actual['Id']='replacement'
                with self.assertRaises(RuntimeError):H.ready(job)

    def test_missing_container_and_daemon_failure_differ(self):
        import subprocess
        with patch.object(H.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','error: no such object: x')):
            self.assertIsNone(H.inspect('x'))
        with patch.object(H.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','daemon unreachable')):
            with self.assertRaises(RuntimeError):H.inspect('x')


if __name__=='__main__':unittest.main()
