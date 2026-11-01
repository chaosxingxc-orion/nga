#!/usr/bin/env python3
"""Exact formal train-only successor; preparation is not activation authority.

Root publishes an exact queue-bound activation ticket after review and publication.
Device operations use the separately reviewed isolated launcher/resource adapter.
Uncertain starts are never replayed. Each chip advances independently.
"""
import argparse
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
    with temp.open('w') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    temp.replace(path)


def exclusive(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())


def process_matches(receipt):
    require(type(receipt['pid']) is int and receipt['pid'] > 0, 'invalid pid')
    try:
        raw = Path(f"/proc/{receipt['pid']}/cmdline").read_bytes()
    except FileNotFoundError:
        return False
    return raw.rstrip(b'\0').split(b'\0') == [os.fsencode(x) for x in receipt['command']]


def plan(job, reviewed=True):
    p = load(job['plan'], job['plan_raw_sha256'])
    require(identity(p) == job['plan_sha256'], 'canonical plan differs')
    require(p.get('schema') == 'r3-formal-k1-plan-v1' and p.get('control_arm') is None
            and p.get('test_read') is False and p.get('scientific_acceptance') is False,
            'exact Base K1 train-only scope required')
    require((p['seed'], p['chip']) in ((2, 1), (3, 4)) and p['chip'] == job['chip']
            and p['out'] == str(Path(job['plan']).parent), 'plan ownership differs')
    require(job['attempt'] == 1 and type(job['attempt']) is int, 'fresh attempt1 only')
    if reviewed:
        review = load(p['review_path'], p['review_sha256'])
        require(review.get('approved_plan_sha256') == job['plan_sha256'] and review.get('verdict') == 'PASS'
            and review.get('review_kind') == 'independent_astra'
            and review.get('reviewer_model') == 'gpt-6-astra', 'exact review differs')
    for key in ('launcher', 'adapter', 'driver'):
        content(p[key], p['files'][p[key]])
    return p


def verify(path, pin, reviewed=True):
    d = load(path, pin)
    require(d['schema'] == 'r3-formal-train-successor-v2' and d['test_read'] is False
            and d['scientific_acceptance'] is False, 'queue scope differs')
    require(d['controller'] == str(Path(__file__).absolute()), 'controller path differs')
    content(d['controller'], d['controller_sha256'])
    for f, h in d['bindings'].items():
        content(f, h)
    jobs = d['jobs']
    require(jobs and all(len({j[k] for j in jobs}) == len(jobs) for k in ('id', 'plan', 'chip')),
            'empty or duplicate jobs')
    for j in jobs:
        require(isinstance(j['id'], str) and j['id'] and
                all(c.isalnum() or c in '-_' for c in j['id']), 'unsafe job ID')
        p = plan(j, reviewed=reviewed)
        prior = load(j['previous_execution'], j['previous_execution_sha256'])
        require(prior.get('schema') == 'r3-engineering-posttrain-execution-v1'
                and prior['chip'] == j['chip'] and prior['out'] == str(Path(j['previous_execution']).parent)
                and prior['out'] != p['out'] and prior.get('test_read') is False
                and prior.get('scientific_acceptance') is False, 'predecessor binding differs')
        for f, h in prior['tools'].items():
            content(f, h)
        content(prior['spec'], prior['spec_sha256'])
    return d


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
    path = Path(job['previous_execution']); root = path.parent
    snap = Snapshot(); p = snap.read(path, job['previous_execution_sha256'])
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
    require(job['previous_execution'] == guard['previous_execution']
            and job['previous_execution_sha256'] == guard['previous_execution_sha256']
            and value['competitors'] == guard['competitors'], 'guard predecessor/competitors differ')
    prior = predecessor(job, resource)
    require(prior is not None and prior == expected['previous'], 'predecessor evidence changed at claim')
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
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
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
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    return {'status': 'launch_requested', 'previous': evidence['previous']}


def cycle(doc, authorization, state_root):
    states = {}
    for job in doc['jobs']:
        if job['id'] not in authorization['allowed_jobs']:
            states[job['id']] = {'status': 'deferred_by_root'}; continue
        try:
            states[job['id']] = tick(job, authorization, state_root)
        except Exception as e:
            states[job['id']] = {'status': 'observation_or_launch_uncertain', 'error': str(e)[:300]}
    return states


def watch(path, pin, apath, apin):
    root = path.parent
    with (root/'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            time.sleep(30)


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
            p = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        atomic(rp, {'pid': p.pid, 'command': command})
        atomic(path.parent/'RELAUNCH.json', {'command': [x if x != 'watch' else 'start' for x in command],
                                          'rule': 'live service idempotent; absent/uncertain service requires repair'})
        print(json.dumps({'status': 'DETACHED', 'pid': p.pid}))


if __name__ == '__main__':
    main()
