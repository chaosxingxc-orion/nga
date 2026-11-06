import ctypes, hashlib, json, os, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import torch
import core, score
from test_cpu import FakeTok, row

class ReferenceExport(unittest.TestCase):
 def run_scorer(self, root, fail=False):
  r=row(); tok=FakeTok(); _,pre,cands=core.encode(r,tok)
  item={'source_key':'decision-v7/dev','row':0,'row_sha256':core.digest(r),'prefix_length':len(pre),'candidate_lengths':list(map(len,cands))}
  work={'mask_sha256':'df9da52a09bed12d562aad304d59863f9c90cc7a46c27b87c818a580774db03d','revision':'synthetic','items':[item],'modes':['full']}
  (root/'mask').write_text('{}'); (root/'work').write_text(json.dumps(work)); (root/'diff').write_text('{"checkpoint_only":[]}')
  (root/'items').mkdir(exist_ok=True); (root/'attempt').mkdir(exist_ok=True)
  class Model:
   hf_device_map={'layer':0}; config=types.SimpleNamespace(text_config=types.SimpleNamespace(max_position_embeddings=2048)); _keys_to_ignore_on_load_unexpected=[]; _raw_capture_count=1
   @classmethod
   def from_pretrained(cls,*a,**kw): return cls(),{}
   def state_dict(self): return {}
   def get_input_embeddings(self): return types.SimpleNamespace(weight=torch.empty(1))
   def eval(self): pass
   def __call__(self,input_ids,attention_mask,use_cache,logits_to_keep):
    w=input_ids.shape[1]; logits=torch.arange(w*17,dtype=torch.float32).reshape(1,w,17).sin()
    return types.SimpleNamespace(logits=logits[:,-logits_to_keep:,:])
  class Query:
   argtypes=None; restype=None
   def __call__(self,i,p): p._obj.value=i; return 0
  npu=types.SimpleNamespace(device_count=lambda:1,set_device=lambda *a:None,matmul=types.SimpleNamespace(allow_hf32=False),conv=types.SimpleNamespace(allow_hf32=False),reset_peak_memory_stats=lambda *a:None,synchronize=lambda *a:None,max_memory_reserved=lambda *a:0,max_memory_allocated=lambda *a:0)
  tf=types.ModuleType('transformers'); tf.AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a,**kw:tok); tf.Qwen3_5ForConditionalGeneration=Model
  a=types.SimpleNamespace(out=str(root),mask=str(root/'mask'),workload=str(root/'work'),dev_root='',code_hash='synthetic',count=1,physical='0',model='',tensor_diff=str(root/'diff'),attempt=str(root/'attempt'),sequence_limit=2048)
  digest=core.digest_bytes
  patches=[mock.patch.dict(sys.modules,{'torch_npu':types.ModuleType('torch_npu'),'transformers':tf}),mock.patch.object(torch,'npu',npu,create=True),mock.patch.dict(os.environ,{'ASCEND_RT_VISIBLE_DEVICES':'0'}),mock.patch.object(ctypes,'CDLL',return_value=types.SimpleNamespace(aclrtGetPhyDevIdByUserDevId=Query())),mock.patch.object(core,'digest_bytes',side_effect=lambda b: work['mask_sha256'] if b==b'{}' else digest(b)),mock.patch.object(core,'read_dev',return_value={'decision-v7/dev':[r]}),mock.patch.object(score.audit,'source_check',return_value={}),mock.patch.object(score.audit,'inventory',return_value=({},{})),mock.patch.object(score.audit,'account',return_value={'errors':[]})]
  if fail: patches.append(mock.patch.object(torch,'save',side_effect=RuntimeError('injected before replace')))
  from contextlib import ExitStack
  with ExitStack() as stack:
   for p in patches: stack.enter_context(p)
   if fail:
    with self.assertRaisesRegex(RuntimeError,'injected before replace'): score.main(a,{'completed':0,'computed':0,'skipped':0})
   else: score.main(a,{'completed':0,'computed':0,'skipped':0})
  return pre,cands,Model()
 def test_export_and_failure_preserves_old_target(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); ref=root/'reference'; ref.mkdir(); target=ref/'logits.pt'; target.write_bytes(b'old target')
   pre,cands,model=self.run_scorer(root)
   manifest=json.loads((ref/'manifest.json').read_text()); c=cands[0]; seq=pre+c
   expected=model(torch.tensor([seq]),None,False,len(c)+1).logits[0]
   tensor=torch.load(target,map_location='cpu',weights_only=True)
   self.assertGreater(len(c),1); self.assertTrue(torch.equal(tensor,expected))
   self.assertEqual(manifest['candidate_token_ids'],c); self.assertEqual(manifest['shape'],list(expected.shape)); self.assertEqual(manifest['dtype'],'float32')
   self.assertEqual(manifest['logits_sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
   self.assertEqual(manifest['npu_score'],core.continuation_sum(expected,seq,len(pre)))
   rec=json.loads(next((root/'items').glob('*.json')).read_text()); self.assertEqual(rec['raw_scores'][0],manifest['npu_score'])
   self.assertFalse(list(ref.glob('.logits-*')))
   old=target.read_bytes(); old_manifest=(ref/'manifest.json').read_bytes()
   for f in (root/'items').glob('*'): f.unlink()
   self.run_scorer(root,True)
   self.assertEqual(target.read_bytes(),old); self.assertEqual((ref/'manifest.json').read_bytes(),old_manifest); self.assertFalse(list(ref.glob('.logits-*')))

if __name__=='__main__': unittest.main()
