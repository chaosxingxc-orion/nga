#!/usr/bin/env python3
"""Finite evidence-bound evaluation successors; no allocation mutation or acceptance."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def next_pin(job):
    plan = load(job['next_execution'])
    if job.get('next_kind', 'evaluation') == 'training':
        require(plan.get('schema') == 'r3-engineering-k1-plan-v1', 'engineering training successor required')
        value = dict(plan, review_sha256='PENDING')
        return hashlib.sha256((json.dumps(value, indent=2, sort_keys=True) + '\n').encode()).hexdigest()
    require(job.get('next_kind', 'evaluation') == 'evaluation', 'unknown successor kind')
    return sha(job['next_execution'])
def require(ok, why):
    if not ok: raise RuntimeError(why)

def atomic(p, data):
    p = Path(p); temp = p.with_suffix('.pending')
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n'); temp.replace(p)

def inspect(name):
    r = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower(): return None
        raise RuntimeError('Docker observation uncertain')
    return json.loads(r.stdout)[0]

def process_matches(receipt, proc_root=Path('/proc')):
    pid = receipt['pid']; require(type(pid) is int and pid > 0, 'invalid pid')
    try: actual = (proc_root / str(pid) / 'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    except FileNotFoundError: return False
    return actual == [os.fsencode(x) for x in receipt['command']]

def verify(path, pin):
    require(sha(path) == pin, 'successor manifest changed')
    d = load(path)
    require(d['schema'] == 'r3-eval-successor-v1' and d['scientific_acceptance'] is False and d['test_read'] is False, 'scope differs')
    require(d['controller'] == str(Path(__file__).resolve()) and sha(__file__) == d['controller_sha256'], 'controller differs')
    jobs = d['jobs']; require(jobs and len({j['id'] for j in jobs}) == len(jobs), 'empty or duplicate jobs')
    require(len({j['next_execution'] for j in jobs}) == len(jobs), 'duplicate successors')
    for j in jobs:
        require(type(j['chip']) is int and 0 <= j['chip'] < 8, 'invalid chip')
        require(next_pin(j) == j['next_sha256'], 'next plan changed')
        p = load(j['next_execution'])
        require(p['chip'] == j['chip'] and p['scientific_acceptance'] is False and p['test_read'] is False, 'next scope/chip differs')
        files = p['files'] if j.get('next_kind') == 'training' else p['tools']
        require(sha(p['launcher']) == files[p['launcher']], 'next launcher changed')
    return d

def predecessor(job):
    kind = job.get('previous_kind', 'evaluation')
    require(kind in ('evaluation', 'training'), 'unknown predecessor kind')
    root = Path(job['previous_eval'])
    terminal = root / ('TRAIN_EXIT.json' if kind == 'training' else 'ENGINEERING_EVAL_EXIT.json')
    if not terminal.exists(): return None
    end = load(terminal); number = end.get('attempt')
    require(type(number) is int and number > 0, 'invalid previous attempt')
    attempt = root / 'attempts' / str(number)
    if not (attempt / 'RELEASE.json').exists(): return None
    plan_path = root / ('plan.json' if kind == 'training' else 'execution.json'); plan = load(plan_path)
    require(plan['chip'] == job['chip'] and plan['out'] == str(root), 'previous plan ownership differs')
    supervisor = load(root / 'SUPERVISOR_RECEIPT.json')
    if kind == 'training':
        require(plan.get('schema') == 'r3-engineering-k1-plan-v1', 'engineering predecessor required')
        pin = hashlib.sha256((json.dumps(dict(plan, review_sha256='PENDING'), indent=2, sort_keys=True) + '\n').encode()).hexdigest()
    else:
        pin = sha(plan_path)
    require(supervisor['command'] == [sys.executable, '-P', plan['launcher'], 'supervise', '--plan', str(plan_path),
            '--sha256', pin, '--attempt', str(number)], 'previous supervisor identity differs')
    # A later live retry supersedes the global marker. Never hand off mid-retry.
    require(load(attempt / 'EXIT.json') == end, 'previous markers disagree')
    proof = load(attempt / 'RELEASE.json'); receipt = load(attempt / 'LAUNCH_RECEIPT.json')
    actual = inspect(plan['container'] + '-a' + str(number))
    require(actual and actual['Id'] == receipt['id'] == proof['container_id'], 'previous retained identity differs')
    require(actual['State']['Status'] in ('exited', 'dead'), 'previous container not terminal')
    require(actual['State']['ExitCode'] == end['exit_code'] == proof['exit_code'], 'previous exit differs')
    require(proof['chip'] == job['chip'] and proof['run'] == plan['run'] and proof['scientific_acceptance'] is False, 'previous release scope differs')
    return {'attempt': number, 'exit_code': end['exit_code'], 'container_id': actual['Id'], 'release_sha256': sha(attempt / 'RELEASE.json')}

def tick(job):
    require(next_pin(job) == job['next_sha256'], 'next plan changed')
    p = load(job['next_execution']); out = Path(p['out'])
    receipt_path = out / 'SUPERVISOR_RECEIPT.json'
    intent_path = out / 'SUCCESSOR_START_INTENT.json'
    if receipt_path.exists():
        require(intent_path.exists(), 'successor started outside this handoff')
        receipt = load(receipt_path)
        expected = [sys.executable, '-P', p['launcher'], 'supervise', '--plan', job['next_execution'],
                    '--sha256', job['next_sha256'], '--attempt', '1']
        require(receipt['command'] == expected, 'next supervisor command differs')
        launch = out / 'attempts/1/LAUNCH_RECEIPT.json'
        if launch.exists():
            actual = inspect(p['container'] + '-a1')
            require(actual and actual['Id'] == load(launch)['id'], 'next retained identity differs')
            if actual['State']['Status'] in ('running', 'exited', 'dead'):
                return {'status': 'handed_off', 'container_id': actual['Id'], 'previous': load(intent_path)['previous']}
        if process_matches(receipt): return {'status': 'supervisor_live', 'pid': receipt['pid']}
        return {'status': 'needs_repair', 'reason': 'successor supervisor absent; no automatic restart'}
    if intent_path.exists(): return {'status': 'needs_repair', 'reason': 'start intent without receipt; do not duplicate'}
    previous = predecessor(job)
    if previous is None: return {'status': 'waiting_previous_release'}
    # The successor supervisor waits for the ledger; this controller never claims.
    command = [sys.executable, '-P', p['launcher'], 'start', '--plan', job['next_execution'], '--sha256', job['next_sha256']]
    subprocess.run([sys.executable, '-P', p['launcher'], 'verify', '--plan', job['next_execution'], '--sha256', job['next_sha256']], check=True, capture_output=True, timeout=120)
    atomic(intent_path, {'command': command, 'previous': previous, 'utc_seconds': time.time()})
    with (out / 'successor-launch.log').open('ab') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    return {'status': 'launch_requested', 'previous': previous}

def watch(path, pin):
    with (path.parent / 'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            d = verify(path, pin); states = {}
            for j in d['jobs']:
                try: states[j['id']] = tick(j)
                except Exception as e: states[j['id']] = {'status': 'observation_or_launch_uncertain', 'error': str(e)[:300]}
            value = {'utc_seconds': time.time(), 'jobs': states, 'scientific_acceptance': False, 'test_read': False}
            atomic(path.parent / 'digest.json', value)
            if all(x['status'] == 'handed_off' for x in states.values()):
                atomic(path.parent / 'DONE.json', value); return
            time.sleep(15)

def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('op', choices=('verify', 'start', 'watch'))
    ap.add_argument('--manifest', required=True); ap.add_argument('--sha256', required=True); a = ap.parse_args()
    path = Path(a.manifest).resolve(); verify(path, a.sha256)
    if a.op == 'verify': print('SUCCESSOR_VERIFIED'); return
    require(socket.gethostname() == 'k8s-node1', 'host 175 only')
    if a.op == 'watch': watch(path, a.sha256); return
    command = [sys.executable, '-P', str(Path(__file__).resolve()), 'watch', '--manifest', str(path), '--sha256', a.sha256]
    with (path.parent / 'start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = path.parent / 'SERVICE.json'
        if receipt.exists():
            old = load(receipt); require(old['command'] == command and process_matches(old), 'prior service not live; inspect before restart')
            print(json.dumps({'status': 'ALREADY_LIVE', 'pid': old['pid']})); return
        with (path.parent / 'service.log').open('ab') as log:
            p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atomic(receipt, {'pid': p.pid, 'command': command})
        atomic(path.parent / 'RELAUNCH.json', {'command': [sys.executable, '-P', str(Path(__file__).resolve()), 'start', '--manifest', str(path), '--sha256', a.sha256]})
        print(json.dumps({'status': 'STARTED', 'pid': p.pid}))

if __name__ == '__main__': main()
