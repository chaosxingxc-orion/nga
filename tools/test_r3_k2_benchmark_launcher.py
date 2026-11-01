"""Synthetic lifecycle checks; no Docker, real ledger, model or data reads."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('bench_launcher',HERE/'r3_k2_benchmark_launcher.py')
L=importlib.util.module_from_spec(s);s.loader.exec_module(L)

class StopObservation(BaseException):pass

class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.out=self.root/'execution';self.out.mkdir();self.a=self.out/'attempts/1';self.a.mkdir(parents=True)
        self.pin='a'*64;self.plan=self.out/'execution.json';self.plan.write_text('{}')
        self.p={'out':str(self.out),'run':'synthetic','allocation':str(self.root/'ledger.json'),'chip':3,
                'container':'bench','benchmark_sha256':'b'*64}
        self.q={'out':str(self.out/'results')};self.spec={'name':'bench-a1'}
        self.observed={'Id':'c'*64,'State':{'Status':'exited','ExitCode':0}}
        self.R=SimpleNamespace(load=lambda p:{'allocation':[{'chip':3,'run':'synthetic'}],'free':[]},
            docker_inspect=lambda n:self.observed,live_chip_conflict=lambda *a:False,release=lambda a:None)
        self.K=SimpleNamespace(command=lambda s:['docker','run','-d'])
        L.atomic(self.a/'CLAIM.json',{'run':'synthetic','chip':3})
        L.atomic(self.a/'LAUNCH_RECEIPT.json',{'id':'c'*64})
        def module(p):return self.R if Path(p).name=='r3_resource_adapter.py' else self.K
        for target,value in [('verify',lambda *a:(self.p,self.q)),('module',module),('spec',lambda *a:self.spec),
                             ('verify_container',lambda p,s,a,cid=None:a)]:
            x=patch.object(L,target,side_effect=value);x.start();self.addCleanup(x.stop)

    def test_missing_driver_marker_fails_even_actual_zero_then_releases(self):
        L.atomic(self.a/'LAUNCH_INTENT.json',{'command':['docker','run','-d'],'pin':self.pin})
        with patch.object(L.subprocess,'run'),patch.object(self.R,'release') as release:
            result=L.supervise(self.plan,self.pin)
        self.assertEqual(result['exit_code'],125);self.assertFalse(result['benchmark_complete']);release.assert_called_once()

    def test_uncertain_launch_never_runs_docker_again(self):
        L.atomic(self.a/'LAUNCH_INTENT.json',{'command':['docker','run','-d'],'pin':self.pin})
        self.R.docker_inspect=lambda n:None
        with patch.object(L.subprocess,'run') as run,patch.object(L.time,'sleep',side_effect=StopObservation):
            with self.assertRaises(StopObservation):L.supervise(self.plan,self.pin)
        run.assert_not_called();self.assertEqual(L.load(self.out/'digest.json')['state'],'observation_uncertain')

    def test_real_release_rejects_replacement_after_supervisor_verified_exit(self):
        import subprocess
        s=importlib.util.spec_from_file_location('real_resource',HERE/'r3_resource_adapter.py')
        resource=importlib.util.module_from_spec(s);s.loader.exec_module(resource)
        self.R=resource
        ledger=Path(self.p['allocation'])
        L.atomic(ledger,{'allocation':[{'chip':3,'run':'synthetic'}],'free':[]})
        before=ledger.read_bytes()
        L.atomic(self.a/'CLAIM.json',{'schema':'r3-resource-claim-v1','run':'synthetic','chip':3})
        L.atomic(self.a/'LAUNCH_INTENT.json',{'command':['docker','run','-d'],'pin':self.pin})
        result_dir=Path(self.q['out']);result_dir.mkdir()
        L.atomic(result_dir/'EXIT.json',{'exit_code':0,'plan_sha256':self.p['benchmark_sha256']})
        L.atomic(result_dir/'RESULT.json',{'exact_loss_and_gradients':True,'plan_sha256':self.p['benchmark_sha256'],'test_read':False,'scientific_acceptance':False})
        old=dict(self.observed,Name='/bench-a1',HostConfig={'AutoRemove':False})
        replacement={'Id':'new','Name':'/bench-a1','State':{'Status':'running','ExitCode':0},
                     'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci3'}]}}
        def run(cmd,**kwargs):return subprocess.CompletedProcess(cmd,0,'new' if cmd[:3]==['docker','ps','-aq'] else '', '')
        # Initial observation, supervisor verification, release entry, then the
        # inventory sees a different live generation under the identical name.
        with patch.object(resource,'docker_inspect',side_effect=[old,old,old,replacement]),patch.object(L.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(RuntimeError,'live container still owns device'):L.supervise(self.plan,self.pin)
        self.assertEqual(ledger.read_bytes(),before)
        self.assertFalse((self.a/'RELEASE.json').exists())
        self.assertFalse((self.a/'SUPERVISOR_DONE.json').exists())

    def test_released_attempt_only_finishes_durable_record(self):
        terminal={'exit_code':0,'container_exit_code':0,'plan_sha256':self.pin}
        L.atomic(self.a/'EXIT.json',terminal);L.atomic(self.a/'RELEASE.json',{'run':'synthetic','chip':3,'exit_code':0,'container_id':'c'*64})
        with patch.object(self.R,'release') as release,patch.object(L.subprocess,'run') as run:
            self.assertEqual(L.supervise(self.plan,self.pin),terminal)
        release.assert_not_called();run.assert_not_called()

    def test_result_and_terminal_scope_checked_before_success(self):
        L.atomic(self.a/'LAUNCH_INTENT.json',{'command':['docker','run','-d'],'pin':self.pin})
        result_dir=Path(self.q['out']);result_dir.mkdir()
        marker={'exit_code':0,'plan_sha256':self.p['benchmark_sha256']}
        report={'exact_loss_and_gradients':True,'plan_sha256':self.p['benchmark_sha256'],
                'test_read':False,'scientific_acceptance':False}
        for field,value in (('exact_loss_and_gradients',False),('plan_sha256','wrong'),
                            ('test_read',True),('scientific_acceptance',True)):
            L.atomic(result_dir/'EXIT.json',marker)
            L.atomic(result_dir/'RESULT.json',dict(report,**{field:value}))
            with patch.object(L.subprocess,'run'),patch.object(self.R,'release') as release:
                result=L.supervise(self.plan,self.pin)
            self.assertEqual(result['exit_code'],125);self.assertFalse(result['benchmark_complete'])
            release.assert_called_once();(self.a/'SUPERVISOR_DONE.json').unlink()
        L.atomic(result_dir/'RESULT.json',report)
        with patch.object(L.subprocess,'run'),patch.object(self.R,'release'):
            result=L.supervise(self.plan,self.pin)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['result_sha256'],L.sha(result_dir/'RESULT.json'))

    def test_wrong_release_identity_cannot_complete(self):
        L.atomic(self.a/'EXIT.json',{'exit_code':0,'container_exit_code':0,'plan_sha256':self.pin})
        L.atomic(self.a/'RELEASE.json',{'run':'different','chip':3,'exit_code':0})
        with patch.object(self.R,'release') as release:
            with self.assertRaisesRegex(ValueError,'released evidence differs'):L.supervise(self.plan,self.pin)
        release.assert_not_called();self.assertFalse((self.a/'SUPERVISOR_DONE.json').exists())

    def test_actual_container_verifier_rejects_effective_mutations(self):
        import copy
        ns={};exec(compile((HERE/'r3_k2_benchmark_launcher.py').read_bytes(),'<launcher>','exec'),ns)
        k=SimpleNamespace(verify_observation=lambda *a:None)
        policy=SimpleNamespace(verify_effective_policy=lambda *a:None)
        ns['module']=lambda p:k if Path(p).name=='r3_final_container.py' else policy
        spec={'environment':{},'devices':['/dev/davinci3','/dev/davinci_manager']}
        actual={'Mounts':[{'Propagation':'rprivate'}],'HostConfig':{'ShmSize':64*1024**3,
            'Ulimits':[{'Name':'memlock','Soft':-1,'Hard':-1},{'Name':'stack','Soft':67108864,'Hard':67108864}],
            'Devices':[{'PathOnHost':p,'PathInContainer':p,'CgroupPermissions':'rwm'} for p in spec['devices']]}}
        with patch.object(L.subprocess,'check_output',return_value='[{}]'):
            ns['verify_container'](self.p,spec,actual)
            for mutate in (lambda a:a['HostConfig'].update(ShmSize=64*1024**2),
                           lambda a:a['HostConfig'].update(Ulimits=[]),
                           lambda a:a['HostConfig']['Devices'][0].update(PathInContainer='/dev/else'),
                           lambda a:a['HostConfig']['Devices'][0].update(CgroupPermissions='r'),
                           lambda a:a['HostConfig']['Devices'].append(dict(a['HostConfig']['Devices'][0]))):
                bad=copy.deepcopy(actual);mutate(bad)
                with self.assertRaises(ValueError):ns['verify_container'](self.p,spec,bad)

    def test_contract_has_only_train_data_and_pinned_inputs(self):
        K=L.module
        real=SimpleNamespace(ENV={'TASK_QUEUE_ENABLE':'2'})
        p=dict(self.p,benchmark='/run/code/r3_k2_sync_benchmark.py',benchmark_plan='/run/plan.json')
        q={'trainer':'/run/code/train_r3.py'}
        # Use the actual source function, temporarily remove setUp's mocked spec.
        ns={};exec(compile((HERE/'r3_k2_benchmark_launcher.py').read_bytes(),'<launcher>','exec'),ns)
        ns['module']=lambda p:real
        spec=ns['spec'](p,q,self.plan,self.pin)
        self.assertEqual([x for x in spec['mounts'] if x.endswith('.jsonl')],[L.TRAIN])
        self.assertFalse(spec['mounts'][L.TRAIN]);self.assertEqual(spec['environment']['NGA_R0_CODE'],'/run/code/r0_code')

if __name__=='__main__':unittest.main()
