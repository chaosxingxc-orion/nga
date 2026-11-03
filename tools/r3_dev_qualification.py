#!/usr/bin/env python3
"""Offline, externally adjudicated DEV qualification. Never grants adoption or TEST.

The caller supplies independent pins for the bundle and adjudication. Hashes bind
bytes, not history: the adjudication is the explicit external trust boundary for
review origin and actual observation origin. Producers must not author it.
"""
import argparse
import ast
import copy
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types

LEGACY = Path('/home/xingchao/workspace/nga/.local/preparations/formal-qualification-consumer-20261101-v3')
LEGACY_SHA = '8a58f535d3b725c07f1c8ced475953a468e762aabd5fcac7d2df0f5d15becf47'
BRIDGE = LEGACY.parent / 'formal-qualification-newwave-v2/consumer.py'
BRIDGE_SHA = '5c9fd8cf31c4ac824bc2c379ecb36d8e56ab158c5b5b084a649896bd05dbfc00'
SOURCE_ADMISSION_SHA = '0d09a8926958ffb05da08ba1bc72f452a97e7e0b4db621efbb021b32cf553887'
ASTRA_SOURCE_SHA = '3b22f4f9d0c659531575f3dd4d9c391bccf35193c5ec56df43ee3f8cce786ab7'
ROLE_SHA = '0c540fe50f8081061be535cc852d70072311ddcc8db0fe948a87ddf198a9d67a'
ROLES = ('primary_s2', 'primary_s3', 'samechip_s2', 'diffchip_s2')
CONTROLS = {'qo_s2': ('K1-QO', 2), 'pt_s2': ('K1-PT', 2), 'pt_s3': ('K1-PT', 3)}
BASE = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'
INSTRUCT = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def module(path, pin):
    data = Path(path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == pin, 'implementation pin differs: '+str(path))
    obj = types.ModuleType(Path(path).stem); obj.__file__ = str(path)
    exec(compile(data, str(path), 'exec', dont_inherit=True), obj.__dict__)
    return obj


# Prospective v6 compatibility: exact reviewed pairs only. The report still
# executes the old strict, whole-population provenance consumer.
SOURCE_COMPATIBILITY = {
    'provenance_r3': ('5eb8da079f0af3d04ca1c3172258c29320490b0b53d7800f2331b2f5735a8cd2',
                      'b87c7f42ff39eca3bd5d92a14c3ddffdb8a4a92ee28cd5e736328392d97877c9'),
    'testlock_r3': ('eed0662f925c154c90036679945ea74b9083043b8da1b545df3e85b89b54cffc',
                    '9b9b85220c493ee301c9bcdb7fd74d036e8cb1ed442500923f9ac41a3698cbba'),
}
K0_HELPER_SHA = '24f45b298f53d07df3e20c76e97ca2ce88c6e6736e5043bbca8a887d48cba771'
K0_EVIDENCE_SHA = 'fc4f3ecb75850761c3fcb87b3e5c0ed2bccba3d1a94b3889e12dc848e3135fa7'
K0_CONFIG = LEGACY.parent/'production-dev-qualification-20261103-v5/CONFIG.json'
K0_CAPTURES = LEGACY.parent/'member-runtime-capture-20261103-v1'
K0_EXECUTIONS = {
    'fcfe5b4bde340497712ea79a045b02ddac1270b0f19c9d9eb623c46ab660c2df': 'k0_base',
    '4261e76402ff9b61fee41c98067fcecdaddb7af9a2b28964ea6d2a2203b2441b': 'k0_instruct',
}


def compatible_source(name, consumer, producer):
    return producer == consumer or SOURCE_COMPATIBILITY.get(name) == (consumer, producer)


def legacy():
    q = module(LEGACY/'consumer.py', LEGACY_SHA)
    q.evaluation_lineage = evaluation_lineage
    # Modify precisely the reviewed equality predicate in a verified original
    # function; neither the legacy files nor its strict provenance are changed.
    raw = (LEGACY/'consumer.py').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == LEGACY_SHA, 'legacy report source changed')
    source = raw.decode()
    old = "producer_names[name]['sha256']==e['sha256']"
    require(source.count(old) == 1, 'legacy source compatibility site differs')
    source = source.replace(old, "compatible_source(name,e['sha256'],producer_names[name]['sha256'])")
    node = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == 'report')
    q.compatible_source = compatible_source
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(LEGACY/'consumer.py'), 'exec'), q.__dict__)
    return q


def k0_ownership(execution, claim, release, claim_pin, release_path, actual, files, execution_pin):
    name = K0_EXECUTIONS.get(execution_pin)
    require(name is not None, 'unsupported legacy K0 execution')
    directory = Path(__file__).resolve().parent
    ep, hp = directory/'r3_k0_legacy_release_evidence.py', directory/'r3_k0_legacy_release_compat.py'
    require(files.get(str(ep)) == K0_EVIDENCE_SHA and files.get(str(hp)) == K0_HELPER_SHA,
            'K0 compatibility sources unbound')
    evidence = module(ep, K0_EVIDENCE_SHA)
    raw = hp.read_bytes(); require(hashlib.sha256(raw).hexdigest() == K0_HELPER_SHA, 'K0 helper changed')
    tree = ast.parse(raw)
    imports = [x for x in tree.body if isinstance(x, ast.ImportFrom) and x.module == 'tools']
    require(len(imports) == 1 and len(imports[0].names) == 1
            and imports[0].names[0].name == 'r3_k0_legacy_release_evidence'
            and imports[0].names[0].asname == 'E', 'K0 evidence import differs')
    tree.body.remove(imports[0])
    ns = {'__name__': 'pinned_k0_compatibility', '__file__': str(hp), 'E': evidence}
    exec(compile(tree, str(hp), 'exec'), ns)
    result = ns['verify'](K0_CONFIG, K0_CAPTURES/name/'CAPTURE.json', name,
        execution=execution, claim=claim, release=release, claim_pin=claim_pin,
        release_path=release_path, actual=actual)
    return result['timing']


def actual_arm(plan):
    cmd = plan.get('command')
    require(isinstance(cmd, list) and all(isinstance(x, str) for x in cmd)
            and cmd[:3] == ['python3', '-P', '/workspace/train_r3.py'], 'producer training command differs')
    flags = [i for i, x in enumerate(cmd) if x.startswith('--ar')]
    require(len(flags) == 1 and cmd[flags[0]] == '--arm' and flags[0]+1 < len(cmd), 'ambiguous training arm')
    arm = cmd[flags[0]+1]
    require(arm in ('k1', 'k2') and plan.get('arm', arm) == arm, 'training objective differs')
    return arm


