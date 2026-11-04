import unittest,tempfile,json,types,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent

def load(name):
 p=HERE/name;m=types.ModuleType(name);m.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
class BackendTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.B=load('bev_native_matched_backend_v1.py');self.M=load('bev_native_matched_perf_v1.py')
  self.item={'input_ids':[7,8]};self.pred={'contract_sha256':'contract','input_sha256':self.M.digest(self.item),'restricted_logprobs':[0.]};self.result={'variant':'reference','forwards':1,'prediction':self.pred,'restricted_logprobs':[0.]};self.a={'input_ids':np.array([[7,8]],dtype=np.int64),'attention_mask':np.array([[1,1]],dtype=np.int64),'logits':np.zeros((1,248320),dtype=np.float32)}
  self.N=types.SimpleNamespace(read_logits=lambda *a,**k:self.pred,digest=self.M.digest);self.plan={'contract_sha256':'contract','protocol_module':self.M,'native_module':self.N,'reference':None};self.save()
 def save(self):
  with (self.root/'operands.npz').open('wb') as f:np.savez(f,**self.a)
  (self.root/'result.json').write_text(json.dumps(self.result));(self.root/'COMMITTED.json').write_text(json.dumps({n:self.B.sha(self.root/n) for n in ['operands.npz','result.json']}))
 def test_real_numpy_full_operand(self):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_changed_bytes(self):
  (self.root/'result.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'changed operand'):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_wrong_variant(self):
  with self.assertRaisesRegex(ValueError,'variant'):self.B.check_operand(self.root,'adapter',self.item,self.plan)
 def test_nonfinite(self):
  self.a['logits'][0,33]=np.nan;self.save()
  with self.assertRaisesRegex(ValueError,'finite'):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_wrong_mask(self):
  self.a['attention_mask'][0,1]=0;self.save()
  with self.assertRaisesRegex(ValueError,'input/mask'):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_rehashed_prediction_tamper(self):
  self.result['restricted_logprobs']=[1.];self.save()
  with self.assertRaisesRegex(ValueError,'stored prediction'):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_full_vocab_required(self):
  self.a['logits']=self.a['logits'][:,:50];self.save()
  with self.assertRaisesRegex(ValueError,'full finite'):self.B.check_operand(self.root,'reference',self.item,self.plan)
 def test_symlink_rejected(self):
  p=self.root.parent/(self.root.name+'-link');p.symlink_to(self.root);self.addCleanup(p.unlink)
  with self.assertRaisesRegex(ValueError,'unsafe'):self.B.check_operand(p,'reference',self.item,self.plan)
if __name__=='__main__':unittest.main()
