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
    def rows(self, seconds=1.0):
        return [dict(step=i, loss=1.0, grad_norm=1.0, step_s=seconds,
                     tokens=100, base_questions=10) for i in range(1, 86)]

    def test_longer_common_window_preserves_duration_gate(self):
        measured, diagnostic = P.measurement_window(self.rows(), 'fast_ref')
        self.assertEqual(len(measured), 80)
        self.assertEqual(diagnostic['measured_seconds'], 80)
        self.assertTrue(diagnostic['valid'])
        _, short = P.measurement_window(self.rows(.5), 'fast_ref')
        self.assertFalse(short['valid'])
        self.assertEqual(short['measured_seconds'], 40)
        self.assertEqual(short['minimum_seconds'], 60)

    def test_invalid_times_and_step_sequences_rejected(self):
        rows = self.rows(2.0); rows[6]['step_s'] = 0
        _, diagnostic = P.measurement_window(rows, 'ref')
        self.assertGreater(diagnostic['measured_seconds'], 60)
        self.assertEqual(diagnostic['nonpositive_time_count'], 1)
        self.assertFalse(diagnostic['valid'])
        rows[6]['step_s'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            P.measurement_window(rows, 'ref')
        with self.assertRaisesRegex(ValueError, 'step sequence'):
            P.measurement_window(self.rows()[:45], 'ref')

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
