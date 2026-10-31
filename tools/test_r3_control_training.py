"""Engineering-only K1-QO/PT exact-plan contracts; no model/NPU access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent

def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
P=module('r3_formal_prepare');L=module('r3_formal_launcher')

class Controls(unittest.TestCase):
    def test_registered_control_settings(self):
        for arm,model,seeds,mode in [('K1-QO',P.MODEL,[2],'drop'),('K1-PT',P.PT_MODEL,[2,3],'full')]:
            for seed in seeds:
                self.assertEqual(P.control_settings(arm,engineering=True,model=model,seed=seed,arm='k1',shared=False,validate_shared=False),
                    {'control_arm':arm,'registered_seeds':seeds,'primary_input_mode':mode,'candidate_for_adoption':False})

    def test_prepare_rejects_invalid_controls_before_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'never'
            for changes in ({'seed':3},{'model':P.PT_MODEL},{'engineering':False},{'arm':'k2'},{'shared':True},{'validate_shared':True}):
                args=dict(seed=2,chip=1,engineering=True,model=P.MODEL,control_arm='K1-QO');args.update(changes)
                with self.subTest(changes=changes),self.assertRaises(ValueError):P.prepare(out,**args)
                self.assertFalse(out.exists())
            with self.assertRaises(ValueError):P.prepare(out,2,1,engineering=True,model=P.PT_MODEL)

    def plan(self,root,control='K1-QO',seed=2):
        model=P.MODEL if control=='K1-QO' else P.PT_MODEL
        cfg=P.control_settings(control,engineering=True,model=model,seed=seed,arm='k1',shared=False,validate_shared=False)
        code=root/'code';code.mkdir(exist_ok=True)
        launcher=str(HERE.resolve()/'r3_formal_launcher.py')
        p={'schema':'r3-engineering-k1-plan-v1','image_sha256':L.IMAGE,'seed':seed,'chip':1,
           'model':str(model),'arm':'k1','out':str(root/'out'),'code':str(code),
           'launcher':launcher,'driver':str(root/'driver.py'),'adapter':str(root/'resource.py'),
           'train_file':str(root/'train.jsonl'),'control_arm':control,'control':cfg,
           'evaluation':cfg.copy(),'execution_scope':'engineering_only','scientific_acceptance':False,
           'test_read':False,'authorization':'user_execute_engineering_when_ready_20261031'}
        p['files']={p[k]:'0'*64 for k in ('launcher','driver','adapter','train_file')}
        p['command']=['python3','-P','/workspace/train_r3.py','--out',p['out'],'--arm','k1','--seed',str(seed),
                      '--model-path',str(model),'--kernel','ref','--grad-ckpt','--micro-tokens','12000','--max-len','4096',
                      '--save-every','200','--no-merge','--epochs','2','--total-steps','3116','--expect-pairs','186']
        if control=='K1-QO':p['command'].append('--drop-state')
        return p

    def verify(self,p,path):
        path.write_text(json.dumps(p))
        with patch.object(L,'sha',return_value='0'*64):return L.verify(path,L.identity(p))

    def test_exact_qo_pt_commands_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for control,seed in [('K1-QO',2),('K1-PT',2),('K1-PT',3)]:
                p=self.plan(root,control,seed);self.assertEqual(self.verify(p,root/'plan.json'),p)

    def test_qo_wrong_seed_model_or_drop_flag_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=self.plan(root)
            for change in ('seed','model','missing_drop','wrong_mode','shared','loss','formal','unlabeled'):
                p=copy.deepcopy(base)
                if change=='seed':p['seed']=3
                elif change=='model':p['model']=str(P.PT_MODEL)
                elif change=='missing_drop':p['command'].remove('--drop-state')
                elif change=='wrong_mode':p['evaluation']['primary_input_mode']='full'
                elif change=='shared':p['k2_impl']='shared'
                elif change=='loss':p['arm']='k2'
                elif change=='formal':p['schema']='r3-formal-k1-plan-v1'
                else:p.pop('control_arm')
                with self.subTest(change=change),self.assertRaises(RuntimeError):self.verify(p,root/'plan.json')

    def test_pt_requires_explicit_control_and_full_input(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=self.plan(root,'K1-PT',3)
            for change in ('unlabeled','drop','pairs','path'):
                p=copy.deepcopy(base)
                if change=='unlabeled':p.pop('control_arm');p.pop('control')
                elif change=='drop':p['command'].append('--drop-state')
                elif change=='pairs':p['command'][-1]='0'
                else:p['model']='/different/Qwen__Qwen3.5-0.8B'
                with self.subTest(change=change),self.assertRaises(RuntimeError):self.verify(p,root/'plan.json')

if __name__=='__main__':unittest.main()
