import ast,hashlib,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from tools import bev_successor_prepare_queue_v4 as Q

class Events(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.out=self.root/'out';self.cfg=self.root/'config.json'
  self.config=dict(schema='bev-successor-prepare-queue-v3',poll_seconds=600,workers=1,npu_launch_allowed=False,scientific_acceptance=False,files={},jobs=[dict(id='x',output_root=str(self.root/'new'),predecessor_root=str(self.root/'old'),base_config=str(self.cfg),decision=str(self.cfg))],output=str(self.out),allocation=str(self.root/'allocation.json'))
  # No release exists, so these pinned dummy inputs are never imported.
  dummy=self.root/'dummy';dummy.write_text('{}');self.config['files']={str(dummy):Q.sha(dummy)};self.config['jobs'][0].update(base_config=str(dummy),decision=str(dummy));self.cfg.write_text(json.dumps(self.config));self.pin=Q.sha(self.cfg)
 def start(self,script=None):
  cmd=[sys.executable,'-B','-P',str(Path(Q.__file__).resolve()),'--config',str(self.cfg),'--sha256',self.pin] if script is None else [sys.executable,'-B','-P','-c',script,str(self.cfg),self.pin,str(Path(Q.__file__).resolve())]
  p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.addCleanup(self.clean,p);return p
 def clean(self,p):
  if p.poll() is None:p.kill()
  p.communicate(timeout=5)
 def wait_file(self,p,timeout=5):
  deadline=time.monotonic()+timeout
  while not p.exists():
   if time.monotonic()>deadline:self.fail('missing '+str(p))
   time.sleep(.01)
 def test_wake_consumes_new_review_request_before_600s(self):
  p=self.start();self.wait_file(self.out/'digest.json');first=Q.read(self.out/'digest.json')['utc_seconds'];node=self.out/'x';node.mkdir();(node/'REVIEW-REQUEST.json').write_text('{}');os.kill(p.pid,signal.SIGUSR1);p.wait(timeout=5)
  self.assertEqual(p.returncode,0);self.assertGreater(Q.read(self.out/'digest.json')['utc_seconds'],first);self.assertEqual(Q.read(self.out/'QUEUE-EXIT.json')['reason'],'prepared')
 def test_signal_stop_writes_nonzero_controller_terminal(self):
  p=self.start();self.wait_file(self.out/'digest.json');os.kill(p.pid,signal.SIGTERM);p.wait(timeout=5);self.assertEqual(p.returncode,143);e=Q.read(self.out/'QUEUE-EXIT.json');self.assertEqual(e['exit_code'],143);self.assertFalse(e['npu_launched'])
 def test_competing_controller_cannot_replace_service(self):
  p=self.start();self.wait_file(self.out/'digest.json');before=(self.out/'SERVICE.json').read_bytes();other=self.start();other.wait(timeout=5);self.assertNotEqual(other.returncode,0);self.assertEqual(before,(self.out/'SERVICE.json').read_bytes());self.assertFalse((self.out/'QUEUE-EXIT.json').exists())
 def test_config_mutation_on_event_fails(self):
  p=self.start();self.wait_file(self.out/'digest.json');self.cfg.write_text(self.cfg.read_text()+' ');os.kill(p.pid,signal.SIGUSR1);p.wait(timeout=5);self.assertNotEqual(p.returncode,0);self.assertEqual(Q.read(self.out/'QUEUE-EXIT.json')['exit_code'],1)
 def test_wake_during_pass_is_not_lost(self):
  script="""import importlib.util,sys,time
from pathlib import Path
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
count=0
def once(c):
 global count
 count+=1
 p=Path(c['output'])/('pass'+str(count));p.write_text(str(time.monotonic()))
 if count==1:time.sleep(.4)
 return [dict(state='prepared_pending_review' if count==2 else 'waiting_exact_release')]
q.once=once
sys.exit(q.run(sys.argv[1],sys.argv[2]))
"""
  p=self.start(script);self.wait_file(self.out/'pass1');os.kill(p.pid,signal.SIGUSR1);p.wait(timeout=5);self.assertEqual(p.returncode,0);self.assertLess(float((self.out/'pass2').read_text())-float((self.out/'pass1').read_text()),3)
 def test_stop_during_owned_work_waits_for_completion(self):
  script="""import importlib.util,sys,subprocess
from pathlib import Path
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
def once(c):
 out=Path(c['output']);child=subprocess.Popen([sys.executable,'-c',"import time,sys;time.sleep(.5);open(sys.argv[1],'w').write('done')",str(out/'child_done')],start_new_session=True)
 (out/'child_started').write_text(str(child.pid));child.wait()
 return [dict(state='waiting_exact_release')]
q.once=once
sys.exit(q.run(sys.argv[1],sys.argv[2]))
"""
  p=self.start(script);self.wait_file(self.out/'child_started');os.kill(p.pid,signal.SIGTERM);p.wait(timeout=5);self.assertEqual(p.returncode,143);self.assertTrue((self.out/'child_done').exists())
 def test_release_prepare_and_pass_implementations_preserved(self):
  old=ast.parse(Path('tools/bev_successor_prepare_queue_v1.py').read_text());new=ast.parse(Path(Q.__file__).read_text())
  for name in ['released','once']:
   a=next(x for x in old.body if isinstance(x,ast.FunctionDef) and x.name==name);b=next(x for x in new.body if isinstance(x,ast.FunctionDef) and x.name==name);self.assertEqual(ast.dump(a),ast.dump(b))
class BuilderLifecycle(Events):
 def builder_fixture(self,delay=.4,ignore=False):
  binder=self.root/'binder.py';binder.write_text("import json\nfrom pathlib import Path\ndef bind(base,allocation,chip,output,config,decision):\n Path(config).write_text(json.dumps({'output':output}))\n")
  builder=self.root/'builder.py';builder.write_text("import sys,json,time,os,signal\nfrom pathlib import Path\nc=json.loads(Path(sys.argv[-1]).read_text());p=Path(c['output']);p.mkdir();(p/'PID').write_text(str(os.getpid()))\n"+("signal.signal(signal.SIGTERM,signal.SIG_IGN)\n" if ignore else "")+"time.sleep("+str(delay)+")\n(p/'PREPARATION.json').write_text(json.dumps({'npu_launched':False,'status':'PREPARED_NOT_ACTIVATED'}))\n(p/'PLAN.json').write_text('{}');(p/'CONFIG.json').write_text('{}')\n")
  self.config.update(binder=Q.ref(binder),builder=Q.ref(builder),python=sys.executable,environment={});self.config['jobs'][0]['chip']=0;self.config['files'].update({str(binder):Q.sha(binder),str(builder):Q.sha(builder)});Path(self.config['allocation']).write_text('{}');self.cfg.write_text(json.dumps(self.config));self.pin=Q.sha(self.cfg)
 def builder_script(self,fail_service=False,fail_identity=False):
  return """import importlib.util,sys,time
from pathlib import Path
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
q.released=lambda *a,**kw:{}
original=q.put
original_identity=q.process_identity
def put(p,d):
 p=Path(p)
 if %s and p.name=='SERVICE.json' and p.parent.name=='x':
  time.sleep(.15)
  raise OSError('injected builder SERVICE persistence failure')
 return original(p,d)
def identity(pid):
 if %s and pid!=__import__('os').getpid():raise OSError('identity capture failed')
 return original_identity(pid)
q.put=put;q.process_identity=identity
sys.exit(q.run(sys.argv[1],sys.argv[2]))
""" % (repr(fail_service),repr(fail_identity))
 def test_service_write_failure_reaps_real_ignoring_builder(self):
  self.builder_fixture(30,True);p=self.start(self.builder_script(True));self.wait_file(self.root/'new/PID');child=int((self.root/'new/PID').read_text());self.wait_file(self.out/'QUEUE-EXIT.json');p.wait(5)
  self.assertEqual(p.returncode,1);self.assertFalse(Path('/proc',str(child)).exists());e=Q.read(self.out/'x/CHILD-STOP.json');self.assertEqual(e['exit_code'],-signal.SIGKILL);self.assertEqual(Q.read(self.out/'x/EXIT.json')['exit_code'],1);self.assertFalse((self.out/'x/SERVICE.json').exists());self.assertTrue(Q.read(self.out/'QUEUE-EXIT.json')['builders_reconciled'])
  before=(self.out/'x/EXIT.json').read_bytes();p2=self.start();p2.wait(5);self.assertEqual(p2.returncode,1);self.assertEqual(before,(self.out/'x/EXIT.json').read_bytes())
 def test_sigterm_during_real_builder_waits_for_success(self):
  self.builder_fixture(.5);p=self.start(self.builder_script());self.wait_file(self.root/'new/PID');child=int((self.root/'new/PID').read_text());p.terminate();p.wait(5);self.assertEqual(p.returncode,143);self.assertFalse(Path('/proc',str(child)).exists());self.assertTrue((self.out/'x/REVIEW-REQUEST.json').exists());self.assertEqual(Q.read(self.out/'x/EXIT.json')['exit_code'],0)
 def test_identity_capture_failure_still_owns_and_reaps(self):
  self.builder_fixture(30);p=self.start(self.builder_script(fail_identity=True));self.wait_file(self.out/'QUEUE-EXIT.json');p.wait(5);self.assertEqual(p.returncode,1);e=Q.read(self.out/'x/CHILD-STOP.json');self.assertIsNone(e['process']);self.assertFalse(Path('/proc',str(e['pid'])).exists())

class AdditionalLifecycle(BuilderLifecycle):
 def test_sigint_real_builder_records_130(self):
  self.builder_fixture(.5);p=self.start(self.builder_script());self.wait_file(self.root/'new/PID');p.send_signal(signal.SIGINT);p.wait(5);self.assertEqual(p.returncode,130);self.assertEqual(Q.read(self.out/'QUEUE-EXIT.json')['exit_code'],130)
 def test_failed_one_pass_does_not_claim_prepared(self):
  self.builder_fixture(.05);script=self.builder_script(True).replace("q.run(sys.argv[1],sys.argv[2])","q.run(sys.argv[1],sys.argv[2],True)");p=self.start(script);p.wait(5);self.assertEqual(p.returncode,1);self.assertEqual(Q.read(self.out/'QUEUE-EXIT.json')['reason'],'preparation_requires_reconciliation');self.assertEqual(Q.read(self.out/'x/EXIT.json')['exit_code'],1)

class CleanupUncertainty(BuilderLifecycle):
 def test_cleanup_identity_mismatch_records_uncertainty_without_signal(self):
  self.builder_fixture(30)
  script=self.builder_script(True).replace("original_identity=q.process_identity", "original_identity=q.process_identity\noriginal_stop=q.stop_owned_builder\ndef altered_stop(proc,identity):\n identity=dict(identity,start_ticks=identity['start_ticks']+1)\n return original_stop(proc,identity)\nq.stop_owned_builder=altered_stop")
  p=self.start(script);self.wait_file(self.root/'new/PID');child=int((self.root/'new/PID').read_text());p.wait(5)
  try:
   e=Q.read(self.out/'QUEUE-EXIT.json');self.assertEqual(e['exit_code'],1);self.assertFalse(e['builders_reconciled']);self.assertEqual(e['reason'],'owned_builder_requires_reconciliation');self.assertTrue(Path('/proc',str(child)).exists());self.assertFalse((self.out/'x/REVIEW-REQUEST.json').exists())
  finally:
   try:os.kill(child,signal.SIGKILL)
   except ProcessLookupError:pass

class ReentrantSignals(Events):
 def test_signal_while_unrelated_event_lock_held_does_not_block(self):
  script="""import importlib.util,sys,threading,os,signal
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
w=q.SignalWakeup();e=threading.Event()
with e._cond:
 os.kill(os.getpid(),signal.SIGUSR1)
 assert w.pending
w.close()
"""
  p=self.start(script);p.wait(timeout=5);self.assertEqual(p.returncode,0)
 def test_signal_burst_coalesces_no_duplicate_preparation(self):
  script="""import importlib.util,sys,time,json
from pathlib import Path
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
q.released=lambda *a,**kw:{}
count=0
def prepare(c,j,proof):
 global count
 count+=1
 node=Path(c['output'])/j['id'];node.mkdir();(node/'BUILDING').write_text('1');time.sleep(.5)
 q.put(node/'REVIEW-REQUEST.json',{'ok':True});(Path(c['output'])/'count').write_text(str(count));return {}
q.prepare=prepare
sys.exit(q.run(sys.argv[1],sys.argv[2]))
"""
  Path(self.config['allocation']).write_text('{}')
  p=self.start(script);self.wait_file(self.out/'x/BUILDING')
  for _ in range(500):os.kill(p.pid,signal.SIGUSR1)
  p.wait(5);self.assertEqual(p.returncode,0);self.assertEqual((self.out/'count').read_text(),'1');self.assertEqual(Q.read(self.out/'PROGRESS.json')['passes_completed'],1)
 def test_exception_from_pass_publishes_integer_terminal(self):
  script="""import importlib.util,sys
s=importlib.util.spec_from_file_location('q',sys.argv[3]);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
def once(c):raise RuntimeError('injected pass failure')
q.once=once
q.run(sys.argv[1],sys.argv[2])
"""
  p=self.start(script);p.wait(5);self.assertNotEqual(p.returncode,0);e=Q.read(self.out/'QUEUE-EXIT.json');self.assertEqual(type(e['exit_code']),int);self.assertEqual(e['exit_code'],1);self.assertEqual(e['error']['type'],'RuntimeError');self.assertEqual(e['progress']['passes_completed'],0)
 def test_signal_handler_contains_no_locking_or_io_calls(self):
  tree=ast.parse(Path(Q.__file__).read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SignalWakeup');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='handle');self.assertFalse(any(isinstance(n,ast.Call) for n in ast.walk(fn)))

if __name__=='__main__':unittest.main()
