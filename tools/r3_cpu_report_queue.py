#!/usr/bin/env python3
"""Ordered, detached CPU selection reporting; never claims devices or reads tests.

Only successfully released inference jobs become ready. A lost worker without a
terminal is a repair condition, never permission to duplicate CPU execution.

New Track KT report jobs may opt into terminal_gate="full_posttrain_v1" with
plan/plan_sha256 and execution/execution_sha256 bindings. This requires scoring,
supervisor and retained host-175 Docker closure before reporting. Existing frozen
queues retain their original gate. poll_interval_seconds defaults to 600 and may
only be increased. Configuration verification is not scientific acceptance.
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
    interval = doc.get('poll_interval_seconds', 600)
    require(type(interval) is int and interval >= 600, 'CPU polling interval must be at least 600 seconds')
    require(doc['schema'] == 'r3-cpu-report-queue-v1' and doc['test_read'] is False
            and doc['scientific_acceptance'] is False, 'queue scope differs')
    require(doc['controller'] == str(Path(__file__).resolve()) and
            sha(__file__) == doc['controller_sha256'], 'controller identity differs')
    require(sha(doc['report_tool']) == doc['report_tool_sha256'], 'report tool changed')
    closure = Path(doc['closure'])
    require(sha(closure / 'manifest.json') == doc['closure_sha256'], 'closure manifest changed')
    for entry in load(closure / 'manifest.json')['code'].values():
        require(sha(entry['snapshot']) == entry['sha256'], 'frozen closure code changed')
    # Legacy queues lack this field. When supplied, it is a runtime contract,
    # not merely a note about which code produced the readouts.
    if 'producer_closure' in doc:
        producer = doc['producer_closure']
        require(isinstance(producer, dict), 'producer closure pin malformed')
        producer_root = safe_absolute(producer.get('path'))
        producer_pin = producer.get('manifest_sha256')
        require(isinstance(producer_pin, str) and re.fullmatch('[0-9a-f]{64}', producer_pin),
                'producer closure pin malformed')
        require(sha(producer_root / 'manifest.json') == producer_pin,
                'producer closure manifest changed')
    jobs = doc['jobs']
    require(jobs and len({j['id'] for j in jobs}) == len(jobs), 'empty or duplicate jobs')
    reports = [j for j in jobs if j.get('kind', 'report') == 'report']
    comparisons = [j for j in jobs if j.get('kind') == 'comparison']
    external_comparisons = [j for j in jobs if j.get('kind') == 'external_comparison']
    r0_reports = [j for j in jobs if j.get('kind') == 'r0_report']
    prechecks = [j for j in jobs if j.get('kind') == 'k0_prechecks']
    pt_reports = [j for j in jobs if j.get('kind') == 'pt_r0_report']
    qo_reports = [j for j in jobs if j.get('kind') == 'qo_diagnostic']
    require(len(reports) + len(comparisons) + len(external_comparisons) + len(r0_reports) + len(prechecks) + len(pt_reports) + len(qo_reports) == len(jobs), 'unknown CPU job kind')
    for job in external_comparisons:
        verify_external_comparison(path, job)
    if qo_reports:
        config = doc['qo_diagnostic']
        require(sha(safe_absolute(config['tool'])) == config['tool_sha256'], 'QO tool changed')
        safe_absolute(config['kev_dir']); safe_absolute(config['data_root'])
        for job in qo_reports:
            refs = job['candidate'] + [job['qo']]
            require(len(job['candidate']) == 2 and len({(r['queue'], r['job']) for r in refs}) == 3,
                    'three distinct external reports required')
            for ref in refs:
                external_report(ref, check_terminal=False)
            output = safe_absolute(job['output'])
            require(output == path.parent / 'comparisons' / job['id'] / 'qo_transfer_diagnostic.json',
                    'QO output must belong to this queue')
    if pt_reports:
        verify_pt_config(doc['pt_r0_report'])
        require(len({j['eval_out'] for j in pt_reports}) == len(pt_reports), 'duplicate PT evaluation')
        for job in pt_reports:
            safe_absolute(job['eval_out']); safe_absolute(job['output'])
            require(Path(job['output']) == Path(job['eval_out']) / 'results/PT_R0_REPORT.json', 'PT output path differs')
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
        if 'terminal_gate' in job:
            require(job.get('kind', 'report') == 'report' and
                    job['terminal_gate'] == 'full_posttrain_v1', 'unsupported terminal gate')
            _, spec = strict_plan(job)
            verify_producer_mounts(doc, spec)
        require(re.fullmatch(r'[A-Za-z0-9_-]+', job['id']), 'unsafe job ID')
        require(Path(job['output']).is_absolute(), 'absolute output required')
        if job.get('kind', 'report') == 'report':
            require(Path(job['eval_out']).is_absolute(), 'absolute evaluation path required')
            require(Path(job['output']).name == 'selection_report.json', 'selection report filename required')
    if comparisons or external_comparisons:
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


def safe_absolute(value):
    require(isinstance(value, str), 'absolute evidence path required')
    path = Path(value)
    require(path.is_absolute() and str(path) == value and '..' not in path.parts
            and not value.startswith('//') and not any(p.is_symlink() for p in (path, *path.parents)),
            'absolute nonsymlink evidence path required')
    return path


def external_report(ref, check_terminal=True):
    """Consume a frozen producer's report; never enqueue or execute its jobs."""
    path = safe_absolute(ref['queue'])
    require(sha(path) == ref['queue_sha256'], 'external queue changed')
    doc = load(path)
    require(doc.get('schema') == 'r3-cpu-report-queue-v1'
            and doc.get('scientific_acceptance') is False and doc.get('test_read') is False,
            'external queue scope differs')
    jobs = [j for j in doc['jobs'] if j['id'] == ref['job']]
    require(len(jobs) == 1 and jobs[0].get('kind', 'report') == 'report', 'external report job required')
    job = jobs[0]
    require(re.fullmatch(r'[A-Za-z0-9_-]+', job['id']), 'unsafe external job ID')
    output = safe_absolute(job['output'])
    require(output == safe_absolute(job['eval_out']) / 'results/selection_report.json',
            'external report path differs')
    if not check_terminal:
        return str(output), None
    terminal = safe_absolute(str(workdir(path, job) / 'EXIT.json'))
    if not terminal.exists():
        return str(output), 'waiting_reports'
    end = load(terminal)
    require(type(end.get('exit_code')) is int and end.get('scientific_acceptance') is False,
            'external terminal scope differs')
    if end['exit_code'] != 0:
        return str(output), 'comparison_blocked'
    require(sha(output) == end.get('output_sha256'), 'external report changed')
    return str(output), 'ready'


