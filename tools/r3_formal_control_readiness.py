#!/usr/bin/env python3
"""Read-only readiness audit for formal K1-QO/K1-PT preparation.

The audit never launches Docker, reads test data, or creates an approval. It
validates the retained training-evidence packs and reports missing K0,
reconstruction, and exact-plan-review prerequisites explicitly.
"""
import argparse, hashlib, importlib.util, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
TRAIN = BASE / 'control_training_evidence_k1_qo_20261031_v3'
PT = BASE / 'control_training_evidence_k1_pt_20261031_v3'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base')
PT_MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B')
DATA = Path('/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl')
CODE = ROOT / 'experiments/r3_sft/r3_code'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def canonical_plan_sha256(plan):
    """Return the plan identity used by the formal launcher/resume validator."""
    import hashlib
    value = dict(plan, review_sha256='PENDING')
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2) + '\n').encode()).hexdigest()


def validator():
    path = ROOT / 'tools/r3_training_evidence.py'
    spec = importlib.util.spec_from_file_location('r3_training_evidence', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def evidence(path, arm, model):
    result = {'path': str(path), 'arm': arm, 'status': 'MISSING'}
    pin_file = path / 'EVIDENCE_SHA256'
    report = path / 'EVIDENCE.json'
    if not report.is_file() or not pin_file.is_file():
        result['reason'] = 'EVIDENCE.json or EVIDENCE_SHA256 missing'; return result
    pin = pin_file.read_text().strip()
    try:
        doc = load(report)
        code_root = Path(next(p for p in doc['files'] if p.endswith('/code/train_r3.py'))).parent
        validator().validate(report, pin, code_root, model, DATA, IMAGE, control_arm=arm,
                             input_mode='drop' if arm == 'K1-QO' else 'full')
    except Exception as exc:
        result['reason'] = type(exc).__name__ + ': ' + str(exc)[:300]; return result
    result.update(status='PASS', sha256=pin)
    return result


def module(name):
    """Use this audited implementation, never execute a helper selected by evidence."""
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location('readiness_' + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def require(value, reason):
    if not value:
        raise ValueError(reason)


def check(fn):
    try:
        fn()
        return {'status': 'PASS'}
    except Exception as exc:
        return {'status': 'INVALID', 'reason': type(exc).__name__ + ': ' + str(exc)[:300]}


def resume_source_ready(plan_path, target=None, pin=None):
    """No receipt-only success: validate the complete source against a target recipe."""
    if target is None or pin is None:
        return False
    try:
        module('r3_resume_evidence').validate(plan_path, pin, target)
        return True
    except Exception:
        return False


def bound(target, field):
    path = Path(target[field])
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            'unsafe evidence path: ' + field)
    pin = target[field + '_sha256']
    require(target['files'].get(str(path)) == pin == sha(path), 'unbound evidence: ' + field)
    return path, pin


def check_inventory(target, inventory):
    require(all(target['files'].get(p) == h for p, h in inventory.items()),
            'validated dependencies absent from target inventory')


def target_resume(target):
    path = Path(target['resume_plan'])
    pin = target['resume_plan_sha256']
    require(target['files'].get(str(path)) == sha(path), 'resume file not bound')
    require(canonical_plan_sha256(load(path)) == pin, 'canonical resume identity differs')
    files = module('r3_resume_evidence').validate(path, pin, target)
    check_inventory(target, files)


def target_reconstruction(target):
    path, pin = bound(target, 'resume_reconstruction')
    require(path.name not in ('PREPARATION.json', 'SUCCESSOR_LAUNCH.json'),
            'preparation is not reconstruction evidence')
    reconstruction_target, target_pin = bound(target, 'reconstruction_target')
    files = module('r3_resume_reconstruction_evidence').validate(
        path, pin, resume_plan=target['resume_plan'], resume_pin=target['resume_plan_sha256'],
        target=target, reconstruction_target=reconstruction_target,
        reconstruction_target_sha256=target_pin)
    check_inventory(target, files)


def target_k0(target):
    path, pin = bound(target, 'fresh_k0_prechecks')
    result = module('r3_fresh_prechecks').validate_bundle(path, pin, target['model'])
    check_inventory(target, {**result['inputs'], **result['checks']})


def target_training(target):
    path, pin = bound(target, 'training_evidence')
    result = module('r3_training_evidence').validate(
        path, pin, target['code'], target['model'], target['train_file'], target['image_sha256'],
        control_arm=target['control_arm'], input_mode=target['control']['primary_input_mode'])
    check_inventory(target, result)


def target_review(target, pin):
    path = Path(target['review_path'])
    require(sha(path) == target['review_sha256'], 'review bytes differ')
    review = load(path)
    require(review.get('verdict') == 'PASS' and review.get('review_kind') == 'independent_astra'
            and review.get('reviewer_model') == 'gpt-6-astra'
            and review.get('approved_plan_sha256') == pin, 'exact target review required')
    # This checks binding, not reviewer authorship. Independent process evidence
    # remains an external acceptance obligation, explicitly reported below.


def target_identity(target, pin):
    require(canonical_plan_sha256(target) == pin, 'target canonical identity differs')
    require(target.get('schema') == 'r3-formal-k1-plan-v1'
            and target.get('scientific_acceptance') is False and target.get('test_read') is False,
            'target formal train-only scope differs')
    arm = target.get('control_arm')
    require(arm in ('K1-QO', 'K1-PT'), 'explicit registered control required')
    seeds = [2] if arm == 'K1-QO' else [2, 3]
    model = str(MODEL if arm == 'K1-QO' else PT_MODEL)
    mode = 'drop' if arm == 'K1-QO' else 'full'
    require(type(target.get('seed')) is int and target['seed'] in seeds
            and target.get('model') == model, 'control seed/model differs')
    control = {'control_arm': arm, 'candidate_for_adoption': False,
               'primary_input_mode': mode, 'registered_seeds': seeds}
    require(target.get('control') == control, 'control input mode/coverage differs')
    require(target.get('image_sha256') == IMAGE and target.get('train_file') == str(DATA),
            'registered image/data differs')
    expected = ['python3', '-P', '/workspace/train_r3.py', '--out', target['out'],
                '--arm', 'k1', '--seed', str(target['seed']), '--model-path', model,
                '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
                '--save-every', '200', '--no-merge', '--epochs', '2', '--total-steps', '3116',
                '--expect-pairs', '186']
    if arm == 'K1-QO':
        expected += ['--drop-state']
    require(target.get('command') == expected, 'control training recipe differs')
    for name in target['files']:
        path = Path(name)
        require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
                'unsafe dependency path')
        require(path.name not in ('test.jsonl', 'test.variants.jsonl') and not
                ('test' in path.parts and path.suffix in ('.jsonl', '.parquet')),
                'test dataset dependency forbidden')
    # Validate bytes only after checking the entire inventory excludes tests.
    for name, digest in target['files'].items():
        require(sha(name) == digest, 'target dependency changed: ' + name)


