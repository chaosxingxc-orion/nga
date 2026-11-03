import json, tempfile, unittest
from pathlib import Path
from tools import r3_eval_profile_probe as P
class Scorer:
 def __init__(self):self.encodes=0;self.scores=0
 def encode(self,rows):self.encodes+=1;return rows
 def score_enc(self,enc,mode='rightpad'):self.scores+=1;return [{'s':len(x['id'])} for x in enc]
class ProfileTests(unittest.TestCase):
 def test_panel_middle_chunk_and_flags(self):
  with tempfile.TemporaryDirectory() as d:
   rows=[{'id':str(i),'cell':'k'} for i in range(70)]+[{'id':str(i),'cell':'t'} for i in range(5)]
   m=P.make_panel(rows,Path(d)/'panel');self.assertEqual(m['rows'],37);self.assertEqual(m['cells']['k']['selected_ids'][0],'id:0');self.assertFalse(m['test_read'])
   out=(Path(d)/'panel.jsonl').read_text();self.assertNotIn('gold',out)
 def test_rejects_gold_and_test(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'dev.jsonl';p.write_text(json.dumps({'id':'x','cell':'dev','gold':1})+'\n')
   with self.assertRaises(ValueError):P.read_jsonl(p)
   with self.assertRaises(ValueError):P.make_panel([{'id':'x','cell':'test'}],Path(d)/'x')
 def test_score_calls_each_method_once_and_equivalence(self):
  s=Scorer();scores,t=P.score_batch(s,[{'id':'a'},{'id':'b'}]);self.assertEqual((s.encodes,s.scores),(1,1));self.assertEqual(P.compare_outputs(scores,scores)['equivalent'],True);self.assertEqual(t.report()['forward_head']['n'],1)
 def test_mutation_rejected(self):
  with self.assertRaises(ValueError):P.compare_outputs([{'x':1}],[{'x':2}])

class FakeFrozenScorer:
 def __init__(self):
  from collections import Counter
  self.stats=Counter();self.calls=[];self.fail=False
 def _sync(self):self.calls.append('sync')
 def load(self):self.calls.append('load');return self
 def encode(self,rows):self.calls.append('encode');return rows
 def _score_flat_batch(self,rows):self.calls.append('flat');return self._token_logprobs(rows)
 def _token_logprobs(self,rows):self.calls.append('head');return [[-float(i) for i in range(len(r['levels']))] for r in rows]
 def score_enc(self,rows,mode='rightpad'):
  self.calls.append('score');self.stats['tokens']+=len(rows)*3
  s=self._score_flat_batch(rows);self._sync()
  if self.fail:s[0][0]=0.25
  return s
 def score_raw(self,rows,mode='rightpad'):return self.score_enc(self.encode(rows),mode=mode)

class LifecycleTests(unittest.TestCase):
 def cells(self):return {'K/decision-v7/dev/clean':[{'id':'1','row':{'levels':[{},{}]}}]}
 def test_wrapper_calls_and_returns_exactly_once(self):
  sc=FakeFrozenScorer();base=sc.score_raw([{'levels':[{},{}]}]);calls=list(sc.calls);sc.calls=[]
  with P.Instrument(sc) as tr:actual=sc.score_raw([{'levels':[{},{}]}])
  self.assertEqual(sc.calls,calls);self.assertEqual(actual,base);self.assertEqual(len(tr.events),4)
  self.assertEqual(sc.encode.__self__,sc)
 def test_completed_passes_persist_and_refuse_restart(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'run';sc=FakeFrozenScorer();P.execute_batches(sc,self.cells(),out,repeats=3)
   self.assertEqual(json.loads((out/'EXIT.json').read_text())['exit_code'],0)
   self.assertEqual(len(list(out.glob('*/PASS.json'))),7)
   with self.assertRaises(FileExistsError):P.execute_batches(sc,self.cells(),out,repeats=3)
 def test_failed_gate_persists_both_operands_and_terminal(self):
  class Bad(FakeFrozenScorer):
   def score_enc(self,*a,**kw):
    self.fail=self.stats['tokens']>0;return super().score_enc(*a,**kw)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'run'
   with self.assertRaises(ValueError):P.execute_batches(Bad(),self.cells(),out,repeats=3)
   self.assertEqual(json.loads((out/'EXIT.json').read_text())['exit_code'],1)
   self.assertTrue(list((out/'cold_reference').glob('*.json')));self.assertTrue(list((out/'split_gate').glob('*.json')))
   self.assertFalse((out/'report.json').exists());self.assertFalse((out/'split_gate/PASS.json').exists())
 def test_write_never_overwrites_existing_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'value.json';P.publish(p,{'first':1})
   with self.assertRaises(FileExistsError):P.publish(p,{'second':2})
   self.assertEqual(json.loads(p.read_text()),{'first':1})


class AdmissionTests(unittest.TestCase):
 def fixture(self,root):
  files={}
  for name in ('model','adapter'):
   d=root/name;d.mkdir()
   for file in (('config.json','model.safetensors') if name=='model' else ('adapter_config.json','adapter_model.safetensors')):
    p=d/file;p.write_bytes(b'{}');files[str(p)]=P.sha(p)
  spec={'schema':'r3-posttrain-dev-spec-v1','test_read':False,'scientific_acceptance':False,
        'model':str(root/'model'),'adapter':str(root/'adapter'),'files':files,
        'command':['python3','--model-path',str(root/'model'),'--adapter',str(root/'adapter'),
                   '--partitions','dev,calibration','--scorer','rightpad','--dtype','float32',
                   '--token-budget','16384','--device','npu:0','--no-hf32']}
  sp=root/'spec.json';sp.write_text(json.dumps(spec));ref=P.pin(sp)
  m=P.make_panel([{'id':str(i),'cell':'cell'+str(i//32)} for i in range(1024)],root/'panel')
  m['source_spec']=ref;mp=root/'panel.manifest.json';mp.write_text(json.dumps(m))
  plan={'schema':P.SCHEMA,'source_spec':ref,'manifest':P.pin(mp),'panel':P.pin(root/'panel.jsonl'),
        'model':spec['model'],'adapter':spec['adapter'],'device':'npu:0','mode':'rightpad','dtype':'float32',
        'repeats':3,'chip':6,'token_budget':16384,'test_read':False,'scientific_acceptance':False,
        'candidate_selection_allowed':False,'files':dict(files,**{str(Path(P.__file__).resolve()):P.sha(P.__file__)})}
  return plan,spec,sp
 def verify(self,root,plan):
  p=root/'plan.json';p.write_text(json.dumps(plan));return P.verify(str(p),P.sha(p))
 def test_actual_verify_binds_model_adapter_and_scope(self):
  import copy
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);plan,spec,sp=self.fixture(root)
   self.assertEqual(len(self.verify(root,plan)[1]),32)
   for key,value in [('model',str(root/'other-model')),('adapter',str(root/'other-adapter')),
                     ('candidate_selection_allowed',True),('candidate_selection_allowed',0)]:
    changed=copy.deepcopy(plan);changed[key]=value
    with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.verify(root,changed)
 def test_inventory_and_spec_argument_mutations_reject(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);plan,spec,sp=self.fixture(root)
   extra=root/'adapter'/'unregistered.bin';extra.write_bytes(b'extra')
   with self.assertRaisesRegex(ValueError,'inventory'):self.verify(root,plan)
   extra.unlink();plan['files'].pop(str(root/'adapter'/'adapter_model.safetensors'))
   with self.assertRaisesRegex(ValueError,'dependency'):self.verify(root,plan)
 def test_source_spec_pin_and_manifest_binding_reject(self):
  import copy
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);plan,spec,sp=self.fixture(root)
   changed=copy.deepcopy(plan);changed['source_spec']['sha256']='0'*64
   with self.assertRaisesRegex(ValueError,'source spec binding'):self.verify(root,changed)
   spec['command']+=['--model-path',spec['model']];sp.write_text(json.dumps(spec))
   with self.assertRaisesRegex(ValueError,'input/source changed'):self.verify(root,plan)

if __name__=='__main__':unittest.main()
