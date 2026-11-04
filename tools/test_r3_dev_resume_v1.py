"""Focused safety checks for immutable DEV-prefix recovery."""
import copy,hashlib,json,tempfile,types,unittest
from pathlib import Path
SRC=Path(__file__).with_name('r3_dev_resume_launcher_v1.py')
M=types.ModuleType('resume_test');exec(compile(SRC.read_text().split('\nbase=')[0],str(SRC),'exec'),M.__dict__)
class Recovery(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)/'new';self.out.mkdir();self.old=Path(self.tmp.name)/'old'
  self.data=self.out/'imported/trackk/d__dev/clean.jsonl';self.data.parent.mkdir(parents=True);self.receipt=Path(str(self.data)+'.receipt.json')
  self.row={'k':'a','ids':['yes','no'],'s':[-1.,-2.],'argmax':0,'tie':False,'m':'a'*16}
  self.meta={'k':'a','ids':['yes','no']};self.write(self.data,self.row,line=True)
  self.r={'path':str(self.old/'results/trackk/d__dev/clean.jsonl'),'committed_bytes':self.data.stat().st_size,'sha256':M.sha(self.data),'rows':1,'model_sha256':'a'*64,'scorer':{'mode':'fp32'}};self.write(self.receipt,self.r)
  self.snapshot=self.out/'SOURCE.json';self.write(self.snapshot,{'out':str(self.old)})
  self.pop=self.out/'POP.json';self.population={'schema':'r3-dev-resume-population-v1','test_read':False,'files':{'trackk/d__dev/clean.jsonl':{'a':self.meta}}};self.write(self.pop,self.population)
  source={'path':str(self.old/'execution.json'),'sha256':M.sha(self.snapshot)}
  self.m={'schema':'r3-dev-imported-prefixes-v1','source_execution':source,'source_snapshot':self.ref(self.snapshot),'population':self.ref(self.pop),'source_out':str(self.old),'target_out':str(self.out),'test_read':False,'scientific_acceptance':False,'entries':[{'relative':'trackk/d__dev/clean.jsonl','data':self.ref(self.data),'receipt':self.ref(self.receipt)}],'file_count':1,'rows':1,'model_sha256':'a'*64,'scorer':{'mode':'fp32'},'run_identity':{'model_sha256':'a'*64}}
  self.p={'out':str(self.out),'successor_guard':{'source_execution':source}};self.sync()
 def write(self,path,obj,line=False):Path(path).write_text(json.dumps(obj)+'\n')
 def ref(self,path):return {'path':str(path),'sha256':M.sha(path)}
 def sync(self):
  self.m['entries'][0]['data']=self.ref(self.data);self.m['entries'][0]['receipt']=self.ref(self.receipt);self.m['population']=self.ref(self.pop);f=self.out/'IMPORTS.json';self.write(f,self.m);self.p['resume_import']=self.ref(f)
 def rowchange(self,fn):
  fn(self.row);self.write(self.data,self.row);self.r.update(committed_bytes=self.data.stat().st_size,sha256=M.sha(self.data));self.write(self.receipt,self.r);self.sync()
 def test_relocation_only_and_no_source_mount(self):
  self.assertFalse((self.old/'execution.json').exists());M.materialize(self.p);dst=self.out/'results/trackk/d__dev/clean.jsonl';self.assertEqual(dst.read_bytes(),self.data.read_bytes());r=M.read(str(dst)+'.receipt.json');r['path']=self.r['path'];self.assertEqual(r,self.r)
 def test_refuses_existing_results(self):
  (self.out/'results').mkdir()
  with self.assertRaises(RuntimeError):M.materialize(self.p)
 def test_byte_corruption(self):
  self.data.write_text('changed')
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_wrong_score_shape(self):
  self.rowchange(lambda r:r.update(s=[1.]))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_nonfinite_score(self):
  self.rowchange(lambda r:r.update(s=[float('nan'),1.]))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_wrong_population(self):
  self.rowchange(lambda r:r.update(k='wrong'))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_wrong_stamp(self):
  self.rowchange(lambda r:r.update(m='b'*16))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_wrong_tie(self):
  self.rowchange(lambda r:r.update(tie=True))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_wrong_probability(self):
  self.rowchange(lambda r:r.update(p=[0.,1.]))
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_path_escape(self):
  self.m['entries'][0]['relative']='../escape.jsonl';self.sync()
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_receipt_model(self):
  self.r['model_sha256']='b'*64;self.write(self.receipt,self.r);self.sync()
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)
 def test_duplicate_keys(self):
  self.data.write_text((json.dumps(self.row)+'\n')*2);self.r.update(rows=2,committed_bytes=self.data.stat().st_size,sha256=M.sha(self.data));self.write(self.receipt,self.r);self.m['rows']=2;self.sync()
  with self.assertRaises(RuntimeError):M.validate_imports(self.p)

