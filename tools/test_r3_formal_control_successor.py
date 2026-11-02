"""CPU tests: real pinned plans/validators and adapter transaction; Docker synthetic."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parent
RUN = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_control_successor_20261102_v1')


def module(p):
    m = types.ModuleType(p.stem); m.__file__ = str(p)
    exec(compile(p.read_bytes(), str(p), 'exec', dont_inherit=True), m.__dict__)
    return m


C = module(ROOT/'r3_formal_control_successor.py')
FIX = module(ROOT/'test_r3_formal_train_successor.py')


def fixture_authority(root, config):
    """Synthetic local authority; never an activation for an experiment path."""
    config_path = root/'CONFIG.json'; C.save(config_path, config)
    config_pin = C.digest(config_path.read_bytes())
    review_path = root/'controller-review.json'
    C.save(review_path, dict(verdict='PASS', reviewer_model='gpt-6-astra',
                            config_sha256=config_pin, controller_sha256=config['controller']['sha256'],
                            scope='SYNTHETIC CPU FIXTURE ONLY'))
    parent_path = root/'parent.json'; C.save(parent_path, {'scope':'SYNTHETIC CPU FIXTURE ONLY'})
    activation = dict(schema='r3-formal-control-activation-v1', config_sha256=config_pin,
                      controller_sha256=config['controller']['sha256'], allowed_jobs=[j['id'] for j in config['jobs']],
                      attempt=1, root_review_accepted=True, prepublished=True, activation_authorized=True,
                      test_read=False, scientific_acceptance=False,
                      controller_review=dict(path=str(review_path), sha256=C.digest(review_path.read_bytes())),
                      parent_receipt=dict(path=str(parent_path), sha256=C.digest(parent_path.read_bytes())))
    activation_path=root/'activation.json'; C.save(activation_path, activation)
    return types.SimpleNamespace(config=str(config_path), sha256=config_pin, activation=str(activation_path),
                                 activation_sha256=C.digest(activation_path.read_bytes()))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.c = C.load(RUN/'CONFIG.json')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_real_three_plans(self):
        for j in self.c['jobs']:
            p = C.checked_plan(j)
            self.assertEqual(p['chip'], j['chip'])
            self.assertFalse(p['control']['candidate_for_adoption'])

    def test_wrong_declared_arm_seed_chip_and_raw_review_pins(self):
        for key, value in [('arm', 'K1'), ('seed', 3), ('chip', 4),
                           ('raw_sha256', '0'*64), ('review_sha256', '0'*64)]:
            j = copy.deepcopy(self.c['jobs'][0]); j[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): C.checked_plan(j)

    def test_engineering_substitution(self):
        j = copy.deepcopy(self.c['jobs'][0]); p = C.load(j['plan']); p['schema'] = 'r3-engineering-k1-plan-v1'
        f = self.root/'plan.json'; f.write_bytes(C.canonical(p)); j['plan'] = str(f)
        j['raw_sha256'] = C.digest(f.read_bytes()); j['canonical_sha256'] = C.digest(C.canonical(dict(p, review_sha256='PENDING')))
        with self.assertRaises(RuntimeError): C.checked_plan(j)

    def test_once_read_source_pin(self):
        p = self.root/'code.py'; p.write_text('value = 3\n'); pin = C.digest(p.read_bytes())
        self.assertEqual(C.source({'path': str(p), 'sha256': pin}).value, 3)
        p.write_text('value = 4\n')
        with self.assertRaises(RuntimeError): C.source({'path': str(p), 'sha256': pin})

    def test_external_activation_is_required(self):
        f = self.root/'ticket.json'; f.write_text('{}')
        with self.assertRaises((RuntimeError, KeyError)): C.authorize(self.c, 'a'*64, f, C.digest(f.read_bytes()))

    def test_independent_lanes_and_fifo(self):
        c = dict(self.c, state_root=str(self.root)); calls = []
        def tick(_, j, args):
            calls.append(j['id']); return {'status': 'training' if j['id']=='qo_seed2' else 'completed'}
        states = C.cycle(c, None, {}, tick)
        self.assertEqual(calls, ['qo_seed2', 'pt_seed3'])
        self.assertEqual(states['pt_seed2']['status'], 'waiting_lane')

    def test_failed_lane_does_not_block_other_chip(self):
        c = dict(self.c, state_root=str(self.root)); calls=[]
        def tick(_, j, args):
            calls.append(j['id']); return {'status': 'failed' if j['id']=='qo_seed2' else 'completed'}
        states=C.cycle(c,None,{},tick)
        self.assertEqual(states['pt_seed2']['status'],'blocked')
        self.assertEqual(states['pt_seed3']['status'],'completed')
        self.assertTrue(all(x['status'] in C.TERMINAL for x in states.values()))

    def test_uncertain_intent_never_replayed(self):
        c=dict(self.c,state_root=str(self.root));j=c['jobs'][0]
        C.save(self.root/(j['id']+'.START_INTENT.json'),{'partial':'fixture'})
        with patch.object(C,'request_start',side_effect=AssertionError('duplicate start')):
            states=C.cycle(c,None,{})
        self.assertEqual(states[j['id']]['status'],'needs_repair')

    def test_bootstrap_compiles_exact_controller_bytes(self):
        p=self.root/'small.py';p.write_text('print("BOUND_OK")\n');pin=C.digest(p.read_bytes())
        cmd=[os.sys.executable,'-B','-P','-c',C.PINNED_EXEC,str(p),pin]
        result=subprocess.run(cmd,text=True,capture_output=True)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout.strip(),'BOUND_OK')
        p.write_text('raise RuntimeError("must not execute")\n')
        result=subprocess.run(cmd,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('controller bytes changed',result.stderr)

    def test_detached_start_handshake_uses_pinned_exec(self):
        c=copy.deepcopy(self.c);c['state_root']=str(self.root/'state');Path(c['state_root']).mkdir()
        j=c['jobs'][0];p={'out':str(self.root/'output')};Path(p['out']).mkdir()
        args=types.SimpleNamespace(config=str(RUN/'CONFIG.json'),sha256='a'*64,activation='/fixture/activation.json',activation_sha256='b'*64)
        calls=[]
        def launch(cmd,**kwargs):
            calls.append((cmd,kwargs));compile(cmd[2],'<bootstrap>','exec')
            self.assertTrue(kwargs['start_new_session']);self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)
            return types.SimpleNamespace(pid=99999999)
        with patch.object(subprocess,'Popen',side_effect=launch):
            result=C.request_start(c,j,args,p)
            with self.assertRaises(FileExistsError):C.request_start(c,j,args,p)
        self.assertEqual(len(calls),1);self.assertEqual(result['status'],'launch_requested')
        receipt=C.load(Path(p['out'])/'SUPERVISOR_RECEIPT.json')
        self.assertIn(C.PINNED_EXEC,receipt['command']);self.assertIn(c['controller']['sha256'],receipt['command'])

    def test_aggregate_failure_finishes_only_when_other_lane_finishes(self):
        states={'qo_seed2':{'status':'failed'},'pt_seed2':{'status':'blocked'},'pt_seed3':{'status':'training'}}
        self.assertIsNone(C.aggregate(states));states['pt_seed3']['status']='completed'
        self.assertEqual(C.aggregate(states),1)
        self.assertEqual(C.aggregate({k:{'status':'completed'} for k in states}),0)

    def test_config_changed_exact_pin_rejected(self):
        f=self.root/'CONFIG.json';f.write_bytes(C.canonical(self.c));pin=C.digest(f.read_bytes())
        c=copy.deepcopy(self.c);c['jobs'][1]['previous']={'kind':'control','job':'pt_seed3'}
        f.write_bytes(C.canonical(c))
        with self.assertRaisesRegex(RuntimeError,'pin changed'):C.verify_config(f,pin)

    def test_exact_legacy_evaluator_interface_from_predecessor_plan(self):
        c=copy.deepcopy(self.c);prior=c['jobs'][2]['previous'];e=C.load(prior['path'],prior['sha256'])
        binding=dict(execution={'path':prior['path'],'sha256':prior['sha256']},
                     launcher={'path':e['launcher'],'sha256':e['tools'][e['launcher']]},contract='legacy-command-results-v1')
        c['evaluation_interfaces']=[binding];h=C.helper(c)
        launcher=h.source(e['launcher'],e['tools'][e['launcher']]);spec=C.load(e['spec'],e['spec_sha256'])
        self.assertEqual(launcher.result_directory(spec,e['out']),Path(e['out'])/'results')
        bad=copy.deepcopy(spec);bad['command'][bad['command'].index('--out')+1]='/tmp/unbound'
        with self.assertRaisesRegex(RuntimeError,'command differs'):launcher.result_directory(bad,e['out'])
        c['evaluation_interfaces'][0]['launcher']['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'pin/contract'):C.helper(c).source(e['launcher'],e['tools'][e['launcher']])

    def test_configured_host_dependency_missing_changed_and_exact(self):
        c=copy.deepcopy(self.c);j=copy.deepcopy(c['jobs'][0]);plan=C.load(j['plan'])
        original=next(x for x in plan['files'] if x.startswith('/home/'))
        raw=C.content(original,plan['files'][original]);deployed=self.root/'host.py';frozen=self.root/'frozen.py';frozen.write_bytes(raw)
        plan['files'][str(deployed)]=plan['files'][original];p=self.root/'plan.json';p.write_bytes(C.canonical(plan))
        j.update(plan=str(p),raw_sha256=C.digest(p.read_bytes()))
        c['host_dependencies']=[dict(path=str(deployed),source=str(frozen),sha256=C.digest(raw),jobs=[j['id']])]
        with self.assertRaises(FileNotFoundError):C.verify_deployment(c,j)
        deployed.write_bytes(raw);C.verify_deployment(c,j)
        deployed.write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'pin changed'):C.verify_deployment(c,j)

    def test_legacy_adapter_never_applies_to_modern_launcher(self):
        c=copy.deepcopy(self.c);prior=c['jobs'][0]['previous'];e=C.load(prior['path'],prior['sha256'])
        c['evaluation_interfaces']=[dict(execution={'path':prior['path'],'sha256':prior['sha256']},
                                        launcher={'path':e['launcher'],'sha256':e['tools'][e['launcher']]},contract='legacy-command-results-v1')]
        with self.assertRaisesRegex(RuntimeError,'legacy evaluator interface differs'):
            C.helper(c).source(e['launcher'],e['tools'][e['launcher']])


class WatchIsolationTests(unittest.TestCase):
    setUp = IdentityTests.setUp

    def watch_fixture(self, corruption, started=False):
        c=copy.deepcopy(self.c);c['state_root']=str(self.root/'state')
        c['controller']={'path':C.__file__,'sha256':C.digest(Path(C.__file__).read_bytes())}
        j=c['jobs'][0]
        if corruption=='plan':j['raw_sha256']='0'*64
        elif corruption=='review':j['review_sha256']='0'*64
        elif corruption=='fresh':j['fresh_files']['missing-synthetic-file']='0'*64
        elif corruption=='code':pass  # Narrow source-read failure is injected by the caller.
        else:raise AssertionError(corruption)
        args=fixture_authority(self.root,c)
        # Immutable controller authority succeeds even when a job is corrupt.
        self.assertEqual(C.verify_controller(args.config,args.sha256),c)
        with self.assertRaises((RuntimeError,FileNotFoundError)):C.verify_config(args.config,args.sha256)
        if started:C.save(Path(c['state_root'])/'qo_seed2.START_INTENT.json',{'scope':'synthetic prior intent'})
        calls=[];sleeps=[];original_cycle=C.cycle
        def local_tick(config,job,a):
            calls.append(job['id']);C.verify_job(config,job)
            # Real local verification above; substitute only external lifecycle.
            return {'status':'training' if calls.count(job['id'])==1 else 'completed'}
        def sleep(seconds):
            self.assertEqual(seconds,600);sleeps.append(seconds)
            self.assertFalse((Path(c['state_root'])/'EXIT.json').exists())
            state=C.load(Path(c['state_root'])/'STATE.json')['jobs']
            self.assertEqual(state['qo_seed2']['status'],'needs_repair' if started else 'failed')
            self.assertEqual(state['pt_seed2']['status'],'blocked')
            self.assertEqual(state['pt_seed3']['status'],'training')
        with patch.object(C.socket,'gethostname',return_value='k8s-node1'), \
             patch.object(C.threading,'Thread'), patch.object(C.time,'sleep',side_effect=sleep), \
             patch.object(C,'cycle',side_effect=lambda x,a,s:original_cycle(x,a,s,local_tick)), \
             patch.object(C,'request_start',side_effect=AssertionError('no start allowed')), \
             patch.object(subprocess,'run',side_effect=AssertionError('no external process')):
            C.watch(c,args)
        end=C.load(Path(c['state_root'])/'EXIT.json')
        self.assertEqual(end['exit_code'],1);self.assertEqual(len(sleeps),1)
        self.assertEqual(end['jobs']['pt_seed3']['status'],'completed')
        self.assertEqual(calls,['qo_seed2','pt_seed3','pt_seed3'])

    def test_watch_plan_corruption_preserves_other_lane_until_completion(self):
        self.watch_fixture('plan')

    def test_watch_review_corruption_preserves_other_lane_until_completion(self):
        self.watch_fixture('review')

    def test_watch_missing_fresh_file_after_intent_needs_repair(self):
        self.watch_fixture('fresh',started=True)

    def test_watch_per_job_source_corruption_preserves_other_lane(self):
        plan=C.load(self.c['jobs'][0]['plan']);target=plan['launcher'];original=C.content
        def corrupt_source(path,pin=None):
            if str(path)==target:raise RuntimeError('pin changed: synthetic per-job source failure')
            return original(path,pin)
        with patch.object(C,'content',side_effect=corrupt_source):
            self.watch_fixture('code')

    def test_watch_per_job_receipt_corruption_between_polls(self):
        c=copy.deepcopy(self.c);c['state_root']=str(self.root/'state')
        c['controller']={'path':C.__file__,'sha256':C.digest(Path(C.__file__).read_bytes())}
        receipt=self.root/'job-validation.json';receipt.write_bytes(C.content(c['jobs'][0]['reviewed_validation']['path']))
        c['jobs'][0]['reviewed_validation']={'path':str(receipt),'sha256':C.digest(receipt.read_bytes())}
        args=fixture_authority(self.root,c);self.assertEqual(C.verify_config(args.config,args.sha256),c)
        calls=[];original_cycle=C.cycle
        def local_tick(config,job,a):
            calls.append(job['id']);C.verify_job(config,job)
            return {'status':'training' if calls.count(job['id'])==1 else 'completed'}
        def corrupt(seconds):
            self.assertEqual(seconds,600)
            self.assertFalse((Path(c['state_root'])/'EXIT.json').exists())
            receipt.write_text('{}')
            C.save(Path(c['state_root'])/'qo_seed2.START_INTENT.json',{'scope':'synthetic prior intent'})
        with patch.object(C.socket,'gethostname',return_value='k8s-node1'), \
             patch.object(C.threading,'Thread'),patch.object(C.time,'sleep',side_effect=corrupt), \
             patch.object(C,'cycle',side_effect=lambda x,a,s:original_cycle(x,a,s,local_tick)), \
             patch.object(C,'request_start',side_effect=AssertionError('no start allowed')):
            C.watch(c,args)
        end=C.load(Path(c['state_root'])/'EXIT.json')
        self.assertEqual(end['exit_code'],1)
        self.assertEqual(end['jobs']['qo_seed2']['status'],'needs_repair')
        self.assertEqual(end['jobs']['pt_seed2']['status'],'blocked')
        self.assertEqual(end['jobs']['pt_seed3']['status'],'completed')
        self.assertEqual(calls,['qo_seed2','pt_seed3','qo_seed2','pt_seed3'])


class LifecycleTests(FIX.SuccessorTests):
    """Inherit accepted realistic lifecycle suite, add external guard cases."""
    def control_config(self):
        c=C.load(RUN/'CONFIG.json')
        j=copy.deepcopy(c['jobs'][0]);j['chip']=1
        j['previous']={'kind':'evaluation','path':str(self.execution),'sha256':FIX.pin(self.execution)}
        return c,j

    def test_external_missing_evaluation_is_wait(self):
        c,j=self.control_config();self.assertIsNone(C.prerequisite(c,j,self.resource))

    def test_external_failed_terminal_is_explicit(self):
        c,j=self.control_config();FIX.write(self.previous/'ENGINEERING_EVAL_EXIT.json',{'exit_code':1,'attempt':1})
        with self.assertRaisesRegex(RuntimeError,'failed'):C.prerequisite(c,j,self.resource)

    def test_external_local_failure_without_global_marker(self):
        c,j=self.control_config();FIX.write(self.previous/'attempts/1/EXIT.json',{'exit_code':1,'attempt':1})
        with self.assertRaisesRegex(RuntimeError,'failed'):C.prerequisite(c,j,self.resource)

    def test_external_actual_lifecycle_success(self):
        self.finish_parent();c,j=self.control_config()
        result=C.prerequisite(c,j,self.resource)
        self.assertEqual(result['container_id'],'parent-id')
        self.assertIn('free_entry',result)

    def retained_control_fixture(self, live):
        c=C.load(RUN/'CONFIG.json');c['state_root']=str(self.state)
        p=C.load(c['jobs'][0]['plan']);p.update(out=str(self.out),allocation=str(self.alloc),chip=1,formal_chips=[1,4],
                                             run='fixture-control',review_path=str(self.out/'review.json'),review_sha256='PENDING')
        p['container']='nga-r3-formal-k1-qo-s2-'+hashlib.sha256(str(self.out).encode()).hexdigest()[:16]
        j=copy.deepcopy(c['jobs'][0]);j.update(plan=str(self.out/'plan.json'),chip=1)
        pin=C.digest(C.canonical(p))
        FIX.write(p['review_path'],dict(approved_plan_sha256=pin,verdict='PASS',review_kind='independent_astra',
                                      reviewer_model='gpt-6-astra',scope='SYNTHETIC CPU FIXTURE ONLY'))
        p['review_sha256']=FIX.pin(p['review_path']);FIX.write(j['plan'],p)
        j.update(raw_sha256=FIX.pin(j['plan']),canonical_sha256=pin,review_sha256=p['review_sha256'])
        c['jobs'][0]=j;args=fixture_authority(self.root,c)
        command=C.supervisor_command(c,args.config,args.sha256,args.activation,args.activation_sha256,j)
        C.save(self.state/'qo_seed2.START_INTENT.json',dict(job=j,config_sha256=args.sha256,command=command,
               config_path=args.config,activation_path=args.activation,activation_sha256=args.activation_sha256))
        # Explicit process-lookup boundary stub below; the policy validator stays real.
        service=dict(pid=os.getpid() if live else 2147483647,command=command)
        FIX.write(self.out/'SUPERVISOR_RECEIPT.json',service)
        launcher,resource=C.tools_for(p);docker=launcher.docker_command(p,j['plan'],1)
        actual=FIX.observed(docker,'retained-control-id');actual['State'].update(Status='running',FinishedAt='')
        self.patch(resource,'docker_inspect',return_value=actual)
        self.patch(resource,'image_inspect',return_value={'Id':FIX.E.IMAGE,'Config':{'Env':[]}})
        self.patch(resource,'daemon_policy',return_value={'runtime':'runc','cgroupns':'private'})
        a=self.out/'attempts/1'
        FIX.write(a/'LAUNCH_RECEIPT.json',dict(id=actual['Id'],image=p['image_sha256'],plan_sha256=pin))
        FIX.write(a/'LAUNCH_SPEC.json',dict(command=docker,plan_sha256=pin))
        FIX.write(a/'CLAIM.json',dict(successor_precondition=dict(config_sha256=args.sha256,job=j['id'],canonical_sha256=pin)))
        FIX.write(self.alloc,dict(allocation=[dict(chip=1,run=p['run'])],free=[]))
        before={q:q.read_bytes() for q in [a/'CLAIM.json',self.alloc]}
        h=C.helper(c)
        # Process lookup is the only OS boundary stub; retained policy is real.
        self.patch(h,'process_matches',return_value=live)
        self.patch(C,'helper',return_value=h)
        self.patch(resource,'release',side_effect=AssertionError('must retain claim'))
        self.patch(C,'request_start',side_effect=AssertionError('must not replay'))
        return c,j,p,resource,before

    def test_terminal_control_dead_supervisor_running_container_needs_repair(self):
        c,j,p,r,before=self.retained_control_fixture(False)
        result=C.terminal_control(c,j,p,r)
        self.assertEqual(result['status'],'needs_repair');self.assertEqual(result['container_id'],'retained-control-id')
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
        self.assertFalse((self.out/'attempts/1/RELEASE.json').exists())
        states={'qo_seed2':result,'pt_seed2':{'status':'blocked'},'pt_seed3':{'status':'training'}}
        self.assertIsNone(C.aggregate(states));states['pt_seed3']={'status':'completed'}
        self.assertEqual(C.aggregate(states),1)

    def test_terminal_control_live_supervisor_running_container_keeps_training(self):
        c,j,p,r,before=self.retained_control_fixture(True)
        result=C.terminal_control(c,j,p,r)
        self.assertEqual(result['status'],'training')
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
        self.assertIsNone(C.aggregate({'qo_seed2':result,'pt_seed2':{'status':'waiting_lane'},'pt_seed3':{'status':'completed'}}))

    def test_external_wrong_device_mount_generation(self):
        self.finish_parent();c,j=self.control_config();original=copy.deepcopy(self.actual)
        changes=[lambda d:d.update(Id='replacement'),
                 lambda d:d['HostConfig']['Devices'].append(dict(PathOnHost='/dev/davinci7',PathInContainer='/dev/davinci7',CgroupPermissions='rwm')),
                 lambda d:d['Mounts'].append(dict(Source='/extra',Destination='/extra',RW=True,Type='bind',Propagation='rprivate')),
                 lambda d:d['HostConfig'].update(Privileged=True),
                 lambda d:d['State'].update(StartedAt='replacement-start')]
        for mutate in changes:
            self.actual=copy.deepcopy(original);mutate(self.actual)
            with self.assertRaises(RuntimeError):C.prerequisite(c,j,self.resource)

    def test_original_claim_callback_twice_inside_real_lock(self):
        # Real resource.claim and its filesystem transaction, no ledger implementation substitute.
        r=module(ROOT/'r3_resource_adapter.py');alloc=self.root/'guard-allocation.json'
        FIX.write(alloc,{'allocation':[],'free':[{'chip':3,'previous_run':'previous','release_evidence':'fixture'}]})
        calls=[]
        def factory(args):
            def guard(doc):
                import fcntl
                with Path(str(alloc)+'.lock').open('a') as contender:
                    with self.assertRaises(BlockingIOError):fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
                calls.append(copy.deepcopy(doc));return {'job':'fixture','previous':'immutable'}
            return guard
        r.successor_guard=factory
        args=types.SimpleNamespace(alloc=str(alloc),run='new',chip=3,owner='fixture',purpose='CPU fixture',proof=str(self.root/'claim.json'))
        r.claim(args);self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1])
        proof=FIX.S.load(args.proof);self.assertIn('successor_precondition',proof)
        with self.assertRaisesRegex(RuntimeError,'already attempted'):r.claim(args)

    def test_configured_composition_uses_real_predecessor_and_transaction(self):
        self.finish_parent();c,j=self.control_config()
        p=C.load(j['plan']);p.update(out=str(self.out),allocation=str(self.alloc),chip=1,formal_chips=[1,4],
                                    run='fixture-control',review_path=str(self.out/'real-shape-review.json'),review_sha256='PENDING')
        suffix=hashlib.sha256(str(self.out).encode()).hexdigest()[:16]
        p['container']='nga-r3-formal-k1-qo-s2-'+suffix
        pin=C.digest(C.canonical(p))
        FIX.write(p['review_path'],{'approved_plan_sha256':pin,'verdict':'PASS','review_kind':'independent_astra',
                                   'reviewer_model':'gpt-6-astra','scope':'SYNTHETIC CPU FIXTURE ONLY'})
        p['review_sha256']=FIX.pin(p['review_path']);FIX.write(self.out/'plan.json',p)
        j.update(plan=str(self.out/'plan.json'),raw_sha256=FIX.pin(self.out/'plan.json'),canonical_sha256=pin,
                 review_sha256=p['review_sha256']);c['jobs'][0]=j
        adapter=module(Path(p['adapter']));self.patch(adapter,'docker_inspect',side_effect=self.inspect)
        self.patch(adapter,'live_chip_conflict',return_value=False)
        self.patch(adapter,'image_inspect',return_value={'Id':FIX.E.IMAGE,'Config':{'Env':[]}})
        self.patch(adapter,'daemon_policy',return_value={'runtime':'runc','cgroupns':'private'})
        # Add the fixed new control name to Docker's explicit fixture boundary.
        original_inspect=self.inspect
        adapter.docker_inspect=lambda name: None if name==p['container']+'-a1' else original_inspect(name)
        authority_calls=[]
        dispatch=C.configured_adapter(c,j,p,adapter,lambda:authority_calls.append(True),'a'*64)
        attempt=self.out/'attempts/1';attempt.mkdir(parents=True)
        dispatch(p,'claim',attempt,p['container']+'-a1',j['plan'],pin,None)
        proof=C.load(attempt/'CLAIM.json')
        self.assertGreaterEqual(len(authority_calls),3)
        self.assertEqual(proof['successor_precondition']['previous']['container_id'],'parent-id')
        self.assertEqual(proof['successor_precondition']['config_sha256'],'a'*64)
        self.assertEqual(C.load(self.alloc)['allocation'][0]['run'],'fixture-control')
        with self.assertRaises(RuntimeError):dispatch(p,'claim',attempt,p['container']+'-a1',j['plan'],pin,None)


if __name__=='__main__':
    unittest.main()
