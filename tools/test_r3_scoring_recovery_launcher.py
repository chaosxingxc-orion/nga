import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('launcher',Path(__file__).with_name('r3_scoring_recovery_launcher.py'))
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)


class RecoveryLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'run';self.out.mkdir()
        self.q={'out':str(self.out/'results'),'model':str(self.root/'model'),
                'schema':'r3-dev-scoring-recovery-v1',
                'protocol':{'records_per_suite':4,'chunk':2,'mode':'rightpad','dtype':'float32',
                            'hf32':False,'token_budget':16384,'max_abs_nats':1e-3},
                'adapter':str(self.root/'adapter'),'adapter_inventory':{'path':str(self.root/'adapter-inventory.json')},
                'closure':{'root':str(self.root/'closure')},'base_inventory':{'path':str(self.out/'inventory.json')},
                'sources':{s:{'path':str(self.root/'KEV'/s/'dev.jsonl')} for s in ('decision-v7','transfer-v4')}}
        self.p={'out':str(self.out),'probe_plan_sha256':'a'*64,'chip':3,'container':'nga-r3-eng-recovery-test',
                'launcher':str(self.out/'execution-tools/r3_scoring_recovery_launcher.py'),
                'probe_plan':str(self.out/'probe.json'),'probe':str(self.out/'probe.py')}
        for name in ('reference','interrupted'):(self.out/'results'/name).mkdir(parents=True)
        self.actual={'Id':'actual','State':{'Status':'exited','ExitCode':137}}

    def ready(self):
        L.atomic(self.out/'results/interrupted/INTERRUPT_READY.json',
            {'plan_sha256':self.p['probe_plan_sha256'],'committed':2,'keys':['a','b']})

    def test_137_is_expected_only_in_interrupt(self):
        self.ready()
        self.assertTrue(L.outcome(self.p,self.q,'interrupt',self.actual)['expected_exit'])
        for phase in ('reference','resume'):
            with self.assertRaisesRegex(ValueError,'failed'):L.outcome(self.p,self.q,phase,self.actual)

    def test_interrupt_requires_committed_proof_and_plan_pin(self):
        with self.assertRaises(FileNotFoundError):L.outcome(self.p,self.q,'interrupt',self.actual)
        self.ready();path=self.out/'results/interrupted/INTERRUPT_READY.json'
        for change in ({'committed':3},{'keys':['a','a']},{'plan_sha256':'b'*64}):
            self.ready();doc=L.load(path);doc.update(change);L.atomic(path,doc)
            with self.assertRaisesRegex(ValueError,'proof'):L.outcome(self.p,self.q,'interrupt',self.actual)

    def test_success_requires_complete_resume_and_finite_numeric_bound(self):
        self.actual['State']['ExitCode']=0
        d={'plan_sha256':self.p['probe_plan_sha256'],'phase':'resume','rows':8,'newly_scored':6,'committed_reused':2,'status':'ENGINEERING_RECOVERY_PASS',
            'max_abs_nats':0.,'test_read':False,'scientific_acceptance':False}
        path=self.out/'results/interrupted/DONE.json';L.atomic(path,d)
        self.assertTrue(L.outcome(self.p,self.q,'resume',self.actual)['expected_exit'])
        for change in ({'plan_sha256':'b'*64},{'rows':7},{'newly_scored':8},{'max_abs_nats':float('nan')},{'max_abs_nats':.002}):
            path.write_text(json.dumps({**d,**change}))
            with self.assertRaises(ValueError):L.outcome(self.p,self.q,'resume',self.actual)

    def test_live_container_never_accepted(self):
        self.ready();self.actual['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'live'):L.outcome(self.p,self.q,'interrupt',self.actual)

    def test_production_chunk_rejects_old_small_completion(self):
        self.q['schema']='r3-dev-scoring-recovery-v2'
        self.q['protocol'].update(records_per_suite=32,chunk=32)
        self.ready()
        with self.assertRaisesRegex(ValueError,'proof'):
            L.outcome(self.p,self.q,'interrupt',self.actual)
        L.atomic(self.out/'results/interrupted/INTERRUPT_READY.json',
                 {'plan_sha256':self.p['probe_plan_sha256'],'committed':32,'keys':list(map(str,range(32)))})
        self.assertTrue(L.outcome(self.p,self.q,'interrupt',self.actual)['expected_exit'])
        self.actual['State']['ExitCode']=0
        d={'plan_sha256':self.p['probe_plan_sha256'],'phase':'resume','rows':64,'newly_scored':32,
           'committed_reused':32,'status':'ENGINEERING_RECOVERY_PASS','max_abs_nats':0.,
           'test_read':False,'scientific_acceptance':False}
        path=self.out/'results/interrupted/DONE.json';L.atomic(path,d)
        self.assertTrue(L.outcome(self.p,self.q,'resume',self.actual)['expected_exit'])
        for change in ({'rows':8},{'newly_scored':6},{'committed_reused':2}):
            L.atomic(path,{**d,**change})
            with self.assertRaises(ValueError):L.outcome(self.p,self.q,'resume',self.actual)

    def test_mounts_only_dev_and_retained_exact_device(self):
        K=Mock(ENV={'HF_HUB_OFFLINE':'1'})
        with patch.object(L,'module',return_value=K):
            spec=L.contract(self.p,self.q,self.out/'execution.json','b'*64,'reference',1)
        self.assertEqual([k for k in spec['mounts'] if k.endswith('.jsonl')],
            [v['path'] for v in self.q['sources'].values()])
        self.assertFalse(spec['mounts'][self.q['model']]);self.assertTrue(spec['mounts'][str(self.out)])
        self.assertEqual(spec['devices'][-1],'/dev/davinci3')
        self.assertIn('-B',spec['cmd']);self.assertNotIn('-I',spec['cmd'])
        Kreal=L.module(Path(__file__).with_name('r3_final_container.py'),'contract_test')
        cmd=Kreal.command(spec);self.assertIn('-d',cmd);self.assertNotIn('--rm',cmd);self.assertIn('--network=none',cmd)

    def test_dataset_directory_or_writable_model_overlap_refused(self):
        q=copy.deepcopy(self.q);q['sources']['decision-v7']['path']=str(self.root/'KEV')
        with self.assertRaisesRegex(ValueError,'dev-only'):L.contract(self.p,q,self.out/'execution.json','b'*64,'reference',1)
        q=copy.deepcopy(self.q);q['model']=str(self.out/'model')
        with self.assertRaisesRegex(ValueError,'overlap'):L.contract(self.p,q,self.out/'execution.json','b'*64,'reference',1)

    def test_uncertain_observation_only_reobserves_same_name(self):
        R=Mock();K=Mock();K.verify_observation.side_effect=lambda s,a,c:a
        R.docker_inspect.side_effect=[RuntimeError('transient'),None,self.actual];sleep=Mock()
        with patch.object(L.subprocess,'run') as launch:
            self.assertEqual(L.observe(R,K,{'name':'same'},'actual',self.out/'digest.json',sleep),self.actual)
        launch.assert_not_called();self.assertEqual(sleep.call_count,2)
        self.assertEqual([c.args for c in R.docker_inspect.call_args_list],[('same',)]*3)

    def test_launch_timeout_is_not_retried_and_actual_exit_reconciled(self):
        self.ready();R=Mock();R.live_chip_conflict.return_value=False;K=Mock();K.command.return_value=['docker','run','fixed']
        R.docker_inspect.return_value=None;K.verify_observation.side_effect=lambda s,a,c:a
        directory=self.out/'interrupt';spec={'name':'same'}
        with patch.object(L,'contract',return_value=spec), \
             patch.object(L,'observe',return_value={**self.actual,'Image':L.IMAGE}) as observe, \
             patch.object(L.subprocess,'run',side_effect=[subprocess.TimeoutExpired('docker',90),Mock()]) as command:
            _,actual,result=L.phase_run(self.p,self.q,self.out/'execution.json','b'*64,'interrupt',R,K,directory)
        self.assertTrue(result['expected_exit']);self.assertEqual(command.call_count,2)
        self.assertEqual(command.call_args_list[0].args[0],['docker','run','fixed'])
        self.assertEqual(command.call_args_list[1].args[0],['docker','logs','actual'])
        self.assertTrue((directory/'ACTUAL_EXIT.json').exists());observe.assert_called_once()

    def test_existing_intent_missing_container_never_relaunches(self):
        self.ready();directory=self.out/'interrupt';directory.mkdir();R=Mock();R.docker_inspect.return_value=None
        K=Mock();K.command.return_value=['docker','run','fixed'];spec={'name':'same'}
        L.atomic(directory/'LAUNCH_INTENT.json',{'plan_sha256':'b'*64,'phase':'interrupt','command':K.command.return_value})
        with patch.object(L,'contract',return_value=spec), \
             patch.object(L,'observe',return_value={**self.actual,'Image':L.IMAGE}), \
             patch.object(L.subprocess,'run') as command:
            L.phase_run(self.p,self.q,self.out/'execution.json','b'*64,'interrupt',R,K,directory)
        command.assert_called_once();self.assertEqual(command.call_args.args[0],['docker','logs','actual'])

    def test_release_completed_crash_does_not_reclaim_or_launch(self):
        directory=self.out/'attempts/1';directory.mkdir(parents=True)
        p={**self.p,'run':'r3_runs/test','allocation':'unused','resource_adapter':'unused'}
        terminal={'plan_sha256':'b'*64,'container_exit_code':0,'phases':[{'phase':'resume'}]}
        L.atomic(directory/'EXIT.json',terminal)
        L.atomic(directory/'RELEASE.json',{'run':p['run'],'chip':p['chip'],'exit_code':0})
        R=Mock();K=Mock()
        with patch.object(L.socket,'gethostname',return_value='k8s-node1'), \
             patch.object(L,'verify',return_value=(p,self.q)),patch.object(L,'module',side_effect=[R,K]), \
             patch.object(L,'phase_run') as phase,patch.object(L.subprocess,'check_output') as image:
            self.assertEqual(L.supervise(self.out/'execution.json','b'*64,1),terminal)
        R.claim.assert_not_called();R.release.assert_not_called();phase.assert_not_called();image.assert_not_called()
        self.assertEqual(L.load(directory/'SUPERVISOR_DONE.json'),terminal)

    def test_release_intent_reconciles_before_reentering_phase_chain(self):
        directory=self.out/'attempts/1';directory.mkdir(parents=True)
        p={**self.p,'run':'r3_runs/test','allocation':'unused','resource_adapter':'unused'}
        terminal={'plan_sha256':'b'*64,'container_exit_code':0,'phases':[{'phase':'resume'}]}
        L.atomic(directory/'EXIT.json',terminal);L.atomic(directory/'RELEASE.json.intent',{'pending':True})
        R=Mock();K=Mock()
        R.release.side_effect=lambda args:L.atomic(directory/'RELEASE.json',{'run':p['run'],'chip':p['chip'],'exit_code':0})
        with patch.object(L.socket,'gethostname',return_value='k8s-node1'), \
             patch.object(L,'verify',return_value=(p,self.q)),patch.object(L,'module',side_effect=[R,K]), \
             patch.object(L,'contract',return_value={'name':'resume'}),patch.object(L,'phase_run') as phase:
            self.assertEqual(L.supervise(self.out/'execution.json','b'*64,1),terminal)
        R.release.assert_called_once();R.claim.assert_not_called();phase.assert_not_called()

    def test_launch_conflict_never_writes_intent_or_launches(self):
        R=Mock();R.docker_inspect.return_value=None;R.live_chip_conflict.return_value=True
        K=Mock();K.command.return_value=['docker','run','fixed'];directory=self.out/'interrupt'
        with patch.object(L,'contract',return_value={'name':'same'}),patch.object(L.subprocess,'run') as launch:
            with self.assertRaisesRegex(ValueError,'still owns device'):
                L.phase_run(self.p,self.q,self.out/'execution.json','b'*64,'interrupt',R,K,directory)
        launch.assert_not_called();self.assertFalse((directory/'LAUNCH_INTENT.json').exists())

    def test_atomic_files_readable_by_host(self):
        p=self.out/'marker.json';L.atomic(p,{'ok':True})
        self.assertEqual(p.stat().st_mode & 0o777,0o644)

if __name__=='__main__':unittest.main()
