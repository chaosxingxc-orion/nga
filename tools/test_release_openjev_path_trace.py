"""Release transaction failure injection; temp files and fake Docker only."""
import copy
import importlib.util
import json
import base64
import shutil
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
  self.anchor=self.root/'TRUSTED_ANCHOR.json'
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
  self.cpu=dict(Id='cpu-id',State=dict(Status='exited',ExitCode=0,StartedAt='cpu-start',FinishedAt='cpu-finish'))
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
  self.req=dict(task='verify',target_plan=str(self.planpath),container='cpu-id');self.save(self.request,self.req)
  self.save(self.vout/'LAUNCH_RECEIPT.json',dict(container_id='cpu-id'))
  self.vreport=dict(plan_sha256=self.ph,actual_exit=0,candidate_batch_admission=False,container_id='npu-id',trace_valid=False,
    npu_started_at='npu-start',npu_finished_at='npu-finish',
    npu_exit_sha256=helpers.sha(self.out/'EXIT'),npu_launch_receipt_sha256=helpers.sha(self.out/'LAUNCH_RECEIPT.json'),
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
  q=r.evidence.Evidence(self.delegate)
  self.save(self.vout/'CPU_EXIT_BINDING.json',r.cpu_exit_binding(q,self.prep,self.request))
  self.approval['cpu_exit_binding_sha256']=helpers.sha(self.vout/'CPU_EXIT_BINDING.json')
  self.save(self.review,self.approval)
  self.save(self.anchor,dict(schema='e38-resource-release-anchor-v1',
    release_review_sha256=helpers.sha(self.review),cpu_exit_binding_sha256=self.approval['cpu_exit_binding_sha256'],
    allocation_before_sha256=helpers.sha(self.allocation),allocation_before_bytes_b64=base64.b64encode(self.allocation.read_bytes()).decode()))
  self.anchor_sha=helpers.sha(self.anchor)
 def save(self,path,value):helpers.atomic(path,value)
 def binding(self,d,spec,launch):
  if not d or launch['container_id']!=d['Id']:raise ValueError('Docker launch binding differs')
 def free_now(self,q,chip):self.queries.append(chip)
 def bound(self):
  q=r.evidence.Evidence(self.delegate);p,b=r.bind(self.planpath,self.request,self.review,q,self.prep,self.anchor,self.anchor_sha);return q,p,b
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
   with self.assertRaises(ValueError):r.bind(self.planpath,self.request,self.review,q,self.prep,self.anchor,self.anchor_sha)
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

 def test_valid_zero_exit_and_launch_receipt_replacement_before_release_rejected(self):
  for path in [self.out/'EXIT',self.vout/'EXIT',self.out/'LAUNCH_RECEIPT.json',self.vout/'LAUNCH_RECEIPT.json']:
   raw=path.read_bytes()
   with self.subTest(path=path):
    if path.name=='EXIT':path.write_text('rc=0 utc=different-but-valid\n')
    else:self.save(path,dict(helpers.load(path),utc='different-generation'))
    with self.assertRaises(ValueError):self.bound()
   path.write_bytes(raw)

 def test_same_id_cpu_or_npu_generation_replacement_before_binding_rejected(self):
  for actual in [self.cpu,self.npu]:
   for key in ['StartedAt','FinishedAt']:
    original=actual['State'][key];actual['State'][key]='restarted'
    with self.subTest(actual=actual['Id'],key=key),self.assertRaises(ValueError):self.bound()
    actual['State'][key]=original

 def test_coordinated_review_journal_rewrite_cannot_change_pinned_before_history(self):
  with patch.object(r,'replace_allocation',side_effect=KeyboardInterrupt('crash')):
   with self.assertRaises(KeyboardInterrupt):self.run_release()
  path=self.journal/'RELEASE_INTENT.json';intent=helpers.load(path)
  before=intent['allocation_before'];before['allocation'][0]['owner']='forged owner history'
  raw=r.encoded(before);new_hash=r.digest(raw)
  self.approval['allocation_before_sha256']=new_hash;self.save(self.review,self.approval)
  intent.update(allocation_before_sha256=new_hash,allocation_before_bytes_b64=base64.b64encode(raw).decode())
  intent['bindings']['approved_allocation_before_sha256']=new_hash
  intent['bindings']['approved_allocation_before_bytes_b64']=base64.b64encode(raw).decode()
  intent['bindings']['release_review_sha256']=helpers.sha(self.review)
  self.save(path,intent)
  self.save(self.journal/'INTENT_COMMITTED.json',dict(intent_sha256=helpers.sha(path)))
  with self.assertRaisesRegex(ValueError,'Anchored release review'):self.run_release()
  # Rewriting the anchor too cannot change the digest pinned by the caller.
  anchor=helpers.load(self.anchor);anchor.update(release_review_sha256=helpers.sha(self.review),
    allocation_before_sha256=new_hash,allocation_before_bytes_b64=base64.b64encode(raw).decode())
  self.save(self.anchor,anchor)
  with self.assertRaisesRegex(ValueError,'Trusted release anchor changed'):self.run_release()
  self.assertEqual(helpers.load(self.allocation),self.before)

 def test_publication_internal_crashes_recover_without_second_allocation_mutation(self):
  original_link=r.evidence.os.link;original_unlink=r.evidence.os.unlink
  original_sync=r.evidence.sync_directory
  for filename in ['RELEASE_INTENT.json','INTENT_COMMITTED.json','RELEASED.json']:
   for stage in ['before_link','after_link','before_unlink_sync','after_unlink']:
    with self.subTest(filename=filename,stage=stage):
     if self.journal.exists():
      shutil.rmtree(self.journal)
     self.save(self.allocation,self.before);injected=[]
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
      with self.assertRaises(KeyboardInterrupt):self.run_release()
     self.assertTrue(injected)
     after=helpers.load(self.allocation)
     self.delegate.utc=lambda:'later-retry-time'
     if after!=self.before:
      with patch.object(r,'replace_allocation',side_effect=AssertionError('second mutation')):
       result=self.run_release()
     else:result=self.run_release()
     self.assertIn(result['status'],['RELEASED','ALREADY_RELEASED'])
     self.assertFalse(list(self.journal.glob('*.pending')))

 def entry_fixture(self):
  # Exercise release() and its compiled import closure with the real queue
  # helper. Docker and host/preparation history are synthetic in this fixture.
  source=Path(r.__file__).parent
  for name in ['jeval_reference_queue.py','e38_evidence.py']:
   shutil.copy2(source/name,self.out/name)
  (self.out/'prepare_openjev_path_trace.py').write_text('''from pathlib import Path
def module(path,name):
    raise AssertionError('path loader must be replaced')
def helper(folder):
    queue=module(folder/'jeval_reference_queue.py','fixture_queue')
    return module(folder/'e38_evidence.py','fixture_evidence').Evidence(queue)
def host(q):
    q.require(q.docker('GET','/info')['Name']=='k8s-node1','Wrong Docker host')
def preparation_binding(q,path,plan):
    q.require(plan['fixture_preparation'] is True,'Fixture preparation differs')
def cpu_binding(q,path,status):
    request=q.load(path);actual=q.inspect(request['container'])
    q.binding(actual,q.load(request['container_spec']),q.load(path.parent/'LAUNCH_RECEIPT.json'))
    q.require(actual['State']['Status']==status,'CPU state differs')
    return request,actual
def free_now(q,chip):
    q.require(q.docker('GET','/fixture-empty/'+str(chip))=={'empty':True},'Fixture occupied')
''')
  for folder,actual in [(self.out,self.npu),(self.vout,self.cpu)]:
   spec=dict(Image=helpers.IMAGE,Cmd=['bash',str(folder/'wrapper.sh')],Entrypoint=['bash'],Env=[],Labels={},
     HostConfig=dict(Binds=[],Devices=[],NetworkMode='none',ShmSize=67108864))
   actual.update(Image=helpers.IMAGE,Config={k:copy.deepcopy(spec[k]) for k in ['Cmd','Entrypoint','Env','Labels']},
     HostConfig=copy.deepcopy(spec['HostConfig']))
   self.save(folder/'spec.json',spec)
   receipt=helpers.load(folder/'LAUNCH_RECEIPT.json')
   receipt.update(image=helpers.IMAGE,command=spec['Cmd'],entrypoint=spec['Entrypoint'])
   self.save(folder/'LAUNCH_RECEIPT.json',receipt)
  self.plan.update(fixture_preparation=True,files={str(self.out/name):helpers.sha(self.out/name)
    for name in ['prepare_openjev_path_trace.py','jeval_reference_queue.py','e38_evidence.py']})
  self.save(self.planpath,self.plan);self.ph=helpers.sha(self.planpath);r.PLAN_HASHES['run']=self.ph
  self.save(self.out/'PARENT_REVIEW.json',dict(approved_plan_sha256=self.ph))
  independent=helpers.load(self.out/'INDEPENDENT_REVIEW.json');independent['approved_plan_sha256']=self.ph
  self.save(self.out/'INDEPENDENT_REVIEW.json',independent)
  receipt=helpers.load(self.out/'LAUNCH_RECEIPT.json');receipt['plan_sha256']=self.ph
  self.save(self.out/'LAUNCH_RECEIPT.json',receipt)
  self.terminal['plan_sha256']=self.ph;self.save(self.out/'COMPLETE.json',self.terminal)
  self.req['container_spec']=str(self.vout/'spec.json');self.save(self.request,self.req)
  self.vreport.update(plan_sha256=self.ph,terminal_sha256=helpers.sha(self.out/'COMPLETE.json'),
    npu_launch_receipt_sha256=helpers.sha(self.out/'LAUNCH_RECEIPT.json'))
  self.save(self.vout/'report.json',self.vreport)
  self.vterminal.update(request_sha256=helpers.sha(self.request),outputs={'report.json':helpers.sha(self.vout/'report.json')})
  self.save(self.vout/'COMPLETE.json',self.vterminal)
  self.save(self.vout/'CPU_EXIT_BINDING.json',r.cpu_exit_binding(r.evidence.Evidence(self.delegate),self.prep,self.request))
  self.approval.update(approved_plan_sha256=self.ph,verification_request_sha256=helpers.sha(self.request),
    verification_report_sha256=helpers.sha(self.vout/'report.json'),verification_terminal_sha256=helpers.sha(self.vout/'COMPLETE.json'),
    cpu_exit_binding_sha256=helpers.sha(self.vout/'CPU_EXIT_BINDING.json'))
  self.save(self.review,self.approval)
  anchor=helpers.load(self.anchor);anchor.update(release_review_sha256=helpers.sha(self.review),
    cpu_exit_binding_sha256=self.approval['cpu_exit_binding_sha256'])
  self.save(self.anchor,anchor);self.anchor_sha=helpers.sha(self.anchor)

 def fake_http(self):
  outer=self
  class Response:
   status=200
   def __init__(self,value):self.value=value
   def read(self):return json.dumps(self.value).encode()
  class Connection:
   def __init__(self,*a,**kw):pass
   def request(self,method,path,**kw):
    outer.assertEqual(method,'GET');self.path=path
   def getresponse(self):
    if self.path=='/info':return Response({'Name':'k8s-node1'})
    if self.path.startswith('/fixture-empty/'):return Response({'empty':True})
    if self.path=='/containers/json?all=1':return Response([])
    if self.path.startswith('/containers/') and self.path.endswith('/json'):
     return Response(outer.containers[self.path.split('/')[2]])
    raise AssertionError(self.path)
   def close(self):self.sock.close()
  return Connection

 def test_real_release_entry_compiles_frozen_queue_closure_and_releases_fixture(self):
  import http.client
  self.entry_fixture()
  with patch.object(http.client,'HTTPConnection',self.fake_http()),patch('socket.socket'):
   result=r.release(self.planpath,self.request,self.review,self.journal,self.anchor,self.anchor_sha)
  self.assertEqual(result['status'],'RELEASED')
  self.assertEqual(helpers.load(self.allocation)['allocation'],[self.before['allocation'][1]])

 def test_real_entry_rejects_changed_nested_queue_before_execution(self):
  self.entry_fixture();queue=self.out/'jeval_reference_queue.py'
  queue.write_text("raise AssertionError('UNVERIFIED_REPLACEMENT_EXECUTED')\n")
  with self.assertRaisesRegex(ValueError,'Frozen release dependency changed'):
   r.release(self.planpath,self.request,self.review,self.journal,self.anchor,self.anchor_sha)
  self.assertEqual(helpers.load(self.allocation),self.before)

 def test_frozen_context_rejects_changed_noncore_python_dependency(self):
  self.entry_fixture()
  extra=self.out/'extra_historical_dependency.py';extra.write_text('trusted = True\n')
  self.plan['files'][str(extra)]=helpers.sha(extra)
  self.save(self.planpath,self.plan);r.PLAN_HASHES['run']=helpers.sha(self.planpath)
  extra.write_text("raise AssertionError('UNVERIFIED_NONCORE_EXECUTION')\n")
  with self.assertRaisesRegex(ValueError,'Frozen Python dependency changed'):
   r.frozen_context(self.planpath)
  self.assertEqual(helpers.load(self.allocation),self.before)

 def test_real_cpu_exit_attestation_persists_current_generation_and_refuses_replacement(self):
  import http.client
  self.entry_fixture();before=self.allocation.read_bytes()
  (self.vout/'CPU_EXIT_BINDING.json').unlink()
  with patch.object(http.client,'HTTPConnection',self.fake_http()),patch('socket.socket'):
   result=r.attest_cpu_exit(self.planpath,self.request)
   self.assertEqual(result['sha256'],helpers.sha(self.vout/'CPU_EXIT_BINDING.json'))
   stored=helpers.load(self.vout/'CPU_EXIT_BINDING.json')
   self.assertEqual(stored['cpu_finished_at'],'cpu-finish')
   self.assertEqual(stored['cpu_exit_sha256'],helpers.sha(self.vout/'EXIT'))
   self.cpu['State']['FinishedAt']='another-exit'
   with self.assertRaises(FileExistsError):r.attest_cpu_exit(self.planpath,self.request)
  self.assertEqual(self.allocation.read_bytes(),before)

class BootstrapTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.path=self.root/'e38_evidence.py'
  self.good=b'authenticated = True\n';self.bad=b"raise AssertionError('UNVERIFIED_HELPER_EXECUTED')\n"
  self.path.write_bytes(self.good);self.digest=r.digest(self.good)

 def test_tampered_helper_is_rejected_before_any_execution(self):
  self.path.write_bytes(self.bad)
  with self.assertRaisesRegex(ValueError,'Bootstrap helper SHA256'):
   r.bootstrap_module(self.path,'bootstrap_bad',self.digest)

 def test_real_release_import_refuses_replaced_global_helper(self):
  target=self.root/'release_openjev_path_trace.py'
  shutil.copy2(Path(r.__file__),target);self.path.write_bytes(self.bad)
  spec=importlib.util.spec_from_file_location('bootstrap_release_bad',target)
  value=importlib.util.module_from_spec(spec)
  with self.assertRaisesRegex(ValueError,'Bootstrap helper SHA256'):
   spec.loader.exec_module(value)

 def test_path_replacement_after_hash_is_rejected(self):
  real=r.hashlib.sha256;replaced=[]
  def racing_hash(raw):
   result=real(raw)
   if raw==self.good and not replaced:
    other=self.root/'replacement';other.write_bytes(self.bad);other.replace(self.path);replaced.append(True)
   return result
  with patch.object(r.hashlib,'sha256',side_effect=racing_hash):
   with self.assertRaisesRegex(ValueError,'Bootstrap helper (path )?changed'):
    r.bootstrap_module(self.path,'bootstrap_race',self.digest)
  self.assertEqual(replaced,[True])

 def test_after_validation_path_replacement_executes_only_snapshot(self):
  import builtins
  original=builtins.compile;replaced=[]
  def racing_compile(raw,filename,*args,**kwargs):
   if filename==str(self.path) and not replaced:
    self.path.write_bytes(self.bad);replaced.append(True)
   return original(raw,filename,*args,**kwargs)
  with patch.object(builtins,'compile',side_effect=racing_compile):
   value=r.bootstrap_module(self.path,'bootstrap_snapshot',self.digest)
  self.assertTrue(value.authenticated);self.assertEqual(replaced,[True])

 def test_symlink_helper_and_parent_are_rejected(self):
  actual=self.root/'actual.py';self.path.rename(actual);self.path.symlink_to(actual)
  with self.assertRaises(OSError):r.bootstrap_module(self.path,'bootstrap_link',self.digest)
  directory=self.root/'directory';directory.mkdir();(directory/'helper.py').write_bytes(self.good)
  link=self.root/'alias';link.symlink_to(directory,target_is_directory=True)
  with self.assertRaises(OSError):r.bootstrap_module(link/'helper.py','bootstrap_parent',self.digest)

if __name__=='__main__':unittest.main()
