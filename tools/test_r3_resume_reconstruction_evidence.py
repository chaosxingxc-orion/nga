"""Real receipt validator with synthetic files, never actual NPU acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
F=module('test_r3_resume_evidence')
V=module('r3_resume_reconstruction_evidence')


class Reconstruction(unittest.TestCase):
    def setUp(self):
        self.fixture=F.Evidence();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tmp.cleanup)
        f=self.fixture
        # Real tiny tensor and complete 20-step loss fixtures. No mocks of the
        # verifier: a positive case must be numerically reconstructed.
        import torch
        for name in ('replica_a','replica_b','replica_c','resumed','zero_moments','no_update'):
            bad=name in ('zero_moments','no_update')
            root=f.root/name
            rows=[dict(step=i,epoch=0,lr=.001,loss=2. if bad else 1.,grad_norm=1.,
                       base_questions=1,examples=1,tokens=10,chunks=1) for i in range(2201,2221)]
            (root/'losses.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
            torch.save({'step':2220,'lora':{'w':torch.tensor([2. if bad else 1.])},
                        'sched':{'last_epoch':2220}},root/'ckpt/step_002220.pt')
        result=F.R.load(f.root/'CONTRACT_RESULT.json')
        result.update(replicas=[{'loss':0.,'weight_relative_l2':0.}]*3,
                      resumed={'loss':0.,'weight_relative_l2':0.})
        result.update(F.R.judge(0.,0.,0.,0.,result['controls']))
        for name in ('CONTRACT_RESULT.json','digest.json'):F.write(f.root/name,result)
        self.target=f.root/'cpu-target.json';F.write(self.target,f.target)
        self.target_pin=F.R.sha(self.target)
        result=F.R.load(f.root/'CONTRACT_RESULT.json')
        self.doc={k:copy.deepcopy(result[k]) for k in
                  ('replicas','resumed','controls','bars','resume_pass','controls_rejected','pass')}
        self.doc.update(inputs=f.validate(),plan_sha256=f.pin,target_sha256=self.target_pin,
                        verifier_sha256=V.VERIFIER_SHA256,validator_sha256=V.VALIDATOR_SHA256,
                        scientific_acceptance=False,test_read=False)
        self.report=f.root/'reconstructed.json';self.save()

    def save(self):
        F.write(self.report,self.doc);self.pin=F.R.sha(self.report)

    def verify(self):
        f=self.fixture
        return V.validate(self.report,self.pin,resume_plan=f.path,resume_pin=f.pin,
                          target=f.target,reconstruction_target=self.target,
                          reconstruction_target_sha256=self.target_pin)

    def test_complete_report_binds_outputs_and_immutable_target(self):
        files=self.verify()
        self.assertEqual(files[str(self.target)],self.target_pin)
        self.assertEqual(files[str(self.report)],self.pin)
        self.assertIn(str(self.fixture.root/'resumed/ckpt/step_002220.pt'),files)

    def test_arbitrary_checkpoint_bytes_rejected_even_with_rehashed_inventory(self):
        (self.fixture.root/'resumed/ckpt/step_002220.pt').write_bytes(b'fixture')
        self.doc['inputs']=self.fixture.validate();self.save()
        with self.assertRaises(Exception):self.verify()

    def test_empty_loss_records_rejected_even_with_rehashed_inventory(self):
        (self.fixture.root/'resumed/losses.jsonl').write_text('{}\n')
        self.doc['inputs']=self.fixture.validate();self.save()
        with self.assertRaisesRegex(ValueError,'step population'):self.verify()

    def test_changed_tensor_with_rehashed_inventory_is_reconstructed(self):
        import torch
        path=self.fixture.root/'resumed/ckpt/step_002220.pt'
        state=torch.load(path,weights_only=True);state['lora']['w']+=.25;torch.save(state,path)
        self.doc['inputs']=self.fixture.validate();self.save()
        with self.assertRaisesRegex(ValueError,'stored distance'):self.verify()

    def test_asserted_pass_without_complete_input_inventory_refused(self):
        self.doc['inputs'].pop(str(self.fixture.root/'resumed/ckpt/step_002220.pt'))
        self.save()
        with self.assertRaisesRegex(ValueError,'inventory'):self.verify()

    def test_changed_weights_even_with_updated_report_hash_refused(self):
        (self.fixture.root/'resumed/ckpt/step_002220.pt').write_bytes(b'changed')
        self.save()
        with self.assertRaisesRegex(ValueError,'inventory'):self.verify()

    def test_wrong_execution_binding_or_approval_scope_refused(self):
        for key,value in [('plan_sha256','f'*64),('target_sha256','e'*64),
                          ('verifier_sha256','d'*64),('validator_sha256','c'*64),
                          ('scientific_acceptance',True),('test_read',True),('pass',False)]:
            old=self.doc[key];self.doc[key]=value;self.save()
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()
            self.doc[key]=old
        self.save()

    def test_wrong_distances_and_nonfinite_numbers_refused(self):
        for value in (.002,float('nan'),True):
            self.doc['resumed']['loss']=value;self.save()
            with self.subTest(value=value),self.assertRaises(ValueError):self.verify()

    def test_input_mode_or_model_change_cannot_reuse_reconstruction(self):
        self.fixture.target['command'].append('--drop-state')
        with self.assertRaisesRegex(ValueError,'recipe'):self.verify()
        self.fixture.target['command'].pop()
        self.fixture.target['model']='/different-instruct'
        with self.assertRaisesRegex(ValueError,'configuration'):self.verify()

    def test_launcher_requires_actual_reconstruction_and_full_binding(self):
        L=module('r3_formal_launcher');f=self.fixture
        helper=str(HERE.resolve()/'r3_resume_reconstruction_evidence.py')
        plan=dict(f.target,resume_plan=str(f.path),resume_plan_sha256=f.pin,
                  resume_reconstruction=str(self.report),resume_reconstruction_sha256=self.pin,
                  reconstruction_target=str(self.target),reconstruction_target_sha256=self.target_pin,
                  files={**self.verify(),helper:F.R.sha(helper)})
        L.verify_resume_reconstruction(plan)
        plan['files'].pop(str(f.root/'resumed/ckpt/step_002220.pt'))
        with self.assertRaisesRegex(RuntimeError,'dependencies not bound'):
            L.verify_resume_reconstruction(plan)
        plan.pop('resume_reconstruction')
        with self.assertRaisesRegex(RuntimeError,'artifact not bound'):
            L.verify_resume_reconstruction(plan)

    def test_formal_prepare_requires_reconstruction_before_output_creation(self):
        P=module('r3_formal_prepare')
        from types import SimpleNamespace
        fake=SimpleNamespace(validate_bundle=lambda *a:{})
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda m:None))
        out=self.fixture.root/'never-created'
        with patch.object(P.importlib.util,'spec_from_file_location',return_value=spec), \
             patch.object(P.importlib.util,'module_from_spec',return_value=fake):
            with self.assertRaisesRegex(ValueError,'CPU resume reconstruction'):
                P.prepare(out,2,1,fresh_prechecks='p',fresh_prechecks_sha256='p',
                    training_evidence='e',training_evidence_sha256='e',
                    resume_plan='r',resume_plan_sha256='r')
        self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
