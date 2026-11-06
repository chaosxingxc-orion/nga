import json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import queue as q
class QueueTests(unittest.TestCase):
 def test_retained(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);l=d/'launch';t=d/'exit';l.write_text('{"container_id":"cid"}');t.write_text('{"container_id":"cid","exit_code":0,"container_exit_code":0}')
   with patch.object(q,'inspect',return_value={'State':{'Running':False,'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False}}):self.assertTrue(q.retained_exit(l,t))
   with patch.object(q,'inspect',return_value={'State':{'Running':True,'Status':'running','ExitCode':0},'HostConfig':{'AutoRemove':False}}):
    with self.assertRaises(ValueError):q.retained_exit(l,t)
   t.write_text('{"container_id":"other","exit_code":0,"container_exit_code":0}')
   with patch.object(q,'inspect',return_value={'State':{'Running':False,'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False}}):
    with self.assertRaises(ValueError):q.retained_exit(l,t)
 def test_plan(self):
  self.assertEqual([j[1] for j in q.JOBS],[4,5,6,7]);self.assertEqual(len(set(j[0] for j in q.JOBS)),4)
 def test_no_wait_on_cpu(self):
  with tempfile.TemporaryDirectory() as d, patch.object(q,'OUT',Path(d)), patch.object(q,'ready',return_value=True), patch.object(q,'free',return_value=True), patch.object(q,'phase') as phase:
   q.lane('08b-k0',4,'lane');self.assertEqual([x.args[2] for x in phase.call_args_list],['infer','score'])
if __name__=='__main__':unittest.main()