def target_implementations(target):
    for name in ('r3_resume_evidence', 'r3_resume_reconstruction_evidence',
                 'r3_training_evidence', 'r3_fresh_prechecks'):
        expected = sha(Path(__file__).with_name(name + '.py'))
        entries = [h for p, h in target['files'].items() if Path(p).name == name + '.py']
        require(entries and all(h == expected for h in entries),
                'target must bind audited validator implementation: ' + name)


def audit_target(path, pin):
    result = {'path': str(path), 'plan_sha256': pin, 'status': 'INVALID', 'checks': {}}
    try:
        target = load(path)
        target_identity(target, pin)
    except Exception as exc:
        result['reason'] = type(exc).__name__ + ': ' + str(exc)[:300]
        return result
    result.update(control_arm=target['control_arm'], seed=target['seed'], model=target['model'],
                  input_mode=target['control']['primary_input_mode'])
    for name, fn in [('validator_implementations', target_implementations), ('fresh_k0', target_k0), ('resume_source', target_resume),
                     ('resume_reconstruction', target_reconstruction),
                     ('training_evidence', target_training)]:
        result['checks'][name] = check(lambda fn=fn: fn(target))
    result['checks']['independent_astra_review'] = check(lambda: target_review(target, pin))
    result['status'] = 'PASS' if all(x['status'] == 'PASS' for x in result['checks'].values()) else 'WAITING'
    return result


def audit_targets(entries):
    targets = [audit_target(Path(path), pin) for path, pin in entries]
    expected = {('K1-QO', 2), ('K1-PT', 2), ('K1-PT', 3)}
    identities = [(x.get('control_arm'), x.get('seed')) for x in targets]
    missing = ['%s/seed%s' % x for x in sorted(expected - set(identities))]
    duplicate = len(identities) != len(set(identities))
    pending = [{'path': row['path'], 'status': row['status'],
                'checks': [name for name, value in row['checks'].items() if value['status'] != 'PASS']}
               for row in targets if row['status'] != 'PASS']
    ok = not missing and not duplicate and len(targets) == len(expected) and all(x['status'] == 'PASS' for x in targets)
    return {'schema': 'r3-formal-control-readiness-v2', 'status': 'READY' if ok else 'WAITING',
            'scientific_acceptance': False, 'test_read': False, 'launch_authorized': False,
            'review_provenance': 'Exact review byte/plan binding checked; independent reviewer authorship requires process evidence.',
            'missing': missing, 'pending_targets': pending, 'duplicate_target_coverage': duplicate, 'targets': targets}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target-plan', nargs=2, action='append', default=[], metavar=('PATH', 'SHA256'),
                    help='repeat for QO seed2 and PT seeds2/3, each independently bound')
    # Retain old invocation syntax for diagnostics only. It cannot grant per-arm readiness.
    ap.add_argument('--k0-preparation', type=Path, default=BASE/'fresh_k0_prechecks_20261031_v1/PREPARED.json')
    ap.add_argument('--resume-plan', type=Path, default=BASE/'k1_current_resume_contract_20261031_v3/seed2/plan.json')
    ap.add_argument('--resume-reconstruction', type=Path, default=BASE/'current_resume_cpu_recompute_20261031_v1/PREPARATION.json')
    ap.add_argument('--review', type=Path)
    ap.add_argument('--expected-plan-sha256')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(argv)
    result = audit_targets(a.target_plan)
    if not a.target_plan:
        result['checks'] = {key: {'status': 'WAITING_TARGET_PLANS'} for key in
                            ('fresh_k0', 'resume_source', 'resume_reconstruction', 'independent_astra_review')}
        result['checks'].update(qo_evidence=evidence(TRAIN, 'K1-QO', MODEL),
                                pt_evidence=evidence(PT, 'K1-PT', PT_MODEL))
        result['diagnostic_only'] = True
    a.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = a.out.with_suffix(a.out.suffix + '.pending')
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    temporary.replace(a.out)
    print(json.dumps({'status': result['status'], 'missing': result['missing'], 'out': str(a.out)}))


if __name__ == '__main__':
    main()
