"""Relay durable experiment events to identity-bound services; never launch NPU.

Publication copies only an independently produced exact approval after its real
successful review terminal and the existing dispatcher validation. Wakeups may
repeat after a crash; dispatcher launch intents remain authoritative.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import threading
import time


def need(ok, why):
    if not ok:
        raise ValueError(why)


def safe(p):
    p = Path(p)
    need(p.is_absolute() and '..' not in p.parts, 'canonical absolute path required')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink rejected')
    return p


def raw(p):
    p = safe(p)
    with p.open('rb') as f:
        a = os.fstat(f.fileno()); b = f.read(); z = os.fstat(f.fileno())
    need((a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
         (z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'changed read')
    return b


def sha(p):
    with safe(p).open('rb') as f:
        a = os.fstat(f.fileno()); h = hashlib.file_digest(f, 'sha256').hexdigest(); z = os.fstat(f.fileno())
    need((a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
         (z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'changed hash')
    return h


def read(p):
    def unique(items):
        d = {}
        for k, v in items:
            need(k not in d, 'duplicate JSON key'); d[k] = v
        return d
    return json.loads(raw(p), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def put(p, d):
    p = safe(p); tmp = safe(p.with_name(p.name + '.pending'))
    with tmp.open('w') as f:
        json.dump(d, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def module(ref):
    need(sha(ref['path']) == ref['sha256'], 'module changed')
    spec = importlib.util.spec_from_file_location('relay_dependency', ref['path'])
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def identity(pid):
    p = Path('/proc') / str(pid)
    fields = (p/'stat').read_text().rsplit(')', 1)[1].split()
    need(fields[0] != 'Z', 'target zombie')
    return dict(pid=pid, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_ticks=str(fields[19]), argv=[v.decode() for v in (p/'cmdline').read_bytes().split(b'\0') if v])


def normalized(i):
    return dict(pid=i['pid'], boot_id=i['boot_id'], start_ticks=str(i['start_ticks']), argv=i['argv'])


def wake(target):
    need(sha(target['service']['path']) == target['service']['sha256'], 'service receipt changed')
    s = read(target['service']['path']); expected = normalized(target['identity'])
    need(normalized(s.get('process', s)) == expected, 'service identity differs')
    fd = os.pidfd_open(expected['pid'])
    try:
        # pidfd opened first; a recycled PID observed afterwards cannot match
        # both the original start tick and boot identity.
        need(identity(expected['pid']) == expected, 'stale process identity')
        signal.pidfd_send_signal(fd, signal.SIGUSR1)
    finally: os.close(fd)


def validate(c):
    need(c['schema'] == 'experiment-event-relay-v1' and c['poll_seconds'] == 15, 'relay contract')
    need(c['npu_launch_allowed'] is False and c['scientific_acceptance'] is False, 'relay authority')
    need(len({e['id'] for e in c['events']}) == len(c['events']), 'duplicate event')
    safe(c['output'])
    for p, h in c['files'].items(): need(sha(p) == h, 'configuration dependency changed')
    for e in c['events']:
        need(e['kind'] in ('release', 'prepared', 'reviewed'), 'event kind')
        for key in ('trigger', 'plan'): safe(e[key])
        need(e['target']['service']['path'] in c['files'] and
             c['files'][e['target']['service']['path']] == e['target']['service']['sha256'], 'unbound service')
        if e['kind'] == 'reviewed':
            for k in ('review', 'intent', 'destination'): safe(e[k])
            need(e['dispatcher_config']['path'] in c['files'] and
                 e['dispatcher']['path'] in c['files'] and
                 e['review_code']['path'] in c['files'] and
                 c['files'][e['review_code']['path']] == e['review_code']['sha256'], 'unbound dispatcher/reviewer')
    return c


def proof(c, e):
    """Return proof only when the durable trigger and its actual inputs exist."""
    if not safe(e['trigger']).exists(): return None
    t = read(e['trigger']); plan = read(e['plan']); pin = sha(e['plan'])
    if e.get('plan_sha256'): need(pin == e['plan_sha256'], 'event plan changed')
    need(plan['run'] == e['run'], 'run identity')
    if e['kind'] == 'release':
        need(t['schema'] == 'r3-resource-release-v1' and t['run'] == e['run'] and
             type(t['exit_code']) is int and t['exit_code'] == 0 and
             t['scientific_acceptance'] is False, 'invalid release')
        need(type(t['chip']) is int and t['chip'] == plan['chip'], 'release chip')
        # The resource guard still validates physical release/current generation.
        return dict(trigger_sha256=sha(e['trigger']), plan_sha256=pin)
    if e['kind'] == 'prepared':
        need(t['schema'] == 'successor-exact-review-request-v1' and
             t['plan'] == dict(path=e['plan'], sha256=pin) and
             t['activation_authorized'] is False and t['npu_launched'] is False,
             'invalid preparation request')
        return dict(trigger_sha256=sha(e['trigger']), plan_sha256=pin)
    need(type(t.get('exit_code')) is int and t['exit_code'] == 0 and t['npu_launched'] is False,
         'review did not successfully finish')
    r = read(e['review']); intent = read(e['intent'])
    need(intent['plan'] == dict(path=e['plan'], sha256=pin) and intent['npu_launched'] is False,
         'review intent differs')
    need(r['reviewer'] == e['reviewer'] and r['review_kind'] == 'independent_execution_review',
         'unexpected independent reviewer')
    need(r['review_evidence'].get(e['review_code']['path']) == e['review_code']['sha256'] and
         sha(e['review_code']['path']) == e['review_code']['sha256'], 'unbound review implementation')
    D = module(e['dispatcher']); dc = read(e['dispatcher_config']['path'])
    need(sha(e['dispatcher_config']['path']) == e['dispatcher_config']['sha256'], 'dispatcher config changed')
    job = next(x for x in dc['jobs'] if x['id'] == e['job'])
    need(job['plan'] == e['plan'] and job['review'] == e['destination'], 'dispatch job differs')
    source_job = dict(job, review=e['review'])
    approval = D.approved(dc, source_job)  # full pinned evidence/command validation, no claim or launch
    need(approval is not None and approval['plan_sha256'] == pin, 'missing exact approval')
    return dict(trigger_sha256=sha(e['trigger']), plan_sha256=pin,
                review_sha256=approval['review_sha256'])


def publish(e, p):
    data = raw(e['review'])
    need(hashlib.sha256(data).hexdigest() == p['review_sha256'], 'review changed before publication')
    dest = safe(e['destination'])
    if dest.exists():
        need(raw(dest) == data, 'different trusted approval exists'); return
    temp = safe(dest.with_name(dest.name + '.relay-pending'))
    with temp.open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    try:
        # Link is no-clobber; another owner publishing different bytes is an error.
        os.link(temp, dest)
    except FileExistsError:
        need(raw(dest) == data, 'trusted approval publication race')
    finally: temp.unlink(missing_ok=True)
    fd = os.open(dest.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def tick(c, state, save, signaler=wake, prover=proof):
    for e in c['events']:
        rec = state['events'].get(e['id'])
        if rec and rec['state'] in ('delivered', 'blocked'): continue
        try:
            p = prover(c, e)
            if p is None: continue
            if rec: need(rec['proof'] == p, 'pending event mutated; reconcile')
            else:
                rec = dict(state='intent', proof=p, utc_seconds=time.time())
                state['events'][e['id']] = rec; save(state)
            if e['kind'] == 'reviewed': publish(e, p)
            signaler(e['target'])
            rec.update(state='delivered', delivered_utc_seconds=time.time()); save(state)
        except Exception as ex:
            state['events'][e['id']] = dict(state='blocked', error=type(ex).__name__+': '+str(ex),
                                           previous=rec, utc_seconds=time.time())
            save(state)
    return state


def run(config, pin, once=False):
    need(sha(config) == pin, 'config changed'); c = validate(read(config))
    root = safe(c['output']); root.mkdir(parents=True, exist_ok=True)
    with (root/'relay.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = root/'STATE.json'; state = read(p) if p.exists() else dict(config_sha256=pin, events={})
        need(state['config_sha256'] == pin, 'state generation differs')
        need(set(state['events']) <= {e['id'] for e in c['events']}, 'foreign events')
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set()); signal.signal(signal.SIGINT, lambda *_: stop.set())
        put(root/'SERVICE.json', dict(process=identity(os.getpid()), config_sha256=pin))
        put(root/'RELAUNCH.json', dict(command=[os.sys.executable, '-B', '-P', str(Path(__file__).resolve()),
            '--config', str(Path(config).resolve()), '--sha256', pin],
            resume='same config/state only; blocked events require explicit new reviewed generation'))
        rc = 1
        try:
            while not stop.is_set():
                need(sha(config) == pin, 'config changed while live')
                tick(c, state, lambda d: put(p, d))
                put(root/'digest.json', dict(utc_seconds=time.time(), states={k:v['state'] for k,v in state['events'].items()},
                                           pending=len(c['events'])-len(state['events']), npu_launched=False))
                if once: break
                stop.wait(c['poll_seconds'])
            rc = 0
        finally: put(root/'EXIT.json', dict(exit_code=rc, utc_seconds=time.time(), npu_launched=False))


if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--config', required=True); ap.add_argument('--sha256', required=True); ap.add_argument('--once', action='store_true')
    a=ap.parse_args(); run(a.config, a.sha256, a.once)
