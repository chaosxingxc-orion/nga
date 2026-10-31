import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('driver',Path(__file__).with_name('r3_final_driver.py'))
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)


class Driver(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'out';self.plan=self.root/'plan.json'
        p={'out':str(self.out)};self.plan.write_text(json.dumps(p))
        self.pin=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.review={'path':str(self.root/'review.json'),'sha256':'b'*64}

    def test_success_retains_result_terminal_and_heartbeat(self):
        with patch.object(D,'evaluate',return_value={'state':'completed','scientific_acceptance':False}):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),0)
        directory=self.out/'final-attempts/1'
        self.assertEqual(json.loads((directory/'EXIT.json').read_text())['exit_code'],0)
        self.assertTrue((directory/'heartbeat.json').exists())
        self.assertTrue((directory/'COMMAND.txt').exists())
        self.assertEqual((directory/'EXIT.json').stat().st_mode & 0o777,0o644)
        self.assertFalse(json.loads((directory/'EXIT.json').read_text())['scientific_acceptance'])

    def test_failure_retained_then_new_attempt_does_not_erase_evidence(self):
        with patch.object(D,'evaluate',side_effect=ValueError('admission failure')):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),1)
        with patch.object(D,'evaluate',return_value={'state':'completed'}):
            self.assertEqual(D.run(self.plan,self.pin,self.review,2),0)
        self.assertEqual(json.loads((self.out/'final-attempts/1/EXIT.json').read_text())['exit_code'],1)
        self.assertEqual(json.loads((self.out/'FINAL_EVAL_EXIT.json').read_text())['attempt'],2)
        with self.assertRaises(FileExistsError):D.run(self.plan,self.pin,self.review,2)

    def test_unpinned_plan_never_creates_output(self):
        with self.assertRaisesRegex(ValueError,'plan differs'):D.run(self.plan,'f'*64,self.review,1)
        self.assertFalse(self.out.exists())

    def test_terminal_records_process_level_exception(self):
        with patch.object(D,'evaluate',side_effect=KeyboardInterrupt):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),1)
        self.assertEqual(json.loads((self.out/'FINAL_EVAL_EXIT.json').read_text())['exit_code'],1)


if __name__=='__main__':unittest.main()
