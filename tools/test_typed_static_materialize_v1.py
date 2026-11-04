import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools import typed_static_materialize_v1 as M

class StaticMaterialize(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.old=self.root/'old';self.new=self.root/'new'
        self.old.mkdir();self.new.mkdir()
        M.put(self.old/'RESOURCE-POLICY.json',{'schema':'PREPARATION_ONLY_NO_RESOURCE_CLAIM'})
        M.put(self.new/'RESOURCE-POLICY.json',{'schema':'PREPARATION_ONLY_NO_RESOURCE_CLAIM'})
        self.config={'run_id':'old','container':'nga-old','output':str(self.old/'output'),
          'model':{'path':'/models/qwen'},'resources':{'chip':1,'allocation':'/allocation.json','policy':M.ref(self.old/'RESOURCE-POLICY.json')},
          'files':{str(self.old/'RESOURCE-POLICY.json'):M.sha(self.old/'RESOURCE-POLICY.json'),str(self.old/'cpu/gold.jsonl'):'a'*64},
          'population':{'gold':{'path':str(self.old/'cpu/gold.jsonl'),'sha256':'a'*64},'count':2000}}
    def test_rebind_only_identity_resource_locations(self):
        before=copy.deepcopy(self.config);r=M.rebind_config(self.config,self.old,self.new,5,{'schema':'PREPARATION_ONLY_NO_RESOURCE_CLAIM'})
        self.assertEqual(before,self.config);self.assertEqual(r['model'],before['model'])
        self.assertEqual(r['population']['count'],2000);self.assertEqual(r['population']['gold']['sha256'],'a'*64)
        self.assertEqual(r['population']['gold']['path'],str(self.new/'cpu/gold.jsonl'));self.assertEqual(r['resources']['chip'],5)
        self.assertNotIn(str(self.old/'RESOURCE-POLICY.json'),r['files'])
    def test_bool_chip_rejected(self):
        with self.assertRaisesRegex(ValueError,'chip'):M.rebind_config(self.config,self.old,self.new,True,{})
    def test_copy_mutation_rejected(self):
        p=self.old/'data';p.write_text('source');pin=M.sha(p);p.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):M.copy_checked(p,self.new/'data',pin)
        self.assertFalse((self.new/'data').exists())
    def test_copy_exclusive_and_exact(self):
        p=self.old/'data';p.write_bytes(b'abc');q=self.new/'data';M.copy_checked(p,q,M.sha(p));self.assertEqual(p.read_bytes(),q.read_bytes())
        with self.assertRaises(FileExistsError):M.copy_checked(p,q,M.sha(p))
    def test_symlink_rejected(self):
        p=self.old/'link';p.symlink_to(self.new)
        with self.assertRaisesRegex(ValueError,'unsafe'):M.safe(p/'file')
    def test_resource_reference_changed(self):
        p=self.old/'decision';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'resource reference'):M.rebind_config(self.config,self.old,self.new,1,{'priority_refs':[{'path':str(p),'sha256':'0'*64}]})
    def test_resource_pin_cannot_replace_static(self):
        p=self.old/'static';p.write_text('{}');self.config['files'][str(p)]='0'*64
        # External static pin collision cannot be overwritten by resource evidence.
        p=self.root/'external';p.write_text('{}');self.config['files'][str(p)]='0'*64
        with self.assertRaisesRegex(ValueError,'conflict'):M.rebind_config(self.config,self.old,self.new,1,{'priority_refs':[M.ref(p)]})
    def test_original_resource_policy_changed(self):
        (self.old/'RESOURCE-POLICY.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'source policy changed'):M.rebind_config(self.config,self.old,self.new,1,{})
    def test_adapter_rejects_changed_materializer(self):
        from tools import typed_static_successor_prepare_v1 as A
        p=self.old/'prepare.json';M.put(p,{'schema':'typed-static-bound-prepare-v1','materializer':{'path':str(self.old/'RESOURCE-POLICY.json'),'sha256':'0'*64}})
        with self.assertRaisesRegex(ValueError,'materializer changed'):A.prepare(p)
    def test_checked_reference_mutation(self):
        p=self.old/'doc';M.put(p,{'x':1});r=M.ref(p);p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'reference changed'):M.checked(r)

if __name__=='__main__':unittest.main()
