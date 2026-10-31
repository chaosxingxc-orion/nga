#!/usr/bin/env python3
"""Finite, frozen engineering train -> Track K inference queue on host 175.

No test scoring or scientific acceptance. Uncertain observations never trigger a
restart. An interrupted launch intent without a receipt requires operator repair.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def atomic(path, value):
    path = Path(path)
    temp = path.with_suffix('.pending')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def process_matches(receipt, proc_root=Path('/proc')):
    """Inspect actual command bytes; PID reuse or absent process is not live."""
    pid = receipt['pid']
    require(type(pid) is int and pid > 0, 'invalid supervisor PID')
    try:
        actual = (proc_root / str(pid) / 'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    except FileNotFoundError:
        return False
    return actual == [os.fsencode(x) for x in receipt['command']]


def verify_manifest(path, pin):
    require(sha(path) == pin, 'queue manifest changed')
    doc = load(path)
    require(doc['schema'] == 'r3-posttrain-queue-v1' and doc['test_read'] is False
            and doc['scientific_acceptance'] is False, 'queue scope differs')
    expected = {'r3_posttrain_eval_queue.py', 'r3_posttrain_eval_plan.py',
                'r3_posttrain_eval_launcher.py', 'r3_resource_adapter.py'}
    require({Path(x).name for x in doc['tools']} == expected, 'tool closure differs')
    root = Path(__file__).resolve().parent
    for filename, digest in doc['tools'].items():
        p = Path(filename)
        require(p.is_absolute() and p.parent.resolve() == root and not p.is_symlink(), 'tool outside frozen closure')
        require(sha(p) == digest, 'queue tool changed')
    require(str(Path(__file__).resolve()) in doc['tools'], 'different queue executable')
    require(sha(Path(doc['closure']) / 'manifest.json') == doc['closure_sha256'], 'evaluator closure changed')
    jobs = doc['jobs']
    require(bool(jobs) and len({j['id'] for j in jobs}) == len(jobs), 'empty or duplicate jobs')
    for key in ('out', 'container', 'training'):
        require(len({j[key] for j in jobs}) == len(jobs), 'duplicate job ' + key)
    for job in jobs:
        require(type(job['chip']) is int and 0 <= job['chip'] < 8, 'invalid chip')
        require(sha(Path(job['training']) / 'plan.json') == job['training_plan_sha256'], 'training plan changed')
        require(load(Path(job['training']) / 'plan.json')['chip'] == job['chip'], 'training chip differs')
    return doc


def tick(job, closure, prepare, launcher, resource):
    training, out = Path(job['training']), Path(job['out'])
    # Never infer training completion from containers or elapsed time.
    terminal = training / 'TRAIN_EXIT.json'
    if not terminal.exists():
        return {'status': 'waiting_training'}
    if load(terminal)['exit_code'] != 0:
        return {'status': 'training_failed', 'exit_code': load(terminal)['exit_code']}
    spec_path = out / 'plan.json'
    if not spec_path.exists():
        state = prepare.prepare(training, Path(closure), out)
        if state['status'] != 'prepared':
            return state
    spec = load(spec_path)
    require(spec['training'] == str(training), 'specification belongs to another training run')
    require(spec['training_variant']['training_plan_sha256'] == job['training_plan_sha256'], 'spec training identity differs')
    execution = out / 'execution.json'
    if not execution.exists():
        if (out / 'execution-tools').exists():
            return {'status': 'needs_repair', 'reason': 'partial bind; preserve evidence and repair explicitly'}
        launcher.bind(spec_path, job['chip'], job['container'])
    plan = load(execution)
    require(plan['chip'] == job['chip'] and plan['container'] == job['container']
            and plan['spec'] == str(spec_path), 'execution identity differs')
    pin_path = out / 'QUEUE_EXECUTION_PIN.json'
    if not pin_path.exists():
        # Frozen launcher independently validates its spec, dependency closure and scope.
        subprocess.run([sys.executable, '-P', plan['launcher'], 'verify', '--plan', str(execution),
                        '--sha256', sha(execution)], check=True, capture_output=True, timeout=120)
        atomic(pin_path, {'sha256': sha(execution)})
    pin = load(pin_path)['sha256']
    require(sha(execution) == pin, 'bound execution changed')
    receipt_path = out / 'SUPERVISOR_RECEIPT.json'
    receipt, number = None, 1
    if receipt_path.exists():
        receipt = load(receipt_path)
        command = receipt['command']
        prefix = [sys.executable, '-P', plan['launcher'], 'supervise', '--plan', str(execution),
                  '--sha256', pin, '--attempt']
        require(isinstance(command, list) and len(command) == len(prefix) + 1
                and command[:-1] == prefix, 'supervisor receipt command differs')
        require(isinstance(command[-1], str) and command[-1].isdigit(), 'invalid supervisor attempt')
        number = int(command[-1])
        require(number >= 1 and str(number) == command[-1], 'invalid supervisor attempt')
        # A later supervisor is admitted only after every previous generation
        # failed and released. No retry is launched automatically by this queue.
        for previous in range(1, number):
            prior = out / 'attempts' / str(previous)
            require((prior / 'EXIT.json').exists() and (prior / 'RELEASE.json').exists(),
                    'previous attempt not terminal and released')
            terminal, released = load(prior / 'EXIT.json'), load(prior / 'RELEASE.json')
            require(terminal.get('attempt') == previous and terminal['exit_code'] != 0
                    and released['exit_code'] == terminal['exit_code']
                    and released['chip'] == job['chip'] and released['run'] == plan['run'],
                    'previous attempt release identity differs')
    attempt = out / 'attempts' / str(number)
    if (attempt / 'SUPERVISOR_FAILED.json').exists():
        return {'status': 'needs_repair', 'reason': 'supervisor failure; see bounded failure receipt', 'attempt': number}
    end, release = out / 'ENGINEERING_EVAL_EXIT.json', attempt / 'RELEASE.json'
    marker = load(end) if end.exists() else None
    if marker:
        require(type(marker.get('attempt')) is int and 1 <= marker['attempt'] <= number,
                'terminal attempt differs from supervisor')
    if marker and marker['attempt'] == number and release.exists():
        require(receipt is not None, 'terminal lacks supervisor identity')
        proof = load(release)
        local_marker = load(attempt / 'EXIT.json')
        require(local_marker == marker, 'global and attempt terminal differ')
        launch = load(attempt / 'LAUNCH_RECEIPT.json')
        actual = resource.docker_inspect(job['container'] + '-a' + str(number))
        require(actual and actual['Id'] == launch['id'] == proof['container_id'], 'terminal container identity differs')
        require(actual['State']['Status'] in ('exited', 'dead'), 'terminal container still live')
        require(actual['State']['ExitCode'] == marker['exit_code'] == proof['exit_code'], 'terminal exit differs')
        require(proof['chip'] == job['chip'] and proof['run'] == plan['run'], 'release ownership differs')
        return {'status': 'done' if marker['exit_code'] == 0 else 'evaluation_failed', 'exit_code': marker['exit_code'], 'attempt': number}
    if receipt is not None:
        if process_matches(receipt):
            return {'status': 'supervisor_live', 'pid': receipt['pid'], 'attempt': number}
        return {'status': 'needs_repair', 'reason': 'supervisor absent or PID reused; no automatic restart', 'attempt': number}
    intent = out / 'QUEUE_START_INTENT.json'
    if intent.exists():
        return {'status': 'needs_repair', 'reason': 'launch requested without receipt; do not duplicate'}
    command = [sys.executable, '-P', plan['launcher'], 'start', '--plan', str(execution), '--sha256', pin]
    atomic(intent, {'command': command, 'utc_seconds': time.time()})
    with (out / 'queue-launch.log').open('ab') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    return {'status': 'launch_requested', 'plan': str(execution)}


def watch(path, pin):
    out = path.parent
    with (out / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root = Path(__file__).parent
        prepare = module(root / 'r3_posttrain_eval_plan.py', 'prepare')
        launcher = module(root / 'r3_posttrain_eval_launcher.py', 'launcher')
        resource = module(root / 'r3_resource_adapter.py', 'resource')
        while True:
            doc = verify_manifest(path, pin)
            states = {}
            for job in doc['jobs']:
                try:
                    states[job['id']] = tick(job, doc['closure'], prepare, launcher, resource)
                except Exception as error:
                    states[job['id']] = {'status': 'observation_or_execution_uncertain', 'error': str(error)[:300]}
            digest = {'utc_seconds': time.time(), 'jobs': states, 'test_read': False, 'scientific_acceptance': False}
            atomic(out / 'digest.json', digest)
            if all(x['status'] in ('done', 'evaluation_failed', 'training_failed', 'not_complete_training') for x in states.values()):
                atomic(out / 'DONE.json', digest)
                return
            time.sleep(30)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=('start', 'watch', 'verify'))
    p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True)
    a = p.parse_args(); path = Path(a.manifest).resolve()
    verify_manifest(path, a.sha256)
    if a.op == 'verify':
        print(json.dumps({'status': 'QUEUE_VERIFIED', 'scientific_acceptance': False})); return
    require(socket.gethostname() == 'k8s-node1', 'host 175 only')
    if a.op == 'watch':
        watch(path, a.sha256); return
    with (path.parent / 'queue-start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = path.parent / 'SERVICE.json'
        command = [sys.executable, '-P', str(Path(__file__).resolve()), 'watch', '--manifest', str(path), '--sha256', a.sha256]
        if receipt.exists():
            old = load(receipt)
            require(old['command'] == command and process_matches(old), 'existing service identity not live; inspect before restart')
            print(json.dumps({'status': 'ALREADY_LIVE', 'pid': old['pid']})); return
        with (path.parent / 'service.log').open('ab') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atomic(receipt, {'pid': child.pid, 'command': command})
        atomic(path.parent / 'RELAUNCH.json', {'command': [sys.executable, '-P', str(Path(__file__).resolve()), 'start', '--manifest', str(path), '--sha256', a.sha256]})
        print(json.dumps({'status': 'STARTED', 'pid': child.pid}))


if __name__ == '__main__':
    main()
