import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('digest',Path(__file__).with_name('r3_training_digest.py'))
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)


class DigestTests(unittest.TestCase):
    def test_total_work_rate_and_terminal_step_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'plan.json').write_text(json.dumps({'model':'/model','stop_after':8}))
            rows=[dict(step=i,loss=1.,grad_norm=1.,step_s=1. if i<7 else 9.,tokens=10,base_questions=1) for i in range(1,8)]
            (root/'losses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            x=D.summarize(root)
            self.assertEqual(x['throughput']['tokens_per_second_per_chip'],2.)
            (root/'TRAIN_EXIT.json').write_text(json.dumps({'exit_code':0}))
            self.assertIn('successful_exit_without_expected_final_step',D.summarize(root)['issues'])

    def test_live_partial_tail_not_completed_and_nan_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'plan.json').write_text(json.dumps({'model':'/model'}))
            row=dict(step=1,loss=float('nan'),grad_norm=1.,step_s=1.,tokens=10,base_questions=1)
            (root/'losses.jsonl').write_text(json.dumps(row)+'\n{"step":2')
            x=D.summarize(root)
            self.assertTrue(x['partial_tail_ignored']);self.assertEqual(x['completed_steps'],1)
            self.assertIn('nonfinite_or_missing_training_measurement',x['issues'])


if __name__=='__main__':unittest.main()