# Guard tests use pinned synthetic failed-generation evidence; Docker is read-only stubbed.
class FailedReleaseGuard(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);(root/'attempts/1').mkdir(parents=True)
  self.g=types.ModuleType('guard_test');self.g.__file__=str(Path(__file__).with_name('r3_dev_resume_successor_v1.py'));exec(compile(Path(self.g.__file__).read_text().split('\ndef configure')[0],self.g.__file__,'exec'),self.g.__dict__)
  self.source={'out':str(root),'run':'oldrun','container':'oldcontainer','chip':2};pin='planpin';container='cid';image='img'
  docs={'claim':{'run':'oldrun','chip':2},'release':{'run':'oldrun','chip':2,'exit_code':1,'scientific_acceptance':False,'container_id':container,'container_started_at':'start','container_finished_at':'finish','allocation_after':{'free':[{'chip':2,'previous_run':'oldrun','release_evidence':str(root/'attempts/1/RELEASE.json')}] }},'terminal':{'source':'retained-container-exit','runtime_terminal_present':False,'exit_code':1,'container_id':container,'raw_plan_sha256':pin},'supervisor_done':{'exit_code':1,'source':'retained-container-reconciliation','container_id':container},'receipt':{'id':container,'image':image,'sha256':pin},'spec':{'command':['docker','run',image,'-P','drive']},'supervisor':{'pid':123}}
  docs['attempt_terminal']=docs['terminal'];names={'claim':'attempts/1/CLAIM.json','release':'attempts/1/RELEASE.json','terminal':'ENGINEERING_EVAL_EXIT.json','attempt_terminal':'attempts/1/EXIT.json','supervisor_done':'attempts/1/SUPERVISOR_DONE.json','receipt':'attempts/1/LAUNCH_RECEIPT.json','spec':'attempts/1/LAUNCH_SPEC.json','supervisor':'SUPERVISOR_RECEIPT.json'}
  self.refs={};self.docs=docs
  for k,n in names.items():
   path=root/n;path.write_text(json.dumps(docs[k]));self.refs[k]={'path':str(path),'sha256':M.sha(path)}
  docs['release']['claim_sha256']=self.refs['claim']['sha256'];self.rewrite('release');docs['terminal']['release_sha256']=self.refs['release']['sha256'];self.rewrite('terminal');self.rewrite('attempt_terminal')
  self.p={'chip':2,'successor_guard':{'physical_release':self.refs,'source_execution':{'path':'source','sha256':pin}}}
  self.live=False;self.conflict=False
  self.a={'Id':container,'Image':image,'State':{'Status':'exited','Running':False,'ExitCode':1,'StartedAt':'start','FinishedAt':'finish'},'RestartCount':0,'Config':{'Cmd':['-P','drive']}}
  def pinned(ref):
   M.need(M.sha(ref['path'])==ref['sha256'],'pin changed');return Path(ref['path'])
  self.g._core=types.SimpleNamespace(require=M.need,pinned=pinned,read=M.read)
  self.g.binding=lambda p:(types.SimpleNamespace(process_matches=lambda _:self.live),self.source)
  self.resource=types.SimpleNamespace(docker_inspect=lambda _:self.a,live_chip_conflict=lambda *_:self.conflict)
 def rewrite(self,k):
  p=Path(self.refs[k]['path']);p.write_text(json.dumps(self.docs[k]));self.refs[k]['sha256']=M.sha(p)
 def test_exact_failure_allowed(self):self.assertEqual(self.g.predecessor(self.p,self.resource)['status'],'failed_dev_physically_released')
 def test_live_supervisor_rejected(self):
  self.live=True
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)
 def test_live_chip_rejected(self):
  self.conflict=True
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)
 def test_changed_generation_rejected(self):
  self.a['Id']='other'
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)
 def test_changed_exit_rejected(self):
  self.a['State']['ExitCode']=0
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)
 def test_restart_rejected(self):
  self.a['RestartCount']=1
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)
 def test_wrong_previous_owner_rejected(self):
  self.docs['release']['allocation_after']['free'][0]['previous_run']='other';self.rewrite('release');self.docs['terminal']['release_sha256']=self.refs['release']['sha256'];self.rewrite('terminal');self.rewrite('attempt_terminal')
  with self.assertRaises(RuntimeError):self.g.predecessor(self.p,self.resource)

if __name__=='__main__':unittest.main()
