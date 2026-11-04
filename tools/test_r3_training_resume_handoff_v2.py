"""Real inline-supervisor evidence contract, without fake legacy receipt."""
import datetime,importlib.util,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_r3_training_resume_handoff_v1 as base
from unittest.mock import patch
import r3_training_resume_handoff_v2 as M

class InlineRecovery(base.RecoveryHandoff):
 def setUp(self):
  super().setUp()
  self.p['launcher']=str(self.train/'launcher.py')
  Path(self.p['launcher']).write_text('# frozen fixture launcher\n')
  self.p['files']={self.p['launcher']:M.sha(self.p['launcher'])}
 def completed(self):
  super().completed();(self.train/'SUPERVISOR_RECEIPT.json').unlink()
  service={'pid':123,'start_ticks':456,'boot_id':'12345678-1234-1234-1234-123456789abc','command':['/usr/bin/python3.12','-B','-P',self.p['launcher'],'watch','--plan',self.j['training_plan']['path'],'--sha256','canonical']}
  self.put(self.train/'SERVICE.json',service)
  intent={'plan':self.j['training_plan']['path'],'sha256':'canonical'}
  self.put(self.train/'SERVICE-START-INTENT.json',intent)
  pre=self.put(self.train/'SUCCESSOR_PRECONDITION.json',{'plan_sha256':'canonical','checkpoint_sha256':'checkpoint-pin'})
  self.put(self.train/'LAUNCH-INTENT.json',dict(intent,precondition_sha256=pre))
  self.put(self.train/'ROOT-SERVICE-VERIFIED.json',{'service':service,'generation_verified':True,'npu_started_asserted':False,'utc_seconds':1793750300})
  self.put(self.train/'SERVICE_EXIT.json',{'exit_code':0,'status':'supervisor_complete','scientific_acceptance':False,'utc_seconds':1793754100})
 def capture(self):return M.capture(self.c,self.p,self.j,self.H,self.B)
 def test_review_missing_recovery_check_rejected(self):
  with patch.object(base, "M", M): super().test_review_missing_recovery_check_rejected()
 def test_partial_completion_waits(self):
  self.put(self.train/'TRAIN_EXIT.json',{'exit_code':0,'attempt':1});self.assertEqual(self.capture()['status'],'waiting_inline_supervisor_evidence')
 def test_missing_receipt_not_required_but_real_evidence_is(self):
  self.completed();d=self.capture();self.assertEqual(d['status'],'REVIEW_REQUIRED');self.assertEqual(len(d['inline_supervisor_evidence']),6);self.assertFalse((self.train/'SUPERVISOR_RECEIPT.json').exists())
  (self.train/'SERVICE.json').unlink();self.assertEqual(self.capture()['status'],'waiting_inline_supervisor_evidence')
 def test_wrong_process_generation_rejected(self):
  self.completed();p=self.train/'SERVICE.json';d=M.read(p);d['start_ticks']+=1;self.put(p,d)
  with self.assertRaisesRegex(ValueError,'observation differs'):self.capture()
 def test_wrong_launch_binding_rejected(self):
  self.completed();p=self.train/'LAUNCH-INTENT.json';d=M.read(p);d['precondition_sha256']='wrong';self.put(p,d)
  with self.assertRaisesRegex(ValueError,'launch intent'):self.capture()
 def test_failed_service_not_accepted(self):
  self.completed();p=self.train/'SERVICE_EXIT.json';d=M.read(p);d['exit_code']=1;self.put(p,d)
  with self.assertRaisesRegex(ValueError,'supervisor incomplete'):self.capture()
 def test_changed_launcher_rejected(self):
  self.completed();Path(self.p['launcher']).write_text('changed')
  with self.assertRaisesRegex(ValueError,'launcher changed'):self.capture()
 def test_future_observation_rejected(self):
  self.completed();p=self.train/'ROOT-SERVICE-VERIFIED.json';d=M.read(p);d['utc_seconds']=9999999999;self.put(p,d)
  with self.assertRaisesRegex(ValueError,'chronology'):self.capture()

if __name__=='__main__':unittest.main()
