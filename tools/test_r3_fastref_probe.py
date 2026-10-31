import importlib.util
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('r3_fastref_probe.py'))
P=importlib.util.module_from_spec(s);s.loader.exec_module(P)


class ProbeStages(unittest.TestCase):
    def test_real_failure_stops_and_cannot_be_silently_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'plan.json').write_text(json.dumps({'files':{}}))
            with patch.object(P.time,'sleep'):
                with self.assertRaisesRegex(RuntimeError,'stage failed'):
                    P.stage(root,'contract',[sys.executable,'-c','raise SystemExit(7)'])
            self.assertEqual(json.loads((root/'contract.json').read_text())['exit_code'],7)
            with patch.object(P.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError,'explicit repair'):P.stage(root,'contract',[])
                spawn.assert_not_called()

    def test_changed_frozen_file_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); dep=root/'input';dep.write_text('original')
            (root/'plan.json').write_text(json.dumps({'files':{str(dep):hashlib.sha256(dep.read_bytes()).hexdigest()}}))
            dep.write_text('changed')
            with patch.object(P.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError,'frozen input changed'):
                    P.stage(root,'contract',[sys.executable,'-c','pass'])
                spawn.assert_not_called()

    def test_success_retained_and_ambiguous_intent_never_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'plan.json').write_text(json.dumps({'files':{}}))
            with patch.object(P.time,'sleep'):P.stage(root,'one',[sys.executable,'-c','print("ok")'])
            with patch.object(P.subprocess,'Popen') as spawn:
                P.stage(root,'one',[sys.executable,'-c','print("ok")']);spawn.assert_not_called()
                with self.assertRaisesRegex(RuntimeError,'identity mismatch'):P.stage(root,'one',[])
                (root/'plan.json').write_text(json.dumps({'files':{},'changed':True}))
                with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
                    P.stage(root,'one',[sys.executable,'-c','print("ok")'])
                (root/'two-INTENT.json').write_text('{}')
                with self.assertRaisesRegex(RuntimeError,'ambiguous'):P.stage(root,'two',[])
                spawn.assert_not_called()


if __name__=='__main__':unittest.main()
