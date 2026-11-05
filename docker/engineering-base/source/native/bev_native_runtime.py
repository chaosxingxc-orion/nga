"""Pinned AnyJev prompt/label readout preparation. No model loading or launch.

Two explicit engine semantics: transformers_full_labels and vllm_top20_labels.
The latter is a CPU diagnostic of top-k censorship, not vLLM numerical equivalence.
Gold is not accepted in inference requests or emitted predictions.
"""
import ast,hashlib,json,math,sys,types
from collections.abc import Mapping
from pathlib import Path
import numpy as np
from typing import Any,Dict,List,Optional,Sequence,Tuple

UPSTREAM=Path('/mnt/cephfs/xingchao/omni/repos/jev/nokia-applied-research__AnyJev')
PINS={'question.py':'72e61e3b846e9efa76cbe5b1f5c8fdc5ffa5e5f9eb86de17bcbae5ffdd4ac368','readout.py':'cb13450f4a54b892bc0be1145d3da00bf89013b4fd321df89927c37bd945d973','tacit.py':'5c470f2521fa01ebf3be9117339939c7575181a452f226d728caa18ccce9b39d'}
def require(ok,why):
 if not ok:raise ValueError(why)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def reference(root=UPSTREAM):
 """Execute exact pinned source AST only; never import downloaded package paths."""
 trees={}
 for name,pin in PINS.items():
  p=Path(root)/'anyjev'/name;raw=p.read_bytes();require(hashlib.sha256(raw).hexdigest()==pin,'upstream source changed');trees[name]=ast.parse(raw)
 q=types.ModuleType('_nga_native_question');sys.modules[q.__name__]=q
 exec(compile(trees['question.py'],str(root/'anyjev/question.py'),'exec'),q.__dict__)
 r=types.SimpleNamespace();ns={'Question':q.Question,'__name__':'_nga_native_readout'}
 module=types.ModuleType(ns['__name__']);module.Question=q.Question;sys.modules[module.__name__]=module
 nodes=[x for x in trees['readout.py'].body if not (isinstance(x,ast.ImportFrom) and x.module=='anyjev.question')]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(root/'anyjev/readout.py'),'exec'),module.__dict__)
 ns={**module.__dict__,'np':np,'math':math,'KINDS':{'choice':'choice','yes_no':'noul','noul':'noul','score':'score'},'Any':Any,'Dict':Dict,'Optional':Optional,'Sequence':Sequence}
 nodes=[x for x in trees['tacit.py'].body if isinstance(x,ast.FunctionDef) and x.name in ['restricted_logprobs','make_question']]
 cls=next(x for x in trees['tacit.py'].body if isinstance(x,ast.ClassDef) and x.name=='Tacit')
 nodes.append(ast.ClassDef(name='Tacit',bases=[],keywords=[],body=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in ['_normalise','_result']],decorator_list=[]))
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(root/'anyjev/tacit.py'),'exec'),ns)
 return types.SimpleNamespace(**ns)

def prepare_request(item,tokenizer,ref=None):
 require('y' not in item and 'gold' not in item,'gold must remain CPU-only')
 require(type(item.get('i')) is int and item['i']>=0 and type(item.get('qid')) is str,'invalid request identity')
 ref=ref or reference();t=ref.Tacit();t.tok=tokenizer;it=t._normalise(item)
 spec=ref.build_prompt(it['state'],it['q'],list(range(it['q'].k)),ref.DEFAULT_SYSTEM,it['labels'])
 text=ref.render_chat(tokenizer,spec);ids=list(tokenizer.encode(text,add_special_tokens=False))
 require(bool(ids) and all(type(x) is int and x>=0 for x in ids),'invalid input tokens')
 return dict(schema='bev-native-input-v1',i=item['i'],qid=item['qid'],request_sha256=digest(item),input_ids=ids,rendered_prompt=text,labels=it['labels'],label_ids=it['ids'],options=list(it['q'].options),kind=it['q'].kind)

def read_logits(prepared,logits,*,mode,contract_sha256,prepared_sha256,ref=None):
 """Caller supplies one final-position FULL vocabulary vector; never branch scores.

Top20 mode returns censored float64 log-probability values as upstream server does;
logit ties at the top20 cut are rejected: server's tie order isn't specified.
Nonfinite native outcomes are retained with explicit nonfinite encoding and cannot
enter the stricter CPU summary until its policy has been independently satisfied.
"""
 require(digest(prepared)==prepared_sha256,'prepared input identity differs')
 require(mode in ('transformers_full_labels','vllm_top20_labels'),'explicit engine mode required')
 require(type(contract_sha256) is str and len(contract_sha256)==64 and all(c in '0123456789abcdef' for c in contract_sha256),'contract pin required')
 z=np.asarray(logits)
 require(z.ndim==1 and len(z)>max(prepared['label_ids']),'finite full vocabulary required')
 try:
  require(np.isfinite(z).all(),'finite full vocabulary required')
 except (TypeError,ValueError):
  raise ValueError('finite full vocabulary required')
 # The native contract computes in float32.  A finite float64 input can
 # overflow during that conversion, so validate the representation consumed
 # by the model as well as the caller's representation.
 with np.errstate(over='ignore',invalid='ignore'):
  z32=z.astype(np.float32)
 require(np.isfinite(z32).all(),'float32 vocabulary is nonfinite')
 z=z32.astype(np.float64);ids=prepared['label_ids'];require(len(ids)==len(set(ids))==len(prepared['options']),'label identity differs')
 retained=None
 if mode=='vllm_top20_labels':
  order=np.argsort(-z);k=min(20,len(z))
  require(k==len(z) or z[order[k-1]]!=z[order[k]],'ambiguous top20 boundary')
  retained=set(int(x) for x in order[:k]);m=float(z.max());lp=z-(m+np.log(np.exp(z-m).sum()));values=[float(lp[i]) if i in retained else -math.inf for i in ids]
 else:values=[float(z[i]) for i in ids]
 ref=ref or reference();lp=ref.restricted_logprobs(values)
 q=types.SimpleNamespace(options=prepared['options']);result=ref.Tacit._result({'q':q},lp,'one_forward')
 def serial(v):return float(v) if math.isfinite(float(v)) else ('-inf' if float(v)<0 else 'inf')
 return dict(schema='bev-native-prediction-v1',i=prepared['i'],qid=prepared['qid'],contract_sha256=contract_sha256,request_sha256=prepared['request_sha256'],input_sha256=digest(prepared),mode=mode,label_ids=ids,label_values=[serial(x) for x in values],restricted_logprobs=[serial(x) for x in lp],index=result['index'],first_index=result['index'],first_margin=serial(result['margin']),route='one_forward',reasoning_tokens=0,top20_label_presence=None if retained is None else [i in retained for i in ids],native_runtime_equivalence=False)


