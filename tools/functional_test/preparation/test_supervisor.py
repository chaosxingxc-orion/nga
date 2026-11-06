import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('host',Path(__file__).with_name('supervisor.py'))
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)

class Lifecycle(unittest.TestCase):
 def test_real_adapter_and_command_lifecycle(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); alloc=root/'alloc.json'; H.save(alloc,{'allocation':[],'free':[{'chip':3}]})
   claim=root/'claim'; release=root/'release'; launch=root/'launch'; state=root/'state'/'fixture'; state.parent.mkdir()
   ident='a'*64; image='sha256:'+'b'*64
   spec={'name':'rc1-test','image':image,'cmd':['-B','-P','/entry','infer'],'mounts':{'/tmp/source':False},'devices':['/dev/davinci3'],'environment':{'X':'Y'}}
   c={'member':'fixture','container':{'spec':spec,'run':'run1','chip':3,'claim':str(claim),'release':str(release),'launch_receipt':str(launch)},'image':image,'out':str(root/'out')}
   (root/'out').mkdir();(root/'out'/'INFERENCE-READY.json').write_text('{}')
   H.save(root/'out'/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':H.digest(c),'exit_code':0,'ready_sha256':H.sha(root/'out'/'INFERENCE-READY.json')})
   h={'state_dir':str(state.parent),'allocation':str(alloc),'owner':'fixture','cpu_python':'/python','cpu_environment':{},'entry':'/entry'}
   c['host']=h; H.save(root/'out'/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':H.digest(c),'exit_code':0,'ready_sha256':H.sha(root/'out'/'INFERENCE-READY.json')}); config=root/'config';config.write_text(json.dumps(c))
   observed={'Id':ident,'Name':'/rc1-test','Image':image,'State':{'Status':'exited','ExitCode':0,'StartedAt':'a','FinishedAt':'b','OOMKilled':False},'HostConfig':{'AutoRemove':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/davinci3'}]},'Config':{'Entrypoint':['python3'],'Cmd':spec['cmd'],'Env':['X=Y']},'Mounts':[{'Type':'bind','Source':p,'Destination':p,'RW':rw} for p,rw in {**spec['mounts'],'/usr/local/Ascend/driver':False}.items()]}
   commands=[]
   def run(cmd,**kwargs):
    commands.append(cmd)
    return SimpleNamespace(stdout=ident+'\n')
   class Proc:
    returncode=0
    pid=42
    def __init__(self,cmd,**kw):
     commands.append(cmd)
     if 'host-cpu' in cmd:
      self_outer.assertTrue(release.exists()); self_outer.assertFalse(json.loads(alloc.read_text())['allocation'])
    def wait(self,timeout=None): return 0
    def poll(self): return 0
   self_outer=self
   with mock.patch.object(H,'validate',return_value=h),mock.patch.object(H,'probe',return_value=True),mock.patch.object(H,'wait_ready'),mock.patch.object(H,'run',side_effect=run),mock.patch.object(H.R,'image_inspect'),mock.patch.object(H.R,'docker_inspect',return_value=observed),mock.patch.object(H.R,'live_chip_conflict',return_value=False),mock.patch.object(H.subprocess,'Popen',side_effect=Proc):
    H.drive(str(config))
   self.assertEqual(json.loads(claim.read_text())['schema'],'r3-resource-claim-v1')
   rel=json.loads(release.read_text());self.assertEqual(rel['schema'],'r3-resource-release-v1');self.assertEqual(rel['claim_sha256'],H.sha(claim));self.assertEqual(rel['container_id'],ident)
   for part in ('before','after'):
    self.assertEqual(rel['allocation_'+part+'_sha256'],H.R.sha_bytes((json.dumps(rel['allocation_'+part],indent=2,sort_keys=True,allow_nan=False)+'\n').encode()))
   docker=next(x for x in commands if x[:2]==['docker','run']);self.assertEqual(docker,H.K.command(spec));self.assertIn('-d',docker);self.assertNotIn('--rm',docker)
   self.assertEqual(json.loads((state/'SUPERVISOR-EXIT.json').read_text())['exit_code'],0)
 def exercise_export_command(self, failure):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); alloc=root/'alloc.json'; H.save(alloc,{'allocation':[],'free':[{'chip':3}]})
   claim=root/'claim'; release=root/'release'; launch=root/'launch'; state=root/'state'/'fixture'; state.parent.mkdir()
   ident='a'*64; image='sha256:'+'b'*64
   spec={'name':'rc1-test','image':image,'cmd':['-B','-P','/entry','infer'],'mounts':{'/tmp/source':False},'devices':['/dev/davinci3'],'environment':{'X':'Y'}}
   c={'member':'fixture','container':{'spec':spec,'run':'run1','chip':3,'claim':str(claim),'release':str(release),'launch_receipt':str(launch)},'image':image,'out':str(root/'out')}
   (root/'out').mkdir();(root/'out'/'INFERENCE-READY.json').write_text('{}')
   H.save(root/'out'/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':H.digest(c),'exit_code':0,'ready_sha256':H.sha(root/'out'/'INFERENCE-READY.json')})
   h={'state_dir':str(state.parent),'allocation':str(alloc),'owner':'fixture','cpu_python':'/python','cpu_environment':{},'entry':'/entry'}
   export=root/'exporter.py';export.write_text('stub'); core=root/'core.py';core.write_text('core'); h.update(entry=str(core),cpu_entry=str(export),implementation_files={str(export):H.sha(export)});c.update(member=H.EXPORT_MEMBER,round_dir=str(root/'campaign/round'),source_files={str(core):H.sha(core)},population_export={'producer':{'path':str(core),'sha256':H.sha(core)},'exporter':{'path':str(export),'sha256':H.sha(export)},'member':H.EXPORT_MEMBER,'scope':H.EXPORT_SCOPE,'directory':str(root/'campaign/population-export')}); state=state.parent/H.EXPORT_MEMBER
   c['host']=h; H.save(root/'out'/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':H.digest(c),'exit_code':0,'ready_sha256':H.sha(root/'out'/'INFERENCE-READY.json')}); config=root/'config';config.write_text(json.dumps(c))
   observed={'Id':ident,'Name':'/rc1-test','Image':image,'State':{'Status':'exited','ExitCode':0,'StartedAt':'a','FinishedAt':'b','OOMKilled':False},'HostConfig':{'AutoRemove':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/davinci3'}]},'Config':{'Entrypoint':['python3'],'Cmd':spec['cmd'],'Env':['X=Y']},'Mounts':[{'Type':'bind','Source':p,'Destination':p,'RW':rw} for p,rw in {**spec['mounts'],'/usr/local/Ascend/driver':False}.items()]}
   commands=[]
   def run(cmd,**kwargs):
    commands.append(cmd)
    return SimpleNamespace(stdout=ident+'\n')
   class Proc:
    returncode=0
    pid=42
    def __init__(self,cmd,**kw):
     commands.append(cmd)
     self.cpu='host-cpu' in cmd
     if self.cpu:
      self_outer.assertTrue(release.exists()); self_outer.assertFalse(json.loads(alloc.read_text())['allocation'])
    def wait(self,timeout=None): return 1 if self.cpu and failure else 0
    def poll(self): return 0
   self_outer=self
   with mock.patch.object(H,'validate',return_value=h),mock.patch.object(H,'probe',return_value=True),mock.patch.object(H,'wait_ready'),mock.patch.object(H,'run',side_effect=run),mock.patch.object(H.R,'image_inspect'),mock.patch.object(H.R,'docker_inspect',return_value=observed),mock.patch.object(H.R,'live_chip_conflict',return_value=False),mock.patch.object(H.subprocess,'Popen',side_effect=Proc):
    if failure:
     with self.assertRaisesRegex(RuntimeError,'CPU phase failed'):H.drive(str(config))
    else:H.drive(str(config))
   self.assertEqual(json.loads(claim.read_text())['schema'],'r3-resource-claim-v1')
   rel=json.loads(release.read_text());self.assertEqual(rel['schema'],'r3-resource-release-v1');self.assertEqual(rel['claim_sha256'],H.sha(claim));self.assertEqual(rel['container_id'],ident)
   for part in ('before','after'):
    self.assertEqual(rel['allocation_'+part+'_sha256'],H.R.sha_bytes((json.dumps(rel['allocation_'+part],indent=2,sort_keys=True,allow_nan=False)+'\n').encode()))
   docker=next(x for x in commands if x[:2]==['docker','run']);self.assertEqual(docker,H.K.command(spec));self.assertIn('-d',docker);self.assertNotIn('--rm',docker)
   self.assertEqual(json.loads((state/'SUPERVISOR-EXIT.json').read_text())['exit_code'],1 if failure else 0)
   self.assertEqual(next(x for x in commands if 'host-cpu' in x),['/python','-P',str(export),'host-cpu','--config',str(config.resolve())])
   self.assertEqual(next(x for x in commands if 'prepare' in x)[2],str(core))
 def test_export_after_release(self):self.exercise_export_command(False)
 def test_export_cpu_failure(self):self.exercise_export_command(True)
 def test_unknown_launch_refuses_duplicate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=root/'state'/'fixture';state.mkdir(parents=True);c={'member':'fixture','container':{'spec':{'name':'name'},'launch_receipt':str(root/'missing')},'image':'img'};p=root/'config';p.write_text(json.dumps(c))
   H.save(state/'LAUNCH-INTENT.json',{'config_sha256':H.digest(c),'name':'name'})
   h={'state_dir':str(state.parent),'cpu_python':'/python','cpu_environment':{},'entry':'/entry'}
   with mock.patch.object(H,'validate',return_value=h),mock.patch.object(H.R,'image_inspect'),mock.patch.object(H,'run') as run,mock.patch.object(H,'long_phase'):
    with self.assertRaisesRegex(RuntimeError,'unknown launch'): H.drive(str(p))
    self.assertEqual(run.call_count,0)
 def test_probe_refuses_live_ownership(self):
  with mock.patch.object(H.P,'host_check'),mock.patch.object(H.P,'Inventory',return_value=SimpleNamespace(inspect=lambda n:None,conflict=lambda c:True)),mock.patch.object(H.P,'device_query',return_value=False):
   self.assertFalse(H.probe(3,'name'))
 def test_busy_wait_until_free(self):
  with tempfile.TemporaryDirectory() as d, mock.patch.object(H,'probe',side_effect=[False,False,True]) as probe,mock.patch.object(H.time,'sleep') as sleep:
   H.wait_ready(3,'name','ledger',Path(d)/'log')
   self.assertEqual(probe.call_count,3); self.assertEqual(sleep.call_args_list,[mock.call(600),mock.call(600)])
 def test_long_prepare_uses_wait_not_metadata_timeout(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); proc=SimpleNamespace(pid=1,wait=mock.Mock(side_effect=[H.subprocess.TimeoutExpired('prepare',600),0]))
   with mock.patch.object(H.subprocess,'Popen',return_value=proc):
    H.long_phase(['/python','prepare'],{},root,root/'supervisor.log','prepare')
   self.assertEqual(proc.wait.call_count,2)
   self.assertEqual(json.loads((root/'PREPARE-EXIT.json').read_text())['exit_code'],0)
   self.assertIn('heartbeat progress=prepare',(root/'supervisor.log').read_text())
 def test_config_builder_binds_real_entry_and_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); entry=root/'entry.py'; entry.write_text('pass\n')
   runtime=root/'runtime.json'; runtime.write_text(json.dumps({'image':'image','environment':{'PATH':'/bin'}}))
   template=root/'template.json'; template.write_text(json.dumps({'image':'image','source_files':{str(entry):H.sha(entry)},'host':{},'container':{'spec':{}},'review':{'stale':True}}))
   out=root/'draft.json'; final=root/'final.json'
   H.subprocess.run([H.sys.executable,'-P',str(Path(__file__).with_name('config_builder.py')),'--template',str(template),'--runtime',str(runtime),'--entry',str(entry),'--config-path',str(final),'--output',str(out)],check=True)
   c=json.loads(out.read_text()); self.assertNotIn('review',c)
   self.assertEqual(c['host']['runtime_evidence']['sha256'],H.sha(runtime))
   self.assertEqual(c['container']['spec']['cmd'],['-B','-P',str(entry),'infer','--config',str(final)])
   self.assertEqual(c['container']['spec']['environment']['PATH'],'/bin')
if __name__=='__main__':unittest.main()
