#!/usr/bin/env python3
"""E34: reconcile only an approved, immutable explicit JEVal queue."""
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
ALLOCATION = '/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json'
KEYS = ['openjev2', 'openjev9', 'nimble']


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def atomic(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def docker(method, path, value=None):
    c = http.client.HTTPConnection('localhost', timeout=30)
    c.sock = socket.socket(socket.AF_UNIX)
    c.sock.settimeout(30)
    c.sock.connect('/var/run/docker.sock')
    try:
        c.request(method, path, body=None if value is None else json.dumps(value),
                  headers={'Content-Type': 'application/json'})
        r = c.getresponse()
        data = r.read()
        if r.status == 404 and method == 'GET':
            return None
        require(r.status < 300, 'Docker HTTP ' + str(r.status) + ' ' + path)
        return json.loads(data) if data else None
    finally:
        c.close()


def inspect(name):
    require(re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'Invalid container name')
    return docker('GET', '/containers/' + name + '/json')


def devices(info):
    return sorted((d['PathOnHost'], d['PathInContainer'], d['CgroupPermissions'])
                  for d in info['HostConfig'].get('Devices') or [])


def image_environment():
    env = dict(x.split('=', 1) for x in docker('GET', '/images/' + IMAGE + '/json')['Config'].get('Env') or [])
    env['TORCH_DEVICE_BACKEND_AUTOLOAD'] = '0'
    return [k + '=' + v for k, v in env.items()]


def binding(info, spec, receipt=None):
    require(info is not None and info['Image'] == spec['Image'], 'Container/image differs')
    for k in ['Cmd', 'Entrypoint']:
        require(info['Config'].get(k) == spec[k], 'Container ' + k + ' differs')
    require(sorted(info['Config'].get('Env') or []) == sorted(spec.get('Env') or []), 'Container environment differs')
    a, b = info['HostConfig'], spec['HostConfig']
    require(sorted(a.get('Binds') or []) == sorted(b.get('Binds') or []), 'Container mounts differ')
    require(devices(info) == devices(spec), 'Container devices differ')
    for k in ['NetworkMode', 'ShmSize']:
        require(a.get(k) == b.get(k), 'Container ' + k + ' differs')
    for k, v in spec['Labels'].items():
        require((info['Config'].get('Labels') or {}).get(k) == v, 'Queue intent label differs')
    if receipt is not None:
        require(info['Id'] == receipt['container_id'], 'Receipt container differs')
        require(receipt['image'] == spec['Image'] and receipt['command'] == spec['Cmd']
                and receipt['entrypoint'] == spec['Entrypoint'], 'Receipt specification differs')


def frozen(files):
    for p, h in files.items():
        require(sha(p) == h, 'Frozen file changed: ' + p)


def wrapper(path, terminal):
    require(re.fullmatch(r'rc=0 utc=\S+\n?', path.read_text()), 'Wrapper not successful: ' + str(path))
    require(path.stat().st_mtime_ns >= terminal.stat().st_mtime_ns, 'Stale wrapper: ' + str(path))


class Queue:
    def __init__(self, path):
        self.path = Path(path)
        self.hash = sha(path)
        self.plan = load(path)
        self.out = Path(self.plan['out'])
        require(self.plan['schema'] == 1 and self.plan['image'] == IMAGE, 'Queue protocol/image')
        require(self.plan['allocation'] == ALLOCATION, 'Allocation path differs')
        keys = [e['key'] for e in self.plan['entries']]
        require(keys and len(keys) == len(set(keys)) and set(keys) <= set(KEYS), 'Queue keys invalid')
        self.keys = keys
        require(load(self.out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == self.hash, 'Queue not approved')
        needed = [str(Path(__file__).resolve())] + list(self.plan['preparation_files'].values())
        require(set(self.plan['preparation_files']) == {'wrapper', 'launch', 'resume', 'preregistration', 'container_spec'}, 'Queue preparation closure')
        require(set(needed) <= self.plan['files'].keys(), 'Queue source not frozen')
        frozen(self.plan['files'])
        self.state_path = self.out / 'STATE.json'
        self.state = load(self.state_path) if self.state_path.exists() else {'plan_sha256': self.hash, 'intents': {}}
        require(self.state['plan_sha256'] == self.hash, 'Queue state differs')
        self.configs = []
        for entry in self.plan['entries']:
            cp = Path(entry['config'])
            require(sha(cp) == entry['config_sha256'], 'Entry config hash differs')
            c = load(cp)
            require(c['key'] == entry['key'] and c['mode'] == 'inference'
                    and c['physical_chip'] == 1 and c['image'] == IMAGE, 'Entry protocol differs')
            require(str(cp) in self.plan['files'] and self.plan['files'][str(cp)] == entry['config_sha256'], 'Entry not frozen')
            if c['key'].startswith('openjev'):
                gate = entry['batch_admission']
                require(gate in self.plan['files'] and sha(gate) == entry['batch_admission_sha256'], 'Batch admission not frozen')
                g = load(gate)
                require(g['approved_config_sha256'] == entry['config_sha256'] and g['candidate_batch_admission'] is True, 'Candidate batch admission missing')
            require(Path(c['out']) == cp.parent, 'Config/output mismatch')
            require(str(cp.parent / 'PARENT_REVIEW.json') in self.plan['files'], 'Entry approval not frozen')
            require(str(cp.parent / 'NPU_SPEC.json') in self.plan['files'], 'Native spec not frozen')
            require(str(cp.parent / 'run.sh') in self.plan['files'], 'Native wrapper not frozen')
            ha = entry['hardened']
            require(all(ha[k] in self.plan['files'] for k in ['auditor', 'wrapper']), 'Hardened audit not frozen')
            require(Path(ha['wrapper']) == Path(ha['out']) / 'run.sh', 'Hardened wrapper path')
            self.configs.append(c)

    def save(self):
        self.state['utc'] = utc()
        atomic(self.state_path, self.state)

    def check_plan(self):
        require(sha(self.path) == self.hash, 'Plan changed')
        frozen(self.plan['files'])

    def controller_binding(self):
        d = inspect(self.plan['container'])
        require(d is not None and d['State']['Status'] == 'running', 'Controller not actually running')
        receipt = load(self.out / 'LAUNCH_RECEIPT.json')
        spec = load(self.plan['preparation_files']['container_spec'])
        binding(d, spec, receipt)
        require(not devices(d) and spec['Image'] == IMAGE, 'Controller CPU/image differs')
        require(spec['Cmd'] == [self.plan['preparation_files']['wrapper']]
                and spec['Entrypoint'] == ['bash'], 'Controller command differs')
        require(receipt['plan_sha256'] == self.hash
                and receipt['wrapper_sha256'] == sha(self.plan['preparation_files']['wrapper']), 'Controller receipt differs')

    def spec(self, c, role):
        run = Path(c['out'])
        if role == 'inference':
            spec = load(run / 'NPU_SPEC.json')
            require(spec['Image'] == IMAGE and spec['Cmd'] == ['bash', str(run / 'run.sh')], 'Native specification differs')
            require([d for d in devices(spec) if re.fullmatch(r'/dev/davinci\d+', d[0])] == [('/dev/davinci1', '/dev/davinci1', 'rwm')], 'Native chip differs')
        else:
            out, _ = self.context(c, role)
            spec = {'Image': IMAGE, 'Cmd': [str(out / 'run.sh')],
                    'Entrypoint': ['bash'], 'Env': image_environment(),
                    'HostConfig': {'Binds': ['/mnt/cephfs:/mnt/cephfs', '/var/run/docker.sock:/var/run/docker.sock'],
                                   'Devices': [], 'NetworkMode': 'none', 'ShmSize': 67108864}}
        spec['Labels'] = {'nga.jeval.queue': self.hash, 'nga.jeval.key': c['key'], 'nga.jeval.role': role}
        return spec

    def context(self, c, role):
        run = Path(c['out'])
        if role == 'hardened':
            entry = next(e for e in self.plan['entries'] if e['key'] == c['key'])
            return Path(entry['hardened']['out']), entry['hardened']['container']
        return (run if role == 'inference' else Path(str(run) + '_finish'),
                c['container'] + ('' if role == 'inference' else '-finish'))

    def check_entry(self, c, entry):
        self.check_plan()
        require(sha(entry['config']) == entry['config_sha256'], 'Config changed')
        require(load(Path(c['out']) / 'PARENT_REVIEW.json')['approved_config_sha256'] == entry['config_sha256'], 'Entry parent approval')
        frozen(c['files'])
        pc = load(c['probe_config'])
        pt = load(Path(pc['out']) / 'COMPLETE.json')
        pr = load(c['probe_review'])
        require(pc['key'] == c['key'] and pc['mode'] == 'probe', 'Probe identity differs')
        require(pt['rc'] == 0 and pt['stage'] == 'probe_completed' and pt['progress'] == pt['total'] == 4, 'Probe incomplete')
        require(sha(c['probe_config']) == pt['config_sha256'] == pr['approved_probe_config_sha256'], 'Probe config differs')
        require(sha(c['probe_report']) == pt['outputs']['PROBE.json'] == pr['approved_probe_sha256'], 'Probe output differs')
        pd = inspect(pc['container'])
        pl = load(Path(pc['out']) / 'LAUNCH_RECEIPT.json')
        require(pd is not None and pd['Id'] == pl['container_id'] and pd['Image'] == IMAGE
                and pd['State']['Status'] == 'exited' and pd['State']['ExitCode'] == 0, 'Probe actual exit differs')
        wrapper(Path(pc['out']) / 'EXIT', Path(pc['out']) / 'COMPLETE.json')

    def resource(self, c, own_id=None, claim=False):
        a = load(self.plan['allocation'])
        owners = [x for x in a['allocation'] if x['chip'] == 1]
        free = [x for x in a['free'] if x['chip'] == 1]
        owner = 'reference_inference/' + Path(c['out']).name
        for obj in docker('GET', '/containers/json'):
            if obj['Id'] != own_id:
                require(not any(d[0] == '/dev/davinci1' for d in devices(inspect(obj['Id']))), 'Live chip conflict')
        if not owners and len(free) == 1 and claim:
            a['free'] = [x for x in a['free'] if x['chip'] != 1]
            a['allocation'].append({'chip': 1, 'owner': 'E34 JEVal serial queue', 'run': owner,
                                    'claimed_utc': utc(), 'release_when': 'complete independent audit and actual exits'})
            atomic(self.plan['allocation'], a)
        else:
            require(len(owners) == 1 and owners[0]['run'] == owner and not free, 'Allocation owner differs')

    def reconcile(self, c, entry, role):
        out, name = self.context(c, role)
        spec = self.spec(c, role)
        receipt_path = out / 'LAUNCH_RECEIPT.json'
        token = c['key'] + ':' + role
        with Path(self.plan['allocation'] + '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            info = inspect(name)
            receipt = load(receipt_path) if receipt_path.exists() else None
            if info is None:
                require(receipt is None and self.state['intents'].get(token, {}).get('phase') in (None, 'creating'), 'Missing established container')
                require(not any((out / n).exists() for n in ['COMPLETE.json', 'EXIT', 'INDEPENDENT_AUDIT.json', 'HARDENED_AUDIT.json']), 'Unreceipted terminal evidence')
                if role == 'inference':
                    # Claim occurs after the native receipt; under the same lock, so no competitor can enter.
                    a = load(self.plan['allocation'])
                    require(not any(x['chip'] == 1 for x in a['allocation'])
                            and sum(x['chip'] == 1 for x in a['free']) == 1, 'Chip not explicitly free')
                    for live in docker('GET', '/containers/json'):
                        require(not any(d[0] == '/dev/davinci1' for d in devices(inspect(live['Id']))), 'Live chip before create')
                self.state['intents'][token] = {'phase': 'creating', 'spec_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()}
                self.save()
                docker('POST', '/containers/create?name=' + name, spec)
                info = inspect(name)
            binding(info, spec, receipt)
            if receipt is None:
                intent = self.state['intents'].get(token, {})
                require(info['State']['Status'] == 'created' and intent.get('phase') == 'creating'
                        and intent.get('spec_sha256') == hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(), 'Unknown unreceipted container')
                receipt = dict(container_id=info['Id'], image=IMAGE, command=spec['Cmd'], entrypoint=spec['Entrypoint'],
                               config_sha256=entry['config_sha256'], wrapper_sha256=sha(out / 'run.sh'))
                atomic(receipt_path, receipt)
            require(receipt['config_sha256'] == entry['config_sha256'] and receipt['wrapper_sha256'] == sha(out / 'run.sh'), 'Receipt config/wrapper differs')
            status = info['State']['Status']
            if role == 'inference':
                self.resource(c, info['Id'], claim=status == 'created')
            if status == 'created':
                require(not (out / 'EXIT').exists() and not (out / 'COMPLETE.json').exists(), 'Created container has terminal evidence')
                self.state['intents'][token] = dict(self.state['intents'].get(token, {}), phase='starting')
                self.save()
                docker('POST', '/containers/' + info['Id'] + '/start')
                return 'running'
            require(status in ('running', 'restarting', 'exited'), 'Unsupported container state')
            if status == 'exited':
                require(info['State']['ExitCode'] == 0, role + ' failed; manual reviewed resume required')
            return status

    def completion(self, c, entry, include_hardened=True):
        run = Path(c['out'])
        finish = Path(str(run) + '_finish')
        for role in ['inference', 'finish']:
            out, name = self.context(c, role)
            d = inspect(name)
            receipt = load(out / 'LAUNCH_RECEIPT.json')
            binding(d, self.spec(c, role), receipt)
            require(receipt['config_sha256'] == entry['config_sha256'] and receipt['wrapper_sha256'] == sha(out / 'run.sh'), 'Completed receipt differs')
            require(d['State']['Status'] == 'exited' and d['State']['ExitCode'] == 0, 'Completed container not exited0')
            wrapper(out / 'EXIT', out / 'COMPLETE.json')
        t, ft = load(run / 'COMPLETE.json'), load(finish / 'COMPLETE.json')
        require(t['rc'] == ft['rc'] == 0 and t['config_sha256'] == ft['config_sha256'] == entry['config_sha256'], 'Terminal config/exit differs')
        require(t['stage'] == 'completed' and t['progress'] == t['total'] == 11257, 'Incomplete inference population')
        require(set(t['outputs']) == {'PROBE.json', 'report.json'}, 'Terminal output closure differs')
        for n, h in t['outputs'].items():
            require(sha(run / n) == h and (run / n).stat().st_mtime_ns <= (run / 'COMPLETE.json').stat().st_mtime_ns, 'Inference output changed')
        audit = load(finish / 'INDEPENDENT_AUDIT.json')
        require(ft['audit_sha256'] == sha(finish / 'INDEPENDENT_AUDIT.json')
                and audit['config_sha256'] == entry['config_sha256']
                and audit['report_sha256'] == sha(run / 'report.json')
                and audit['status'] == 'VERIFIED_SCOPED' and audit['rows'] == 11257, 'Audit binding/population differs')
        require((finish / 'INDEPENDENT_AUDIT.json').stat().st_mtime_ns <= (finish / 'COMPLETE.json').stat().st_mtime_ns, 'Stale audit terminal')
        require(ft['review_flags'] == audit['review_flags'], 'Audit flags differ')
        require(ft['status'] == ('COMPLETED_SCOPED_REVIEW_REQUIRED' if audit['review_flags'] else 'COMPLETED_SCOPED'), 'Audit status differs')
        paths = [run / n for n in ['COMPLETE.json', 'EXIT', 'report.json', 'PROBE.json', 'LAUNCH_RECEIPT.json']]
        paths += [finish / n for n in ['COMPLETE.json', 'EXIT', 'INDEPENDENT_AUDIT.json', 'LAUNCH_RECEIPT.json']]
        flags = audit['review_flags']
        if include_hardened:
            ho, hn = self.context(c, 'hardened')
            hd = inspect(hn)
            hreceipt = load(ho / 'LAUNCH_RECEIPT.json')
            binding(hd, self.spec(c, 'hardened'), hreceipt)
            require(hreceipt['config_sha256'] == entry['config_sha256'] and hreceipt['wrapper_sha256'] == sha(ho / 'run.sh'), 'Hardened receipt differs')
            require(hd['State']['Status'] == 'exited' and hd['State']['ExitCode'] == 0, 'Hardened actual exit differs')
            ht = load(ho / 'COMPLETE.json')
            hr = load(ho / 'HARDENED_AUDIT.json')
            wrapper(ho / 'EXIT', ho / 'COMPLETE.json')
            require(ht['rc'] == 0 and ht['config_sha256'] == entry['config_sha256'] and ht['audit_sha256'] == sha(ho / 'HARDENED_AUDIT.json')
                    and (ho / 'HARDENED_AUDIT.json').stat().st_mtime_ns <= (ho / 'COMPLETE.json').stat().st_mtime_ns, 'Hardened terminal differs')
            require(hr['config_sha256'] == entry['config_sha256'] and hr['report_sha256'] == sha(run / 'report.json')
                    and hr['status'] in ['VERIFIED_HARDENED_SCOPED', 'VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED'], 'Hardened report differs')
            flags = {'native': flags, 'hardened': hr['review_flags'], 'inherited': hr['inherited_review_flags']}
            paths += [ho / n for n in ['COMPLETE.json', 'EXIT', 'HARDENED_AUDIT.json', 'LAUNCH_RECEIPT.json']]
        return {'config_sha256': entry['config_sha256'], 'plan_sha256': self.hash, 'evidence': {str(p): sha(p) for p in paths}, 'review_flags': flags}

    def release(self, c, acceptance):
        marker = self.out / (c['key'] + '-RELEASED.json')
        intent = self.out / (c['key'] + '-RELEASE_INTENT.json')
        if marker.exists():
            m = load(marker)
            require(m['plan_sha256'] == self.hash and m['config_sha256'] == load(acceptance)['config_sha256']
                    and m['acceptance_sha256'] == sha(acceptance), 'Release receipt differs')
            return
        evidence = {'plan_sha256': self.hash, 'config_sha256': load(acceptance)['config_sha256'], 'acceptance_sha256': sha(acceptance), 'run': 'reference_inference/' + Path(c['out']).name}
        with Path(self.plan['allocation'] + '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            a = load(self.plan['allocation'])
            owners = [x for x in a['allocation'] if x['chip'] == 1]
            free = [x for x in a['free'] if x['chip'] == 1]
            for obj in docker('GET', '/containers/json'):
                require(not any(d[0] == '/dev/davinci1' for d in devices(inspect(obj['Id']))), 'Live chip prevents release')
            if owners:
                require(len(owners) == 1 and owners[0]['run'] == evidence['run'] and not free, 'Release owner differs')
                if intent.exists():
                    require(load(intent) == evidence, 'Release intent differs')
                else:
                    atomic(intent, evidence)
                a['allocation'] = [x for x in a['allocation'] if x['chip'] != 1]
                a['free'].append({'chip': 1, 'previous_run': evidence['run'], 'release_evidence': str(acceptance), 'released_utc': utc()})
                atomic(self.plan['allocation'], a)
            else:
                require(intent.exists() and load(intent) == evidence and len(free) == 1
                        and free[0].get('release_evidence') == str(acceptance), 'Unproven prior release')
            atomic(marker, evidence)

    def step(self):
        self.check_plan()
        states = {}
        for c, entry in zip(self.configs, self.plan['entries']):
            ap = self.out / (c['key'] + '-ACCEPTED.json')
            if ap.exists():
                require(load(ap) == self.completion(c, entry), 'Accepted evidence changed')
                self.release(c, ap)
                states[c['key']] = {'stage': 'complete', 'review_flags': load(ap)['review_flags']}
                continue
            admitted = self.state.get('admitted', [])
            if c['key'] not in admitted:
                self.check_entry(c, entry)
                self.state['admitted'] = admitted + [c['key']]
                self.save()
            inference = self.reconcile(c, entry, 'inference')
            audit = self.reconcile(c, entry, 'finish')
            if inference == audit == 'exited':
                self.completion(c, entry, include_hardened=False)
                if self.reconcile(c, entry, 'hardened') != 'exited':
                    states[c['key']] = {'stage': 'hardened_audit', 'chips': 0}
                    break
                self.check_entry(c, entry)
                accepted = self.completion(c, entry)
                atomic(ap, accepted)
                self.release(c, ap)
                states[c['key']] = {'stage': 'complete', 'review_flags': accepted['review_flags']}
                continue
            p = Path(c['out']) / 'STATUS.json'
            status = load(p) if p.exists() else {}
            states[c['key']] = {'stage': 'inference' if inference != 'exited' else 'audit',
                'progress': status.get('progress'), 'total': status.get('total'), 'chips': 1,
                'questions_per_second_per_chip': status.get('questions_per_second_per_chip'), 'reserved_gib': status.get('reserved_gib')}
            break
        for key in self.keys:
            states.setdefault(key, {'stage': 'pending'})
        return states

    def run(self):
        self.out.mkdir(exist_ok=True)
        with (self.out / 'queue.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(docker('GET', '/info')['Name'] == 'k8s-node1', '175 Docker daemon only')
            self.controller_binding()
            terminal = self.out / 'QUEUE_COMPLETE.json'
            if terminal.exists():
                old = load(terminal)
                require(old['rc'] == 0 and old['plan_sha256'] == self.hash, 'Previous queue failure preserved; reviewed continuation required')
                require(all(s['stage'] == 'complete' for s in self.step().values()), 'Queue success changed')
                return
            try:
                # Restart rechecks immutable dependencies, even if previously admitted.
                for c, entry in zip(self.configs, self.plan['entries']):
                    self.check_entry(c, entry)
                while True:
                    states = self.step()
                    status = {'utc': utc(), 'plan_sha256': self.hash, 'entries': states}
                    atomic(self.out / 'STATUS.json', status)
                    lines = [status['utc']] + [k + ': ' + json.dumps(v, sort_keys=True) for k, v in states.items()]
                    (self.out / 'digest.md').write_text('\n'.join(lines) + '\n')
                    with (self.out / 'heartbeat.log').open('a') as f:
                        f.write(json.dumps(status) + '\n')
                    if all(v['stage'] == 'complete' for v in states.values()):
                        atomic(terminal, dict(status, rc=0))
                        return
                    time.sleep(10)
            except Exception as exc:
                atomic(self.out / 'FAILURE.json', {'utc': utc(), 'type': type(exc).__name__, 'message': str(exc)})
                atomic(terminal, {'utc': utc(), 'rc': 1, 'plan_sha256': self.hash, 'failure': str(self.out / 'FAILURE.json')})
                (self.out / 'digest.md').write_text(utc() + ' failed; see ' + str(self.out / 'FAILURE.json') + '\n')
                raise


def audit(config, auditor, out):
    out = Path(out)
    require(not any((out / n).exists() for n in ['COMPLETE.json', 'HARDENED_AUDIT.json', 'EXIT']), 'Old hardened evidence preserved')
    rc = 1
    ch = sha(config)
    try:
        subprocess.run([sys.executable, '-P', str(auditor), '--config', str(config), '--out', str(out / 'HARDENED_AUDIT.json')], check=True)
        report = load(out / 'HARDENED_AUDIT.json')
        require(report['config_sha256'] == ch and sha(config) == ch, 'Hardened config binding')
        rc = 0
    finally:
        terminal = {'rc': rc, 'utc': utc(), 'config_sha256': ch}
        if rc == 0:
            terminal['audit_sha256'] = sha(out / 'HARDENED_AUDIT.json')
        atomic(out / 'COMPLETE.json', terminal)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path)
    p.add_argument('--audit-config', type=Path)
    p.add_argument('--auditor', type=Path)
    p.add_argument('--audit-out', type=Path)
    a = p.parse_args()
    if a.audit_config:
        audit(a.audit_config, a.auditor, a.audit_out)
    else:
        try:
            Queue(a.plan).run()
        except Exception as exc:
            # Even configuration admission failures before construction get a terminal.
            # Do not overwrite any previous success/failure evidence.
            out = Path(load(a.plan)['out'])
            with (out / 'queue.lock').open('w') as failure_lock:
                fcntl.flock(failure_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if (out / 'QUEUE_COMPLETE.json').exists():
                    raise
                atomic(out / 'FAILURE.json', {'utc': utc(), 'type': type(exc).__name__, 'message': str(exc)})
                atomic(out / 'QUEUE_COMPLETE.json', {'utc': utc(), 'rc': 1, 'plan_sha256': sha(a.plan), 'failure': str(out / 'FAILURE.json')})
                (out / 'digest.md').write_text(utc() + ' failed; see ' + str(out / 'FAILURE.json') + '\n')
            raise
