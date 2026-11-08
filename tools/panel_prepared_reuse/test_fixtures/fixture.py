import copy, importlib.util, json, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
CODE = ROOT / 'pack' / 'code'
spec = importlib.util.spec_from_file_location('panel_under_test', CODE / 'bev_native_dataset_panel_v1.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
sys.path.insert(0, str(CODE))
import resource_v3 as Q

class Prepared(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'run'; self.root.mkdir(); self.n=0
  def file(name, value='x'):
   p=self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(value); return str(p)
  self.file=file
  def ref(p): return {'path':p,'sha256':C.sha(p)}
  self.ref=ref
  runtime=str(CODE/'bev_native_dataset_panel_v1.py'); consumer=file('code/consumer.py'); runtime_sibling=Path(consumer).with_name('bev_native_dataset_panel_v1.py')
  # Runtime identity must be the actual module under test; consumer sibling check is real.
  consumer=str(CODE/'fixture-consumer-unused.py')
  # Use existing sibling file without writing into the source tree.
  consumer=str(CODE/'resource_v3.py')
  modules={k:ref(runtime if k=='runtime' else consumer) for k in C.MODULES}
  loader=file('code/loader.py',"ENV = {}\nIMAGE = 'sha256:' + '4'*64\n"); modules['loader']=ref(loader)
  model=self.root/'model'; model.mkdir(); weight=file('model/weights.safetensors')
  mf={weight:C.sha(weight)}; st=Path(weight).stat(); self.asset={'model_byte_pins_inherited_from_accepted_launch':mf,'model_stat_continuity':{weight:{'size':st.st_size,'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns,'inode':st.st_ino}}}
  self.asset_path='/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_rc1_family_numeric_20261107/2b/package/assets/ASSET-RECEIPT.json'
  self.asset_pin='a'*64
  original_sha=C.sha; original_read=C.read
  sha_patch=patch.object(C,'sha',side_effect=lambda p:self.asset_pin if str(p)==self.asset_path else original_sha(p)); sha_patch.start(); self.addCleanup(sha_patch.stop)
  read_patch=patch.object(C,'read',side_effect=lambda p:self.asset if str(p)==self.asset_path else original_read(p)); read_patch.start(); self.addCleanup(read_patch.stop)
  files={runtime:C.sha(runtime),consumer:C.sha(consumer),loader:C.sha(loader),self.asset_path:self.asset_pin}
  pop={}
  for k in ('requests','items','gold','source','contract'):
   p=file('population/'+k); files[p]=C.sha(p); pop[k]=ref(p)
  pop.update(count=1,source_rows=1,semantic_duplicates=0,kinds={'choice':1,'yes_no':0,'score':0},ordered_inputs_sha256='1'*64,contract_sha256='2'*64,protocol_binding_sha256='3'*64)
  upstream={}
  for name in ('question.py','readout.py','tacit.py'):
   p=file('upstream/anyjev/'+name); files[p]=C.sha(p); upstream[name]=ref(p)
  self.config=dict(schema='native-dataset-panel-config-v1',run_id='run',output=str(self.root/'output'),container='run',host_name='host',host_environment={},host_python=str(self.root/'python'),cpu_python=str(self.root/'python'),cpu_environment={},model={'path':str(model),'files':mf,'manifest_sha256':C.digest(mf),'family':'qwen3.5_decoder','name':'fixture','kind':'fixed_instruct'},population=pop,protocol=dict(id='native-full-label-panel-v2',family='qwen3.5_decoder',max_length=8192,batch_size=1,dtype='float32',hf32=False,vocabulary=248320,adapter='transformers_full_labels'),modules=modules,upstream={'root':str(self.root/'upstream'),'files':upstream},resources={'chip':None,'allocation':file('allocation.json','{}'),'policy':None},numeric={'model':'2b','admission_sha256':'73589e71c7d463b2833e6559db4b4dc4d4a71a7fd1e40aaea3f9b770971807ce'},image='sha256:'+'4'*64,environment={},files=files,scope='public_fixed_instruct_test',test_read=True,scientific_acceptance=False,candidate_test_authority=False,candidate_selection_allowed=False,poll_seconds=600,cpu_only_paths=[pop[k]['path'] for k in ('items','gold','source','contract')]+[consumer])
  self.cpu=self.root/'CPU-CONFIG.json'; self.write(self.cpu,self.config)
  self.prepare=self.root/'CPU-PREPARE.json'; self.plan=self.root/'PLAN.json'; self.final=self.root/'CONFIG.json'
  self.validator=patch.object(C,'validate_population',side_effect=lambda c:setattr(self,'n',self.n+1)); self.validator.start(); self.addCleanup(self.validator.stop)
  C.build(str(self.cpu),C.sha(self.cpu),str(self.prepare),cpu_prepare=True); self.pin=C.sha(self.prepare)
  self.bound=copy.deepcopy(self.config)
  claim=file('claim.json','{}'); release=file('release.json','{}')
  policy=file('policy.json',json.dumps({'predecessor':{'claim':ref(claim),'release':ref(release)}}))
  for p in (claim,release,policy): self.bound['files'][p]=C.sha(p)
  self.bound['resources'].update(chip=4,policy=ref(policy))
 def write(self,p,obj): Path(p).write_text(json.dumps(obj,sort_keys=True))
 def build(self,pin=None):
  self.write(self.final,self.bound)
  return C.build(str(self.final),C.sha(self.final),str(self.plan),prepared_plan=str(self.prepare),prepared_pin=self.pin if pin is None else pin)
 def test_reuse_and_projection(self):
  got=self.build(); self.assertEqual(self.n,1)
  C.verify(str(self.plan),C.sha(self.plan),cpu=True)
  self.plan.unlink(); full=C.build(str(self.final),C.sha(self.final),str(self.plan)); self.assertEqual(self.n,2); self.assertEqual(got,full)
 def test_rejections(self):
  with self.assertRaises(ValueError): self.build('0'*64)
  for key,value in [('protocol',dict(self.bound['protocol'],max_length=42)),('population',dict(self.bound['population'],count=2)),('host_name','changed')]:
   old=self.bound[key]; self.bound[key]=value
   with self.assertRaises(ValueError): self.build()
   self.bound[key]=old
  extra=self.file('extra','x'); self.bound['files'][extra]=C.sha(extra)
  with self.assertRaises(ValueError): self.build()
  del self.bound['files'][extra]
  source=self.bound['population']['source']['path']; Path(source).write_text('tamper')
  with self.assertRaises(ValueError): self.build()
 def test_missing_refs_and_prepare_mode(self):
  for kwargs in ({'prepared_plan':str(self.prepare)}, {'prepared_pin':self.pin}, {'cpu_prepare':True,'prepared_plan':str(self.prepare),'prepared_pin':self.pin}):
   with self.assertRaises(ValueError): C.build(str(self.cpu),C.sha(self.cpu),str(self.plan),**kwargs)
 def test_runtime_source_identity(self):
  d=C.read(self.prepare); d['modules']['runtime']['sha256']='0'*64; self.write(self.prepare,d)
  with self.assertRaisesRegex(ValueError,'runtime differs'): self.build(C.sha(self.prepare))
 def test_stale_generation_actual_guard(self):
  d=self.build(); policy=C.read(d['queue']['path']); policy.update(schema='instruct08-documents-resource-v1',chip=4,run=d['run'],allocation=d['allocation'],free_entry={'chip':4,'generation':1},pending_claims=[]); self.write(d['queue']['path'],policy)
  d['queue']['sha256']=C.sha(d['queue']['path']); d['files'][d['queue']['path']]=d['queue']['sha256']
  R=types.SimpleNamespace(validate_doc=lambda x:None)
  with self.assertRaisesRegex(ValueError,'free generation changed'): Q.guard(d,R,{'free':[{'chip':4,'generation':2}],'allocation':[],'pending_claims':[]})

if __name__=='__main__': unittest.main(verbosity=2)
