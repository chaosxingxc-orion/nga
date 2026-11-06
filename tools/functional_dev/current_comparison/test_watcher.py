"""CPU watcher checks; no review artifact is synthesized or model work launched."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('watch_fixture',HERE/'fixtures.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
spec=importlib.util.spec_from_file_location('watch_tests',HERE/'watcher.py');W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=HERE/'scratch');self.addCleanup(self.tmp.cleanup)
        self.config,self.inspections=F.build(self.tmp.name)
        self.config['poll_seconds']=600
    def test_no_review_waits(self):
        self.assertFalse(W.review(self.config));self.config['mode']='production';self.assertEqual(W.run(self.config,once=True),2)
        self.assertEqual(W.M.obj(Path(self.config['output'])/'comparison.json')['status'],'PENDING_INDEPENDENT_REVIEW')
    def test_fingerprint_stat_only(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('no file content polling')):
            a=W.fingerprint(self.config);self.assertEqual(a,W.fingerprint(self.config))
        p=Path(self.config['k0_root'])/'08b-k0'/'score-EXIT.json';p.write_text('{}');self.assertNotEqual(a,W.fingerprint(self.config))
    def test_adapter_publication_change_detected(self):
        before=W.fingerprint(self.config);p=Path(self.config['lanes'][0]['new_adapter'])/'BINDING.json';p.write_text('{}');self.assertNotEqual(before,W.fingerprint(self.config))
    def test_unchanged_skips_recompute(self):
        self.config['mode']='production';c=object()
        results=[({'status':'INCOMPLETE_PENDING','operands':[]},2),({'status':'MATCHED_CURRENT_DESCRIPTIVE_DEV','operands':[]},0)]
        samples=iter([['first'],['first'],['first'],['changed'],['changed']])
        with patch.object(W,'review',return_value=True),patch.object(W,'fingerprint',side_effect=lambda x:next(samples)),patch.object(W.M,'Consumer',return_value=c),patch.object(W.M,'assemble',side_effect=results) as run,patch.object(W.time,'sleep') as sleep:
            self.assertEqual(W.run(self.config),0);self.assertEqual(run.call_count,2);self.assertEqual(sleep.call_args_list,[unittest.mock.call(600),unittest.mock.call(600)])
    def test_change_during_reconstruction_refused(self):
        self.config['mode']='production'
        with patch.object(W,'review',return_value=True),patch.object(W,'fingerprint',side_effect=[['before'],['after']]),patch.object(W.M,'Consumer'),patch.object(W.M,'assemble',return_value=({'status':'MATCHED_CURRENT_DESCRIPTIVE_DEV','operands':[]},0)):
            with self.assertRaisesRegex(W.M.Contradiction,'changed during'):W.run(self.config,once=True)
    def test_fixture_watcher_not_allowed(self):
        with self.assertRaises(W.M.Contradiction):W.run(self.config,once=True)

if __name__=='__main__':unittest.main(verbosity=2)
