"""CPU-only registered-schema lifecycle tests; no device or docker queries."""
import copy,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parent
PREP=ROOT.parent/'.local/preparations/dag-exploration-adapters-20261103-v1'
def mod(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
N=mod('experiment_dag_exploration_v1');S=mod('experiment_dag_exploration_service_v1');D=mod('experiment_dag')

class RegisteredSchemas(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.cap=N.read(PREP/'CAPABILITIES.json');self.calls=[]
 def write(self,name,value):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return N.ref(p)
 def fixture(self,kind='native_dev72_shard_v1'):
  filename='NATIVE08B_SHARD-BINDING.json' if kind=='native_dev72_shard_v1' else 'PROFILE_NAMED-BINDING.json'
  self.b=N.read(PREP/filename);self.p=N.pinned(self.b['plan']);self.p.update(out=str(self.root/'out'),container='fixture',allocation=str(self.root/'ALLOCATION.json'))
  self.b['node_id']='fixture';self.b['plan']=self.write('PLAN.json',self.p)
  self.view,self.cmd,argv,split=N.describe(self.b,self.cap)
  self.review=N.pinned(self.b['review']);self.review['approved_plan_sha256']=self.b['plan']['sha256'];self.review['approved_plan']=self.b['plan']['path'];self.review['expected_commands']={'1':self.cmd};self.review['hashes']={**self.p['files'],self.b['plan']['path']:self.b['plan']['sha256']}
  if kind=='profile_named_async_v1':
   H=N.module(self.p['host']);self.review['cpu_commands']={str(i):H.cpu_command(self.p,self.b['plan']['path'],self.b['plan']['sha256'],i) for i in self.p['parse_attempts']}
  self.b['review']=self.write('REVIEW.json',self.review)
  self.node={'id':'fixture','lane':'npu','devices':[self.p['chip']],'priority':1,'purpose':'CPU fixture of real registered schema','split':'DEV','protocol':self.b['protocol'],'sources':[self.b['plan']],'adapter':N.ADAPTER_ID,'stage':'planned','managed_by':'dag','depends_on':[],'action':{'binding':self.write('BINDING.json',self.b),'review':self.b['review']},'missing':[]}
  self.g={'schema':'nga-experiment-dag-v1','id':'fixture','policy':{'poll_seconds':600,'cpu_slots':2,'target_ready_depth':3,'target_reserve_depth':6,'ordering':'priority_then_id'},'adapters':{N.ADAPTER_ID:{'version':1,'implementation':N.ref(N.__file__),'integration':'reviewed_dispatch'}},'nodes':[self.node]}
  self.gh=D.digest(self.g);self.grant={'schema':'nga-exploration-dag-activation-v1','verdict':'PASS','activation_authorized':True,'scientific_acceptance':False,'graph_sha256':self.gh,'bindings':{'fixture':self.node['action']},'capabilities':self.cap}
  self.actual=None;self.a=N.ExplorationAdapter(self.cap,self.root/'service',query=lambda name:self.actual,launch=lambda argv,e,t:self.calls.append(argv) or {'pid':1},grant=self.grant)
  self.a.authorize(self.b,self.review,self.node,self.gh)
  return self.a
 def lifecycle(self,rc=0,artifact=False):
  h=Path(self.p['out'])/'host_attempts/1';a=Path(self.p['out'])/'attempts/1';h.mkdir(parents=True);a.mkdir(parents=True)
  image=self.view['image'];cid='c'*64;cmd=self.cmd[self.cmd.index(image)+1:]
  self.actual={'Id':cid,'Image':image,'Config':{'Cmd':cmd},'HostConfig':{'AutoRemove':False,'Privileged':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x} for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci'+str(self.p['chip']))]},'State':{'Status':'running' if rc is None else 'exited','Running':rc is None,'ExitCode':0 if rc is None else rc,'StartedAt':'2026-11-03T10:00:00Z','FinishedAt':'2026-11-03T10:01:00Z'}}
  def put(p,x):p.write_text(json.dumps(x))
  put(h/'LAUNCH_SPEC.json',{'command':self.cmd,'plan_sha256':self.b['plan']['sha256']})
  put(h/'LAUNCH_RECEIPT.json',{'container_id':cid,'command':cmd,'plan_sha256':self.b['plan']['sha256'],'attempt':1,'scientific_acceptance':False})
  put(h/'CLAIM.json',{'schema':'r3-resource-claim-v1','run':self.p['run'],'chip':self.p['chip'],'allocation':self.p['allocation'],'scientific_acceptance':False,'execution_authorized':False})
  if rc is not None:
   put(h/'RELEASE.json',{'schema':'r3-resource-release-v1','run':self.p['run'],'chip':self.p['chip'],'claim_sha256':N.sha(h/'CLAIM.json'),'container_id':cid,'container':'fixture-a1','exit_code':rc,'scientific_acceptance':False,'container_started_at':'2026-11-03T10:00:00Z','container_finished_at':'2026-11-03T10:01:00Z'})
   terminal={'plan_sha256':self.b['plan']['sha256'],'attempt':1,'exit_code':rc,'scientific_acceptance':False,'test_read':False}
   put(a/'EXIT.json',terminal);put(h/'EXIT.json',{**terminal,'container_id':cid,'container_exit_code':rc,'runner_terminal_matches':True})
   if artifact:
    report={**terminal,'schema':'native-dev72-shards-complete-v1','items':72,'numerical_equivalence_verified':False}
    if self.b['kind']=='profile_named_async_v1':
     report['schema']='r3-profile-runtime-report-v1';put(a/'FORWARDS.json',{'fixture':True});put(a/'RAW-MANIFEST.json',{'schema':'r3-profile-raw-manifest-v1','plan_sha256':self.b['plan']['sha256']});report.update(forward_manifest_sha256=N.sha(a/'FORWARDS.json'),raw_manifest_sha256=N.sha(a/'RAW-MANIFEST.json'))
    put(a/'report.json',report)
  return h,a
 def snapshot(self):return {'schema':'nga-dag-observation-v1','graph_sha256':self.gh,'as_of':'fixture','authority':'adapter_observations','observations':{},'resources':{str(i):'free_observed' for i in range(8)}}
 def config(self):
  return {'schema':'nga-exploration-dag-service-v1','host_name':'k8s-node1','output':str(self.root/'service'),'graph':self.write('GRAPH.json',self.g),'allocation':self.p['allocation'],'modules':{'dag':N.ref(D.__file__),'native':N.ref(N.__file__),'service':N.ref(S.__file__)},'capabilities':self.cap,'mode':'plan','activation':None,'interval_seconds':600,'service_python':'/usr/bin/python3.12'}
 def test_actual_packages_dryrun_exact_command_without_queries(self):
  config=N.read(PREP/'SERVICE-CONFIG.json');adapter=N.ExplorationAdapter(config['capabilities'],config['output'],query=lambda name:self.fail('device query'))
  graph=N.pinned(config['graph']);snap,errors=S.make_snapshot(config,graph,D,N,adapter,False)
  self.assertEqual(errors,{});self.assertEqual(set(adapter.bindings),{'native08b_shard','profile_named'})
  for b,d,cmd,argv,gh in adapter.bindings.values():
   self.assertEqual(cmd,N.pinned(b['review'])['expected_commands']['1']);self.assertEqual(argv[0],'/usr/bin/python3.12');self.assertEqual(argv[4],'start')
  self.assertEqual(D.plan(graph,snap,{N.ADAPTER_ID:adapter})['proposed'],[])
 def test_same_registered_schema_accepts_future_fresh_metadata(self):
  self.fixture();self.assertEqual(self.view['out'],str(self.root/'out'))
  with patch.object(N.socket,'gethostname',return_value='k8s-node1'):self.a.reserve_and_start(self.b,self.node,'token')
  self.assertEqual(len(self.calls),1)
 def test_profile_exact_top_level_interface(self):
  self.fixture('profile_named_async_v1');self.assertEqual(self.view['image'],self.p['image_sha256']);self.assertEqual(self.view['host_name'],'k8s-node1')
  self.assertEqual(self.cmd[self.cmd.index(self.p['image_sha256'])+1:][3],self.p['runtime']['path'])
 def test_unknown_host_or_future_schema_is_unsupported(self):
  self.fixture();caps=copy.deepcopy(self.cap);caps[self.b['kind']]={'f'*64:'k8s-node1'}
  with self.assertRaises(ValueError):N.describe(self.b,caps)
  with self.assertRaises(ValueError):N.describe(dict(self.b,kind='future_dev72_2b'),self.cap)
 def test_identity_and_host_environment_reject(self):
  self.fixture()
  for key,value in [('model_sha256','f'*64),('inputs_sha256','f'*64),('protocol','foreign'),('host_name','foreign'),('attempt',True),('host_python','/usr/bin/python3')]:
   with self.subTest(key=key),self.assertRaises(ValueError):N.describe(dict(self.b,**{key:value}),self.cap)
  with self.assertRaises(ValueError):N.describe(dict(self.b,host_environment={'PYTHONDONTWRITEBYTECODE':'1','BASH_ENV':'/tmp/x'}),self.cap)
 def test_foreign_review_and_cpu_command_reject(self):
  self.fixture('profile_named_async_v1');bad=copy.deepcopy(self.review);bad['cpu_commands']['1']=['sh']
  self.b['review']=self.write('REVIEW.json',bad);self.node['action']={'binding':self.write('BINDING.json',self.b),'review':self.b['review']}
  with self.assertRaises(ValueError):self.a.authorize(self.b,bad,self.node,self.gh)
 def test_external_frozen_cannot_dispatch(self):
  self.fixture()
  with self.assertRaises(ValueError):self.a.reserve_and_start(self.b,dict(self.node,managed_by='external_frozen'),'token')
  self.assertEqual(self.calls,[])
 def test_no_effect_without_grant_or_with_existing_attempt(self):
  self.fixture();self.a.grant=None
  with self.assertRaises(ValueError):self.a.reserve_and_start(self.b,self.node,'token')
  self.a.grant=self.grant;self.lifecycle(None)
  with patch.object(N.socket,'gethostname',return_value='k8s-node1'),self.assertRaises(ValueError):self.a.reserve_and_start(self.b,self.node,'token')
  self.assertEqual(self.calls,[])
 def test_absent_after_intent_is_uncertain(self):
  self.fixture();self.assertEqual(self.a.observe(self.node,None),{'state':'absent'});self.assertEqual(self.a.observe(self.node,{'status':'intent'})['state'],'uncertain')
 def test_uncertain_launch_never_resends(self):
  self.fixture()
  def uncertain(*args):self.calls.append('effect');raise TimeoutError()
  self.a.launch=uncertain
  with patch.object(N.socket,'gethostname',return_value='k8s-node1'):
   for _ in range(3):state=D.dispatch_once(self.g,self.snapshot(),{N.ADAPTER_ID:self.a},self.root/'journal')
  self.assertEqual(self.calls,['effect']);self.assertEqual(state['attempts']['fixture']['status'],'uncertain')
 def test_retained_running_exact_generation(self):
  self.fixture();h,a=self.lifecycle(None);self.assertEqual(self.a.observe(self.node,None)['state'],'running');self.actual['Id']='foreign'
  with self.assertRaises(ValueError):self.a.observe(self.node,None)
 def test_release_on_crash_does_not_imply_output(self):
  self.fixture();self.lifecycle(1);o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release']);self.assertEqual(o['failed_facts'],['success'])
 def test_success_without_report_has_no_artifact_or_scientific_fact(self):
  self.fixture();self.lifecycle(0);o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release','success'])
 def test_shard_artifact_never_implies_equivalence(self):
  self.fixture();self.lifecycle(0,True);o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release','success','artifact']);self.assertNotIn('numerical_equivalence',o['facts'])
 def test_profile_artifact_never_implies_coverage(self):
  self.fixture('profile_named_async_v1');self.lifecycle(0,True);o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release','success','artifact']);self.assertNotIn('scientific_admission',o['facts'])
 def test_foreign_terminal_preserves_physical_release(self):
  self.fixture();h,a=self.lifecycle(0);terminal=N.read(a/'EXIT.json');terminal['plan_sha256']='e'*64;(a/'EXIT.json').write_text(json.dumps(terminal));o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release']);self.assertEqual(o['failed_facts'],['success'])
 def test_bad_artifact_does_not_erase_release_success(self):
  self.fixture('profile_named_async_v1');h,a=self.lifecycle(0,True);(a/'FORWARDS.json').write_text('{}');o=self.a.observe(self.node,None);self.assertEqual(o['facts'],['resource_release','success']);self.assertEqual(o['failed_facts'],['artifact'])
 def test_invalid_release_cannot_release(self):
  self.fixture();h,a=self.lifecycle(0);release=N.read(h/'RELEASE.json');release['claim_sha256']='f'*64;(h/'RELEASE.json').write_text(json.dumps(release))
  with self.assertRaises(ValueError):self.a.observe(self.node,None)
 def test_restarted_same_container_cannot_reuse_old_release(self):
  self.fixture();self.lifecycle(0,True)
  for key in ('StartedAt','FinishedAt'):
   original=self.actual['State'][key];self.actual['State'][key]='2026-11-03T23:00:00Z'
   with self.subTest(key=key),self.assertRaises(ValueError):self.a.observe(self.node,None)
   self.actual['State'][key]=original
 def test_empty_or_absent_generation_timestamps_reject(self):
  self.fixture();h,a=self.lifecycle(0);original=N.read(h/'RELEASE.json')
  for key in ('container_started_at','container_finished_at'):
   for value in ('',None,False):
    changed=dict(original,**{key:value});(h/'RELEASE.json').write_text(json.dumps(changed))
    with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.a.observe(self.node,None)
   changed=dict(original);del changed[key];(h/'RELEASE.json').write_text(json.dumps(changed))
   with self.assertRaises(ValueError):self.a.observe(self.node,None)
  (h/'RELEASE.json').write_text(json.dumps(original))
  self.actual['State']['StartedAt']=''
  with self.assertRaises(ValueError):self.a.observe(self.node,None)
 def test_service_600s_explicit_python_and_exact_grant(self):
  self.fixture();c=self.config();cp=self.write('SERVICE.json',c);S.verify(cp['path'],cp['sha256'])
  for key,value in [('interval_seconds',60),('service_python','python3')]:
   bad=dict(c,**{key:value});p=self.write('BAD.json',bad)
   with self.assertRaises(ValueError):S.verify(p['path'],p['sha256'])
  c['mode']='dispatch';p=self.write('BAD.json',c)
  with self.assertRaises(ValueError):S.verify(p['path'],p['sha256'])
  grant={**self.grant,'modules':c['modules'],'host_name':c['host_name'],'allocation':c['allocation'],'output':c['output'],'service_python':c['service_python']};c['activation']=self.write('ACTIVATION.json',grant);p=self.write('DISPATCH.json',c);S.verify(p['path'],p['sha256'])
 def test_dryrun_does_not_write_or_query(self):
  self.fixture();c=self.config();cp=self.write('SERVICE.json',c);r=subprocess.run([sys.executable,'-B','-P',str(ROOT/'experiment_dag_exploration_service_v1.py'),'dry-run','--config',cp['path'],'--sha256',cp['sha256']],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr);out=json.loads(r.stdout);self.assertEqual(out['admission_errors'],{});self.assertFalse(out['launched']);self.assertTrue(out['no_device_query']);self.assertFalse(Path(c['output']).exists())
 def test_arbitrary_command_intent_rejected(self):
  p=self.write('INTENT.json',{'argv':['sh','-c','false']})
  with self.assertRaises(ValueError):N.envelope(p['path'])

if __name__=='__main__':unittest.main()
