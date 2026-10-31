"""Full original-source and metric verification wired into publication recovery."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

fixture=load('metric_publication_fixture',HERE/'test_r3_final_metrics.py')


class Publication(unittest.TestCase):
    def setUp(self):
        # Reuse the original-producer fixture, not its test methods.
        self.case=fixture.Metrics();self.case.setUp();self.addCleanup(self.case.doCleanups)
        c=self.case;self.root=c.root;self.run=c.run;self.round=self.root/'round'
        P=load('publication_prepare',HERE/'r3_final_eval_prepare.py')
        P.prepare_testlock(fixture.SOURCE/'testlock_r3.py',self.root/'testlock_r3.py')
        c.C.KEV_DIR=str(c.data)
        self.TL=load('testlock_r3',self.root/'testlock_r3.py')
        PV=load('provenance_r3',fixture.SOURCE/'provenance_r3.py')
        self.A=load('publication_adapter',HERE/'r3_final_test_adapter.py')
        self.model=self.root/'model';self.model.mkdir()
        (self.model/'model.safetensors').write_bytes(b'synthetic identity bytes')
        (self.model/'.complete').write_text('synthetic-revision\n')
        self.identity=self.TL.model_identity(str(self.model),round_dir=str(self.root/'hash-cache'))
        final=self.round/'FINAL.json';final.write_text(json.dumps({'models':[self.identity]}))
        self.owner=dict(model_sha256=self.identity['sha256'],execution_sha256='b'*64,
            final_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),run_dir=str(self.run))
        self.args=SimpleNamespace(out=str(self.run),round_dir=str(self.round),adapter=None,
            model_path=str(self.model),partitions='calibration,test',stages='k',limit=0,
            limit_groups=0,shard=0,num_shards=1,k_only='',b4_base=None,unit_tag='',dtype='float32',
            no_hf32=True,require_record_grade=True,device='npu')
        paths=list(c.scores)
        for path in paths:
            rows=c.C.read_jsonl(path)
            c.C.write_jsonl(path,[PV.stamp(r,self.identity['sha256']) for r in rows])
        (self.run/'RUN_IDENTITY.json').write_text(json.dumps({'model_sha256':self.identity['sha256']}))
        PV.write_unit_manifest(str(self.run),'synthetic',self.identity['sha256'],
            {'record_grade':True,'mode':'rightpad','dtype':'float32','token_budget':16384,'hf32':{'hf32':False}},paths)
        report=copy.deepcopy(c.report);report['header']['model']=self.identity
        report['test_publication']={'state':'unpublished'}
        self.producer=Mock(return_value=report)
        env=dict(C=c.C,TL=self.TL,_run_full_deferred=self.producer)
        exec(compile(P.BRIDGE,'<generated-bridge>','exec'),env)
        self.evaluator=SimpleNamespace(run_guarded_test=env['run_guarded_test'],TL=self.TL)

    def execute(self):
        return self.A.run(self.args,Mock(),self.evaluator,owner=self.owner,validate_admission=lambda:None)

    def test_source_and_full_metrics_verify_before_and_after_partial_commit(self):
        original=self.A.L.CompletionLog.append_line
        def interrupted(log,f,line):original(log,f,line);raise RuntimeError('interrupt')
        with patch.object(self.A.L.CompletionLog,'append_line',interrupted):
            with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(len(self.TL.read_log(str(self.round))),1)
        self.execute();self.producer.assert_called_once()
        self.assertEqual(len(self.TL.read_log(str(self.round))),2)

    def test_wrong_secondary_blocks_all_publication(self):
        self.producer.return_value['track_k']['partitions']['transfer-v4/test']['secondary']['operator']['accuracy']=.123
        with self.assertRaisesRegex(ValueError,'reconstructed metric differs'):self.execute()
        self.assertEqual(self.TL.read_log(str(self.round)),[])
        self.assertFalse((self.run/'TEST-STAGED-RESULTS.json').exists())

    def test_recovery_rechecks_metrics_even_when_staged_hashes_are_consistent(self):
        # Stop before any append, retaining the verified staged evidence.
        with patch.object(self.A.L.CompletionLog,'append',side_effect=RuntimeError('before commit')):
            with self.assertRaises(RuntimeError):self.execute()
        report_path=self.run/'TEST-PRODUCER-REPORT.json';report=json.loads(report_path.read_text())
        report['track_k']['operator_fit']['fitted']={'forged':True}
        report_path.write_text(json.dumps(report))
        staged_path=self.run/'TEST-STAGED-RESULTS.json';staged=json.loads(staged_path.read_text())
        for result in staged['results'].values():result['producer_report_sha256']=self.A.G.digest(report)
        staged_path.write_text(json.dumps(staged))
        with self.assertRaisesRegex(ValueError,'operator fit differs'):self.execute()
        self.producer.assert_called_once()
        self.assertEqual(self.TL.read_log(str(self.round)),[])


if __name__=='__main__':unittest.main()
