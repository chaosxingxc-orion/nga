"""Real tiny PEFT forward through root inference, export and trained score."""
import copy, hashlib, json, sys, tempfile, unittest, importlib.util, threading
from contextlib import ExitStack
from collections import Counter
from pathlib import Path
from unittest import mock
import torch, numpy as np, jsonschema
from transformers import LlamaConfig, LlamaForCausalLM, AutoModelForCausalLM
from peft import LoraConfig, TaskType, get_peft_model, PeftModel
from safetensors.torch import load_file, save_file
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'components/inference'))
import trained_inference as m
sys.path.insert(0,str(ROOT))
import test_panel_bridge as B
N=m.base.native; P=m.base.protocol
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v): Path(p).write_text(json.dumps(v,sort_keys=True)+'\n')
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,p);o=importlib.util.module_from_spec(spec);sys.modules[name]=o;spec.loader.exec_module(o);return o
class TrainedIntegration(unittest.TestCase):
 def setUp(self):
  self.stack=ExitStack(); self.addCleanup(self.stack.close)
  self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
  root=self.root; self.base=root/'base'; self.base.mkdir(); self.pub=root/'train'; self.pub.mkdir()
  torch.manual_seed(19)
  LlamaForCausalLM(LlamaConfig(vocab_size=248320,hidden_size=16,intermediate_size=32,num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2)).save_pretrained(self.base)
  files={p.name:m.training.sha(p) for p in self.base.iterdir()}
  self.recipe={'id':'k1-base-0.8b-3116-v2','model_id':'Qwen3.5-0.8B-Base','revision':'fixture-only','files':files,'pairs':7,'trainable_parameters':1}
  targets=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj','in_proj_qkv','in_proj_z','in_proj_a','in_proj_b','out_proj']
  model=get_peft_model(AutoModelForCausalLM.from_pretrained(self.base,local_files_only=True),LoraConfig(task_type=TaskType.CAUSAL_LM,r=16,lora_alpha=32,lora_dropout=.05,target_modules=targets,bias='none'))
  trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]; self.top=m.family.topology(trainable)
  self.stack.enter_context(mock.patch.dict(m.family.RECIPES,{self.recipe['id']:self.recipe}))
  self.stack.enter_context(mock.patch.object(m.family,'TOTAL',2))
  self.stack.enter_context(mock.patch.object(m.family,'expected_topology',return_value=self.top))
  opt=torch.optim.AdamW([p for n,p in trainable],lr=1e-4,weight_decay=.01)
  sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=1e-4,total_steps=2,pct_start=.1)
  self.ids=torch.tensor([[1,7,3,9]])
  for _ in range(2):
   opt.zero_grad(); model(self.ids,labels=self.ids).loss.backward(); opt.step(); sched.step()
  ident=m.family.identity({'seed':11},self.recipe)
  cp_sha=m.family.save_v2(torch,self.pub,2,trainable,opt,sched,ident,None)
  self.cp=self.pub/'ckpt/step_000002.pt'; self.st=torch.load(self.cp,weights_only=True)
  m.family.publish_adapter(self.pub,self.st,ident,'independent-review',cp_sha)
  manifest=root/'manifest.json'; manifest.write_text(json.dumps({'model_id':self.recipe['model_id'],'files':files}))
  self.cfg={'adapter':m.VERSION,'runtime':'npu','recipe_id':self.recipe['id'],'model':{'id':self.recipe['model_id'],'path':str(self.base),'manifest':str(manifest),'manifest_sha256':m.base.sha(manifest)},'adapter_publication':{'path':str(self.pub/'adapter'),'checkpoint':str(self.cp),'checkpoint_sha256':cp_sha,'seed':11,'owner':'independent-review'},'max_length':8192,'batch_size':1,'image_sha256':'a'*64}
  self.row={'i':0,'qid':'review','state':'s','question':'Is it true?','kind':'yes_no','options':['Yes','No']}
  data=root/'requests.jsonl'; data.write_text(json.dumps(self.row)+'\n')
  self.cfg['dataset']={'path':str(data),'sha256':m.base.sha(data),'count':1}
  self.model_identity,self.model_hash=m.model_identity(self.cfg)
  self.set_contract(self.model_hash)
 def set_contract(self,h):
  c={'schema':m.base.protocol.PROTOCOL,'count':1,'items_sha256':'b'*64,'source_sha256':'c'*64,'model_sha256':h,'runtime_protocol_sha256':m.base.sha(m.base.SOURCE_ROOT/'bev_native_runtime.py'),'tau':0.5}
  p=self.root/'contract.json'; p.write_text(json.dumps(c))
  self.cfg['panel']={'contract':str(p),'contract_file_sha256':m.base.sha(p),'contract_sha256':m.base.protocol.sha256_value(c),'ordered_requests_sha256':m.base.native.digest([self.row]),'model_sha256':h}
 def reject(self,pattern):
  with mock.patch.object(m,'load_model',side_effect=AssertionError('weights loaded')) as loader, mock.patch.object(m.base.native,'read_model_batch',side_effect=AssertionError('forward')) as forward:
   with self.assertRaisesRegex(ValueError,pattern): m.run(self.cfg,self.root/'output')
   loader.assert_not_called(); forward.assert_not_called()
 def refresh_receipt(self):
  pub=self.pub/'adapter'; p=pub/'PUBLICATION.json'; v=json.loads(p.read_text())
  v['files']={n:m.base.sha(pub/n) for n in ('adapter_config.json','adapter_model.safetensors')}; p.write_text(json.dumps(v))
 def rewrite_checkpoint(self):
  torch.save(self.st,self.cp); self.cfg['adapter_publication']['checkpoint_sha256']=m.base.sha(self.cp)
 def establish_bridge(self):
  self.items=[dict(i=0,qid='choice',y=1,state='s1',question='Choose',kind='choice',options=['red','blue','green']),dict(i=1,qid='bool',y=0,state='s2',question='Is it?',kind='yes_no',options=['Yes','No']),dict(i=2,qid='score',y=2,state='s3',question='Rate',kind='score',options=['low','mid','high'])]
  self.rows=[{k:v for k,v in x.items() if k!='y'} for x in self.items]
  self.ref=N.reference(m.base.SOURCE_ROOT);self.tok=B.Tokenizer();self.reqs=[N.prepare_request(x,self.tok,self.ref) for x in self.rows]
  self.inp=self.root/'population';self.inp.mkdir();self.paths={}
  for name,data in [('items',self.items),('gold',[dict(i=x['i'],qid=x['qid'],y=x['y'],request_sha256=P.request_hash(x)) for x in self.items]),('requests',self.reqs),('dataset',self.rows)]:
   p=self.inp/(name+'.jsonl');p.write_text(''.join(json.dumps(v)+'\n' for v in data));self.paths[name]=p
  contract=P.make_contract(self.items,source_sha256='b'*64,model_sha256=self.model_hash,runtime_protocol_sha256=sha(m.base.SOURCE_ROOT/'bev_native_runtime.py'),tau=.7)
  cp=self.inp/'contract.json';put(cp,contract);self.paths['contract']=cp;self.cpin=P.sha256_value(contract)
  self.cfg['dataset']=dict(path=str(self.paths['dataset']),sha256=sha(self.paths['dataset']),count=3)
  self.cfg['panel']=dict(contract=str(cp),contract_file_sha256=sha(cp),contract_sha256=self.cpin,ordered_requests_sha256=N.digest(self.rows),model_sha256=self.model_hash)
  self.out=self.root/'inference';self.config=dict(self.cfg,schema='nga-unified-config-v1',output=str(self.out));self.configpath=self.root/'entry.json';put(self.configpath,self.config)
  pop=dict(count=3,kinds=dict(Counter(x['kind'] for x in self.items)),contract_sha256=self.cpin,protocol_binding_sha256=sha(m.base.SOURCE_ROOT/'bev_native_runtime.py'),source={'sha256':'b'*64},ordered_inputs_sha256=N.digest(self.reqs))
  for k in ('items','gold','requests','contract'):pop[k]=dict(path=str(self.paths[k]),sha256=sha(self.paths[k]))
  self.manifest=dict(schema='native-panel-input-manifest-v1',population=pop,records=str(self.root/'unused'),receipts_sha256='d'*64,model_sha256=self.model_hash,plan_sha256='e'*64,scope='independent-fixture-only',model='tiny trained Llama (fixture)',engine='actual PEFT CPU forward; fixture tokenizer')
  self.mp=self.root/'population.json';put(self.mp,self.manifest)
  self.A=load(ROOT/'adapter.py','review_adapter');orig=self.A.load
  def loader(p,name):
   obj=orig(p,name)
   if name=='nga_trained_inference':obj.load_model=lambda c:obj._load_peft(c,'cpu')
   return obj
  self.stack.enter_context(mock.patch.object(self.A,'load',side_effect=loader))
  self.stack.enter_context(mock.patch.object(m.base,'load_tokenizer',return_value=self.tok))
 def invoke(self,c,p):put(p,c);return self.A.run(self.A.config(str(p)),str(p))
 def export(self,suffix):
  out=self.root/suffix;c=dict(schema='nga-unified-config-v1',adapter='native-panel-export-v2',runtime='cpu',source=str(self.out),owner_sha256=sha(self.out/'OWNER.json'),source_config=str(self.configpath),source_config_sha256=sha(self.configpath),panel_manifest=str(self.mp),panel_manifest_sha256=sha(self.mp),output=str(out))
  self.invoke(c,self.root/(suffix+'-config.json'));return out
 def chain(self):
  self.establish_bridge();pin=sha(self.configpath)
  with mock.patch.object(sys,'argv',['adapter.py',str(self.configpath)]): self.A.main()
  expected=m._load_peft(self.cfg,'cpu');base=AutoModelForCausalLM.from_pretrained(self.base,local_files_only=True).eval();delta=[]
  for i,req in enumerate(self.reqs):
   enc=self.tok([req['rendered_prompt']]);
   with torch.no_grad():z=expected(**enc).logits[0,-1].numpy();b=base(**enc).logits[0,-1].numpy()
   saved=np.load(self.out/'items'/f'{i:08d}'/'logits.npy');self.assertEqual(saved.shape,(248320,));self.assertTrue(np.array_equal(saved.view('u4'),z.view('u4')));delta.append(float(np.max(np.abs(z-b))))
   pred=N.read_logits(req,saved,mode='transformers_full_labels',contract_sha256=self.cpin,prepared_sha256=N.digest(req),ref=self.ref)
   self.assertEqual(pred,json.loads((self.out/'items'/f'{i:08d}'/'record.json').read_text())['prediction'])
  self.assertTrue(all(x>0 for x in delta));export=self.export('export')
  em=json.loads((export/'manifest.json').read_text());self.assertEqual(em['model_sha256'],self.model_hash)
  for p in (export/'records').iterdir():self.assertEqual(json.loads((p/'record.json').read_text())['model_sha256'],self.model_hash)
  sc=dict(schema='nga-unified-config-v1',adapter='native-panel-score-v1',runtime='cpu',manifest=str(export/'manifest.json'),manifest_sha256=sha(export/'manifest.json'),output=str(self.root/'score'),workers=1,chunk_size=1)
  sc['trained_provenance']=dict(source=str(self.out),source_config=str(self.configpath),source_config_sha256=sha(self.configpath),source_manifest=str(self.mp),source_manifest_sha256=sha(self.mp),receipt=str(export/'trained-export-receipt.json'),receipt_sha256=sha(export/'trained-export-receipt.json'))
  self.invoke(sc,self.root/'score-config.json');self.assertEqual(json.loads((self.root/'score/trained-report.json').read_text())['model_sha256'],self.model_hash);summary=json.loads((self.root/'score/summary.json').read_text());self.assertEqual({k:v['n'] for k,v in summary['by_type'].items()},{'choice':1,'yes_no':1,'score':1})
  generic={k:v for k,v in sc.items() if k!='trained_provenance'};generic['output']=str(self.root/'generic-score');self.invoke(generic,self.root/'generic-score-config.json');self.assertEqual((self.root/'generic-score/summary.json').read_bytes(),(self.root/'score/summary.json').read_bytes())
  self.A.run(self.A.config(str(self.configpath)),str(self.configpath));self.assertEqual(json.loads((self.out/'completion.json').read_text())['reused'],3);self.assertEqual(sha(self.configpath),pin)
  negatives=[]
  for field in ['OWNER.json','completion.json','model-identity.json','predictions.json','items/00000000/COMMITTED.json','items/00000000/logits.npy']:
   path=self.out/field;raw=path.read_bytes();path.write_bytes(b'{}' if path.suffix=='.json' else b'corrupt')
   try:
    with self.assertRaises((ValueError,KeyError)):self.export('negative-'+str(len(negatives)))
    self.assertFalse((self.root/('negative-'+str(len(negatives)))).exists());negatives.append(field)
   finally:path.write_bytes(raw)
  # Base-only relabel with updated manifest pin is still rejected.
  original=copy.deepcopy(self.manifest);self.manifest['model_sha256']=m.training.canonical(self.recipe['files']);put(self.mp,self.manifest)
  with self.assertRaisesRegex(ValueError,'manifest model differs'):self.export('base-relabel')
  put(self.mp,original)
  # Updated manifest pin cannot substitute a base-only or foreign identity.
  receipt=export/'trained-export-receipt.json';rr=json.loads(receipt.read_text())
  for i,foreign in enumerate((m.training.canonical(self.recipe['files']),'f'*64)):
   em['model_sha256']=foreign;put(export/'manifest.json',em)
   rr['export_manifest_sha256']=sha(export/'manifest.json');put(receipt,rr);sc['trained_provenance']['receipt_sha256']=sha(receipt)
   sc['manifest_sha256']=sha(export/'manifest.json');sc['output']=str(self.root/('score-negative-'+str(i)))
   with self.assertRaises(ValueError):self.invoke(sc,self.root/('score-negative-config-'+str(i)+'.json'))
 def test_actual_chain(self): self.chain()
 def test_dtype_and_foreign_sources(self):
  self.cfg['adapter_publication']['owner']='foreign';self.reject('binding');self.cfg['adapter_publication']['owner']='independent-review'
  self.st['identity']['seed']=12;self.rewrite_checkpoint();self.reject('checkpoint identity mismatch')
 def test_wrong_base_and_contract(self):
  contract=Path(self.cfg['panel']['contract']);v=json.loads(contract.read_text());v['model_sha256']='0'*64;put(contract,v);self.cfg['panel']['contract_file_sha256']=sha(contract);self.cfg['panel']['contract_sha256']=P.sha256_value(v);self.reject('trained model identity differs')
  path=self.base/'config.json';path.write_bytes(path.read_bytes()+b' ');self.reject('manifest content mismatch')
 def test_receipt_consistent_dtype(self):
  p=self.pub/'adapter/adapter_model.safetensors';v=load_file(str(p));k=next(iter(v));v[k]=v[k].double();save_file(v,str(p),metadata={'format':'pt'});self.refresh_receipt();self.reject('dtype or shape')
 def test_guard(self):
  self.assertTrue(m._guard_module.lock.acquire(False))
  try:
   with self.assertRaisesRegex(RuntimeError,'already active'):m.run(self.cfg,self.root/'other')
  finally:m._guard_module.lock.release()
  self.assertFalse((self.root/'other').exists())
if __name__=='__main__': unittest.main(verbosity=2)