def external_comparison_refs(job):
    require(isinstance(job.get('candidate'), list) and len(job['candidate']) == 2,
            'two external candidate reports required')
    require(not any(k in job for k in ('incumbent', 'r0_report')),
            'external comparison supports K0 diagnostics only')
    refs = job['candidate'] + [job['baseline']]
    for ref in refs:
        require(isinstance(ref, dict) and set(ref) == {'queue', 'queue_sha256', 'job'} and
                isinstance(ref['job'], str) and re.fullmatch(r'[A-Za-z0-9_-]+', ref['job']) and
                isinstance(ref['queue_sha256'], str) and re.fullmatch('[0-9a-f]{64}', ref['queue_sha256']),
                'invalid external comparison reference')
    require(len({(ref['queue'], ref['job']) for ref in refs}) == 3,
            'three distinct external reports required')
    return refs


def verify_external_comparison(path, job):
    refs = external_comparison_refs(job)
    outputs = [external_report(ref, check_terminal=False)[0] for ref in refs]
    require(len(set(outputs)) == 3, 'external reports alias the same output')
    require(all(safe_absolute(ref['queue']) != path for ref in refs), 'self-referencing external queue')
    require(isinstance(job.get('id'), str) and re.fullmatch(r'[A-Za-z0-9_-]+', job['id']),
            'unsafe external comparison ID')
    require(safe_absolute(job['output']) == path.parent / 'comparisons' / job['id'] / 'development_comparison.json',
            'external comparison output must belong to this queue')


def validate_external_comparison_output(report, job, started_inputs=None):
    require(report.get('schema') == 'r3-development-comparison-v1' and
            report.get('scientific_acceptance') is False and report.get('test_read') is False,
            'external comparison output scope differs')
    expected = {}
    for ref in external_comparison_refs(job):
        output, state = external_report(ref)
        require(state == 'ready', 'external comparison dependency no longer ready')
        expected[output] = sha(output)
    require(started_inputs is None or expected == started_inputs,
            'external comparison inputs changed during execution')
    require(report.get('inputs') == expected, 'external comparison inputs differ')


