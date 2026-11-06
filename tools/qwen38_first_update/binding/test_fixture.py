import importlib.util, json, shutil, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PREP=ROOT/'qwen38-fixture-launch-preparation'
PACKAGE=ROOT/'qwen38-post-k0-queue/candidate/package'
spec=importlib.util.spec_from_file_location('fixture',HERE/'fixture.py'); f=importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

class FixtureTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.d=Path(self.tmp.name)
  cand=ROOT/'qwen38-renderer-terminal-fix/candidate'; group=HERE/'adapter'; bridge=PREP/'marker_bridge.py'; probe=self.d/'probe'; probe.write_text('mock')
  self.c={'dispatchable':True,'source_integration_review':'accepted','review_receipt':'TEST ONLY','mapping_evidence':'TEST ONLY','candidate':str(cand),'out':str(self.d/'out'),'name':'test-fixture','phase':'phase1','image':'sha256:'+'a'*64,'chips':[1,3,5,7],'device_mapping':[{'physical':x,'container':i} for i,x in enumerate([1,3,5,7])],'visible_devices':'0,1,2,3','allocation':str(self.d/'alloc.json'),'probe':str(probe),'group_source':str(group),'bridge_source':str(bridge),'candidate_pins':{x:f.sha(cand/x) for x in f.FILES},'source_pins':{str(x):f.sha(x) for x in [probe,group/'group_adapter.py',group/'r3_resource_adapter.py',bridge]}}
  self.config=self.d/'config.json'; self.config.write_text(json.dumps(self.c))
  self.a=f.prepare(self.config,HERE/'fixture.py'); self.assertTrue((self.a/'PREPARED.json').exists()); self.assertFalse((self.a/'CLAIM.json').exists())
  self.g=f.module(self.a/'adapter/group_adapter.py','testgroup'); self.g.r3.live_chip_conflict=lambda *x:False
  self.captured=[]; self.cid='a'*64
  self.obj={'Id':self.cid,'Name':'/test-fixture','State':{'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci'+str(x)} for x in self.c['chips']]}}
  self.g.r3.docker_inspect=lambda n:self.obj
  # Match the adapter's actual ledger schema.
  self.ledger={'free':[{'chip':x} for x in range(8)],'allocation':[]}; self.c['allocation']=str(self.d/'alloc.json'); (self.d/'alloc.json').write_text(json.dumps(self.ledger))
 def test_wait_launch_release(self):
  orig=f.loaded; calls=[]
  def load(a): return self.a,self.c,self.g
  def host(c):
   calls.append('host')
   if len(calls)==1: raise RuntimeError('busy')
   return {'chips':c['chips'],'certain':True,'unmanaged_owners':[]}
  def sleep(n):
   self.assertFalse((self.a/'CLAIM.json').exists()); self.assertTrue((self.a/'work/entry.py').exists()); calls.append('wait')
  def proc(argv,**kw):
   self.captured.append(argv)
   if argv[:2]==['docker','run']:
    self.assertTrue((self.a/'CLAIM.json').exists()); (Path(self.c['out'])/'exit-phase1.marker').write_text('0\n'); return subprocess.CompletedProcess(argv,0,self.cid+'\n','')
   if argv[:2]==['docker','wait']: return subprocess.CompletedProcess(argv,0,'0\n','')
   raise AssertionError(argv)
  # Name is initially absent and becomes visible after launch.
  self.g.r3.docker_inspect=lambda n: self.obj if self.captured else None
  with patch.object(f,'loaded',load),patch.object(f,'host',host),patch.object(f.time,'sleep',sleep),patch.object(f.subprocess,'run',proc):
   self.assertEqual(f.run(self.a),0)
  command=self.captured[0]; self.assertIn('/dev/davinci5:/dev/davinci2',command); self.assertIn('ASCEND_RT_VISIBLE_DEVICES=0,1,2,3',command); self.assertEqual(command[-2:],['bash',str(self.a/'work/container_entry.sh')]); self.assertTrue((self.a/'RELEASE.json').exists()); self.assertEqual(len(json.loads((self.d/'alloc.json').read_text())['free']),8)
 def test_ambiguous_launch_retains(self):
  self.g.r3.docker_inspect=lambda n:None
  def proc(argv,**kw): raise subprocess.TimeoutExpired(argv,120)
  with patch.object(f,'loaded',lambda a:(self.a,self.c,self.g)),patch.object(f,'host',lambda c:{'chips':c['chips'],'certain':True,'unmanaged_owners':[]}),patch.object(f.subprocess,'run',proc):
   with self.assertRaises(subprocess.TimeoutExpired): f.run(self.a)
   self.assertTrue((self.a/'CLAIM.json').exists()); self.assertTrue((self.a/'LAUNCH-INTENT.json').exists()); self.assertFalse((self.a/'RELEASE.json').exists())
   with self.assertRaisesRegex(RuntimeError,'reconcile'): f.run(self.a)
 def test_missing_marker_retains(self):
  (self.a/'CONTAINER.json').write_text(json.dumps({'id':self.cid,'name':'test-fixture'}))
  with patch.object(f,'loaded',lambda a:(self.a,self.c,self.g)),patch.object(f.subprocess,'run',lambda argv,**kw:subprocess.CompletedProcess(argv,0,'0\n','')):
   with self.assertRaises(FileNotFoundError): f.observe(self.a)
  self.assertFalse((self.a/'RELEASE.json').exists())
if __name__=='__main__': unittest.main()
