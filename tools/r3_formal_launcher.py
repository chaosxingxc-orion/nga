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
CONTROL_MODELS = {'K1-QO':'/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base',
                  'K1-PT':'/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'}


def source_module(path, name):
    """Compile the actual source bytes; never execute import-cache bytecode."""
    import types
    path = safe_content_path(path)
    raw = path.read_bytes()
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), value.__dict__)
    return value


def safe_content_path(path):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe content path')
    require(not is_test_data(path), 'test dataset dependency forbidden')
    return path


def sha(path):
    path=safe_content_path(path)
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(path):
    return json.loads(safe_content_path(path).read_text())


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


def is_test_data(filename):
    path = Path(filename)
    return path.name in ('test.jsonl', 'test.variants.jsonl') or (
        'test' in path.parts and path.suffix in ('.jsonl', '.parquet'))


def verify_fresh_prechecks(p):
    import importlib.util
    helper_path = Path(__file__).with_name('r3_fresh_prechecks.py')
    require(str(helper_path) in p['files'], 'fresh precheck verifier not pinned')
    require(p['files'][str(helper_path)] == sha(helper_path), 'fresh precheck source differs')
    require(p.get('fresh_k0_prechecks') in p['files'] and
            p['files'][p['fresh_k0_prechecks']] == p.get('fresh_k0_prechecks_sha256'),
            'fresh K0 prechecks not bound')
    helper = source_module(helper_path, 'formal_fresh_prechecks')
    bundle = helper.validate_bundle(p['fresh_k0_prechecks'], p['fresh_k0_prechecks_sha256'], p['model'])
    require(all(p['files'].get(f) == h for f,h in {**bundle['inputs'], **bundle['checks']}.items()),
            'fresh precheck dependencies not bound')


def verify_resume_evidence(p):
    import importlib.util
    helper_path = Path(__file__).with_name('r3_resume_evidence.py')
    require(str(helper_path) in p['files'], 'resume evidence verifier not pinned')
    require(p.get('resume_plan') in p['files'] and p.get('resume_plan_sha256'), 'resume plan not bound')
    require(p['files'][str(helper_path)] == sha(helper_path), 'resume verifier source differs')
    helper = source_module(helper_path, 'formal_resume_evidence')
    evidence = helper.validate(p['resume_plan'], p['resume_plan_sha256'], p)
    require(all(p['files'].get(f) == h for f,h in evidence.items()), 'resume evidence dependencies not bound')


def verify_resume_reconstruction(p):
    import importlib.util
    helper_path = Path(__file__).with_name('r3_resume_reconstruction_evidence.py')
    require(p['files'].get(str(helper_path)) == sha(helper_path), 'reconstruction verifier not pinned')
    for field in ('resume_reconstruction', 'reconstruction_target'):
        require(p.get(field) in p['files'] and p.get(field+'_sha256')
                and p['files'][p[field]] == p[field+'_sha256'], 'reconstruction artifact not bound')
    helper = source_module(helper_path, 'formal_resume_reconstruction')
    files = helper.validate(p['resume_reconstruction'], p['resume_reconstruction_sha256'],
        resume_plan=p['resume_plan'], resume_pin=p['resume_plan_sha256'], target=p,
        reconstruction_target=p['reconstruction_target'],
        reconstruction_target_sha256=p['reconstruction_target_sha256'])
    require(all(p['files'].get(f) == h for f,h in files.items()), 'reconstruction dependencies not bound')


def validate_dependency_inventory(files):
    """Check every path before reading any dependency bytes."""
    require(isinstance(files, dict), 'dependency inventory required')
    for filename in files:
        q = Path(filename)
        require(q.is_absolute() and '..' not in q.parts and
                not any(x.is_symlink() for x in (q, *q.parents)), 'unsafe dependency path')
        require(not is_test_data(filename), 'test dataset dependency forbidden')


