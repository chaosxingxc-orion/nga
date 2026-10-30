#!/usr/bin/env python3
"""Read-only E33 completion waiter; invokes a separately frozen hardened audit."""
import argparse
import fcntl
import hashlib
import http.client
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


def run(path):
    plan = load(path)
    ph = sha(path)
    out = Path(plan['out'])
    with (out / 'waiter.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not any((out / n).exists() for n in ['COMPLETE.json', 'HARDENED_AUDIT.json', 'EXIT']), 'Existing waiter evidence preserved')
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
            with (out / 'audit.log').open('ab') as f:
                subprocess.run([sys.executable, '-P', plan['auditor'], '--config', plan['config'], '--out', str(out / 'HARDENED_AUDIT.json')], stdout=f, stderr=f, check=True)
            require(source_state(plan), 'Sources changed after audit')
            for p, h in plan['files'].items():
                require(sha(p) == h, 'Waiter dependency changed during audit')
            a = load(out / 'HARDENED_AUDIT.json')
            require(a['config_sha256'] == plan['config_sha256'] and a['report_sha256'] == sha(Path(c['out']) / 'report.json')
                    and a['status'] in ['VERIFIED_HARDENED_SCOPED', 'VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED'], 'Hardened audit differs')
            rc = 0
        except Exception as exc:
            atomic(out / 'FAILURE.json', {'utc': utc(), 'error_type': type(exc).__name__, 'message': str(exc)})
            (out / 'digest.md').write_text(utc() + ' failed; see ' + str(out / 'FAILURE.json') + '\n')
            raise
        finally:
            t = {'utc': utc(), 'rc': rc, 'plan_sha256': ph, 'config_sha256': plan['config_sha256']}
            if rc == 0:
                t.update(audit_sha256=sha(out / 'HARDENED_AUDIT.json'), review_flags=a['review_flags'], inherited_review_flags=a['inherited_review_flags'], status=a['status'])
            atomic(out / 'COMPLETE.json', t)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    run(p.parse_args().plan)
