#!/usr/bin/env python3
"""Prepare and guard launch of an explicit immutable E34 queue on 175."""
import argparse
import fcntl
import importlib.util
import json
import hashlib
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def module(path):
    spec = importlib.util.spec_from_file_location('frozen_jeval_queue', path)
    q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q)
    return q


def shell_wrapper(command, out):
    return ('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n' + shlex.join(command)
            + ' >> ' + shlex.quote(str(out / 'run.log')) + ' 2>&1\nrc=$?\n'
            + 'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '
            + shlex.quote(str(out / 'EXIT')) + '\nexit "$rc"\n')


def handover_snapshot(q, path, config):
    prior = q.load(path)
    q.frozen(prior['files'])
    receipt_path = Path(prior['out']) / 'LAUNCH_RECEIPT.json'
    receipt = q.load(receipt_path)
    spec_path = prior['preparation_files']['container_spec']
    d = q.inspect(prior['container'])
    q.binding(d, q.load(spec_path), receipt)
    q.require(d['State']['Status'] == 'exited' and not q.chip_access(d), 'Prior controller must be stopped and CPU-only')
    q.require(receipt['plan_sha256'] == q.sha(path) and receipt['wrapper_sha256'] == q.sha(prior['preparation_files']['wrapper']), 'Prior controller receipt binding')
    c = q.load(config)
    entries = [e for e in prior['entries'] if e['key'] == c['key']]
    q.require(len(entries) == 1 and entries[0]['config'] == str(config) and entries[0]['config_sha256'] == q.sha(config), 'Prior configuration differs')
    adopted, files = {}, [path, receipt_path, Path(spec_path), Path(prior['preparation_files']['wrapper'])]
    for role in ['inference', 'finish']:
        out = config.parent if role == 'inference' else Path(str(config.parent) + '_finish')
        name = c['container'] + ('' if role == 'inference' else '-finish')
        rp = out / 'LAUNCH_RECEIPT.json'
        model = q.inspect(name)
        if model is None and not rp.exists():
            continue
        q.require(model is not None and rp.exists(), 'Incomplete adopted role identity')
        r = q.load(rp)
        labels = model['Config'].get('Labels') or {}
        label_hash = q.role_label_hash(path, c['key'], role)
        q.require(r['container_id'] == model['Id'] and r['config_sha256'] == q.sha(config)
                  and r['wrapper_sha256'] == q.sha(out / 'run.sh')
                  and labels.get('nga.jeval.queue') == label_hash and labels.get('nga.jeval.role') == role
                  and labels.get('nga.jeval.key') == c['key'], 'Adopted role receipt/labels differ')
        adopted[role] = dict(container_id=model['Id'], receipt_sha256=q.sha(rp), label_hash=label_hash)
        files += [rp, out / 'run.sh']
    q.require('inference' in adopted, 'Handover requires established inference')
    return dict(plan=str(path), plan_sha256=q.sha(path), receipt_sha256=q.sha(receipt_path),
                container_id=d['Id'], finished_at=d['State']['FinishedAt'], adopted={c['key']: adopted}), files


