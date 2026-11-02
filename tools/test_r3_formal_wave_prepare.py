"""CPU fixtures: real staged controller/review/role/binder, synthetic TRAIN producer.

No training, Docker, NPU, scientific review, or production ledger is used. Review
fixtures explicitly say synthetic; tests do not authenticate their authorship.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).absolute().parent

def mod(path):
    p=Path(path);m=types.ModuleType(p.stem);m.__file__=str(p)
    exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
P=mod(HERE/'r3_formal_wave_prepare.py')

def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(P.raw(d))

PRODUCER='''
import json,hashlib,shutil
from pathlib import Path
ROOT=Path('/unused')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(out,seed,chip,**kwargs):
 out.mkdir();code=out/'code';code.mkdir();tools=out/'tools';tools.mkdir()
 for name in ('r3_formal_launcher.py','r3_resource_adapter.py','r3_formal_roles.py'):
  shutil.copyfile(ROOT/'tools'/name,tools/name)
 for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
  target=code/rel;target.parent.mkdir(exist_ok=True);target.write_bytes(b'fixture training code')
 schedule=json.loads(Path(kwargs['formal_schedule']).read_bytes());role=kwargs['formal_role'];n=next(n for n in schedule['nodes'] if n['id']==role)
 guard=json.loads(Path(kwargs['successor_guard']).read_bytes());controller=guard.pop('controller');guard.pop('controller_sha256');guard['controller']=controller
 files={str(p):sha(p) for folder in (code,tools) for p in folder.rglob('*') if p.is_file()}
 files.update(schedule['shared_inputs']);files[kwargs['formal_schedule']]=kwargs['formal_schedule_sha256'];files[controller]=sha(controller);files[kwargs['successor_guard']]=kwargs['successor_guard_sha256']
 model=next(str(Path(f).parent) for f in schedule['shared_inputs'] if f.endswith('/config.json'))
 train=next(f for f in schedule['shared_inputs'] if f.endswith('/train.jsonl'))
 p=dict(schema='r3-formal-k1-plan-v1',seed=seed,chip=chip,out=str(out),code=str(code),model=model,train_file=train,
  formal_chips=schedule['physical_chips'],formal_schedule=kwargs['formal_schedule'],formal_schedule_sha256=kwargs['formal_schedule_sha256'],formal_role=role,
  evaluation={'candidate_for_adoption':n['candidate_for_seed_mean']},container=n['container'],command=n['command_candidate'],files=files,
  launcher=str(tools/'r3_formal_launcher.py'),adapter=str(tools/'r3_resource_adapter.py'),driver=controller,
  successor_guard=guard,review_path=str(out/'ASTRA_REVIEW.json'),review_sha256='PENDING',image_sha256='fixture-image',run='fixture/'+role,
  test_read=False,scientific_acceptance=False)
 (out/'plan.json').write_text(json.dumps(p,indent=2,sort_keys=True)+'\\n')
 return p
'''
LAUNCHER='''
from pathlib import Path
import types
SUCCESSOR_CLAIM_GUARD_VERSION=1
def formal_target_identity(p):
 path=Path(__file__).with_name('r3_formal_roles.py');m=types.ModuleType('roles');m.__file__=str(path)
 exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__)
 return m.validate_plan(p)
'''

class StageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.repo=self.base/'repository';self.root=self.base/'wave'
  for rel in P.SOURCE_NAMES:
   source=HERE.parent/rel;target=self.repo/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
  (self.repo/'tools/r3_formal_prepare.py').write_text(PRODUCER);(self.repo/'tools/r3_formal_launcher.py').write_text(LAUNCHER)
  self.train=self.base/'data/train.jsonl';self.train.parent.mkdir();self.train.write_text('synthetic TRAIN')
  self.model=self.base/'model';self.model.mkdir();write(self.model/'config.json',{})
  shared={str(p):P.sha(p) for p in (self.train,self.model/'config.json')}
  codepin=hashlib.sha256(b'fixture training code').hexdigest();nodes=[];predecessors={}
  for role,seed,chip in [('primary_s2',2,1),('primary_s3',3,2),('samechip_s2',2,1),('diffchip_s2',2,2)]:
   out=self.root/role
   deps=[('external_'+role) if role.startswith('primary') else ('primary_s2_release' if role=='samechip_s2' else 'primary_s3_release')]
   nodes.append(dict(id=role,role=role,seed=seed,chip=chip,kind='training',steps=3116,candidate_for_seed_mean=role.startswith('primary'),out=str(out),container='fixture-'+role,
    command_candidate=['python3','-P','/workspace/train_r3.py','--out',str(out),'--seed',str(seed),'--arm','k1'],depends_on=deps))
   pred=('samechip_s2' if role=='primary_s2' else 'diffchip_s2' if role=='primary_s3' else 'primary_s2_dev' if role=='samechip_s2' else 'primary_s3_dev')
   nodes.append(dict(id=role+'_dev',kind='dev_calibration_track_t_readout',training_id=role,chip=chip,out=str(self.root/'evaluations'/role),test_read=False,same_scorer_and_population_as_primary=True,depends_on=[pred+'_release']))
   if role.startswith('primary'):
    prior=self.base/('prior-'+role);prior.mkdir();write(prior/'spec.json',{})
    write(prior/'execution.json',dict(schema='r3-engineering-posttrain-execution-v1',chip=chip,out=str(prior),test_read=False,scientific_acceptance=False,tools={},spec=str(prior/'spec.json'),spec_sha256=P.sha(prior/'spec.json')))
    predecessors[role]={'path':str(prior/'execution.json'),'sha256':P.sha(prior/'execution.json')}
  self.schedule=dict(schema='r3-formal-role-schedule-v1',scientific_acceptance=False,test_read=False,floor_gating_role='diffchip_s2',samechip_gates=False,
    floor_replicates_excluded_from_all_candidate_estimators=True,nodes=nodes,physical_chips=[1,2],shared_inputs=shared,
    code_by_relative_path={r:codepin for r in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py')},external_predecessors=predecessors,target_root=str(self.root))
  self.closure=self.base/'closure';self.closure.mkdir();write(self.closure/'manifest.json',dict(data={},code={},mounts=[],command_template=['python3','--arm','K1','--adapter','<COMPLETED_ADAPTER>','--out','<FRESH_EVAL_OUTPUT>'],evaluation_profile='track_kt'))
  self.req=dict(schema='r3-formal-wave-request-v1',repository=str(self.repo),target_root=str(self.root),source_sha256={r:P.sha(self.repo/r) for r in P.SOURCE_NAMES},
    review_policy=P.POLICY,poll_interval_seconds=600,schedule=self.schedule,inputs={'fresh_k0_prechecks':str(self.model/'config.json'),'fresh_k0_prechecks_sha256':P.sha(self.model/'config.json')},closure={'path':str(self.closure/'manifest.json'),'sha256':P.sha(self.closure/'manifest.json')})
  self.request=self.base/'request.json';write(self.request,self.req);P.freeze(str(self.request),P.sha(self.request))
  self.config=self.root/'WAVE.json';self.pin=P.sha(self.config)

 def reviews(self,stage):
  selected=P.PRIMARY if stage=='primary' else P.AUX;bundle=self.root/'stages'/(stage.upper()+'-PREPARED.json');d=P.load(bundle)
  evidence=self.base/(stage+'-review');evidence.mkdir();report=evidence/'report.json';terminal=evidence/'terminal.json';result=evidence/'result.json'
  write(report,dict(verdict='PASS',scope='exact-formal-train-only-readiness-no-activation',approved_canonical_plan_sha256=[j['plan_sha256'] for j in d['jobs']],synthetic=True))
  write(terminal,dict(exit_code=0,synthetic=True));write(result,dict(synthetic=True))
  ref=lambda p:dict(path=str(p),sha256=P.sha(p));refs={}
  for j in d['jobs']:
   review=dict(schema=P.POLICY,scope='exact-formal-train-only-readiness-no-activation',requested_model='gpt-6-astra',model_evidence_kind='parent-observed-requested-model-dispatch',
    runtime_attestation='unavailable-not-required',worker_exit_code=0,worker_id='synthetic-worker',authenticator_identity='synthetic-parent',authenticated_at='fixture',activation_authorized=False,
    review_report=ref(report),worker_terminal=ref(terminal),worker_result=ref(result),prepared_queue=ref(bundle),
    plans=[dict(path=x['plan'],canonical_sha256=x['plan_sha256'],prepared_raw_sha256=x['plan_raw_sha256']) for x in d['jobs']],synthetic=True)
   path=evidence/(j['id']+'.json');write(path,review);refs[j['id']]=ref(path)
  ticket=evidence/'injection.json';write(ticket,dict(schema='r3-authenticated-review-injection-v1',config_sha256=self.pin,stage=stage,reviews=refs,synthetic=True));return ticket

 def advance(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  P.prepare_stage(str(self.config),self.pin,'aux');ticket=self.reviews('aux');P.attach(str(self.config),self.pin,'aux',str(ticket),P.sha(ticket));return P.finalize(str(self.config),self.pin)

 def test_staged_real_review_and_queue_contract(self):
  P.prepare_stage(str(self.config),self.pin,'primary');pending={r:P.sha(self.root/r/'plan.json') for r in P.PRIMARY}
  self.assertFalse((self.root/'samechip_s2').exists());ticket=self.reviews('primary');a=P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  for r in P.PRIMARY:self.assertNotEqual(pending[r],a['plans'][r]['raw_sha256']);self.assertEqual(pending[r],a['plans'][r]['canonical_sha256'])
  P.prepare_stage(str(self.config),self.pin,'aux');before={r:P.sha(self.root/r/'plan.json') for r in P.PRIMARY}
  for aux,primary in [('samechip_s2','primary_s2'),('diffchip_s2','primary_s3')]:
   guard=P.load(self.root/aux/'plan.json')['successor_guard'];self.assertEqual(guard['previous_training']['plan_raw_sha256'],before[primary])
  t=self.reviews('aux');P.attach(str(self.config),self.pin,'aux',str(t),P.sha(t));r=P.finalize(str(self.config),self.pin)
  self.assertEqual(before,{r:P.sha(self.root/r/'plan.json') for r in P.PRIMARY});self.assertIn('activation_still_required',r['status']);self.assertEqual(P.validate(str(self.config),self.pin)['roles']['diffchip_s2'],'review_attached')
  self.assertFalse((self.root/'samechip_s2/attempts').exists())

 def test_aux_before_primary_review_refused(self):
  P.prepare_stage(str(self.config),self.pin,'primary')
  with self.assertRaises(FileNotFoundError):P.prepare_stage(str(self.config),self.pin,'aux')
  self.assertFalse((self.root/'samechip_s2').exists())

 def test_wrong_injection_rejects_before_mutation(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');d=P.load(ticket);d['config_sha256']='0'*64;write(ticket,d)
  with self.assertRaisesRegex(ValueError,'identity'):P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  for r in P.PRIMARY:self.assertEqual(P.load(self.root/r/'plan.json')['review_sha256'],'PENDING')

 def test_wrong_exact_review_no_partial_attach(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');d=P.load(ticket);ref=d['reviews']['primary_s3'];report=P.load(ref['path']);report['scope']='wrong';write(Path(ref['path']),report);ref['sha256']=P.sha(ref['path']);write(ticket,d)
  with self.assertRaises(RuntimeError):P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  for r in P.PRIMARY:self.assertFalse((self.root/r/'ASTRA_REVIEW.json').exists())

 def test_primary_tamper_blocks_aux(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  p=self.root/'primary_s2/plan.json';d=P.load(p);d['review_sha256']='f'*64;write(p,d)
  with self.assertRaisesRegex(ValueError,'primary changed'):P.prepare_stage(str(self.config),self.pin,'aux')

 def test_source_change_and_schedule_change_refused(self):
  p=self.root/'source/tools/r3_formal_roles.py';old=p.read_bytes();p.write_bytes(old+b'\n')
  with self.assertRaisesRegex(ValueError,'source changed'):P.prepare_stage(str(self.config),self.pin,'primary')
  p.write_bytes(old);s=self.root/'SCHEDULE.json';d=P.load(s);d['physical_chips']=[1,3];write(s,d)
  with self.assertRaisesRegex(ValueError,'pin changed'):P.prepare_stage(str(self.config),self.pin,'primary')

 def test_partial_prepare_failure_not_retried(self):
  out=self.root/'primary_s2';out.mkdir()
  with self.assertRaisesRegex(ValueError,'uncertain'):P.prepare_stage(str(self.config),self.pin,'primary')
  self.assertFalse((self.root/'primary_s3').exists())

 def test_review_attachment_resume_same_pin_only(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');first=P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  self.assertEqual(first,P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket)))
  d=P.load(ticket);d['extra']='changed';write(ticket,d)
  with self.assertRaisesRegex(ValueError,'different already attached'):P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))

 def test_module_compiles_verified_single_buffer(self):
  path=self.base/'buffer.py';path.write_text('value=1')
  with patch.object(Path,'read_bytes',side_effect=[b'value=1',b'value=999']) as reader:
   m=P.module(str(path),hashlib.sha256(b'value=1').hexdigest())
   self.assertEqual(m.value,1);self.assertEqual(reader.call_count,1)

 def test_partial_attachment_resumes_same_target_bytes(self):
  P.prepare_stage(str(self.config),self.pin,'primary');ticket=self.reviews('primary');real=P.write;hit=[]
  def injected(path,doc,replace=False):
   if path==self.root/'primary_s3/plan.json' and replace and not hit:
    hit.append(True);raise OSError('simulated interruption')
   return real(path,doc,replace)
  with patch.object(P,'write',side_effect=injected):
   with self.assertRaisesRegex(OSError,'interruption'):P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  before=P.sha(self.root/'primary_s2/plan.json')
  P.attach(str(self.config),self.pin,'primary',str(ticket),P.sha(ticket))
  self.assertEqual(before,P.sha(self.root/'primary_s2/plan.json'))
  P.prepare_stage(str(self.config),self.pin,'aux')
  self.assertEqual(P.load(self.root/'samechip_s2/plan.json')['successor_guard']['previous_training']['plan_raw_sha256'],before)

if __name__=='__main__':unittest.main()
