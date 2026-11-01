"""CPU counterexamples: real controller/source/claim/flock/fsync; Docker replies synthetic.

No host inventory, Docker, network, NPU, TEST or experiment logs are accessed.
Frozen adapter/launcher path may be overridden for independent exact review.
"""
import contextlib
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
FROZEN = Path(os.environ.get('FORMAL_SUCCESSOR_TEST_TOOLS', str(BASE/'formal_k1_preparation_20261101_v5/seed2/tools')))

def module(path):
    path = Path(path); value = types.ModuleType(path.stem); value.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), value.__dict__)
    return value

S = module(ROOT/'r3_formal_train_successor.py')
R = module(FROZEN/'r3_resource_adapter.py')
L = module(FROZEN/'r3_formal_launcher.py')
E = module(BASE/'r0_current_scoring_20261031_v1/execution-tools/r3_posttrain_eval_launcher.py')


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def pin(path):return S.digest(Path(path).read_bytes())


def observed(command, cid):
    image = E.IMAGE; index = command.index(image)
    env = [command[i+1] for i,x in enumerate(command[:index]) if x=='-e']
    mounts = []
    for i,x in enumerate(command[:index]):
        if x=='--mount':
            v=dict(x.split('=',1) if '=' in x else (x,True) for x in command[i+1].split(','))
            mounts.append(dict(Source=v['src'],Destination=v['dst'],RW='readonly' not in v,Type='bind',Propagation='rprivate'))
    return dict(Id=cid,Name='/'+command[command.index('--name')+1],Image=image,
                Config=dict(Cmd=command[index+1:],Entrypoint=['python3'],Env=env),Mounts=mounts,
                State=dict(Status='exited',ExitCode=0,StartedAt='start',FinishedAt='finish'),
                HostConfig=dict(AutoRemove=False,Privileged=False,NetworkMode='none',Runtime='runc',CgroupnsMode='private',IpcMode='private',
                    ShmSize=64*1024**3,Ulimits=[dict(Name='memlock',Soft=-1,Hard=-1),dict(Name='stack',Soft=67108864,Hard=67108864)],
                    Devices=[dict(PathOnHost=command[i+1],PathInContainer=command[i+1],CgroupPermissions='rwm')
                             for i,x in enumerate(command[:index]) if x=='--device']))


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.previous=self.root/'previous';self.previous.mkdir()
        self.out=self.root/'formal';self.out.mkdir();self.state=self.root/'queue';self.state.mkdir()
        self.alloc=self.root/'allocation.json';self.execution=self.previous/'execution.json'
        self.model=self.root/'model';self.model.mkdir();(self.model/'.complete').write_text('revision\n')
        self.spec=dict(schema='r3-baseline-dev-spec-v1',evaluation_profile='track_k',model=str(self.model),
                       readonly_data_mounts=[],code_mounts=[],image_sha256=E.IMAGE,network='none',test_read=False,scientific_acceptance=False,
                       files={str(self.model/'.complete'):pin(self.model/'.complete'),str(self.model/'model.safetensors'):'a'*64})
        self.spec['command']=E.expected_command(self.spec,self.previous);write(self.previous/'spec.json',self.spec)
        self.prior=dict(schema='r3-engineering-posttrain-execution-v1',chip=1,out=str(self.previous),run='prior-run',
                        launcher=E.__file__,container='parent',allocation=str(self.alloc),spec=str(self.previous/'spec.json'),
                        spec_sha256=pin(self.previous/'spec.json'),tools={E.__file__:pin(E.__file__)})
        write(self.execution,self.prior)
        self.job=dict(id='seed2',chip=1,attempt=1,plan=str(self.out/'plan.json'),previous_execution=str(self.execution),
                      previous_execution_sha256=pin(self.execution),fresh_files=[],competitors=[])
        self.p=dict(schema='r3-formal-k1-plan-v1',seed=2,test_read=False,scientific_acceptance=False,out=str(self.out),
                    launcher=L.__file__,adapter=R.__file__,driver=str(ROOT/'r3_formal_train_successor.py'),
                    code='/fixture/code',model=str(self.model),train_file='/fixture/train.jsonl',image_sha256=E.IMAGE,
                    environment={},chip=1,container='formal',allocation=str(self.alloc),run='formal-run',
                    review_path=str(self.out/'review.json'),review_sha256='PENDING',
                    successor_guard=dict(controller=S.__file__,previous_execution=str(self.execution),
                                         previous_execution_sha256=pin(self.execution),competitors=[]))
        self.p['files']={x:pin(x) for x in (L.__file__,R.__file__,S.__file__)}
        self.seal_plan()
        self.a=dict(competitors={'seed2':[]},allowed_jobs=['seed2'])
        self.actual=observed(E.docker_command(self.prior,self.spec,str(self.execution),pin(self.execution),1),'parent-id')
        self.formal_actual=None
        self.resource=R
        self.patch(R,'docker_inspect',side_effect=self.inspect)
        self.patch(R,'live_chip_conflict',return_value=False)
        self.patch(R,'image_inspect',return_value={'Id':E.IMAGE,'Config':{'Env':[]}})
        self.patch(R,'daemon_policy',return_value={'runtime':'runc','cgroupns':'private'})
        # Any overlooked subprocess boundary fails closed, rather than touching Docker.
        self.patch(subprocess,'run',side_effect=AssertionError('unmocked external process'))
        self.patch(subprocess,'check_output',side_effect=AssertionError('unmocked external process'))

    def patch(self,obj,key,**kw):
        value=patch.object(obj,key,**kw);result=value.start();self.addCleanup(value.stop);return result

    def inspect(self,name):
        if name=='parent-a1':return copy.deepcopy(self.actual)
        if name=='formal-a1':return copy.deepcopy(self.formal_actual)
        raise AssertionError('unexpected Docker identity '+name)

    def seal_plan(self):
        h=S.identity(self.p)
        write(self.p['review_path'],dict(approved_plan_sha256=h,verdict='PASS',review_kind='independent_astra',reviewer_model='gpt-6-astra',scope='SYNTHETIC CPU FIXTURE ONLY'))
        self.p['review_sha256']=pin(self.p['review_path']);write(self.job['plan'],self.p)
        self.job.update(plan_sha256=h,plan_raw_sha256=pin(self.job['plan']))
        self.job['fresh_files']=sorted(str(f.relative_to(self.out)) for f in self.out.rglob('*') if f.is_file())

    def finish_parent(self):
        a=self.previous/'attempts/1';end=dict(exit_code=0,attempt=1)
        write(self.previous/'ENGINEERING_EVAL_EXIT.json',end);write(a/'EXIT.json',end)
        write(self.previous/'SUPERVISOR_RECEIPT.json',dict(pid=2147483647,command=[sys.executable,'-P',E.__file__,'supervise','--plan',str(self.execution),'--sha256',pin(self.execution),'--attempt','1']))
        write(a/'LAUNCH_RECEIPT.json',dict(id='parent-id',image=E.IMAGE,sha256=pin(self.execution)))
        write(a/'LAUNCH_SPEC.json',dict(command=E.docker_command(self.prior,self.spec,str(self.execution),pin(self.execution),1),sha256=pin(self.execution)))
        self.lineage(self.prior,a,self.actual)
        write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))
        self.results=self.previous/'results'
        files={'model.safetensors':'a'*64}
        modelhash=S.digest(json.dumps(dict(kind='checkpoint',weight_files=files,revision='revision'),sort_keys=True,separators=(',',':')).encode())
        write(self.results/'EVAL_COMPLETE.track_k.json',dict(exit_code=0,error=None))
        scorer=dict(record_grade=True,mode='rightpad',dtype='float32',token_budget=16384,hf32={'hf32':False})
        readout=self.results/'readouts/dev.jsonl';readout.parent.mkdir(parents=True)
        readout.write_text(json.dumps({'m':modelhash[:16],'value':1})+'\n')
        manifest=self.results/'manifests/track_k.json'
        write(manifest,dict(model_sha256=modelhash,stamp=modelhash[:16],scorer=scorer,tag='track_k',files={'readouts/dev.jsonl':{'sha256':pin(readout),'rows':1}}))
        write(self.results/'RUN_IDENTITY.json',dict(model_sha256=modelhash,model_path=str(self.model),arm='K0'))
        write(self.results/'SCORING_RECEIPT.track_k.json',dict(schema='r3-scoring-receipt-v1',scientific_acceptance=False,header=dict(
            argv=self.spec['command'][2:],provenance_manifest=str(manifest),model=dict(path=str(self.model),sha256=modelhash),device='npu:0',dry_run_warnings=[],arm='K0',scorer=scorer)))

    def lineage(self,p,a,actual,guard=None):
        entry=dict(chip=1,run=p['run'],claimed_utc='claim-time',owner='fixture')
        before=dict(allocation=[],free=[dict(chip=1,previous_run='earlier')])
        owned=dict(allocation=[entry],free=[])
        free=dict(chip=1,previous_run=p['run'],release_evidence=str(a/'RELEASE.json'),released_utc='free-time')
        released=dict(allocation=[],free=[free])
        claim=dict(schema='r3-resource-claim-v1',run=p['run'],chip=1,allocation=str(self.alloc),entry=entry,allocation_before=before,allocation_after=owned)
        if guard:claim['successor_precondition']=guard
        write(a/'CLAIM.json',claim)
        write(a/'RELEASE.json',dict(schema='r3-resource-release-v1',run=p['run'],chip=1,container=actual['Name'][1:],container_id=actual['Id'],
              container_started_at='start',container_finished_at='finish',exit_code=0,scientific_acceptance=False,allocation_before=owned,allocation_after=released,released_utc='proof-time'))
        if guard:
            release_path=a/'RELEASE.json';v=json.loads(release_path.read_bytes());v['claim_sha256']=pin(a/'CLAIM.json');write(release_path,v)
        write(self.alloc,released)

    def precondition(self):
        evidence=S.ready(self.job,self.p,R,self.a);self.assertEqual(evidence['status'],'eligible')
        path=self.out/'SUCCESSOR_PRECONDITION.json';write(path,dict(job=self.job,evidence=evidence,competitors=self.a['competitors']['seed2']))
        return dict(job=self.job,evidence=evidence,precondition_sha256=pin(path))

    def claim(self,intent):
        args=types.SimpleNamespace(alloc=str(self.alloc),run=self.p['run'],chip=1,proof=str(self.out/'attempts/1/CLAIM.json'),owner='fixture',purpose='CPU fixture',
                                  plan=self.job['plan'],plan_sha256=self.job['plan_sha256'],precondition_sha256=intent['precondition_sha256'])
        with contextlib.redirect_stdout(io.StringIO()):R.claim(args)
        return json.loads(Path(args.proof).read_bytes())

    def completed_successor(self):
        intent=self.precondition();a=self.out/'attempts/1';cmd=L.docker_command(self.p,self.job['plan'],1)
        self.formal_actual=observed(cmd,'formal-id')
        write(self.out/'SUPERVISOR_RECEIPT.json',dict(pid=2147483647,command=[sys.executable,'-P',L.__file__,'supervise','--plan',self.job['plan'],'--sha256',self.job['plan_sha256'],'--attempt','1','--precondition-sha256',intent['precondition_sha256']]))
        write(a/'LAUNCH_RECEIPT.json',dict(id='formal-id',image=E.IMAGE,plan_sha256=self.job['plan_sha256']))
        write(a/'LAUNCH_SPEC.json',dict(command=cmd,plan_sha256=self.job['plan_sha256']))
        self.lineage(self.p,a,self.formal_actual,dict(precondition_sha256=intent['precondition_sha256'],previous=intent['evidence']['previous']))
        end=dict(exit_code=0,attempt=1)
        write(self.out/'TRAIN_EXIT.json',end);write(a/'EXIT.json',end);write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))
        return intent

    def test_wait_then_real_lineage(self):
        self.assertIsNone(S.predecessor(self.job,R));self.finish_parent()
        result=S.ready(self.job,self.p,R,self.a);self.assertEqual(result['status'],'eligible')
        self.assertGreaterEqual(len(result['previous']['hashes']),15)

    def test_parent_done_and_newer_attempt_wait(self):
        self.finish_parent();done=self.previous/'attempts/1/SUPERVISOR_DONE.json';raw=done.read_bytes();done.unlink()
        self.assertIsNone(S.predecessor(self.job,R));done.write_bytes(raw)
        q=self.previous/'SUPERVISOR_RECEIPT.json';v=json.loads(q.read_bytes());v['command'][-1]='2';write(q,v)
        self.assertIsNone(S.predecessor(self.job,R))

    def test_existing_owner_waits_and_dirty_output_rejects(self):
        self.finish_parent();ledger=json.loads(self.alloc.read_bytes());original=copy.deepcopy(ledger)
        ledger['allocation']=[dict(chip=1,run='other')];ledger['free']=[];write(self.alloc,ledger)
        self.assertEqual(S.ready(self.job,self.p,R,self.a)['status'],'waiting_resource_owner')
        write(self.alloc,original);(self.out/'foreign').touch()
        with self.assertRaisesRegex(RuntimeError,'not fresh'):S.ready(self.job,self.p,R,self.a)

    def test_parent_buffer_race_rejects(self):
        self.finish_parent();q=self.previous/'attempts/1/RELEASE.json';original=S.Snapshot.raw
        def race(snap,path,pin=None):
            raw=original(snap,path,pin)
            if Path(path)==self.results/'RUN_IDENTITY.json':q.write_bytes(q.read_bytes()+b' ')
            return raw
        with patch.object(S.Snapshot,'raw',race),self.assertRaisesRegex(RuntimeError,'content changed'):S.predecessor(self.job,R)

    def test_B1_coherent_foreign_image_and_driver(self):
        self.finish_parent();a=self.previous/'attempts/1'
        write(a/'LAUNCH_RECEIPT.json',dict(id='parent-id',image='foreign',sha256=pin(self.execution)))
        write(a/'LAUNCH_SPEC.json',dict(command=['docker','run','foreign','foreign-driver'],sha256=pin(self.execution)))
        self.actual['Image']='foreign';self.actual['Config']['Cmd']=['foreign-driver']
        with self.assertRaisesRegex(RuntimeError,'launch identity'):S.predecessor(self.job,R)

    def test_B1_required_claim_completion_and_results(self):
        self.finish_parent()
        for q in (self.previous/'attempts/1/CLAIM.json',self.results/'EVAL_COMPLETE.track_k.json',self.results/'SCORING_RECEIPT.track_k.json',self.results/'manifests/track_k.json',self.results/'readouts/dev.jsonl'):
            raw=q.read_bytes();q.unlink()
            with self.subTest(path=q),self.assertRaises(FileNotFoundError):S.predecessor(self.job,R)
            q.write_bytes(raw)

    def test_B1_effective_configuration_negatives(self):
        self.finish_parent();old=copy.deepcopy(self.actual)
        mutations=[lambda x:x.update(Name='/foreign'),lambda x:x['Config'].update(Cmd=['foreign']),lambda x:x['Config'].update(Env=['EVIL=1']),
                   lambda x:x['Mounts'][0].update(RW=True),lambda x:x['HostConfig']['Devices'][0].update(PathInContainer='/wrong'),
                   lambda x:x['HostConfig'].update(Privileged=True),lambda x:x['HostConfig'].update(NetworkMode='host'),lambda x:x['HostConfig'].update(AutoRemove=True)]
        for mutate in mutations:
            self.actual=copy.deepcopy(old);mutate(self.actual)
            with self.subTest(mutation=mutate),self.assertRaises(RuntimeError):S.predecessor(self.job,R)

    def test_B1_foreign_result_lineage(self):
        self.finish_parent();q=self.results/'RUN_IDENTITY.json';v=json.loads(q.read_bytes());v['model_sha256']='foreign';write(q,v)
        with self.assertRaisesRegex(RuntimeError,'lineage'):S.predecessor(self.job,R)

    def test_B1_wrong_release_owner_or_claim_generation(self):
        self.finish_parent();q=self.previous/'attempts/1/RELEASE.json';old=json.loads(q.read_bytes())
        for field,value in [('run','foreign'),('chip',4),('container_id','foreign'),('container_started_at','wrong')]:
            write(q,dict(old,**{field:value}))
            with self.subTest(field=field),self.assertRaises(RuntimeError):S.predecessor(self.job,R)
        v=copy.deepcopy(old);v['allocation_before']['allocation'][0]['claimed_utc']='other-claim';write(q,v)
        with self.assertRaisesRegex(RuntimeError,'generation'):S.predecessor(self.job,R)

    def test_B2_changed_target_free_generation_rejected_real_claim(self):
        self.finish_parent();intent=self.precondition();ledger=json.loads(self.alloc.read_bytes());ledger['free'][0]['previous_run']='intervening-foreign-run';write(self.alloc,ledger)
        before=self.alloc.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'free predecessor generation'):self.claim(intent)
        self.assertEqual(self.alloc.read_bytes(),before)

    def test_B2_unrelated_chip_update_survives_real_claim(self):
        self.finish_parent();intent=self.precondition();ledger=json.loads(self.alloc.read_bytes());ledger['allocation'].append(dict(chip=4,run='scale-chain',claimed_utc='new'));ledger['free'].append(dict(chip=6,previous_run='other'));write(self.alloc,ledger)
        proof=self.claim(intent);now=json.loads(self.alloc.read_bytes())
        self.assertIn(ledger['allocation'][0],now['allocation']);self.assertIn(ledger['free'][1],now['free'])
        self.assertEqual(proof['successor_precondition']['previous'],intent['evidence']['previous'])
        with self.assertRaisesRegex(RuntimeError,'already attempted'):self.claim(intent)

    def test_B2_all_observations_under_real_flock(self):
        self.finish_parent();intent=self.precondition();calls=[]
        def observed_locked(name):
            with Path(str(self.alloc)+'.lock').open('a') as lock:
                with self.assertRaises(BlockingIOError):fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            calls.append(name);return self.inspect(name)
        with patch.object(R,'docker_inspect',side_effect=observed_locked):self.claim(intent)
        self.assertEqual(calls.count('parent-a1'),2);self.assertEqual(calls.count('formal-a1'),2)

    def test_B2_parent_changes_after_ready(self):
        self.finish_parent();intent=self.precondition();self.actual['Id']='replacement'
        with self.assertRaisesRegex(RuntimeError,'generation'):self.claim(intent)

    def test_B2_name_and_device_rechecked_at_claim(self):
        self.finish_parent();intent=self.precondition();self.formal_actual=observed(L.docker_command(self.p,self.job['plan'],1),'collision')
        with self.assertRaisesRegex(RuntimeError,'name collision'):self.claim(intent)
        self.formal_actual=None
        with patch.object(R,'live_chip_conflict',return_value=True),self.assertRaisesRegex(RuntimeError,'device holder'):self.claim(intent)

    def test_B2_live_competitor_rechecked_at_claim(self):
        self.finish_parent();service=self.root/'service.json'
        write(service,dict(pid=os.getpid(),command=['previously-dead']))
        competitor=dict(receipt=str(service),sha256=pin(service));self.p['successor_guard']['competitors']=[competitor];self.seal_plan();self.a['competitors']['seed2']=[competitor]
        intent=self.precondition()
        # Deterministic /proc replacement only for the exact competitor PID.
        original=Path.read_bytes
        def proc(path):
            if str(path)==f'/proc/{os.getpid()}/cmdline':return b'previously-dead\0'
            return original(path)
        with patch.object(Path,'read_bytes',proc),self.assertRaisesRegex(RuntimeError,'competing authorized'):self.claim(intent)

    def test_B2_evidence_mutation_before_commit_leaves_intent_no_claim(self):
        self.finish_parent();intent=self.precondition();original=R.write_atomic
        def mutate(path,value):
            result=original(path,value)
            if str(path).endswith('CLAIM.json.intent'):
                q=self.results/'EVAL_COMPLETE.track_k.json';write(q,dict(exit_code=1,error='changed'))
            return result
        before=self.alloc.read_bytes()
        with patch.object(R,'write_atomic',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'completion failed'):self.claim(intent)
        self.assertEqual(before,self.alloc.read_bytes());self.assertTrue((self.out/'attempts/1/CLAIM.json.intent').exists())
        with self.assertRaisesRegex(RuntimeError,'already attempted'):self.claim(intent)

    def release_args(self):
        return types.SimpleNamespace(alloc=str(self.alloc),run=self.p['run'],chip=1,
                    proof=str(self.out/'attempts/1/RELEASE.json'),claim=str(self.out/'attempts/1/CLAIM.json'),
                    container='formal-a1',container_id='formal-id')

    def test_real_release_preserves_unrelated_chip_and_claim(self):
        self.finish_parent();intent=self.precondition();proof=self.claim(intent)
        self.formal_actual=observed(L.docker_command(self.p,self.job['plan'],1),'formal-id')
        ledger=json.loads(self.alloc.read_bytes());ledger['allocation'].append(dict(chip=4,run='scale'))
        write(self.alloc,ledger)
        with contextlib.redirect_stdout(io.StringIO()):R.release(self.release_args())
        released=json.loads(Path(self.release_args().proof).read_bytes())
        self.assertEqual(released['claim_sha256'],pin(self.release_args().claim))
        self.assertEqual(S.ownership(self.p,proof,released,Path(self.release_args().proof),self.formal_actual)['previous_run'],'formal-run')
        self.assertEqual(json.loads(self.alloc.read_bytes())['allocation'],[dict(chip=4,run='scale')])

    def test_real_release_rejects_same_run_different_claim_generation(self):
        self.finish_parent();intent=self.precondition();self.claim(intent)
        self.formal_actual=observed(L.docker_command(self.p,self.job['plan'],1),'formal-id')
        ledger=json.loads(self.alloc.read_bytes());ledger['allocation'][0]['claimed_utc']='other';write(self.alloc,ledger)
        before=self.alloc.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'claim generation'):R.release(self.release_args())
        self.assertEqual(self.alloc.read_bytes(),before)

    def test_real_release_rechecks_under_lock_and_rejects_replacement(self):
        self.finish_parent();intent=self.precondition();self.claim(intent)
        self.formal_actual=observed(L.docker_command(self.p,self.job['plan'],1),'formal-id')
        original=R.write_atomic
        def mutate(path,value):
            result=original(path,value)
            if str(path).endswith('RELEASE.json.intent'):self.formal_actual['Id']='replacement'
            return result
        before=self.alloc.read_bytes()
        with patch.object(R,'write_atomic',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'generation'):R.release(self.release_args())
        self.assertEqual(before,self.alloc.read_bytes())
        with self.assertRaises(RuntimeError):R.release(self.release_args())

    def test_B4_completed_hashes_all_validated_buffers(self):
        self.finish_parent();intent=self.completed_successor();v=S.observe(self.job,self.p,intent,R)
        self.assertEqual(v['status'],'completed')
        self.assertTrue(all(pin(f)==h for f,h in v['hashes'].items()))
        for name in ('CLAIM.json','LAUNCH_SPEC.json','LAUNCH_RECEIPT.json','SUPERVISOR_RECEIPT.json','SUCCESSOR_PRECONDITION.json'):
            self.assertTrue(any(Path(f).name==name for f in v['hashes']))

    def test_B4_replacement_after_semantic_read_rejected(self):
        self.finish_parent();intent=self.completed_successor();a=self.out/'attempts/1';original=S.Snapshot.raw
        def racing(snap,path,pin=None):
            raw=original(snap,path,pin)
            if Path(path)==a/'SUPERVISOR_DONE.json':
                q=a/'RELEASE.json';v=json.loads(q.read_bytes());v['run']='foreign-after-validation-read';write(q,v)
            return raw
        with patch.object(S.Snapshot,'raw',racing),self.assertRaisesRegex(RuntimeError,'content changed'):S.observe(self.job,self.p,intent,R)

    def test_B4_launch_claim_receipt_replacements_rejected(self):
        self.finish_parent();intent=self.completed_successor();a=self.out/'attempts/1';original=S.Snapshot.raw
        for target in (a/'CLAIM.json',a/'LAUNCH_SPEC.json',a/'LAUNCH_RECEIPT.json',self.out/'SUPERVISOR_RECEIPT.json'):
            saved=target.read_bytes()
            def racing(snap,path,pin=None):
                raw=original(snap,path,pin)
                if Path(path)==a/'SUPERVISOR_DONE.json':target.write_bytes(saved+b' ')
                return raw
            with self.subTest(target=target),patch.object(S.Snapshot,'raw',racing),self.assertRaisesRegex(RuntimeError,'content changed'):S.observe(self.job,self.p,intent,R)
            target.write_bytes(saved)

    def test_uncertain_start_never_replays(self):
        self.finish_parent()
        original=S.source
        with patch.object(S,'source',side_effect=lambda path,h:R if path==R.__file__ else original(path,h)), patch.object(subprocess,'run',side_effect=[None,RuntimeError('uncertain launch')]) as run:
            with self.assertRaisesRegex(RuntimeError,'uncertain launch'):S.tick(self.job,self.a,self.state)
            self.assertEqual(S.tick(self.job,self.a,self.state)['status'],'needs_repair');self.assertEqual(run.call_count,2)

    def test_queue_independent_progress(self):
        jobs=[dict(self.job,id='seed3'),self.job];auth=dict(self.a,allowed_jobs=['seed2','seed3'])
        with patch.object(S,'tick',side_effect=[RuntimeError('waiting scale chain'),{'status':'launch_requested'}]):
            states=S.cycle({'jobs':jobs},auth,self.state)
        self.assertEqual(states['seed2']['status'],'launch_requested')

    def test_no_approval_forged(self):
        self.p['review_sha256']='PENDING';write(self.job['plan'],self.p);self.job['plan_raw_sha256']=pin(self.job['plan'])
        with self.assertRaises(RuntimeError):S.plan(self.job)
        self.assertEqual(S.plan(self.job,reviewed=False),self.p)


