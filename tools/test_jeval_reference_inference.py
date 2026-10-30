import copy,importlib.util,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import jeval_reference_inference as m

def raw(kind='choice',label='b'):
 q={'type':kind,'instructions':'Choose'}
 if kind!='noul':q['criteria']={'a':'first','b':'second'} if kind=='choice' else ['low','middle','high']
 return {'id':'fixture','state':'{"keep":"string"}','questions_json':json.dumps({'q':q}),'label_json':json.dumps(label)}
def ans(kind='choice'):
 if kind=='noul':return {'type':'noul','noul':.5}
 if kind=='score':return {'type':'score','score':.8,'confidence':.2,'probabilities':{'0':.5,'1':.2,'2':.3},'legend':{'0':'low','1':'middle','2':'high'}}
 return {'type':'choice','choice':'b','confidence':.1,'probabilities':{'a':.8,'b':.1}}
class Tests(unittest.TestCase):
 def test_returned_choice_not_probability_argmax(self):
  r=m.summarize([raw()],[{'status':'valid','answer':ans()}]);self.assertEqual(r['classification']['accuracy'],1);self.assertAlmostEqual(r['classification']['raw_brier'],1.45);self.assertAlmostEqual(r['classification']['ece10'],.9)
 def test_raw_brier_does_not_renormalize(self):
  a=ans();a['probabilities']={'a':0.,'b':0.};r=m.summarize([raw()],[{'status':'valid','answer':a}]);self.assertEqual(r['classification']['raw_brier'],1)
 def test_missing_excluded_from_brier_but_wrong_in_accuracy(self):
  rs=[raw(),raw()];result=m.summarize(rs,[{'status':'valid','answer':ans()},{'status':'overlength'}]);self.assertEqual(result['classification']['accuracy'],.5);self.assertEqual(result['classification']['valid'],1);self.assertAlmostEqual(result['classification']['raw_brier'],1.45)
 def test_zero_valid_undefined(self):
  r=m.summarize([raw()],[{'status':'unsupported'}]);self.assertEqual(r['classification']['accuracy'],0);self.assertIsNone(r['classification']['ece10']);self.assertIsNone(r['classification']['raw_brier'])
 def test_noul_half_tie_returns_true(self):
  r=m.summarize([raw('noul',1)],[{'status':'valid','answer':ans('noul')}]);self.assertEqual(r['classification']['accuracy'],1);self.assertEqual(r['classification']['raw_brier'],.5)
 def test_score_returned_value_original_scale(self):
  r=m.summarize([raw('score',2)],[{'status':'valid','answer':ans('score')}]);self.assertAlmostEqual(r['score']['native_scale_mae'],1.2)
 def test_missing_score_excluded_not_zero(self):
  r=m.summarize([raw('score',2),raw('score',2)],[{'status':'valid','answer':ans('score')},{'status':'overlength'}]);self.assertEqual(r['score']['valid'],1);self.assertAlmostEqual(r['score']['native_scale_mae'],1.2)
 def test_extra_missing_nonfinite_and_order_rejected(self):
  _,q=m.question(raw())
  for a in [dict(ans(),extra=1),{k:v for k,v in ans().items() if k!='confidence'},dict(ans(),confidence=float('nan')),dict(ans(),probabilities={'b':.1,'a':.8})]:
   with self.assertRaises(ValueError):m.response(q,a)
 def test_gold_metadata_invariance_with_candidate_discrimination(self):
  r=raw();changed=copy.deepcopy(r);changed.update(label_json='"a"',source='foreign');self.assertEqual(m.input_record(m.request(r)),m.input_record(m.request(changed)));self.assertEqual(m.request(r)['state'],r['state'])
  q=json.loads(changed['questions_json']);q['q']['criteria']={'b':'second','a':'first'};changed['questions_json']=json.dumps(q);self.assertNotEqual(m.stamp(m.input_record(m.request(r))),m.stamp(m.input_record(m.request(changed))))
 def test_input_record_does_not_mutate_request(self):
  req=m.request(raw());before=copy.deepcopy(req);m.input_record(req);self.assertEqual(req,before)
 def test_score_gold_range_rejected(self):
  with self.assertRaises(ValueError):m.gold(raw('score',4))
 def test_boundary_bin_local_convention(self):
  a=ans();a.update(confidence=.1,choice='b');b=ans();b.update(confidence=.099999,choice='a');r=m.summarize([raw(),raw()],[{'status':'valid','answer':a},{'status':'valid','answer':b}]);self.assertAlmostEqual(r['classification']['ece10'],(.9+.099999)/2)
class FinisherPreservation(unittest.TestCase):
 def test_existing_terminal_not_overwritten(self):
  import tempfile
  from pathlib import Path
  import jeval_reference_finish as f
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);run=root/'run';run.mkdir();out=root/'run_finish';out.mkdir();cp=run/'config.json';cp.write_text(json.dumps({'out':str(run),'files':{}}));terminal=out/'COMPLETE.json';terminal.write_text('preserved')
   with self.assertRaisesRegex(ValueError,'Existing finisher'):f.main(cp)
   self.assertEqual(terminal.read_text(),'preserved')
 def test_changed_frozen_dependency_rejected_before_docker(self):
  import tempfile
  from pathlib import Path
  import jeval_reference_finish as f
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);run=root/'run';run.mkdir();(root/'run_finish').mkdir();dep=root/'native.py';dep.write_text('changed');cp=run/'config.json';cp.write_text(json.dumps({'out':str(run),'files':{str(dep):'wrong'}}))
   with self.assertRaisesRegex(ValueError,'Frozen finisher dependency'):f.main(cp)
if __name__=='__main__':unittest.main()
