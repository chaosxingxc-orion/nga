"""CPU-only dual identity/counterexample tests. No production artifact is fabricated."""
import copy,importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).parent
PREP=ROOT.parent/'.local/preparations/native-2b-shard-successor-20261103-v1'
def mod(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=mod('bev_native_shard_dual_contract_v1');A=mod('bev_native_shard_dual_runtime_v1');Q=mod('bev_native_shard_dual_resource_v1');U=mod('bev_native_shard_dual_consume_v1');H=mod('bev_native_shard_dual_host_v1');K=mod('bev_native_shard_dual_package_v1')

class DualTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.template=B.read(PREP/'TEMPLATE.json');cls.rp=cls.template['reference_plan'];cls.context=B.reference(cls.rp);cls.bp,cls.cfg,cls.reg,cls.model,cls.proto,cls.L,cls.N,cls.P,cls.R,cls.items,cls.up=cls.context
  cls.base=B.module(cls.template['modules']['contract']);cls.S=B.module(cls.template['modules']['shard']);cls.population=B.build(cls.rp,cls.template['modules']['contract'])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def put(self,name,v):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v));return B.ref(p)
 def contract(self):return A.shard_interface(B,self.base,self.rp,self.template['modules']['contract'])
 def operand(self,item,variant='adapter',contract=None):
  pin=contract or self.bp['contract_sha256'];logits=np.zeros((1,248320),dtype=np.float32)
  for i,k in enumerate(item['label_ids']):logits[0,k]=i/16
  pred=self.N.read_logits(item,logits[0],mode='transformers_full_labels',contract_sha256=pin,prepared_sha256=self.N.digest(item))
  return {'input_ids':np.array([item['input_ids']],dtype=np.int64),'attention_mask':np.ones((1,len(item['input_ids'])),dtype=np.int64),'logits':logits},{'prediction':pred,'restricted_logprobs':pred['restricted_logprobs'],'variant':variant,'forwards':1}
 def test_real2b_population_dual_identity_and_sparse_ids(self):
  b=self.population['binding'];self.assertNotEqual(b['contract_sha256'],b['reference_plan_sha256']);self.assertEqual(b['contract_sha256'],self.bp['contract_sha256']);self.assertEqual(b['model_sha256'],self.model['model_manifest_sha256']);self.assertEqual(b['source_indices'][-1],159);self.assertEqual([len(x['global_ordinals']) for x in self.population['shards']],[36,36]);self.assertEqual(self.S.load_requests(b),self.items)
 def test_original_runner_projects_new_reference_exactly(self):
  p=self.put('POP.json',self.population);p,b,sh,_=self.S.load_population(p,1,contract=self.contract());self.assertEqual(sh['global_ordinals'][-1],71)
 def test_original_contract_cannot_alias_2b_to08b(self):
  b=self.population['binding']
  with self.assertRaises(ValueError):self.base.build_dev72(b['parent_population'],b['inputs'],b['model_sha256'],self.rp)
 def test_numeric_contract_cannot_be_host_plan_hash(self):
  bad=copy.deepcopy(self.bp);bad['contract_sha256']=self.rp['sha256'];p=self.put('BADPLAN.json',bad)
  with self.assertRaises(ValueError):B.reference(p)
 def test_population_reorder_renumber_model_and_contract_mutations_reject(self):
  for change in ('order','indices','model','contract','plan'):
   bad=copy.deepcopy(self.population)
   if change=='order':bad['shards'][0]['global_ordinals'].reverse()
   elif change=='indices':bad['binding']['source_indices']=list(range(72))
   elif change=='model':bad['binding']['model_sha256']='0'*64
   elif change=='contract':bad['binding']['contract_sha256']=self.rp['sha256']
   else:bad['binding']['reference_plan_sha256']='0'*64
   p=self.put('BAD-'+change+'.json',bad)
   with self.subTest(change=change),self.assertRaises(ValueError):self.S.load_population(p,0,contract=self.contract())
 def test_projection_rejects_foreign_execution_identity(self):
  c=self.contract();b=self.population['binding']
  with self.assertRaises(ValueError):c.build_dev72(b['parent_population'],b['inputs'],b['model_sha256'],dict(self.rp,sha256='0'*64))
 def test_saved_full_operand_roundtrip_and_exact_numeric_counterexamples(self):
  item=self.items[-1];arrays,res=self.operand(item);p=self.root/'operand';self.P.persist_operand(p,arrays,res);loaded,_=A.full_operand(self.L,p,self.P,self.bp['contract_sha256'],item,self.N,'adapter');self.assertEqual(loaded['logits'].shape,(1,248320))
  for key in ('logits','input_ids','attention_mask'):
   bad={k:v.copy() for k,v in arrays.items()};bad[key].flat[0]+=1
   with self.subTest(key=key),self.assertRaises(ValueError):self.P.compare_operands(arrays,bad,res,res)
  bad=copy.deepcopy(res);bad['prediction']['first_index']+=1
  with self.assertRaises(ValueError):self.P.compare_operands(arrays,arrays,res,bad)
 def test_248319_and_wrong_contract_rejected(self):
  item=self.items[0];arrays,res=self.operand(item);arrays['logits']=arrays['logits'][:,:248319];p=self.root/'short';self.P.persist_operand(p,arrays,res)
  with self.assertRaises(ValueError):A.full_operand(self.L,p,self.P,self.bp['contract_sha256'],item,self.N,'adapter')
  arrays,res=self.operand(item,contract=self.rp['sha256']);p=self.root/'foreign';self.P.persist_operand(p,arrays,res)
  with self.assertRaises(ValueError):A.full_operand(self.L,p,self.P,self.bp['contract_sha256'],item,self.N,'adapter')
 def test_incomplete_operand_commit_and_wrong_mask_rejected(self):
  item=self.items[0];arrays,res=self.operand(item);p=self.root/'partial';self.P.persist_operand(p,arrays,res);(p/'COMMITTED.json').unlink()
  with self.assertRaises((ValueError,OSError)):A.full_operand(self.L,p,self.P,self.bp['contract_sha256'],item,self.N,'adapter')
  arrays['attention_mask'][0,0]=0;p=self.root/'badmask';self.P.persist_operand(p,arrays,res)
  with self.assertRaises(ValueError):A.full_operand(self.L,p,self.P,self.bp['contract_sha256'],item,self.N,'adapter')
 def test_sequential_shard_resume_preserves_sparse_i_and_does_not_repeat(self):
  population=self.put('POP.json',self.population);calls=[];preds={}
  def predict(item):
   calls.append(item['i']);a,r=self.operand(item);preds[item['i']]=r['prediction'];return r['prediction']
  def validate(pred,item,b):self.assertEqual(pred,self.operand(item)[1]['prediction']);self.assertEqual(b['contract_sha256'],self.bp['contract_sha256'])
  fail_i=self.items[38]['i']
  def fail(item):
   if item['i']==fail_i:raise RuntimeError('injected partial run')
   return predict(item)
  out=self.root/'shard1'
  with self.assertRaises(RuntimeError):self.S.run_shard(population,1,out,fail,validate,contract=self.contract())
  previous=(out/'attempts/1/EXIT.json').read_bytes();calls.clear();r=self.S.run_shard(population,1,out,predict,validate,attempt=2,contract=self.contract());self.assertEqual((r['computed'],r['reused']),(34,2));self.assertEqual(calls,[x['i'] for x in self.items[38:]]);self.assertEqual((out/'attempts/1/EXIT.json').read_bytes(),previous)
 def test_producer_boolean_cannot_replace_independent_receipt(self):
  p=self.put('PRODUCER.json',{'schema':'native-dev72-reference-comparison-v1','numerical_equivalence_observed':True})
  with self.assertRaises(ValueError):B.acceptance(p,self.rp,{'path':'/missing','sha256':'0'*64},{'path':'/missing','sha256':'0'*64},{'path':'/missing','sha256':'0'*64},1)
 def test_receipt_without_real_files_rejected(self):
  base=Path(self.bp['out'])/'cpu/1';ev={'path':str(base/'REFERENCE-EVIDENCE.json'),'sha256':'0'*64};su={'path':str(base/'summary.json'),'sha256':'0'*64};te={'path':str(base/'EXIT.json'),'sha256':'0'*64}
  r={'schema':'native-dev72-independent-result-v1','verdict':'PASS','plan':self.rp,'attempt':1,'contract_sha256':self.bp['contract_sha256'],'model_sha256':self.model['model_manifest_sha256'],'evidence':ev,'summary':su,'terminal':te,'items':72,'raw_operand_comparisons':144,'zero_tolerance':True,'numerical_equivalence_verified':True,'scientific_acceptance':False,'test_read':False,'reviewer':'CPU fixture only'};p=self.put('REVIEW.json',r)
  with self.assertRaises((ValueError,OSError)):B.acceptance(p,self.rp,ev,su,te,1)
  for key,value in [('model_sha256','f'*64),('contract_sha256',self.rp['sha256']),('attempt',True),('raw_operand_comparisons',True),('scientific_acceptance',True)]:
   bad=self.put('BADREVIEW.json',dict(r,**{key:value}))
   with self.subTest(key=key),self.assertRaises(ValueError):B.acceptance(bad,self.rp,ev,su,te,1,read_artifacts=False)
 def test_prepare_only_no_artifacts_or_output_created(self):
  before=Path(self.template['package_path']).exists()
  with patch.object(K,'write',side_effect=AssertionError('unexpected write')):t,Bb,bp,c,r,m,pop=K.prepare(B.ref(PREP/'TEMPLATE.json'))
  self.assertEqual(Path(t['package_path']).exists(),before);self.assertEqual(t['chip'],6)
 def test_bind_missing_receipt_does_not_create_package(self):
  before=Path(self.template['package_path']).exists()
  with self.assertRaises(OSError):K.bind(B.ref(PREP/'TEMPLATE.json'),{'path':str(self.root/'ABSENT.json'),'sha256':'0'*64},{},[],'')
  self.assertEqual(Path(self.template['package_path']).exists(),before)
 def test_cpu_mount_isolation(self):
  d={'model':str(self.root/'model'),'modules':{'consumer':{'path':str(self.root/'consume.py')}},'baseline_evidence':{'path':str(self.root/'cpu/EVIDENCE.json')},'baseline_summary':{'path':str(self.root/'cpu/summary.json')},'baseline_terminal':{'path':str(self.root/'cpu/EXIT.json')},'files':{},'out':str(self.root/'output')}
  for f in A.cpu_only(d):d['files'][f]='a'*64
  mounts=A.mounts(d,str(self.root/'PLAN.json'));self.assertTrue(all(not Path(f).is_relative_to(m['source']) for f in A.cpu_only(d) for m in mounts))
  d['out']=str(self.root)
  with self.assertRaises(ValueError):A.mounts(d,str(self.root/'PLAN.json'))
 def test_failure_terminal_before_any_model_load(self):
  p=self.put('PLAN.json',{'out':str(self.root/'out')})
  with patch.object(A,'verify',side_effect=ValueError('fixture')):
   with self.assertRaises(ValueError):A.run(p['path'],p['sha256'],1)
  self.assertEqual(B.read(self.root/'out/attempts/1/EXIT.json')['exit_code'],1)
 def test_cpu_handoff_failure_does_not_rewrite_npu_terminal(self):
  out=self.root/'out';h=out/'host_attempts/1';h.mkdir(parents=True);(h/'EXIT.json').write_text('immutable')
  with patch.object(H,'module',return_value=types.SimpleNamespace(start=lambda *args:(_ for _ in ()).throw(RuntimeError()))):H.handoff_cpu({'out':str(out),'modules':{'consumer':{}}},types.SimpleNamespace(plan='plan',sha256='pin',attempt=1))
  self.assertEqual((h/'EXIT.json').read_text(),'immutable');self.assertTrue((out/'cpu/HANDOFF-ERROR.json').exists())

 def test_full72_cpu_merge_and_corruption_counterexample(self):
  # Test-only synthetic operands stay under TemporaryDirectory; no production receipt.
  candidate=self.root/'candidate';reference=self.root/'reference';popref=self.put('POP.json',self.population);preds={};files={}
  for item in self.items:
   arrays,result=self.operand(item);key=self.N.digest(item)
   dest=candidate/'operands'/key;dest.parent.mkdir(parents=True,exist_ok=True);self.P.persist_operand(dest,arrays,result);preds[item['i']]=result['prediction']
   baseline=reference/'items/reference'/key;baseline.parent.mkdir(parents=True,exist_ok=True);r=copy.deepcopy(result);r['variant']='reference';self.P.persist_operand(baseline,arrays,r)
   for name in ('COMMITTED.json','operands.npz','result.json'):files[str(baseline/name)]=B.sha(baseline/name)
  for sid in (0,1):self.S.run_shard(popref,sid,candidate/'shards'/str(sid),lambda item:preds[item['i']],lambda pred,item,b:self.assertEqual(pred,preds[item['i']]),contract=self.contract())
  baseline_plan=self.put('BASELINE.json',dict(self.bp,out=str(reference)));evidence=self.put('EVIDENCE.json',{'files':files});rp=self.put('REVIEW.json',{'fixture_only':True})
  d={'out':str(candidate),'population':popref,'model_sha256':self.model['model_manifest_sha256'],'contract_sha256':self.bp['contract_sha256'],'baseline_plan':baseline_plan,'baseline_attempt':1,'baseline_result_review':rp,'baseline_evidence':evidence,'baseline_summary':rp,'baseline_terminal':rp,'modules':{'runtime':{'test':'runtime'},'dual_contract':{'test':'contract'},'consumer':B.ref(U.__file__)}}
  dp=self.put('CANDIDATE.json',d);runtime=types.SimpleNamespace(verify=lambda *a,**k:(d,{},self.population,self.L,self.N,self.P,self.contract(),self.S,self.items),pinned=B.pinned,full_operand=A.full_operand)
  def modules(x):return runtime if x==d['modules']['runtime'] else types.SimpleNamespace(acceptance=lambda *a,**k:True)
  with patch.object(U,'module',side_effect=modules),patch.object(U,'lifecycle'):
   out=U.consume(dp['path'],dp['sha256'],1);self.assertEqual(out['raw_operand_equal'],72);self.assertEqual(out['contract_sha256'],self.bp['contract_sha256']);self.assertEqual(out['reference_plan_sha256'],baseline_plan['sha256']);self.assertFalse(out['cross_card_equivalence'])
   victim=candidate/'operands'/self.N.digest(self.items[-1]);arrays,result=self.operand(self.items[-1]);arrays['logits'][0,0]=1
   import shutil
   shutil.rmtree(victim);self.P.persist_operand(victim,arrays,result)
   with self.assertRaises(ValueError):U.consume(dp['path'],dp['sha256'],1)
 def test_predictor_uses_registered_reference_collect_once(self):
  item=self.items[0];arrays,result=self.operand(item);obj=A.Predictor.__new__(A.Predictor);obj.d={'contract_sha256':self.bp['contract_sha256'],'model_sha256':self.model['model_manifest_sha256']};obj.p={'max_length':4096};obj.N=self.N;obj.L=self.L;obj.P=self.P;obj.out=self.root;obj.model=object();obj.tok=object();obj.ref=object();obj.engine=object();calls=[]
  import contextlib
  obj.torch=types.SimpleNamespace(inference_mode=contextlib.nullcontext);obj.collect=lambda *args:calls.append(args) or (arrays,result)
  first=obj(item);second=obj(item);self.assertEqual(first,second);self.assertEqual(len(calls),1);obj.validate(first,item,self.population['binding'])
 def test_reference_mismatched_tolerance_and_tokenizer_registry_reject(self):
  registry=copy.deepcopy(self.reg);registry['population']['tolerance']=1;rr=self.put('REGISTRY.json',registry);config=copy.deepcopy(self.cfg);config['registry_sha256']=__import__('hashlib').sha256(json.dumps(registry,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();cr=self.put('CONFIG.json',config);bp=copy.deepcopy(self.bp);bp['config']=cr;bp['registry']=rr;bp['files'].update({cr['path']:cr['sha256'],rr['path']:rr['sha256']});pr=self.put('BADPLAN.json',bp)
  with self.assertRaises(ValueError):B.reference(pr)
 def test_resource_generation_not_numeric_contract_in_population(self):
  b=self.population['binding'];self.assertEqual(b['source_execution'],self.rp);self.assertEqual(b['reference_config'],self.bp['config']);self.assertEqual(b['reference_registry'],self.bp['registry']);self.assertNotEqual(b['source_execution']['sha256'],b['contract_sha256'])

class ResourceTests(unittest.TestCase):
 def fixture(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name);out=root/'prev/output';h=out/'host_attempts/1';h.mkdir(parents=True);files={}
  def put(p,v):p.write_text(json.dumps(v));x=B.ref(p);files[x['path']]=x['sha256'];return x
  plan={'schema':'native-dev72-reference-execution-v1','run':'previous','chip':6,'allocation':str(root/'allocation'),'out':str(out),'container':'reference','image':'sha256:'+'a'*64}
  pp=put(root/'PLAN.json',plan);claim={'schema':'r3-resource-claim-v1','run':'previous','chip':6,'allocation':plan['allocation'],'scientific_acceptance':False,'execution_authorized':False};cp=put(h/'CLAIM.json',claim)
  free={'chip':6,'previous_run':'previous','release_evidence':str(h/'RELEASE.json')};alloc={'allocation':[],'free':[free],'pending_claims':[]};cmd=['docker','run',plan['image'],'python3','run.py']
  rel={'schema':'r3-resource-release-v1','run':'previous','chip':6,'claim_sha256':cp['sha256'],'container_id':'cid','container':'reference-a1','exit_code':0,'allocation_after':copy.deepcopy(alloc),'scientific_acceptance':False,'container_started_at':'2026-11-03T11:00:00Z','container_finished_at':'2026-11-03T11:01:00Z'};rp=put(h/'RELEASE.json',rel)
  sp=put(h/'LAUNCH_SPEC.json',{'plan_sha256':pp['sha256'],'command':cmd});rec=put(h/'LAUNCH_RECEIPT.json',{'container_id':'cid','plan_sha256':pp['sha256'],'command':['python3','run.py'],'attempt':1,'scientific_acceptance':False});pr=put(root/'PRIORITY.json',{'rationale':'independent CPU fixture'})
  q={'schema':'native-dev72-dual-shard-resource-v1','scientific_acceptance':False,'allocation':plan['allocation'],'writer_lock':plan['allocation']+'.lock','chip':6,'run':'candidate','free_entry':free,'pending_claims':[],'attempt':1,'predecessor':{'plan':pp,'claim':cp,'release':rp,'launch_spec':sp,'launch_receipt':rec},'priority_refs':[pr],'selection':'CPU fixture'};qp=put(root/'QUEUE.json',q)
  d={'schema':'native-dev72-dual-shard-execution-v1','test_read':False,'scientific_acceptance':False,'allocation':plan['allocation'],'chip':6,'run':'candidate','queue':qp,'files':files}
  actual={'Id':'cid','Image':plan['image'],'Config':{'Cmd':['python3','run.py']},'HostConfig':{'AutoRemove':False,'Privileged':False,'NetworkMode':'none','Devices':[{'PathOnHost':'/dev/'+x,'PathInContainer':'/dev/'+x} for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci6')]},'State':{'Status':'exited','Running':False,'ExitCode':0,'StartedAt':rel['container_started_at'],'FinishedAt':rel['container_finished_at']}}
  R=types.SimpleNamespace(read_bytes=lambda p:Path(p).read_bytes(),sha_bytes=lambda v:__import__('hashlib').sha256(v).hexdigest(),validate_doc=lambda x:None,docker_inspect=lambda n:actual,live_chip_conflict=lambda *x:False)
  return d,R,alloc,actual
 def test_exact_reference_physical_generation(self):
  d,R,alloc,a=self.fixture();r=Q.guard(d,R,alloc);self.assertTrue(r['physical_release_verified']);self.assertFalse(r['scientific_acceptance_required'])
 def test_retained_container_restart_timestamps_reject(self):
  for key in ('StartedAt','FinishedAt'):
   d,R,alloc,a=self.fixture();a['State'][key]='2026-11-03T23:00:00Z'
   with self.subTest(key=key),self.assertRaises(ValueError):Q.guard(d,R,alloc)
 def test_priority_owner_free_generation_and_live_conflict(self):
  for attack in ('priority','owner','free','live'):
   d,R,alloc,a=self.fixture()
   if attack=='priority':alloc['pending_claims']=[{'new':'priority'}]
   if attack=='owner':alloc['allocation']=[{'chip':6}]
   if attack=='free':alloc['free'][0]=dict(alloc['free'][0],previous_run='foreign')
   if attack=='live':R.live_chip_conflict=lambda *x:True
   with self.subTest(attack=attack),self.assertRaises(ValueError):Q.guard(d,R,alloc)
 def test_retained_image_command_devices_isolation_and_bool_exit(self):
  for attack in ('id','image','command','device','extra_device','privileged','network','autoremove','exit'):
   d,R,alloc,a=self.fixture()
   if attack=='id':a['Id']='foreign'
   if attack=='image':a['Image']='foreign'
   if attack=='command':a['Config']['Cmd']=['sh']
   if attack=='device':a['HostConfig']['Devices'][-1]['PathInContainer']='/dev/davinci0'
   if attack=='extra_device':a['HostConfig']['Devices'].append({'PathOnHost':'/dev/davinci0','PathInContainer':'/dev/davinci0'})
   if attack=='privileged':a['HostConfig']['Privileged']=True
   if attack=='network':a['HostConfig']['NetworkMode']='host'
   if attack=='autoremove':a['HostConfig']['AutoRemove']=True
   if attack=='exit':a['State']['ExitCode']=False
   with self.subTest(attack=attack),self.assertRaises(ValueError):Q.guard(d,R,alloc)
 def test_foreign_schema_and_chip_never_query_device(self):
  d,R,alloc,a=self.fixture();R.docker_inspect=lambda n:self.fail('unexpected query')
  for key,value in [('schema','native-dev72-shard-execution-v1'),('chip',True)]:
   with self.subTest(key=key),self.assertRaises(ValueError):Q.guard(dict(d,**{key:value}),R,alloc)

if __name__=='__main__':unittest.main()
