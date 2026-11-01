import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('launch', HERE / 'r3_formal_launcher.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


class Formal(unittest.TestCase):
    def test_formal_scope_flags_rejected_even_with_matching_identity(self):
        for field in ('scientific_acceptance', 'test_read'):
            for value in (True, None, 0):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as td:
                    plan = {'schema': 'r3-formal-k1-plan-v1',
                            'scientific_acceptance': False, 'test_read': False}
                    plan[field] = value
                    path = Path(td) / 'plan.json'
                    path.write_text(json.dumps(plan))
                    with self.assertRaisesRegex(RuntimeError, 'training scope'):
                        L.verify(str(path), L.identity(plan), reviewed=False)

    def test_unit_test_source_is_not_test_dataset(self):
        for p in ('/code/test_k2_shared.py','/code/test_train_r3.py','/data/dev.jsonl'):
            self.assertFalse(L.is_test_data(p))
        for p in ('/data/test.jsonl','/data/test.variants.jsonl','/data/test/shard.parquet'):
            self.assertTrue(L.is_test_data(p))

    def test_missing_container_case_variants_and_daemon_failure(self):
        for message in ('Error: No such object: absent', 'error: no such object: absent'):
            with patch.object(L.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', message)):
                self.assertIsNone(L.inspect('absent'))
        with patch.object(L.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'daemon unreachable')):
            with self.assertRaises(RuntimeError):
                L.inspect('absent')

    def test_uncertain_observation_retries_same_generation(self):
        with tempfile.TemporaryDirectory() as td:
            heartbeat = Path(td) / 'heartbeat.json'
            actual = {'Id': 'same', 'State': {'Status': 'running'}}
            with patch.object(L, 'inspect', side_effect=[RuntimeError('daemon timeout'), None, actual]) as query:
                seen = L.observe_retained('retained', 'same', heartbeat, sleep=lambda _: None)
            self.assertEqual(seen, actual)
            self.assertEqual(query.call_count, 3)
            self.assertEqual(json.loads(heartbeat.read_text())['action'], 'retry_without_restart_or_release')

    def test_container_cannot_see_cephfs_or_test(self):
        p = {'container':'test','chip':1,'code':'/run/code','out':'/run', 'model':'/models/qwen',
             'train_file':'/data/train.jsonl','environment':{'NGA_R0_CODE':'/workspace/r0_code'},'image_sha256':L.IMAGE}
        cmd = L.docker_command(p, '/run/plan.json', 1)
        self.assertIn('--network=none', cmd)
        self.assertIn('--pull=never', cmd)
        self.assertNotIn('--rm', cmd)
        mounts = [cmd[i+1] for i,x in enumerate(cmd) if x=='--mount']
        self.assertEqual(len(mounts),5)
        self.assertTrue(all('test' not in x and 'src=/mnt/cephfs,' not in x for x in mounts))
        self.assertIn('type=bind,src=/run/code,dst=/workspace,readonly', mounts)

    def test_ordinary_formal_retained_container_rejects_extra_configuration(self):
        import copy
        p = {'container':'formal', 'chip':1, 'code':'/run/code', 'out':'/run',
             'model':'/model', 'train_file':'/data/train.jsonl',
             'environment':{'HF_HUB_OFFLINE':'1'}, 'image_sha256':L.IMAGE,
             'schema':'r3-formal-k1-plan-v1'}
        mounts=[]
        cmd=L.docker_command(p,'/run/plan.json',1)
        for i, item in enumerate(cmd):
            if item == '--mount':
                fields=dict(x.split('=',1) if '=' in x else (x,True) for x in cmd[i+1].split(','))
                mounts.append({'Source':fields['src'],'Destination':fields['dst'],
                               'RW':'readonly' not in fields,'Type':'bind'})
        image={'Id':L.IMAGE,'Config':{'Env':['PATH=/bin'],'User':'','WorkingDir':''}}
        observed={'Image':L.IMAGE,'Mounts':mounts,'Config':{'Entrypoint':['python3'],
                  'Cmd':['-P','/workspace/r3_formal_driver.py','--plan','/run/plan.json','--attempt','1'],
                  'Env':['PATH=/bin','HF_HUB_OFFLINE=1']},
                  'HostConfig':{'NetworkMode':'none','Privileged':False,'AutoRemove':False,
                     'ShmSize':64*1024**3,'IpcMode':'private','Runtime':'ascend','CgroupnsMode':'private',
                     'Ulimits':[{'Name':'memlock','Soft':-1,'Hard':-1},
                                {'Name':'stack','Soft':67108864,'Hard':67108864}],
                     'Devices':[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x,'CgroupPermissions':'rwm'}
                                for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci1')]}}
        L.verify_control_resume_container(p,'/run/plan.json',1,observed,image,daemon={'runtime':'ascend','cgroupns':'private'})
        legacy=copy.deepcopy(observed);legacy['HostConfig']['CgroupnsMode']='host'
        L.verify_control_resume_container(p,'/run/plan.json',1,legacy,image,daemon={'runtime':'ascend','cgroupns':'host'})
        with self.assertRaisesRegex(RuntimeError,'CgroupnsMode'):
            L.verify_control_resume_container(p,'/run/plan.json',1,legacy,image,daemon={'runtime':'ascend','cgroupns':'private'})
        for mutate in (lambda d:d['HostConfig'].update(Privileged=True),
                       lambda d:d['Config'].update(Healthcheck={'Test':['CMD-SHELL','touch /run/probe']}),
                       lambda d:d['HostConfig'].update(Memory=67108864),
                       lambda d:d['HostConfig'].update(NanoCpus=1000000),
                       lambda d:d['HostConfig'].update(Runtime='custom'),
                       lambda d:d['HostConfig'].update(Init=True),
                       lambda d:d['HostConfig'].update(NetworkMode='host'),
                       lambda d:d['Config'].update(Entrypoint=['bash']),
                       lambda d:d['Mounts'][0].update(RW=True),
                       lambda d:d['Config']['Env'].append('HF_HUB_OFFLINE=0'),
                       lambda d:d['Config']['Env'].append('PYTHONPATH=/synthetic/out'),
                       lambda d:d['HostConfig'].update(CapAdd=['SYS_ADMIN']),
                       lambda d:d['HostConfig'].update(SecurityOpt=['seccomp=unconfined']),
                       lambda d:d['HostConfig'].update(ShmSize=1),
                       lambda d:d['HostConfig']['Devices'][0].update(PathInContainer='/wrong'),
                       lambda d:d['HostConfig']['Devices'][0].update(CgroupPermissions='r'),
                       lambda d:d['HostConfig']['Ulimits'][0].update(Hard=1)):
            bad=copy.deepcopy(observed);mutate(bad)
            with self.assertRaises(RuntimeError):
                L.verify_control_resume_container(p,'/run/plan.json',1,bad,image,daemon={'runtime':'ascend','cgroupns':'private'})

    def test_retained_container_id_must_match_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);command=['fixture']
            (root/'LAUNCH_RECEIPT.json').write_text(json.dumps({'id':'one','image':L.IMAGE,'plan_sha256':'pin'}))
            (root/'LAUNCH_SPEC.json').write_text(json.dumps({'command':command,'plan_sha256':'pin'}))
            L.verify_retained_receipts(root,'pin',{'Id':'one','Image':L.IMAGE},command)
            with self.assertRaisesRegex(RuntimeError,'identity'):
                L.verify_retained_receipts(root,'pin',{'Id':'other','Image':L.IMAGE},command)

    def test_forbidden_inventory_rejected_before_any_dependency_read(self):
        plan={'schema':'r3-engineering-k1-plan-v1','image_sha256':L.IMAGE,
              'scientific_acceptance':False,'test_read':False,
              'files':{'/safe/code.py':'x','/synthetic/test.jsonl':'y'}}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'plan.json';path.write_text(json.dumps(plan))
            with patch.object(L,'sha',side_effect=AssertionError('must not hash')) as read:
                with self.assertRaisesRegex(RuntimeError,'test dataset'):
                    L.verify(path,L.identity(plan))
                read.assert_not_called()

    def test_review_hash_does_not_cycle_plan_identity(self):
        p = {'schema':'fixture','review_sha256':'PENDING'}
        self.assertEqual(L.identity(p),L.identity(dict(p,review_sha256='abc')))
        self.assertNotEqual(L.identity(p),L.identity(dict(p,schema='changed')))

    def test_driver_startup_error_has_terminal_and_log(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'plan.json').write_text(json.dumps({'out':td,'command':['/missing/executable']}))
            r=subprocess.run([sys.executable,str(HERE/'r3_formal_driver.py'),'--plan',str(root/'plan.json'),'--attempt','1'])
            self.assertEqual(r.returncode,125)
            terminal=json.loads((root/'TRAIN_EXIT.json').read_text())
            self.assertEqual(terminal['exit_code'],125)
            self.assertFalse(terminal['scientific_acceptance'])
            self.assertTrue((root/'attempts/1/FAILED').exists())
            self.assertIn('FileNotFoundError',(root/'attempts/1/run.log').read_text())

    def test_driver_failure_and_success_markers_separate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for attempt,rc in ((1,3),(2,0)):
                (root/'plan.json').write_text(json.dumps({'out':td,'command':[sys.executable,'-c',f'raise SystemExit({rc})']}))
                r=subprocess.run([sys.executable,str(HERE/'r3_formal_driver.py'),'--plan',str(root/'plan.json'),'--attempt',str(attempt)])
                self.assertEqual(r.returncode,rc)
            self.assertTrue((root/'attempts/1/FAILED').exists())
            self.assertTrue((root/'attempts/2/DONE').exists())
            self.assertEqual(json.loads((root/'TRAIN_EXIT.json').read_text())['attempt'],2)


if __name__ == '__main__':
    unittest.main()
