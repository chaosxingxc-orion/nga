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

# Passed to Python as immutable command text; target bytes are read once, checked
# against the externally supplied pin, then compiled from that same buffer.
BOOTSTRAP = '''import hashlib,os,stat,sys
from pathlib import Path
p=Path(sys.argv[1]);pin=sys.argv[2];args=sys.argv[3:]
if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('unsafe controller')
fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
with os.fdopen(fd,'rb') as f:
 s=os.fstat(f.fileno())
 if not stat.S_ISREG(s.st_mode):raise ValueError('nonregular controller')
 raw=f.read()
if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('controller bytes changed')
sys.argv=[str(p),*args]
exec(compile(raw,str(p),'exec',dont_inherit=True),{'__name__':'__main__','__file__':str(p),'_EXECUTED_SHA256':pin})
'''


def command(q, op, path, pin, key=None):
    args = [sys.executable, '-P', '-c', BOOTSTRAP, q['controller']['path'],
            q['controller']['sha256'], op, '--queue', str(path), '--sha256', pin]
    return args + (['--job', key] if key is not None else [])


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


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def snapshot(path, expected=None):
    raw = read(path)
    pin = hashlib.sha256(raw).hexdigest()
    require(expected is None or pin == expected, 'artifact changed: '+str(path))
    return parse(raw), pin


def load(path):
    return snapshot(path)[0]


