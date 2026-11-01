#!/usr/bin/env python3
"""Single-owner CPU precheck waiter; frozen producer consumption, never rescoring.

No retries, no inference/NPU, no formal approval. Terminal success requires the
pinned generator AND full v2 consumer to finish. PID receipts indicate liveness
only. A lost process, failed producer, changed source, or partial output requires
operator inspection and a new generation.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and str(p) == str(path) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
    return p


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(path, pin):
    raw = safe(path).read_bytes()
    require(digest(raw) == pin, 'source pin differs: ' + str(path))
    return raw


def atomic(path, value):
    p = Path(path)
    tmp = p.with_suffix(p.suffix + '.tmp')
    with tmp.open('w') as f:
        f.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def module(path, pin):
    raw = pinned(path, pin)
    m = types.ModuleType('pinned_prechecks')
    m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), m.__dict__)
    return m


def request(path, pin):
    q = json.loads(pinned(path, pin))
    require(q['schema'] == 'instruct-v2-precheck-cpu-queue-20261101-v1'
            and q['scientific_acceptance'] is False and q['test_read'] is False
            and q['automatic_retry'] is False and q['model_monitor_interval_seconds'] == 600,
            'queue scope differs')
    require(q['worker'] == str(Path(__file__).absolute()), 'different worker')
    pinned(q['worker'], q['worker_sha256'])
    require(safe(q['output']) == safe(path).parent / 'evidence' / 'K0_PRECHECKS.json',
            'output must belong to new queue')
    return q


def prerequisite(q):
    """Read/hash/parse identical buffers; no output consumption before EXIT."""
    p = q['producer']
    raw = pinned(p['queue'], p['queue_sha256'])
    doc = json.loads(raw)
    require(doc.get('schema') == 'r3-cpu-report-queue-v1'
            and doc.get('scientific_acceptance') is False and doc.get('test_read') is False,
            'producer scope differs')
    pinned(doc['controller'], doc['controller_sha256'])
    jobs = [j for j in doc['jobs'] if j['id'] == p['job']['id']]
    require(jobs == [p['job']] and p['job']['kind'] == 'report', 'producer job identity differs')
    require(p['job']['output'] == str(safe(p['job']['eval_out']) / 'results/selection_report.json'),
            'producer output identity differs')
    terminal = safe(p['terminal'])
    require(terminal == safe(p['queue']).parent / 'jobs' / p['job']['id'] / 'EXIT.json',
            'producer terminal identity differs')
    if not terminal.exists():
        return None
    terminal_raw = terminal.read_bytes()
    end = json.loads(terminal_raw)
    require(type(end.get('exit_code')) is int and end['exit_code'] == 0
            and end.get('scientific_acceptance') is False, 'producer failed or terminal scope differs')
    report_raw = pinned(p['job']['output'], end.get('output_sha256'))
    report = json.loads(report_raw)
    require(report.get('schema') == 'r3-selection-report-v1' and
            report.get('scientific_acceptance') is False, 'producer report scope differs')
    require(report['header']['arm'] == 'K0' and all(
            report['header']['model'].get(k) == v for k, v in q['expected_report_model'].items())
            and set(report['header']['partitions']) == {'dev', 'calibration'}, 'producer K0 identity differs')
    return {'queue': p['queue'], 'queue_sha256': digest(raw), 'job': p['job'],
            'terminal': str(terminal), 'terminal_sha256': digest(terminal_raw),
            'report': p['job']['output'], 'report_sha256': digest(report_raw)}


def dependencies(q):
    # Preflight the complete set before reading any dependency bytes.
    for path in q['source_pins']:
        safe(path)
    for path, pin in q['source_pins'].items():
        pinned(path, pin)


def produce(path, pin):
    q = request(path, pin)
    root = path.parent
    dependencies(q)
    consumed = prerequisite(q)
    require(consumed is not None, 'producer terminal absent')
    require(not safe(q['output']).parent.exists(), 'output generation already exists')
    atomic(root / 'CONSUMED.json', consumed)
    generator = module(q['generator'], q['source_pins'][q['generator']])
    args = types.SimpleNamespace(**q['generator_arguments'])
    generator.run(args)
    # The current consumer is pinned separately, compiled from the checked buffer.
    consumer = module(q['consumer'], q['source_pins'][q['consumer']])
    output = safe(q['output'])
    output_pin = digest(output.read_bytes())
    bundle = consumer.validate_bundle(str(output), output_pin, q['generator_arguments']['model'])
    require(prerequisite(q) == consumed, 'producer changed during consumption')
    dependencies(q)
    atomic(root / 'VALIDATION.json', {'output': str(output), 'output_sha256': output_pin,
           'schema': bundle['schema'], 'inputs': len(bundle['inputs']), 'checks': len(bundle['checks']),
           'full_validate_bundle_completed': True, 'consumed': consumed,
           'review': 'PENDING_ROOT_REVIEW', 'scientific_acceptance': False, 'test_read': False})


def command(path, pin, op):
    return [sys.executable, '-B', '-P', str(Path(__file__).absolute()), op,
            '--queue', str(path), '--sha256', pin]


def matches(receipt):
    try:
        actual = (Path('/proc') / str(receipt['pid']) / 'cmdline').read_bytes()
        stat = (Path('/proc') / str(receipt['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
    except FileNotFoundError:
        return False
    return (actual.rstrip(b'\0').split(b'\0') == [os.fsencode(x) for x in receipt['command']]
            and stat[19] == receipt['start_ticks'])


def receipt(process, cmd):
    stat = (Path('/proc') / str(process.pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': process.pid, 'command': cmd, 'start_ticks': stat[19],
            'utc_seconds': time.time(), 'completion': False}


def watch(path, pin):
    root = path.parent
    rc = 1
    child = None
    state = 'starting'
    q = None
    with (root / 'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            require(not (root / 'EXIT.json').exists() and not (root / 'PRODUCE_INTENT.json').exists(),
                    'prior attempt present; no automatic retry')
            while True:
                q = request(path, pin)
                consumed = prerequisite(q)
                state = 'waiting_producer_terminal' if consumed is None else 'producer_terminal_verified'
                atomic(root / 'heartbeat.json', {'state': state, 'utc_seconds': time.time(),
                       'pid': os.getpid(), 'progress_count': 0, 'model_monitor_interval_seconds': 600,
                       'script_poll_seconds': 15, 'scientific_acceptance': False, 'test_read': False})
                if consumed is not None:
                    break
                time.sleep(15)
            dependencies(q)
            cmd = command(path, pin, 'produce')
            atomic(root / 'PRODUCE_INTENT.json', {'command': cmd, 'consumed': consumed})
            with (root / 'producer.log').open('xb') as log:
                child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True)
            atomic(root / 'CHILD.json', receipt(child, cmd))
            state = 'producing_and_fully_validating'
            while child.poll() is None:
                atomic(root / 'heartbeat.json', {'state': state, 'utc_seconds': time.time(),
                       'pid': os.getpid(), 'child_pid': child.pid, 'progress_count': 1,
                       'model_monitor_interval_seconds': 600, 'scientific_acceptance': False})
                time.sleep(15)
            require(child.returncode == 0, 'producer/validator failed; inspect bounded failure, no retry')
            validation = json.loads((root / 'VALIDATION.json').read_bytes())
            require(validation['full_validate_bundle_completed'] is True and
                    validation['consumed'] == consumed == prerequisite(q), 'completion binding differs')
            pinned(q['output'], validation['output_sha256'])
            dependencies(q)
            rc = 0
            state = 'completed_pending_root_review'
        except Exception as error:
            state = 'failed_closed'
            atomic(root / 'FAILURE.json', {'type': type(error).__name__, 'message': str(error)[:1000]})
        finally:
            if child is not None and child.poll() is None:
                child.wait()
            atomic(root / 'heartbeat.json', {'state': state, 'utc_seconds': time.time(),
                   'progress_count': 2 if rc == 0 else 0, 'model_monitor_interval_seconds': 600,
                   'scientific_acceptance': False})
            atomic(root / 'EXIT.json', {'exit_code': rc, 'queue_sha256': pin,
                   'output_sha256': digest(safe(q['output']).read_bytes()) if rc == 0 else None,
                   'validation_sha256': digest((root / 'VALIDATION.json').read_bytes()) if rc == 0 else None,
                   'review': 'PENDING_ROOT_REVIEW', 'scientific_acceptance': False, 'test_read': False})
    return rc


def start(path, pin):
    q = request(path, pin)
    dependencies(q)
    prerequisite(q)
    root = path.parent
    with (root / 'start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not any((root / f).exists() for f in ('START_INTENT.json', 'SERVICE.json', 'EXIT.json')),
                'generation already activated; no automatic retry')
        cmd = command(path, pin, 'watch')
        atomic(root / 'RELAUNCH.json', {'command': command(path, pin, 'start'),
               'environment_overrides': q['runtime_environment'],
               'policy': 'Idempotency guard rejects reactivation. Failure/lost process requires root inspection and fresh generation.'})
        atomic(root / 'START_INTENT.json', {'command': cmd, 'utc_seconds': time.time()})
        with (root / 'service.log').open('xb') as log:
            process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        r = receipt(process, cmd)
        atomic(root / 'SERVICE.json', r)
        require(matches(r), 'new waiter PID/command/start time not verified')
        atomic(root / 'ACTIVATION.json', {'service': r, 'process_identity_verified': True,
               'queue_sha256': pin, 'status': 'ACTIVE_NOT_COMPLETE', 'scientific_acceptance': False,
               'review': 'PENDING_ROOT_REVIEW', 'model_monitor_interval_seconds': 600})
        print(json.dumps({'pid': process.pid, 'status': 'ACTIVE_NOT_COMPLETE', 'queue_sha256': pin}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=('start', 'watch', 'produce'))
    p.add_argument('--queue', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if a.op == 'produce':
        try:
            produce(a.queue, a.sha256)
        except Exception as error:
            atomic(a.queue.parent / 'PRODUCER_FAILURE.json', {'type': type(error).__name__, 'message': str(error)[:1000]})
            return 1
        return 0
    if a.op == 'watch':
        return watch(a.queue, a.sha256)
    start(a.queue, a.sha256)
    return 0


if __name__ == '__main__':
    sys.exit(main())
