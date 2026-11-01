#!/usr/bin/env python3
"""Exact formal train-only successor; preparation is not activation authority.

Root publishes an exact queue-bound activation ticket after review and publication.
All device operations stay in the unchanged reviewed launcher/resource adapter.
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


def plan(job):
    p = load(job['plan'], job['plan_raw_sha256'])
    require(identity(p) == job['plan_sha256'], 'canonical plan differs')
    require(p.get('schema') == 'r3-formal-k1-plan-v1' and p.get('control_arm') is None
            and p.get('test_read') is False and p.get('scientific_acceptance') is False,
            'exact Base K1 train-only scope required')
    require((p['seed'], p['chip']) in ((2, 1), (3, 4)) and p['chip'] == job['chip']
            and p['out'] == str(Path(job['plan']).parent), 'plan ownership differs')
    require(job['attempt'] == 1 and type(job['attempt']) is int, 'fresh attempt1 only')
    review = load(p['review_path'], p['review_sha256'])
    require(review.get('approved_plan_sha256') == job['plan_sha256'] and review.get('verdict') == 'PASS'
            and review.get('review_kind') == 'independent_astra'
            and review.get('reviewer_model') == 'gpt-6-astra', 'exact review differs')
    for key in ('launcher', 'adapter', 'driver'):
        content(p[key], p['files'][p[key]])
    return p


def verify(path, pin):
    d = load(path, pin)
    require(d['schema'] == 'r3-formal-train-successor-v1' and d['test_read'] is False
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
        p = plan(j)
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


def predecessor(job, resource):
    """Exact pinned parent, actual retained generation, matching terminal/release/DONE."""
    path = Path(job['previous_execution']); root = path.parent
    p = load(path, job['previous_execution_sha256'])
    marker = root/'ENGINEERING_EVAL_EXIT.json'
    if not marker.exists():
        return None
    captured = {}
    def read(q):
        raw = content(q); captured[str(q)] = digest(raw); return json.loads(raw)
    end = read(marker); receipt = read(root/'SUPERVISOR_RECEIPT.json')
    cmd = receipt['command']; prefix = [sys.executable, '-P', p['launcher'], 'supervise', '--plan',
                                      str(path), '--sha256', job['previous_execution_sha256'], '--attempt']
    require(cmd[:-1] == prefix and cmd[-1].isdigit() and int(cmd[-1]) > 0, 'parent supervisor differs')
    n = int(cmd[-1])
    if end['attempt'] < n:
        return None  # A newer retry owns the chip.
    require(type(end['attempt']) is int and end['attempt'] == n, 'parent attempt differs')
    attempt = root/'attempts'/str(n)
    if not all((attempt/x).exists() for x in ('RELEASE.json', 'SUPERVISOR_DONE.json')):
        return None
    require(read(attempt/'EXIT.json') == end, 'parent terminal differs')
    release = read(attempt/'RELEASE.json'); done = read(attempt/'SUPERVISOR_DONE.json')
    launch = read(attempt/'LAUNCH_RECEIPT.json')
    spec = read(attempt/'LAUNCH_SPEC.json')
    name = p['container']+'-a'+str(n); actual = resource.docker_inspect(name)
    require(actual and actual['Id'] == launch['id'] == release['container_id'], 'parent retained generation differs')
    require(launch['sha256'] == spec['sha256'] == job['previous_execution_sha256']
            and actual['Image'] == launch['image'], 'parent launch identity differs')
    command = spec['command']; image_at = command.index(launch['image'])
    require(actual['Config']['Cmd'] == command[image_at+1:] and
            {d['PathOnHost'] for d in actual['HostConfig']['Devices']} ==
            {'/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', f"/dev/davinci{job['chip']}"},
            'parent command/device differs')
    require(actual['State']['Status'] in ('exited', 'dead') and not actual['HostConfig']['AutoRemove'], 'parent not retained terminal')
    rc = end.get('container_exit_code', end['exit_code'])
    require(type(rc) is int and type(end['exit_code']) is int and actual['State']['ExitCode'] == rc
            == release['exit_code'] == done['exit_code'] and end['exit_code'] == 0 == rc, 'parent unsuccessful')
    require(release.get('schema') == 'r3-resource-release-v1' and release['chip'] == job['chip']
            and release['run'] == p['run'] and release['container'] == name
            and release.get('scientific_acceptance') is False and done.get('scientific_acceptance') is False,
            'parent release ownership differs')
    require(not process_matches(receipt), 'parent supervisor still live')
    for f, h in captured.items():
        content(f, h)
    content(path, job['previous_execution_sha256'])
    return dict(container_id=actual['Id'], attempt=n, run=p['run'], hashes=captured,
                release_path=str(attempt/'RELEASE.json'))


def ready(job, p, resource, authorization):
    prior = predecessor(job, resource)
    if prior is None:
        return {'status': 'waiting_previous_release_and_supervisor_done'}
    for entry in authorization['competitors'][job['id']]:
        receipt = load(entry['receipt'], entry['sha256'])
        require(not process_matches(receipt), 'competing authorized successor live')
        if 'retirement' in entry:
            content(entry['retirement'], entry['retirement_sha256'])
    allocation = resource.load(p['allocation']); resource.validate_doc(allocation)
    owners = [x for x in allocation['allocation'] if x['chip'] == job['chip']]
    if owners:
        return {'status': 'waiting_resource_owner', 'owners': owners}
    free = [x for x in allocation['free'] if x['chip'] == job['chip']]
    require(len(free) == 1 and free[0].get('previous_run') == prior['run']
            and free[0].get('release_evidence') == prior['release_path'], 'free ledger release differs')
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
    return {'status': 'eligible', 'previous': prior, 'allocation_sha256': digest(resource.read_bytes(p['allocation']))}


def observe(job, p, intent, resource):
    out = Path(p['out']); rp = out/'SUPERVISOR_RECEIPT.json'
    require(intent['job'] == job, 'start intent wrong plan/job')
    if not rp.exists():
        return {'status': 'needs_repair', 'reason': 'start intent without receipt; never restart'}
    receipt = load(rp)
    expected = [sys.executable, '-P', p['launcher'], 'supervise', '--plan', job['plan'],
                '--sha256', job['plan_sha256'], '--attempt', '1']
    require(receipt['command'] == expected, 'successor supervisor differs')
    attempt = out/'attempts/1'; launch = attempt/'LAUNCH_RECEIPT.json'
    if not launch.exists():
        return {'status': 'supervisor_live' if process_matches(receipt) else 'needs_repair'}
    actual = resource.docker_inspect(p['container']+'-a1'); lr = load(launch)
    require(actual and actual['Id'] == lr['id'] and lr['plan_sha256'] == job['plan_sha256'], 'successor retained generation differs')
    launcher = source(p['launcher'], p['files'][p['launcher']])
    launcher.verify_retained_receipts(attempt, job['plan_sha256'], actual,
                                     launcher.docker_command(p, job['plan'], 1))
    require(actual['Image'] == p['image_sha256'] and not actual['HostConfig']['AutoRemove']
            and actual['Config']['Cmd'] == ['-P', '/workspace/r3_formal_driver.py', '--plan', job['plan'], '--attempt', '1'],
            'successor image/command differs')
    if actual['State']['Status'] not in ('exited', 'dead'):
        return {'status': 'training', 'container_id': actual['Id']}
    required = [out/'TRAIN_EXIT.json', attempt/'EXIT.json', attempt/'RELEASE.json', attempt/'SUPERVISOR_DONE.json']
    if not all(q.exists() for q in required):
        return {'status': 'waiting_successor_release_and_done'}
    values = [load(q) for q in required]; end, local, rel, done = values
    require(end == local and end['attempt'] == 1 and rel['container_id'] == actual['Id']
            and rel['run'] == p['run'] and rel['chip'] == job['chip'] and rel['scientific_acceptance'] is False
            and rel.get('schema') == 'r3-resource-release-v1' and done.get('scientific_acceptance') is False
            and rel['exit_code'] == actual['State']['ExitCode'] == done['exit_code']
            == end.get('container_exit_code', end['exit_code']), 'successor terminal/release differs')
    require(type(end['exit_code']) is int and (end['exit_code'] != 0 or actual['State']['ExitCode'] == 0),
            'successful training with failed container')
    require(not process_matches(receipt), 'successor supervisor still live')
    return {'status': 'completed' if end['exit_code'] == 0 else 'failed_released',
            'container_id': actual['Id'], 'hashes': {str(q): digest(content(q)) for q in required}}


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
    command[3] = 'start'
    exclusive(intent_path, {'job': job, 'evidence': evidence, 'command': command, 'utc_seconds': time.time()})
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
    parser.add_argument('--authorization'); parser.add_argument('--authorization-sha256')
    args = parser.parse_args(); path = Path(args.manifest).absolute(); doc = verify(path, args.sha256)
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
