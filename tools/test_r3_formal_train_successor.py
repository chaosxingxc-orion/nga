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
FROZEN = Path(os.environ.get('FORMAL_SUCCESSOR_TEST_TOOLS', str(BASE/'formal_k1_preparation_20261101_v6/seed2/tools')))

def module(path):
    path = Path(path); value = types.ModuleType(path.stem); value.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), value.__dict__)
    return value

S = module(Path(os.environ.get('FORMAL_SUCCESSOR_TEST_CONTROLLER', str(ROOT/'r3_formal_train_successor.py'))))
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
                    launcher=L.__file__,adapter=R.__file__,driver=S.__file__,
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

class FailclosedStartTests(unittest.TestCase):
    setUp = SuccessorTests.setUp
    patch = SuccessorTests.patch
    inspect = SuccessorTests.inspect
    seal_plan = SuccessorTests.seal_plan
    finish_parent = SuccessorTests.finish_parent
    lineage = SuccessorTests.lineage
    precondition = SuccessorTests.precondition
    claim = SuccessorTests.claim
    completed_successor = SuccessorTests.completed_successor
    release_args = SuccessorTests.release_args
    # Run only the new methods; original 27 are loaded separately by the runner.
    def abort_args(self):
        a=self.release_args();a.proof=str(self.out/'attempts/1/ABORT.json');return a

    def test_abort_all_generations_and_replays_are_inert(self):
        self.finish_parent();intent=self.precondition();self.claim(intent)
        a=self.abort_args()
        for mode in ('ordinary','wrong_generation','claim_replaced','proof_replay','intent_replay','container_live','device_live'):
            with self.subTest(mode=mode):
                ledger=json.loads(self.alloc.read_bytes());ledger['allocation']=[dict(ledger['allocation'][0]),dict(chip=4,run='unrelated')]
                if mode=='wrong_generation':ledger['allocation'][0]['claimed_utc']='new-generation'
                write(self.alloc,ledger)
                if mode=='claim_replaced':Path(a.claim).write_bytes(Path(a.claim).read_bytes()+b' ')
                if mode=='proof_replay':write(a.proof,dict(synthetic=True))
                if mode=='intent_replay':write(a.proof+'.intent',dict(synthetic=True))
                before={str(q):q.read_bytes() for q in (self.alloc,Path(a.claim),Path(a.proof),Path(a.proof+'.intent')) if q.exists()}
                with patch.object(R,'locked',side_effect=AssertionError('abort must not lock')),patch.object(R,'docker_inspect',side_effect=AssertionError('abort must not inspect')),patch.object(R,'live_chip_conflict',side_effect=AssertionError('abort must not observe device')),self.assertRaisesRegex(RuntimeError,'automatic abort disabled'):
                    R.abort_claim(a)
                self.assertEqual(before,{q:Path(q).read_bytes() for q in before})
                # The exposed CLI must reject without a different dispatch path.
                with self.assertRaisesRegex(RuntimeError,'automatic abort disabled'):
                    R.main(['abort','--alloc',a.alloc,'--run',a.run,'--chip','1','--container',a.container,'--claim',a.claim,'--proof',a.proof])
                self.assertEqual(self.alloc.read_bytes(),before[str(self.alloc)])

    def test_container_appearing_at_abort_lock_never_reaches_lock(self):
        self.finish_parent();intent=self.precondition();self.claim(intent);before=self.alloc.read_bytes()
        def late(path):
            self.formal_actual=observed(L.docker_command(self.p,self.job['plan'],1),'late-container')
            self.formal_actual['State']['Status']='running'
            return R.locked(path)
        with patch.object(R,'locked',side_effect=late) as lock,self.assertRaisesRegex(RuntimeError,'automatic abort disabled'):R.abort_claim(self.abort_args())
        lock.assert_not_called();self.assertEqual(before,self.alloc.read_bytes())

    @contextlib.contextmanager
    def launcher_boundary(self,dispatch,inspect=None):
        with patch.object(L,'verify',return_value=self.p),patch.object(L.socket,'gethostname',return_value='k8s-node1'),patch.object(L.subprocess,'check_output',return_value=json.dumps([{'Id':E.IMAGE}])),patch.object(L,'inspect',side_effect=inspect or self.inspect),patch.object(L,'source_module',return_value=R),patch.object(L.subprocess,'run',side_effect=dispatch),contextlib.redirect_stdout(io.StringIO()):
            yield

    def failure_case(self,mode):
        self.finish_parent();intent=self.precondition();calls=[];captured={};a=self.out/'attempts/1'
        def dispatch(cmd,**kwargs):
            if cmd[:2]==['docker','run']:
                calls.append('docker_run');captured['ledger']=self.alloc.read_bytes();captured['claim']=(a/'CLAIM.json').read_bytes()
                self.assertTrue((a/'NEEDS_REPAIR.json').exists())
                if mode in ('late_container','late_device'):
                    self.formal_actual=observed(cmd,'late-container');self.formal_actual['State']['Status']='running'
                if mode=='replace_claim':(a/'CLAIM.json').write_bytes(captured['claim']+b' ')
                if mode in ('missing_after_success','inspect_timeout','replace_claim_success'):
                    if mode=='replace_claim_success':
                        self.formal_actual=observed(cmd,'created');(a/'CLAIM.json').write_bytes(captured['claim']+b' ')
                    return None
                if mode=='keyboard_interrupt':raise KeyboardInterrupt('synthetic interruption')
                raise RuntimeError('synthetic uncertain docker run')
            if len(cmd)>3 and cmd[2]==R.__file__:
                calls.append(cmd[3]);self.assertEqual(cmd[3],'claim');return R.main(cmd[3:])
            raise AssertionError('unexpected external command')
        def inspect(name):
            if mode=='inspect_timeout' and 'docker_run' in calls:raise subprocess.TimeoutExpired('docker inspect',30)
            return self.inspect(name)
        # Preserve a concurrent unrelated chip exactly through the real claim/start failure.
        ledger=json.loads(self.alloc.read_bytes());ledger['allocation'].append(dict(chip=4,run='unrelated',claimed_utc='other'));write(self.alloc,ledger)
        with self.launcher_boundary(dispatch,inspect),self.assertRaises((RuntimeError,KeyboardInterrupt,subprocess.TimeoutExpired)):
            L.supervisor(self.job['plan'],self.job['plan_sha256'],1,intent['precondition_sha256'])
        marker=json.loads((a/'NEEDS_REPAIR.json').read_bytes())
        self.assertEqual(calls,['claim','docker_run']);self.assertEqual(self.alloc.read_bytes(),captured['ledger'])
        self.assertEqual(marker['captured_claim_utf8'].encode(),captured['claim']);self.assertEqual(marker['claim_sha256'],S.digest(captured['claim']))
        self.assertEqual(marker['plan_sha256'],self.job['plan_sha256']);self.assertEqual(marker['phase'],'docker_start_uncertain')
        self.assertFalse((a/'ABORT.json').exists());self.assertFalse((a/'RELEASE.json').exists())
        if mode not in ('replace_claim','replace_claim_success'):self.assertEqual((a/'CLAIM.json').read_bytes(),captured['claim'])
        marker_before=(a/'NEEDS_REPAIR.json').read_bytes()
        # Direct supervisor replay rejects even if the delayed container now appears.
        with self.launcher_boundary(dispatch,inspect),self.assertRaisesRegex(RuntimeError,'explicit repair'):
            L.supervisor(self.job['plan'],self.job['plan_sha256'],1,intent['precondition_sha256'])
        self.assertEqual(calls,['claim','docker_run']);self.assertEqual(marker_before,(a/'NEEDS_REPAIR.json').read_bytes())
        write(self.state/'seed2.START_INTENT.json',intent)
        with patch.object(S,'source',return_value=R):self.assertEqual(S.tick(self.job,self.a,self.state)['status'],'needs_repair')
        self.assertEqual(self.alloc.read_bytes(),captured['ledger'])

    def test_real_failure_branch_absent_retains_claim(self):self.failure_case('absent')
    def test_real_failure_branch_late_container_retains_claim(self):self.failure_case('late_container')
    def test_real_failure_branch_late_device_retains_claim(self):
        with patch.object(R,'live_chip_conflict',side_effect=lambda *args: self.formal_actual is not None):self.failure_case('late_device')
    def test_real_failure_branch_captures_claim_before_replacement(self):self.failure_case('replace_claim')
    def test_successful_docker_missing_observation_retains_claim(self):self.failure_case('missing_after_success')
    def test_successful_docker_inspect_timeout_retains_claim(self):self.failure_case('inspect_timeout')
    def test_successful_docker_claim_replacement_retains_claim(self):self.failure_case('replace_claim_success')
    def test_interrupted_docker_retains_claim(self):self.failure_case('keyboard_interrupt')

    def test_marker_file_and_directory_fsync(self):
        self.finish_parent();intent=self.precondition();self.claim(intent);a=self.out/'attempts/1';sync=os.fsync;calls=[]
        def record(fd):
            import stat
            calls.append('directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file');return sync(fd)
        with patch.object(L.os,'fsync',side_effect=record):L.start_marker(a,self.p,self.job['plan_sha256'],intent['precondition_sha256'],(a/'CLAIM.json').read_bytes(),'synthetic')
        self.assertEqual(calls,['file','directory'])

    def test_marker_blocks_completed_status(self):
        self.finish_parent();intent=self.completed_successor();write(self.out/'attempts/1/NEEDS_REPAIR.json',dict(synthetic=True))
        with patch.object(R,'docker_inspect',side_effect=AssertionError('must stop before Docker')):
            self.assertEqual(S.observe(self.job,self.p,intent,R)['status'],'needs_repair')

    def test_confirmed_start_clears_latch_only_after_retained_validation(self):
        self.finish_parent();intent=self.precondition();a=self.out/'attempts/1';calls=[]
        def dispatch(cmd,**kwargs):
            if cmd[:2]==['docker','run']:
                calls.append('docker_run');self.assertTrue((a/'NEEDS_REPAIR.json').exists())
                self.formal_actual=observed(cmd,'confirmed');self.formal_actual['State']['Status']='running';return None
            self.assertEqual(cmd[3],'claim');calls.append('claim');return R.main(cmd[3:])
        def stop_after_validation(seconds):
            self.assertFalse((a/'NEEDS_REPAIR.json').exists());self.assertTrue((a/'LAUNCH_RECEIPT.json').exists())
            raise RuntimeError('synthetic stop before monitoring')
        with self.launcher_boundary(dispatch),patch.object(L,'daemon_policy',return_value=dict(runtime='runc',cgroupns='private')),patch.object(L.time,'sleep',side_effect=stop_after_validation),self.assertRaisesRegex(RuntimeError,'synthetic stop'):
            L.supervisor(self.job['plan'],self.job['plan_sha256'],1,intent['precondition_sha256'])
        self.assertEqual(calls,['claim','docker_run']);self.assertFalse((a/'RELEASE.json').exists())

    def test_marker_fsync_failure_prevents_docker(self):
        self.finish_parent();intent=self.precondition();calls=[];a=self.out/'attempts/1'
        def dispatch(cmd,**kwargs):
            self.assertEqual(cmd[3],'claim');calls.append('claim');return R.main(cmd[3:])
        with self.launcher_boundary(dispatch),patch.object(L,'sync_directory',side_effect=OSError('synthetic fsync failed')),self.assertRaisesRegex(OSError,'synthetic fsync'):
            L.supervisor(self.job['plan'],self.job['plan_sha256'],1,intent['precondition_sha256'])
        self.assertEqual(calls,['claim']);self.assertTrue((a/'NEEDS_REPAIR.json').exists())
        self.assertEqual(json.loads(self.alloc.read_bytes())['allocation'][0],json.loads((a/'CLAIM.json').read_bytes())['entry'])

    def envelope_fixture(self):
        self.p['review_policy']=S.REVIEW_POLICY;self.p['review_sha256']='PENDING';h=S.identity(self.p)
        report=self.root/'independent-report.json';write(report,dict(verdict='PASS',scope=S.REVIEW_SCOPE,approved_canonical_plan_sha256=[h],synthetic=True))
        terminal=self.root/'worker-terminal.json';write(terminal,dict(exit_code=0,synthetic=True))
        result=self.root/'worker-result.txt';result.write_text('SYNTHETIC CPU FIXTURE ONLY\n')
        queue=self.root/'prepared-queue.json';write(queue,dict(controller=self.p['successor_guard']['controller'],jobs=[dict(plan=self.job['plan'],plan_sha256=h,plan_raw_sha256=h)]))
        ref=lambda p:dict(path=str(p),sha256=pin(p))
        value=dict(schema=S.REVIEW_POLICY,scope=S.REVIEW_SCOPE,requested_model='gpt-6-astra',model_evidence_kind='parent-observed-requested-model-dispatch',runtime_attestation='unavailable-not-required',worker_exit_code=0,worker_id='synthetic-worker',authenticator_identity='synthetic-parent',authenticated_at='synthetic',activation_authorized=False,review_report=ref(report),worker_terminal=ref(terminal),worker_result=ref(result),prepared_queue=ref(queue),plans=[dict(path=self.job['plan'],canonical_sha256=h,prepared_raw_sha256=h)],synthetic=True)
        self.attach_fixture(value,h);return value,h

    def attach_fixture(self,value,h):
        write(self.p['review_path'],value);self.p['review_sha256']=pin(self.p['review_path']);write(self.job['plan'],self.p);self.job.update(plan_sha256=h,plan_raw_sha256=pin(self.job['plan']))

    def test_requested_model_parent_pinned_fixture_accepts(self):
        value,h=self.envelope_fixture();self.assertEqual(S.plan(self.job),self.p)
        # Exact same verifier invoked by the isolated launcher, with source hash checked there.
        S.verify_review(self.p,h)

    def test_requested_model_envelope_pin_scope_and_policy_negatives(self):
        original,h=self.envelope_fixture()
        for field,value in [('requested_model','other'),('runtime_attestation','provider-attested'),('scope','activation'),('worker_exit_code',1),('activation_authorized',True),('plans',[])]:
            bad=copy.deepcopy(original);bad[field]=value;self.attach_fixture(bad,h)
            with self.subTest(field=field),self.assertRaises(RuntimeError):S.plan(self.job)
        for field in ('review_report','worker_terminal','worker_result','prepared_queue'):
            bad=copy.deepcopy(original);bad[field]['sha256']='0'*64;self.attach_fixture(bad,h)
            with self.subTest(field=field),self.assertRaises(RuntimeError):S.plan(self.job)
        self.attach_fixture(original,h);report=Path(original['review_report']['path']);v=json.loads(report.read_bytes());v['verdict']='BLOCK';write(report,v)
        original['review_report']['sha256']=pin(report);self.attach_fixture(original,h)
        with self.assertRaisesRegex(RuntimeError,'independent PASS'):S.plan(self.job)


if __name__=='__main__':unittest.main()
