import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

P=Path(__file__).with_name('r3_instruct_v2_precheck_waiter_20261101.py')
spec=importlib.util.spec_from_file_location('waiter',P);W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)

class WaiterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.queue=self.root/'queue.json';self.controller=self.root/'controller.py';self.controller.write_text('# frozen')
  self.output=self.root/'eval/results/selection_report.json';self.output.parent.mkdir(parents=True)
  self.terminal=self.root/'jobs/instruct-k0/EXIT.json';self.terminal.parent.mkdir(parents=True)
  self.job={'id':'instruct-k0','kind':'report','eval_out':str(self.output.parent.parent),'output':str(self.output)}
  self.doc={'schema':'r3-cpu-report-queue-v1','test_read':False,'scientific_acceptance':False,'jobs':[self.job],'controller':str(self.controller),'controller_sha256':W.digest(self.controller.read_bytes())}
  self.queue.write_text(json.dumps(self.doc))
  self.model={'kind':'checkpoint','path':'/models/Instruct'}
  self.q={'producer':{'queue':str(self.queue),'queue_sha256':W.digest(self.queue.read_bytes()),'job':self.job.copy(),'terminal':str(self.terminal)},'expected_report_model':self.model}
 def complete(self,code=0):
  self.output.write_text(json.dumps({'schema':'r3-selection-report-v1','scientific_acceptance':False,'header':{'arm':'K0','model':self.model,'partitions':['dev','calibration']}}))
  self.terminal.write_text(json.dumps({'exit_code':code,'output_sha256':W.digest(self.output.read_bytes()),'scientific_acceptance':False}))
 def test_wait_without_reading_report(self):
  self.output.write_text('invalid unfinished report')
  self.assertIsNone(W.prerequisite(self.q))
 def test_process_ack_is_not_terminal(self):
  (self.terminal.parent/'WORKER.json').write_text(json.dumps({'pid':os.getpid()}))
  self.assertIsNone(W.prerequisite(self.q))
 def test_success_exact_hashes(self):
  self.complete();r=W.prerequisite(self.q)
  self.assertEqual(r['terminal_sha256'],W.digest(self.terminal.read_bytes()))
  self.assertEqual(r['report_sha256'],W.digest(self.output.read_bytes()))
 def test_failed_terminal_rejected(self):
  self.complete(1)
  with self.assertRaisesRegex(ValueError,'producer failed'):W.prerequisite(self.q)
 def test_boolean_exit_rejected(self):
  self.complete(False)
  with self.assertRaises(ValueError):W.prerequisite(self.q)
 def test_queue_change_rejected(self):
  self.queue.write_text('{}')
  with self.assertRaisesRegex(ValueError,'source pin'):W.prerequisite(self.q)
 def test_controller_change_rejected(self):
  self.controller.write_text('# changed')
  with self.assertRaisesRegex(ValueError,'source pin'):W.prerequisite(self.q)
 def test_report_changed_rejected(self):
  self.complete();self.output.write_text('{}')
  with self.assertRaisesRegex(ValueError,'source pin'):W.prerequisite(self.q)
 def test_job_identity_rejected(self):
  self.q['producer']['job']['id']='other'
  with self.assertRaisesRegex(ValueError,'job identity'):W.prerequisite(self.q)
 def test_wrong_terminal_rejected(self):
  self.q['producer']['terminal']=str(self.root/'EXIT.json')
  with self.assertRaisesRegex(ValueError,'terminal identity'):W.prerequisite(self.q)
 def test_wrong_model_rejected(self):
  self.complete();self.q['expected_report_model']={'kind':'checkpoint','path':'/models/Base'}
  with self.assertRaisesRegex(ValueError,'K0 identity'):W.prerequisite(self.q)
 def test_symlink_and_test_paths_rejected(self):
  link=self.root/'link';link.symlink_to(self.queue)
  for p in (link,self.root/'test.jsonl',self.root/'test/rows.parquet'):
   with self.assertRaises(ValueError):W.safe(p)
 def test_same_buffer_used_for_compile(self):
  p=self.root/'source.py';p.write_text('value = 37\n');raw=p.read_bytes()
  original=W.pinned
  def race(path,pin):
   result=original(path,pin);p.write_text('raise RuntimeError("mutated")\n');return result
  with patch.object(W,'pinned',side_effect=race):m=W.module(str(p),W.digest(raw))
  self.assertEqual(m.value,37)
 def test_source_inventory_preflight_before_read(self):
  with patch.object(W,'pinned') as read:
   with self.assertRaises(ValueError):W.dependencies({'source_pins':{str(self.controller):'x',str(self.root/'test.jsonl'):'x'}})
   read.assert_not_called()
 def test_pid_command_and_starttime(self):
  cmd=[sys.executable,'-c','import time; time.sleep(5)'];p=subprocess.Popen(cmd)
  self.addCleanup(lambda:(p.terminate(),p.wait()) if p.poll() is None else None)
  r=W.receipt(p,cmd);self.assertTrue(W.matches(r))
  r['start_ticks']='0';self.assertFalse(W.matches(r))
 def test_start_never_retries(self):
  (self.root/'START_INTENT.json').write_text('{}')
  with patch.object(W,'request',return_value={}),patch.object(W,'dependencies'),patch.object(W,'prerequisite'),patch.object(W.subprocess,'Popen') as spawn:
   with self.assertRaisesRegex(ValueError,'no automatic retry'):W.start(self.queue,'pin')
   spawn.assert_not_called()
 def test_watch_failure_terminal_no_retry(self):
  with patch.object(W,'request',return_value={'output':str(self.output)}),patch.object(W,'prerequisite',side_effect=ValueError('producer failed')),patch.object(W.subprocess,'Popen') as spawn:
   self.assertEqual(W.watch(self.queue,'pin'),1);spawn.assert_not_called()
  self.assertEqual(json.loads((self.root/'EXIT.json').read_text())['exit_code'],1)
 def test_existing_output_rejected_before_generator(self):
  self.output.parent.mkdir(exist_ok=True)
  with patch.object(W,'request',return_value={'output':str(self.output)}),patch.object(W,'dependencies'),patch.object(W,'prerequisite',return_value={'ok':True}),patch.object(W,'module') as mod:
   with self.assertRaisesRegex(ValueError,'already exists'):W.produce(self.queue,'pin')
   mod.assert_not_called()
 def produce_fixture(self, validator_fails=False):
  output=self.root/'new/evidence/K0_PRECHECKS.json'
  q={'output':str(output),'generator':'/generator.py','consumer':'/consumer.py',
     'source_pins':{'/generator.py':'g','/consumer.py':'c'},'generator_arguments':{'model':'/model'}}
  def run(args):
   output.parent.mkdir(parents=True);output.write_text('{}')
  def validate(*args):
   if validator_fails:raise ValueError('full validator rejected')
   return {'schema':'r3-fresh-k0-prechecks-v2','inputs':{},'checks':{}}
  return q,types.SimpleNamespace(run=run),types.SimpleNamespace(validate_bundle=validate)
 def test_full_consumer_required_for_completion(self):
  q,g,c=self.produce_fixture(validator_fails=True)
  with patch.object(W,'request',return_value=q),patch.object(W,'dependencies'),patch.object(W,'prerequisite',return_value={'identity':'fixed'}),patch.object(W,'module',side_effect=[g,c]):
   with self.assertRaisesRegex(ValueError,'full validator'):W.produce(self.queue,'pin')
  self.assertFalse((self.root/'VALIDATION.json').exists())
 def test_producer_mutation_during_consumption_rejected(self):
  q,g,c=self.produce_fixture()
  with patch.object(W,'request',return_value=q),patch.object(W,'dependencies'),patch.object(W,'prerequisite',side_effect=[{'identity':'before'},{'identity':'after'}]),patch.object(W,'module',side_effect=[g,c]):
   with self.assertRaisesRegex(ValueError,'changed during'):W.produce(self.queue,'pin')
  self.assertFalse((self.root/'VALIDATION.json').exists())
 def test_validated_output_has_exact_consumer_receipt(self):
  q,g,c=self.produce_fixture()
  with patch.object(W,'request',return_value=q),patch.object(W,'dependencies'),patch.object(W,'prerequisite',return_value={'identity':'fixed'}),patch.object(W,'module',side_effect=[g,c]):W.produce(self.queue,'pin')
  result=json.loads((self.root/'VALIDATION.json').read_text())
  self.assertTrue(result['full_validate_bundle_completed'])
  self.assertEqual(result['output_sha256'],W.digest(Path(q['output']).read_bytes()))
  self.assertFalse(result['scientific_acceptance'])
  self.assertFalse((self.root/'EXIT.json').exists())

 def run_watch_completion(self, mutation=None):
  output=self.root/'evidence/K0_PRECHECKS.json'
  consumed={'identity':'fixed'}
  validation={'full_validate_bundle_completed':True,'consumed':consumed,
              'output_sha256':W.digest(b'{"validated": true}')}
  validation_raw=json.dumps(validation).encode()
  def spawn(*args,**kwargs):
   output.parent.mkdir();output.write_bytes(b'{"validated": true}')
   (self.root/'VALIDATION.json').write_bytes(validation_raw)
   return types.SimpleNamespace(pid=os.getpid(),returncode=0,poll=lambda:0)
  original_atomic=W.atomic
  def write(path,value):
   original_atomic(path,value)
   if Path(path).name=='heartbeat.json' and value['state']=='completed_pending_root_review' and mutation:
    mutation(output,self.root/'VALIDATION.json')
  with patch.object(W,'request',return_value={'output':str(output)}),patch.object(W,'dependencies'),patch.object(W,'prerequisite',return_value=consumed),patch.object(W.subprocess,'Popen',side_effect=spawn),patch.object(W,'atomic',side_effect=write):
   rc=W.watch(self.queue,'pin')
  return rc,validation_raw,output

 def test_watch_success_retains_validated_hashes(self):
  rc,raw,output=self.run_watch_completion()
  self.assertEqual(rc,0)
  terminal=json.loads((self.root/'EXIT.json').read_bytes())
  self.assertEqual(terminal['validation_sha256'],W.digest(raw))
  self.assertEqual(terminal['output_sha256'],W.digest(output.read_bytes()))
  self.assertFalse((self.root/'FAILURE.json').exists())

 def test_watch_rejects_output_mutation_before_completion(self):
  rc,_,_=self.run_watch_completion(lambda output,validation:output.write_text('{"changed": true}'))
  self.assertEqual(rc,1)
  terminal=json.loads((self.root/'EXIT.json').read_bytes())
  self.assertEqual(terminal['exit_code'],1)
  self.assertIsNone(terminal['output_sha256'])
  self.assertIn('source pin differs',json.loads((self.root/'FAILURE.json').read_bytes())['message'])

 def test_watch_rejects_validation_mutation_before_completion(self):
  rc,_,_=self.run_watch_completion(lambda output,validation:validation.write_text('{"changed": true}'))
  self.assertEqual(rc,1)
  terminal=json.loads((self.root/'EXIT.json').read_bytes())
  self.assertEqual(terminal['exit_code'],1)
  self.assertIsNone(terminal['validation_sha256'])
  self.assertIn('source pin differs',json.loads((self.root/'FAILURE.json').read_bytes())['message'])

 def test_watch_validation_parse_and_hash_use_identical_buffer(self):
  original_loads=W.json.loads
  def parse(raw,*args,**kwargs):
   result=original_loads(raw,*args,**kwargs)
   if isinstance(result,dict) and result.get('full_validate_bundle_completed'):
    (self.root/'VALIDATION.json').write_text('{"changed_after_read": true}')
   return result
  with patch.object(W.json,'loads',side_effect=parse):rc,_,_=self.run_watch_completion()
  self.assertEqual(rc,1)
  self.assertEqual(json.loads((self.root/'EXIT.json').read_bytes())['exit_code'],1)

 def assert_replay_preserves(self):
  before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name!='watch.lock'}
  with patch.object(W,'request') as request,patch.object(W.subprocess,'Popen') as spawn:
   with self.assertRaisesRegex(ValueError,'prior attempt'):W.watch(self.queue,'pin')
   request.assert_not_called();spawn.assert_not_called()
  after={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name!='watch.lock'}
  self.assertEqual(before,after)

 def test_watch_replay_preserves_actual_success(self):
  self.assertEqual(self.run_watch_completion()[0],0)
  self.assert_replay_preserves()

 def test_watch_replay_preserves_actual_failure(self):
  with patch.object(W,'request',side_effect=ValueError('initial failure')):
   self.assertEqual(W.watch(self.queue,'pin'),1)
  self.assert_replay_preserves()

 def test_watch_replay_preserves_partial_generations(self):
  markers=['EXIT.json','FAILURE.json','PRODUCE_INTENT.json','WATCH_INTENT.json',
           'PRODUCER_FAILURE.json','CHILD.json','CONSUMED.json','VALIDATION.json',
           'heartbeat.json','producer.log','evidence']
  for name in markers:
   with self.subTest(marker=name):
    p=self.root/name
    if name=='evidence':p.mkdir()
    else:p.write_bytes(b'partial receipt; preserve exact bytes')
    self.assert_replay_preserves()
    if p.is_dir():p.rmdir()
    else:p.unlink()

 def test_watch_excludes_concurrent_terminal_owner(self):
  with (self.root/'watch.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with patch.object(W,'request') as request:
    with self.assertRaises(BlockingIOError):W.watch(self.queue,'pin')
    request.assert_not_called()
  self.assertFalse((self.root/'WATCH_INTENT.json').exists())
  self.assertFalse((self.root/'EXIT.json').exists())
  self.assertFalse((self.root/'FAILURE.json').exists())

if __name__=='__main__':unittest.main()
