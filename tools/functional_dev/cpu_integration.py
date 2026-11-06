"""Exercise real frozen run_full and resumable stores with its deterministic mock scorer."""
import importlib.util, json, os, sys
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('dev_wrapper','/work/dev_wrapper.py'); w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
import full_eval_r3
class Fake:
 @staticmethod
 def make_score_fn(args): return full_eval_r3.mock_score_fn('mock')
a=SimpleNamespace(model='mock',adapter='fake-seed2',out='/out/result',limit=2)
w.run(a,full_eval_r3,Fake)
first=json.load(open('/out/result/report.json'))
# A second pass should reproduce the same metrics via stores, without forwarding scores.
class NoScore:
 @staticmethod
 def make_score_fn(args):
  sc=full_eval_r3.mock_score_fn('mock')
  def no(*a,**kw): raise AssertionError('resume attempted scoring')
  no.describe=sc.describe
  return no
w.run(a,full_eval_r3,NoScore)
second=json.load(open('/out/result/report.json'))
assert first['track_k']==second['track_k']
assert set(first['track_k']['partitions'])=={'decision-v7/dev','decision-v7/calibration','transfer-v4/dev'}
print('REAL_RUN_FULL_MOCK_RESUME_OK')
