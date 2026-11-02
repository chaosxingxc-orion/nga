import unittest,types
import numpy as np
from tools import bev_native_runtime as R
class Tok:
 chat_template=None
 def encode(self,x,add_special_tokens=False):
  if x in ['Yes','No']:return [20 if x=='Yes' else 21]
  if len(x)==1:return [ord(x)]
  return [ord(c) for c in x]
class NativeRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ref=R.reference()
 def item(self,kind='choice',opts=None):return dict(i=0,qid='q',state='s',question='Q?',options=opts or ['first','second'],kind=kind)
 def test_prompt_exact_and_no_gold(self):
  p=R.prepare_request(self.item(),Tok(),self.ref)
  self.assertEqual(p['labels'],['A','B']);self.assertIn('A. first\nB. second',p['rendered_prompt']);self.assertTrue(p['rendered_prompt'].endswith('Answer:'))
  with self.assertRaises(ValueError):R.prepare_request(dict(self.item(),y=0),Tok(),self.ref)
 def test_native_kinds(self):
  p=R.prepare_request(self.item('yes_no',['ignored1','ignored2']),Tok(),self.ref);self.assertEqual(p['options'],['Yes','No']);self.assertEqual(p['label_ids'],[20,21])
  p=R.prepare_request(self.item('score'),Tok(),self.ref);self.assertEqual(p['labels'],['1','2']);self.assertIn('1. first',p['rendered_prompt'])
 def test_read_matches_reference_and_contract(self):
  p=R.prepare_request(self.item(),Tok(),self.ref);z=np.arange(100,dtype=np.float32)/9
  v=R.read_logits(p,z,mode='transformers_full_labels',contract_sha256='a'*64,prepared_sha256=R.digest(p),ref=self.ref)
  lp=self.ref.restricted_logprobs(z[p['label_ids']]);self.assertEqual(v['restricted_logprobs'],lp.tolist());self.assertEqual(v['index'],1);self.assertNotIn('y',v)
 def test_top20_censorship_uniform_if_all_missing(self):
  p=R.prepare_request(self.item(),Tok(),self.ref);z=np.arange(100,dtype=np.float32)
  v=R.read_logits(p,z,mode='vllm_top20_labels',contract_sha256='a'*64,prepared_sha256=R.digest(p),ref=self.ref)
  self.assertEqual(v['top20_label_presence'],[False,False]);self.assertEqual(v['restricted_logprobs'],[-np.log(2)]*2);self.assertEqual(v['index'],int(np.argsort(-np.array(v['restricted_logprobs']))[0]))
 def test_one_present_infinite_gap_preserved(self):
  p=R.prepare_request(self.item(),Tok(),self.ref);z=np.arange(100,dtype=np.float32);z[65]=101
  v=R.read_logits(p,z,mode='vllm_top20_labels',contract_sha256='a'*64,prepared_sha256=R.digest(p),ref=self.ref);self.assertEqual(v['first_margin'],'inf');self.assertEqual(v['label_values'][1],'-inf')
 def test_invalid_shapes_modes_boundary(self):
  p=R.prepare_request(self.item(),Tok(),self.ref)
  for z,mode in [(np.zeros((2,100)),'transformers_full_labels'),(np.zeros(100),'vllm_top20_labels'),(np.arange(100),'wrong')]:
   with self.assertRaises(ValueError):R.read_logits(p,z,mode=mode,contract_sha256='a'*64,prepared_sha256=R.digest(p),ref=self.ref)
 def test_template_and_digit_fallback(self):
  class T(Tok):
   chat_template='yes'
   def apply_chat_template(self,msgs,**kw):return str(kw['enable_thinking'])+msgs[1]['content']+'ASSISTANT'
   def encode(self,x,add_special_tokens=False):return [1,2] if x.strip().isdigit() else super().encode(x,add_special_tokens)
  p=R.prepare_request(self.item('score'),T(),self.ref);self.assertEqual(p['labels'],['A','B']);self.assertTrue(p['rendered_prompt'].startswith('False'));self.assertTrue(p['rendered_prompt'].endswith('ASSISTANT'))
 def test_mutated_preparation_rejects(self):
  p=R.prepare_request(self.item(),Tok(),self.ref);pin=R.digest(p);p['label_ids'].reverse()
  with self.assertRaises(ValueError):R.read_logits(p,np.arange(100),mode='transformers_full_labels',contract_sha256='a'*64,prepared_sha256=pin,ref=self.ref)
 def test_finite_float64_overflow_rejected_after_cast(self):
  p=R.prepare_request(self.item(),Tok(),self.ref)
  for mode in ('transformers_full_labels','vllm_top20_labels'):
   for index,value in [(65,1e300),(66,-1e300),(2,1e300)]:
    with self.subTest(mode=mode,index=index,value=value):
     z=np.arange(128,dtype=np.float64);z[index]=value
     with self.assertRaisesRegex(ValueError,'float32 vocabulary is nonfinite'):
      R.read_logits(p,z,mode=mode,contract_sha256='a'*64,prepared_sha256=R.digest(p),ref=self.ref)
 def test_batch_input_tampering_rejected_before_forward(self):
  import torch
  class T(Tok):
   padding_side='left'
   def __init__(self,mutate):self.mutate=mutate
   def __call__(self,texts,**kwargs):
    rows=[self.encode(t) for t in texts];w=max(map(len,rows))
    enc=dict(input_ids=torch.tensor([[0]*(w-len(r))+r for r in rows]),attention_mask=torch.tensor([[0]*(w-len(r))+[1]*len(r) for r in rows]))
    self.mutate(enc)
    return enc
  class Model:
   device='cpu'
   calls=0
   def __call__(self,**kwargs):
    self.calls+=1
    return types.SimpleNamespace(logits=torch.arange(128,dtype=torch.float32).repeat(len(kwargs['input_ids']),1,1))
  def change(enc):enc['input_ids'][0,-1]=42
  def reorder(enc):
   for k in enc:enc[k]=enc[k].flip(0)
  def truncate(enc):
   for k in enc:enc[k]=enc[k][:,:-1]
  def rightpad(enc):
   for k in enc:enc[k][0]=enc[k][0].roll(-1)
  def hole(enc):enc['attention_mask'][0,-2]=0;enc['attention_mask'][0,0]=1
  def nonbinary(enc):enc['attention_mask'][0,-1]=2
  def dropped(enc):
   for k in enc:enc[k]=enc[k][:1]
  def rank(enc):enc['input_ids']=enc['input_ids'].unsqueeze(0)
  def mismatch(enc):enc['attention_mask']=enc['attention_mask'][:,:-1]
  def missing(enc):del enc['attention_mask']
  def boolids(enc):enc['input_ids']=enc['input_ids'].bool()
  def floats(enc):enc['attention_mask']=enc['attention_mask'].float()
  def excess_width(enc):
   for k in enc:enc[k]=torch.cat([torch.zeros((2,1),dtype=enc[k].dtype),enc[k]],dim=1)
  for mutate in (change,reorder,truncate,rightpad,hole,nonbinary,dropped,rank,mismatch,missing,boolids,floats,excess_width):
   with self.subTest(mutation=mutate.__name__):
    tok=T(mutate);rows=[R.prepare_request(self.item(),tok,self.ref),R.prepare_request(dict(self.item(),i=1,state='longer state'),tok,self.ref)];m=Model()
    with self.assertRaises(ValueError):
     R.read_model_batch(m,rows,tok,mode='transformers_full_labels',contract_sha256='a'*64,prepared_pins=list(map(R.digest,rows)),max_length=1000,ref=self.ref)
    self.assertEqual(m.calls,0)
 def test_cpu_model_adapter_final_position_and_leftpad(self):
  import torch
  class Enc(dict):
   def to(self,device):return self
  class T(Tok):
   padding_side='left'
   def __call__(self,texts,**kwargs):
    rows=[self.encode(t) for t in texts];w=max(map(len,rows));return Enc(input_ids=torch.tensor([[0]*(w-len(r))+r for r in rows]),attention_mask=torch.tensor([[0]*(w-len(r))+[1]*len(r) for r in rows]))
  class Model:
   device='cpu'
   def __call__(self,**kwargs):
    self.kwargs=kwargs;return types.SimpleNamespace(logits=torch.arange(128,dtype=torch.float32).repeat(len(kwargs['input_ids']),1,1))
  tok=T();rows=[R.prepare_request(self.item(),tok,self.ref),R.prepare_request(dict(self.item(),i=1,state='longer state'),tok,self.ref)];m=Model()
  result=R.read_model_batch(m,rows,tok,mode='transformers_full_labels',contract_sha256='a'*64,prepared_pins=list(map(R.digest,rows)),max_length=1000,ref=self.ref)
  self.assertEqual([x['index'] for x in result],[1,1]);self.assertEqual(m.kwargs['logits_to_keep'],1);self.assertEqual(int(m.kwargs['attention_mask'][0,-1]),1)
  with self.assertRaises(ValueError):R.read_model_batch(m,rows,tok,mode='transformers_full_labels',contract_sha256='a'*64,prepared_pins=list(map(R.digest,rows)),max_length=2,ref=self.ref)
 def test_unregistered_batch_fields_rejected_before_forward(self):
  import torch
  class T(Tok):
   padding_side='left'
   def __init__(self,field):self.field=field
   def __call__(self,texts,**kwargs):
    rows=[self.encode(t) for t in texts];w=max(map(len,rows))
    enc=dict(input_ids=torch.tensor([[0]*(w-len(r))+r for r in rows]),attention_mask=torch.tensor([[0]*(w-len(r))+[1]*len(r) for r in rows]))
    enc[self.field]=torch.zeros_like(enc['input_ids'])
    return enc
  class Model:
   device='cpu'
   calls=0
   def __call__(self,**kwargs):
    self.calls+=1
    raise AssertionError('unregistered inputs reached forward')
  for field in ('position_ids','token_type_ids','cache_position','inputs_embeds','past_key_values'):
   with self.subTest(field=field):
    tok=T(field);rows=[R.prepare_request(self.item(),tok,self.ref)];m=Model()
    with self.assertRaisesRegex(ValueError,'unregistered tensors'):
     R.read_model_batch(m,rows,tok,mode='transformers_full_labels',contract_sha256='a'*64,prepared_pins=list(map(R.digest,rows)),max_length=1000,ref=self.ref)
    self.assertEqual(m.calls,0)
 def test_batch_wrapper_cannot_inject_inputs_after_validation(self):
  import torch
  class Enc(dict):
   def items(self):
    raise AssertionError('untrusted mapping items must not be re-read')
   def to(self,device):
    raise AssertionError('untrusted batch wrapper must not move itself')
  class T(Tok):
   padding_side='left'
   def __call__(self,texts,**kwargs):
    ids=[self.encode(t) for t in texts]
    return Enc(input_ids=torch.tensor(ids),attention_mask=torch.ones((len(ids),len(ids[0])),dtype=torch.long))
  class Model:
   device='cpu'
   def __call__(self,**kwargs):
    self.kwargs=kwargs
    return types.SimpleNamespace(logits=torch.arange(128,dtype=torch.float32).repeat(len(kwargs['input_ids']),1,1))
  tok=T();rows=[R.prepare_request(self.item(),tok,self.ref)];m=Model()
  result=R.read_model_batch(m,rows,tok,mode='transformers_full_labels',contract_sha256='a'*64,prepared_pins=list(map(R.digest,rows)),max_length=1000,ref=self.ref)
  self.assertEqual(set(m.kwargs),{'input_ids','attention_mask','logits_to_keep'})
  self.assertEqual(result[0]['index'],1)
if __name__=='__main__':unittest.main()
