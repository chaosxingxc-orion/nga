"""Actual frozen source verifier against temporary synthetic populations.

No NPU/model execution, real test datasets or review approval. These checks use
the original provenance, population, model hashing and headline implementations.
"""
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).parent
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value


class SourceVerification(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen CPU source not installed')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data';self.run=self.root/'run'
        self.round=self.root/'round';self.round.mkdir();self.run.mkdir()
        modules=patch.dict(sys.modules);modules.start();self.addCleanup(modules.stop)
        original_path=list(sys.path);self.addCleanup(lambda:sys.path.__setitem__(slice(None),original_path))
        sys.path.insert(0,str(SOURCE))
        self.C=load('core_r3',SOURCE/'core_r3.py');self.C.KEV_DIR=str(self.data)
        self.P=load('prepare_source_test',HERE/'r3_final_eval_prepare.py')
        self.P.prepare_testlock(SOURCE/'testlock_r3.py',self.root/'testlock_r3.py')
        self.TL=load('testlock_r3',self.root/'testlock_r3.py')
        self.PV=load('provenance_r3',SOURCE/'provenance_r3.py')
        load('degenerate_r3',SOURCE/'degenerate_r3.py')
        load('prechecks_r3',SOURCE/'prechecks_r3.py')
        load('selection_evidence_r3',SOURCE/'selection_evidence_r3.py')
        self.A=load('final_source_adapter',HERE/'r3_final_test_adapter.py')
        # This suite isolates original provenance checks. Full metric and source
        # integration is covered separately by test_r3_final_publication.py.
        metric_check=patch.object(self.A.M,'verify',return_value={'scope':'source-only fixture'})
        metric_check.start();self.addCleanup(metric_check.stop)
        self.model=self.root/'model';self.model.mkdir()
        (self.model/'weights.safetensors').write_bytes(b'synthetic bytes, never loaded as a model')
        (self.model/'.complete').write_text('synthetic-revision\n')
        self.identity=self.TL.model_identity(str(self.model),round_dir=str(self.root/'identity-cache'))
        final=self.round/'FINAL.json';final.write_text(json.dumps({'models':[self.identity]}))
        self.owner=dict(model_sha256=self.identity['sha256'],execution_sha256='b'*64,
            final_sha256=self.C.sha256_file(str(final)),run_dir=str(self.run))
        self.args=SimpleNamespace(out=str(self.run),round_dir=str(self.round),adapter=None,
            model_path=str(self.model),partitions='calibration,test',stages='k',limit=0,
            limit_groups=0,shard=0,num_shards=1,k_only='',b4_base=None,unit_tag='',dtype='float32',
            no_hf32=True,require_record_grade=True,device='npu')
        self.paths=[];self.manifest={'suites':{}};parts={'decision-v7/calibration':{'n':1}}
        for suite,n in [('decision-v7',1200),('transfer-v4',656)]:
            rows=[dict(kev={'id':str(i),'qindex':0},levels=[{'id':'a','name':'A'},{'id':'b','name':'B'}],
                gold='a',qname='synthetic',source='fixture',level_type='nominal') for i in range(n)]
            variants=[dict(rows[0],kev={'id':'variant','qindex':0})]
            outputs={}
            for kind,population in [('clean',rows),('variants',variants)]:
                path=self.C.partition_path(suite,'test',kind=='variants',str(self.data))
                self.C.write_jsonl(path,population)
                outputs[kind]={'path':str(Path(path).relative_to(self.data)),'sha256':self.C.sha256_file(path)}
            self.manifest['suites'][suite]={'partitions':{'test':{'outputs':outputs}}}
            for kind,population in [('clean',rows),('variants',variants),('question_only',rows),('empty_input',rows)]:
                path=self.C.k_readout_path(str(self.run),suite,'test',kind)
                readouts=[self.PV.stamp(self.C.readout_row(row,[0.,-1.] if i%2==0 else [-1.,0.]),self.identity['sha256'])
                          for i,row in enumerate(population)]
                self.C.write_jsonl(path,readouts);self.paths.append(path)
            parts[suite+'/test']={'headline':{'n':n,'kev_rule_accuracy':.5}}
        (self.data/'manifest.json').write_text(json.dumps(self.manifest))
        (self.run/'RUN_IDENTITY.json').write_text(json.dumps({'model_sha256':self.identity['sha256']}))
        self.refresh_provenance()
        report={'test_publication':{'state':'unpublished'},'track_k':{'operator_fit':{'synthetic':True},'partitions':parts}}
        self.producer=Mock(return_value=report)
        env=dict(C=self.C,TL=self.TL,_run_full_deferred=self.producer)
        exec(compile(self.P.BRIDGE,'<generated-bridge>','exec'),env)
        self.evaluator=SimpleNamespace(run_guarded_test=env['run_guarded_test'],TL=self.TL)
        self.opened=[];original_open=builtins.open
        def guarded_open(path,*args,**kwargs):
            if isinstance(path,(str,Path)) and str(path).endswith('.jsonl'):
                resolved=Path(path).resolve()
                if not resolved.is_relative_to(self.root):raise AssertionError('real dataset access refused')
                self.opened.append(str(resolved))
            return original_open(path,*args,**kwargs)
        guard=patch('builtins.open',guarded_open);guard.start();self.addCleanup(guard.stop)

    def refresh_provenance(self):
        desc={'record_grade':True,'mode':'rightpad','dtype':'float32','token_budget':16384,'hf32':{'hf32':False}}
        self.PV.write_unit_manifest(str(self.run),'synthetic',self.identity['sha256'],desc,self.paths)

    def execute(self):
        return self.A.run(self.args,Mock(),self.evaluator,owner=self.owner,validate_admission=lambda:None)

    def test_original_source_checks_and_half_publication_recovery(self):
        original=self.A.L.CompletionLog.append_line
        def interrupted(log,f,line):original(log,f,line);raise RuntimeError('interrupt')
        with patch.object(self.A.L.CompletionLog,'append_line',interrupted):
            with self.assertRaises(RuntimeError):self.execute()
        self.execute();self.producer.assert_called_once()
        self.assertEqual(len(self.TL.read_log(str(self.round))),2)
        self.assertTrue(self.opened)
        self.assertTrue(all(Path(p).is_relative_to(self.root) for p in self.opened))

    def test_stale_producer_hash_refused(self):
        self.execute();path=Path(self.paths[0]);path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(RuntimeError,'sha256 differs'):self.execute()
        self.producer.assert_called_once()

    def test_same_count_wrong_population_even_with_refreshed_manifest_refused(self):
        self.execute();path=self.paths[0];rows=self.C.read_jsonl(path);rows[0]['k']='foreign/0'
        self.C.write_jsonl(path,rows);self.refresh_provenance()
        with self.assertRaisesRegex(ValueError,'population'):self.execute()
        self.producer.assert_called_once()

    def test_changed_weight_bytes_refused(self):
        self.execute();(self.model/'weights.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'selected model'):self.execute()
        self.producer.assert_called_once()

    def test_wrong_stored_decision_even_with_refreshed_manifest_refused(self):
        self.execute();path=self.paths[0];rows=self.C.read_jsonl(path);rows[0]['argmax']=1
        self.C.write_jsonl(path,rows);self.refresh_provenance()
        with self.assertRaisesRegex(ValueError,'stored decision'):self.execute()
        self.producer.assert_called_once()

    def test_claimed_accuracy_must_equal_original_metric_recomputation(self):
        self.producer.return_value['track_k']['partitions']['decision-v7/test']['headline']['kev_rule_accuracy']=.75
        with self.assertRaisesRegex(RuntimeError,'headline differs'):self.execute()
        self.assertEqual(self.TL.read_log(str(self.round)),[])

    def test_changed_dataset_manifest_hash_refused(self):
        self.execute()
        path=self.data/'decision-v7/test.jsonl';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(RuntimeError,'do not match KEV/manifest'):self.execute()
        self.producer.assert_called_once()


if __name__=='__main__':unittest.main()
