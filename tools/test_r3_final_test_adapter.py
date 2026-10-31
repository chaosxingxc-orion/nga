"""Generated guard and recovery entry integration; synthetic data/scoring only."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).parent
def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
A=module('r3_final_test_adapter');P=module('r3_final_eval_prepare')


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.round=self.root/'round';self.round.mkdir()
        self.final=self.round/'FINAL.json';self.final.write_text('{}')
        self.owner=dict(model_sha256='a'*64,execution_sha256='b'*64,
            final_sha256=hashlib.sha256(self.final.read_bytes()).hexdigest(),run_dir=str(self.root/'out'))
        self.args=SimpleNamespace(out=self.owner['run_dir'],round_dir=str(self.round),adapter=None,
            model_path=str(self.root/'model'),partitions='calibration,test',stages='k',limit=0,
            limit_groups=0,shard=0,num_shards=1,k_only='',b4_base=None,unit_tag='',dtype='float32',
            no_hf32=True,require_record_grade=True,device='npu')
        self.identity=dict(path=self.args.model_path,sha256='a'*64)
        self.core=SimpleNamespace(TestLockRefusal=ValueError,
            sha256_file=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest())
        self.verifier=Mock(return_value={'verified':True})
        self.tl=SimpleNamespace(model_identity=Mock(return_value=self.identity),
            authorize_test_read=Mock(side_effect=lambda identity,suite,split,rd:SimpleNamespace(identity=identity,suite=suite,split=split)),
            verify_test_result=self.verifier)
        self.core.KEV_DIR=str(self.root/'synthetic-data')
        self.tl.C=self.core
        metric_check=patch.object(A.M,'verify',return_value={'scope':'control-flow fixture'})
        metric_check.start();self.addCleanup(metric_check.stop)
        self.report={'test_publication':{'state':'unpublished'},'track_k':{'operator_fit':{'n':100},'partitions':{
            'decision-v7/calibration':{'n':100},
            'decision-v7/test':{'headline':{'n':1200,'kev_rule_accuracy':.75}},
            'transfer-v4/test':{'headline':{'n':656,'kev_rule_accuracy':.625}}}}}
        self.producer=Mock(return_value=self.report)
        env=dict(C=self.core,TL=self.tl,_run_full_deferred=self.producer)
        exec(compile(P.BRIDGE,'<generated-bridge>','exec'),env)
        recovery=dict(C=self.core,json=json,tempfile=tempfile,FINAL_NAME='FINAL.json',
            model_identity=self.tl.model_identity,_abs=lambda p:str(Path(p).absolute()),
            is_named=lambda doc,identity:True,read_final=lambda rd:{},
            TestTicket=lambda identity,suite,split,token:SimpleNamespace(identity=identity,suite=suite,split=split),
            _TOKEN=object(),verify_test_result=self.verifier)
        exec(compile(P.RECOVERY,'<generated-recovery>','exec'),recovery)
        self.tl.verify_reserved_test_result=recovery['verify_reserved_test_result']
        self.evaluator=SimpleNamespace(run_guarded_test=env['run_guarded_test'],TL=self.tl)
        self.admission=Mock()

    def run_case(self):
        return A.run(self.args,Mock(),self.evaluator,owner=self.owner,validate_admission=self.admission)

    def test_complete_and_recover_never_reauthorize_or_rescore(self):
        self.run_case();self.run_case()
        self.producer.assert_called_once()
        self.assertEqual(self.tl.authorize_test_read.call_count,2)
        self.assertEqual(len((self.round/'TEST-READS.log').read_text().splitlines()),2)
        self.assertGreaterEqual(self.verifier.call_count,6)

    def test_first_log_committed_second_pending_recovers_with_generated_verifier(self):
        original=A.L.CompletionLog.append_line
        def die(log,f,line):
            original(log,f,line);raise RuntimeError('simulated process interruption')
        with patch.object(A.L.CompletionLog,'append_line',die):
            with self.assertRaises(RuntimeError):self.run_case()
        self.assertEqual(len((self.round/'TEST-READS.log').read_text().splitlines()),1)
        self.run_case()
        self.producer.assert_called_once();self.assertEqual(self.tl.authorize_test_read.call_count,2)
        self.assertEqual(len((self.round/'TEST-READS.log').read_text().splitlines()),2)

    def test_changed_final_or_report_refused_on_recovery(self):
        self.run_case();self.final.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'FINAL changed'):self.run_case()
        self.final.write_text('{}')
        report=Path(self.args.out)/'TEST-PRODUCER-REPORT.json';doc=json.loads(report.read_text())
        doc['track_k']['operator_fit']['n']=1;report.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'producer report changed'):self.run_case()
        self.producer.assert_called_once()

    def test_failure_in_recovery_source_verification_never_republishes(self):
        self.run_case();before=(self.round/'TEST-READS.log').read_bytes()
        self.verifier.side_effect=ValueError('producer provenance mismatch')
        with self.assertRaisesRegex(ValueError,'provenance mismatch'):self.run_case()
        self.assertEqual(before,(self.round/'TEST-READS.log').read_bytes())
        self.producer.assert_called_once()


if __name__=='__main__':unittest.main()