def prepare(source, prereg, config, out, name, handover_plan=None):
    q = module(source / 'jeval_reference_queue.py')
    q.require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 Docker only')
    q.require(not out.exists(), 'Preparation path already exists')
    c = q.load(config)
    q.require(c['key'] == 'nimble' and c['mode'] == 'inference' and c['physical_chip'] == 1, 'Nimble-only chip1 scope')
    q.require(c['image'] == q.IMAGE, 'Immutable image')
    q.require(q.inspect(name) is None, 'Queue container already exists')
    handover, handover_files = (handover_snapshot(q, handover_plan, config) if handover_plan else (None, []))
    if not handover:
        q.require(q.inspect(c['container']) is None and not (config.parent / 'LAUNCH_RECEIPT.json').exists(), 'Formal model already launched')
    q.require(q.load(config.parent / 'PARENT_REVIEW.json')['approved_config_sha256'] == q.sha(config), 'Explicit formal approval required')
    out.mkdir()
    hard = out / 'nimble_hardened'
    hard.mkdir()
    for filename in ['jeval_reference_queue.py', 'prepare_jeval_reference_queue.py', 'audit_jeval_inference_hardened.py', 'test_jeval_reference_queue.py']:
        shutil.copy2(source / filename, out / filename)
    shutil.copy2(prereg, out / 'PREREGISTRATION.md')
    frozen_q = module(out / 'jeval_reference_queue.py')
    cp = out / 'plan.json'
    (out / 'run.sh').write_text(shell_wrapper(['python3', '-P', str(out / 'jeval_reference_queue.py'), '--plan', str(cp)], out))
    (hard / 'run.sh').write_text(shell_wrapper(['python3', '-P', str(out / 'jeval_reference_queue.py'), '--audit-config', str(config), '--auditor', str(out / 'audit_jeval_inference_hardened.py'), '--audit-out', str(hard)], hard))
    for filename, flag in [('LAUNCH_EXACT.sh', '--launch'), ('RESUME_EXACT.sh', '--resume')]:
        (out / filename).write_text('#!/usr/bin/env bash\nset -e\n' + shlex.join(['python3', '-I', str(out / 'prepare_jeval_reference_queue.py'), flag, str(cp)]) + '\n')
    spec = {'Image': q.IMAGE, 'Cmd': [str(out / 'run.sh')], 'Entrypoint': ['bash'], 'Env': q.image_environment(),
            'Labels': {'nga.jeval.queue.name': name},
            'HostConfig': {'Binds': ['/mnt/cephfs:/mnt/cephfs', '/var/run/docker.sock:/var/run/docker.sock'], 'Devices': [], 'NetworkMode': 'none', 'ShmSize': 67108864}}
    q.atomic(out / 'CONTAINER_SPEC.json', spec)
    query_env = dict(x.split('=', 1) for x in q.image_environment())
    query_env['LD_LIBRARY_PATH'] = '/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common'
    query_spec = dict(Image=q.IMAGE, Cmd=['-P', str(out / 'jeval_reference_queue.py'), '--process-query', '{request}'],
                      Entrypoint=['python3'], Env=[k + '=' + v for k, v in query_env.items()], Labels={},
                      HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs', '/usr/local/sbin:/usr/local/sbin:ro',
                          '/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro', '/etc/ascend_install.info:/etc/ascend_install.info:ro'],
                          Devices=[dict(PathOnHost=p, PathInContainer=p, CgroupPermissions='rwm')
                              for p in ['/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', '/dev/davinci1']],
                          NetworkMode='none', PidMode='host', ShmSize=67108864))
    q.atomic(out / 'PROCESS_QUERY_SPEC.json', query_spec)
    entry = {'key': 'nimble', 'config': str(config), 'config_sha256': q.sha(config),
             'hardened': {'auditor': str(out / 'audit_jeval_inference_hardened.py'), 'wrapper': str(hard / 'run.sh'), 'out': str(hard), 'container': name + '-hardened'}}
    prep = dict(wrapper=str(out / 'run.sh'), launch=str(out / 'LAUNCH_EXACT.sh'), resume=str(out / 'RESUME_EXACT.sh'), preregistration=str(out / 'PREREGISTRATION.md'), container_spec=str(out / 'CONTAINER_SPEC.json'), process_query_spec=str(out / 'PROCESS_QUERY_SPEC.json'))
    paths = [p for p in out.rglob('*') if p.is_file()]
    paths += [config, config.parent / 'PARENT_REVIEW.json', config.parent / 'NPU_SPEC.json', config.parent / 'run.sh']
    paths += handover_files
    plan = dict(schema=1, out=str(out), container=name, image=q.IMAGE, allocation=q.ALLOCATION, preparation_files=prep, entries=[entry], files={str(p): q.sha(p) for p in paths})
    if handover:
        plan['handover'] = handover
    q.atomic(cp, plan)
    for p in out.rglob('*.py'):
        compile(p.read_bytes(), str(p), 'exec')
    for p in out.rglob('*.sh'):
        subprocess.run(['bash', '-n', str(p)], check=True)
    # Read-only dry admission: simulate only the absent queue approval, never write it.
    actual_load = frozen_q.load
    def reviewed_load(path):
        if Path(path) == out / 'PARENT_REVIEW.json':
            return {'approved_plan_sha256': frozen_q.sha(cp)}
        return actual_load(path)
    frozen_q.load = reviewed_load
    queue = frozen_q.Queue(cp)
    queue.check_entry(queue.configs[0], entry)
    q.atomic(out / 'PREPARATION_AUDIT.json', dict(plan_sha256=q.sha(cp), config_sha256=q.sha(config), frozen_files=len(plan['files']), generated_python_compiled=True, generated_shell_syntax=True, dry_entry_admission=True, queue_approval_written=False, launched=False, utc=q.utc()))
    print(json.dumps({'plan': str(cp), 'plan_sha256': q.sha(cp), 'frozen_files': len(plan['files']), 'status': 'PREPARED_NOT_LAUNCHED'}))