def formal_target_identity(p):
    """Shared non-I/O identity invariants for formal launch and readiness."""
    require(p.get('schema') == 'r3-formal-k1-plan-v1' and
            p.get('scientific_acceptance') is False and p.get('test_read') is False,
            'formal scope differs')
    require(type(p.get('chip')) is int and p['chip'] in (1, 4), 'formal chip differs')
    require(type(p.get('seed')) is int and p['seed'] in (2, 3), 'formal seed differs')
    evaluation = p.get('evaluation', {})
    require(evaluation.get('test_requires_separate_final_ticket') is True,
            'separate final test ticket required')
    arm = p.get('control_arm')
    if arm is not None:
        require(arm in CONTROL_MODELS, 'formal control arm differs')
        seeds = [2] if arm == 'K1-QO' else [2, 3]
        control = {'control_arm':arm, 'candidate_for_adoption':False,
                   'primary_input_mode':'drop' if arm == 'K1-QO' else 'full',
                   'registered_seeds':seeds}
        require(p['seed'] in seeds and p.get('model') == CONTROL_MODELS[arm],
                'formal control model/seed differs')
        require(p.get('control') == control and all(evaluation.get(k) == v for k,v in control.items()),
                'formal control evaluation differs')
        suffix = hashlib.sha256(str(Path(p['out']).absolute()).encode()).hexdigest()[:16]
        require(p.get('container') == f'nga-r3-formal-{arm.lower()}-s{p["seed"]}-{suffix}',
                'formal control container identity differs')


