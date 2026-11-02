"""Real staged queue + role binder, synthetic TRAIN/review receipts; CPU only."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import test_r3_formal_wave_prepare as fixture
P,mod,write=fixture.P,fixture.mod,fixture.write

class HandoffTests(unittest.TestCase):
 setUp=fixture.StageTests.setUp
 reviews=fixture.StageTests.reviews
 advance=fixture.StageTests.advance
 def setup_handoff(self):
  self.final=self.advance();self.hpath=Path(self.final['handoff']);self.hpin=self.final['handoff_sha256']
  self.H=mod(self.root/'source/tools/r3_formal_wave_handoff.py');self.b,self.jobs,_=self.H.identity(str(self.hpath),self.hpin)
 def complete(self,role):
  H=self.H;j=self.jobs[role];root=Path(j['training']);p=P.load(root/'plan.json');a=root/'attempts/1'
  end=dict(exit_code=0,attempt=1,started_utc='start',finished_utc='end',scientific_acceptance=False)
  write(root/'TRAIN_EXIT.json',end);write(a/'EXIT.json',end);write(a/'CLAIM.json',dict(run=p['run'],chip=p['chip']))
  write(a/'RELEASE.json',dict(schema='r3-resource-release-v1',run=p['run'],chip=p['chip'],container=p['container']+'-a1',container_id='fixture-'+role,
   claim_sha256=P.sha(a/'CLAIM.json'),exit_code=0,scientific_acceptance=False))
  write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False));write(a/'LAUNCH_RECEIPT.json',dict(id='fixture-'+role,image=p['image_sha256'],plan_sha256=j['canonical_plan_sha256']))
  for name in H.EXTRA[2:]:
   if name=='attempts/1/LAUNCH_RECEIPT.json':continue
   write(root/name,dict(synthetic=True))
  write(root/'manifest.json',dict(summary={'final_step':3116},arm='k1',model_path=p['model'],args=dict(arm='k1',seed=p['seed'],model_path=p['model'])))
  write(root/'adapter/adapter_config.json',{});(root/'adapter/adapter_model.safetensors').write_bytes(b'synthetic adapter')
 def postreview(self,role):
  state=Path(self.b['state_root'])/role;captured=P.load(state/'CAPTURE.json');j=self.jobs[role]
  evidence=self.base/('post-'+role+'-evidence.json');write(evidence,dict(synthetic=True))
  review=dict(schema='r3-formal-independent-postrun-v1',verdict='PASS',independent=True,training=j['training'],
   queue_sha256=self.b['queue']['sha256'],binding_sha256=self.hpin,capture_sha256=P.sha(state/'CAPTURE.json'),files=captured['files'],test_read=False,scientific_acceptance=False,
   evidence_files={str(evidence):P.sha(evidence)},checks={k:True for k in ('genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116')},synthetic=True)
  path=self.base/('post-'+role+'-review.json');write(path,review);return path
 def test_all_roles_real_binder_after_explicit_review(self):
  self.setup_handoff()
  for role in P.ROLES:self.complete(role)
  _,d=self.H.cycle(str(self.hpath),self.hpin);self.assertTrue(all(x['status']=='REVIEW_REQUIRED' for x in d['jobs'].values()))
  for role in P.ROLES:
   self.assertFalse(Path(self.jobs[role]['fresh_eval_out']).exists());r=self.postreview(role);self.H.inject(str(self.hpath),self.hpin,role,str(r),P.sha(r))
  d=self.H.watch(str(self.hpath),self.hpin,once=True)
  self.assertTrue(all(x['status']=='prepared' for x in d['jobs'].values()))
  for role in P.ROLES:
   spec=P.load(Path(self.jobs[role]['fresh_eval_out'])/'plan.json')
   self.assertEqual(spec['training_variant']['formal_role_identity']['role'],role)
   self.assertEqual(spec['training_variant']['seed'],3 if role=='primary_s3' else 2)
   self.assertEqual(spec['execution_review'],'PENDING');self.assertEqual(spec['chip_assignment'],'PENDING')
   self.assertFalse((Path(self.jobs[role]['fresh_eval_out'])/'execution.json').exists())
  self.H.watch(str(self.hpath),self.hpin,once=True)
 def test_missing_review_does_not_block_other_role_capture(self):
  self.setup_handoff();self.complete('primary_s3');_,d=self.H.cycle(str(self.hpath),self.hpin)
  self.assertEqual(d['jobs']['primary_s3']['status'],'REVIEW_REQUIRED');self.assertEqual(d['jobs']['primary_s2']['status'],'waiting_training')
 def test_wrong_seed_and_adapter_mutation_fail_closed(self):
  self.setup_handoff();self.complete('primary_s3');p=Path(self.jobs['primary_s3']['training'])/'manifest.json';v=P.load(p);v['args']['seed']=2;write(p,v)
  _,d=self.H.cycle(str(self.hpath),self.hpin);self.assertEqual(d['jobs']['primary_s3']['status'],'needs_repair')
  self.assertFalse(Path(self.jobs['primary_s3']['fresh_eval_out']).exists())
 def test_wrong_review_checks_no_prepare(self):
  self.setup_handoff();self.complete('diffchip_s2');self.H.cycle(str(self.hpath),self.hpin);r=self.postreview('diffchip_s2');v=P.load(r);v['checks']['retained_container_identity']=False;write(r,v)
  with self.assertRaisesRegex(ValueError,'incomplete'):self.H.inject(str(self.hpath),self.hpin,'diffchip_s2',str(r),P.sha(r))
  self.assertFalse(Path(self.jobs['diffchip_s2']['fresh_eval_out']).exists())
 def test_uncertain_binder_intent_never_retried(self):
  self.setup_handoff();role='samechip_s2';self.complete(role);self.H.cycle(str(self.hpath),self.hpin);r=self.postreview(role);self.H.inject(str(self.hpath),self.hpin,role,str(r),P.sha(r))
  state=Path(self.b['state_root'])/role;write(state/'PREPARE_INTENT.json',dict(synthetic=True));_,d=self.H.cycle(str(self.hpath),self.hpin)
  self.assertEqual(d['jobs'][role]['status'],'needs_repair');self.assertFalse(Path(self.jobs[role]['fresh_eval_out']).exists())
 def test_launch_order_and_polling_changes_reject(self):
  self.setup_handoff();b=P.load(self.hpath);b['jobs'][0]['launch_dependencies']=[];write(self.hpath,b)
  with self.assertRaisesRegex(ValueError,'placement/order'):self.H.identity(str(self.hpath),P.sha(self.hpath))
  b['poll_interval_seconds']=10;write(self.hpath,b)
  with self.assertRaisesRegex(ValueError,'cadence'):self.H.identity(str(self.hpath),P.sha(self.hpath))
 def test_no_execution_start_interface(self):
  self.setup_handoff();self.assertFalse(hasattr(self.H,'start'))

 def test_changed_adapter_after_capture_fails_closed(self):
  self.setup_handoff();role='primary_s2';self.complete(role);self.H.cycle(str(self.hpath),self.hpin)
  (Path(self.jobs[role]['new_adapter'])/'adapter_model.safetensors').write_bytes(b'changed')
  _,d=self.H.cycle(str(self.hpath),self.hpin);self.assertEqual(d['jobs'][role]['status'],'needs_repair')
  self.assertFalse(Path(self.jobs[role]['fresh_eval_out']).exists())
 def test_global_identity_failure_has_durable_terminal(self):
  self.setup_handoff();d=P.load(self.hpath);d['jobs'][0]['chip']=7;write(self.hpath,d)
  with self.assertRaisesRegex(ValueError,'placement/order'):self.H.watch(str(self.hpath),P.sha(self.hpath),once=True)
  self.assertEqual(P.load(Path(self.b['state_root'])/'EXIT.json')['exit_code'],1)

if __name__=='__main__':unittest.main()
