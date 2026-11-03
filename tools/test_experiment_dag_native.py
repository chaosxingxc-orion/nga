import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent

def mod(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
N=mod('experiment_dag_native');S=mod('experiment_dag_native_service');D=mod('experiment_dag')

class NativeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.r=Path(self.temp.name)
  host=self.r/'host.py';host.write_text("def command(d,path,pin,a):\n return ['docker','run','-d','--name',d['container']+'-a'+str(a),d['image_sha256'],'python3','-B','-P',d['runtime']['path'],'run','--plan',path,'--sha256',pin,'--attempt',str(a)]\n")
  runtime=self.r/'runtime.py';runtime.write_text('# immutable fixture runtime\n');cfg=self.put('CONFIG.json',{})
  self.plan={'schema':'native-panel-execution-v2','scientific_acceptance':False,'candidate_test_authority':False,'candidate_selection_allowed':False,'chip':0,'run':'run','scope':'public_fixed_base_test','test_read':True,'config':cfg,'modules':{'host':N.ref(host),'runtime':N.ref(runtime),'resource':N.ref(runtime)},'files':{str(host):N.sha(host),str(runtime):N.sha(runtime),cfg['path']:cfg['sha256']},'model_sha256':'a'*64,'population':{'ordered_inputs_sha256':'b'*64},'protocol':{'id':'native-full-label-panel-v2'},'host_python':str(Path(sys.executable).resolve()),'host_environment':{'PYTHONDONTWRITEBYTECODE':'1'},'host_name':socket.gethostname(),'out':str(self.r/'out'),'allocation':str(self.r/'alloc.json'),'container':'native_fixture','image':'sha256:'+'c'*64}
  self.pp=self.put('PLAN.json',self.plan);self.cap={'native_panel_v2':[N.sha(host)],'native_long_dev_v1':[N.sha(host)]}
  self.binding={'schema':'nga-native-dag-binding-v1','node_id':'x','kind':'native_panel_v2','plan':self.pp,'review':{'path':str(self.r/'REVIEW.json'),'sha256':'0'*64},'attempt':1,'model_sha256':'a'*64,'inputs_sha256':'b'*64,'protocol':'native-full-label-panel-v2','host_python':str(Path(sys.executable).resolve()),'host_environment':{'PYTHONDONTWRITEBYTECODE':'1'}}
  d,cmd,argv,split=N.describe(self.binding,self.cap);self.cmd=cmd
  review={'verdict':'PASS','activation_authorized':True,'scientific_acceptance':False,'candidate_test_authority':False,'approved_plan_sha256':self.pp['sha256'],'attempts':[1],'test_read':True,'expected_commands':{'1':cmd},'hashes':self.plan['files']}
  self.binding['review']=self.put('REVIEW.json',review);self.bp=self.put('BINDING.json',self.binding);self.review=review
  self.node={'id':'x','lane':'npu','devices':[0],'priority':1,'purpose':'fixture','split':'TEST','protocol':self.binding['protocol'],'sources':[self.pp],'adapter':'native_guarded_v1','stage':'planned','managed_by':'dag','depends_on':[],'action':{'binding':self.bp,'review':self.binding['review']},'missing':[]}
  self.g={'schema':'nga-experiment-dag-v1','id':'fixture','policy':{'poll_seconds':600,'cpu_slots':1,'target_ready_depth':2,'target_reserve_depth':3,'ordering':'priority_then_id'},'adapters':{'native_guarded_v1':{'version':1,'implementation':N.ref(N.__file__),'integration':'reviewed_dispatch'}},'nodes':[self.node]}
  self.gh=D.digest(self.g);self.actual=None;self.calls=[];self.grant={'schema':'nga-native-dag-activation-v1','verdict':'PASS','activation_authorized':True,'scientific_acceptance':False,'graph_sha256':self.gh,'bindings':{'x':self.node['action']},'capabilities':self.cap}
  self.adapter=N.NativeAdapter(self.cap,self.r/'service',query=lambda name:self.actual,launch=lambda a,e,t:self.calls.append(a) or {'pid':1},grant=self.grant)
 def put(self,name,d):
  p=self.r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));return N.ref(p)
 def auth(self):return self.adapter.authorize(self.binding,self.review,self.node,self.gh)
 def launched(self,rc=None):
  h=Path(self.plan['out'])/'host_attempts/1';h.mkdir(parents=True);a=Path(self.plan['out'])/'attempts/1';a.mkdir(parents=True)
  cid='d'*64;cmd=self.cmd[self.cmd.index(self.plan['image'])+1:]
  self.actual={'Id':cid,'Image':self.plan['image'],'HostConfig':{'AutoRemove':False,'Privileged':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x} for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci0')]},'Config':{'Cmd':cmd},'State':{'Status':'running' if rc is None else 'exited','Running':rc is None,'ExitCode':0 if rc is None else rc}}
  def put(p,d):p.write_text(json.dumps(d))
  put(h/'LAUNCH_RECEIPT.json',{'container_id':cid,'plan_sha256':self.pp['sha256'],'attempt':1,'scientific_acceptance':False,'command':cmd})
  put(h/'LAUNCH_SPEC.json',{'command':self.cmd})
  put(h/'CLAIM.json',{'schema':'r3-resource-claim-v1','run':'run','chip':0,'allocation':self.plan['allocation']})
  if rc is not None:
   put(h/'RELEASE.json',{'schema':'r3-resource-release-v1','run':'run','chip':0,'claim_sha256':N.sha(h/'CLAIM.json'),'container_id':cid,'container':'native_fixture-a1','exit_code':rc,'scientific_acceptance':False})
   term={'plan_sha256':self.pp['sha256'],'attempt':1,'exit_code':rc,'scientific_acceptance':False,'test_read':True}
   put(a/'EXIT.json',term);put(h/'EXIT.json',dict(term,container_id=cid,container_exit_code=rc,runner_terminal_matches=True))
  return h,a
 def test_valid_command_is_fixed_guarded_host(self):
  self.assertTrue(self.auth());_,cmd,argv,_=N.describe(self.binding,self.cap);self.assertEqual(argv[3],self.plan['modules']['host']['path']);self.assertEqual(argv[4],'start');self.assertEqual(cmd,self.cmd)
 def test_changed_plan_and_unknown_host_reject(self):
  for change in ('plan','host'):
   b=copy.deepcopy(self.binding);caps=copy.deepcopy(self.cap)
   if change=='plan':b['plan']['sha256']='e'*64
   else:caps['native_panel_v2']=['e'*64]
   with self.assertRaises(ValueError):N.describe(b,caps)
 def test_model_input_protocol_chip_and_attempt_alias_reject(self):
  for key in ('model_sha256','inputs_sha256','protocol'):
   b=dict(self.binding,**{key:'wrong'})
   with self.assertRaises(ValueError):self.adapter.authorize(b,self.review,self.node,self.gh)
  with self.assertRaises(ValueError):self.adapter.authorize(dict(self.binding,attempt=True),self.review,self.node,self.gh)
  with self.assertRaises(ValueError):self.adapter.authorize(self.binding,self.review,dict(self.node,devices=[1]),self.gh)
 def test_science_and_foreign_review_reject(self):
  for r in (dict(self.review,scientific_acceptance=True),dict(self.review,approved_plan_sha256='f'*64),dict(self.review,attempts=[True])):
   with self.assertRaises(ValueError):self.adapter.authorize(self.binding,r,self.node,self.gh)
 def test_unsupported_environment_rejects(self):
  with self.assertRaises(ValueError):N.environment({'PYTHONDONTWRITEBYTECODE':'1','BASH_ENV':'/tmp/x'})
  with self.assertRaises(ValueError):N.environment({'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'.'})
 def test_external_owner_never_starts(self):
  self.auth()
  with self.assertRaises(ValueError):self.adapter.reserve_and_start(self.binding,dict(self.node,managed_by='external_frozen'),'token')
  self.assertFalse(self.calls)
 def test_existing_attempt_and_missing_grant_reject(self):
  self.auth();self.adapter.grant=None
  with self.assertRaises(ValueError):self.adapter.reserve_and_start(self.binding,self.node,'token')
  self.adapter.grant=self.grant;self.launched()
  with self.assertRaises(ValueError):self.adapter.reserve_and_start(self.binding,self.node,'token')
  self.assertFalse(self.calls)
 def test_admitted_fixed_command_reaches_injected_effect_only_once(self):
  self.auth();self.adapter.reserve_and_start(self.binding,self.node,'token');self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0][4],'start')
 def test_absent_after_intent_uncertain(self):
  self.auth();self.assertEqual(self.adapter.observe(self.node,None),{'state':'absent'});self.assertEqual(self.adapter.observe(self.node,{'status':'intent'})['state'],'uncertain')
 def test_running_receipt_exact_and_foreign_runtime_reject(self):
  self.auth();self.launched();self.assertEqual(self.adapter.observe(self.node,None)['state'],'running');self.actual['Id']='bad'
  with self.assertRaises(ValueError):self.adapter.observe(self.node,None)
 def test_full_release_required_and_success_never_science(self):
  self.plan['run']='run';self.pp=self.put('PLAN.json',self.plan);self.binding['plan']=self.pp;self.set_review();self.auth();h,a=self.launched(0)
  o=self.adapter.observe(self.node,None);self.assertEqual(o['facts'],['resource_release','success']);self.assertNotIn('scientific_admission',o['facts']);(h/'RELEASE.json').unlink();self.assertEqual(self.adapter.observe(self.node,None)['state'],'uncertain')
 def set_review(self):
  self.review['approved_plan_sha256']=self.pp['sha256'];_,self.cmd,_,_=N.describe(self.binding,self.cap);self.review['expected_commands']['1']=self.cmd;self.binding['review']=self.put('REVIEW.json',self.review);self.node['action']['review']=self.binding['review'];self.node['action']['binding']=self.put('BINDING.json',self.binding)
 def test_failed_but_released_is_not_success(self):
  self.plan['run']='run';self.pp=self.put('PLAN.json',self.plan);self.binding['plan']=self.pp;self.set_review();self.auth();self.launched(1);o=self.adapter.observe(self.node,None);self.assertEqual(o['state'],'failed');self.assertEqual(o['facts'],['resource_release']);self.assertEqual(o['failed_facts'],['success'])
 def test_arbitrary_argv_intent_cannot_execute(self):
  p=self.r/'INTENT.json';p.write_text(json.dumps({'argv':['sh','-c','touch /tmp/unwanted']}))
  with self.assertRaises(ValueError):N.envelope(str(p))
 def test_real_service_plan_refuses_activation_and_cpu_nodes(self):
  alloc=self.r/'alloc.json';alloc.write_text(json.dumps({'allocation':[],'free':[{'chip':0}]}))
  self.node['managed_by']='external_frozen';gp=self.put('GRAPH.json',self.g)
  c={'schema':'nga-native-dag-service-v1','host_name':socket.gethostname(),'output':str(self.r/'service'),'graph':gp,'allocation':str(alloc),'modules':{'dag':N.ref(D.__file__),'native':N.ref(N.__file__),'service':N.ref(S.__file__)},'capabilities':self.cap,'mode':'plan','activation':None,'interval_seconds':600}
  cp=self.put('SERVICE-CONFIG.json',c);S.verify(cp['path'],cp['sha256'])
  c['mode']='dispatch';cp=self.put('SERVICE-CONFIG.json',c)
  with self.assertRaises(ValueError):S.verify(cp['path'],cp['sha256'])
  self.g['nodes'][0]['lane']='cpu';self.g['nodes'][0]['devices']=[];c['graph']=self.put('GRAPH.json',self.g);c['mode']='plan';cp=self.put('SERVICE-CONFIG.json',c)
  with self.assertRaises(ValueError):S.verify(cp['path'],cp['sha256'])

 def service(self):
  alloc=self.r/'alloc.json';alloc.write_text(json.dumps({'allocation':[],'free':[{'chip':0}]}))
  c={'schema':'nga-native-dag-service-v1','host_name':socket.gethostname(),'output':str(self.r/'service'),'graph':self.put('GRAPH.json',self.g),'allocation':str(alloc),'modules':{'dag':N.ref(D.__file__),'native':N.ref(N.__file__),'service':N.ref(S.__file__)},'capabilities':self.cap,'mode':'plan','activation':None,'interval_seconds':600}
  return c
 def test_source_mutation_rejected_by_core_admission(self):
  self.assertEqual(D.authorized_action(self.g,self.node,{'native_guarded_v1':self.adapter})[1],self.binding)
  Path(self.plan['modules']['runtime']['path']).write_text('# changed')
  with self.assertRaises(ValueError):D.authorized_action(self.g,self.node,{'native_guarded_v1':self.adapter})
 def test_binding_substitution_rejected(self):
  b=dict(self.binding,node_id='y')
  with self.assertRaises(ValueError):self.adapter.authorize(b,self.review,self.node,self.gh)
  self.auth()
  with self.assertRaises(ValueError):self.adapter.reserve_and_start(dict(self.binding,attempt=2),self.node,'token')
  self.assertFalse(self.calls)
 def test_device_substitution_and_claim_tampering_rejected(self):
  self.auth();h,a=self.launched();self.actual['HostConfig']['Devices'][-1]['PathOnHost']='/dev/davinci1'
  with self.assertRaises(ValueError):self.adapter.observe(self.node,None)
  self.actual['HostConfig']['Devices'][-1]['PathOnHost']='/dev/davinci0';c=N.read(h/'CLAIM.json');c['run']='foreign';(h/'CLAIM.json').write_text(json.dumps(c))
  with self.assertRaises(ValueError):self.adapter.observe(self.node,None)
 def test_release_generation_and_boolean_exit_rejected(self):
  self.auth();h,a=self.launched(0);rel=N.read(h/'RELEASE.json');rel['claim_sha256']='0'*64;(h/'RELEASE.json').write_text(json.dumps(rel))
  with self.assertRaises(ValueError):self.adapter.observe(self.node,None)
  rel['claim_sha256']=N.sha(h/'CLAIM.json');rel['exit_code']=False;(h/'RELEASE.json').write_text(json.dumps(rel))
  with self.assertRaises(ValueError):self.adapter.observe(self.node,None)
 def test_service_dryrun_has_no_side_effects(self):
  c=self.service();cp=self.put('SERVICE-CONFIG.json',c)
  result=subprocess.run([sys.executable,'-B',S.__file__,'dry-run','--config',cp['path'],'--sha256',cp['sha256']],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);out=json.loads(result.stdout)
  self.assertEqual(out['admission_errors'],{});self.assertFalse(out['launched']);self.assertTrue(out['no_device_query']);self.assertEqual(list(out['commands']),['x']);self.assertFalse(Path(c['output']).exists())
 def test_service_dispatch_requires_exact_graph_and_modules(self):
  c=self.service();grant=dict(self.grant,modules=c['modules'],host_name=c['host_name'],allocation=c['allocation'],output=c['output'])
  c['mode']='dispatch';c['activation']=self.put('ACTIVATION.json',grant);cp=self.put('SERVICE-CONFIG.json',c);S.verify(cp['path'],cp['sha256'])
  grant['graph_sha256']='0'*64;c['activation']=self.put('ACTIVATION.json',grant);cp=self.put('SERVICE-CONFIG.json',c)
  with self.assertRaises(ValueError):S.verify(cp['path'],cp['sha256'])
 def test_service_foreign_host_and_short_poll_refused(self):
  c=self.service();cp=self.put('SERVICE-CONFIG.json',c);v=S.verify(cp['path'],cp['sha256'])
  with patch.object(S.socket,'gethostname',return_value='foreign'):
   with self.assertRaises(ValueError):S.once(*v)
  c['interval_seconds']=60;cp=self.put('SERVICE-CONFIG.json',c)
  with self.assertRaises(ValueError):S.verify(cp['path'],cp['sha256'])
 def test_external_observation_error_holds_device(self):
  self.node['managed_by']='external_frozen';self.auth();self.adapter.query=lambda name:(_ for _ in ()).throw(RuntimeError('unavailable'))
  c=self.service();snap,errors=S.make_snapshot(c,self.g,D,N,self.adapter)
  self.assertEqual(snap['observations']['x']['state'],'uncertain');self.assertIn('x',errors);self.assertEqual(D.plan(self.g,snap,{'native_guarded_v1':self.adapter})['proposed'],[])
 def test_plan_once_cannot_dispatch_and_logs_heartbeat(self):
  c=self.service();cp=self.put('SERVICE-CONFIG.json',c);v=S.verify(cp['path'],cp['sha256'])
  with patch.object(v[3],'inspect',return_value=None):
   # A substitute adapter removes hardware access; production uses its fixed query.
   with patch.object(v[3],'NativeAdapter',return_value=self.adapter):
    S.once(*v,False)
    with self.assertRaises(ValueError):S.once(*v,True)
  self.assertTrue((Path(c['output'])/'heartbeat.json').exists());self.assertFalse(self.calls)

 def test_managed_observation_error_holds_only_its_chip(self):
  self.auth();self.adapter.query=lambda name:(_ for _ in ()).throw(RuntimeError('unavailable'));c=self.service()
  snap,errors=S.make_snapshot(c,self.g,D,N,self.adapter)
  self.assertEqual(snap['observations']['x']['state'],'uncertain');self.assertEqual(D.plan(self.g,snap,{'native_guarded_v1':self.adapter})['proposed'],[])
 def test_restart_identity_checks_and_preserves_journal(self):
  out=self.r/'service';out.mkdir();old=dict(S.identity(__import__('os').getpid()),config_sha256='a'*64);(out/'SERVICE.json').write_text(json.dumps(old))
  with self.assertRaises(ValueError):S.pinned_service_identity(out,'a'*64)
  with self.assertRaises(ValueError):S.pinned_service_identity(out,'b'*64)
  old['start_ticks']-=1;(out/'SERVICE.json').write_text(json.dumps(old));self.assertEqual(S.pinned_service_identity(out,'a'*64),old)

 def test_crash_release_unblocks_resource_without_success(self):
  self.auth();h,a=self.launched(1);(a/'EXIT.json').unlink();o=self.adapter.observe(self.node,None)
  self.assertEqual(o['facts'],['resource_release']);self.assertEqual(o['failed_facts'],['success'])
 def test_mismatched_runtime_success_keeps_release(self):
  self.auth();h,a=self.launched(0);term=N.read(h/'EXIT.json');term['runner_terminal_matches']=False;term['exit_code']=1;(h/'EXIT.json').write_text(json.dumps(term));o=self.adapter.observe(self.node,None)
  self.assertEqual(o['facts'],['resource_release']);self.assertEqual(o['failed_facts'],['success']);self.assertNotIn('scientific_admission',o['facts'])

if __name__=='__main__':unittest.main()
