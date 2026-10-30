#!/usr/bin/env python3
"""Fail-closed recovery and hard/soft denominator checks; no model dependencies."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('subject', Path(__file__).with_name('openjev_reference_eval.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.row = {'id':'a','split':'test','options':['no','yes'],'target':[0.,1.],
                    'source':'synthetic','kind':'noul','group_id':'g','state':'abc','question':'q'}
        self.value = {**m.row_identity(self.row,0,'identity'), 'logits':[0.,1.],
                      'probabilities':m.softmax([0.,1.],1.5),'input_tokens':4}
        self.env = {'payload':self.value,'sha256':m.stamp(self.value)}

    def test_valid_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.atomic(Path(tmp)/'record-000000.json',self.env)
            self.assertEqual(m.receipts(Path(tmp),[self.row],'identity',1.5),[self.value])

    def test_payload_corruption(self):
        self.value['logits'][1]=3
        with self.assertRaisesRegex(ValueError,'checksum'):
            m.validate_receipt(self.env,self.row,0,'identity',1.5)

    def test_changed_candidate_order(self):
        changed={**self.row,'options':['yes','no']}
        with self.assertRaisesRegex(ValueError,'input/order'):
            m.validate_receipt(self.env,changed,0,'identity',1.5)

    def test_wrong_identity(self):
        with self.assertRaisesRegex(ValueError,'input/order'):
            m.validate_receipt(self.env,self.row,0,'other',1.5)

    def test_wrong_probabilities_even_with_valid_hash(self):
        self.value['probabilities']=[.5,.5]
        self.env['sha256']=m.stamp(self.value)
        with self.assertRaisesRegex(ValueError,'Probability'):
            m.validate_receipt(self.env,self.row,0,'identity',1.5)

    def test_missing_middle_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.atomic(Path(tmp)/'record-000001.json',self.env)
            with self.assertRaisesRegex(ValueError,'Noncontiguous'):
                m.receipts(Path(tmp),[self.row],'identity',1.5)

    def test_extra_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.atomic(Path(tmp)/'record-000000.json',self.env)
            with self.assertRaisesRegex(ValueError,'Extra'):
                m.receipts(Path(tmp),[],'identity',1.5)

    def test_duplicate_input_ids(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            m.validate_rows([self.row,self.row],2)

    def test_missing_input(self):
        with self.assertRaisesRegex(ValueError,'row count'):
            m.validate_rows([self.row],2)

    def test_partial_no_report(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            m.summarize([self.row],[],None,1.5)

    def test_preflight_evidence_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'lengths').mkdir()
            value={'index':0,'id':'a','identity':'identity','input_sha256':m.stamp(self.row),'lengths':[4]}
            m.atomic(out/'lengths/record-000000.json',{'payload':value,'sha256':m.stamp(value)})
            pre={'identity':'identity','rows':1,'status':'ready','max_length':4096,'overlength_rows':0,
                 'overlength_candidates':0,'ordered_ids_sha256':m.stamp(['a']),
                 'maximum_candidate_tokens':4,'candidate_prompts':1}
            m.atomic(out/'PREFLIGHT.json',pre)
            terminal={'rc':0,'identity':'identity','stage':'ready',
                      'outputs':{'PREFLIGHT.json':m.digest(out/'PREFLIGHT.json')}}
            m.atomic(out/'preflight-COMPLETE.json',terminal)
            (out/'preflight-EXIT').write_text('rc=0 utc=2026-10-30T15:32:23Z\n')
            m.validate_preflight({'max_length':4096},[self.row],'identity',out)
            pre['maximum_candidate_tokens']=3;m.atomic(out/'PREFLIGHT.json',pre)
            with self.assertRaisesRegex(ValueError,'hash'):
                m.validate_preflight({'max_length':4096},[self.row],'identity',out)
            terminal['outputs']['PREFLIGHT.json']=m.digest(out/'PREFLIGHT.json')
            m.atomic(out/'preflight-COMPLETE.json',terminal)
            (out/'preflight-EXIT').write_text('rc=0 utc=2026-10-30T15:32:23Z\n')
            with self.assertRaisesRegex(ValueError,'summary'):
                m.validate_preflight({'max_length':4096},[self.row],'identity',out)
            terminal['rc']=1;m.atomic(out/'preflight-COMPLETE.json',terminal)
            with self.assertRaisesRegex(ValueError,'terminal'):
                m.validate_preflight({'max_length':4096},[self.row],'identity',out)
            terminal['rc']=0;m.atomic(out/'preflight-COMPLETE.json',terminal)
            os.utime(out/'preflight-EXIT',ns=(1,1))
            with self.assertRaisesRegex(ValueError,'wrapper'):
                m.validate_preflight({'max_length':4096},[self.row],'identity',out)
            (out/'preflight-EXIT').write_text('rc=0 utc=2026-10-30T15:32:23Z\n')
            (out/'lengths/record-000000.json').unlink()
            with self.assertRaisesRegex(ValueError,'incomplete'):
                m.validate_preflight({'max_length':4096},[self.row],'identity',out)

    def test_guarded_restart_binding(self):
        config={'physical_chip':2,'out':'/runs/run','image':'sha256:abc'}
        allocation={'allocation':[{'chip':2,'run':'run'}]}
        container={'State':{'Status':'exited'},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci2'}]},
                   'Id':'id','Image':'sha256:abc','Config':{'Cmd':['bash','/runs/run/evaluate.sh'],'Entrypoint':None}}
        receipt={'container_id':'id','image':'sha256:abc','command':['bash','/runs/run/evaluate.sh'],'entrypoint':None}
        m.check_restart(config,allocation,container,[],receipt)
        with self.assertRaisesRegex(ValueError,'running container'):
            m.check_restart(config,allocation,container,[container],receipt)
        changed={**receipt,'container_id':'other'}
        with self.assertRaisesRegex(ValueError,'identity/image'):
            m.check_restart(config,allocation,container,[],changed)
        with self.assertRaisesRegex(ValueError,'ownership'):
            m.check_restart(config,{'allocation':[]},container,[],receipt)
        container['HostConfig']['Devices'].append({'PathOnHost':'/dev/davinci3'})
        with self.assertRaisesRegex(ValueError,'Physical chip'):
            m.check_restart(config,allocation,container,[],receipt)

    def test_native_soft_metric_denominators(self):
        path=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030/code/jev/metrics.py')
        spec=importlib.util.spec_from_file_location('native_metrics',path)
        native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        targets=[[0,1],[.25,.75]];probs=[[.25,.75],[.75,.25]]
        result=native.evaluate_probabilities(targets,probs)
        self.assertEqual(result['count'],2)
        self.assertEqual(result['hard_count'],1)
        self.assertEqual(result['accuracy'],1)
        self.assertEqual(result['expected_accuracy'],.625)
        self.assertAlmostEqual(result['brier'],.3125)
        self.assertAlmostEqual(result['expected_brier'],.5)
        self.assertAlmostEqual(result['multiclass_ece'],.125)
        rows=[self.row,{**self.row,'id':'b','target':[.25,.75]}]
        report=m.summarize(rows,[self.value,self.value],native.evaluate_probabilities,1.5)
        self.assertEqual((report['total_count'],report['hard_count'],report['soft_count'],report['failed_count']),(2,1,1,0))
        self.assertEqual(report['by_source_serving']['synthetic']['count'],2)


if __name__=='__main__':
    unittest.main()
