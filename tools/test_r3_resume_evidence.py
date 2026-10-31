"""Synthetic receipt fixtures test rejection behavior, not real NPU execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('resume_evidence',HERE/'r3_resume_evidence.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
spec=importlib.util.spec_from_file_location('resume_contract',HERE/'r3_resume_contract.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


def write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d)+'\n')


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        b=Path(self.tmp.name);self.root=b/'contract';root=self.root;root.mkdir()
        model=b/'model';model.mkdir();(model/'weights').write_bytes(b'fixture')
        train=b/'train.jsonl';train.write_text('{}\n');code=b/'target-code';code.mkdir()
        tested=root/'code';tested.mkdir();sourcecode=b/'source-code';sourcecode.mkdir()
        for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
            for d in (code,tested,sourcecode):
                p=d/rel;p.parent.mkdir(exist_ok=True);p.write_text('# fixture\n')
        shutil.copy2(HERE/'r3_resume_contract.py',tested/'r3_resume_contract.py')
        self.target={'code':str(code),'model':str(model),'train_file':str(train),'image_sha256':'image','environment':{'TASK_QUEUE_ENABLE':'2'},
                     'command':['python3','-P','/workspace/train_r3.py','--out','target','--seed','3','--arm','k1','--micro-tokens','12000']}
        original=b/'source';original.mkdir();checkpoint=original/'ckpt.pt';checkpoint.write_bytes(b'synthetic checkpoint')
        shutil.copy2(checkpoint,root/'SOURCE.pt')
        source={**self.target,'out':str(original),'code':str(sourcecode),'seed':2,'files':{str(p):R.sha(p) for p in [*sourcecode.rglob('*.py'),model/'weights',train]}}
        source['command']=list(self.target['command']);source['command'][source['command'].index('--seed')+1]='2'
        write(root/'SOURCE_PLAN.json',source)
        config={'source_sha256':R.sha(root/'SOURCE.pt'),'source_step':2200,'steps':20,'replicas':3,'split':10,'factor':1.5,'loss_slack':2.4e-7,'weight_relative_l2_slack':1e-7,'test_read':False,'scientific_acceptance':False}
        write(root/'CONTRACT.json',config)
        write(root/'SOURCE.json',{'training':str(original),'checkpoint':str(checkpoint),'sha256':config['source_sha256'],'step':2200})
        plan={**self.target,'out':str(root),'code':str(tested),'run':'contract','container':'contract-container','chip':1,'seed':2,
              'schema':'r3-engineering-k1-plan-v1','validation_kind':'current_k1_resume_contract','test_read':False,'scientific_acceptance':False,
              'command':['python3','-P','/workspace/r3_resume_contract.py','--out',str(root)],'review_sha256':'PENDING'}
        plan['files']={str(p):R.sha(p) for p in [*root.rglob('*'),model/'weights',train] if p.is_file()}
        self.path=root/'plan.json';write(self.path,plan);self.pin=R.identity(plan)
        terminal={'exit_code':0,'attempt':1};write(root/'TRAIN_EXIT.json',terminal);attempt=root/'attempts/1'
        write(attempt/'EXIT.json',terminal)
        write(attempt/'LAUNCH_RECEIPT.json',{'id':'f'*64,'image':'image','plan_sha256':self.pin})
        cmd=['docker','run','-d','--network=none','--pull=never']
        for device in ('davinci_manager','devmm_svm','hisi_hdc','davinci1'):cmd += ['--device','/dev/'+device]
        cmd += ['-e','TASK_QUEUE_ENABLE=2']
        for mount in (f'type=bind,src={tested},dst=/workspace,readonly',
                      f'type=bind,src={model},dst={model},readonly',f'type=bind,src={train},dst={train},readonly',
                      f'type=bind,src={root},dst={root}',
                      'type=bind,src=/usr/local/Ascend/driver,dst=/usr/local/Ascend/driver,readonly',
                      f'type=bind,src={tested},dst=/mnt/cephfs/xingchao/experiments/jev/r3_code,readonly'):
            cmd += ['--mount',mount]
        cmd += ['--entrypoint','python3','image','-P','/workspace/r3_formal_driver.py','--plan',str(self.path),'--attempt','1']
        write(attempt/'LAUNCH_SPEC.json',{'command':cmd,'plan_sha256':self.pin})
        write(attempt/'RELEASE.json',{'schema':'r3-resource-release-v1','run':'contract','chip':1,'container_id':'f'*64,'container':'contract-container-a1','exit_code':0,'container_finished_at':'finish','container_started_at':'start','released_utc':'release'})
        write(attempt/'SUPERVISOR_DONE.json',{'exit_code':0})
        for i,name in enumerate(['replica_a','replica_b','replica_c','resumed','resumed','zero_moments','no_update']):
            write(root/f'STAGE-{i}.json',{'exit_code':0,'stage':i,'name':name})
            d=root/name;d.mkdir(exist_ok=True);(d/'losses.jsonl').write_text('{}\n');(d/'ckpt').mkdir(exist_ok=True);(d/'ckpt/step_002220.pt').write_bytes(b'fixture')
        controls={'zero_moments':{'loss':1.,'weight_relative_l2':1.},'no_update':{'loss':1.,'weight_relative_l2':1.}}
        result=C.judge(.01,.01,.001,.001,controls)
        result.update(replicas=[{'loss':.01,'weight_relative_l2':.01}]*3,resumed={'loss':.001,'weight_relative_l2':.001},controls=controls,source_step=2200,source_sha256=config['source_sha256'],test_read=False,scientific_acceptance=False)
        write(root/'CONTRACT_RESULT.json',result);write(root/'digest.json',result)

    def validate(self):return R.validate(self.path,self.pin,self.target)

    def test_complete_synthetic_bundle_binds_all_outputs(self):
        files=self.validate()
        self.assertIn(str(self.root/'STAGE-6.json'),files)
        self.assertIn(str(self.root/'resumed/ckpt/step_002220.pt'),files)
        self.assertIn(str(self.root/'attempts/1/RELEASE.json'),files)

    def test_missing_or_failed_execution_cannot_pass(self):
        for rel in ('TRAIN_EXIT.json','attempts/1/RELEASE.json','STAGE-6.json'):
            p=self.root/rel;old=p.read_bytes();p.unlink()
            with self.subTest(rel=rel),self.assertRaises(ValueError):self.validate()
            p.write_bytes(old)
        p=self.root/'TRAIN_EXIT.json';d=json.loads(p.read_text());d['exit_code']=1;write(p,d)
        with self.assertRaisesRegex(ValueError,'terminal'):self.validate()

    def test_pass_boolean_does_not_override_failed_control(self):
        d=json.loads((self.root/'CONTRACT_RESULT.json').read_text());d['controls']['no_update']={'loss':0.,'weight_relative_l2':0.}
        for name in ('CONTRACT_RESULT.json','digest.json'):write(self.root/name,d)
        with self.assertRaisesRegex(ValueError,'recomputed'):self.validate()

    def test_individual_nan_floor_cannot_hide_in_max(self):
        d=json.loads((self.root/'CONTRACT_RESULT.json').read_text());d['replicas'][1]['loss']=float('nan')
        for name in ('CONTRACT_RESULT.json','digest.json'):write(self.root/name,d)
        with self.assertRaises(ValueError):self.validate()

    def test_configuration_code_model_and_pin_changes_fail(self):
        for key,value in [('image_sha256','wrong'),('environment',{}),('model','/wrong')]:
            old=self.target[key];self.target[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()
            self.target[key]=old
        p=Path(self.target['code'])/'train_r3.py';p.write_text('different\n')
        with self.assertRaisesRegex(ValueError,'code differs'):self.validate()

    def test_cpu_only_launch_cannot_pass_as_npu_evidence(self):
        p=self.root/'attempts/1/LAUNCH_SPEC.json';d=json.loads(p.read_text());cmd=d['command'];i=cmd.index('/dev/davinci1');del cmd[i-1:i+1];write(p,d)
        with self.assertRaisesRegex(ValueError,'NPU device'):self.validate()

    def test_wrong_launch_identity_and_stage_identity_fail(self):
        for rel,key,value in [('attempts/1/LAUNCH_RECEIPT.json','plan_sha256','wrong'),('STAGE-4.json','name','replica_a')]:
            p=self.root/rel;old=p.read_bytes();d=json.loads(old);d[key]=value;write(p,d)
            with self.subTest(rel=rel),self.assertRaises(ValueError):self.validate()
            p.write_bytes(old)


class EntryPoints(unittest.TestCase):
    def test_launcher_requires_bound_resume_plan_and_all_outputs(self):
        spec=importlib.util.spec_from_file_location('launcher',HERE/'r3_formal_launcher.py')
        L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
        helper=str(HERE/'r3_resume_evidence.py')
        with self.assertRaisesRegex(RuntimeError,'resume plan not bound'):
            L.verify_resume_evidence({'files':{helper:'fixture'}})
        with tempfile.TemporaryDirectory() as td:
            # Execute the real helper on a missing input, with the entry binding present.
            p={'files':{helper:R.sha(helper),td+'/missing.json':'fixture'},'resume_plan':td+'/missing.json','resume_plan_sha256':'fixture'}
            with self.assertRaises(FileNotFoundError):L.verify_resume_evidence(p)

    def test_prepare_missing_resume_fails_before_creating_output(self):
        spec=importlib.util.spec_from_file_location('prepare',HERE/'r3_formal_prepare.py')
        P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'new'
            fake=type('Helper',(),{'validate_bundle':staticmethod(lambda *a:{})})()
            loader=type('Loader',(),{'exec_module':staticmethod(lambda m:None)})()
            fake_spec=type('Spec',(),{'loader':loader})()
            with patch.object(P.importlib.util,'spec_from_file_location',return_value=fake_spec), patch.object(P.importlib.util,'module_from_spec',return_value=fake):
                with self.assertRaisesRegex(ValueError,'resume plan'):
                    P.prepare(out,2,1,fresh_prechecks='fixture',fresh_prechecks_sha256='fixture',training_evidence='fixture',training_evidence_sha256='fixture')
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