def validate_qo_output(report, job):
    require(report.get('schema') == 'r3-qo-transfer-dev-diagnostic-v1'
            and report.get('scientific_acceptance') is False
            and report.get('test_read') is False and report.get('adoption_authorized') is False,
            'QO diagnostic scope differs')
    expected = {}
    for ref in job['candidate'] + [job['qo']]:
        output, state = external_report(ref)
        require(state == 'ready', 'QO dependency no longer ready')
        expected[output] = sha(output)
    require(report.get('inputs') == expected, 'QO output inputs differ')


def verify_pt_config(config):
    for filename, digest in config['files'].items():
        require(sha(safe_absolute(filename)) == digest, 'PT CPU dependency changed')
    require(config['tool'] in config['files']
            and Path(config['tool']).name == 'r3_pt_r0_consumer.py', 'PT consumer not pinned')
    required = ('r3_pt_r0_report.py', 'r3_model_inventory.py', 'r3_r0_report.py', 'r3_r0_prepare.py', 'r0rescore_verify.py')
    require(all(str(Path(config['tool']).with_name(name)) in config['files'] for name in required),
            'PT consumer helper not pinned')
    require(sha(safe_absolute(config['config'])) == config['config_sha256'], 'PT consumer config changed')
    root = safe_absolute(config['r0_run'])
    consumer = load(config['config'])
    require(consumer.get('schema') == 'r3-pt-r0-consumer-config-v1'
            and consumer.get('tools') == config['files'], 'PT consumer tool binding differs')
    execution = consumer.get('r0_execution', {})
    require(execution.get('path') == str(root / 'execution.json')
            and sha(root / 'execution.json') == execution.get('sha256'), 'PT R0 execution binding differs')


def pt_execution_pin(job):
    root = safe_absolute(job['eval_out'])
    entry = load(root / 'QUEUE_EXECUTION_PIN.json')
    value = entry.get('sha256')
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
            and sha(root / 'execution.json') == value, 'PT queued execution pin differs')
    return value


def pt_r0_ready(doc, job):
    state = ready(job)
    if state != 'ready':
        return state
    pt_execution_pin(job)
    root = safe_absolute(doc['pt_r0_report']['r0_run'])
    baseline_state = ready({'eval_out': str(root)})
    if baseline_state != 'ready':
        return 'r0_' + baseline_state
    marker = root / 'R0RESCORE_COMPLETE.json'
    if not marker.exists():
        return 'waiting_r0_report'
    value = load(marker)
    require(type(value.get('exit_code')) is int and value['exit_code'] == 0
            and value.get('run_of_record') is True and value.get('limit_groups') == 0
            and value.get('scientific_acceptance') is False
            and value.get('candidate_test_read') is False, 'R0 completion scope differs')
    require(value.get('execution_sha256') == sha(root / 'execution.json'), 'R0 completed execution differs')
    require(value.get('verified') == str(root / 'R0RESCORE_VERIFIED.json')
            and sha(root / 'R0RESCORE_VERIFIED.json') == value.get('verified_sha256')
            and sha(root / 'instruct/report.json') == value.get('report_sha256'), 'R0 completed report changed')
    # This is readiness only. The consumer independently rebuilds R0 sources;
    # marker hashes never stand in for scientific verification.
    return 'ready'


def validate_pt_output(report, doc, job):
    require(report.get('schema') == 'r3-pt-r0-diagnostics-v1'
            and report.get('scientific_acceptance') is False
            and report.get('publication_authorized') is False
            and report.get('candidate_test_read') is False, 'PT diagnostics scope differs')
    proof = report.get('consumer_verification', {})
    require(proof.get('run') == job['eval_out']
            and proof.get('pt_execution_sha256') == pt_execution_pin(job)
            and proof.get('config_sha256') == doc['pt_r0_report']['config_sha256']
            and proof.get('r0_source_reconstructed') is True, 'PT output scope or binding differs')