def read_model_batch(model,prepared,tokenizer,*,mode,contract_sha256,prepared_pins,max_length,ref=None):
 """Prospective Transformers engine adapter. No load, device move or launch here.

 Caller owns exact model/dtype/kernel identity. This preserves upstream left-pad
 final-position full-vocabulary read; batch shape numerical equivalence unproven.
 No silent truncation. Cached native input identities are revalidated on use.
 """
 import torch
 require(prepared and len(prepared)==len(prepared_pins),'population missing')
 require(tokenizer.padding_side=='left','native final-position read requires left padding')
 require(type(max_length) is int and max_length>0,'invalid max length')
 for row,pin in zip(prepared,prepared_pins):
  require(digest(row)==pin,'prepared input identity differs')
  require(tokenizer.encode(row['rendered_prompt'],add_special_tokens=False)==row['input_ids'],'tokenizer/input mismatch')
  require(len(row['input_ids'])<=max_length,'input exceeds registered max; no truncation')
 enc=tokenizer([x['rendered_prompt'] for x in prepared],return_tensors='pt',padding=True,add_special_tokens=False)
 # Validate the actual tensors returned by the batch tokenizer before moving
 # them to the model.  Checking single-row encode() above is insufficient:
 # a faulty/custom batch path could silently reorder, truncate or mutate a
 # row while the prediction still carries the original request hash.
 require(isinstance(enc,Mapping) and 'input_ids' in enc and 'attention_mask' in enc,'tokenizer batch missing tensors')
 # The native protocol registers exactly these two inputs.  Passing an
 # unregistered tokenizer field (for example position_ids or token_type_ids)
 # would let a custom batching path change model semantics while the pinned
 # input hash remains unchanged.  Such fields must first be added to a new
 # protocol with their own identity and numerical checks; they are rejected
 # here rather than silently forwarded.
 require(set(enc.keys())=={'input_ids','attention_mask'},'tokenizer batch contains unregistered tensors')
 input_ids,attention_mask=enc['input_ids'],enc['attention_mask']
 require(all(torch.is_tensor(v) for v in enc.values()),'tokenizer batch values must be tensors')
 require(getattr(input_ids,'ndim',None)==2 and getattr(attention_mask,'ndim',None)==2,'tokenizer batch tensors must be 2-D')
 require(tuple(input_ids.shape)==tuple(attention_mask.shape),'input/mask shape mismatch')
 require(input_ids.shape[0]==len(prepared),'tokenizer batch dropped rows')
 require(input_ids.shape[1]>0 and input_ids.shape[1]<=max_length,'tokenizer batch width exceeds registered max')
 integer_dtypes=(torch.uint8,torch.int8,torch.int16,torch.int32,torch.int64)
 require(input_ids.dtype in integer_dtypes and attention_mask.dtype in integer_dtypes+(torch.bool,),'tokenizer batch tensors must be integer')
 width=int(input_ids.shape[1])
 for index,row in enumerate(prepared):
  ids_row=input_ids[index].detach().cpu().tolist(); mask_row=attention_mask[index].detach().cpu().tolist()
  require(all(int(x) in (0,1) for x in mask_row),'attention mask must be binary')
  n=sum(int(x) for x in mask_row)
  require(n==len(row['input_ids']) and n>0,'tokenizer batch length differs from pinned input')
  require(mask_row[:width-n]==[0]*(width-n) and mask_row[width-n:]==[1]*n,'padding must be left-only')
  require(ids_row[width-n:]==list(row['input_ids']),'batched input ids differ from pinned input')
 require(width==max(len(x['input_ids']) for x in prepared),'tokenizer batch width differs from registered population')
 # Construct the call only from the tensor objects validated above.  Do not
 # iterate an arbitrary Mapping a second time: a wrapper can expose different
 # items from its keys or replace values after validation.
 enc={'input_ids':input_ids.to(model.device),'attention_mask':attention_mask.to(model.device)}
 require(enc['input_ids'].shape[0]==len(prepared),'tokenizer batch dropped rows')
 with torch.no_grad():
  try:logits=model(**enc,logits_to_keep=1).logits[:,-1,:].float()
  except TypeError:logits=model(**enc).logits[:,-1,:].float()
 rows=logits.cpu().numpy();require(len(rows)==len(prepared),'model batch dropped rows')
 return [read_logits(p,z,mode=mode,contract_sha256=contract_sha256,prepared_sha256=pin,ref=ref) for p,z,pin in zip(prepared,rows,prepared_pins)]
