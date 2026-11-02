import copy
from collections import Counter
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
HERE=Path(__file__).resolve().parent

def module(name):
 s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=module('bev_batch_efficiency_probe');H=module('bev_batch_efficiency_host');E=module('test_bev_encode_once');B=module('bev_public_test_bridge')

class Tests(unittest.TestCase):
 def fixture(self,root,unstable=False):
  rows=[E.row(str(i),text='context '+str(i)) for i in range(72)]
  class Scorer(E.Scorer):
   def __init__(self,model,**kw):super().__init__();self.token_budget=kw['token_budget'];self.stats=Counter();self.calls=0
   def load(self):return self
   def score_enc(self,enc,mode):
    self.calls+=1;self.stats.update(tokens=100,padded_tokens=10,forwards=1,head_positions=16,items=len(enc));result=super().score_enc(enc,mode)
    if unstable and self.calls==10:result[0][0]+=1e-9
    return result
  sm=types.SimpleNamespace(R3Scorer=Scorer,dedup_enc=lambda enc:(enc,[list(range(len(e.cands))) for e in enc],0,0))
  sc=Scorer('unused',token_budget=16384);lengths={r['id']:max(len(e.prefix)+len(c) for c in e.cands) for r in rows for e in sc.encode([B.to_r3_row(r['request'])])}
  orders={'baseline':[r['id'] for r in rows],'bucketed':sorted(lengths,key=lambda x:(lengths[x],x))};orders={k:[v[i:i+8] for i in range(0,72,8)] for k,v in orders.items()}
  requests=root/'requests.jsonl';requests.write_text(''.join(json.dumps(r)+'\n' for r in rows));batches=root/'batches.json';batches.write_text(json.dumps(orders))
  out=root/'output';out.mkdir();P.reserve_measurement(out,'a'*64,1)
  plan=dict(out=str(out),model='/unused',inputs={'requests':{'path':str(requests)},'batches':{'path':str(batches)}},scoring=P.SCORING)
  npu=types.SimpleNamespace(set_device=lambda _:None,synchronize=lambda:None,max_memory_reserved=lambda:5*2**30,conv=types.SimpleNamespace(allow_hf32=True),matmul=types.SimpleNamespace(allow_hf32=True))
  return rows,orders,plan,(E.P,sm,B,E.R),npu
 def run_fixture(self,root,unstable=False):
  rows,orders,plan,components,npu=self.fixture(root,unstable)
  with mock.patch.object(P,'verify',return_value=plan),mock.patch.object(P,'load_components',return_value=components),mock.patch.dict(sys.modules,{'torch':types.SimpleNamespace(npu=npu),'torch_npu':types.SimpleNamespace()}),contextlib.redirect_stdout(io.StringIO()):
   if unstable:
    with self.assertRaisesRegex(ValueError,'raw score'):P.run(root/'plan.json','a'*64,1)
   else:self.assertEqual(P.run(root/'plan.json','a'*64,1),0)
  return rows,orders,plan
 def test_complete_sweeps_and_operands_are_reconstructible(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);rows,orders,plan=self.run_fixture(root);out=Path(plan['out']);ids=[r['id'] for r in rows]
   ops=[json.loads((out/'attempts/1'/f'{k}-operand.json').read_text()) for k in ('baseline','repeat','bucketed')]
   P.compare(ops[0],ops[1],ids);P.compare(ops[0],ops[2],ids)
   self.assertEqual(len(ops[2]['tokens']),72);self.assertEqual(len(list((out/'trials').glob('*.json'))),6)
   trials=[json.loads(p.read_text()) for p in (out/'trials').glob('*.json')];report=P.summarize(trials,ids,'a'*64)
   self.assertEqual(report['measurements']['baseline']['sweeps'],3);self.assertEqual(report['measurements']['bucketed']['counts']['items'],216)
   for mutation in ('missing','duplicate','foreign','raw','bad_time','bad_attempt'):
    bad=copy.deepcopy(trials)
    if mutation=='missing':bad.pop()
    if mutation=='duplicate':bad[-1]=bad[0]
    if mutation=='foreign':bad[0]['outputs'][0]['id']='foreign'
    if mutation=='raw':bad[0]['outputs'][0]['raw'][0]+=1
    if mutation=='bad_time':bad[0]['score_seconds']=float('nan')
    if mutation=='bad_attempt':bad[0]['attempt']=999
    with self.assertRaises(ValueError):P.summarize(bad,ids,'a'*64)
 def test_numerical_mismatch_saves_both_operands_before_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);rows,orders,plan=self.run_fixture(root,True);out=Path(plan['out'])
   self.assertTrue((out/'FAILURE.json').exists());self.assertEqual(json.loads((out/'attempts/1/EXIT.json').read_text())['exit_code'],1)
   self.assertTrue((out/'attempts/1/baseline-operand.json').exists());self.assertTrue((out/'attempts/1/repeat-operand.json').exists());self.assertTrue((out/'attempts/1/bucketed-operand.json').exists())
   self.assertFalse((out/'COMPLETE.json').exists());self.assertEqual(list((out/'trials').iterdir()),[])
 def test_duplicate_missing_ids_and_candidate_swap_reject(self):
  ids=[str(i) for i in range(72)];orders={v:[ids[i:i+8] for i in range(0,72,8)] for v in ('baseline','bucketed')}
  P.validate_orders(orders,ids);orders['bucketed'][0][0]='1'
  with self.assertRaises(ValueError):P.validate_orders(orders,ids)
  outputs=[dict(id=i,raw=[1.,2.],prediction=dict(id=i,status='ok',index=1)) for i in ids]
  a=dict(outputs=outputs,tokens={});b=copy.deepcopy(a);b['outputs'][0]['raw'].reverse()
  with self.assertRaises(ValueError):P.compare(a,b,ids)
  bad=copy.deepcopy(outputs);bad[-1]=bad[0]
  with self.assertRaises(ValueError):P.canonical_outputs(bad,ids)
 def test_existing_timing_artifact_refused_before_loading_or_claim(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);rows,orders,plan,components,npu=self.fixture(root);out=Path(plan['out']);(out/'trials').mkdir();f=out/'trials/foreign.json';f.write_text('{"attempt":999}')
   with mock.patch.object(P,'verify',return_value=plan),mock.patch.object(P,'load_components') as load:
    with self.assertRaisesRegex(ValueError,'existing measurement'):P.run(root/'plan.json','a'*64,1)
    load.assert_not_called()
   review=root/'review.json';review.write_text(json.dumps({'attempts':[1]}));args=types.SimpleNamespace(plan=str(root/'plan.json'),sha256='a'*64,review=str(review),review_sha256='b'*64,attempt=1)
   with mock.patch.object(H,'review',return_value=plan),mock.patch.object(H,'runner',return_value=P),mock.patch.object(H.socket,'gethostname',return_value='k8s-node1'),mock.patch.object(H.subprocess,'run') as call,mock.patch.object(H.subprocess,'Popen') as spawn:
    for op in (H.start,H.supervise):
     with self.assertRaisesRegex(ValueError,'existing measurement'):op(args)
    call.assert_not_called();spawn.assert_not_called()
   self.assertEqual(f.read_text(),'{"attempt":999}')
 def test_exclusive_commit_collision_and_no_retry(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/'trial.json';P.atomic(f,dict(attempt=999),exclusive=True)
   with self.assertRaises(FileExistsError):P.atomic(f,dict(attempt=1),exclusive=True)
   self.assertEqual(json.loads(f.read_text())['attempt'],999)
   with self.assertRaises(ValueError):P.fresh_measurement(root,2)
 def test_detached_command_attempt1_and_precise_device(self):
  plan=dict(container='probe',chip=7,environment=P.ENV,mounts=[],image_sha256=P.IMAGE,code={'runner':{'path':'/fixed/runner.py'}})
  command=H.expected_command(plan,'/fixed/plan','a'*64,1);self.assertEqual(command[:3],['docker','run','-d']);self.assertNotIn('--rm',command);self.assertIn('/dev/davinci7',command)
  with self.assertRaises(ValueError):H.expected_command(plan,'/fixed/plan','a'*64,2)

if __name__=='__main__':unittest.main()
