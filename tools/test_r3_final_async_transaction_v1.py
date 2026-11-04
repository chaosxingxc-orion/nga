"""Synthetic first-consumption and recovery tests; no TEST or NPU access."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('async_test',Path(__file__).with_name('r3_final_async_transaction_v1.py'))
X=importlib.util.module_from_spec(spec);spec.loader.exec_module(X)

class Async(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.owner=dict(model_sha256='a'*64,execution_sha256='b'*64,final_sha256='c'*64,run_dir=str(self.root/'run'))
  self.report={'source':'synthetic','scores':[.5,.75]};self.results={s:{'n':n,'headline_accuracy':.5,'producer_report_sha256':X.G.digest(self.report)} for s,n in zip(X.SUITES,(1200,656))}
  self.log={};self.calls=[];self.released=False;self.manifest=None
  def scoring(suites):
   self.calls.append('score');X.G.atomic(self.root/'run/TEST-PRODUCER-REPORT.json',self.report);return self.results
  self.score=Mock(side_effect=scoring)
 def stage(self):
  return X.score_phase(str(self.root/'round'),owner=self.owner,validate_admission=lambda:None,
   score=self.score,read_completion=lambda s:self.log.get(s),bind_execution=lambda a,b:None)
 def release(self):
  doc=X.load_scored(self.root/'run',self.owner);self.manifest=X.G.digest(doc);self.released=True
 def check_release(self,owner,pin):
  if not self.released or owner!=self.owner or pin!=self.manifest:raise ValueError('no matching successful actual release')
 def verify(self,s,r):
  self.calls.append('verify:'+s)
  if r!=self.results[s]:raise ValueError('bad source/readout')
 def consume(self,**changes):
  kw=dict(owner=self.owner,validate_admission=lambda:None,validate_release=self.check_release,
   verify_result=self.verify,read_completion=lambda s:self.log.get(s),append_completion=lambda s,r:self.log.__setitem__(s,r),
   bind_execution=lambda a,b:None,validate_publication=lambda:None)
  return X.consume(str(self.root/'round'),**dict(kw,**changes))
 def test_first_consume_after_release_no_scoring_and_two_checks(self):
  self.stage();self.assertFalse(self.log);self.assertFalse((self.root/'run/TEST-STAGED-RESULTS.json').exists())
  self.release();out=self.consume();self.assertEqual(out['state'],'completed');self.score.assert_called_once()
  for s in X.SUITES:self.assertEqual(self.calls.count('verify:'+s),2)
  self.assertEqual(set(self.log),set(X.SUITES))
 def test_no_release_never_verifies_or_publishes(self):
  self.stage()
  with self.assertRaisesRegex(ValueError,'release'):self.consume()
  self.assertEqual(self.calls,['score']);self.assertFalse(self.log)
 def test_rescore_attempt_after_scoring_failure_refused(self):
  self.score.side_effect=RuntimeError('interrupted scoring')
  with self.assertRaises(RuntimeError):self.stage()
  with self.assertRaisesRegex(ValueError,'no blind rescore'):self.stage()
  self.score.assert_called_once()
 def test_stage_recovery_no_rescore(self):
  self.stage();self.stage();self.score.assert_called_once()
 def test_second_verification_fails_before_any_publication(self):
  self.stage();self.release();count=[0]
  def verify(s,r):
   count[0]+=1
   if count[0]==4:raise ValueError('changed readout')
  with self.assertRaisesRegex(ValueError,'changed'):self.consume(verify_result=verify)
  self.assertFalse(self.log);self.consume();self.score.assert_called_once()
 def test_partial_cpu_commit_recovers_without_scoring(self):
  self.stage();self.release()
  def append(s,r):
   self.log[s]=r;raise RuntimeError('after log')
  with self.assertRaises(RuntimeError):self.consume(append_completion=append)
  self.consume();self.consume();self.score.assert_called_once();self.assertEqual(len(self.log),2)
 def test_report_mutation_rejected_before_verification(self):
  self.stage();self.release();X.G.atomic(self.root/'run/TEST-PRODUCER-REPORT.json',{'mutated':True})
  with self.assertRaisesRegex(ValueError,'producer'):self.consume()
  self.assertEqual(self.calls,['score']);self.assertFalse(self.log)
 def test_manifest_owner_and_missing_suite_rejected(self):
  self.stage();self.release();p=self.root/'run'/X.SCORED;old=json.loads(p.read_text())
  for kind in ('owner','suite','producer'):
   d=json.loads(json.dumps(old))
   if kind=='owner':d['owner']['execution_sha256']='f'*64
   elif kind=='suite':del d['results'][X.SUITES[1]]
   else:d['producer_report_sha256']='f'*64
   X.G.atomic(p,d)
   with self.assertRaises(ValueError):self.consume()
  self.assertEqual(self.calls,['score']);self.assertFalse(self.log)
 def test_release_revocation_before_publication_blocks(self):
  self.stage();self.release();calls=[0]
  def release(owner,pin):
   calls[0]+=1
   if calls[0]==2:raise ValueError('release changed')
  with self.assertRaisesRegex(ValueError,'release changed'):self.consume(validate_release=release)
  self.assertFalse(self.log)
 def test_changed_verified_stage_and_log_refused(self):
  self.stage();self.release();self.consume();p=self.root/'run/TEST-STAGED-RESULTS.json';d=json.loads(p.read_text());d['results'][X.SUITES[0]]['n']=1;X.G.atomic(p,d)
  with self.assertRaisesRegex(ValueError,'stage differs'):self.consume()
 def test_completed_without_manifest_refused_no_rescore(self):
  self.stage();self.release();self.consume();(self.root/'run'/X.SCORED).unlink()
  with self.assertRaisesRegex(ValueError,'no blind rescore'):self.stage()
  self.score.assert_called_once()

if __name__=='__main__':unittest.main()
