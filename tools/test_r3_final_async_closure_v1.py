"""New closure and executable post-release wiring; synthetic artifacts only."""
import ast,hashlib,importlib.util,json,os,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch

def load(name):
 s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=load('r3_final_async_closure_v1');H=load('r3_final_async_handoff_v1');RF=load('test_r3_final_async_release_v1')
SOURCE=Path('/home/xingchao/workspace/nga/.local/preparations/final-closure-20261101-v1')
PIN='7c3588de299f19dba0852257dd9cedb1454f2bb16d7efce6b7ad862a81fbe753'

class Closure(unittest.TestCase):
 def test_actual_source_transform_and_all_files_verify(self):
  before={p:B.C.sha(p) for p in SOURCE.rglob('*.py')}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'closure';result=B.prepare(str(SOURCE),PIN,str(root));B.C.verify(root,result['sha256'])
   for name in B.MODULES:self.assertTrue((root/'r3_code'/(name+'.py')).exists())
   text=(root/'r3_code/r3_final_driver.py').read_text();tree=ast.parse(text)
   funcs={n.name:ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
   self.assertIn('adapter.score_phase',funcs['evaluate_score']);self.assertIn('adapter.consume',funcs['evaluate_cpu']);self.assertNotIn('make_score_fn(',funcs['evaluate_cpu']);self.assertIn("'SCORE-EXIT.json'",funcs['run']);self.assertNotIn("'FINAL_EVAL_EXIT.json'",funcs['run'])
   self.assertIn('verify_scored_test_result',(root/'r3_code/testlock_r3.py').read_text())
   self.assertIn('cpu_execution',(root/'r3_code/r3_final_admission.py').read_text())
  self.assertEqual(before,{p:B.C.sha(p) for p in before})
 def test_generated_supervisor_executes_release_before_dispatch(self):
  text=B.supervisor(Path('tools/r3_final_supervisor.py').read_text());tree=ast.parse(text)
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='supervise')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);out=root/'out';d=out/'supervisor-attempts/1';d.mkdir(parents=True);a=out/'final-attempts/1';a.mkdir(parents=True)
   plan={'out':str(out),'closure':{'root':str(root)},'image':'img','chip':3,'model_sha256':'a'*64,'final':{'sha256':'c'*64}};path=root/'plan.json';path.write_text(json.dumps(plan));pin='b'*64;review={'path':'review','sha256':'d'*64};spec={'name':'fake'};cmd=['fake'];actual={'Id':'id','State':{'Status':'exited','ExitCode':0}}
   for name,value in [('LAUNCH_INTENT.json',{'plan_sha256':pin,'review':review,'attempt':1,'command':cmd}),('CLAIM.json',{}),('LAUNCH_RECEIPT.json',{'id':'id'})]: (d/name).write_text(json.dumps(value))
   (a/'SCORE-EXIT.json').write_text(json.dumps({'exit_code':0}));events=[]
   def require(ok,why):
    if not ok:raise ValueError(why)
   class Releaser:
    docker_inspect=staticmethod(lambda name:actual)
    def release(self,args):events.append('release')
   def dispatch(*args):
    require(events==['release'],'CPU before release');events.append('dispatch');return {'state':'cpu_dispatched'}
   env={'__file__':str(root/'r3_code/r3_final_supervisor.py'),'Path':Path,'json':json,'os':os,'fcntl':__import__('fcntl'),'time':__import__('time'),'socket':types.SimpleNamespace(gethostname=lambda:'k8s-node1'),
    'A':types.SimpleNamespace(require=require,C=types.SimpleNamespace(safe=Path),verify=lambda *a:None),
    'K':types.SimpleNamespace(contract=lambda *a:spec,command=lambda s:cmd,verify_observation=lambda s,o,c:o),
    'R':Releaser(),'D':types.SimpleNamespace(atomic=lambda p,v:p.write_text(json.dumps(v)),utc=lambda:'now'),
    'V':types.SimpleNamespace(G=types.SimpleNamespace(digest=lambda d:'e'*64),X=types.SimpleNamespace(load_scored=lambda *a:{}),reconcile_score_exit=lambda *a,**kw:{'exit_code':0,'publication_complete':False}),
    'H':types.SimpleNamespace(start_cpu=dispatch),'resource_args':lambda *a:None,
    'subprocess':types.SimpleNamespace(STDOUT=-2,check_output=lambda *a,**kw:'img',run=lambda *a,**kw:None)}
   exec(compile(ast.Module(body=[fn],type_ignores=[]),'generated-supervisor','exec'),env)
   env['supervise'](path,pin,review,1);self.assertEqual(events,['release','dispatch'])

