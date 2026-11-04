import copy,json,tempfile,unittest
from pathlib import Path
from tools import bev_successor_prepare_queue_v1 as Q
class ReleaseDependency(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)/'old';self.h=self.root/'output/host_attempts/1';self.h.mkdir(parents=True);(self.root/'output/attempts/1').mkdir(parents=True)
  self.run='r3_runs/old';self.plan={'run':self.run,'chip':0,'container':'old'};self.save(self.root/'PLAN.json',self.plan);pin=Q.sha(self.root/'PLAN.json')
  claim={'schema':'r3-resource-claim-v1','run':self.run,'chip':0};self.save(self.h/'CLAIM.json',claim)
  free={'chip':0,'previous_run':self.run,'release_evidence':str(self.h/'RELEASE.json')};self.allocation={'free':[free],'allocation':[]}
  self.release={'schema':'r3-resource-release-v1','run':self.run,'chip':0,'claim_sha256':Q.sha(self.h/'CLAIM.json'),'exit_code':0,'scientific_acceptance':False,'container':'old-a1','container_id':'id','container_started_at':'s','container_finished_at':'f','allocation_after':copy.deepcopy(self.allocation)}
  self.save(self.h/'RELEASE.json',self.release);common={'exit_code':0,'scientific_acceptance':False,'plan_sha256':pin,'attempt':1};self.save(self.h/'EXIT.json',dict(common,runner_terminal_matches=True,container_id='id'));self.save(self.root/'output/attempts/1/EXIT.json',common);self.save(self.h/'LAUNCH_RECEIPT.json',{'container_id':'id','plan_sha256':pin,'attempt':1})
  self.job={'predecessor_root':str(self.root),'predecessor_plan_sha256':pin,'chip':0};self.actual={'Id':'id','State':{'Running':False,'Status':'exited','ExitCode':0,'StartedAt':'s','FinishedAt':'f'},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci0'}]},'RestartCount':0}
 def save(self,p,d):p.write_text(json.dumps(d))
 def test_released_without_cpu_result_can_prepare(self):
  proof=Q.released(self.job,self.allocation,lambda _:self.actual);self.assertEqual(proof['container_id'],'id');self.assertFalse((self.root/'output/cpu').exists())
 def test_no_marker_waits_without_docker_guess(self):
  (self.h/'RELEASE.json').unlink();self.assertIsNone(Q.released(self.job,self.allocation,lambda _:self.fail('must not infer from docker')))
 def test_owned_chip_waits(self):
  self.allocation['allocation']=[{'chip':0}];self.assertIsNone(Q.released(self.job,self.allocation,lambda _:self.actual))
 def test_live_container_and_foreign_generation_rejected(self):
  self.actual['State']['Running']=True
  with self.assertRaises(ValueError):Q.released(self.job,self.allocation,lambda _:self.actual)
  self.actual['State']['Running']=False;self.actual['Id']='foreign'
  with self.assertRaises(ValueError):Q.released(self.job,self.allocation,lambda _:self.actual)
 def test_failed_or_rewritten_terminal_rejected(self):
  for key,val in [('exit_code',1),('exit_code',False),('attempt',2),('plan_sha256','changed')]:
   p=self.h/'EXIT.json';original=Q.read(p);self.save(p,dict(original,**{key:val}))
   with self.subTest(key=key,val=val),self.assertRaises(ValueError):Q.released(self.job,self.allocation,lambda _:self.actual)
   self.save(p,original)
if __name__=='__main__':unittest.main()
