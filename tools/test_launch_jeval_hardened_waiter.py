import copy, hashlib, importlib.util, json, runpy, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(__file__).with_name('launch_jeval_hardened_waiter.py').read_text()
WAITER=Path(__file__).with_name('jeval_hardened_waiter.py').read_text()
class Guards(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
  (self.p/'launch.py').write_text(SOURCE);(self.p/'jeval_hardened_waiter.py').write_text(WAITER);(self.p/'run.sh').write_text('exit 0')
  self.binds=[str(self.p.parent)+':'+str(self.p.parent)+':ro',str(self.p)+':'+str(self.p)+':rw','/var/run/docker.sock:/var/run/docker.sock:ro']
  self.spec={'Config':{'Cmd':['run.sh'],'Entrypoint':['bash'],'Env':[]},'HostConfig':{'Binds':self.binds,'Devices':[],'NetworkMode':'none','ShmSize':67108864}}
  self.write('CONTAINER_SPEC.json',self.spec)
  self.plan=dict(container='fixture',image='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7',files={},wrapper=str(self.p/'run.sh'))
  self.write('plan.json',self.plan);self.ph=hashlib.sha256((self.p/'plan.json').read_bytes()).hexdigest();self.write('PARENT_REVIEW.json',dict(approved_plan_sha256=self.ph))
  self.d=dict(Id='fixture-id',Name='/fixture',Image=self.plan['image'],Config=dict(self.spec['Config'],Labels={'nga.waiter.plan':self.ph}),HostConfig=self.spec['HostConfig'],State=dict(Status='created',ExitCode=0,FinishedAt='now'),Mounts=[dict(Type='bind',Source=b.split(':')[0],Destination=b.split(':')[1],RW=b.split(':')[2]=='rw') for b in self.binds])
  spec=importlib.util.spec_from_file_location('launcher_fixture',self.p/'launch.py');self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
  original_mount_check=self.module.w.cpu_mount_binding
  self.module.w.cpu_mount_binding=lambda d,p:original_mount_check(d,p,self.p.parent)
 def tearDown(self):self.t.cleanup()
 def write(self,n,x):(self.p/n).write_text(json.dumps(x))
 def runlaunch(self,resume=False):
  with patch('sys.argv',['launch.py']+(['--resume'] if resume else [])),patch.object(self.module,'lookup_container',return_value=self.d),patch('subprocess.check_call') as start:
   try:self.module.launch(self.p,resume)
   except SystemExit as e:
    if e.code:raise
   return start.call_count
 def receipt(self):self.write('LAUNCH_RECEIPT.json',dict(container_id='fixture-id',plan_sha256=self.ph,wrapper_sha256=hashlib.sha256((self.p/'run.sh').read_bytes()).hexdigest()))
 def test_created_gap_adopts_owned_only(self):self.assertEqual(self.runlaunch(),1)
 def test_foreign_label_rejected(self):
  self.d['Config']['Labels']={}
  with self.assertRaisesRegex(ValueError,'ownership'):self.runlaunch()
 def test_terminal_preserved(self):
  self.write('COMPLETE.json',{'rc':1})
  with self.assertRaisesRegex(ValueError,'terminal'):self.runlaunch()
 def test_running_no_duplicate(self):
  self.receipt();self.d['State']['Status']='running';self.assertEqual(self.runlaunch(True),0)
 def test_reviewed_exit_with_published_report_can_resume(self):
  self.receipt();self.d['State'].update(Status='exited',ExitCode=137);(self.p/'EXIT').write_text('rc=137 utc=now\n');self.write('HARDENED_AUDIT.json',{'existing':'evidence'})
  self.write('RESUME_REVIEW.json',dict(approved_plan_sha256=self.ph,container_id='fixture-id',finished_at='now',exit_sha256=hashlib.sha256((self.p/'EXIT').read_bytes()).hexdigest()))
  self.assertEqual(self.runlaunch(True),1);self.assertEqual(json.loads((self.p/'HARDENED_AUDIT.json').read_text()),{'existing':'evidence'})
 def test_unreviewed_exit_rejected(self):
  self.receipt();self.d['State'].update(Status='exited',ExitCode=137)
  with self.assertRaises(FileNotFoundError):self.runlaunch(True)
 def test_changed_finished_at_rejected(self):
  self.receipt();self.d['State'].update(Status='exited',ExitCode=137);self.write('RESUME_REVIEW.json',dict(approved_plan_sha256=self.ph,container_id='fixture-id',finished_at='old',exit_sha256=None))
  with self.assertRaisesRegex(ValueError,'review differs'):self.runlaunch(True)
 def test_extra_device_exposures_rejected(self):
  for key,value in [('Privileged',True),('DeviceRequests',[{}]),('DeviceCgroupRules',['c *:* rwm']),('Mounts',[{}]),('CapAdd',['SYS_ADMIN']),('PidMode','host'),('IpcMode','host'),('CgroupnsMode','host')]:
   self.d['HostConfig']=copy.deepcopy(self.spec['HostConfig']);self.d['HostConfig'][key]=value
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exposure'):self.runlaunch()
 def test_daemon_failure_not_treated_as_absence(self):
  with patch('sys.argv',['launch.py']),patch.object(self.module,'lookup_container',side_effect=ConnectionError('Cannot connect to daemon')),patch('subprocess.check_output') as create:
   with self.assertRaisesRegex(ConnectionError,'Cannot connect'):self.module.launch(self.p)
   create.assert_not_called()
 def test_http404_creates_absent_container(self):
  with patch.object(self.module,'lookup_container',side_effect=[None,self.d]),patch('subprocess.check_output',return_value='fixture-id\n') as create,patch('subprocess.check_call') as start:
   self.module.launch(self.p)
   self.assertEqual(create.call_args.args[0][:2],['docker','create']);start.assert_called_once_with(['docker','start','fixture-id'])
 def test_http_lookup_only404_is_absence(self):
  from unittest.mock import MagicMock
  for status in [200,404,403,500]:
   connection=MagicMock();response=connection.getresponse.return_value
   response.status=status;response.read.return_value=json.dumps(self.d).encode()
   with self.subTest(status=status),patch.object(self.module.http.client,'HTTPConnection',return_value=connection),patch.object(self.module.socket,'socket'):
    if status in [403,500]:
     with self.assertRaisesRegex(ValueError,'absence not established'):self.module.lookup_container('fixture')
    else:self.assertEqual(self.module.lookup_container('fixture'),self.d if status==200 else None)
    connection.close.assert_called_once()
 def test_http_connection_failure_cannot_create(self):
  with patch.object(self.module.socket,'socket') as sock,patch('subprocess.check_output') as create:
   sock.return_value.connect.side_effect=ConnectionError('socket unavailable')
   with self.assertRaisesRegex(ConnectionError,'socket unavailable'):self.module.launch(self.p)
   create.assert_not_called()
 def test_writable_source_bind_rejected(self):
  self.d['HostConfig']['Binds'][0]=str(self.p.parent)+':'+str(self.p.parent)+':rw'
  self.write('CONTAINER_SPEC.json',self.spec)
  with self.assertRaisesRegex(ValueError,'bind allowlist'):self.runlaunch()
 def test_device_bind_rejected(self):
  self.d['HostConfig']['Binds'].append('/dev:/host-dev:ro')
  self.write('CONTAINER_SPEC.json',self.spec)
  with self.assertRaisesRegex(ValueError,'bind allowlist'):self.runlaunch()
 def test_effective_mount_rw_change_rejected(self):
  self.d['Mounts'][0]['RW']=True
  with self.assertRaisesRegex(ValueError,'effective mounts'):self.runlaunch()
 def test_success_terminal_interrupted_wrapper_can_resume(self):
  self.write('COMPLETE.json',dict(rc=0,plan_sha256=self.ph))
  self.receipt();self.d['State'].update(Status='exited',ExitCode=137)
  self.write('RESUME_REVIEW.json',dict(approved_plan_sha256=self.ph,container_id='fixture-id',finished_at='now',exit_sha256=None))
  self.assertEqual(self.runlaunch(True),1)
if __name__ == '__main__':
 unittest.main()
