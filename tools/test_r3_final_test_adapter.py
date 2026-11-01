"""Generated guard and recovery entry integration; synthetic data/scoring only."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).parent
def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
A=module('r3_final_test_adapter');P=module('r3_final_eval_prepare');F=module('test_r3_final_metrics')


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.round=self.root/'round';self.round.mkdir()
        self.final=self.round/'FINAL.json';self.final.write_text('{}')
        self.owner=dict(model_sha256='a'*64,execution_sha256='b'*64,
            final_sha256=hashlib.sha256(self.final.read_bytes()).hexdigest(),run_dir=str(self.root/'out'))
        self.args=SimpleNamespace(out=self.owner['run_dir'],round_dir=str(self.round),adapter=None,
            arm='K0',model_path=str(self.root/'model'),partitions='calibration,test',stages='k',limit=0,
            limit_groups=0,shard=0,num_shards=1,k_only='',b4_base=None,unit_tag='',dtype='float32',
            no_hf32=True,require_record_grade=True,device='npu')
        self.identity=dict(path=self.args.model_path,sha256='a'*64,kind='checkpoint',base_path=self.args.model_path,base_revision='synthetic')
        self.prompt=SimpleNamespace(PROMPT_VERSION='fixture',PROMPT_FORMAT='fixture')
        prompt_context=patch.dict(sys.modules, {'prompt':self.prompt})
        prompt_context.start();self.addCleanup(prompt_context.stop)
        self.core=SimpleNamespace(TestLockRefusal=ValueError,
            sha256_file=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest())
        self.verifier=Mock(return_value={'verified':True})
        self.tl=SimpleNamespace(model_identity=Mock(return_value=self.identity),
            authorize_test_read=Mock(side_effect=lambda identity,suite,split,rd:SimpleNamespace(identity=identity,suite=suite,split=split)),
            verify_test_result=self.verifier)
        self.core.KEV_DIR=str(self.root/'synthetic-data')
        self.tl.C=self.core
        def metrics(ticket,run_dir,*,kev_dir,report,provenance_verifier):
            headline=report['track_k']['partitions'][ticket.suite+'/test']['headline']
            verified=provenance_verifier(ticket,headline['n'],headline['kev_rule_accuracy'],run_dir,kev_dir=kev_dir)
            return {'scope':'control-flow fixture','source_verification':verified}
        metric_check=patch.object(A.M,'verify',side_effect=metrics)
        metric_check.start();self.addCleanup(metric_check.stop)
        self.report={'header':F.header(self.identity,'K0',self.prompt),'test_publication':{'state':'unpublished'},'track_k':{'operator_fit':{'n':100},'partitions':{
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
        self.evaluator=SimpleNamespace(run_guarded_test=env['run_guarded_test'],TL=self.tl,P=self.prompt)
        self.admission=Mock()

    def run_case(self):
        return A.run(self.args,Mock(),self.evaluator,owner=self.owner,validate_admission=self.admission)

    def test_complete_and_recover_never_reauthorize_or_rescore(self):
        self.run_case();self.run_case()
        self.producer.assert_called_once()
        self.assertEqual(self.tl.authorize_test_read.call_count,2)
        self.assertEqual(len((self.round/'TEST-READS.log').read_text().splitlines()),2)
        self.assertGreaterEqual(self.verifier.call_count,6)

    def test_supplement_retained_on_normal_and_recovery_paths(self):
        def metrics(ticket,*args,**kwargs):
            self.assertIs(kwargs['provenance_verifier'],self.verifier)
            return {'reference_metrics':{'suite':ticket.suite,'synthetic':True},'source_verification':{}}
        with patch.object(A.M,'verify',side_effect=metrics),patch.dict(sys.modules,{'r3_final_metrics':A.M}):
            first=self.run_case();second=self.run_case()
        expected={s:{'suite':s,'synthetic':True} for s in ('decision-v7','transfer-v4')}
        self.assertEqual(first['reference_metrics'],expected)
        self.assertEqual(second['reference_metrics'],expected)
        self.producer.assert_called_once()

    def control(self,arm):
        self.args.arm=arm
        self.args.model_path=str(self.root/('Qwen__Qwen3.5-0.8B-Base' if arm=='K1-QO' else 'Qwen__Qwen3.5-0.8B'))
        self.args.adapter=str(self.root/'adapter')
        self.identity.update(path=self.args.adapter,base_path=self.args.model_path,kind='lora-adapter-unmerged')
        self.report['header']=F.header(self.identity,arm,self.prompt)

    def test_qo_complete_and_recover_never_rescore(self):
        self.control('K1-QO');self.test_complete_and_recover_never_reauthorize_or_rescore()

    def test_pt_complete_and_recover_never_rescore(self):
        self.control('K1-PT');self.test_complete_and_recover_never_reauthorize_or_rescore()

    def refused_header(self,pattern):
        with self.assertRaisesRegex(ValueError,pattern):self.run_case()
        self.assertFalse((Path(self.args.out)/'TEST-PRODUCER-REPORT.json').exists())
        self.verifier.assert_not_called()

    def test_wrong_arm_never_publishes(self):
        self.report['header']['arm']='K1';self.refused_header('arm differs')

    def test_qo_wrong_input_mode_never_publishes(self):
        self.control('K1-QO')
        self.report['header']['primary_input_mode']='full';self.refused_header('input mode')

    def test_pt_wrong_base_never_publishes(self):
        self.control('K1-PT')
        self.report['header']['model']=dict(self.identity,base_path=str(self.root/'wrong-base'))
        self.refused_header('control base')

    def test_wrong_scorer_identity_never_publishes(self):
        self.report['header']['scorer']['model_path']=str(self.root/'wrong-model')
        self.refused_header('scorer model/adapter')

    def test_recovery_validates_header_before_source_verifier(self):
        with patch.object(A.L.CompletionLog,'append',side_effect=RuntimeError('interrupt')):
            with self.assertRaises(RuntimeError):self.run_case()
        path=Path(self.args.out)/'TEST-PRODUCER-REPORT.json';report=json.loads(path.read_text())
        report['header']['primary_input_mode']='drop';path.write_text(json.dumps(report))
        staged_path=Path(self.args.out)/'TEST-STAGED-RESULTS.json';staged=json.loads(staged_path.read_text())
        for result in staged['results'].values():result['producer_report_sha256']=A.G.digest(report)
        staged_path.write_text(json.dumps(staged));self.verifier.reset_mock()
        with self.assertRaisesRegex(ValueError,'input mode'):self.run_case()
        self.verifier.assert_not_called()

    def test_direct_recovery_checks_header_before_source_read(self):
        with patch.object(A.L.CompletionLog,'append',side_effect=RuntimeError('interrupt')):
            with self.assertRaises(RuntimeError):self.run_case()
        path=Path(self.args.out)/'TEST-PRODUCER-REPORT.json';report=json.loads(path.read_text())
        report['header']['primary_input_mode']='drop';path.write_text(json.dumps(report))
        staged_path=Path(self.args.out)/'TEST-STAGED-RESULTS.json';staged=json.loads(staged_path.read_text())
        for result in staged['results'].values():result['producer_report_sha256']=A.G.digest(report)
        staged_path.write_text(json.dumps(staged));self.verifier.reset_mock()
        # Bypass only the outer duplicate check to exercise generated recovery.
        original=A.M.validate_header
        calls=[]
        def outer_then_real(header, **kwargs):
            calls.append(header)
            if len(calls)==1:return {}
            return original(header, **kwargs)
        with patch.object(A.M,'validate_header',side_effect=outer_then_real):
            with self.assertRaisesRegex(ValueError,'input mode'):self.run_case()
        self.assertEqual(len(calls),2)
        self.verifier.assert_not_called()

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
