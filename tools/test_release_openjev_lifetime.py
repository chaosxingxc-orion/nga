"""E40 release: real files/transaction; synthetic Docker and scientific modules."""
import base64
import copy
import importlib.util
import json
import shutil
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
def module(n):
 s=importlib.util.spec_from_file_location(n,HERE/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
r=module('release_openjev_lifetime');qmod=module('jeval_reference_queue')

class Fixture(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.out=self.root/'run';self.out.mkdir();self.cpuout=self.root/'verify';self.cpuout.mkdir()
  self.planpath=self.out/'plan.json';self.request=self.cpuout/'request.json';self.ap=self.root/'ALLOCATION.json'
  self.review=self.root/'RELEASE_REVIEW.json';self.anchor=self.root/'ANCHOR.json';self.journal=self.root/'e40_release_test'
  self.p=dict(out=str(self.out),physical_chip=1,candidate_batch_admission=False,container='npu',files={},
   container_spec=str(self.out/'NPU_SPEC.json'),wrapper=str(self.out/'run.sh'))
  self.save(self.planpath,self.p);self.ph=qmod.sha(self.planpath)
  self.save(self.out/'NPU_SPEC.json',{'fake':'spec','HostConfig':{}});(self.out/'run.sh').write_text('wrapper')
  self.save(self.out/'PARENT_REVIEW.json',dict(approved=True,approved_plan_sha256=self.ph))
  (self.out/'astra.md').write_text('scoped PASS fixture')
  self.save(self.out/'INDEPENDENT_REVIEW.json',dict(approved=True,approved_plan_sha256=self.ph,
   review_path=str(self.out/'astra.md'),review_sha256=qmod.sha(self.out/'astra.md')))
  self.save(self.out/'LAUNCH_RECEIPT.json',dict(container_id='npu-id',plan_sha256=self.ph,
   wrapper_sha256=qmod.sha(self.out/'run.sh'),parent_review_sha256=qmod.sha(self.out/'PARENT_REVIEW.json')))
  self.gen=dict(container_id='npu-id',started_at='npu-start',launch_receipt_sha256=qmod.sha(self.out/'LAUNCH_RECEIPT.json'))
  self.save(self.out/'GENERATION.json',self.gen)
  self.science=dict(exact_outputs=False,review_flags=['narrow diagnostic','L1 mismatch'],candidate_batch_admission=False)
  self.nr=dict(generation=self.gen,**self.science)
  for folder,key in [('items','receipt_manifest'),('attempts','attempt_manifest')]:
   (self.out/folder).mkdir();manifest={}
   for i in range(8):
    f=self.out/folder/(str(i)+'.json');self.save(f,{'item':i});manifest[f.name]=qmod.sha(f)
   self.nr[key]=manifest
  self.save(self.out/'report.json',self.nr)
  self.nt=dict(rc=0,stage='completed',progress=8,total=8,plan_sha256=self.ph,
   output_sha256=qmod.sha(self.out/'report.json'),candidate_batch_admission=False,rejected_manifest={})
  self.save(self.out/'COMPLETE.json',self.nt);(self.out/'EXIT').write_text('rc=0 utc=now\n')
  self.npu=dict(Id='npu-id',State=dict(Status='exited',ExitCode=0,StartedAt='npu-start',FinishedAt='npu-end'))
  self.cpu=dict(Id='cpu-id',State=dict(Status='exited',ExitCode=0,StartedAt='cpu-start',FinishedAt='cpu-end'))
  self.containers={'npu':self.npu,'npu-id':self.npu,'cpu':self.cpu,'cpu-id':self.cpu};self.active=[]
  self.req=dict(schema='e40-detached-cpu-verify-v1',out=str(self.cpuout),container='cpu',plan=str(self.planpath),
   plan_sha256=self.ph,npu_id='npu-id',npu_started_at='npu-start',npu_finished_at='npu-end',files={})
  self.save(self.request,self.req);self.rh=qmod.sha(self.request)
  self.save(self.cpuout/'PARENT_REVIEW.json',dict(approved=True,approved_request_sha256=self.rh))
  (self.cpuout/'run.sh').write_text('cpu wrapper');(self.cpuout/'openjev_lifetime_verify_launch.py').write_text('fixture source')
  self.save(self.cpuout/'CPU_SPEC.json',dict(HostConfig=dict(Devices=[])))
  self.save(self.cpuout/'LAUNCH_RECEIPT.json',dict(container_id='cpu-id',request_sha256=self.rh,
   wrapper_sha256=qmod.sha(self.cpuout/'run.sh'),parent_review_sha256=qmod.sha(self.cpuout/'PARENT_REVIEW.json')))
  self.cr=dict(plan_sha256=self.ph,actual_exit=0,finished_at='npu-end',generation=self.gen,
   report_sha256=qmod.sha(self.out/'report.json'),terminal_sha256=qmod.sha(self.out/'COMPLETE.json'),**self.science)
  self.save(self.cpuout/'report.json',self.cr)
  self.ct=dict(rc=0,request_sha256=self.rh,cpu_id='cpu-id',cpu_started_at='cpu-start',
   outputs={'report.json':qmod.sha(self.cpuout/'report.json')})
  self.save(self.cpuout/'COMPLETE.json',self.ct);(self.cpuout/'EXIT').write_text('rc=0 utc=now\n')
  att=dict(request_sha256=self.rh,report_sha256=qmod.sha(self.cpuout/'report.json'),terminal_sha256=qmod.sha(self.cpuout/'COMPLETE.json'),
   receipt_sha256=qmod.sha(self.cpuout/'LAUNCH_RECEIPT.json'),exit_sha256=qmod.sha(self.cpuout/'EXIT'),container_id='cpu-id',
   started_at='cpu-start',finished_at='cpu-end',actual_exit=0,devices=[])
  self.save(self.cpuout/'CPU_EXIT_BINDING.json',att)
  self.before=dict(allocation=[dict(chip=1,run='reference_inference/run'),dict(chip=4,run='other')],free=[])
  self.save(self.ap,self.before)
  self.approval=dict(schema='e40-resource-release-review-v1',approved=True,approved_plan_sha256=self.ph,
   verification_request_sha256=self.rh,verification_report_sha256=qmod.sha(self.cpuout/'report.json'),
   verification_terminal_sha256=qmod.sha(self.cpuout/'COMPLETE.json'),accepted_exact_outputs=False,
   accepted_review_flags=self.science['review_flags'],candidate_batch_admission=False,
   release_tool_sha256=qmod.sha(Path(r.__file__)),evidence_helper_sha256=r.EVIDENCE_HELPER_SHA256,
   cpu_verifier_tool_sha256=qmod.sha(self.cpuout/'openjev_lifetime_verify_launch.py'),
   cpu_exit_binding_sha256=qmod.sha(self.cpuout/'CPU_EXIT_BINDING.json'),allocation_before_sha256=qmod.sha(self.ap))
  self.save(self.review,self.approval)
  self.save(self.anchor,dict(schema='e40-resource-release-anchor-v1',release_review_sha256=qmod.sha(self.review),
   cpu_exit_binding_sha256=qmod.sha(self.cpuout/'CPU_EXIT_BINDING.json'),allocation_before_sha256=qmod.sha(self.ap),
   allocation_before_bytes_b64=base64.b64encode(self.ap.read_bytes()).decode()))
  self.pin=qmod.sha(self.anchor)
  self.delegate=types.SimpleNamespace(inspect=lambda n:self.containers.get(n),binding=self.binding,
   devices=lambda d:d.get('devices',[]),docker=lambda *a:self.active,chip_access=lambda d,c:d.get('chip')==c,utc=lambda:'now')
  self.proto=types.SimpleNamespace(check_receipts=lambda *a,**kw: {'fixture':True})
  self.verifier=types.SimpleNamespace(reconstruct=lambda items:copy.deepcopy(self.science))
  self.prep=types.SimpleNamespace(frozen_module=self.frozen,free_now=lambda *a:None)
  for k,v in [('ROOT',self.root),('ALLOCATION',self.ap),('PLAN_HASHES',{'run':self.ph})]:
   p=patch.object(r,k,v);p.start();self.addCleanup(p.stop)
 def frozen(self,path,name):
  if path.name=='openjev_lifetime_protocol.py':return self.proto
  if path.name=='openjev_lifetime_verify.py':return self.verifier
  return types.SimpleNamespace(check_prediction=lambda *a:None)
 def save(self,path,value):qmod.atomic(path,value)
 def binding(self,actual,spec,receipt):
  if actual is None or actual['Id']!=receipt['container_id']:raise ValueError('Docker binding differs')
 def bound(self):
  q=r.evidence.Evidence(self.delegate)
  p,b=r.bind(self.planpath,self.request,self.review,q,self.prep,self.anchor,self.pin)
  return q,p,b
 def release(self):
  q,p,b=self.bound();return r.transaction(q,self.prep,p,b,self.journal)
 def test_real_release_entry_calls_bind_and_transaction(self):
  q=r.evidence.Evidence(self.delegate)
  with patch.object(r,'frozen_context',return_value=(q,self.prep)) as context, patch.object(r,'bind',wraps=r.bind) as binding:
   result=r.release(self.planpath,self.request,self.review,self.journal,self.anchor,self.pin)
  self.assertEqual(result['status'],'RELEASED');context.assert_called_once_with(self.planpath)
  binding.assert_called_once();self.assertEqual(qmod.load(self.ap)['allocation'],self.before['allocation'][1:])
 def test_frozen_context_authenticates_before_executing_closure(self):
  marker=self.root/'executed'
  queue=self.out/'jeval_reference_queue.py';prep=self.out/'prepare_openjev_path_trace.py'
  queue.write_text('value=23\n')
  prep.write_text('def host(q): pass\n')
  plan=dict(self.p,files={str(queue):qmod.sha(queue),str(prep):qmod.sha(prep)})
  self.save(self.planpath,plan);pin=qmod.sha(self.planpath)
  with patch.object(r,'PLAN_HASHES',{'run':pin}):
   q,p=r.frozen_context(self.planpath)
   self.assertEqual(p.frozen_module(queue,'verified_queue').value,23)
   queue.write_text('open('+repr(str(marker))+',"w").write("bad")\n')
   with self.assertRaisesRegex(ValueError,'dependency changed'):r.frozen_context(self.planpath)
  self.assertFalse(marker.exists())
 def test_negative_result_releases_only_chip1(self):
  self.assertEqual(self.release()['status'],'RELEASED')
  after=qmod.load(self.ap);self.assertEqual(after['allocation'],self.before['allocation'][1:])
  b=qmod.load(self.journal/'RELEASE_INTENT.json')['bindings']
  self.assertFalse(b['accepted_exact_outputs']);self.assertEqual(b['accepted_review_flags'],self.science['review_flags'])
 def test_replay_preserves_new_owner(self):
  self.release();after={'allocation':[{'chip':1,'run':'next'}],'free':[]};self.save(self.ap,after)
  self.assertEqual(self.release()['status'],'ALREADY_RELEASED');self.assertEqual(qmod.load(self.ap),after)
 def test_restart_generation_rejected(self):
  for obj,key in [(self.npu,'StartedAt'),(self.cpu,'FinishedAt')]:
   old=obj['State'][key];obj['State'][key]='changed'
   with self.assertRaises(ValueError):self.bound()
   obj['State'][key]=old
 def test_real_exit_failure(self):
  self.cpu['State']['ExitCode']=1
  with self.assertRaises(ValueError):self.bound()
 def test_cpu_device_exposure_rejected(self):
  self.cpu['devices']=['/dev/davinci1']
  with self.assertRaises(ValueError):self.bound()
 def test_anchor_rewrite_not_authorized(self):
  x=qmod.load(self.anchor);x['allocation_before_sha256']='0'*64;self.save(self.anchor,x)
  with self.assertRaisesRegex(ValueError,'anchor'):self.bound()
 def test_changed_science_or_receipt_rejected(self):
  self.verifier.reconstruct=lambda i:dict(self.science,exact_outputs=True)
  with self.assertRaisesRegex(ValueError,'Scientific'):self.bound()
  self.verifier.reconstruct=lambda i:copy.deepcopy(self.science)
  self.save(self.out/'items/0.json',{'changed':True})
  with self.assertRaisesRegex(ValueError,'Receipt'):self.bound()
 def test_flags_cannot_be_dropped_even_with_new_anchor(self):
  self.approval['accepted_review_flags']=[];self.save(self.review,self.approval)
  x=qmod.load(self.anchor);x['release_review_sha256']=qmod.sha(self.review);self.save(self.anchor,x);self.pin=qmod.sha(self.anchor)
  with self.assertRaisesRegex(ValueError,'approval'):self.bound()
 def test_active_or_created_blocks(self):
  for status in ['created','running','paused','restarting']:
   self.containers['other']=dict(Id='other',State=dict(Status=status),chip=1);self.active=[{'Id':'other'}]
   with self.assertRaises(ValueError):self.release()
  self.assertEqual(qmod.load(self.ap),self.before)
 def test_changed_exit_after_bind_blocks(self):
  q,p,b=self.bound();self.npu['State']['Status']='running'
  with self.assertRaises(ValueError):r.transaction(q,self.prep,p,b,self.journal)
 def test_crash_after_allocation_recovers_without_second_write(self):
  publish=r.evidence.publish_new
  def fail(path,value):
   if path.name=='RELEASED.json':raise KeyboardInterrupt()
   publish(path,value)
  with patch.object(r.evidence,'publish_new',side_effect=fail),self.assertRaises(KeyboardInterrupt):self.release()
  after=qmod.sha(self.ap)
  with patch.object(r,'replace_allocation',side_effect=AssertionError('second write')):self.release()
  self.assertEqual(qmod.sha(self.ap),after)
 def test_crash_before_allocation_recovers(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt()),self.assertRaises(KeyboardInterrupt):self.release()
  self.assertEqual(qmod.load(self.ap),self.before);self.release()
 def test_unrelated_allocation_change_blocks(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt()),self.assertRaises(KeyboardInterrupt):self.release()
  changed=dict(self.before,other='changed');self.save(self.ap,changed)
  with self.assertRaises(ValueError):self.release()
  self.assertEqual(qmod.load(self.ap),changed)
 def test_symlink_lock_rejected(self):
  target=self.root/'target';target.write_text('keep');Path(str(self.ap)+'.lock').symlink_to(target)
  with self.assertRaises(OSError):self.release()
  self.assertEqual(target.read_text(),'keep')

 def test_publication_internal_crashes_recover_without_second_allocation_mutation(self):
  original_link=r.evidence.os.link;original_unlink=r.evidence.os.unlink
  original_sync=r.evidence.sync_directory
  for filename in ['RELEASE_INTENT.json','INTENT_COMMITTED.json','RELEASED.json']:
   for stage in ['before_link','after_link','before_unlink_sync','after_unlink']:
    with self.subTest(filename=filename,stage=stage):
     if self.journal.exists():
      shutil.rmtree(self.journal)
     self.save(self.ap,self.before);injected=[]
     def link(source,target,*args,**kwargs):
      if Path(target).name==filename and not injected:
       injected.append(True)
       if stage=='before_link':raise KeyboardInterrupt(stage)
       result=original_link(source,target,*args,**kwargs)
       if stage=='after_link':raise KeyboardInterrupt(stage)
       return result
      return original_link(source,target,*args,**kwargs)
     def unlink(path,*args,**kwargs):
      result=original_unlink(path,*args,**kwargs)
      if Path(path).name==filename+'.pending' and stage=='after_unlink':
       injected.append(True);raise KeyboardInterrupt(stage)
      return result
     def sync(path):
      target=Path(path)/filename;pending=target.with_name(filename+'.pending')
      if stage=='before_unlink_sync' and target.exists() and pending.exists():
       raise KeyboardInterrupt(stage)
      return original_sync(path)
     with patch.object(r.evidence.os,'link',side_effect=link),patch.object(r.evidence.os,'unlink',side_effect=unlink),patch.object(r.evidence,'sync_directory',side_effect=sync):
      with self.assertRaises(KeyboardInterrupt):self.release()
     self.assertTrue(injected)
     after=qmod.load(self.ap)
     self.delegate.utc=lambda:'later-retry-time'
     if after!=self.before:
      with patch.object(r,'replace_allocation',side_effect=AssertionError('second mutation')):
       result=self.release()
     else:result=self.release()
     self.assertIn(result['status'],['RELEASED','ALREADY_RELEASED'])
     self.assertFalse(list(self.journal.glob('*.pending')))


if __name__=='__main__':unittest.main()
