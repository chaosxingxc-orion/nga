import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import exporter,integration,watcher,collector

class Integration(unittest.TestCase):
 def test_pending_does_not_read_payload(self):
  with tempfile.TemporaryDirectory() as d, patch.object(integration,'capture_populations',side_effect=AssertionError('read')):
   cfg={'configs':{r:str(Path(d)/r) for r in collector.ROLES}}
   self.assertEqual(watcher.tick(cfg,d)['status'],'pending')
 def test_changed_capture_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);collector.save(p/'CAPTURE.json',{'populations':{}});collector.save(p/'COMPLETE.json',{'capture_sha256':'0'*64})
   with self.assertRaisesRegex(ValueError,'capture hash'):integration.capture_populations({'export_dir':d})
 def test_observation_requires_retained_container(self):
  with tempfile.TemporaryDirectory() as d:
   cfg={'configs':{r:str(Path(d)/(r+'.json')) for r in collector.ROLES}}
   launch=Path(d)/'launch';collector.save(launch,{'id':'abc'})
   for r in collector.ROLES:collector.save(cfg['configs'][r],{'container':{'spec':{},'launch_receipt':str(launch)}})
   class K:
    @staticmethod
    def verify_observation(spec,obs,cid):
     if obs['Id']!=cid:raise ValueError('container identity')
   obs=[{'Id':'abc','State':{'Status':'running','ExitCode':0}}]
   with patch.object(integration.subprocess,'check_output',return_value=json.dumps(obs)):
    with self.assertRaisesRegex(ValueError,'retained container'):integration.observations(cfg,d,K)
if __name__=='__main__':unittest.main()

class ActualProducerCapture(unittest.TestCase):
 def test_real_cpu_captures_frozen_fixture(self):
  import importlib.util
  ref=Path(__file__).resolve().parents[3]/'science/same-test-reference-fix'
  spec=importlib.util.spec_from_file_location('producer_fixture',ref/'fixture.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  ns,m=mod.helpers();f=ns['FrozenFixture']('test_real_two_phase_persistence_and_roles');f.setUp()
  try:
   f.c.update(schema='fixture',protocol={},manifest={},source_files={},image='fixture')
   ready=f.infer();root=f.root/'export'
   report=m.cpu(f.c,verify_fn=lambda c,i,d,x:exporter.capture(m,c,i,d,x,root))
   self.assertEqual(len(report['test_reads']),2)
   captured=collector.read(root/'CAPTURE.json');self.assertEqual(len(captured['populations']),6)
   for key,p in captured['populations'].items():
    suite,partition,kind=key.split('/');src=f.data/(suite+'/'+partition+('.variants' if kind=='variants' else '')+'.jsonl')
    expected=[json.loads(line) for line in src.read_text().splitlines()]
    self.assertEqual(collector.read(p['path']),expected)
  finally:f.tearDown()
