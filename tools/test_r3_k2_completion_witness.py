"""Synthetic CPU chain tests. In-memory path routing is NOT production evidence.

Pinned real execution/spec/source are used for pure command derivation. All future
completion documents, observer/parent attestations and rows are synthetic and only
written under TemporaryDirectory; no original predecessor path is written.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('witness', Path(__file__).with_name('r3_k2_completion_witness.py'))
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
PLAN = 'a'*64
SCHEMA = Path(__file__).resolve().parent.parent/'.local/reports/k2-retained-v2-independent-review/completion-witness.schema.json'
if not SCHEMA.exists(): SCHEMA = Path(__file__).resolve().parent.parent/'completion-witness.schema.json'


def reference(path):
    raw = Path(path).read_bytes()
    return dict(path=str(path), sha256=W.digest(raw), bytes=len(raw))


class SyntheticChain:
    def __init__(self, directory):
        self.directory = directory; self.mapping = {}; self.docs = {}; self.refs = {}
        self.original_opened = W.opened
        self.execution = json.loads((W.ROOT/'execution.json').read_bytes())
        self.spec = json.loads((W.ROOT/'plan.json').read_bytes())
        self.sources = [reference(p) for p in sorted({**self.execution['tools'], **{p:h for p,h in self.spec['files'].items() if p.endswith('.py')}})]
        self.argv, self.scorer = W.derive(self.execution, self.spec, Path(self.execution['launcher']).read_bytes())
        self.verifier = reference(W.__file__)
        self.put('execution', self.execution); self.put('spec', self.spec)
        self.put('launch_spec', dict(command=self.argv, sha256=W.EXECUTION))
        self.put('launch_receipt', dict(id=W.CID, image=W.IMAGE, sha256=W.EXECUTION))
        # Keep exact execution and spec bytes; pretty reserialization would change their identities.
        for key, name in [('execution','execution.json'), ('spec','plan.json')]:
            self.mapping[self.refs[key]['path']].write_bytes((W.ROOT/name).read_bytes())
            self.refs[key] = dict(reference(self.mapping[self.refs[key]['path']]), path=str(W.ROOT/name))
        claim = json.loads((W.ROOT/'attempts/1/CLAIM.json').read_bytes()); self.put('claim', claim)
        release_before = copy.deepcopy(claim['allocation_after']); release_after = copy.deepcopy(release_before)
        release_after['allocation'] = [x for x in release_after['allocation'] if x['chip'] != 3]
        self.finish = '2026-11-02T00:00:03Z'; self.released = '2026-11-02T00:00:04Z'; self.observed = '2026-11-02T00:00:05Z'
        act = json.loads((W.ROOT/'ACTUAL_ACTIVATION_VERIFIED.json').read_bytes())
        self.start = act['container_state']['StartedAt']
        release_after['free'] = sorted(release_after['free']+[dict(chip=3, previous_run=W.RUN, release_evidence=str(W.ROOT/W.FIXED['release']), released_utc=self.released)], key=lambda x:x['chip'])
        release = dict(schema='r3-resource-release-v1', run=W.RUN, chip=3, container=W.NAME, container_id=W.CID,
                       container_started_at=self.start, container_finished_at=self.finish, exit_code=0,
                       scientific_acceptance=False, released_utc=self.released)
        for key, value in [('before', release_before), ('after', release_after)]:
            release['allocation_'+key] = value; release['allocation_'+key+'_sha256'] = W.digest(W.ledger_bytes(value))
        self.put('release', release)
        terminal = dict(attempt=1, exit_code=0, utc_seconds=W.timestamp('2026-11-02T00:00:02Z'), scientific_acceptance=False)
        self.put('attempt_terminal', terminal); self.put('root_terminal', terminal)
        self.put('supervisor_done', dict(exit_code=0, scientific_acceptance=False))
        self.put('evaluator_complete', dict(exit_code=0, error=None, utc='2026-11-02T00:00:01Z'))
        model = self.spec['model']; revision = (Path(model)/'.complete').read_text().splitlines()[0].strip()
        weights = {str(Path(p).relative_to(model)): sha for p,sha in self.spec['files'].items() if Path(p).is_relative_to(model) and Path(p).suffix in ('.safetensors','.pt','.bin')}
        self.model_sha = W.digest(json.dumps(dict(kind='checkpoint',weight_files=weights,revision=revision),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
        scorer = dict(record_grade=True, mode='rightpad',dtype='float32',token_budget=16384,hf32={'hf32':False})
        self.outputs = []
        for rel in sorted(W.expected_outputs(self.scorer)):
            raw = (json.dumps(dict(k=rel,m=self.model_sha[:16]))+'\n').encode()
            path = str(W.ROOT/'results'/rel); ref = self.raw(path, raw); ref['rows'] = 1; self.outputs.append(ref)
        manifest = dict(model_sha256=self.model_sha,stamp=self.model_sha[:16],tag='track_kt',scorer=scorer,utc='2026-11-02T00:00:00Z',
                        files={str(Path(r['path']).relative_to(W.ROOT/'results')):dict(sha256=r['sha256'],rows=r['rows']) for r in self.outputs})
        self.put('unit_manifest', manifest)
        self.put('run_identity', dict(model_sha256=self.model_sha, model_path=model,arm='K0',track_t_config='r3',prompt_version='r0-prompt-v2'))
        data = {p:self.spec['files'][p] for p in self.spec['readonly_data_mounts'] if Path(p).name != 'manifest.json'}
        header = dict(argv=self.scorer[2:],arm='K0',stages='k_score,t_score',partitions=['dev','calibration'],dtype='float32',device='npu:0',track_t_config='r3',
                      limit=0,limit_groups=0,dry_run_warnings=[],provenance_manifest=str(W.ROOT/W.FIXED['unit_manifest']),
                      model=dict(path=model,sha256=self.model_sha,kind='checkpoint',base_path=model,base_revision=revision),
                      scorer=scorer,data_files=data,prompt_version='r0-prompt-v2',prompt_format='raw-completion (no chat template)',render='record_name',primary_input_mode='full',track_t_sources='typed-decisions,openjev-synth,akhilaaa3',utc='2026-11-01T08:22:00Z')
        self.put('scoring_receipt', dict(schema='r3-scoring-receipt-v1',scientific_acceptance=False,
                 scope='producer header only; CPU must verify and rebuild metrics from readouts',track_k={'partitions':{}},header=header))
        image_config = dict(Env=['PATH=/synthetic/image/bin'],User='',WorkingDir='')
        policy = W.container_policy(self.argv,image_config); self.put('container_spec',policy)
        host = dict(NetworkMode='none',AutoRemove=False,RestartPolicy=policy['restart'],ShmSize=policy['shm_size'],
                    Privileged=False,ReadonlyRootfs=False,PidMode='',IpcMode='private',CapAdd=None,CapDrop=None,SecurityOpt=None,
                    Binds=None,VolumesFrom=None,DeviceRequests=None,Devices=policy['devices'],Ulimits=policy['ulimits'])
        actual = dict(Id=W.CID,Name='/'+W.NAME,Image=W.IMAGE,RestartCount=0,Config=dict(Entrypoint=['python3'],Cmd=policy['cmd'],
                      User='',WorkingDir='',Image=W.IMAGE,Env=[k+'='+v for k,v in policy['environment'].items()]),HostConfig=host,
                      Mounts=policy['mounts'],State=dict(Status='exited',Running=False,Paused=False,Restarting=False,OOMKilled=False,
                      Dead=False,ExitCode=0,Error='',StartedAt=self.start,FinishedAt=self.finish))
        self.put('container_observation',dict(schema='k2-trusted-container-observation-v1',observer_id='synthetic-observer',
                 observed_utc=self.observed,test_read=False,scientific_acceptance=False,inspect=actual,
                 image_inspect=dict(Id=W.IMAGE,Config=image_config),artifacts={},result_files=self.outputs))
        self.put('prelaunch_authentication',dict(schema='k2-prelaunch-parent-authentication-v1',parent_id='synthetic-parent',
                 execution=self.refs['execution'],spec=self.refs['spec'],source_writers=self.sources,
                 historical_trust_scope='prelaunch-verification-and-retained-container-observation',source_consumption_proven=False,
                 test_read=False,scientific_acceptance=False,prelaunch_receipt=reference(W.ROOT/'PRELAUNCH_VERIFIED.json'),
                 activation_receipt=reference(W.ROOT/'ACTUAL_ACTIVATION_VERIFIED.json'),
                 root_handoff=reference('/home/xingchao/workspace/nga/.local/reports/chip3-ready-successor-handoff-result.json'),verified_before_launch_utc='2026-11-01T08:21:00Z'))
        self.refresh()

    def raw(self,path,raw):
        f = self.directory/(str(len(self.mapping))+'.data') if path not in self.mapping else self.mapping[path]
        f.write_bytes(raw); self.mapping[path] = f
        return dict(path=path,sha256=W.digest(raw),bytes=len(raw))

    def put(self,key,doc):
        path = str(W.ROOT/W.FIXED[key]) if key in W.FIXED else str(self.directory/(key+'.json'))
        self.docs[key] = copy.deepcopy(doc)
        self.refs[key] = self.raw(path,(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode())

    def refresh(self):
        fixed = {k:self.refs[k] for k in W.FIXED}
        observation = self.docs['container_observation']; observation['artifacts'] = fixed; observation['result_files'] = self.outputs
        self.put('container_observation',observation)
        derived = dict(docker_argv=self.argv,scorer_argv=self.scorer,container_spec=self.refs['container_spec'])
        results = dict(files=len(self.outputs),rows=sum(r['rows'] for r in self.outputs),bytes=sum(r['bytes'] for r in self.outputs),expected_model_sha256=self.model_sha)
        self.put('verification_report',dict(schema='k2-completion-chain-verification-v1',reviewer_id='synthetic-reviewer',consumer_plan_sha256=PLAN,
                 artifacts=fixed,source_writers=self.sources,result_files=self.outputs,results=results,derived=derived,
                 test_read=False,scientific_acceptance=False,activation_authorized=False))
        witness = dict(schema='k2-authenticated-legacy-completion-witness-v1',issued_utc='2026-11-02T00:00:06Z',issuer_id='synthetic-issuer',
                       consumer_plan_sha256=PLAN,verifier=self.verifier,
                       predecessor=dict(run=W.RUN,out=str(W.ROOT),attempt=1,chip=3,execution_sha256=W.EXECUTION,spec_sha256=W.SPEC,
                                        container_name=W.NAME,container_id=W.CID,image=W.IMAGE),
                       artifacts={k:self.refs[k] for k in (*W.FIXED,'container_observation','prelaunch_authentication','verification_report')},
                       source_writers=self.sources,result_files=self.outputs,derived=derived,
                       completion=dict(legacy_terminal_plan_sha256_absent=True,exit_code=0,container_status='exited',started_at=self.start,
                                       finished_at=self.finish,released_utc=self.released,observed_utc=self.observed),
                       authentication=dict(method='external-parent-pinned-attestation',authenticated_by='synthetic-parent',trust_anchor=self.refs['prelaunch_authentication']),
                       activation_authorized=False,scientific_acceptance=False,test_read=False)
        self.put('witness',witness)
        self.put('parent_attestation',dict(schema='k2-completion-parent-attestation-v1',parent_id='synthetic-parent',consumer_plan_sha256=PLAN,
                 witness=self.refs['witness'],verifier=self.verifier,prelaunch_authentication=self.refs['prelaunch_authentication'],
                 container_observation=self.refs['container_observation'],verification_report=self.refs['verification_report'],reviewer_id='synthetic-reviewer',
                 issuer_id='synthetic-issuer',activation_authorized=False,scientific_acceptance=False,test_read=False,attested_utc='2026-11-02T00:00:07Z'))
        self.put('request',dict(schema='k2-completion-verification-request-v1',consumer_plan_sha256=PLAN,ready=True,parent_id='synthetic-parent',
                 reviewer_id='synthetic-reviewer',observer_id='synthetic-observer',witness_schema=reference(SCHEMA),verifier=self.verifier,
                 witness=self.refs['witness'],parent_attestation=self.refs['parent_attestation'],prelaunch_authentication=self.refs['prelaunch_authentication'],
                 container_observation=self.refs['container_observation'],activation_authorized=False,scientific_acceptance=False,test_read=False))

    def opened(self,path): return self.original_opened(str(self.mapping.get(path,path)))

    def walk(self,root,**kw):
        prefix = str(root)+'/'
        groups = {}
        for r in self.outputs:
            p = Path(r['path'])
            if str(p).startswith(prefix): groups.setdefault(str(p.parent),[]).append(p.name)
        return [(p,[],names) for p,names in groups.items()]

    def verify(self,plan=PLAN):
        with patch.object(W,'opened',self.opened), patch.object(W.os,'walk',self.walk):
            return W.verify(self.refs['request']['path'],self.refs['request']['sha256'],plan)


class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='k2-synthetic-'); self.addCleanup(self.temp.cleanup)
        self.f = SyntheticChain(Path(self.temp.name))

    def reject(self,key,mutate):
        doc=copy.deepcopy(self.f.docs[key]); mutate(doc); self.f.put(key,doc); self.f.refresh()
        with self.assertRaises((ValueError,KeyError,TypeError,OSError)): self.f.verify()

    def test_complete_synthetic_chain_and_retained_pins(self):
        result=self.f.verify(); self.assertEqual(result['results']['files'],32)
        self.assertFalse(result['activation_authorized']); self.assertFalse(result['source_consumption_proven'])
        self.assertIn(self.f.refs['attempt_terminal'],result['checked_metadata'])

    def test_consumer_replay(self):
        with self.assertRaises(ValueError): self.f.verify('b'*64)

    def test_wrong_external_request_pin(self):
        with patch.object(W,'opened',self.f.opened),self.assertRaises(ValueError):
            W.verify(self.f.refs['request']['path'],'0'*64,PLAN)

    def test_self_declared_witness_not_authentication(self):
        self.f.mapping[self.f.refs['parent_attestation']['path']].write_text('{"authenticated":true}')
        with self.assertRaises(ValueError):self.f.verify()

    def test_missing_parent(self):
        self.f.mapping[self.f.refs['parent_attestation']['path']].unlink()
        with self.assertRaises(OSError):self.f.verify()

    def test_missing_observer(self):
        self.f.mapping[self.f.refs['container_observation']['path']].unlink()
        with self.assertRaises(OSError):self.f.verify()

    def test_rehashed_launch_substitution(self): self.reject('launch_spec',lambda d:d['command'].append('--privileged'))
    def test_rehashed_receipt_substitution(self): self.reject('launch_receipt',lambda d:d.update(id='b'*64))
    def test_rehashed_attempt_replay(self): self.reject('attempt_terminal',lambda d:d.update(attempt=2))
    def test_rehashed_null_terminal_pin(self): self.reject('attempt_terminal',lambda d:d.update(plan_sha256=None))
    def test_rehashed_wrong_terminal_pin(self): self.reject('attempt_terminal',lambda d:d.update(plan_sha256='b'*64))
    def test_rehashed_matching_pin_not_legacy(self): self.reject('attempt_terminal',lambda d:d.update(plan_sha256=W.EXECUTION))
    def test_fallback_refused(self): self.reject('attempt_terminal',lambda d:d.update(source='retained-container-exit'))
    def test_false_exit_is_not_zero(self): self.reject('supervisor_done',lambda d:d.update(exit_code=False))
    def test_missing_scope(self): self.reject('supervisor_done',lambda d:d.pop('scientific_acceptance'))
    def test_null_scope(self): self.reject('supervisor_done',lambda d:d.update(scientific_acceptance=None))
    def test_evaluator_error(self): self.reject('evaluator_complete',lambda d:d.update(error='synthetic failure'))
    def test_release_wrong_identity(self): self.reject('release',lambda d:d.update(container_id='b'*64))
    def test_release_missing_exit(self): self.reject('release',lambda d:d.pop('exit_code'))
    def test_ledger_digest_wrong(self): self.reject('release',lambda d:d.update(allocation_before_sha256='b'*64))
    def test_running_observation(self): self.reject('container_observation',lambda d:d['inspect']['State'].update(Status='running'))
    def test_wrong_image(self): self.reject('container_observation',lambda d:d['inspect'].update(Image='sha256:'+'b'*64))
    def test_wrong_cmd(self): self.reject('container_observation',lambda d:d['inspect']['Config']['Cmd'].append('--attempt=2'))
    def test_wrong_device(self): self.reject('container_observation',lambda d:d['inspect']['HostConfig']['Devices'][0].update(PathOnHost='/dev/davinci7'))
    def test_wrong_mount(self): self.reject('container_observation',lambda d:d['inspect']['Mounts'][0].update(RW=True))
    def test_missing_env(self): self.reject('container_observation',lambda d:d['inspect']['Config'].pop('Env'))
    def test_autoremove(self): self.reject('container_observation',lambda d:d['inspect']['HostConfig'].update(AutoRemove=True))
    def test_restart(self): self.reject('container_observation',lambda d:d['inspect']['HostConfig']['RestartPolicy'].update(Name='always'))
    def test_network(self): self.reject('container_observation',lambda d:d['inspect']['HostConfig'].update(NetworkMode='host'))
    def test_observer_self_identity(self): self.reject('container_observation',lambda d:d.update(observer_id='self'))
    def test_timestamp_inversion(self): self.reject('release',lambda d:d.update(released_utc='2026-11-01T01:00:00Z'))
    def test_rehashed_header_command(self): self.reject('scoring_receipt',lambda d:d['header']['argv'].append('--partitions=test'))
    def test_rehashed_manifest_model(self): self.reject('unit_manifest',lambda d:d.update(model_sha256='b'*64))
    def test_rehashed_manifest_missing_output(self): self.reject('unit_manifest',lambda d:d['files'].pop(next(iter(d['files']))))
    def test_rehashed_scorer_scope(self): self.reject('scoring_receipt',lambda d:d['header']['scorer'].update(record_grade=False))
    def test_changed_result_buffer(self):
        self.f.mapping[self.f.outputs[0]['path']].write_bytes(b'{}\n')
        with self.assertRaises(ValueError):self.f.verify()
    def test_rehashed_wrong_model_stamp(self):
        self.replace_row(dict(k='synthetic',m='b'*16))
        with self.assertRaisesRegex(ValueError,'row stamp'):self.f.verify()

    def replace_row(self,row):
        old=self.f.outputs[0]; ref=self.f.raw(old['path'],(json.dumps(row)+'\n').encode());ref['rows']=1
        self.f.outputs[0]=ref
        m=self.f.docs['unit_manifest'];rel=str(Path(ref['path']).relative_to(W.ROOT/'results'))
        m['files'][rel]=dict(sha256=ref['sha256'],rows=1);self.f.put('unit_manifest',m);self.f.refresh()

    def test_rehashed_partial_result(self):
        self.replace_row(dict(k='synthetic',m=self.f.model_sha[:16]))
        old=self.f.outputs[0];raw=self.f.mapping[old['path']].read_bytes()[:-1]
        ref=self.f.raw(old['path'],raw);ref['rows']=1;self.f.outputs[0]=ref
        m=self.f.docs['unit_manifest'];rel=str(Path(ref['path']).relative_to(W.ROOT/'results'))
        m['files'][rel]=dict(sha256=ref['sha256'],rows=1);self.f.put('unit_manifest',m);self.f.refresh()
        with self.assertRaisesRegex(ValueError,'partial/oversize result row'):self.f.verify()

    def test_duplicate_role_key_rehashed(self):
        for i,r in enumerate(self.f.outputs):
            if '/trackt/' not in r['path']:continue
            ref=self.f.raw(r['path'],(json.dumps(dict(k='duplicate',m=self.f.model_sha[:16]))+'\n').encode())
            ref['rows']=1;self.f.outputs[i]=ref
            rel=str(Path(ref['path']).relative_to(W.ROOT/'results'))
            self.f.docs['unit_manifest']['files'][rel]=dict(sha256=ref['sha256'],rows=1)
        self.f.put('unit_manifest',self.f.docs['unit_manifest']);self.f.refresh()
        with self.assertRaisesRegex(ValueError,'duplicate role/key'):self.f.verify()

    def test_source_closure_missing(self):
        self.f.sources.pop();self.f.refresh()
        with self.assertRaisesRegex(ValueError,'source closure'):self.f.verify()

    def test_unrelated_chip_change_between_claim_release_allowed(self):
        d=self.f.docs['release']
        for side in ('before','after'):
            ledger=d['allocation_'+side]
            next(e for e in ledger['allocation'] if e['chip']==0)['purpose']='another owner updated its purpose'
            d['allocation_'+side+'_sha256']=W.digest(W.ledger_bytes(ledger))
        self.f.put('release',d);self.f.refresh();self.f.verify()

    def test_rehashed_owner_transition(self):
        d=self.f.docs['release'];ledger=d['allocation_before']
        next(e for e in ledger['allocation'] if e['chip']==3)['run']='other/run'
        d['allocation_before_sha256']=W.digest(W.ledger_bytes(ledger))
        self.f.put('release',d);self.f.refresh()
        with self.assertRaisesRegex(ValueError,'ownership continuity'):self.f.verify()

    def test_terminal_copies_both_rehashed_wrong_attempt(self):
        for key in ('attempt_terminal','root_terminal'):
            d=self.f.docs[key];d['attempt']=True;self.f.put(key,d)
        self.f.refresh()
        with self.assertRaisesRegex(ValueError,'terminal:attempt'):self.f.verify()

    def test_both_terminal_pins_rehashed_null_wrong_matching(self):
        for pin in (None,'b'*64,W.EXECUTION):
            for key in ('attempt_terminal','root_terminal'):
                d=self.f.docs[key];d['plan_sha256']=pin;self.f.put(key,d)
            self.f.refresh()
            with self.assertRaisesRegex(ValueError,'legacy branch forbids'):self.f.verify()

    def test_missing_data_identity(self):
        self.reject('scoring_receipt',lambda d:d['header']['data_files'].pop(next(iter(d['header']['data_files']))))

    def test_partial_metadata(self):
        self.f.mapping[self.f.refs['release']['path']].write_bytes(b'{')
        with self.assertRaises(ValueError):self.f.verify()
    def test_each_missing_artifact(self):
        for key in W.FIXED:
            with self.subTest(key=key):
                path=self.f.mapping[self.f.refs[key]['path']]; raw=path.read_bytes(); path.unlink()
                with self.assertRaises(OSError):self.f.verify()
                path.write_bytes(raw)
    def test_json_duplicate_and_nonfinite(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}'):
            with self.assertRaises(ValueError):W.parse(raw)
    def test_bounded_json(self):
        p=Path(self.temp.name)/'large.json';p.write_bytes(b' '*(W.MAX_JSON+1))
        with self.assertRaises(ValueError):W.Checked().doc(reference(p))
    def test_symlink_and_traversal(self):
        p=Path(self.temp.name)/'link';p.symlink_to(self.f.mapping[self.f.refs['request']['path']])
        with self.assertRaises(ValueError):W.opened(str(p))
        with self.assertRaises(ValueError):W.safe('/tmp/a/../b')
    def test_original_pin_survives_path_replacement(self):
        p=Path(self.temp.name)/'snapshot.json';p.write_text('{"value":1}');ref=reference(p);checked=W.Checked()
        self.assertEqual(checked.doc(ref),{'value':1});p.write_text('{"value":2}')
        self.assertEqual(checked.doc(ref),{'value':1});self.assertEqual(checked.refs[str(p)],ref)
        with self.assertRaises(ValueError):W.Checked().doc(ref)
    def test_probe_explicit_legacy_integration(self):
        probe_path=Path(__file__).with_name('r3_k2_retained_tensor_probe.py')
        scope={'__name__':'probe_integration','__file__':str(probe_path)}
        exec(compile(probe_path.read_bytes(),str(probe_path),'exec'),scope)
        root=Path(self.temp.name)/'k2_retained_tensor_20261101_v3'
        request_path=str(root.with_name('k2_completion_witness_20261101_v3')/'request.json')
        self.f.refs['request']=self.f.raw(request_path,self.f.mapping[self.f.refs['request']['path']].read_bytes())
        a=dict(schema='k2-retained-parent-activation-v1',plan_sha256=PLAN,authorized_by='parent',allow_npu=True,
               test_read=False,no_TEST=True,independent_prepared_review_passed=True,automatic_rerun=False,
               review_path=str(Path(self.temp.name)/'review.json'),review_sha256='b'*64,
               predecessor_route='authenticated-legacy-completion-v1',completion_request=self.f.refs['request'])
        helper=str(root/'tools/r3_k2_completion_witness.py')
        def read(path,pin):
            if Path(path).name=='plan.json':return {'evidence':{helper:self.f.verifier['sha256']}},PLAN
            return dict(plan_sha256=PLAN,prepared_accepted=True,reviewer='independent'),pin
        # Only activation/review loading and helper module construction are mocked.
        # The actual new guard calls the actual full verifier on synthetic chain bytes.
        scope.update(load=lambda path:a,checked_json=read,source=lambda *args:W)
        with patch.object(W,'opened',self.f.opened),patch.object(W.os,'walk',self.f.walk):
            result=scope['activation_guard'](root,PLAN)
            self.assertEqual(result['_completion_checked']['results']['files'],32)
            self.f.mapping[self.f.refs['release']['path']].unlink()
            with self.assertRaises(OSError):scope['activation_guard'](root,PLAN)
        a['predecessor_route']='invented'
        with self.assertRaisesRegex(ValueError,'unknown predecessor route'):scope['activation_guard'](root,PLAN)

    def test_preparation_request_refused(self):
        d=self.f.docs['request'];d['ready']=False;self.f.put('request',d)
        with self.assertRaisesRegex(ValueError,'preparation only'):self.f.verify()


if __name__=='__main__':unittest.main()
