import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

s=importlib.util.spec_from_file_location('cpu_queue',Path(__file__).with_name('r3_cpu_report_queue.py'))
Q=importlib.util.module_from_spec(s);s.loader.exec_module(Q)


class CPUQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'queue.json';self.pin='pin'
        self.job={'id':'one','eval_out':str(self.root/'eval'),'output':str(self.root/'selection_report.json')}
        self.doc={'jobs':[self.job],'closure':str(self.root/'closure'),'report_tool':str(self.root/'report.py')}

    def write(self,p,value):
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def inference_ready(self):
        root=Path(self.job['eval_out']);end={'attempt':2,'exit_code':0}
        self.write(root/'attempts/1/EXIT.json',{'attempt':1,'exit_code':7})
        self.write(root/'attempts/1/RELEASE.json',{'exit_code':7,'container_id':'prior','run':'run','chip':1,'scientific_acceptance':False})
        self.write(root/'attempts/1/LAUNCH_RECEIPT.json',{'id':'prior'})
        self.write(root/'ENGINEERING_EVAL_EXIT.json',end)
        self.write(root/'attempts/2/EXIT.json',end)
        self.write(root/'attempts/2/RELEASE.json',{'exit_code':0,'container_id':'exact','run':'run','chip':1,'scientific_acceptance':False})
        self.write(root/'attempts/2/LAUNCH_RECEIPT.json',{'id':'exact'})
        self.write(root/'execution.json',{'run':'run','chip':1,'launcher':'/frozen/launcher.py'})
        self.write(root/'SUPERVISOR_RECEIPT.json',{'command':['python','-P','/frozen/launcher.py','supervise','--plan',str(root/'execution.json'),'--sha256',Q.sha(root/'execution.json'),'--attempt','2']})

    def test_wait_release_failure_and_mismatch(self):
        self.assertEqual(Q.ready(self.job),'waiting_inference')
        root=Path(self.job['eval_out'])
        self.inference_ready()
        end={'attempt':2,'exit_code':7}
        self.write(root/'ENGINEERING_EVAL_EXIT.json',end)
        self.write(root/'attempts/2/EXIT.json',end)
        (root/'attempts/2/RELEASE.json').unlink()
        self.assertEqual(Q.ready(self.job),'waiting_release')
        self.write(root/'attempts/2/RELEASE.json',{'exit_code':7,'container_id':'exact','run':'run','chip':1,'scientific_acceptance':False})
        self.assertEqual(Q.ready(self.job),'inference_failed')
        self.inference_ready();self.assertEqual(Q.ready(self.job),'ready')
        self.write(root/'attempts/2/EXIT.json',{'attempt':1,'exit_code':0})
        with self.assertRaisesRegex(RuntimeError,'terminal mismatch'):Q.ready(self.job)

    def test_r0_job_uses_same_release_gate_and_serial_lane(self):
        self.job.update(kind='r0_report',output=str(Path(self.job['eval_out'])/'R0RESCORE_COMPLETE.json'))
        self.doc['r0_report']={'tool':'/frozen/r0.py','preparation':'/frozen/PREPARATION.json',
                              'preparation_sha256':'prep-pin','execution_sha256':'exec-pin'}
        self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'waiting_inference')
        self.inference_ready();self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'ready')
        command=Q.report_command(self.doc,self.job)
        self.assertEqual(command[command.index('--run')+1],self.job['eval_out'])
        self.assertEqual(command[command.index('--execution-sha256')+1],'exec-pin')
        with patch.object(Q,'observe',return_value={'status':'reporting','pid':9}),patch.object(Q.subprocess,'Popen') as spawn:
            Q.tick(self.path,self.pin,self.doc);spawn.assert_not_called()

    def test_real_r0_worker_requires_hashed_complete_evidence(self):
        self.inference_ready()
        self.job.update(kind='r0_report',output=str(Path(self.job['eval_out'])/'R0RESCORE_COMPLETE.json'))
        tool=self.root/'r0.py'
        tool.write_text('''import sys,json,hashlib
from pathlib import Path
r=Path(sys.argv[sys.argv.index('--run')+1]);(r/'instruct').mkdir(exist_ok=True)
v=r/'R0RESCORE_VERIFIED.json';v.write_text('{}')
p=r/'instruct/report.json';p.write_text('{}')
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
(r/'R0RESCORE_COMPLETE.json').write_text(json.dumps({'exit_code':0,'run_of_record':True,'limit_groups':0,'scientific_acceptance':False,'candidate_test_read':False,'verified':str(v),'verified_sha256':sha(v),'report_sha256':sha(p)}))
''')
        self.doc['r0_report']={'tool':str(tool),'preparation':'/frozen/prep','preparation_sha256':'pin','execution_sha256':'pin'}
        Q.workdir(self.path,self.job).mkdir(parents=True)
        with patch.object(Q,'verify',return_value=self.doc):self.assertEqual(Q.worker(self.path,self.pin,'one'),0)
        self.assertEqual(Q.observe(self.path,self.pin,self.job,self.doc)['status'],'done')

    def test_previous_failure_during_new_attempt_waits_then_accepts_success(self):
        self.inference_ready();root=Path(self.job['eval_out'])
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':1,'exit_code':7})
        self.assertEqual(Q.ready(self.job),'waiting_inference')
        # A waiting retry must not close the queue, even when it is the only job.
        with patch.object(Q,'verify',return_value=self.doc),patch.object(Q.time,'sleep',side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):Q.watch(self.path,self.pin)
        self.assertFalse((self.root/'DONE.json').exists())
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':2,'exit_code':0})
        self.assertEqual(Q.ready(self.job),'ready')

    def test_failed_inference_remains_observed_for_later_retry(self):
        with patch.object(Q,'verify',return_value=self.doc),patch.object(Q,'tick',return_value={'one':{'status':'inference_failed'}}),patch.object(Q.time,'sleep',side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):Q.watch(self.path,self.pin)
        self.assertFalse((self.root/'DONE.json').exists())

    def test_failed_terminal_requires_matching_release_and_prior_history(self):
        self.inference_ready();root=Path(self.job['eval_out'])
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':2,'exit_code':7})
        self.write(root/'attempts/2/EXIT.json',{'attempt':2,'exit_code':7})
        with self.assertRaisesRegex(RuntimeError,'release mismatch'):Q.ready(self.job)
        self.inference_ready()
        self.write(root/'attempts/1/EXIT.json',{'attempt':1,'exit_code':0})
        with self.assertRaisesRegex(RuntimeError,'retry after successful'):Q.ready(self.job)

    def test_future_terminal_and_wrong_plan_pin_refused(self):
        self.inference_ready();root=Path(self.job['eval_out'])
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':3,'exit_code':0})
        with self.assertRaisesRegex(RuntimeError,'generation differs'):Q.ready(self.job)
        self.inference_ready();plan=Q.load(root/'execution.json');plan['chip']=5;self.write(root/'execution.json',plan)
        with self.assertRaisesRegex(RuntimeError,'generation differs'):Q.ready(self.job)

    def test_ready_later_job_runs_without_waiting_first(self):
        later=dict(self.job,id='two',eval_out=str(self.root/'later'))
        doc={'jobs':[dict(self.job,id='first'),later]}
        with patch.object(Q,'observe',side_effect=[{'status':'waiting_inference'},{'status':'ready'}]),patch.object(Q.subprocess,'Popen',return_value=Mock(pid=55)) as popen:
            result=Q.tick(self.path,self.pin,doc)
        self.assertEqual(result['two']['status'],'reporting');self.assertEqual(popen.call_count,1)
        self.assertIn('--job',popen.call_args.args[0]);self.assertEqual(popen.call_args.args[0][-1],'two')
        self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_existing_worker_and_intent_never_duplicate(self):
        self.inference_ready();root=Q.workdir(self.path,self.job)
        self.write(root/'WORKER.json',{'pid':55,'command':Q.worker_command(self.path,self.pin,'one')})
        for live,want in [(True,'reporting'),(False,'needs_repair')]:
            with patch.object(Q,'process_matches',return_value=live),patch.object(Q.subprocess,'Popen') as popen:
                states=Q.tick(self.path,self.pin,self.doc)
            self.assertEqual(states['one']['status'],want);popen.assert_not_called()
        (root/'WORKER.json').unlink();self.write(root/'START_INTENT.json',{})
        self.assertEqual(Q.observe(self.path,self.pin,self.job)['status'],'needs_repair')

    def test_pid_reuse_is_not_live(self):
        proc=self.root/'proc';(proc/'55').mkdir(parents=True)
        (proc/'55/cmdline').write_bytes(b'python\0unrelated\0')
        self.assertFalse(Q.process_matches({'pid':55,'command':['python','report']},proc))
        self.assertTrue(Q.process_matches({'pid':55,'command':['python','unrelated']},proc))

    def test_real_report_child_success_and_changed_output_refused(self):
        self.inference_ready();root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        script=Path(self.doc['report_tool']);script.write_text('import sys,json\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index("--output")+1]);p.write_text(json.dumps({"schema":"r3-selection-report-v1","scientific_acceptance":False}))\n')
        with patch.object(Q,'verify',return_value=self.doc):self.assertEqual(Q.worker(self.path,self.pin,'one'),0)
        self.assertEqual(Q.observe(self.path,self.pin,self.job)['status'],'done')
        Path(self.job['output']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'report changed'):Q.observe(self.path,self.pin,self.job)

    def test_real_failed_child_never_done(self):
        self.inference_ready();root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        Path(self.doc['report_tool']).write_text('raise SystemExit(7)\n')
        with patch.object(Q,'verify',return_value=self.doc):self.assertEqual(Q.worker(self.path,self.pin,'one'),7)
        self.assertEqual(Q.observe(self.path,self.pin,self.job)['status'],'report_failed')
        self.assertFalse(Path(self.job['output']).exists())

    def comparison_fixture(self):
        reports = [dict(self.job, id=name, output=str(self.root/name/'selection_report.json'))
                   for name in ('s2','s3','k0')]
        job = {'id':'comparison','kind':'comparison','candidate':['s2','s3'],'baseline':'k0',
               'output':str(self.root/'development_comparison.json')}
        doc = {**self.doc, 'jobs':reports+[job], 'comparison':{'tool':str(self.root/'compare.py'),
               'selector':'/frozen/select.py','selector_sha256':'pin'}, 'report_tool_sha256':'report-pin'}
        for report in reports:
            self.write(Path(report['output']), {'synthetic':True})
            self.write(Q.workdir(self.path,report)/'EXIT.json',{'exit_code':0,'output_sha256':Q.sha(report['output'])})
        return doc,job,reports

    def test_comparison_waits_for_all_report_terminals_and_hashes(self):
        doc,job,reports=self.comparison_fixture()
        self.assertEqual(Q.job_ready(self.path,doc,job),'ready')
        end=Q.workdir(self.path,reports[0])/'EXIT.json';original=end.read_bytes();end.unlink()
        self.assertEqual(Q.job_ready(self.path,doc,job),'waiting_reports')
        self.write(end,{'exit_code':7})
        self.assertEqual(Q.job_ready(self.path,doc,job),'comparison_blocked')
        end.write_bytes(original);Path(reports[0]['output']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'report changed'):Q.job_ready(self.path,doc,job)

    def test_gated_comparison_waits_for_r0_and_passes_exact_run(self):
        doc,job,_=self.comparison_fixture()
        r0={'id':'r0','kind':'r0_report','eval_out':str(self.root/'r0'),
            'output':str(self.root/'r0/R0RESCORE_COMPLETE.json')}
        doc['jobs'].append(r0);job['r0_report']='r0'
        doc['r0_report']={'execution_sha256':'external-pin'}
        self.assertEqual(Q.job_ready(self.path,doc,job),'waiting_reports')
        self.write(Path(r0['output']),{'exit_code':0})
        self.write(Q.workdir(self.path,r0)/'EXIT.json',{'exit_code':0,'output_sha256':Q.sha(r0['output'])})
        self.assertEqual(Q.job_ready(self.path,doc,job),'ready')
        command=Q.report_command(doc,job)
        self.assertEqual(command[command.index('--r0-run')+1],r0['eval_out'])
        self.assertEqual(command[command.index('--r0-execution-sha256')+1],'external-pin')
        Path(r0['output']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'dependency report changed'):Q.job_ready(self.path,doc,job)

    def test_real_comparison_worker_uses_common_serial_cpu_lane(self):
        doc,job,reports=self.comparison_fixture();root=Q.workdir(self.path,job);root.mkdir(parents=True)
        Path(doc['comparison']['tool']).write_text('import sys,json\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index("--output")+1]);p.write_text(json.dumps({"schema":"r3-development-comparison-v1","scientific_acceptance":False,"test_read":False}))\n')
        with patch.object(Q,'verify',return_value=doc):self.assertEqual(Q.worker(self.path,self.pin,job['id']),0)
        self.assertEqual(Q.observe(self.path,self.pin,job,doc)['status'],'done')
        command=Q.report_command(doc,job)
        self.assertEqual(command[command.index('--candidate')+1:command.index('--baseline')],
                         [reports[0]['output'],reports[1]['output']])
        with patch.object(Q,'observe',side_effect=[{'status':'reporting'},{'status':'done'},{'status':'done'},{'status':'ready'}]),patch.object(Q.subprocess,'Popen') as popen:
            Q.tick(self.path,self.pin,doc)
        popen.assert_not_called()


if __name__=='__main__':unittest.main()
