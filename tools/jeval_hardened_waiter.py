#!/usr/bin/env python3
"""Read-only E33 completion waiter; invokes a separately frozen hardened audit."""
import argparse
import fcntl
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'


def require(value, message):
    if not value:
        raise ValueError(message)


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def atomic(p, x):
    p = Path(p)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name + '.')
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), 0o644)
            json.dump(x, f, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect(name):
    require(re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'Invalid container name')
    c = http.client.HTTPConnection('localhost', timeout=30)
    c.sock = socket.socket(socket.AF_UNIX)
    c.sock.settimeout(30)
    c.sock.connect('/var/run/docker.sock')
    try:
        c.request('GET', '/containers/' + name + '/json')
        r = c.getresponse()
        require(r.status == 200, 'Docker inspection failed')
        return json.loads(r.read())
    finally:
        c.close()


def mapping(host):
    return (sorted(host.get('Binds') or []), sorted((d['PathOnHost'], d['PathInContainer'], d['CgroupPermissions']) for d in host.get('Devices') or []))


def binding(d, expected):
    require(d['Id'] == expected['container_id'] and d['Image'] == IMAGE, 'Container identity differs')
    for k in ['Cmd', 'Entrypoint', 'Env']:
        a, b = d['Config'].get(k), expected['Config'].get(k)
        require(sorted(a or []) == sorted(b or []) if k == 'Env' else a == b, 'Container configuration differs: ' + k)
    require(mapping(d['HostConfig']) == mapping(expected['HostConfig']), 'Container resources differ')
    for k in ['NetworkMode', 'ShmSize']:
        require(d['HostConfig'].get(k) == expected['HostConfig'].get(k), 'Container host configuration differs')


def cpu_mount_binding(d, out, source_root=Path('/mnt/cephfs')):
    """Operational source protection; Docker socket is not capability isolation."""
    out = Path(out)
    require(out.is_absolute() and out.resolve() == out and out != source_root
            and source_root in out.parents, 'Waiter output mount scope')
    wanted = {(str(source_root), str(source_root), False),
              (str(out), str(out), True),
              ('/var/run/docker.sock', '/var/run/docker.sock', False)}
    binds = [str(source_root) + ':' + str(source_root) + ':ro', str(out) + ':' + str(out) + ':rw',
             '/var/run/docker.sock:/var/run/docker.sock:ro']
    host = d['HostConfig']
    require(sorted(host.get('Binds') or []) == sorted(binds), 'Waiter bind allowlist differs')
    mounts = d.get('Mounts') or []
    require(len(mounts) == 3 and all(m.get('Type') == 'bind' for m in mounts)
            and {(m['Source'], m['Destination'], m['RW']) for m in mounts} == wanted,
            'Waiter effective mounts differ')
    require(not any(host.get(k) for k in ['Devices', 'Privileged', 'DeviceRequests',
            'DeviceCgroupRules', 'CapAdd', 'Mounts', 'VolumesFrom', 'SecurityOpt']),
            'Waiter privileged/device/mount exposure')
    require(host.get('PidMode', '') == '' and host.get('IpcMode', 'private') == 'private'
            and host.get('UsernsMode', '') == '' and host.get('CgroupnsMode', 'private') == 'private',
            'Waiter namespace exposure')


def source_state(plan):
    require(sha(plan['config']) == plan['config_sha256'], 'Source config changed')
    c = load(plan['config'])
    run = Path(c['out'])
    finish = Path(str(run) + '_finish')
    states = []
    for role, out in [('inference', run), ('finish', finish)]:
        expected = plan['sources'][role]
        d = inspect(expected['container_id'])
        binding(d, expected)
        receipt = load(out / 'LAUNCH_RECEIPT.json')
        require(sha(out / 'LAUNCH_RECEIPT.json') == expected['receipt_sha256'] and receipt['container_id'] == d['Id']
                and receipt['config_sha256'] == plan['config_sha256'] and receipt['wrapper_sha256'] == sha(out / 'run.sh'), 'Source receipt differs')
        status = d['State']['Status']
        require(status in ['running', 'restarting', 'exited'], 'Unexpected source state')
        if status == 'exited':
            require(d['State']['ExitCode'] == 0, 'Source failed: ' + role)
            t = load(out / 'COMPLETE.json')
            require(t['rc'] == 0 and t['config_sha256'] == plan['config_sha256'], 'Source terminal failed/differs')
            require(re.fullmatch(r'rc=0 utc=\S+\n?', (out / 'EXIT').read_text()), 'Source wrapper failed')
            require((out / 'EXIT').stat().st_mtime_ns >= (out / 'COMPLETE.json').stat().st_mtime_ns, 'Source wrapper stale')
            if role == 'inference':
                require(t['stage'] == 'completed' and t['progress'] == t['total'] == 11257, 'Source population incomplete')
                require(set(t['outputs']) == {'report.json', 'PROBE.json'}, 'Source outputs incomplete')
                for n, h in t['outputs'].items():
                    require(sha(out / n) == h, 'Source output changed')
            else:
                audit = load(out / 'INDEPENDENT_AUDIT.json')
                require(t['audit_sha256'] == sha(out / 'INDEPENDENT_AUDIT.json') and audit['config_sha256'] == plan['config_sha256']
                        and audit['report_sha256'] == sha(run / 'report.json') and audit['rows'] == 11257
                        and audit['status'] == 'VERIFIED_SCOPED' and audit['review_flags'] == t['review_flags'], 'Source audit differs')
        states.append(status)
    return states == ['exited', 'exited']



def process_identity(pid):
    """PID reuse is not identity: include boot, start ticks and actual argv."""
    root = Path('/proc') / str(pid)
    try:
        stat = (root / 'stat').read_text()
        fields = stat[stat.rfind(')') + 2:].split()
        if fields[0] == 'Z':
            return None
        return dict(pid=pid, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    start_ticks=fields[19], argv=(root / 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0'))
    except (FileNotFoundError, ProcessLookupError):
        return None


def no_clobber_json(path, value):
    """A complete JSON publication never replaces prior evidence."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.pending-')
    with os.fdopen(fd, 'w') as f:
        os.fchmod(f.fileno(), 0o644)
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.link(tmp, path)
    os.unlink(tmp)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def attempt_worker(path, lock_fd):
    """The inherited flock owns the entire create/execute/commit attempt."""
    p = Path(path); a = load(p); out = p.parent; ah = sha(p)
    require(os.fstat(lock_fd).st_ino == (out / 'attempt.lock').stat().st_ino, 'Attempt lock differs')
    require(process_identity(os.getpid())['argv'] == a['command'], 'Attempt command differs')
    no_clobber_json(out / 'PROCESS.json', dict(attempt_sha256=ah, process=process_identity(os.getpid())))
    rc = 1
    auditor_returncode = None
    try:
        require(sha(a['auditor']) == a['auditor_sha256'] and sha(a['config']) == a['config_sha256'], 'Attempt frozen source changed')
        with (out / 'audit.log').open('ab') as log:
            result = subprocess.run([sys.executable, '-P', a['auditor'], '--config', a['config'],
                                     '--out', str(out / 'HARDENED_AUDIT.json')], stdout=log, stderr=log,
                                    pass_fds=(lock_fd,))
        auditor_returncode = result.returncode
        require(result.returncode == 0 and (out / 'HARDENED_AUDIT.json').is_file(), 'Auditor failed')
        report = load(out / 'HARDENED_AUDIT.json')
        require(report['config_sha256'] == a['config_sha256'], 'Attempt report config differs')
        require(sha(a['auditor']) == a['auditor_sha256'] and sha(a['config']) == a['config_sha256'], 'Attempt source changed after audit')
        rc = 0
    finally:
        value = dict(rc=rc, attempt_sha256=ah, utc=utc(), process=process_identity(os.getpid()),
                     auditor_returncode=auditor_returncode,
                     interrupted=auditor_returncode is not None and auditor_returncode < 0)
        if rc == 0:
            value['report_sha256'] = sha(out / 'HARDENED_AUDIT.json')
        no_clobber_json(out / 'ATTEMPT_COMPLETE.json', value)
        os.close(lock_fd)


def audit_report(plan, report):
    c = load(plan['config'])
    require(report['config_sha256'] == plan['config_sha256'] and report['report_sha256'] == sha(Path(c['out']) / 'report.json')
            and report['status'] in ['VERIFIED_HARDENED_SCOPED', 'VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED'], 'Hardened audit differs')
    require(sha(plan['auditor']) == plan['files'][plan['auditor']], 'Audit verifier changed')
    spec = importlib.util.spec_from_file_location('waiter_receipt_verifier', plan['auditor'])
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    verifier.verify_receipt_manifest(Path(c['out']), report['receipt_manifest'])


def recover_wrapper_exit(plan, ph, out, container_id):
    marker = out / 'EXIT'
    if not marker.exists():
        return
    review = load(out / 'RESUME_REVIEW.json')
    require(review['approved_plan_sha256'] == ph and review['container_id'] == container_id
            and review['exit_sha256'] == sha(marker), 'Interrupted wrapper resume not approved')
    require(re.fullmatch(r'rc=(?:[1-9][0-9]*|-[1-9][0-9]*) utc=\S+\n?', marker.read_text()), 'Successful/invalid wrapper cannot resume')
    archive = out / ('interruption-' + str(time.time_ns()))
    archive.mkdir()
    no_clobber_json(archive / 'RESUME_REVIEW.json', review)
    os.replace(marker, archive / 'EXIT')


def reconcile_audit(plan, ph, out, source_validator=source_state, report_validator=audit_report):
    """Resume a successful attempt, or preserve an interrupted attempt and retry.

    An auditor that is still running holds the inherited lock even if its
    supervisor/controller died. No process is inferred dead from a missing file.
    """
    state_path = out / 'AUDIT_STATE.json'
    state = load(state_path) if state_path.exists() else dict(plan_sha256=ph, attempts=[])
    require(state['plan_sha256'] == ph, 'Audit state plan differs')
    attempts = out / 'attempts'; attempts.mkdir(exist_ok=True)
    children = {}
    while True:
        require(source_validator(plan), 'Sources changed before audit attempt')
        if not state['attempts'] or state.get('phase') == 'abandoned':
            require(len(state['attempts']) < plan.get('max_interrupted_audit_attempts', 3), 'Interrupted audit retry limit')
            ad = attempts / ('attempt-' + str(len(state['attempts'])))
            if ad.exists():
                # Creation can precede durable state. Preserve the entire
                # untracked directory, but never move a live attempt.
                with (ad / 'attempt.lock').open('a') as orphan_lock:
                    try:
                        fcntl.flock(orphan_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        atomic(out / 'STATUS.json', dict(utc=utc(), stage='waiting_untracked_audit', attempt=str(ad)))
                        (out / 'digest.md').write_text(utc() + ' waiting_untracked_audit ' + str(ad) + '\n')
                        time.sleep(1)
                        continue
                    orphan = attempts / (ad.name + '.untracked-' + str(time.time_ns()))
                    ad.rename(orphan)
            ad.mkdir()
            lock = (ad / 'attempt.lock').open('w')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ap = ad / 'attempt.json'
            command = [sys.executable, '-P', str(Path(__file__).resolve()), '--audit-attempt', str(ap), '--lock-fd', str(lock.fileno())]
            spec = dict(plan_sha256=ph, config=plan['config'], config_sha256=plan['config_sha256'],
                        auditor=plan['auditor'], auditor_sha256=sha(plan['auditor']), command=command)
            no_clobber_json(ap, spec)
            state['attempts'].append(dict(path=str(ap), sha256=sha(ap)))
            state['phase'] = 'prepared'; atomic(state_path, state)
            # The flock is inherited before the parent closes it, eliminating
            # the spawn-before-PROCESS receipt gap.
            try:
                with (ad / 'supervisor.log').open('ab') as log:
                    children[str(ap)] = subprocess.Popen(command, stdout=log, stderr=log, pass_fds=(lock.fileno(),))
            finally:
                lock.close()
        entry = state['attempts'][-1]; ap = Path(entry['path']); ad = ap.parent
        require(sha(ap) == entry['sha256'], 'Audit attempt changed')
        a = load(ap)
        require(a['plan_sha256'] == ph and a['config_sha256'] == plan['config_sha256']
                and a['auditor'] == plan['auditor'] and sha(a['auditor']) == a['auditor_sha256'], 'Attempt identity differs')
        with (ad / 'attempt.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if (ad / 'PROCESS.json').exists():
                    receipt = load(ad / 'PROCESS.json')
                    require(receipt['attempt_sha256'] == entry['sha256'] and receipt['process']['argv'] == a['command'], 'Attempt process receipt differs')
                    actual = process_identity(receipt['process']['pid'])
                    # A dead supervisor may leave the auditor alive holding
                    # the inherited lock. Wait; never run a duplicate audit.
                    # PID reuse only means the supervisor is no longer there.
                    # The inherited lock still proves an attempt is active.
                    if actual is not None and actual != receipt['process']:
                        atomic(out / 'SUPERVISOR_IDENTITY_NOTICE.json', dict(utc=utc(), attempt=str(ad),
                               reason='Supervisor PID reused while inherited attempt lock remains held'))
                atomic(out / 'STATUS.json', dict(utc=utc(), stage='hardened_audit', attempt=str(ad)))
                (out / 'digest.md').write_text(utc() + ' hardened_audit ' + str(ad) + '\n')
                time.sleep(1)
                continue
            if str(ap) in children:
                children[str(ap)].wait(timeout=10)
            receipt_path = ad / 'PROCESS.json'; terminal = ad / 'ATTEMPT_COMPLETE.json'
            if not terminal.exists():
                abandoned = ad / 'ABANDONED.json'
                reason = 'No completion and no process holds the inherited attempt lock; artifacts preserved'
                if abandoned.exists():
                    old = load(abandoned)
                    require(old['attempt_sha256'] == entry['sha256'] and old['reason'] == reason, 'Abandoned attempt marker differs')
                else:
                    no_clobber_json(abandoned, dict(utc=utc(), attempt_sha256=entry['sha256'], reason=reason))
                state['phase'] = 'abandoned'; atomic(state_path, state)
                continue
            t = load(terminal); process = load(receipt_path)
            require(t['attempt_sha256'] == process['attempt_sha256'] == entry['sha256']
                    and t['process'] == process['process'] and t['process']['argv'] == a['command'], 'Completed audit process identity differs')
            if t.get('interrupted') is True:
                require(t['rc'] != 0 and isinstance(t.get('auditor_returncode'), int)
                        and t['auditor_returncode'] < 0, 'Invalid auditor interruption receipt')
                abandoned = ad / 'ABANDONED.json'
                marker = dict(attempt_sha256=entry['sha256'],
                              reason='Auditor terminated by signal; artifacts preserved',
                              auditor_returncode=t['auditor_returncode'])
                if abandoned.exists():
                    require(load(abandoned) == marker, 'Interrupted attempt marker differs')
                else:
                    no_clobber_json(abandoned, marker)
                state['phase'] = 'abandoned'; atomic(state_path, state)
                continue
            require(t['rc'] == 0, 'Audit attempt failed; reviewed new generation required')
            candidate = ad / 'HARDENED_AUDIT.json'
            require(sha(candidate) == t['report_sha256'], 'Attempt output changed')
            report = load(candidate)
            require(source_validator(plan), 'Sources changed after audit')
            report_validator(plan, report)
            intent = dict(plan_sha256=ph, attempt_sha256=entry['sha256'], attempt_report_sha256=t['report_sha256'])
            ip = out / 'AUDIT_COMMIT_INTENT.json'
            if ip.exists():
                require(load(ip) == intent, 'Audit commit intent differs')
            else:
                no_clobber_json(ip, intent)
            public = out / 'HARDENED_AUDIT.json'
            if not public.exists():
                no_clobber_json(public, report)
            require(load(public) == report, 'Published audit differs')
            # Recheck at the commit boundary, including every receipt hash.
            require(source_validator(plan), 'Sources changed during audit publication')
            report_validator(plan, load(public))
            state['phase'] = 'committed'; state['published_sha256'] = sha(public)
            atomic(state_path, state)
            return report


def final_report(plan, ph, out, source_validator=None, report_validator=None):
    """Validate public bytes against the committed attempt, returning their hash.

    A terminal must carry this authenticated hash, never a later unvalidated
    read of whichever bytes happen to occupy the public report path.
    """
    source_validator = source_validator or source_state
    report_validator = report_validator or audit_report
    state = load(out / 'AUDIT_STATE.json')
    require(state['plan_sha256'] == ph and state['phase'] == 'committed', 'Audit commit state differs')
    entry = state['attempts'][-1]
    attempt = Path(entry['path'])
    require(sha(attempt) == entry['sha256'], 'Final audit attempt changed')
    terminal = load(attempt.parent / 'ATTEMPT_COMPLETE.json')
    require(terminal['rc'] == 0 and terminal['attempt_sha256'] == entry['sha256'], 'Final audit attempt failed/differs')
    intent = dict(plan_sha256=ph, attempt_sha256=entry['sha256'],
                  attempt_report_sha256=terminal['report_sha256'])
    require(load(out / 'AUDIT_COMMIT_INTENT.json') == intent, 'Final audit intent differs')
    candidate = attempt.parent / 'HARDENED_AUDIT.json'
    require(sha(candidate) == terminal['report_sha256'], 'Final attempt output changed')
    raw = (out / 'HARDENED_AUDIT.json').read_bytes()
    public_hash = hashlib.sha256(raw).hexdigest()
    require(public_hash == state['published_sha256'], 'Final published audit changed')
    report = json.loads(raw)
    require(report == load(candidate), 'Final published audit differs from attempt')
    require(source_validator(plan), 'Sources changed before final commit')
    report_validator(plan, report)
    require(sha(out / 'HARDENED_AUDIT.json') == public_hash, 'Published audit changed during final validation')
    return report, public_hash


def success_terminal(plan, ph, out):
    report, public_hash = final_report(plan, ph, out)
    return dict(utc=utc(), rc=0, plan_sha256=ph, config_sha256=plan['config_sha256'],
                audit_sha256=public_hash, review_flags=report['review_flags'],
                inherited_review_flags=report['inherited_review_flags'], status=report['status'])


def run(path):
    plan = load(path)
    ph = sha(path)
    out = Path(plan['out'])
    with (out / 'waiter.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existing_terminal = load(out / 'COMPLETE.json') if (out / 'COMPLETE.json').exists() else None
        require(Path(plan['wrapper']).parent == out and Path(plan['config']).is_absolute(), 'Waiter path scope')
        rc = 1
        try:
            require(plan['schema'] == 1 and plan['image'] == IMAGE and plan['readonly_sources'] is True, 'Waiter protocol')
            require(load(out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Waiter not approved')
            frozen = plan['files']
            for fp, expected_hash in frozen.items():
                require(sha(fp) == expected_hash, 'Waiter frozen source changed: ' + fp)
            require({str(Path(__file__).resolve()), plan['auditor'], plan['config'], plan['wrapper'], plan['container_spec'], plan['preregistration']} <= plan['files'].keys(), 'Waiter dependency closure')
            me = inspect(plan['container'])
            expected = load(plan['container_spec'])
            own_receipt = load(out / 'LAUNCH_RECEIPT.json')
            expected['container_id'] = own_receipt['container_id']
            binding(me, expected)
            require(not (me['HostConfig'].get('Devices') or []) and own_receipt['plan_sha256'] == ph
                    and own_receipt['wrapper_sha256'] == sha(plan['wrapper']), 'Waiter identity/CPU binding')
            cpu_mount_binding(me, out)
            if existing_terminal is not None:
                require(existing_terminal['rc'] == 0, 'Existing failed terminal preserved; new generation required')
                verified = success_terminal(plan, ph, out)
                require({k: v for k, v in existing_terminal.items() if k != 'utc'}
                        == {k: v for k, v in verified.items() if k != 'utc'}, 'Existing successful terminal differs')
                recover_wrapper_exit(plan, ph, out, own_receipt['container_id'])
                (out / 'digest.md').write_text(utc() + ' recovered_successful_terminal; original evidence preserved\n')
                rc = 0
                return
            recover_wrapper_exit(plan, ph, out, own_receipt['container_id'])
            while True:
                require(sha(path) == ph, 'Waiter plan changed')
                for p, h in plan['files'].items():
                    require(sha(p) == h, 'Waiter frozen source changed: ' + p)
                done = source_state(plan)
                c = load(plan['config'])
                sp = Path(c['out']) / 'STATUS.json'
                s = load(sp) if sp.exists() else {}
                snap = {'utc': utc(), 'stage': 'audit' if done else 'waiting_native_finish', 'progress': s.get('progress'),
                        'total': s.get('total'), 'questions_per_second_per_chip': s.get('questions_per_second_per_chip'),
                        'chips': 1, 'reserved_gib': s.get('reserved_gib')}
                atomic(out / 'STATUS.json', snap)
                (out / 'digest.md').write_text(json.dumps(snap) + '\n')
                with (out / 'heartbeat.log').open('a') as f:
                    f.write(json.dumps(snap) + '\n')
                if done:
                    break
                time.sleep(10)
            reconcile_audit(plan, ph, out)
            require(source_state(plan), 'Sources changed after audit')
            for p, h in plan['files'].items():
                require(sha(p) == h, 'Waiter dependency changed during audit')
            t = success_terminal(plan, ph, out)
            no_clobber_json(out / 'COMPLETE.json', t)
            rc = 0
        except Exception as exc:
            atomic(out / 'FAILURE.json', {'utc': utc(), 'error_type': type(exc).__name__, 'message': str(exc)})
            (out / 'digest.md').write_text(utc() + ' failed; see ' + str(out / 'FAILURE.json') + '\n')
            raise
        finally:
            if rc != 0 and existing_terminal is None and not (out / 'COMPLETE.json').exists():
                no_clobber_json(out / 'COMPLETE.json', dict(utc=utc(), rc=rc,
                                plan_sha256=ph, config_sha256=plan['config_sha256']))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path)
    p.add_argument('--audit-attempt', type=Path)
    p.add_argument('--lock-fd', type=int)
    args = p.parse_args()
    if args.audit_attempt:
        attempt_worker(args.audit_attempt, args.lock_fd)
    else:
        run(args.plan)
