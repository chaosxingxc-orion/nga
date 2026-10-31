import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('container_contract',Path(__file__).with_name('r3_final_container.py'))
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


class Container(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);artifact=lambda n:{'path':str(root/(n+'.json')),'sha256':'b'*64}
        self.plan={'chip':1,'image':'sha256:'+'a'*64,'closure':{'root':str(root/'code')},
            'out':str(root/'out'),'round_dir':str(root/'round'),'model':str(root/'model'),
            'adapter':None,'adapter_inventory':None,'final':artifact('round/FINAL'),
            'dataset_manifest':artifact('data/manifest'),'base_inventory':artifact('inventory'),
            'eligibility':artifact('eligibility'),'evidence':{'selection':artifact('selection')}}
        self.spec=C.contract(self.plan,str(root/'plan.json'),'c'*64,artifact('review'),1)
        self.observed={'Id':'actual-container-id','Name':'/'+self.spec['name'],'Image':self.spec['image'],
            'HostConfig':{'AutoRemove':False,'NetworkMode':'none','Privileged':False,
                'Devices':[{'PathOnHost':d} for d in self.spec['devices']]},
            'Config':{'Entrypoint':['python3'],'Cmd':self.spec['cmd'],
                'Env':[k+'='+v for k,v in self.spec['environment'].items()]},
            'Mounts':[{'Type':'bind','Source':p,'Destination':p,'RW':rw}
                for p,rw in {**self.spec['mounts'],'/usr/local/Ascend/driver':False}.items()],
            'State':{'Status':'running','ExitCode':0,'FinishedAt':'synthetic'}}

    def test_detached_retained_exact_mount_contract(self):
        cmd=C.command(self.spec)
        self.assertIn('-d',cmd);self.assertNotIn('--rm',cmd);self.assertIn('--network=none',cmd)
        self.assertEqual(len([x for x in self.spec['mounts'] if x.endswith('.jsonl')]),6)
        self.assertTrue(all(not rw for p,rw in self.spec['mounts'].items() if p.endswith('.jsonl')))
        C.verify_observation(self.spec,self.observed,'actual-container-id')

    def test_wrong_generation_device_command_or_mount_rejected(self):
        for kind in ('id','device','command','mount','privileged'):
            d=copy.deepcopy(self.observed)
            if kind=='id':d['Id']='other'
            elif kind=='device':d['HostConfig']['Devices'].append({'PathOnHost':'/dev/davinci2'})
            elif kind=='command':d['Config']['Cmd']=['unreviewed']
            elif kind=='mount':d['Mounts'][0]['RW']=not d['Mounts'][0]['RW']
            else:d['HostConfig']['Privileged']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                C.verify_observation(self.spec,d,'actual-container-id')

    def test_live_or_unobserved_container_cannot_be_released(self):
        with self.assertRaisesRegex(ValueError,'not exited'):
            C.reconcile_exit(self.observed,None,plan_sha256='c'*64,attempt=1)
        with self.assertRaisesRegex(ValueError,'missing'):
            C.verify_observation(self.spec,None,'actual-container-id')

    def test_sigkill_missing_marker_is_failure_evidence(self):
        self.observed['State'].update(Status='exited',ExitCode=137)
        m=C.reconcile_exit(self.observed,None,plan_sha256='c'*64,attempt=1)
        self.assertEqual(m['exit_code'],137);self.assertFalse(m['publication_complete'])

    def test_exit_zero_without_marker_is_not_success(self):
        self.observed['State']['Status']='exited'
        m=C.reconcile_exit(self.observed,None,plan_sha256='c'*64,attempt=1)
        self.assertEqual(m['exit_code'],125);self.assertEqual(m['container_exit_code'],0)
        self.assertEqual(C.reconcile_exit(self.observed,m,plan_sha256='c'*64,attempt=1),m)

    def test_disagreement_does_not_rewrite_driver_marker(self):
        self.observed['State'].update(Status='exited',ExitCode=137)
        marker={'plan_sha256':'c'*64,'attempt':1,'exit_code':0,'publication_complete':True}
        before=copy.deepcopy(marker)
        with self.assertRaisesRegex(ValueError,'disagreement'):
            C.reconcile_exit(self.observed,marker,plan_sha256='c'*64,attempt=1)
        self.assertEqual(marker,before)


if __name__=='__main__':unittest.main()
