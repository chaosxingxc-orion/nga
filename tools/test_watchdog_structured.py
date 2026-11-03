"""Regressions for native JSON progress and exact engineering terminal names."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from tools import watchdog as w

NOW = 1800000000.0

class StructuredWatchdog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'run'
        self.root.mkdir()
        self.cfg = w.make_cfg(root=[str(self.root)], out_dir=str(Path(self.tmp.name)/'digest'), max_depth=0, no_npu=True)

    def put(self, name, value):
        p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value))

    def result(self):
        d=w.build_digest(self.cfg,{},NOW)
        self.assertEqual(len(d['runs']),1)
        return d['runs'][0]

    def progress(self, **kw):
        return dict(utc_seconds=NOW-10, completed=2000,total=46320,
                    questions_per_second_per_chip=3.1,
                    runtime=dict(chips=1,reserved_gib=3.6),**kw)

    def test_json_progress_perf_discovered_without_logs(self):
        self.put('heartbeat.json',self.progress())
        r=self.result()
        self.assertEqual(r['state'],'running')
        self.assertEqual((r['progress']['done'],r['progress']['total']),(2000,46320))
        self.assertEqual(r['perf']['ex_s'],3.1)
        self.assertEqual(r['perf']['reserved_gib'],3.6)
        self.assertEqual(r['perf']['chips'],1)
        self.assertIsNone(r['progress']['eta_utc'])
        self.assertFalse(r['progress']['uniform_cost'])

    def test_stale_progress_not_hidden_by_fresh_child_liveness(self):
        d=self.progress();d['utc_seconds']=NOW-4000
        self.put('heartbeat.json',d)
        self.put('attempts/1/heartbeat.json',dict(utc_seconds=NOW-1,state='runtime_alive'))
        r=self.result();self.assertEqual(r['state'],'stalled')
        self.assertIn('JSON progress timestamp',' '.join(r['notes']))

    def test_liveness_only_is_not_progress(self):
        self.put('heartbeat.json',dict(utc_seconds=NOW-1,state='control_scoring',chips=1))
        r=self.result();self.assertEqual(r['state'],'running')
        self.assertIsNone(r['progress']['done']);self.assertIsNone(r['perf'])

    def test_invalid_json_not_fresh_mtime(self):
        bad=[dict(completed=True),dict(total=False),dict(completed=46321),
             dict(utc_seconds=float('nan')),dict(questions_per_second_per_chip=float('inf')),
             dict(runtime=dict(chips=True)),dict(runtime=dict(chips=1,reserved_gib=-1))]
        for patch in bad:
            with self.subTest(patch=patch):
                d=self.progress();d.update(patch);self.put('heartbeat.json',d)
                r=self.result();self.assertEqual(r['state'],'unknown')
                self.assertIsNone(r['progress'])
        (self.root/'heartbeat.json').write_text('{torn')
        self.assertEqual(self.result()['state'],'unknown')

    def test_oversize_snapshot_rejected(self):
        (self.root/'heartbeat.json').write_text(' '* (w.JSON_HEARTBEAT_LIMIT+1))
        self.assertEqual(self.result()['state'],'unknown')

    def test_exact_terminal_beats_stale_progress(self):
        self.put('heartbeat.json',dict(utc_seconds=NOW-4000,state='runtime_alive'))
        for name in ('EVAL_COMPLETE.track_kt.json','EVAL_COMPLETE.track_t_pt_r0.json','ENGINEERING_EVAL_EXIT.json','EXIT.json'):
            with self.subTest(name=name):
                self.put(name,dict(exit_code=0,attempt=1,scientific_acceptance=False))
                self.assertEqual(self.result()['state'],'done')
                (self.root/name).unlink()

    def test_terminal_names_not_wildcards_or_status_only(self):
        self.put('heartbeat.json',dict(utc_seconds=NOW-4000,state='runtime_alive'))
        self.put('EVAL_COMPLETE.foreign.json',dict(exit_code=0))
        self.assertEqual(self.result()['state'],'stalled')
        self.put('EVAL_COMPLETE.track_kt.json',dict(status='complete'))
        self.assertEqual(self.result()['state'],'unknown')

    def test_scoped_terminal_false_success_rejected(self):
        for value in (dict(exit_code=False),dict(exit_code=0,scientific_acceptance=True),
                      dict(exit_code=0,error='bad'),dict(exit_code=0,rc=1),dict(exit_code=0,schema='foreign'),dict(exit_code=0,status='running')):
            with self.subTest(value=value):
                self.put('EVAL_COMPLETE.track_kt.json',value)
                self.assertEqual(self.result()['state'],'unknown')
        (self.root/'EVAL_COMPLETE.track_kt.json').unlink()
        self.put('ENGINEERING_EVAL_EXIT.json',dict(exit_code=0,attempt=True,scientific_acceptance=False))
        self.assertEqual(self.result()['state'],'unknown')

    def test_completed_count_aliases_and_phase_reset_no_false_rate(self):
        for phase,count in [('first',32),('second',1)]:
            self.put('heartbeat.json',dict(utc_seconds=NOW-10,state='control_scoring',phase=phase,completed_questions=count,total=64))
            r=self.result();self.assertEqual(r['progress']['done'],count)
            self.assertIsNone(r['progress']['rate_per_min']);self.assertIsNone(r['progress']['eta_utc'])
        self.put('heartbeat.json',dict(utc_seconds=NOW-10,completed_items=9,total_items=9))
        self.assertEqual(self.result()['progress']['total'],9)

    def test_log_heartbeat_behavior_preserved(self):
        (self.root/'heartbeat.log').write_text(w.iso(NOW-10)+' completed=12 total=20\n')
        r=self.result();self.assertEqual(r['state'],'running');self.assertEqual(r['progress']['done'],12)

    def test_bad_status_types_are_bounded_not_exceptions(self):
        for name in ('ENGINEERING_EVAL_EXIT.json','EVAL_COMPLETE.track_kt.json','EVAL_COMPLETE.track_t_pt_r0.json','EXIT.json'):
            for status in ([],{},['running'],1,None):
                with self.subTest(name=name,status=status):
                    self.put(name,dict(exit_code=0,attempt=1,scientific_acceptance=False,status=status))
                    self.assertEqual(self.result()['state'],'unknown')
                    (self.root/name).unlink()

    def test_exit_metadata_contradictions_and_minimal_legacy(self):
        for value in (dict(exit_code=0,rc=1),dict(exit_code=0,rc=False),
                      dict(exit_code=0,scientific_acceptance=True),dict(exit_code=0,status='running'),
                      dict(exit_code=0,stage='failed')):
            with self.subTest(value=value):
                self.put('EXIT.json',value)
                self.assertEqual(self.result()['state'],'unknown')
        self.put('EXIT.json',dict(exit_code=0))
        self.assertEqual(self.result()['state'],'done')
        self.put('EXIT.json',dict(exit_code=1))
        self.assertEqual(self.result()['state'],'failed')

    def test_cached_stale_progress_retains_authority(self):
        self.put('heartbeat.json',dict(utc_seconds=NOW-4000,completed=2,total=10))
        self.put('attempts/1/heartbeat.json',dict(utc_seconds=NOW-1,state='runtime_alive'))
        before=self.result()
        cached=w.refresh_cached(dict(before),str(self.root),self.cfg,NOW+1)
        self.assertEqual(before['state'],'stalled')
        self.assertEqual(cached['heartbeat_epoch'],before['heartbeat_epoch'])
        self.assertEqual(cached['age_s'],4001)
        self.assertEqual(cached['heartbeat_source'],'heartbeat.json progress')

    def test_json_and_log_counters_never_form_trend(self):
        (self.root/'heartbeat.log').write_text(''.join(w.iso(NOW-t)+' completed=1 total=10\n' for t in (60,40,30)))
        self.put('heartbeat.json',dict(utc_seconds=NOW-1,completed=2,total=10))
        r=self.result()
        self.assertEqual(r['progress']['done'],2)
        self.assertIsNone(r['progress']['rate_per_min'])
        self.assertIsNone(r['progress']['window_s'])
        self.assertIsNone(r['progress']['eta_utc'])
        samples,*_=w.read_heartbeat(str(self.root),self.cfg)
        self.assertIsNone(w.flat_stretch(samples))

    def test_json_progress_keeps_log_error_clustering(self):
        self.put('heartbeat.json',self.progress())
        (self.root/'runtime.log').write_text('RuntimeError: test sentinel failure\n')
        r=self.result()
        self.assertGreater(r['errors']['error_lines'],0)
        self.assertTrue(r['pointers'])

if __name__=='__main__':unittest.main()
