import contextlib, io, json, tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
import materializer as M

class ResultRoute(unittest.TestCase):
 def test_existing_loop_survives_assembly_and_waits_for_review(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);M.save(out/'pending.json',{'roles':[{'status':'ready'}]*12})
   outcomes=[{'status':'pending'},{'status':'ready_for_review'},{'status':'ready_for_consumer','consumer_exit':2}]
   with patch.object(sys,'argv',['materializer','--out',d,'--result-config',str(out/'config.json')]),patch.object(M,'step',side_effect=['pending','materialized']) as step,patch.object(M,'result_tick',side_effect=outcomes) as tick,patch.object(M.time,'sleep') as sleep,contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(M.main(),0)
   self.assertEqual(step.call_count,2);self.assertEqual(tick.call_count,3)
   self.assertEqual([c.args for c in sleep.call_args_list],[(600,),(600,)])
   self.assertEqual(M.collector.read(out/'EXIT.json')['consumer_exit'],2)
   self.assertIn('--result-config',(out/'RELAUNCH.sh').read_text())
 def test_result_error_stops_with_terminal(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);M.save(out/'pending.json',{'roles':[{'status':'pending'}]*12})
   with patch.object(sys,'argv',['materializer','--out',d,'--result-config',str(out/'config.json')]),patch.object(M,'step',return_value='pending'),patch.object(M,'result_tick',side_effect=ValueError('collector error')),contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaisesRegex(ValueError,'collector error'):M.main()
   self.assertEqual(M.collector.read(out/'EXIT.json')['exit_code'],1)
 def test_subprocess_route_and_error_heartbeat(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);M.save(out/'same-test/heartbeat.json',{'status':'pending'})
   with patch.object(M.subprocess,'run') as run:
    run.return_value.returncode=0
    self.assertEqual(M.result_tick(out/'config.json',out)['status'],'pending')
    args=run.call_args.args[0]
    self.assertEqual(Path(args[3]),Path(M.__file__).resolve().parent.parent/'package/watcher.py')
    self.assertEqual(args[-1],'--once')
    M.save(out/'same-test/heartbeat.json',{'status':'error'})
    with self.assertRaisesRegex(ValueError,'collector failed'):M.result_tick(out/'config.json',out)
if __name__=='__main__':unittest.main()
