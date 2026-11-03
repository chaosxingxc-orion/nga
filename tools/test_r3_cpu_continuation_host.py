import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from tools import r3_cpu_continuation_host as H

class Host(unittest.TestCase):
 def fixture(self,root):
  binary=root/'bin';binary.mkdir();docker=binary/'docker'
  docker.write_text('''#!/usr/bin/env python3
import os,json,sys,time
from pathlib import Path
c=json.loads(Path(os.environ['NGA_HOST_TEST_FIXTURE']).read_text());op=sys.argv[1]
if op=='run':print('a'*64)
elif op=='inspect':print(json.dumps([{'Image':c['image'],'Config':{'Cmd':['worker']},'HostConfig':{'Devices':[],'Privileged':False,'AutoRemove':False}}]))
elif op=='logs':print('CPU fixture stage')
elif op=='wait':
 time.sleep(1)
 Path(c['runtime_terminal']).write_text(json.dumps({'exit_code':0,'config_sha256':c['config_sha256']}))
 print(0)
''');docker.chmod(0o755)
  c={'image':'sha256:fixture','config_sha256':'f'*64,'host_output':str(root/'host'),'runtime_terminal':str(root/'runtime.EXIT.json'),'docker_command':['docker','run','-d','sha256:fixture','worker'],'files':{}}
  p=root/'OPS.json';p.write_text(json.dumps(c));return p,c,{'PATH':str(binary)+os.pathsep+os.environ['PATH'],'NGA_HOST_TEST_FIXTURE':str(p)}
 def wait_end(self,root):
  until=time.monotonic()+5
  while time.monotonic()<until:
   if (root/'EXIT.json').exists():return H.read(root/'EXIT.json')
   time.sleep(.02)
  self.fail('fixture did not terminate')
 def test_inherited_lock_survives_delayed_parent_and_duplicate(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,env=self.fixture(Path(t));root=Path(c['host_output']);real=subprocess.Popen;children=[]
   def delayed(*args,**kwargs):
    child=real(*args,**kwargs);children.append(child);time.sleep(.3);self.assertIsNone(child.poll());return child
   with patch.dict(os.environ,env),patch.object(H.subprocess,'Popen',side_effect=delayed):H.execute('start',p,H.sha(p))
   service=H.read(root/'SERVICE.json');self.assertEqual(H.identity(service['pid']),{k:service[k] for k in ('pid','boot_id','start_ticks')})
   self.assertEqual((Path('/proc')/str(service['pid'])/'cmdline').read_bytes().split(b'\0')[:-1],[x.encode() for x in service['command']])
   with patch.dict(os.environ,env),self.assertRaises((BlockingIOError,ValueError)):H.execute('start',p,H.sha(p))
   self.assertFalse((root/'EXIT.json').exists());self.assertEqual(self.wait_end(root)['exit_code'],0);children[0].wait(timeout=2)
   self.assertIn('CPU fixture stage',(root/'runtime.log').read_text())
   before=(root/'EXIT.json').read_bytes()
   with patch.dict(os.environ,env),self.assertRaises(ValueError):H.execute('start',p,H.sha(p))
   self.assertEqual(before,(root/'EXIT.json').read_bytes())
 def test_pinned_dependency_failure_has_host_log_heartbeat_terminal(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,env=self.fixture(Path(t));c['files']={str(Path(t)/'absent'):'x'};p.write_text(json.dumps(c));root=Path(c['host_output'])
   with self.assertRaises(FileNotFoundError):H.execute('start',p,H.sha(p))
   self.assertEqual(H.read(root/'EXIT.json')['exit_code'],1);self.assertTrue((root/'heartbeat.json').exists());self.assertIn('host_failed',(root/'supervisor.log').read_text());self.assertFalse((root/'START.json').exists())
 def test_untrusted_config_pin_has_no_output(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,env=self.fixture(Path(t))
   with self.assertRaises(ValueError):H.execute('start',p,'wrong')
   self.assertFalse(Path(c['host_output']).exists())
 def test_run_without_handoff_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,env=self.fixture(Path(t))
   with self.assertRaisesRegex(ValueError,'inherited lock'):H.execute('run',p,H.sha(p))
   self.assertFalse((Path(c['host_output'])/'START.json').exists())
if __name__=='__main__':unittest.main()
