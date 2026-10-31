#!/usr/bin/env python3
"""Consume a completed, pinned NPU restart contract; never grant scientific approval.

This validates execution receipts and recomputes the registered numerical decision.
It does not independently recompute tensor distances or authenticate a fabricated
receipt; independent exact-plan review and retained-container verification remain
separate obligations. No torch import, NPU access, or experiment mutation occurs.
"""
import hashlib
import math
import json
from pathlib import Path

CONTRACT_SHA256 = {
    'c3b67285436701d04da557c18ab813853debc354a3ea7cc4859d95ebf6aaf817',
    'b5a0da60a0351c47baa03eedea50d77495ee4cbc8b7550b116d91d21b473f25d',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    p = Path(path)
    require(p.is_absolute() and p.is_file() and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe resume evidence path')
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def identity(plan):
    return hashlib.sha256((json.dumps(dict(plan, review_sha256='PENDING'), indent=2, sort_keys=True)+'\n').encode()).hexdigest()


def recipe(command):
    command = list(command)
    # The bounded contract is seed 2; it validates the shared recipe for seeds 2/3.
    for key in ('--out', '--seed'):
        require(command.count(key) == 1, 'invalid training command')
        command[command.index(key)+1] = '<bound>'
    return command


def judge(loss_floor, weight_floor, resume_loss, resume_weight, controls):
    """Independent recomputation of the fixed v2/v3 numerical decision."""
    require(set(controls) == {'zero_moments','no_update'}, 'both corruption controls required')
    values = [loss_floor,weight_floor,resume_loss,resume_weight]
    for row in controls.values():
        values.extend((row['loss'],row['weight_relative_l2']))
    require(all(type(x) in (int,float) and math.isfinite(x) and x >= 0 for x in values), 'invalid resume distance')
    bars = {'loss':1.5*loss_floor+2.4e-7,'weight_relative_l2':1.5*weight_floor+1e-7}
    require(all(math.isfinite(x) for x in bars.values()), 'resume tolerance overflow')
    resumed = resume_loss <= bars['loss'] and resume_weight <= bars['weight_relative_l2']
    rejected = {k:r['loss'] > bars['loss'] or r['weight_relative_l2'] > bars['weight_relative_l2'] for k,r in controls.items()}
    return {'bars':bars,'resume_pass':resumed,'controls_rejected':rejected,'pass':resumed and all(rejected.values())}


def validate(path, pin, target):
    path = Path(path)
    plan = load(path)
    require(identity(plan) == pin, 'resume plan identity differs')
    root = path.parent
    require(plan.get('out') == str(root) and plan.get('validation_kind') == 'current_k1_resume_contract'
            and plan.get('schema') == 'r3-engineering-k1-plan-v1' and plan.get('seed') == 2
            and plan.get('test_read') is False and plan.get('scientific_acceptance') is False,
            'resume plan scope differs')
    files = dict(plan['files'])
    for filename, digest in files.items():
        require(sha(filename) == digest, 'resume input changed: '+filename)
    files[str(path)] = sha(path)

    def read(p, frozen=False):
        p = Path(p)
        digest = sha(p)
        if frozen:
            require(files.get(str(p)) == digest, 'resume input not bound: '+str(p))
        files[str(p)] = digest
        return load(p)

    require(plan['command'] == ['python3','-P','/workspace/r3_resume_contract.py','--out',str(root)], 'resume execution command differs')
    for key in ('model', 'train_file', 'image_sha256', 'environment'):
        require(plan.get(key) == target.get(key), 'resume configuration differs: '+key)
    contract_code = Path(plan['code'])/'r3_resume_contract.py'
    require(files.get(str(contract_code)) in CONTRACT_SHA256, 'unrecognized resume contract implementation')
    source = read(root/'SOURCE_PLAN.json', True)
    require(source.get('seed') == 2 and source.get('arm', 'k1') == 'k1'
            and recipe(source['command']) == recipe(target['command']), 'resume training recipe differs')
    for key in ('model', 'train_file', 'image_sha256', 'environment'):
        require(source.get(key) == target.get(key), 'checkpoint source configuration differs: '+key)
    for relative in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
        tested = str(Path(plan['code'])/relative)
        current = Path(target['code'])/relative
        require(files.get(tested) == sha(current), 'resume training code differs: '+relative)
        original = str(Path(source['code'])/relative)
        require(source['files'].get(original) == files[tested], 'checkpoint training code differs: '+relative)
    model = Path(target['model'])
    actual = {str(p):sha(p) for p in model.rglob('*') if p.is_file()}
    require(actual and actual == {p:h for p,h in files.items() if p.startswith(str(model)+'/')}, 'resume model inventory differs')
    require(all(source['files'].get(p) == h for p,h in actual.items()), 'checkpoint model differs')
    train = target['train_file']
    require(files.get(train) == source['files'].get(train) == sha(train), 'resume training data differs')
    config = read(root/'CONTRACT.json', True)
    expected = {'steps':20,'replicas':3,'split':10,'factor':1.5,'loss_slack':2.4e-7,
                'weight_relative_l2_slack':1e-7,'test_read':False,'scientific_acceptance':False}
    require(all(type(config.get(k)) is type(v) and config[k] == v for k,v in expected.items()), 'resume protocol differs')
    require(type(config.get('source_step')) is int and 20 <= config['source_step'] < 3096, 'resume source is not trained state')
    origin = read(root/'SOURCE.json', True)
    require(origin['step'] == config['source_step'] and origin['sha256'] == config['source_sha256']
            == files.get(str(root/'SOURCE.pt')) and origin['training'] == source['out'], 'resume checkpoint binding differs')
    files[origin['checkpoint']] = sha(origin['checkpoint'])
    require(files[origin['checkpoint']] == config['source_sha256'], 'original checkpoint changed')
    terminal = read(root/'TRAIN_EXIT.json')
    require(type(terminal.get('exit_code')) is int and terminal['exit_code'] == 0
            and type(terminal.get('attempt')) is int and terminal['attempt'] >= 1, 'resume run not successfully terminal')
    attempt = root/'attempts'/str(terminal['attempt'])
    require(read(attempt/'EXIT.json') == terminal, 'resume terminal records disagree')
    launch = read(attempt/'LAUNCH_RECEIPT.json')
    require(launch.get('plan_sha256') == pin and launch.get('image') == target['image_sha256']
            and isinstance(launch.get('id'),str) and len(launch['id']) == 64, 'resume launch identity differs')
    launch_spec = read(attempt/'LAUNCH_SPEC.json')
    cmd = launch_spec['command']
    require(launch_spec.get('plan_sha256') == pin and cmd[:3] == ['docker','run','-d']
            and '--rm' not in cmd and '--network=none' in cmd and '--pull=never' in cmd,
            'resume container launch policy differs')
    devices = [cmd[i+1] for i,x in enumerate(cmd) if x == '--device']
    require(set(devices) == {'/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc',f"/dev/davinci{plan['chip']}"}
            and len(devices) == 4, 'resume launch has no matching NPU device')
    env = [cmd[i+1] for i,x in enumerate(cmd) if x == '-e']
    require(sorted(env) == sorted(k+'='+v for k,v in plan['environment'].items()), 'resume launch environment differs')
    mounts = [cmd[i+1] for i,x in enumerate(cmd) if x == '--mount']
    required_mounts = [f"type=bind,src={plan['code']},dst=/workspace,readonly",
                       f"type=bind,src={plan['model']},dst={plan['model']},readonly",
                       f"type=bind,src={plan['train_file']},dst={plan['train_file']},readonly",
                       f"type=bind,src={root},dst={root}",
                       'type=bind,src=/usr/local/Ascend/driver,dst=/usr/local/Ascend/driver,readonly',
                       f"type=bind,src={plan['code']},dst=/mnt/cephfs/xingchao/experiments/jev/r3_code,readonly"]
    require(sorted(mounts) == sorted(required_mounts), 'resume launch mounts differ')
    require(cmd[-8:] == ['python3',target['image_sha256'],'-P','/workspace/r3_formal_driver.py',
                        '--plan',str(path),'--attempt',str(terminal['attempt'])], 'resume driver command differs')
    release = read(attempt/'RELEASE.json')
    require(release.get('schema') == 'r3-resource-release-v1' and release.get('run') == plan['run']
            and release.get('chip') == plan['chip'] and release.get('container_id') == launch['id']
            and release.get('container') == plan['container']+'-a'+str(terminal['attempt'])
            and type(release.get('exit_code')) is int and release['exit_code'] == 0
            and release.get('container_finished_at') and release.get('container_started_at')
            and release.get('released_utc'), 'resume release missing or inconsistent')
    done = read(attempt/'SUPERVISOR_DONE.json')
    require(type(done.get('exit_code')) is int and done['exit_code'] == 0, 'resume supervisor not complete')
    names = ['replica_a','replica_b','replica_c','resumed','resumed','zero_moments','no_update']
    for index, name in enumerate(names):
        receipt = read(root/f'STAGE-{index}.json')
        require(type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0
                and receipt.get('stage') == index and receipt.get('name') == name, 'resume stage incomplete')
    for name in set(names):
        for p in (root/name/'losses.jsonl', root/name/'ckpt'/f"step_{config['source_step']+20:06d}.pt"):
            files[str(p)] = sha(p)
    result = read(root/'CONTRACT_RESULT.json')
    require(result == read(root/'digest.json'), 'resume result and digest disagree')
    require(result.get('source_step') == config['source_step'] and result.get('source_sha256') == config['source_sha256']
            and result.get('test_read') is False and result.get('scientific_acceptance') is False, 'resume result scope differs')
    floors = result['replicas']
    require(isinstance(floors,list) and len(floors) == 3, 'three independent replica distances required')
    # Check every individual floor too: max() must not hide NaN or negative values.
    for row in floors:
        judge(row['loss'],row['weight_relative_l2'],0.,0.,result['controls'])
    verdict = judge(max(r['loss'] for r in floors),max(r['weight_relative_l2'] for r in floors),
                           result['resumed']['loss'],result['resumed']['weight_relative_l2'],result['controls'])
    require(verdict['pass'] is True and all(result.get(k) == v for k,v in verdict.items()), 'recomputed resume contract failed')
    return files
