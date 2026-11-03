import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import r3_profile_async as R
from tools import r3_profile_async_host as H
class Tests(unittest.TestCase):
 def raw(self,root):
  p=root/'trace'/'worker_ascend_pt';(p/'FRAMEWORK').mkdir(parents=True);(p/'PROF_x/device_0').mkdir(parents=True)
  (p/'FRAMEWORK/torch.op_range').write_bytes(b'raw');(p/'PROF_x/device_0/data').write_bytes(b'raw');(p/'profiler_info.json').write_text('{}');return p
 def test_manifest_binds_and_rejects_missing_framework(self):
  with tempfile.TemporaryDirectory() as x:
   p=self.raw(Path(x));d=R.capture_manifest(p.parent,'p');self.assertEqual(len(d['files']),3)
   (p/'FRAMEWORK/torch.op_range').unlink()
   with self.assertRaisesRegex(ValueError,'framework'):R.capture_manifest(p.parent,'p')
 def test_raw_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as x:
   p=self.raw(Path(x));(p/'foreign').symlink_to('/etc/hosts')
   with self.assertRaisesRegex(ValueError,'symlink'):R.snapshot(p)
 def test_parsed_capture_rejected(self):
  with tempfile.TemporaryDirectory() as x:
   p=self.raw(Path(x));(p/'ASCEND_PROFILER_OUTPUT').mkdir();(p/'ASCEND_PROFILER_OUTPUT/x').write_text('x')
   with self.assertRaisesRegex(ValueError,'already parsed'):R.capture_manifest(p.parent,'p')
 def test_cpu_command_no_device_readonly_raw(self):
  d=dict(container='c',environment={'Z':'1','A':'2'},mounts=[dict(source='/raw',destination='/raw',readonly=False)],out='/raw',image_sha256='sha256:x',runtime={'path':'/code.py'})
  c=H.cpu_command(d,'/plan','p',1);self.assertNotIn('--device',c);self.assertNotIn('--privileged',c);self.assertNotIn('--rm',c)
  self.assertIn('type=bind,src=/raw,dst=/raw,readonly',c);self.assertIn('type=bind,src=/raw/cpu,dst=/raw/cpu',c)
  self.assertLess(c.index('A=2'),c.index('Z=1'));self.assertIn('-d',c)
 def fixture(self,r):
  raw=self.raw(r/'attempts/1');d={'out':str(r),'run':'run','chip':6};h=r/'host_attempts/1';a=r/'attempts/1';h.mkdir(parents=True);a.mkdir(parents=True,exist_ok=True)
  R.write(h/'CLAIM.json',dict(schema='r3-resource-claim-v1',run='run',chip=6));R.write(h/'LAUNCH_RECEIPT.json',dict(container_id='cid',plan_sha256='p'))
  R.write(h/'RELEASE.json',dict(schema='r3-resource-release-v1',claim_sha256=R.sha(h/'CLAIM.json'),container_id='cid',run='run',chip=6))
  R.write(h/'EXIT.json',dict(exit_code=0,container_exit_code=0,runner_terminal_matches=True,container_id='cid',scientific_acceptance=False));R.write(a/'EXIT.json',dict(exit_code=0,plan_sha256='p',attempt=1,scientific_acceptance=False));R.write(a/'RAW-MANIFEST.json',R.capture_manifest(raw.parent,'p'));R.write(a/'report.json',dict(schema='r3-profile-runtime-report-v1',plan_sha256='p',attempt=1,raw_manifest_sha256=R.sha(a/'RAW-MANIFEST.json'),all_raw_exact=True,test_read=False,scientific_acceptance=False,timing_claim=False));return d
 def test_release_required_and_generation_and_raw_rechecked(self):
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);d=self.fixture(r);R.released(d,'p')
   with self.assertRaisesRegex(ValueError,'generation'):R.released(d,'foreign')
   (r/'attempts/1/trace/worker_ascend_pt/FRAMEWORK/torch.op_range').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'raw changed'):R.released(d,'p')
 def test_capture_failure_prevents_parse(self):
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);d=self.fixture(r);R.write(r/'attempts/1/EXIT.json',dict(exit_code=1,plan_sha256='p',attempt=1))
   with self.assertRaisesRegex(ValueError,'capture failure'):R.released(d,'p')
 def test_parser_failure_has_terminal_and_preserves_raw(self):
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);d=self.fixture(r);p=r/'plan.json';R.write(p,d);before=R.snapshot(r/'attempts/1/trace/worker_ascend_pt')
   with patch.object(R,'verify',side_effect=ValueError('plan invalid')):
    with self.assertRaises(ValueError):R.parse(p,'p',1)
   self.assertEqual(R.read(r/'cpu/attempts/1/EXIT.json')['exit_code'],1);self.assertEqual(R.snapshot(r/'attempts/1/trace/worker_ascend_pt'),before)
   with self.assertRaises(FileExistsError):R.parse(p,'p',1)
 def test_capture_failure_writes_terminal(self):
  with tempfile.TemporaryDirectory() as x:
   p=Path(x)/'plan.json';R.write(p,{'out':x})
   with patch.object(R,'verify',side_effect=ValueError('bad plan')):
    with self.assertRaises(ValueError):R.run(p,'p',1)
   self.assertEqual(R.read(Path(x)/'attempts/1/EXIT.json')['exit_code'],1)
 def test_duplicate_cpu_event_rejected(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);(r/'cpu/host_attempts/1').mkdir(parents=True);d={'out':x,'parse_attempts':[1,2],'runtime':{}};a=SimpleNamespace(plan='p',sha256='h',review='r',review_sha256='r')
   with patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H,'module') as m:
    with self.assertRaisesRegex(ValueError,'exists'):H.start_cpu(a,1)
 def test_parser_failure_then_explicit_new_attempt_preserves_raw(self):
  import sys,types
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);d=self.fixture(r);d['max_process_number']=4;p=r/'plan.json';R.write(p,d)
   before=R.snapshot(r/'attempts/1/trace/worker_ascend_pt')
   def fail(*a,**k):raise RuntimeError('parse failure')
   fake=types.SimpleNamespace(profiler=types.SimpleNamespace(analyse=fail))
   with patch.object(R,'verify'),patch.object(R,'installed_profiler'),patch.dict(sys.modules,{'torch_npu':fake}):
    with self.assertRaises(RuntimeError):R.parse(p,'p',1)
   self.assertEqual(R.read(r/'cpu/attempts/1/EXIT.json')['exit_code'],1)
   def ok(path,**kw):
    out=Path(path)/'ASCEND_PROFILER_OUTPUT';out.mkdir()
    for n in ['kernel_details.csv','operator_details.csv','step_trace_time.csv']:(out/n).write_text('header\nvalue\n')
   fake.profiler.analyse=ok
   with patch.object(R,'verify'),patch.object(R,'installed_profiler'),patch.dict(sys.modules,{'torch_npu':fake}):R.parse(p,'p',2)
   self.assertEqual(R.read(r/'cpu/attempts/2/EXIT.json')['exit_code'],0);self.assertEqual(R.snapshot(r/'attempts/1/trace/worker_ascend_pt'),before)

 def parsed_fixture(self,r):
  d=self.fixture(r);a=r/'cpu/attempts/1';a.mkdir(parents=True);export=a/'worker_ascend_pt/ASCEND_PROFILER_OUTPUT';export.mkdir(parents=True)
  for n in R.EXPORTS:(export/n).write_text('header\nvalue\n')
  R.write(a/'EXIT.json',dict(exit_code=0,plan_sha256='p',attempt=1,scientific_acceptance=False))
  R.write(a/'report.json',dict(schema='r3-profile-offline-report-v1',plan_sha256='p',attempt=1,raw_manifest_sha256=R.sha(r/'attempts/1/RAW-MANIFEST.json'),exports={n:R.sha(export/n) for n in R.EXPORTS},scientific_acceptance=False,test_read=False,coverage_adjudicated=False))
  return d
 def test_manifest_foreign_and_report_pin_reject(self):
  with tempfile.TemporaryDirectory() as x:
   r=Path(x);d=self.fixture(r);m=r/'attempts/1/RAW-MANIFEST.json';old=R.read(m);foreign=self.raw(r/'foreign');R.write(m,R.capture_manifest(foreign.parent,'p'))
   report=R.read(r/'attempts/1/report.json');report['raw_manifest_sha256']=R.sha(m);R.write(r/'attempts/1/report.json',report)
   with self.assertRaisesRegex(ValueError,'outside'):R.released(d,'p')
   R.write(m,old)
   with self.assertRaisesRegex(ValueError,'binding'):R.released(d,'p')
 def test_container_failure_and_resource_schema_reject(self):
  for key,value in [('container_exit_code',9),('container_exit_code',False),('runner_terminal_matches',1)]:
   with self.subTest(key=key,value=value),tempfile.TemporaryDirectory() as x:
    r=Path(x);d=self.fixture(r);p=r/'host_attempts/1/EXIT.json';v=R.read(p);v[key]=value;R.write(p,v)
    with self.assertRaises(ValueError):R.released(d,'p')
 def test_cpu_terminal_and_report_tampering_reject(self):
  for mode in ['terminal','report','both','attempt','raw','exports','file']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as x:
    r=Path(x);d=self.parsed_fixture(r);R.parsed(d,'p',1);a=r/'cpu/attempts/1'
    if mode in ('terminal','both','attempt'):
     v=R.read(a/'EXIT.json');v['plan_sha256' if mode!='attempt' else 'attempt']='foreign' if mode!='attempt' else True;R.write(a/'EXIT.json',v)
    if mode in ('report','both','raw','exports'):
     v=R.read(a/'report.json');v[{'raw':'raw_manifest_sha256','exports':'exports'}.get(mode,'plan_sha256')]={} if mode=='exports' else 'foreign';R.write(a/'report.json',v)
    if mode=='file':(a/'worker_ascend_pt/ASCEND_PROFILER_OUTPUT/kernel_details.csv').write_text('changed')
    with self.assertRaises(ValueError):R.parsed(d,'p',1)
 def test_cpu_host_never_completes_foreign_generations(self):
  import types
  for mode in ['valid','terminal','report','both']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as x:
    r=Path(x);d=self.parsed_fixture(r);d.update(parse_attempts=[1,2],runtime={},container='c',image_sha256='img');h=r/'cpu/host_attempts/1';h.mkdir(parents=True)
    for name in ([] if mode=='valid' else ['EXIT.json'] if mode=='terminal' else ['report.json'] if mode=='report' else ['EXIT.json','report.json']):
     p=r/'cpu/attempts/1'/name;v=R.read(p);v['plan_sha256']='foreign';R.write(p,v)
    args=types.SimpleNamespace(plan='p',sha256='p',review='r',review_sha256='h',attempt=1)
    actual={'Id':'cid','Config':{'Cmd':['parse']},'HostConfig':{'Devices':[],'Privileged':False,'AutoRemove':False},'Image':'img','State':{'Status':'exited','ExitCode':0}}
    class Logger:
     def wait(self,**kw):return 0
    with patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H,'module',return_value=R),patch.object(H,'inspect',side_effect=[None,actual,actual]),patch.object(H,'cpu_command',return_value=['docker','run','img','parse']),patch.object(H.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)),patch.object(H.subprocess,'Popen',return_value=Logger()):H.supervise_cpu(args)
    self.assertEqual((r/'cpu/COMPLETE.json').exists(),mode=='valid');self.assertEqual(R.read(h/'EXIT.json')['exit_code'],0 if mode=='valid' else 1)
 def test_parsed_outputs_readable_for_host(self):
  with tempfile.TemporaryDirectory() as x:
   p=Path(x)/'worker';p.mkdir(mode=0o700);f=p/'data';f.write_text('ok');f.chmod(0o600);R.accessible_tree(p)
   self.assertEqual(p.stat().st_mode&0o777,0o755);self.assertEqual(f.stat().st_mode&0o777,0o644)

if __name__=='__main__':unittest.main()
