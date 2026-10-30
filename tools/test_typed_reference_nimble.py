import copy,importlib.util,json,unittest
from pathlib import Path
from types import SimpleNamespace
s=importlib.util.spec_from_file_location('adapter',Path(__file__).with_name('typed_reference_nimble.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def row():
 return {'id':'fixture','state':json.dumps({'x':['中文',1]}),'questions':json.dumps({'a':{'type':'choice','instructions':'Choose','criteria':{'one':None,'two':''}},'b':{'type':'noul','instructions':'Boolean?'},'c':{'type':'score','instructions':'Level?','criteria':['low','high']},'d':{'type':'choice','instructions':'Extra','criteria':{'x':'defined','y':'other'}},'e':{'type':'noul','instructions':'Flag?','criteria':{'false':'No','true':'Yes'}}}),'gold':'SECRET'}
class AdapterTests(unittest.TestCase):
 def test_full_schema_and_null(self):
  context,schema=m.model_input(row());self.assertEqual(len(schema),5);self.assertEqual(schema['a']['choices'],['one','two']);self.assertNotIn('one',schema['a']['choice_descriptions']);self.assertEqual(schema['b']['choices'],[False,True]);self.assertEqual(schema['c']['choices'],['0','1']);self.assertNotIn('SECRET',context+json.dumps(schema))
 def test_gold_invariance(self):
  r=row();a=m.model_input(r);r.update(gold='OTHER',factors='LEAK',id='different');self.assertEqual(a,m.model_input(r))
 def test_candidate_discrimination(self):
  r=row();a=m.model_input(r);q=json.loads(r['questions']);q['a']['criteria']={'two':'','one':None};r['questions']=json.dumps(q);self.assertNotEqual(a,m.model_input(r))
 def test_v1_limit(self):
  r=row();q=json.loads(r['questions']);q['a']['criteria']={str(i):str(i) for i in range(26)};r['questions']=json.dumps(q);m.model_input(r);q['a']['criteria']['26']='26';r['questions']=json.dumps(q)
  with self.assertRaisesRegex(ValueError,'26'):m.model_input(r)
 def test_invalid_description(self):
  r=row();q=json.loads(r['questions']);q['a']['criteria']['one']={'nested':'unsupported'};r['questions']=json.dumps(q)
  with self.assertRaisesRegex(ValueError,'definition'):m.model_input(r)
 def test_receipt_wrong_field_order(self):
  r=row();_,schema=m.model_input(r);p=SimpleNamespace(names=list(schema),choices=[s['choices'] for s in schema.values()],full_ids=[[1,2]]*5,candidate_ids=[[3,4]]*5);x=m.prepared_receipt(r,0,p);self.assertEqual(len(x['fields']),5);p.names=list(reversed(p.names))
  with self.assertRaisesRegex(ValueError,'field order'):m.prepared_receipt(r,0,p)
 def test_missing_field_not_silently_zipped(self):
  r=row();_,schema=m.model_input(r);p=SimpleNamespace(names=list(schema),choices=[s['choices'] for s in schema.values()],full_ids=[[1,2]]*4,candidate_ids=[[3,4]]*5)
  with self.assertRaisesRegex(ValueError,'field count'):m.prepared_receipt(r,0,p)
if __name__=='__main__':unittest.main()
