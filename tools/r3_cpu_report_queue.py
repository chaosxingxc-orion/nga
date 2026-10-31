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
    reports = [j for j in jobs if j.get('kind', 'report') == 'report']
    comparisons = [j for j in jobs if j.get('kind') == 'comparison']
    r0_reports = [j for j in jobs if j.get('kind') == 'r0_report']
    prechecks = [j for j in jobs if j.get('kind') == 'k0_prechecks']
    require(len(reports) + len(comparisons) + len(r0_reports) + len(prechecks) == len(jobs), 'unknown CPU job kind')
    if prechecks:
        config = doc['k0_prechecks']
        require(Path(config['tool']).is_absolute() and sha(config['tool']) == config['tool_sha256'], 'precheck tool changed')
        report_ids = {j['id'] for j in reports}
        for job in prechecks:
            require(job['baseline'] in report_ids, 'precheck baseline must be a report')
            require(Path(job['model']).is_absolute(), 'absolute precheck model required')
            require(Path(job['output']).name == 'K0_PRECHECKS.json', 'precheck output differs')
    if r0_reports:
        require(len(r0_reports) == 1, 'one full R0 report required')
        config = doc['r0_report']
        for filename, digest in config['files'].items():
            require(Path(filename).is_absolute() and sha(filename) == digest, 'R0 CPU dependency changed')
        require(config['tool'] in config['files'] and
                str(Path(config['tool']).with_name('r3_r0_prepare.py')) in config['files'] and
                str(Path(config['tool']).with_name('r0rescore_verify.py')) in config['files'], 'R0 tools not pinned')
        require(sha(config['preparation']) == config['preparation_sha256'], 'R0 preparation changed')
        for job in r0_reports:
            require(Path(job['eval_out']).is_absolute() and
                    Path(job['output']) == Path(job['eval_out']) / 'R0RESCORE_COMPLETE.json', 'R0 output differs')
            require(sha(Path(job['eval_out']) / 'execution.json') == config['execution_sha256'], 'R0 execution changed')
    for key in ('eval_out',):
        require(len({j[key] for j in reports}) == len(reports), 'duplicate ' + key)
    for key in ('output',):
        require(len({j[key] for j in jobs}) == len(jobs), 'duplicate ' + key)
    for job in jobs:
        require(re.fullmatch(r'[A-Za-z0-9_-]+', job['id']), 'unsafe job ID')
        require(Path(job['output']).is_absolute(), 'absolute output required')
        if job.get('kind', 'report') == 'report':
            require(Path(job['eval_out']).is_absolute(), 'absolute evaluation path required')
            require(Path(job['output']).name == 'selection_report.json', 'selection report filename required')
    if comparisons:
        config = doc['comparison']
        for key in ('tool', 'selector'):
            require(Path(config[key]).is_absolute() and sha(config[key]) == config[key + '_sha256'],
                    'comparison code changed')
        report_ids = {j['id'] for j in reports}
        r0_ids = {j['id'] for j in r0_reports}
        for job in comparisons:
            require(len(job['candidate']) == 2 and len(set(job['candidate'])) == 2, 'two candidate reports required')
            require(not job.get('incumbent') or len(job['incumbent']) == 2 and len(set(job['incumbent'])) == 2,
                    'two incumbent reports required')
            require(set(job['candidate'] + [job['baseline']] + job.get('incumbent', [])) <= report_ids,
                    'comparison dependency is not a report job')
            require(not job.get('r0_report') or job['r0_report'] in r0_ids, 'invalid R0 dependency')
            require(Path(job['output']).name == 'development_comparison.json', 'comparison output filename required')
    return doc


def ready(job):
    root = Path(job['eval_out'])
    terminal = root / 'ENGINEERING_EVAL_EXIT.json'
    if not terminal.exists():
        return 'waiting_inference'
    end = load(terminal)
    ended_number = end.get('attempt')
    require(type(ended_number) is int and ended_number > 0, 'invalid inference attempt')
    plan_path = root / 'execution.json'
    plan = load(plan_path)
    supervisor = load(root / 'SUPERVISOR_RECEIPT.json')
    command = supervisor['command']
    require(isinstance(command, list) and len(command) == 10 and
            command[1:9] == ['-P', plan['launcher'], 'supervise', '--plan', str(plan_path),
                            '--sha256', sha(plan_path), '--attempt'] and
            isinstance(command[-1], str) and command[-1].isdigit(),
            'inference supervisor generation differs')
    number = int(command[-1])
    require(number >= 1 and str(number) == command[-1] and ended_number <= number,
            'inference terminal generation differs')

    def released(attempt_number, marker):
        attempt = root / 'attempts' / str(attempt_number)
        require(marker.get('attempt') == attempt_number, 'inference terminal mismatch')
        require(load(attempt / 'EXIT.json') == marker, 'inference terminal mismatch')
        release = load(attempt / 'RELEASE.json')
        launch = load(attempt / 'LAUNCH_RECEIPT.json')
        require(release['exit_code'] == marker['exit_code'] and release['container_id'] == launch['id']
                and release['run'] == plan['run'] and release['chip'] == plan['chip']
                and release['scientific_acceptance'] is False, 'inference release mismatch')

    for previous in range(1, number):
        marker = load(root / 'attempts' / str(previous) / 'EXIT.json')
        require(marker['exit_code'] != 0, 'retry after successful inference')
        released(previous, marker)
        if previous == ended_number:
            require(marker == end, 'inference terminal mismatch')
    if ended_number < number:
        # Supervisor runs on host 175; this CPU service may run elsewhere.
        # A newer receipt is reason to wait, never proof of liveness or success.
        return 'waiting_inference'
    if not (root / 'attempts' / str(number) / 'RELEASE.json').exists():
        return 'waiting_release'
    released(number, end)
    return 'ready' if end['exit_code'] == 0 else 'inference_failed'


