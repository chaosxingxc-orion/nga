#!/usr/bin/env python3
"""Real-filesystem launch crash recovery with synthetic Docker transport."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent

def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

m=module('openjev_lifetime_launch');d=module('e38_evidence');old=module('prepare_openjev_path_trace');proto=module('openjev_lifetime_protocol')

class Evidence:
    def sha(self,p):return d.Snapshot(p).sha256
    def verify(self,**kw):pass

class Queue:
    def __init__(self):self.actual=None;self.starts=0;self.creates=0;self.crash=None;self.clock=0
    def load(self,p):return json.loads(Path(p).read_bytes())
    def utc(self):self.clock+=1;return 'time'+str(self.clock)
    def atomic(self,p,value):
        Path(p).write_text(json.dumps(value))
        if self.crash=='claim':self.crash=None;raise RuntimeError('lost claim response')
    def inspect(self,name):return self.actual
    def binding(self,actual,spec,receipt=None):
        if actual is None or actual['spec']!=spec:raise ValueError('Docker binding differs')
        if receipt and receipt['container_id']!=actual['Id']:raise ValueError('Docker receipt differs')
    def chip_access(self,actual,chip):return True
    def docker(self,method,path,value=None):
        if method=='GET':return [{'Id':self.actual['Id']}] if self.actual else []
        if '/create?' in path:
            self.creates+=1;self.actual={'Id':'retained-id','spec':value,'State':{'Status':'created'}}
            if self.crash=='create':self.crash=None;raise RuntimeError('lost create response')
        elif path.endswith('/start'):
            self.starts+=1;self.actual['State']['Status']='running'
            if self.crash=='start':self.crash=None;raise RuntimeError('lost start response')

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.out=self.root/'run';self.out.mkdir();self.allocation=self.root/'allocation.json'
        self.before={'allocation':[{'chip':4,'run':'other'}],'free':[{'chip':1},{'chip':7}],'metadata':'retain'}
        self.allocation.write_text(json.dumps(self.before));self.q=Queue();self.e=Evidence()
        self.p={'container':'test','wrapper':str(self.out/'run.sh'),'container_spec':str(self.out/'spec.json')}
        self.spec={'Cmd':['bash',self.p['wrapper']],'Entrypoint':['entry']}
        (self.out/'spec.json').write_text(json.dumps(self.spec));(self.out/'run.sh').write_text('wrapper')
        (self.out/'PARENT_REVIEW.json').write_text('{}');(self.out/'PLAN.sha256').write_text('pin\n')
        self.empty_checks=0
    def free(self,q,chip,ignore=None):
        self.empty_checks+=1
        if self.q.actual and self.q.actual['State']['Status']=='running':raise ValueError('physical NPU busy')
    def launch(self):
        with patch.object(old,'free_now',side_effect=self.free):
            return m.transaction(self.p,'pin',self.out,self.spec,self.q,self.e,d,old,proto,self.allocation)
    def test_running_recovery_needs_no_empty_npu(self):
        self.assertEqual(self.launch()['status'],'running');count=self.empty_checks
        self.assertEqual(self.launch()['status'],'running');self.assertEqual(self.empty_checks,count)
        self.assertEqual((self.q.creates,self.q.starts),(1,1))
    def test_lost_claim_response(self):
        self.q.crash='claim'
        with self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(self.launch()['status'],'running');self.assertEqual(self.q.starts,1)
    def test_lost_create_response(self):
        self.q.crash='create'
        with self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(self.launch()['status'],'running');self.assertEqual(self.q.creates,1)
    def test_lost_start_response(self):
        self.q.crash='start'
        with self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(self.launch()['status'],'running');self.assertEqual(self.q.starts,1)
    def test_pending_receipt_preserves_time_bytes(self):
        original=d.publish_new;retained={}
        def interrupted(path,value):
            if Path(path).name=='LAUNCH_RECEIPT.json':
                pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
                retained['raw']=pending.read_bytes();raise RuntimeError('receipt pending')
            return original(path,value)
        with patch.object(d,'publish_new',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(self.launch()['status'],'running')
        self.assertEqual((self.out/'LAUNCH_RECEIPT.json').read_bytes(),retained['raw'])
    def test_pending_claim_preserves_original_time(self):
        original=d.publish_new
        def interrupted(path,value):
            if Path(path).name=='CLAIM.json':
                Path(str(path)+'.pending').write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
                raise RuntimeError('claim pending')
            return original(path,value)
        with patch.object(d,'publish_new',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.launch()
        saved=self.q.load(self.out/'CLAIM.json.pending')
        self.launch();self.assertEqual(self.q.load(self.allocation),saved['after'])
    def test_changed_pending_receipt_rejected(self):
        self.q.crash='create'
        with self.assertRaises(RuntimeError):self.launch()
        (self.out/'LAUNCH_RECEIPT.json.pending').write_text('{"container_id":"other"}')
        with self.assertRaises(ValueError):self.launch()
        self.assertEqual(self.q.starts,0)
    def test_running_missing_receipt_rejected(self):
        self.launch();(self.out/'LAUNCH_RECEIPT.json').unlink()
        with self.assertRaises(ValueError):self.launch()
    def test_other_owners_unchanged(self):
        self.launch();a=self.q.load(self.allocation)
        self.assertEqual(a['allocation'][0],self.before['allocation'][0]);self.assertEqual(a['free'],[{'chip':7}])
        self.assertEqual(a['metadata'],'retain')
    def test_terminal_cannot_restart(self):
        self.launch();(self.out/'EXIT').write_text('rc=0')
        with self.assertRaises(ValueError):self.launch()
    def test_stopped_container_cannot_restart(self):
        self.launch();self.q.actual['State']['Status']='exited'
        with self.assertRaises(ValueError):self.launch()
    def test_bootstrap_script_sanitizes_before_python(self):
        source=(HERE/'openjev_lifetime_prepare.py').read_text()
        self.assertIn('unset PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP',source)
        self.assertIn('export PYTHONNOUSERSITE=1',source)
        self.assertIn('/usr/local/python3.12.13/bin/python3 -B -S -s -P',source)
        self.assertNotIn('cd /tmp',source)

if __name__=='__main__':unittest.main()
