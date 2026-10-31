"""Full supervisor with simulated Docker; real temporary resource ledger."""
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
CF=load('closure_flow',HERE/'r3_final_closure.py')
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2')


class Flow(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen source absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);closure=self.root/'closure';CF.prepare(SOURCE,closure)
        self.S=load('supervisor_flow',closure/'r3_code/r3_final_supervisor.py')
        self.out=self.root/'out';self.alloc=self.root/'allocation.json'
        self.alloc.write_text(json.dumps({'allocation':[],'free':[{'chip':i} for i in range(8)]}))
        artifact=lambda n:{'path':str(self.root/(n+'.json')),'sha256':'b'*64}
        self.plan={'image':'sha256:'+'a'*64,'closure':{'root':str(closure)},'chip':1,'arm':'K1',
            'out':str(self.out),'round_dir':str(self.root/'round'),'model':str(self.root/'model'),
            'adapter':None,'adapter_inventory':None,'final':artifact('round/FINAL'),
            'dataset_manifest':artifact('data/manifest'),'base_inventory':artifact('base'),
            'eligibility':artifact('eligibility'),'evidence':{'selection':artifact('selection')}}
        self.path=self.root/'plan.json';self.path.write_text(json.dumps(self.plan));self.pin='c'*64
        self.review=artifact('review');self.spec=self.S.K.contract(self.plan,str(self.path),self.pin,self.review,1)
        self.container=None;self.launches=0;self.exit_code=137;self.timeout=False;self.marker=None
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for obj,name,value in [(self.S.A,'verify',lambda *a:None),
                (self.S.socket,'gethostname',lambda:'k8s-node1'),(self.S.K,'ALLOCATION',str(self.alloc)),
                (self.S.R,'docker_inspect',self.inspect),(self.S.R,'live_chip_conflict',lambda *a:False),
                (self.S.subprocess,'check_output',lambda *a,**k:self.plan['image']+'\n'),
                (self.S.subprocess,'run',self.docker_run)]:
            self.stack.enter_context(patch.object(obj,name,value))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def inspect(self,name):return copy.deepcopy(self.container)

    def docker_run(self,command,**kwargs):
        if command[:2]==['docker','logs']:return subprocess.CompletedProcess(command,0)
        self.assertEqual(command,self.S.K.command(self.spec));self.launches+=1
        self.container={'Id':'retained-actual-id','Name':'/'+self.spec['name'],'Image':self.spec['image'],
            'HostConfig':{'AutoRemove':False,'NetworkMode':'none','Devices':[{'PathOnHost':d} for d in self.spec['devices']]},
            'Config':{'Entrypoint':['python3'],'Cmd':self.spec['cmd'],'Env':[k+'='+v for k,v in self.spec['environment'].items()]},
            'Mounts':[{'Type':'bind','Source':p,'Destination':p,'RW':rw}
                for p,rw in {**self.spec['mounts'],'/usr/local/Ascend/driver':False}.items()],
            'State':{'Status':'exited','ExitCode':self.exit_code,'FinishedAt':'synthetic'}}
        if self.marker is not None:
            directory=self.out/'final-attempts/1';directory.mkdir(parents=True)
            (directory/'EXIT.json').write_text(json.dumps(self.marker))
        if self.timeout:raise subprocess.TimeoutExpired(command,90)
        return subprocess.CompletedProcess(command,0,stdout='retained-actual-id')

    def run_supervisor(self):return self.S.supervise(self.path,self.pin,self.review,1)

    def test_actual_ledger_claim_sigkill_reconciliation_release_and_resume(self):
        result=self.run_supervisor();self.assertEqual(result['exit_code'],137)
        ledger=json.loads(self.alloc.read_text());self.assertEqual(ledger['allocation'],[])
        self.assertTrue((self.out/'supervisor-attempts/1/RELEASE.json').exists())
        self.assertEqual(self.run_supervisor(),result);self.assertEqual(self.launches,1)

    def test_docker_launch_timeout_with_created_container_never_launches_twice(self):
        self.timeout=True;result=self.run_supervisor()
        self.assertEqual(result['exit_code'],137);self.assertEqual(self.launches,1)

    def test_exit_zero_missing_driver_marker_is_failure_after_release(self):
        self.exit_code=0;result=self.run_supervisor()
        self.assertEqual(result['exit_code'],125);self.assertFalse(result['publication_complete'])
        self.assertEqual(self.run_supervisor(),result);self.assertEqual(self.launches,1)

    def test_driver_container_disagreement_retains_claim_and_original_marker(self):
        self.marker={'plan_sha256':self.pin,'attempt':1,'exit_code':0,'publication_complete':True}
        with self.assertRaisesRegex(ValueError,'disagreement'):self.run_supervisor()
        self.assertEqual(len(json.loads(self.alloc.read_text())['allocation']),1)
        self.assertFalse((self.out/'supervisor-attempts/1/RELEASE.json').exists())
        self.assertEqual(json.loads((self.out/'final-attempts/1/EXIT.json').read_text()),self.marker)

    def test_missing_previously_launched_container_never_restarts(self):
        self.run_supervisor();self.container=None
        with self.assertRaisesRegex(ValueError,'do not relaunch'):self.run_supervisor()
        self.assertEqual(self.launches,1)


if __name__=='__main__':unittest.main()
