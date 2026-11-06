#!/usr/bin/env python3
"""Generated-only mathematical and adversarial integration checks."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
import consumer as N
GENERATED=P/'scratch/generated'

class Checks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.config=N.read(GENERATED/'consumer-config.json');cls.packet=N.read(cls.config['packet']['path'])
  cls.mods=N.instrument(cls.packet);cls.pop=N.populations(cls.packet,cls.mods[0]);cls.role=cls.packet['roster'][0]
 def validate(self,packet=None,role=None):return N.member(packet or self.packet,role or self.role,self.pop,self.mods)
 def change(self,key,value):
  packet=copy.deepcopy(self.packet);packet[key]=value;return packet
 def assert_auth_reject(self,packet,needle):
  with tempfile.TemporaryDirectory(dir=P/'scratch') as d:
   path=Path(d)/'packet.json';N.save(path,packet);pin={'path':str(path),'sha256':N.sha(path)}
   config={**self.config,'packet':pin}
   with self.assertRaisesRegex(ValueError,needle):N.authenticate(packet,config,pin)
 def mutate_file(self,evkey,change,needle,refresh=True):
  packet=copy.deepcopy(self.packet);ev=packet['members'][self.role['id']];path=Path(ev[evkey]['path']);before=path.read_bytes()
  try:
   doc=N.read(path);change(doc);N.save(path,doc)
   if refresh:
    ev[evkey]['sha256']=N.sha(path);packet['authorized_files'][str(path)]=N.sha(path)
   with self.assertRaisesRegex((ValueError,RuntimeError),needle):self.validate(packet)
  finally:path.write_bytes(before)
 def test_01_complete_cli_all_sizes_suites_rules(self):
  result=N.read(P/'scratch/comparison/comparison.json')
  self.assertEqual(result['status'],'partial');self.assertEqual(result['own_base_status'],'complete');self.assertEqual(result['reference_alignment_status'],'pending');self.assertTrue(result['fixture_only']);self.assertFalse(result['publication_authorized'])
  self.assertEqual(len(result['roster']),12);self.assertEqual(len(result['comparisons']),8)
  for cell in result['comparisons'].values():
   self.assertEqual(cell['status'],'complete')
   for rule in ('raw','r0'):
    panel=cell['rules'][rule]
    self.assertEqual(set(panel['per_seed_descriptive']),{'2','3'})
    for seed in panel['per_seed_descriptive'].values():self.assertEqual(sum(seed['paired_discordants'].values()),N.SUITES[cell['suite']])
    interval=panel['two_seed_mean']['historical_bootstrap']
    self.assertEqual((interval['resamples'],interval['rng_seed'],interval['ci_level']),(10000,20261030,.9))
    self.assertEqual(interval['n'],N.SUITES[cell['suite']])
  self.assertGreater(len({c['worker_pid'] for c in result['comparisons'].values()}),1)
 def test_02_historical_bootstrap_handcomputable(self):
  fn=N.bootstrap(self.packet)
  for a,b,expected in [([1,1],[0,0],1),([0,0],[1,1],-1),([.5,.5],[.5,.5],0)]:
   r=fn(a,b);self.assertEqual((r['mean_difference'],r['ci_lower'],r['ci_upper']),(expected,)*3)
  # Independent enumeration for n=2: all empirical delta means are -1,0,+1,
  # and the 5th/95th percentiles must be -1/+1 for the fixed 10000 draws.
  r=fn([1,0],[0,1]);self.assertEqual((r['mean_difference'],r['ci_lower'],r['ci_upper']),(0,-1,1))
 def test_03_probability_handcalculations_and_edges(self):
  RM=self.mods[-1];r=RM.summarize([[0.,0.],[0.]], [1,0])
  self.assertEqual(r['accuracy'],.5);self.assertEqual(r['tie_count'],1)
  self.assertAlmostEqual(r['nll'],math.log(2)/2);self.assertEqual(r['brier_sum'],.25);self.assertEqual(r['ece10'],.25)
  self.assertEqual(r['ece10_bins'][5]['n'],1);self.assertEqual(r['ece10_bins'][9]['n'],1)
  self.assertIsNone(r['ece10_bins'][0]['accuracy'])
  extreme=RM.summarize([[1000.,-1000.]],[1]);self.assertEqual(extreme['nll'],2000)
  ece,bins=RM.ece10([0,1,0],[.3,.30000000000000004,1.]);self.assertEqual([b['n'] for b in bins],[0,0,1,1,0,0,0,0,0,1])
 def test_04_ties_singletons_strata(self):
  C=self.mods[0];rows=copy.deepcopy(self.pop['decision-v7/test/clean'][:2]);rows[1]['levels']=rows[1]['levels'][:1];rows[1]['gold']=rows[1]['levels'][0]['id']
  h=C.headline(rows,[[0.,0.],[0.]])
  self.assertEqual(h['kev_rule_accuracy'],1.);self.assertEqual(h['r0_rule_accuracy'],.5);self.assertEqual(h['tie_count'],1)
  census=C.near_tie_census([[0.,0.],[0.],[-.001,0.],[-.01,0.],[-.1,0.]])
  self.assertEqual((census['n_one_option'],census['exact_tie_count'],census['n_gap_le_tau'],census['n_gap_le_10tau'],census['n_gap_le_100tau']),(1,1,2,3,4))
 def test_05_actual_completed_scope_no_new_ticket_or_writes(self):
  import testlock_r3 as TL
  before={p:N.sha(p) for p in self.packet['authorized_files']}
  with patch.object(TL,'authorize_test_read',side_effect=AssertionError('new ticket')),patch.object(TL,'record_test_read',side_effect=AssertionError('new completion')):
   lane=self.validate()
  self.assertEqual(lane['status'],'reconstructed');self.assertEqual(before,{p:N.sha(p) for p in before})
 def test_06_wrong_seed_size_and_fixed_role(self):
  for field,value in [('seed',3),('size','q9b'),('terminal_step',3000),('arm','K0')]:
   packet=copy.deepcopy(self.packet);packet['roster'][0][field]=value
   self.assert_auth_reject(packet,'wrong')
 def test_07_wrong_source_revision(self):
  packet=copy.deepcopy(self.packet);packet['producer']['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'changed bytes|wrong producer'):N.instrument(packet)
 def test_08_failed_phase_not_masked_by_missing_sibling(self):
  self.mutate_file('infer_exit',lambda d:d.update(exit_code=1),'failed/mismatched infer')
 def test_09_mode_revision_population(self):
  self.mutate_file('identity',lambda d:d.update(base_revision='other'),'model identity digest')
  self.mutate_file('ready',lambda d:d['descriptor'].update(mode='leftpad'),'non-record scorer')
 def test_10_missing_threshold_table(self):
  self.mutate_file('fit',lambda d:d.pop('entries'),'report handoff/fit pin differs')
  # Hash-refresh report too so table semantics, not only file linkage, must fail.
  packet=copy.deepcopy(self.packet);ev=packet['members'][self.role['id']];paths=[Path(ev[k]['path']) for k in ('fit','report')];before=[p.read_bytes() for p in paths]
  try:
   fit=N.read(paths[0]);fit.pop('entries');N.save(paths[0],fit);ev['fit']['sha256']=N.sha(paths[0]);packet['authorized_files'][str(paths[0])]=N.sha(paths[0])
   report=N.read(paths[1]);report['operator_fit_artifact']=ev['fit'];N.save(paths[1],report);ev['report']['sha256']=N.sha(paths[1]);packet['authorized_files'][str(paths[1])]=N.sha(paths[1])
   with self.assertRaisesRegex(ValueError,'fitted tau table differs'):self.validate(packet)
  finally:
   for p,b in zip(paths,before):p.write_bytes(b)
 def test_11_changed_store_bytes(self):
  C=self.mods[0];path=Path(C.k_readout_path(self.packet['members'][self.role['id']]['ready']['path'].rsplit('/',1)[0],'decision-v7','test','clean'));before=path.read_bytes()
  try:
   path.write_bytes(before+b'\n')
   with self.assertRaisesRegex(ValueError,'changed store/receipt bytes'):self.validate()
  finally:path.write_bytes(before)
 def test_12_candidate_gold_nonfinite_and_order(self):
  C,_,_,_,SE,_,_=self.mods;rows=self.pop['decision-v7/test/clean'];stored=[C.readout_row(r,[0.,-1.]) for r in rows]
  for kind in ('ids','gold','s','argmax'):
   bad=copy.deepcopy(stored)
   if kind=='ids':bad[0]['ids'].reverse()
   elif kind=='gold':bad[0]['gold']='b'
   elif kind=='s':bad[0]['s'][0]=math.nan
   else:bad[0]['argmax']=1
   with self.assertRaises(ValueError):SE.validate_population(bad,rows,C.kev_key)
 def test_13_equal_metric_vector_swap_cannot_reuse_old_receipt(self):
  C=self.mods[0];ev=self.packet['members'][self.role['id']];path=Path(C.k_readout_path(str(Path(ev['ready']['path']).parent),'decision-v7','test','clean'));before=path.read_bytes()
  try:
   rows=[json.loads(s) for s in before.splitlines()];i,j=0,2
   self.assertEqual(rows[i]['gold'],rows[j]['gold'])
   self.assertNotEqual(rows[i]['s'],rows[j]['s'])
   accuracy=sum(r['argmax']==r['gold_index'] for r in rows)
   for field in ('s','argmax','tie'):rows[i][field],rows[j][field]=rows[j][field],rows[i][field]
   self.assertEqual(sum(r['argmax']==r['gold_index'] for r in rows),accuracy)
   path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'changed store/receipt bytes'):self.validate()
  finally:path.write_bytes(before)
 def test_14_report_metric_tamper(self):
  self.mutate_file('report',lambda d:d['track_k']['partitions']['decision-v7/test']['arms']['uniform'].update(kev_rule_accuracy=.999),'persisted Track K metrics')
  self.mutate_file('report',lambda d:d['probability_panels']['decision-v7/test/clean'].update(nll=.001),'persisted binary64 probability')
 def test_15_missing_evidence_cannot_be_promoted_to_production(self):
  p=copy.deepcopy(self.packet);p['kind']='production'
  self.assert_auth_reject(p,'production disabled')
  p=copy.deepcopy(self.packet);p['members'][self.role['id']].pop('fit')
  with self.assertRaisesRegex(ValueError,'completed evidence inventory'):self.validate(p)
 def test_16_missing_seed_and_failed_lane_both_visible(self):
  with tempfile.TemporaryDirectory(dir=P/'scratch') as d:
   p=copy.deepcopy(self.packet);p['members']={self.role['id']:p['members'][self.role['id']]}
   ev=p['members'][self.role['id']];f=Path(ev['infer_exit']['path']);before=f.read_bytes()
   try:
    x=N.read(f);x['exit_code']=1;N.save(f,x);ev['infer_exit']['sha256']=N.sha(f);p['authorized_files'][str(f)]=N.sha(f)
    pp=Path(d)/'packet.json';N.save(pp,p);cfg={**self.config,'packet':{'path':str(pp),'sha256':N.sha(pp)}};cp=Path(d)/'config.json';N.save(cp,cfg)
    r=N.run(cp,Path(d)/'out')
    self.assertEqual(r['roster'][self.role['id']]['status'],'invalid');self.assertIn('failed/mismatched infer',r['roster'][self.role['id']]['reason'])
    self.assertEqual(r['roster']['q0p8b-s3']['status'],'missing');self.assertEqual(r['comparisons']['q0p8b/decision-v7']['status'],'unavailable')
    self.assertIsNone(r['descriptive_historical_criterion_indicator']['q0p8b']['raw']['value'])
   finally:f.write_bytes(before)
 def test_17_identical_receipts_skip_recompute(self):
  out=P/'scratch/comparison';before=(out/'comparison.json').read_bytes()
  with patch.object(N,'member',side_effect=AssertionError('reconstructed unchanged receipt')):
   N.run(GENERATED/'consumer-config.json',out)
  self.assertEqual((out/'comparison.json').read_bytes(),before);self.assertIn('skipped',N.read(out/'poll.json')['status'])
 def test_18_exact_fraction_indicator_boundaries(self):
  cells={}
  for size in N.SIZES:
   for suite in N.SUITES:
    delta=(1,100) if suite=='decision-v7' else (-1,100)
    e={'numerator':delta[0],'denominator':delta[1]}
    cells[f'{size}/{suite}']={'status':'complete','rules':{r:{'two_seed_mean':{'exact_difference':e,'interval_percentage_points':[-2,2]}} for r in ('raw','r0')}}
  self.assertTrue(N.historical_indicator(cells)['q0p8b']['raw']['value'])
  cells['q0p8b/transfer-v4']['rules']['raw']['two_seed_mean']['exact_difference']={'numerator':-11,'denominator':1000}
  self.assertFalse(N.historical_indicator(cells)['q0p8b']['raw']['value'])

 def test_19_frozen_permutation_and_nota_handcalculations(self):
  C,V,_,_,_,_,_=self.mods
  rows=copy.deepcopy(self.pop['decision-v7/test/clean'][:2]);variants=[];scores={C.kev_key(r):[0.,-2.] for r in rows}
  for i,parent in enumerate(rows):
   v=copy.deepcopy(parent);v['variant']='permuted';v['kev']['parent_id']=v['kev']['id'];v['kev']['id']+='-p';v['levels'].reverse();variants.append(v)
   scores[C.kev_key(v)]=[-2.,0.] if i==0 else [0.,0.]
  metrics=V.permutation_metrics(V.build_permutation_pairs(rows,variants),scores,arm_kind='K1')
  self.assertEqual((metrics['n_pairs_total'],metrics['n_dropped_tied_pairs'],metrics['n'],metrics['n_flips']),(2,1,1,0))
  self.assertEqual(metrics['discrimination_counterpart']['permuted_rows_accuracy']['n'],2)
  parent=rows[0];variants=[]
  for kind in ('none_present','none_absent'):
   r=copy.deepcopy(parent);r['variant']=kind;r['kev']['parent_id']=r['kev']['id'];r['kev']['id']+='-'+kind;r['kev']['none_key']='none';r['levels'].append({'id':'none','name':'none','definition':'none'})
   if kind=='none_absent':r['gold']='none'
   variants.append(r);scores[C.kev_key(r)]=[0.,-2.,-3.] if kind=='none_present' else [-3.,-2.,0.]
  m=V.nota_metrics(V.build_nota_units([parent],variants),scores)
  self.assertEqual(m['kev_rule']['both_sides_right'],1);self.assertEqual(m['r0_rule']['both_sides_right'],1)
  scores[C.kev_key(variants[0])]=[0.,0.,-2.]
  m=V.nota_metrics(V.build_nota_units([parent],variants),scores)
  self.assertEqual(m['kev_rule']['both_sides_right'],1);self.assertEqual(m['r0_rule']['both_sides_right'],0)
 def test_20_operator_fitting_grid_and_fallback(self):
  C,V,_,_,_,_,_=self.mods
  rows=copy.deepcopy(self.pop['decision-v7/calibration/clean'][:20])
  for r in rows:r['gold']='a'
  fitted=V.fit_operator(rows,[[0.,-2.]]*20)
  self.assertEqual(V.operator_decision(fitted,rows[0],[0.,-2.])[1],.85)
  transfer=copy.deepcopy(rows[0]);transfer['source']='transfer-v4'
  self.assertEqual(V.operator_decision(fitted,transfer,[0.,-2.])[1:],(.5,'default'))
  wrong=V.fit_operator(rows,[[-2.,0.]]*20)
  self.assertEqual(V.operator_decision(wrong,rows[0],[0.,-2.])[1],.95)
 def test_21_same_base_runtime_and_population_refusals(self):
  b=self.validate();b['identity']=b['base_identity'];a=copy.deepcopy(b);c=copy.deepcopy(b)
  for field in ('runtime','tokenizer','descriptor','base_identity'):
   bad=copy.deepcopy(a);bad[field]={'changed':True}
   with self.assertRaisesRegex(ValueError,'runtime-confounded|base bytes'):
    N.comparison_job((self.packet,'q0p8b','decision-v7',[b,bad,c]))
  bad=copy.deepcopy(a);bad['vectors']['decision-v7']['keys'].reverse()
  with self.assertRaisesRegex(ValueError,'paired population differs'):
   N.comparison_job((self.packet,'q0p8b','decision-v7',[b,bad,c]))
 def test_22_generated_schema_valid(self):
  import jsonschema
  schema=N.read(P/'packet.schema.json');jsonschema.Draft202012Validator.check_schema(schema)
  jsonschema.validate(self.packet,schema)

 def test_23_external_trust_anchor_and_source_closure(self):
  # These are GENERATED policy-injection probes, never production receipts.
  # Even a declaration of accepted=true cannot authenticate a different source
  # closure, missing current model bindings, or fixture payload as production.
  packet=copy.deepcopy(self.packet);packet['kind']='production';packet.pop('fixture_only')
  acceptance=N.read(P.parent/'rc1-test-integrated-review/CORE-ACCEPTANCE.json')
  fake_acceptance={'path':'/generated/acceptance.json','sha256':'a'*64}
  fake_review={'path':'/generated/review.json','sha256':'b'*64}
  pp={'path':'/generated/packet.json','sha256':'c'*64}
  config={**self.config,'allow_production':True,'packet':pp,'source_acceptance':fake_acceptance,'completed_access_review':fake_review}
  bindings={r['id']:{'identity_sha256':r['identity_sha256'],'model':r['model'],'adapter':r['adapter'],'evidence':r['evidence']} for r in packet['roster']}
  review={'schema':'rc1-numerical-completed-access-review-v1','accepted':True,'packet_sha256':pp['sha256'],'new_test_access':False,'scope':'reconstruct-authorized-saved-vectors-only',
          'source_acceptance':fake_acceptance,'authorized_files':packet['authorized_files'],'model_bindings':bindings}
  def load(path):return review if path==fake_review['path'] else acceptance
  with patch.object(N,'pin',side_effect=lambda p:p['path']),patch.object(N,'read',side_effect=load):
   with self.assertRaisesRegex(ValueError,'frozen manifest differs|fixture|generated identity'):
    N.authenticate(packet,config,pp)
   wrong=copy.deepcopy(packet);wrong['source_files']['/unknown.py']='f'*64
   with self.assertRaisesRegex(ValueError,'source closure differs'):
    N.authenticate(wrong,config,pp)
   review['model_bindings']={}
   with self.assertRaisesRegex(ValueError,'reviewed model/publication/runtime bindings differ'):
    N.authenticate(packet,config,pp)
 def test_24_probability_deterioration_stays_visible(self):
  result=N.read(P/'scratch/comparison/comparison.json')
  for cell in result['comparisons'].values():
   self.assertEqual(set(cell['probability_differences_vs_own_base']),{'2','3'})
   for seed in cell['probability_differences_vs_own_base'].values():
    for v in seed.values():
     self.assertEqual(v['difference'],v['candidate']-v['base'])
     if v['difference']>0:self.assertEqual(v['direction'],'worsened')

 def test_25_constant_uniform_and_discordant_handcounts(self):
  C,_,D,_,_,_,_=self.mods
  train=copy.deepcopy(self.pop['decision-v7/train/clean'][:3])
  train[0]['gold']='b';train[1]['gold']='b';train[2]['gold']='a'
  fit=D.fit_constant(train)
  rows=copy.deepcopy(train)
  rows[1]['source']='new-source';rows[2]['source']='new-source';rows[2]['level_type']='ordinal'
  scores,tiers=D.score_constant(fit,rows)
  self.assertEqual(tiers,{'question':1,'position':1,'position0':1})
  self.assertEqual(scores,[[0.,1.],[0.,1.],[1.,0.]])
  self.assertEqual(C.headline(rows,scores)['kev_rule_accuracy'],1)
  uniform=C.headline(rows,D.score_uniform(rows))
  self.assertEqual(uniform['kev_rule_accuracy'],1/3);self.assertEqual(uniform['r0_rule_accuracy'],0)
  e=N.effect([1,0,1,0],[0,1,1,0],N.bootstrap(self.packet))
  self.assertEqual(e['exact_difference'],{'numerator':0,'denominator':1})
  self.assertEqual(e['historical_bootstrap']['n'],4)

class Digest(unittest.TextTestResult):
 def startTest(self,test):
  super().startTest(test);N.save(P/'scratch/test-progress.json',{'test':test.id(),'completed':self.testsRun-1,'utc_epoch':time.time()})
 def stopTest(self,test):
  super().stopTest(test);N.save(P/'scratch/test-progress.json',{'test':test.id(),'completed':self.testsRun,'utc_epoch':time.time()})
if __name__=='__main__':
 start=time.monotonic();result=unittest.TextTestRunner(verbosity=2,resultclass=Digest).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 N.save(P/'test-results.json',{'fixture_only':True,'tests':result.testsRun,'successful':result.wasSuccessful(),'seconds':time.monotonic()-start,
   'failures':[{'test':t.id(),'traceback':s} for t,s in result.failures],'errors':[{'test':t.id(),'traceback':s} for t,s in result.errors]})
 raise SystemExit(0 if result.wasSuccessful() else 1)
