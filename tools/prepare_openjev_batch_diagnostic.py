#!/usr/bin/env python3
"""E37 immutable preparation and guarded retained launch on 175.

Does not release resources or grant E33/E36 admission. Preparation is read-only
outside its new generation. Source config retains its historical physical chip;
only the diagnostic specification selects the physical chip, native logical 0.
"""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
ALLOCATION = ROOT.parent / 'CHIP-ALLOCATION.json'
ALLOWED_CHIPS = (0, 1, 2, 3, 4, 5)  # 6/7 remain reserved to other work.
NAMES = ['openjev_batch_diagnostic.py', 'openjev_candidate_chunks.py',
         'prepare_openjev_batch_diagnostic.py', 'test_openjev_batch_diagnostic.py',
         'test_prepare_openjev_batch_diagnostic.py', 'jeval_reference_queue.py']


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def helper(folder):
    return module(folder / 'jeval_reference_queue.py', 'e37_resource_helpers')


def require(value, message):
    if not value:
        raise ValueError(message)


def docker_host(q):
    require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 Docker only')


def host(q):
    docker_host(q)
    require(Path('/proc/1/root/proc').exists() and not Path('/.dockerenv').exists(),
            'Launcher must run on host for physical occupancy check')


def process_query(output, chip):
    lines = [x.strip() for x in output.splitlines() if x.strip()]
    require(len(lines) >= 4 and re.fullmatch(r'NPU ID\s*:\s*' + str(chip), lines[0])
            and re.fullmatch(r'Chip Count\s*:\s*1', lines[1])
            and re.fullmatch(r'Chip ID\s*:\s*0', lines[-1]), 'Unknown npu-smi header')
    require(lines[2:-1] == ['No process in device.'], 'Physical chip occupied or unknown process output')


def free_now(q, chip, ignore=None):
    for item in q.docker('GET', '/containers/json'):
        if item['Id'] != ignore:
            require(not q.chip_access(q.inspect(item['Id']), chip), 'Live Docker resource conflict')
    result = subprocess.run(['/usr/local/sbin/npu-smi', 'info', '-t', 'proc-mem', '-i', str(chip)],
                            capture_output=True, text=True, check=True, timeout=20)
    require(not result.stderr.strip(), 'npu-smi emitted stderr; occupancy is not certified')
    process_query(result.stdout, chip)


def allocation_check(a, chip, run, allow_owned=False):
    owners = [x for x in a['allocation'] if x['chip'] == chip]
    free = [x for x in a['free'] if x['chip'] == chip]
    require((not owners and len(free) == 1) or
            (allow_owned and len(owners) == 1 and owners[0]['run'] == run and not free),
            'Chip is neither explicitly free nor exact retained owner')
    return bool(owners)


def spec_for(source_spec, chip, out, name):
    require(type(chip) is int and chip in ALLOWED_CHIPS, 'E37 allowed physical chips are 0 through 5; chips 6/7 excluded')
    s = copy.deepcopy(source_spec)
    devices = s['HostConfig']['Devices']
    selected = [x for x in devices if re.fullmatch(r'/dev/davinci\d+', x['PathOnHost'])]
    require(len(selected) == 1, 'Source must expose exactly one physical chip')
    selected[0]['PathOnHost'] = '/dev/davinci' + str(chip)
    selected[0]['PathInContainer'] = '/dev/davinci' + str(chip)
    require(selected[0]['CgroupPermissions'] == 'rwm', 'Native device permissions differ')
    env = dict(x.split('=', 1) for x in s['Env'])
    require(env.get('ASCEND_RT_VISIBLE_DEVICES') == '0', 'Native logical device zero required')
    require(not any(s['HostConfig'].get(k) for k in ['Privileged', 'DeviceRequests', 'DeviceCgroupRules', 'Mounts']), 'Unsafe source device exposure')
    s['Cmd'] = ['bash', str(out / 'run.sh')]
    s['Labels'] = {'nga.e37.name': name}
    return s


def wrapper(out):
    command = ['python3', '-P', str(out / 'openjev_batch_diagnostic.py'), '--plan', str(out / 'plan.json')]
    return ('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n' + shlex.join(command) +
            ' >> ' + shlex.quote(str(out / 'run.log')) + ' 2>&1\nrc=$?\n' +
            'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > ' +
            shlex.quote(str(out / 'EXIT')) + '\nexit "$rc"\n')


