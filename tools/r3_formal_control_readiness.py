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
    checks['fresh_k0'] = {'path': str(a.k0_preparation), 'status':
                          'PASS' if k0.get('status') == 'PASS' else k0.get('status', 'MISSING')}
    resume = load(a.resume_plan) if a.resume_plan.is_file() else {}
    train_exit = Path(resume.get('out', a.resume_plan.parent)) / 'attempts/1/TRAIN_EXIT.json'
    checks['resume_source'] = {'path': str(a.resume_plan), 'status':
                               'PASS' if train_exit.is_file() else 'WAITING_TRAIN_EXIT',
                               'train_exit': str(train_exit)}
    rec = load(a.resume_reconstruction) if a.resume_reconstruction.is_file() else {}
    checks['resume_reconstruction'] = {'path': str(a.resume_reconstruction), 'status':
                                      'PASS' if rec.get('status') == 'PASS' else rec.get('status', 'WAITING')}
    checks['independent_astra_review'] = {'status': 'PASS' if a.review and a.review.is_file() and
                                         load(a.review).get('verdict') == 'PASS' else 'MISSING'}
    missing = [key for key, value in checks.items() if value.get('status') != 'PASS']
    result = {'schema': 'r3-formal-control-readiness-v1', 'scientific_acceptance': False,
              'test_read': False, 'status': 'READY' if not missing else 'WAITING',
              'missing': missing, 'checks': checks}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': result['status'], 'missing': missing, 'out': str(a.out)}))


if __name__ == '__main__': main()
