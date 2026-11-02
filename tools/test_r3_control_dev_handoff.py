"""Actual control shapes, real binder; synthetic completion/review bytes only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import r3_control_dev_handoff as C

PREP=Path(__file__).resolve().parents[1]/'.local/preparations/control-dev-handoff-20261102-v4'


def put(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc));return path


class ActualControls(unittest.TestCase):
    def test_three_current_controls_inspect_without_mutation(self):
        spec=importlib.util.spec_from_file_location('frozen_handoff',PREP/'r3_control_dev_handoff.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        ref=C.load(PREP/'CONFIG-PIN.json');b,jobs,_=m.identity(ref['path'],ref['sha256'])
        before={j['training_plan']['path']:C.sha(j['training_plan']['path']) for j in jobs.values()}
        result=m.inspect(ref['path'],ref['sha256'])
        self.assertEqual(set(result['jobs']),set(C.ROLES))
        self.assertTrue(all(v['status']=='waiting_training' for v in result['jobs'].values()))
        self.assertTrue(all(any(p.endswith('TRAIN_EXIT.json') for p in v['missing']) for v in result['jobs'].values()))
        self.assertEqual(before,{p:C.sha(p) for p in before})
        self.assertFalse(Path(b['state_root']).exists())


class ControlPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        original=C.load(PREP/'CONFIG.json');self.b=copy.deepcopy(original)
        self.b.update(state_root=str(self.root/'state'),_pin='b'*64,_path=str(self.root/'config.json'),deployment={'python':'/usr/bin/python3.11'})
        self.closure=self.root/'closure';put(self.closure/'manifest.json',{
            'evaluation_profile':'track_kt','data':{},'code':{},'mounts':[],
            'command_template':['python3','--arm','K1','--adapter','<COMPLETED_ADAPTER>','--out','<FRESH_EVAL_OUTPUT>']})
        self.b['closure']={'path':str(self.closure/'manifest.json'),'sha256':C.sha(self.closure/'manifest.json')}
        self.H=C.configured_handoff(self.b);self.Q=C.module(self.b['sources']['qualifier'])
        self.jobs={};self.plans={};self.queue={'jobs':[]}
        for item in original['jobs']:
            role=item['role'];p=C.load(item['training_plan']['path']);train=self.root/role;out=self.root/(role+'-dev')
            # Preserve actual no-top-level-arm command/control shape; isolate IO.
            p.update(out=str(train),run='fixture/'+role,files={})
            p['command']=list(p['command']);p['command'][p['command'].index('--out')+1]=str(train)
            put(train/'plan.json',p);self.plans[role]=p
            self.jobs[role]=dict(role=role,seed=p['seed'],training=str(train),new_adapter=str(train/'adapter'),
                canonical_plan_sha256=self.Q.ledger_digest(dict(p,review_sha256='PENDING')),required_final_step=3116,
                training_plan={'path':str(train/'plan.json'),'sha256':C.sha(train/'plan.json')},fresh_eval_out=str(out),
                late_bound_hashes=self.H.LATE,chip=p['chip'],launch_dependencies=['independent review'])
            prior=self.root/(role+'-prior');execution=put(prior/'execution.json',dict(run='previous/'+role,chip=p['chip'],container='previous-'+role))
            qj=dict(id=role,plan=str(train/'plan.json'),canonical_sha256=self.jobs[role]['canonical_plan_sha256'],previous=dict(kind='evaluation',path=str(execution),sha256=C.sha(execution)))
            self.queue['jobs'].append(qj);self.jobs[role]['queue_job']=qj
        queue=put(self.root/'queue.json',self.queue);self.b['queue']={'path':str(queue),'sha256':C.sha(queue)}
        self.b['jobs']=[dict(role=r,training=j['training']) for r,j in self.jobs.items()]
    def complete(self,role):
        j=self.jobs[role];p=self.plans[role];root=Path(j['training']);a=root/'attempts/1'
        end=dict(exit_code=0,attempt=1,started_utc='2026-11-02T01:00:00Z',finished_utc='2026-11-02T02:00:00Z',scientific_acceptance=False)
        put(root/'TRAIN_EXIT.json',end);put(a/'EXIT.json',end)
        qj=j['queue_job'];prior=Path(qj['previous']['path']).parent;pa=prior/'attempts/1';run='previous/'+role
        free=dict(chip=p['chip'],previous_run=run,release_evidence=str(pa/'RELEASE.json'),released_utc='2026-11-02T00:00:00Z')
        old_end=dict(exit_code=0,attempt=1);put(prior/'ENGINEERING_EVAL_EXIT.json',old_end);put(pa/'EXIT.json',old_end)
        put(pa/'CLAIM.json',dict(run=run,chip=p['chip']));put(pa/'LAUNCH_RECEIPT.json',dict(id='old-'+role))
        put(pa/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))
        put(pa/'RELEASE.json',dict(run=run,chip=p['chip'],container='previous-'+role+'-a1',container_id='old-'+role,
            exit_code=0,scientific_acceptance=False,allocation_after={'free':[free],'allocation':[]}))
        pins={str(x):C.sha(x) for x in [prior/'execution.json',prior/'ENGINEERING_EVAL_EXIT.json',*pa.glob('*.json')]}
        guard=dict(config_sha256=self.b['queue']['sha256'],job=qj['id'],canonical_sha256=j['canonical_plan_sha256'],free_entry=free,
            previous=dict(attempt=1,container_id='old-'+role,run=run,release_path=str(pa/'RELEASE.json'),free_entry=free,hashes=pins))
        put(a/'CLAIM.json',dict(run=p['run'],chip=p['chip'],successor_precondition=guard))
        put(a/'RELEASE.json',dict(schema='r3-resource-release-v1',run=p['run'],chip=p['chip'],container=p['container']+'-a1',container_id=role,claim_sha256=C.sha(a/'CLAIM.json'),exit_code=0,scientific_acceptance=False))
        put(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))
        put(a/'LAUNCH_RECEIPT.json',dict(id=role,image=p['image_sha256'],plan_sha256=j['canonical_plan_sha256']))
        put(a/'LAUNCH_SPEC.json',dict(synthetic=True));put(root/'SUPERVISOR_RECEIPT.json',dict(synthetic=True))
        put(root/'manifest.json',dict(summary={'final_step':3116},arm='k1',model_path=p['model'],
            args=dict(arm='k1',model_path=p['model'],seed=p['seed'],drop_state=role=='qo_s2')))
        put(root/'adapter/adapter_config.json',{});(root/'adapter/adapter_model.safetensors').write_bytes(b'synthetic')
    def cycle(self):
        with patch.object(self.H,'identity',return_value=(self.b,self.jobs,{})),patch.object(C,'identity',return_value=(self.b,self.jobs,{})):
            return self.H.cycle(self.b['_path'],self.b['_pin'])[1]
    def review(self,role):
        state=Path(self.b['state_root'])/role;capture=C.load(state/'CAPTURE.json')
        evidence=put(self.root/(role+'-external.json'),{'synthetic':True})
        review=dict(schema='r3-formal-independent-postrun-v1',verdict='PASS',independent=True,training=self.jobs[role]['training'],
            queue_sha256=self.b['queue']['sha256'],binding_sha256=self.b['_pin'],capture_sha256=C.sha(state/'CAPTURE.json'),files=capture['files'],
            test_read=False,scientific_acceptance=False,evidence_files={str(evidence):C.sha(evidence)},
            checks={k:True for k in ('genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116','control_prerequisite_identity_and_release')})
        path=put(self.root/(role+'-review.json'),review)
        with patch.object(self.H,'identity',return_value=(self.b,self.jobs,{})):
            self.H.inject(self.b['_path'],self.b['_pin'],role,str(path),C.sha(path))
        return path
    def test_all_three_real_binder_control_shapes(self):
        for role in C.ROLES:self.complete(role)
        self.assertTrue(all(v['status']=='REVIEW_REQUIRED' for v in self.cycle()['jobs'].values()))
        for role in C.ROLES:
            self.assertFalse(Path(self.jobs[role]['fresh_eval_out']).exists());self.review(role)
        result=self.cycle();self.assertTrue(all(v['status']=='prepared' for v in result['jobs'].values()))
        self.assertTrue(all(v['status']=='prepared' for v in self.cycle()['jobs'].values()))
        for role,(arm,seed) in C.ROLES.items():
            out=Path(self.jobs[role]['fresh_eval_out']);spec=C.load(out/'plan.json')
            self.assertEqual(spec['training_variant']['arm'],arm.lower());self.assertEqual(spec['training_variant']['seed'],seed)
            self.assertEqual(spec['execution_review'],'PENDING');self.assertEqual(spec['chip_assignment'],'PENDING')
            self.assertFalse((out/'execution.json').exists());self.assertNotIn('arm',C.load(Path(self.jobs[role]['training'])/'plan.json'))
    def test_wrong_control_manifest_does_not_prepare(self):
        self.complete('qo_s2');p=Path(self.jobs['qo_s2']['training'])/'manifest.json';d=C.load(p);d['args']['drop_state']=False;put(p,d)
        result=self.cycle();self.assertEqual(result['jobs']['qo_s2']['status'],'needs_repair')
        self.assertEqual(result['jobs']['pt_s3']['status'],'waiting_training')
    def test_genuine_failed_training_is_terminal_other_roles_continue(self):
        put(Path(self.jobs['qo_s2']['training'])/'TRAIN_EXIT.json',dict(exit_code=1,attempt=1))
        self.complete('pt_s3');result=self.cycle()
        self.assertEqual(result['jobs']['qo_s2']['status'],'training_failed');self.assertEqual(result['jobs']['pt_s3']['status'],'REVIEW_REQUIRED')
    def test_missing_release_named_without_capture(self):
        self.complete('pt_s2');root=Path(self.jobs['pt_s2']['training']);(root/'attempts/1/RELEASE.json').unlink()
        value=self.H.capture(self.b,self.jobs['pt_s2'],self.plans['pt_s2'])
        self.assertEqual(value['status'],'waiting_completion_evidence');self.assertIn(str(root/'attempts/1/RELEASE.json'),value['missing'])
    def test_no_review_no_output_and_uncertain_intent_not_retried(self):
        self.complete('pt_s3');self.cycle();out=Path(self.jobs['pt_s3']['fresh_eval_out']);self.assertFalse(out.exists())
        self.review('pt_s3');put(Path(self.b['state_root'])/'pt_s3/PREPARE_INTENT.json',{'synthetic':True})
        self.assertEqual(self.cycle()['jobs']['pt_s3']['status'],'needs_repair');self.assertFalse(out.exists())
    def test_adapter_mutation_after_capture_rejects(self):
        self.complete('pt_s3');self.cycle();(Path(self.jobs['pt_s3']['new_adapter'])/'adapter_model.safetensors').write_bytes(b'changed')
        self.assertEqual(self.cycle()['jobs']['pt_s3']['status'],'needs_repair')
    def test_wrong_review_checks_reject_before_binder(self):
        self.complete('pt_s3');self.cycle();path=self.review('pt_s3');d=C.load(path);d['checks']['retained_container_identity']=False;put(path,d)
        state=Path(self.b['state_root'])/'pt_s3'
        with self.assertRaisesRegex(ValueError,'incomplete'):
            self.H.review_check(state,{'path':str(path),'sha256':C.sha(path)},self.b,self.jobs['pt_s3'],self.plans['pt_s3'])
        self.assertFalse(Path(self.jobs['pt_s3']['fresh_eval_out']).exists())
    def test_cycle_digest_preserves_precise_missing_dependencies(self):
        self.complete('pt_s3')
        with patch.object(self.H,'identity',return_value=(self.b,self.jobs,{})),patch.object(C,'identity',return_value=(self.b,self.jobs,{})):
            _,d=C.cycle(self.b['_path'],self.b['_pin'],self.H)
        self.assertIn(str(Path(self.jobs['qo_s2']['training'])/'TRAIN_EXIT.json'),d['jobs']['qo_s2']['missing'])
        self.assertEqual(d['jobs']['pt_s3']['missing'],[str(Path(self.b['state_root'])/'pt_s3/REVIEW-REFERENCE.json')])
    def alter_guard(self,change):
        root=Path(self.jobs['pt_s3']['training']);path=root/'attempts/1/CLAIM.json';doc=C.load(path);change(doc);put(path,doc)
        release=root/'attempts/1/RELEASE.json';d=C.load(release);d['claim_sha256']=C.sha(path);put(release,d)
    def test_missing_embedded_guard_reproduction_cannot_capture(self):
        self.complete('pt_s3');self.alter_guard(lambda d:d.pop('successor_precondition'))
        self.assertEqual(self.cycle()['jobs']['pt_s3']['status'],'needs_repair')
        self.assertFalse((Path(self.b['state_root'])/'pt_s3/CAPTURE.json').exists())
    def test_wrong_guard_identity_and_free_entry_reject(self):
        self.complete('pt_s3')
        for key,value in [('config_sha256','bad'),('job','bad'),('canonical_sha256','bad'),('free_entry',{'chip':4})]:
            with self.subTest(key=key):
                self.complete('pt_s3');self.alter_guard(lambda d:d['successor_precondition'].__setitem__(key,value))
                with self.assertRaises(ValueError):self.H.capture(self.b,self.jobs['pt_s3'],self.plans['pt_s3'])
    def test_predecessor_wrong_path_inventory_and_changed_evidence_reject(self):
        for change in [lambda g:g['previous'].__setitem__('release_path','/tmp/wrong'),
                       lambda g:g['previous']['hashes'].clear(),
                       lambda g:g['previous']['hashes'].__setitem__(self.jobs['pt_s3']['queue_job']['previous']['path'],'0'*64)]:
            self.complete('pt_s3');self.alter_guard(lambda d:change(d['successor_precondition']))
            with self.assertRaises(ValueError):self.H.capture(self.b,self.jobs['pt_s3'],self.plans['pt_s3'])
    def test_external_review_must_explicitly_verify_prerequisite(self):
        self.complete('pt_s3');self.cycle();path=self.review('pt_s3');doc=C.load(path)
        doc['checks'].pop('control_prerequisite_identity_and_release');put(path,doc)
        with self.assertRaisesRegex(ValueError,'prerequisite verification'):
            self.H.review_check(Path(self.b['state_root'])/'pt_s3',{'path':str(path),'sha256':C.sha(path)},self.b,self.jobs['pt_s3'],self.plans['pt_s3'])

    def test_control_predecessor_binds_original_plan_and_claim(self):
        self.complete('qo_s2');self.complete('pt_s2')
        j=self.jobs['pt_s2'];qj=j['queue_job'];priorjob=self.jobs['qo_s2'];p=self.plans['qo_s2'];root=Path(priorjob['training']);a=root/'attempts/1'
        qj['previous']={'kind':'control','job':'qo_s2'}
        self.jobs['qo_s2']['queue_job']['raw_sha256']=priorjob['training_plan']['sha256']
        put(Path(self.b['queue']['path']),self.queue);self.b['queue']['sha256']=C.sha(self.b['queue']['path'])
        free=dict(chip=p['chip'],previous_run=p['run'],release_evidence=str(a/'RELEASE.json'),released_utc='time')
        release=C.load(a/'RELEASE.json');release['allocation_after']={'free':[free],'allocation':[]};put(a/'RELEASE.json',release)
        pins={str(x):C.sha(x) for x in [root/'TRAIN_EXIT.json',*a.glob('*.json')]}
        guard=dict(config_sha256=self.b['queue']['sha256'],job=qj['id'],canonical_sha256=j['canonical_plan_sha256'],free_entry=free,
            previous=dict(status='completed',container_id='qo_s2',run=p['run'],release_path=str(a/'RELEASE.json'),free_entry=free,hashes=pins))
        path=Path(j['training'])/'attempts/1/CLAIM.json';claim=C.load(path);claim['successor_precondition']=guard;put(path,claim)
        got=C.prerequisite(self.b,j,self.plans['pt_s2']);self.assertEqual(got[priorjob['training_plan']['path']],priorjob['training_plan']['sha256'])
        release['claim_sha256']='0'*64;put(a/'RELEASE.json',release);pins[str(a/'RELEASE.json')]=C.sha(a/'RELEASE.json');put(path,claim)
        with self.assertRaisesRegex(ValueError,'control claim'):C.prerequisite(self.b,j,self.plans['pt_s2'])
    def test_internally_consistent_free_entry_still_requires_original_release(self):
        self.complete('pt_s3')
        def corrupt(d):
            g=d['successor_precondition'];g['free_entry']['released_utc']='invented';g['previous']['free_entry']['released_utc']='invented'
        self.alter_guard(corrupt)
        with self.assertRaisesRegex(ValueError,'not in release'):self.H.capture(self.b,self.jobs['pt_s3'],self.plans['pt_s3'])

    def test_event_wait_uses_600_seconds_and_writes_terminal(self):
        from types import SimpleNamespace
        class Wake:
            paths=[];waits=[];closed=False
            def __init__(self,paths):self.paths.extend(paths)
            def wait(self,n):self.waits.append(n)
            def close(self):Wake.closed=True
        waiting={'jobs':{r:{'status':'waiting_training'} for r in C.ROLES}}
        finished={'jobs':{r:{'status':'prepared'} for r in C.ROLES}}
        with patch.object(C,'identity',return_value=(self.b,self.jobs,{})),patch.object(C,'configured_handoff',return_value=self.H),\
             patch.object(C,'module',return_value=SimpleNamespace(CompletionWake=Wake)),\
             patch.object(C,'cycle',side_effect=[(self.b,waiting),(self.b,finished)]):
            result=C.watch(self.b['_path'],self.b['_pin'])
            with self.assertRaisesRegex(ValueError,'terminal watcher'):C.watch(self.b['_path'],self.b['_pin'])
        self.assertEqual(Wake.waits,[600]);self.assertTrue(Wake.closed)
        self.assertTrue(any(p.endswith('REVIEW-REFERENCE.json') for p in Wake.paths))
        state=Path(self.b['state_root']);self.assertEqual(C.load(state/'EXIT.json')['exit_code'],0)
        self.assertTrue((state/'RELAUNCH.json').exists());self.assertEqual(result,finished)
        relaunch=C.load(state/'RELAUNCH.json');self.assertIn('nohup',relaunch['detached_command'])
        self.assertIn('2>&1 < /dev/null &',relaunch['detached_command']);self.assertEqual(relaunch['durable_log'],str(state/'watch.log'))


if __name__=='__main__':unittest.main()
