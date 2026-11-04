"""Worker contract tests with pinned fixture; real-record arithmetic tested separately."""
import copy,fcntl,gc,importlib.util,json,sys,tempfile,unittest,warnings
from unittest.mock import patch
from pathlib import Path
s=importlib.util.spec_from_file_location('first',Path(__file__).with_name('bev_native_cpu_first_consumer_v1.py'));M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
FIXTURE='''import json
from pathlib import Path
class Progress:
 def __init__(self,out): self.phase='records';self.completed=0;self.receipts_sha256='fixture';self.timings={}
 def emit(self): pass
def load(ref): return None
def consume(C,path,pin,attempt,progress):
 d=json.loads(Path(path).read_text())
 if d.get('fail'): raise ValueError('invalid lifecycle')
 return {'n':2,'scientific_acceptance':False,'candidate_test_authority':False,'plan_sha256':pin,'one_forward':{'correct':1,'accuracy':0.5}}
'''
class FirstWorker(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.module=self.root/'fixture.py';self.module.write_text(FIXTURE)
  self.plan=self.root/'PLAN.json';self.d={'out':str(self.root/'production'),'test_read':True,'scientific_acceptance':False,'modules':{'runtime':{'path':'fixture','sha256':'fixture'}},'files':{}}
  self.plan.write_text(json.dumps(self.d))
  self.cfg={'schema':'native-first-cpu-consumer-v1','read_only_saved_records':True,'attempt':1,'plan':{'path':str(self.plan),'sha256':M.sha(self.plan)},'output':str(self.root/'new-output'),'consumer':{'path':str(Path(M.__file__).resolve()),'sha256':M.sha(Path(M.__file__).resolve())},'replay_consumer':{'path':str(self.module),'sha256':M.sha(self.module)},'runtime_module':self.d['modules']['runtime'],'python':sys.executable}
 def run_cfg(self):
  path=self.root/'CONFIG.json';path.write_text(json.dumps(self.cfg));return M.run(str(path),M.sha(path))
 def test_first_summary_with_no_prior_summary_and_repeat_rejected(self):
  self.assertFalse((self.root/'production/cpu/1/summary.json').exists())
  self.assertEqual(self.run_cfg(),0)
  out=Path(self.cfg['output']);end=M.read(out/'EXIT.json');self.assertEqual(end['exit_code'],0)
  self.assertFalse(end['old_summary_required']);self.assertEqual(M.read(out/'summary.json')['one_forward']['correct'],1)
  original_terminal=(out/'EXIT.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'must be new'):self.run_cfg()
  self.assertEqual((out/'EXIT.json').read_bytes(),original_terminal)
  self.assert_lock_free()
 def assert_lock_free(self):
  with (self.root/'new-output.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def test_admission_failure_does_not_leak_descriptor_or_lock(self):
  before=len(list(Path('/proc/self/fd').iterdir()))
  self.cfg['replay_consumer']['sha256']='0'*64
  with warnings.catch_warnings(record=True) as observed:
   warnings.simplefilter('always',ResourceWarning)
   for _ in range(4):
    with self.assertRaisesRegex(ValueError,'consumer source changed'):self.run_cfg()
   gc.collect()
  self.assertFalse([w for w in observed if issubclass(w.category,ResourceWarning)])
  self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
  self.assert_lock_free(); self.assertFalse(Path(self.cfg['output']).exists())
 def test_service_write_failure_is_terminal_failure(self):
  original_put=M.put
  def faulty(path,obj):
   if Path(path).name=='SERVICE.json':raise OSError('injected service write failure')
   original_put(path,obj)
  with patch.object(M,'put',side_effect=faulty):self.assertEqual(self.run_cfg(),1)
  out=Path(self.cfg['output']);self.assertEqual(M.read(out/'EXIT.json')['exit_code'],1)
  self.assertIsNone(M.read(out/'EXIT.json')['summary_sha256'])
  self.assertFalse((out/'summary.json').exists());self.assert_lock_free()
 def test_error_and_terminal_write_failure_still_unlocks(self):
  original_put=M.put
  def faulty(path,obj):
   if Path(path).name in ('SERVICE.json','ERROR.json','EXIT.json'):raise OSError('injected unavailable output')
   original_put(path,obj)
  with patch.object(M,'put',side_effect=faulty):
   with self.assertRaises(OSError):self.run_cfg()
  out=Path(self.cfg['output']);self.assertFalse((out/'EXIT.json').exists())
  self.assertFalse((out/'summary.json').exists());self.assert_lock_free()
 def test_duplicate_lock(self):
  with (self.root/'new-output.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaises(BlockingIOError):self.run_cfg()
  self.assertFalse(Path(self.cfg['output']).exists())
 def test_lifecycle_failure_writes_failure_not_summary(self):
  self.d['fail']=True;self.plan.write_text(json.dumps(self.d));self.cfg['plan']['sha256']=M.sha(self.plan)
  self.assertEqual(self.run_cfg(),1);out=Path(self.cfg['output'])
  self.assertFalse((out/'summary.json').exists());self.assertEqual(M.read(out/'EXIT.json')['exit_code'],1)
 def test_bad_consumer_and_plan_hash_rejected(self):
  for ref in ('consumer','replay_consumer','plan'):
   with self.subTest(ref=ref):
    old=copy.deepcopy(self.cfg);self.cfg[ref]['sha256']='0'*64
    with self.assertRaises(ValueError):self.run_cfg()
    self.cfg=old
 def test_bool_attempt_and_extra_oracle_rejected(self):
  self.cfg['attempt']=True
  with self.assertRaisesRegex(ValueError,'attempt'):self.run_cfg()
  self.cfg['attempt']=1;self.cfg['expected_summary']={}
  with self.assertRaisesRegex(ValueError,'fields'):self.run_cfg()
 def test_parent_traversal_rejected_before_writes(self):
  (self.root/'scratch').mkdir()
  self.cfg['output']=str(self.root/'scratch/../production/unexpected-cpu')
  with self.assertRaisesRegex(ValueError,'noncanonical'):self.run_cfg()
  self.assertFalse((self.root/'production').exists())
  self.d['out']=str(self.root/'scratch/../production')
  self.plan.write_text(json.dumps(self.d));self.cfg['plan']['sha256']=M.sha(self.plan)
  self.cfg['output']=str(self.root/'new-output')
  with self.assertRaisesRegex(ValueError,'noncanonical'):self.run_cfg()
  self.assertFalse((self.root/'new-output').exists())
 def test_symlink_parent_rejected_before_writes(self):
  target=self.root/'production';target.mkdir()
  alias=self.root/'alias';alias.symlink_to(target,target_is_directory=True)
  self.cfg['output']=str(alias/'unexpected-cpu')
  with self.assertRaisesRegex(ValueError,'symlink'):self.run_cfg()
  self.assertEqual(list(target.iterdir()),[])
 def test_output_overlap_and_symlink_rejected(self):
  for output in (self.root/'production/child',self.root):
   self.cfg['output']=str(output)
   with self.assertRaisesRegex(ValueError,'overlap'):self.run_cfg()
  (self.root/'alias').symlink_to(self.root);self.cfg['output']=str(self.root/'alias/new')
  with self.assertRaisesRegex(ValueError,'unsafe'):self.run_cfg()
 def test_changed_closure_rejected_before_summary(self):
  src=self.root/'source.txt';src.write_text('actual');self.d['files']={str(src):'0'*64};self.plan.write_text(json.dumps(self.d));self.cfg['plan']['sha256']=M.sha(self.plan)
  self.assertEqual(self.run_cfg(),1);self.assertFalse((Path(self.cfg['output'])/'summary.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)
