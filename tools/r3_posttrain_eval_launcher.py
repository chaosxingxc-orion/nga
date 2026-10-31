#!/usr/bin/env python3
"""Engineering Track K dev/calibration execution; never selects a scientific winner.

bind freezes a prepared posttrain specification and launcher dependencies. start
runs a detached supervisor that waits for an explicitly free chip. Failed runs
can be resumed with a higher --attempt using the evaluator's item cache.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
ENTRY = str(BASE / 'r3_code/eval_r3.py')
GROUPS = ','.join(f'{suite}/{split}/{kind}'
    for suite, split in [('decision-v7', 'dev'), ('decision-v7', 'calibration'), ('transfer-v4', 'dev')]
    for kind in (('clean', 'question_only', 'empty_input') if split == 'calibration'
                 else ('clean', 'variants', 'question_only', 'empty_input')))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.pending')
    temp.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    os.replace(temp, path)


def safe_file(path):
    p = Path(path)
    require(p.is_absolute() and p.is_file(), 'missing absolute file: ' + str(p))
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink dependency')
    return p


def expected_command(spec, out):
    arm = spec['training_variant']['arm'].upper()
    require(arm in ('K1', 'K2'), 'unsupported training arm')
    return ['python3', '-P', ENTRY, '--full', '--model-path', spec['model'],
            '--adapter', spec['adapter'], '--arm', arm, '--out', str(out / 'results'),
            '--round-dir', str(out / 'identity'), '--partitions', 'dev,calibration',
            '--stages', 'k_score', '--k-only', GROUPS, '--scorer', 'rightpad',
            '--dtype', 'float32', '--no-hf32', '--token-budget', '16384',
            '--require-record-grade', '--device', 'npu:0']


def verify_spec(spec, out):
    require(spec['schema'] == 'r3-posttrain-dev-spec-v1', 'unexpected specification')
    require(spec['image_sha256'] == IMAGE and spec['network'] == 'none', 'image/network differs')
    require(spec['test_read'] is False and spec['scientific_acceptance'] is False, 'scope differs')
    require(spec['training_exit']['exit_code'] == 0, 'training did not succeed')
    require(spec['command'] == expected_command(spec, out), 'command differs from engineering Track K recipe')
    require(len(spec['readonly_data_mounts']) == 7, 'expected seven non-test data inputs')
    allowed_data = {str(BASE / 'KEV/manifest.json'), str(BASE / 'KEV/decision-v7/train.jsonl')}
    for suite, split in [('decision-v7', 'dev'), ('decision-v7', 'calibration'), ('transfer-v4', 'dev')]:
        allowed_data.add(str(BASE / 'KEV' / suite / (split + '.jsonl')))
        if split == 'dev':
            allowed_data.add(str(BASE / 'KEV' / suite / (split + '.variants.jsonl')))
    require(set(spec['readonly_data_mounts']) == allowed_data, 'non-test data inventory differs')
    for filename, digest in spec['files'].items():
        require(sha(safe_file(filename)) == digest, 'frozen dependency changed: ' + filename)
    require(allowed_data <= set(spec['files']), 'unbound data input')
    expected_dest = {str(BASE / 'r3_code'), str(BASE / 'r0_code')}
    require(len(spec['code_mounts']) == 2 and {m['destination'] for m in spec['code_mounts']} == expected_dest,
            'code mount destinations differ')
    for mount in spec['code_mounts']:
        require(mount['readonly'] is True, 'writable code')
        root = Path(mount['source'])
        require(not any(p.is_symlink() for p in (root, *root.parents, *root.rglob('*'))), 'code symlink')
        files = {str(p) for p in root.rglob('*') if p.is_file()}
        require(files and files <= set(spec['files']), 'unbound code dependency')
    for directory in (spec['model'], spec['adapter']):
        root = Path(directory)
        require(not any(p.is_symlink() for p in (root, *root.parents, *root.rglob('*'))), 'model/adapter symlink')
        files = {str(p) for p in root.rglob('*') if p.is_file()}
        require(files and files <= set(spec['files']), 'unbound model/adapter dependency')
    training = Path(spec['training'])
    require(str(training / 'manifest.json') in spec['files'] and str(training / 'TRAIN_EXIT.json') in spec['files'],
            'unbound training identity')
    require(load(training / 'TRAIN_EXIT.json')['exit_code'] == 0 and
            load(training / 'manifest.json').get('summary', {}).get('final_step') == 3116, 'incomplete training')


def bind(spec_path, chip, container):
    source = safe_file(spec_path)
    out = source.parent
    require(out.is_relative_to(BASE / 'r3_runs'), 'output must be in r3_runs')
    spec = load(source)
    verify_spec(spec, out)
    require(type(chip) is int and 0 <= chip < 8, 'invalid chip')
    require(container.startswith('nga-r3-eng-eval-') and all(c.isalnum() or c in '-_' for c in container), 'invalid container name')
    require(not (out / 'results').exists() and not (out / 'identity').exists(), 'fresh output required')
    frozen = out / 'execution-tools'
    frozen.mkdir(exist_ok=False)
    for name in ('r3_posttrain_eval_launcher.py', 'r3_resource_adapter.py'):
        shutil.copy2(Path(__file__).with_name(name), frozen / name)
    p = {'schema': 'r3-engineering-posttrain-execution-v1', 'spec': str(source), 'spec_sha256': sha(source),
         'chip': chip, 'container': container, 'out': str(out), 'run': str(out.relative_to(BASE)),
         'allocation': str(BASE / 'CHIP-ALLOCATION.json'), 'launcher': str(frozen / Path(__file__).name),
         'resource_adapter': str(frozen / 'r3_resource_adapter.py'),
         'tools': {str(f): sha(f) for f in frozen.iterdir()},
         'execution_scope': 'engineering_only', 'scientific_acceptance': False, 'test_read': False}
    path = out / 'execution.json'
    with path.open('x') as stream:
        json.dump(p, stream, indent=2); stream.write('\n')
    return path, sha(path)


def verify(path, pin):
    require(sha(safe_file(path)) == pin, 'execution plan changed')
    p = load(path)
    require(p['schema'] == 'r3-engineering-posttrain-execution-v1', 'execution schema differs')
    require(p['execution_scope'] == 'engineering_only' and p['test_read'] is False and
            p['scientific_acceptance'] is False, 'execution scope differs')
    require(Path(path).parent == Path(p['out']) and Path(p['out']).is_relative_to(BASE / 'r3_runs'), 'output differs')
    require(p['allocation'] == str(BASE / 'CHIP-ALLOCATION.json') and p['run'] == str(Path(p['out']).relative_to(BASE)), 'ledger/run differs')
    require(type(p['chip']) is int and 0 <= p['chip'] < 8, 'invalid chip')
    for name in ('launcher', 'resource_adapter'):
        require(p[name] in p['tools'], 'unbound execution tool')
    for filename, digest in p['tools'].items():
        require(sha(safe_file(filename)) == digest, 'execution tool changed')
    require(Path(__file__).resolve() == Path(p['launcher']).resolve(), 'different executable launcher')
    require(sha(safe_file(p['spec'])) == p['spec_sha256'], 'evaluation specification changed')
    spec = load(p['spec'])
    verify_spec(spec, Path(p['out']))
    return p, spec


def resource_module(p):
    spec = importlib.util.spec_from_file_location('resource', p['resource_adapter'])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def resource_op(p, op, attempt, name):
    command = [sys.executable, '-P', p['resource_adapter'], op, '--alloc', p['allocation'],
               '--run', p['run'], '--chip', str(p['chip']), '--proof', str(attempt / (op.upper() + '.json'))]
    if op == 'claim':
        command += ['--owner', 'R3 engineering dev inference', '--purpose', 'Track K dev/calibration only']
    else:
        command += ['--container', name, '--claim', str(attempt / 'CLAIM.json')]
    subprocess.run(command, check=True)


def docker_command(p, spec, plan_path, pin, attempt):
    name = p['container'] + '-a' + str(attempt)
    command = ['docker', 'run', '-d', '--pull=never', '--name', name, '--network=none', '--shm-size', '64g',
               '--ulimit', 'memlock=-1:-1', '--ulimit', 'stack=67108864:67108864']
    mounts = {m['destination']: (m['source'], True) for m in spec['code_mounts']}
    for directory in (spec['model'], spec['adapter']):
        mounts[directory] = (directory, True)
    for filename in spec['readonly_data_mounts'] + [str(Path(spec['training']) / 'manifest.json')]:
        mounts[filename] = (filename, True)
    mounts[p['out']] = (p['out'], False)
    mounts['/usr/local/Ascend/driver'] = ('/usr/local/Ascend/driver', True)
    for dst, (src, readonly) in mounts.items():
        command += ['--mount', f'type=bind,src={src},dst={dst}' + (',readonly' if readonly else '')]
    for device in ('davinci_manager', 'devmm_svm', 'hisi_hdc', f"davinci{p['chip']}"):
        command += ['--device', '/dev/' + device]
    for key, value in {'ASCEND_RT_VISIBLE_DEVICES': '0', 'TASK_QUEUE_ENABLE': '2',
                       'PYTORCH_NPU_ALLOC_CONF': 'expandable_segments:True', 'PYTHONDONTWRITEBYTECODE': '1',
                       'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'}.items():
        command += ['-e', key + '=' + value]
    return command + ['--entrypoint', 'python3', IMAGE, '-P', p['launcher'], 'drive',
                      '--plan', str(plan_path), '--sha256', pin, '--attempt', str(attempt)]


def drive(path, pin, number):
    # Host verified dependencies before launch. Container mounts intentionally omit
    # training internals; here bind the executable command to the exact pinned plan.
    require(sha(path) == pin, 'execution plan changed in container')
    p = load(path); require(sha(p['spec']) == p['spec_sha256'], 'specification changed in container')
    spec = load(p['spec']); require(spec['command'] == expected_command(spec, Path(p['out'])), 'command changed')
    attempt = Path(p['out']) / 'attempts' / str(number)
    rc, process = 125, None
    try:
        with (attempt / 'run.log').open('ab', buffering=0) as log:
            process = subprocess.Popen(spec['command'], cwd='/tmp', stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            def stop(sig, frame):
                try: os.killpg(process.pid, sig)
                except ProcessLookupError: pass
            signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
            while process.poll() is None:
                count = sum(1 for _ in (Path(p['out']) / 'results').rglob('*.jsonl'))
                atomic(attempt / 'heartbeat.json', {'utc_seconds': time.time(), 'pid': process.pid,
                       'readout_files': count, 'progress_unit': 'files, not scored questions'})
                time.sleep(15)
            rc = process.returncode
            if rc == 0:
                marker = Path(p['out']) / 'results/EVAL_COMPLETE.json'
                require(marker.exists() and load(marker).get('exit_code') == 0, 'evaluator terminal marker missing or failed')
    except BaseException:
        if rc == 0: rc = 125
        raise
    finally:
        terminal = {'exit_code': rc, 'attempt': number, 'utc_seconds': time.time(), 'scientific_acceptance': False}
        atomic(attempt / 'EXIT.json', terminal)
        atomic(Path(p['out']) / 'ENGINEERING_EVAL_EXIT.json', terminal)
    return rc


def supervise(path, pin, number):
    p, spec = verify(path, pin)
    require(socket.gethostname() == 'k8s-node1', 'host 175 only')
    require(number >= 1, 'invalid attempt')
    out = Path(p['out']); name = p['container'] + '-a' + str(number)
    lock = (out / 'supervisor.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    attempt = out / 'attempts' / str(number); attempt.mkdir(parents=True, exist_ok=True)
    resource = resource_module(p)
    try:
        actual = resource.docker_inspect(name)
        if actual is None:
            terminal = out / 'ENGINEERING_EVAL_EXIT.json'
            if terminal.exists():
                prior = load(terminal)
                require(prior['exit_code'] != 0 and prior['attempt'] < number, 'cannot repeat completed attempt')
                require((out / 'attempts' / str(prior['attempt']) / 'RELEASE.json').exists(), 'prior attempt not released')
            else:
                require(number == 1 and not (out / 'results').exists() and not (out / 'identity').exists(), 'first attempt output is not fresh')
            require(not (attempt / 'EXIT.json').exists() and not (attempt / 'ABORT.json').exists(), 'attempt already terminal/aborted')
            while not (attempt / 'CLAIM.json').exists():
                allocation = resource.load(p['allocation']); resource.validate_doc(allocation)
                free = any(x['chip'] == p['chip'] for x in allocation['free'])
                if (attempt / 'CLAIM.json.intent').exists() or (free and not resource.live_chip_conflict(p['chip'], name)):
                    p, spec = verify(path, pin)
                    resource_op(p, 'claim', attempt, name)
                    break
                atomic(attempt / 'supervisor_heartbeat.json', {'utc_seconds': time.time(), 'status': 'waiting_resource'})
                time.sleep(15)
            # Claims are durable; on restart require the ledger still names this run.
            ownership = resource.load(p['allocation'])
            require(any(x['chip'] == p['chip'] and x['run'] == p['run'] for x in ownership['allocation']), 'claim no longer owns chip')
            command = docker_command(p, spec, path, pin, number)
            atomic(attempt / 'LAUNCH_SPEC.json', {'command': command, 'sha256': pin})
            try:
                require(subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip() == IMAGE, 'image differs')
                subprocess.run(command, check=True)
            except BaseException:
                if resource.docker_inspect(name) is None:
                    resource_op(p, 'abort', attempt, name)
                raise
            actual = resource.docker_inspect(name)
            require(actual is not None, 'container cannot be observed')
            atomic(attempt / 'LAUNCH_RECEIPT.json', {'id': actual['Id'], 'image': actual['Image'], 'sha256': pin})
        claim = load(attempt / 'CLAIM.json')
        require(claim.get('run') == p['run'] and claim.get('chip') == p['chip'], 'claim identity differs')
        receipt = attempt / 'LAUNCH_RECEIPT.json'
        if receipt.exists():
            require(load(receipt)['id'] == actual['Id'], 'retained container generation differs')
        require(actual['Image'] == IMAGE and not actual['HostConfig']['AutoRemove'], 'container image/retention differs')
        expected_cmd = ['-P', p['launcher'], 'drive', '--plan', str(path), '--sha256', pin, '--attempt', str(number)]
        require(actual['Config']['Cmd'] == expected_cmd, 'container command differs')
        require({d['PathOnHost'] for d in actual['HostConfig']['Devices']} ==
                {'/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', f"/dev/davinci{p['chip']}"}, 'container device differs')
        container_id = actual['Id']
        while actual['State']['Status'] not in ('exited', 'dead'):
            atomic(attempt / 'supervisor_heartbeat.json', {'utc_seconds': time.time(), 'status': actual['State']['Status'], 'container_id': container_id})
            time.sleep(15)
            try:
                observed = resource.docker_inspect(name)
                require(observed is not None and observed['Id'] == container_id, 'retained container missing/replaced')
                actual = observed
            except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
                atomic(attempt / 'supervisor_heartbeat.json', {'utc_seconds': time.time(), 'status': 'observation_unknown', 'error': str(error)[:300]})
        with (attempt / 'container.log').open('wb') as log:
            subprocess.run(['docker', 'logs', name], stdout=log, stderr=subprocess.STDOUT, check=True)
        if not (attempt / 'EXIT.json').exists():
            atomic(attempt / 'EXIT.json', {'exit_code': actual['State']['ExitCode'], 'attempt': number,
                   'source': 'retained-container-exit', 'scientific_acceptance': False})
            atomic(out / 'ENGINEERING_EVAL_EXIT.json', load(attempt / 'EXIT.json'))
        require(load(attempt / 'EXIT.json')['exit_code'] == actual['State']['ExitCode'], 'terminal/container exit mismatch')
        resource_op(p, 'release', attempt, name)
        atomic(attempt / 'SUPERVISOR_DONE.json', {'exit_code': actual['State']['ExitCode'], 'scientific_acceptance': False})
    except BaseException as error:
        atomic(attempt / 'SUPERVISOR_FAILED.json', {'error': str(error), 'scientific_acceptance': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('bind', 'verify', 'start', 'supervise', 'drive'))
    parser.add_argument('--plan', required=True); parser.add_argument('--sha256')
    parser.add_argument('--chip', type=int); parser.add_argument('--container'); parser.add_argument('--attempt', type=int, default=1)
    a = parser.parse_args()
    if a.op == 'bind':
        path, pin = bind(a.plan, a.chip, a.container)
        print(json.dumps({'plan': str(path), 'sha256': pin, 'scientific_acceptance': False})); return 0
    if a.op == 'drive': return drive(a.plan, a.sha256, a.attempt)
    p, spec = verify(a.plan, a.sha256)
    if a.op == 'verify': print(json.dumps({'status': 'ENGINEERING_EXECUTION_VERIFIED', 'scientific_acceptance': False}))
    elif a.op == 'supervise': supervise(a.plan, a.sha256, a.attempt)
    else:
        require(socket.gethostname() == 'k8s-node1', 'host 175 only')
        command = [sys.executable, '-P', p['launcher'], 'supervise', '--plan', a.plan, '--sha256', a.sha256, '--attempt', str(a.attempt)]
        with (Path(p['out']) / 'supervisor.log').open('ab', buffering=0) as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        atomic(Path(p['out']) / 'SUPERVISOR_RECEIPT.json', {'pid': process.pid, 'command': command})
        atomic(Path(p['out']) / 'RELAUNCH.json', {'command': [sys.executable, '-P', p['launcher'], 'start', '--plan', a.plan, '--sha256', a.sha256, '--attempt', str(a.attempt)], 'resume_note': 'For a failed released attempt increment --attempt; readout item caches resume.'})
        print(json.dumps({'status': 'SUPERVISOR_STARTED', 'pid': process.pid, 'container_started': False}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