class CPUEntry(unittest.TestCase):
 def test_generated_cpu_entry_never_constructs_scorer(self):
  text=B.driver(Path('tools/r3_final_driver.py').read_text());fn=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_cpu')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);out=root/'out';out.mkdir();(out/'TEST-PRODUCER-REPORT.json').write_text('{}')
   plan={'closure':{'root':str(root),'sha256':'a'*64},'dataset_manifest':{'path':str(root/'data/manifest.json')},'arm':'K0','model':'model','out':str(out),'round_dir':str(root/'round'),'adapter':None,'model_sha256':'b'*64,'final':{'sha256':'c'*64}}
   events=[]
   def require(ok,why):
    if not ok:raise ValueError(why)
   evaluator=types.SimpleNamespace(C=types.SimpleNamespace(KEV_DIR=root/'data'),P=object(),parse_full_args=lambda x:types.SimpleNamespace())
   admission=types.SimpleNamespace(verify=lambda *a:events.append('admission'))
   scorer=types.SimpleNamespace(__file__=str(root/'r3_code/eval_r3.py'),make_score_fn=lambda *a:(_ for _ in ()).throw(AssertionError('CPU constructed scorer')))
   handoff=types.SimpleNamespace(verify_release=lambda *a:events.append('release'))
   def consume(args,evaluator,**kw):
    kw['validate_release'](kw['owner'],'d'*64);events.append('cpu_verify');kw['validate_publication']();return {'state':'completed'}
   adapter=types.SimpleNamespace(consume=consume)
   env={'__file__':str(root/'r3_code/r3_final_driver.py'),'Path':Path,'json':json,'C':types.SimpleNamespace(safe=Path,verify=lambda *a,**kw:None,require=require),'local':lambda name:{'r3_final_async_adapter_v1':adapter,'r3_final_async_handoff_v1':handoff}[name],
    'export_vector':lambda *a,**kw:events.append('export'),'export_reference_metrics':lambda *a:None}
   with patch.dict(__import__('sys').modules,{'r3_final_admission':admission,'full_eval_r3':evaluator,'eval_r3':scorer}):
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'generated-cpu','exec'),env)
    self.assertEqual(env['evaluate_cpu'](plan,'e'*64,{},root/'plan.json',1)['state'],'completed')
   self.assertLess(events.index('release'),events.index('cpu_verify'));self.assertIn('export',events)

class RealReleaseDispatch(RF.Release):
 def test_dispatch_rejects_missing_actual_release_without_popen(self):
  self.plan['cpu_execution']={'python':str(Path(__import__('sys').executable).resolve()),'environment':{'PYTHONDONTWRITEBYTECODE':'1','TORCH_DEVICE_BACKEND_AUTOLOAD':'0'}}
  (self.d/'RELEASE.json').unlink()
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',side_effect=FileNotFoundError('release absent')),patch.object(H.subprocess,'Popen') as popen:
   with self.assertRaises(FileNotFoundError):H.start_cpu(self.plan,'/plan',self.pin,{},1)
   popen.assert_not_called()
 def test_durable_intent_suppresses_duplicate_dispatch(self):
  self.plan['cpu_execution']={'python':str(Path(__import__('sys').executable).resolve()),'environment':{'PYTHONDONTWRITEBYTECODE':'1','TORCH_DEVICE_BACKEND_AUTOLOAD':'0'}}
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',return_value={'state':'actual_exit_and_release_verified'}),patch.object(H.subprocess,'Popen',return_value=types.SimpleNamespace(pid=os.getpid())) as popen:
   self.assertEqual(H.start_cpu(self.plan,'/plan',self.pin,{'path':'x','sha256':'a'*64},1)['state'],'cpu_dispatched')
   self.assertEqual(H.start_cpu(self.plan,'/plan',self.pin,{'path':'x','sha256':'a'*64},1)['state'],'already_dispatched_or_uncertain');popen.assert_called_once()
 def test_unknown_dispatch_never_retries(self):
  self.plan['cpu_execution']={'python':str(Path(__import__('sys').executable).resolve()),'environment':{'PYTHONDONTWRITEBYTECODE':'1','TORCH_DEVICE_BACKEND_AUTOLOAD':'0'}}
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',return_value={}),patch.object(H.subprocess,'Popen',side_effect=OSError('unknown launch')) as popen:
   with self.assertRaises(OSError):H.start_cpu(self.plan,'/plan',self.pin,{'path':'x','sha256':'a'*64},1)
   self.assertEqual(H.start_cpu(self.plan,'/plan',self.pin,{'path':'x','sha256':'a'*64},1)['state'],'already_dispatched_or_uncertain');popen.assert_called_once()

