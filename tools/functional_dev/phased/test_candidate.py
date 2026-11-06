import importlib.util, json, unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).parent
spec=importlib.util.spec_from_file_location('wrapper',P/'phase_wrapper.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
spec=importlib.util.spec_from_file_location('queue',P/'queue_proposal.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
class Tests(unittest.TestCase):
 def test_original_groups(self):
  self.assertEqual(w.GROUPS, ['decision-v7/calibration/clean'] + [f'{suite}/dev/{kind}' for suite in ('decision-v7','transfer-v4') for kind in ('clean','variants','question_only','empty_input')])
  # Frozen contract: variant population totals 312 per adapter.
  self.assertEqual(8 * (1148 + (1264 + 656) * 3 + 312), 57760)
 def test_checked(self):
  rows=[{'levels':[1,2]}]
  for x in ([],[[1]],[[1,float('nan')]],[[1,'2']],[[1,2],[3,4]]):
   with self.assertRaises(ValueError):w.checked(lambda r,m:x)(rows)
  self.assertEqual(w.checked(lambda r,m:[[1,2]])(rows),[[1,2]])
 def test_offline(self):
  o=w.Offline({'scorer':'x'});self.assertEqual(o.describe(),{'scorer':'x'})
  with self.assertRaisesRegex(RuntimeError,'forbidden'):o([], 'full')
 def test_order(self):
  events=[]
  with patch.object(q,'launch_phase',side_effect=lambda j,k,b,p:events.append(p)):
   q.launch({},'full',{})
  self.assertEqual(events,['infer','score'])
 def test_config(self):
  self.assertEqual(len(q.C['jobs']),8);self.assertEqual(q.C['cpu_parallel_jobs'],2)
  self.assertEqual({x['chip'] for x in q.C['jobs']},set(range(8)))
if __name__=='__main__':unittest.main()
