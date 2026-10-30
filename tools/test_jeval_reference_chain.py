"""Full 11,257-row synthetic chain; not a model or native tokenizer test."""
import copy,importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import jeval_reference_inference as d
import verify_jeval_reference_inference as v
class Chain(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.r=Path(cls.tmp.name);cls.rows=[];items=[];elig=[]
  for i in range(11257):
   kind='choice' if i<9582 else 'noul' if i<10938 else 'score';q={'type':kind,'instructions':'Choose'}
   if kind!='noul':q['criteria']={'a':'low','b':'high'} if kind=='choice' else ['low','high']
   raw={'id':str(i),'state':'unchanged','questions_json':json.dumps({'q':q}),'label_json':json.dumps('a' if kind=='choice' else 0)};cls.rows.append(raw);ks=['a','b'] if kind=='choice' else ['false','true'] if kind=='noul' else ['0','1']
   a={'type':kind}
   if kind=='noul':a['noul']=.5
   elif kind=='choice':a.update(choice='a',confidence=0.,probabilities=dict(zip(ks,[.5,.5])))
   else:a.update(score=.5,confidence=0.,probabilities=dict(zip(ks,[.5,.5])),legend=dict(zip(ks,q['criteria'])))
   e={'index':i,'id':str(i),'input_sha256':d.stamp(raw),'request_sha256':d.stamp(d.request(raw)),'status':'eligible','reason':'within_native_budget','max_tokens':2,'token_sha256':'tokens','candidate_count':2};elig.append(e)
   items.append({'index':i,'id':str(i),'input_sha256':d.stamp(raw),'request_sha256':d.stamp(d.request(raw)),'eligibility':{k:e[k] for k in ['status','reason','max_tokens','token_sha256','candidate_count']},'status':'valid','answer':a,'native_probabilities':dict(zip(ks,[.5,.5])),'logits':[0.,0.],'logits_temperature':'already_scaled','seconds':.1,'consumed_token_sha256':'tokens'})
  cls.items=items;cls.elig=elig
  for n in ['data','preregistration','base','code','checkpoint']:
   p=cls.r/n
   if n in ['base','code','checkpoint']:p.mkdir();(p/'native.py').write_text('frozen')
   else:p.write_text('frozen')
  cls.scripts=['jeval_reference_inference.py','jeval_reference_preflight.py','verify_jeval_reference_inference.py','prepare_jeval_reference_inference.py','jeval_reference_finish.py','test_jeval_reference_inference.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh']
  for n in cls.scripts:(cls.r/n).write_text('frozen')
  native={str(p):v.sha(p) for role in ['base','code','checkpoint'] for p in (cls.r/role).iterdir()};ec={role:str(cls.r/role) for role in ['base','code','checkpoint']};ec.update(files=native);(cls.r/'eligibility_config').write_text(json.dumps(ec));(cls.r/'eligibility_report').write_text(json.dumps({'config_sha256':v.sha(cls.r/'eligibility_config'),'items':elig}))
  c={k:str(cls.r/k) for k in ['data','preregistration','base','code','checkpoint','eligibility_config','eligibility_report']};c.update(out=str(cls.r),mode='inference',family='kev',image='immutable',temperature=2.,files={**native,**{str(cls.r/n):v.sha(cls.r/n) for n in cls.scripts+['data','preregistration','eligibility_config','eligibility_report']}});probes=[]
  for kind in ['choice','noul','score']:
   q={'type':kind,'instructions':'Choose the appropriate synthetic level.'}
   if kind!='noul':q['criteria']={'a':'first','b':'second'} if kind=='choice' else ['low','middle','high']
   probes.append({'request':{'state':'Synthetic observation: choose the first level.','questions':{'q':q}},'passes':[{'seconds':.1,'prediction':{'native_probabilities':{'a':.5,'b':.5}}} for _ in range(2)]})
  probes.append({'boundary_index':0,'input_sha256':d.stamp(cls.rows[0]),'max_tokens':2,'chips':1,'reserved_gib':1.,'passes':copy.deepcopy(probes[0]['passes'])});(cls.r/'PROBE.json').write_text(json.dumps(probes));probe=cls.r/'probe';probe.mkdir();(probe/'PROBE.json').write_text(json.dumps(probes));(probe/'config.json').write_text(json.dumps({'out':str(probe)}));(probe/'COMPLETE.json').write_text(json.dumps({'rc':0,'stage':'probe_completed','config_sha256':v.sha(probe/'config.json'),'outputs':{'PROBE.json':v.sha(probe/'PROBE.json')}}));(probe/'PROBE_REVIEW.json').write_text(json.dumps({'approved_probe_config_sha256':v.sha(probe/'config.json'),'approved_probe_sha256':v.sha(probe/'PROBE.json')}))
  c.update(probe_config=str(probe/'config.json'),probe_report=str(probe/'PROBE.json'),probe_review=str(probe/'PROBE_REVIEW.json'));c['files'].update({str(probe/n):v.sha(probe/n) for n in ['config.json','PROBE.json','PROBE_REVIEW.json']});cls.cp=cls.r/'config.json';cls.cp.write_text(json.dumps(c));ch=v.sha(cls.cp);folder=cls.r/'records';folder.mkdir()
  for i,item in enumerate(items):item['config_sha256']=ch;(folder/f'{i:06d}.json').write_text(json.dumps({'payload':item,'sha256':d.stamp(item)}))
  report=d.summarize(cls.rows,items);report['config_sha256']=ch;(cls.r/'report.json').write_text(json.dumps(report));cls.terminal={'rc':0,'stage':'completed','progress':11257,'total':11257,'config_sha256':ch,'outputs':{'report.json':v.sha(cls.r/'report.json'),'PROBE.json':v.sha(cls.r/'PROBE.json')}};(cls.r/'COMPLETE.json').write_text(json.dumps(cls.terminal));(cls.r/'EXIT').write_text('rc=0 utc=2026-10-30T19:00:00Z\n');(cls.r/'LAUNCH_RECEIPT.json').write_text(json.dumps({'config_sha256':ch,'command':['bash',str(cls.r/'run.sh')],'image':'immutable','wrapper_sha256':v.sha(cls.r/'run.sh')}))
  cls.pa=types.ModuleType('pyarrow');cls.pq=types.ModuleType('pyarrow.parquet');cls.pq.read_table=lambda _:types.SimpleNamespace(to_pylist=lambda:cls.rows)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def execute(self):
  with patch.dict(sys.modules,{'pyarrow':self.pa,'pyarrow.parquet':self.pq}),patch.object(v,'DATA_SHA',v.sha(self.r/'data')),patch.object(v,'checkpoint_binding'):return v.check(self.cp)
 def test_full_population_and_metric_chain(self):
  result=self.execute();self.assertEqual(result['rows'],11257);self.assertEqual(result['classification']['total'],10938);self.assertEqual(result['score']['valid'],319);self.assertEqual(result['classification']['correct'],9582)
 def test_missing_receipt_rejected(self):
  p=self.r/'records/000000.json';b=p.read_bytes();p.unlink()
  try:
   with self.assertRaisesRegex(ValueError,'Receipt coverage'):self.execute()
  finally:p.write_bytes(b)
 def test_false_consumed_tokens_rejected(self):
  p=self.r/'records/000000.json';b=p.read_bytes();e=json.loads(b);e['payload']['consumed_token_sha256']='wrong';e['sha256']=d.stamp(e['payload']);p.write_text(json.dumps(e))
  try:
   with self.assertRaisesRegex(ValueError,'Consumed tokens'):self.execute()
  finally:p.write_bytes(b)
 def test_wrong_returned_score_rejected_even_with_matching_receipt_hash(self):
  p=self.r/'records/010938.json';b=p.read_bytes();e=json.loads(b);e['payload']['answer']['score']=0.;e['sha256']=d.stamp(e['payload']);p.write_text(json.dumps(e))
  try:
   with self.assertRaisesRegex(ValueError,'Returned score'):self.execute()
  finally:p.write_bytes(b)
 def test_missing_required_probe_output_rejected(self):
  p=self.r/'COMPLETE.json';b=p.read_bytes();st=p.stat();t=json.loads(b);t['outputs'].pop('PROBE.json');p.write_text(json.dumps(t));os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
  try:
   with self.assertRaisesRegex(ValueError,'Required terminal outputs'):self.execute()
  finally:p.write_bytes(b);os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
 def test_forged_score_legend_rejected(self):
  p=self.r/'records/010938.json';b=p.read_bytes();e=json.loads(b);e['payload']['answer']['legend']['0']='wrong';e['sha256']=d.stamp(e['payload']);p.write_text(json.dumps(e))
  try:
   with self.assertRaisesRegex(ValueError,'Score legend'):self.execute()
  finally:p.write_bytes(b)
 def test_forged_score_confidence_rejected(self):
  p=self.r/'records/010938.json';b=p.read_bytes();e=json.loads(b);e['payload']['answer']['confidence']=.8;e['sha256']=d.stamp(e['payload']);p.write_text(json.dumps(e))
  try:
   with self.assertRaisesRegex(ValueError,'Score native confidence'):self.execute()
  finally:p.write_bytes(b)
 def test_probe_negative_duration_rejected(self):
  probes=json.loads((self.r/'PROBE.json').read_text());probes[0]['passes'][0]['seconds']=-1
  with self.assertRaisesRegex(ValueError,'Probe duration'):v.validate_probe(probes,{'items':self.elig},self.rows)
 def test_wrong_boundary_rejected(self):
  probes=json.loads((self.r/'PROBE.json').read_text());probes[3]['boundary_index']=1
  with self.assertRaisesRegex(ValueError,'Boundary probe'):v.validate_probe(probes,{'items':self.elig},self.rows)
if __name__=='__main__':unittest.main()