class LifecycleRepair(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.out=self.base/'out';self.root=self.out/'cpu-final-attempts/1';self.root.mkdir(parents=True)
  self.pin='a'*64;self.review={'path':'/review','sha256':'b'*64};self.plan={'out':str(self.out),'closure':{'root':str(self.base/'closure')},'cpu_execution':{'python':str(Path(__import__('sys').executable).resolve()),'environment':{'PYTHONDONTWRITEBYTECODE':'1','TORCH_DEVICE_BACKEND_AUTOLOAD':'0'}}}
  self.path=self.base/'plan.json';self.path.write_text(json.dumps(self.plan))
  self.intent={'plan_sha256':self.pin,'attempt':1,'review':self.review,'command':H.cpu_command(self.plan,self.path,self.pin,self.review,1),'environment':self.plan['cpu_execution']['environment'],'automatic_retry':False}
  self.put('START-INTENT.json',self.intent)
  prior=self.out/'supervisor-attempts/1';prior.mkdir(parents=True);(prior/'DONE.json').write_text(json.dumps({'exit_code':0,'publication_complete':False}))
 def put(self,name,data):(self.root/name).write_text(json.dumps(data))
 def terminal(self,code=1):self.put('EXIT.json',{'exit_code':code,'publication_complete':code==0,'plan_sha256':self.pin,'attempt':1})
 def process(self,gone=False):
  r=H.process_generation(os.getpid());r.update(plan_sha256=self.pin,attempt=1)
  if gone:r['start_ticks']-=1
  self.put('CONSUMER.json',r)
 def test_owned_bad_intent_writes_terminal(self):
  self.intent['command']=['wrong'];self.put('START-INTENT.json',self.intent)
  with patch.object(H.A,'identity',return_value=self.pin):self.assertEqual(H.consume(self.path,self.pin,self.review,1),1)
  d=json.loads((self.root/'EXIT.json').read_text());self.assertEqual(d['state'],'preflight_rejected');self.assertEqual(d['exit_code'],1)
 def test_wrong_closure_writes_terminal(self):
  with patch.object(H.A,'identity',return_value=self.pin):self.assertEqual(H.consume(self.path,self.pin,self.review,1),1)
  self.assertEqual(json.loads((self.root/'EXIT.json').read_text())['state'],'preflight_rejected')
 def test_foreign_intent_does_not_write_terminal(self):
  self.intent['plan_sha256']='c'*64;self.put('START-INTENT.json',self.intent)
  with patch.object(H.A,'identity',return_value=self.pin):
   with self.assertRaises(ValueError):H.consume(self.path,self.pin,self.review,1)
  self.assertFalse((self.root/'EXIT.json').exists())
 def test_existing_terminal_not_overwritten(self):
  self.terminal(0);before=(self.root/'EXIT.json').read_bytes()
  with patch.object(H.A,'identity',return_value=self.pin):
   with self.assertRaises(ValueError):H.consume(self.path,self.pin,self.review,1)
  self.assertEqual(before,(self.root/'EXIT.json').read_bytes())
 def test_locked_consumer_does_not_write(self):
  fd=H.acquire(self.root,'consumer.lock')
  try:
   with patch.object(H.A,'identity',return_value=self.pin):
    with self.assertRaises(BlockingIOError):H.consume(self.path,self.pin,self.review,1)
   self.assertFalse((self.root/'EXIT.json').exists())
  finally:os.close(fd)
 def test_unknown_prior_dispatch_rejected(self):
  with self.assertRaisesRegex(ValueError,'unresolved'):H.reconcile_prior_cpu(self.plan,self.pin,2)
 def test_failed_terminal_with_live_process_rejected(self):
  self.terminal();self.process()
  with self.assertRaisesRegex(ValueError,'still live'):H.reconcile_prior_cpu(self.plan,self.pin,2)
 def test_terminal_without_process_rejected(self):
  self.terminal()
  with self.assertRaisesRegex(ValueError,'generation'):H.reconcile_prior_cpu(self.plan,self.pin,2)
 def test_completed_publication_rejected(self):
  self.terminal(0);self.process(True)
  with self.assertRaisesRegex(ValueError,'completed'):H.reconcile_prior_cpu(self.plan,self.pin,2)
 def test_exited_failed_consumer_fenced(self):
  self.terminal();self.process(True);H.reconcile_prior_cpu(self.plan,self.pin,2)
  self.assertTrue((self.root/'FENCED.json').exists())
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',return_value={}):
   with self.assertRaisesRegex(ValueError,'fenced'):H.start_cpu(self.plan,self.path,self.pin,self.review,1)
 def test_launch_failure_is_durable_uncertainty_not_exit(self):
  (self.root/'START-INTENT.json').unlink()
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',return_value={}),patch.object(H.subprocess,'Popen',side_effect=OSError('spawn')):
   with self.assertRaises(OSError):H.start_cpu(self.plan,self.path,self.pin,self.review,1)
  self.assertEqual(json.loads((self.root/'LAUNCH-ERROR.json').read_text())['state'],'launch_uncertain');self.assertFalse((self.root/'EXIT.json').exists())
 def test_service_write_failure_must_not_mark_live_child_exited(self):
  (self.root/'START-INTENT.json').unlink();original=H.D.atomic
  def fail(path,data):
   if Path(path).name=='SERVICE.json':raise OSError('service write')
   return original(path,data)
  with patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',return_value={}),patch.object(H.subprocess,'Popen',return_value=types.SimpleNamespace(pid=os.getpid())),patch.object(H.D,'atomic',side_effect=fail):
   with self.assertRaises(OSError):H.start_cpu(self.plan,self.path,self.pin,self.review,1)
  self.assertFalse((self.root/'EXIT.json').exists());self.assertTrue((self.root/'LAUNCH-ERROR.json').exists())
 def test_successful_owned_consumer_publishes_then_blocks_restart(self):
  filename=str(Path(self.plan['closure']['root'])/'r3_code/r3_final_async_handoff_v1.py')
  events=[]
  with patch.object(H,'__file__',filename),patch.object(H.A,'identity',return_value=self.pin),patch.object(H.A,'verify',return_value={}),patch.object(H,'verify_release',side_effect=lambda *a:events.append('release')),patch.object(H.D,'evaluate_cpu',create=True,side_effect=lambda *a:(events.append('consume') or {'state':'completed'})):
   self.intent['command']=H.cpu_command(self.plan,self.path,self.pin,self.review,1);self.put('START-INTENT.json',self.intent)
   self.assertEqual(H.consume(self.path,self.pin,self.review,1),0)
  self.assertEqual(events,['release','consume']);self.assertTrue((self.root/'heartbeat.json').exists())
  self.assertTrue(json.loads((self.root/'EXIT.json').read_text())['publication_complete'])
  with self.assertRaisesRegex(ValueError,'completed'):H.reconcile_prior_cpu(self.plan,self.pin,2)
 def test_post_preflight_failure_is_terminal(self):
  filename=str(Path(self.plan['closure']['root'])/'r3_code/r3_final_async_handoff_v1.py')
  with patch.object(H,'__file__',filename),patch.object(H.A,'identity',return_value=self.pin),patch.object(H.A,'verify',side_effect=ValueError('admission changed')):
   self.intent['command']=H.cpu_command(self.plan,self.path,self.pin,self.review,1);self.put('START-INTENT.json',self.intent)
   self.assertEqual(H.consume(self.path,self.pin,self.review,1),1)
  self.assertEqual(json.loads((self.root/'EXIT.json').read_text())['state'],'verification_failed')
 def test_generated_restart_gate_precedes_claim(self):
  text=B.supervisor(Path('tools/r3_final_supervisor.py').read_text())
  self.assertLess(text.index('H.reconcile_prior_cpu(plan,pin,attempt)'),text.index('R.claim(resource_args'))

if __name__=='__main__':unittest.main()