def canonical_pin(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


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
    q, _ = snapshot(path, pin)
    scope(q)
    require(q['schema'] == 'r3-member-rebuild-queue-v4', 'queue schema differs')
    require(q['controller']['path'] == str(Path(__file__).resolve())
            and globals().get('_EXECUTED_SHA256') == q['controller']['sha256'],
            'controller must execute verified bytes via bootstrap')
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
    q, _ = snapshot(job['producer_queue'], job['producer_queue_sha256'])
    matches = [j for j in q['jobs'] if j['id'] == job['id']]
    require(len(matches) == 1 and matches[0].get('kind') == 'report'
            and matches[0].get('output') == job['report'], 'producer job/output mapping differs')
    require(sum(j.get('output') == job['report'] for j in q['jobs']) == 1,
            'producer output has multiple owners')
    require(Path(job['terminal']) == Path(job['producer_queue']).parent/'jobs'/job['id']/'EXIT.json',
            'producer terminal owner differs')
    terminal, terminal_pin = snapshot(job['terminal'])
    zero(terminal)
    require(terminal.get('scientific_acceptance') is False, 'producer scope differs')
    report_pin = sha(job['report'])
    require(terminal['output_sha256'] == report_pin, 'producer output differs')
    return {'queue': {'path': job['producer_queue'], 'sha256': job['producer_queue_sha256']},
            'terminal': {'path': job['terminal'], 'sha256': terminal_pin},
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
    h = C.scope(snapshot(job['report'], bindings['report']['sha256'])[0])
    e = job['expected']
    require(h['arm'] == e['arm'] and h['model']['base_path'] == e['base']
            and h['model']['path'] == (e['adapter'] or e['base']), 'report model differs')
    if e['adapter'] and entry['adapter_inventory'] is None:
        train = safe(e['adapter']).parent/'TRAIN_EXIT.json'
        train_doc, train_pin = snapshot(train)
        zero(train_doc)
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
    req, _ = snapshot(root/'request.json', intent['request_sha256'])
    scope(req)
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


def reconstruction_payload(document, req, q):
    member = document['member']
    require(isinstance(document.get('evidence'), dict), 'reconstruction payload required')
    evidence = document['evidence']
    require(member.get('verified_evidence_sha256') == canonical_pin(evidence),
            'reconstruction digest differs')
    require(evidence['report'] == req['entry']['report'], 'reconstructed report binding differs')
    tool = next(p for p in q['code'] if p.endswith('/r3_selection_report.py'))
    expected_code = {'report_tool': {'path': tool, 'sha256': q['code'][tool]},
        'closure_manifest': q['closure_manifest'],
        'consumer_sha256': q['code'][next(p for p in q['code'] if p.endswith('/r3_campaign_sources.py'))],
        'structure_sha256': q['code'][next(p for p in q['code'] if p.endswith('/r3_final_campaign.py'))],
        'inventory_sha256': q['code'][next(p for p in q['code'] if p.endswith('/r3_model_inventory.py'))]}
    require(evidence['code'] == expected_code, 'reconstruction code differs')
    inventories = {}
    for name, entry in req['entry'].items():
        if name.endswith('_inventory') and entry is not None:
            inv, _ = snapshot(entry['path'], entry['sha256'])
            require(canonical_pin(inv['inventory']) == inv['inventory_sha256'], 'inventory digest differs')
            inventories[name] = inv['inventory_sha256']
    require(evidence['inventories'] == inventories, 'reconstruction inventory differs')
    require(member['model']['base_inventory_sha256'] == inventories['base_inventory'], 'member base inventory differs')
    report, _ = snapshot(req['entry']['report']['path'], req['entry']['report']['sha256'])
    require(evidence['reconstructed_report_sha256'] == canonical_pin(report), 'report reconstruction digest differs')
    require(isinstance(evidence.get('source_snapshot'), dict)
            and set(evidence['source_snapshot']) == {'files', 'trees', 'models'}
            and all(evidence['source_snapshot'].values()), 'source snapshot missing')
    for entry in req['entry'].values():
        if entry is not None:
            require(evidence['source_snapshot']['files'].get(entry['path']) == entry['sha256'],
                    'snapshot artifact binding differs')
    if 'training' in member:
        require(evidence.get('training') == member['training'], 'training evidence differs')


def failure_state(failure, key, pin):
    scope(failure)
    require(failure.get('state') == 'failed_no_retry'
            and failure.get('job_id') == key and failure.get('queue_sha256') == pin,
            'invalid persisted failure')
    return {'state': 'failed_no_retry', 'job_id': key, 'error': failure.get('error', '')}


def reconstruct(req, q):
    """Replay the real source verifier, including full reports and model bytes.

Recovered completion has the same requirements as fresh completion; a collection
of mutually consistent saved hashes cannot stand in for this computation.
    """
    C = sources(q)
    C.artifact(q['closure_manifest'])
    tool_path = next(p for p in q['code'] if p.endswith('/r3_selection_report.py'))
    tool = C.module(tool_path, 'pinned_report')
    deps = tool.modules(Path(q['closure_manifest']['path']).parent/'r3_code',
                        manifest_pin=q['closure_manifest']['sha256'])
    code = {'report_tool': {'path': tool_path, 'sha256': q['code'][tool_path]},
            'closure_manifest': q['closure_manifest'],
            'consumer_sha256': q['code'][C.__file__],
            'structure_sha256': q['code'][str(C.HERE/'r3_final_campaign.py')],
            'inventory_sha256': q['code'][str(C.HERE/'r3_model_inventory.py')]}
    member, evidence = C.rebuild_member(req['entry'], tool, deps, q['kev_dir'], q['data_root'], code)
    C.artifact(q['closure_manifest'])
    identity(member, req['expected'])
    return member, evidence


def completed(root, job, queue_path, pin):
    require(not safe(root/'FAILURE.json').exists(), 'persisted failure forbids completion')
    req = validate_request(root, job, queue_path, pin)
    end = load(root/'EXIT.json')
    scope(end)
    zero(end)
    result, result_pin = snapshot(root/'RESULT.json', end['result_sha256'])
    scope(result)
    request_doc, request_pin = snapshot(root/'request.json')
    require(request_doc == req, 'request changed during completion')
    for d in (end, result):
        require(d['request_sha256'] == request_pin and d['queue_sha256'] == pin
                and d['job_id'] == job['id'], 'completion identity differs')
    require(result['producer'] == req['producer'], 'result producer differs')
    require(set(result['outputs']) == {'evidence.json'}, 'exact singleton output required')
    evidence, _ = snapshot(root/'evidence.json', result['outputs']['evidence.json'])
    scope(evidence)
    require(evidence['request_sha256'] == request_pin and evidence.get('job_id') == job['id']
            and evidence.get('queue_sha256') == pin, 'evidence envelope differs')
    identity(evidence['member'], job['expected'])
    q, _ = snapshot(queue_path, pin)
    reconstruction_payload(evidence, req, q)
    member_now, evidence_now = reconstruct(req, q)
    require(canonical_pin(member_now) == canonical_pin(evidence['member'])
            and canonical_pin(evidence_now) == canonical_pin(evidence['evidence']),
            'saved completion differs from actual source reconstruction')
    require(validate_request(root, job, queue_path, pin) == req, 'request changed during completion rebuild')
    return {'state': 'producer_complete', 'root': str(root), 'result_sha256': result_pin,
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
        member, evidence = reconstruct(req, q)
        verify_queue(path, pin)
        require(validate_request(root, job, path, pin) == req, 'request changed during rebuild')
        write(root/'evidence.json', dict(common, member=member, evidence=evidence), exclusive=True)
        write(root/'RESULT.json', dict(common, producer=req['producer'],
              outputs={'evidence.json': sha(root/'evidence.json')}), exclusive=True)
        write(root/'EXIT.json', dict(common, exit_code=0, result_sha256=sha(root/'RESULT.json')), exclusive=True)
        # The supervisor's completion path independently replays reconstruction.
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
        accepted = {}  # Process-local only: a restart must reconstruct again.
        while True:
            verify_queue(path, pin)
            states = {}
            for job in q['jobs']:
                key = job['id']
                out = safe(root/'members'/key)
                try:
                    if key in accepted:
                        require(all(sha(out/name) == h for name,h in accepted[key]['pins'].items()),
                                'completed receipt changed')
                        states[key] = accepted[key]['state']
                        continue
                    if (out/'FAILURE.json').exists():
                        failure = load(out/'FAILURE.json')
                        states[key] = failure_state(failure, key, pin)
                        continue
                    if (out/'EXIT.json').exists():
                        states[key] = completed(out, job, path, pin)
                        accepted[key] = {'state': states[key], 'pins': {name: sha(out/name) for name in
                            ('INTENT.json', 'request.json', 'RESULT.json', 'EXIT.json', 'evidence.json')}}
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
                    cmd = command(q, 'worker', path, pin, key)
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
                    accepted[key] = {'state': states[key], 'pins': {name: sha(out/name) for name in
                        ('INTENT.json', 'request.json', 'RESULT.json', 'EXIT.json', 'evidence.json')}}
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
