"""CPU-only protocol counterexamples; timing uses a fake clock, never performance claims."""
import copy,importlib.util,math,types,unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).with_name('bev_native_matched_perf_v1.py');s=importlib.util.spec_from_file_location('M',p);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)

def source(i=0,kind='choice'):
 n=2;keys=['true','false'] if kind=='noul' else [str(x) for x in range(n)];defs=['True','False'] if kind=='noul' else ['low','high']
 return {'id':str(i),'request':{'input':'state'+str(i),'type':kind,'level_type':{'choice':'nominal','noul':'boolean','score':'ordinal'}[kind],'candidate_set':'exclusive','question':'Q?','candidate_keys':keys,'definitions':defs}}
def bridge(r):
 if set(r)!={'input','type','level_type','candidate_set','question','candidate_keys','definitions'}:raise ValueError('gold')
def row(i,kind='choice'):
 r=source(i,kind);return {'schema':'bev-native-input-v1','i':i,'qid':str(i),'request_sha256':'r'+str(i),'input_ids':[1,2],'rendered_prompt':'text','labels':['0','1'] if kind=='score' else ['A','B'],'label_ids':[16,17],'options':['Yes','No'] if kind=='noul' else ['low','high'],'kind':kind}
class ContractTests(unittest.TestCase):
 def test_fixed_population_mapping(self):
  b=types.SimpleNamespace(to_r3_row=bridge)
  for kind in ('choice','noul','score'):
   x=M.map_request(source(2,kind),2,b);self.assertEqual(x['qid'],'2');self.assertEqual(x['i'],2)
   self.assertEqual(x['kind'],'yes_no' if kind=='noul' else kind);self.assertNotIn('y',x)
   if kind=='score':self.assertEqual(x['first_level'],0)
   if kind=='noul':self.assertEqual(x['options'],['Yes','No'])
 def test_gold_foreign_envelope_and_ordinal_rejected(self):
  b=types.SimpleNamespace(to_r3_row=bridge);x=source();x['gold']=0
  with self.assertRaises(ValueError):M.map_request(x,0,b)
  x=source();x['request']['y']=0
  with self.assertRaises(ValueError):M.map_request(x,0,b)
  with self.assertRaises(ValueError):M.map_request(source(),True,b)
 def test_schedule_pair_order_and_exact_population(self):
  ss=M.schedule(6516);self.assertEqual([x['arm'] for x in ss],['reference','adapter_sequential','adapter_sequential','reference'])
  self.assertEqual(ss[1]['ranges'],[[0,3258],[3258,6516]])
  for x in ss:self.assertEqual([i for lo,hi in x['ranges'] for i in range(lo,hi)],list(range(6516)))
  for n in [72,6515,6517,True]:
   with self.assertRaises(ValueError):M.schedule(n)
 def test_population_rejects_reorder_drop_gold_candidate_change(self):
  rows=[row(i) for i in range(6516)];sources=[source(i) for i in range(6516)];n=types.SimpleNamespace(digest=M.digest);p=M.validate_population(rows,sources,n);self.assertEqual(p['count'],6516);self.assertEqual(len(p['ordered_input_sha256']),6516)
  changes=[lambda xs:xs.reverse(),lambda xs:xs.pop(),lambda xs:xs[0].update(y=0),lambda xs:xs[0]['options'].reverse(),lambda xs:xs[0].update(i=True),lambda xs:xs[0].update(input_ids=[1]*4097)]
  for change in changes:
   bad=copy.deepcopy(rows);change(bad)
   with self.subTest(change=change),self.assertRaises(ValueError):M.validate_population(bad,sources,n)
 def test_warmup_uses_length_then_ordinal_only(self):
  rows=[row(i) for i in range(6516)];self.assertEqual(M.warmup_indices(rows),[0,3257,6515]);rows[-1]['input_ids']=[1]*3;self.assertEqual(M.warmup_indices(rows)[-1],6515)
 def fixture(self):
  rows=[row(i) for i in range(6516)];pop={'ordered_inputs_sha256':M.digest(rows),'ordered_input_sha256':[M.digest(x) for x in rows],'total_input_tokens':13032};trials=[]
  for trial in M.schedule(6516):
   wall=2*6516;compute=6516;persist=0
   trials.append(dict(trial,items=6516,tokens=13032,chips=1,compute_seconds=compute,persist_seconds=persist,wall_seconds=wall,items_per_second_per_chip=.5,tokens_per_second_per_chip=1.,chip_hours=wall/3600,reused_items=0,peak_allocated_bytes=100,peak_reserved_bytes=200,observations=[{'ordinal':i,'input_sha256':pop['ordered_input_sha256'][i],'collect_seconds':1.,'persist_seconds':0.,'persisted':{}} for i in range(6516)]))
  receipt={'verdict':'PASS','population_sha256':pop['ordered_inputs_sha256'],'full_operand_comparisons':19548,'zero_tolerance':True};return trials,pop,receipt
 def test_summary_requires_full_equality_and_four_trials(self):
  t,p,r=self.fixture();result=M.summarize(t,p,r);self.assertEqual(result['pooled_wall_reference_over_adapter_sequential'],1);self.assertFalse(result['production_speedup_acceptance']);self.assertFalse(result['statistical_significance_claim'])
  for key,value in [('verdict','PENDING'),('population_sha256','x'),('full_operand_comparisons',True),('zero_tolerance',False)]:
   rr=dict(r,**{key:value})
   with self.assertRaises(ValueError):M.summarize(t,p,rr)
  with self.assertRaises(ValueError):M.summarize(t[:3],p,r)
 def test_reused_wrong_rate_time_token_or_memory_rejected(self):
  t,p,r=self.fixture()
  for key,value in [('reused_items',1),('reused_items',False),('tokens',13031),('chips',True),('wall_seconds',0),('wall_seconds',math.nan),('compute_seconds',7000),('items_per_second_per_chip',1),('chip_hours',1),('peak_allocated_bytes',201)]:
   bad=copy.deepcopy(t);bad[0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):M.summarize(bad,p,r)
 def test_missing_or_duplicate_observation_rejected(self):
  t,p,r=self.fixture()
  for change in (lambda x:x.pop(),lambda x:x.reverse(),lambda x:x[0].update(ordinal=True),lambda x:x[0].update(input_sha256='x'),lambda x:x[0].update(collect_seconds=-1)):
   bad=copy.deepcopy(t);change(bad[0]['observations'])
   with self.assertRaises(ValueError):M.summarize(bad,p,r)
 def test_timing_separates_collect_and_persist_with_sync(self):
  # Short shape is injected only for unit mechanics; production insists6516.
  rows=[row(i) for i in range(4)];trial={'trial':0,'pair':0,'arm':'reference','ranges':[[0,4]],'count':4};ticks=iter(range(100));sync=[];calls=[];progress=[]
  with patch.object(M,'schedule',return_value=[trial]),patch.object(M,'full'):
   out=M.measure_trial(trial,rows,lambda arm,item:(calls.append(item['i']) or {},{}),lambda *a:{'fixture':True},lambda:sync.append(True),lambda:{'peak_allocated_bytes':10,'peak_reserved_bytes':20},lambda:None,lambda *a:progress.append(a),clock=lambda:float(next(ticks)))
  self.assertEqual(calls,list(range(4)));self.assertEqual(out['compute_seconds'],4);self.assertEqual(out['persist_seconds'],4);self.assertEqual(len(sync),10);self.assertEqual(progress[-1][0],4)
 def test_measurement_rejects_scope_mutation_before_collect(self):
  rows=[row(i) for i in range(6516)];trial=M.schedule(6516)[0];trial['ranges']=[[0,6515]]
  with self.assertRaises(ValueError):M.measure_trial(trial,rows,lambda *a:self.fail('unexpected collect'),None,None,None,None,None)
 def test_failed_fresh_experiment_terminal_and_no_resume(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'plan.json';p.write_text('{}');rows=[row(i) for i in range(6516)];root=Path(td)/'output';calls=[]
   def fail():calls.append(True);raise RuntimeError('injected model load failure')
   with self.assertRaises(RuntimeError):M.execute_fresh(root,M.pin(p),rows,fail)
   self.assertEqual(json.loads((root/'EXIT.json').read_text())['exit_code'],1);self.assertFalse(json.loads((root/'FAILURE.json').read_text())['timing_eligible'])
   before=(root/'EXIT.json').read_bytes()
   with self.assertRaises(ValueError):M.execute_fresh(root,M.pin(p),rows,fail)
   self.assertEqual(calls,[True]);self.assertEqual((root/'EXIT.json').read_bytes(),before)
 def test_experiment_clock_load_warmup_and_trials_separate(self):
  # Backend/trial internals are synthetic; assert orchestration budget identities only.
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'plan.json';p.write_text('{}');rows=[row(i) for i in range(6516)];root=Path(td)/'output';clock=[0.];warm=[]
   def now():clock[0]+=1;return clock[0]
   backend=types.SimpleNamespace(synchronize=lambda:None,collect=lambda arm,item:(warm.append((arm,item['i'])) or {},{}),persist=lambda *a:{'fixture':True},memory=lambda:{'peak_allocated_bytes':10,'peak_reserved_bytes':20},reset_peak=lambda:None,progress=lambda *a:None)
   def trial(t,*args):
    clock[0]+=10;return dict(t,wall_seconds=10,chip_hours=10/3600,peak_allocated_bytes=10,peak_reserved_bytes=20)
   with patch.object(M,'full'),patch.object(M,'measure_trial',side_effect=trial):
    r=M.execute_fresh(root,M.pin(p),rows,lambda:backend,now)
   self.assertEqual(len(warm),6);self.assertEqual(r['warmup_forwards'],6);self.assertEqual(len(r['trials']),4);self.assertGreaterEqual(r['whole_occupied_seconds'],42);self.assertFalse(r['timing_acceptance']);self.assertEqual(json.loads((root/'EXIT.json').read_text())['exit_code'],0)
 def test_atomic_report_never_replaces(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.json';M.put(p,{'value':1});before=p.read_bytes()
   with self.assertRaises(FileExistsError):M.put(p,{'value':2})
   self.assertEqual(p.read_bytes(),before)
if __name__=='__main__':unittest.main()
