import copy, json, sys, unittest
from pathlib import Path
from contextlib import ExitStack
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_unified_container_host_v1 as fixture
import unified_container_host_v1 as host

class AttemptHost(unittest.TestCase):
 def setUp(self):
  self.f=fixture.HostTest(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
  self.c=self.f.host(self.f.c,'attempt-v5'); self.d=fixture.FakeDocker(self.f.q)
  with ExitStack() as stack: self.meta=host.establish_owner(self.c,stack)
  self.terminal=self.meta/'terminal.json'; self.terminal.write_bytes(b'{"historical":true}\n')
  (self.meta/'cpu-handoff.json').write_bytes(b'{"historical":true}\n')
 def test_bound_rejections_and_historical_evidence(self):
  configs=[]
  for name in ('reject-one','reject-two'):
   c=copy.deepcopy(self.c);c['name']=name;configs.append(c)
   with self.assertRaisesRegex(ValueError,'launch identity'):host.run(c,self.d)
  records=[json.loads(p.read_text()) for p in self.meta.glob('attempt-failure-*.json')]
  self.assertEqual({x['attempted_config_sha256'] for x in records},{host.U.digest(c) for c in configs})
  self.assertEqual({x['intended_launch_sha256'] for x in records},{host.U.digest(host.launch_spec(c)) for c in configs})
  for r in records:
   self.assertTrue((self.meta/('attempt-failure-'+r['attempt_id']+'.json')).exists());self.assertTrue(r['nonlaunch']);self.assertEqual(r['stage'],'validation');self.assertEqual(r['historical_terminal'],'not_the_result_of_this_attempt');self.assertIn('attempted_input_ref',r)
  self.assertEqual(self.terminal.read_bytes(),b'{"historical":true}\n');self.assertEqual((self.meta/'cpu-handoff.json').read_bytes(),b'{"historical":true}\n');self.assertFalse(self.d.objects)
 def test_malformed_foreign_symlink_and_write_error(self):
  for value in (None,{}, {'output':42}, {'output':'/tmp/../tmp'}):
   with self.assertRaises(Exception): host.run(value,self.d)
  c=copy.deepcopy(self.c);c['name']='reject';owner=self.meta/'OWNER.json';saved=owner.read_bytes();owner.write_text('{}')
  with self.assertRaisesRegex(ValueError,'launch identity'):host.run(c,self.d)
  self.assertFalse(list(self.meta.glob('attempt-failure-*')));owner.write_bytes(saved)
  with mock.patch.object(host.R,'write_atomic',side_effect=OSError('disk')):
   with self.assertRaisesRegex(ValueError,'launch identity'):host.run(c,self.d)
  link=self.meta.parent/'link';link.symlink_to(self.meta,target_is_directory=True)
  c['output']=str(link/'..'/'absent')
  with self.assertRaises(Exception):host.run(c,self.d)
  self.assertFalse(list(self.meta.glob('attempt-failure-*')))
if __name__=='__main__':unittest.main()
