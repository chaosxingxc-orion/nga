import importlib.util,json,pathlib,unittest,copy,subprocess,tempfile,sys
p=pathlib.Path(__file__).with_name('bev_native_protocol.py');s=importlib.util.spec_from_file_location('native',p);n=importlib.util.module_from_spec(s);s.loader.exec_module(n)

def spec(kind='choice',criteria=None,label='b'):
 return dict(type=kind,criteria=criteria if criteria is not None else {'a':'A','b':'B'},label=label,instructions='Choose')
def rows(*qs):return [dict(state='input',questions_json=json.dumps({str(i):q for i,q in enumerate(qs)}))]

class NativeTests(unittest.TestCase):
 def test_choice_uses_definition_and_order(self):
  x=n.bev_items(rows(spec()));self.assertEqual(x[0]['options'],['A','B']);self.assertEqual(x[0]['y'],1);self.assertNotIn('first_level',x[0])
 def test_noul_and_score_native_mapping(self):
  x=n.bev_items(rows(spec('noul',{},False),spec('score',['low','high'],1)));self.assertEqual(x[0]['options'],['Yes','No']);self.assertEqual(x[0]['y'],1);self.assertEqual(x[1]['y'],1);self.assertNotIn('first_level',x[1])
 def test_native_filter_and_edge_semantics(self):
  x=n.bev_items(rows(spec(criteria={'a':'same','b':'same'}),spec('score',['x','x'],True),spec('choice',{str(i):str(i) for i in range(27)},'0'),spec('noul',{},1)))
  self.assertEqual(len(x),1);self.assertIs(x[0]['y'],True)
 def test_malformed_json_skipped_nonobject_raises(self):
  self.assertEqual(n.bev_items([{'questions_json':'broken'}]),[])
  with self.assertRaises(AttributeError):n.bev_items([{'questions_json':'[]'}])
 def fixture(self):
  it=n.bev_items(rows(spec(),spec('noul',{},True),spec('score',['low','high'],0)))
  rr=[dict(i=i,qid=x['qid'],y=x['y'],index=j,first_index=k,route=route,first_margin=m,reasoning_tokens=t) for i,(x,j,k,route,m,t) in enumerate(zip(it,[1,0,1],[0,0,0],['cot','one_forward','cot'],[.49,.5,.1],[9,0,7]))]
  c=n.make_contract(it,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64);h=n.sha256_value(c)
  for item,row in zip(it,rr):row.update(contract_sha256=h,request_sha256=n.request_hash(item))
  self.contract=c;self.pin=h
  return it,rr
 def summary(self,a,b):return n.summarise(a,b,contract=self.contract,contract_sha256=self.pin)
 def test_exact_arithmetic_boundary_and_escalation(self):
  a,b=self.fixture();r=self.summary(a,b);self.assertEqual(r,dict(n=3,one_forward={'correct':2},adaptive={'correct':2,'escalated':2,'below_tau':2,'reasoning_tokens':16},escalated_decisions={'correct_before':1,'correct_after':1}))
 def test_identity_cannot_pass_by_count(self):
  a,b=self.fixture()
  for bad in [b[:-1],b[::-1],[b[0],b[0],b[2]]]:
   with self.assertRaises(ValueError):self.summary(a,bad)
 def test_bad_index_gold_and_margin_reject(self):
  a,b=self.fixture()
  for change in [{'index':True},{'index':99},{'y':0},{'first_margin':float('nan')},{'reasoning_tokens':-1}]:
   bad=[dict(x) for x in b];bad[0].update(change)
   with self.assertRaises(ValueError):self.summary(a,bad)

 def test_original_population_substitution_reproduction_rejects(self):
  a,b=self.fixture()
  for key,value in [('state','foreign'),('question','foreign'),('options',['X','Y']),('kind','score')]:
   changed=copy.deepcopy(a);changed[0][key]=value
   with self.assertRaises(ValueError):self.summary(changed,b)
 def test_options_reorder_and_foreign_contract_reject(self):
  a,b=self.fixture();changed=copy.deepcopy(a);changed[0]['options'].reverse()
  with self.assertRaises(ValueError):self.summary(changed,b)
  c=dict(self.contract,model_sha256='d'*64)
  with self.assertRaises(ValueError):n.summarise(a,b,contract=c,contract_sha256=self.pin)
  with self.assertRaises(ValueError):n.summarise(a,b,contract=c,contract_sha256=n.sha256_value(c))
 def test_prediction_binding_required(self):
  a,b=self.fixture()
  for key in ['request_sha256','contract_sha256']:
   bad=copy.deepcopy(b);bad[0].pop(key)
   with self.assertRaises(ValueError):self.summary(a,bad)
  bad=copy.deepcopy(b);bad[0]['request_sha256']=b[1]['request_sha256']
  with self.assertRaises(ValueError):self.summary(a,bad)
 def test_invalid_native_records_reject(self):
  a,b=self.fixture()
  for change in [{'route':'direct'},{'route':'made_up'},{'first_margin':-.1},{'first_margin':True},{'first_margin':float('inf')},{'i':False},{'y':True},{'route':'one_forward'},{'first_margin':.5}]:
   bad=copy.deepcopy(b);bad[0].update(change)
   with self.subTest(change=change),self.assertRaises(ValueError):self.summary(a,bad)
  bad=copy.deepcopy(b);bad[1]['reasoning_tokens']=1
  with self.assertRaises(ValueError):self.summary(a,bad)
 def test_tau_domain_no_probability_upper_bound(self):
  a,b=self.fixture()
  for tau in [True,-.1,float('inf'),float('nan'),'0.5']:
   with self.assertRaises(ValueError):n.make_contract(a,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64,tau=tau)
  b[1]['first_margin']=12;self.summary(a,b)
  self.assertEqual(n.make_contract(a,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64,tau=2)['tau'],2)
 def test_bool_mapper_compatibility_not_strict_gold(self):
  a=n.bev_items(rows(spec('score',['x','y'],True)))
  self.assertIs(a[0]['y'],True)
  with self.assertRaises(ValueError):n.make_contract(a,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64)
 def test_duplicate_requests_preserved_with_unique_ordinals(self):
  a=n.bev_items(rows(spec(),spec()));c=n.make_contract(a,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64);h=n.sha256_value(c)
  b=[dict(i=x['i'],qid=x['qid'],y=x['y'],index=x['y'],first_index=x['y'],route='one_forward',first_margin=1,reasoning_tokens=0,contract_sha256=h,request_sha256=n.request_hash(x)) for x in a]
  self.assertEqual(n.summarise(a,b,contract=c,contract_sha256=h)['n'],2)
  with self.assertRaises(ValueError):n.summarise(a,[b[0],b[0]],contract=c,contract_sha256=h)
 def test_contract_field_type_confusion_reject(self):
  a,b=self.fixture()
  for count in [3.0,True]:
   c=dict(self.contract,count=count)
   with self.assertRaises(ValueError):n.summarise(a,b,contract=c,contract_sha256=n.sha256_value(c))
 def test_cli_requires_pin_and_exclusive_output(self):
  a,b=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td)
   for name,value in [('items',a),('predictions',b),('contract',self.contract)]: (root/name).write_text(json.dumps(value))
   cmd=[sys.executable,str(p),'--items',str(root/'items'),'--predictions',str(root/'predictions'),'--contract',str(root/'contract'),'--contract-sha256',self.pin,'--output',str(root/'report')]
   run=subprocess.run(cmd,capture_output=True);self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual(json.loads((root/'report').read_text())['n'],3)
   self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
