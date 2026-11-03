import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from tools import r3_k0_current_identity as U
class CurrentK0(unittest.TestCase):
 def test_bar_matches_registered_implementation(self):
  p='/mnt/cephfs/xingchao/experiments/jev/r3_code/k0_rescore.py';spec=importlib.util.spec_from_file_location('old_bar',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  for a,b in [([[0.,-1.],[0.,0.]],[[0.,-1.],[0.,0.]]),([[0.,-1.]],[[0.,-1.002]]),([[0.,-0.0001]],[[0.0002,0.]])]:
   expected=m.compare(a,b);expected['pass_bar']=expected.pop('pass');self.assertEqual(U.strict_compare(a,b),expected)
 def test_arity_nonfinite_boolean_rejected(self):
  for v in [[[1.]],[[1.,2.,3.]],[[True,2.]],[[float('nan'),2.]],[[float('inf'),2.]]]:
   with self.assertRaises(ValueError):U.strict_compare([[1.,2.]],v)
 def test_no_missing_question(self):
  with self.assertRaises(ValueError):U.strict_compare([[1.,2.]],[])
 def test_raw_receipt_population_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'raw.jsonl';model='a'*64;src={'k':{'levels':[{'id':'a'},{'id':'b'}]}}
   def write(r):
    p.write_text(json.dumps(r)+'\n');Path(str(p)+'.receipt.json').write_text(json.dumps({'path':str(p),'sha256':U.sha(p),'committed_bytes':p.stat().st_size,'rows':1,'model_sha256':model,'scorer':{'record_grade':True}}))
   row={'k':'k','ids':['a','b'],'s':[1.,2.],'m':model[:16]};write(row);self.assertEqual(set(U.current_raw(p,src,model)),{'k'})
   for bad in [dict(row,ids=['b','a']),dict(row,s=[1.]),dict(row,k='foreign'),dict(row,m='b'*16)]:
    write(bad)
    with self.assertRaises(ValueError):U.current_raw(p,src,model)
 def test_duplicate_or_torn_input_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'x';p.write_text('{"k":"x"}\n{"k":"x"}\n')
   with self.assertRaises(ValueError):U.rows_jsonl(p,lambda r:r['k'])
   p.write_text('{"k":"x"}')
   with self.assertRaises(ValueError):U.rows_jsonl(p,lambda r:r['k'])
 def test_resume_uses_bound_rows_and_generation(self):
  with tempfile.TemporaryDirectory() as tmp:
   rows=[{'levels':[{'id':'a'},{'id':'b'}],'input':i} for i in range(3)];calls=[]
   def fn(rs):calls.append(len(rs));return [[1.,2.] for r in rs]
   c={'phase':'test','plan_sha256':'a'}
   a,_=U.score_batches(tmp,c,rows,fn,[[0,1],[2]]);b,_=U.score_batches(tmp,c,rows,fn,[[0,1],[2]])
   self.assertEqual(a,b);self.assertEqual(calls,[2,1])
   with self.assertRaises(ValueError):U.score_batches(tmp,dict(c,plan_sha256='b'),rows,fn,[[0,1],[2]])
   z=copy.deepcopy(rows);z[0]['input']=9
   with self.assertRaises(ValueError):U.score_batches(tmp,c,z,fn,[[0,1],[2]])
 def test_resume_truncated_scores_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   rows=[{'levels':[{'id':'a'},{'id':'b'}]}];c={'phase':'test'}
   U.score_batches(tmp,c,rows,lambda r:[[1.,2.]],[[0]])
   p=Path(tmp)/'0.json';j=U.read(p);j['scores']=[[1.]];p.write_text(json.dumps(j))
   with self.assertRaises(ValueError):U.score_batches(tmp,c,rows,lambda r:[],[[0]])
 def test_wrong_group_coverage_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):U.score_batches(tmp,{},[{}],lambda r:[],[[0],[0]])
 def test_cpu_reconstruction_rejects_duplicate_missing_and_wrong_generation(self):
  from tools import r3_k0_current_identity_consume as C
  with tempfile.TemporaryDirectory() as tmp:
   # Empty/missing matrix cannot be promoted by a VERIFIED label.
   d={'controls':[{'id':str(i)} for i in range(10)],'out':tmp}
   for report in [{'schema':'r3-k0-current-control-report-v1','verdict':'VERIFIED','c32':[]}, {'schema':'foreign','verdict':'VERIFIED','c32':[]}]:
    with self.assertRaises(ValueError):C.reconstruct(d,{'cells':[]},report,U)
 def test_sample_identity_and_candidate_arity(self):
  row={'levels':[{'id':'a'},{'id':'b'}]};c={'keys':[str(i) for i in range(64)],'rows':[row]*64,'stored':[[1.,2.]]*64};U.validate_cell(c)
  z=copy.deepcopy(c);z['keys'][1]=z['keys'][0]
  with self.assertRaises(ValueError):U.validate_cell(z)
  z=copy.deepcopy(c);z['stored'][4]=[1.]
  with self.assertRaises(ValueError):U.validate_cell(z)
