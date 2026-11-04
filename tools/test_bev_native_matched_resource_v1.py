import unittest,json,types,copy,hashlib,tempfile
from pathlib import Path
HERE=Path(__file__).parent
class ResourceTests(unittest.TestCase):
 def setUp(self):
  src=HERE/'bev_native_matched_resource_v1.py';self.M=types.ModuleType('res');self.M.__file__=str(src);exec(compile(src.read_bytes(),str(src),'exec'),self.M.__dict__)
  self.d=json.loads(Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_matched_2b_preparation_20261104_v1/execution-v2/PLAN.json').read_text());q=json.loads(Path(self.d['queue']['path']).read_text());v={k:json.loads(Path(r['path']).read_text()) for k,r in q['predecessor'].items()};rel=v['release'];old=v['plan'];rec=v['receipt']
  self.actual={'Id':rec['container_id'],'Image':old['image'],'State':{'Status':'exited','Running':False,'ExitCode':rel['exit_code'],'StartedAt':rel['container_started_at'],'FinishedAt':rel['container_finished_at']},'Config':{'Cmd':rec['command']},'HostConfig':{'AutoRemove':False,'Privileged':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/'+n,'PathInContainer':'/dev/'+n} for n in ['davinci_manager','devmm_svm','hisi_hdc','davinci6']]},'RestartCount':0}
  self.alloc={'free':[q['free_entry']],'allocation':[],'pending_claims':q['pending_claims']};self.R=types.SimpleNamespace(validate_doc=lambda x:None,docker_inspect=lambda n:self.actual,live_chip_conflict=lambda *x:False)
 def test_exact_release(self):self.M.guard(self.d,self.R,self.alloc)
 def test_foreign_free(self):
  self.alloc['free'][0]=dict(self.alloc['free'][0],previous_run='foreign')
  with self.assertRaisesRegex(ValueError,'lineage'):self.M.guard(self.d,self.R,self.alloc)
 def test_new_pending_priority(self):
  self.alloc['pending_claims']=[]
  with self.assertRaisesRegex(ValueError,'priority'):self.M.guard(self.d,self.R,self.alloc)
 def test_restarted_container(self):
  self.actual['RestartCount']=1
  with self.assertRaisesRegex(ValueError,'generation'):self.M.guard(self.d,self.R,self.alloc)
 def test_wrong_finish(self):
  self.actual['State']['FinishedAt']='other'
  with self.assertRaisesRegex(ValueError,'generation'):self.M.guard(self.d,self.R,self.alloc)
 def test_still_running(self):
  self.actual['State']['Running']=True
  with self.assertRaisesRegex(ValueError,'physical exit'):self.M.guard(self.d,self.R,self.alloc)
 def test_wrong_device(self):
  self.actual['HostConfig']['Devices'][-1]['PathOnHost']='/dev/davinci5'
  with self.assertRaisesRegex(ValueError,'device'):self.M.guard(self.d,self.R,self.alloc)
 def test_live_conflict(self):
  self.R.live_chip_conflict=lambda *x:True
  with self.assertRaisesRegex(ValueError,'conflict'):self.M.guard(self.d,self.R,self.alloc)
if __name__=='__main__':unittest.main()
