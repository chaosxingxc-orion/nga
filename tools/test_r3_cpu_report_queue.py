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
        self.write(root/'ENGINEERING_EVAL_EXIT.json',end)
        self.write(root/'attempts/2/EXIT.json',end)
        self.write(root/'attempts/2/RELEASE.json',{'exit_code':0,'container_id':'exact','run':'run','chip':1,'scientific_acceptance':False})
        self.write(root/'attempts/2/LAUNCH_RECEIPT.json',{'id':'exact'})
        self.write(root/'execution.json',{'run':'run','chip':1,'launcher':'/frozen/launcher.py'})
        self.write(root/'SUPERVISOR_RECEIPT.json',{'command':['python','-P','/frozen/launcher.py','supervise','--plan',str(root/'execution.json'),'--sha256',Q.sha(root/'execution.json'),'--attempt','2']})

    def test_wait_release_failure_and_mismatch(self):
        self.assertEqual(Q.ready(self.job),'waiting_inference')
        root=Path(self.job['eval_out'])
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':1,'exit_code':1})
        self.assertEqual(Q.ready(self.job),'inference_failed')
        self.write(root/'ENGINEERING_EVAL_EXIT.json',{'attempt':1,'exit_code':0})
        self.assertEqual(Q.ready(self.job),'waiting_release')
        self.inference_ready();self.assertEqual(Q.ready(self.job),'ready')
        self.write(root/'attempts/2/EXIT.json',{'attempt':1,'exit_code':0})
        with self.assertRaisesRegex(RuntimeError,'terminal mismatch'):Q.ready(self.job)

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


if __name__=='__main__':unittest.main()
