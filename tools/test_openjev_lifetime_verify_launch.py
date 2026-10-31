#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('cpu_launch',HERE/'openjev_lifetime_verify_launch.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Evidence:
    def __init__(self):self.snapshots={}
    def frozen(self,files):
        for f,h in files.items():
            if m.sha(f)!=h:raise ValueError('Frozen differs')
    def verify(self):pass
    def load(self,f):return m.load(f)

class Durable:
    @staticmethod
    def publish_new(f,v):
        with Path(f).open('x') as out:json.dump(v,out)

class Queue:
    def __init__(self,spec):self.value=None;self.spec=spec;self.calls=[]
    def inspect(self,name):return self.value
    def binding(self,actual,spec,receipt=None):
        if actual is None:raise ValueError('Missing Docker')
        if receipt and actual['Id']!=receipt['container_id']:raise ValueError('Receipt differs')
    def docker(self,method,path,value=None):
        self.calls.append(path)
        if '/create?' in path:self.value={'Id':'cpu-123','HostConfig':copy.deepcopy(self.spec['HostConfig']),'State':{'Status':'created','StartedAt':'','ExitCode':0}}
        elif path.endswith('/start'):self.value['State'].update(Status='running',StartedAt='time1')

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
        self.spec=dict(Image=m.IMAGE,Cmd=['bash',str(self.out/'run.sh')],Env=['TORCH_DEVICE_BACKEND_AUTOLOAD=0'],
            Entrypoint=['bash'],HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs','/var/run/docker.sock:/var/run/docker.sock'],
            Devices=[],NetworkMode='none',AutoRemove=False,NanoCpus=2000000000,Memory=4*2**30,ShmSize=64*2**20))
        self.q=Queue(self.spec);self.r={'container':'cpu'}
        for n,v in [('CPU_SPEC.json',self.spec),('PARENT_REVIEW.json',{'approved':True,'approved_request_sha256':'pin'})]:
            (self.out/n).write_text(json.dumps(v))
        (self.out/'REQUEST.sha256').write_text('pin\n');(self.out/'run.sh').write_text('wrapper')
        self.ctx=(self.r,self.out,Durable,Evidence(),self.q,self.spec)
    def launch(self):
        with patch.object(m,'context',return_value=self.ctx),patch.object(m.socket,'gethostname',return_value='k8s-node1'):
            return m.launch(self.out/'request.json','pin')
    def test_no_devices_spec(self):m.safe_spec(self.spec,self.out)
    def test_device_exposure_rejected(self):
        for key,val in [('Devices',[{'PathOnHost':'/dev/davinci1'}]),('Privileged',True),('Binds',['/dev:/dev']),('AutoRemove',True)]:
            s=copy.deepcopy(self.spec);s['HostConfig'][key]=val
            with self.assertRaises(ValueError):m.safe_spec(s,self.out)
    def test_launch_created_then_running_idempotent(self):
        self.assertEqual(self.launch()['status'],'running');self.launch();self.assertEqual(len(self.q.calls),2)
    def test_stopped_generation_never_restarted(self):
        self.launch();self.q.value['State']['Status']='exited'
        with self.assertRaises(ValueError):self.launch()
        self.assertEqual(len(self.q.calls),2)
    def test_running_without_receipt_fails(self):
        self.launch();(self.out/'LAUNCH_RECEIPT.json').unlink()
        with self.assertRaises(ValueError):self.launch()
    def test_missing_container_with_receipt_fails(self):
        self.launch();self.q.value=None
        with self.assertRaises(ValueError):self.launch()
    def test_preexisting_unowned_container_fails(self):
        self.q.value={'Id':'other','State':{'Status':'created'}}
        with self.assertRaises(ValueError):self.launch()
    def test_wrong_receipt_id_fails(self):
        self.launch();r=m.load(self.out/'LAUNCH_RECEIPT.json');r['container_id']='other';(self.out/'LAUNCH_RECEIPT.json').write_text(json.dumps(r))
        with self.assertRaises(ValueError):self.launch()
    def test_wrong_request_approval_fails(self):
        (self.out/'PARENT_REVIEW.json').write_text('{"approved":true,"approved_request_sha256":"wrong"}')
        with self.assertRaises(ValueError):self.launch()
    def test_existing_terminal_fails(self):
        (self.out/'COMPLETE.json').write_text('{}')
        with self.assertRaises(ValueError):self.launch()
    def test_authenticated_module_exact_bytes(self):
        p=self.out/'x.py';p.write_text('value=23\n');pin=m.sha(p);self.assertEqual(m.module(p,pin).value,23)
        p.write_text('raise RuntimeError("must not execute")\n')
        with self.assertRaises(ValueError):m.module(p,pin)
    def test_symlink_path_rejected(self):
        p=self.out/'real';p.write_text('hi');link=self.out/'link';link.symlink_to(p)
        with self.assertRaises(ValueError):m.raw(link)

if __name__=='__main__':unittest.main()
