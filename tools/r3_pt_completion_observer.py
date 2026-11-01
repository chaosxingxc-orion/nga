#!/usr/bin/env python3
"""Deterministic external observer; no authorization creation or producer startup.

watch requires an out-of-band root-pinned authorization and a separate writer UID.
Root is the operator, not a claim made by a producer JSON document. The process
and filesystem checks are cooperative deployment checks, not a hostile OS sandbox.
"""
import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import sys
import time
import types

GEN = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/pt_formal_prepare_successor_20261101_v3')
REQUEST_PIN = 'bca80be89c0fb9c49200be68ed98c1e6255437e2ad7337795437876fb5af0da9'
MANIFEST_PIN = 'b2e59e04762951949d545e467f8faec93c8a8f608a5050612cabb04ebd19b180'
WORKER_PIN = '54c8251ab7e72a3e71c591452cd526d75a5c776f47e8c5450c593fa2e046a288'
MAPPING_PIN = '3d42f76158d86e54fd2039c23838f597b405b972766e277b64f3b6ff2cb6d621'
CONTRACT_PIN = '5d41b777977f4082178b5d30eeec7f29f72c219537d1be3f5526275ada169ec8'
REVIEW_PIN = 'b1f49399e0dd1ef2132a99219287dbd724ebd2c82c85156f95fd69071a302066'
FALLBACK_SECONDS = 600


class Block(ValueError):
    """Preserve evidence; explicit root inspection/new generation required."""


def require(ok, why):
    if not ok:
        raise Block(why)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'non-concrete pin')
    return value


def safe(path):
    p = Path(path)
    require(p.is_absolute() and str(p) == str(path) and '..' not in p.parts, 'unsafe path')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
    require(p.suffix != '.log' and not str(p).startswith('/dev/'), 'log/device forbidden')
    return p


def read(path):
    p = safe(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode), 'nonregular input')
        raw = f.read()
        after = os.fstat(f.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'unstable read')
    return raw


def checked(ref):
    require(set(ref) == {'path', 'sha256'}, 'invalid reference')
    raw = read(ref['path'])
    require(digest(raw) == pin(ref['sha256']), 'pin differs: ' + ref['path'])
    return raw


def document(ref):
    return json.loads(checked(ref))


