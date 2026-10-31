"""Synthetic source/checkpoint packaging, never real recovery success."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('control_resume',HERE/'r3_control_resume_prepare.py')
P=importlib.util.module_from_spec(s);s.loader.exec_module(P)


class Preparation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.base=self.root/'Base';self.pt=self.root/'Instruct'
        for name,value in [('BASE',str(self.base)),('INSTRUCT',str(self.pt))]:
            ctx=patch.object(P,name,value);ctx.start();self.addCleanup(ctx.stop)
        for model in (self.base,self.pt):model.mkdir();(model/'weights.bin').write_bytes(model.name.encode())
        self.src=self.root/'source';code=self.src/'code';code.mkdir(parents=True)
        for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py','r3_formal_driver.py'):
            p=code/rel;p.parent.mkdir(exist_ok=True);p.write_text('# synthetic source\n')
        self.train=self.root/'train.jsonl';self.train.write_text('{}\n')
        self.checkpoint=self.src/'ckpt/step_000200.pt';self.checkpoint.parent.mkdir();self.checkpoint.write_bytes(b'synthetic checkpoint')
        self.plan_path=self.src/'plan.json';self.out=self.root/'prepared'
        self.plan={'schema':'r3-engineering-k1-plan-v1','control_arm':'K1-QO','model':str(self.base),
                   'arm':'k1','seed':2,'out':str(self.src),'code':str(code),'train_file':str(self.train),
                   'driver':str(code/'r3_formal_driver.py'),'image_sha256':P.IMAGE,'environment':{},
                   'authorization':'user_execute_engineering_when_ready_20261031',
                   'execution_scope':'engineering_only','test_read':False,'scientific_acceptance':False}
        self.configure('K1-QO')
    def configure(self,arm):
        model=self.base if arm=='K1-QO' else self.pt
        self.plan.update(control_arm=arm,model=str(model))
        self.plan['command']=['python3','-P','/workspace/train_r3.py','--out',str(self.src),'--arm','k1','--seed','2',
            '--model-path',str(model),'--kernel','ref','--grad-ckpt','--micro-tokens','12000','--max-len','4096',
            '--save-every','200','--no-merge','--epochs','2','--total-steps','3116','--expect-pairs','186']
        if arm=='K1-QO':self.plan['command'].append('--drop-state')
        self.plan['files']={str(p):P.R.sha(p) for p in [*Path(self.plan['code']).rglob('*'),*model.iterdir(),self.train] if p.is_file()}
        self.save()
    def save(self):self.plan_path.write_text(json.dumps(self.plan));self.pin=P.R.identity(self.plan)
    def prepare(self):return P.prepare(self.plan_path,self.pin,self.checkpoint,P.R.sha(self.checkpoint),200,self.out,2)
    def test_qo_pt_package_preserves_recipe_and_frozen_contract(self):
        for arm in ('K1-QO','K1-PT'):
            self.configure(arm);self.out=self.root/arm;r=self.prepare()
            d=json.loads((self.out/'DRAFT.json').read_text());cfg=json.loads((self.out/'CONTRACT.json').read_text())
            self.assertFalse(r['deployable']);self.assertFalse(r['checkpoint_state_verified'])
            self.assertNotIn('launcher',d);self.assertEqual(cfg['steps'],20);self.assertEqual(cfg['split'],10)
            self.assertEqual(P.R.sha(self.out/'code/r3_resume_contract.py'),P.R.sha(HERE/'r3_resume_contract.py'))
            self.assertEqual(json.loads((self.out/'SOURCE_PLAN.json').read_text())['command'],self.plan['command'])
    def test_wrong_drop_model_seed_or_objective_refused(self):
        for key,value in [('seed',3),('model',str(self.pt)),('arm','k2')]:
            old=self.plan[key];self.plan[key]=value;self.save()
            with self.subTest(key=key),self.assertRaises(ValueError):self.prepare()
            self.plan[key]=old
        self.save();self.plan['command'].remove('--drop-state');self.save()
        with self.assertRaisesRegex(ValueError,'recipe'):self.prepare()
        self.assertFalse(self.out.exists())
    def test_checkpoint_owner_pin_step_and_symlink_refused(self):
        with self.assertRaisesRegex(ValueError,'pin'):
            P.prepare(self.plan_path,self.pin,self.checkpoint,'0'*64,200,self.out,2)
        with self.assertRaisesRegex(ValueError,'owner/step'):
            P.prepare(self.plan_path,self.pin,self.checkpoint,P.R.sha(self.checkpoint),201,self.out,2)
        link=self.src/'linked.pt';link.symlink_to(self.checkpoint)
        with self.assertRaisesRegex(ValueError,'nonsymlink'):
            P.prepare(self.plan_path,self.pin,link,P.R.sha(self.checkpoint),200,self.out,2)
    def test_source_inventory_change_and_no_overwrite(self):
        (self.base/'extra.bin').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError,'model inventory'):self.prepare()
        (self.base/'extra.bin').unlink();self.prepare()
        with self.assertRaisesRegex(ValueError,'new output'):self.prepare()


if __name__=='__main__':unittest.main()
