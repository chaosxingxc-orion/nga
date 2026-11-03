import copy,hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_dev72_contract_v1 as C,bev_native_dev72_resource_v1 as Q,bev_native_dev72_runtime_v1 as A,bev_native_dev72_host_v1 as H,bev_native_dev72_consume_v1 as U
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_dev72_registry_20261103_v2')
PLAN=ROOT.parent/'native_dev72_2b_reference_20261103_v2/HOST-PLAN.json'
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
@unittest.skipUnless(ROOT.exists(),'frozen DEV72 config unavailable')
class Dev72Contract(unittest.TestCase):
 def fixture(self):return read(ROOT/'CONFIG.json'),read(ROOT/'REGISTRY.json')
 def seal(self,c,r):c['registry_sha256']=digest(r)
 def test_real_sparse_original_population_and_three_passes(self):
  c,r=self.fixture();v=C.validate(c,r);self.assertEqual(v['items'],72);self.assertEqual(v['forwards'],216);self.assertEqual(r['population']['source_indices'][-1],159);self.assertFalse(v['launch_authority'])
 def test_model_selection_by_registry_without_name_dispatch(self):
  c,r=self.fixture();r['model']['alternate_registered_name']=copy.deepcopy(r['model'][c['model']]);c['model']='alternate_registered_name';self.seal(c,r);self.assertEqual(C.validate(c,r)['items'],72)
 def test_unknown_model_protocol_resource_rejected(self):
  for k in ('model','protocol','resources'):
   c,r=self.fixture();c[k]='unregistered'
   with self.assertRaises(ValueError):C.validate(c,r)
 def test_population_renumber_reorder_and_test_scope_rejected(self):
  for mode in ('renumber','reorder','test','count','gold'):
   c,r=self.fixture()
   with tempfile.TemporaryDirectory() as t:
    rows=[json.loads(x) for x in Path(c['inputs']['path']).read_text().splitlines()]
    if mode=='renumber':
     for i,x in enumerate(rows):x['i']=i
    elif mode=='reorder':rows.reverse()
    elif mode=='test':r['population']['source_split']='test'
    elif mode=='count':rows.pop()
    else:rows[0]['gold']=0
    p=Path(t)/'requests.jsonl';p.write_text(''.join(json.dumps(x)+chr(10) for x in rows));c['inputs'].update(path=str(p),sha256=C.sha(p),ordered_sha256=digest(rows));self.seal(c,r)
    with self.assertRaises(ValueError):C.validate(c,r)
 def test_tokenizer_and_model_manifest_tamper_reject(self):
  for mode in ('tokenizer','manifest','source'):
   c,r=self.fixture();m=r['model'][c['model']]
   if mode=='tokenizer':m['files'][m['path']+'/tokenizer.json']='f'*64;m['model_manifest_sha256']=digest(m['files'])
   elif mode=='manifest':m['model_manifest_sha256']='f'*64
   else:r['population']['source_plan']['sha256']='f'*64
   self.seal(c,r)
   with self.assertRaises(ValueError):C.validate(c,r)
 def test_precision_variants_tolerance_and_sparse_type_reject(self):
  changes=[('protocol','dtype','bfloat16'),('protocol','hf32',True),('protocol','batch_size',2),('protocol','max_length',8192),('protocol','variants',['adapter']),('population','tolerance',0.01),('population','tolerance',False),('population','padding_side','right')]
  for where,k,v in changes:
   c,r=self.fixture();target=r['protocol'][c['protocol']] if where=='protocol' else r['population'];target[k]=v;self.seal(c,r)
   with self.assertRaises(ValueError):C.validate(c,r)
 def test_contract_identity_changes_for_model_inputs_protocol_and_helper(self):
  d=read(PLAN);c,r=self.fixture();m=r['model'][c['model']];base={m['path']:m['model_manifest_sha256'],'protocol':r['protocol'][c['protocol']],'inputs':c['inputs'],'native':d['modules']['native'],'loader':d['modules']['loader'],'probe':d['modules']['probe']}
  self.assertEqual(digest(base),d['contract_sha256']);self.assertNotEqual(d['contract_sha256'],C.sha(PLAN))
  for key in base:
   changed=copy.deepcopy(base);changed[key]={'changed':True};self.assertNotEqual(digest(changed),d['contract_sha256'])
 def test_cpu_consumer_not_directly_or_ancestor_mounted(self):
  d=read(PLAN);self.assertEqual(d['mounts'],A.mounts(d,PLAN,read(ROOT/'REGISTRY.json')['model']['qwen3_5_2b_base']['path']))
  for p in d['cpu_only']:
   self.assertFalse(any(Path(p).is_relative_to(m['source']) for m in d['mounts']))
 def test_command_chip6_retained_and_three_pass_configuration(self):
  d=read(PLAN);cmd=H.command(dict(d,runtime=d['modules']['runtime'],image_sha256=d['image']),str(PLAN),C.sha(PLAN),1)
  self.assertIn('/dev/davinci6',cmd);self.assertNotIn('--rm',cmd);self.assertNotIn('-I',cmd);self.assertIn('--network=none',cmd)
 def test_strict_json_rejects_duplicate_and_nonfinite(self):
  for s in ['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}']:
   with self.assertRaises(ValueError):C.strict_json(s)
