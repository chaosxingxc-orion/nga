import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from tools import r3_monitor_registry as M

class Monitor(unittest.TestCase):
 def phases(self,**kw):return {k:{'state':v} for k,v in kw.items()}
 def test_missing_registered_root(self):
  self.assertEqual(M.phase_observation({'runs':[]},'/missing')['state'],'not_observed_or_queued')
 def test_complete_beats_stale_progress_not_log_errors(self):
  p=self.phases(runtime='done',host='done',progress='stalled',cpu='done');p['progress']['errors']={'error_lines':2};p['progress']['pointers']=[{'path':'x','line_start':1}]
  r=M.aggregate({'id':'a','chip':0,'required_phases':['runtime','host']},p,{'state':'released_bound','exit_code':0})
  self.assertEqual(r['state'],'complete_observed');self.assertEqual(len(r['log_issues']),1)
 def test_cpu_partial_failure_and_unknown_not_complete(self):
  for state,want in [('not_observed_or_queued','awaiting_cpu'),('failed','cpu_failed'),('unknown','cpu_unknown')]:
   r=M.aggregate({'id':'a','chip':0,'required_phases':['runtime','host']},self.phases(runtime='done',host='done',cpu=state),{'state':'released_bound','exit_code':0});self.assertEqual(r['state'],want)
 def test_partial_terminal_and_release_unknown(self):
  t={'id':'a','chip':0,'required_phases':['runtime','host']}
  self.assertEqual(M.aggregate(t,self.phases(runtime='done',host='not_observed_or_queued'),{'state':'not_observed'})['state'],'running')
  self.assertEqual(M.aggregate(t,self.phases(runtime='done',host='done'),{'state':'unknown'})['state'],'release_unknown')
 def fixture(self,r):
  claim=r/'CLAIM.json';release=r/'RELEASE.json';terminal=r/'EXIT.json';receipt=r/'LAUNCH_RECEIPT.json';cid='a'*64
  M.put(claim,{'schema':'r3-resource-claim-v1','run':'run','chip':0});M.put(release,{'schema':'r3-resource-release-v1','run':'run','chip':0,'exit_code':0,'scientific_acceptance':False,'container':'c','container_id':cid,'claim_sha256':M.sha(claim)});M.put(terminal,{'exit_code':0});M.put(receipt,{'container_id':cid})
  return {'run':'run','chip':0,'container':'c','release':{'path':str(release),'claim':str(claim),'terminal':str(terminal),'receipt':str(receipt)}}
 def test_bound_release_and_single_attacks(self):
  for key,value in [('chip',False),('exit_code',False),('container_id','b'*64),('claim_sha256','f'*64),('scientific_acceptance',True)]:
   with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
    t=self.fixture(Path(tmp));self.assertEqual(M.release_observation(t)['state'],'released_bound');d=M.read(t['release']['path']);d[key]=value;M.put(t['release']['path'],d);self.assertEqual(M.release_observation(t)['state'],'unknown')
 def test_exact_legacy_observed_not_modern(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=self.fixture(Path(tmp));d=M.read(t['release']['path']);del d['claim_sha256'];M.put(t['release']['path'],d)
   self.assertEqual(M.release_observation(t)['state'],'unknown');t['release']['legacy_release_sha256']=M.sha(t['release']['path']);t['release']['legacy_claim_sha256']=M.sha(t['release']['claim']);r=M.release_observation(t);self.assertEqual(r['state'],'released_legacy_observed');self.assertFalse(r['modern_binding'])
 def test_malformed_file_and_nonfinite(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=self.fixture(Path(tmp));Path(t['release']['path']).write_text('{bad');self.assertEqual(M.release_observation(t)['state'],'unknown')
   Path(t['release']['path']).write_text('{"x":NaN}')
   with self.assertRaises(ValueError):M.read(t['release']['path'])
 def test_group_command_bare_markers_logs_and_no_hardware(self):
  c={'watchdog':{'path':'/source'},'groups':{'runtime':{'markers':['EXIT.json'],'logs':['*.log','../../host_attempts/*/runtime.log']}},'tasks':[{'phases':{'runtime':'/r'}}]};v=M.group_command(c,'runtime','/o');self.assertIn('--no-npu',v);self.assertIn('*.log,../../host_attempts/*/runtime.log',v);self.assertNotIn('--watch',v)
 def test_unregistered_cpu_never_complete(self):
  r=M.aggregate({'id':'a','chip':0,'required_phases':['runtime']},self.phases(runtime='done'),{'state':'released_bound','exit_code':0})
  self.assertEqual(r['state'],'inference_complete_cpu_untracked')
 def test_duplicate_json_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'x.json';p.write_text('{"exit_code":1,"exit_code":0}')
   with self.assertRaises(ValueError):M.read(p)
 def test_local_fixture_detached_singleton_identity_and_exit(self):
  # Synthetic local fixture only: no production data, containers or hardware.
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);runner=Path(M.__file__).resolve();fake=Path('tools/watchdog.py').resolve();out=root/'out'

   c={'schema':'r3-monitor-registry-v1','interval_seconds':600,'scientific_acceptance':False,'output':str(out),'runner':{'path':str(runner),'sha256':M.sha(runner)},'watchdog':{'path':str(fake),'sha256':M.sha(fake)},'groups':{'runtime':{'markers':['EXIT.json'],'logs':['*.log']}},'tasks':[{'id':'fixture','run':'fixture','container':'fixture','chip':0,'required_phases':['runtime'],'phases':{'runtime':str(root/'absent')},'release':{'path':str(root/'release'),'claim':str(root/'claim')}}]}
   cp=root/'config.json';M.put(cp,c);cmd=[sys.executable,'-B','-P',str(runner),'start','--config',str(cp),'--sha256',M.sha(cp)]
   first=subprocess.run(cmd,capture_output=True,text=True,timeout=10);self.assertEqual(first.returncode,0,first.stderr);pid=json.loads(first.stdout)['pid']
   try:
    for _ in range(100):
     if (out/'heartbeat.json').exists():break
     time.sleep(.02)
    self.assertTrue((out/'heartbeat.json').exists());receipt=M.read(out/'SERVICE.json');self.assertEqual(receipt['start_ticks'],M.process_identity(pid)['start_ticks'])
    second=subprocess.run(cmd,capture_output=True,text=True,timeout=10);self.assertNotEqual(second.returncode,0)
    once_cmd=[*cmd];once_cmd[4]='once'
    self.assertNotEqual(subprocess.run(once_cmd,capture_output=True,text=True,timeout=10).returncode,0)
    self.assertEqual(M.read(out/'digest.json')['logical_task_count'],1)
   finally:
    os.kill(pid,signal.SIGTERM)
    for _ in range(100):
     if (out/'EXIT.json').exists():break
     time.sleep(.02)
    self.assertEqual(M.read(out/'EXIT.json')['exit_code'],0)
class Regressions(unittest.TestCase):
 def setup_group(self,root):
  path=root/'run';path.mkdir();out=root/'out';out.mkdir();wp=Path('tools/watchdog.py').resolve()
  c={'watchdog':{'path':str(wp),'sha256':M.sha(wp)},'runner':{'path':M.__file__,'sha256':M.sha(M.__file__)},'groups':{'runtime':{'markers':['EXIT.json'],'logs':['*.log']}},'tasks':[{'phases':{'runtime':str(path)}}]}
  return c,path,out,M.load_watchdog(c['watchdog'])
 def test_log_only_and_incremental_restart_append_rotation_truncation(self):
  with tempfile.TemporaryDirectory() as tmp:
   c,p,o,w=self.setup_group(Path(tmp));log=p/'run.log';log.write_text('ERROR startup failed\nWARNING check\n')
   d=M.observe_group(c,'runtime',o,w,time.time());r=d['runs'][0]
   self.assertEqual(r['state'],'unknown');self.assertEqual(r['errors']['error_lines'],1);self.assertEqual(r['errors']['warning_lines'],1)
   self.assertGreater(d['scan_bytes'],0)
   self.assertEqual(M.observe_group(c,'runtime',o,w,time.time())['scan_bytes'],0)
   with log.open('a') as f:f.write('ERROR new\n')
   d=M.observe_group(c,'runtime',o,w,time.time());self.assertEqual(d['scan_bytes'],10);self.assertEqual(d['runs'][0]['errors']['error_lines'],2)
   log.rename(p/'old.txt');log.write_text('WARNING replacement\n')
   d=M.observe_group(c,'runtime',o,w,time.time());self.assertEqual(d['runs'][0]['errors']['error_lines'],0);self.assertEqual(d['runs'][0]['errors']['warning_lines'],1)
   log.write_text('ERROR short\n');self.assertEqual(M.observe_group(c,'runtime',o,w,time.time())['runs'][0]['errors']['error_lines'],1)
   log.write_text('WARNING truncate then regrow beyond original file length\n');r=M.observe_group(c,'runtime',o,w,time.time())['runs'][0]
   self.assertEqual(r['errors']['error_lines'],0);self.assertEqual(r['errors']['warning_lines'],1)
 def test_warning_and_shared_physical_log_dedup(self):
  evidence={'path':'/log','device':1,'inode':2,'error_lines':1,'warning_lines':2,'untracked_lines':0}
  ph={k:{'state':'running','errors':{'error_lines':1,'warning_lines':2},'log_evidence':[evidence]} for k in ('host','runtime')}
  r=M.aggregate({'id':'x','chip':0,'required_phases':['runtime','host']},ph,{'state':'not_observed'})
  self.assertEqual(r['log_counts'],{'error_lines':1,'warning_lines':2,'untracked_lines':0})
 def test_legacy_liveness_strict_and_terminal_conflict(self):
  with tempfile.TemporaryDirectory() as tmp:
   c,p,o,w=self.setup_group(Path(tmp));hb={'pid':7,'progress_unit':'files and bytes, not scored questions','readout_bytes':30,'readout_files':2,'utc_seconds':time.time()};M.put(p/'heartbeat.json',hb)
   r=M.observe_group(c,'runtime',o,w,time.time())['runs'][0];self.assertEqual(r['state'],'running');self.assertIsNone(r['progress']['done'])
   for field,value in [('pid',True),('readout_bytes',-1),('readout_files',2.0),('utc_seconds',time.time()+999),('progress_unit','questions')]:
    with self.subTest(field=field):
     M.put(p/'heartbeat.json',{**hb,field:value});self.assertEqual(M.observe_group(c,'runtime',o,w,time.time())['runs'][0]['state'],'unknown')
   M.put(p/'heartbeat.json',hb);M.put(p/'EXIT.json',{'exit_code':0,'rc':1})
   self.assertEqual(M.observe_group(c,'runtime',o,w,time.time())['runs'][0]['state'],'unknown')
 def test_json_flat_history_persists_no_mixed_rate(self):
  with tempfile.TemporaryDirectory() as tmp:
   c,p,o,w=self.setup_group(Path(tmp));now=time.time()
   for age in (20000,10000,0):
    M.put(p/'heartbeat.json',{'utc_seconds':now-age,'completed':4,'total':10,'attempt':1});r=M.observe_group(c,'runtime',o,w,now-age)['runs'][0]
   self.assertTrue(r['progress_flat']['confirmed']);self.assertIsNone(r['progress']['rate_per_min'])
   phase=M.phase_observation({'runs':[r]},str(p));self.assertIn('runtime:progress_flat',M.compact_flags({'phases':{'runtime':phase}}))
   M.put(p/'heartbeat.json',{'utc_seconds':now+1,'completed':5,'total':10,'attempt':1});r=M.observe_group(c,'runtime',o,w,now+1)['runs'][0];self.assertIsNone(r['progress_flat'])
   M.put(p/'heartbeat.json',{'utc_seconds':now+2,'completed':1,'total':10,'attempt':2});r=M.observe_group(c,'runtime',o,w,now+2)['runs'][0];self.assertEqual(r['json_progress_history']['samples'],1)
 def test_release_rejects_conflicting_alias(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=Monitor().fixture(Path(tmp));d=M.read(t['release']['path']);d['rc']=1;M.put(t['release']['path'],d);self.assertEqual(M.release_observation(t)['state'],'unknown')

if __name__=='__main__':unittest.main()
