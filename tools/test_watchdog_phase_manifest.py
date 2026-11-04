import json,tempfile,unittest,time
from pathlib import Path
from tools import watchdog as W
class Phases(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name);self.out=self.r/'run/output';self.out.mkdir(parents=True);self.man=self.r/'manifest.json'
 def put(self,p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
 def rows(self):return [dict(id='one/npu',path=str(self.out),marker=str(self.out/'attempts/1/EXIT.json'),log_globs=['host_attempts/1/*.log']),dict(id='one/cpu',path=str(self.out/'cpu/1'),marker=str(self.out/'cpu/1/EXIT.json'),log_globs=['*.log'])]
 def cfg(self):return W.make_cfg(root=[str(self.r)],run_manifest=str(self.man),out_dir=str(self.r/'digest'),no_npu=True)
 def test_nested_terminal_overrides_fresh_output_heartbeat(self):
  self.put(self.out/'heartbeat.json',dict(utc_seconds=time.time(),completed=1000,total=1000));self.put(self.out/'attempts/1/EXIT.json',dict(exit_code=0,scientific_acceptance=False));self.put(self.man,self.rows());d=W.build_digest(self.cfg(),{});self.assertEqual(d['runs'][0]['state'],'done');self.assertEqual(d['queued'],['one/cpu'])
 def test_separate_cpu_failure(self):
  self.put(self.out/'attempts/1/EXIT.json',dict(exit_code=0));self.put(self.out/'cpu/1/EXIT.json',dict(exit_code=1));self.put(self.man,self.rows());d=W.build_digest(self.cfg(),{});self.assertEqual({r['id']:r['state'] for r in d['runs']},{'one/npu':'done','one/cpu':'failed'})
 def test_bool_and_conflicting_scope_rejected(self):
  self.put(self.man,self.rows());self.put(self.out/'attempts/1/EXIT.json',dict(exit_code=False));self.assertEqual(W.build_digest(self.cfg(),{})['runs'][0]['state'],'unknown');self.put(self.out/'attempts/1/EXIT.json',dict(exit_code=0,scientific_acceptance=True));self.assertEqual(W.build_digest(self.cfg(),{})['runs'][0]['state'],'unknown')
 def test_duplicate_ids_and_paths_rejected(self):
  for key in ['id','path']:
   rr=self.rows();rr[1][key]=rr[0][key];self.put(self.man,rr)
   with self.assertRaises(ValueError):W.discover(self.cfg())
 def test_precreated_empty_output_stays_pending(self):
  self.put(self.man,self.rows());d=W.build_digest(self.cfg(),{});self.assertEqual(d['runs'],[]);self.assertEqual(d['queued'],['one/cpu','one/npu'])
 def test_foreign_marker_rejected(self):
  rr=self.rows();rr[0]['marker']=str(self.r/'other/EXIT.json');self.put(self.man,rr)
  with self.assertRaises(ValueError):W.discover(self.cfg())
 def test_cache_detects_new_terminal(self):
  self.put(self.out/'heartbeat.json',dict(utc_seconds=time.time(),state='alive'));self.put(self.man,self.rows());cfg=self.cfg();cfg.interval=600;s={};W.build_digest(cfg,{},sched=s);self.put(self.out/'attempts/1/EXIT.json',dict(exit_code=0));d=W.build_digest(cfg,{},sched=s);self.assertEqual(d['runs'][0]['state'],'done')
if __name__=='__main__':unittest.main()
