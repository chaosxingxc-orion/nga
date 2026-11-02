"""CPU queue integration with real phase snapshots; no NPU or live-state writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from tools import r3_cpu_report_queue as Q
from tools import test_r3_main_metric_phase as fixture
M, put, CLOSURE = fixture.M, fixture.put, fixture.CLOSURE


class MainMetricQueue(unittest.TestCase):
    def setUp(self):
        self.phase=fixture.PhaseTests(methodName='runTest'); self.phase.setUp()
        self.addCleanup(self.phase.tearDown)
        self.root=self.phase.root/'queue'; self.root.mkdir()
        self.path=self.root/'QUEUE.json'
        self.job=dict(id='clean',kind='main_metric_diagnostic',
                      contract=str(self.phase.path),contract_sha256=self.phase.pin,
                      eval_out=str(self.phase.out),
                      output=str(self.root/'diagnostics/clean/main_metric_diagnostic.json'))
        manifest=CLOSURE.parent/'manifest.json'
        self.doc=dict(schema='r3-cpu-report-queue-v1',test_read=False,scientific_acceptance=False,
                      controller=str(Path(Q.__file__).resolve()),controller_sha256=Q.sha(Q.__file__),
                      report_tool=str(Path(M.__file__).resolve()),report_tool_sha256=Q.sha(M.__file__),
                      closure=str(CLOSURE.parent),closure_sha256=Q.sha(manifest),
                      main_metric_diagnostic=dict(tool=str(Path(M.__file__).resolve()),tool_sha256=Q.sha(M.__file__)),
                      jobs=[self.job],event_wake_paths=[str(self.phase.out/'MAIN_METRIC_COMPLETE.json'),
                                                     str(Q.workdir(self.path,self.job)/'EXIT.json')])
        self.save()
    def save(self):
        put(self.path,self.doc);self.pin=Q.sha(self.path)
    def complete(self):
        return self.phase.complete()
    def test_verify_wait_and_ready_without_full_terminal(self):
        self.assertEqual(Q.verify(self.path,self.pin),self.doc)
        self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'waiting_main_metric')
        self.complete()
        with patch.object(Q,'ready',side_effect=AssertionError('must not use full-run gate')):
            self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'ready')
        self.assertFalse((self.phase.out/'ENGINEERING_EVAL_EXIT.json').exists())
        self.assertFalse((self.phase.out/'RELEASE.json').exists())
    def test_actual_worker_immutable_output_later_failure_and_no_duplicate(self):
        expected=self.complete()
        root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        original=Q.subprocess.Popen
        calls=[]
        def start(*args,**kwargs):
            calls.append(kwargs)
            return original(*args,**kwargs)
        with patch.object(Q.subprocess,'Popen',side_effect=start):
            self.assertEqual(Q.worker(self.path,self.pin,'clean'),0)
        self.assertEqual(Q.load(self.job['output']),expected)
        self.assertTrue(calls[0]['start_new_session'])
        end=Q.load(root/'EXIT.json')
        for k,v in Q.MAIN_METRIC_FLAGS.items():self.assertIs(end[k],v)
        # A later whole-run failure cannot promote or invalidate this diagnostic.
        put(self.phase.out/'ENGINEERING_EVAL_EXIT.json',dict(exit_code=1))
        put(self.phase.out/'EVAL_FAILED.track_kt.json',dict(exit_code=1))
        with patch.object(Q.subprocess,'Popen') as spawn:
            self.assertEqual(Q.tick(self.path,self.pin,self.doc)['clean']['status'],'done')
            self.assertEqual(Q.tick(self.path,self.pin,self.doc)['clean']['status'],'done')
            spawn.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,'already terminal'):
            Q.worker(self.path,self.pin,'clean')
        self.assertFalse((self.phase.out/'RELEASE.json').exists())
        self.assertFalse((self.phase.out/'results/selection_report.json').exists())
        self.assertEqual(Q.ready({'eval_out':str(self.root/'still-running-full')}),'waiting_inference')
    def test_source_and_contract_mutation_rejected(self):
        self.complete()
        source=self.root/'consumer.py';source.write_text('# fixture')
        d=copy.deepcopy(self.doc);d['main_metric_diagnostic']['tool_sha256']='0'*64
        with self.assertRaises(RuntimeError):Q.main_metric_inputs(self.path,d,self.job)
        self.phase.path.write_text(self.phase.path.read_text()+' ')
        with self.assertRaisesRegex(RuntimeError,'dependency changed'):
            Q.job_ready(self.path,self.doc,self.job)
    def test_mutation_during_worker_fails_without_accepted_output(self):
        self.complete();root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        original=Q.validate_main_metric_output
        def mutate_then_validate(report,path,doc,job,pins):
            self.phase.path.write_text(self.phase.path.read_text()+' ')
            return original(report,path,doc,job,pins)
        with patch.object(Q,'validate_main_metric_output',side_effect=mutate_then_validate):
            self.assertEqual(Q.worker(self.path,self.pin,'clean'),125)
        end=Q.load(root/'EXIT.json')
        self.assertEqual(end['exit_code'],125);self.assertIsNone(end['output_sha256'])
        self.assertFalse(end['scientific_acceptance'])
        # Retain failed child output as evidence; no duplicate attempt.
        with patch.object(Q.subprocess,'Popen') as spawn:
            self.assertEqual(Q.tick(self.path,self.pin,self.doc)['clean']['status'],'report_failed')
            spawn.assert_not_called()
    def test_wrong_attempt_model_scope_population_and_snapshot_rejected(self):
        self.complete();p=self.phase.out/'MAIN_METRIC_COMPLETE.json';original=p.read_bytes()
        edits=[
            lambda d:d.update(attempt=2),
            lambda d:d.update(attempt=True),
            lambda d:d['header']['model'].update(sha256='0'*64),
            lambda d:d.update(resources_released=True),
            lambda d:d.update(candidate_selection_allowed=True),
            lambda d:d.update(test_read=True),
            lambda d:d['snapshots'].pop('transfer-v4/dev/clean'),
            lambda d:d['snapshots']['decision-v7/dev/clean']['data'].update(sha256='0'*64),
        ]
        for edit in edits:
            d=json.loads(original);edit(d);put(p,d)
            with self.subTest(edit=edit), self.assertRaises(RuntimeError):
                Q.job_ready(self.path,self.doc,self.job)
            p.write_bytes(original)
    def test_output_scope_and_completed_snapshot_mutation_rejected(self):
        r=self.complete();pins=Q.main_metric_inputs(self.path,self.doc,self.job)
        for k in ['candidate_selection_allowed','scientific_acceptance','test_read','resources_released']:
            wrong=copy.deepcopy(r);wrong[k]=True
            with self.subTest(k=k),self.assertRaisesRegex(RuntimeError,'scope or identity'):
                Q.validate_main_metric_output(wrong,self.path,self.doc,self.job,pins)
        target=self.phase.out/'main_metric_phase/decision-v7.jsonl'
        target.write_bytes(target.read_bytes()+b' ')
        with self.assertRaisesRegex(RuntimeError,'snapshot differs'):
            Q.validate_main_metric_output(r,self.path,self.doc,self.job,pins)
    def test_diagnostic_cannot_be_formal_comparison_or_output(self):
        original=copy.deepcopy(self.doc)
        for output in [str(self.phase.out/'main_metric_diagnostic.json'),
                       str(self.root/'diagnostics/clean/selection_report.json')]:
            self.job['output']=output;self.save()
            with self.assertRaises(RuntimeError):Q.verify(self.path,self.pin)
        self.doc=original;self.job=self.doc['jobs'][0]
        self.job['terminal_gate']='full_posttrain_v1';self.save()
        with self.assertRaises(RuntimeError):Q.verify(self.path,self.pin)
        self.job.pop('terminal_gate')
        self.doc['jobs'].append(dict(id='cmp',kind='comparison',candidate=['clean','other'],
                                    baseline='clean',output=str(self.root/'development_comparison.json')))
        self.doc['comparison']=dict(tool=M.__file__,tool_sha256=Q.sha(M.__file__),
                                    selector=M.__file__,selector_sha256=Q.sha(M.__file__))
        self.save()
        with self.assertRaisesRegex(RuntimeError,'dependency is not a report'):
            Q.verify(self.path,self.pin)
    def test_lost_worker_or_preexisting_output_never_restarts(self):
        self.complete();root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        put(root/'START_INTENT.json',dict(command=['old']))
        with patch.object(Q.subprocess,'Popen') as spawn:
            self.assertEqual(Q.tick(self.path,self.pin,self.doc)['clean']['status'],'needs_repair')
            spawn.assert_not_called()
        (root/'START_INTENT.json').unlink()
        Path(self.job['output']).parent.mkdir(parents=True)
        put(Path(self.job['output']),dict(untrusted=True))
        with patch.object(Q.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'fresh report'):Q.worker(self.path,self.pin,'clean')
            spawn.assert_not_called()
    def test_phase_event_and_missed_event_ten_minute_fallback(self):
        self.assertEqual(Q.event_paths(self.doc)[0].name,'MAIN_METRIC_COMPLETE.json')
        wake=Q.CompletionWake([self.phase.out/'MAIN_METRIC_COMPLETE.json'])
        try:
            self.assertIsNotNone(wake.fd)
            put(self.phase.out/'MAIN_METRIC_COMPLETE.json',dict(hint_only=True))
            self.assertEqual(wake.wait(1),'completion_hint')
            with self.assertRaises(RuntimeError):Q.job_ready(self.path,self.doc,self.job)
        finally:wake.close()
        wake=Mock(mode='event_unavailable_poll_fallback')
        wake.wait.return_value='poll_timeout'
        with patch.object(Q,'verify',return_value=self.doc) as verify, \
             patch.object(Q,'CompletionWake',return_value=wake), \
             patch.object(Q,'tick',side_effect=[{'clean':{'status':'waiting_main_metric'}},
                                               {'clean':{'status':'done'}}]):
            Q.watch(self.path,self.pin)
        wake.wait.assert_called_once_with(600);self.assertEqual(verify.call_count,2)
        self.doc['poll_interval_seconds']=599;self.save()
        with self.assertRaisesRegex(RuntimeError,'at least 600'):Q.verify(self.path,self.pin)


if __name__=='__main__':unittest.main()
