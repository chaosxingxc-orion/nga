import unittest,types,tempfile,json
from pathlib import Path
class HostTests(unittest.TestCase):
 def setUp(self):
  p=Path(__file__).with_name('bev_native_matched_host_v1.py');self.M=types.ModuleType('host');self.M.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),self.M.__dict__);self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.d={'out':str(self.root)}
 def test_fresh_attempt(self):self.M.previous(self.d,1,'pin')
 def test_second_attempt_refused(self):
  with self.assertRaisesRegex(ValueError,'attempt1'):self.M.previous(self.d,2,'pin')
 def test_existing_host_refused(self):
  (self.root/'host_attempts').mkdir()
  with self.assertRaisesRegex(ValueError,'never resume'):self.M.previous(self.d,1,'pin')
 def test_existing_timing_refused(self):
  (self.root/'measurement').mkdir()
  with self.assertRaisesRegex(ValueError,'never resume'):self.M.previous(self.d,1,'pin')
 def test_direct_supervise_without_intent_refused(self):
  self.M.verify=lambda *x:self.d;self.M.original_supervise=lambda *x:self.fail('base called')
  a=types.SimpleNamespace(plan='p',sha256='h',review='r',review_sha256='rh',attempt=1)
  with self.assertRaisesRegex(ValueError,'intent required'):self.M.supervise(a)
 def test_claimed_attempt_cannot_replay(self):
  self.M.verify=lambda *x:self.d;self.M.original_supervise=lambda *x:self.fail('base called');a=types.SimpleNamespace(plan='p',sha256='h',review='r',review_sha256='rh',attempt=1);h=self.root/'host_attempts/1';h.mkdir(parents=True)
  cmd=[self.M.H.sys.executable,'-B','-P',str(Path(self.M.__file__).resolve()),'supervise','--plan','p','--sha256','h','--review','r','--review-sha256','rh','--attempt','1'];(h/'START_INTENT.json').write_text(json.dumps({'command':cmd}));(h/'CLAIM.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'cannot replay'):self.M.supervise(a)
if __name__=='__main__':unittest.main()
