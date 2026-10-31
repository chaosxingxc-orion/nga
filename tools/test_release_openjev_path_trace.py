"""Release transaction failure injection; temp files and fake Docker only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


def module(name):
 spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
 value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

r=module('release_openjev_path_trace');helpers=module('jeval_reference_queue')


class ReleaseFixture(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.out=self.root/'run';self.out.mkdir()
  self.vout=self.root/'verify';self.vout.mkdir();self.allocation=self.root/'ALLOCATION.json'
  self.journal=self.root/'e38_release_fixture';self.review=self.root/'RELEASE_REVIEW.json'
  self.planpath=self.out/'plan.json';self.request=self.vout/'request.json'
  self.plan=dict(out=str(self.out),container='npu',physical_chip=4,allocation=str(self.allocation),
    execution_revision='astra-v3-strict-attempts',candidate_batch_admission=False,
    container_spec=str(self.out/'spec.json'),wrapper=str(self.out/'wrapper.sh'))
  self.save(self.planpath,self.plan);self.ph=helpers.sha(self.planpath)
  self.save(self.out/'spec.json',{'Cmd':['fake']});(self.out/'wrapper.sh').write_text('wrapper')
  self.save(self.out/'PARENT_REVIEW.json',{'approved_plan_sha256':self.ph})
  actual_review=self.out/'astra.md';actual_review.write_text('test fixture only')
  self.save(self.out/'INDEPENDENT_REVIEW.json',dict(approved=True,approved_plan_sha256=self.ph,
    review_path=str(actual_review),review_sha256=helpers.sha(actual_review)))
  self.save(self.out/'LAUNCH_RECEIPT.json',dict(container_id='npu-id',plan_sha256=self.ph,
    wrapper_sha256=helpers.sha(self.out/'wrapper.sh')))
  self.npu=dict(Id='npu-id',State=dict(Status='exited',ExitCode=0,StartedAt='npu-start',FinishedAt='npu-finish'))
  self.cpu=dict(Id='cpu-id',State=dict(Status='exited',ExitCode=0,FinishedAt='cpu-finish'))
  self.containers={'npu':self.npu,'npu-id':self.npu,'cpu-id':self.cpu}
  self.active=[];self.queries=[]
  manifests={}
  for folder in ['items','attempts']:
   (self.out/folder).mkdir();manifests[folder]={}
   for i in range(8):
    f=self.out/folder/(str(i)+'.json');self.save(f,dict(fixture=i));manifests[folder][f.name]=helpers.sha(f)
  self.report=dict(receipt_manifest=manifests['items'],attempt_manifest=manifests['attempts'])
  self.save(self.out/'report.json',self.report)
  self.terminal=dict(rc=0,stage='completed',plan_sha256=self.ph,progress=8,total=8,trace_valid=False,
    review_flags=['E38 exact control failed: original_hook_effect_0'],outputs={'report.json':helpers.sha(self.out/'report.json')})
  self.save(self.out/'COMPLETE.json',self.terminal);(self.out/'EXIT').write_text('rc=0 utc=fixture\n')
  self.req=dict(task='verify',target_plan=str(self.planpath));self.save(self.request,self.req)
  self.vreport=dict(plan_sha256=self.ph,actual_exit=0,candidate_batch_admission=False,container_id='npu-id',trace_valid=False,
    npu_started_at='npu-start',npu_finished_at='npu-finish',
    terminal_sha256=helpers.sha(self.out/'COMPLETE.json'),report_sha256=helpers.sha(self.out/'report.json'),
    receipt_manifest=manifests['items'],attempt_manifest=manifests['attempts'])
  self.save(self.vout/'report.json',self.vreport)
  self.vterminal=dict(rc=0,stage='completed',progress=1,total=1,request_sha256=helpers.sha(self.request),
    outputs={'report.json':helpers.sha(self.vout/'report.json')})
  self.save(self.vout/'COMPLETE.json',self.vterminal);(self.vout/'EXIT').write_text('rc=0 utc=fixture\n')
  self.approval=dict(schema='e38-resource-release-review-v1',approved=True,approved_plan_sha256=self.ph,
    verification_request_sha256=helpers.sha(self.request),verification_report_sha256=helpers.sha(self.vout/'report.json'),
    verification_terminal_sha256=helpers.sha(self.vout/'COMPLETE.json'),accepted_trace_valid=False,
    accepted_review_flags=self.terminal['review_flags'],candidate_batch_admission=False,
    release_tool_sha256=helpers.sha(Path(r.__file__)),evidence_helper_sha256=helpers.sha(Path(r.__file__).with_name('e38_evidence.py')))
  self.before=dict(allocation=[dict(chip=4,run='reference_inference/run'),dict(chip=6,run='unrelated')],free=[dict(chip=0)])
  self.save(self.allocation,self.before)
  self.approval['allocation_before_sha256']=helpers.sha(self.allocation)
  self.save(self.review,self.approval)
  self.prep=types.SimpleNamespace(preparation_binding=lambda *a:None,
    cpu_binding=lambda q,request,status:(q.load(request),self.cpu),free_now=self.free_now)
  self.delegate=types.SimpleNamespace(atomic=helpers.atomic,utc=lambda:'release-time',inspect=lambda name:self.containers.get(name),
    devices=lambda x:[],binding=self.binding,docker=lambda *a:self.active,
    chip_access=lambda d,chip:d.get('chip')==chip)
  for key,value in [('ROOT',self.root),('ALLOCATION',self.allocation),('PLAN_HASHES',{'run':self.ph})]:
   patcher=patch.object(r,key,value);patcher.start();self.addCleanup(patcher.stop)
 def save(self,path,value):helpers.atomic(path,value)
 def binding(self,d,spec,launch):
  if not d or launch['container_id']!=d['Id']:raise ValueError('Docker launch binding differs')
 def free_now(self,q,chip):self.queries.append(chip)
 def bound(self):
  q=r.evidence.Evidence(self.delegate);p,b=r.bind(self.planpath,self.request,self.review,q,self.prep);return q,p,b
 def run_release(self):
  q,p,b=self.bound();return r.transaction(q,self.prep,p,b,self.journal)
 def test_false_scientific_result_releases_only_own_chip_and_preserves_flags(self):
  result=self.run_release();self.assertEqual(result['status'],'RELEASED')
  got=helpers.load(self.allocation)
  self.assertEqual(got['allocation'],[self.before['allocation'][1]])
  intent=helpers.load(self.journal/'RELEASE_INTENT.json')
  self.assertFalse(intent['bindings']['accepted_trace_valid'])
  self.assertEqual(intent['bindings']['accepted_review_flags'],self.terminal['review_flags'])
  self.assertEqual(helpers.sha(self.allocation),result['allocation_after_sha256'])
  self.assertTrue(self.queries)
 def test_replay_cannot_release_next_owner(self):
  self.run_release();next_owner=dict(allocation=[dict(chip=4,run='next')],free=[]);self.save(self.allocation,next_owner)
  self.queries.clear();self.assertEqual(self.run_release()['status'],'ALREADY_RELEASED')
  self.assertEqual(helpers.load(self.allocation),next_owner);self.assertFalse(self.queries)
 def test_crash_after_allocation_recovers_without_second_mutation(self):
  original=r.evidence.publish_new
  def crash(path,value):
   if Path(path).name=='RELEASED.json':raise KeyboardInterrupt('power loss')
   return original(path,value)
  with patch.object(r.evidence,'publish_new',side_effect=crash):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  after=helpers.sha(self.allocation)
  with patch.object(r,'replace_allocation',side_effect=AssertionError('second allocation write')):
   self.assertEqual(self.run_release()['status'],'RELEASED')
  self.assertEqual(helpers.sha(self.allocation),after)
 def test_crash_after_intent_recovers_exact_before_state(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('power loss')):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  self.assertEqual(helpers.load(self.allocation),self.before)
  self.assertEqual(self.run_release()['status'],'RELEASED')
 def test_foreign_owner_duplicate_free_and_other_chips_rejected(self):
  for changed in [dict(allocation=[dict(chip=4,run='foreign')],free=[]),
    dict(allocation=self.before['allocation'],free=[dict(chip=4)]),dict(allocation=[dict(chip=6,run='reference_inference/run')],free=[])]:
   with self.subTest(changed=changed):
    self.save(self.allocation,changed)
    with self.assertRaises(ValueError):self.run_release()
    self.assertEqual(helpers.load(self.allocation),changed)
 def test_active_or_created_container_and_failed_query_rejected(self):
  for status in ['running','created','paused','restarting']:
   self.containers['foreign']=dict(Id='foreign',State=dict(Status=status),chip=4);self.active=[dict(Id='foreign')]
   with self.subTest(status=status),self.assertRaises(ValueError):self.run_release()
  self.active=[]
  with patch.object(self.prep,'free_now',side_effect=ValueError('process query failed')):
   with self.assertRaises(ValueError):self.run_release()
  self.assertEqual(helpers.load(self.allocation),self.before)
 def test_cpu_or_npu_exit_failure_and_restart_after_binding_rejected(self):
  for obj in [self.cpu,self.npu]:
   obj['State']['ExitCode']=1
   with self.assertRaises(ValueError):self.bound()
   obj['State']['ExitCode']=0
  q,p,b=self.bound();self.cpu['State']['Status']='running'
  with self.assertRaises(ValueError):r.transaction(q,self.prep,p,b,self.journal)
  self.assertEqual(helpers.load(self.allocation),self.before)
 def test_parent_review_must_acknowledge_false_and_flags(self):
  for key,value in [('approved',False),('accepted_trace_valid',True),('accepted_review_flags',[]),('verification_report_sha256','bad')]:
   changed=dict(self.approval,**{key:value});self.save(self.review,changed)
   with self.subTest(key=key),self.assertRaises(ValueError):self.bound()
 def test_changed_evidence_receipt_attempt_review_or_terminal_rejected(self):
  for path in [self.out/'items/0.json',self.out/'attempts/0.json',self.out/'astra.md',self.vout/'COMPLETE.json',self.out/'COMPLETE.json']:
   original=path.read_bytes();path.write_text('{}')
   with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):self.bound()
   path.write_bytes(original)
 def test_report_atomic_replace_between_parse_and_hash_rejected(self):
  q=r.evidence.Evidence(self.delegate);original=json.loads;raw=(self.vout/'report.json').read_bytes();replaced=[]
  def race(data,*a,**kw):
   parsed=original(data,*a,**kw)
   if bytes(data) == raw and not replaced:
    self.save(self.vout/'report.json',dict(parsed,actual_exit=999));replaced.append(True)
   return parsed
  with patch.object(json,'loads',side_effect=race):
   with self.assertRaises(ValueError):r.bind(self.planpath,self.request,self.review,q,self.prep)
  self.assertEqual(replaced,[True])
 def test_pending_intent_cannot_mutate_other_chips_even_if_rehashed(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('power loss')):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  path=self.journal/'RELEASE_INTENT.json';intent=helpers.load(path)
  intent['allocation_after']['allocation']=[];intent['allocation_after_sha256']=r.digest(r.encoded(intent['allocation_after']));self.save(path,intent)
  with self.assertRaises(ValueError):self.run_release()
  self.assertEqual(helpers.load(self.allocation),self.before)
 def test_unrelated_allocation_change_during_gap_blocks_recovery(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('power loss')):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  changed=dict(self.before,updated='another owner update');self.save(self.allocation,changed)
  with self.assertRaises(ValueError):self.run_release()
  self.assertEqual(helpers.load(self.allocation),changed)

 def test_pending_and_completed_intent_before_tampering_rejected(self):
  for completed in (False,True):
   with self.subTest(completed=completed):
    if completed:
     # Restore the pending intent then complete before the second corruption.
     (self.journal/'RELEASE_INTENT.json').write_bytes(original)
     self.run_release()
    else:
     with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('power loss')):
      with self.assertRaises(KeyboardInterrupt):self.run_release()
    path=self.journal/'RELEASE_INTENT.json';original=path.read_bytes();intent=helpers.load(path)
    intent['allocation_before']['allocation'][0]['owner']='forged history'
    self.save(path,intent)
    with self.assertRaises(ValueError):self.run_release()
 def test_self_consistent_before_rehash_still_cannot_change_committed_intent(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('power loss')):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  path=self.journal/'RELEASE_INTENT.json';intent=helpers.load(path)
  intent['allocation_before']['allocation'][0]['owner']='forged history'
  raw=r.encoded(intent['allocation_before']);intent['allocation_before_bytes_b64']=r.base64.b64encode(raw).decode()
  intent['allocation_before_sha256']=r.digest(raw);self.save(path,intent)
  with self.assertRaises(ValueError):self.run_release()
  self.assertEqual(helpers.load(self.allocation),self.before)

 def test_lock_symlinks_are_rejected_without_truncating_target(self):
  outside=self.root/'outside';outside.write_text('sentinel')
  self.journal.mkdir()
  (self.journal/'release.lock').symlink_to(outside)
  q,p,b=self.bound()
  with self.assertRaises((ValueError,OSError)):
   r.transaction(q,self.prep,p,b,self.journal)
  self.assertEqual(outside.read_text(),'sentinel')

if __name__=='__main__':unittest.main()
