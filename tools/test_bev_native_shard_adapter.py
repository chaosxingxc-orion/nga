import copy,json,shutil,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_shard_resource as Q
from tools import bev_native_shard_host as H
from tools import bev_native_shard_consume as U
from tools import bev_native_shard_adapter as A
from tools import bev_native_shard_contract as C
from tools import bev_native_shard_runner as S

PROBE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_dev_probe_preparation_20261102_v1/inference/plan.json')
BASELINE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_dev_execution_20261103_v4/HOST-PLAN.json')

@unittest.skipUnless(PROBE.exists(),'real DEV72 source unavailable')
class ActualDev72(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.p=A.read(PROBE);self.items=A.read(self.p['inputs']['path'])['items']
  self.req=self.root/'requests.jsonl';self.req.write_text(''.join(json.dumps(x)+'\n' for x in self.items));self.model=C.digest({x['path']:x['sha256'] for x in self.p['model_files'].values()});self.population=C.build_dev72(A.ref(PROBE),A.ref(self.req),self.model,A.ref(BASELINE));self.pop=self.root/'POPULATION.json';S.write_json(self.pop,self.population);self.ref=A.ref(self.pop)
 def test_sparse_ids_and_exact_parent_preserved(self):
  rows=S.load_requests(self.population['binding']);self.assertEqual(rows,self.items);self.assertEqual(rows[-1]['i'],159);self.assertEqual(self.population['shards'][1]['global_ordinals'][-1],71)
  for sid in (0,1):self.assertEqual(S.load_population(self.ref,sid)[1]['source_indices'],[x['i'] for x in self.items])
 def test_renumbered_and_reordered_population_rejects(self):
  for change in ('renumber','reorder'):
   rows=copy.deepcopy(self.items)
   if change=='renumber':
    for i,r in enumerate(rows):r['i']=i
   else:rows.reverse()
   self.req.write_text(''.join(json.dumps(x)+'\n' for x in rows))
   with self.assertRaises(ValueError):C.build_dev72(A.ref(PROBE),A.ref(self.req),self.model,A.ref(BASELINE))
 def test_real_saved_operand_validator_and_interrupted_resume(self):
  try:import numpy
  except ImportError:self.skipTest('numpy required for real saved operands')
  bp=A.read(BASELINE);L=A.module(bp['runtime']);N=A.module(self.p['runtime']);P=A.module(bp['probe']);out=self.root/'shard';calls=[]
  def predict(item):
   calls.append(item['i']);return L.load_operand(Path(bp['out'])/'items/reference'/N.digest(item),P,A.sha(BASELINE),item,N,'reference')[1]['prediction']
  def validate(pred,item,b):
   expected=L.load_operand(Path(bp['out'])/'items/reference'/N.digest(item),P,A.sha(BASELINE),item,N,'reference')[1]['prediction'];self.assertTrue(L.exact_json(pred,expected));self.assertEqual(b['model_sha256'],self.model)
  stop=self.items[38]['i']
  def fail(item):
   if item['i']==stop:raise RuntimeError('injected test failure')
   return predict(item)
  with self.assertRaises(RuntimeError):S.run_shard(self.ref,1,out,fail,validate)
  old=(out/'attempts/1/EXIT.json').read_bytes();calls.clear();r=S.run_shard(self.ref,1,out,predict,validate,attempt=2)
  self.assertEqual((r['computed'],r['reused']),(34,2));self.assertEqual(calls,[x['i'] for x in self.items[38:]]);self.assertEqual((out/'attempts/1/EXIT.json').read_bytes(),old);self.assertTrue((out/'items/000071/COMMITTED.json').exists())
 def test_real_predictor_revalidates_existing_full_operand(self):
  try:import numpy
  except ImportError:self.skipTest('numpy required')
  bp=A.read(BASELINE);L=A.module(bp['runtime']);N=A.module(self.p['runtime']);P=A.module(bp['probe']);obj=A.Predictor.__new__(A.Predictor);obj.d={'contract_sha256':A.sha(BASELINE),'model_sha256':self.model};obj.N=N;obj.L=L;obj.P=P;obj.out=self.root
  item=self.items[-1];src=Path(bp['out'])/'items/adapter'/N.digest(item);dst=self.root/'operands'/N.digest(item);dst.parent.mkdir();shutil.copytree(src,dst)
  pred=obj(item);obj.validate(pred,item,self.population['binding']);pred['first_index']=999
  with self.assertRaises(ValueError):obj.validate(pred,item,self.population['binding'])
  (dst/'COMMITTED.json').unlink()
  with self.assertRaises((ValueError,FileNotFoundError)):obj(item)
 def test_merge_maintains_source_order_and_rejects_missing_shard(self):
  b=self.population['binding'];parts=[]
  for sid in (0,1):
   manifest=self.population['shards'][sid];preds=[dict(i=self.items[i]['i'],qid=self.items[i]['qid'],request_sha256=self.items[i]['request_sha256'],input_sha256=C.digest(self.items[i])) for i in manifest['global_ordinals']]
   parts.append(dict(shard_id=sid,manifest_sha256=C.digest(manifest),exit_code=0,model_sha256=self.model,contract_sha256=b['contract_sha256'],scientific_acceptance=False,predictions=preds))
  result=C.merge_population(self.population,self.items,parts);self.assertEqual([x['i'] for x in result['predictions']],[x['i'] for x in self.items]);self.assertFalse(result['complete'])
  with self.assertRaises(ValueError):C.merge_population(self.population,self.items,parts[:1])

class ResourceAndHost(unittest.TestCase):
 def fixture(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);out=root/'previous/output';h=out/'host_attempts/1';h.mkdir(parents=True);files={}
  def put(path,x):path.write_text(json.dumps(x));r=A.ref(path);files[r['path']]=r['sha256'];return r
  plan={'schema':'native-config-execution-v1','run':'previous','chip':7,'allocation':str(root/'allocation'),'out':str(out),'container':'previous','image':'sha256:'+'a'*64}
  pp=put(root/'PLAN.json',plan);claim={'schema':'r3-resource-claim-v1','run':'previous','chip':7,'allocation':plan['allocation']};cp=put(h/'CLAIM.json',claim)
  free={'chip':7,'previous_run':'previous','release_evidence':str(h/'RELEASE.json')};allocation={'allocation':[],'free':[free],'pending_claims':[]}
  rel={'schema':'r3-resource-release-v1','run':'previous','chip':7,'claim_sha256':cp['sha256'],'allocation_after':allocation,'container_id':'cid','exit_code':1,'container':'previous-a1','scientific_acceptance':False};rp=put(h/'RELEASE.json',rel)
  hp=put(h/'EXIT.json',{'container_id':'cid','plan_sha256':pp['sha256'],'attempt':1,'scientific_acceptance':False});review=put(root/'REVIEW.json',{'verdict':'PASS','approved_plan_sha256':pp['sha256'],'scientific_acceptance':False});priority=put(root/'PRIORITY.json',{'selection':'fixture'})
  q={'schema':'native-shard-resource-successor-v1','scientific_acceptance':False,'allocation':plan['allocation'],'writer_lock':plan['allocation']+'.lock','chip':7,'run':'candidate','free_entry':free,'pending_claims':[],'attempt':1,'predecessor':{'plan':pp,'claim':cp,'release':rp,'host_exit':hp,'review':review},'priority_refs':[priority],'selection':'fixture selected'};qp=put(root/'POLICY.json',q)
  d={'schema':'native-dev72-shard-execution-v1','test_read':False,'scientific_acceptance':False,'allocation':plan['allocation'],'chip':7,'run':'candidate','queue':qp,'files':files}
  actual={'Id':'cid','Image':plan['image'],'State':{'Status':'exited','Running':False,'ExitCode':1}}
  R=types.SimpleNamespace(read_bytes=lambda p:Path(p).read_bytes(),sha_bytes=lambda b:__import__('hashlib').sha256(b).hexdigest(),validate_doc=lambda x:None,docker_inspect=lambda n:actual,live_chip_conflict=lambda *x:False)
  return d,R,allocation,actual
 def test_failed_predecessor_physical_release_can_feed_dev(self):
  d,R,a,actual=self.fixture();r=Q.guard(d,R,a);self.assertTrue(r['physical_release_verified']);self.assertFalse(r['scientific_acceptance_required'])
 def test_priority_change_owner_and_device_conflict_reject(self):
  for attack in ('priority','owner','device','container'):
   d,R,a,actual=self.fixture()
   if attack=='priority':a['pending_claims']=[{'new':'higher'}]
   elif attack=='owner':a['allocation']=[{'chip':7}]
   elif attack=='device':R.live_chip_conflict=lambda *x:True
   else:actual['Id']='foreign'
   with self.assertRaises(ValueError):Q.guard(d,R,a)
 def test_cpu_handoff_failure_preserves_npu_terminal(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);h=root/'host_attempts/1';h.mkdir(parents=True);terminal=h/'EXIT.json';terminal.write_text('unchanged')
   d={'out':str(root),'modules':{'consumer':{'path':'fixture','sha256':'x'}}};args=types.SimpleNamespace(plan='plan',sha256='pin',attempt=1)
   with patch.object(H,'module',return_value=types.SimpleNamespace(start=lambda *x:(_ for _ in ()).throw(OSError('failure')))):H.handoff_cpu(d,args)
   self.assertEqual(terminal.read_text(),'unchanged');self.assertTrue((root/'cpu/HANDOFF-ERROR.json').exists())
 def test_runtime_load_failure_records_terminal(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'PLAN.json';p.write_text(json.dumps({'out':str(root/'output')}))
   with patch.object(A,'verify',side_effect=ValueError('fixture malformed')):
    with self.assertRaises(ValueError):A.run(str(p),A.sha(p),1)
   e=A.read(root/'output/attempts/1/EXIT.json');self.assertEqual(e['exit_code'],1);self.assertFalse(e['scientific_acceptance']);self.assertTrue((root/'output/attempts/1/heartbeat.json').exists())

 def test_consumer_start_requires_physical_release_first(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'PLAN.json';p.write_text('{}');d={'out':str(Path(td)/'output')}
   with patch.object(U,'lifecycle',side_effect=ValueError('release missing')),patch.object(U.subprocess,'Popen') as popen:
    with self.assertRaises(ValueError):U.start(d,str(p),U.sha(p),1)
    popen.assert_not_called()

 def test_cpu_consumer_not_visible_directly_or_through_ancestor(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);consumer=root/'cpu/consume.py';evidence=root/'cpu/baseline.json';model=root/'model';runtime=root/'code/runtime.py';out=root/'output'
   d={'model':str(model),'modules':{'consumer':{'path':str(consumer),'sha256':'a'*64}},'baseline_evidence':{'path':str(evidence),'sha256':'b'*64},'files':{str(consumer):'a'*64,str(evidence):'b'*64,str(runtime):'c'*64},'out':str(out)}
   mounts=A.mounts(d,str(root/'PLAN.json'));self.assertFalse(any(Path(x).is_relative_to(m['source']) for x in A.cpu_only(d) for m in mounts))
   d['out']=str(root)
   with self.assertRaises(ValueError):A.mounts(d,str(root/'PLAN.json'))
   d['out']=str(out);d['model']=str(root/'cpu')
   with self.assertRaises(ValueError):A.mounts(d,str(root/'PLAN.json'))

if __name__=='__main__':unittest.main()
