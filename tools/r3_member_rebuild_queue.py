"""Ordered CPU source reconstruction for pending DEV members; never select/test.

Both modes verify the queue, this script and exact source bytes before loading
local helpers. An interrupted intent requires inspection, never an automatic retry.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time
import types


def require(ok, why):
    if not ok:
        raise ValueError(why)


def safe(value):
    p = Path(value)
    require(p.is_absolute() and str(p) == str(value) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p


def read(path):
    p = safe(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'regular file required')
        raw = stream.read()
        after = os.fstat(stream.fileno())
        fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(fingerprint(before) == fingerprint(after) == fingerprint(p.lstat()), 'file changed')
    return raw


def sha(path):
    return hashlib.sha256(read(path)).hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(read(path), object_pairs_hook=pairs)


def write(path, doc, exclusive=False):
    p = safe(path)
    raw = (json.dumps(doc, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    dest = p if exclusive else safe(str(p)+'.pending')
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        safe(p)
        os.replace(dest, p)


def scope(doc):
    require(doc.get('scientific_acceptance') is False and doc.get('test_read') is False,
            'engineering DEV scope required')


def zero(doc):
    require(type(doc.get('exit_code')) is int and doc['exit_code'] == 0, 'successful integer exit required')


def verify_queue(path, pin):
    require(sha(path) == pin, 'queue changed')
    q = load(path)
    scope(q)
    require(q['schema'] == 'r3-member-rebuild-queue-v2', 'queue schema differs')
    require(q['controller']['path'] == str(Path(__file__).resolve())
            and sha(__file__) == q['controller']['sha256'], 'controller bytes differ')
    require(q['interval_seconds'] == 30, 'queue cadence differs')
    root = safe(path).parent
    require(set(Path(p).name for p in q['code']) == {
        'r3_campaign_sources.py', 'r3_final_campaign.py', 'r3_model_inventory.py',
        'r3_selection_report.py'}, 'source set differs')
    for p, h in q['code'].items():
        require(safe(p).parent == root/'code' and sha(p) == h, 'code changed')
    require({str(p) for p in (root/'code').rglob('*.py')} == set(q['code']), 'code membership differs')
    jobs = q['jobs']
    require(jobs and len({j['id'] for j in jobs}) == len(jobs), 'duplicate jobs')
    for j in jobs:
        require(j['id'].replace('-', '').replace('_', '').isalnum(), 'unsafe job id')
        require(set(j['expected']) == {'role', 'arm', 'seed', 'base', 'adapter'}, 'expected identity fields differ')
        for key in ('producer_queue', 'terminal', 'report'):
            safe(j[key])
    return q


def sources(q):
    path = next(p for p in q['code'] if p.endswith('/r3_campaign_sources.py'))
    raw = read(path)
    require(hashlib.sha256(raw).hexdigest() == q['code'][path], 'consumer bytes differ')
    module = types.ModuleType('pinned_campaign_sources')
    module.__file__ = path
    module.__dict__['_SOURCE_PINS'] = q['code']
    exec(compile(raw, path, 'exec', dont_inherit=True), module.__dict__)
    return module


def producer(job):
    require(sha(job['producer_queue']) == job['producer_queue_sha256'], 'producer queue changed')
    q = load(job['producer_queue'])
    matches = [j for j in q['jobs'] if j['id'] == job['id']]
    require(len(matches) == 1 and matches[0].get('kind') == 'report'
            and matches[0].get('output') == job['report'], 'producer job/output mapping differs')
    require(Path(job['terminal']) == Path(job['producer_queue']).parent/'jobs'/job['id']/'EXIT.json',
            'producer terminal owner differs')
    terminal = load(job['terminal'])
    zero(terminal)
    require(terminal.get('scientific_acceptance') is False, 'producer scope differs')
    report_pin = sha(job['report'])
    require(terminal['output_sha256'] == report_pin, 'producer output differs')
    return {'queue': {'path': job['producer_queue'], 'sha256': job['producer_queue_sha256']},
            'terminal': {'path': job['terminal'], 'sha256': sha(job['terminal'])},
            'report': {'path': job['report'], 'sha256': report_pin}, 'job_id': job['id']}


def identity(member, expected):
    require(member['role'] == expected['role'] and member['arm'] == expected['arm'], 'member role/arm differs')
    require(member['model']['base_path'] == expected['base'], 'member base differs')
    require(member['model']['path'] == (expected['adapter'] or expected['base']), 'member model path differs')
    if expected['seed'] is None:
        require('training' not in member and expected['adapter'] is None, 'baseline has training')
    else:
        t = member['training']
        require(type(t.get('seed')) is int and t['seed'] == expected['seed'], 'member seed differs')
        require(t['arm'] == expected['arm'] and t['adapter_path'] == expected['adapter'], 'training identity differs')


def request(root, job, q, queue_path, queue_pin, C):
    bindings = producer(job)
    entry = {'report': bindings['report'], 'base_inventory': job['base_inventory'],
             'adapter_inventory': job['adapter_inventory']}
    C.artifact(entry['base_inventory'])
    h = C.scope(load(job['report']))
    e = job['expected']
    require(h['arm'] == e['arm'] and h['model']['base_path'] == e['base']
            and h['model']['path'] == (e['adapter'] or e['base']), 'report model differs')
    if e['adapter'] and entry['adapter_inventory'] is None:
        train = safe(e['adapter']).parent/'TRAIN_EXIT.json'
        zero(load(train))
        train_pin = sha(train)
        inv = C.M.capture(e['adapter'])
        ip = root/'adapter-inventory.json'
        write(ip, {'inventory': inv, 'inventory_sha256': C.M.identity(inv),
                   'training_terminal': {'path': str(train), 'sha256': train_pin},
                   'scientific_acceptance': False}, exclusive=True)
        require(sha(train) == train_pin, 'training terminal changed')
        entry['adapter_inventory'] = {'path': str(ip), 'sha256': sha(ip)}
    elif entry['adapter_inventory']:
        C.artifact(entry['adapter_inventory'])
    require(producer(job) == bindings, 'producer changed during preparation')
    return {'queue': {'path': str(queue_path), 'sha256': queue_pin}, 'job_id': job['id'],
            'expected': e, 'producer': bindings, 'entry': entry,
            'scientific_acceptance': False, 'test_read': False}


def validate_request(root, job, queue_path, pin):
    intent = load(root/'INTENT.json')
    scope(intent)
    require(intent['queue_sha256'] == pin and intent['job_id'] == job['id'], 'intent identity differs')
    req = load(root/'request.json')
    scope(req)
    require(sha(root/'request.json') == intent['request_sha256'], 'request changed')
    require(req['queue'] == {'path': str(queue_path), 'sha256': pin}
            and req['job_id'] == job['id'] and req['expected'] == job['expected'], 'request identity differs')
    require(req['producer'] == producer(job), 'bound producer changed')
    require(req['entry']['report'] == req['producer']['report']
            and req['entry']['base_inventory'] == job['base_inventory'], 'request artifact differs')
    if job['adapter_inventory'] is not None:
        require(req['entry']['adapter_inventory'] == job['adapter_inventory'], 'adapter inventory differs')
    elif job['expected']['adapter'] is None:
        require(req['entry']['adapter_inventory'] is None, 'baseline adapter supplied')
    else:
        require(req['entry']['adapter_inventory'] == {'path': str(root/'adapter-inventory.json'),
                'sha256': sha(root/'adapter-inventory.json')}, 'captured adapter binding differs')
    return req


def completed(root, job, queue_path, pin):
    require(not safe(root/'FAILURE.json').exists(), 'persisted failure forbids completion')
    req = validate_request(root, job, queue_path, pin)
    end = load(root/'EXIT.json')
    scope(end)
    zero(end)
    result = load(root/'RESULT.json')
    scope(result)
    require(end['result_sha256'] == sha(root/'RESULT.json'), 'result hash differs')
    request_pin = sha(root/'request.json')
    for d in (end, result):
        require(d['request_sha256'] == request_pin and d['queue_sha256'] == pin
                and d['job_id'] == job['id'], 'completion identity differs')
    require(result['producer'] == req['producer'], 'result producer differs')
    require(set(result['outputs']) == {'evidence.json'}, 'exact singleton output required')
    require(sha(root/'evidence.json') == result['outputs']['evidence.json'], 'evidence changed')
    evidence = load(root/'evidence.json')
    scope(evidence)
    require(evidence['request_sha256'] == request_pin, 'evidence request differs')
    identity(evidence['member'], job['expected'])
    return {'state': 'producer_complete', 'root': str(root), 'result_sha256': sha(root/'RESULT.json'),
            'independent_acceptance': False}


def worker(path, pin, key):
    q = verify_queue(path, pin)
    jobs = [j for j in q['jobs'] if j['id'] == key]
    require(len(jobs) == 1, 'worker job missing')
    job = jobs[0]
    root = safe(path).parent/'members'/key
    req = validate_request(root, job, path, pin)
    require(not (root/'EXIT.json').exists(), 'worker already terminal')
    stop = threading.Event()
    def heartbeat():
        while not stop.is_set():
            write(root/'heartbeat.json', {'state': 'rebuilding', 'utc_seconds': time.time()})
            stop.wait(30)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    common = {'job_id': key, 'queue_sha256': pin, 'request_sha256': sha(root/'request.json'),
              'scientific_acceptance': False, 'test_read': False}
    rc = 1
    try:
        C = sources(q)
        C.artifact(q['closure_manifest'])
        tool_path = next(p for p in q['code'] if p.endswith('/r3_selection_report.py'))
        tool = C.module(tool_path, 'pinned_report')
        deps = tool.modules(Path(q['closure_manifest']['path']).parent/'r3_code')
        code = {'report_tool': {'path': tool_path, 'sha256': q['code'][tool_path]},
                'closure_manifest': q['closure_manifest'],
                'consumer_sha256': q['code'][C.__file__],
                'structure_sha256': q['code'][str(C.HERE/'r3_final_campaign.py')],
                'inventory_sha256': q['code'][str(C.HERE/'r3_model_inventory.py')]}
        member, evidence = C.rebuild_member(req['entry'], tool, deps, q['kev_dir'], q['data_root'], code)
        identity(member, req['expected'])
        verify_queue(path, pin)
        require(validate_request(root, job, path, pin) == req, 'request changed during rebuild')
        C.artifact(q['closure_manifest'])
        write(root/'evidence.json', dict(common, member=member, evidence=evidence), exclusive=True)
        write(root/'RESULT.json', dict(common, producer=req['producer'],
              outputs={'evidence.json': sha(root/'evidence.json')}), exclusive=True)
        write(root/'EXIT.json', dict(common, exit_code=0, result_sha256=sha(root/'RESULT.json')), exclusive=True)
        completed(root, job, path, pin)
        rc = 0
    except Exception as error:
        write(root/'FAILURE.json', dict(common, state='failed_no_retry',
              error=type(error).__name__+': '+str(error)[:350]), exclusive=True)
        if not (root/'EXIT.json').exists():
            write(root/'EXIT.json', dict(common, exit_code=1), exclusive=True)
    finally:
        stop.set()
        thread.join()
    return rc


def watch(path, pin):
    q = verify_queue(path, pin)
    root = safe(path).parent
    lock_path = safe(root/'worker.lock')
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        require(stat.S_ISREG(os.fstat(lock.fileno()).st_mode), 'regular lock required')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        C = sources(q)
        while True:
            verify_queue(path, pin)
            states = {}
            for job in q['jobs']:
                key = job['id']
                out = safe(root/'members'/key)
                try:
                    if (out/'FAILURE.json').exists():
                        failure = load(out/'FAILURE.json')
                        scope(failure)
                        require(failure['job_id'] == key and failure['queue_sha256'] == pin,
                                'failure identity differs')
                        states[key] = failure
                        continue
                    if (out/'EXIT.json').exists():
                        states[key] = completed(out, job, path, pin)
                        continue
                    require(not (out/'INTENT.json').exists(), 'uncertain intent; no automatic restart')
                    if not safe(job['terminal']).exists():
                        states[key] = {'state': 'waiting_report_terminal'}
                        continue
                    out.mkdir(parents=True, exist_ok=False)
                    req = request(out, job, q, path, pin, C)
                    write(out/'request.json', req, exclusive=True)
                    # Recheck every producer binding immediately before exclusive intent.
                    verify_queue(path, pin)
                    require(producer(job) == req['producer'], 'producer changed before launch')
                    write(out/'INTENT.json', {'queue_sha256': pin, 'job_id': key,
                          'request_sha256': sha(out/'request.json'), 'scientific_acceptance': False,
                          'test_read': False}, exclusive=True)
                    cmd = [sys.executable, '-P', str(Path(__file__).resolve()), 'worker',
                           '--queue', str(path), '--sha256', pin, '--job', key]
                    write(out/'RELAUNCH.json', {'command': cmd}, exclusive=True)
                    logfile = safe(out/'worker.log')
                    logfd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(logfd, 'ab') as log:
                        child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                                 stderr=subprocess.STDOUT, start_new_session=True)
                    write(out/'PROCESS.json', {'pid': child.pid, 'command': cmd}, exclusive=True)
                    while child.poll() is None:
                        write(root/'digest.json', {'jobs': {**states, key: {'state': 'rebuilding',
                              'pid': child.pid}}, 'utc_seconds': time.time(), 'scientific_acceptance': False})
                        time.sleep(30)
                    require(child.wait() == 0, 'worker failed')
                    states[key] = completed(out, job, path, pin)
                except Exception as error:
                    out.mkdir(parents=True, exist_ok=True)
                    failure = {'state': 'failed_no_retry', 'job_id': key, 'queue_sha256': pin,
                               'error': type(error).__name__+': '+str(error)[:350],
                               'scientific_acceptance': False, 'test_read': False}
                    if not (out/'FAILURE.json').exists():
                        write(out/'FAILURE.json', failure, exclusive=True)
                    states[key] = failure
            write(root/'digest.json', {'jobs': states, 'utc_seconds': time.time(), 'scientific_acceptance': False})
            if all(d['state'] in ('producer_complete', 'failed_no_retry') for d in states.values()):
                rc = 0 if all(d['state'] == 'producer_complete' for d in states.values()) else 1
                write(root/'EXIT.json', {'exit_code': rc, 'jobs': states,
                      'scientific_acceptance': False, 'test_read': False}, exclusive=True)
                return rc
            time.sleep(q['interval_seconds'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('verify', 'watch', 'worker'))
    parser.add_argument('--queue', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--job')
    args = parser.parse_args()
    path = safe(args.queue)
    if args.op == 'verify':
        verify_queue(path, args.sha256)
    else:
        sys.exit(worker(path, args.sha256, args.job) if args.op == 'worker' else watch(path, args.sha256))
