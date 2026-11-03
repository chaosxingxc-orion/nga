"""Control identity regression for the pinned-plan legacy API adapter."""
import copy
import json
from pathlib import Path
import types
import unittest
from unittest.mock import Mock
from tools import r3_dev_qualification as P

ROOT = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
PLANS = {
    'K1': ROOT/'formal_prospective_08b_20261102_v3/primary_s2/plan.json',
    'K1-QO': ROOT/'formal_controls_prospective_20261102_v1/qo/seed2/plan.json',
    'K1-PT': ROOT/'formal_controls_prospective_20261102_v1/pt/seed3/plan.json',
}


class ControlArguments(unittest.TestCase):
    def fixture(self, identity):
        path=PLANS[identity]; plan=json.loads(path.read_text())
        entry={'plan':str(path),'arm':identity,'seed':plan['seed']}
        validator=Mock(return_value={'unchanged':'evidence'})
        api=types.SimpleNamespace(training=types.SimpleNamespace(validate=validator))
        def old(entry,rep,bundle,scoped):
            self.assertEqual(entry['arm'],'K1')
            self.assertIsNot(scoped,api)
            return scoped.training.validate(*(plan[k] for k in ('training_evidence','training_evidence_sha256','code','model','train_file','image_sha256')))
        api.Q=types.SimpleNamespace(bound=Mock(return_value=plan),training_lineage=old)
        return plan,entry,api,validator

    def test_exact_forwarding_and_shared_api_unmodified(self):
        for identity,control,mode in [('K1',None,'full'),('K1-QO','K1-QO','drop'),('K1-PT','K1-PT','full')]:
            with self.subTest(identity=identity):
                plan,entry,api,validator=self.fixture(identity)
                out=P.training_lineage(entry,{}, {'files':{}},api)
                self.assertEqual(out,{'unchanged':'evidence'})
                self.assertEqual(validator.call_args.kwargs,dict(control_arm=control,input_mode=mode))
                self.assertIs(api.training.validate,validator)
                api.Q.bound.assert_called_once_with(entry['plan'],{})

    def test_wrong_or_missing_member_identity_rejected(self):
        for value in ['K1','K1-QO',None]:
            plan,entry,api,validator=self.fixture('K1-PT');entry['arm']=value
            with self.assertRaisesRegex(ValueError,'identity'):P.training_lineage(entry,{}, {'files':{}},api)
            validator.assert_not_called()

    def test_mutable_caller_override_rejected(self):
        for key,value in [('control_arm','K1-QO'),('input_mode','drop'),('primary_input_mode','drop')]:
            plan,entry,api,validator=self.fixture('K1-PT');entry[key]=value
            with self.assertRaisesRegex(ValueError,'argument'):P.training_lineage(entry,{}, {'files':{}},api)
            validator.assert_not_called()

    def test_missing_or_inconsistent_plan_control_rejected(self):
        for mutation in ['missing','role','mode','command','objective']:
            plan,entry,api,validator=self.fixture('K1-PT')
            if mutation=='missing':del plan['control_arm']
            if mutation=='role':plan['evaluation']['control_arm']='K1-QO'
            if mutation=='mode':plan['control']['primary_input_mode']='drop'
            if mutation=='command':plan['command'].append('--drop-state')
            if mutation=='objective':plan['arm']='k2'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):P.training_lineage(entry,{}, {'files':{}},api)
            validator.assert_not_called()

    def test_ordinary_plan_cannot_hide_control_metadata(self):
        for fields in [{'control':{'control_arm':'K1-QO'}},{'input_mode':'drop'},{'evaluation':{'control_arm':'K1-PT'}}]:
            plan,entry,api,validator=self.fixture('K1');plan.update(fields)
            with self.assertRaises(ValueError):P.training_lineage(entry,{}, {'files':{}},api)
            validator.assert_not_called()

    def test_legacy_call_target_cannot_drift(self):
        plan,entry,api,validator=self.fixture('K1-PT')
        api.Q.training_lineage=lambda entry,rep,bundle,scoped:scoped.training.validate('foreign-evidence')
        with self.assertRaisesRegex(ValueError,'call differs'):P.training_lineage(entry,{}, {'files':{}},api)
        validator.assert_not_called()

    def test_validator_failure_preserved(self):
        plan,entry,api,validator=self.fixture('K1-PT');validator.side_effect=ValueError('control/input-mode evidence differs')
        with self.assertRaisesRegex(ValueError,'evidence differs'):P.training_lineage(entry,{}, {'files':{}},api)
        self.assertIs(api.training.validate,validator)

if __name__=='__main__':unittest.main()
