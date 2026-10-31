#!/usr/bin/env python3
"""Host-175 formal training supervisor. No scientific acceptance is implied by release."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time

IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def identity(plan):
    value = dict(plan, review_sha256='PENDING')
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2) + '\n').encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, path)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def verify(path, pin, reviewed=True):
    p = load(path)
    require(identity(p) == pin, 'plan identity changed')
    require(p['schema'] in ('r3-formal-k1-plan-v1', 'r3-engineering-k1-plan-v1') and p['image_sha256'] == IMAGE, 'plan schema/image mismatch')
    require(p['seed'] in (2, 3) and p['chip'] in (1, 4), 'unregistered seed/chip')
    expected = ['python3', '-P', '/workspace/train_r3.py', '--out', p['out'], '--arm', 'k1', '--seed', str(p['seed']),
                '--model-path', p['model'], '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
                '--save-every', '200', '--no-merge', '--epochs', '2', '--total-steps', '3116', '--expect-pairs', '186']
    require(p['command'] == expected, 'training recipe mismatch')
    for filename, digest in p['files'].items():
        q = Path(filename)
        require(not any(x.is_symlink() for x in (q, *q.parents)), 'symlink dependency')
        require(sha(q) == digest, 'frozen dependency changed: ' + filename)
    for name in ('launcher', 'driver', 'adapter'):
        require(p[name] in p['files'], 'unbound tool: ' + name)
    require(Path(p['launcher']).resolve() == Path(__file__).resolve(), 'different executable launcher')
    require(p['train_file'] in p['files'], 'unbound train')
    require(not any('/test' in f for f in p['files']), 'test dependency forbidden')
    source_files = {str(f) for f in Path(p['code']).rglob('*') if f.is_file()}
    require(source_files == {f for f in p['files'] if f.startswith(p['code'] + '/')}, 'code closure inventory mismatch')
    if p['schema'] == 'r3-engineering-k1-plan-v1':
        require(p.get('execution_scope') == 'engineering_only' and p.get('scientific_acceptance') is False
                and p.get('test_read') is False, 'engineering scope must exclude scientific acceptance/test')
        require(p.get('authorization') == 'user_execute_engineering_when_ready_20261031', 'engineering authorization missing')
    elif reviewed:
        review = load(p['review_path'])
        require(sha(p['review_path']) == p['review_sha256'], 'review hash mismatch')
        require(review.get('approved_plan_sha256') == pin and review.get('verdict') == 'PASS'
                and review.get('review_kind') == 'independent_astra'
                and review.get('reviewer_model') == 'gpt-6-astra', 'independent exact-plan Astra PASS required')
    return p


def inspect(name):
    proc = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        require('no such' in proc.stderr.lower(), 'Docker observation failed: ' + proc.stderr[:200])
        return None
    return json.loads(proc.stdout)[0]


def observe_retained(name, container_id, heartbeat, sleep=time.sleep):
    """Retry uncertain observations; never infer exit/release from a timeout or absence."""
    while True:
        try:
            value = inspect(name)
            require(value is not None, 'retained container missing')
            require(value['Id'] == container_id, 'retained generation changed')
            return value
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
            atomic(heartbeat, {'utc_seconds': time.time(), 'container': name,
                               'status': 'observation_unknown', 'error': str(error)[:300],
                               'action': 'retry_without_restart_or_release'})
            sleep(15)


def adapter(p, op, attempt, container):
    cmd = [sys.executable, '-P', p['adapter'], op, '--alloc', p['allocation'], '--run', p['run'], '--chip', str(p['chip'])]
    if op == 'claim':
        owner = 'R3 engineering K1' if p['schema'] == 'r3-engineering-k1-plan-v1' else 'R3 formal K1'
        cmd += ['--owner', owner, '--purpose', f"K1 seed {p['seed']}; train only", '--proof', str(attempt / 'CLAIM.json')]
    else:
        cmd += ['--container', container, '--claim', str(attempt / 'CLAIM.json'), '--proof', str(attempt / (op.upper() + '.json'))]
    subprocess.run(cmd, check=True)


def docker_command(p, plan_path, attempt_no):
    name = p['container'] + '-a' + str(attempt_no)
    cmd = ['docker', 'run', '-d', '--pull=never', '--name', name, '--network=none', '--shm-size', '64g',
           '--ulimit', 'memlock=-1:-1', '--ulimit', 'stack=67108864:67108864',
           '--mount', f"type=bind,src={p['code']},dst=/workspace,readonly",
           '--mount', f"type=bind,src={p['model']},dst={p['model']},readonly",
           '--mount', f"type=bind,src={p['train_file']},dst={p['train_file']},readonly",
           '--mount', f"type=bind,src={p['out']},dst={p['out']}",
           '--mount', 'type=bind,src=/usr/local/Ascend/driver,dst=/usr/local/Ascend/driver,readonly']
    for dev in ('davinci_manager', 'devmm_svm', 'hisi_hdc', f"davinci{p['chip']}"):
        cmd += ['--device', '/dev/' + dev]
    for key, value in p['environment'].items():
        cmd += ['-e', key + '=' + value]
    cmd += ['--entrypoint', 'python3', p['image_sha256'], '-P', '/workspace/r3_formal_driver.py',
            '--plan', plan_path, '--attempt', str(attempt_no)]
    return cmd


def supervisor(path, pin, attempt_no):
    p = verify(path, pin)
    require(socket.gethostname() == 'k8s-node1', 'must run on host npu / 175')
    image = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    require(image == IMAGE, 'actual image digest mismatch')
    out = Path(p['out'])
    lock = (out / 'supervisor.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    attempt = out / 'attempts' / str(attempt_no)
    attempt.mkdir(parents=True, exist_ok=True)
    container = p['container'] + '-a' + str(attempt_no)
    try:
        d = inspect(container)
        if d is None:
            terminal = out / 'TRAIN_EXIT.json'
            if terminal.exists():
                last = load(terminal)
                require(last['exit_code'] != 0 and last['attempt'] < attempt_no, 'cannot repeat a completed attempt')
                prior = out / 'attempts' / str(last['attempt'])
                require((prior / 'RELEASE.json').exists(), 'previous attempt is not released')
            require(not (attempt / 'EXIT.json').exists(), 'attempt already terminal')
            # A ledger entry alone cannot establish absence of a stale live device holder.
            spec = __import__('importlib.util', fromlist=['util']).spec_from_file_location('resource_adapter', p['adapter'])
            resource = __import__('importlib.util', fromlist=['util']).module_from_spec(spec)
            spec.loader.exec_module(resource)
            require(not resource.live_chip_conflict(p['chip'], container), 'live container owns device')
            adapter(p, 'claim', attempt, container)
            command = docker_command(p, path, attempt_no)
            atomic(attempt / 'LAUNCH_SPEC.json', {'command': command, 'plan_sha256': pin})
            try:
                subprocess.run(command, check=True)
            except BaseException:
                if inspect(container) is None:
                    adapter(p, 'abort', attempt, container)
                raise
            d = inspect(container)
            require(d is not None, 'started container cannot be observed')
            atomic(attempt / 'LAUNCH_RECEIPT.json', {'id': d['Id'], 'image': d['Image'], 'plan_sha256': pin})
        require(d['Image'] == IMAGE and not d['HostConfig']['AutoRemove'], 'container identity mismatch')
        require(d['Config']['Cmd'] == ['-P', '/workspace/r3_formal_driver.py', '--plan', path, '--attempt', str(attempt_no)], 'container command mismatch')
        devices = {x['PathOnHost'] for x in d['HostConfig']['Devices']}
        require(devices == {'/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', f"/dev/davinci{p['chip']}"}, 'container devices mismatch')
        while d['State']['Status'] not in ('exited', 'dead'):
            atomic(attempt / 'supervisor_heartbeat.json', {'utc_seconds': time.time(), 'container': container, 'status': d['State']['Status']})
            time.sleep(15)
            d = observe_retained(container, d['Id'], attempt / 'supervisor_heartbeat.json')
        # Preserve Docker startup stderr even when the Python driver never started.
        with (attempt / 'container.log').open('wb') as f:
            subprocess.run(['docker', 'logs', container], stdout=f, stderr=subprocess.STDOUT, check=True)
        if not (attempt / 'EXIT.json').exists():
            atomic(attempt / 'EXIT.json', {'exit_code': d['State']['ExitCode'], 'attempt': attempt_no,
                                         'source': 'retained-container-exit', 'scientific_acceptance': False})
            atomic(out / 'TRAIN_EXIT.json', load(attempt / 'EXIT.json'))
        adapter(p, 'release', attempt, container)
        atomic(attempt / 'SUPERVISOR_DONE.json', {'exit_code': d['State']['ExitCode'], 'scientific_acceptance': False})
    except BaseException as e:
        atomic(attempt / 'SUPERVISOR_FAILED.json', {'error': str(e), 'scientific_acceptance': False})
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('op', choices=('verify', 'start', 'supervise'))
    ap.add_argument('--plan', required=True)
    ap.add_argument('--sha256', required=True)
    ap.add_argument('--attempt', type=int, default=1)
    ap.add_argument('--unreviewed', action='store_true')
    a = ap.parse_args()
    require(not a.unreviewed or a.op == 'verify', 'unreviewed allowed only for CPU verification')
    p = verify(a.plan, a.sha256, reviewed=not a.unreviewed)
    if a.op == 'verify':
        print(json.dumps({'status': 'PLAN_VERIFIED', 'reviewed': not a.unreviewed and p['schema'] == 'r3-formal-k1-plan-v1', 'scope': p.get('execution_scope', 'formal'), 'sha256': a.sha256}))
    elif a.op == 'supervise':
        supervisor(a.plan, a.sha256, a.attempt)
    else:
        require(socket.gethostname() == 'k8s-node1', 'must start on host npu / 175')
        cmd = [sys.executable, '-P', p['launcher'], 'supervise', '--plan', a.plan, '--sha256', a.sha256, '--attempt', str(a.attempt)]
        with (Path(p['out']) / 'supervisor.log').open('ab', buffering=0) as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atomic(Path(p['out']) / 'SUPERVISOR_RECEIPT.json', {'pid': process.pid, 'command': cmd})
        print(json.dumps({'status': 'SUPERVISOR_STARTED', 'pid': process.pid, 'container_started': False}))


if __name__ == '__main__':
    main()
