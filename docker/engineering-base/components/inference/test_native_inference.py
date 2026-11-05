"""Bounded CPU tests. Injected model functions are never a production route."""
import hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'source/native'))
spec=importlib.util.spec_from_file_location('native_inference',HERE/'native_inference.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.SOURCE_ROOT=HERE.parent.parent/'source/native'

class Storage(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); self.items=self.root/'items'; self.items.mkdir(); self.dest=self.items/'00000000'
  self.ref=m.native.reference(m.SOURCE_ROOT); self.ident='a'*64
  self.prepared={'i':0,'qid':'q','request_sha256':'b'*64,'label_ids':[1,2],'options':['Yes','No']}
  self.z=np.zeros(248320,dtype=np.float32); self.z[0]=-0.; self.z[1]=1.; self.z[2]=-1.; self.z[3]=np.nextafter(np.float32(0),np.float32(1))
  self.pred=m.native.read_logits(self.prepared,self.z,mode='transformers_full_labels',contract_sha256=self.ident,prepared_sha256=m.native.digest(self.prepared),ref=self.ref)
 def tearDown(self): self.t.cleanup()
 def commit(self): m.commit_item(self.items,self.dest,self.prepared,self.ident,self.z,self.pred)
 def test_exact_and_score(self):
  self.commit(); z=np.load(self.dest/'logits.npy',allow_pickle=False)
  self.assertTrue(np.array_equal(z.view('u4'),self.z.view('u4')))
  self.assertTrue(m.exact(m.validate_record(self.dest,self.prepared,self.ident,self.ref),self.pred))
 def test_forged_boolean(self):
  self.commit(); p=self.dest/'record.json'; v=json.loads(p.read_text()); v['prediction']['index']=False; p.write_text(json.dumps(v)); r=self.dest/'COMMITTED.json'; v=json.loads(r.read_text());v['manifest_sha256']=m.sha(p);r.write_text(json.dumps(v))
  with self.assertRaises(ValueError): m.validate_record(self.dest,self.prepared,self.ident,self.ref)
 def test_truncated(self):
  self.commit(); (self.dest/'logits.npy').write_bytes(b'bad')
  with self.assertRaises(ValueError): m.validate_record(self.dest,self.prepared,self.ident,self.ref)
 def test_duplicate(self):
  self.commit()
  with self.assertRaises(ValueError): self.commit()
  self.assertTrue(m.exact(m.validate_record(self.dest,self.prepared,self.ident,self.ref),self.pred))
 def test_duplicate_json_and_strict_types(self):
  p=self.root/'a'; p.write_text('{"i":0,"i":1}')
  with self.assertRaises(ValueError): m.read_json(p)
  self.assertFalse(m.exact(False,0)); self.assertFalse(m.exact([True],[1]))
 def test_v1_read_only(self):
  self.dest.mkdir(); p=self.dest/'record.json'; m.write(p,dict(schema='nga-native-item-v1',identity=self.ident,prepared=self.prepared,logits=self.z.tolist(),prediction=self.pred)); m.write(self.dest/'COMMITTED.json',{'record_sha256':m.sha(p)})
  self.assertTrue(m.exact(m.validate_record(self.dest,self.prepared,self.ident,self.ref),self.pred))

 def test_compact_bridge_rejects_unbound_contract_before_effects(self):
  out=self.root/'compact'
  with self.assertRaisesRegex(ValueError,'panel population contract'):
   m.export_compact(self.root,out,[self.prepared],self.ident,'c'*64,self.ref)
  self.assertFalse(out.exists())
 def test_writer_lock(self):
  import fcntl
  cfg={'adapter':'native-full-label-v1','runtime':'npu','model':{'path':str(self.root/'model'),'manifest':str(self.root/'manifest')},'dataset':{'path':str(self.root/'data')}}
  out=self.root/'locked'; lock=(self.root/'locked.lock').open('w')
  try:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with mock.patch.object(m,'verify',return_value=[{'i':0}]):
    with self.assertRaises(BlockingIOError): m.run(cfg,out)
   self.assertFalse(out.exists())
  finally: lock.close()
 def test_owner_recovery_and_terminal(self):
  cfg={'adapter':'native-full-label-v1','runtime':'npu','model':{'path':str(self.root/'model'),'manifest':str(self.root/'manifest')},'dataset':{'path':str(self.root/'data')}}
  rows=[{'i':0}]; out=self.root/'run'
  z=self.z; prepared=self.prepared; pred=self.pred
  def batch(model, inputs, tok, **kw):
   return [m.native.read_logits(inputs[0],z,mode='transformers_full_labels',contract_sha256=kw['contract_sha256'],prepared_sha256=m.native.digest(inputs[0]),ref=self.ref)]
  with mock.patch.object(m,'verify',return_value=rows), mock.patch.object(m,'load_tokenizer',return_value=object()), mock.patch.object(m,'load_model',return_value=object()), mock.patch.object(m.native,'prepare_request',return_value=dict(prepared,input_ids=[1])), mock.patch.object(m.native,'read_model_batch',side_effect=batch):
   (out/'items'/'00000000').mkdir(parents=True)
   # Unowned directory is never adopted.
   with self.assertRaises(ValueError): m.run(cfg,out)
   (out/'items'/'00000000').rmdir(); (out/'items').rmdir(); out.rmdir()
   result=m.run(cfg,out); self.assertEqual(result['completed'],1)
   with mock.patch.object(m,'load_model',side_effect=AssertionError('weights loaded')):
    self.assertEqual(m.run(cfg,out)['reused'],1)
   partial=out/'items'/'.partial-old'; partial.mkdir(); (partial/'evidence').write_text('retained')
   self.assertEqual(m.run(cfg,out)['reused'],1)
   self.assertTrue(any(p.joinpath('evidence').exists() for p in (out/'quarantine').iterdir()))
   (out/'items'/'00000000'/'logits.npy').write_bytes(b'torn')
   with mock.patch.object(m,'load_model',side_effect=AssertionError('weights loaded')):
    with self.assertRaises(ValueError): m.run(cfg,out)
   self.assertEqual(json.loads((out/'EXIT.json').read_text())['exit_code'],1)

if __name__=='__main__': unittest.main()
