"""DEV qualification tests. Synthetic numerics use the real frozen selector.

The state-machine fixture substitutes member IO/runtime verification and role
materialization only; it never substitutes evaluate, numerical, or selector.
Those IO contracts have separate rejection tests. Real complete campaign does
not yet exist; a synthetic pass is not a live campaign claim.
"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from tools import r3_dev_qualification as P


def imported(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


FIX=imported(P.LEGACY/'test_consumer.py','dev_numeric_fixture')


class Numerical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=P.source_api()
    def setUp(self):
        self.reports={}
        for name in P.ROLES:
            self.reports[name]=FIX.reports(seed=3 if name=='primary_s3' else 2)
            self.reports[name]['selection_evidence']['adapter_path']='/fixture/'+name+'/adapter'
        for name,(arm,seed) in P.CONTROLS.items():self.reports[name]=FIX.reports(arm,seed)
        for name in ('k0_base','k0_instruct'):self.reports[name]=FIX.reports('K0')
        self.gate={'statuses':{'boolean':'pass','nominal':'void','ordinal':'void'}}
    def run_numeric(self):return P.numerical(self.reports,self.gate,self.api)
    def test_complete_positive_real_numeric(self):
        out=self.run_numeric();self.assertTrue(out['numeric_predicates_pass'])
        self.assertEqual(set(out['floors']['diffchip']['flip']),{'boolean'})
        self.assertFalse(out['floors']['samechip']['numeric_role_gates'])
        self.assertFalse(out['semantic_transfer_seal']['changes_adoption_gate'])
    def test_negative_is_numeric_false(self):
        for name in ('primary_s2','primary_s3'):
            self.reports[name]['track_k']['partitions']['transfer-v4/dev']['headline']['kev_rule_accuracy']=.59
        self.assertFalse(self.run_numeric()['numeric_predicates_pass'])
    def test_first_k1_no_positive_ci_requirement(self):
        out=self.run_numeric()
        self.assertTrue(out['numeric_predicates_pass'])
        self.assertFalse(out['development_comparison']['against_k0']['combined']['lower_bound_above_zero'])
    def test_large_floor_does_not_invent_first_k1_threshold(self):
        r=self.reports['diffchip_s2'];r['track_k']['partitions']['transfer-v4/dev']['headline']['kev_rule_accuracy']=.1
        out=self.run_numeric();self.assertTrue(out['numeric_predicates_pass']);self.assertGreater(out['floors']['diffchip']['accuracy']['transfer-v4'],.5)
    def test_empty_floor_population_rejects(self):
        self.reports['samechip_s2']['track_t']['selection']['typed-decisions']['boolean']['n_units']=0
        with self.assertRaisesRegex(ValueError,'floor population'):self.run_numeric()
    def test_zero_pairs_rejects(self):
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['boolean']['n_pairs_used']=0
        with self.assertRaisesRegex(ValueError,'floor population'):self.run_numeric()
    def test_floor_bad_structural_population_rejects(self):
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['boolean']['n_units']=99
        with self.assertRaisesRegex(ValueError,'structural'):self.run_numeric()
    def test_void_preserved_not_added_to_floor(self):
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['nominal']['n_units']=0
        out=self.run_numeric();self.assertNotIn('nominal',out['floors']['diffchip']['flip'])
    def test_all_void_no_eligibility(self):
        self.gate['statuses']={k:'void' for k in self.gate['statuses']}
        with self.assertRaisesRegex(ValueError,'empty R0'):self.run_numeric()
    def test_semantic_claim_requires_qo_gap_without_adoption_change(self):
        out=self.run_numeric();self.assertTrue(out['numeric_predicates_pass'])
        self.assertFalse(out['semantic_transfer_seal']['per_seed']['2']['semantic_transfer_claim'])
    def test_aux_recipe_drift_rejects(self):
        self.reports['samechip_s2']['selection_evidence']['training_variant']['args']['lr']=.2
        with self.assertRaisesRegex(ValueError,'recipe'):self.run_numeric()


class StateMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=P.source_api()
    def setUp(self):
        Numerical.setUp(self);self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.e={}
        for name in self.reports:
            arm,seed=('K0',None) if name.startswith('k0_') else P.CONTROLS.get(name,('K1',3 if name=='primary_s3' else 2))
            self.e[name]={'arm':arm,'report':str(self.root/name/'selection_report.json'),'model':{'path':str(self.root/name/'adapter')}}
            if seed:self.e[name].update(seed=seed,plan=str(self.root/name/'plan.json'))
        f=self.root/'evidence.json';f.write_text('{}');self.files={str(f):P.sha(f)}
        self.b={'schema':'r3-production-dev-bundle-v1','branch':'firstK1','test_read':False,'files':self.files,'entries':self.e}
        self.a={'schema':'r3-independent-dev-adjudication-v1','bundle_sha256':'a'*64,'test_read':False,'scientific_acceptance':False,'authenticator_identity':'fixture-independent-caller','origin':'independent-parent-adjudication','source_applicability_sha256':P.SOURCE_ADMISSION_SHA,'members':{}}
        self.nodes={};self.times={}
        for i,role in enumerate(P.ROLES):
            chip=1 if role in ('primary_s2','samechip_s2') else 2;seq=0 if role.startswith('primary') else 2
            self.times[role]={'training':{'start':seq,'finish':seq+1,'release':seq+1,'container_id':role,'chip':chip},'evaluation':{'start':10+seq,'finish':11+seq,'release':11+seq,'container_id':role+'-dev','chip':chip},'report':self.reports[role]}
            self.nodes[role]={'chip':chip,'depends_on':[]};self.nodes[role+'_dev']={'chip':chip,'depends_on':[]}
        for name in self.reports:
            if name not in self.times:self.times[name]={'report':self.reports[name]}
    def evaluated(self):
        with patch.object(P,'admitted_r0',return_value=self.gate),patch.object(P,'role_bindings',return_value=self.nodes),patch.object(P,'member',side_effect=lambda name,*a:self.times[name]):
            return P.evaluate(self.b,self.a,'a'*64,self.api)
    def test_end_to_end_synthetic_eligible(self):
        out=self.evaluated();self.assertEqual(out['status'],'ELIGIBLE');self.assertTrue(out['completed']);self.assertTrue(out['candidate_eligibility_granted']);self.assertFalse(out['test_read']);self.assertFalse(out['scientific_acceptance']);self.assertFalse(out['final_test_logger_authority'])
    def test_end_to_end_synthetic_negative_completes(self):
        self.reports['primary_s3']['track_k']['partitions']['transfer-v4/dev']['arms']['constant']['kev_rule_accuracy']=.9
        out=self.evaluated();self.assertEqual(out['status'],'NEGATIVE');self.assertTrue(out['completed']);self.assertFalse(out['candidate_eligibility_granted'])
    def test_missing_control_waits(self):
        del self.e['pt_s3'];out=self.evaluated();self.assertEqual(out['status'],'WAIT');self.assertIn('pt_s3',' '.join(out['missing']))
    def test_missing_aux_waits(self):
        del self.e['samechip_s2'];self.assertEqual(self.evaluated()['status'],'WAIT')
    def test_alias_rejects(self):
        self.e['samechip_s2']['plan']=self.e['primary_s2']['plan'];self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_wrong_seed_and_control_rejects(self):
        self.e['qo_s2']['seed']=3;self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_runtime_chronology_rejects(self):
        self.times['samechip_s2']['training']['start']=.5;self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_runtime_same_generation_rejects(self):
        self.times['samechip_s2']['training']['container_id']='primary_s2';self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_empty_floor_is_fail_not_ignored_diagnostic(self):
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['boolean']['n_pairs_used']=0
        self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_rehashed_wrong_source_admission_rejects(self):
        self.a['source_applicability_sha256']='b'*64;self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_wrong_bundle_pin_rejects(self):
        self.a['bundle_sha256']='b'*64;self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_test_ticket_always_rejected(self):
        self.a['final_ticket']={};self.assertEqual(self.evaluated()['status'],'FAIL')
    def test_missing_external_adjudication_waits(self):
        self.assertEqual(P.evaluate(self.b,None,'a'*64,self.api)['status'],'WAIT')
    def test_partial_real_metadata_missing_members_and_authority_are_both_reported(self):
        del self.e['diffchip_s2'];out=P.evaluate(self.b,None,'a'*64,self.api)
        self.assertEqual(out['status'],'WAIT');self.assertIn('diffchip_s2',' '.join(out['missing']));self.assertIn('adjudication',' '.join(out['missing']))
    def test_missing_file_waits_and_changed_file_fails(self):
        path=next(iter(self.files));Path(path).unlink();self.assertEqual(self.evaluated()['status'],'WAIT')
        Path(path).write_text('{"changed":true}');self.assertEqual(self.evaluated()['status'],'FAIL')


class PlanContract(unittest.TestCase):
    def test_actual_producer_plan_shape(self):
        base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_controls_prospective_20261102_v1')
        for sub,label in [('qo/seed2','K1-QO'),('pt/seed2','K1-PT'),('pt/seed3','K1-PT')]:
            plan=json.loads((base/sub/'plan.json').read_text());self.assertNotIn('arm',plan)
            self.assertEqual(P.actual_arm(plan),'k1');self.assertEqual(P.label(plan),label)
    def test_ambiguous_and_wrong_control_identity(self):
        path=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_controls_prospective_20261102_v1/qo/seed2/plan.json')
        original=json.loads(path.read_text())
        for update in [{'command':original['command']+['--arm','k1']},{'seed':3},{'model':P.INSTRUCT},{'arm':'k2'},{'command':[x for x in original['command'] if x!='--drop-state']}]:
            with self.subTest(update=update),self.assertRaises(ValueError):P.label(dict(original,**update))
    def test_actual_primary_missing_top_arm_supported(self):
        path=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_prospective_08b_20261102_v3/primary_s2/plan.json')
        p=json.loads(path.read_text());self.assertNotIn('arm',p);self.assertEqual(P.label(p),'K1')
    def test_invalid_retained_terminal_rejects(self):
        api=P.source_api()
        docs={'container':[{'State':{'Status':'exited','Running':False,'ExitCode':1}}],'image':[{}],'daemon':{}}
        refs={k:{'path':k,'sha256':'a'*64} for k in docs}
        with patch.object(P,'refdoc',side_effect=lambda r,*a:docs[r['path']]),self.assertRaisesRegex(ValueError,'failed'):P.observed(refs,{},api)


class R0Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api=P.source_api();q=cls.api.Q
        source=Path('/home/xingchao/workspace/nga/.local/reviews/astra-source-admission-20261102-v1/SOURCE-APPLICABILITY.json')
        doc=q.load(source);request=q.load(doc['r0']['artifacts']['request']['path']);files=dict(request['files'])
        for ref in [*doc['r0']['artifacts'].values(),doc['review'],doc['parent_dispatch_receipt'],{'path':str(source),'sha256':P.SOURCE_ADMISSION_SHA}]:files[ref['path']]=ref['sha256']
        old=P.BRIDGE.parent/'ADMITTED-R0-REVIEW.json';files[str(old)]=P.sha(old)
        suspicious=Path(doc['r0']['artifacts']['request']['path']).parent/'SUSPICIOUS_CELLS.json';files[str(suspicious)]=P.sha(suspicious)
        cls.b={'files':files,'source_applicability':{'path':str(source),'sha256':P.SOURCE_ADMISSION_SHA},'data_root':request['data_root'],'r0':{'run':request['run'],'execution_sha256':doc['r0']['artifacts']['execution']['sha256']}}
    def test_actual_exact_r0_reuse_and_voids(self):
        with tempfile.TemporaryDirectory() as scratch,P.read_boundary(self.api,self.b['files'],scratch):out=P.admitted_r0(self.b,self.api)
        self.assertEqual(out['statuses'],dict(boolean='pass',nominal='void',ordinal='void'));self.assertEqual(out['suspicious_evidence']['retained'],28)
        self.assertFalse(out['candidate_eligibility_granted'])
    def test_rehashed_source_admission_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            b=copy.deepcopy(self.b);p=Path(d)/'forged.json';doc=self.api.Q.load(b['source_applicability']['path']);doc['r0']['statuses']['nominal']='pass';p.write_text(json.dumps(doc))
            b['files'][str(p)]=P.sha(p);b['source_applicability']={'path':str(p),'sha256':P.sha(p)}
            with self.assertRaisesRegex(ValueError,'unreviewed/rehashed'):P.admitted_r0(b,self.api)
    def test_missing_source_admission_wait_contract(self):
        b=copy.deepcopy(self.b);b['source_applicability']=None
        with self.assertRaises(FileNotFoundError):P.admitted_r0(b,self.api)


class Ownership(unittest.TestCase):
    def setUp(self):
        self.plan={'run':'r3_runs/example','chip':1,'allocation':'/allocation.json'}
        start='2026-11-02T01:00:00+00:00';finish='2026-11-02T02:00:00+00:00';release='2026-11-02T02:00:01+00:00'
        entry={'chip':1,'run':self.plan['run'],'claimed_utc':'2026-11-02T00:59:00+00:00'}
        before={'allocation':[],'free':[{'chip':1},{'chip':2}],'updated_utc':entry['claimed_utc'],'updated_by':'fixture'}
        after=dict(before,allocation=[entry],free=[{'chip':2}],updated_by='r3_resource_adapter claim')
        self.claim={'schema':'r3-resource-claim-v1','run':self.plan['run'],'chip':1,'allocation':self.plan['allocation'],'entry':entry,'claimed_utc':entry['claimed_utc'],'allocation_before':before,'allocation_after':after}
        final=dict(after,allocation=[],free=[{'chip':1,'previous_run':self.plan['run'],'release_evidence':'/run/RELEASE.json','released_utc':release},{'chip':2}],updated_utc=release,updated_by='r3_resource_adapter release')
        self.release={'schema':'r3-resource-release-v1','run':self.plan['run'],'chip':1,'container':'fixture','container_id':'cid','claim_sha256':'a'*64,'exit_code':0,'scientific_acceptance':False,'container_started_at':start,'container_finished_at':finish,'released_utc':release,'allocation_before':after,'allocation_after':final}
        self.actual={'Id':'cid','Name':'/fixture','State':{'StartedAt':start,'FinishedAt':finish}}
        self.rehash()
    def rehash(self):
        for r in (self.claim,self.release):
            for side in ('before','after'):r['allocation_'+side+'_sha256']=P.ledger_digest(r['allocation_'+side])
    def validate(self):return P.ownership(self.plan,self.claim,self.release,'a'*64,'/run/RELEASE.json',self.actual)
    def test_complete_claim_release(self):self.assertEqual(self.validate()['chip'],1)
    def test_missing_claim_pin_rejects(self):
        del self.release['claim_sha256']
        with self.assertRaisesRegex(ValueError,'generation'):self.validate()
    def test_false_zero_not_exit_code(self):
        self.release['exit_code']=False
        with self.assertRaisesRegex(ValueError,'release failed'):self.validate()
    def test_wrong_generation(self):
        self.actual['Id']='other'
        with self.assertRaisesRegex(ValueError,'generation'):self.validate()
    def test_rehashed_other_chip_change(self):
        self.release['allocation_after']['free'][-1]['chip']=3;self.rehash()
        with self.assertRaisesRegex(ValueError,'transition'):self.validate()
    def test_rehashed_different_claim_owner(self):
        self.release['allocation_before']=copy.deepcopy(self.release['allocation_before']);self.release['allocation_before']['allocation'][0]['run']='other';self.rehash()
        with self.assertRaisesRegex(ValueError,'owner'):self.validate()
    def test_duplicate_ledger_chip(self):
        self.release['allocation_after']['allocation'].append({'chip':1});self.rehash()
        with self.assertRaisesRegex(ValueError,'ledger chip'):self.validate()
    def test_release_before_end(self):
        self.release['released_utc']='2026-11-02T01:50:00+00:00'
        with self.assertRaisesRegex(ValueError,'chronology'):self.validate()
    def test_claim_schema(self):
        self.claim['schema']='fake'
        with self.assertRaisesRegex(ValueError,'schema'):self.validate()


class ReviewContract(unittest.TestCase):
    def setUp(self):
        self.api=P.source_api();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.files={}
        self.entry={'plan':str(self.root/'plan.json')};self.plan={'review_path':str(self.root/'review.json'),'review_sha256':'PENDING'}
        canonical=P.ledger_digest(self.plan)
        report=self.put('report.json',{'verdict':'PASS','approved_canonical_plan_sha256':[canonical],'created_utc':'2026-11-02T01:00:00+00:00'})
        self.report=report
        dispatch=self.put('dispatch.json',{'requested_model':'gpt-6-astra','dispatch_observed_by_parent':True,'completion_received_by_parent':True,'backend_runtime_attestation':False,'reports':{'exact':report},'utc':'2026-11-02T01:00:01+00:00'})
        rev=self.put('review.json',{'approved_plan_sha256':canonical,'verdict':'PASS'})
        self.plan['review_sha256']=rev['sha256'];self.put('plan.json',self.plan)
        self.decision={'decision':'ADMIT_EXACT_PROSPECTIVE_EXECUTION','plan_sha256':self.files[self.entry['plan']],'requested_model':'gpt-6-astra','review_origin_authenticated':True,'observation_origin_authenticated':True,'review_sha256':rev['sha256'],'review_report':report,'dispatch_receipt':dispatch,'review_completed_utc':'2026-11-02T01:00:00+00:00'}
    def put(self,name,doc):
        p=self.root/name;p.write_text(json.dumps(doc));self.files[str(p)]=P.sha(p);return {'path':str(p),'sha256':self.files[str(p)]}
    def validate(self):return P.verify_prelaunch('primary_s2',self.entry,self.plan,self.decision,self.files,self.api)
    def test_authentic_external_pin_contract(self):self.assertEqual(self.validate(),P.moment('2026-11-02T01:00:01+00:00'))
    def test_unadjudicated_origin(self):
        self.decision['review_origin_authenticated']=False
        with self.assertRaisesRegex(ValueError,'adjudication'):self.validate()
    def test_rehashed_review_wrong_plan(self):
        self.decision['review_report']=self.put('report.json',{'verdict':'PASS','approved_canonical_plan_sha256':['b'*64],'created_utc':'2026-11-02T01:00:00+00:00'})
        with self.assertRaisesRegex(ValueError,'exact independent'):self.validate()
    def test_rehashed_dispatch_wrong_model(self):
        doc=self.api.Q.load(self.decision['dispatch_receipt']['path']);doc['requested_model']='other';self.decision['dispatch_receipt']=self.put('dispatch.json',doc)
        with self.assertRaisesRegex(ValueError,'collaboration'):self.validate()
    def test_backdated_review_time_rejects(self):
        self.decision['review_completed_utc']='2026-11-02T00:59:00+00:00'
        with self.assertRaisesRegex(ValueError,'chronology'):self.validate()
    def test_dispatch_does_not_bind_report(self):
        doc=self.api.Q.load(self.decision['dispatch_receipt']['path']);doc['reports']={};self.decision['dispatch_receipt']=self.put('dispatch.json',doc)
        with self.assertRaisesRegex(ValueError,'not bound'):self.validate()


class EvaluationRuntime(unittest.TestCase):
    def setUp(self):
        self.api=P.source_api();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.files={}
        self.p={'schema':'r3-engineering-posttrain-execution-v1','out':str(self.root),'container':'fixture','run':'r3_runs/fixture','chip':1,'allocation':'/allocation.json','launcher':'/frozen/launcher.py'}
        self.spec={'model':P.BASE,'adapter':'/adapter','training':'/training','code_mounts':[{'source':'/code','destination':'/workspace','readonly':True}],'readonly_data_mounts':['/data.json'],'image_sha256':self.api.evaluation.IMAGE,'evaluation_profile':'track_kt','schema':'r3-posttrain-dev-spec-v1'}
        sr=self.put(self.root/'spec.json',self.spec);self.p.update(spec=sr['path'],spec_sha256=sr['sha256']);ex=self.put(self.root/'execution.json',self.p);self.entry={'execution':ex['path']}
        cmd=self.api.evaluation.docker_command(self.p,self.spec,ex['path'],ex['sha256'],1);cut=cmd.index('--entrypoint')
        mounts=[];devices=[];env=[]
        for i,t in enumerate(cmd[:cut]):
            if t=='--mount':
                v=dict(x.split('=',1) if '=' in x else (x,True) for x in cmd[i+1].split(','));mounts.append({'Source':v['src'],'Destination':v['dst'],'RW':'readonly' not in v,'Type':'bind','Propagation':'rprivate'})
            if t=='--device':devices.append({'PathOnHost':cmd[i+1],'PathInContainer':cmd[i+1],'CgroupPermissions':'rwm'})
            if t=='-e':env.append(cmd[i+1])
        own=Ownership();own.setUp();self.claim=own.claim;self.release=own.release
        self.claim['run']=self.claim['entry']['run']=self.p['run'];self.release['run']=self.p['run'];self.release['allocation_after']['free'][0]['previous_run']=self.p['run'];self.release['allocation_after']['free'][0]['release_evidence']=str(self.root/'attempts/1/RELEASE.json')
        for rec in (self.claim,self.release):
            for side in ('before','after'):rec['allocation_'+side+'_sha256']=P.ledger_digest(rec['allocation_'+side])
        claim=self.put(self.root/'attempts/1/CLAIM.json',self.claim);self.release['claim_sha256']=claim['sha256'];self.put(self.root/'attempts/1/RELEASE.json',self.release)
        self.actual={'Id':'cid','Image':self.api.evaluation.IMAGE,'Name':'/fixture-a1','Config':{'Entrypoint':['python3'],'Cmd':cmd[cut+3:],'Env':env},
          'HostConfig':{'Devices':devices,'Runtime':'runc','CgroupnsMode':'private','NetworkMode':'none','IpcMode':'private','ShmSize':64*1024**3,'Ulimits':[{'Name':'memlock','Soft':-1,'Hard':-1},{'Name':'stack','Soft':67108864,'Hard':67108864}]},
          'Mounts':mounts,'State':dict(own.actual['State'],Status='exited',Running=False,ExitCode=0,OOMKilled=False,Error='')}
        self.release['container']='fixture-a1';self.put(self.root/'attempts/1/RELEASE.json',self.release)
        self.put(self.root/'attempts/1/LAUNCH_RECEIPT.json',{'id':'cid','image':self.api.evaluation.IMAGE,'sha256':ex['sha256']})
        terminal={'exit_code':0,'attempt':1,'scientific_acceptance':False};self.put(self.root/'ENGINEERING_EVAL_EXIT.json',terminal);self.put(self.root/'attempts/1/EXIT.json',terminal);self.put(self.root/'attempts/1/SUPERVISOR_DONE.json',{'exit_code':0})
        self.observations={'container':self.put(self.root/'container.json',[self.actual]),'image':self.put(self.root/'image.json',[{'Id':self.api.evaluation.IMAGE,'Config':{'Env':[]}}]),'daemon':self.put(self.root/'daemon.json',{'DefaultRuntime':'runc','CgroupVersion':'2'})}
        resource=Path(json.loads((P.LEGACY.parent/'production-dev-qualification-20261103-v5/CONFIG.json').read_text())['resource_validator']['path']);self.files[str(resource)]=P.sha(resource)
        self.b={'files':self.files,'resource_validator':{'path':str(resource),'sha256':self.files[str(resource)]}}
        self.decision={'execution_sha256':ex['sha256'],'evaluation_observations':self.observations}
    def put(self,p,d):
        p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));self.files[str(p)]=P.sha(p);return {'path':str(p),'sha256':self.files[str(p)]}
    def update_actual(self):self.observations['container']=self.put(self.root/'container.json',[self.actual])
    def validate(self):return P.evaluation_runtime(self.entry,self.decision,self.b,self.api)
    def test_complete_real_evaluation_runtime_validator(self):self.assertEqual(self.validate()['container_id'],'cid')
    def test_extra_gold_mount_rejected(self):
        self.actual['Mounts'].append({'Source':'/gold','Destination':'/gold','RW':False,'Type':'bind'});self.update_actual()
        with self.assertRaisesRegex(ValueError,'mounts'):self.validate()
    def test_extra_chip_rejected(self):
        self.actual['HostConfig']['Devices'].append({'PathOnHost':'/dev/davinci7','PathInContainer':'/dev/davinci7','CgroupPermissions':'rwm'});self.update_actual()
        with self.assertRaisesRegex(ValueError,'devices'):self.validate()
    def test_changed_effective_environment_rejected(self):
        self.actual['Config']['Env'].append('OVERRIDE=1');self.update_actual()
        with self.assertRaisesRegex(RuntimeError,'environment'):self.validate()
    def test_failed_driver_terminal_rejected(self):
        self.put(self.root/'ENGINEERING_EVAL_EXIT.json',{'exit_code':1,'attempt':1})
        with self.assertRaisesRegex(ValueError,'terminals'):self.validate()
    def test_fallback_terminal_rejected(self):
        d={'exit_code':0,'attempt':1,'source':'retained-container-exit'}
        self.put(self.root/'ENGINEERING_EVAL_EXIT.json',d);self.put(self.root/'attempts/1/EXIT.json',d)
        with self.assertRaisesRegex(ValueError,'genuine'):self.validate()
    def test_wrong_execution_generation_rejected(self):
        self.decision['execution_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'adjudicated'):self.validate()


class ReplacementNumerical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=P.source_api()
    def setUp(self):
        Numerical.setUp(self)
        for seed in (2,3):self.reports['candidate_s'+str(seed)]=FIX.reports('K2',seed,80)
    def test_registered_replacement_real_bootstrap(self):
        out=P.numerical(self.reports,self.gate,self.api,'replacement')
        self.assertTrue(out['numeric_predicates_pass']);self.assertTrue(out['replacement']['condition_a']);self.assertFalse(out['floor_indeterminate'])
    def test_floor_indeterminate_is_not_eligible(self):
        for name in ('samechip_s2','diffchip_s2'):
            self.reports[name]['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=.4
        out=P.numerical(self.reports,self.gate,self.api,'replacement')
        self.assertTrue(out['numeric_predicates_pass']);self.assertTrue(out['floor_indeterminate'])
    def test_same_chip_larger_does_not_gate(self):
        self.reports['samechip_s2']['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=.4
        out=P.numerical(self.reports,self.gate,self.api,'replacement');self.assertFalse(out['floor_indeterminate'])
    def test_no_improvement_is_negative(self):
        for seed in (2,3):self.reports['candidate_s'+str(seed)]=FIX.reports('K2',seed)
        out=P.numerical(self.reports,self.gate,self.api,'replacement');self.assertFalse(out['numeric_predicates_pass'])


V4_ROOT = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_prospective_08b_20261102_v4')
CONTROL_ROOT = V4_ROOT.parent/'formal_controls_prospective_20261102_v1'
CONTROL_REVIEWS = Path(P.__file__).resolve().parents[1]/'.local/reviews/astra-formal-controls-exact-20261102-v1'


def actual_review_case(path, api):
    # Read actual existing review graph, without following arbitrary evidence hashes.
    docs = {}; files = {}
    def read(path):
        path = str(path)
        if path not in docs:
            docs[path] = api.Q.load(path); files[path] = P.sha(path)
        return docs[path]
    def ref(r):
        d = read(r['path']); assert files[r['path']] == r['sha256']; return d
    plan = read(path); review = read(plan['review_path'])
    decision = {'decision': 'ADMIT_EXACT_PROSPECTIVE_EXECUTION',
        'plan_sha256': files[str(path)], 'requested_model': 'gpt-6-astra',
        'review_origin_authenticated': True, 'observation_origin_authenticated': True,
        'review_sha256': plan['review_sha256']}
    if review['schema'] == P.COLLAB_REVIEW_POLICY:
        observation = ref(review['parent_observation'])
        for k in ('original_dispatch', 'review_task', 'completion', 'worker_result', 'review_report'):
            ref(observation[k])
        ref(review['prepared_queue']); report = ref(review['review_report'])
        decision.update(review_report=review['review_report'], dispatch_receipt=observation['original_dispatch'],
                        review_completed_utc=report['created_utc'])
    else:
        receipt_path = CONTROL_REVIEWS/'PARENT-RECEIPT.json'
        receipt = read(receipt_path); read(receipt['original_dispatch_receipt'])
        report_ref = receipt['reports']['astra-formal-controls-exact-current.json']
        report = ref(report_ref)
        for x in report['reviews']:
            if x['plan_sha256'] == review['approved_plan_sha256']: ref(x)
        decision.update(review_report=report_ref,
                        dispatch_receipt={'path':str(receipt_path),'sha256':files[str(receipt_path)]},
                        review_completed_utc=report['created_utc'],
                        authenticator_identity='/root', producer_agent_id='/fixture/control-producer')
    return dict(entry={'plan':str(path)}, plan=plan, decision=decision, files=files, docs=docs)


class ActualReviewTransports(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.api = P.source_api()
    def validate(self, case, api=None):
        return P.verify_prelaunch('fixture', case['entry'], case['plan'], case['decision'], case['files'], api or self.api)
    def test_real_v4_all_primary_and_auxiliary_review_closures(self):
        for role in P.ROLES:
            with self.subTest(role=role):
                case = actual_review_case(V4_ROOT/role/'plan.json', self.api)
                with tempfile.TemporaryDirectory() as scratch, P.read_boundary(self.api, case['files'], scratch):
                    end = self.validate(case)
                self.assertEqual(end, P.moment(case['docs'][case['plan']['review_path']]['authenticated_at']))
    def test_real_control_all_three_review_shapes(self):
        for arm, seed in (('qo',2),('pt',2),('pt',3)):
            with self.subTest(arm=arm,seed=seed):
                case = actual_review_case(CONTROL_ROOT/arm/('seed'+str(seed))/'plan.json', self.api)
                with tempfile.TemporaryDirectory() as scratch, P.read_boundary(self.api, case['files'], scratch):
                    self.validate(case)
    def test_actual_v4_partial_campaign_without_adjudication_stays_wait(self):
        files={};entries={}
        for role in P.ROLES:
            case=actual_review_case(V4_ROOT/role/'plan.json',self.api);files.update(case['files'])
            entries[role]={'plan':case['entry']['plan']}
        bundle={'schema':'r3-production-dev-bundle-v1','branch':'firstK1','test_read':False,
                'files':files,'entries':entries}
        with tempfile.TemporaryDirectory() as scratch,P.read_boundary(self.api,files,scratch):
            result=P.evaluate(bundle,None,'a'*64,self.api)
        self.assertEqual(result['status'],'WAIT');self.assertFalse(result['candidate_eligibility_granted'])
        self.assertIn('missing campaign members',' '.join(result['missing']))
        self.assertIn('adjudication',' '.join(result['missing']))
    def mutated_case(self, case, target, edit):
        # Rehash a copied real graph in memory. Only byte IO is substituted.
        # Plan paths, authority identities and real field shapes are retained.
        case = copy.deepcopy(case); docs=case['docs']; edit(docs[target]); newpins={}
        def rebuild(path):
            if path in newpins: return newpins[path]
            def visit(value):
                if isinstance(value,dict):
                    if set(value)=={'path','sha256'} and value['path'] in docs:
                        value['sha256']=rebuild(value['path'])
                    else:
                        for item in value.values():visit(item)
                elif isinstance(value,list):
                    for item in value:visit(item)
            visit(docs[path]); newpins[path]=P.ledger_digest(docs[path]);return newpins[path]
        for path in docs:rebuild(path)
        review_path=case['plan']['review_path'];case['plan']['review_sha256']=newpins[review_path]
        case['files']=newpins;case['decision']['review_sha256']=newpins[review_path]
        case['decision']['plan_sha256']=P.ledger_digest(case['plan'])
        newpins[case['entry']['plan']]=case['decision']['plan_sha256']
        for name in ('review_report','dispatch_receipt'):
            case['decision'][name]['sha256']=newpins[case['decision'][name]['path']]
        def bound(path, files):
            path=str(path)
            if path not in docs:raise FileNotFoundError(path)
            if files.get(path)!=P.ledger_digest(docs[path]):raise ValueError('fixture byte pin differs')
            return copy.deepcopy(docs[path])
        api=types.SimpleNamespace(Q=types.SimpleNamespace(bound=bound,exact=self.api.Q.exact))
        return case,api
    def test_v2_rehashed_binding_and_chronology_mutations(self):
        original=actual_review_case(V4_ROOT/'primary_s2/plan.json',self.api)
        review=original['docs'][original['plan']['review_path']]
        observation=original['docs'][review['parent_observation']['path']]
        mutations=[
            ('dispatch reviewer', observation['original_dispatch']['path'], lambda d:d.update(agent_id='/forged')),
            ('dispatch model', observation['original_dispatch']['path'], lambda d:d.update(requested_model='other')),
            ('task scope', observation['review_task']['path'], lambda d:d.update(scope='other')),
            ('task plan', observation['review_task']['path'], lambda d:d['plans'][0].update(canonical_sha256='b'*64)),
            ('completion status', observation['completion']['path'], lambda d:d.update(status='running')),
            ('completion before report', observation['completion']['path'], lambda d:d.update(observed_at='2026-01-01T00:00:00Z')),
            ('result empty', review['worker_result']['path'], lambda d:d.update(returned_text='')),
            ('result before report', review['worker_result']['path'], lambda d:d.update(observed_at='2026-01-01T00:00:00Z')),
            ('observation producer', review['parent_observation']['path'], lambda d:d.update(producer_agent_id='/forged')),
            ('report reviewer', review['review_report']['path'], lambda d:d.update(reviewer_agent_id='/forged')),
            ('report plan', review['review_report']['path'], lambda d:d.update(approved_canonical_plan_sha256=['b'*64])),
            ('prepared controller', review['prepared_queue']['path'], lambda d:d.update(controller='other')),
            ('review authority', original['plan']['review_path'], lambda d:d.update(authenticator_identity=d['reviewer_agent_id'])),
            ('fabricated exit', original['plan']['review_path'], lambda d:d.update(worker_exit_code=0)),
            ('backend claim', original['plan']['review_path'], lambda d:d.update(backend_runtime_attestation=True)),
        ]
        for name,target,edit in mutations:
            with self.subTest(name=name):
                case,api=self.mutated_case(original,target,edit)
                with self.assertRaises((ValueError,RuntimeError)):self.validate(case,api)
    def test_rehashed_graph_fixture_has_positive_control(self):
        original=actual_review_case(V4_ROOT/'primary_s2/plan.json',self.api)
        case,api=self.mutated_case(original,original['plan']['review_path'],lambda d:None)
        self.validate(case,api)
    def test_review_completion_must_precede_training(self):
        case=actual_review_case(V4_ROOT/'primary_s2/plan.json',self.api)
        completed=self.validate(case)
        entry=dict(case['entry'],report='/fixture/report.json',arm='K1',seed=2)
        decision=dict(case['decision'],report_sha256='a'*64)
        files=dict(case['files'],**{entry['report']:'a'*64})
        with patch.object(P,'protocol',return_value={}),patch.object(P,'training_runtime',return_value={'start':completed}):
            with self.assertRaisesRegex(ValueError,'review was not before training'):
                P.member('primary_s2',entry,decision,{'files':files},self.api)
    def test_v2_each_closure_reference_requires_independent_file_pin(self):
        for role in ('primary_s2','samechip_s2'):
            case=actual_review_case(V4_ROOT/role/'plan.json',self.api)
            for path in case['files']:
                if path == case['entry']['plan']:continue
                with self.subTest(role=role,path=path):
                    changed=copy.deepcopy(case);changed['files'].pop(path)
                    with self.assertRaises((ValueError,KeyError,FileNotFoundError)):self.validate(changed)
    def test_real_control_wrong_report_and_authority_rejected(self):
        original=actual_review_case(CONTROL_ROOT/'qo/seed2/plan.json',self.api)
        for field,value in [('producer_agent_id','/root'),('authenticator_identity','/root/astra_admission_verified')]:
            case=copy.deepcopy(original);case['decision'][field]=value
            with self.assertRaisesRegex(ValueError,'separation'):self.validate(case)
        case=copy.deepcopy(original);case['decision']['review_report']=case['decision']['dispatch_receipt']
        with self.assertRaises(ValueError):self.validate(case)


class ReplacementCarry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=P.source_api()
    def setUp(self):
        ReplacementNumerical.setUp(self)
        for seed in (2,3):
            a=self.reports['candidate_s'+str(seed)];b=self.reports['primary_s'+str(seed)]
            a['track_k']['partitions']['decision-v7/dev']=copy.deepcopy(b['track_k']['partitions']['decision-v7/dev'])
            a['selection_evidence']['correct'][:1264]=b['selection_evidence']['correct'][:1264]
        base=self.reports['primary_s2']['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']
        self.reports['diffchip_s2']['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=base-.02
    def evaluated(self):
        state=StateMachine();state.api=self.api;state.setUp();self.addCleanup(state.doCleanups)
        state.b['branch']='replacement'
        for name,report in self.reports.items():
            state.reports[name]=report
            if name not in state.e:
                state.e[name]={'arm':'K2','seed':int(name[-1]),'report':str(state.root/name/'selection_report.json'),
                               'plan':str(state.root/name/'plan.json'),'model':{'path':str(state.root/name/'adapter')}}
                state.times[name]={'report':report}
            else:state.times[name]['report']=report
        return state.evaluated()
    def test_b_indeterminate_carrier_mapping_stays_unresolved(self):
        out=self.evaluated();self.assertEqual(out['status'],'INDETERMINATE')
        n=out['checks']['numeric']['value'];self.assertTrue(n['numeric_predicates_pass'])
        self.assertTrue(n['floor_indeterminate']);self.assertTrue(n['floor_qualification_indeterminate'])
        carry=n['replacement']['floor_carry'];self.assertEqual(carry['carrier_mapping_status'],'UNRESOLVED')
        self.assertIsNone(carry['cross_suite_floor_aggregation'])
        self.assertEqual(carry['combined_bootstrap_unchanged']['mean_difference'],80/1920)
    def test_positive_native_margin_below_own_floor_is_not_eligible(self):
        base=self.reports['primary_s2']['track_k']['partitions']['transfer-v4/dev']['headline']['kev_rule_accuracy']
        self.reports['diffchip_s2']['track_k']['partitions']['transfer-v4/dev']['headline']['kev_rule_accuracy']=base-.2
        out=self.evaluated();self.assertEqual(out['status'],'INDETERMINATE');self.assertFalse(out['candidate_eligibility_granted'])
    def test_failed_a_is_negative(self):
        for seed in (2,3):self.reports['candidate_s'+str(seed)]=FIX.reports('K2',seed)
        self.assertEqual(self.evaluated()['status'],'NEGATIVE')
    def test_failed_c_is_negative(self):
        for seed in (2,3):self.reports['candidate_s'+str(seed)]['track_t']['selection']['typed-decisions']['boolean']['flip_T1_argmax']=.061
        self.assertEqual(self.evaluated()['status'],'NEGATIVE')
    def test_failed_b_tolerance_is_negative(self):
        for seed in (2,3):
            r=self.reports['candidate_s'+str(seed)];values=r['selection_evidence']['correct']
            for i in range(20):values[i]=0
            r['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']-=20/1264
        self.assertEqual(self.evaluated()['status'],'NEGATIVE')
    def test_c_floor_indeterminate_is_not_carried_by_b(self):
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['boolean']['flip_T1_argmax']=.07
        self.assertEqual(self.evaluated()['status'],'INDETERMINATE')
    def test_samechip_floor_remains_diagnostic(self):
        # No gating diffchip floor; even a larger samechip floor cannot gate.
        self.reports['diffchip_s2']['track_k']['partitions']['decision-v7/dev']=copy.deepcopy(
            self.reports['primary_s2']['track_k']['partitions']['decision-v7/dev'])
        self.reports['samechip_s2']['track_k']['partitions']['transfer-v4/dev']['headline']['kev_rule_accuracy']=.1
        self.assertEqual(self.evaluated()['status'],'ELIGIBLE')
    def test_unresolved_mapping_is_narrowly_identified(self):
        raw=P.numerical(self.reports,self.gate,self.api,'replacement')
        self.assertTrue(raw['numeric_predicates_pass'])
        self.assertTrue(raw['floor_qualification_indeterminate'])
        carry=raw['replacement']['floor_carry']
        self.assertEqual(carry['carrier_mapping_status'],'UNRESOLVED')
        self.assertIsNone(carry['carrier_mapping_authority'])
        self.assertEqual(carry['indeterminate_b_suites'],['decision-v7'])
    def test_externally_pinned_mapping_has_no_scientific_authority(self):
        raw=P.numerical(self.reports,self.gate,self.api,'replacement')
        decision={'schema':'r3-native-carrier-mapping-adjudication-v1',
            'decision':'ACCEPT_NATIVE_POSITIVE_SUITE_MAPPING',
            'evidence_sha256':P.ledger_digest(raw),
            'carrying_suites':['transfer-v4'],'rationale':'Synthetic independent mapping',
            'test_read':False,'scientific_acceptance':False}
        state=StateMachine();state.api=self.api;state.setUp();self.addCleanup(state.doCleanups)
        state.a['replacement_floor_carry']=decision
        # The same admission path used after caller-pin verification rejects
        # the extra authority regardless of evidence hash or rationale.
        with self.assertRaisesRegex(ValueError,'unregistered carrier mapping'):
            P.admitted_root(state.b,state.a,'a'*64,self.api)
        self.assertEqual(state.evaluated()['status'],'FAIL')
    def test_partial_campaign_never_eligible(self):
        self.reports.pop('pt_s3')
        # The synthetic IO fixture still has the registered member but no report
        # substitution; use the actual membership gate with the member removed.
        state=StateMachine();state.api=self.api;state.setUp();self.addCleanup(state.doCleanups)
        state.e.pop('pt_s3')
        self.assertEqual(state.evaluated()['status'],'WAIT')
    def test_reviewer_counterexample_all_native_overlays_pass(self):
        for seed in (2,3):
            r=self.reports['candidate_s'+str(seed)]
            r['selection_evidence']['correct'][1049]=1
            r['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=1050/1264
        base=self.reports['primary_s2']['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']
        self.reports['diffchip_s2']['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=base-.005
        out=self.evaluated();self.assertEqual(out['status'],'ELIGIBLE')
        n=out['checks']['numeric']['value'];r=n['replacement']
        self.assertTrue(n['numeric_predicates_pass']);self.assertFalse(n['floor_qualification_indeterminate'])
        self.assertEqual(set(r['floor_b'].values()),{'PASS'});self.assertEqual(set(r['floor_c'].values()),{'PASS'})
        self.assertEqual(r['floor_carry']['carrier_mapping_status'],'NOT_REQUIRED')
        comp=n['development_comparison']['against_incumbent']
        self.assertEqual(comp['combined']['mean_difference'],.0421875)
        self.assertEqual(comp['combined']['ci_lower'],.034895833333333334)
        self.assertLess(comp['per_suite']['decision-v7']['paired_bootstrap']['mean_difference'],n['floors']['diffchip']['accuracy']['decision-v7'])
    def test_c_native_indeterminacy_without_b_indeterminacy(self):
        self.reports['diffchip_s2']['track_k']['partitions']['decision-v7/dev']=copy.deepcopy(
            self.reports['primary_s2']['track_k']['partitions']['decision-v7/dev'])
        self.reports['diffchip_s2']['track_t']['selection']['typed-decisions']['boolean']['flip_T1_argmax']=.07
        out=self.evaluated();self.assertEqual(out['status'],'INDETERMINATE')
        carry=out['checks']['numeric']['value']['replacement']['floor_carry']
        self.assertEqual(carry['carrier_mapping_status'],'NOT_REQUIRED')
        self.assertEqual(carry['indeterminate_c_cells'],['boolean'])


if __name__=='__main__':unittest.main()
