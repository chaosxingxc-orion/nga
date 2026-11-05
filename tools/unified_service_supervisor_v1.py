#!/usr/bin/env python3
"""Single-owner local supervisor for the registered unified event service."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import math
import select
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
REGISTRY = {'unified_event_service_v1': (HERE / 'unified_event_service_v1.py', 'serve'),
            'synthetic_fake_physical_v1': (HERE / 'test_unified_service_supervisor_v1.py', '--fake-service')}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(x, expected=None):
    require(type(x) is dict and set(x) == {'path', 'sha256'}, 'invalid pin')
    require(type(x['path']) is str and Path(x['path']).is_absolute() and str(Path(x['path']).resolve()) == x['path'], 'path must be absolute and resolved')
    require(type(x['sha256']) is str and re.fullmatch('[0-9a-f]{64}', x['sha256']), 'invalid digest')
    require(expected is None or x['path'] == str(expected.resolve()), 'unregistered entry')
    require(digest(x['path']) == x['sha256'], 'pin mismatch: ' + x['path'])


def load(path, sha):
    pin({'path': path, 'sha256': sha})
    c = json.loads(Path(path).read_bytes())
    require(type(c) is dict and set(c) == {'schema', 'service', 'entry', 'python', 'service_config', 'supervisor', 'state_dir', 'heartbeat_seconds', 'max_retries', 'retry_backoff_seconds'}, 'closed config required')
    require(c['schema'] == 'unified-service-supervisor-v1' and c['service'] in REGISTRY, 'unknown service')
    require(type(c['heartbeat_seconds']) is int and 10 <= c['heartbeat_seconds'] <= 30, 'invalid heartbeat cadence')
    require(type(c['max_retries']) is int and 0 <= c['max_retries'] <= 100, 'invalid retry budget')
    require(type(c['retry_backoff_seconds']) is int and 1 <= c['retry_backoff_seconds'] <= 3600, 'invalid retry backoff')
    pin(c['entry'], REGISTRY[c['service']][0]); pin(c['python']); pin(c['service_config']); pin(c['supervisor'], Path(__file__))
    require(type(c['state_dir']) is str and Path(c['state_dir']).is_absolute() and str(Path(c['state_dir']).resolve()) == c['state_dir'], 'invalid state directory')
    require(os.access(c['python']['path'], os.X_OK), 'interpreter not executable')
    return c


def atomic(path, obj):
    path = Path(path); tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    with tmp.open('x') as f:
        json.dump(obj, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def identity(pid):
    try:
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        s = Path('/proc/%d/stat' % pid).read_text(); fields = s[s.rfind(')') + 2:].split()
        if fields[0] == 'Z': return None
        return {'boot_id': boot, 'pid': pid, 'starttime': fields[19]}
    except (OSError, IndexError): return None


def matches(ident):
    return type(ident) is dict and type(ident.get('pid')) is int and identity(ident['pid']) == ident


def terminate_matching(ident):
    if not matches(ident): return False
    # pidfd pins the kernel process identity across the check and signal.
    try:
        fd = os.pidfd_open(ident['pid'])
        try:
            if not matches(ident): return False
            signal.pidfd_send_signal(fd, signal.SIGTERM)
            return True
        finally: os.close(fd)
    except (OSError, AttributeError): return False


def read(path): return json.loads(Path(path).read_bytes())


def relaunch(c, path, sha, root):
    argv = [c['python']['path'], '-B', '-P', str(Path(__file__).resolve()), 'start', '--config', path, '--sha256', sha]
    p = root / 'relaunch.sh'; tmp = root / ('.relaunch.' + uuid.uuid4().hex)
    with tmp.open('x') as f:
        f.write('#!/bin/sh\nexec ' + shlex.join(argv) + '\n'); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, 0o700); os.replace(tmp, p)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def start(path, sha):
    c = load(path, sha); root = Path(c['state_dir']); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (root / 'owner.lock').open('a')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: return 0
    relaunch(c, path, sha, root)
    # A separate session and inherited lock remove the caller's lifetime from ownership.
    with (root / 'supervisor.log').open('ab', buffering=0) as log:
        subprocess.Popen([c['python']['path'], '-B', '-P', str(Path(__file__).resolve()), 'monitor', '--config', path, '--sha256', sha, '--lock-fd', str(lock.fileno())], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, pass_fds=(lock.fileno(),))
    lock.close(); return 0


def runner(path, sha, attempt, lock_fd):
    lock = os.fdopen(lock_fd, 'a'); root = Path(attempt)
    try:
        c = load(path, sha)
        require(root.parent == Path(c['state_dir']) / 'attempts' and root.name.isdecimal(), 'bad attempt')
        atomic(root / 'runner.json', identity(os.getpid()))
        # This intent precedes process creation: absence of a terminal is never success.
        atomic(root / 'intent.json', {'generation': root.name, 'state': 'launching'})
        entry, verb = REGISTRY[c['service']]
        argv = [c['python']['path'], '-B', '-P', str(entry), verb, '--config', c['service_config']['path'], '--sha256', c['service_config']['sha256']]
        with (root / 'stdout.log').open('ab', buffering=0) as out, (root / 'stderr.log').open('ab', buffering=0) as err:
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            ident = identity(child.pid)
            atomic(root / 'service.json', {'generation': root.name, 'identity': ident})
            rc = child.wait()
        atomic(root / 'terminal.json', {'generation': root.name, 'outcome': 'confirmed', 'exit_code': rc, 'time': time.time()})
    except BaseException as exc:
        # An exception after an attempted spawn cannot prove the child is absent.
        atomic(root / 'uncertain.json', {'generation': root.name, 'error': type(exc).__name__ + ': ' + str(exc)})
    finally: lock.close()


def terminal_record(a):
    t = read(a / 'terminal.json')
    require(type(t) is dict and set(t) == {'generation', 'outcome', 'exit_code', 'time'} and t['generation'] == a.name and t['outcome'] == 'confirmed' and type(t['exit_code']) is int and type(t['time']) in (int, float) and math.isfinite(t['time']), 'invalid terminal')
    return t


def monitor(path, sha, lock_fd):
    lock = os.fdopen(lock_fd, 'a'); c = load(path, sha); root = Path(c['state_dir']); attempts = root / 'attempts'; attempts.mkdir(exist_ok=True)
    runners = []
    wake_read, wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    old_handler = signal.signal(signal.SIGCHLD, lambda *_: None)
    old_wakeup = signal.set_wakeup_fd(wake_write)
    libc = ctypes.CDLL(None, use_errno=True)
    event_fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    require(event_fd >= 0, 'inotify unavailable')
    watched = None
    next_heartbeat = 0.0
    try:
        while True:
            runners = [p for p in runners if p.poll() is None]
            names = sorted((p for p in attempts.iterdir() if p.is_dir() and p.name.isdecimal()), key=lambda p: int(p.name))
            require([p.name for p in names] == [str(i) for i in range(1, len(names) + 1)], 'invalid attempt sequence')
            retry_at = None
            if names:
                # Durable attempts are the retry counter, including after monitor restart.
                for previous in names[:-1]:
                    require(terminal_record(previous)['exit_code'] != 0, 'invalid previous attempt')
                a = names[-1]; gen = a.name; terminal = a / 'terminal.json'
                if watched != a:
                    require(libc.inotify_add_watch(event_fd, os.fsencode(a), 0x00000080) >= 0, 'inotify watch failed')
                    watched = a
                if terminal.exists():
                    t = terminal_record(a)
                    # A runner can publish its terminal before it exits. Keep ownership
                    # until every runner we spawned has been explicitly reaped.
                    if not runners:
                        if t['exit_code'] == 0:
                            atomic(root / 'status.json', {'state': 'completed', 'generation': gen, 'exit_code': 0}); return
                        if len(names) > c['max_retries']:
                            atomic(root / 'status.json', {'state': 'exhausted', 'generation': gen, 'exit_code': t['exit_code'], 'retries_used': len(names) - 1}); return
                        retry_at = t['time'] + c['retry_backoff_seconds']
                else:
                    with (a / 'runner.lock').open('a') as probe:
                        try: fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError: pass
                        else:
                            if terminal.exists(): continue
                            atomic(root / 'status.json', {'state': 'unconfirmed', 'generation': gen}); return
            if not names or (retry_at is not None and time.time() >= retry_at):
                # Full closure is checked again immediately before every admission.
                c = load(path, sha)
                gen = str(len(names) + 1); a = attempts / gen; a.mkdir()
                runlock = (a / 'runner.lock').open('a'); fcntl.flock(runlock, fcntl.LOCK_EX)
                try:
                    runners.append(subprocess.Popen([c['python']['path'], '-B', '-P', str(Path(__file__).resolve()), 'runner', '--config', path, '--sha256', sha, '--attempt', str(a), '--lock-fd', str(runlock.fileno())], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, pass_fds=(runlock.fileno(),)))
                finally: runlock.close()
                next_heartbeat = 0.0
                continue
            now = time.monotonic()
            if now >= next_heartbeat:
                atomic(root / 'heartbeat.json', {'utc_seconds': time.time(), 'completed': int(gen) - 1, 'generation': gen, 'state': 'running'})
                next_heartbeat = now + c['heartbeat_seconds']
            timeout = min(600.0, max(0.0, next_heartbeat - time.monotonic()))
            if retry_at is not None: timeout = min(timeout, max(0.0, retry_at - time.time()))
            ready, _, _ = select.select([wake_read, event_fd], [], [], timeout)
            for fd in ready:
                try:
                    while os.read(fd, 4096): pass
                except BlockingIOError: pass
    except Exception as exc:
        atomic(root / 'status.json', {'state': 'blocked', 'error': type(exc).__name__ + ': ' + str(exc)})
    finally:
        # Terminal paths wait for owned runners above; abnormal exits must not
        # block forever on a still-running service.
        for process in runners: process.poll()
        signal.set_wakeup_fd(old_wakeup); signal.signal(signal.SIGCHLD, old_handler)
        os.close(event_fd); os.close(wake_read); os.close(wake_write); lock.close()


def main():
    p = argparse.ArgumentParser(); p.add_argument('op', choices=['start', 'monitor', 'runner']); p.add_argument('--config', required=True); p.add_argument('--sha256', required=True); p.add_argument('--lock-fd', type=int); p.add_argument('--attempt'); a = p.parse_args()
    if a.op == 'start': return start(a.config, a.sha256)
    if a.op == 'monitor': monitor(a.config, a.sha256, a.lock_fd)
    else: runner(a.config, a.sha256, a.attempt, a.lock_fd)
    return 0


if __name__ == '__main__': sys.exit(main())
