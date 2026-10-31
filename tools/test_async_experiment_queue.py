#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('queue',Path(__file__).with_name('async_experiment_queue.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.live={};self.calls=[];self.saved=[];self.jobs=[]
  for index,chip in [(0,1),(1,1),(2,4)]:
   out=self.root/str(index);out.mkdir();job=dict(id=str(index),chip=chip,plan_sha256='pin',action_log=str(out/'action.log'),release_marker=str(out/'release.json'))
   for lane in ('npu','cpu'):job[lane]=dict(container=lane+str(index),receipt=str(out/(lane+'receipt.json')),terminal=str(out/(lane+'terminal.json')))
   for kind in ('launch','operational_release','cpu_launch'):job[kind]={'kind':kind,'job':job['id']}
   self.jobs.append(job)
  self.manifest={'jobs':self.jobs};self.state={'jobs':{j['id']:{'npu':'queued','cpu':'queued'} for j in self.jobs}}
 def put(self,p,x):Path(p).write_text(json.dumps(x))
 def start(self,j,lane):
  s=j[lane];self.live[s['container']]={'Id':'id-'+s['container'],'HostConfig':{'AutoRemove':False,'Devices':[]},'State':{'Status':'running','StartedAt':'start'}}
  self.put(s['receipt'],{'container_id':'id-'+s['container']})
 def finish(self,j,lane,rc=0):
  self.start(j,lane);self.live[j[lane]['container']]['State'].update(Status='exited',ExitCode=rc,FinishedAt='end');self.put(j[lane]['terminal'],{'rc':rc})
 def proof(self,j):
  obs=m.observe(j['npu'],self.live.get);folder=Path(j['release_marker']).parent
  entries={j['npu'][k]:m.sha(j['npu'][k]) for k in ('receipt','terminal')}
  self.put(folder/'evidence.json',entries);self.put(folder/'transition.json',{'only_chip':j['chip']})
  self.put(j['release_marker'],dict(status='OPERATIONALLY_RELEASED',job_id=j['id'],plan_sha256='pin',chip=j['chip'],scientific_acceptance=False,
   **{k:obs[k] for k in ('container_id','started_at','finished_at','terminal_sha256','receipt_sha256')},
   retained_evidence_manifest=str(folder/'evidence.json'),retained_evidence_manifest_sha256=m.sha(folder/'evidence.json'),
   allocation_transition=str(folder/'transition.json'),allocation_transition_sha256=m.sha(folder/'transition.json')))
 def action(self,a,out):
  self.calls.append((a['kind'],a['job']));j=self.jobs[int(a['job'])]
  if a['kind']=='launch':self.start(j,'npu')
  elif a['kind']=='cpu_launch':self.start(j,'cpu')
  else:self.proof(j)
  return {'returncode':0,'uncertain':False}
 def tick(self):return m.tick(self.manifest,self.state,lambda x:self.saved.append(copy.deepcopy(x)),self.live.get,self.action)
 def test_parallel_chip_first_jobs(self):
  self.tick();self.assertEqual(self.calls,[('launch','0'),('launch','2')])
 def test_next_npu_starts_while_cpu_running(self):
  self.tick();self.finish(self.jobs[0],'npu');self.tick()
  self.assertIn(('launch','1'),self.calls);self.assertEqual(self.state['jobs']['0']['cpu'],'launch_intent')
  self.tick();self.assertEqual(self.state['jobs']['0']['cpu'],'running');self.assertEqual(self.state['jobs']['1']['npu'],'running')
 def test_cpu_queue_strict_order(self):
  self.finish(self.jobs[2],'npu');self.tick();self.assertNotIn(('cpu_launch','2'),self.calls)
 def test_reconcile_lost_start_response_without_duplicate(self):
  self.start(self.jobs[0],'npu');self.state['jobs']['0']['npu']='launch_intent';self.tick();self.assertNotIn(('launch','0'),self.calls)
 def test_lost_release_response_reconciles_proof(self):
  self.finish(self.jobs[0],'npu');self.proof(self.jobs[0]);self.state['jobs']['0']['npu']='release_pending';self.tick()
  self.assertNotIn(('operational_release','0'),self.calls);self.assertIn(('launch','1'),self.calls)
 def test_failed_cpu_does_not_stop_npu(self):
  self.finish(self.jobs[0],'npu');self.proof(self.jobs[0]);self.finish(self.jobs[0],'cpu',1);self.tick()
  self.assertEqual(self.state['jobs']['0']['cpu'],'quarantined');self.assertIn(('launch','1'),self.calls)
 def test_failed_npu_is_released_and_does_not_block_its_chip(self):
  self.finish(self.jobs[0],'npu',1);self.tick();self.assertEqual(self.state['jobs']['0']['npu'],'failed_released')
  self.assertIn(('operational_release','0'),self.calls)
  self.assertIn(('launch','1'),self.calls);self.assertIn(('launch','2'),self.calls)
  self.assertEqual(self.state['jobs']['0']['npu_exit_code'],1)
 def test_failed_npu_without_proof_keeps_chip_blocked(self):
  self.finish(self.jobs[0],'npu',137)
  def no_release(a,out):
   if a['kind']=='operational_release':return {'returncode':1,'uncertain':True}
   return self.action(a,out)
  m.tick(self.manifest,self.state,lambda _:None,self.live.get,no_release)
  self.assertEqual(self.state['jobs']['0']['npu'],'release_pending')
  self.assertEqual(self.state['jobs']['0']['npu_exit_code'],137)
  self.assertNotIn(('launch','1'),self.calls)
  self.assertIn(('launch','2'),self.calls)
 def test_failed_npu_invalid_proof_keeps_chip_blocked(self):
  j=self.jobs[0];self.finish(j,'npu',1);self.proof(j)
  p=m.load(j['release_marker']);p['container_id']='wrong';self.put(j['release_marker'],p)
  self.tick();self.assertEqual(self.state['jobs']['0']['npu'],'quarantined')
  self.assertNotIn(('launch','1'),self.calls)
 def test_completion_never_confers_scientific_acceptance(self):
  for failed in (False,True):
   state={'jobs':{'a':{'npu':'failed_released' if failed else 'done','cpu':'done'}}}
   terminal=m.completion_record(state,'queue','state')
   self.assertIs(terminal['scientific_acceptance'],False)
   self.assertEqual(terminal['scientific_failures'],['a'] if failed else [])
 def test_wrong_generation_never_released(self):
  self.finish(self.jobs[0],'npu');self.live['npu0']['Id']='other';self.tick()
  self.assertEqual(self.state['jobs']['0']['npu'],'quarantined');self.assertNotIn(('operational_release','0'),self.calls)
 def test_missing_terminal_quarantines(self):
  self.finish(self.jobs[0],'npu');Path(self.jobs[0]['npu']['terminal']).unlink();self.tick()
  self.assertEqual(self.state['jobs']['0']['npu'],'quarantined')
 def test_wrong_release_target_quarantines(self):
  j=self.jobs[0];self.finish(j,'npu');self.proof(j);x=m.load(j['release_marker']);x['chip']=4;self.put(j['release_marker'],x);self.tick()
  self.assertEqual(self.state['jobs']['0']['npu'],'quarantined');self.assertNotIn(('launch','1'),self.calls)
 def test_retained_evidence_mutation_quarantines(self):
  j=self.jobs[0];self.finish(j,'npu');self.proof(j);self.put(j['npu']['terminal'],{'rc':0,'changed':True});self.tick()
  self.assertEqual(self.state['jobs']['0']['npu'],'quarantined')
 def test_action_error_does_not_assume_no_launch(self):
  original=self.action
  def lost(a,out):original(a,out);return {'returncode':None,'uncertain':True}
  m.tick(self.manifest,self.state,lambda x:None,self.live.get,lost);self.tick()
  self.assertEqual(self.calls.count(('launch','0')),1)

if __name__=='__main__':unittest.main()
