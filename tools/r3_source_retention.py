"""Read-only proposed source-copy contract; never changes recovery admission.

Hashes bind bytes to a caller-pinned plan, not authorship or prelaunch timing.
This helper does not load tensors, prove training, or validate numerical recovery.
The existing r3_resume_evidence validator still requires the original checkpoint.
"""
import hashlib
import json
from pathlib import Path
import re

MODES = ('require_original', 'pinned_copy_proposal')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe source path')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def identity(plan):
    return hashlib.sha256((json.dumps(dict(plan, review_sha256='PENDING'),
                                     indent=2, sort_keys=True)+'\n').encode()).hexdigest()


def validate(plan_path, plan_pin, *, mode='require_original'):
    """Return diagnostic evidence only. Missing original needs explicit proposal mode.

    No integration with the execution/readiness validators is performed. An
    absent path does not establish why or when it disappeared. A trusted reviewer
    must separately establish execution history and accept a new evidence policy.
    """
    require(mode in MODES, 'unknown source-retention mode')
    require(isinstance(plan_pin, str) and re.fullmatch('[0-9a-f]{64}', plan_pin),
            'external canonical plan pin required')
    path = safe(plan_path)
    plan_bytes = path.read_bytes()
    plan = json.loads(plan_bytes)
    require(identity(plan) == plan_pin, 'canonical plan identity differs')
    root = path.parent
    require(plan.get('out') == str(root) and plan.get('seed') == 2 and
            type(plan.get('seed')) is int and
            plan.get('schema') == 'r3-engineering-k1-plan-v1' and
            plan.get('validation_kind') == 'current_k1_resume_contract' and
            plan.get('scientific_acceptance') is False and plan.get('test_read') is False,
            'source contract scope differs')
    require(plan.get('command') == ['python3', '-P', '/workspace/r3_resume_contract.py',
                                  '--out', str(root)], 'restart command differs')
    inventory = {}

    def bound(name, parse=True):
        p = root / name
        digest = sha(p)
        require(plan['files'].get(str(p)) == digest, 'missing or changed prelaunch pin: '+name)
        inventory[str(p)] = digest
        if not parse:
            return digest
        raw = p.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'metadata changed during read')
        return json.loads(raw)

    source = bound('SOURCE_PLAN.json')
    origin = bound('SOURCE.json')
    contract = bound('CONTRACT.json')
    copy_pin = bound('SOURCE.pt', parse=False)
    step = contract.get('source_step')
    require(type(step) is int and 20 <= step < 3096 and
            type(origin.get('step')) is int and origin['step'] == step,
            'trained source step differs')
    require(contract.get('source_sha256') == origin.get('sha256') == copy_pin,
            'source copy binding differs')
    require(contract.get('scientific_acceptance') is False and contract.get('test_read') is False,
            'contract scope differs')
    training = safe(source['out'])
    require(origin.get('training') == str(training), 'source training identity differs')
    original = safe(origin['checkpoint'])
    require(original == training/'ckpt'/f'step_{step:06d}.pt', 'source checkpoint path/step differs')
    require(source.get('schema') == 'r3-engineering-k1-plan-v1' and
            type(source.get('seed')) is int and source['seed'] == 2 and
            source.get('scientific_acceptance') is False and source.get('test_read') is False,
            'source plan scope differs')
    for field in ('model', 'train_file', 'image_sha256', 'environment'):
        require(field in source and field in plan and source[field] == plan[field],
                'source configuration differs: '+field)
    cmd = source['command']
    require(isinstance(cmd, list) and cmd[:3] == ['python3', '-P', '/workspace/train_r3.py'],
            'source training command differs')
    for flag, value in (('--out', str(training)), ('--seed', '2'), ('--arm', 'k1'),
                        ('--model-path', source['model']), ('--total-steps', '3116')):
        require(cmd.count(flag) == 1 and cmd.index(flag)+1 < len(cmd) and
                cmd[cmd.index(flag)+1] == value, 'source command binding differs: '+flag)
    present = original.exists()
    if present:
        require(original.is_file() and sha(original) == copy_pin, 'present original checkpoint differs')
        inventory[str(original)] = copy_pin
    else:
        require(mode == 'pinned_copy_proposal', 'original checkpoint missing; default contract rejects')
    for filename, pin in inventory.items():
        require(sha(filename) == pin, 'source input changed during validation')
    require(original.exists() == present, 'original presence changed during validation')
    require(path.read_bytes() == plan_bytes, 'plan changed during validation')
    inventory[str(path)] = hashlib.sha256(plan_bytes).hexdigest()
    return {'schema': 'r3-source-retention-proposal-v1', 'status': 'DIAGNOSTIC_BINDINGS_MATCH',
            'mode': mode, 'plan_sha256': plan_pin, 'source_plan_sha256': identity(source),
            'source_step': step, 'source_sha256': copy_pin, 'inputs': inventory,
            'original_checkpoint': str(original), 'original_present': present,
            'source_copy': str(root/'SOURCE.pt'), 'scientific_acceptance': False,
            'test_read': False, 'launch_authorized': False, 'reconstruction_accepted': False,
            'scope': 'Pinned source-byte relationships only; no tensor/step-content validation, '
                     'training authenticity, deletion cause or prelaunch timing proved.'}
