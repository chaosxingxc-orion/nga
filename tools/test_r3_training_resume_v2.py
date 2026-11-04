import unittest,tempfile,json,types,contextlib,io,sys
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent
def load(p):
 m=types.ModuleType(p.stem);m.__file__=str(p.resolve());exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
M=load(HERE/'r3_training_resume_v2.py')
class Contracts(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.out=self.root/'out';self.out.mkdir();self.qo=self.root/'qo';a=self.qo/'attempts/1';a.mkdir(parents=True)
  self.ref={'out':str(self.qo),'container':'qo','container_id':'id','claim_sha256':'claim','receipt_sha256':'receipt'}
  self.release={'run':'qo_run','allocation_after':{'free':[{'chip':3,'previous_run':'qo_run','release_evidence':str(a/'RELEASE.json')}]}}
  (a/'RELEASE.json').write_text(json.dumps(self.release));self.p={'out':str(self.out),'chip':3,'container':'pt','recovery':{'resource_predecessor':self.ref,'checkpoint':{'sha256':'ck'}}}
  (self.out/'SUCCESSOR_PRECONDITION.json').write_text(json.dumps({'release_sha256':M.sha(a/'RELEASE.json')}));self.R=types.SimpleNamespace(docker_inspect=lambda _:None,live_chip_conflict=lambda *_:False)
 def context(self):return patch.multiple(M,successor_binding=lambda *a:None,verify_review=lambda *a:None,verify_import=lambda *a,**k:None,ready=lambda *a:True)
 def test_exact_free_generation(self):
  with self.context():self.assertEqual(M.claim_precondition(self.p,'pin','pre',dict(allocation=[],free=self.release['allocation_after']['free']),self.R)['container_id'],'id')
 def test_foreign_generation_rejected(self):
  with self.context(),self.assertRaisesRegex(RuntimeError,'foreign free'):M.claim_precondition(self.p,'pin','pre',dict(allocation=[],free=[{'chip':3,'previous_run':'other','release_evidence':'other'}]),self.R)
 def test_missing_release_rejected(self):
  with self.context(),patch.object(M,'ready',return_value=False),self.assertRaisesRegex(RuntimeError,'not released'):M.claim_precondition(self.p,'pin','pre',dict(allocation=[],free=[]),self.R)
 def test_checkpoint_mutation_rejected_at_claim(self):
  with self.context(),patch.object(M,'verify_import',side_effect=RuntimeError('checkpoint changed')),self.assertRaisesRegex(RuntimeError,'checkpoint changed'):M.claim_precondition(self.p,'pin','pre',dict(allocation=[],free=[]),self.R)
 def test_live_conflict_rejected(self):
  self.R.live_chip_conflict=lambda *_:True
  with self.context(),self.assertRaisesRegex(RuntimeError,'conflict'):M.claim_precondition(self.p,'pin','pre',dict(allocation=[],free=self.release['allocation_after']['free']),self.R)
 def test_supervise_cli_absent(self):
  with patch.object(sys,'argv',['x','supervise','--plan','/p','--sha256','h']),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):M.main()
 def test_error_terminal(self):
  (self.out/'SERVICE-START-INTENT.json').write_text(json.dumps({'plan':'/p','sha256':'h'}))
  with patch.object(M,'read',side_effect=lambda x: {'out':str(self.out)} if str(x)=='/p' else json.loads(Path(x).read_text())),patch.object(M,'configure',side_effect=RuntimeError('bad verification')),self.assertRaisesRegex(RuntimeError,'bad verification'):M.watch('/p','h')
  self.assertEqual(json.loads((self.out/'SERVICE_EXIT.json').read_text())['exit_code'],1)
 def test_existing_launch_intent_refuses(self):
  (self.out/'LAUNCH-INTENT.json').write_text('{}')
  with patch.object(M,'read',return_value={'out':str(self.out)}),self.assertRaisesRegex(RuntimeError,'uncertain'):M.watch('/p','h')
 def test_real_resource_claim_refuses_foreign_lineage(self):
  base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_pt2_training_resume_20261104_v1/tools/r3_resource_adapter.py');R=load(base)
  alloc=self.root/'alloc.json';doc={'allocation':[],'free':[{'chip':3,'previous_run':'foreign','release_evidence':'/foreign'}]};alloc.write_text(json.dumps(doc));before=alloc.read_bytes()
  args=types.SimpleNamespace(alloc=str(alloc),run='pt',chip=3,proof=str(self.out/'CLAIM.json'),owner='test',purpose='test')
  with self.context(),patch.object(R,'successor_guard',return_value=lambda allocation:M.claim_precondition(self.p,'pin','pre',allocation,self.R)),self.assertRaisesRegex(RuntimeError,'foreign free'):R.claim(args)
  self.assertEqual(alloc.read_bytes(),before);self.assertFalse((self.out/'CLAIM.json').exists())
 def test_duplicate_watch_does_not_write_terminal(self):
  import fcntl
  with (self.out/'service.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with patch.object(M,'read',return_value={'out':str(self.out)}),self.assertRaises(BlockingIOError):M.watch('/p','h')
  self.assertFalse((self.out/'SERVICE_EXIT.json').exists())
 def test_driver_import_mutation(self):
  D=load(HERE/'r3_training_resume_driver_v2.py');(self.out/'ckpt').mkdir();(self.out/'ckpt/step_002400.pt').write_bytes(b'changed');(self.out/'losses.jsonl').write_bytes(b'loss')
  self.p['recovery']['loss_prefix']={'sha256':'no'}
  with self.assertRaisesRegex(RuntimeError,'imports differ'):D.validate(self.p)
if __name__=='__main__':unittest.main()