class ResourceAndLifecycle(unittest.TestCase):
 def fixture(self):
  d=read(PLAN);q=read(d['queue']['path']);p=read(q['predecessor']['plan']['path']);rel=read(q['predecessor']['release']['path']);receipt=read(q['predecessor']['launch_receipt']['path']);allocation=copy.deepcopy(rel['allocation_after']);actual={'Id':rel['container_id'],'Image':p['image_sha256'],'State':{'Status':'exited','Running':False,'ExitCode':rel['exit_code'],'StartedAt':rel['container_started_at'],'FinishedAt':rel['container_finished_at']},'Config':{'Cmd':receipt['command']},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci6'}]}}
  R=types.SimpleNamespace(read_bytes=lambda p:Path(p).read_bytes(),sha_bytes=lambda b:hashlib.sha256(b).hexdigest(),validate_doc=lambda x:None,docker_inspect=lambda n:actual,live_chip_conflict=lambda *x:False)
  return d,q,R,allocation,actual
 def test_real_physical_release_uses_no_cpu_or_test_acceptance(self):
  d,q,R,a,actual=self.fixture();v=Q.guard(d,R,a);self.assertTrue(v['physical_release_verified']);self.assertFalse(v['scientific_acceptance_required']);self.assertEqual(set(q['predecessor']),{'plan','claim','release','launch_spec','launch_receipt'})
 def test_priority_owner_conflict_foreign_id_and_bool_exit_reject(self):
  for attack in ('priority','owner','conflict','id','exit','running','device','command','started_at','finished_at'):
   d,q,R,a,actual=self.fixture()
   if attack=='priority':a['pending_claims']=[]
   elif attack=='owner':a['allocation'].append({'chip':6})
   elif attack=='conflict':R.live_chip_conflict=lambda *x:True
   elif attack=='id':actual['Id']='foreign'
   elif attack=='exit':actual['State']['ExitCode']=False
   elif attack=='running':actual['State']['Running']=True
   elif attack=='device':actual['HostConfig']['Devices']=[]
   elif attack=='started_at':actual['State']['StartedAt']='2026-11-03T23:00:00Z'
   elif attack=='finished_at':actual['State']['FinishedAt']='2026-11-03T23:00:00Z'
   else:actual['Config']['Cmd']=['foreign']
   with self.assertRaises(ValueError):Q.guard(d,R,a)
 def test_uncertain_launch_keeps_claim_and_never_handoff(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);h=root/'host_attempts/1';h.mkdir(parents=True);d={'out':str(root),'modules':{'resource_base':{}},'resource':{'path':'/resource'},'container':'dev','chip':6,'image_sha256':'image'};calls=[]
   def run(cmd,**kw):calls.append(cmd);return types.SimpleNamespace(returncode=1 if 'docker' in cmd else 0)
   args=types.SimpleNamespace(plan='/plan',sha256='pin',review='/review',review_sha256='rpin',attempt=1)
   with patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H,'preflight'),patch.object(H,'module',return_value=types.SimpleNamespace(live_chip_conflict=lambda *x:False)),patch.object(H,'inspect',return_value=None),patch.object(H,'command',return_value=['docker','run','image','run']),patch.object(H.subprocess,'run',side_effect=run),patch.object(H,'handoff_cpu') as cpu:
    with self.assertRaisesRegex(ValueError,'uncertain'):H.supervise(args)
    self.assertFalse(cpu.called);self.assertTrue(any('claim' in c for c in calls));self.assertFalse(any('release' in c for c in calls));self.assertFalse((h/'EXIT.json').exists())
 def test_handoff_failure_preserves_runtime_terminal(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);h=root/'host_attempts/1';h.mkdir(parents=True);terminal=h/'EXIT.json';terminal.write_text('immutable');d={'out':str(root),'modules':{'consumer':{}}};args=types.SimpleNamespace(plan='/p',sha256='pin',attempt=1)
   with patch.object(H,'module',return_value=types.SimpleNamespace(start=lambda *x:(_ for _ in ()).throw(OSError()))):H.handoff_cpu(d,args)
   self.assertEqual(terminal.read_text(),'immutable');self.assertTrue((root/'cpu/HANDOFF-ERROR.json').exists())
 def test_foreign_terminal_generation_and_bool_exit_reject(self):
  term={'exit_code':0,'plan_sha256':'pin','attempt':1,'scientific_acceptance':False};actual={'Id':'cid','State':{'ExitCode':0}};receipt={'container_id':'cid','plan_sha256':'pin','attempt':1,'scientific_acceptance':False}
  self.assertTrue(H.runtime_terminal_matches(term,'pin',1,actual,receipt))
  for k,v in [('exit_code',False),('plan_sha256','foreign'),('attempt',True)]:self.assertFalse(H.runtime_terminal_matches(dict(term,**{k:v}),'pin',1,actual,receipt))
 def test_consumer_without_lifecycle_cannot_start(self):
  d=read(PLAN)
  with self.assertRaises((FileNotFoundError,ValueError)):U.start(d,str(PLAN),C.sha(PLAN),1)
if __name__=='__main__':unittest.main()
