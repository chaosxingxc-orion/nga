#!/usr/bin/env python3
"""Ordered, detached CPU selection reporting; never claims devices or reads tests.

Only successfully released inference jobs become ready. A lost worker without a
terminal is a repair condition, never permission to duplicate CPU execution.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def atomic(path, value):
    path = Path(path)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def process_matches(receipt, proc_root=Path('/proc')):
    pid = receipt['pid']
    require(type(pid) is int and pid > 0, 'invalid PID')
    try:
        actual = (proc_root / str(pid) / 'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    except FileNotFoundError:
        return False
    return actual == [os.fsencode(x) for x in receipt['command']]


def verify(path, pin):
    require(sha(path) == pin, 'queue manifest changed')
    doc = load(path)
    require(doc['schema'] == 'r3-cpu-report-queue-v1' and doc['test_read'] is False
            and doc['scientific_acceptance'] is False, 'queue scope differs')
    require(doc['controller'] == str(Path(__file__).resolve()) and
            sha(__file__) == doc['controller_sha256'], 'controller identity differs')
    require(sha(doc['report_tool']) == doc['report_tool_sha256'], 'report tool changed')
    closure = Path(doc['closure'])
    require(sha(closure / 'manifest.json') == doc['closure_sha256'], 'closure manifest changed')
    for entry in load(closure / 'manifest.json')['code'].values():
        require(sha(entry['snapshot']) == entry['sha256'], 'frozen closure code changed')
    jobs = doc['jobs']
    require(jobs and len({j['id'] for j in jobs}) == len(jobs), 'empty or duplicate jobs')
    for key in ('eval_out', 'output'):
        require(len({j[key] for j in jobs}) == len(jobs), 'duplicate ' + key)
    for job in jobs:
        require(re.fullmatch(r'[A-Za-z0-9_-]+', job['id']), 'unsafe job ID')
        require(Path(job['eval_out']).is_absolute() and Path(job['output']).is_absolute(), 'absolute paths required')
        require(Path(job['output']).name == 'selection_report.json', 'selection report filename required')
    return doc


def ready(job):
    root = Path(job['eval_out'])
    terminal = root / 'ENGINEERING_EVAL_EXIT.json'
    if not terminal.exists():
        return 'waiting_inference'
    end = load(terminal)
    number = end.get('attempt')
    require(type(number) is int and number > 0, 'invalid inference attempt')
    if end['exit_code'] != 0:
        return 'inference_failed'
    attempt = root / 'attempts' / str(number)
    if not (attempt / 'RELEASE.json').exists():
        return 'waiting_release'
    require(load(attempt / 'EXIT.json') == end, 'inference terminal mismatch')
    release = load(attempt / 'RELEASE.json')
    launch = load(attempt / 'LAUNCH_RECEIPT.json')
    plan_path = root / 'execution.json'
    plan = load(plan_path)
    supervisor = load(root / 'SUPERVISOR_RECEIPT.json')
    command = supervisor['command']
    require(isinstance(command, list) and len(command) == 10 and
            command[1:] == ['-P', plan['launcher'], 'supervise', '--plan', str(plan_path),
                            '--sha256', sha(plan_path), '--attempt', str(number)],
            'inference supervisor generation differs')
    require(release['exit_code'] == 0 and release['container_id'] == launch['id']
            and release['run'] == plan['run'] and release['chip'] == plan['chip']
            and release['scientific_acceptance'] is False, 'inference release mismatch')
    return 'ready'


def report_command(doc, job):
    return [sys.executable, '-P', doc['report_tool'], '--run', str(Path(job['eval_out']) / 'results'),
            '--frozen-code-dir', str(Path(doc['closure']) / 'r3_code'), '--output', job['output']]


def worker_command(path, pin, job_id):
    return [sys.executable, '-P', str(Path(__file__).resolve()), 'worker',
            '--manifest', str(path), '--sha256', pin, '--job', job_id]


def workdir(path, job):
    return path.parent / 'jobs' / job['id']


def worker(path, pin, job_id):
    doc = verify(path, pin)
    job = next(j for j in doc['jobs'] if j['id'] == job_id)
    root = workdir(path, job)
    require(ready(job) == 'ready', 'inference not ready')
    require(not (root / 'EXIT.json').exists(), 'worker already terminal')
    require(not Path(job['output']).exists(), 'fresh report output required')
    command = report_command(doc, job)
    rc, process = 125, None
    try:
        with (root / 'report.log').open('ab', buffering=0) as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            atomic(root / 'CHILD.json', {'pid': process.pid, 'command': command})
            while process.poll() is None:
                atomic(root / 'heartbeat.json', {'utc_seconds': time.time(), 'pid': process.pid,
                       'status': 'reporting'})
                time.sleep(1)
            rc = process.returncode
            if rc < 0:
                rc = 128 - rc
            if rc == 0:
                report = load(job['output'])
                require(report.get('schema') == 'r3-selection-report-v1' and
                        report.get('scientific_acceptance') is False, 'report output scope differs')
    except BaseException:
        rc = 125
        with (root / 'report.log').open('a') as log:
            traceback.print_exc(file=log)
        # A reporting child is independently observable even if this worker dies.
        # Do not kill or restart it based on missing parent observations.
    finally:
        if process is not None and process.poll() is None:
            process.wait()
        atomic(root / 'EXIT.json', {'exit_code': rc, 'utc_seconds': time.time(),
               'output_sha256': sha(job['output']) if rc == 0 else None,
               'scientific_acceptance': False})
    return rc


def observe(path, pin, job):
    root = workdir(path, job)
    terminal = root / 'EXIT.json'
    if terminal.exists():
        end = load(terminal)
        if end['exit_code'] == 0:
            require(sha(job['output']) == end['output_sha256'], 'completed report changed')
        return {'status': 'done' if end['exit_code'] == 0 else 'report_failed', 'exit_code': end['exit_code']}
    receipt = root / 'WORKER.json'
    if receipt.exists():
        value = load(receipt)
        require(value['command'] == worker_command(path, pin, job['id']), 'worker command differs')
        if process_matches(value):
            return {'status': 'reporting', 'pid': value['pid']}
        child = root / 'CHILD.json'
        if child.exists() and process_matches(load(child)):
            return {'status': 'orphan_child_live', 'pid': load(child)['pid']}
        return {'status': 'needs_repair', 'reason': 'worker absent or PID reused without terminal'}
    if (root / 'START_INTENT.json').exists():
        return {'status': 'needs_repair', 'reason': 'start intent without receipt; no duplicate execution'}
    return {'status': ready(job)}


def tick(path, pin, doc):
    states = {}
    for job in doc['jobs']:
        try:
            states[job['id']] = observe(path, pin, job)
        except Exception as error:
            states[job['id']] = {'status': 'observation_uncertain', 'error': str(error)[:300]}
    # Uncertain workers may still consume CPU. Stop new starts until inspected.
    busy = any(x['status'] in ('reporting', 'orphan_child_live', 'needs_repair', 'observation_uncertain') for x in states.values())
    if not busy:
        for job in doc['jobs']:
            if states[job['id']]['status'] != 'ready':
                continue
            root = workdir(path, job); root.mkdir(parents=True, exist_ok=True)
            command = worker_command(path, pin, job['id'])
            atomic(root / 'START_INTENT.json', {'command': command, 'utc_seconds': time.time()})
            with (root / 'worker.log').open('ab') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                           stdin=subprocess.DEVNULL, start_new_session=True)
            atomic(root / 'WORKER.json', {'pid': process.pid, 'command': command})
            states[job['id']] = {'status': 'reporting', 'pid': process.pid}
            break
    return states


def watch(path, pin):
    with (path.parent / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            doc = verify(path, pin)
            states = tick(path, pin, doc)
            digest = {'utc_seconds': time.time(), 'jobs': states, 'scientific_acceptance': False}
            atomic(path.parent / 'digest.json', digest)
            if all(x['status'] in ('done', 'report_failed', 'inference_failed') for x in states.values()):
                atomic(path.parent / 'DONE.json', digest); return
            time.sleep(15)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=('verify', 'start', 'watch', 'worker'))
    p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True); p.add_argument('--job')
    a = p.parse_args(); path = Path(a.manifest).resolve()
    verify(path, a.sha256)
    if a.op == 'verify': print('CPU_QUEUE_VERIFIED'); return 0
    if a.op == 'worker': return worker(path, a.sha256, a.job)
    if a.op == 'watch': watch(path, a.sha256); return 0
    command = [sys.executable, '-P', str(Path(__file__).resolve()), 'watch', '--manifest', str(path), '--sha256', a.sha256]
    with (path.parent / 'start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = path.parent / 'SERVICE.json'
        if receipt.exists():
            previous = load(receipt)
            require(previous['command'] == command and process_matches(previous), 'prior service missing; inspect before restart')
            print(json.dumps({'status': 'ALREADY_LIVE', 'pid': previous['pid']})); return 0
        with (path.parent / 'service.log').open('ab') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atomic(receipt, {'pid': process.pid, 'command': command})
        atomic(path.parent / 'RELAUNCH.json', {'command': [sys.executable, '-P', str(Path(__file__).resolve()), 'start', '--manifest', str(path), '--sha256', a.sha256]})
        print(json.dumps({'status': 'STARTED', 'pid': process.pid}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
