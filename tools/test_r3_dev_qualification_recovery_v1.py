import importlib.util
from pathlib import Path
import types
import unittest

spec=importlib.util.spec_from_file_location('wrapper',Path(__file__).with_name('r3_dev_qualification_recovery_v1.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.original=M.original_member;self.verify=M.H.verify_recovery
        self.addCleanup(setattr,M,'original_member',self.original);self.addCleanup(setattr,M.H,'verify_recovery',self.verify)
        self.events=[];M.original_member=lambda *a:self.events.append('frozen') or {'result':'frozen'}
        M.H.verify_recovery=lambda *a:self.events.append('recovery')
    def invoke(self,execution,entry):
        api=types.SimpleNamespace(Q=types.SimpleNamespace(bound=lambda *a:execution))
        return M.member('diffchip_s2',dict(execution='p',**entry),{},dict(files={}),api)
    def test_nonrecovery_preserves_frozen_path(self):
        self.assertEqual(self.invoke({},{}),{'result':'frozen'});self.assertEqual(self.events,['frozen'])
    def test_recovery_requires_external_review(self):
        self.assertRaises(ValueError,self.invoke,{'resume_import':{}},{});self.assertEqual(self.events,[])
    def test_recovery_checked_before_frozen(self):
        self.invoke({'resume_import':{}},{'recovery_result_review':{'path':'x','sha256':'y'}});self.assertEqual(self.events,['recovery','frozen'])
    def test_extra_recovery_claim_rejected(self):
        self.assertRaises(ValueError,self.invoke,{},dict(recovery_result_review={}));self.assertEqual(self.events,[])
    def test_recovery_failure_cannot_fall_through(self):
        def fail(*a):raise ValueError('invalid provenance')
        M.H.verify_recovery=fail;self.assertRaises(ValueError,self.invoke,{'resume_import':{}},dict(recovery_result_review={}));self.assertEqual(self.events,[])

if __name__=='__main__':unittest.main()