def source_evidence(q, config, e36_path):
    c = q.load(config)
    require(c['family'] == 'openjev' and c['mode'] == 'probe' and c['image'] == q.IMAGE, 'Accepted Open-Jev probe required')
    q.frozen(c['files'])
    driver = module(Path(c['out']) / 'jeval_reference_inference.py', 'e37_native_source')
    driver.sha = q.sha  # Same SHA256 implementation; CPU heartbeat counts dependency checks.
    eligibility = driver.verify_files(c)
    review = config.parent / 'PROBE_REVIEW.json'
    term = config.parent / 'COMPLETE.json'
    require(q.load(review)['approved_probe_config_sha256'] == q.sha(config)
            and q.load(review)['approved_probe_sha256'] == q.sha(config.parent / 'PROBE.json'), 'Source probe review changed')
    t = q.load(term)
    require(t['rc'] == 0 and t['progress'] == t['total'] == 4
            and t['config_sha256'] == q.sha(config)
            and t['outputs']['PROBE.json'] == q.sha(config.parent / 'PROBE.json'), 'Source probe terminal differs')
    paths = [config, review, term, config.parent / 'PROBE.json', config.parent / 'EXIT',
             config.parent / 'LAUNCH_RECEIPT.json', config.parent / 'NPU_SPEC.json']
    for plan_path, receipt_config in [(config, True), (e36_path, False)]:
        plan = q.load(plan_path); out = Path(plan['out']); receipt = q.load(out / 'LAUNCH_RECEIPT.json')
        d = q.inspect(plan['container']); spec = q.load(out / 'NPU_SPEC.json'); spec.setdefault('Labels', {})
        q.binding(d, spec)
        require(d['Id'] == receipt['container_id'] and d['State']['Status'] == 'exited'
                and d['State']['ExitCode'] == 0, 'Historical run actual exit differs')
        require(receipt['wrapper_sha256'] == q.sha(out / 'run.sh')
                and receipt['config_sha256' if receipt_config else 'plan_sha256'] == q.sha(plan_path), 'Historical receipt differs')
        require(re.fullmatch(r'rc=0 utc=\S+\n?', (out / 'EXIT').read_text()), 'Historical wrapper failed')
    ep = q.load(e36_path); q.frozen(ep['files']); eo = Path(ep['out']); et = q.load(eo / 'COMPLETE.json')
    require(ep['source_config'] == str(config) and ep['source_config_sha256'] == q.sha(config), 'E36 source differs')
    require(et['rc'] == 0 and et['plan_sha256'] == q.sha(e36_path)
            and et['progress'] == et['total'] == 20, 'E36 execution incomplete')
    er = q.load(eo / 'report.json')
    require(er['candidate_batch_admission'] is False and et['outputs']['report.json'] == q.sha(eo / 'report.json'), 'E36 failure evidence changed')
    paths += [e36_path, eo / 'COMPLETE.json', eo / 'report.json', eo / 'EXIT', eo / 'LAUNCH_RECEIPT.json', eo / 'NPU_SPEC.json']
    return c, eligibility, paths, ep['files']


def _prepare(source, prereg, config, e36_path, out, name, chip, request_path, helper_override=None):
    q = helper_override or helper(source); docker_host(q)
    require(out.parent == ROOT and not out.exists(), 'Use new direct reference_inference generation')
    require(re.fullmatch(r'nga-e37-[A-Za-z0-9_.-]+', name), 'Invalid E37 container name')
    require(q.inspect(name) is None, 'Container already exists')
    c, eligibility, historical, old_files = source_evidence(q, config, e36_path)
    diagnostic = module(source / 'openjev_batch_diagnostic.py', 'e37_diagnostic')
    selection = diagnostic.select(eligibility)
    out.mkdir()
    q.atomic(out / 'PREPARATION_IDENTITY.json', dict(request=str(request_path), request_sha256=q.sha(request_path)))
    for name_ in NAMES:
        shutil.copy2(source / name_, out / name_)
    shutil.copy2(prereg, out / 'PREREGISTRATION.md')
    (out / 'run.sh').write_text(wrapper(out))
    for script, flag in [('LAUNCH_EXACT.sh', '--launch'), ('RESUME_EXACT.sh', '--resume')]:
        (out / script).write_text('#!/usr/bin/env bash\nset -e\n' + shlex.join([
            'python3', '-I', str(out / 'prepare_openjev_batch_diagnostic.py'), flag, str(out / 'plan.json')]) + '\n')
    spec = spec_for(q.load(config.parent / 'NPU_SPEC.json'), chip, out, name)
    q.atomic(out / 'NPU_SPEC.json', spec)
    plan = dict(schema=1, image=q.IMAGE, chunk_rows=8, out=str(out), source_config=str(config),
                source_config_sha256=q.sha(config), source_physical_chip=c['physical_chip'],
                physical_chip=chip, logical_device='npu:0', container=name, selection=selection,
                preregistration=str(out / 'PREREGISTRATION.md'), wrapper=str(out / 'run.sh'),
                launch=str(out / 'LAUNCH_EXACT.sh'), resume=str(out / 'RESUME_EXACT.sh'),
                container_spec=str(out / 'NPU_SPEC.json'), allocation=str(ALLOCATION),
                e36_plan=str(e36_path), candidate_batch_admission=False,
                eligibility_sha256=q.sha(c['eligibility_report']), preparation_request=str(request_path),
                preparation_request_sha256=q.sha(request_path), files={**old_files, **c['files']})
    for p in historical + [p for p in out.iterdir() if p.is_file()]:
        plan['files'][str(p)] = q.sha(p)
    plan['files'].update(q.load(request_path)['files'])
    plan['files'][str(request_path)] = q.sha(request_path)
    q.atomic(out / 'plan.json', plan)
    for p in out.glob('*.py'): compile(p.read_bytes(), str(p), 'exec')
    for p in out.glob('*.sh'): subprocess.run(['bash', '-n', str(p)], check=True)
    q.atomic(out / 'PREPARATION_AUDIT.json', dict(plan_sha256=q.sha(out / 'plan.json'),
             files=len(plan['files']), python_compiled=True, shell_syntax=True,
             launched=False, resource_claimed=False, utc=q.utc()))
    return out / 'plan.json'


