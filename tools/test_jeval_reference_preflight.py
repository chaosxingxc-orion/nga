import copy,importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('j',Path(__file__).with_name('jeval_reference_preflight.py'));j=importlib.util.module_from_spec(s);s.loader.exec_module(j)
def row(n=2):return {'id':'case','state':'{"keep":"original JSON string"}','questions_json':json.dumps({'q':{'type':'choice','instructions':'Select','criteria':{str(i):'level '+str(i) for i in range(n)}}}),'label':'0'}
class Tokenizer:
 def apply_chat_template(self,messages,**kwargs):return messages[0]['content']
 def __call__(self,text,**kwargs):return {'input_ids':list(text.encode())}
def compile_(state,qs):return [{'state':state,'id':n,'answer_keys':j.keys(q),'options':list(q['criteria'].values())} for n,q in qs.items()]
def prompts(r):return [r['state']+' '+v for v in r['options']]
class Tests(unittest.TestCase):
 def test_state_string_unchanged(self):self.assertEqual(j.request(row())['state'],row()['state'])
 def test_gold_metadata_isolation(self):
  a=row();b=copy.deepcopy(a);b.update(label='different',id='other',source='different');self.assertEqual(j.request(a),j.request(b));self.assertEqual(j.schema(j.request(a)),j.schema(j.request(b)))
 def test_candidate_order_content_discriminates(self):
  a=row();b=copy.deepcopy(a);q=json.loads(b['questions_json']);q['q']['criteria']={'1':'changed','0':'level 0'};b['questions_json']=json.dumps(q)
  self.assertNotEqual(j.check(j.request(a),'openjev',Tokenizer(),(compile_,prompts)),j.check(j.request(b),'openjev',Tokenizer(),(compile_,prompts)))
 def test_nimble_27_unsupported_before_tokenization(self):
  out=j.check(j.request(row(27)),'nimble',None,None);self.assertEqual(out['status'],'unsupported');self.assertEqual(out['candidate_count'],27)
 def test_nimble_empty_state_unsupported_without_placeholder(self):
  for state in ('',' \n'):
   a=row();a['state']=state;req=j.request(a);out=j.check(req,'nimble',None,None);self.assertEqual(out['reason'],'native_nonempty_context_required');self.assertEqual(req['state'],state)
 def test_nimble_width_precedes_empty_state(self):
  a=row(27);a['state']='';out=j.check(j.request(a),'nimble',None,None);self.assertEqual(out['reason'],'native_v1_candidate_limit_26')
 def test_openjev_overlength_preserved(self):
  a=row();a['state']='x'*5000;out=j.check(j.request(a),'openjev',Tokenizer(),(compile_,prompts));self.assertEqual(out['status'],'overlength');self.assertGreater(out['max_tokens'],4096)
 def test_native_nimble_overlength_message(self):
  def native(*a,**k):raise ValueError('Longest prompt has 3000 tokens; limit is 2048. Nothing was truncated.')
  out=j.check(j.request(row()),'nimble',None,native);self.assertEqual(out['status'],'overlength');self.assertEqual(out['max_tokens'],3000)
 def test_nimble_unrelated_error_fails(self):
  def native(*a,**k):raise ValueError('Choice code A is broken')
  with self.assertRaisesRegex(ValueError,'broken'):j.check(j.request(row()),'nimble',None,native)
 def test_empty_or_multiple_questions_fail(self):
  a=row();a['questions_json']='{}'
  with self.assertRaises(ValueError):j.request(a)
 def test_null_description_absent(self):
  a=row();q=json.loads(a['questions_json']);q['q']['criteria']['0']=None;a['questions_json']=json.dumps(q);self.assertNotIn('0',j.schema(j.request(a))['q']['choice_descriptions'])
 def test_kev_overflow_is_not_other_failure(self):
  class Overflow(ValueError):pass
  class Request:
   model_validate=staticmethod(lambda x:x)
  def encode(*a,**k):raise Overflow('branch too long')
  native=(Request,lambda r:({},[{'keys':j.keys(next(iter(r['questions'].values())))}]),encode,Overflow)
  self.assertEqual(j.check(j.request(row()),'kev',None,native)['status'],'overlength')
if __name__=='__main__':unittest.main()
