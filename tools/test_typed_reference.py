import copy,importlib.util,json,math,unittest
from pathlib import Path

def module(name):
 s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('typed_reference_kev');v=module('verify_typed_reference')
def raw():
 qs={'a':{'type':'choice','instructions':'Choose','criteria':{'x':None,'y':''}},'b':{'type':'noul','instructions':'真的？'},'c':{'type':'score','instructions':'Level','criteria':['low','high']},'d':{'type':'choice','instructions':'Choose','criteria':{'z':'Z','w':'W'}},'e':{'type':'noul','instructions':'Confirm'}}
 gold={k:{'type':q['type'],'probabilities':{x:p for x,p in zip(m.keys(q),[.499999,.5])}} for k,q in qs.items()}
 return {'id':'fixture','workflow':'fixture','split':'test','state':json.dumps({'中文':{'nested':['x']}}),'questions':json.dumps(qs),'gold':json.dumps(gold)}
def pred(r):
 return {'probabilities':{q:{k:.5 for k in m.keys(x)} for q,x in m.request(r)['questions'].items()},'logits':{q:{k:0. for k in m.keys(x)} for q,x in m.request(r)['questions'].items()},'inference_temperature':2.}
class Tests(unittest.TestCase):
 def test_gold_not_in_model_input(self):
  r=raw();a=m.inference_record(r);r['gold']='changed';r['factors']='secret';self.assertEqual(a,m.inference_record(r));self.assertNotIn('gold',a)
 def test_candidate_reorder_changes_input(self):
  r=raw();a=m.orderedsha(m.request(r));q=json.loads(r['questions']);q['a']['criteria']={'y':'','x':None};r['questions']=json.dumps(q);self.assertNotEqual(a,m.orderedsha(m.request(r)))
 def test_three_types_valid(self):m.validate_prediction(raw(),pred(raw()),2.)
 def test_wrong_question_order(self):
  r=raw();p=pred(r);p['probabilities']=dict(reversed(list(p['probabilities'].items())))
  with self.assertRaisesRegex(ValueError,'question order'):m.validate_prediction(r,p,2.)
 def test_invalid_values(self):
  for x in [float('nan'),-1.,2.]:
   r=raw();p=pred(r);p['probabilities']['a']['x']=x
   with self.assertRaises(ValueError):m.validate_prediction(r,p,2.)
 def test_missing_question(self):
  r=raw();p=pred(r);del p['probabilities']['a']
  with self.assertRaises(ValueError):m.validate_prediction(r,p,2.)
 def test_receipt_foreign_index(self):
  r=raw();payload={'index':0,'id':r['id'],'identity':'i','input_sha256':v.stamp(r),'request_ordered_sha256':v.stamp(m.request(r),False),'prediction':pred(r),'seconds':.1};e={'payload':payload,'sha256':v.stamp(payload)}
  self.assertEqual(v.validate_receipt(e,r,0,'i',2.),pred(r))
  with self.assertRaisesRegex(ValueError,'identity'):v.validate_receipt(e,r,1,'i',2.)
 def test_metric_independence_and_gold_rounding(self):
  r=raw();p=pred(r);a=m.native_score([r],[p],2.,lambda prediction,gold:tuple(v.score(prediction['probabilities'],gold)[k] for k in ['ok','kl','brier','conf']));b=v.summaries([r],[p],2.);v.same(a,b)
  self.assertGreater(a['original_arithmetic_raw_readout']['brier'],0)
 def test_missing_uniform_and_tie(self):
  g={'type':'choice','probabilities':{'a':.5,'b':.5}};s=v.score({},g);self.assertTrue(s['ok']);self.assertEqual(s['brier'],0.)
 def test_noul_aliases(self):
  g={'type':'noul','probabilities':{'false':.2,'true':.8}};self.assertTrue(v.score({'no':.2,'yes':.8},g)['ok'])
class ExecutionBindingTests(unittest.TestCase):
 def test_changed_config_preserves_original_terminal_hash(self):
  import tempfile
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cfg=root/'config.json';scorer=root/'scorer.py';scorer.write_text('fixture')
   config={'out':str(root),'context':m.CONTEXT,'scorer':str(scorer),'kev_code':str(root)}
   cfg.write_text(json.dumps(config));initial=m.digest(cfg)
   def changed(*args):
    cfg.write_text(json.dumps({**config,'changed':True}));return {'rows':400}
   with patch('sys.argv',['typed','--config',str(cfg),'--mode','preflight']),patch.object(m,'verify_files'),patch.object(m,'dataset',return_value=[]),patch.object(m,'preflight',side_effect=changed),patch.object(m,'SCORER_SHA',m.digest(scorer)):
    with self.assertRaisesRegex(ValueError,'Config changed during execution'):m.main()
   terminal=json.loads((root/'preflight-COMPLETE.json').read_text())
   self.assertEqual(terminal['rc'],1);self.assertEqual(terminal['config_sha256'],initial)
 def test_serving_uses_saved_probability_tie_direction(self):
  r=raw();p=pred(r)
  for q in p['probabilities']:
   ks=list(p['probabilities'][q]);p['probabilities'][q]={ks[0]:.49999999,ks[1]:.50000001}
  fn=lambda prediction,gold:tuple(v.score(prediction['probabilities'],gold)[k] for k in ['ok','kl','brier','conf'])
  serving=m.native_score([r],[p],2.,fn);raw_t1=m.native_score([r],[p],1.,fn)
  self.assertEqual(serving['original_arithmetic_raw_readout']['accuracy'],1.)
  self.assertEqual(raw_t1['original_arithmetic_raw_readout']['accuracy'],0.)
  v.same(serving,v.summaries([r],[p],2.))

class OriginalFormulaTests(unittest.TestCase):
 def test_against_original_score_one(self):
  import ast
  path=Path('/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py')
  self.assertEqual(m.digest(path),m.SCORER_SHA)
  node=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='score_one')
  namespace={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
  for g in [json.loads(raw()['gold'])['a'],{'type':'noul','probabilities':{'false':.7,'true':.3}}]:
   for p in [{},{'x':.8,'y':.2},{'no':.8,'yes':.2}]:
    actual=namespace['score_one']({'probabilities':p},g);expected=v.score(p,g)
    for a,b in zip(actual,[expected[k] for k in ['ok','kl','brier','conf']]):self.assertAlmostEqual(a,b,places=12)
if __name__=='__main__':unittest.main()
