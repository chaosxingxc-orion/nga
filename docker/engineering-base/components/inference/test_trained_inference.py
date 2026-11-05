"""CPU physical-boundary test: real training, family publication, verification and PEFT load."""
import copy, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
import torch
from transformers import LlamaConfig, LlamaForCausalLM, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, PeftModel, TaskType
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import trained_inference as m

class Physical(unittest.TestCase):
 def test_real_publication_and_peft_load(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); modeldir=root/'base'; modeldir.mkdir(); out=root/'run'; out.mkdir(); (out/'ckpt').mkdir()
   torch.manual_seed(7)
   LlamaForCausalLM(LlamaConfig(vocab_size=48,hidden_size=16,intermediate_size=32,num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2)).save_pretrained(modeldir)
   files={p.name:m.training.sha(p) for p in modeldir.iterdir()}; recipe={'id':'fixture','model_id':'tiny','revision':'abc','files':files,'pairs':1,'trainable_parameters':1}
   cfg=LoraConfig(task_type=TaskType.CAUSAL_LM,r=16,lora_alpha=32,lora_dropout=.05,target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj','in_proj_qkv','in_proj_z','in_proj_a','in_proj_b','out_proj'],bias='none')
   model=get_peft_model(AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True),cfg)
   trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]; top=m.family.topology(trainable)
   opt=torch.optim.AdamW([p for _,p in trainable],lr=1e-4,weight_decay=.01); sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=1e-4,total_steps=2,pct_start=.1)
   ids=torch.tensor([[1,2,3,4]])
   for _ in range(2):
    opt.zero_grad(); model(input_ids=ids,labels=ids).loss.backward(); opt.step(); sched.step()
   ident=m.family.identity({'seed':2},recipe)
   with mock.patch.object(m.family,'TOTAL',2), mock.patch.dict(m.family.RECIPES,{'fixture':recipe}), mock.patch.object(m.family,'expected_topology',return_value=top):
    cp_sha=m.family.save_v2(torch,out,2,trainable,opt,sched,ident,None); cp=out/'ckpt/step_000002.pt'; st=torch.load(cp,weights_only=True)
    m.family.publish_adapter(out,st,ident,'owner',cp_sha)
    m.family.publish_adapter(out,st,ident,'owner',cp_sha)
    manifest=root/'manifest.json'; manifest.write_text(json.dumps({'model_id':'tiny','files':files}))
    config={'recipe_id':'fixture','model':{'id':'tiny','path':str(modeldir),'manifest':str(manifest),'manifest_sha256':m.training.sha(manifest)},'adapter_publication':{'path':str(out/'adapter'),'checkpoint':str(cp),'checkpoint_sha256':cp_sha,'seed':2,'owner':'owner'}}
    identity,digest=m.model_identity(config); self.assertEqual(digest,m.base.native.digest(identity))
    wrong=copy.deepcopy(config); wrong['model']['id']='wrong'
    with self.assertRaises(ValueError): m.model_identity(wrong)
    wrong=copy.deepcopy(config); wrong['adapter_publication']['checkpoint_sha256']='0'*64
    with self.assertRaises(ValueError): m.model_identity(wrong)
    wrong=copy.deepcopy(config); wrong['adapter_publication']['seed']=3
    with self.assertRaises(ValueError): m.model_identity(wrong)

    actual=m._load_peft(config,'cpu'); standard=PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(modeldir,dtype=torch.float32,local_files_only=True,trust_remote_code=False),out/'adapter',is_trainable=False,local_files_only=True).eval()
    baseline=AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True).eval()
    with torch.no_grad(): a=actual(ids).logits; b=baseline(ids).logits; c=standard(ids).logits
    self.assertFalse(torch.equal(a,b)); torch.testing.assert_close(a,c,rtol=0,atol=0)
    with self.assertRaises(ValueError): m.family.publish_adapter(out,st,dict(ident,model_id='wrong'),'owner',cp_sha)
    with self.assertRaises(ValueError): m.family.publish_adapter(out,st,ident,'owner','0'*64)
    bad=copy.deepcopy(st); key=next(iter(bad['lora'])); bad['lora'][key]=bad['lora'][key][:-1]
    with self.assertRaises(ValueError): m.family.publish_adapter(out,bad,ident,'owner',cp_sha)
    from safetensors.torch import load_file, save_file
    tensor=out/'adapter/adapter_model.safetensors'
    published=load_file(str(tensor)); key=next(iter(published)); published[key]=published[key].double()
    save_file(published,str(tensor),metadata={'format':'pt'})
    receipt=out/'adapter/PUBLICATION.json'; r=json.loads(receipt.read_text()); r['files']['adapter_model.safetensors']=m.base.sha(tensor); receipt.write_text(json.dumps(r))
    with self.assertRaisesRegex(ValueError,'dtype or shape'): m.model_identity(config)
    published[key]=published[key].float(); save_file(published,str(tensor),metadata={'format':'pt'})
    r['files']['adapter_model.safetensors']=m.base.sha(tensor); receipt.write_text(json.dumps(r))
    tensor=out/'adapter/adapter_model.safetensors'; data=tensor.read_bytes(); tensor.write_bytes(data[:-1]+bytes([data[-1]^1]))
    with self.assertRaises(ValueError): m.family.publish_adapter(out,st,ident,'owner',cp_sha)
    with self.assertRaises(ValueError): m.model_identity(config)
 def test_trained_run_resume_and_corruption(self):
  import numpy as np
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); out=root/'output'; ref=m.base.native.reference(m.base.SOURCE_ROOT)
   cfg={'model':{'path':str(root/'model'),'manifest':str(root/'manifest')},'adapter_publication':{'path':str(root/'adapter'),'checkpoint':str(root/'checkpoint')},'dataset':{'path':str(root/'data')},'panel':{'contract':str(root/'contract'),'contract_sha256':'c'*64,'ordered_requests_sha256':'d'*64}}
   row={'i':0}; prepared={'i':0,'qid':'q','request_sha256':'e'*64,'label_ids':[1,2],'options':['Yes','No'],'input_ids':[1]}; z=np.zeros(248320,dtype=np.float32); z[1]=1
   def batch(model,inputs,tok,**kw):
    model() # exercise per-model forward capture
    return [m.base.native.read_logits(inputs[0],z,mode='transformers_full_labels',contract_sha256=kw['contract_sha256'],prepared_sha256=m.base.native.digest(inputs[0]),ref=ref)]
   class Fake:
    device='cpu'
    def __call__(self,**kwargs): return type('Output',(),{'logits':torch.from_numpy(z).reshape(1,1,-1)})()
   admitted=([row],ref,{'schema':'fixture'},'a'*64,'b'*64)
   with mock.patch.object(m,'admit',return_value=admitted), mock.patch.object(m.base,'load_tokenizer',return_value=object()), mock.patch.object(m,'load_model',return_value=Fake()), mock.patch.object(m.base.native,'prepare_request',return_value=prepared), mock.patch.object(m.base.protocol,'request_hash',return_value='e'*64), mock.patch.object(m.base.native,'read_model_batch',side_effect=batch):
    self.assertEqual(m.run(cfg,out)['completed'],1)
    with mock.patch.object(m,'load_model',side_effect=AssertionError('unexpected load')):
     self.assertEqual(m.run(cfg,out)['reused'],1)
     (out/'items/00000000/logits.npy').write_bytes(b'corrupt')
     with self.assertRaises(ValueError): m.run(cfg,out)
    self.assertEqual(json.loads((out/'EXIT.json').read_text())['exit_code'],1)
 def test_registry_and_schema(self):
  import jsonschema
  schema=json.loads((HERE/'trained-schema.json').read_text())
  self.assertEqual({x['pairs'] for x in m.family.RECIPES.values()},{186,248})
  for r in m.family.RECIPES.values(): self.assertEqual(len(m.family.expected_topology(r)),2*r['pairs'])
  with self.assertRaises(jsonschema.ValidationError): jsonschema.validate({'adapter':'trained-full-label-v1','loader':'evil'},schema)

if __name__=='__main__': unittest.main()
