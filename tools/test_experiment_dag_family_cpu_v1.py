import copy,importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parent
def mod(n):
 p=ROOT/(n+'.py');s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=mod('experiment_dag_family_cpu_v1');S=mod('experiment_dag_family_service_v1');D=mod('experiment_dag');N=mod('experiment_dag_native')
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def put(self,n,v):
  p=self.root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v));return A.ref(p)
 def release_fixture(self):
  v=dict(run='fixture',chip=5,allocation=str(self.root/'allocation.json'),out=str(self.root/'previous'),container='panel',image_sha256='image');h=Path(v['out'])/'host_attempts/1';h.mkdir(parents=True);source={'path':str(self.root/'SOURCE.json'),'sha256':'1'*64};cl=dict(schema='r3-resource-claim-v1',run='fixture',chip=5,allocation=v['allocation']);cp=self.put('previous/host_attempts/1/CLAIM.json',cl)
  spec=dict(plan_sha256=source['sha256'],command=['docker','run','image','python3','run']);self.put('previous/host_attempts/1/LAUNCH_SPEC.json',spec);self.put('previous/host_attempts/1/LAUNCH_RECEIPT.json',dict(plan_sha256=source['sha256'],attempt=1,scientific_acceptance=False,container_id='cid',command=['python3','run']))
  rel=dict(schema='r3-resource-release-v1',run='fixture',chip=5,claim_sha256=cp['sha256'],scientific_acceptance=False,exit_code=1,container_id='cid',container='panel-a1',container_started_at='start',container_finished_at='finish',allocation_after={'allocation':[],'free':[{'chip':5,'previous_run':'fixture','release_evidence':str(h/'RELEASE.json')}]});self.put('previous/host_attempts/1/RELEASE.json',rel)
  actual=dict(Id='cid',Image='image',Config={'Cmd':['python3','run']},State={'Status':'exited','Running':False,'ExitCode':1,'StartedAt':'start','FinishedAt':'finish'},HostConfig={'Devices':[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x} for x in ['davinci_manager','devmm_svm','hisi_hdc','davinci5']],'Privileged':False,'NetworkMode':'none','AutoRemove':False})
  return dict(attempt=1),({}, {}, {}, {'source':source}, v),actual
 def test_physical_failure_release_is_ready_without_cpu_analysis(self):
  b,d,actual=self.release_fixture()
  with patch.object(A,'describe',return_value=d):r=A.release_evidence(b,lambda name:actual)
  self.assertEqual(r['exit_code'],1);self.assertFalse(r['test_quality_required'])
 def test_missing_release_never_queries_hardware(self):
  b,d,actual=self.release_fixture();(Path(d[4]['out'])/'host_attempts/1/RELEASE.json').unlink()
  with patch.object(A,'describe',return_value=d):self.assertIsNone(A.release_evidence(b,lambda name:self.fail('unexpected inspect')))
 def test_release_generation_and_device_mutations_reject(self):
  b,d,actual=self.release_fixture()
  for field in ['StartedAt','FinishedAt','ExitCode']:
   bad=copy.deepcopy(actual);bad['State'][field]=False if field=='ExitCode' else 'restart'
   with patch.object(A,'describe',return_value=d),self.subTest(field=field),self.assertRaises(ValueError):A.release_evidence(b,lambda name:bad)
  bad=copy.deepcopy(actual);bad['HostConfig']['Devices'].append({'PathOnHost':'/dev/davinci0','PathInContainer':'/dev/davinci0'})
  with patch.object(A,'describe',return_value=d),self.assertRaises(ValueError):A.release_evidence(b,lambda name:bad)
 def graph(self):
  impl=A.ref(A.__file__);nodes=[]
  for size,chip in [('4b',5),('9b',0)]:
   source=self.put(size+'-source.json',{'fixture':size});bind=self.put(size+'-binding.json',{'id':size});review=self.put(size+'-review.json',{'fixture_only':True})
   nodes.append(dict(id='release_'+size,lane='npu',devices=[chip],priority=90,purpose='release fixture',split='DEV',protocol='fixed',sources=[source],adapter='family_cpu_bind_v1',stage='planned',managed_by='external_frozen',depends_on=[],action=None,missing=[]))
   nodes.append(dict(id='bind_'+size,lane='cpu',devices=[],priority=80,purpose='bind fixture',split='DEV',protocol='fixed',sources=[source],adapter='family_cpu_bind_v1',stage='planned',managed_by='dag',depends_on=[dict(node='release_'+size,kind='resource_release')],action=dict(binding=bind,review=review),missing=[]))
  return dict(schema='nga-experiment-dag-v1',id='fixture',policy=dict(poll_seconds=600,cpu_slots=2,target_ready_depth=2,target_reserve_depth=2,ordering='priority_then_id'),adapters={'family_cpu_bind_v1':dict(version=1,implementation=impl,integration='reviewed_dispatch')},nodes=nodes)
 def snap(self,g,states):
  return dict(schema='nga-dag-observation-v1',graph_sha256=D.digest(g),as_of='fixture',authority='adapter_observations',observations=states,resources={str(i):'unknown' for i in range(8)})
 def test_two_cpu_branches_and_isolated_uncertainty(self):
  g=self.graph();fake=types.SimpleNamespace(implementation_sha256=A.sha(A.__file__),authorize=lambda *x:True)
  ready=lambda:dict(state='released',facts=['resource_release'],failed_facts=[],evidence=[])
  s=self.snap(g,{'release_4b':ready(),'release_9b':ready()});self.assertEqual(set(D.plan(g,s,{A.ADAPTER_ID:fake})['proposed']),{'bind_4b','bind_9b'})
  s['observations']['release_4b']=dict(state='uncertain',facts=[],failed_facts=[],evidence=[]);self.assertEqual(D.plan(g,s,{A.ADAPTER_ID:fake})['proposed'],['bind_9b'])
 def test_uncertain_intent_never_reexecutes_and_other_branch_can_start(self):
  g=self.graph();calls=[];fake=types.SimpleNamespace(implementation_sha256=A.sha(A.__file__),authorize=lambda *x:True,observe=lambda *x:{'state':'absent'},reserve_and_start=lambda b,n,t:calls.append(n['id']) or {'pid':1})
  ready=dict(state='released',facts=['resource_release'],failed_facts=[],evidence=[]);s=self.snap(g,{'release_4b':ready,'release_9b':ready});reg={A.ADAPTER_ID:fake};D.dispatch_once(g,s,reg,self.root/'journal');D.dispatch_once(g,s,reg,self.root/'journal');self.assertEqual(sorted(calls),['bind_4b','bind_9b'])
 def test_cpu_ready_has_no_science_or_npu_success_claim(self):
  out=self.root/'worker';out.mkdir();b=dict(role='bind_reference',output=str(out));plan=self.put('PLAN.json',{'out':'/fixture/output'});bound=self.put('BOUND.json',{'plan':plan,'spec':{'fixture_only':True}});ready=self.put('worker/READY.json',dict(status='ready_for_review',binding_sha256=A.digest(b),graph_sha256='gh',model='4B',activation_authorized=False,npu_started=False,bound=bound,plan=plan));self.put('worker/EXIT.json',dict(exit_code=0,binding_sha256=A.digest(b),graph_sha256='gh',npu_started=False,ready=ready));a=A.FamilyCPUAdapter(D,N);a.bindings['x']=(b,{'spec':{'fixture_only':True},'model':'4B'}, {'root':'/fixture'},'gh');r=a.observe({'id':'x'},None);self.assertEqual(r['facts'],['success','artifact']);self.assertNotIn('scientific_admission',r['facts'])
 def test_cpu_failed_and_uncertain_are_distinct(self):
  out=self.root/'worker';out.mkdir();b=dict(role='bind_reference',output=str(out));a=A.FamilyCPUAdapter(D,N);a.bindings['x']=(b,{}, {},'gh');self.assertEqual(a.observe({'id':'x'},None)['state'],'uncertain');self.put('worker/EXIT.json',dict(exit_code=1,binding_sha256=A.digest(b),graph_sha256='gh',npu_started=False));self.assertEqual(a.observe({'id':'x'},None)['state'],'failed')
 def test_external_observer_cannot_execute(self):
  a=A.FamilyCPUAdapter(D,N);b={'role':'physical_release'};a.bindings['x']=(b,{}, {},'gh')
  with self.assertRaises(ValueError):a.reserve_and_start(b,{'id':'x','managed_by':'external_frozen'},'token')
 def test_worker_validation_failure_writes_terminal_before_effect(self):
  out=self.root/'worker';out.mkdir();b=dict(output=str(out));intent=self.put('worker/INTENT.json',dict(schema='native-family-cpu-intent-v1',binding=b,core=A.ref(D.__file__),native={'path':str(self.root/'missing.py'),'sha256':'0'*64},token='t',graph_sha256='gh',service_identity=None))
  with self.assertRaises(OSError):A.worker(intent['path'])
  end=A.read(out/'EXIT.json');self.assertEqual(end['exit_code'],1);self.assertFalse(end['npu_started']);self.assertTrue((out/'ERROR.json').exists())
 def test_worker_terminal_is_never_overwritten_by_replay(self):
  out=self.root/'worker';out.mkdir();self.put('worker/INTENT.json',{'schema':'no-effect fixture'});self.put('worker/EXIT.json',{'exit_code':0});before=(out/'EXIT.json').read_bytes()
  with self.assertRaises(ValueError):A.worker(str(out/'INTENT.json'))
  self.assertEqual((out/'EXIT.json').read_bytes(),before)
 def test_one_admission_error_does_not_erase_other_branch(self):
  g=self.graph();obs=dict(state='released',facts=['resource_release'],failed_facts=[],evidence=[]);adapter=types.SimpleNamespace(admission_errors={'release_4b':dict(error_type='ValueError',reason='changed')},observe=lambda n,i:obs if n['id']=='release_9b' else {'state':'absent'})
  snap,errors=S.snapshot({},g,D,A,N,adapter);self.assertEqual(snap['observations']['release_4b']['state'],'uncertain');self.assertEqual(snap['observations']['release_9b']['facts'],['resource_release']);self.assertEqual(set(errors),{'release_4b'})
 def test_same_config_restart_preserves_controller_intent(self):
  out=self.root/'service';out.mkdir();review={'path':'/review','sha256':'a'*64};intent=self.put('service/SERVICE_START_INTENT.json',dict(config_sha256='pin',review=review));self.put('service/SERVICE.json',dict(pid=123,boot_id='old',start_ticks=1,config_sha256='pin',review=review,start_intent=intent));self.put('service/controller/state.json',dict(graph_sha256='g',attempts={'bind_4b':{'status':'uncertain'}}));before=(out/'controller/state.json').read_bytes()
  with patch.object(A,'same_process',return_value=True),self.assertRaises(ValueError):S.reconcile_service(out,'pin',review,A,D)
  with patch.object(A,'same_process',return_value=False):S.reconcile_service(out,'pin',review,A,D)
  self.assertEqual((out/'controller/state.json').read_bytes(),before)
  with patch.object(A,'same_process',return_value=False),self.assertRaises(ValueError):S.reconcile_service(out,'foreign',review,A,D)
 def test_no_arbitrary_command_or_npu_launch_surface(self):
  source=Path(A.__file__).read_text();self.assertNotIn("['docker','run'",source);self.assertNotIn("['npu-smi'",source);self.assertIn("K.bind(c['spec']",source);self.assertNotIn("host','start",source)
 def test_worker_environment_and_inherited_service_lock(self):
  source=Path(S.__file__).read_text();self.assertIn("pass_fds=(lock.fileno(),)",source);self.assertIn("env.update(c['environment'])",source);self.assertIn('wake.wait(600)',source);self.assertIn("name==b'RELEASE.json'",source)

 def capability_fixture(self):
  sources=[]
  for i in range(4):
   p=self.root/('source'+str(i)+'.py');p.write_text('# fixture '+str(i));sources.append(A.ref(p))
  c=dict(model='4B',source_files=sources);cr=self.put('candidate.json',c)
  ri=dict(schema='native-dev72-family-registration-review-input-v1',candidate=cr,source_files=sources)
  for k in ('launch_authorized','scientific_acceptance','physical_release_asserted','npu_launched','test_read'):ri[k]=False
  rr=self.put('review-input.json',ri)
  r=dict(schema='native-dev72-family-registration-independent-v1',verdict='PASS_PREPARATION_AND_BINDING_CAPABILITY_ONLY',review_inputs={'4B':rr})
  for k in ('activation_authorized','scientific_acceptance','numerical_acceptance','physical_release_asserted','resource_claimed','npu_used','test_read'):r[k]=False
  return cr,c,ri,r
 def test_actual_receipt_shape_binds_candidate_and_four_sources(self):
  cr,c,ri,r=self.capability_fixture();self.assertEqual(A.capability_review(cr,c,r),ri)
  self.assertFalse(r['activation_authorized'])
 def test_receipt_wrong_model_authority_candidate_source_and_tamper_reject(self):
  cr,c,ri,r=self.capability_fixture()
  for key,value in [('verdict','PASS'),('schema','invented'),('activation_authorized',True),('scientific_acceptance',True),('numerical_acceptance',True),('review_inputs',{'9B':r['review_inputs']['4B']})]:
   bad=copy.deepcopy(r);bad[key]=value
   with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):A.capability_review(cr,c,bad)
  for key,value in [('candidate',dict(cr,sha256='0'*64)),('source_files',c['source_files'][:3]),('launch_authorized',True)]:
   bad=copy.deepcopy(ri);bad[key]=value;rr=copy.deepcopy(r);rr['review_inputs']['4B']=self.put('bad-input.json',bad)
   with self.subTest(key=key),self.assertRaises(ValueError):A.capability_review(cr,c,rr)
  Path(c['source_files'][0]['path']).write_text('# changed')
  with self.assertRaises(ValueError):A.capability_review(cr,c,r)
 def launch_fixture(self):
  out=self.root/'service';out.mkdir()
  args=types.SimpleNamespace(op='start',sha256='pin',config='/fixture/config',review='/fixture/review',review_sha256='r')
  c=dict(service_python='/usr/bin/python3.12',environment={'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'/fixture/python'})
  review=dict(path=args.review,sha256=args.review_sha256)
  return out,args,c,review
 def test_parent_receipt_failure_after_popen_cannot_start_or_restart(self):
  out,args,c,review=self.launch_fixture();calls=[]
  def launch(*a,**kw):
   self.assertTrue((out/'SERVICE_START_INTENT.json').exists());calls.append(a);return types.SimpleNamespace(pid=123)
  def atomic(p,v):
   if Path(p).name=='SERVICE.json':raise OSError('injected receipt failure')
   return D.atomic(p,v)
  fakeD=types.SimpleNamespace(atomic=atomic)
  with (out/'service.lock').open('a') as lock,patch.object(S.subprocess,'Popen',side_effect=launch),patch.object(A,'identity',return_value=dict(pid=123,boot_id='boot',start_ticks=1)):
   with self.assertRaises(OSError):S.launch_service(c,args,review,out,lock,A,fakeD)
   original=(out/'SERVICE_START_INTENT.json').read_bytes()
   for op in ('start','restart'):
    args.op=op
    with self.assertRaises(ValueError):S.launch_service(c,args,review,out,lock,A,D)
   self.assertEqual((out/'SERVICE_START_INTENT.json').read_bytes(),original)
  self.assertEqual(len(calls),1)
 def test_popen_failure_retains_intent_and_rejects_blind_retry(self):
  out,args,c,review=self.launch_fixture()
  with (out/'service.lock').open('a') as lock,patch.object(S.subprocess,'Popen',side_effect=OSError('injected')) as popen:
   with self.assertRaises(OSError):S.launch_service(c,args,review,out,lock,A,D)
   self.assertTrue((out/'SERVICE_START_INTENT.json').exists())
   with self.assertRaises(ValueError):S.launch_service(c,args,review,out,lock,A,D)
   self.assertEqual(popen.call_count,1)
 def test_restart_receipt_must_match_current_intent(self):
  out,args,c,review=self.launch_fixture()
  self.put('service/SERVICE_START_INTENT.json',dict(config_sha256='pin',review=review,generation=2))
  self.put('service/SERVICE.json',dict(config_sha256='pin',review=review,start_intent={'path':str(out/'SERVICE_START_INTENT.json'),'sha256':'0'*64}))
  with patch.object(A,'same_process',return_value=False),self.assertRaises(ValueError):S.reconcile_service(out,'pin',review,A,D)


 def test_confirmed_dead_restart_archives_intent_and_preserves_worker_journal(self):
  out,args,c,review=self.launch_fixture();pids=iter([123,456])
  with (out/'service.lock').open('a') as lock,patch.object(S.subprocess,'Popen',side_effect=lambda *a,**kw:types.SimpleNamespace(pid=next(pids))),patch.object(A,'identity',side_effect=lambda pid:dict(pid=pid,boot_id='boot',start_ticks=pid)),patch.object(A,'same_process',return_value=False):
   self.assertEqual(S.launch_service(c,args,review,out,lock,A,D),123)
   old=S.read(out/'SERVICE.json');old_hash=S.sha(out/'SERVICE.json')
   self.put('service/controller/state.json',dict(attempts={'bind_4b':{'status':'uncertain'}}))
   journal=(out/'controller/state.json').read_bytes()
   args.op='restart';self.assertEqual(S.launch_service(c,args,review,out,lock,A,D),456)
   self.assertEqual((out/'controller/state.json').read_bytes(),journal)
   self.assertEqual(S.read(out/'history'/old_hash/'SERVICE.json'),old)
   self.assertEqual(S.read(out/'SERVICE.json')['start_intent'],S.ref(out/'SERVICE_START_INTENT.json'))

if __name__=='__main__':unittest.main()
