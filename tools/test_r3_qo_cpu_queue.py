"""External report consumption and queue lifecycle regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('queue',Path(__file__).with_name('r3_cpu_report_queue.py'))
Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)

class ExternalReports(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.refs=[];self.outputs=[]
        for i in range(3):
            base=self.root/str(i);base.mkdir();output=base/'eval/results/selection_report.json'
            job={'id':'report','output':str(output),'eval_out':str(base/'eval')}
            queue=base/'queue.json'
            queue.write_text(json.dumps({'schema':'r3-cpu-report-queue-v1','test_read':False,'scientific_acceptance':False,'jobs':[job]}))
            self.refs.append({'queue':str(queue),'queue_sha256':Q.sha(queue),'job':'report'})
            self.outputs.append(output)
        self.path=self.root/'consumer/queue.json'
        self.job={'id':'qo','kind':'qo_diagnostic','candidate':self.refs[:2],'qo':self.refs[2],
                  'output':str(self.path.parent/'comparisons/qo/qo_transfer_diagnostic.json')}
        self.doc={'jobs':[self.job],'qo_diagnostic':{'tool':'/frozen/diagnostic.py','kev_dir':'/kev','data_root':'/data'},
                  'report_tool':'/report.py','report_tool_sha256':'report-pin','closure':'/closure','closure_sha256':'closure-pin'}

    def complete(self,index,exit_code=0):
        output=self.outputs[index];output.parent.mkdir(parents=True,exist_ok=True);output.write_text('{}')
        end=Path(self.refs[index]['queue']).parent/'jobs/report/EXIT.json';end.parent.mkdir(parents=True,exist_ok=True)
        end.write_text(json.dumps({'exit_code':exit_code,'scientific_acceptance':False,'output_sha256':Q.sha(output)}))

    def test_waits_for_all_external_producers_and_binds_hashes(self):
        self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'waiting_reports')
        for i in range(2):self.complete(i)
        self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'waiting_reports')
        self.complete(2);self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'ready')
        command=Q.report_command(self.doc,self.job)
        self.assertEqual(command[command.index('--candidate')+1:command.index('--qo')],[str(p) for p in self.outputs[:2]])
        self.outputs[2].write_text('{"changed":true}')
        with self.assertRaisesRegex(RuntimeError,'external report changed'):Q.job_ready(self.path,self.doc,self.job)

    def test_changed_producer_and_failed_or_invalid_terminal_refused(self):
        self.complete(0,7)
        self.assertEqual(Q.job_ready(self.path,self.doc,self.job),'comparison_blocked')
        self.complete(0,False)
        with self.assertRaisesRegex(RuntimeError,'terminal scope'):Q.job_ready(self.path,self.doc,self.job)
        Path(self.refs[1]['queue']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'external queue changed'):Q.external_report(self.refs[1])

    def test_output_must_bind_exact_inputs_and_scope(self):
        for i in range(3):self.complete(i)
        result={'schema':'r3-qo-transfer-dev-diagnostic-v1','scientific_acceptance':False,'test_read':False,
                'adoption_authorized':False,'inputs':{str(p):Q.sha(p) for p in self.outputs}}
        Q.validate_qo_output(result,self.job)
        for field in ('test_read','adoption_authorized','inputs'):
            bad=copy.deepcopy(result);bad[field]=True
            with self.assertRaises(RuntimeError):Q.validate_qo_output(bad,self.job)

    def test_existing_intent_blocks_duplicate_and_external_producers_never_spawn(self):
        for i in range(3):self.complete(i)
        root=Q.workdir(self.path,self.job);root.mkdir(parents=True)
        (root/'START_INTENT.json').write_text('{}')
        with patch.object(Q.subprocess,'Popen') as launch:
            states=Q.tick(self.path,'pin',self.doc);launch.assert_not_called()
        self.assertEqual(states['qo']['status'],'needs_repair')
        self.assertEqual(len(self.doc['jobs']),1)

    def test_real_child_failure_creates_terminal(self):
        for i in range(3):self.complete(i)
        tool=self.root/'fail.py';tool.write_text('raise SystemExit(7)')
        self.doc['qo_diagnostic']['tool']=str(tool)
        Q.workdir(self.path,self.job).mkdir(parents=True)
        with patch.object(Q,'verify',return_value=self.doc):
            self.assertEqual(Q.worker(self.path,'pin','qo'),7)
        self.assertEqual(Q.load(Q.workdir(self.path,self.job)/'EXIT.json')['exit_code'],7)
        self.assertEqual(Q.observe(self.path,'pin',self.job,self.doc)['status'],'report_failed')

if __name__=='__main__':unittest.main()
