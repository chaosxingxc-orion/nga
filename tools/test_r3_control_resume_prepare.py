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
        self.root=Path(self.tmp.name);self.base=self.root/'Qwen__Qwen3.5-0.8B-Base';self.pt=self.root/'Qwen__Qwen3.5-0.8B'
        for name,value in [('BASE',str(self.base)),('INSTRUCT',str(self.pt)),('RUN_ROOT',self.root),('ALLOCATION',str(self.root/'CHIP-ALLOCATION.json'))]:
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
                   'driver':str(code/'r3_formal_driver.py'),'image_sha256':P.IMAGE,'environment':P.ENVIRONMENT.copy(),
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

    def finalized(self):
        self.prepare();path=self.out/'PREPARATION.json'
        return P.finalize(path,P.R.sha(path))

    def test_finalize_real_launcher_admission_and_mount_contract(self):
        for arm in ('K1-QO','K1-PT'):
            self.configure(arm);self.out=self.root/arm;r=self.finalized()
            # Frozen test copy substitutes only registered filesystem roots.
            helper=self.out/'tools/r3_control_resume_prepare.py'
            text=helper.read_text().replace("BASE='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'",'BASE='+repr(str(self.base)))
            text=text.replace("INSTRUCT='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'",'INSTRUCT='+repr(str(self.pt)))
            text=text.replace("RUN_ROOT=Path('/mnt/cephfs/xingchao/experiments/jev')",'RUN_ROOT=Path('+repr(str(self.root))+')')
            helper.write_text(text)
            plan=P.R.load(r['plan']);plan['files'][str(helper)]=P.R.sha(helper)
            Path(r['plan']).write_text(json.dumps(plan))
            spec=importlib.util.spec_from_file_location('frozen_control_launcher',plan['launcher'])
            launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)
            with patch.object(launch,'CONTROL_MODELS',{'K1-QO':str(self.base),'K1-PT':str(self.pt)}):
                self.assertEqual(launch.verify(r['plan'],P.R.identity(plan)),plan)
            command=launch.docker_command(plan,r['plan'],1)
            self.assertIn('type=bind,src='+plan['code']+',dst=/mnt/cephfs/xingchao/experiments/jev/r3_code,readonly',command)
            self.assertNotIn('--rm',command)
            self.assertTrue(r['deployable']);self.assertFalse(r['scientific_acceptance'])
            self.assertTrue((self.out/'RELAUNCH.sh').exists())
            mounts=[]
            for i,value in enumerate(command):
                if value=='--mount':
                    fields=dict((part.split('=',1) if '=' in part else (part,True)) for part in command[i+1].split(','))
                    mounts.append({'Type':'bind','Source':fields['src'],'Destination':fields['dst'],'RW':'readonly' not in fields})
            observed={'Mounts':mounts,'Config':{'Entrypoint':['python3'],'Env':[k+'='+v for k,v in plan['environment'].items()]},
                      'HostConfig':{'NetworkMode':'none','Privileged':False}}
            image={'Id':plan['image_sha256'],'Config':{'Env':[]}}
            observed['Image']=plan['image_sha256']
            observed['Config']['Cmd']=['-P','/workspace/r3_formal_driver.py','--plan',r['plan'],'--attempt','1']
            observed['HostConfig'].update(AutoRemove=False,ShmSize=64*1024**3,IpcMode='private',
                Ulimits=[{'Name':'memlock','Soft':-1,'Hard':-1},{'Name':'stack','Soft':67108864,'Hard':67108864}],
                Devices=[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x,'CgroupPermissions':'rwm'}
                         for x in ('davinci_manager','devmm_svm','hisi_hdc',f'davinci{plan["chip"]}')])
            launch.verify_control_resume_container(plan,r['plan'],1,observed,image)
            mounts[0]['RW']=True
            with self.assertRaisesRegex(RuntimeError,'mounts'):launch.verify_control_resume_container(plan,r['plan'],1,observed,image)
            mounts[0]['RW']=False;observed['Config']['Env'].append('HF_HUB_OFFLINE=0')
            with self.assertRaisesRegex(RuntimeError,'environment'):launch.verify_control_resume_container(plan,r['plan'],1,observed,image)

    def test_finalized_plan_rejects_contract_source_environment_and_identity_changes(self):
        r=self.finalized();plan=P.R.load(r['plan']);P.verify_launch(plan)
        for key,value in [('seed',3),('environment',{}),('model',str(self.pt)),('container','wrong'),('run','wrong')]:
            old=plan[key];plan[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):P.verify_launch(plan)
            plan[key]=old
        contract=self.out/'CONTRACT.json';old=contract.read_bytes();doc=json.loads(old);doc['steps']=21
        contract.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'contract'):P.verify_launch(plan)
        contract.write_bytes(old)
        self.checkpoint.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checkpoint'):P.verify_launch(plan)

    def test_finalization_pin_and_repeat_refused(self):
        self.prepare();path=self.out/'PREPARATION.json'
        with self.assertRaisesRegex(ValueError,'pin'):P.finalize(path,'0'*64)
        P.finalize(path,P.R.sha(path))
        with self.assertRaisesRegex(ValueError,'new finalization'):P.finalize(path,P.R.sha(path))


if __name__=='__main__':unittest.main()