def verify(path, pin, reviewed=True):
    p = load(path)
    require(identity(p) == pin, 'plan identity changed')
    require(p.get('scientific_acceptance') is False and p.get('test_read') is False,
            'training scope must exclude scientific acceptance/test')
    require(p['schema'] in ('r3-formal-k1-plan-v1', 'r3-engineering-k1-plan-v1') and p['image_sha256'] == IMAGE, 'plan schema/image mismatch')
    validate_dependency_inventory(p['files'])
    engineering = p['schema'] == 'r3-engineering-k1-plan-v1'
    if not engineering:
        formal_target_identity(p)
    require(p['seed'] in (2, 3) and p['chip'] in (tuple(range(8)) if engineering else (1, 4)), 'unregistered seed/chip')
    model_name = Path(p['model']).name
    formal_models = ('Qwen__Qwen3.5-0.8B-Base', 'Qwen__Qwen3.5-0.8B')
    require(model_name in (('Qwen__Qwen3.5-0.8B-Base', 'Qwen__Qwen3.5-2B-Base', 'Qwen__Qwen3.5-4B-Base', 'Qwen__Qwen3.5-9B-Base', 'Qwen__Qwen3.5-0.8B') if engineering
                          else formal_models), 'model outside registered execution scope')
    pairs = '186' if model_name in ('Qwen__Qwen3.5-0.8B-Base','Qwen__Qwen3.5-0.8B') else '0'
    arm = p.get('arm', 'k1') if engineering else 'k1'
    require(arm in ('k1', 'k2'), 'unregistered loss arm')
    control_arm=p.get('control_arm')
    control_resume = engineering and p.get('validation_kind') == 'current_k1_resume_contract'
    if control_arm is not None:
        require(control_arm in ('K1-QO','K1-PT') and arm=='k1'
                and not p.get('k2_impl') and (not p.get('validation_kind') or control_resume), 'invalid engineering control recipe')
        model=CONTROL_MODELS[control_arm]
        seeds=[2] if control_arm=='K1-QO' else [2,3]
        mode='drop' if control_arm=='K1-QO' else 'full'
        require(p['model']==model and type(p['seed']) is int and p['seed'] in seeds,'control model/seed differs')
        if not engineering:
            require(p['schema'] == 'r3-formal-k1-plan-v1' and p.get('control', {}).get('candidate_for_adoption') is False,
                    'formal control provenance differs')
            require(isinstance(p.get('container'), str) and f'formal-{control_arm.lower()}-s{p["seed"]}-' in p['container'],
                    'formal control container identity differs')
        require(p.get('control')=={'control_arm':control_arm,'candidate_for_adoption':False,
                'primary_input_mode':mode,'registered_seeds':seeds},'control identity differs')
        require(all(p.get('evaluation',{}).get(k)==v for k,v in p['control'].items()),'control evaluation differs')
    else:
        require(model_name!='Qwen__Qwen3.5-0.8B' and not p.get('control'),'instruct checkpoint requires explicit K1-PT control')
    expected = ['python3', '-P', '/workspace/train_r3.py', '--out', p['out'], '--arm', arm, '--seed', str(p['seed']),
                '--model-path', p['model'], '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
                '--save-every', '200', '--no-merge', '--epochs', '2', '--total-steps', '3116', '--expect-pairs', pairs]
    if engineering and p.get('stop_after', 0):
        require(type(p['stop_after']) is int and 10 <= p['stop_after'] <= 3116, 'invalid engineering step bound')
        expected += ['--stop-after', str(p['stop_after'])]
    if control_arm=='K1-QO':expected += ['--drop-state']
    if engineering and p.get('k2_impl') == 'shared':
        require(arm == 'k2' and p.get('stop_after') in (0, 45), 'invalid shared engineering schedule')
        if not p.get('stop_after'):
            evidence = p.get('shared_contract')
            require(evidence in p['files'], 'shared numerical evidence not pinned')
            contract = load(evidence)
            require(contract.get('status') == 'CONTRACT_PASS' and len(contract.get('results', [])) == 4,
                    'shared numerical tests incomplete')
        expected.remove('--grad-ckpt')
        expected[expected.index('--micro-tokens')+1] = '3000'
        expected += ['--k2-impl', 'shared', '--gdn-impl', 'ref', '--k2-rows', '48']
    if engineering and p.get('validation_kind') == 'shared_k2_reference_contract':
        require(p.get('k2_impl') == 'shared', 'shared validation closure required')
        expected = ['python3', '-P', '/workspace/test_k2_shared.py', '--device', 'npu:0', '--impls', 'ref']
    if control_resume:
        require(type(p['seed']) is int and p['seed']==2 and not p.get('stop_after'), 'control restart seed/schedule differs')
        expected = ['python3', '-P', '/workspace/r3_resume_contract.py', '--out', p['out']]
    require(p['command'] == expected, 'training recipe mismatch')
    for filename, digest in p['files'].items():
        q = Path(filename)
        require(not any(x.is_symlink() for x in (q, *q.parents)), 'symlink dependency')
        require(sha(q) == digest, 'frozen dependency changed: ' + filename)
    for name in ('launcher', 'driver', 'adapter'):
        require(p[name] in p['files'], 'unbound tool: ' + name)
    require(Path(p['launcher']).resolve() == Path(__file__).resolve(), 'different executable launcher')
    require(p['train_file'] in p['files'], 'unbound train')
    require(not any(is_test_data(f) for f in p['files']), 'test dataset dependency forbidden')
    source_files = {str(f) for f in Path(p['code']).rglob('*') if f.is_file()}
    require(source_files == {f for f in p['files'] if f.startswith(p['code'] + '/')}, 'code closure inventory mismatch')
    if control_resume:
        import importlib.util
        helper_path=Path(__file__).with_name('r3_control_resume_prepare.py')
        require(p['files'].get(str(helper_path))==sha(helper_path),'control restart verifier not bound')
        helper = source_module(helper_path, 'control_restart_admission')
        helper.verify_launch(p)
    if not engineering:
        verify_resume_evidence(p)
        verify_resume_reconstruction(p)
        verify_fresh_prechecks(p)
        import importlib.util
        helper_path = Path(__file__).with_name('r3_training_evidence.py')
        require(str(helper_path) in p['files'], 'training evidence verifier not pinned')
        require(p.get('training_evidence') in p['files'] and
                p['files'][p['training_evidence']] == p.get('training_evidence_sha256'), 'training evidence not bound')
        helper = source_module(helper_path, 'formal_training_evidence')
        evidence = helper.validate(p['training_evidence'], p['training_evidence_sha256'],
                                   p['code'], p['model'], p['train_file'], p['image_sha256'],
                                   control_arm=control_arm,
                                   input_mode=(p.get('control') or {}).get('primary_input_mode', 'full'))
        require(all(p['files'].get(f) == h for f,h in evidence.items()), 'training evidence dependencies not bound')
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
        owner = 'R3 engineering ' + p.get('arm', 'k1').upper() if p['schema'] == 'r3-engineering-k1-plan-v1' else 'R3 formal K1'
        cmd += ['--owner', owner, '--purpose', f"{p.get('arm', 'k1')} seed {p['seed']}; train only", '--proof', str(attempt / 'CLAIM.json')]
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
    if p.get('k2_impl') == 'shared':
        cmd += ['--mount', f"type=bind,src={p['code']}/r0_code,dst=/mnt/cephfs/xingchao/experiments/jev/r0_code,readonly"]
    if p.get('validation_kind'):
        cmd += ['--mount', f"type=bind,src={p['code']},dst=/mnt/cephfs/xingchao/experiments/jev/r3_code,readonly"]
    for dev in ('davinci_manager', 'devmm_svm', 'hisi_hdc', f"davinci{p['chip']}"):
        cmd += ['--device', '/dev/' + dev]
    for key, value in p['environment'].items():
        cmd += ['-e', key + '=' + value]
    cmd += ['--entrypoint', 'python3', p['image_sha256'], '-P', '/workspace/r3_formal_driver.py',
            '--plan', plan_path, '--attempt', str(attempt_no)]
    return cmd


