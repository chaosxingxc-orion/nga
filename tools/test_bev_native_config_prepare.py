import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('bev_native_config_prepare.py'))
B=importlib.util.module_from_spec(s);s.loader.exec_module(B)

class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
    def put(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value));return B.ref(p)
    def test_changed_source_rejected(self):
        r=self.put('pin.json',{'x':1});Path(r['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'source changed'):B.pinned(r)
    def test_symlink_and_relative_refs_rejected(self):
        p=self.root/'real';p.write_text('{}');link=self.root/'link';link.symlink_to(p)
        for v in [str(link),'relative']:
            with self.assertRaises(ValueError):B.safe(v)
    def test_real_serialize_preserves_all_execution_modules(self):
        mod=self.put('module.json',{})
        modules={k:mod for k in ('contract','runtime','loader','native','host','probe','resource','resource_base','upstream_binding')}
        refs={name:self.put(name+'.json',{}) for name in ('template','configuration','registry','resource_policy','upstream')}
        out=self.root/'fresh';model=self.root/'model';model.mkdir();weights=model/'weights';weights.write_text('weights')
        c={'run_id':'fresh','output':str(out/'output'),'model':'m','protocol':'p','resources':'r','inputs':{'path':str(weights),'sha256':B.sha(weights),'count':3}}
        reg={'platform':{'output_root':str(self.root)},'model':{'m':{'path':str(model),'model_manifest_sha256':'modelpin','files':{str(weights):B.sha(weights)}}},'protocol':{'p':{'variants':['a','b','c']}},'resources':{'r':{'chip':7}}}
        values={'template':{'schema':'native-config-execution-v1','modules':modules,'host_name':'host'},'configuration':c,'registry':reg,'resource_policy':{'run':'r3_runs/fresh','chip':7,'scientific_acceptance':False,'test_read':False,'allocation':'/alloc'},'upstream':{'root':'/upstream'}}
        for name,v in values.items():Path(refs[name]['path']).write_text(json.dumps(v));refs[name]=B.ref(refs[name]['path'])
        spec={'schema':'native-config-prepare-v1',**refs,'root':str(out)};pr=self.put('prepare.json',spec)
        fake=types.SimpleNamespace(validate=lambda *a:None,ENV={},IMAGE='image',PINS={},digest=lambda value:'contract',mounts=lambda *a:[],verify=lambda *a:None,command=lambda *a:['retained-command'])
        with patch.object(B,'module',return_value=fake):result=B.prepare(pr['path'],pr['sha256'])
        plan=json.loads((out/'PLAN.json').read_text());self.assertTrue(result['executable_modules_unchanged']);self.assertEqual(result['forwards'],9)
        self.assertEqual(plan['modules']['runtime'],modules['runtime']);self.assertFalse(result['npu_launched']);self.assertFalse(result['resource_admission_checked'])
        with patch.object(B,'module',return_value=fake),self.assertRaisesRegex(ValueError,'package exists'):B.prepare(pr['path'],pr['sha256'])
    def test_invalid_spec_rejected_without_creating_package(self):
        r=self.put('invalid.json',{'schema':'native-config-prepare-v1','root':str(self.root/'out')})
        with self.assertRaisesRegex(ValueError,'fields'):B.prepare(r['path'],r['sha256'])
        self.assertFalse((self.root/'out').exists())

if __name__=='__main__':unittest.main()
