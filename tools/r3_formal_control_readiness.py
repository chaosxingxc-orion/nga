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


def validator():
    path = ROOT / 'tools/r3_training_evidence.py'
    spec = importlib.util.spec_from_file_location('r3_training_evidence', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def fresh_precheck_validator(path):
    """Load the frozen K0 precheck helper beside the prepared queue record."""
    helper = Path(path).parent / 'r3_fresh_prechecks.py'
    if not helper.is_file():
        helper = ROOT / 'tools/r3_fresh_prechecks.py'
    spec = importlib.util.spec_from_file_location('r3_fresh_prechecks_readiness', helper)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod, helper


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--k0-preparation', type=Path,
                    default=BASE/'fresh_k0_prechecks_20261031_v1/PREPARED.json')
    ap.add_argument('--resume-plan', type=Path,
                    default=BASE/'k1_current_resume_contract_20261031_v3/seed2/plan.json')
    ap.add_argument('--resume-reconstruction', type=Path,
                    default=BASE/'current_resume_cpu_recompute_20261031_v1/PREPARATION.json')
    ap.add_argument('--review', type=Path, default=None)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    checks = {
        'qo_evidence': evidence(TRAIN, 'K1-QO', MODEL),
        'pt_evidence': evidence(PT, 'K1-PT', PT_MODEL),
    }
    k0 = load(a.k0_preparation) if a.k0_preparation.is_file() else {}
    # PREPARED.json is a queue hand-off record.  It intentionally remains in
    # WAITING_VERIFIED_K0_REPORT after the worker starts; only the immutable
    # K0_PRECHECKS.json produced by the worker can establish PASS.
    k0_bundle = a.k0_preparation.parent / 'evidence' / 'K0_PRECHECKS.json'
    if k0_bundle.is_file():
        try:
            helper, _ = fresh_precheck_validator(a.k0_preparation)
            helper.validate_bundle(k0_bundle, sha(k0_bundle), str(MODEL))
            k0_status = 'PASS'
        except Exception:
            k0_status = 'INVALID'
    else:
        k0_status = k0.get('status', 'MISSING')
    checks['fresh_k0'] = {'path': str(k0_bundle), 'status': k0_status}
    resume = load(a.resume_plan) if a.resume_plan.is_file() else {}
    train_exit = Path(resume.get('out', a.resume_plan.parent)) / 'attempts/1/TRAIN_EXIT.json'
    exit_doc = load(train_exit) if train_exit.is_file() else {}
    checks['resume_source'] = {'path': str(a.resume_plan), 'status':
                               'PASS' if (exit_doc.get('exit_code') == 0
                                          and exit_doc.get('scientific_acceptance') is False
                                          and exit_doc.get('test_read') is False)
                               else ('INVALID' if train_exit.is_file() else 'WAITING_TRAIN_EXIT'),
                               'train_exit': str(train_exit)}
    rec = load(a.resume_reconstruction) if a.resume_reconstruction.is_file() else {}
    # PREPARATION.json is only a waiting hand-off. A reconstruction PASS must
    # be an actual bounded report with numerical and immutable-input bindings.
    rec_pass = (a.resume_reconstruction.name not in ('PREPARATION.json', 'SUCCESSOR_LAUNCH.json')
                and rec.get('pass') is True and rec.get('resume_pass') is True
                and rec.get('scientific_acceptance') is False and rec.get('test_read') is False
                and isinstance(rec.get('inputs'), dict) and bool(rec['inputs'])
                and isinstance(rec.get('plan_sha256'), str) and len(rec['plan_sha256']) == 64
                and isinstance(rec.get('target_sha256'), str) and len(rec['target_sha256']) == 64)
    checks['resume_reconstruction'] = {'path': str(a.resume_reconstruction), 'status':
                                      'PASS' if rec_pass else (rec.get('status', 'WAITING')
                                      if a.resume_reconstruction.is_file() else 'WAITING')}
    review = load(a.review) if a.review and a.review.is_file() else {}
    checks['independent_astra_review'] = {'status': 'PASS' if (
        review.get('verdict') == 'PASS'
        and review.get('review_kind') == 'independent_astra'
        and review.get('reviewer_model') == 'gpt-6-astra'
        and isinstance(review.get('approved_plan_sha256'), str)
        and len(review['approved_plan_sha256']) == 64
    ) else ('INVALID' if review else 'MISSING')}
    missing = [key for key, value in checks.items() if value.get('status') != 'PASS']
    result = {'schema': 'r3-formal-control-readiness-v1', 'scientific_acceptance': False,
              'test_read': False, 'status': 'READY' if not missing else 'WAITING',
              'missing': missing, 'checks': checks}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': result['status'], 'missing': missing, 'out': str(a.out)}))


if __name__ == '__main__': main()
