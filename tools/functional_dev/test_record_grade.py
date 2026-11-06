import importlib.util,json,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).parent
spec=importlib.util.spec_from_file_location('wrapper',P/'dev_wrapper.py'); w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
spec=importlib.util.spec_from_file_location('queue',P/'queue.py'); q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
class Tests(unittest.TestCase):
 def test_shape_finite(self):
  row=[{'levels':[1,2]}]
  for f in (lambda r,m: [],lambda r,m:[[1]],lambda r,m:[[1,float('nan')]],lambda r,m:[[1,'2']],lambda r,m:[[1,2],[3,4]]):
   with self.assertRaises(ValueError):w.checked(f)(row)
  self.assertEqual(w.checked(lambda r,m:[[1.,2.]])(row),[[1.,2.]])
 def test_wrapper_fixed_report_and_resume(self):
  with tempfile.TemporaryDirectory() as t:
   a=SimpleNamespace(model='base',adapter='adapter-s3',out=t,limit=0)
   seen=[]; store={}
   class Full:
    @staticmethod
    def parse_full_args(argv):
     seen.extend(argv);return SimpleNamespace(**{k.lstrip('-').replace('-','_'):argv[i+1] for i,k in enumerate(argv[:-1]) if k in ('--model-path','--adapter','--out')})
    @staticmethod
    def run_full(args,sc):
     for key in ('a','b'):
      if key not in store:store[key]=sc([{'levels':[0,1]}])[0]
     return {'track_k':{'partitions':{k:{'n':n} for k,n in [('decision-v7/dev',1264),('decision-v7/calibration',1148),('transfer-v4/dev',656)]}}}
   class Eval:
    @staticmethod
    def make_score_fn(args):
     assert args.adapter=='adapter-s3' and args.token_budget==16384
     return lambda rows,mode:[[1.,2.] for r in rows]
   w.run(a,Full,Eval);w.run(a,Full,Eval)
   self.assertEqual(len(store),2);self.assertEqual(json.loads((Path(t)/'report.json').read_text())['track_k']['partitions']['transfer-v4/dev']['n'],656)
   self.assertIn('dev,calibration',seen);self.assertIn('k',seen);self.assertNotIn('report',seen);self.assertNotIn('test',seen)
 def test_no_report_on_incomplete(self):
  with tempfile.TemporaryDirectory() as t:
   a=SimpleNamespace(model='x',adapter='y',out=t,limit=0)
   f=SimpleNamespace(parse_full_args=lambda x:SimpleNamespace(),run_full=lambda a,s:{'track_k':{'partitions':{}}})
   with self.assertRaises(KeyError):w.run(a,f,SimpleNamespace(make_score_fn=lambda a:lambda r,m:[]))
   self.assertFalse((Path(t)/'report.json').exists())
 def test_fixed_lanes(self):
  jobs=q.C['jobs'];self.assertEqual(len(jobs),8);self.assertEqual({j['seed'] for j in jobs},{2,3});self.assertEqual({j['chip'] for j in jobs},set(range(8)))
 def test_missing_completion_and_failed_parent(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'q0p8b-s2').mkdir();(root/'q0p8b-s2/train-LAUNCH.json').write_text('{"container_id":"abc"}')
   j=q.C['jobs'][0]
   with patch.object(q,'ROOT',root),patch.object(q,'cmd',side_effect=['3',json.dumps([{'State':{'ExitCode':3}}])]):
    with self.assertRaisesRegex(RuntimeError,'training actual'):q.ready(j)
   with patch.object(q,'ROOT',root),patch.object(q,'cmd',side_effect=['0',json.dumps([{'State':{'ExitCode':0}}])]),patch.object(q.time,'sleep'):
    with self.assertRaisesRegex(RuntimeError,'missing terminal'):q.ready(j)
if __name__=='__main__':unittest.main()