class LifecycleRepair(unittest.TestCase):
 def test_historical_consumer_closure_is_pinned_and_tamper_rejected(self):
  from tools import r3_k0_current_identity_consume as C
  from unittest.mock import patch
  import sys,types
  with patch.dict(sys.modules,{'r3_k0_current_identity':U,'r3_k0_current_identity_consume':C}):
   from tools import r3_k0_current_identity_prepare as P
   with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/'closure').mkdir();bridge=root/'bridge';bridge.mkdir()
    for name in ['consumer.py','closure/manifest.json','R0_COMPATIBLE_SOURCES.json','source.py','bridge/consumer.py','bridge/role_validator.py']:(root/name).write_text('{}')
    inventory={'closure_manifest_sha256':U.sha(root/'closure/manifest.json'),'files':[{'snapshot':str(root/'source.py'),'sha256':U.sha(root/'source.py')}]};U.put(root/'SOURCE_PINS.json',inventory)
    legacy=types.SimpleNamespace(SOURCE_PINS_SHA256=U.sha(root/'SOURCE_PINS.json'),R0_SOURCES_SHA256=U.sha(root/'R0_COMPATIBLE_SOURCES.json'))
    q=types.SimpleNamespace(LEGACY=root,LEGACY_SHA=U.sha(root/'consumer.py'),legacy=lambda:legacy,BRIDGE=bridge/'consumer.py',BRIDGE_SHA=U.sha(bridge/'consumer.py'),ROLE_SHA=U.sha(bridge/'role_validator.py'))
    config=root/'config.json';U.put(config,{'qualifier':{}});files={}
    with patch.object(C,'load',return_value=q):
     P.qualification_sources(config,files);self.assertEqual(len(files),7);self.assertIn(str(root/'source.py'),files)
     (root/'source.py').write_text('changed')
     with self.assertRaises(ValueError):P.qualification_sources(config,{})
     (root/'source.py').unlink()
     with self.assertRaises(FileNotFoundError):P.qualification_sources(config,{})
 def fixture(self,root):
  from tools import r3_k0_current_identity_host as H
  h=root/'host_attempts/1';a=root/'attempts/1';h.mkdir(parents=True);a.mkdir(parents=True)
  d={'out':str(root),'run':'run','chip':0,'container':'fixture','host':{},'environment':{},'mounts':[],'image_sha256':'sha256:x','runtime':{'path':'/runner'}};pin='a'*64;cid='b'*64
  claim={'run':'run','chip':0};U.put(h/'CLAIM.json',claim)
  docs={'RELEASE.json':{'run':'run','chip':0,'schema':'r3-resource-release-v1','container_id':cid,'container':'fixture-a1','exit_code':0,'scientific_acceptance':False,'claim_sha256':U.sha(h/'CLAIM.json')},'EXIT.json':{'exit_code':0,'container_exit_code':0,'container_id':cid,'runner_terminal_matches':True,'scientific_acceptance':False}}
  cmd=H.command(d,root.parent/'HOST-PLAN.json',pin,1)
  docs['LAUNCH_SPEC.json']={'command':cmd,'plan_sha256':pin};docs['LAUNCH_RECEIPT.json']={'command':cmd[cmd.index('sha256:x')+1:],'container_id':cid,'plan_sha256':pin}
  for n,v in docs.items():U.put(h/n,v)
  U.put(a/'EXIT.json',{'exit_code':0,'plan_sha256':pin,'attempt':1,'scientific_acceptance':False})
  return d,pin,H
 def test_separate_lifecycle_attacks(self):
  from tools import r3_k0_current_identity_consume as C
  from unittest.mock import patch
  attacks=[('host','container_exit_code',1),('host','container_exit_code',False),('host','scientific_acceptance',True),('runtime','scientific_acceptance',True),('release','scientific_acceptance',True),('release','schema','foreign'),('claim','chip',False),('release','chip',False),('release','exit_code',1),('runtime','attempt',True),('spec','command',['wrong']),('receipt','command',['wrong']),('release','container','wrong'),('host','container_id','wrong')]
  for kind,key,value in attacks:
   with self.subTest(kind=kind,key=key),tempfile.TemporaryDirectory() as td:
    root=Path(td)/'output';d,pin,H=self.fixture(root);paths={'host':root/'host_attempts/1/EXIT.json','runtime':root/'attempts/1/EXIT.json','release':root/'host_attempts/1/RELEASE.json','claim':root/'host_attempts/1/CLAIM.json','spec':root/'host_attempts/1/LAUNCH_SPEC.json','receipt':root/'host_attempts/1/LAUNCH_RECEIPT.json'}
    with patch.object(C,'load',return_value=H):C.lifecycle(d,pin,1)
    p=paths[kind];doc=U.read(p);doc[key]=value;p.write_text(json.dumps(doc))
    if kind=='claim':p=paths['release'];doc=U.read(p);doc['claim_sha256']=U.sha(paths['claim']);p.write_text(json.dumps(doc))
    with patch.object(C,'load',return_value=H),self.assertRaises(ValueError):C.lifecycle(d,pin,1)
 def test_cpu_device_free_and_inputs_readonly(self):
  from tools import r3_k0_current_identity_host as H
  d={'container':'x','environment':{},'mounts':[{'source':'/input','destination':'/input','readonly':True},{'source':'/output','destination':'/output','readonly':False}],'out':'/output','image_sha256':'sha256:x','consumer':{'path':'/consumer'}}
  c=H.cpu_command(d,'/p','hash',1);self.assertNotIn('--device',c);self.assertNotIn('--privileged',c)
  mounts=[c[i+1] for i,v in enumerate(c) if v=='--mount'];self.assertEqual([x for x in mounts if not x.endswith('readonly')],['type=bind,src=/output/cpu,dst=/output/cpu'])
 def test_record_grade_and_model_checks(self):
  from tools import r3_k0_current_identity_consume as C
  d={'targets':{'base':{'model':{'path':'/model'}}}};z={'scorer':'scorer_r3.R3Scorer','mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,'score_chunk_questions':32,'dedup':True,'render':'record_name','model_path':'/model','adapter':None,'record_grade':True,'record_grade_problems':[]}
  C.record_grade(d,{'weights':'base','describe':z})
  for k,v in [('model_path','/foreign'),('record_grade',False),('hf32',True),('score_chunk_questions',True),('token_budget',32),('adapter','/adapter')]:
   with self.subTest(k=k),self.assertRaises(ValueError):C.record_grade(d,{'weights':'base','describe':dict(z,**{k:v})})

if __name__=='__main__':unittest.main()
