"""Scope and failure regressions; actual training check lives in preparation evidence."""
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r3_dev_qualification_recovery_v2 as M

class Composition(unittest.TestCase):
 def api(self,plan=None,execution=None):
  values={'plan':plan or {},'execution':execution or {}}
  return types.SimpleNamespace(Q=types.SimpleNamespace(bound=lambda path,files:values[path]))
 def test_ordinary_member_calls_exact_v1(self):
  entry={'plan':'plan','execution':'execution'};api=self.api();decision={'existing':True};bundle={'files':{}}
  with patch.object(M.V,'member',return_value='original') as old:
   self.assertEqual(M.member('primary_s2',entry,decision,bundle,api),'original');old.assert_called_once_with('primary_s2',entry,decision,bundle,api)
 def test_ordinary_cannot_carry_recovery_binding(self):
  with self.assertRaisesRegex(ValueError,'ordinary'):
   M.member('primary_s2',{'plan':'plan','recovered_training':{}},None,{'files':{}},self.api())
 def test_other_training_recovery_rejected(self):
  with self.assertRaisesRegex(ValueError,'pt_s2'):
   M.member('pt_s3',{'plan':'plan'},None,{'files':{}},self.api({'recovery':{}}))
 def test_training_recovery_cannot_imply_dev_import_authority(self):
  with self.assertRaisesRegex(ValueError,'imported DEV'):
   M.member('pt_s2',{'plan':'plan','execution':'execution'},None,{'files':{}},self.api({'recovery':{}},{'resume_import':{}}))
 def test_scoped_callbacks_do_not_change_original_globals(self):
  def frozen(name,entry,decision,bundle,api):
   p=api.Q.bound(entry['plan'],bundle['files'])
   return verify_prelaunch(name,entry,p,decision,bundle['files'],api),training_runtime(entry,p,decision,api,bundle['files'])
  before=dict(frozen.__globals__);entry={'plan':'plan','execution':'execution'};api=self.api({'recovery':{}})
  with patch.object(M.V,'original_member',frozen),patch.object(M.T,'verify',return_value={'prelaunch_completed':1,'training':{'start':2}}):
   self.assertEqual(M.member('pt_s2',entry,{}, {'files':{}},api),(1,{'start':2}))
  self.assertEqual(frozen.__globals__,before)
 def test_missing_external_decision_rejected_before_loading(self):
  q=types.SimpleNamespace(label=lambda p:'K1-PT')
  with self.assertRaisesRegex(ValueError,'adjudication'):
   M.T.verify('pt_s2',{'arm':'K1-PT','seed':2,'plan':'plan'},{'chip':3,'recovery':{'schema':'formal-pt2-checkpoint-recovery-v1'}},None,{},q)
 def test_boolean_seed_refused(self):
  with self.assertRaisesRegex(ValueError,'seed2'):
   M.T.verify('pt_s2',{'arm':'K1-PT','seed':True},{},None,{},None)

if __name__=='__main__':unittest.main()