def small_frozen(q, files):
    """Host operations never silently hash model-sized files."""
    sizes = [Path(name).stat().st_size for name in files]
    require(all(size <= 8 * 2**20 for size in sizes) and sum(sizes) <= 64 * 2**20,
            'Control closure too large for short host verification')
    q.frozen(files)


def control_files(q, plan):
    """Exempt only the exact inherited data/native closure, checked by the driver.

    No caller-supplied skip list is accepted. The source configuration and E36
    plan themselves are small, approved controls; all their expected hashes must
    remain in the diagnostic plan even though host launch does not reread weights.
    """
    source = q.load(plan['source_config']); old = q.load(plan['e36_plan'])
    inherited = {**old['files'], **source['files']}
    require(all(plan['files'].get(name) == digest for name, digest in inherited.items()),
            'Runtime full dependency closure omitted or changed')
    request = Path(plan['preparation_request'])
    needed = set(plan['files']) - set(inherited)
    needed.update(str(Path(plan['out']) / name) for name in NAMES)
    needed.update(plan[k] for k in ['source_config', 'e36_plan', 'wrapper', 'launch',
                                    'resume', 'container_spec', 'preregistration'])
    needed.add(str(Path(plan['source_config']).parent / 'NPU_SPEC.json'))
    needed.add(str(request)); needed.update(q.load(request)['files'])
    require(needed <= set(plan['files']), 'Required control closure omitted')
    return {name: plan['files'][name] for name in needed}


def cpu_wrapper(out, command):
    return ('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n' + shlex.join(command) +
            ' >> ' + shlex.quote(str(out / 'run.log')) + ' 2>&1\nrc=$?\n' +
            'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > ' +
            shlex.quote(str(out / 'EXIT')) + '\nexit "$rc"\n')


def make_request(source, prereg, config, e36_path, out, name, chip, request_out, verify=None):
    """Short host action; no full model reads, resource claim or job launch."""
    q = helper(source); docker_host(q)
    require(request_out.parent == ROOT and not request_out.exists(), 'New CPU request generation required')
    if verify is None:
        host(q)
        require(type(chip) is int and chip in ALLOWED_CHIPS and out.parent == ROOT and not out.exists(), 'New target and allowed chip required')
        require(re.fullmatch(r'nga-e37-[A-Za-z0-9_.-]+', name), 'Invalid diagnostic name')
        with Path(str(ALLOCATION) + '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            allocation_check(q.load(ALLOCATION), chip, 'reference_inference/' + out.name)
            free_now(q, chip)
        task = 'prepare'; external = [config, e36_path, config.parent / 'NPU_SPEC.json']
    else:
        task = 'verify'; external = [verify]
        require(verify.parent.parent == ROOT, 'Verification target outside reference directory')
    cpu_name = 'nga-e37-cpu-' + request_out.name
    require(re.fullmatch(r'[A-Za-z0-9_.-]+', cpu_name), 'Invalid CPU container name')
    require(q.inspect(cpu_name) is None, 'CPU container already exists')
    # Bound the source inputs before hashing or copying anything.
    paths = [source / name_ for name_ in NAMES] + [prereg] + external
    require(all(p.stat().st_size <= 8 * 2**20 for p in paths), 'Request control file too large')
    request_out.mkdir()
    for name_ in NAMES: shutil.copy2(source / name_, request_out / name_)
    shutil.copy2(prereg, request_out / 'PREREGISTRATION.md')
    request_path = request_out / 'request.json'
    command = ['python3', '-P', str(request_out / 'prepare_openjev_batch_diagnostic.py'), '--cpu-task', str(request_path)]
    (request_out / 'run.sh').write_text(cpu_wrapper(request_out, command))
    for filename, flag in [('LAUNCH_EXACT.sh', '--cpu-launch'), ('RESUME_EXACT.sh', '--cpu-resume')]:
        (request_out / filename).write_text('#!/usr/bin/env bash\nset -e\n' + shlex.join([
            'python3', '-I', str(request_out / 'prepare_openjev_batch_diagnostic.py'), flag, str(request_path)]) + '\n')
    spec = dict(Image=q.IMAGE, Cmd=[str(request_out / 'run.sh')], Entrypoint=['bash'], Env=q.image_environment(),
                Labels={'nga.e37.cpu': cpu_name}, HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs',
                '/var/run/docker.sock:/var/run/docker.sock'], Devices=[], NetworkMode='none', ShmSize=67108864))
    q.atomic(request_out / 'CPU_SPEC.json', spec)
    req = dict(schema=1, task=task, out=str(request_out), container=cpu_name, image=q.IMAGE,
        source=str(request_out), preregistration=str(request_out / 'PREREGISTRATION.md'),
        wrapper=str(request_out / 'run.sh'), container_spec=str(request_out / 'CPU_SPEC.json'),
        target_plan=str(verify) if verify else str(out / 'plan.json'),
        config=str(config) if config else None, e36_plan=str(e36_path) if e36_path else None,
        target_out=str(out) if out else None, target_container=name, physical_chip=chip,
        resource_check_utc=q.utc() if task == 'prepare' else None,
        source_config_sha256=q.sha(config) if task == 'prepare' else None,
        e36_plan_sha256=q.sha(e36_path) if task == 'prepare' else None,
        files={str(p): q.sha(p) for p in external + [x for x in request_out.iterdir() if x.is_file()]})
    q.atomic(request_path, req)
    for p in request_out.glob('*.py'): compile(p.read_bytes(), str(p), 'exec')
    for p in request_out.glob('*.sh'): subprocess.run(['bash', '-n', str(p)], check=True)
    return request_path