class DockerParserTests(unittest.TestCase):
    def test_B3_only_exact_requested_absence(self):
        for func in (R.docker_inspect,L.inspect):
            for stderr in ('Error: No such object: formal-a1','Error response from daemon: No such container: formal-a1'):
                with self.subTest(func=func,stderr=stderr),patch.object(subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stderr=stderr+'\n',stdout='[]\n')):
                    self.assertIsNone(func('formal-a1'))

    def test_B3_uncertain_errors_and_successes_never_absent(self):
        cases=[(1,'Cannot connect: dial unix /var/run/docker.sock: no such file or directory',''),(1,'Error: No such object: other','[]'),
               (1,'permission denied',''),(1,'Error: No such object: formal-a1\ntransport failed','[]'),(0,'','[]'),(0,'','{}'),(0,'','[{}]'),(0,'','garbage')]
        for func in (R.docker_inspect,L.inspect):
            for rc,stderr,stdout in cases:
                with self.subTest(func=func,stderr=stderr,stdout=stdout),patch.object(subprocess,'run',return_value=types.SimpleNamespace(returncode=rc,stderr=stderr,stdout=stdout)),self.assertRaises((RuntimeError,ValueError)):
                    func('formal-a1')
            with patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired('docker inspect',30)),self.assertRaises(subprocess.TimeoutExpired):func('formal-a1')

if __name__=='__main__':unittest.main()
