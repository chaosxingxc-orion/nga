import copy, hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent

def module(name):
 s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
R=module('r3_formal_roles');L=module('r3_formal_launcher');D=module('r3_formal_driver')

class Roles(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.code=self.root/'code';self.code.mkdir();self.model=self.root/'model';self.model.mkdir();self.weight=self.model/'weights';self.weight.write_bytes(b'weights');self.train=self.root/'train.jsonl';self.train.write_bytes(b'train')
  codes={}
  for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
   p=self.code/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(b'code');codes[rel]=R.sha(p)
  self.d={'schema':'r3-formal-role-schedule-v1','scientific_acceptance':False,'test_read':False,'floor_gating_role':'diffchip_s2','samechip_gates':False,'floor_replicates_excluded_from_all_candidate_estimators':True,'physical_chips':[1,2],'shared_inputs':{str(self.train):R.sha(self.train),str(self.weight):R.sha(self.weight)},'code_by_relative_path':codes,'nodes':[]}
  deps={'primary_s2':[], 'primary_s3':[], 'samechip_s2':['primary_s2_release'],'diffchip_s2':['primary_s3_release']}
  devdeps={'primary_s2':['samechip_s2_release'],'samechip_s2':['primary_s2_dev_release'],'primary_s3':['diffchip_s2_release'],'diffchip_s2':['primary_s3_dev_release']}
  for role in R.ROLES:
   seed=3 if role=='primary_s3' else 2;chip=1 if role in ('primary_s2','samechip_s2') else 2;out=str(self.root/role)
   self.d['nodes'].append(dict(id=role,role=role,kind='training',seed=seed,chip=chip,steps=3116,out=out,container=role,candidate_for_seed_mean=role.startswith('primary_'),depends_on=deps[role],command_candidate=['python3','--out',out,'--seed',str(seed),'--steps','3116']))
   self.d['nodes'].append(dict(id=role+'_dev',kind='dev_calibration_track_t_readout',training_id=role,chip=chip,out=str(self.root/(role+'_dev')),test_read=False,same_scorer_and_population_as_primary=True,depends_on=devdeps[role]))
  self.path=self.root/'schedule.json';self.write()
 def write(self):self.path.write_text(json.dumps(self.d));self.pin=R.sha(self.path)
 def plan(self,role):
  n=next(n for n in self.d['nodes'] if n['id']==role)
  return dict(schema='r3-formal-k1-plan-v1',scientific_acceptance=False,test_read=False,formal_schedule=str(self.path),formal_schedule_sha256=self.pin,formal_role=role,formal_chips=[1,2],code=str(self.code),model=str(self.model),train_file=str(self.train),files={str(self.path):self.pin,**self.d['shared_inputs'],**{str(self.code/k):v for k,v in self.d['code_by_relative_path'].items()},str(HERE/'r3_formal_roles.py'):R.sha(HERE/'r3_formal_roles.py')},evaluation={'candidate_for_adoption':n['candidate_for_seed_mean'],'test_requires_separate_final_ticket':True},**{k:n[k] for k in ['seed','chip','out','container']},command=n['command_candidate'])
 def test_four_roles_with_common_chip_list(self):
  for r in R.ROLES:L.formal_target_identity(self.plan(r))
 def test_mutated_roles_seed_chip_membership_recipe_inventory_order_rejected(self):
  for field,value in [('chip',1),('seed',3),('candidate_for_seed_mean',True),('role','samechip_s2'),('out',str(self.root/'primary_s2')),('container','primary_s2'),('depends_on',[])]:
   with self.subTest(field=field):
    d=copy.deepcopy(self.d);n=next(n for n in d['nodes'] if n['id']=='diffchip_s2');n[field]=value
    with self.assertRaises(RuntimeError):R.validate_schedule(d)
  d=copy.deepcopy(self.d);d['nodes'][4]['command_candidate'][-1]='20'
  with self.assertRaises(RuntimeError):R.validate_schedule(d)
 def test_plan_changed_hash_and_role_rejected(self):
  for field,value in [('formal_role','samechip_s2'),('chip',1),('seed',3),('container','other'),('formal_schedule_sha256','0'*64),('formal_chips',[2,1])]:
   with self.subTest(field=field):
    p=self.plan('diffchip_s2');p[field]=value
    with self.assertRaises(RuntimeError):R.validate_plan(p)
 def test_auxiliary_cannot_enter_candidate_membership(self):
  p=self.plan('diffchip_s2');p['evaluation']['candidate_for_adoption']=True
  with self.assertRaises(RuntimeError):R.validate_plan(p)
 def test_shared_input_bytes_change_rejected(self):
  p=self.plan('primary_s2');self.weight.write_bytes(b'new')
  with self.assertRaises(RuntimeError):R.validate_plan(p)
 def test_partial_binding_cannot_fall_back_to_legacy(self):
  p=self.plan('primary_s2');del p['formal_schedule']
  with self.assertRaises(RuntimeError):L.formal_target_identity(p)
 def test_new_atomic_writers_explicit_readable_under_restrictive_umask(self):
  old=os.umask(0o077)
  try:
   for mod in (L,D):
    path=self.root/(mod.__name__+'.json');mod.atomic(path,{'exit_code':0});self.assertEqual(path.stat().st_mode&0o777,0o644)
  finally:os.umask(old)
 def test_comparison_rejects_auxiliary_and_mixed_wave(self):
  C=module('r3_development_compare')
  reports=[{'selection_evidence':{'seed':seed,'formal_role_identity':{'role':role,'seed':seed,'schedule_sha256':'a'*64,'candidate_for_adoption':True}}} for seed,role in [(2,'primary_s2'),(3,'primary_s3')]]
  C.candidate_roles(reports,"a"*64)
  for field,value in [('role','samechip_s2'),('candidate_for_adoption',False),('schedule_sha256','other')]:
   changed=copy.deepcopy(reports);changed[0]['selection_evidence']['formal_role_identity'][field]=value
   with self.assertRaises(ValueError):C.candidate_roles(changed,"a"*64)
 def test_successor_requires_its_own_exact_role_and_schedule_binding(self):
  S=module('r3_formal_train_successor');p=self.plan('diffchip_s2')
  p.update(launcher=str(HERE/'r3_formal_launcher.py'),adapter=str(HERE/'r3_resource_adapter.py'),driver=str(HERE/'r3_formal_driver.py'))
  for k in ('launcher','adapter','driver'):p['files'][p[k]]=R.sha(p[k])
  root=Path(p['out']);root.mkdir();path=root/'plan.json';path.write_text(json.dumps(p))
  j={'plan':str(path),'plan_raw_sha256':R.sha(path),'plan_sha256':S.identity(p),'chip':2,'attempt':1,'formal_role':'diffchip_s2','formal_schedule_sha256':self.pin}
  self.assertEqual(S.plan(j,reviewed=False)['formal_role'],'diffchip_s2')
  for k,v in [('formal_role','primary_s2'),('formal_schedule_sha256','wrong')]:
   with self.assertRaises(RuntimeError):S.plan(dict(j,**{k:v}),reviewed=False)
 def test_posttrain_auxiliary_role_survives_materialization(self):
  P=module('r3_posttrain_eval_plan');p=self.plan('samechip_s2');p.update(launcher=str(HERE/'r3_formal_launcher.py'),image_sha256='image',arm='k1')
  root=Path(p['out']);root.mkdir();(root/'plan.json').write_text(json.dumps(p));(root/'TRAIN_EXIT.json').write_text('{"exit_code":0}')
  (root/'manifest.json').write_text(json.dumps({'summary':{'final_step':3116},'args':{'seed':2}}));adapter=root/'adapter';adapter.mkdir()
  for n in ('adapter_config.json','adapter_model.safetensors'):(adapter/n).write_bytes(b'fixture')
  closure=self.root/'closure';closure.mkdir();(closure/'manifest.json').write_text(json.dumps({'data':{},'code':{},'mounts':[],'command_template':['python','--arm','K1','--adapter','<COMPLETED_ADAPTER>']}))
  out=self.root/'materialized';P.prepare(root,closure,out);spec=json.loads((out/'plan.json').read_text())
  self.assertEqual(spec['training_variant']['formal_role_identity']['role'],'samechip_s2')
  self.assertFalse(spec['training_variant']['formal_role_identity']['candidate_for_adoption'])
  self.assertEqual(spec['files'][str(self.path)],self.pin)
 def test_comparator_refuses_swapped_missing_and_unexpected_wave(self):
  C=module('r3_development_compare')
  reports=[{'selection_evidence':{'seed':seed,'formal_role_identity':{'role':'primary_s'+str(seed),'seed':seed,'schedule_sha256':'a'*64,'candidate_for_adoption':True}}} for seed in (2,3)]
  for pin in (None,'','wave','b'*64):
   with self.assertRaises(ValueError):C.candidate_roles(reports,pin)
  for role,pin in [('primary_s3','a'*64),('primary_s2',None),('primary_s2','')]:
   changed=copy.deepcopy(reports);changed[0]['selection_evidence']['formal_role_identity'].update(role=role,schedule_sha256=pin)
   with self.assertRaises(ValueError):C.candidate_roles(changed,'a'*64)
 def test_release_bound_id_and_timeout(self):
  attempt=self.root/'attempt';attempt.mkdir();(attempt/'LAUNCH_RECEIPT.json').write_text(json.dumps({'id':'exact'}));p={'adapter':'/adapter','allocation':'/allocation','run':'run','chip':1}
  with patch.object(L.subprocess,'run') as run:L.adapter(p,'release',attempt,'name')
  self.assertEqual(run.call_args.kwargs['timeout'],300);self.assertEqual(run.call_args.args[0][-2:],['--container-id','exact'])

if __name__=='__main__':unittest.main()