def environment_map(items):
    require(isinstance(items, list), 'container environment list required')
    result = {}
    for item in items:
        require(isinstance(item, str) and '=' in item, 'invalid container environment')
        key, value = item.split('=', 1)
        require(key not in result, 'duplicate container environment key')
        result[key] = value
    return result


def daemon_policy():
    """Observe defaults from the actual daemon, not from the candidate container."""
    value=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True))
    require(value.get('DefaultRuntime') and value.get('CgroupVersion') in ('1','2'), 'unknown Docker defaults')
    return {'runtime':value['DefaultRuntime'],
            'cgroupns':'private' if value['CgroupVersion']=='2' else 'host'}


def verify_effective_policy(observed, image, environment, *, daemon=None):
    """Shared CPU/NPU execution policy; command, mounts/devices checked by caller."""
    require(image is not None and observed.get('Image')==image.get('Id'), 'pinned image configuration required')
    daemon=daemon_policy() if daemon is None else daemon
    cfg=observed.get('Config',{});host=observed.get('HostConfig',{});defaults=image.get('Config',{})
    expected=environment_map(defaults.get('Env') or []);expected.update(environment)
    require(environment_map(cfg.get('Env'))==expected,'retained environment differs')
    for key in ('User','WorkingDir','StopSignal'):
        require((cfg.get(key) or '')==(defaults.get(key) or ''),'retained image default differs: '+key)
    require(cfg.get('Healthcheck')==defaults.get('Healthcheck'),'retained healthcheck differs')
    for key in ('Tty','OpenStdin','StdinOnce'):
        require(not cfg.get(key),'retained interactive configuration: '+key)
    for key in ('CapAdd','CapDrop','SecurityOpt','DeviceRequests','DeviceCgroupRules','GroupAdd',
                'Binds','VolumesFrom','Links','ExtraHosts','Dns','DnsSearch','DnsOptions','Sysctls','Tmpfs',
                'PortBindings','StorageOpt','Annotations','LxcConf','VolumeDriver','CgroupParent',
                'Cgroup','UsernsMode','Isolation','ContainerIDFile','CpusetCpus','CpusetMems',
                'BlkioWeightDevice','BlkioDeviceReadBps','BlkioDeviceWriteBps','BlkioDeviceReadIOps','BlkioDeviceWriteIOps'):
        require(not host.get(key),'retained extra configuration: '+key)
    for key in ('Memory','MemoryReservation','MemorySwap','NanoCpus','CpuShares','CpuPeriod','CpuQuota',
                'CpuRealtimePeriod','CpuRealtimeRuntime','CpuCount','CpuPercent','BlkioWeight',
                'IOMaximumIOps','IOMaximumBandwidth','OomScoreAdj'):
        require(host.get(key,0)==0,'retained resource override: '+key)
    for key in ('MemorySwappiness','PidsLimit'):
        require(host.get(key) is None,'retained resource override: '+key)
    for key in ('Init','OomKillDisable','ReadonlyRootfs','PublishAllPorts','Privileged','AutoRemove'):
        require(host.get(key) in (None,False),'retained host flag differs: '+key)
    require(host.get('Runtime')==daemon['runtime'],'retained runtime differs')
    require(host.get('CgroupnsMode')==daemon['cgroupns'],'retained namespace differs: CgroupnsMode')
    require(host.get('NetworkMode')=='none','retained network differs')
    for key in ('PidMode','UTSMode'):
        require(not host.get(key),'retained namespace differs: '+key)
    require(host.get('IpcMode') in ('private',''),'retained IPC differs')
    restart=host.get('RestartPolicy') or {}
    require(restart.get('Name','no') in ('no','') and restart.get('MaximumRetryCount',0)==0,
            'retained restart policy differs')


