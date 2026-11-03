import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from tools import bev_native_config_contract as C

class Contract(unittest.TestCase):
 def fixture(self,p):
  rows=[{'i':0,'input_ids':[7,8]}];f=p/'requests.jsonl';f.write_text(json.dumps(rows[0])+'\n')
  model={'family':'family','path':str(p/'model'),'files':{str(f):C.sha(f)},'model_manifest_sha256':'a'*64}
  r={'schema':'native-capability-registry-v1','platform':{'chips':[0,1],'output_root':str(p),'image':'sha256:x'},'model':{'small':model,'large':copy.deepcopy(model)},'protocol':{'long':{'compatible_families':['family'],'batch_size':1,'max_length':2,'dtype':'float32','hf32':False,'lengths':[2],'variants':['a','b','c'],'adapters':{'predictor':'native'}}},'resources':{'one':{'chip':0,'chips':1,'requires_idle_and_no_ready_queue':True}},'adapters':{'native':{'interface':'predictor','implemented':False}}}
  c={'schema':'native-experiment-config-v1','run_id':'run','registry_sha256':hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'model':'small','protocol':'long','resources':'one','adapters':{'predictor':'native'},'inputs':{'path':str(f),'sha256':C.sha(f),'count':1,'ordered_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()},'output':str(p/'run/output'),'scope':{'test_read':False,'scientific_acceptance':False,'launch_authority':False}}
  return c,r
 def test_existing_capability_model_change_configuration_only(self):
  with tempfile.TemporaryDirectory() as t:
   c,r=self.fixture(Path(t));a=C.validate(c,r);c['model']='large';b=C.validate(c,r);self.assertEqual(a,b);self.assertFalse(b['launch_authority']);self.assertFalse(b['runtime_available'])
 def test_unknown_and_mutated_config_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   c,r=self.fixture(Path(t))
   for key,value in [('model','missing'),('protocol','missing'),('resources','missing'),('registry_sha256','bad'),('scope',{'test_read':0,'scientific_acceptance':False,'launch_authority':False}),('output','/elsewhere'),('adapters',{'predictor':'arbitrary.py'})]:
    with self.subTest(key=key),self.assertRaises(ValueError):C.validate({**c,key:value},r)
   z=copy.deepcopy(r);z['resources']['one']['chip']=True
   c['registry_sha256']=hashlib.sha256(json.dumps(z,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   with self.assertRaises(ValueError):C.validate(c,z)
 def test_input_integrity_and_strict_json(self):
  for s in ['{"a":1,"a":2}','{"nested":[1e999]}','{"x":NaN}']:
   with self.assertRaises(ValueError):C.strict_json(s)
  with tempfile.TemporaryDirectory() as t:
   c,r=self.fixture(Path(t));Path(c['inputs']['path']).write_text('{"i":0,"input_ids":[7,9]}\n')
   with self.assertRaises(ValueError):C.validate(c,r)
 def test_registry_protocol_and_path_counterexamples(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);c,r=self.fixture(root)
   mutations=[lambda c,r:c.update(run_id='.',output=str(root/'output')),lambda c,r:c.update(run_id='..',output=str(root/'../output')),lambda c,r:r.update(schema='unknown'),lambda c,r:r.update(unknown=1),lambda c,r:r['adapters']['native'].update(implemented='false'),lambda c,r:r['adapters']['native'].update(extra=1),lambda c,r:r['protocol']['long'].update(max_length=1),lambda c,r:r['protocol']['long'].update(max_length=True),lambda c,r:r['protocol']['long'].update(lengths=[0]),lambda c,r:r['protocol']['long'].update(variants=[]),lambda c,r:r['protocol']['long'].update(variants=['a','a'])]
   for fn in mutations:
    cc,rr=copy.deepcopy(c),copy.deepcopy(r);fn(cc,rr);cc['registry_sha256']=hashlib.sha256(json.dumps(rr,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with self.assertRaises(ValueError):C.validate(cc,rr)
   (root/'run').symlink_to(root/'elsewhere',target_is_directory=True)
   with self.assertRaises(ValueError):C.validate(c,r)
if __name__=='__main__':unittest.main()
