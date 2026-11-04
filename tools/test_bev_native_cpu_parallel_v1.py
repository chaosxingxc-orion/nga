"""Bounded thread work, deterministic merging and owned failure tests."""
import contextlib,importlib.util,io,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).with_name('bev_native_cpu_parallel_v1.py').resolve()
s=importlib.util.spec_from_file_location('parallel_cpu',P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Parallel(unittest.TestCase):
 def test_parallel_order_and_real_threads(self):
  lock=threading.Lock();threads=set()
  def work(start,end):
   with lock:threads.add(threading.get_ident())
   time.sleep(.01 if start==0 else .001)
   return list(range(start,end))
  actual=[x for chunk in M.ordered_chunks(work,103,workers=4,chunk_size=7) for x in chunk]
  self.assertEqual(actual,list(range(103)));self.assertGreater(len(threads),1)
 def test_bounded_submission(self):
  started=[];lock=threading.Lock();gate=threading.Event()
  def work(a,b):
   with lock:started.append(a)
   if a==0:gate.wait(2)
   return a
  gen=M.ordered_chunks(work,1000,workers=3,chunk_size=1);result=[]
  t=threading.Thread(target=lambda:result.append(next(gen)));t.start();time.sleep(.05)
  self.assertLessEqual(len(started),6);gate.set();t.join();self.assertEqual(result,[0]);gen.close()
 def test_thread_failure_propagates(self):
  def work(a,b):
   if a==4:raise ValueError('bad record')
   return a
  with self.assertRaisesRegex(ValueError,'bad record'):list(M.ordered_chunks(work,20,workers=4,chunk_size=2))
 def test_one_worker_identical_order(self):
  fn=lambda a,b:list(range(a,b))
  self.assertEqual(list(M.ordered_chunks(fn,20,workers=1,chunk_size=3)),list(M.ordered_chunks(fn,20,workers=4,chunk_size=3)))
 def test_bad_config(self):
  for opt in ({'workers':True,'chunk_size':1},{'workers':0,'chunk_size':1},{'workers':33,'chunk_size':1},{'workers':4,'chunk_size':0},{'workers':1,'chunk_size':1025},{'workers':1}):
   with self.assertRaises(ValueError):M.parallel_options(opt)
 def test_imports_exact_and_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'items').mkdir();old=root/'OLD.json';M.put(old,{'out':'old-output'})
   entries=[]
   for i in range(15):
    dest=root/'items'/f'{i:06d}';dest.mkdir();M.put(dest/'record.json',{'i':i});M.put(dest/'COMMITTED.json',{'record.json':M.sha(dest/'record.json')})
    entries.append({'ordinal':i,'record_sha256':M.sha(dest/'record.json'),'commit_sha256':M.sha(dest/'COMMITTED.json')})
   previous={'path':str(old),'sha256':M.sha(old)};manifest=root/'IMPORTED.json';M.put(manifest,{'schema':'native-panel-imported-commits-v1','source_plan':previous,'source_out':'old-output','count':15,'items':entries})
   d={'out':str(root),'recovery':{'source_plan':previous,'manifest':{'path':str(manifest)},'imported_count':15}}
   class Progress:
    def tick(self,n):self.done=n
   progress=Progress()
   for workers in [1,4]:self.assertEqual(M.check_imports(None,M,d,progress,{'workers':workers,'chunk_size':3}),15)
   self.assertEqual(progress.done,15)
   (root/'items/000004/record.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'imported bytes changed'):M.check_imports(None,M,d,progress,{'workers':4,'chunk_size':3})
 def test_owned_failure_terminal_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);prod=root/'production';prod.mkdir();out=root/'result'
   runtime=root/'runtime.py';runtime.write_text('# fixture\n')
   replay=root/'replay.py';replay.write_text('''class Progress:
 def __init__(self,out): self.phase='fixture';self.completed=0
 def emit(self): pass
def load(ref): return object()
''')
   plan=root/'PLAN.json';M.put(plan,{'out':str(prod),'test_read':True,'scientific_acceptance':False,'modules':{'runtime':{'path':str(runtime),'sha256':M.sha(runtime)}},'files':{}})
   cfg=root/'CONFIG.json';M.put(cfg,{'schema':'native-parallel-cpu-consumer-v1','read_only_saved_records':True,'attempt':1,'plan':{'path':str(plan),'sha256':M.sha(plan)},'output':str(out),'consumer':{'path':str(P),'sha256':M.sha(P)},'replay_consumer':{'path':str(replay),'sha256':M.sha(replay)},'runtime_module':{'path':str(runtime),'sha256':M.sha(runtime)},'python':'python3','parallel':{'workers':4,'chunk_size':4}})
   with patch.object(M,'consume',side_effect=ValueError('worker failure')),contextlib.redirect_stderr(io.StringIO()): self.assertEqual(M.run(str(cfg),M.sha(cfg)),1)
   exit_bytes=(out/'EXIT.json').read_bytes();self.assertEqual(json.loads(exit_bytes)['exit_code'],1);self.assertFalse((out/'summary.json').exists())
   with self.assertRaisesRegex(ValueError,'output must be new'):M.run(str(cfg),M.sha(cfg))
   self.assertEqual(exit_bytes,(out/'EXIT.json').read_bytes());self.assertEqual(list(prod.iterdir()),[])
if __name__=='__main__':unittest.main()