def label(plan):
    arm = actual_arm(plan); control = plan.get('control_arm')
    if control is None:
        require('--drop-state' not in plan['command'] and plan['model'] == BASE, 'unlabelled control')
        return arm.upper()
    require(arm == 'k1' and control in ('K1-QO', 'K1-PT'), 'control objective differs')
    c = plan.get('control', {}); e = plan['evaluation']
    seeds = [2] if control == 'K1-QO' else [2, 3]
    mode = 'drop' if control == 'K1-QO' else 'full'
    require(type(plan['seed']) is int and plan['seed'] in seeds, 'control seed differs')
    require(plan['model'] == (BASE if control == 'K1-QO' else INSTRUCT), 'control checkpoint differs')
    require(plan['command'].count('--drop-state') == (1 if control == 'K1-QO' else 0), 'control input state differs')
    for value in (c, e):
        require(value.get('control_arm') == control and value.get('candidate_for_adoption') is False
                and value.get('primary_input_mode') == mode and value.get('registered_seeds') == seeds, 'control role contract differs')
    return control


def training_lineage(entry, rep, bundle, api):
    """Bind control arguments to the pinned producer plan, retaining legacy checks.

    The legacy validator caller predates controls. Give that call a private API
    view; do not mutate a shared validator or rewrite any frozen evidence.
    """
    plan = api.Q.bound(entry['plan'], bundle['files'])
    identity = label(plan)
    require(entry.get('arm') == identity, 'training member control identity differs')
    control = plan.get('control_arm')
    mode = 'drop' if control == 'K1-QO' else 'full'
    if control is None:
        require(not plan.get('control') and
                plan.get('evaluation', {}).get('control_arm') is None and
                plan.get('evaluation', {}).get('primary_input_mode', 'full') == 'full',
                'unlabelled training control metadata')
    for key, expected in (('control_arm', control), ('input_mode', mode),
                          ('primary_input_mode', mode)):
        for source in (entry, plan):
            require(key not in source or source[key] == expected,
                    'training control argument differs: '+key)
    expected_args = (plan['training_evidence'], plan['training_evidence_sha256'],
                     plan['code'], plan['model'], plan['train_file'], plan['image_sha256'])
    def validate(*args, **kwargs):
        require(args == expected_args and not kwargs, 'legacy training call differs')
        return api.training.validate(*args, control_arm=control, input_mode=mode)
    scoped = copy.copy(api)
    scoped.training = types.SimpleNamespace(validate=validate)
    return api.Q.training_lineage(dict(entry, arm=actual_arm(plan).upper()),
                                  rep, bundle, scoped)


def evaluation_lineage(entry, bundle, api):
    """Same legacy checks, with explicit semantic-control/actual objective binding."""
    q = api.Q; files = bundle['files']; execution = q.bound(entry['execution'], files)
    require(execution.get('schema') == 'r3-engineering-posttrain-execution-v1'
            and execution.get('test_read') is False and execution.get('scientific_acceptance') is False, 'evaluation execution scope differs')
    spec = q.bound(execution['spec'], files)
    require(files[execution['spec']] == execution['spec_sha256'] and spec['evaluation_profile'] == 'track_kt', 'evaluation specification differs')
    require(Path(entry['report']).parent == Path(execution['out'])/'results'
            and spec['model'] == entry['model']['base_path'], 'evaluation generation/model differs')
    if entry['arm'] != 'K0':
        p = q.bound(entry['plan'], files); root = Path(p['out'])
        m = q.bound(root/'manifest.json', files); end = q.bound(root/'TRAIN_EXIT.json', files)
        require(entry['plan'] == str(root/'plan.json') and spec['training'] == str(root)
                and spec['adapter'] == str(root/'adapter') == entry['model']['path'], 'evaluation adapter lineage differs')
        v = spec['training_variant']
        require(all(type(x) is int for x in (entry['seed'], v['seed'], p['seed'], m['args']['seed']))
                and entry['seed'] == v['seed'] == p['seed'] == m['args']['seed'], 'evaluation seed differs')
        require(v['training_plan_sha256'] == files[entry['plan']]
                and v['arm'].upper() == entry['arm'] == label(p)
                and m['arm'] == m['args']['arm'] == actual_arm(p), 'evaluation objective/control differs')
        require(v['k2_impl'] == p.get('k2_impl', 'rows') == m['args'].get('k2_impl', 'rows'), 'implementation differs')
        require(spec['model'] == p['model'] == m['model_path']
                and type(m['total_steps']) is int and m['total_steps'] == 3116
                and type(m['summary']['final_step']) is int and m['summary']['final_step'] == 3116, 'training completion differs')
        q.exact(spec['training_exit'], end, 'training terminal differs')
        q.exact(api.deps[1].training_variant(m), entry['training_variant'], 'recipe differs')
    for group in (spec['files'], execution['tools']):
        for path, pin in group.items():
            require(files.get(path) == pin, 'evaluation dependency unbound')
    api.evaluation.verify_spec(spec, Path(execution['out']))
    return spec


def source_api():
    q = legacy(); api = q.source_modules(); api.Q = q
    # The frozen evaluator demands a non-existent top-level arm on formal controls.
    # Re-run its unchanged control validator with an in-memory view containing the
    # objective already parsed and checked from the exact producer command.
    old = api.evaluation.verify_control_manifest
    def controls(spec):
        if api.evaluation.is_baseline(spec):
            return old(spec)
        path = str(Path(spec['training'])/'plan.json')
        p = api.evaluation.load(path)
        if p.get('control_arm') is None:
            return old(spec)
        require(label(p) == spec['training_variant']['arm'].upper(), 'control semantic arm differs')
        original_load = api.evaluation.load
        try:
            api.evaluation.load = lambda target: dict(p, arm=actual_arm(p)) if str(target) == path else original_load(target)
            return old(spec)
        finally:
            api.evaluation.load = original_load
    api.evaluation.verify_control_manifest = controls
    return api


def refdoc(ref, files, q):
    if ref is None:
        raise FileNotFoundError('required evidence reference absent')
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}
            and files.get(ref['path']) == ref['sha256'], 'unbound evidence reference')
    return q.bound(ref['path'], files)


def moment(value):
    require(isinstance(value, str), 'timestamp required')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'timezone missing')
    return parsed.timestamp()