def comparison_dependencies(job):
    if job.get('kind') == 'k0_prechecks':
        return [job['baseline']]
    return job['candidate'] + [job['baseline']] + job.get('incumbent', []) + ([job['r0_report']] if job.get('r0_report') else [])


def job_ready(path, doc, job):
    if job.get('kind', 'report') in ('report', 'r0_report'):
        return ready(job)
    by_id = {j['id']: j for j in doc['jobs']}
    for name in comparison_dependencies(job):
        dependency = by_id[name]
        terminal = workdir(path, dependency) / 'EXIT.json'
        if not terminal.exists():
            return 'waiting_reports'
        end = load(terminal)
        if end['exit_code'] != 0:
            return 'comparison_blocked'
        require(sha(dependency['output']) == end['output_sha256'], 'dependency report changed')
    return 'ready'


def report_command(doc, job):
    if job.get('kind') == 'k0_prechecks':
        baseline = next(j for j in doc['jobs'] if j['id'] == job['baseline'])
        return [sys.executable, '-P', doc['k0_prechecks']['tool'],
                '--k0-report', baseline['output'], '--report-tool', doc['report_tool'],
                '--report-tool-sha256', doc['report_tool_sha256'],
                '--frozen-code-dir', str(Path(doc['closure'])/'r3_code'),
                '--closure-sha256', doc['closure_sha256'], '--model', job['model'],
                '--out', str(Path(job['output']).parent)]
    if job.get('kind') == 'r0_report':
        config = doc['r0_report']
        return [sys.executable, '-P', config['tool'], '--run', job['eval_out'],
                '--preparation', config['preparation'], '--sha256', config['preparation_sha256'],
                '--execution-sha256', config['execution_sha256']]
    if job.get('kind') == 'comparison':
        config = doc['comparison']; by_id = {j['id']: j for j in doc['jobs']}
        command = [sys.executable, '-P', config['tool'], '--candidate',
                   *[by_id[x]['output'] for x in job['candidate']], '--baseline', by_id[job['baseline']]['output'],
                   '--frozen-code-dir', str(Path(doc['closure']) / 'r3_code'),
                   '--selector', config['selector'], '--selector-sha256', config['selector_sha256'],
                   '--report-tool', doc['report_tool'], '--report-tool-sha256', doc['report_tool_sha256'],
                   '--output', job['output']]
        if job.get('incumbent'):
            command += ['--incumbent', *[by_id[x]['output'] for x in job['incumbent']]]
        if job.get('r0_report'):
            command += ['--r0-run', by_id[job['r0_report']]['eval_out'],
                        '--r0-execution-sha256', doc['r0_report']['execution_sha256']]
        return command
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
    require(job_ready(path, doc, job) == 'ready', 'job inputs not ready')
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
                if job.get('kind') == 'r0_report':
                    require(type(report.get('exit_code')) is int and report['exit_code'] == 0
                            and report.get('run_of_record') is True and report.get('limit_groups') == 0
                            and report.get('scientific_acceptance') is False
                            and report.get('candidate_test_read') is False, 'R0 completion scope differs')
                    require(sha(report['verified']) == report['verified_sha256'] and
                            sha(Path(job['eval_out'])/'instruct/report.json') == report['report_sha256'],
                            'R0 verified output identity differs')
                elif job.get('kind') == 'k0_prechecks':
                    require(report.get('schema') == 'r3-fresh-k0-prechecks-v1'
                            and report.get('status') == 'PASS'
                            and report.get('scientific_acceptance') is False
                            and report.get('test_read') is False
                            and report.get('model') == job['model'], 'precheck output scope differs')
                    for filename, digest in {**report['inputs'], **report['checks']}.items():
                        require(sha(filename) == digest, 'precheck evidence changed')
                else:
                    schema = 'r3-development-comparison-v1' if job.get('kind') == 'comparison' else 'r3-selection-report-v1'
                    require(report.get('schema') == schema and
                            report.get('scientific_acceptance') is False, 'report output scope differs')
                if job.get('kind') == 'comparison':
                    require(report.get('test_read') is False, 'comparison read test')
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


def observe(path, pin, job, doc=None):
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
    return {'status': job_ready(path, doc, job) if doc is not None else ready(job)}


def tick(path, pin, doc):
    states = {}
    for job in doc['jobs']:
        try:
            states[job['id']] = observe(path, pin, job, doc)
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
            # An inference failure can still receive an operator-authorized
            # retry. Keep observing it so later success is not left unreported.
            if all(x['status'] in ('done', 'report_failed') for x in states.values()):
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
