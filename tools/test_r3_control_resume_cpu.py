"""CPU command/lifecycle counterexamples, no real containers or model files."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('cpu',HERE/'r3_control_resume_cpu.py')
C=importlib.util.module_from_spec(s);s.loader.exec_module(C)

class CPU(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'cpu';self.out.mkdir()
        self.config_path=self.out/'CONFIG.json';self.pin='a'*64
        self.c={'schema':'r3-control-resume-cpu-v1','out':str(self.out),'container':'test-cpu',
                'image':C.IMAGE,'files':{str(self.root/'checkpoint.pt'):'fixture'},'tools':{},
                'scientific_acceptance':False,'test_read':False}
        self.actual=self.container()
        self.image={'Id':C.IMAGE,'Config':{'Env':[]}}
        self.daemon={'runtime':'ascend','cgroupns':'private'}
        self.image_patch=patch.object(C,'image_config',return_value=self.image);self.image_patch.start();self.addCleanup(self.image_patch.stop)
        self.policy=C.policy()
        self.policy_patch=patch.object(C,'policy',return_value=self.policy);self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
        self.daemon_patch=patch.object(self.policy,'daemon_policy',return_value=self.daemon);self.daemon_patch.start();self.addCleanup(self.daemon_patch.stop)
    def container(self):
        cmd,mounts,args=C.command(self.c,self.config_path,self.pin)
        return {'Id':'b'*64,'Image':C.IMAGE,'Name':'/test-cpu','State':{'Status':'running','ExitCode':0},
            'HostConfig':{'AutoRemove':False,'Devices':[],'Privileged':False,'NetworkMode':'none','Runtime':'ascend','CgroupnsMode':'private','IpcMode':'private','ShmSize':64*1024**2},
            'Config':{'Entrypoint':['python3'],'Cmd':args,'Env':['TORCH_DEVICE_BACKEND_AUTOLOAD=0']},
            'Mounts':[{'Type':'bind','Source':p,'Destination':p,'RW':rw} for p,rw in mounts.items()]}
    def test_preparation_rejects_previous_validator_before_execution(self):
        legacy='ea8e367417bb1b0990e9c67f4d2cecfb8c70c2c7589c9850e298d7d36c3c1be3'
        self.assertEqual(C.sha(C.HERE/'r3_resume_evidence.py'), C.VALIDATOR)
        with patch.object(C,'VALIDATOR',legacy), patch.object(C,'released') as release:
            with self.assertRaisesRegex(ValueError,'CPU implementation differs'):
                C.prepare(self.root/'plan.json',self.pin,self.root/'new','new-cpu')
            release.assert_not_called()
            self.assertFalse((self.root/'new').exists())

    def test_old_validator_inventory_cannot_be_relabelled_current(self):
        config=dict(self.c,tools={
            str(self.out/'code/r3_resume_recompute.py'):C.VERIFIER,
            str(self.out/'code/r3_resume_evidence.py'):
                'ea8e367417bb1b0990e9c67f4d2cecfb8c70c2c7589c9850e298d7d36c3c1be3'})
        C.atomic(self.config_path,config)
        with self.assertRaisesRegex(ValueError,'CPU tools differ'):
            C.verify(self.config_path,C.sha(self.config_path))

    def test_detached_cpu_command_and_readonly_inputs(self):
        command,mounts,args=C.command(self.c,self.config_path,self.pin)
        self.assertEqual(command[:3],['docker','run','-d']);self.assertNotIn('--rm',command)
        self.assertNotIn('--device',command);self.assertIn('--network=none',command)
        self.assertFalse(mounts[str(self.root/'checkpoint.pt')]);self.assertTrue(mounts[str(self.out)])
        self.assertFalse(mounts[str(self.config_path)])
        C.check_container(self.c,self.config_path,self.pin,self.actual)
    def test_wrong_devices_mounts_and_generation_refused(self):
        for mutate in (lambda a:a['HostConfig'].update(Devices=[{'PathOnHost':'/dev/davinci0'}]),
                       lambda a:a['Mounts'][0].update(RW=not a['Mounts'][0]['RW']),
                       lambda a:a.update(Image='wrong'),
                       lambda a:a['Config']['Env'].append('PYTHONPATH=/synthetic/cpu'),
                       lambda a:a['HostConfig'].update(CapAdd=['SYS_ADMIN']),
                       lambda a:a['Config'].update(Healthcheck={'Test':['CMD','evil']}),
                       lambda a:a['HostConfig'].update(Memory=1)):
            a=self.container();mutate(a)
            with self.assertRaises((ValueError,RuntimeError)):C.check_container(self.c,self.config_path,self.pin,a)
    def test_terminal_without_marker_not_success(self):
        self.actual['State']['Status']='exited'
        with patch.object(C,'verify',return_value=self.c),patch.object(C,'inspect',return_value=self.actual):
            self.assertEqual(C.observe(self.config_path,self.pin)['status'],'needs_repair')
            (self.out/'RECOMPUTED.json').write_text('{}')
            C.atomic(self.out/'EXIT.json',{'exit_code':0,'config_sha256':self.pin,'result_sha256':C.sha(self.out/'RECOMPUTED.json')})
            self.assertEqual(C.observe(self.config_path,self.pin)['status'],'done')
            (self.out/'RECOMPUTED.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'result changed'):C.observe(self.config_path,self.pin)
    def test_ambiguous_intent_never_launches_again(self):
        C.atomic(self.out/'START_INTENT.json',{'config_sha256':self.pin})
        with patch.object(C,'verify',return_value=self.c),patch.object(C,'inspect',return_value=None), \
             patch.object(C.subprocess,'run') as launch:
            self.assertEqual(C.start(self.config_path,self.pin)['status'],'needs_repair')
            launch.assert_not_called()
    def test_release_requires_matching_actual_terminal(self):
        run=self.root/'resume';attempt=run/'attempts/1';attempt.mkdir(parents=True)
        plan={'control_arm':'K1-QO','validation_kind':'current_k1_resume_contract','container':'resume',
              'launcher':'/fixture/launcher.py','chip':0}
        C.atomic(run/'plan.json',plan);C.atomic(run/'SOURCE_PLAN.json',{})
        C.atomic(run/'TRAIN_EXIT.json',{'attempt':1,'exit_code':0})
        C.atomic(attempt/'LAUNCH_RECEIPT.json',{'id':'c'*64})
        C.atomic(attempt/'RELEASE.json',{'container_id':'c'*64})
        C.atomic(run/'SUPERVISOR_RECEIPT.json',{'command':['python3','-P',plan['launcher'],'supervise','--plan',str(run/'plan.json'),'--sha256',self.pin,'--attempt','1']})
        validator=SimpleNamespace(identity=lambda p:self.pin,validate=lambda *a:{})
        actual={'Id':'c'*64,'Image':C.IMAGE,'State':{'Status':'running','ExitCode':0},
                'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':p} for p in
                ('/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci0')]},
                'Config':{'Entrypoint':['python3'],'Cmd':['-P','/workspace/r3_formal_driver.py','--plan',str(run/'plan.json'),'--attempt','1']}}
        with patch.object(C,'inspect',return_value=actual), patch.object(self.policy,'verify_control_resume_container') as effective:
            with self.assertRaisesRegex(ValueError,'actually complete'):C.released(run/'plan.json',self.pin,validator)
            actual['State']['Status']='exited'
            self.assertEqual(C.released(run/'plan.json',self.pin,validator)[3]['container_id'],'c'*64)
            effective.assert_called()
            plan.update(control_arm=None,arm='k1',execution_scope='engineering_only',
                        model='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base',
                        test_read=False,scientific_acceptance=False)
            C.atomic(run/'plan.json',plan)
            self.assertEqual(C.released(run/'plan.json',self.pin,validator)[3]['container_id'],'c'*64)
            effective.assert_called()
            for field,value in (('model','other'),('test_read',True),('execution_scope','formal'),('arm','k2')):
                bad=dict(plan,**{field:value});C.atomic(run/'plan.json',bad)
                with self.assertRaisesRegex(ValueError,'restart identity'):C.released(run/'plan.json',self.pin,validator)
            C.atomic(run/'plan.json',plan)
            actual['Id']='d'*64
            with self.assertRaisesRegex(ValueError,'identity'):C.released(run/'plan.json',self.pin,validator)

    def test_preparation_mounts_original_target_code_for_real_validator(self):
        source=self.root/'source';source.mkdir();code=source/'code';code.mkdir()
        files={}
        for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
            p=code/rel;p.parent.mkdir(exist_ok=True);p.write_text('# fixture\n');files[str(p)]=C.sha(p)
        target=source/'SOURCE_PLAN.json';C.atomic(target,{'code':str(code),'files':files})
        plan=source/'plan.json';C.atomic(plan,{})
        out=self.root/'fresh-cpu'
        with patch.object(C,'released',return_value=({},target,{str(plan):C.sha(plan)},{'container_id':'a'*64})):
            result=C.prepare(plan,self.pin,out,'test-fresh-cpu')
        config=C.load(result['config'])
        self.assertTrue(set(files)<=set(config['files']))
        with patch.object(C,'__file__',str(out/'code/r3_control_resume_cpu.py')):
            C.verify(result['config'],result['sha256'])
        cmd,mounts,args=C.command(config,result['config'],result['sha256'])
        for p in files:self.assertIs(mounts[p],False)
        (code/'kev_aug.py').write_text('changed')
        with patch.object(C,'__file__',str(out/'code/r3_control_resume_cpu.py')):
            with self.assertRaisesRegex(ValueError,'input changed'):C.verify(result['config'],result['sha256'])

if __name__=='__main__':unittest.main()