def launch(path, resume=False):
    out = path.parent
    q = module(out / 'jeval_reference_queue.py')
    q.require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 Docker only')
    with (out / 'launch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        plan = q.load(path)
        ph = q.sha(path)
        q.require(q.load(out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Queue approval differs')
        q.frozen(plan['files'])
        q.require(not any((out / n).exists() for n in ['QUEUE_COMPLETE.json', 'FAILURE.json']), 'Terminal evidence retained; new generation/review required')
        exit_path = out / 'EXIT'
        spec = q.load(plan['preparation_files']['container_spec'])
        expected = dict(plan_sha256=ph, spec_sha256=q.sha(plan['preparation_files']['container_spec']))
        intent_path = out / 'LAUNCH_INTENT.json'
        receipt_path = out / 'LAUNCH_RECEIPT.json'
        d = q.inspect(plan['container'])
        if d is None:
            q.require(not resume and not receipt_path.exists() and not exit_path.exists(), 'Missing retained container or terminal evidence')
            if intent_path.exists():
                q.require(q.load(intent_path) == expected, 'Launch intent changed')
            else:
                q.atomic(intent_path, expected)
            q.docker('POST', '/containers/create?name=' + plan['container'], spec)
            d = q.inspect(plan['container'])
        q.binding(d, spec)
        if receipt_path.exists():
            receipt = q.load(receipt_path)
            q.binding(d, spec, receipt)
            q.require(receipt['plan_sha256'] == ph and receipt['wrapper_sha256'] == q.sha(plan['preparation_files']['wrapper']), 'Queue receipt differs')
        else:
            q.require(d['State']['Status'] == 'created' and intent_path.exists() and q.load(intent_path) == expected, 'Unknown container or receipt gap')
            receipt = dict(container_id=d['Id'], image=q.IMAGE, command=spec['Cmd'], entrypoint=spec['Entrypoint'], plan_sha256=ph, wrapper_sha256=q.sha(plan['preparation_files']['wrapper']))
            q.atomic(receipt_path, receipt)
        status = d['State']['Status']
        if status == 'running':
            q.require(not exit_path.exists(), 'Running controller has stale EXIT')
            print(json.dumps({'container_id': d['Id'], 'status': 'ALREADY_RUNNING'}))
            return
        q.require(status == 'created' or (resume and status == 'exited' and d['State']['ExitCode'] != 0), 'No interrupted controller to resume')
        if status == 'exited':
            approved = q.load(out / 'RESUME_REVIEW.json')
            q.require(approved['approved_plan_sha256'] == ph and approved['container_id'] == d['Id'] and approved['finished_at'] == d['State']['FinishedAt'], 'Explicit interrupted-generation resume review required')
            token = hashlib.sha256((d['Id'] + '\n' + d['State']['FinishedAt']).encode()).hexdigest()
            archive = out / 'resume_history' / token
            prior_exit = archive / 'EXIT'
            evidence = exit_path if exit_path.exists() else prior_exit
            if evidence.exists():
                match = re.fullmatch(r'rc=([0-9]+) utc=\S+\n?', evidence.read_text())
                q.require(match and int(match[1]) == d['State']['ExitCode'] != 0
                          and approved.get('exit_sha256') == q.sha(evidence), 'Interrupted EXIT review differs')
                archive.mkdir(parents=True, exist_ok=True)
                if prior_exit.exists():
                    q.require(q.sha(prior_exit) == approved['exit_sha256'], 'Archived EXIT changed')
                else:
                    exit_path.replace(prior_exit)
                if exit_path.exists():
                    exit_path.unlink()
            else:
                q.require(approved.get('exit_sha256') is None, 'Reviewed EXIT missing')
        else:
            q.require(not exit_path.exists(), 'Created controller has terminal evidence')
        q.docker('POST', '/containers/' + d['Id'] + '/start')
        print(json.dumps({'container_id': d['Id'], 'status': 'STARTED'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path)
    p.add_argument('--preregistration', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--name')
    p.add_argument('--handover-plan', type=Path)
    p.add_argument('--launch', type=Path)
    p.add_argument('--resume', type=Path)
    a = p.parse_args()
    if a.launch or a.resume:
        launch(a.launch or a.resume, bool(a.resume))
    else:
        prepare(a.source.resolve(), a.preregistration.resolve(), a.config.resolve(), a.out.resolve(), a.name,
                a.handover_plan.resolve() if a.handover_plan else None)
