"""Bounded K2 benchmark metadata; never reads logs, tensors or datasets.

Reported numbers are observations, not independent equivalence verification or
authorization to replace a trainer. Invoke at the shared monitoring cadence.
"""
import hashlib
import json
from pathlib import Path
import types

LIMIT = 262144


def arithmetic(report, plan_pin):
    path = Path(__file__).with_name('r3_k2_benchmark_verify.py')
    verifier = types.ModuleType('k2_arithmetic')
    exec(compile(path.read_bytes(), str(path), 'exec'), verifier.__dict__)
    return verifier.verify(report, plan_pin)


def read(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('unsafe metadata path')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('metadata size limit exceeded')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except RecursionError as exc:
        raise ValueError('metadata nesting limit exceeded') from exc
    if not isinstance(value, dict):
        raise ValueError('metadata must be an object')
    return value, hashlib.sha256(raw).hexdigest()


def summarize(root, execution_pin):
    root = Path(root)
    result = {'run': str(root), 'state': 'not_started', 'flags': [],
              'scientific_acceptance': False, 'completion_verified': False,
              'scope': 'metadata only; no actual process/container or tensor verification'}
    try:
        plan, pin = read(root / 'execution.json')
        if pin != execution_pin or plan.get('out') != str(root):
            raise ValueError('execution identity differs')
        benchmark, pin = read(plan['benchmark_plan'])
        if pin != plan['benchmark_sha256'] or benchmark['out'] != str(root / 'results'):
            raise ValueError('benchmark identity differs')
        if (root / 'SUPERVISOR_RECEIPT.json').exists():
            result['state'] = 'supervisor_started'
        if (root / 'digest.json').exists():
            state, _ = read(root / 'digest.json')
            if state.get('state') in ('waiting_resource', 'observation_uncertain', 'running'):
                result['state'] = state['state']
        if (root / 'results/heartbeat.json').exists():
            heartbeat, _ = read(root / 'results/heartbeat.json')
            n = heartbeat.get('completed_pairs')
            if (type(n) is not int or not 0 <= n <= 13
                    or type(heartbeat.get('total_pairs')) is not int or heartbeat['total_pairs'] != 13):
                raise ValueError('invalid paired progress')
            result.update(completed_pairs=n, total_pairs=13, heartbeat_utc_seconds=heartbeat.get('utc_seconds'))
        terminal_path = root / 'ENGINEERING_EVAL_EXIT.json'
        if not terminal_path.exists():
            return result
        terminal, _ = read(terminal_path)
        if terminal.get('plan_sha256') != execution_pin or type(terminal.get('exit_code')) is not int:
            raise ValueError('terminal identity differs')
        result.update(state='terminal_reported', exit_code=terminal['exit_code'],
                      release_recorded=(root / 'attempts/1/RELEASE.json').exists(),
                      supervisor_done_recorded=(root / 'attempts/1/SUPERVISOR_DONE.json').exists())
        if terminal['exit_code'] != 0:
            result['flags'].append('benchmark_failed')
            return result
        driver, _ = read(root / 'results/EXIT.json')
        report, digest = read(root / 'results/RESULT.json')
        if (type(driver.get('exit_code')) is not int or driver['exit_code'] != 0 or driver.get('plan_sha256') != pin
                or report.get('plan_sha256') != pin or digest != terminal.get('result_sha256')
                or terminal.get('benchmark_complete') is not True
                or report.get('scientific_acceptance') is not False or report.get('test_read') is not False):
            raise ValueError('terminal/result binding differs')
        checked = arithmetic(report, pin)
        result['arithmetic'] = checked
        result.update(reported_speedup=report.get('speedup'),
                      reported_exact_loss_and_gradients=report.get('exact_loss_and_gradients'),
                      reported_speed_candidate=report.get('engineering_speed_candidate'),
                      reported_performance=report.get('performance'), result_sha256=digest)
        rows = report.get('rows', [])
        if len(rows) != 13 or any(row.get('exact') is not True for row in rows):
            result['flags'].append('incomplete_or_inexact_pairs')
        if report.get('exact_loss_and_gradients') is not True:
            result['flags'].append('equivalence_not_reported')
        if report.get('engineering_speed_candidate') is not True:
            result['flags'].append('speed_threshold_not_met')
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        result.update(state='needs_inspection')
        result['flags'].append(type(exc).__name__ + ': ' + str(exc)[:200])
    return result
