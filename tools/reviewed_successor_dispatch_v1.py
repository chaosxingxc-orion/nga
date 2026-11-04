#!/usr/bin/env python3
"""Dispatch externally approved exact fixed-base plans once; never adjudicate them.

Runs on the NPU host. Existing host/resource modules retain physical claim and
admission authority. SIGUSR1 wakes the script on approval publication; 600 seconds
is the fallback. This is not a static-plan/resource-binding redesign or full DAG.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import types


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts, 'absolute canonical path required')
    need(not any(x.is_symlink() for x in [p, *p.parents]), 'symlink path rejected')
    return p


def raw(path):
    p = safe(path)
    with p.open('rb') as f:
        a = os.fstat(f.fileno()); b = f.read(); z = os.fstat(f.fileno())
    need((a.st_ino, a.st_dev, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
         (z.st_ino, z.st_dev, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'changed read')
    return b


def sha(path):
    p = safe(path); digest = hashlib.sha256()
    with p.open('rb') as f:
        a = os.fstat(f.fileno())
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
        z = os.fstat(f.fileno())
    need((a.st_ino, a.st_dev, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
         (z.st_ino, z.st_dev, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'changed hash read')
    return digest.hexdigest()


def read(path):
    return json.loads(raw(path))


def put(path, value):
    p = safe(path); tmp = p.with_name(p.name + '.pending')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def proc_identity(pid):
    p = Path('/proc') / str(pid)
    try:
        stat = (p / 'stat').read_text(); tail = stat[stat.rfind(')') + 2:].split()
        if tail[0] == 'Z':
            return None
        return dict(pid=pid, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    start_ticks=tail[19], argv=[x.decode() for x in (p / 'cmdline').read_bytes().split(b'\0') if x])
    except (FileNotFoundError, ProcessLookupError):
        return None


def validate(c):
    need(c['schema'] == 'reviewed-successor-dispatch-v1' and c['poll_seconds'] == 600, 'queue protocol')
    need(c['host_name'] == socket.gethostname(), 'wrong physical host')
    need(c['scientific_acceptance'] is False, 'no scientific authority')
    safe(c['output']); need(c['jobs'], 'empty queue')
    for key in ('id', 'plan', 'review', 'out', 'container'):
        need(len({j[key] for j in c['jobs']}) == len(c['jobs']), 'duplicate ' + key)
    for j in c['jobs']:
        need(re.fullmatch(r'[a-zA-Z0-9_-]+', j['id']) is not None, 'invalid id')
        need(type(j['chip']) is int and 0 <= j['chip'] < 8 and j['attempt'] == 1 and type(j['attempt']) is int, 'chip/attempt')
        for k in ('plan', 'review', 'out'):
            safe(j[k])
        need(Path(j['plan']).parent == Path(j['out']).parent, 'plan/output siblings')
        need(j['scope'] == 'public_fixed_base_test', 'fixed-base scope only')
    return c


def approved(c, j):
    """Externally deposited review is consumed, never authored or amended here."""
    if not Path(j['plan']).exists() or not Path(j['review']).exists():
        return None
    d = read(j['plan']); r = read(j['review']); pin = sha(j['plan']); rpin = sha(j['review'])
    need(d['schema'] == 'native-dataset-panel-execution-v1', 'unsupported plan')
    for k in ('out', 'chip', 'container', 'scope'):
        need(d[k] == j[k] and type(d[k]) is type(j[k]), 'job binding ' + k)
    need(d['run'] == j['run'] and d['host_name'] == c['host_name'], 'run/host binding')
    need(d['scientific_acceptance'] is False and d['candidate_test_authority'] is False and d['candidate_selection_allowed'] is False, 'plan authority')
    need(r['verdict'] == 'PASS' and r['approved_plan_sha256'] == pin and r['activation_authorized'] is True, 'exact PASS required')
    need(r['scientific_acceptance'] is False and r['candidate_test_authority'] is False and r['test_read'] is True and r['scope'] == j['scope'], 'review scope')
    need(1 in r['attempts'] and all(type(a) is int for a in r['attempts']), 'review attempt')
    host = d['modules']['host']
    need(host['sha256'] == c['host_module_sha256'] and sha(host['path']) == c['host_module_sha256'], 'unapproved host implementation')
    need(d['host_python'] == c['host_python'], 'host interpreter')
    policy = d['queue']; need(sha(policy['path']) == policy['sha256'], 'resource policy changed')
    need(read(policy['path']).get('schema') != 'PREPARATION_ONLY_NO_RESOURCE_CLAIM', 'resource placeholder')
    h = types.ModuleType('pinned_native_host'); h.__file__ = host['path']
    exec(compile(raw(host['path']), host['path'], 'exec'), h.__dict__)
    projected = dict(d, runtime=d['modules']['runtime'], image_sha256=d['image'])
    need(r['expected_commands']['1'] == h.command(projected, j['plan'], pin, 1), 'unreviewed docker command')
    pins = {}
    for group in (d['files'], r['hashes'], r.get('review_evidence', {})):
        for p, h in group.items():
            need(p not in pins or pins[p] == h, 'conflicting evidence pin'); pins[p] = h
    need(all(r['hashes'].get(p) == h for p, h in d['files'].items()), 'review incomplete')
    for p, h in pins.items():
        need(sha(p) == h, 'dependency changed: ' + p)
    # Native host rechecks full exact docker argv, runtime admission and locked
    # physical resource generation; this queue cannot waive any of those checks.
    cmd = [d['host_python'], '-B', '-P', host['path'], 'start', '--plan', j['plan'],
           '--sha256', pin, '--review', j['review'], '--review-sha256', rpin, '--attempt', '1']
    return dict(plan_sha256=pin, review_sha256=rpin, command=cmd,
                environment=d['host_environment'], plan=d, verified_pins=len(pins))


def launch(binding, logfile):
    env = dict(os.environ, **binding['environment'])
    with safe(logfile).open('ab') as log:
        p = subprocess.Popen(binding['command'], env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    # A failed receipt after Popen must never cause an automatic second start.
    return dict(pid=p.pid, process=proc_identity(p.pid))


def docker(name):
    r = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower():
            return None
        raise RuntimeError('Docker observation uncertain')
    return json.loads(r.stdout)[0]


def reconcile(j, rec, query=docker):
    """No launch action on this path, including missing or stale process handles."""
    d = read(j['plan']); need(sha(j['plan']) == rec['plan_sha256'], 'launched plan changed')
    h = Path(j['out']) / 'host_attempts' / '1'; receipt = h / 'LAUNCH_RECEIPT.json'
    actual = query(j['container'] + '-a1')
    if actual is None:
        need(not receipt.exists(), 'retained container missing')
        return 'launch_uncertain'
    need(receipt.exists(), 'container lacks bound receipt')
    rr = read(receipt)
    need(rr['container_id'] == actual['Id'] and rr['plan_sha256'] == rec['plan_sha256'] and type(rr['attempt']) is int and rr['attempt'] == 1, 'container receipt mismatch')
    need(rr['scientific_acceptance'] is False and rr['command'] == actual['Config']['Cmd'], 'receipt command/authority')
    need(actual['Image'] == d['image'] and actual['Name'] == '/' + j['container'] + '-a1', 'container identity')
    need(actual['HostConfig'].get('AutoRemove') is False and actual.get('RestartCount') == 0, 'retained lifecycle')
    need(any(x['PathOnHost'] == '/dev/davinci' + str(j['chip']) for x in actual['HostConfig']['Devices']), 'chip mapping')
    expected = [d['image'], 'python3', '-B', '-P', d['modules']['runtime']['path'], 'run', '--plan', j['plan'], '--sha256', rec['plan_sha256'], '--attempt', '1']
    need(actual['Config']['Cmd'] == expected[1:], 'container command differs')
    state = actual['State']
    if state['Status'] in ('running', 'created'):
        return 'running' if state['Status'] == 'running' else 'container_created'
    need(state['Status'] == 'exited' and state['Running'] is False, 'unknown physical state')
    hp = h / 'EXIT.json'; rp = Path(j['out']) / 'attempts' / '1' / 'EXIT.json'
    if not hp.exists() or not rp.exists():
        return 'exited_pending_terminal'
    ht = read(hp); rt = read(rp)
    for t in (ht, rt):
        need(t['plan_sha256'] == rec['plan_sha256'] and type(t['attempt']) is int and t['attempt'] == 1 and t['scientific_acceptance'] is False, 'terminal binding')
        need(type(t['exit_code']) is int and type(state['ExitCode']) is int and t['exit_code'] == state['ExitCode'], 'terminal exit mismatch')
    need(ht['container_id'] == actual['Id'] and ht['runner_terminal_matches'] is True, 'host terminal unmatched')
    return 'inference_complete' if state['ExitCode'] == 0 else 'inference_failed'


def tick(c, state, save, approve=approved, spawn=launch, observe=reconcile):
    for j in c['jobs']:
        rec = state['jobs'].setdefault(j['id'], dict(state='pending_review'))
        if rec.get('launch_intent'):
            try:
                rec['state'] = observe(j, rec); rec.pop('error', None)
            except Exception as e:
                rec.update(state='launch_uncertain', error=type(e).__name__ + ': ' + str(e)[:250])
            save(state); continue
        try:
            binding = approve(c, j)
            if binding is None:
                rec['state'] = 'pending_review'; save(state); continue
            rec.update(state='ready', plan_sha256=binding['plan_sha256'], review_sha256=binding['review_sha256'])
            save(state)
            allocation = read(binding['plan']['allocation'])
            if any(x['chip'] == j['chip'] for x in allocation['allocation']):
                rec['state'] = 'waiting_resource'; save(state); continue
            # This inexpensive observation does not confer resource ownership.
            # The existing adapter still rechecks exact generation/physical
            # device state under its allocation lock at the actual claim.
            need(len([x for x in allocation['free'] if x['chip'] == j['chip']]) == 1, 'free generation missing')
            # Existing native start intent, even without our state, quarantines
            # this job. Host start.lock is a second independent at-most-once guard.
            need(not (Path(j['out']) / 'host_attempts' / '1').exists(), 'host attempt already exists; reconcile')
            rec.update(state='launch_intent', launch_intent=True, command=binding['command'], utc_seconds=time.time())
            save(state)  # fsynced before any Popen
            rec['launcher'] = spawn(binding, str(Path(c['output']) / (j['id'] + '.launcher.log')))
            rec['state'] = 'launch_submitted'; save(state)
        except Exception as e:
            rec.update(state='launch_uncertain' if rec.get('launch_intent') else 'review_rejected',
                       error=type(e).__name__ + ': ' + str(e)[:250])
            save(state)
    return state


def run(config, pin, once=False):
    need(sha(config) == pin, 'queue config changed'); c = validate(read(config))
    root = safe(c['output']); root.mkdir(parents=True, exist_ok=True)
    lockfd = os.open(root / 'dispatcher.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lockfd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = root / 'STATE.json'
        state = read(path) if path.exists() else dict(config_sha256=pin, jobs={})
        need(state['config_sha256'] == pin and set(state['jobs']) <= {j['id'] for j in c['jobs']}, 'state/config differs')
        wake = threading.Event(); stopped = threading.Event()
        signal.signal(signal.SIGUSR1, lambda *_: wake.set())
        def stop(*_):
            stopped.set(); wake.set()
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        put(root / 'SERVICE.json', dict(process=proc_identity(os.getpid()), config_sha256=pin))
        put(root / 'RELAUNCH.json', dict(command=[sys.executable, '-B', '-P', str(Path(__file__).resolve()), '--config', config, '--sha256', pin], resume='same config and state only; launch intents never replayed'))
        def save(s):
            put(path, s)
        def beat():
            while not stopped.wait(30):
                put(root / 'heartbeat.json', dict(utc_seconds=time.time(), jobs=len(state['jobs']), scientific_acceptance=False))
        heartbeat = threading.Thread(target=beat, daemon=True); heartbeat.start()
        rc = 1
        try:
            while not stopped.is_set():
                need(sha(config) == pin, 'queue changed while active')
                wake.clear(); tick(c, state, save)
                put(root / 'digest.json', dict(utc_seconds=time.time(), jobs=state['jobs'], scientific_acceptance=False))
                lines = ['# Reviewed successor dispatcher', '', '| Job | State |', '| --- | --- |']
                lines.extend('| ' + j['id'] + ' | ' + state['jobs'][j['id']]['state'] + ' |' for j in c['jobs'])
                (root / 'digest.md').write_text('\n'.join(lines) + '\n')
                if once:
                    break
                wake.wait(c['poll_seconds'])
            rc = 0
        finally:
            stopped.set(); heartbeat.join(2)
            put(root / 'EXIT.json', dict(exit_code=rc, utc_seconds=time.time(), config_sha256=pin, scientific_acceptance=False, scope='dispatcher_not_experiment'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True); ap.add_argument('--sha256', required=True); ap.add_argument('--once', action='store_true')
    a = ap.parse_args(); run(a.config, a.sha256, a.once)