def verify_control_resume_container(p, plan_path, attempt_no, observed, image=None, daemon=None):
    """Bind retained effective configuration to canonical command and image defaults."""
    require(image is not None and image.get('Id') == p['image_sha256'],
            'pinned image configuration required')
    command=docker_command(p,plan_path,attempt_no)
    expected=[]
    for index,value in enumerate(command):
        if value!='--mount':continue
        parts=dict((item.split('=',1) if '=' in item else (item,True))
                   for item in command[index+1].split(','))
        expected.append((parts['src'],parts['dst'],'readonly' not in parts))
    mounts=observed.get('Mounts',[])
    actual=[(m.get('Source'),m.get('Destination'),m.get('RW')) for m in mounts]
    require(len(actual)==len(expected) and sorted(actual)==sorted(expected)
            and all(m.get('Type')=='bind' and m.get('Propagation','rprivate')=='rprivate' for m in mounts),
            'control restart retained mounts differ')
    cfg=observed.get('Config',{}); host=observed.get('HostConfig',{}); defaults=image.get('Config',{})
    verify_effective_policy(observed,image,p['environment'],daemon=daemon)
    require(observed.get('Image') == image['Id'] and
            cfg.get('Entrypoint')==['python3'] and
            cfg.get('Cmd')==['-P','/workspace/r3_formal_driver.py','--plan',str(plan_path),'--attempt',str(attempt_no)] and
            host.get('NetworkMode')=='none' and host.get('Privileged') is False and
            host.get('AutoRemove') is False, 'retained identity/isolation differs')
    wanted_env=environment_map(defaults.get('Env') or [])
    wanted_env.update(p['environment'])
    require(environment_map(cfg.get('Env')) == wanted_env, 'retained environment differs')
    for key in ('User','WorkingDir','StopSignal'):
        require((cfg.get(key) or '') == (defaults.get(key) or ''), 'retained image default differs: '+key)
    for key in ('CapAdd','CapDrop','SecurityOpt','DeviceRequests','DeviceCgroupRules','GroupAdd',
                'Binds','VolumesFrom','Links','ExtraHosts','Dns','DnsSearch','Sysctls','Tmpfs'):
        require(not host.get(key), 'retained extra configuration: '+key)
    require(host.get('ShmSize') == 64 * 1024**3, 'retained shared memory differs')
    limits=host.get('Ulimits') or []
    require(len(limits)==2 and {x.get('Name'):(x.get('Soft'),x.get('Hard')) for x in limits} ==
            {'memlock':(-1,-1),'stack':(67108864,67108864)}, 'retained ulimits differ')
    devices=host.get('Devices') or []
    wanted={'/dev/'+x for x in ('davinci_manager','devmm_svm','hisi_hdc',f'davinci{p["chip"]}')}
    require(len(devices)==4 and {(x.get('PathOnHost'),x.get('PathInContainer'),x.get('CgroupPermissions'))
            for x in devices} == {(x,x,'rwm') for x in wanted}, 'retained device configuration differs')
    for key in ('PidMode','UTSMode'):
        allowed=('',)
        require((host.get(key) or '') in allowed, 'retained namespace differs: '+key)
    require(host.get('IpcMode') in ('private',''), 'retained IPC differs')
    for key in ('ReadonlyRootfs','PublishAllPorts'):
        require(not host.get(key), 'retained host flag differs: '+key)
    require((host.get('RestartPolicy') or {}).get('Name','no') in ('no',''), 'retained restart policy differs')


def verify_retained_receipts(attempt, pin, observed, command):
    launch=load(attempt/'LAUNCH_RECEIPT.json')
    spec=load(attempt/'LAUNCH_SPEC.json')
    require(launch.get('id') == observed.get('Id') and launch.get('image') == observed.get('Image')
            and launch.get('plan_sha256') == pin, 'retained launch receipt identity differs')
    require(spec.get('plan_sha256') == pin and spec.get('command') == command,
            'retained complete command differs')


def supervisor(path, pin, attempt_no):
    p = verify(path, pin)
    require(socket.gethostname() == 'k8s-node1', 'must run on host npu / 175')
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE], text=True))[0]
    require(image.get('Id') == IMAGE, 'actual image digest mismatch')
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
            resource = source_module(p['adapter'], 'resource_adapter')
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
        verify_retained_receipts(attempt, pin, d, docker_command(p,path,attempt_no))
        verify_control_resume_container(p,path,attempt_no,d,image)
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
