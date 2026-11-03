import tempfile,unittest,json
from unittest.mock import patch
from pathlib import Path
from tools import r3_eval_profile_runtime as R
from tools import r3_eval_profile_probe as P
from tools import r3_eval_profile_host as H
from tools.test_r3_eval_profile_probe import FakeFrozenScorer
class RuntimeTests(unittest.TestCase):
 def cells(self):return {'K/a':[{'id':'a','row':{'levels':[{},{}]}}],'K/b':[{'id':'b','row':{'levels':[{},{}]}}]}
 def test_full_and_resume_do_not_repeat_completed_chunks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'attempts/1').mkdir(parents=True)
   a=R.batches(P,FakeFrozenScorer(),self.cells(),root,1,'a'*64);self.assertEqual(len(a['trials']),14);self.assertTrue(a['timing_comparable'])
   (root/'attempts/2').mkdir();s=FakeFrozenScorer();b=R.batches(P,s,self.cells(),root,2,'a'*64);self.assertEqual(b['reused_chunks'],14);self.assertFalse(b['timing_comparable']);self.assertEqual(s.stats['tokens'],0)
 def test_changed_saved_operand_rejects(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'attempts/1').mkdir(parents=True);R.batches(P,FakeFrozenScorer(),self.cells(),root,1,'a'*64)
   target=next((root/'items/cold_reference').glob('*.receipt.json'));r=R.read(target);r['plan_sha256']='b'*64;R.write(target,r)
   (root/'attempts/2').mkdir()
   with self.assertRaises(ValueError):R.batches(P,FakeFrozenScorer(),self.cells(),root,2,'a'*64)
 def test_interrupted_batch_recovers_without_repeating_completed(self):
  class Fail(FakeFrozenScorer):
   def score_raw(self,*a,**k):
    if self.stats['tokens']>=3:raise RuntimeError('interrupted')
    return super().score_raw(*a,**k)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'attempts/1').mkdir(parents=True)
   with self.assertRaises(RuntimeError):R.batches(P,Fail(),self.cells(),root,1,'a'*64)
   (root/'attempts/2').mkdir();b=R.batches(P,FakeFrozenScorer(),self.cells(),root,2,'a'*64);self.assertEqual(b['reused_chunks'],1);self.assertFalse(b['timing_comparable'])
 def test_preload_failure_writes_terminal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'plan.json';p.write_text(json.dumps({'out':d}))
   with patch.object(R,'verify',side_effect=RuntimeError('loader dependency')):
    with self.assertRaises(RuntimeError):R.run(p,'a'*64,1)
   self.assertEqual(R.read(Path(d)/'attempts/1/EXIT.json')['exit_code'],1)
 def test_retained_detached_command_is_single_chip(self):
  d={'container':'nga-r3-profile-test','chip':6,'environment':{},'mounts':[],
     'image_sha256':'sha256:aaa','runtime':{'path':'/runtime.py'}}
  cmd=H.command(d,'/plan.json','a'*64,1)
  self.assertIn('-d',cmd);self.assertNotIn('--rm',cmd);self.assertIn('/dev/davinci6',cmd)
  self.assertIn('--pull=never',cmd);self.assertIn('--network=none',cmd)
  self.assertEqual(cmd[cmd.index(d['image_sha256'])+1:],['python3','-B','-P','/runtime.py','run','--plan','/plan.json','--sha256','a'*64,'--attempt','1'])
 def test_existing_attempt_blocks_duplicate_start(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'host_attempts/1').mkdir(parents=True)
   with self.assertRaisesRegex(ValueError,'attempt exists'):H.previous({'out':d},1)
 def test_successful_previous_attempt_cannot_resume(self):
  with tempfile.TemporaryDirectory() as d:
   h=Path(d)/'host_attempts/1';h.mkdir(parents=True)
   claim={'run':'r','chip':6};R.write(h/'CLAIM.json',claim)
   R.write(h/'RELEASE.json',{'schema':'r3-resource-release-v1','run':'r','chip':6,'claim_sha256':R.sha(h/'CLAIM.json'),'container_id':'cid'})
   R.write(h/'EXIT.json',{'container_id':'cid','exit_code':0})
   with patch.object(H,'inspect',return_value={'Id':'cid','State':{'Status':'exited'}}):
    with self.assertRaisesRegex(ValueError,'completed run'):H.previous({'out':d,'container':'c','run':'r','chip':6},2)
if __name__=='__main__':unittest.main()
