"""CPU-only collector tests. Synthetic producer/runtime bytes confer no review authority."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import patch
from tools import r3_formal_postrun_collect as C
from tools import test_r3_formal_wave_handoff as F

REPO=Path(__file__).resolve().parents[1]
OWNERSHIP=REPO/'tools/r3_dev_qualification.py'
LEGACY=REPO/'.local/preparations/formal-qualification-consumer-20261101-v3/reference/collect_evidence.py'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def ref(p):return dict(path=str(p),sha256=C.sha(p))
def tensorfile(p,shapes,payload=True):
 h={};offset=0
 for k,s in shapes.items():
  n=s[0]*s[1]*4;h[k]=dict(dtype='F32',shape=s,data_offsets=[offset,offset+n]);offset+=n
 raw=json.dumps(h).encode();raw+=b' '*((-len(raw))%8)
 with p.open('wb') as f:
  f.write(struct.pack('<Q',len(raw)));f.write(raw)
  if payload:
   block=b'\0'*1048576
   while offset:n=min(offset,len(block));f.write(block[:n]);offset-=n

class StagedTests(unittest.TestCase):
 setUp=F.HandoffTests.setUp
 reviews=F.HandoffTests.reviews
 advance=F.HandoffTests.advance
 setup_handoff=F.HandoffTests.setup_handoff
 complete=F.HandoffTests.complete
 def collector_config(self,role='primary_s2'):
  self.setup_handoff();p=self.base/'collector.json'
  write(p,dict(schema=C.SCHEMA,test_read=False,scientific_acceptance=False,controller=ref(Path(C.__file__).resolve()),legacy=ref(LEGACY),ownership_verifier=ref(OWNERSHIP),handoff_controller=ref(Path(self.H.__file__)),handoff=ref(self.hpath),role=role,training_plan=self.jobs[role]['training_plan'],output=str(self.base/'collection.json')))
  return p
 def test_current_four_role_shape_wait_no_mutation(self):
  p=self.collector_config();before=set(self.base.rglob('*'));d=C.inspect(str(p),C.sha(p));self.assertEqual(d['status'],'WAIT');self.assertIn(str(Path(self.jobs['primary_s2']['training'])/'TRAIN_EXIT.json'),d['missing']);self.assertEqual(before,set(self.base.rglob('*')))
 def test_changed_plan_or_source_rejected(self):
  p=self.collector_config();pin=C.sha(p);plan=Path(self.jobs['primary_s2']['training_plan']['path']);plan.write_text(plan.read_text()+' ')
  with self.assertRaises((ValueError,RuntimeError)):C.inspect(str(p),pin)
 def test_missing_supervisor_or_capture_wait(self):
  p=self.collector_config();self.complete('primary_s2');root=Path(self.jobs['primary_s2']['training']);(root/'attempts/1/SUPERVISOR_DONE.json').unlink();d=C.collect(str(p),C.sha(p),None,None,None);self.assertEqual(d['status'],'WAIT');self.assertIn(str(root/'attempts/1/SUPERVISOR_DONE.json'),d['missing']);self.assertFalse((self.base/'collection.json').exists())
 def test_successful_driver_required(self):
  p=self.collector_config();write(Path(self.jobs['primary_s2']['training'])/'TRAIN_EXIT.json',{'exit_code':1})
  with self.assertRaisesRegex(ValueError,'training failed'):C.inspect(str(p),C.sha(p))
 def test_missing_training_prereview_rejected(self):
  p=self.collector_config();review=Path(self.jobs['primary_s2']['training'])/'ASTRA_REVIEW.json';review.unlink()
  with self.assertRaises(FileNotFoundError):C.inspect(str(p),C.sha(p))
 def test_changed_handoff_source_rejected(self):
  p=self.collector_config();f=Path(self.H.__file__);f.write_bytes(f.read_bytes()+b'\n')
  with self.assertRaises(ValueError):C.inspect(str(p),C.sha(p))
 def test_config_and_executable_pins(self):
  p=self.collector_config();d=C.read(p);d['controller']['sha256']='0'*64;write(p,d)
  with self.assertRaises(ValueError):C.inspect(str(p),C.sha(p))

 def test_ownership_verifier_pin_required(self):
  p=self.collector_config();d=C.read(p);d['ownership_verifier']['sha256']='0'*64;write(p,d)
  with self.assertRaisesRegex(ValueError,'ownership verifier'):C.inspect(str(p),C.sha(p))
 def test_snapshot_binds_capture_claim_release_adapter(self):
  p=self.collector_config();self.complete('primary_s2');self.H.cycle(str(self.hpath),self.hpin);root=Path(self.jobs['primary_s2']['training']);state=Path(self.b['state_root'])/'primary_s2';cp=C.sha(state/'CAPTURE.json')
  for relative in ['adapter/adapter_model.safetensors','attempts/1/CLAIM.json','attempts/1/RELEASE.json','manifest.json']:
   target=root/relative;original=target.read_bytes();target.write_bytes(original+b' ')
   with self.assertRaises(ValueError):C.collect(str(p),C.sha(p),cp,str(self.base/'unopened-observations.json'),'0'*64)
   target.write_bytes(original)
  target=state/'CAPTURE.json';target.write_bytes(target.read_bytes()+b' ')
  with self.assertRaises(ValueError):C.collect(str(p),C.sha(p),cp,str(self.base/'unopened-observations.json'),'0'*64)

class FullEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);r=self.root
  self.L=C.module(ref(LEGACY));self.H=C.module(ref(REPO/'tools/r3_formal_wave_handoff.py'))
  train=r/'training';train.mkdir();model=r/'model';model.mkdir();code=train/'code';code.mkdir();a=train/'attempts/1';a.mkdir(parents=True);adapter=train/'adapter';adapter.mkdir();state=r/'capture';state.mkdir();self.state=state
  for name in ['train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py']:
   f=code/name;f.parent.mkdir(exist_ok=True);f.write_text('synthetic training source')
  data=r/'train.jsonl';data.write_text('synthetic TRAIN')
  shapes={}
  for i in range(31):
   for n in ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj']:shapes[f'model.language_model.layers.{i}.self_attn.{n}.weight']=[1024,2612]
  shapes[next(iter(shapes))][1]+=120
  tensorfile(model/'base.safetensors',shapes,payload=False);write(model/'config.json',{'text_config':{'num_hidden_layers':31}});write(model/'model.safetensors.index.json',{'weight_map':{k:'base.safetensors' for k in shapes}})
  launcher=REPO/'tools/r3_formal_launcher.py'
  p=dict(seed=3,chip=2,out=str(train),model=str(model),code=str(code),train_file=str(data),launcher=str(launcher),allocation=str(r/'allocation.json'),run='synthetic/primary_s3',container='synthetic',image_sha256='synthetic-image',environment={'ASCEND_RT_VISIBLE_DEVICES':'0'},command=['python3','-P','train_r3.py','--seed','3','--arm','k1','--out',str(train),'--model-path',str(model)])
  p['files']={str(f):C.sha(f) for f in [data,launcher,*code.rglob('*.py'),*model.iterdir()]};self.p=p
  plan=train/'plan.json';write(plan,p);j=dict(role='primary_s3',training=str(train),seed=3,chip=2,new_adapter=str(adapter),training_plan=ref(plan),canonical_plan_sha256='synthetic-canonical',required_final_step=3116,late_bound_hashes=self.H.LATE);self.j=j
  b=dict(queue=ref(plan),closure=ref(plan),source_files={},_pin='synthetic-binding',state_root=str(state.parent/'states'));self.b=b
  end=dict(exit_code=0,attempt=1,started_utc='2026-11-02T01:00:01Z',finished_utc='2026-11-02T02:00:00Z',scientific_acceptance=False);write(train/'TRAIN_EXIT.json',end);write(a/'EXIT.json',end)
  st=dict(Status='exited',Running=False,ExitCode=0,StartedAt='2026-11-02T01:00:00Z',FinishedAt='2026-11-02T02:00:01Z')
  claimed='2026-11-02T00:59:59Z';entry=dict(chip=2,run=p['run'],claimed_utc=claimed)
  initial=dict(allocation=[],free=[dict(chip=2,previous_run='prior')],updated_utc=claimed,updated_by='prior')
  before=dict(allocation=[entry],free=[],updated_utc=claimed,updated_by='r3_resource_adapter claim')
  claim=dict(schema='r3-resource-claim-v1',allocation=p['allocation'],entry=entry,run=p['run'],chip=2,claimed_utc=claimed,allocation_before=initial,allocation_after=before,allocation_before_sha256=self.L.ledger_digest(initial),allocation_after_sha256=self.L.ledger_digest(before));write(a/'CLAIM.json',claim)
  after=dict(allocation=[],free=[dict(chip=2,previous_run=p['run'],release_evidence=str(a/'RELEASE.json'),released_utc=st['FinishedAt'])],updated_utc=st['FinishedAt'],updated_by='r3_resource_adapter release')
  release=dict(schema='r3-resource-release-v1',run=p['run'],chip=2,container=p['container']+'-a1',container_id='synthetic-id',claim_sha256=C.sha(a/'CLAIM.json'),exit_code=0,scientific_acceptance=False,released_utc=st['FinishedAt'],container_started_at=st['StartedAt'],container_finished_at=st['FinishedAt'],allocation_before=before,allocation_after=after,allocation_before_sha256=self.L.ledger_digest(before),allocation_after_sha256=self.L.ledger_digest(after));write(a/'RELEASE.json',release)
  api=self.L.extracted_launcher(launcher,p['files'][str(launcher)]);command=api['docker_command'](p,str(plan),1)
  write(a/'LAUNCH_RECEIPT.json',dict(id='synthetic-id',image=p['image_sha256'],plan_sha256=j['canonical_plan_sha256']));write(a/'LAUNCH_SPEC.json',dict(command=command,plan_sha256=j['canonical_plan_sha256']));write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False));write(train/'SUPERVISOR_RECEIPT.json',dict(synthetic=True));write(train/'SUCCESSOR_PRECONDITION.json',dict(synthetic=True))
  args=dict(lora_r=16,lora_alpha=32,lora_dropout=0.05,expect_pairs=186,seed=3,arm='k1',epochs=2,total_steps=3116,kernel='ref',no_merge=True,grad_ckpt=True,micro_tokens=12000,max_len=4096,model_path=p['model'],out=p['out']);m=dict(args=args,summary={'final_step':3116},lora_pairs=186,trainable_params=10822656,chips=1,train_file=ref(data),code_sha256={n:p['files'][str(code/n)] for n in ['train_r3.py','build_kev_sft.py','kev_aug.py']},prompt_py_sha256=p['files'][str(code/'r0_code/prompt.py')],arm='k1',model_path=p['model']);write(train/'manifest.json',m);self.manifest=m
  cfg=dict(peft_type='LORA',task_type='CAUSAL_LM',r=16,lora_alpha=32,lora_dropout=0.05,bias='none',inference_mode=True,base_model_name_or_path=p['model'],target_modules=self.L.TARGETS);write(adapter/'adapter_config.json',cfg);expected=self.L.expected_shapes(model,cfg);tensorfile(adapter/'adapter_model.safetensors',expected)
  cap=self.H.capture(b,j,p);write(state/'CAPTURE.json',cap);self.cp=C.sha(state/'CAPTURE.json')
  mounts=[]
  for i,x in enumerate(command):
   if x=='--mount':
    parts=dict(y.split('=',1) if '=' in y else (y,True) for y in command[i+1].split(','));mounts.append(dict(Source=parts['src'],Destination=parts['dst'],RW='readonly' not in parts,Type='bind'))
  obs=dict(Id='synthetic-id',Image=p['image_sha256'],Name='/synthetic-a1',State=st,Mounts=mounts,Config=dict(Env=['ASCEND_RT_VISIBLE_DEVICES=0'],Entrypoint=['python3'],Cmd=['-P','/workspace/r3_formal_driver.py','--plan',str(plan),'--attempt','1']),HostConfig=dict(NetworkMode='none',Runtime='runc',CgroupnsMode='private',IpcMode='private',Privileged=False,AutoRemove=False,ShmSize=64*1024**3,Ulimits=[dict(Name='memlock',Soft=-1,Hard=-1),dict(Name='stack',Soft=67108864,Hard=67108864)],Devices=[dict(PathOnHost='/dev/'+x,PathInContainer='/dev/'+x,CgroupPermissions='rwm') for x in ['davinci_manager','devmm_svm','hisi_hdc','davinci2']]))
  docs={'container':[obs],'image':[{'Id':p['image_sha256'],'Config':{'Env':[]}}],'daemon':dict(DefaultRuntime='runc',CgroupVersion='2')}
  for k,d in docs.items():write(r/(k+'.json'),d)
  self.op=r/'observations.json';write(self.op,dict(schema='r3-postrun-external-observations-v1',training=p['out'],capture_sha256=self.cp,observations={k:ref(r/(k+'.json')) for k in docs}))
  self.config=r/'collector.json';self.out=r/'collection.json';self.c=dict(legacy=ref(LEGACY),ownership_verifier=ref(OWNERSHIP),controller=ref(Path(C.__file__).resolve()),handoff=ref(plan),handoff_controller=ref(Path(self.H.__file__)),training_plan=ref(plan),role='primary_s3');write(self.config,self.c)
 def run_collect(self):
  # Only identity is substituted: independent staged tests cover actual frozen identity.
  # All capture, runtime, ownership, manifest, architecture, payload and snapshot checks run.
  with patch.object(C,'identity',return_value=(self.c,self.L,self.H,self.b,self.j,self.p,self.state,self.out)):
   return C.collect(str(self.config),C.sha(self.config),self.cp,str(self.op),C.sha(self.op))
 def test_complete_collection_seed3_schema_and_exclusive_publication(self):
  d=self.run_collect();self.assertEqual(d['schema'],'formal-postrun-evidence-collection-v2');self.assertEqual(d['adapter_payload']['element_count'],10822656);self.assertEqual(d['adapter_payload']['tensor_count'],372);self.assertFalse(d['scientific_acceptance']);self.assertEqual(d['files'],C.read(self.state/'CAPTURE.json')['files']);self.assertEqual(C.read(Path(self.p['out'])/'manifest.json')['args']['seed'],3)
  with self.assertRaises(FileExistsError):self.run_collect()
 def test_observation_binding_wrong(self):
  d=C.read(self.op);d['capture_sha256']='wrong';write(self.op,d)
  with self.assertRaisesRegex(ValueError,'another capture'):self.run_collect()
  self.assertFalse(self.out.exists())
 def test_runtime_wrong_device(self):
  f=self.root/'container.json';d=C.read(f);d[0]['HostConfig']['Devices'][-1]['PathOnHost']='/dev/davinci7';write(f,d);o=C.read(self.op);o['observations']['container']=ref(f);write(self.op,o)
  with self.assertRaisesRegex(RuntimeError,'device'):self.run_collect()
 def test_manifest_seed_objective_duplicate_flag(self):
  C.manifest_check(self.L,self.manifest,self.p)
  m=copy.deepcopy(self.manifest);p=copy.deepcopy(self.p);m['args']['seed']=2;p['seed']=2;p['command'][p['command'].index('--seed')+1]='2';C.manifest_check(self.L,m,p)
  for change in ['seed','arm','duplicate']:
   m=copy.deepcopy(self.manifest);p=copy.deepcopy(self.p)
   if change=='duplicate':p['command']+=['--arm','k1']
   else:m['args'][change]=2 if change=='seed' else 'qo'
   with self.assertRaises(ValueError):C.manifest_check(self.L,m,p)
 def test_terminal_chronology_rejects(self):
  t=Path(self.p['out']);e=C.read(t/'TRAIN_EXIT.json');e['finished_utc']='2026-11-03T00:00:00Z';write(t/'TRAIN_EXIT.json',e);write(t/'attempts/1/EXIT.json',e);cap=self.H.capture(self.b,self.j,self.p);write(self.state/'CAPTURE.json',cap);self.cp=C.sha(self.state/'CAPTURE.json');d=C.read(self.op);d['capture_sha256']=self.cp;write(self.op,d)
  with self.assertRaisesRegex(ValueError,'chronology'):self.run_collect()

 def test_current_ownership_rejects_ledger_identity_and_chronology_mutations(self):
  Q=C.module(ref(OWNERSHIP));root=Path(self.p['out']);a=root/'attempts/1'
  claim=C.read(a/'CLAIM.json');release=C.read(a/'RELEASE.json');actual=C.read(self.root/'container.json')[0]
  def check(c,r,obs):
   return Q.ownership(self.p,c,r,Q.ledger_digest(c),a/'RELEASE.json',obs)
  check(claim,release,actual)
  for mutation in ['unrelated','owner','hash','type','time','label','claim_label','claim_identity']:
   with self.subTest(mutation=mutation):
    c=copy.deepcopy(claim);r=copy.deepcopy(release);obs=copy.deepcopy(actual)
    if mutation=='unrelated':r['allocation_after']['extra']='not-in-before'
    if mutation=='owner':r['allocation_before']['allocation'][0]['run']='other'
    if mutation=='hash':r['allocation_after_sha256']='0'*64
    if mutation=='type':r['allocation_after']['free'][0]['chip']=2.0
    if mutation=='time':r['released_utc']='2026-11-01T00:00:00Z'
    if mutation=='label':r['allocation_after']['updated_by']='r3_resource_adapter guarded successor release'
    if mutation=='claim_label':c['allocation_after']['updated_by']='other'
    if mutation=='claim_identity':c['entry']['claimed_utc']='2026-11-01T00:00:00Z'
    # Except the explicit hash case, rehash malicious edits so transition and
    # identity checks themselves must reject self-consistent forged metadata.
    for rec in (c,r):
     for side in ('before','after'):
      if not (mutation=='hash' and rec is r and side=='after'):
       rec['allocation_'+side+'_sha256']=Q.ledger_digest(rec['allocation_'+side])
    r['claim_sha256']=Q.ledger_digest(c)
    with self.assertRaises(ValueError):check(c,r,obs)
 def test_snapshot_mutation_and_payload_nonfinite(self):
  f=self.root/'guard.json';write(f,{'x':1})
  with self.L.owned_snapshot() as s:
   s.capture(f);write(f,{'x':2})
   with self.assertRaises(ValueError):s.final_check()
  f=self.root/'bad.safetensors';tensorfile(f,{'x':[1,1]});data=f.read_bytes();f.write_bytes(data[:-4]+struct.pack('<f',float('nan')))
  with self.assertRaisesRegex(ValueError,'nonfinite'):self.L.verify_payload(f,{'x':[1,1]})

if __name__=='__main__':unittest.main()
