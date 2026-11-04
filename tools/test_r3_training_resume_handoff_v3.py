"""Complete builder + post-build capture regression; review_check is never mocked."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_r3_training_resume_handoff_v2 as prior
import r3_training_resume_handoff_v3 as M

class PrepareComplete(prior.InlineRecovery):
 def fixture(self):
  self.completed()
  self.p['arm']='k1-pt'
  self.c['training_plan']['sha256']=self.put(self.train/'plan.json',self.p)
  self.c.update(evaluation_out=str(self.r/'fresh-dev'),relocated_command_flags=['--adapter','--out','--round-dir'])
  closure=self.r/'closure';closure.mkdir()
  template=['python3','scoring.py','--arm','K1-PT','--model-path',M.MODEL,'--adapter','<COMPLETED_ADAPTER>','--out','<FRESH_EVAL_OUTPUT>','--round-dir','<FRESH_IDENTITY_CACHE>']
  cp=closure/'manifest.json';self.put(cp,{'evaluation_profile':'track_kt','data':{},'code':{},'mounts':[],'command_template':template})
  self.c['closure']={'path':str(cp),'sha256':M.sha(cp)}
  tp=self.r/'protocol.json';self.put(tp,{'command':template});self.c['protocol_template']={'path':str(tp),'sha256':M.sha(tp)}
  cap=M.capture(self.c,self.p,self.j,self.H,self.B);self.put(self.state/'CAPTURE.json',cap)
  rp=self.r/'independent-review.json';ep=self.r/'actual-collection.json';self.put(ep,{'fixture':True})
  checks={k:True for k in ('genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116','recovery_checkpoint_and_step_identity','recovery_predecessor_identity_and_release','observation_origin_authenticated')}
  self.put(rp,{'schema':'r3-recovery-independent-postrun-v1','verdict':'PASS','independent':True,'binding_sha256':self.c['_pin'],'capture_sha256':M.sha(self.state/'CAPTURE.json'),'training_plan_sha256':self.c['training_plan']['sha256'],'files':cap['files'],'scientific_acceptance':False,'test_read':False,'checks':checks,'evidence_files':{str(ep):M.sha(ep)}})
  return {'path':str(rp),'sha256':M.sha(rp)}
 def test_real_builder_and_final_review_success_restore(self):
  review=self.fixture();semantic=self.B.semantic_arm
  with patch.object(M,'identity',return_value=(self.c,self.p,self.j,self.H,self.B)):
   result=M.prepare('fixture','binding',review)
  self.assertEqual(result['status'],'prepared');self.assertIs(self.B.semantic_arm,semantic)
  self.assertTrue((self.state/'PREPARED.json').exists())
  # The final unmocked capture and review still agree after actual preparation.
  M.review_check(self.c,self.p,self.j,self.H,self.B,review)
  with patch.object(M,'identity',return_value=(self.c,self.p,self.j,self.H,self.B)):
   with self.assertRaisesRegex(ValueError,'never retry'):M.prepare('fixture','binding',review)
 def test_builder_exception_restores_and_retains_intent(self):
  review=self.fixture();semantic=self.B.semantic_arm
  with patch.object(M,'identity',return_value=(self.c,self.p,self.j,self.H,self.B)),patch.object(self.B,'prepare',side_effect=OSError('injected builder failure')):
   with self.assertRaisesRegex(OSError,'injected'):M.prepare('fixture','binding',review)
  self.assertIs(self.B.semantic_arm,semantic);self.assertTrue((self.state/'PREPARE_INTENT.json').exists());self.assertFalse((self.state/'PREPARED.json').exists())
 def test_real_postcheck_mutation_rejected(self):
  review=self.fixture();original=self.B.prepare;semantic=self.B.semantic_arm
  def builder(*a):
   result=original(*a);d=M.read(self.train/'manifest.json');d['summary']['final_step']=3115;self.put(self.train/'manifest.json',d);return result
  with patch.object(M,'identity',return_value=(self.c,self.p,self.j,self.H,self.B)),patch.object(self.B,'prepare',side_effect=builder):
   with self.assertRaisesRegex(ValueError,'manifest identity'):M.prepare('fixture','binding',review)
  self.assertIs(self.B.semantic_arm,semantic);self.assertFalse((self.state/'PREPARED.json').exists())

if __name__=='__main__':unittest.main()
