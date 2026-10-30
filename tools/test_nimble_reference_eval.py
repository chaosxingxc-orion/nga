import importlib.util, pathlib, types, unittest, sys
sys.path.insert(0,"/mnt/cephfs/xingchao/omni/repos/jev/bespokelabsai__nimble")
p=pathlib.Path(__file__).with_name('nimble_reference_eval.py');s=importlib.util.spec_from_file_location('eval',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def fixture(self):
  row={'id':'x','reference':{'target':True},'input':{'questions':{'decision':{'type':'noul'}}},'domain':'fixture','family':'a'};p=types.SimpleNamespace(candidate_ids=[[1,2]],full_ids=[[10,20]],choices=[[False,True]])
  field={'value':False,'candidate_token_ids':[1,2],'prompt_token_sha256':m.identity_tokens([10,20]),'logits':{'false':0.,'true':0.},'scores':{'false':.5,'true':.5}}
  from nimble.evaluation.evaluate_pilot import assess
  v={'identity':'fixed','id':'x','input_sha256':m.identity(row),'result':{'id':'x','type':'noul','domain':'fixture','family':'a','split':'test','reference':row['reference'],'student':assess({'false':.5,'true':.5},True,'noul'),'raw_student':{'temperature':1.,'output':{'decision':False},'fields':{'decision':field}}}}
  return row,p,v
 def check(self,v,row,p):return m.verify_receipt({'payload':v,'sha256':m.identity(v)},row,'fixed',p)
 def test_valid(self):r,p,v=self.fixture();self.check(v,r,p)
 def test_wrong_probability_even_rehashed(self):
  r,p,v=self.fixture();v['result']['raw_student']['fields']['decision']['scores']={'false':.3,'true':.7}
  with self.assertRaisesRegex(ValueError,'Probability'):self.check(v,r,p)
 def test_wrong_candidate_order(self):
  r,p,v=self.fixture();v['result']['raw_student']['fields']['decision']['candidate_token_ids']=[2,1]
  with self.assertRaisesRegex(ValueError,'Candidate'):self.check(v,r,p)
 def test_wrong_input(self):
  r,p,v=self.fixture();r['id']='other'
  with self.assertRaisesRegex(ValueError,'identity'):self.check(v,r,p)
 def test_prompt_changed(self):
  r,p,v=self.fixture();p.full_ids=[[30,40]]
  with self.assertRaisesRegex(ValueError,'Prompt'):self.check(v,r,p)
 def test_key_order_even_with_same_numeric_values(self):
  r,p,v=self.fixture();v['result']['raw_student']['fields']['decision']['logits']={'true':0.,'false':0.}
  with self.assertRaisesRegex(ValueError,'key order'):self.check(v,r,p)
 def test_index_binding(self):
  r,p,v=self.fixture();v['index']=2
  with self.assertRaisesRegex(ValueError,'index'):m.verify_receipt({'payload':v,'sha256':m.identity(v)},r,'fixed',p,1)
 def test_forged_student_metrics(self):
  from nimble.evaluation.evaluate_pilot import assess
  r,p,v=self.fixture();r.update(reference={'target':True},input={'questions':{'decision':{'type':'noul'}}},domain='fixture',family='a')
  v['input_sha256']=m.identity(r);result=v['result'];result.update(reference=r['reference'],id='x',type='noul',domain='fixture',family='a',student=assess({'false':.5,'true':.5},True,'noul'))
  self.check(v,r,p)
  result['student']['correct']=True
  with self.assertRaisesRegex(ValueError,'student'):self.check(v,r,p)
 def test_wrong_typed_choice(self):
  r,p,v=self.fixture();v['result']['raw_student']['fields']['decision']['value']=True
  with self.assertRaisesRegex(ValueError,'choice'):self.check(v,r,p)
 def test_wrong_output(self):
  r,p,v=self.fixture();v['result']['raw_student']['output']['decision']=True
  with self.assertRaisesRegex(ValueError,'choice'):self.check(v,r,p)
 def test_wrong_temperature(self):
  r,p,v=self.fixture();v['result']['raw_student']['temperature']=2.
  with self.assertRaisesRegex(ValueError,'temperature'):self.check(v,r,p)
 def test_wrong_split(self):
  r,p,v=self.fixture();v['result']['split']='dev'
  with self.assertRaisesRegex(ValueError,'input'):self.check(v,r,p)
if __name__=='__main__':unittest.main()
