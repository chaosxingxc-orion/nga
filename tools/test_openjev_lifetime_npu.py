#!/usr/bin/env python3
"""CPU protocol tests use real durable files and independent prediction checks."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).parent

def module(n):
    s=importlib.util.spec_from_file_location(n,HERE/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

pmod=module('openjev_lifetime_protocol');ev=module('e38_evidence');verify=module('openjev_lifetime_verify')
prior=module('verify_openjev_path_trace');driver=module('openjev_lifetime_npu')

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        inp=dict(index=4200,shape=[15,186],candidate_order=[str(i) for i in range(15)],request={'x':1},
            request_sha256=pmod.stamp({'x':1}),ordered_id_row_hashes=['a']*15,ordered_mask_row_hashes=['b']*15,
            eligibility={'lengths':[186]*15})
        self.p=dict(schema=pmod.SCHEMA,image=pmod.IMAGE,schedule=pmod.schedule(),candidate_batch_admission=False,
            physical_chip=1,logical_device='npu:0',input=inp,native_source_sha256=pmod.SOURCE,
            safety=dict(max_reserved_gib=48,min_free_gib=8,chips=1,on_error='stop_and_preserve_generation',larger_inputs_authorized=False),
            performance_scope='full forward including identical passive token guard; no internal instrumentation',
            resume_policy='verified fixed prefix, same Docker start generation only; unmatched intent fails closed',
            expected_core_names=['layer'+str(i) for i in range(18)],out=str(self.root),source_config_sha256='c',
            candidate_sources={k:k for k in ['original','L1','L2','L1L2']})
        self.gen=dict(container_id='id',started_at='start',launch_receipt_sha256='receipt')
        for f in ['items','attempts']:(self.root/f).mkdir()
    def add(self,i):
        t=pmod.schedule()[i];ident=pmod.identity(self.p,'plan',t);n=pmod.name(t)+'.json'
        attempt=dict(**ident,generation=self.gen,phase='forward_intent',utc='now')
        ev.publish_new(self.root/'attempts'/n,attempt)
        v=dict(**ident,generation=self.gen,attempt_sha256=ev.Snapshot(self.root/'attempts'/n).sha256,
            observed_input={k:self.p['input'][k] for k in ['shape','ordered_id_row_hashes','ordered_mask_row_hashes']},
            core_calls=self.p['expected_core_names'],candidate_source_sha256=t['mode'],seconds=2.,chips=1,
            questions_per_second_per_chip=.5,tokens_per_second_per_chip=1395.,baseline_allocated_gib=4.,
            baseline_reserved_gib=5.,peak_allocated_gib=6.,peak_reserved_gib=7.,free_before_gib=50.,
            prediction=dict(logits=[0.]*15,answer={'choice':'0'}))
        ev.publish_new(self.root/'items'/n,dict(payload=v,sha256=pmod.stamp(v)))
    def check(self,complete=False,gen=None):
        return pmod.check_receipts(self.p,'plan',ev.Evidence(),lambda a,b:None,complete,gen)
    def mutate(self,i,key,value):
        n=pmod.name(pmod.schedule()[i])+'.json';f=self.root/'items'/n;x=json.loads(f.read_text());x['payload'][key]=value
        x['sha256']=pmod.stamp(x['payload']);f.write_text(json.dumps(x))
    def test_real_native_prediction_checker(self):
        fixture=json.loads((HERE/'fixtures/e38_e37_native_predictions.json').read_text())
        rec=next(r for r in fixture['records'] if r['model']==2)
        pred=json.loads(rec['raw_receipt_json'])['payload']['prediction']
        p={'input':fixture['frozen_input']['2'] if '2' in fixture['frozen_input'] else fixture['frozen_input'],
           'numeric_contract':dict(temperature=rec['temperature'],probability_mass_atol=1e-6,
            probability_mass_rtol=1e-6,logit_probability_atol=1e-5,wire_probability_atol=1e-8,
            confidence_atol=1e-7,argmax_tie='first_in_candidate_order')}
        prior.check_prediction(pred,p)
        broken=copy.deepcopy(pred);broken['logits'][0]+=5
        with self.assertRaises(ValueError):prior.check_prediction(broken,p)
    def test_bootstrap_wrong_pin(self):
        path=self.root/'plan.json';path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Caller-pinned'):driver.bootstrap(path,'bad')
    def test_bootstrap_rejects_unbound_executable_without_execution(self):
        marker=self.root/'executed'
        (self.root/'evil.py').write_text('open('+repr(str(marker))+',"w").write("bad")')
        path=self.root/'plan.json';path.write_text(json.dumps({'out':str(self.root),'files':{}}))
        import hashlib
        with self.assertRaisesRegex(ValueError,'Unbound executable'):driver.bootstrap(path,hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(marker.exists())
    def test_empty_and_complete_prefix(self):
        self.assertEqual(self.check(),{})
        for i in range(8):self.add(i);self.assertEqual(len(self.check(gen=self.gen)),i+1)
        self.assertTrue(verify.reconstruct(self.check(True))['exact_outputs'])
    def test_unmatched_intent(self):
        self.add(0);next((self.root/'items').iterdir()).unlink()
        with self.assertRaisesRegex(ValueError,'Unmatched'):self.check()
    def test_unknown_pending(self):
        (self.root/'items'/'4200_original_0.json.pending').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Foreign'):self.check()
    def test_wrong_resume_generation(self):
        self.add(0)
        with self.assertRaisesRegex(ValueError,'Resume'):self.check(gen={**self.gen,'started_at':'other'})
    def test_out_of_order(self):
        self.add(1)
        with self.assertRaisesRegex(ValueError,'prefix'):self.check()
    def test_changed_receipt_identity(self):
        for key,value in [('plan_sha256','wrong'),('candidate_source_sha256','wrong'),('observed_input',{}),('core_calls',[])]:
            with self.subTest(key=key):
                self.setUp();self.add(0);self.mutate(0,key,value)
                with self.assertRaises(ValueError):self.check()
    def test_mutated_attempt(self):
        self.add(0);f=next((self.root/'attempts').iterdir());x=json.loads(f.read_text());x['utc']='other';f.write_text(json.dumps(x))
        with self.assertRaisesRegex(ValueError,'Attempt'):self.check()
    def test_memory_envelope(self):
        self.add(0);self.mutate(0,'peak_reserved_gib',49.)
        with self.assertRaisesRegex(ValueError,'Safety'):self.check()
    def test_signed_zero_exactness(self):
        for i in range(8):self.add(i)
        values=self.check(True);values['4200_L1_0.json']['prediction']['logits'][0]=-0.0
        result=verify.reconstruct(values)
        self.assertFalse(result['exact_outputs']);self.assertFalse(result['controls']['L1_vs_original_0'])
    def test_symlink_receipt_rejected(self):
        self.add(0);f=next((self.root/'items').iterdir());other=self.root/'foreign';f.rename(other);f.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'Foreign'):self.check()
    def test_complete_required(self):
        self.add(0)
        with self.assertRaisesRegex(ValueError,'Incomplete'):self.check(True)

if __name__=='__main__':unittest.main()