def verify_producer_mounts(doc, spec):
    producer = doc.get('producer_closure')
    require(isinstance(producer, dict), 'strict producer closure required')
    root = safe_absolute(producer.get('path'))
    expected = {str(root / name) for name in ('r3_code', 'r0_code')}
    mounts = spec.get('code_mounts', [])
    require(len(mounts) == 2 and {m.get('source') for m in mounts} == expected and
            all(m.get('readonly') is True and m.get('destination') ==
                '/mnt/cephfs/xingchao/experiments/jev/' + Path(m['source']).name for m in mounts),
            'declared producer closure differs from actual code mounts')


def strict_plan(job):
    """Pin a new post-training consumer without changing legacy queues."""
    root = safe_absolute(job['eval_out'])
    for key, filename in (('execution', 'execution.json'), ('plan', 'plan.json')):
        require(job.get(key) == str(root / filename) and
                sha(root / filename) == job.get(key + '_sha256'), 'strict ' + key + ' binding differs')
    execution = load(root / 'execution.json')
    spec = load(root / 'plan.json')
    require(execution.get('spec') == str(root / 'plan.json') and
            execution.get('spec_sha256') == job['plan_sha256'] and
            execution.get('out') == str(root), 'strict producer specification differs')
    require(execution.get('test_read') is False and execution.get('scientific_acceptance') is False and
            spec.get('test_read') is False and spec.get('scientific_acceptance') is False and
            spec.get('evaluation_profile') == 'track_kt', 'strict producer scope differs')
    require(job['output'] == str(root / 'results/selection_report.json'), 'strict report output differs')
    return execution, spec


def full_posttrain_ready(job, number, end):
    execution, spec = strict_plan(job)
    root = Path(job['eval_out']); attempt = root / 'attempts' / str(number)
    require(type(end.get('exit_code')) is int and end.get('scientific_acceptance') is False,
            'strict terminal scope differs')
    done = attempt / 'SUPERVISOR_DONE.json'
    if not done.exists():
        return 'waiting_supervisor'
    completed = load(done)
    require(type(completed.get('exit_code')) is int and completed['exit_code'] == end['exit_code'] and
            completed.get('scientific_acceptance') is False, 'supervisor terminal differs')
    if end['exit_code'] == 0:
        marker = root / 'results/EVAL_COMPLETE.track_kt.json'
        if not marker.exists():
            return 'waiting_scoring_terminal'
        scoring = load(marker)
        require(type(scoring.get('exit_code')) is int and scoring['exit_code'] == 0 and
                not scoring.get('error'),
                'scoring terminal differs')
    launch = load(attempt / 'LAUNCH_RECEIPT.json')
    require(launch.get('sha256') == job['execution_sha256'] and
            launch.get('image') == spec.get('image_sha256'), 'strict launch binding differs')
    container = launch['id']
    require(isinstance(container, str) and re.fullmatch('[0-9a-f]{64}', container),
            'invalid retained container ID')
    # Only after file closure; never read logs or infer death from a timeout.
    raw = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                   'npu', 'docker', 'inspect', container], text=True, timeout=30)
    inspected = json.loads(raw)
    require(isinstance(inspected, list) and len(inspected) == 1, 'retained container observation differs')
    actual = inspected[0]
    expected_command = ['-P', execution['launcher'], 'drive', '--plan', job['execution'],
                        '--sha256', job['execution_sha256'], '--attempt', str(number)]
    require(actual.get('Id') == container and
            actual.get('Name') == '/' + execution['container'] + '-a' + str(number) and
            actual.get('Image') == spec['image_sha256'] and
            actual.get('HostConfig', {}).get('AutoRemove') is False and
            actual.get('Config', {}).get('Cmd') == expected_command, 'retained container binding differs')
    state = actual.get('State', {})
    if state.get('Status') in ('running', 'created', 'restarting', 'paused'):
        return 'waiting_container_terminal'
    require(state.get('Status') in ('exited', 'dead') and state.get('Running') is False and
            type(state.get('ExitCode')) is int and state['ExitCode'] == end['exit_code'] and
            (end['exit_code'] != 0 or (not state.get('OOMKilled') and not state.get('Error'))),
            'retained container terminal differs')
    return 'ready' if end['exit_code'] == 0 else 'inference_failed'


