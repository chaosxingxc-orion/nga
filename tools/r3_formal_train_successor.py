#!/usr/bin/env python3
"""Exact formal train-only successor; preparation is not activation authority.

Root publishes an exact queue-bound activation ticket after review and publication.
Device operations use the separately reviewed isolated launcher/resource adapter.
Uncertain starts are never replayed. Each chip advances independently.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import types


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def content(path, pin=None):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(q.is_symlink() for q in (p, *p.parents)), 'unsafe path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and
            not ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
    raw = p.read_bytes()
    require(pin is None or digest(raw) == pin, 'content changed: ' + str(p))
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, pin=None):
    return json.loads(content(path, pin))


def identity(p):
    return digest((json.dumps(dict(p, review_sha256='PENDING'), indent=2, sort_keys=True)+'\n').encode())


def source(path, pin):
    raw = content(path, pin)  # Compile exactly the bytes whose hash was checked.
    m = types.ModuleType(Path(path).stem)
    m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), m.__dict__)
    return m


def atomic(path, value):
    path = Path(path)
    temp = path.with_suffix('.pending')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.fchmod(fd, 0o644)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    temp.replace(path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    os.fchmod(fd, 0o644)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    sync_directory(Path(path).parent)


def process_matches(receipt):
    require(type(receipt['pid']) is int and receipt['pid'] > 0, 'invalid pid')
    try:
        raw = Path(f"/proc/{receipt['pid']}/cmdline").read_bytes()
    except FileNotFoundError:
        return False
    return raw.rstrip(b'\0').split(b'\0') == [os.fsencode(x) for x in receipt['command']]


REVIEW_POLICY = 'requested-astra-parent-pinned-v1'
COLLAB_REVIEW_POLICY = 'requested-astra-collaboration-parent-pinned-v2'
REVIEW_SCOPE = 'exact-formal-train-only-readiness-no-activation'


def verify_collaboration_review(p, pin, review):
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
        return json.loads(content(path,ref['sha256']))
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
    prepared=load(prepared_ref['path'],prepared_ref['sha256'])
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


def verify_review(p, pin):
    """The parent authenticates this pin via the externally pinned attached queue.

    Hashes bind bytes, not authorship. No backend runtime attestation is claimed.
    The producer must never create the real parent envelope or approval.
    """
    review = load(p['review_path'], p['review_sha256'])
    if p.get('review_policy') == COLLAB_REVIEW_POLICY:
        return verify_collaboration_review(p,pin,review)
    if p.get('review_policy') != REVIEW_POLICY:
        require('review_policy' not in p, 'unknown review policy')
        require(review.get('approved_plan_sha256') == pin and review.get('verdict') == 'PASS'
                and review.get('review_kind') == 'independent_astra'
                and review.get('reviewer_model') == 'gpt-6-astra', 'exact review differs')
        return
    require(review.get('schema') == REVIEW_POLICY and review.get('scope') == REVIEW_SCOPE
            and review.get('requested_model') == 'gpt-6-astra'
            and review.get('model_evidence_kind') == 'parent-observed-requested-model-dispatch'
            and review.get('runtime_attestation') == 'unavailable-not-required'
            and review.get('worker_exit_code') == 0 and type(review.get('worker_exit_code')) is int
            and review.get('worker_id') and review.get('authenticator_identity')
            and review.get('authenticated_at') and review.get('activation_authorized') is False,
            'parent review policy differs')
    def artifact(key):
        ref = review[key]
        return content(ref['path'], ref['sha256'])
    report = json.loads(artifact('review_report'))
    artifact('worker_terminal'); artifact('worker_result')
    require(report.get('verdict') == 'PASS' and report.get('scope') == REVIEW_SCOPE
            and pin in report.get('approved_canonical_plan_sha256', []), 'independent PASS/scope differs')
    prepared = json.loads(artifact('prepared_queue'))
    require(prepared['controller'] == p['successor_guard']['controller'], 'review queue controller differs')
    matches = [j for j in prepared['jobs'] if j['plan'] == str(Path(p['out'])/'plan.json')]
    require(len(matches) == 1 and matches[0]['plan_sha256'] == pin
            and matches[0]['plan_raw_sha256'] == pin, 'prepared plan pins differ')
    expected = dict(path=matches[0]['plan'], canonical_sha256=pin, prepared_raw_sha256=pin)
    require(expected in review.get('plans', []), 'review exact plan pins differ')


def plan(job, reviewed=True):
    p = load(job['plan'], job['plan_raw_sha256'])
    require(identity(p) == job['plan_sha256'], 'canonical plan differs')
    require(p.get('schema') == 'r3-formal-k1-plan-v1' and p.get('control_arm') is None
            and p.get('test_read') is False and p.get('scientific_acceptance') is False,
            'exact Base K1 train-only scope required')
    if any(k in p for k in ('formal_schedule','formal_schedule_sha256','formal_role')):
        source(p['launcher'],p['files'][p['launcher']]).formal_target_identity(p)
        require(job.get('formal_role')==p['formal_role'] and job.get('formal_schedule_sha256')==p['formal_schedule_sha256'], 'successor role binding differs')
    else:
        require((p['seed'], p['chip']) in ((2, 1), (3, 4)), 'legacy plan ownership differs')
    require(p['chip'] == job['chip']
            and p['out'] == str(Path(job['plan']).parent), 'plan ownership differs')
    require(job['attempt'] == 1 and type(job['attempt']) is int, 'fresh attempt1 only')
    if reviewed:
        verify_review(p, job['plan_sha256'])
    for key in ('launcher', 'adapter', 'driver'):
        content(p[key], p['files'][p[key]])
    return p


def verify(path, pin, reviewed=True):
    d = load(path, pin)
    require(d['schema'] in ('r3-formal-train-successor-v2', 'r3-formal-train-successor-v3') and d['test_read'] is False
            and d['scientific_acceptance'] is False, 'queue scope differs')
    require(d['controller'] == str(Path(__file__).absolute()), 'controller path differs')
    content(d['controller'], d['controller_sha256'])
    for f, h in d['bindings'].items():
        content(f, h)
    jobs = d['jobs']
    unique = ('id', 'plan', 'chip') if d['schema'].endswith('v2') else ('id', 'plan')
    require(jobs and all(len({j[k] for j in jobs}) == len(jobs) for k in unique),
            'empty or duplicate jobs')
    if d['schema'].endswith('v3'):
        verify_wave(d, reviewed)
    for j in jobs:
        require(isinstance(j['id'], str) and j['id'] and
                all(c.isalnum() or c in '-_' for c in j['id']), 'unsafe job ID')
        p = plan(j, reviewed=reviewed)
        if 'previous_training' in j:
            require(d['schema'].endswith('v3') and 'previous_execution' not in j, 'training dependency requires v3')
            training_binding(j, p)
            continue
        prior = load(j['previous_execution'], j['previous_execution_sha256'])
        if prior.get('schema') == 'bev-dev-plan-v1':
            bev_binding(j, prior)
            continue
        require(prior.get('schema') == 'r3-engineering-posttrain-execution-v1'
                and prior['chip'] == j['chip'] and prior['out'] == str(Path(j['previous_execution']).parent)
                and prior['out'] != p['out'] and prior.get('test_read') is False
                and prior.get('scientific_acceptance') is False, 'predecessor binding differs')
        for f, h in prior['tools'].items():
            content(f, h)
        content(prior['spec'], prior['spec_sha256'])
    return d


def training_binding(job, target):
    ref = job['previous_training']
    p = load(ref['plan'], ref['plan_raw_sha256'])
    require(identity(p) == ref['plan_sha256'] and p.get('test_read') is False
            and p.get('scientific_acceptance') is False and p.get('control_arm') is None,
            'training predecessor scope/identity differs')
    require(p.get('schema') in ('r3-formal-k1-plan-v1', 'r3-engineering-k1-plan-v1')
            and p['chip'] == job['chip'] and p['out'] == str(Path(ref['plan']).parent)
            and p['out'] != target['out'], 'training predecessor placement differs')
    for k in ('launcher', 'adapter', 'driver'):
        content(p[k], p['files'][p[k]])
    return p


def verify_wave(d, reviewed=True):
    """Four roles, one common reviewed schedule, explicit per-chip FIFO edges."""
    require(type(d.get('poll_interval_seconds')) is int and d['poll_interval_seconds'] >= 600,
            'v3 polling must be at least600 seconds')
    schedule = load(d['formal_schedule'], d['formal_schedule_sha256'])
    require(d['bindings'].get(d['formal_schedule']) == d['formal_schedule_sha256'], 'wave binding missing')
    jobs = d['jobs']; by = {j['id']:j for j in jobs}
    roles = {j.get('formal_role'):j for j in jobs}
    require(len(jobs) == len(roles) == 4 and set(roles) ==
            {'primary_s2','primary_s3','samechip_s2','diffchip_s2'}, 'four exact training roles required')
    plans = {j['id']:plan(j, reviewed=reviewed) for j in jobs}
    require(len({p['out'] for p in plans.values()}) == 4 and
            len({p['container'] for p in plans.values()}) == 4, 'duplicate output/container')
    nodes = {n['id']:n for n in schedule['nodes']}
    for j in jobs:
        p=plans[j['id']]; role=j['formal_role']
        require(p['formal_schedule'] == d['formal_schedule'] and
                p['formal_schedule_sha256'] == j['formal_schedule_sha256'] == d['formal_schedule_sha256'],
                'mixed wave schedule')
        # A new queue must never depend on a launcher which only checks outside claim lock.
        launcher = source(p['launcher'], p['files'][p['launcher']])
        require(getattr(launcher, 'SUCCESSOR_CLAIM_GUARD_VERSION', None) == 1,
                'v3 requires reviewed launcher claim-guard integration')
        require(p.get('successor_guard',{}).get('controller') == d['controller']
                and p['files'].get(d['controller']) == d['controller_sha256'], 'claim guard controller pin differs')
        if role.startswith('primary_'):
            require(j.get('depends_on') is None, 'primary must have external predecessor')
        else:
            previous_role = 'primary_s2' if role == 'samechip_s2' else 'primary_s3'
            prior=roles[previous_role]; ref=j.get('previous_training',{})
            require(j.get('depends_on') == prior['id'] and prior['chip'] == j['chip'], 'within-chip predecessor differs')
            require(ref == {k:prior[k] for k in ('plan','plan_sha256','plan_raw_sha256')},
                    'training edge exact plan differs')
            require(nodes[role]['depends_on'] == [previous_role+'_release'], 'schedule edge differs')
        guard=p['successor_guard']
        if 'previous_training' in j:
            require(guard.get('previous_training') == j['previous_training'], 'training claim guard edge differs')
        else:
            require(guard.get('previous_execution') == j.get('previous_execution') and
                    guard.get('previous_execution_sha256') == j.get('previous_execution_sha256'), 'evaluation claim guard edge differs')
    # Manifest order is execution order per chip, not an incidental caller choice.
    for chip in {j['chip'] for j in jobs}:
        lane=[j for j in jobs if j['chip']==chip]
        require(len(lane)==2 and lane[0]['formal_role'].startswith('primary_') and
                lane[1].get('depends_on')==lane[0]['id'], 'per-chip FIFO order differs')
    return plans


def authorize(path, pin, queue_pin, doc):
    a = load(path, pin)
    require(a.get('schema') == 'r3-formal-train-activation-v1' and a.get('queue_sha256') == queue_pin
            and a.get('root_review_accepted') is True and a.get('prepublished') is True
            and a.get('train_only') is True and a.get('test_read') is False
            and a.get('scientific_acceptance') is False, 'root activation/publication required')
    require(a.get('allowed_jobs') and set(a['allowed_jobs']) <= {j['id'] for j in doc['jobs']}, 'activation jobs differ')
    require(a.get('published_files') and a.get('competing_successors_reconciled') is True,
            'publication/ownership reconciliation missing')
    for f, h in a['published_files'].items():
        content(f, h)
    for job_id in a['allowed_jobs']:
        require(job_id in a['competitors'], 'competitor inventory missing')
        job = next(j for j in doc['jobs'] if j['id'] == job_id)
        require(a['competitors'][job_id] == job['competitors'], 'reviewed competitor inventory differs')
    return a


class Snapshot:
    """Hash and parse the same bytes; recheck all captured pins at return/commit."""
    def __init__(self):
        self.hashes = {}

    def raw(self, path, pin=None):
        path = str(path)
        raw = content(path, pin)
        h = digest(raw)
        require(path not in self.hashes or self.hashes[path] == h, 'evidence changed during capture')
        self.hashes[path] = h
        return raw

    def read(self, path, pin=None):
        return json.loads(self.raw(path, pin))

    def recheck(self):
        for path, pin in self.hashes.items():
            content(path, pin)


def ownership(p, claim, release, release_path, container):
    """Per-chip lineage; unrelated chips may change between claim and release."""
    def entries(doc, section):
        return [x for x in doc[section] if x['chip'] == p['chip']]
    for doc, schema in ((claim, 'r3-resource-claim-v1'), (release, 'r3-resource-release-v1')):
        require(doc.get('schema') == schema and doc.get('chip') == p['chip']
                and doc.get('run') == p['run'], 'claim/release ownership differs')
        for stage in ('before', 'after'):
            value = doc['allocation_'+stage]
            chips = [x['chip'] for x in value['allocation'] + value['free']]
            require(len(chips) == len(set(chips)), 'duplicate lineage chip')
            # Historical before snapshots need not have canonical JSON serialization.
            # The captured claim/release buffer is pinned; compare its semantic entries.
    require(claim['allocation'] == p['allocation'] and claim['entry']['run'] == p['run']
            and claim['entry']['chip'] == p['chip'], 'claim allocation/entry differs')
    require(not entries(claim['allocation_before'], 'allocation')
            and len(entries(claim['allocation_before'], 'free')) == 1
            and entries(claim['allocation_after'], 'allocation') == [claim['entry']]
            and not entries(claim['allocation_after'], 'free'), 'claim transition differs')
    require(entries(release['allocation_before'], 'allocation') == [claim['entry']]
            and not entries(release['allocation_before'], 'free')
            and not entries(release['allocation_after'], 'allocation'), 'release claim generation differs')
    free = entries(release['allocation_after'], 'free')
    require(len(free) == 1 and free[0]['previous_run'] == p['run']
            and free[0]['release_evidence'] == str(release_path), 'release free generation differs')
    require(release['container'] == container['Name'].removeprefix('/')
            and release['container_id'] == container['Id']
            and release['container_started_at'] == container['State']['StartedAt']
            and release['container_finished_at'] == container['State']['FinishedAt'], 'release retained times/identity differ')
    return free[0]


def retained(command, image_id, actual, resource):
    """Compare effective configuration to the command derived from pinned source."""
    require(command.count(image_id) == 1 and actual['Image'] == image_id, 'retained image differs')
    index = command.index(image_id)
    require(actual['Name'] == '/' + command[command.index('--name')+1]
            and actual['Config']['Entrypoint'] == [command[command.index('--entrypoint')+1]]
            and actual['Config']['Cmd'] == command[index+1:], 'retained name/command differs')
    mounts = []
    environment = {}
    devices = []
    for i, arg in enumerate(command[:index]):
        if arg == '--mount':
            parts = dict(x.split('=', 1) if '=' in x else (x, True) for x in command[i+1].split(','))
            mounts.append((parts['src'], parts['dst'], 'readonly' not in parts))
        elif arg == '--device':
            devices.append((command[i+1], command[i+1], 'rwm'))
        elif arg == '-e':
            key, value = command[i+1].split('=', 1); environment[key] = value
    observed = actual['Mounts']; host = actual['HostConfig']
    require(sorted(mounts) == sorted((x['Source'], x['Destination'], x['RW']) for x in observed)
            and all(x['Type'] == 'bind' and x.get('Propagation', 'rprivate') == 'rprivate' for x in observed),
            'retained mounts differ')
    require(sorted(devices) == sorted((x['PathOnHost'], x['PathInContainer'], x['CgroupPermissions'])
                                     for x in host['Devices']), 'retained devices differ')
    require(host['ShmSize'] == 64*1024**3 and len(host['Ulimits']) == 2
            and {x['Name']:(x['Soft'], x['Hard']) for x in host['Ulimits']} ==
            {'memlock':(-1,-1), 'stack':(67108864,67108864)}, 'retained limits differ')
    image = resource.image_inspect(image_id)
    require(image['Id'] == image_id, 'image defaults identity differs')
    resource.verify_effective_policy(actual, image, environment)


def evaluator_lineage(p, spec, launcher, snap):
    root = launcher.result_directory(spec, p['out']); tag = launcher.profile(spec)
    end = snap.read(root/('EVAL_COMPLETE.'+tag+'.json'))
    receipt = snap.read(root/('SCORING_RECEIPT.'+tag+'.json'))
    rid = snap.read(root/'RUN_IDENTITY.json')
    manifest_path = root/'manifests'/(tag+'.json')
    manifest = snap.read(manifest_path)
    require(type(end.get('exit_code')) is int and end['exit_code'] == 0 and end.get('error') is None,
            'evaluator completion failed')
    require(receipt.get('schema') == 'r3-scoring-receipt-v1'
            and receipt.get('scientific_acceptance') is False, 'scoring receipt scope differs')
    header = receipt['header']; cmd = spec['command']
    require(header['argv'] == cmd[2:] and header['provenance_manifest'] == str(manifest_path)
            and header['model']['path'] == spec.get('adapter', spec['model'])
            and header['device'] == 'npu:0' and not header['dry_run_warnings'], 'evaluator command/model differs')
    # Reproduce testlock_r3.model_identity from pinned weight hashes, without cache writes.
    model_root = Path(spec.get('adapter', spec['model']))
    suffixes = ('.safetensors', '.bin', '.pt', '.json') if 'adapter' in spec else ('.safetensors', '.bin', '.pt')
    files = {str(Path(f).relative_to(model_root)): h for f,h in spec['files'].items()
             if Path(f).is_relative_to(model_root) and Path(f).suffix in suffixes
             and not any(x.startswith('.') for x in Path(f).relative_to(model_root).parts)}
    revpath = str(Path(spec['model'])/'.complete')
    rev = snap.raw(revpath, spec['files'][revpath]).decode().splitlines()[0].strip() or 'unknown'
    payload = (dict(kind='lora-adapter-unmerged', adapter_files=files, base_revision=rev, base_path=spec['model'])
               if 'adapter' in spec else dict(kind='checkpoint', weight_files=files, revision=rev))
    expected = digest(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())
    require(files and header['model']['sha256'] == rid['model_sha256'] == manifest['model_sha256'] == expected
            and rid['model_path'] == str(model_root) and rid['arm'] == header['arm'] == cmd[cmd.index('--arm')+1]
            and manifest['tag'] == tag and manifest['stamp'] == expected[:16], 'result model lineage differs')
    scorer = manifest['scorer']
    require(scorer == header['scorer'] and scorer.get('record_grade') is True
            and scorer.get('mode') == 'rightpad' and scorer.get('dtype') == 'float32'
            and scorer.get('token_budget') == 16384 and scorer.get('hf32', {}).get('hf32') is False,
            'result scorer differs')
    require(manifest['files'], 'empty result manifest')
    for rel, entry in manifest['files'].items():
        q = Path(rel)
        require(not q.is_absolute() and '..' not in q.parts and q.suffix == '.jsonl', 'unsafe result path')
        raw = snap.raw(root/q, entry['sha256'])
        rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
        require(rows and len(rows) == entry['rows'] and all(r.get('m') == expected[:16] for r in rows),
                'result rows/stamps differ')
    # Operational provenance only: population completeness/metrics remain independent scientific checks.


def predecessor(job, resource):
    if 'previous_training' in job:
        return training_predecessor(job, resource)
    path = Path(job['previous_execution']); root = path.parent
    snap = Snapshot(); p = snap.read(path, job['previous_execution_sha256'])
    if p.get('schema') == 'bev-dev-plan-v1':
        return bev_predecessor(job, p, resource, snap)
    marker = root/'ENGINEERING_EVAL_EXIT.json'
    if not marker.exists():
        return None
    spec = snap.read(p['spec'], p['spec_sha256'])
    for f,h in p['tools'].items():
        snap.raw(f,h)
    # Authenticate the mounted evaluator source closure, not only its filenames.
    for mount in spec['code_mounts']:
        root_code = Path(mount['source'])
        expected_files = {f for f in spec['files'] if Path(f).is_relative_to(root_code)}
        require(expected_files == {str(f) for f in root_code.rglob('*') if f.is_file()}, 'evaluator source inventory differs')
        for f in expected_files:
            snap.raw(f, spec['files'][f])
    launcher = source(p['launcher'], p['tools'][p['launcher']])
    require(spec['command'] == launcher.expected_command(spec, root)
            and spec['image_sha256'] == launcher.IMAGE, 'pinned predecessor recipe differs')
    end = snap.read(marker); receipt = snap.read(root/'SUPERVISOR_RECEIPT.json')
    cmd = receipt['command']; prefix = [sys.executable, '-P', p['launcher'], 'supervise', '--plan',
                                      str(path), '--sha256', job['previous_execution_sha256'], '--attempt']
    require(cmd[:-1] == prefix and cmd[-1].isdigit() and int(cmd[-1]) > 0, 'parent supervisor differs')
    n = int(cmd[-1])
    if end['attempt'] < n:
        return None
    require(type(end['attempt']) is int and end['attempt'] == n, 'parent attempt differs')
    attempt = root/'attempts'/str(n)
    if not all((attempt/x).exists() for x in ('RELEASE.json', 'SUPERVISOR_DONE.json')):
        return None
    require(snap.read(attempt/'EXIT.json') == end, 'parent terminal differs')
    release = snap.read(attempt/'RELEASE.json'); done = snap.read(attempt/'SUPERVISOR_DONE.json')
    claim = snap.read(attempt/'CLAIM.json'); launch = snap.read(attempt/'LAUNCH_RECEIPT.json')
    launch_spec = snap.read(attempt/'LAUNCH_SPEC.json')
    name = p['container']+'-a'+str(n); actual = resource.docker_inspect(name)
    require(actual and actual['Id'] == launch['id'] == release['container_id'], 'parent retained generation differs')
    command = launcher.docker_command(p, spec, str(path), job['previous_execution_sha256'], n)
    require(launch['sha256'] == launch_spec['sha256'] == job['previous_execution_sha256']
            and launch['image'] == spec['image_sha256'] and launch_spec['command'] == command,
            'parent launch identity differs')
    retained(command, spec['image_sha256'], actual, resource)
    require(actual['State']['Status'] in ('exited', 'dead'), 'parent not retained terminal')
    rc = end.get('container_exit_code', end['exit_code'])
    require(all(type(x) is int and x == 0 for x in
                (rc, end['exit_code'], actual['State']['ExitCode'], release['exit_code'], done['exit_code']))
            and release.get('scientific_acceptance') is False and done.get('scientific_acceptance') is False,
            'parent unsuccessful/scope differs')
    free = ownership(p, claim, release, attempt/'RELEASE.json', actual)
    evaluator_lineage(p, spec, launcher, snap)
    require(not process_matches(receipt), 'parent supervisor still live')
    snap.recheck()
    return dict(container_id=actual['Id'], attempt=n, run=p['run'], hashes=snap.hashes,
                release_path=str(attempt/'RELEASE.json'), free_entry=free)


def bev_binding(job, p):
    """A BEV predecessor is operational evidence, never a formal candidate."""
    require(p.get('schema') == 'bev-dev-plan-v1' and p.get('test_read') is False
            and p.get('scientific_acceptance') is False and p.get('source_split') == 'train_derived_dev'
            and p.get('chip') == job['chip'] and p.get('chips') == 1
            and p.get('out') == str(Path(job['previous_execution']).parent/'output')
            and p.get('selection') == 'all_registered_dev_ids'
            and type(p.get('expected_questions')) is int and p['expected_questions'] == 6516,
            'BEV predecessor scope/placement differs')
    for group in ('code', 'inputs'):
        require(isinstance(p.get(group), dict) and p[group], 'BEV pin inventory missing')
        for entry in p[group].values(): content(entry['path'], entry['sha256'])
    require(set(p['inputs']) == {'ids','requests'}, 'BEV input inventory differs')
    return p


def bev_predecessor(job, p, resource, snap):
    """Consume BEV runner + host terminals and the exact retained release generation.

    This checks completed execution and resource lineage, not accuracy or native
    TEST qualification. Missing terminal/release waits; malformed evidence fails.
    """
    bev_binding(job, p); root=Path(p['out']); complete=root/'COMPLETE.json'
    def attempts():
        found=[]
        for folder in (root/'host_attempts',root/'attempts'):
            if folder.exists():
                for path in folder.iterdir():
                    require(path.is_dir() and not path.is_symlink() and path.name.isdecimal()
                            and int(path.name)>0 and str(int(path.name))==path.name, 'BEV attempt inventory differs')
                    found.append(str(path))
        return sorted(found)
    inventory=attempts()
    if not inventory: return None
    n=max(int(Path(x).name) for x in inventory)
    host=root/'host_attempts'/str(n); a=root/'attempts'/str(n)
    if not all(x.is_file() for x in (host/'EXIT.json',host/'RELEASE.json',a/'EXIT.json')):
        observed=[snap.read(x) for x in (host/'EXIT.json',a/'EXIT.json') if x.is_file()]
        if any(type(x.get('exit_code')) is int and x['exit_code']!=0 for x in observed):
            return dict(status='needs_reconciliation',reason='failed BEV attempt lacks full terminal/release evidence',attempt=n)
        return None
    end=snap.read(complete) if complete.exists() else None
    for group in ('code','inputs'):
        for entry in p[group].values(): snap.raw(entry['path'],entry['sha256'])
    pin=job['previous_execution_sha256']; terminal=snap.read(a/'EXIT.json'); final=snap.read(host/'EXIT.json')
    require(terminal.get('attempt')==n and terminal.get('plan_sha256')==pin
            and terminal.get('scientific_acceptance') is False
            and final.get('runner_terminal_matches') is True
            and final.get('scientific_acceptance') is False, 'BEV terminal binding differs')
    launch=snap.read(host/'LAUNCH_RECEIPT.json'); spec=snap.read(host/'LAUNCH_SPEC.json')
    release=snap.read(host/'RELEASE.json'); claim=snap.read(host/'CLAIM.json'); service=snap.read(host/'SERVICE.json')
    start=snap.read(host/'START_INTENT.json');cmd=service['command']
    prefix=[sys.executable,'-B','-P',p['code']['host']['path'],'supervise','--plan',job['previous_execution'],'--sha256',pin,'--review']
    require(cmd[:10]==prefix and len(cmd)==15 and cmd[11]=='--review-sha256'
            and cmd[13:]==['--attempt',str(n)] and start['command']==cmd,
            'BEV supervisor identity differs')
    review=snap.read(cmd[10],cmd[12]);require(review.get('approved_plan_sha256')==pin
            and review.get('activation_authorized') is True and review.get('scientific_acceptance') is False,
            'BEV original execution review differs')
    actual=resource.docker_inspect(p['container']+'-a'+str(n))
    require(actual and actual['Id']==launch['container_id']==release['container_id']==final['container_id']
            and actual['State']['Status']=='exited', 'BEV retained generation differs')
    codes=[terminal.get('exit_code'),final.get('exit_code'),final.get('container_exit_code'),
           release.get('exit_code'),actual['State']['ExitCode']]
    require(all(type(x) is int for x in codes) and len(set(codes))==1
            and release.get('scientific_acceptance') is False, 'BEV predecessor exit codes differ')
    expected=['python3','-B','-P',p['code']['runner']['path'],'run','--plan',job['previous_execution'],
              '--sha256',pin,'--attempt',str(n)]
    image=resource.image_inspect(p['image_sha256']);command=spec['command'];ix=command.index(p['image_sha256'])
    require(command[ix+1:]==expected and actual['Config']['Cmd']==expected==launch['command']
            and actual['Config']['Entrypoint']==image.get('Config',{}).get('Entrypoint')
            and launch['plan_sha256']==spec['plan_sha256']==pin
            and command[:3]==['docker','run','-d'] and '--rm' not in command
            and command[command.index('--name')+1]==p['container']+'-a'+str(n)
            and actual['Name']=='/'+p['container']+'-a'+str(n), 'BEV retained command differs')
    before=command[3:ix];options={};i=0
    while i<len(before):
        key=before[i];require(key in ('--name','--network','--shm-size','--ulimit','--device','-v','-e')
                               and i+1<len(before),'BEV unexpected Docker option')
        options.setdefault(key,[]).append(before[i+1]);i+=2
    require(options.get('--name')==[p['container']+'-a'+str(n)] and options.get('--network')==['none']
            and options.get('--shm-size')==['16g'] and options.get('--ulimit')==['memlock=-1:-1','stack=67108864:67108864']
            and options.get('-e')==[k+'='+v for k,v in p['environment'].items()], 'BEV launch options differ')
    device_paths=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(p['chip'])]
    require(options.get('--device')==device_paths and sorted((x['PathOnHost'],x['PathInContainer'],x['CgroupPermissions']) for x in actual['HostConfig']['Devices'])==sorted((x,x,'rwm') for x in device_paths),'BEV devices differ')
    binds=options.get('-v',[]); expected_binds=['/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro']+[
        x['source']+':'+x['destination']+(':ro' if x['readonly'] else '') for x in p['mounts']]
    optional=[x+':'+x+':ro' for x in ('/usr/local/sbin','/etc/ascend_install.info')]
    require(binds[:len(expected_binds)]==expected_binds and all(x in optional for x in binds[len(expected_binds):])
            and len(set(binds))==len(binds) and sorted(actual['HostConfig'].get('Binds') or [])==sorted(binds),'BEV bind declaration differs')
    expected_mounts=[]
    for b in binds:
        parts=b.split(':');require(len(parts) in (2,3) and (len(parts)==2 or parts[2]=='ro'),'BEV bind mode differs')
        expected_mounts.append((parts[0],parts[1],len(parts)==2))
    require(sorted(expected_mounts)==sorted((x['Source'],x['Destination'],x['RW']) for x in actual['Mounts'])
            and all(x['Type']=='bind' and x.get('Propagation','rprivate')=='rprivate' for x in actual['Mounts']), 'BEV effective mounts differ')
    hostconfig=actual['HostConfig'];require(hostconfig.get('ShmSize')==16*1024**3
        and len(hostconfig.get('Ulimits',[]))==2 and {x['Name']:(x['Soft'],x['Hard']) for x in hostconfig['Ulimits']}=={'memlock':(-1,-1),'stack':(67108864,67108864)},'BEV limits differ')
    # Shared policy rejects Binds for --mount launchers. Here exact -v binds were checked above.
    policy=dict(actual,HostConfig=dict(hostconfig,Binds=None))
    resource.verify_effective_policy(policy,image,p['environment'])
    free=ownership(p,claim,release,host/'RELEASE.json',actual)
    require(not process_matches(service),'BEV supervisor still live')
    require(attempts()==inventory, 'BEV attempt inventory changed')
    snap.recheck()
    if codes[0]!=0:
        require(end is None or end.get('attempt')!=n, 'failed BEV attempt has conflicting completion')
        return dict(status='predecessor_failed',attempt=n,exit_code=codes[0],container_id=actual['Id'],
                    run=p['run'],hashes=snap.hashes,release_path=str(host/'RELEASE.json'))
    if end is None or end.get('attempt')!=n:
        return dict(status='needs_reconciliation',reason='successful BEV terminal lacks matching COMPLETE',attempt=n)
    require(end.get('schema')=='bev-dev-completion-v1' and end.get('plan_sha256')==pin
            and end.get('rows')==6516 and end.get('outcomes')=={'ok':6516}
            and len(end.get('items',{}))==6516 and end.get('scientific_acceptance') is False
            and end.get('test_read') is False, 'BEV completion identity differs')
    ids=snap.read(p['inputs']['ids']['path'],p['inputs']['ids']['sha256'])
    require(isinstance(ids,list) and len(ids)==len(set(ids))==6516 and all(isinstance(x,str) for x in ids)
            and set(end['items'])=={digest(x.encode())+'.json' for x in ids}
            and all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h)
                    for h in end['items'].values()),'BEV completion inventory differs')
    require(type(end.get('exit_code')) is int and end['exit_code']==0, 'BEV completion exit differs')
    snap.recheck()
    return dict(container_id=actual['Id'],attempt=n,run=p['run'],hashes=snap.hashes,
                release_path=str(host/'RELEASE.json'),free_entry=free)


def training_predecessor(job, resource):
    """Successful TRAIN_EXIT plus retained generation, claim/release and final manifest.

    This is operational handoff evidence. Scientific/DEV eligibility is separate.
    """
    target=plan(job); p=training_binding(job,target); ref=job['previous_training'];root=Path(p['out'])
    marker=root/'TRAIN_EXIT.json'
    if not marker.exists(): return None
    snap=Snapshot();snap.raw(ref['plan'],ref['plan_raw_sha256'])
    for f,h in p['files'].items():snap.raw(f,h)
    end=snap.read(marker);receipt=snap.read(root/'SUPERVISOR_RECEIPT.json');cmd=receipt['command']
    require(cmd[:3]==[sys.executable,'-P',p['launcher']] and cmd[3:6]==['supervise','--plan',ref['plan']]
            and cmd[6:8]==['--sha256',ref['plan_sha256']] and cmd[8]=='--attempt'
            and cmd[9].isdigit(), 'training supervisor identity differs')
    n=int(cmd[9]);require(n>0 and type(end.get('attempt')) is int, 'training attempt invalid')
    if end['attempt']<n:return None
    require(end['attempt']==n,'training terminal attempt differs')
    if 'successor_guard' in p:
        require(len(cmd)==12 and cmd[10]=='--precondition-sha256','training guard command missing')
        pre=snap.read(root/'SUCCESSOR_PRECONDITION.json',cmd[11])
        require(pre['job']['plan']==ref['plan'] and pre['job']['plan_sha256']==ref['plan_sha256'], 'predecessor own claim binding differs')
    else:require(len(cmd)==10,'unexpected training supervisor arguments')
    a=root/'attempts'/str(n)
    if not (a/'RELEASE.json').exists():return None
    if p['schema']=='r3-formal-k1-plan-v1' and not (a/'SUPERVISOR_DONE.json').exists():return None
    require(snap.read(a/'EXIT.json')==end,'training terminal disagreement')
    release=snap.read(a/'RELEASE.json');claim=snap.read(a/'CLAIM.json')
    launch=snap.read(a/'LAUNCH_RECEIPT.json');spec=snap.read(a/'LAUNCH_SPEC.json')
    launcher=source(p['launcher'],p['files'][p['launcher']]);command=launcher.docker_command(p,ref['plan'],n)
    actual=resource.docker_inspect(p['container']+'-a'+str(n))
    require(actual and actual['Id']==launch['id']==release['container_id']
            and launch['plan_sha256']==spec['plan_sha256']==ref['plan_sha256']
            and spec['command']==command and launch['image']==p['image_sha256'],'training launch identity differs')
    retained(command,p['image_sha256'],actual,resource)
    codes=[end['exit_code'],end.get('container_exit_code',end['exit_code']),release['exit_code'],actual['State']['ExitCode']]
    if p['schema']=='r3-formal-k1-plan-v1':
        done=snap.read(a/'SUPERVISOR_DONE.json');require(done.get('scientific_acceptance') is False,'training done scope differs');codes.append(done['exit_code'])
    require(actual['State']['Status'] in ('exited','dead') and all(type(x) is int and x==0 for x in codes), 'training predecessor failed')
    free=ownership(p,claim,release,a/'RELEASE.json',actual)
    if 'successor_guard' in p:
        require(release.get('claim_sha256')==snap.hashes[str(a/'CLAIM.json')] and
                claim['successor_precondition']['precondition_sha256']==cmd[11], 'training claim generation differs')
    manifest=snap.read(root/'manifest.json')
    require(manifest['summary']['final_step']==3116 and manifest['total_steps']==3116
            and manifest['args']['seed']==p['seed'] and manifest['args']['out']==p['out'], 'training final trajectory incomplete')
    for rel in ('adapter/adapter_model.safetensors','adapter/adapter_config.json','ckpt/step_003116.pt'):
        snap.raw(root/rel)
    require(not process_matches(receipt),'training predecessor supervisor still live')
    snap.recheck()
    return dict(container_id=actual['Id'],attempt=n,run=p['run'],hashes=snap.hashes,
                release_path=str(a/'RELEASE.json'),free_entry=free)


def competitors(entries):
    snap = Snapshot()
    for entry in entries:
        receipt = snap.read(entry['receipt'], entry['sha256'])
        require(not process_matches(receipt), 'competing authorized successor live')
        if 'retirement' in entry:
            snap.raw(entry['retirement'], entry['retirement_sha256'])
    snap.recheck()


def claim_precondition(p, plan_pin, precondition_pin, allocation, resource):
    """Called by the real adapter *inside* its allocation flock, twice before mutation."""
    snap = Snapshot()
    value = snap.read(Path(p['out'])/'SUCCESSOR_PRECONDITION.json', precondition_pin)
    job = value['job']; expected = value['evidence']; guard = p['successor_guard']
    require(identity(p) == plan_pin == job['plan_sha256'] and p == plan(job), 'guard plan differs')
    if 'previous_training' in job:
        require(job['previous_training'] == guard.get('previous_training'), 'guard training predecessor differs')
    else:
        require(job['previous_execution'] == guard.get('previous_execution')
                and job['previous_execution_sha256'] == guard.get('previous_execution_sha256'), 'guard predecessor differs')
    require(value['competitors'] == guard['competitors'], 'guard competitors differ')
    prior = predecessor(job, resource)
    require(prior is not None and 'status' not in prior and prior == expected['previous'], 'predecessor evidence changed at claim')
    free = [x for x in allocation['free'] if x['chip'] == p['chip']]
    require(not any(x['chip'] == p['chip'] for x in allocation['allocation'])
            and free == [expected['free_entry']] == [prior['free_entry']], 'free predecessor generation changed at claim')
    competitors(value['competitors'])
    require(resource.docker_inspect(p['container']+'-a1') is None, 'fixed container name collision at claim')
    require(not resource.live_chip_conflict(p['chip'], None), 'competing live device holder at claim')
    snap.recheck()
    return dict(precondition_sha256=precondition_pin, previous=prior, free_entry=free[0])


def ready(job, p, resource, authorization):
    prior = predecessor(job, resource)
    if prior is None:
        return {'status': 'waiting_previous_release_and_supervisor_done'}
    if 'status' in prior:
        return prior
    competitors(authorization['competitors'][job['id']])
    allocation_raw = resource.read_bytes(p['allocation'])
    allocation = json.loads(allocation_raw); resource.validate_doc(allocation)
    owners = [x for x in allocation['allocation'] if x['chip'] == job['chip']]
    if owners:
        return {'status': 'waiting_resource_owner', 'owners': owners}
    free = [x for x in allocation['free'] if x['chip'] == job['chip']]
    require(free == [prior['free_entry']], 'free ledger release differs')
    require(resource.docker_inspect(p['container']+'-a1') is None, 'fixed container name collision')
    require(not resource.live_chip_conflict(job['chip'], None), 'competing live device holder')
    out = Path(p['out'])
    entries = list(out.rglob('*'))
    require(not any(q.is_symlink() for q in entries), 'symlink in formal output')
    actual = sorted(str(q.relative_to(out)) for q in entries if q.is_file())
    require(actual == job['fresh_files'], 'formal output not fresh')
    require(not any((out/x).exists() for x in ('attempts', 'ckpt', 'adapter', 'manifest.json', 'TRAIN_EXIT.json')),
            'formal training artifacts already exist')
    require(os.access(out, os.W_OK), 'formal output remains read-only; root must enable execution writes')
    return {'status': 'eligible', 'previous': prior, 'allocation_sha256': digest(allocation_raw), 'free_entry': free[0]}


def observe(job, p, intent, resource):
    out = Path(p['out']); rp = out/'SUPERVISOR_RECEIPT.json'
    require(intent['job'] == job, 'start intent wrong plan/job')
    if (out/'attempts/1/NEEDS_REPAIR.json').exists():
        return {'status': 'needs_repair', 'reason': 'durable start uncertainty; explicit reconciliation required'}
    if not rp.exists():
        return {'status': 'needs_repair', 'reason': 'start intent without receipt; never restart'}
    snap = Snapshot(); receipt = snap.read(rp)
    expected = [sys.executable, '-P', p['launcher'], 'supervise', '--plan', job['plan'],
                '--sha256', job['plan_sha256'], '--attempt', '1',
                '--precondition-sha256', intent['precondition_sha256']]
    snap.raw(out/'SUCCESSOR_PRECONDITION.json', intent['precondition_sha256'])
    require(receipt['command'] == expected, 'successor supervisor differs')
    attempt = out/'attempts/1'; launch = attempt/'LAUNCH_RECEIPT.json'
    if not launch.exists():
        return {'status': 'supervisor_live' if process_matches(receipt) else 'needs_repair'}
    actual = resource.docker_inspect(p['container']+'-a1'); lr = snap.read(launch)
    require(actual and actual['Id'] == lr['id'] and lr['plan_sha256'] == job['plan_sha256'], 'successor retained generation differs')
    launcher = source(p['launcher'], p['files'][p['launcher']])
    ls = snap.read(attempt/'LAUNCH_SPEC.json'); claim = snap.read(attempt/'CLAIM.json')
    command = launcher.docker_command(p, job['plan'], 1)
    require(ls['command'] == command and ls['plan_sha256'] == lr['plan_sha256'] == job['plan_sha256']
            and lr['image'] == p['image_sha256'], 'successor launch binding differs')
    require(claim['successor_precondition']['precondition_sha256'] == intent['precondition_sha256']
            and claim['successor_precondition']['previous'] == intent['evidence']['previous'], 'successor claim intent differs')
    retained(command, p['image_sha256'], actual, resource)
    if actual['State']['Status'] not in ('exited', 'dead'):
        return {'status': 'training', 'container_id': actual['Id']}
    required = [out/'TRAIN_EXIT.json', attempt/'EXIT.json', attempt/'RELEASE.json', attempt/'SUPERVISOR_DONE.json']
    if not all(q.exists() for q in required):
        return {'status': 'waiting_successor_release_and_done'}
    values = [snap.read(q) for q in required]; end, local, rel, done = values
    require(end == local and end['attempt'] == 1 and rel['container_id'] == actual['Id']
            and rel['run'] == p['run'] and rel['chip'] == job['chip'] and rel['scientific_acceptance'] is False
            and rel.get('schema') == 'r3-resource-release-v1' and done.get('scientific_acceptance') is False
            and rel['exit_code'] == actual['State']['ExitCode'] == done['exit_code']
            == end.get('container_exit_code', end['exit_code']), 'successor terminal/release differs')
    require(type(end['exit_code']) is int and (end['exit_code'] != 0 or actual['State']['ExitCode'] == 0),
            'successful training with failed container')
    require(rel.get('claim_sha256') == snap.hashes[str(attempt/'CLAIM.json')], 'release captured claim pin differs')
    ownership(p, claim, rel, attempt/'RELEASE.json', actual)
    require(not process_matches(receipt), 'successor supervisor still live')
    snap.recheck()
    return {'status': 'completed' if end['exit_code'] == 0 else 'failed_released',
            'container_id': actual['Id'], 'hashes': snap.hashes}


def tick(job, authorization, state_root):
    p = plan(job); resource = source(p['adapter'], p['files'][p['adapter']])
    intent_path = state_root/(job['id']+'.START_INTENT.json')
    if intent_path.exists():
        return observe(job, p, load(intent_path), resource)
    require(not (Path(p['out'])/'SUPERVISOR_RECEIPT.json').exists(), 'successor started outside this handoff')
    evidence = ready(job, p, resource, authorization)
    if evidence['status'] != 'eligible':
        return evidence
    # Actual reviewed=True validator (no --unreviewed); stdout belongs to normal durable log.
    command = [sys.executable, '-P', p['launcher'], 'verify', '--plan', job['plan'], '--sha256', job['plan_sha256']]
    with (state_root/(job['id']+'.verify.log')).open('ab') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    plan(job)
    evidence = ready(job, p, resource, authorization)  # Re-observe after expensive CPU validation.
    if evidence['status'] != 'eligible':
        return evidence
    precondition = Path(p['out'])/'SUCCESSOR_PRECONDITION.json'
    exclusive(precondition, {'job': job, 'evidence': evidence, 'competitors': authorization['competitors'][job['id']]})
    precondition_pin = digest(content(precondition))
    command[3] = 'start'
    command += ['--precondition-sha256', precondition_pin]
    exclusive(intent_path, {'job': job, 'evidence': evidence, 'precondition_sha256': precondition_pin,
                            'command': command, 'utc_seconds': time.time()})
    with (state_root/(job['id']+'.launch.log')).open('ab') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return {'status': 'launch_requested', 'previous': evidence['previous']}


def cycle(doc, authorization, state_root):
    if doc.get('schema') == 'r3-formal-train-successor-v3':
        return wave_cycle(doc, authorization, state_root)
    states = {}
    for job in doc['jobs']:
        if job['id'] not in authorization['allowed_jobs']:
            states[job['id']] = {'status': 'deferred_by_root'}; continue
        try:
            states[job['id']] = tick(job, authorization, state_root)
        except Exception as e:
            states[job['id']] = {'status': 'observation_or_launch_uncertain', 'error': str(e)[:300]}
    return states


WAVE_FAILURES = frozenset(('failed_released','predecessor_failed','blocked_by_failed_predecessor'))
WAVE_TERMINALS = WAVE_FAILURES | frozenset(('completed','deferred_by_root'))

def wave_lane(jobs, authorization, state_root):
    states={};blocked=None;failed=False
    for job in jobs:
        if job['id'] not in authorization['allowed_jobs']:
            states[job['id']]={'status':'deferred_by_root'};blocked=job['id'];continue
        if blocked:
            states[job['id']]={'status':'blocked_by_failed_predecessor' if failed else 'waiting_queue_predecessor','job':blocked};continue
        try:states[job['id']]=tick(job,authorization,state_root)
        except Exception as error:states[job['id']]={'status':'observation_or_launch_uncertain','error':str(error)[:300]}
        if states[job['id']]['status']!='completed':
            blocked=job['id'];failed=states[job['id']]['status'] in WAVE_FAILURES
    return states


def wave_cycle(doc, authorization, state_root):
    """One concurrent observation cycle, also used by bounded CPU tests."""
    chips=sorted({j['chip'] for j in doc['jobs']})
    with ThreadPoolExecutor(max_workers=len(chips)) as pool:
        futures=[pool.submit(wave_lane,[j for j in doc['jobs'] if j['chip']==chip],authorization,state_root) for chip in chips]
        result={}
        for future in futures:result.update(future.result())
    return result


def watch_wave(path, pin, apath, apin, initial):
    """Persistent chip lanes have independent clocks; aggregation never gates them."""
    root=path.parent;mutex=threading.Lock();stop=threading.Event()
    states={j['id']:{'status':'not_yet_observed'} for j in initial['jobs']};errors={}
    def lane(chip):
        try:
            while not stop.is_set():
                d=verify(path,pin);a=authorize(apath,apin,pin,d)
                jobs=[j for j in d['jobs'] if j['chip']==chip]
                values=wave_lane(jobs,a,root)
                with mutex:states.update(values)
                if all(x['status'] in WAVE_TERMINALS for x in values.values()):return
                stop.wait(d['poll_interval_seconds'])
        except Exception as error:
            with mutex:errors[str(chip)]=str(error)[:300]
    threads=[threading.Thread(target=lane,args=(chip,),daemon=True) for chip in sorted({j['chip'] for j in initial['jobs']})]
    for thread in threads:thread.start()
    while any(t.is_alive() for t in threads):
        with mutex:value={'utc_seconds':time.time(),'jobs':dict(states),'lane_errors':dict(errors),'scientific_acceptance':False,'test_read':False}
        atomic(root/'digest.json',value);atomic(root/'heartbeat.json',value)
        # Machine-only heartbeat aggregation; no Docker/model polling here.
        stop.wait(min(15, initial['poll_interval_seconds']))
    with mutex:value={'utc_seconds':time.time(),'jobs':dict(states),'lane_errors':dict(errors),'scientific_acceptance':False,'test_read':False}
    atomic(root/'digest.json',value)
    atomic(root/'EXIT.json',dict(value,exit_code=int(bool(errors) or any(x['status'] not in ('completed','deferred_by_root') for x in states.values()))))


def watch(path, pin, apath, apin):
    root = path.parent
    with (root/'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial=verify(path,pin)
        if initial['schema']=='r3-formal-train-successor-v3':
            return watch_wave(path,pin,apath,apin,initial)
        stop = threading.Event()
        def heartbeat():
            while not stop.is_set():
                atomic(root/'service_heartbeat.json', {'utc_seconds': time.time(), 'pid': os.getpid(),
                       'progress_source': str(root/'digest.json'), 'status': 'observing_or_validating'})
                stop.wait(15)
        threading.Thread(target=heartbeat, daemon=True).start()
        while True:
            d = verify(path, pin); a = authorize(apath, apin, pin, d)
            states = cycle(d, a, root)
            value = {'utc_seconds': time.time(), 'jobs': states, 'progress_count': sum(
                x['status'] in ('completed', 'failed_released') for x in states.values()),
                'scientific_acceptance': False, 'test_read': False}
            atomic(root/'digest.json', value); atomic(root/'heartbeat.json', value)
            if all(x['status'] in ('completed', 'failed_released', 'deferred_by_root') for x in states.values()):
                stop.set()
                atomic(root/'EXIT.json', dict(value, exit_code=int(any(x['status']=='failed_released' for x in states.values())))); return
            time.sleep(d.get('poll_interval_seconds', 30))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('verify', 'start', 'watch'))
    parser.add_argument('--manifest', required=True); parser.add_argument('--sha256', required=True)
    parser.add_argument('--unreviewed', action='store_true')
    parser.add_argument('--authorization'); parser.add_argument('--authorization-sha256')
    args = parser.parse_args(); path = Path(args.manifest).absolute()
    require(not args.unreviewed or args.op == 'verify', 'unreviewed CPU verify only')
    doc = verify(path, args.sha256, reviewed=not args.unreviewed)
    if args.op == 'verify':
        print(json.dumps({'status': 'CPU_QUEUE_VERIFIED', 'activation_authorized': False})); return
    require(socket.gethostname() == 'k8s-node1', 'activation on host175 only')
    require(args.authorization and args.authorization_sha256, 'root publication ticket required')
    authorize(args.authorization, args.authorization_sha256, args.sha256, doc)
    if args.op == 'watch':
        try:
            watch(path, args.sha256, args.authorization, args.authorization_sha256)
        except BaseException as exc:
            atomic(path.parent/'EXIT.json', {'exit_code': 1, 'error': str(exc)[:300], 'utc_seconds': time.time()}); raise
        return
    command = [sys.executable, '-P', str(Path(__file__).absolute()), 'watch', '--manifest', str(path),
               '--sha256', args.sha256, '--authorization', args.authorization,
               '--authorization-sha256', args.authorization_sha256]
    with (path.parent/'start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rp = path.parent/'SERVICE.json'
        if rp.exists():
            receipt = load(rp)
            require(receipt['command'] == command and process_matches(receipt), 'old service uncertain; explicit repair required')
            print('ALREADY_LIVE'); return
        exclusive(path.parent/'SERVICE_START_INTENT.json', {'command': command, 'utc_seconds': time.time()})
        with (path.parent/'service.log').open('ab') as log:
            p = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        atomic(rp, {'pid': p.pid, 'command': command})
        atomic(path.parent/'RELAUNCH.json', {'command': [x if x != 'watch' else 'start' for x in command],
                                          'rule': 'live service idempotent; absent/uncertain service requires repair'})
        print(json.dumps({'status': 'DETACHED', 'pid': p.pid}))


if __name__ == '__main__':
    main()
