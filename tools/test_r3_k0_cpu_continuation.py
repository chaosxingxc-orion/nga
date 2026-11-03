import contextlib, importlib.util, io, json, tempfile, threading, unittest
from pathlib import Path
from tools import r3_k0_cpu_continuation as C

class AuditHeartbeat(unittest.TestCase):
 def test_real_audit_boundary_remains_strict_and_stage_events_survive(self):
  source=Path('/home/xingchao/workspace/nga/.local/preparations/formal-qualification-consumer-20261101-v3/consumer.py')
  if not source.is_file():self.skipTest('frozen integration fixture unavailable; run target-image preflight')
  spec=importlib.util.spec_from_file_location('real_boundary',source);Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);scratch=root/'scratch';scratch.mkdir();out=root/'out';out.mkdir();events=[];errors=[]
   def put(p,d):p.write_text(json.dumps(d))
   def event(stage):
    events.append(stage)
    with contextlib.redirect_stdout(io.StringIO()):C.stage_event(put,out,stage)
   def work():
    with Q.ReadBoundary({},scratch).installed():
     def forbidden_beat():
      try:put(out/'heartbeat.json',{'bad':True})
      except ValueError as e:errors.append(str(e))
     t=threading.Thread(target=forbidden_beat);t.start();t.join()
     (scratch/'allowed.json').write_text('{}')
    return {'strict_report':'unchanged'}
   self.assertEqual(C.audited_stage(work,event),{'strict_report':'unchanged'})
   self.assertEqual(errors,['write outside private scratch forbidden'])
   self.assertEqual(events,['strict_reports_start','strict_reports_reconstructed'])
   self.assertEqual(json.loads((out/'heartbeat.json').read_text())['stage'],'strict_reports_reconstructed')
 def test_failure_does_not_emit_false_success(self):
  events=[]
  def fail():raise ValueError('audited consumer rejected input')
  with self.assertRaises(ValueError):C.audited_stage(fail,events.append)
  self.assertEqual(events,['strict_reports_start'])

if __name__=='__main__':unittest.main()
