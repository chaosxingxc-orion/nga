import hashlib,json,tempfile,unittest,types,importlib.util
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('h',HERE/'r3_training_resume_handoff_v1.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
def load(path):
 m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
class RecoveryHandoff(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name);self.train=self.r/'training';self.train.mkdir();self.state=self.r/'state';self.state.mkdir()
  self.H=load(HERE/'r3_formal_wave_handoff.py');self.B=load(HERE/'r3_posttrain_eval_plan.py')
  self.p={'out':str(self.train),'run':'r3_runs/recovered','container':'recovered','chip':3,'image_sha256':'image','model':M.MODEL,'seed':2,'control_arm':'K1-PT','command':['--arm','k1'],'recovery':{'source_plan':{'path':'source','sha256':'source-pin'},'checkpoint':{'path':'checkpoint','sha256':'checkpoint-pin'}}}
  self.c={'_pin':'binding','state_root':str(self.state),'training_plan':{'path':str(self.train/'plan.json'),'sha256':'plan-pin'},'canonical_plan_sha256':'canonical'}
  self.j={'role':'pt_s2','seed':2,'training':str(self.train),'new_adapter':str(self.train/'adapter'),'canonical_plan_sha256':'canonical','required_final_step':3116,'training_plan':self.c['training_plan'],'late_bound_hashes':self.H.LATE}
 def put(self,p,d):
  p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));return M.sha(p)
 def completed(self):
  end={'exit_code':0,'attempt':1,'scientific_acceptance':False,'started_utc':'2026-11-04T00:00:00Z','finished_utc':'2026-11-04T01:00:00Z'}
  for n in ['TRAIN_EXIT.json','attempts/1/EXIT.json']:self.put(self.train/n,end)
  claim={'run':self.p['run'],'chip':3};pin=self.put(self.train/'attempts/1/CLAIM.json',claim)
  self.put(self.train/'attempts/1/RELEASE.json',{'schema':'r3-resource-release-v1','run':self.p['run'],'chip':3,'container':'recovered-a1','container_id':'cid','claim_sha256':pin,'exit_code':0,'scientific_acceptance':False})
  self.put(self.train/'attempts/1/LAUNCH_RECEIPT.json',{'id':'cid','image':'image','plan_sha256':'canonical'})
  for n in ['attempts/1/SUPERVISOR_DONE.json','SUPERVISOR_RECEIPT.json','attempts/1/LAUNCH_SPEC.json']:self.put(self.train/n,{'exit_code':0,'scientific_acceptance':False})
  self.put(self.train/'manifest.json',{'summary':{'final_step':3116},'arm':'k1','model_path':M.MODEL,'args':{'arm':'k1','seed':2,'model_path':M.MODEL,'drop_state':False}})
  self.put(self.train/'adapter/adapter_config.json',{});self.put(self.train/'adapter/adapter_model.safetensors',{})
  pin=self.put(self.train/'plan.json',self.p);self.c['training_plan']['sha256']=pin
 def capture(self):return M.capture(self.c,self.p,self.j,self.H,self.B)
 def test_wait_before_terminal(self):self.assertEqual(self.capture(),{'status':'waiting_training'})
 def test_failure_not_completion(self):
  self.put(self.train/'TRAIN_EXIT.json',{'exit_code':1,'attempt':1});self.assertEqual(self.capture()['status'],'training_failed')
 def test_partial_completion_waits(self):
  self.put(self.train/'TRAIN_EXIT.json',{'exit_code':0,'attempt':1});self.assertEqual(self.capture()['status'],'waiting_completion_evidence')
 def test_complete_capture_requires_review_not_old_queue(self):
  self.completed();d=self.capture();self.assertEqual(d['status'],'REVIEW_REQUIRED');self.assertNotIn('queue_sha256',d);self.assertFalse(d['retained_container_verified']);self.assertEqual(d['source_checkpoint'],self.p['recovery']['checkpoint'])
 def test_foreign_release_rejected(self):
  self.completed();p=self.train/'attempts/1/RELEASE.json';d=M.read(p);d['container_id']='foreign';self.put(p,d)
  with self.assertRaisesRegex(ValueError,'release/launch/claim'):self.capture()
 def test_reconstructed_terminal_rejected(self):
  self.completed()
  for n in ['TRAIN_EXIT.json','attempts/1/EXIT.json']:
   p=self.train/n;d=M.read(p);d['source']='retained-container-exit';self.put(p,d)
  with self.assertRaisesRegex(ValueError,'genuine'):self.capture()
 def test_wrong_control_manifest_rejected(self):
  self.completed();p=self.train/'manifest.json';d=M.read(p);d['args']['drop_state']=True;self.put(p,d)
  with self.assertRaises(RuntimeError):self.capture()
 def test_symlink_artifact_rejected(self):
  self.completed();p=self.train/'adapter/adapter_model.safetensors';p.unlink();p.symlink_to(self.train/'manifest.json')
  with self.assertRaises(ValueError):self.capture()
 def test_source_pin_mismatch_rejected(self):
  p=self.r/'source';p.write_text('x')
  with self.assertRaisesRegex(ValueError,'reference changed'):M.ref({'path':str(p),'sha256':'wrong'})
 def test_outputs_overlap_rejected(self):
  with self.assertRaisesRegex(ValueError,'overlap'):M.disjoint(self.train,self.train/'child')
 def test_test_path_rejected(self):
  with self.assertRaisesRegex(ValueError,'TEST'):M.safe(str(self.r/'test.jsonl'))
 def test_review_missing_recovery_check_rejected(self):
  self.completed();cap=self.capture();self.put(self.state/'CAPTURE.json',cap);ep=self.r/'evidence';ep.write_text('actual');rp=self.r/'review.json'
  checks={k:True for k in ['genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116','recovery_checkpoint_and_step_identity','observation_origin_authenticated']}
  r={'schema':'r3-recovery-independent-postrun-v1','verdict':'PASS','independent':True,'binding_sha256':'binding','capture_sha256':M.sha(self.state/'CAPTURE.json'),'training_plan_sha256':self.c['training_plan']['sha256'],'files':cap['files'],'scientific_acceptance':False,'test_read':False,'checks':checks,'evidence_files':{str(ep):M.sha(ep)}}
  pin=self.put(rp,r)
  with self.assertRaisesRegex(ValueError,'verification incomplete'):M.review_check(self.c,self.p,self.j,self.H,self.B,{'path':str(rp),'sha256':pin})
  r['checks']['recovery_predecessor_identity_and_release']=True;pin=self.put(rp,r);M.review_check(self.c,self.p,self.j,self.H,self.B,{'path':str(rp),'sha256':pin})
  ep.write_text('changed')
  with self.assertRaisesRegex(ValueError,'external evidence changed'):M.review_check(self.c,self.p,self.j,self.H,self.B,{'path':str(rp),'sha256':pin})
if __name__=='__main__':unittest.main()