def ready(job):
    if 'terminal_gate' in job:
        require(job['terminal_gate'] == 'full_posttrain_v1', 'unsupported terminal gate')
        strict_plan(job)
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
    if job.get('terminal_gate') == 'full_posttrain_v1':
        return full_posttrain_ready(job, number, end)
    return 'ready' if end['exit_code'] == 0 else 'inference_failed'


def comparison_dependencies(job):
    if job.get('kind') == 'k0_prechecks':
        return [job['baseline']]
    return job['candidate'] + [job['baseline']] + job.get('incumbent', []) + ([job['r0_report']] if job.get('r0_report') else [])


def job_ready(path, doc, job):
    if job.get('kind') == 'external_comparison':
        states = [external_report(ref)[1] for ref in external_comparison_refs(job)]
        return 'comparison_blocked' if 'comparison_blocked' in states else (
            'ready' if all(s == 'ready' for s in states) else 'waiting_reports')
    if job.get('kind') == 'qo_diagnostic':
        states = [external_report(ref)[1] for ref in job['candidate'] + [job['qo']]]
        return 'comparison_blocked' if 'comparison_blocked' in states else (
            'ready' if all(s == 'ready' for s in states) else 'waiting_reports')
    if job.get('kind') == 'pt_r0_report':
        return pt_r0_ready(doc, job)
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
    if job.get('kind') == 'external_comparison':
        config = doc['comparison']
        outputs = []
        for ref in external_comparison_refs(job):
            output, state = external_report(ref)
            require(state == 'ready', 'external comparison dependency not ready')
            outputs.append(output)
        return [sys.executable, '-P', config['tool'], '--candidate', *outputs[:2],
                '--baseline', outputs[2], '--frozen-code-dir', str(Path(doc['closure']) / 'r3_code'),
                '--selector', config['selector'], '--selector-sha256', config['selector_sha256'],
                '--report-tool', doc['report_tool'], '--report-tool-sha256', doc['report_tool_sha256'],
                '--output', job['output']]
    if job.get('kind') == 'qo_diagnostic':
        config = doc['qo_diagnostic']
        return [sys.executable, '-P', config['tool'], '--candidate',
                *[external_report(ref)[0] for ref in job['candidate']],
                '--qo', external_report(job['qo'])[0],
                '--report-tool', doc['report_tool'], '--report-tool-sha256', doc['report_tool_sha256'],
                '--closure', doc['closure'], '--closure-sha256', doc['closure_sha256'],
                '--kev-dir', config['kev_dir'], '--data-root', config['data_root'], '--output', job['output']]
    if job.get('kind') == 'pt_r0_report':
        config = doc['pt_r0_report']
        return [sys.executable, '-P', config['tool'], '--run', job['eval_out'],
                '--execution-sha256', pt_execution_pin(job), '--config', config['config'],
                '--config-sha256', config['config_sha256'], '--output', job['output']]
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
    if job.get('kind') == 'external_comparison':
        verify_external_comparison(path, job)
        Path(job['output']).parent.mkdir(parents=True, exist_ok=True)
    command = report_command(doc, job)
    started_inputs = ({external_report(ref)[0]: sha(external_report(ref)[0])
                       for ref in external_comparison_refs(job)}
                      if job.get('kind') == 'external_comparison' else None)
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
                if job.get('kind') == 'qo_diagnostic':
                    validate_qo_output(report, job)
                elif job.get('kind') == 'external_comparison':
                    validate_external_comparison_output(report, job, started_inputs)
                elif job.get('kind') == 'pt_r0_report':
                    validate_pt_output(report, doc, job)
                elif job.get('kind') == 'r0_report':
                    require(type(report.get('exit_code')) is int and report['exit_code'] == 0
                            and report.get('run_of_record') is True and report.get('limit_groups') == 0
                            and report.get('scientific_acceptance') is False
                            and report.get('candidate_test_read') is False, 'R0 completion scope differs')
                    require(sha(report['verified']) == report['verified_sha256'] and
                            sha(Path(job['eval_out'])/'instruct/report.json') == report['report_sha256'],
                            'R0 verified output identity differs')
                elif job.get('kind') == 'k0_prechecks':
                    require(report.get('schema') == 'r3-fresh-k0-prechecks-v2'
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
            time.sleep(doc.get('poll_interval_seconds', 600))


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
