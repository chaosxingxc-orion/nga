"""Scoped K0 source and identity admission; synthetic controls stay in memory."""
import copy,json,types,unittest
from pathlib import Path
from unittest.mock import patch
from tools import r3_dev_qualification as Q
INPUT=Path('/home/xingchao/workspace/nga/.local/preparations/k0-member-evidence-20261103-v1')

class K0Scope(unittest.TestCase):
 def fixture(self):
  b=json.loads((INPUT/'k0_base-BUNDLE.json').read_text());e=b['entry'];x=json.loads(Path(e['execution']).read_text());s=json.loads(Path(x['spec']).read_text());return b,e,s
 def test_global_pairs_not_broadened(self):
  self.assertEqual(set(Q.SOURCE_COMPATIBILITY),{'provenance_r3','testlock_r3'})
  for n,(c,p) in Q.K0_RAW_SOURCE_PAIRS.items():self.assertFalse(Q.compatible_source(n,c,p))
 def test_real_scoped_pairs(self):
  for name in ('k0_base','k0_instruct'):
   b=json.loads((INPUT/(name+'-BUNDLE.json')).read_text());e=b['entry'];x=json.loads(Path(e['execution']).read_text());s=json.loads(Path(x['spec']).read_text())
   for n,(c,p) in Q.K0_RAW_SOURCE_PAIRS.items():self.assertTrue(Q.report_compatible_source(n,c,p,e,b,s))
 def test_wrong_source_and_scope_rejected(self):
  b,e,s=self.fixture();n,(c,p)=next(iter(Q.K0_RAW_SOURCE_PAIRS.items()))
  for nn,cc,pp in [('foreign',c,p),(n,p,c),(n,'0'*64,p),(n,c,'0'*64)]:self.assertFalse(Q.report_compatible_source(nn,cc,pp,e,b,s))
  for change in ('arm','plan','execution','closure','specpin','specbody','report-stage','partition','duplicate-flag','adapter'):
   bb,ee,ss=copy.deepcopy((b,e,s))
   if change=='arm':ee['arm']='K1'
   if change=='plan':ee['plan']='foreign'
   if change=='execution':bb['files'][ee['execution']]='0'*64
   if change=='closure':bb['files'][ee['producer_manifest']]='0'*64
   if change=='specpin':bb['files'][json.loads(Path(ee['execution']).read_text())['spec']]='0'*64
   if change=='specbody':ss['evaluation_profile']='r0'
   if change=='report-stage':ss['command'][ss['command'].index('--stages')+1]='k_score,t_score,report'
   if change=='partition':ss['command'][ss['command'].index('--partitions')+1]='test'
   if change=='duplicate-flag':ss['command']+=['--arm','K0']
   if change=='adapter':ss['adapter']='foreign'
   with self.subTest(change=change):self.assertFalse(Q.report_compatible_source(n,c,p,ee,bb,ss))
 def test_pinned_legacy_full_report_has_scoped_predicate(self):
  q=Q.legacy();self.assertIn('report_compatible_source',q.report.__code__.co_names)
  self.assertIn('verified_report',q.report.__code__.co_names)
  self.assertIn('evaluation_lineage',q.report.__code__.co_names)
 def identity_fixture(self):
  # No synthetic acceptance is persisted or passed to full member/campaign.
  plan=json.loads(Q.K0_CURRENT_PLAN.read_text());root=Path(plan['out']);cpu=root/'cpu/1';host=root/'host_attempts/1';docs={str(Q.K0_CURRENT_PLAN):plan};files={str(Q.K0_CURRENT_PLAN):Q.K0_CURRENT_PLAN_SHA}
  def add(p,d):docs[str(p)]=d;files[str(p)]='f'*64
  sample=json.loads(Path(plan['sample']['path']).read_text());add(plan['sample']['path'],sample);files[plan['sample']['path']]=plan['sample']['sha256']
  targets={k:{z:v[z] for z in ('execution','report','model')} for k,v in plan['targets'].items()}
  for t in targets.values():files[t['execution']['path']]=t['execution']['sha256'];files[t['report']['path']]=t['report']['sha256']
  rt={'exit_code':0,'attempt':1,'plan_sha256':Q.K0_CURRENT_PLAN_SHA,'scientific_acceptance':False}
  for p in (cpu/'EXIT.json',root/'cpu/host-1/EXIT.json',root/'attempts/1/EXIT.json'):add(p,dict(rt))
  add(host/'EXIT.json',dict(exit_code=0,container_exit_code=0,runner_terminal_matches=True,scientific_acceptance=False,container_id='a'*64))
  add(host/'CLAIM.json',dict(run=plan['run'],chip=plan['chip']))
  add(host/'RELEASE.json',dict(schema='r3-resource-release-v1',exit_code=0,scientific_acceptance=False,claim_sha256='f'*64,run=plan['run'],chip=plan['chip'],container_id='a'*64,container=plan['container']+'-a1'))
  add(root/'attempts/1/report.json',dict(identity={k:dict(sha256=t['model']['sha256']) for k,t in targets.items()},schema='r3-k0-current-control-report-v1',verdict='VERIFIED',plan_sha256=Q.K0_CURRENT_PLAN_SHA,attempt=1,sample_sha1=sample['sample_sha1'],own_failures=[],cross_passes=[],scientific_acceptance=False,test_read=False))
  add(cpu/'report.json',dict(schema='r3-k0-current-complete-v1',plan_sha256=Q.K0_CURRENT_PLAN_SHA,attempt=1,controls=dict(c32_cells=10,own_pass=10,counterpart_fail=10),reports={k:dict(execution_sha256=t['execution']['sha256'],report_sha256=t['report']['sha256'],canonical_json_identical=True,selection_only_strict_consumer=True) for k,t in targets.items()},npureport_sha256='f'*64,release_sha256='f'*64,sample_sha1=sample['sample_sha1'],scientific_acceptance=False,test_read=False))
  add(cpu/'COMPLETE.json',dict(exit_code=0,plan_sha256=Q.K0_CURRENT_PLAN_SHA,report_sha256='f'*64,scientific_acceptance=False))
  identity=dict(schema='r3-k0-current-identity-acceptance-v1',verdict='PASS',scientific_acceptance=False,test_read=False,independent_reconstruction=True,lifecycle_verified=True,reviewer='synthetic unit fixture only',control_plan=dict(path=str(Q.K0_CURRENT_PLAN),sha256=Q.K0_CURRENT_PLAN_SHA),attempt=1,controls_report=dict(path=str(cpu/'report.json'),sha256='f'*64),sample_sha1=sample['sample_sha1'],targets=targets)
  b,e,s=self.fixture();q=types.SimpleNamespace(bound=lambda p,f:docs[str(p)])
  return identity,e,files,q,docs,root
 def test_identity_binding_positive_in_memory_only(self):
  i,e,f,q,d,r=self.identity_fixture();self.assertEqual(Q.k0_identity_acceptance('k0_base',e,i,f,q)['attempt'],1)
 def test_generic_pass_and_identity_mutations_rejected(self):
  for key,value in [('schema','foreign'),('verdict','PASS_WITH_SCOPE'),('scientific_acceptance',True),('test_read',True),('independent_reconstruction',False),('lifecycle_verified',False),('reviewer',''),('control_plan',{}),('attempt',True),('attempt',2),('controls_report',{}),('sample_sha1','foreign'),('targets',{})]:
   i,e,f,q,d,r=self.identity_fixture();i[key]=value
   with self.subTest(key=key,value=value),self.assertRaises((ValueError,KeyError)):Q.k0_identity_acceptance('k0_base',e,i,f,q)
  i,e,f,q,d,r=self.identity_fixture()
  with self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,{'verdict':'PASS'},f,q)
 def test_single_runtime_perturbations_rejected(self):
  changes=[('cpu/1/EXIT.json','exit_code',False),('cpu/host-1/EXIT.json','exit_code',1),('attempts/1/EXIT.json','attempt',True),('host_attempts/1/EXIT.json','container_exit_code',1),('host_attempts/1/RELEASE.json','chip',False),('host_attempts/1/RELEASE.json','schema','foreign'),('host_attempts/1/RELEASE.json','exit_code',1),('host_attempts/1/RELEASE.json','claim_sha256','foreign'),('cpu/1/COMPLETE.json','report_sha256','foreign'),('cpu/1/report.json','controls',{'c32_cells':10,'own_pass':9,'counterpart_fail':10}),('attempts/1/report.json','identity',{}),('attempts/1/report.json','own_failures',['bad']),('attempts/1/report.json','cross_passes',['bad']),('cpu/1/report.json','release_sha256','foreign')]
  for rel,key,value in changes:
   i,e,f,q,d,r=self.identity_fixture();d[str(r/rel)][key]=value
   with self.subTest(rel=rel,key=key),self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,i,f,q)
 def test_member_and_other_target_binding_rejected(self):
  i,e,f,q,d,r=self.identity_fixture();e=copy.deepcopy(e);e['model']['sha256']='0'*64
  with self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,i,f,q)
  i,e,f,q,d,r=self.identity_fixture();d[str(r/'cpu/1/report.json')]['reports']['instruct']['report_sha256']='0'*64
  with self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,i,f,q)

if __name__=='__main__':unittest.main()
