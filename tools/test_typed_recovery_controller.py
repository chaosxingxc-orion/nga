import copy,hashlib,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SPEC=importlib.util.spec_from_file_location('controller',Path(__file__).with_name('typed_recovery_controller.py'));m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
class Fixture:
 def __init__(self,root):
  self.root=Path(root);self.run=self.root/'run';self.run.mkdir();self.out=self.root/'controller';self.out.mkdir();self.verifier=self.root/'verify.py';self.verifier.write_text('fixture')
  (self.run/'run.sh').write_text('fixture');(self.run/'records').mkdir();(self.run/'records/000000.json').write_text('preserved bytes')
  self.c={'out':str(self.run),'container':'test-inference','image':'sha256:image','mode':'inference','expected_count':3,'physical_chip':0,'files':{str(self.run/'run.sh'):m.sha(self.run/'run.sh')}};self.cp=self.run/'config.json';self.write(self.cp,self.c)
  self.plan={'schema':1,'out':str(self.out),'config':str(self.cp),'kind':'cpu_fixture','max_retries':2,'retry_exit_codes':[137,143],'verifier':str(self.verifier),'audit_binds':[str(self.root)+':'+str(self.root)],'inference':{'Image':'sha256:image','Cmd':['bash',str(self.run/'run.sh')],'Entrypoint':[],'WorkingDir':'/tmp','HostConfig':{'Devices':[],'Binds':[str(self.root)+':'+str(self.root)]}},'files':{str(p):m.sha(p) for p in [Path(m.__file__),self.cp,self.run/'run.sh',self.verifier]}}
  self.plan['preparation_files']={}
  for name in ['controller_wrapper','launch','resume','preregistration']:
   path=self.root/name;path.write_text('frozen '+name);self.plan['preparation_files'][name]=str(path);self.plan['files'][str(path)]=m.sha(path)
  self.pp=self.out/'plan.json';self.write(self.pp,self.plan);self.write(self.out/'PARENT_REVIEW.json',{'approved_plan_sha256':m.sha(self.pp)});self.containers={};self.calls=[];self.fail=None
 def write(self,p,x):p.write_text(json.dumps(x))
 def docker(self,method,path,body=None):
  self.calls.append((method,path))
  if method=='GET':
   if path=='/containers/json':return [{'Id':v['Id']} for v in self.containers.values() if v['State']['Status']=='running']
   name=path.split('/')[2];return self.containers.get(name) or next((v for v in self.containers.values() if v['Id']==name),None)
  if '/create?' in path:
   name=path.split('name=')[1];info={'Id':'id-'+name,'Image':body['Image'],'Config':{k:copy.deepcopy(body.get(k)) for k in ['Cmd','Entrypoint','WorkingDir','Labels','Env']},'HostConfig':copy.deepcopy(body['HostConfig']),'State':{'Status':'created','ExitCode':0,'StartedAt':'never'}};self.containers[name]=info
   if self.fail=='after_create':self.fail=None;raise ConnectionError('after create')
   return {'Id':info['Id']}
  if path.endswith('/start'):
   i=next(v for v in self.containers.values() if v['Id']==path.split('/')[2]);i['State'].update(Status='running',StartedAt='start-'+str(len(self.calls)))
   if self.fail=='after_start':self.fail=None;raise ConnectionError('after start')
   return
  raise AssertionError(path)
 def controller(self):return m.Controller(self.pp)
 def completed(self,c):
  for name in ['report.json','PREFLIGHT.json','PROBE.json']:self.write(self.run/name,{'valid':True})
  self.write(self.run/'inference-COMPLETE.json',{'rc':0,'config_sha256':c.ch,'stage':'completed','progress':3,'total':3,'outputs':{n:m.sha(self.run/n) for n in ['report.json','PREFLIGHT.json','PROBE.json']}});(self.run/'EXIT').write_text('rc=0 utc=2026-10-30T18:00:00Z\n');self.containers['test-inference']['State'].update(Status='exited',ExitCode=0)
class ControllerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.f=Fixture(self.tmp.name);self.patch=patch.object(m,'docker',side_effect=self.f.docker);self.patch.start();self.addCleanup(self.patch.stop)
 def test_create_interruption_reconciles_without_duplicate(self):
  c=self.f.controller();self.f.fail='after_create'
  with self.assertRaises(ConnectionError):c.step()
  self.assertEqual(self.f.controller().step(),'started');self.assertEqual(sum('/create?' in p for _,p in self.f.calls),1)
 def test_start_interruption_reconciles_live_without_restart(self):
  c=self.f.controller();self.f.fail='after_start'
  with self.assertRaises(ConnectionError):c.step()
  self.assertEqual(self.f.controller().step(),'running');self.assertEqual(sum(p.endswith('/start') for _,p in self.f.calls),1)
 def test_created_receipt_gap_recovers_native_receipt(self):
  c=self.f.controller();self.assertEqual(c.step(),'started');self.f.containers['test-inference']['State']['Status']='created';c.state['phase']='starting';c.save();(self.f.run/'LAUNCH_RECEIPT.json').unlink();self.assertEqual(self.f.controller().step(),'started');self.assertTrue((self.f.run/'LAUNCH_RECEIPT.json').exists())
 def test_missing_native_receipt_after_live_is_not_rebuilt(self):
  c=self.f.controller();c.step();c.step();(self.f.run/'LAUNCH_RECEIPT.json').unlink()
  with self.assertRaisesRegex(ValueError,'Missing native'):c.step()
 def test_retry_limit_is_bounded(self):
  c=self.f.controller();c.step()
  for i in range(2):
   self.f.containers['test-inference']['State'].update(Status='exited',ExitCode=137,StartedAt='attempt-'+str(i));self.assertEqual(c.step(),'started')
  self.f.containers['test-inference']['State'].update(Status='exited',ExitCode=137,StartedAt='third')
  with self.assertRaisesRegex(ValueError,'Retry limit'):c.step()
 def test_foreign_identity_rejected(self):
  c=self.f.controller();c.step();self.f.containers['test-inference']['Id']='foreign'
  with self.assertRaisesRegex(ValueError,'Foreign'):c.step()
 def test_wrong_device_rejected(self):
  c=self.f.controller();c.step();self.f.containers['test-inference']['HostConfig']['Devices']=[{'PathOnHost':'/dev/davinci0'}]
  with self.assertRaisesRegex(ValueError,'Devices'):c.step()
 def test_unlabelled_container_rejected(self):
  c=self.f.controller();self.f.fail='after_create'
  with self.assertRaises(ConnectionError):c.step()
  self.f.containers['test-inference']['Config']['Labels']={}
  with self.assertRaisesRegex(ValueError,'label'):self.f.controller().step()
 def test_sigkill_preserves_receipts_and_archives(self):
  c=self.f.controller();c.step();info=self.f.containers['test-inference'];info['State'].update(Status='exited',ExitCode=137);(self.f.run/'EXIT').write_text('rc=137 old');self.assertEqual(c.step(),'started');self.assertEqual((self.f.run/'records/000000.json').read_text(),'preserved bytes');self.assertEqual((self.f.out/'retry-1/EXIT').read_text(),'rc=137 old')
 def test_nonretryable_semantic_failure(self):
  c=self.f.controller();c.step();self.f.containers['test-inference']['State'].update(Status='exited',ExitCode=1)
  with self.assertRaisesRegex(ValueError,'Non-retryable'):c.step()
 def test_success_marker_never_retried(self):
  c=self.f.controller();c.step();self.f.completed(c);self.f.containers['test-inference']['State']['ExitCode']=137
  with self.assertRaisesRegex(ValueError,'Successful terminal'):c.step()
 def test_success_starts_only_audit(self):
  c=self.f.controller();c.step();self.f.completed(c);self.assertEqual(c.step(),'audit_started');self.assertEqual(sum(p.endswith('/start') and 'test-inference/' in p for _,p in self.f.calls),1)
 def test_failed_audit_not_success(self):
  c=self.f.controller();c.step();self.f.completed(c);c.step();a=self.f.containers['test-inference-recovery-audit-0'];a['State'].update(Status='exited',ExitCode=1)
  with self.assertRaisesRegex(ValueError,'Non-retryable audit'):c.step()
  self.assertFalse((self.f.out/'COMPLETE.json').exists())
 def test_killed_audit_gets_separate_generation(self):
  c=self.f.controller();c.step();self.f.completed(c);c.step();self.f.containers['test-inference-recovery-audit-0']['State'].update(Status='exited',ExitCode=137);self.assertEqual(c.step(),'audit_retry_registered');self.assertEqual(c.step(),'audit_started');self.assertTrue((self.f.out/'audit-0/LAUNCH_RECEIPT.json').exists());self.assertTrue((self.f.out/'audit-1/LAUNCH_RECEIPT.json').exists())
 def test_full_success_is_idempotent_and_preserves_review_flags(self):
  c=self.f.controller();c.step();self.f.completed(c);c.step();audit=self.f.out/'audit-0';self.f.write(audit/'INDEPENDENT_AUDIT.json',{'config_sha256':c.ch,'review_flags':[{'reason':'fixture_flag'}]});self.f.write(audit/'AUDIT_COMPLETE.json',{'rc':0,'config_sha256':c.ch,'audit_sha256':m.sha(audit/'INDEPENDENT_AUDIT.json'),'audit_plan_sha256':m.sha(audit/'audit-plan.json'),'inference_terminal_sha256':m.sha(self.f.run/'inference-COMPLETE.json')});self.f.containers['test-inference-recovery-audit-0']['State'].update(Status='exited',ExitCode=0)
  self.assertEqual(c.step(),'complete');calls=len(self.f.calls);before=(self.f.out/'COMPLETE.json').read_bytes();self.assertEqual(self.f.controller().step(),'complete');self.assertTrue(all(method=='GET' for method,_ in self.f.calls[calls:]));self.assertEqual(before,(self.f.out/'COMPLETE.json').read_bytes());self.assertEqual(m.load(self.f.out/'COMPLETE.json')['status'],'COMPLETED_SCOPED_REVIEW_REQUIRED')
 def finish(self):
  c=self.f.controller();c.step();self.f.completed(c);c.step();audit=self.f.out/'audit-0'
  self.f.write(audit/'INDEPENDENT_AUDIT.json',{'config_sha256':c.ch,'review_flags':[]})
  self.f.write(audit/'AUDIT_COMPLETE.json',{'rc':0,'config_sha256':c.ch,'audit_sha256':m.sha(audit/'INDEPENDENT_AUDIT.json'),'audit_plan_sha256':m.sha(audit/'audit-plan.json'),'inference_terminal_sha256':m.sha(self.f.run/'inference-COMPLETE.json')})
  self.f.containers['test-inference-recovery-audit-0']['State'].update(Status='exited',ExitCode=0)
  return c
 def test_wrong_expected_count_rejected(self):
  c=self.f.controller();c.step();self.f.completed(c);p=self.f.run/'inference-COMPLETE.json';t=m.load(p);t.update(progress=2,total=2);self.f.write(p,t)
  with self.assertRaisesRegex(ValueError,'Success count'):c.step()
 def test_missing_preparation_dependency_rejected(self):
  self.f.plan['files'].pop(self.f.plan['preparation_files']['launch']);self.f.write(self.f.pp,self.f.plan);self.f.write(self.f.out/'PARENT_REVIEW.json',{'approved_plan_sha256':m.sha(self.f.pp)})
  with self.assertRaisesRegex(ValueError,'Preparation dependency'):self.f.controller()
 def test_audit_acceptance_rechecks_live_inference(self):
  c=self.finish();self.f.containers['test-inference']['State']['Status']='running'
  with self.assertRaisesRegex(ValueError,'container state'):c.audit()
 def test_audit_acceptance_rechecks_replaced_inference(self):
  c=self.finish();self.f.containers['test-inference']['Id']='foreign'
  with self.assertRaisesRegex(ValueError,'Foreign'):c.audit()
 def test_stale_audit_terminal_rejected(self):
  c=self.finish();p=self.f.out/'audit-0/AUDIT_COMPLETE.json';os.utime(p,ns=(1,1))
  with self.assertRaisesRegex(ValueError,'Stale audit'):c.step()
 def test_wrong_audit_terminal_plan_rejected(self):
  c=self.finish();p=self.f.out/'audit-0/AUDIT_COMPLETE.json';t=m.load(p);t['audit_plan_sha256']='wrong';self.f.write(p,t)
  with self.assertRaisesRegex(ValueError,'Audit terminal binding'):c.step()
 def test_completed_fast_path_rechecks_config(self):
  c=self.finish();c.step();self.f.cp.write_text('{}')
  with self.assertRaisesRegex(ValueError,'Frozen file'):c.step()
 def test_completed_fast_path_rechecks_wrapper(self):
  c=self.finish();c.step();Path(self.f.plan['preparation_files']['controller_wrapper']).write_text('changed')
  with self.assertRaisesRegex(ValueError,'Frozen file'):c.step()
 def test_completed_fast_path_rechecks_audit_identity(self):
  c=self.finish();c.step();self.f.containers['test-inference-recovery-audit-0']['Id']='foreign'
  with self.assertRaisesRegex(ValueError,'Foreign'):c.step()
 def test_completed_fast_path_rechecks_inference_identity(self):
  c=self.finish();c.step();self.f.containers['test-inference']['Id']='foreign'
  with self.assertRaisesRegex(ValueError,'Foreign'):c.step()
 def test_completed_fast_path_rechecks_inference_live(self):
  c=self.finish();c.step();self.f.containers['test-inference']['State']['Status']='running'
  with self.assertRaisesRegex(ValueError,'container state'):c.step()
 def test_corrupt_audit_plan_rejected(self):
  c=self.f.controller();c.step();self.f.completed(c);c.step();p=self.f.out/'audit-0/audit-plan.json';x=m.load(p);x['verifier']='foreign';self.f.write(p,x)
  with self.assertRaisesRegex(ValueError,'Audit plan changed'):c.step()
 def test_false_exit_zero_rejected(self):
  c=self.f.controller();c.step();self.f.containers['test-inference']['State'].update(Status='exited',ExitCode=0)
  with self.assertRaisesRegex(ValueError,'Exited0'):c.step()
if __name__=='__main__':unittest.main()
