import importlib.util,json,unittest
from pathlib import Path

def load(n):
 s=importlib.util.spec_from_file_location(n,Path(__file__).with_name(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
N=load('explicit_noul_protocol_v1');O=load('bev_native_protocol')
def row(spec):return {'state':'{"evidence":"input"}','questions_json':json.dumps({'id':spec})}
def q(label=True,criteria=None):return dict(type='noul',instructions='Evidence supports claim?',criteria=criteria,label=label)
class Tests(unittest.TestCase):
 def test_both_definitions_and_label_semantics(self):
  d={'true':'Explicit supported','false':'Explicit contradicted'}
  a,b=[N.bev_items([row(q(label,d))])[0] for label in (True,False)]
  self.assertEqual((a['y'],b['y']),(0,1));self.assertEqual(a['options'],['Yes','No'])
  self.assertIn(json.dumps(d,separators=(',',':')),a['question']);self.assertEqual(N.request_hash(a),N.request_hash(b))
 def test_definition_change_binds_request(self):
  a=N.bev_items([row(q(True,{'true':'supported','false':'refuted'}))])[0]
  b=N.bev_items([row(q(True,{'true':'supported','false':'unknown'}))])[0]
  self.assertNotEqual(N.request_hash(a),N.request_hash(b))
 def test_malformed_no_silent_coercion(self):
  for d in ({},{'true':'yes'},{'true':'yes','false':9},{'true':'','false':'no'}):self.assertEqual(N.bev_items([row(q(True,d))]),[])
  self.assertEqual(N.bev_items([row(q(1,None))]),[])
 def test_bare_and_other_kinds_unchanged(self):
  for spec in (q(),dict(type='choice',instructions='Choose',criteria={'x':'a','y':'b'},label='x'),dict(type='score',instructions='Rate',criteria=['a','b'],label=1)):
   self.assertEqual(N.bev_items([row(spec)]),O.bev_items([row(spec)]))
 def test_frozen_contract_not_old_protocol(self):
  a=N.bev_items([row(q())]);kw=dict(source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64)
  self.assertNotEqual(N.make_contract(a,**kw),O.make_contract(a,**kw))
if __name__=='__main__':unittest.main()