def cpu_request_check(q, request_path):
    r = q.load(request_path); out = request_path.parent
    require(r['schema'] == 1 and r['image'] == q.IMAGE and r['out'] == str(out)
            and r['task'] in ('prepare', 'verify'), 'CPU request identity differs')
    needed = {str(out / name) for name in NAMES + ['run.sh', 'CPU_SPEC.json', 'LAUNCH_EXACT.sh', 'RESUME_EXACT.sh', 'PREREGISTRATION.md']}
    needed.update([r['config'], r['e36_plan'], str(Path(r['config']).parent / 'NPU_SPEC.json')] if r['task'] == 'prepare' else [r['target_plan']])
    require(needed <= set(r['files']), 'CPU executable/input closure omitted')
    small_frozen(q, r['files'])
    require(q.load(out / 'PARENT_REVIEW.json')['approved_request_sha256'] == q.sha(request_path), 'CPU request approval differs')
    spec = q.load(r['container_spec'])
    require(spec['Image'] == q.IMAGE and spec['Cmd'] == [r['wrapper']] and spec['Entrypoint'] == ['bash']
            and not q.devices(spec) and not any(spec['HostConfig'].get(k) for k in ['Privileged', 'DeviceRequests', 'DeviceCgroupRules', 'Mounts'])
            and spec['HostConfig']['NetworkMode'] == 'none'
            and sorted(spec['HostConfig']['Binds']) == ['/mnt/cephfs:/mnt/cephfs', '/var/run/docker.sock:/var/run/docker.sock'],
            'CPU request must expose no NPU or host devices')
    return r, spec


def cpu_binding(q, request_path, status=None):
    r, spec = cpu_request_check(q, request_path); out = request_path.parent
    d = q.inspect(r['container']); receipt = q.load(out / 'LAUNCH_RECEIPT.json')
    q.binding(d, spec, receipt)
    require(receipt['request_sha256'] == q.sha(request_path) and receipt['wrapper_sha256'] == q.sha(r['wrapper']), 'CPU launch receipt differs')
    if status: require(d['State']['Status'] == status, 'CPU actual state differs')
    return r, d


