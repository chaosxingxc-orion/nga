import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('release_test',Path(__file__).with_name('r3_final_async_release_v1.py'));R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
class Release(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir();self.d=self.run/'supervisor-attempts/1';self.d.mkdir(parents=True);self.a=self.run/'final-attempts/1';self.a.mkdir(parents=True)
  self.plan={'model_sha256':'a'*64,'out':str(self.run),'final':{'sha256':'c'*64},'chip':3};self.pin=R.G.digest(self.plan);self.owner=dict(model_sha256='a'*64,run_dir=str(self.run),execution_sha256=self.pin,final_sha256='c'*64)
  report={'fake':'synthetic'};rp=R.G.digest(report);R.G.atomic(self.run/'TEST-PRODUCER-REPORT.json',report);doc=dict(R.X.binding(self.owner),results={s:{'producer_report_sha256':rp} for s in R.X.SUITES},producer_report_sha256=rp,scientific_acceptance=False);R.G.atomic(self.run/R.X.SCORED,doc);self.mp=R.G.digest(doc)
  R.G.atomic(self.a/'SCORE-EXIT.json',{'schema':'r3-final-score-exit-v1','exit_code':0,'attempt':1,'plan_sha256':self.pin,'scored_manifest_sha256':self.mp,'scoring_complete':True,'publication_complete':False,'scientific_acceptance':False})
  R.G.atomic(self.d/'LAUNCH_RECEIPT.json',{'id':'id1','plan_sha256':self.pin});claim={'schema':'r3-resource-claim-v1','run':'final-test/'+self.pin,'chip':3};R.G.atomic(self.d/'CLAIM.json',claim)
  before={'allocation':[{'chip':3,'run':'final-test/'+self.pin}],'free':[]};after={'allocation':[],'free':[{'chip':3,'previous_run':'final-test/'+self.pin}]}
  ledger=lambda x:hashlib.sha256((json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
  self.release={'schema':'r3-resource-release-v1','run':'final-test/'+self.pin,'chip':3,'claim_sha256':R.sha(self.d/'CLAIM.json'),'container_id':'id1','container':'fake','exit_code':0,'scientific_acceptance':False,'container_finished_at':'finish','container_started_at':'start','allocation_before':before,'allocation_after':after,'allocation_before_sha256':ledger(before),'allocation_after_sha256':ledger(after)};R.G.atomic(self.d/'RELEASE.json',self.release)
  self.spec={'name':'fake','image':'img','cmd':['fake'],'devices':['/dev/davinci3'],'mounts':{},'environment':{}}
  self.actual={'Id':'id1','Name':'/fake','Image':'img','HostConfig':{'AutoRemove':False,'NetworkMode':'none','Privileged':False,'Devices':[{'PathOnHost':'/dev/davinci3'}]},'Config':{'Entrypoint':['python3'],'Cmd':['fake'],'Env':[]},'Mounts':[{'Type':'bind','Source':'/usr/local/Ascend/driver','Destination':'/usr/local/Ascend/driver','RW':False}],'State':{'Status':'exited','ExitCode':0,'OOMKilled':False,'StartedAt':'start','FinishedAt':'finish'}}
 def check(self):return R.validate(self.plan,self.pin,1,self.owner,self.mp,spec=self.spec,observe=lambda name:self.actual)
 def test_real_structure(self):self.assertEqual(self.check()['state'],'actual_exit_and_release_verified')
 def test_live_failed_and_replaced_container(self):
  old=copy.deepcopy(self.actual)
  for path,key,v in [('State','Status','running'),('State','ExitCode',1),('State','OOMKilled',True),(None,'Id','id2')]:
   self.actual=copy.deepcopy(old);(self.actual[path] if path else self.actual)[key]=v
   with self.assertRaises(ValueError):self.check()
 def test_manifest_terminal_and_release_mismatch(self):
  for key,v in [('container_id','other'),('claim_sha256','0'*64),('exit_code',False),('container_finished_at','other')]:
   R.G.atomic(self.d/'RELEASE.json',dict(self.release,**{key:v}))
   with self.assertRaises(ValueError):self.check()
  R.G.atomic(self.d/'RELEASE.json',self.release);p=self.a/'SCORE-EXIT.json';d=json.loads(p.read_text());d['scored_manifest_sha256']='0'*64;R.G.atomic(p,d)
  with self.assertRaisesRegex(ValueError,'terminal identity'):self.check()
 def test_score_only_terminal_distinct_from_publication(self):
  marker=json.loads((self.a/'SCORE-EXIT.json').read_text())
  self.assertEqual(R.reconcile_score_exit(self.actual,marker,plan_sha256=self.pin,attempt=1,manifest_sha256=self.mp),marker)
  missing=R.reconcile_score_exit(self.actual,None,plan_sha256=self.pin,attempt=1,manifest_sha256=self.mp)
  self.assertEqual(missing['exit_code'],125);self.assertFalse(missing['scoring_complete'])
  marker['publication_complete']=True
  with self.assertRaisesRegex(ValueError,'authority'):R.reconcile_score_exit(self.actual,marker,plan_sha256=self.pin,attempt=1,manifest_sha256=self.mp)
 def test_missing_release(self):
  (self.d/'RELEASE.json').unlink()
  with self.assertRaises(FileNotFoundError):self.check()
if __name__=='__main__':unittest.main()