def ledger_digest(doc):
    return hashlib.sha256((json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()).hexdigest()


def ledger(doc):
    require(isinstance(doc, dict) and isinstance(doc.get('allocation'), list) and isinstance(doc.get('free'), list), 'ledger shape differs')
    chips = [x.get('chip') for k in ('allocation', 'free') for x in doc[k]]
    require(all(type(x) is int and 0 <= x < 8 for x in chips) and len(set(chips)) == len(chips), 'ledger chip identity differs')


def ownership(plan, claim, release, claim_pin, release_path, actual):
    """Validate whole transitions; unrelated chips may change between claim/release."""
    chip = plan['chip']; run = plan['run']; state = actual['State']
    require(claim.get('schema') == 'r3-resource-claim-v1' and release.get('schema') == 'r3-resource-release-v1', 'resource receipt schema differs')
    require(claim.get('run') == release.get('run') == run and type(claim.get('chip')) is int
            and claim['chip'] == release.get('chip') == chip and claim.get('allocation') == plan['allocation'], 'resource identity differs')
    require(release.get('claim_sha256') == claim_pin and release.get('container_id') == actual['Id']
            and '/'+release.get('container', '') == actual['Name'], 'claim/release generation differs')
    require(type(release.get('exit_code')) is int and release['exit_code'] == 0
            and release.get('scientific_acceptance') is False, 'release failed or mis-scoped')
    require(release.get('container_started_at') == state['StartedAt']
            and release.get('container_finished_at') == state['FinishedAt'], 'release time differs')
    for rec in (claim, release):
        for side in ('before', 'after'):
            doc = rec['allocation_'+side]; ledger(doc)
            require(rec['allocation_'+side+'_sha256'] == ledger_digest(doc), 'ledger digest differs')
    before, after = claim['allocation_before'], claim['allocation_after']; entry = claim['entry']
    require(entry.get('run') == run and type(entry.get('chip')) is int and entry['chip'] == chip
            and entry.get('claimed_utc') == claim.get('claimed_utc'), 'claim owner differs')
    require(sum(x['chip'] == chip for x in before['free']) == 1 and not any(x['chip'] == chip for x in before['allocation']), 'claim chip not free')
    expected = dict(before, allocation=sorted(before['allocation']+[entry], key=lambda x:x['chip']),
                    free=[x for x in before['free'] if x['chip'] != chip],
                    updated_utc=after.get('updated_utc'), updated_by='r3_resource_adapter claim')
    require(canonical(expected) == canonical(after), 'claim transition differs')
    before, after = release['allocation_before'], release['allocation_after']
    require(canonical([x for x in before['allocation'] if x['chip'] == chip]) == canonical([entry])
            and not any(x['chip'] == chip for x in before['free']), 'released owner differs')
    free = [x for x in after['free'] if x['chip'] == chip]
    require(len(free) == 1 and free[0].get('previous_run') == run
            and free[0].get('release_evidence') == str(release_path), 'release free entry differs')
    expected = dict(before, allocation=[x for x in before['allocation'] if x['chip'] != chip],
                    free=sorted(before['free']+free, key=lambda x:x['chip']), updated_utc=after.get('updated_utc'),
                    updated_by='r3_resource_adapter release')
    require(canonical(expected) == canonical(after), 'release transition differs')
    require(moment(claim['claimed_utc']) <= moment(state['StartedAt']) <= moment(state['FinishedAt'])
            <= moment(release['released_utc']) and moment(free[0]['released_utc']) >= moment(state['FinishedAt']), 'resource chronology differs')
    return {'start': moment(state['StartedAt']), 'finish': moment(state['FinishedAt']), 'release': moment(release['released_utc']), 'container_id': actual['Id'], 'chip': chip}


def entries(bundle):
    required = set(ROLES) | set(CONTROLS) | {'k0_base', 'k0_instruct'}
    if bundle.get('branch') == 'replacement':
        required |= {'candidate_s2','candidate_s3'}
    supplied = bundle.get('entries', {})
    require(isinstance(supplied, dict) and not (set(supplied)-required), 'unknown campaign member')
    missing = sorted(required-set(supplied))
    if missing:
        raise FileNotFoundError('missing campaign members: '+', '.join(missing))
    require(len({e['report'] for e in supplied.values()}) == len(supplied), 'report aliases campaign members')
    expected = {r: ('K1', 3 if r == 'primary_s3' else 2) for r in ROLES}
    expected.update(CONTROLS)
    expected.update({'candidate_s2':('K2',2),'candidate_s3':('K2',3)})
    for name, e in supplied.items():
        if name.startswith('k0_'):
            require(e['arm'] == 'K0' and 'seed' not in e and 'plan' not in e, 'K0 must be untuned and unseeded')
        else:
            require((e['arm'], e['seed']) == expected[name] and type(e['seed']) is int, 'arm/seed membership differs: '+name)
    trained = [e for k,e in supplied.items() if not k.startswith('k0_')]
    require(len({e['plan'] for e in trained}) == len(trained)
            and len({e['model']['path'] for e in trained}) == len(trained), 'primary/control/auxiliary alias')
    return supplied


def admitted_root(bundle, adjudication, bundle_pin, api):
    q = api.Q
    require(bundle.get('schema') == 'r3-production-dev-bundle-v1' and bundle.get('branch') in ('firstK1','replacement')
            and bundle.get('test_read') is False, 'registered firstK1 or replacement branch required')
    if adjudication is None:
        raise FileNotFoundError('independent campaign adjudication has not been issued')
    require(adjudication.get('schema') == 'r3-independent-dev-adjudication-v1'
            and adjudication.get('bundle_sha256') == bundle_pin
            and adjudication.get('test_read') is False and adjudication.get('scientific_acceptance') is False
            and adjudication.get('authenticator_identity') and adjudication.get('origin') == 'independent-parent-adjudication', 'external adjudication binding differs')
    require(not any(k in d for d in (bundle, adjudication) for k in ('final_ticket', 'test_logger', 'test_authority', 'override')), 'TEST/override authority forbidden')
    require('replacement_floor_carry' not in adjudication, 'unregistered carrier mapping authority forbidden')
    require(adjudication.get('source_applicability_sha256') == SOURCE_ADMISSION_SHA, 'R0 applicability not accepted')
    return {'origin_authentication': 'externally pinned caller adjudication; not inferred from producer hashes', 'branch': bundle['branch']}


def admitted_r0(bundle, api):
    q = api.Q; files = bundle['files']; ref = bundle.get('source_applicability')
    doc = refdoc(ref, files, q)
    require(ref['sha256'] == SOURCE_ADMISSION_SHA and doc['schema'] == 'r3-prospective-source-applicability-v1'
            and doc['review']['sha256'] == ASTRA_SOURCE_SHA and doc['test_read'] is False, 'unreviewed/rehashed source applicability')
    review = refdoc(doc['review'], files, q); parent = refdoc(doc['parent_dispatch_receipt'], files, q)
    require(review['r0_source_admission']['verdict'] == 'ACCEPT_EXACT_RECONSTRUCTION_AS_REUSABLE_SOURCE_EVIDENCE'
            and parent['requested_model'] == 'gpt-6-astra' and parent['completion_received_by_parent'] is True, 'actual source review binding differs')
    r = doc['r0']; require(r['source_inventory_items'] == 225 and r['rows_per_role'] == 102654
            and r['retain_suspicious_entries'] == 28 and r['retain_void_populations'] is True, 'R0 preservation contract differs')
    # Reuse the old exact numerical bridge, including all 225 input checks and full
    # Track T equality; the new independent ruling changes applicability only.
    bridge = module(BRIDGE, BRIDGE_SHA)
    oldreview = BRIDGE.parent/'ADMITTED-R0-REVIEW.json'
    require(files.get(str(oldreview)) == bridge.R0_REVIEW_SHA, 'old numerical review missing')
    old_bundle = dict(bundle, _wave_authority={'r0_bridge_admission': {'path': str(oldreview), 'sha256': bridge.R0_REVIEW_SHA}, 'r0_bridge_artifacts': r['artifacts']})
    gate = bridge.scoped_r0_gate(old_bundle, api)
    q.exact(gate['statuses'], r['statuses'], 'R0 void statuses changed')
    suspicious = str(Path(r['artifacts']['request']['path']).parent/'SUSPICIOUS_CELLS.json')
    value = q.bound(suspicious, files)
    require(files[suspicious] == review['reverified_evidence_hashes'][suspicious] and isinstance(value,list) and len(value)==28, 'suspicious evidence changed')
    return dict(gate, source_applicability_sha256=ref['sha256'],
                scope='independently admitted exact R0 source dependency only',
                suspicious_evidence={'path':suspicious,'sha256':files[suspicious],'retained':28},
                qualification_admission=True, candidate_eligibility_granted=False)


COLLAB_REVIEW_POLICY = 'requested-astra-collaboration-parent-pinned-v2'
REVIEW_SCOPE = 'exact-formal-train-only-readiness-no-activation'

# Read-bound equivalent of r3_formal_train_successor.py at
# fcbc3fc6b196c07bc0fd47a8566820ac7ef35005852cd230095b568d2b277f7d.
def verify_collaboration_review(p, pin, review, files, q):
    """Parent-observed tool transport, not an OS exit or provider attestation.

    The plan pins parent/producer identities before review. The external parent
    authenticates the observation receipt and actual tool events; self-consistent
    hashes alone cannot establish who wrote any of these artifacts.
    """
    from datetime import datetime
    authority=p.get('review_authority',{})
    parent=authority.get('parent_agent_id');producer=authority.get('producer_agent_id')
    agent=review.get('reviewer_agent_id')
    require(isinstance(parent,str) and parent and isinstance(producer,str) and producer
            and parent!=producer and isinstance(agent,str) and agent
            and agent not in (parent,producer), 'collaboration authority separation differs')
    require(review.get('schema')==COLLAB_REVIEW_POLICY and review.get('scope')==REVIEW_SCOPE
            and review.get('requested_model')=='gpt-6-astra'
            and review.get('authenticator_identity')==parent
            and review.get('backend_runtime_attestation') is False
            and review.get('os_process_exit_attested') is False
            and review.get('activation_authorized') is False
            and 'worker_exit_code' not in review and 'worker_terminal' not in review,
            'collaboration review transport differs')
    protected=Path(p['formal_schedule']).parent if p.get('formal_schedule') else Path(p['out'])
    def artifact(ref):
        require(isinstance(ref,dict) and set(ref)=={'path','sha256'},'collaboration artifact ref differs')
        path=Path(ref['path'])
        require(not path.is_relative_to(protected) and not path.is_relative_to(Path(p['out'])),
                'parent/reviewer evidence inside producer generation')
        return refdoc(ref, files, q)
    def timestamp(value):
        require(isinstance(value,str),'collaboration timestamp missing')
        try: result=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError: raise RuntimeError('collaboration timestamp malformed')
        require(result.tzinfo is not None,'collaboration timestamp must include timezone')
        return result
    observation=artifact(review.get('parent_observation'))
    require(observation.get('schema')=='parent-observed-collaboration-review-v1'
            and observation.get('observer_agent_id')==parent
            and observation.get('producer_agent_id')==producer
            and observation.get('reviewer_agent_id')==agent
            and observation.get('status')=='completed' and observation.get('scope')==REVIEW_SCOPE
            and observation.get('backend_runtime_attestation') is False
            and observation.get('os_process_exit_attested') is False
            and observation.get('activation_authorized') is False,
            'collaboration parent observation differs')
    dispatch=artifact(observation.get('original_dispatch'))
    task=artifact(observation.get('review_task'))
    completion=artifact(observation.get('completion'))
    report=artifact(review.get('review_report'));result=artifact(review.get('worker_result'))
    require(dispatch.get('schema')=='parent-observed-collaboration-dispatch-v1'
            and dispatch.get('tool')=='collaboration.spawn_agent'
            and dispatch.get('observer_agent_id')==parent and dispatch.get('agent_id')==agent
            and dispatch.get('requested_model')=='gpt-6-astra'
            and dispatch.get('model_override_explicit') is True,
            'original explicit model dispatch lineage differs')
    require(task.get('schema')=='parent-observed-collaboration-task-v1'
            and task.get('tool') in ('collaboration.spawn_agent','collaboration.followup_task')
            and task.get('observer_agent_id')==parent and task.get('agent_id')==agent
            and task.get('scope')==REVIEW_SCOPE
            and task.get('original_dispatch')==observation['original_dispatch'],
            'exact review task lineage differs')
    require(completion.get('schema')=='parent-observed-collaboration-completion-v1'
            and completion.get('observer_agent_id')==parent and completion.get('agent_id')==agent
            and completion.get('status')=='completed' and completion.get('scope')==REVIEW_SCOPE
            and completion.get('review_task')==observation['review_task']
            and completion.get('review_report')==observation.get('review_report')==review['review_report']
            and completion.get('worker_result')==observation.get('worker_result')==review['worker_result'],
            'collaboration completion/result binding differs')
    prepared_ref=review.get('prepared_queue')
    require(task.get('prepared_queue')==observation.get('prepared_queue')==prepared_ref,
            'collaboration prepared input differs')
    prepared=refdoc(prepared_ref, files, q)
    require(prepared.get('controller')==p['successor_guard']['controller'],'review queue controller differs')
    jobs=prepared.get('jobs',[])
    require(jobs and len({j['plan'] for j in jobs})==len(jobs),'prepared plan inventory differs')
    expected=[dict(path=j['plan'],canonical_sha256=j['plan_sha256'],prepared_raw_sha256=j['plan_raw_sha256']) for j in jobs]
    require(all(x['canonical_sha256']==x['prepared_raw_sha256'] for x in expected)
            and dict(path=str(Path(p['out'])/'plan.json'),canonical_sha256=pin,prepared_raw_sha256=pin) in expected
            and task.get('plans')==observation.get('plans')==review.get('plans')==expected,
            'collaboration exact plan pins differ')
    require(report.get('verdict')=='PASS' and report.get('scope')==REVIEW_SCOPE
            and report.get('reviewer_agent_id')==agent
            and report.get('prepared_queue')==prepared_ref
            and report.get('approved_canonical_plan_sha256')==[x['canonical_sha256'] for x in expected]
            and result.get('schema')=='parent-observed-collaboration-result-v1'
            and result.get('observer_agent_id')==parent and result.get('agent_id')==agent
            and result.get('scope')==REVIEW_SCOPE and result.get('review_report')==review['review_report']
            and isinstance(result.get('returned_text'),str) and result['returned_text'],
            'independent collaboration PASS/result differs')
    times=[timestamp(dispatch.get('observed_at')),timestamp(task.get('observed_at')),
           timestamp(report.get('created_utc')),timestamp(completion.get('observed_at')),
           timestamp(observation.get('observed_at')),timestamp(review.get('authenticated_at'))]
    require(times==sorted(times) and timestamp(result.get('observed_at'))<=times[4]
            and timestamp(result.get('observed_at'))>=times[2], 'collaboration chronology differs')

    return times[-1].timestamp(), observation


def verify_control_review(entry, plan, pin, review, report, decision, files, q):
    """Consume original control receipts, never fabricate v2 events.

    Control plans predate v2 authority fields, so the external adjudicator
    explicitly names parent and producer; the original receipt binds reviewer.
    """
    receipt = refdoc(decision['dispatch_receipt'], files, q)
    original_path = receipt.get('original_dispatch_receipt')
    require(isinstance(original_path, str), 'original control dispatch reference missing')
    original = q.bound(original_path, files)
    agent = review.get('reviewer_agent')
    parent = decision.get('authenticator_identity'); producer = decision.get('producer_agent_id')
    require(all(isinstance(x, str) and x for x in (parent, producer, agent))
            and len({parent, producer, agent}) == 3, 'control authority separation differs')
    require(review.get('verdict') == 'PASS' and review.get('approved_plan_sha256') == pin
            and review.get('reviewer_model') == 'gpt-6-astra'
            and review.get('scope') == 'exact-prospective-control-train-only'
            and review.get('control_arm') == label(plan) and review.get('seed') == plan['seed']
            and review.get('chip') == plan['chip'] and review.get('attempts') == [1]
            and review.get('activation_authorized') is False and review.get('scientific_acceptance') is False
            and review.get('test_read') is False and review.get('backend_runtime_attestation') is False,
            'exact control review differs')
    require(receipt.get('schema') == original.get('schema') == 'parent-observed-collaboration-review-receipt-v1'
            and receipt.get('agent') == original.get('agent') == agent
            and receipt.get('requested_model') == original.get('requested_model') == 'gpt-6-astra'
            and original.get('dispatch_tool') == 'collaboration.spawn_agent'
            and original.get('dispatch_observed_by_parent') is True
            and receipt.get('completion_received_by_parent') is True
            and all(x.get('backend_runtime_attestation') is False
                    and x.get('os_process_exit_attested') is False for x in (receipt, original))
            and receipt.get('activation_authorized') is False, 'control dispatch lineage differs')
    refs = list(receipt.get('reports', {}).values())
    require(decision['review_report'] in refs
            and any(x.get('sha256') == plan['review_sha256'] for x in refs), 'control receipt not bound to reports')
    require(report.get('schema') == 'astra-formal-controls-exact-review-v1'
            and report.get('verdict') == receipt.get('actual_returned_verdict') == 'PASS_EXACT_TRAIN_ONLY_PRELAUNCH_REVIEW'
            and report.get('reviewer_agent') == agent and report.get('requested_model') == 'gpt-6-astra'
            and report.get('backend_runtime_attestation') is False and report.get('activation_authorized') is False,
            'returned control report differs')
    matches = [x for x in report.get('reviews', []) if x.get('plan_sha256') == pin]
    require(len(matches) == 1 and matches[0].get('sha256') == plan['review_sha256'], 'control report exact plan pin differs')
    returned = refdoc({k: matches[0][k] for k in ('path', 'sha256')}, files, q)
    q.exact(returned, review, 'returned control review differs')
    times = [moment(original.get('utc')), moment(report.get('created_utc')), moment(receipt.get('utc'))]
    reviewed = moment(decision.get('review_completed_utc'))
    require(times == sorted(times) and times[1] <= reviewed <= times[2], 'control review chronology differs')
    return times[-1]


def verify_prelaunch(name, entry, plan, decision, files, api):
    q = api.Q
    require(decision.get('decision') == 'ADMIT_EXACT_PROSPECTIVE_EXECUTION'
            and decision.get('plan_sha256') == files[entry['plan']]
            and decision.get('requested_model') == 'gpt-6-astra'
            and decision.get('review_origin_authenticated') is True
            and decision.get('observation_origin_authenticated') is True, 'independent runtime adjudication differs: '+name)
    review = q.bound(plan['review_path'], files)
    require(plan['review_sha256'] == files[plan['review_path']] == decision['review_sha256'], 'review pin differs')
    pin = hashlib.sha256((json.dumps(dict(plan, review_sha256='PENDING'), indent=2, sort_keys=True)+'\n').encode()).hexdigest()
    report = refdoc(decision['review_report'], files, q)
    if review.get('schema') == COLLAB_REVIEW_POLICY or plan.get('review_policy') == COLLAB_REVIEW_POLICY:
        require(plan.get('review_policy') == COLLAB_REVIEW_POLICY, 'collaboration plan policy differs')
        completed, observation = verify_collaboration_review(plan, pin, review, files, q)
        require(review['review_report'] == decision['review_report']
                and observation['original_dispatch'] == decision['dispatch_receipt'], 'adjudicated collaboration refs differ')
        reviewed = moment(decision['review_completed_utc'])
        require(moment(report['created_utc']) <= reviewed <= completed, 'review chronology differs')
        return completed
    if review.get('schema') == 'astra-formal-control-exact-review-v1':
        return verify_control_review(entry, plan, pin, review, report, decision, files, q)
    require(report.get('verdict') == 'PASS' and pin in report.get('approved_canonical_plan_sha256', []), 'exact independent PASS missing')
    dispatch = refdoc(decision['dispatch_receipt'], files, q)
    require(dispatch.get('requested_model') == 'gpt-6-astra' and dispatch.get('completion_received_by_parent') is True
            and dispatch.get('dispatch_observed_by_parent') is True
            and dispatch.get('backend_runtime_attestation') is False, 'authentic collaboration receipt missing')
    require(any(x.get('sha256') == decision['review_report']['sha256'] for x in dispatch.get('reports', {}).values()), 'dispatch not bound to review')
    if review.get('schema') == 'requested-astra-parent-pinned-v1':
        require(review.get('requested_model') == 'gpt-6-astra' and review.get('activation_authorized') is False
                and review.get('review_report') == decision['review_report']
                and any(x.get('canonical_sha256') == pin and x.get('path') == entry['plan'] for x in review.get('plans', [])), 'formal review envelope differs')
    else:
        require(review.get('approved_plan_sha256') == pin and review.get('verdict') == 'PASS', 'direct review differs')
    reviewed=moment(decision['review_completed_utc'])
    recorded=report.get('created_utc',report.get('utc'))
    require(recorded is not None and moment(recorded)<=reviewed, 'review chronology lacks actual report timestamp')
    require(moment(dispatch['utc'])>=moment(recorded), 'dispatch completion receipt predates review')
    return max(reviewed,moment(dispatch['utc']))


def role_bindings(bundle, supplied, api):
    q = api.Q; files = bundle['files']
    if bundle.get('schedule') is None or bundle.get('role_validator') is None:
        raise FileNotFoundError('formal schedule or role-validator reference missing')
    ref = bundle['role_validator']; require(ref['sha256'] == ROLE_SHA and files.get(ref['path']) == ROLE_SHA, 'unreviewed role validator')
    roles = module(ref['path'], ROLE_SHA); schedule = refdoc(bundle['schedule'], files, q)
    by = roles.validate_schedule(schedule)
    for role in ROLES:
        p = q.bound(supplied[role]['plan'], files)
        require(p.get('schema') == 'r3-formal-k1-plan-v1' and p['formal_role'] == role
                and p['formal_schedule'] == bundle['schedule']['path']
                and p['formal_schedule_sha256'] == bundle['schedule']['sha256']
                and label(p) == 'K1', 'formal role plan differs')
        roles.validate_plan(p)
    return by


def protocol(bundle, name, entry, api):
    header = copy.deepcopy(bundle['protocol_header'])
    header['primary_input_mode'] = 'drop' if name == 'qo_s2' else 'full'
    expected_base = INSTRUCT if name in ('pt_s2', 'pt_s3', 'k0_instruct') else BASE
    require(entry['model']['base_path'] == expected_base, 'entry checkpoint differs: '+name)
    if name.startswith('k0_'):
        require(entry['model']['path'] == expected_base and entry['model']['kind'] == 'checkpoint', 'K0 checkpoint identity differs')
    return dict(bundle, protocol_header=header)


def numerical(reports, gate, api, branch='firstK1'):
    """Registered first-K1 rules; no invented bootstrap or broad floor gate."""
    q=api.Q; primary=[reports[r] for r in ('primary_s2','primary_s3')]
    require(branch in ('firstK1','replacement'),'unknown numeric branch')
    cand=primary if branch=='firstK1' else [reports[r] for r in ('candidate_s2','candidate_s3')]
    repeats={k:reports[k+'_s2'] for k in ('samechip','diffchip')}
    result=q.numeric(branch,cand,reports['k0_base'],[] if branch=='firstK1' else primary,repeats,gate,api)
    active=[k for k,v in gate['statuses'].items() if v in ('pass','fail')]
    require(active, 'empty R0 gating population')
    for r in primary+list(repeats.values()):
        for kind in active:
            c=r['track_t']['selection']['typed-decisions'][kind]
            require(type(c['n_units']) is int and c['n_units']>0
                    and type(c['n_pairs_used']) is int and c['n_pairs_used']>0
                    and type(c['n_pairs_dropped_tie']) is int and c['n_pairs_dropped_tie']>=0, 'empty/invalid floor population')
    result['floors']=q.floor_diagnostics(primary[0],repeats,api.S,active)
    result['floor_policy']='Full samechip and diffchip evidence mandatory; no new threshold for first-K1. Only diffchip gates later registered replacement margins.'
    result.pop('broad_floor_applicability',None)
    qo=api.S._dev_acc(reports['qo_s2'],'transfer-v4')
    result['semantic_transfer_seal']={'reference':'SFT5.5','qo_accuracy':qo,
        'per_seed':{str(r['selection_evidence']['seed']):{'accuracy':api.S._dev_acc(r,'transfer-v4'),
        'gap':api.S._dev_acc(r,'transfer-v4')-qo,
        'semantic_transfer_claim':api.S._dev_acc(r,'transfer-v4')-qo>=.05-api.S.EPS} for r in cand},
        'changes_adoption_gate':False}
    result['control_metrics']={name:{s:api.S._dev_acc(reports[name],s) for s in q.SUITES} for name in CONTROLS}
    result['numeric_predicates_scope']='Registered K-floor, current-wave absolute lines, K0 guard and admitted R0 dependency; replacement additionally uses registered 8.2(a,b,c). Controls and both full floors validated separately.'
    result['floor_indeterminate']=False
    result['floor_qualification_indeterminate']=False
    if branch=='replacement':
        floor=result['replacement']
        outcomes=list(floor['floor_b'].values())+list(floor['floor_c'].values())
        require(outcomes,'replacement floor comparison empty')
        result['floor_indeterminate']='INDETERMINATE' in outcomes
        if 'FAIL' in outcomes:result['numeric_predicates_pass']=False
        carry = replacement_floor_carry(result)
        result['replacement']['floor_carry'] = carry
        result['floor_qualification_indeterminate'] = carry['status'] != 'PASS'
    return result


def replacement_floor_carry(result):
    """Report registered native overlays without inventing carrier authority.

    Section 14.10 item 8 permits a/c carry when b is indeterminate, but does
    not specify the combined-a/native-floor mapping. That unresolved case
    withholds eligibility. Ordinary all-PASS overlays need no extra rule.
    """
    replacement = result['replacement']
    comparison = result['development_comparison']['against_incumbent']
    b_indeterminate = [s for s,v in replacement['floor_b'].items() if v == 'INDETERMINATE']
    c_indeterminate = [c for c,v in replacement['floor_c'].items() if v == 'INDETERMINATE']
    outcomes = list(replacement['floor_b'].values()) + list(replacement['floor_c'].values())
    require(outcomes and set(outcomes) <= {'PASS','FAIL','INDETERMINATE'}, 'native floor outcome differs')
    status = 'FAIL' if 'FAIL' in outcomes else 'INDETERMINATE' if b_indeterminate or c_indeterminate else 'PASS'
    return {'status': status, 'indeterminate_b_suites': b_indeterminate,
            'indeterminate_c_cells': c_indeterminate,
            'carrier_mapping_status': 'UNRESOLVED' if b_indeterminate else 'NOT_REQUIRED',
            'carrier_mapping_authority': None,
            'combined_bootstrap_unchanged': comparison['combined'],
            'cross_suite_floor_aggregation': None,
            'scope': 'Registered b/c native overlays only. A/c carrier mapping remains unresolved when b is indeterminate; an external receipt cannot amend scientific rules.'}


def collector(api):
    path=LEGACY/'reference/collect_evidence.py'
    pins=api.Q.load(LEGACY/'SOURCE_PINS.json')['files']
    matches=[e for e in pins if e['snapshot']==str(path)]
    require(len(matches)==1,'collector source absent from accepted closure')
    return module(path,matches[0]['sha256'])


def observed(refs, files, api):
    require(isinstance(refs,dict) and set(refs)=={'container','image','daemon'},'complete observation roles required')
    docs={k:refdoc(v,files,api.Q) for k,v in refs.items()}
    for name in ('container','image'):
        require(isinstance(docs[name],list) and len(docs[name])==1,'single observation required')
        docs[name]=docs[name][0]
    state=docs['container']['State']
    require(state.get('Status')=='exited' and state.get('Running') is False
            and type(state.get('ExitCode')) is int and state['ExitCode']==0
            and not state.get('OOMKilled') and not state.get('Error'),'retained execution failed')
    return docs


def training_runtime(entry, plan, decision, api, files):
    q=api.Q; col=collector(api); refs=decision.get('training_observations')
    if refs is None:raise FileNotFoundError('training observations not adjudicated')
    docs=observed(refs,files,api); root=Path(plan['out']); path=entry['plan']
    col.load=lambda p,**kw:q.bound(p,files)
    col.raw=lambda p,pin=None,limit=2**20:q.read_pinned(p,pin,files,limit)
    canonical_pin=hashlib.sha256((json.dumps(dict(plan,review_sha256='PENDING'),indent=2,sort_keys=True)+'\n').encode()).hexdigest()
    col.verify_container(plan,{'training_plan':{'path':path},'canonical_plan_sha256':canonical_pin},docs['container'],docs['image'],docs['daemon'])
    a=root/'attempts/1';claim=q.bound(a/'CLAIM.json',files);release=q.bound(a/'RELEASE.json',files)
    timing=ownership(plan,claim,release,files[str(a/'CLAIM.json')],a/'RELEASE.json',docs['container'])
    end=q.bound(root/'TRAIN_EXIT.json',files);q.exact(end,q.bound(a/'EXIT.json',files),'training terminals disagree')
    require(end.get('attempt')==1 and end.get('source')!='retained-container-exit'
            and type(end.get('exit_code')) is int and end['exit_code']==0,'genuine successful driver terminal missing')
    require(timing['start']<=moment(end['started_utc'])<=moment(end['finished_utc'])<=timing['finish'],'training driver chronology differs')
    c=q.bound(root/'adapter/adapter_config.json',files);col.verify_config(c,plan['model'])
    payload=col.verify_payload(root/'adapter/adapter_model.safetensors',col.expected_shapes(plan['model'],c))
    require(payload['scanned_sha256']==files[str(root/'adapter/adapter_model.safetensors')],'adapter payload differs')
    collection=q.bound(entry['postrun_collection'],files); review=q.bound(entry['postrun_review'],files)
    require(collection.get('schema')=='formal-postrun-evidence-collection-v2' and collection['training']==plan['out']
            and collection.get('test_read') is False and collection.get('scientific_acceptance') is False,'postrun collection scope differs')
    require(review.get('schema')=='r3-formal-independent-postrun-v1' and review.get('verdict')=='PASS'
            and review.get('independent') is True and review.get('training')==plan['out']
            and review.get('test_read') is False and review.get('scientific_acceptance') is False,'postrun independent review differs')
    require(decision['postrun_review_sha256']==files[entry['postrun_review']]
            and review['evidence_files'].get(entry['postrun_collection'])==files[entry['postrun_collection']],'postrun origin binding differs')
    q.exact(review['files'],collection['files'],'postrun inventory differs')
    q.exact(review['capture_sha256'],collection['capture_sha256'],'capture differs')
    q.exact(payload,collection['adapter_payload'],'captured payload differs')
    for group in (collection['files'],collection['verified_training_files'],collection['external_observation_pins'],review['evidence_files']):
        for p,h in group.items():require(files.get(p)==h,'postrun dependency unbound')
    for ref in refs.values():require(collection['external_observation_pins'].get(ref['path'])==ref['sha256'],'observation not collector-bound')
    return timing


def evaluation_runtime(entry,decision,bundle,api):
    q=api.Q; files=bundle['files'];p=q.bound(entry['execution'],files);spec=q.bound(p['spec'],files)
    refs=decision.get('evaluation_observations')
    if refs is None:raise FileNotFoundError('evaluation observations not adjudicated')
    docs=observed(refs,files,api);actual=docs['container'];root=Path(p['out']);a=root/'attempts/1'
    require(decision.get('execution_sha256')==files[entry['execution']],'execution not independently adjudicated')
    require(actual['Name']=='/'+p['container']+'-a1' and actual['Image']==spec['image_sha256']==api.evaluation.IMAGE,'evaluation generation differs')
    cmd=api.evaluation.docker_command(p,spec,entry['execution'],files[entry['execution']],1)
    cut=cmd.index('--entrypoint');require(actual['Config']['Entrypoint']==['python3']
            and actual['Config']['Cmd']==cmd[cut+3:],'evaluation command differs')
    mounts=[];devices=[];env={}
    for i,token in enumerate(cmd[:cut]):
        if token=='--mount':
            vals=dict(x.split('=',1) if '=' in x else (x,True) for x in cmd[i+1].split(','))
            mounts.append((vals['src'],vals['dst'],'readonly' not in vals))
        if token=='--device':devices.append(cmd[i+1])
        if token=='-e':k,v=cmd[i+1].split('=',1);env[k]=v
    require(sorted(mounts)==sorted((x['Source'],x['Destination'],x['RW']) for x in actual['Mounts'])
            and all(x['Type']=='bind' and x.get('Propagation','rprivate')=='rprivate' for x in actual['Mounts']),'evaluation effective mounts differ')
    require(sorted((x,x,'rwm') for x in devices)==sorted((x['PathOnHost'],x['PathInContainer'],x['CgroupPermissions']) for x in actual['HostConfig']['Devices']),'evaluation devices differ')
    resource_ref=bundle['resource_validator'];require(resource_ref['sha256']=='c531413e8109a9eae1a3bb2dba6a914543d814131c90179bbb6b0974ed40051d'
        and files.get(resource_ref['path'])==resource_ref['sha256'],'resource policy not accepted')
    resource=module(resource_ref['path'],resource_ref['sha256'])
    daemon=docs['daemon'];require(daemon.get('DefaultRuntime') and daemon.get('CgroupVersion') in ('1','2'),'unknown daemon')
    resource.verify_effective_policy(actual,docs['image'],env,daemon={'runtime':daemon['DefaultRuntime'],'cgroupns':'private' if daemon['CgroupVersion']=='2' else 'host'})
    require(actual['HostConfig']['ShmSize']==64*1024**3 and len(actual['HostConfig'].get('Ulimits',[]))==2
            and {x['Name']:(x['Soft'],x['Hard']) for x in actual['HostConfig']['Ulimits']}=={'memlock':(-1,-1),'stack':(67108864,67108864)},'evaluation limits differ')
    end=q.bound(root/'ENGINEERING_EVAL_EXIT.json',files);q.exact(end,q.bound(a/'EXIT.json',files),'evaluation terminals differ')
    require(type(end.get('exit_code')) is int and end['exit_code']==0 and end.get('attempt')==1
            and end.get('source')!='retained-container-exit','genuine evaluation terminal absent')
    launch=q.bound(a/'LAUNCH_RECEIPT.json',files)
    require(launch['id']==actual['Id'] and launch['image']==actual['Image'] and launch['sha256']==files[entry['execution']],'evaluation launch receipt differs')
    done=q.bound(a/'SUPERVISOR_DONE.json',files);require(type(done.get('exit_code')) is int and done['exit_code']==0,'evaluation supervisor not complete')
    claim=q.bound(a/'CLAIM.json',files);release=q.bound(a/'RELEASE.json',files)
    if files[entry['execution']] in K0_EXECUTIONS:
        require(entry['arm'] == 'K0' and 'plan' not in entry, 'legacy K0 role differs')
        return k0_ownership(p,claim,release,files[str(a/'CLAIM.json')],a/'RELEASE.json',actual,
                            files,files[entry['execution']])
    return ownership(p,claim,release,files[str(a/'CLAIM.json')],a/'RELEASE.json',actual)


def member(name,entry,decision,bundle,api):
    q=api.Q; files=bundle['files']; context=protocol(bundle,name,entry,api)
    if decision is None:raise FileNotFoundError('independent member adjudication absent: '+name)
    require(decision.get('report_sha256')==files.get(entry['report'])
            and decision.get('observation_origin_authenticated') is True,'report/observation adjudication differs')
    plan=None;train=None
    if not name.startswith('k0_'):
        plan=q.bound(entry['plan'],files)
        require(plan.get('schema')=='r3-formal-k1-plan-v1' and label(plan)==entry['arm']
                and plan['seed']==entry['seed'] and plan.get('test_read') is False
                and plan.get('scientific_acceptance') is False,'formal training member differs')
        completed=verify_prelaunch(name,entry,plan,decision,files,api)
        train=training_runtime(entry,plan,decision,api,files)
        require(completed<train['start'],'review was not before training')
    else:
        require(decision.get('decision')=='ADMIT_EXACT_FROZEN_K0_SOURCE'
                and decision.get('checkpoint_revision_and_scorer_applicable') is True,'K0 applicability not independently adjudicated')
        identity=refdoc(decision.get('identity_control_acceptance'),files,q)
        require(identity.get('verdict') in ('PASS','PASS_WITH_SCOPE') or identity.get('status')=='PASS','K0 identity-control acceptance absent')
    ev=evaluation_runtime(entry,decision,bundle,api)
    if train:require(train['finish']<=ev['start'],'evaluation predates training completion')
    # Current role-aware producer adds role identity to selection_evidence. Use its
    # exact accepted bytes and existing numeric closure; no report normalization.
    source=bundle['selection_report_source']
    require(source['sha256']=='28af554ca6e12c3ca18a85dbc84928e6838bbbad9a556684e7de7fdcb86e4da0'
            and files.get(source['path'])==source['sha256'],'role-aware report source differs')
    report_module=module(source['path'],source['sha256']);old_R=api.R
    spec=q.bound(q.bound(entry['execution'],files)['spec'],files)
    binding=spec.get('formal_role_binding')
    if binding is not None:
        execution=q.bound(entry['execution'],files)
        binding=dict(binding,evaluation_plan=execution['spec'],evaluation_plan_sha256=execution['spec_sha256'])
    if name in ROLES:
        require(binding and binding['training_plan']==entry['plan'] and binding['training_plan_sha256']==files[entry['plan']],'DEV role binding absent')
    original=report_module.rebuild
    report_module.rebuild=lambda run,kev,data,deps:original(run,kev,data,deps,role_binding=binding)
    try:
        api.R=report_module
        rep=q.report(entry,context,api)
    finally:api.R=old_R
    if plan:
        training_lineage(entry,rep,context,api)
    return {'report':rep,'training':train,'evaluation':ev}


def chronology(nodes,verified):
    times={}
    for name in ROLES:
        times[name]=verified[name]['training'];times[name+'_dev']=verified[name]['evaluation']
        require(times[name]['chip']==nodes[name]['chip'] and times[name+'_dev']['chip']==nodes[name+'_dev']['chip'],'physical role chip differs')
    require(len({v['container_id'] for v in times.values()})==8,'runtime generation reused across physical roles')
    for name,node in nodes.items():
        for dep in node.get('depends_on',[]):
            predecessor=dep.removesuffix('_release')
            if predecessor in times:require(times[predecessor]['release']<=times[name]['start'],'formal role chronology violated')
    for chip in {x['chip'] for x in times.values()}:
        intervals=sorted((x['start'],x['release']) for x in times.values() if x['chip']==chip)
        require(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'same-chip role intervals overlap')
    return {'physical_roles_validated':list(ROLES),'candidate_seeds':[2,3],'auxiliary_excluded_from_estimators':True}


def evaluate(bundle,adjudication,bundle_pin,api=None):
    api=source_api() if api is None else api;q=api.Q
    result={'schema':'r3-production-dev-qualification-v1','status':'WAIT','candidate_eligibility_granted':False,
        'scientific_acceptance':False,'test_read':False,'final_test_logger_authority':False,'checks':{},'missing':[]}
    def check(name,fn):
        try:
            value=fn();result['checks'][name]={'status':'VALIDATED','value':value};return value
        except FileNotFoundError as e:result['checks'][name]={'status':'WAIT','reason':str(e)};result['missing'].append(str(e))
        except (ValueError,KeyError,TypeError,RuntimeError,OSError,AssertionError,ImportError) as e:result['checks'][name]={'status':'FAIL','reason':str(e)}
        return None
    def finish():
        states=[x['status'] for x in result['checks'].values()]
        if 'FAIL' in states:result['status']='FAIL'
        elif 'WAIT' in states:result['status']='WAIT'
        elif 'numeric' not in result['checks']:result['status']='WAIT';result['missing'].append('complete validated numerical evidence')
        else:
            passed=result['checks']['numeric']['value']['numeric_predicates_pass']
            indeterminate=result['checks']['numeric']['value'].get('floor_qualification_indeterminate',False)
            result['status']='NEGATIVE' if not passed else 'INDETERMINATE' if indeterminate else 'ELIGIBLE'
            result['candidate_eligibility_granted']=bool(passed and not indeterminate)
        result['completed']=result['status'] in ('ELIGIBLE','NEGATIVE','INDETERMINATE','FAIL')
        result['scope']='DEV eligibility only. Final adoption, PT R0 B-4, final campaign membership and one-read TEST ticket remain separate.'
        return result
    # Validate malformed existing inputs even when some future evidence is absent.
    if check('inventory',lambda:q.inventory(bundle['files']) or {'pins_valid':True}) is None:return finish()
    supplied=check('membership',lambda:entries(bundle))
    if check('adjudication',lambda:admitted_root(bundle,adjudication,bundle_pin,api)) is None:return finish()
    gate=check('r0',lambda:admitted_r0(bundle,api))
    if supplied is None:return finish()
    nodes=check('role_bindings',lambda:role_bindings(bundle,supplied,api));verified={}
    for name,entry in supplied.items():
        value=check('member:'+name,lambda name=name,entry=entry:member(name,entry,adjudication.get('members',{}).get(name),bundle,api))
        if value is not None:verified[name]=value
    if nodes is not None and all(r in verified for r in ROLES):check('chronology',lambda:chronology(nodes,verified))
    if len(verified)==len(supplied) and gate is not None:
        check('numeric',lambda:numerical({k:v['report'] for k,v in verified.items()},gate,api,bundle['branch']))
    check('final_inventory',lambda:q.inventory(bundle['files']) or {'unchanged':True})
    return finish()


@contextmanager
def read_boundary(api,files,scratch):
    q=api.Q;guard=q.ReadBoundary(files,scratch);old=tempfile.tempdir
    guard.files.update([str(LEGACY/'consumer.py'),str(BRIDGE),str(BRIDGE.parent/'role_validator.py')])
    try:
        tempfile.tempdir=scratch
        with guard.installed():yield
    finally:guard.active=False;tempfile.tempdir=old


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','bundle-sha256','adjudication','adjudication-sha256','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args(argv);api=source_api();q=api.Q
    require(sha(q.safe(a.bundle))==a.bundle_sha256 and sha(q.safe(a.adjudication))==a.adjudication_sha256,'external caller pins differ')
    bundle=q.load(a.bundle);adjudication=q.load(a.adjudication)
    output=q.safe(a.output);require(not output.exists(),'output already exists')
    import numpy
    try:import torch
    except ImportError:pass
    with tempfile.TemporaryDirectory(prefix='r3-dev-qualification-') as scratch:
        with read_boundary(api,bundle.get('files',{}),scratch):result=evaluate(bundle,adjudication,a.bundle_sha256,api)
    require(sha(a.bundle)==a.bundle_sha256 and sha(a.adjudication)==a.adjudication_sha256,'root inputs changed')
    result.update(bundle_sha256=a.bundle_sha256,adjudication_sha256=a.adjudication_sha256)
    with output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return {'ELIGIBLE':0,'NEGATIVE':3,'INDETERMINATE':4,'WAIT':2,'FAIL':1}[result['status']]


if __name__=='__main__':raise SystemExit(main())
