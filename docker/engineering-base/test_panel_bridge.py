"""CPU integration: synthetic model boundary only; production admission/export/scorer."""
import hashlib, importlib.util, json, sys, tempfile, unittest
from collections import Counter
from pathlib import Path
from unittest import mock
import numpy as np
import torch

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'source/native'))
import bev_native_runtime as N
import bev_native_protocol as P
spec=importlib.util.spec_from_file_location('bridge_adapter',BASE/'adapter.py')
A=importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x): Path(p).write_text(json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n')
def jsonl(p,x): Path(p).write_text(''.join(json.dumps(v,sort_keys=True)+'\n' for v in x))

class Tokenizer:
 padding_side='left'; chat_template=None
 def encode(self,text,add_special_tokens=False):
  return [{'A':11,'B':12,'C':13,'Yes':21,'No':22,'1':31,'2':32,'3':33}.get(text,40)]
 def __call__(self,texts,**kw):
  rows=[self.encode(t) for t in texts]
  return {'input_ids':torch.tensor(rows),'attention_mask':torch.ones((len(rows),1),dtype=torch.int64)}
class FrozenModel:
 device='cpu'
 def __init__(self,vectors,fail=None): self.vectors=vectors; self.n=0; self.fail=fail
 def __call__(self,**kw):
  if self.n==self.fail: raise RuntimeError('synthetic interruption')
  z=self.vectors[self.n]; self.n+=1
  return type('Output',(),{'logits':torch.from_numpy(z.copy()).reshape(1,1,-1)})()

class Bridge(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.inp=self.root/'input'; self.inp.mkdir()
  modelroot=self.root/'models';modelroot.mkdir(); model=modelroot/'Qwen__Qwen3.5-0.8B-Base';model.mkdir(); (model/'weights').write_bytes(b'test-only synthetic model identity')
  files={'weights':sha(model/'weights')}; self.modelpin=N.digest(files); mm=self.inp/'model.json';put(mm,dict(schema='nga-model-manifest-v1',model_id='Qwen3.5-0.8B-Base',files=files))
  self.items=[dict(i=0,qid='choice',y=1,state='s1',question='Choose',kind='choice',options=['red','blue','green']),dict(i=1,qid='bool',y=0,state='s2',question='Is it?',kind='yes_no',options=['Yes','No']),dict(i=2,qid='score',y=2,state='s3',question='Rate',kind='score',options=['low','mid','high'])]
  self.rows=[{k:v for k,v in x.items() if k!='y'} for x in self.items]
  ref=N.reference(BASE/'source/native');self.reqs=[N.prepare_request(x,Tokenizer(),ref) for x in self.rows]
  runtimepin=sha(BASE/'source/native/bev_native_runtime.py');self.contract=P.make_contract(self.items,source_sha256='b'*64,model_sha256=self.modelpin,runtime_protocol_sha256=runtimepin,tau=0.7);self.cpin=P.sha256_value(self.contract)
  self.paths={}
  for name,data in [('items',self.items),('gold',[dict(i=x['i'],qid=x['qid'],y=x['y'],request_sha256=P.request_hash(x)) for x in self.items]),('requests',self.reqs),('dataset',self.rows)]:
   p=self.inp/(name+'.jsonl');jsonl(p,data);self.paths[name]=p
  cp=self.inp/'contract.json';put(cp,self.contract);self.paths['contract']=cp
  self.vectors=[]
  for req,values in zip(self.reqs,([0.25,2.0,-1.0],[1.25,-0.5],[-2.0,0.3,1.5])):
   z=np.full(248320,-3.25,dtype=np.float32);z[req['label_ids']]=values;z[200000]=7.0;self.vectors.append(z)
  self.out=self.root/'inference'; self.cfg=dict(schema='nga-unified-config-v1',adapter='native-full-label-v2',runtime='npu',model=dict(id='Qwen3.5-0.8B-Base',path=str(model),manifest=str(mm),manifest_sha256=sha(mm)),dataset=dict(path=str(self.paths['dataset']),sha256=sha(self.paths['dataset']),count=3),max_length=8192,batch_size=1,output=str(self.out),image_sha256='c'*64,panel=dict(contract=str(cp),contract_file_sha256=sha(cp),contract_sha256=self.cpin,ordered_requests_sha256=N.digest(self.rows),model_sha256=self.modelpin))
  self.cfgpath=self.root/'infer.json';put(self.cfgpath,self.cfg)
  pop=dict(count=3,kinds=dict(Counter(x['kind'] for x in self.items)),contract_sha256=self.cpin,protocol_binding_sha256=runtimepin,source={'sha256':'b'*64},ordered_inputs_sha256=N.digest(self.reqs))
  for key in ('items','gold','requests','contract'):pop[key]=dict(path=str(self.paths[key]),sha256=sha(self.paths[key]))
  self.manifest=dict(schema='native-panel-input-manifest-v1',population=pop,records=str(self.root/'unused'),receipts_sha256='d'*64,model_sha256=self.modelpin,plan_sha256='e'*64,scope='synthetic',model='fixture',engine='frozen-vectors')
  self.mp=self.root/'population.json';put(self.mp,self.manifest)
  self.modelroot=modelroot; self.original_load=A.load
 def tearDown(self): self.tmp.cleanup()
 def invoke(self,c,path):
  put(path,c); return A.run(A.config(str(path)),str(path))
 def infer(self,vectors=None,fail=None):
  vectors=self.vectors if vectors is None else vectors
  def loader(path,name):
   m=self.original_load(path,name)
   if name=='nga_native_inference':
    m.MODEL_ROOTS=(self.modelroot,);m.load_tokenizer=lambda c:Tokenizer()
    def load_model(c):
     if not vectors: raise AssertionError('completed reuse loaded model')
     return FrozenModel(vectors,fail)
    m.load_model=load_model
   return m
  with mock.patch.object(A,'load',side_effect=loader): return self.invoke(self.cfg,self.cfgpath)
 def export(self,out=None,change=None):
  c=dict(schema='nga-unified-config-v1',adapter='native-panel-export-v2',runtime='cpu',source=str(self.out),owner_sha256=sha(self.out/'OWNER.json'),source_config=str(self.cfgpath),source_config_sha256=sha(self.cfgpath),panel_manifest=str(self.mp),panel_manifest_sha256=sha(self.mp),output=str(out or self.root/'export'))
  if change: c.update(change)
  def loader(path,name):
   m=self.original_load(path,name)
   if name=='nga_panel_export': m.I.MODEL_ROOTS=(self.modelroot,)
   return m
  with mock.patch.object(A,'load',side_effect=loader): return self.invoke(c,self.root/'export-config.json')
 def score(self,manifest,out):
  c=dict(schema='nga-unified-config-v1',adapter='native-panel-score-v1',runtime='cpu',manifest=str(manifest),manifest_sha256=sha(manifest),output=str(out),workers=1,chunk_size=1)
  self.invoke(c,self.root/(out.name+'-config.json'));return json.loads((out/'summary.json').read_text())
 def baseline(self):
  records=self.root/'baseline-records';records.mkdir(); receipts=[];ref=N.reference(BASE/'source/native')
  for i,(req,z) in enumerate(zip(self.reqs,self.vectors)):
   p=N.read_logits(req,z,mode='transformers_full_labels',contract_sha256=self.cpin,prepared_sha256=N.digest(req),ref=ref);d=records/f'{i:06d}';d.mkdir();put(d/'record.json',dict(schema='bev-native-compact-v1',model_sha256=self.modelpin,contract_sha256=self.cpin,prediction=p,forwards=1));put(d/'COMMITTED.json',{'record.json':sha(d/'record.json')});receipts.append(sha(d/'COMMITTED.json'))
  m={**self.manifest,'records':str(records),'receipts_sha256':N.digest(receipts)};p=self.root/'baseline.json';put(p,m);return p
 def test_three_type_parity_and_completed_reuse(self):
  self.infer(); self.assertEqual(json.loads((self.out/'completion.json').read_text())['completed'],3)
  saved=[sha(self.out/'items'/f'{i:08d}'/'logits.npy') for i in range(3)]
  for i in range(3): self.assertTrue(np.array_equal(np.load(self.out/'items'/f'{i:08d}'/'logits.npy').view('u4'),self.vectors[i].view('u4')))
  self.infer(vectors=[]);self.assertEqual(json.loads((self.out/'completion.json').read_text())['reused'],3);self.assertEqual(saved,[sha(self.out/'items'/f'{i:08d}'/'logits.npy') for i in range(3)])
  self.export(); baseline=self.score(self.baseline(),self.root/'baseline-score'); actual=self.score(self.root/'export/manifest.json',self.root/'export-score'); self.assertEqual(actual,baseline)
  self.assertEqual((self.root/'baseline-score/summary.json').read_bytes(),(self.root/'export-score/summary.json').read_bytes())
  self.assertEqual([(k,actual['by_type'][k]['n'],actual['by_type'][k]['correct']) for k in ('choice','yes_no','score')],[('choice',1,1),('yes_no',1,1),('score',1,1)])
 def test_interruption_resume(self):
  with self.assertRaisesRegex(RuntimeError,'synthetic interruption'): self.infer(fail=1)
  self.assertTrue((self.out/'items/00000000/COMMITTED.json').exists());self.assertEqual(json.loads((self.out/'EXIT.json').read_text())['exit_code'],1)
  partial=self.out/'items/.partial-interrupted';partial.mkdir();(partial/'evidence').write_text('retained')
  self.infer(vectors=self.vectors[1:]); self.assertEqual(json.loads((self.out/'completion.json').read_text())['reused'],1);self.export();self.assertEqual(self.score(self.baseline(),self.root/'baseline-score'),self.score(self.root/'export/manifest.json',self.root/'export-score'))
  self.assertTrue(any((p/'evidence').exists() for p in (self.out/'quarantine').iterdir()))
 def test_bad_request_populations(self):
  self.infer()
  for mode in ('missing','extra','permuted'):
   with self.subTest(mode=mode):
    rows=list(self.reqs)
    if mode=='missing': rows.pop()
    if mode=='extra': rows.append(rows[-1])
    if mode=='permuted': rows[0],rows[1]=rows[1],rows[0]
    jsonl(self.paths['requests'],rows);self.manifest['population']['requests']['sha256']=sha(self.paths['requests']);self.manifest['population']['ordered_inputs_sha256']=N.digest(rows);put(self.mp,self.manifest)
    out=self.root/('bad-'+mode)
    with self.assertRaises(ValueError):self.export(out)
    self.assertFalse(out.exists())
 def test_foreign_owner_contract_model_and_v1_refusal(self):
  self.infer()
  owner=self.out/'OWNER.json';original=owner.read_text();put(owner,{'foreign':True})
  with self.assertRaisesRegex(ValueError,'foreign owner'):self.export(self.root/'foreign')
  self.assertFalse((self.root/'foreign').exists());owner.write_text(original)
  for key in ('contract_sha256','model_sha256'):
   old=self.manifest['population']['contract_sha256'] if key=='contract_sha256' else self.manifest[key]
   if key=='contract_sha256': self.manifest['population'][key]='0'*64
   else:self.manifest[key]='0'*64
   put(self.mp,self.manifest);out=self.root/('wrong-'+key)
   with self.assertRaises(ValueError):self.export(out)
   self.assertFalse(out.exists())
   if key=='contract_sha256':self.manifest['population'][key]=old
   else:self.manifest[key]=old
  put(self.mp,self.manifest)
  v1=dict(schema='nga-unified-config-v1',adapter='native-panel-export-v1',runtime='cpu',source=str(self.out),owner_sha256='0'*64,inference_identity_sha256='0'*64,source_config=str(self.cfgpath),source_config_sha256='0'*64,model_inventory_sha256='0'*64,panel_manifest=str(self.mp),panel_manifest_sha256='0'*64,output=str(self.root/'v1'))
  with self.assertRaisesRegex(ValueError,'v1 inference'):self.invoke(v1,self.root/'v1.json')
  self.assertFalse((self.root/'v1').exists())
 def test_source_requests_must_match_frozen_order(self):
  for mode in ('missing','extra','permuted'):
   with self.subTest(mode=mode):
    rows=list(self.rows)
    if mode=='missing': rows.pop()
    if mode=='extra': rows.append(dict(rows[-1],i=3,qid='extra'))
    if mode=='permuted':
     rows[0],rows[1]=dict(rows[1],i=0),dict(rows[0],i=1)
    jsonl(self.paths['dataset'],rows);self.cfg['dataset'].update(sha256=sha(self.paths['dataset']),count=len(rows))
    with self.assertRaisesRegex(ValueError,'contract count differs|ordered requests differ'):self.infer()
    self.assertFalse(self.out.exists())

if __name__=='__main__': unittest.main(verbosity=2)
