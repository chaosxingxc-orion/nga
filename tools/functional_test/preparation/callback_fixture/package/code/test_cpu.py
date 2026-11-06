import json, math, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import torch
import core

class FakeTok:
 pad_token_id = 0
 def __call__(self,s,add_special_tokens=False):
  assert add_special_tokens is False
  return {'input_ids':[ord(c)%17 for c in s]}

def row():
 return {'candidate_set':'exclusive','task_definition':'decide','input':'hello','question':'what','group_id':'g','variant':'original','qname':'q','gold':'b','levels':[{'id':'a','name':'A','definition':'first'},{'id':'b','name':'BC','definition':'second'}]}

class Tests(unittest.TestCase):
 def test_multitoken_reference(self):
  # Formula matches HFScorer's retained positions keep-1-n+q.
  gen=torch.Generator().manual_seed(18)
  for n in (1,2,5):
   prefix=[1,3,4]; cand=list(range(n)); seq=prefix+cand; full=torch.randn(len(seq),11,generator=gen)
   keep=n+1; retained=full[-keep:]; logp=torch.log_softmax(retained.float(),-1)
   ref=sum(float(logp[keep-1-n+q,seq[len(seq)-n+q]]) for q in range(n))
   self.assertAlmostEqual(core.continuation_sum(retained,seq,len(prefix)),ref,places=6)
   direct=torch.log_softmax(full.float(),-1)
   self.assertAlmostEqual(ref,sum(float(direct[len(prefix)-1+q,cand[q]]) for q in range(n)),places=6)
   with self.assertRaises(ValueError): core.continuation_sum(retained[1:],seq,len(prefix))
 def test_encoding_and_controls(self):
  r=row(); p,pre,c=core.encode(r,FakeTok()); self.assertEqual(p.candidates,(' A',' BC')); self.assertEqual(list(map(len,c)),[2,3]); self.assertTrue(pre)
  self.assertNotEqual(core.encode(r,FakeTok(),'full')[0].text,core.encode(r,FakeTok(),'blank')[0].text)
  self.assertNotEqual(core.encode(r,FakeTok(),'blank')[0].text,core.encode(r,FakeTok(),'drop')[0].text)
  bad=row(); bad['gold']='missing'
  with self.assertRaises(ValueError): core.encode(bad,FakeTok())
 def test_resume_and_schema(self):
  r=row(); ident=core.expected(r,'decision-v7/dev',0,'full','run')
  rec=dict(ident,raw_scores=[-1.,-2.],prefix_length=10,candidate_lengths=[1,2])
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'items/a.json'; core.put(f,rec); self.assertEqual(core.validate_record(json.loads(f.read_text()),ident),rec)
   reversed_row=row(); reversed_row['levels'].reverse()
   with self.assertRaises(ValueError): core.validate_record(rec,core.expected(reversed_row,'decision-v7/dev',0,'full','run'))
   wrong=row(); wrong['gold']='a'
   with self.assertRaises(ValueError): core.validate_record(rec,core.expected(wrong,'decision-v7/dev',0,'full','run'))
   self.assertIsNone(core.load_completed(Path(d)/'items/b.json',ident)); self.assertEqual(core.load_completed(f,ident),rec)
   for change in ({'raw_scores':[float('nan'),0]}, {'candidate_lengths':[1]}, {'prefix_length':0}):
    with self.assertRaises(ValueError): core.validate_record(dict(rec,**change),ident)
 def test_against_actual_reference_scorer(self):
  sys.path.insert(0,'/mnt/cephfs/xingchao/experiments/jev/r0_code')
  import scorer
  class Model:
   def __call__(self,input_ids,attention_mask,use_cache,logits_to_keep):
    width=input_ids.shape[1]; vocab=17
    logits=torch.arange(width*vocab,dtype=torch.float32).reshape(1,width,vocab).sin()
    return type('Result',(),{'logits':logits[:,-logits_to_keep:,:]})()
  tok=FakeTok(); r=row(); model=Model()
  ref=scorer.HFScorer('unused',device='cpu',token_budget=1,model=model,tokenizer=tok)
  captured=[]; original=scorer.softmax
  scorer.softmax=lambda x:(captured.append(x[:]),original(x))[1]
  try: ref.score([r])
  finally: scorer.softmax=original
  _,prefix,candidates=core.encode(r,tok); actual=[]
  for c in candidates:
   seq=prefix+c; ids=torch.tensor([seq]); logits=model(ids,torch.ones_like(ids),False,len(c)+1).logits[0]
   actual.append(core.continuation_sum(logits,seq,len(prefix)))
  self.assertEqual(actual,captured[0])
 def test_manifest_validation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); mask={}
   for s in ('decision-v7','transfer-v4'):
    for name in ('dev','dev.variants'):
     data=(json.dumps(row())+'\n').encode(); path=root/s/(name+'.jsonl'); path.parent.mkdir(exist_ok=True); path.write_bytes(data)
     mask[s+'/'+name]={'source_sha256':core.digest_bytes(data),'rows':[dict(row=0,sha256=core.digest_bytes(data.rstrip(b'\n')),group_id='g',variant='original',qname='q')]}
   self.assertEqual(len(core.read_dev(mask,root)),4)
   mask['decision-v7/dev']['rows'][0]['sha256']='bad'
   with self.assertRaises(ValueError): core.read_dev(mask,root)

if __name__=='__main__': unittest.main()
