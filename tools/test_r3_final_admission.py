"""Binding checks only: temporary synthetic eligibility/review, never approval."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).parent
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2')
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
C=load('closure_admission_fixture',HERE/'r3_final_closure.py')


class Admission(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen source absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);closure=self.root/'closure';receipt=C.prepare(SOURCE,closure)
        self.A=load('frozen_admission_fixture',closure/'r3_code/r3_final_admission.py')
        self.model=self.root/'Qwen__Qwen3.5-0.8B-Base';self.model.mkdir()
        (self.model/'model.safetensors').write_bytes(b'synthetic fixture')
        inv=self.A.M.capture(self.model)
        inventory=self.write('inventory',{'inventory':inv,'inventory_sha256':self.A.M.identity(inv)})
        self.evidence={k:self.write(k,{'synthetic_fixture':True}) for k in (
            'development_comparison','r0_gating','resume_reconstruction','training_eligibility','selection_decision')}
        self.eligible={'schema':'r3-final-eligibility-v1','status':'ELIGIBLE','candidate_test_read':False,
            'seed_set':[2,3],'suites':self.A.SUITES,'evidence':self.evidence,
            'selected_models':[{'path':str(self.model),'sha256':'a'*64,'arm':'K0'}]}
        eligibility=self.write('eligibility',self.eligible)
        rd=self.root/'round';rd.mkdir()
        final=self.write('round/FINAL',{'eligibility_sha256':eligibility['sha256'],'models':self.eligible['selected_models']})
        self.plan={'schema':'r3-final-test-plan-v1','host':'k8s-node1','image':self.A.IMAGE,'chip':1,
            'suites':self.A.SUITES,'partitions':['calibration','test'],'arm':'K0',
            'scoring':{'mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,'stages':'k','shards':1},
            'out':str(self.root/'out'),'round_dir':str(rd),'model_sha256':'a'*64,'model':str(self.model),
            'adapter':None,'adapter_inventory':None,'eligibility':eligibility,'evidence':self.evidence,'final':final,
            'dataset_manifest':self.write('dataset-manifest',{'suites':{s:{} for s in self.A.SUITES}}),
            'closure':{'root':str(closure),'sha256':receipt['manifest_sha256']},'base_inventory':inventory}
        self.pin=self.A.identity(self.plan)
        self.review={'schema':'r3-final-test-review-v1','review_kind':'independent_astra','reviewer_model':'gpt-6-astra',
            'verdict':'PASS','approved_plan_sha256':self.pin,'blocking_findings':[],'evidence_checks':['synthetic fixture only'],
            'eligibility_sha256':eligibility['sha256'],'evidence':self.evidence}
        self.review_entry=self.write('review',self.review)

    def write(self,name,value):
        p=self.root/(name+'.json');p.write_text(json.dumps(value))
        return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

    def verify(self):return self.A.verify(self.plan,self.pin,self.review_entry)

    def test_consistent_binding_does_not_claim_scientific_acceptance(self):
        result=self.verify();self.assertTrue(result['artifact_bindings_verified']);self.assertFalse(result['scientific_acceptance'])

    def test_plan_and_review_mismatch_refused(self):
        self.plan['chip']=2
        with self.assertRaisesRegex(ValueError,'plan identity'):self.verify()
        self.plan['chip']=1;self.review['approved_plan_sha256']='f'*64;self.review_entry=self.write('review',self.review)
        with self.assertRaisesRegex(ValueError,'exact-plan review'):self.verify()

    def test_review_without_checks_or_with_blockers_refused(self):
        for field,value in [('evidence_checks',[]),('blocking_findings',['unresolved'])]:
            original=self.review[field];self.review[field]=value;self.review_entry=self.write('review',self.review)
            with self.assertRaisesRegex(ValueError,'blockers or lacks checks'):self.verify()
            self.review[field]=original

    def test_changed_evidence_or_base_bytes_refused(self):
        path=Path(self.evidence['r0_gating']['path']);raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.verify()
        path.write_bytes(raw);(self.model/'model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'model byte inventory'):self.verify()

    def test_ineligible_model_is_rejected_even_with_rebound_review(self):
        self.eligible['selected_models'][0]['sha256']='f'*64
        self.plan['eligibility']=self.write('eligibility',self.eligible)
        self.pin=self.A.identity(self.plan)
        self.review.update(approved_plan_sha256=self.pin,eligibility_sha256=self.plan['eligibility']['sha256'])
        self.review_entry=self.write('review',self.review)
        with self.assertRaisesRegex(ValueError,'model not eligible'):self.verify()


if __name__=='__main__':unittest.main()