def cpu_launch(path, resume=False):
    q = helper(path.parent); docker_host(q); out = path.parent
    with (out / 'launch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        r, spec = cpu_request_check(q, path); rh = q.sha(path)
        small_frozen(q, r['files'])
        require(q.load(out / 'PARENT_REVIEW.json')['approved_request_sha256'] == rh, 'CPU request review required')
        require(not (out / 'COMPLETE.json').exists(), 'CPU terminal preserved')
        spec = q.load(r['container_spec']); intent = out / 'LAUNCH_INTENT.json'; receipt = out / 'LAUNCH_RECEIPT.json'
        expected = dict(request_sha256=rh, spec_sha256=q.sha(r['container_spec']))
        d = q.inspect(r['container'])
        if d is None:
            require(not resume and not receipt.exists() and not (out / 'EXIT').exists(), 'Missing retained CPU container')
            if intent.exists(): require(q.load(intent) == expected, 'CPU intent differs')
            else: q.atomic(intent, expected)
            q.docker('POST', '/containers/create?name=' + r['container'], spec); d = q.inspect(r['container'])
        q.binding(d, spec)
        if not receipt.exists():
            require(d['State']['Status'] == 'created' and intent.exists() and q.load(intent) == expected, 'Unknown CPU receipt gap')
            q.atomic(receipt, dict(container_id=d['Id'], image=q.IMAGE, command=spec['Cmd'], entrypoint=spec['Entrypoint'],
                                  request_sha256=rh, wrapper_sha256=q.sha(r['wrapper']), utc=q.utc()))
        cpu_binding(q, path)
        if d['State']['Status'] == 'running':
            require(not (out / 'EXIT').exists(), 'Running CPU with stale EXIT')
            return dict(container_id=d['Id'], status='ALREADY_RUNNING')
        require(d['State']['Status'] == 'created' or (resume and d['State']['Status'] == 'exited'), 'No interrupted CPU task')
        if d['State']['Status'] == 'exited': review_interruption(q, out, rh, d)
        else: require(not (out / 'EXIT').exists(), 'Created CPU task with EXIT')
        q.docker('POST', '/containers/' + d['Id'] + '/start')
        return dict(container_id=d['Id'], status='STARTED', devices=[])


def in_cpu_container(actual):
    import socket
    return Path('/.dockerenv').exists() and socket.gethostname() == actual['Config']['Hostname']


def cpu_task(path):
    """Long hashing/verification runs only in its retained CPU container."""
    q = helper(path.parent); docker_host(q); out = path.parent
    with (out / 'task.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r, actual = cpu_binding(q, path, 'running')
        require(in_cpu_container(actual), 'CPU task process identity differs')
        require(not (out / 'COMPLETE.json').exists(), 'CPU terminal preserved')
        rh = q.sha(path); state = dict(stage='verify_request', progress=0, total=None, chips=0)
        raw_sha = q.sha
        def counted_sha(filename):
            digest = raw_sha(filename); state['progress'] += 1
            return digest
        q.sha = counted_sha
        stop = threading.Event(); error = None; rc = 1; result = None
        def heartbeat():
            while not stop.wait(10):
                value = dict(utc=q.utc(), **state); q.atomic(out / 'STATUS.json', value)
                (out / 'digest.md').write_text(json.dumps(value) + '\n')
                with (out / 'heartbeat.log').open('a') as stream: stream.write(json.dumps(value) + '\n')
        thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
        try:
            state['stage'] = r['task'] + '_full_dependency_hashing'
            if r['task'] == 'prepare':
                target = Path(r['target_out']); target_plan = target / 'plan.json'
                require(q.sha(r['config']) == r['source_config_sha256'] and q.sha(r['e36_plan']) == r['e36_plan_sha256'], 'Requested source identity changed')
                identity = dict(request=str(path), request_sha256=rh)
                intent = out / 'TARGET_INTENT.json'
                if intent.exists(): require(q.load(intent) == identity, 'Preparation target intent changed')
                else:
                    require(not target.exists(), 'Unowned target directory exists')
                    q.atomic(intent, identity)
                if target.exists():
                    marker = target / 'PREPARATION_IDENTITY.json'
                    require((marker.exists() and q.load(marker) == identity) or not any(target.iterdir()), 'Foreign partial preparation directory')
                    require(not (target / 'LAUNCH_RECEIPT.json').exists() and q.inspect(r['target_container']) is None, 'Partial preparation target already launched')
                    if target_plan.exists() and (target / 'PREPARATION_AUDIT.json').exists():
                        prior = q.load(target_plan)
                        require(prior['preparation_request_sha256'] == rh and prior['preparation_request'] == str(path)
                                and q.load(target / 'PREPARATION_AUDIT.json')['plan_sha256'] == q.sha(target_plan), 'Recovered preparation identity differs')
                        q.frozen(prior['files'])
                    else:
                        history = out / 'partial_preparations'; history.mkdir(exist_ok=True)
                        target.rename(history / str(time.time_ns()))
                if not target.exists():
                    target_plan = _prepare(Path(r['source']), Path(r['preregistration']), Path(r['config']),
                        Path(r['e36_plan']), target, r['target_container'], r['physical_chip'], path, helper_override=q)
                q.frozen(q.load(target_plan)['files'])
                result = dict(plan=str(target_plan), plan_sha256=q.sha(target_plan),
                    source_config_sha256=r['source_config_sha256'], e36_plan_sha256=r['e36_plan_sha256'],
                    full_closure_verified=True, launched=False, resource_claimed=False)
            else:
                require(r['files'][r['target_plan']] == q.sha(r['target_plan']), 'Verification plan changed')
                result = verify_complete(Path(r['target_plan']), helper_override=q)
            small_frozen(q, r['files']); require(q.sha(path) == rh, 'CPU request changed during execution')
            if (out / 'report.json').exists():
                require(q.load(out / 'report.json') == result, 'Existing CPU report differs; preserved')
            else:
                q.atomic(out / 'report.json', result)
            state.update(stage='completed', progress=1, total=1); rc = 0
        except BaseException as exc:
            error = type(exc).__name__ + ': ' + str(exc); state['stage'] = 'failed'; raise
        finally:
            stop.set(); thread.join(); q.sha = raw_sha
            q.atomic(out / 'COMPLETE.json', dict(rc=rc, error=error, request_sha256=rh,
                outputs={'report.json': q.sha(out / 'report.json')} if (out / 'report.json').exists() else {},
                utc=q.utc(), **state))


def preparation_binding(q, plan_path, plan):
    """Short host check of successful full-hash CPU evidence and small controls."""
    request = Path(plan['preparation_request'])
    require(q.sha(request) == plan['preparation_request_sha256'], 'Preparation request changed')
    r, d = cpu_binding(q, request, 'exited'); out = request.parent
    require(r['task'] == 'prepare' and r['target_plan'] == str(plan_path)
            and r['config'] == plan['source_config'] and r['e36_plan'] == plan['e36_plan']
            and r['physical_chip'] == plan['physical_chip'] and r['target_container'] == plan['container'], 'Preparation target differs')
    require(d['State']['ExitCode'] == 0 and re.fullmatch(r'rc=0 utc=\S+\n?', (out / 'EXIT').read_text()), 'CPU preparation not successful')
    terminal = q.load(out / 'COMPLETE.json'); report = q.load(out / 'report.json')
    require(terminal['rc'] == 0 and terminal['stage'] == 'completed' and terminal['progress'] == terminal['total'] == 1
            and terminal['request_sha256'] == q.sha(request)
            and terminal['outputs'] == {'report.json': q.sha(out / 'report.json')}, 'CPU preparation terminal differs')
    require(report['plan'] == str(plan_path) and report['plan_sha256'] == q.sha(plan_path)
            and report['source_config_sha256'] == plan['source_config_sha256']
            and report['source_config_sha256'] == r['source_config_sha256']
            and report['e36_plan_sha256'] == r['e36_plan_sha256']
            and report['full_closure_verified'] is True and report['launched'] is False
            and report['resource_claimed'] is False, 'Preparation report differs')
    # Source identities are checked before their manifests are used to derive the
    # only files whose large reads are deferred to the already-frozen driver.
    require(q.sha(plan['source_config']) == r['source_config_sha256']
            and q.sha(plan['e36_plan']) == r['e36_plan_sha256'], 'Source manifests changed')
    small_frozen(q, control_files(q, plan))


def validate_items(q, plan, ph):
    """Reject altered/foreign receipts before launch; driver rechecks request identity."""
    folder = Path(plan['out']) / 'items'
    if not folder.exists(): return
    require(folder.is_dir() and not folder.is_symlink(), 'Items directory differs')
    diagnostic = module(Path(plan['out']) / 'openjev_batch_diagnostic.py', 'e37_resume_diagnostic')
    names = {}
    for item in plan['selection']['selected']:
        modes = ['original', 'noop', 'chunk8'] if item['role'] == 'boundary' else ['original', 'chunk8']
        tasks = [(mode, rep, False) for mode in modes for rep in range(2)]
        if item['role'] == 'boundary': tasks += [(mode, 0, True) for mode in ['original', 'chunk8']]
        for mode, rep, prof in tasks:
            name = f"{item['index']}_{mode}_{rep}" + ('_profiled' if prof else '') + '.json'
            names[name] = dict(plan_sha256=ph, index=item['index'], mode=mode, rep=rep, profiled=prof)
    for p in folder.iterdir():
        # Interrupted atomic publication's .json.tmp is preserved, never adopted.
        if p.name.endswith('.json.tmp'):
            require(p.name[:-4] in names and p.is_file() and not p.is_symlink(), 'Unknown partial receipt')
            continue
        require(p.name in names and p.is_file() and not p.is_symlink(), 'Unknown receipt')
        diagnostic.verify_receipt(q.load(p), names[p.name])


def review_interruption(q, out, ph, d):
    require(d['State']['Status'] == 'exited' and d['State']['ExitCode'] in (137, 143), 'Only reviewed signal interruption may resume')
    review = q.load(out / 'RESUME_REVIEW.json')
    require(review['approved_plan_sha256'] == ph and review['container_id'] == d['Id']
            and review['finished_at'] == d['State']['FinishedAt'], 'Resume generation review differs')
    token = hashlib.sha256((d['Id'] + '\n' + d['State']['FinishedAt']).encode()).hexdigest()
    archive = out / 'resume_history' / token; evidence = out / 'EXIT'
    if not evidence.exists(): evidence = archive / 'EXIT'
    if evidence.exists():
        match = re.fullmatch(r'rc=([0-9]+) utc=\S+\n?', evidence.read_text())
        require(match and int(match[1]) == d['State']['ExitCode'] and review.get('exit_sha256') == q.sha(evidence), 'Reviewed EXIT differs')
        archive.mkdir(parents=True, exist_ok=True)
        if evidence == out / 'EXIT':
            require(not (archive / 'EXIT').exists(), 'Ambiguous interruption archive')
            evidence.replace(archive / 'EXIT')
    else:
        require(review.get('exit_sha256') is None, 'Reviewed EXIT missing')
    # The driver uses a fixed .json.tmp path. Preserve interrupted publications
    # before it can reuse that name; completed item files remain byte-identical.
    folder = out / 'items'
    if folder.exists():
        for partial in folder.glob('*.json.tmp'):
            archive.mkdir(parents=True, exist_ok=True)
            saved = archive / partial.name
            require(not saved.exists(), 'Partial archive already exists')
            partial.replace(saved)


def launch(path, resume=False):
    out = path.parent; q = helper(out); host(q)
    with (out / 'launch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        p = q.load(path); ph = q.sha(path)
        require(p['out'] == str(out) and out.parent == ROOT and p['allocation'] == str(ALLOCATION), 'Run location differs')
        require(p['image'] == q.IMAGE and type(p['physical_chip']) is int and p['physical_chip'] in ALLOWED_CHIPS and p['candidate_batch_admission'] is False, 'Diagnostic protocol differs')
        require(q.load(out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Exact plan review required')
        preparation_binding(q, path, p)
        require(not any((out / n).exists() for n in ['COMPLETE.json', 'FAILURE.json', 'report.json']), 'Terminal/failure/report preserved; new review/generation required')
        validate_items(q, p, ph)
        spec = q.load(p['container_spec'])
        source_spec = q.load(Path(p['source_config']).parent / 'NPU_SPEC.json')
        require(spec == spec_for(source_spec, p['physical_chip'], out, p['container']), 'Device/source specification differs')
        expected = dict(plan_sha256=ph, spec_sha256=q.sha(p['container_spec']))
        intent = out / 'LAUNCH_INTENT.json'; receipt = out / 'LAUNCH_RECEIPT.json'
        with Path(str(ALLOCATION) + '.lock').open('w') as resource_lock:
            fcntl.flock(resource_lock, fcntl.LOCK_EX)
            a = q.load(ALLOCATION); run = 'reference_inference/' + out.name
            d = q.inspect(p['container'])
            owned = allocation_check(a, p['physical_chip'], run, allow_owned=True)
            if d is None:
                require(not owned and not resume and not receipt.exists() and not (out / 'EXIT').exists(), 'Missing retained container or prior EXIT')
                if intent.exists(): require(q.load(intent) == expected, 'Intent differs')
                else: q.atomic(intent, expected)
                free_now(q, p['physical_chip'])
                q.docker('POST', '/containers/create?name=' + p['container'], spec)
                d = q.inspect(p['container'])
            q.binding(d, spec)
            if receipt.exists():
                r = q.load(receipt); q.binding(d, spec, r)
                require(r['plan_sha256'] == ph and r['wrapper_sha256'] == q.sha(p['wrapper']), 'Receipt binding differs')
            else:
                require(d['State']['Status'] == 'created' and intent.exists() and q.load(intent) == expected, 'Foreign or receipt-gap container')
                q.atomic(receipt, dict(container_id=d['Id'], image=p['image'], command=spec['Cmd'],
                         entrypoint=spec['Entrypoint'], plan_sha256=ph, wrapper_sha256=q.sha(p['wrapper']), utc=q.utc()))
            status = d['State']['Status']
            if status == 'running':
                require(owned and not (out / 'EXIT').exists(), 'Running allocation/EXIT differs')
                return dict(container_id=d['Id'], status='ALREADY_RUNNING')
            require(status == 'created' or (resume and owned and status == 'exited'), 'No interrupted retained run')
            free_now(q, p['physical_chip'], ignore=d['Id'])
            if status == 'exited': review_interruption(q, out, ph, d)
            else: require(not (out / 'EXIT').exists(), 'Created run has EXIT')
            if not owned:
                a['free'] = [x for x in a['free'] if x['chip'] != p['physical_chip']]
                a['allocation'].append(dict(chip=p['physical_chip'], owner='E37 diagnostic', run=run,
                    claimed_utc=q.utc(), release_when='terminal, receipts, independent diagnostic review and actual exit'))
                q.atomic(ALLOCATION, a)
            q.docker('POST', '/containers/' + d['Id'] + '/start')
            return dict(container_id=d['Id'], status='STARTED', candidate_batch_admission=False)


def verify_complete(path, helper_override=None):
    """Read-only outcome verification; does not grant admission or release a chip."""
    out = path.parent; q = helper_override or helper(out); docker_host(q)
    p = q.load(path); ph = q.sha(path)
    require(p['out'] == str(out) and p['image'] == q.IMAGE, 'Completion plan identity')
    require(q.load(out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Plan approval differs')
    q.frozen(p['files'])
    receipt = q.load(out / 'LAUNCH_RECEIPT.json'); d = q.inspect(p['container'])
    q.binding(d, q.load(p['container_spec']), receipt)
    require(receipt['plan_sha256'] == ph and receipt['wrapper_sha256'] == q.sha(p['wrapper']), 'Completion receipt differs')
    require(d['State']['Status'] == 'exited' and d['State']['ExitCode'] == 0, 'Retained container not successful')
    require(re.fullmatch(r'rc=0 utc=\S+\n?', (out / 'EXIT').read_text()), 'Wrapper not successful')
    terminal = q.load(out / 'COMPLETE.json'); report = q.load(out / 'report.json')
    require(terminal['rc'] == 0 and terminal['stage'] == 'completed' and terminal['plan_sha256'] == ph,
            'Diagnostic terminal incomplete')
    require(set(terminal['outputs']) == {'SELECTION.json', 'report.json'}, 'Terminal output set differs')
    for name, digest in terminal['outputs'].items():
        require(q.sha(out / name) == digest, 'Terminal output changed')
    require(q.load(out / 'SELECTION.json') == p['selection'] == report['selection'], 'Selection changed')
    require(report['plan_sha256'] == ph and report['candidate_batch_admission'] is False
            and report['existing_e36_admission'] == 'failed; unchanged', 'Diagnostic admission changed')
    validate_items(q, p, ph)
    committed = {name: q.sha(out / name) for name in ['COMPLETE.json', 'report.json', 'SELECTION.json', 'EXIT', 'LAUNCH_RECEIPT.json']}
    before_items = {item.name: q.sha(item) for item in (out / 'items').iterdir()}
    diagnostic = module(out / 'openjev_batch_diagnostic.py', 'e37_complete_diagnostic')
    folder = out / 'items'; results = {}; expected = []
    for item in p['selection']['selected']:
        modes = ['original', 'noop', 'chunk8'] if item['role'] == 'boundary' else ['original', 'chunk8']
        tasks = [(mode, rep, False) for mode in modes for rep in range(2)]
        if item['role'] == 'boundary': tasks += [(mode, 0, True) for mode in ['original', 'chunk8']]
        for mode, rep, prof in tasks:
            name = f"{item['index']}_{mode}_{rep}" + ('_profiled' if prof else '')
            expected.append(name + '.json'); results[name] = q.load(folder / (name + '.json'))['payload']
    require(sorted(x.name for x in folder.iterdir()) == sorted(expected), 'Completed item set differs')
    require(terminal['progress'] == terminal['total'] == len(expected), 'Forward count differs')
    valid = True; comparisons = {}
    for item in p['selection']['selected']:
        prefix = str(item['index'])
        def pred(mode, rep=0, prof=False):
            return results[f'{prefix}_{mode}_{rep}' + ('_profiled' if prof else '')]['prediction']
        cell = dict(original_repeat=diagnostic.comparison(pred('original'), pred('original', 1)),
                    chunk_repeat=diagnostic.comparison(pred('chunk8'), pred('chunk8', 1)),
                    original_vs_chunk=diagnostic.comparison(pred('original'), pred('chunk8')))
        if item['role'] == 'boundary':
            cell.update(noop_repeat=diagnostic.comparison(pred('noop'), pred('noop', 1)),
                        original_vs_noop=diagnostic.comparison(pred('original'), pred('noop')),
                        original_hook_effect=diagnostic.comparison(pred('original'), pred('original', prof=True)),
                        chunk_hook_effect=diagnostic.comparison(pred('chunk8'), pred('chunk8', prof=True)))
            valid &= all(cell[k]['exact_prediction'] for k in ['original_repeat', 'noop_repeat',
                         'original_vs_noop', 'original_hook_effect', 'chunk_hook_effect'])
        comparisons[prefix] = cell
    require(comparisons == report['comparisons'] and report['diagnostic_valid'] == valid
            and report['paired_denominator'] == len(comparisons)
            and report['paired_decision_flips'] == sum(c['original_vs_chunk']['decision_changed'] for c in comparisons.values()),
            'Diagnostic comparison arithmetic differs')
    manifest = {name: q.sha(folder / name) for name in sorted(expected)}
    require(manifest == before_items and sorted(x.name for x in folder.iterdir()) == sorted(expected), 'Receipt set changed during verification')
    require(committed == {name: q.sha(out / name) for name in committed}, 'Completion evidence changed during verification')
    require(q.sha(path) == ph, 'Plan changed during verification')
    q.frozen(p['files'])
    return dict(plan_sha256=ph, container_id=d['Id'], actual_exit=0,
                terminal_sha256=q.sha(out / 'COMPLETE.json'), report_sha256=q.sha(out / 'report.json'),
                receipt_manifest=manifest, diagnostic_valid=valid, candidate_batch_admission=False,
                scope='Read-only artifact/comparison verification; no raw request retokenization, NPU parity approval or resource release')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ['source', 'preregistration', 'config', 'e36-plan', 'out', 'request-out', 'verify-plan',
                'launch', 'resume', 'verify-complete', 'cpu-launch', 'cpu-resume', 'cpu-task']:
        parser.add_argument('--' + key, type=Path)
    parser.add_argument('--name'); parser.add_argument('--chip', type=int, choices=ALLOWED_CHIPS)
    args = parser.parse_args()
    if args.cpu_task:
        cpu_task(args.cpu_task.resolve()); result = {'status': 'CPU_TASK_COMPLETED'}
    elif args.cpu_launch or args.cpu_resume:
        result = cpu_launch((args.cpu_launch or args.cpu_resume).resolve(), bool(args.cpu_resume))
    elif args.verify_complete:
        # Full verification belongs to a retained CPU job. Public entry requires
        # that execution identity; --verify-plan prepares that job instead.
        raise ValueError('Use --verify-plan with --request-out, then --cpu-launch; full verification must be detached')
    elif args.launch or args.resume:
        result = launch((args.launch or args.resume).resolve(), bool(args.resume))
    else:
        resolve = lambda x: x.resolve() if x else None
        result = {'request': str(make_request(resolve(args.source), resolve(args.preregistration),
            resolve(args.config), resolve(args.e36_plan), resolve(args.out), args.name, args.chip,
            resolve(args.request_out), resolve(args.verify_plan)))}
    print(json.dumps(result))
