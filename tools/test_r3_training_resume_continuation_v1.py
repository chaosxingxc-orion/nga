import unittest,tempfile,json,types,subprocess,importlib.util,fcntl
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
def load(n):
 p=HERE/n;s=importlib.util.spec_from_file_location(p.stem,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
S=load('r3_training_resume_service_v1.py');C=load('r3_training_resume_collector_v1.py')
class Continuation(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name);self.root=self.r/'service';self.root.mkdir();self.c={'state_root':str(self.root),'poll_interval_seconds':600,'observation_root':str(self.r/'observations')};self.p={'out':str(self.r/'training'),'container':'target','image_sha256':'image'}
  self.config=self.r/'config.json';S.put(self.config,self.c);self.pin=S.sha(self.config);self.activation={'path':'external','sha256':'pin'}
  S.put(self.root/'START-INTENT.json',{'config_sha256':self.pin,'activation':self.activation})
 def test_observation_uses_fixed_readonly_commands(self):
  calls=[]
  def run(cmd,**kwargs):calls.append(cmd);return types.SimpleNamespace(returncode=0,stdout='{}')
  r=S.observe(self.c,self.p,'capture',run);d=S.read(r['path']);self.assertEqual(len(calls),3);self.assertTrue(all(x[0]=='ssh' and x[-2]=='npu' for x in calls));self.assertEqual(d['capture_sha256'],'capture');self.assertEqual(S.read(Path(r['path']).parent/'EXIT.json')['exit_code'],0)
 def test_observation_failure_retained_no_manifest(self):
  def run(*a,**k):return types.SimpleNamespace(returncode=1,stdout='')
  with self.assertRaises(OSError):S.observe(self.c,self.p,'capture',run)
  root=Path(self.c['observation_root'])/'attempt-1';self.assertEqual(S.read(root/'EXIT.json')['exit_code'],1);self.assertFalse((root/'OBSERVATIONS.json').exists())
 def test_observation_timeout_does_not_adopt_partial(self):
  def run(*a,**k):raise subprocess.TimeoutExpired('ssh',45)
  with self.assertRaises(subprocess.TimeoutExpired):S.observe(self.c,self.p,'capture',run)
  self.assertFalse((Path(self.c['observation_root'])/'attempt-1/OBSERVATIONS.json').exists())
 def test_service_error_writes_terminal(self):
  with patch.object(S,'identity',side_effect=ValueError('changed source')):
   with self.assertRaisesRegex(ValueError,'changed source'):S.watch(str(self.config),self.pin,self.activation)
  self.assertEqual(S.read(self.root/'EXIT.json')['exit_code'],1)
 def test_duplicate_watch_does_not_write_terminal(self):
  with (self.root/'watch.lock').open('a') as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaises(BlockingIOError):S.watch(str(self.config),self.pin,self.activation)
  self.assertFalse((self.root/'EXIT.json').exists())
 def test_completed_watch_not_overwritten(self):
  S.put(self.root/'EXIT.json',{'exit_code':0,'status':'prepared'});before=(self.root/'EXIT.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'already terminal'):S.watch(str(self.config),self.pin,self.activation)
  self.assertEqual(before,(self.root/'EXIT.json').read_bytes())
 def test_prepared_exit_honest(self):
  identity=(self.c,None,None,None,None,None,self.root)
  with patch.object(S,'identity',return_value=identity),patch.object(S,'authorize'),patch.object(S,'tick',return_value={'status':'prepared'}):S.watch(str(self.config),self.pin,self.activation)
  self.assertEqual(S.read(self.root/'EXIT.json')['status'],'prepared')
 def test_failed_training_not_success(self):
  with patch.object(S,'identity',return_value=(self.c,None,None,None,None,None,self.root)),patch.object(S,'authorize'),patch.object(S,'tick',return_value={'status':'training_failed'}):S.watch(str(self.config),self.pin,self.activation)
  self.assertEqual(S.read(self.root/'EXIT.json')['exit_code'],1)
 def predecessor(self):
  q=self.r/'qo';t=self.r/'pt';q.mkdir();t.mkdir();p={'out':str(t),'chip':3,'recovery':{'checkpoint':{'sha256':'ckpt'},'resource_predecessor':{'out':str(q),'container_id':'cid'}}}
  refs={q/'attempts/1/LAUNCH_RECEIPT.json':{'id':'cid'},q/'attempts/1/CLAIM.json':{'chip':3,'run':'qo'}}
  for path,d in refs.items():S.put(path,d)
  r=p['recovery']['resource_predecessor'];r.update(receipt_sha256=S.sha(q/'attempts/1/LAUNCH_RECEIPT.json'),claim_sha256=S.sha(q/'attempts/1/CLAIM.json'))
  rp=q/'attempts/1/RELEASE.json';free={'chip':3,'previous_run':'qo','release_evidence':str(rp)};S.put(rp,{'container_id':'cid','chip':3,'run':'qo','claim_sha256':r['claim_sha256'],'allocation_after':{'free':[free]}})
  S.put(t/'SUCCESSOR_PRECONDITION.json',{'release_sha256':S.sha(rp),'plan_sha256':C._H.canonical(p),'checkpoint_sha256':'ckpt'})
  claim={'allocation_before':{'free':[free]},'successor_precondition':{'schema':'pt2-recovery-claim-v2','release_sha256':S.sha(rp),'container_id':'cid','checkpoint_sha256':'ckpt','precondition_sha256':S.sha(t/'SUCCESSOR_PRECONDITION.json')}}
  return p,claim
 def test_exact_recovery_predecessor(self):
  p,c=self.predecessor();self.assertEqual(len(C.predecessor(p,c,S.read,S.sha)),4)
 def test_foreign_free_lineage_rejected(self):
  p,c=self.predecessor();c['allocation_before']['free']=[{'chip':3,'previous_run':'foreign'}]
  with self.assertRaisesRegex(ValueError,'lineage'):C.predecessor(p,c,S.read,S.sha)
 def test_missing_locked_proof_rejected(self):
  p,c=self.predecessor();c.pop('successor_precondition')
  with self.assertRaisesRegex(ValueError,'recovery proof'):C.predecessor(p,c,S.read,S.sha)
 def test_altered_checkpoint_proof_rejected(self):
  p,c=self.predecessor();c['successor_precondition']['checkpoint_sha256']='foreign'
  with self.assertRaisesRegex(ValueError,'recovery proof'):C.predecessor(p,c,S.read,S.sha)
 def test_real_dev_builder_preserves_protocol(self):
  H=C._H;B=load('r3_posttrain_eval_plan.py');training=self.r/'training';training.mkdir();out=self.r/'evaluation';state=self.r/'handoff';state.mkdir();closure=self.r/'closure';closure.mkdir()
  p={'out':str(training),'model':H.MODEL,'image_sha256':'image','control_arm':'K1-PT','seed':2,'arm':'k1','command':['--arm','k1'],'files':{}}
  S.put(training/'plan.json',p);S.put(training/'TRAIN_EXIT.json',{'exit_code':0});S.put(training/'manifest.json',{'summary':{'final_step':3116},'arm':'k1','model_path':H.MODEL,'args':{'seed':2,'arm':'k1','model_path':H.MODEL,'drop_state':False}})
  S.put(training/'adapter/adapter_config.json',{});S.put(training/'adapter/adapter_model.safetensors',{})
  cmd=['python3','--model-path',H.MODEL,'--adapter','<COMPLETED_ADAPTER>','--arm','K1-PT','--out','<FRESH_EVAL_OUTPUT>','--round-dir','<FRESH_IDENTITY_CACHE>','--partitions','dev,calibration']
  S.put(closure/'manifest.json',{'evaluation_profile':'track_kt','data':{},'code':{},'mounts':[],'command_template':cmd})
  template=self.r/'template.json';S.put(template,{'command':cmd})
  c={'state_root':str(state),'evaluation_out':str(out),'closure':{'path':str(closure/'manifest.json')},'protocol_template':{'path':str(template)},'relocated_command_flags':['--adapter','--out','--round-dir'],'training_plan':{'sha256':S.sha(training/'plan.json')}}
  j={'new_adapter':str(training/'adapter')};base=load('r3_formal_wave_handoff.py')
  with patch.object(H,'identity',return_value=(c,p,j,base,B)),patch.object(H,'review_check',return_value=({},{})):
   result=H.prepare('config','pin',{'path':'review','sha256':'pin'})
  spec=S.read(out/'plan.json');self.assertEqual(result['status'],'prepared');self.assertEqual(spec['training_variant']['arm'],'k1-pt');self.assertEqual(spec['training_variant']['seed'],2);self.assertFalse(spec['test_read']);self.assertEqual(spec['command'][-1],'dev,calibration')
 def test_exclusive_intent(self):
  p=self.r/'intent.json';S.put(p,{'v':1},True)
  with self.assertRaises(FileExistsError):S.put(p,{'v':2},True)
  self.assertEqual(S.read(p),{'v':1})
if __name__=='__main__':unittest.main()
