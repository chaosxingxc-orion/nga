import copy,importlib.util,json,sys,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('adapter',Path(__file__).with_name('typed_openjev_preflight.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
CODE='/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030_v3/code'
sys.path.insert(0,CODE)
from jev.api import compile_request,candidate_prompts
class Tokenizer:
 def apply_chat_template(self,messages,**kw):return messages[0]['content']
 def __call__(self,prompts,**kw):return {'input_ids':[[ord(c) for c in p] for p in prompts]}
class MappingTests(unittest.TestCase):
 def test_all_five_native_questions(self):
  r=m.compile_five(m.synthetic(),compile_request);self.assertEqual(len(r),5);self.assertEqual(r[0]['options'],['a','b: ']);self.assertEqual(r[1]['answer_keys'],['false','true']);self.assertEqual(r[2]['answer_keys'],['0','1','2']);self.assertEqual(r[0]['state'],{'nested':{'text':'中文','n':3}})
 def test_gold_isolation(self):
  raw=m.synthetic();a=m.encode(raw,Tokenizer(),compile_request,candidate_prompts);raw.update(gold='LEAK',factors='SECRET',id='other');self.assertEqual(a,m.encode(raw,Tokenizer(),compile_request,candidate_prompts))
 def test_order_and_content_discrimination(self):
  raw=m.synthetic();a=m.encode(raw,Tokenizer(),compile_request,candidate_prompts);q=m.request(raw)['questions'];q['route']['criteria']={'b':'','a':None};raw['questions']=json.dumps(q);self.assertNotEqual(a,m.encode(raw,Tokenizer(),compile_request,candidate_prompts));q['route']['criteria']['a']='changed';raw['questions']=json.dumps(q);self.assertNotEqual(a,m.encode(raw,Tokenizer(),compile_request,candidate_prompts))
 def test_missing_question_refused(self):
  raw=m.synthetic();q=m.request(raw)['questions'];q.pop('allow');raw['questions']=json.dumps(q)
  with self.assertRaisesRegex(ValueError,'five'):m.compile_five(raw,compile_request)
 def test_wrong_native_order_refused(self):
  with self.assertRaisesRegex(ValueError,'order/count'):m.compile_five(m.synthetic(),lambda s,q:list(reversed(compile_request(s,q))))
 def test_overflow_refused(self):
  raw=m.synthetic();raw['state']=json.dumps('x'*5000)
  with self.assertRaisesRegex(ValueError,'overflow'):m.encode(raw,Tokenizer(),compile_request,candidate_prompts)
 def test_no_adjacent_questions_invented(self):
  records=m.compile_five(m.synthetic(),compile_request);self.assertNotIn('Choose extra',candidate_prompts(records[0])[0]);self.assertEqual(len(candidate_prompts(records[1])),1)
 def test_bad_type_refused(self):
  raw=m.synthetic();q=m.request(raw)['questions'];q['route']['type']='invented';raw['questions']=json.dumps(q)
  with self.assertRaises(ValueError):m.compile_five(raw,compile_request)
if __name__=='__main__':unittest.main()