def reference(path):
    return {'path': str(path), 'sha256': digest(read(path))}


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable(path, value):
    """O_EXCL intentionally retains incomplete files; never adopt partial bytes."""
    path = safe(path)
    raw = canonical(value)
    if path.exists():
        # Validate and sync the same opened record, never rewrite retained bytes.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            require(stat.S_ISREG(os.fstat(f.fileno()).st_mode), 'nonregular input')
            require(f.read() == raw, 'conflict/partial write: ' + str(path))
            os.fsync(f.fileno())
        fsync_dir(path.parent)
        return reference(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fsync_dir(path.parent)
    return reference(path)


@contextlib.contextmanager
def exclusive(path):
    fd = os.open(safe(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def process_identity(pid):
    """Read only /proc metadata; never emit environment values (may contain secrets)."""
    require(type(pid) is int and pid > 1, 'invalid PID')
    base = Path('/proc') / str(pid)
    def procstat():
        return (base/'stat').read_text().rsplit(')', 1)[1].split()
    before = procstat()
    require(before[0] not in ('Z', 'X'), 'owner exited')
    exe = str((base/'exe').resolve(strict=True))
    result = {'pid': pid, 'start_ticks': before[19],
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'command': [os.fsdecode(x) for x in (base/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')],
              'environment_sha256': digest((base/'environ').read_bytes()),
              'uid': base.stat().st_uid, 'exe': reference(exe),
              'cwd': str((base/'cwd').resolve(strict=True))}
    after = procstat()
    require(before[19] == after[19] and after[0] not in ('Z', 'X'), 'PID changed/exited during inspection')
    return result


def live_identity(expected):
    try:
        actual = process_identity(expected['pid'])
    except (OSError, ValueError) as e:
        raise Block('owner disappeared/uninspectable; explicit root repair required') from e
    require(actual == expected, 'owner PID reuse/runtime/command/environment differs; root repair required')
    return actual


def stable(paths, seconds=0.05):
    before = {str(p): read(p) for p in paths}
    time.sleep(seconds)
    after = {str(p): read(p) for p in paths}
    require(before == after, 'completion mutated during stable observation')
    return before


def private_directory(path, uid, mode=0o700):
    p = safe(path)
    s = p.stat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == uid and stat.S_IMODE(s.st_mode) == mode,
            'observer directory owner/mode differs')
    # Writable ancestors allow replacement; sticky system temp directories are OK.
    for parent in p.parents:
        s = parent.stat()
        require(not (s.st_mode & 0o022) or bool(s.st_mode & stat.S_ISVTX),
                'writable ancestor of authority/state directory')
    return p


def runtime_inventory(ref):
    obj = document(ref)
    require(obj.get('schema') == 'pt-observer-runtime-inventory-v1', 'runtime inventory schema')
    require(obj.get('files') and obj.get('roots'), 'empty runtime inventory')
    actual_paths = set()
    for root in obj['roots']:
        root = safe(root)
        require(root.is_dir(), 'runtime root absent')
        for p in root.rglob('*'):
            if p.is_file():
                # Root records real targets; symlink identities are separately bound.
                actual_paths.add(str(p.resolve(strict=True)))
    require(actual_paths == set(obj['files']), 'runtime membership changed')
    for path, h in obj['files'].items():
        checked({'path': path, 'sha256': h})
    actual_links = {str(p): os.readlink(p) for root in obj['roots']
                    for p in Path(root).rglob('*') if p.is_symlink()}
    require(actual_links == obj.get('symlinks', {}), 'runtime symlink membership changed')
    for path, target in obj.get('symlinks', {}).items():
        require(Path(path).is_symlink() and os.readlink(path) == target, 'runtime symlink changed')
    return obj


def load_producer():
    ref = {'path': str(GEN/'r3_pt_formal_prepare_successor.py'), 'sha256': WORKER_PIN}
    raw = checked(ref)
    mod = types.ModuleType('pt_v3_observer_producer')
    mod.__file__ = ref['path']
    exec(compile(raw, ref['path'], 'exec', dont_inherit=True), mod.__dict__)
    return mod


def load_config(ref):
    c = document(ref)
    require(c.get('schema') == 'pt-completion-observer-config-v1', 'configuration schema')
    expected = {'request': (GEN/'REQUEST.json', REQUEST_PIN),
                'manifest': (GEN/'MANIFEST.json', MANIFEST_PIN),
                'worker': (GEN/'r3_pt_formal_prepare_successor.py', WORKER_PIN),
                'mapping': (GEN/'OBSERVER_MAPPING.json', MAPPING_PIN),
                'contract': (GEN/'OBSERVER_INTEGRATION_CONTRACT.md', CONTRACT_PIN)}
    for key, (path, h) in expected.items():
        require(c[key] == {'path': str(path), 'sha256': h}, 'different frozen v3 ' + key)
        checked(c[key])
    require(c['fallback_seconds'] == FALLBACK_SECONDS, 'fallback must be 600 seconds')
    state = safe(c['state_directory'])
    require(not state.is_relative_to(GEN), 'observer state must be separate from producer')
    r, mapping = document(c['request']), document(c['mapping'])
    q = document(r['queue'])
    rq = document({'path': q['producer']['queue'], 'sha256': q['producer']['queue_sha256']})
    expected_bindings = {'queue': r['queue'], 'precheck_service': r['precheck_service'],
                        'precheck_activation': r['precheck_activation'],
                        'precheck_worker': {'path': q['worker'], 'sha256': q['worker_sha256']},
                        'report_queue': mapping['report_queue'], 'report_job': q['producer']['job'],
                        'report_controller': {'path': rq['controller'], 'sha256': rq['controller_sha256']}}
    require(c['bindings'] == expected_bindings, 'configuration upstream bindings differ')
    require(mapping['request'] == c['request'] and mapping['report_job'] == q['producer']['job']
            and mapping['report_queue'] == {'path': q['producer']['queue'], 'sha256': q['producer']['queue_sha256']},
            'mapping upstream differs')
    for key, value in expected_bindings.items():
        if key != 'report_job':
            checked(value)
    require(c['artifact_paths'] == mapping['artifact_paths'] and len(set(c['artifact_paths'])) == 5,
            'five artifact paths differ')
    return c, r, q


def authenticate(config_ref, authorization_ref):
    """Root supplies the actual authorization hash on the protected launch command."""
    c, r, q = load_config(config_ref)
    a = document(authorization_ref)
    require(a.get('schema') == 'pt-completion-observer-root-authorization-v1'
            and a.get('config') == config_ref and a.get('observer') == reference(Path(__file__).absolute())
            and a.get('authorized') is True and a.get('scientific_acceptance') is False
            and a.get('training_authorized') is False, 'root authorization differs')
    uid = os.geteuid()
    require(type(a.get('observer_uid')) is int and a['observer_uid'] == uid, 'observer UID differs')
    private_directory(Path(authorization_ref['path']).parent, uid)
    auth_stat = Path(authorization_ref['path']).stat()
    require(auth_stat.st_uid == uid and not auth_stat.st_mode & 0o022, 'authorization file owner/mode differs')
    private_directory(c['state_directory'], uid, 0o755)
    require(Path(c['state_directory']) != Path(authorization_ref['path']).parent, 'separate authorization and state directories required')
    for name in ('source_review', 'publication', 'producer_deployment', 'upstream_launch_evidence', 'member_launch_evidence'):
        checked(a[name])
    review = document(a['producer_review'])
    require(a['producer_review']['sha256'] == REVIEW_PIN and review.get('verdict') == 'PASS', 'producer review differs')
    parent = document(a['producer_parent_decision'])
    require(parent.get('review_sha256') == REVIEW_PIN and parent.get('decision') == 'ACCEPT_EXACT_OFFLINE_CPU_PRODUCER_READINESS',
            'producer parent decision differs')
    service = document(r['precheck_service'])
    report_service = document(a['report_service'])
    require(a['report_service']['path'] == str(Path(q['producer']['queue']).parent/'SERVICE.json'), 'report SERVICE location differs')
    require(set(a['owners']) == {'report', 'precheck'}, 'completion owners differ')
    for role, receipt in (('report', report_service), ('precheck', service)):
        owner = a['owners'][role]
        require(owner['pid'] == receipt['pid'] and owner['command'] == receipt['command']
                and type(owner['uid']) is int and owner['uid'] != uid, 'separate owner/observer authority required')
        if 'start_ticks' in receipt:
            require(owner['start_ticks'] == receipt['start_ticks'], 'service start ticks differ')
    report_command = a['owners']['report']['command']
    require(report_command[1:] == ['-P', c['bindings']['report_controller']['path'], 'watch', '--manifest',
                                 q['producer']['queue'], '--sha256', q['producer']['queue_sha256']], 'report command differs')
    activation = document(r['precheck_activation'])
    require(activation.get('service') == service and activation.get('process_identity_verified') is True
            and activation.get('queue_sha256') == r['queue']['sha256'], 'precheck activation identity differs')
    require(a['owners']['precheck']['command'] == [r['python'], '-B', '-P', q['worker'], 'watch', '--queue',
                                                  r['queue']['path'], '--sha256', r['queue']['sha256']], 'precheck command differs')
    require(str(Path(sys.executable).resolve()) == str(Path(r['python']).resolve()), 'retained Python runtime required')
    require(sys.dont_write_bytecode and sys.flags.safe_path, 'observer requires -B -P')
    for key, value in r['runtime_environment'].items():
        require(os.environ.get(key) == value, 'required runtime environment differs: ' + key)
    require(a['observer_runtime']['executable'] == str(Path(sys.executable).resolve())
            and a['observer_runtime']['environment_sha256'] == digest(Path('/proc/self/environ').read_bytes())
            and a['observer_runtime']['cwd'] == str(Path.cwd()), 'observer runtime/environment differs')
    require([authorization_ref['sha256'] if x == '{ROOT_AUTH_SHA256}' else x
             for x in a['observer_runtime']['command']] == [os.fsdecode(x) for x in Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')],
            'observer launch command differs')
    for role in ('report', 'precheck'):
        require(a['owners'][role]['exe']['sha256'] == reference(a['owners'][role]['exe']['path'])['sha256'],
                'owner executable changed')
    for name in ('observer', 'report', 'precheck'):
        inv = runtime_inventory(a['runtime_inventories'][name])
        executable = a['observer_runtime']['executable'] if name == 'observer' else a['owners'][name]['exe']['path']
        require(executable in inv['files'], 'runtime inventory omits executable')
    return c, r, q, a


class Events:
    """Local inotify plus periodic reconciliation (Ceph events may not be delivered)."""
    def __init__(self, paths):
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        require(self.fd >= 0, 'inotify unavailable; root repair required')
        self.libc = libc
        self.paths = paths
        self.watches = {}
        self.refresh()

    def refresh(self):
        for path in self.paths:
            parent = Path(path).parent
            while not parent.exists():
                parent = parent.parent
            if str(parent) not in self.watches:
                wd = self.libc.inotify_add_watch(self.fd, os.fsencode(safe(parent)),
                                                0x8 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800 | 0x4)
                require(wd >= 0, 'cannot watch completion directory')
                self.watches[str(parent)] = wd

    def wait(self, seconds=FALLBACK_SECONDS):
        ready, _, _ = select.select([self.fd], [], [], seconds)
        if ready:
            # All notifications are hints, including overflow; reconcile everything.
            while True:
                try:
                    os.read(self.fd, 65536)
                except BlockingIOError:
                    break
            self.watches.clear()
        self.refresh()
        return bool(ready)

    def close(self):
        os.close(self.fd)


class Observer:
    def __init__(self, config, request, queue, authorization, auth_ref, config_ref, producer):
        self.c, self.r, self.q, self.a = config, request, queue, authorization
        self.auth_ref, self.config_ref, self.producer = auth_ref, config_ref, producer
        self.root = Path(config['state_directory'])
        self.paths = config['artifact_paths']
        self.groups = {'report': self.paths[:2], 'precheck': self.paths[2:]}
        self.binding = {'authorization': auth_ref, 'config': config_ref}

    def guards(self):
        checked(self.auth_ref)
        checked(self.config_ref)
        checked(self.c['worker'])
        checked(self.a['observer'])
        for key in ('queue', 'precheck_service', 'precheck_activation', 'report_queue', 'report_controller', 'precheck_worker'):
            checked(self.c['bindings'][key])

    def restore(self):
        for path in self.root.iterdir():
            require(path.is_file() and not path.is_symlink(), 'nonregular observer state')
            require(path.stat().st_uid == os.geteuid() and not path.stat().st_mode & 0o022,
                    'observer state owner/mode differs')
        allowed = {'observer.lock', 'STARTED.json', 'OWNER_report.json', 'OWNER_precheck.json',
                   'AUTHENTICATION.json', 'PROVENANCE.json', 'SIGNALLED.json', 'BLOCKED.json'}
        require(set(p.name for p in self.root.iterdir()) <= allowed, 'unknown/partial state files; root repair required')
        require(not (self.root/'BLOCKED.json').exists(), 'prior block requires root repair/new generation')
        started = {'schema': 'pt-observer-started-v1', **self.binding, 'owners': self.a['owners']}
        if (self.root/'STARTED.json').exists():
            require(json.loads(read(self.root/'STARTED.json')) == started, 'partial/conflicting startup')
            durable(self.root/'STARTED.json', started)
        else:
            require(not any((self.root/name).exists() for name in allowed - {'observer.lock'}), 'orphan state')
            for owner in self.a['owners'].values():
                live_identity(owner)
            durable(self.root/'STARTED.json', started)
        # Every uncompleted owner must still exist on restart; never adopt EXIT alone.
        for role in self.groups:
            if (self.root/f'OWNER_{role}.json').exists():
                # Existence alone cannot justify the live-owner exemption.
                self.owner(role)
            else:
                live_identity(self.a['owners'][role])
        if (self.root/'AUTHENTICATION.json').exists():
            require((self.root/'PROVENANCE.json').exists(), 'authentication without provenance')
        if (self.root/'SIGNALLED.json').exists():
            require((self.root/'AUTHENTICATION.json').exists(), 'signal receipt without authentication')

    def owner(self, role):
        path = self.root/f'OWNER_{role}.json'
        expected = {'schema': 'pt-observer-owner-completion-v1', **self.binding,
                    'role': role, 'owner': self.a['owners'][role]}
        if path.exists():
            doc = json.loads(read(path))
            require({k: doc.get(k) for k in expected} == expected and set(doc) == set(expected) | {'artifacts'},
                    'partial/wrong completion owner')
            require(set(doc['artifacts']) == set(self.groups[role]), 'owner artifact paths differ')
            for p, h in doc['artifacts'].items():
                checked({'path': p, 'sha256': h})
            # A crash can leave complete flushed bytes before their first fsync.
            # Establish file + directory durability before relying on ownership.
            durable(path, doc)
            return doc
        live_identity(self.a['owners'][role])
        if not Path(self.groups[role][0]).exists():
            return None
        # Both fences must be live: disappeared owner + terminal is never authority.
        raw = stable(self.groups[role])
        end = json.loads(raw[self.groups[role][0]])
        require(type(end.get('exit_code')) is int and end['exit_code'] == 0
                and end.get('scientific_acceptance') is False, 'failed/partial terminal')
        if role == 'report':
            require(end.get('output_sha256') == digest(raw[self.groups[role][1]]), 'report terminal hash differs')
        else:
            require(end.get('queue_sha256') == self.r['queue']['sha256'] and end.get('test_read') is False
                    and end.get('validation_sha256') == digest(raw[self.groups[role][1]])
                    and end.get('output_sha256') == digest(raw[self.groups[role][2]]), 'precheck terminal linkage differs')
        live_identity(self.a['owners'][role])
        doc = {**expected, 'artifacts': {p: digest(b) for p, b in raw.items()}}
        durable(path, doc)
        return doc

    def linkage(self, hashes):
        result = self.producer.dependency(self.r)
        require(result is not None and result.get('state') == 'WAIT_EXTERNAL_COMPLETION_AUTHENTICATION'
                and result.get('observed') == hashes, 'actual full dependency linkage differs')
        service = document(self.r['precheck_service'])
        activation = document(self.r['precheck_activation'])
        require(activation.get('service') == service and activation.get('process_identity_verified') is True
                and activation.get('queue_sha256') == self.r['queue']['sha256'], 'SERVICE/ACTIVATION differs')
        for p, h in hashes.items():
            checked({'path': p, 'sha256': h})

    def step(self):
        self.guards()
        self.restore()
        owners = {role: self.owner(role) for role in self.groups}
        if any(v is None for v in owners.values()):
            return 'WAIT_GENUINE_COMPLETION'
        hashes = {p: h for v in owners.values() for p, h in v['artifacts'].items()}
        require(set(hashes) == set(self.paths), 'exact five artifacts required')
        require({p: digest(b) for p, b in stable(self.paths).items()} == hashes, 'stale owned completion')
        self.linkage(hashes)  # Actual pinned waiter + dependency; not a numerical PASS.
        provenance = {'schema': 'pt-observer-provenance-v1', **self.binding,
                      'owners': {role: reference(self.root/f'OWNER_{role}.json') for role in self.groups},
                      'artifacts': hashes, 'dependency_state': 'AUTHENTICATED_LINKAGE_ONLY',
                      'scientific_acceptance': False}
        prov_ref = durable(self.root/'PROVENANCE.json', provenance)
        self.guards()
        self.linkage(hashes)
        authentication = {'schema': 'r3-pt-precheck-authentication-v1',
                          'external_process_and_terminal_authenticated': True,
                          'queue': self.r['queue'], 'precheck_service': self.r['precheck_service'],
                          'worker_sha256': self.q['worker_sha256'], 'artifacts': hashes,
                          'scientific_acceptance': False, 'observer_provenance': prov_ref,
                          'root_authorization': self.auth_ref}
        auth = durable(self.root/'AUTHENTICATION.json', authentication)
        self.guards()
        self.linkage(hashes)
        # Execute the exact frozen signal implementation from its checked buffer.
        # No producer start/run, numerical validation, child process or arbitrary command.
        result = self.producer.send_signal(Path(self.c['request']['path']), self.c['request']['sha256'],
                                           Path(auth['path']), auth['sha256'])
        require(result.get('signal_retained') is True, 'signal failed')
        envelope = {'request_sha256': self.c['request']['sha256'], 'authentication': auth}
        require(read(Path(self.r['root'])/'SIGNAL.json') == self.producer.canonical(envelope), 'durable producer envelope differs')
        self.guards()
        self.linkage(hashes)
        durable(self.root/'SIGNALLED.json', {'schema': 'pt-observer-signalled-v1', **self.binding,
                                           'authentication': auth, 'envelope': reference(Path(self.r['root'])/'SIGNAL.json')})
        return 'SIGNALLED'


def watch(config_ref, authorization_ref):
    c, r, q, a = authenticate(config_ref, authorization_ref)
    producer = load_producer()
    producer.deployment(r, c['request']['sha256'], Path(a['producer_deployment']['path']),
                        a['producer_deployment']['sha256'])
    # Actual request validation checks the reviewed source/data closure, without TEST.
    require(producer.request(Path(c['request']['path']), c['request']['sha256']) == r, 'producer request differs')
    observer = Observer(c, r, q, a, authorization_ref, config_ref, producer)
    with exclusive(observer.root/'observer.lock'):
        events = Events(c['artifact_paths'])
        try:
            while True:
                state = observer.step()
                print(json.dumps({'state': state, 'utc_seconds': time.time(), 'fallback_seconds': FALLBACK_SECONDS}), flush=True)
                if state == 'SIGNALLED':
                    return 0
                events.wait()
        except Exception as e:
            # A bounded pointer, no traceback/raw logs, no destructive repair.
            durable(observer.root/'BLOCKED.json', {'schema': 'pt-observer-block-v1',
                    'error_type': type(e).__name__, 'reason': str(e)[:700],
                    'repair': 'Preserve this generation; root must inspect and explicitly authorize a new generation.'})
            raise
        finally:
            events.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=['inspect-process', 'check-config', 'watch'])
    p.add_argument('--pid', type=int)
    p.add_argument('--config')
    p.add_argument('--config-sha256')
    p.add_argument('--authorization')
    p.add_argument('--authorization-sha256')
    args = p.parse_args()
    if args.op == 'inspect-process':
        print(json.dumps(process_identity(args.pid), indent=2, sort_keys=True))
    elif args.op == 'check-config':
        c, _, _ = load_config({'path': args.config, 'sha256': args.config_sha256})
        print(json.dumps({'status': 'CONFIG_PINS_VALID_ONLY', 'artifacts': c['artifact_paths'], 'activation': False}))
    else:
        return watch({'path': args.config, 'sha256': args.config_sha256},
                     {'path': args.authorization, 'sha256': args.authorization_sha256})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Block, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'BLOCK_ROOT_REPAIR_REQUIRED', 'reason': str(error)[:700]}), file=sys.stderr)
        raise SystemExit(2)
