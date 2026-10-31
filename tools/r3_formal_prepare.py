#!/usr/bin/env python3
"""Prepare fresh train-only K1 plans, never launches and never creates review approval."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path('/home/xingchao/workspace/nga')
BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base')
TRAIN = BASE / 'KEV/decision-v7/train.jsonl'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def prepare(out, seed, chip, engineering=False, model=MODEL, stop_after=0, arm='k1', shared=False):
    if arm not in ('k1', 'k2'):
        raise ValueError('unsupported loss arm')
    if not engineering and (model != MODEL or stop_after or arm != 'k1' or shared):
        raise ValueError('formal recipe cannot be overridden')
    out.mkdir(parents=True, exist_ok=False)
    code = out / 'code'
    code.mkdir()
    source = BASE / 'r3_code' if shared else ROOT / 'experiments/r3_sft/r3_code'
    names = ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py', 'gdn_fast_ref.py', 'k2_shared.py') if shared else ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py')
    for name in names:
        shutil.copy2(source / name, code / name)
    (code / 'r0_code').mkdir()
    shutil.copy2(ROOT / 'experiments/r0_baseline/prompt.py', code / 'r0_code/prompt.py')
    shutil.copy2(ROOT / 'tools/r3_formal_driver.py', code / 'r3_formal_driver.py')
    tool_dir = out / 'tools'
    tool_dir.mkdir()
    for name in ('r3_formal_launcher.py', 'r3_resource_adapter.py'):
        shutil.copy2(ROOT / 'tools' / name, tool_dir / name)
    shutil.copytree(BASE / 'r3_runs/formal_k1_prechecks_20261031/prechecks', out / 'prechecks')
    for p in (out / 'prechecks').glob('*.json'):
        if json.loads(p.read_text()).get('ok') is not True:
            raise RuntimeError('failed precheck: ' + str(p))
    prereg = ROOT / '.local/archive/2026-10-31/experiments'
    for name in ('R3-SFT-PREREG.md', 'R3-TRAINING-WAVE-PREREG-2026-10-31.md'):
        shutil.copy2(prereg / name, out / name)
    files = {str(p): sha(p) for p in out.rglob('*') if p.is_file()}
    files[str(TRAIN)] = sha(TRAIN)
    for p in model.iterdir():
        if p.is_file():
            files[str(p)] = sha(p)
    command = ['python3', '-P', '/workspace/train_r3.py', '--out', str(out), '--arm', arm, '--seed', str(seed),
               '--model-path', str(model), '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
               '--save-every', '200', '--no-merge', '--epochs', '2', '--total-steps', '3116', '--expect-pairs', '186' if model == MODEL else '0']
    if stop_after:
        command += ['--stop-after', str(stop_after)]
    if shared:
        if not engineering or arm != 'k2' or stop_after != 45:
            raise ValueError('shared path is a 45-step K2 engineering validation')
        command.remove('--grad-ckpt')
        command[command.index('--micro-tokens')+1] = '3000'
        command += ['--k2-impl', 'shared', '--gdn-impl', 'ref', '--k2-rows', '48']
    plan = {'schema': 'r3-formal-k1-plan-v1', 'seed': seed, 'chip': chip, 'run': str(out.relative_to(BASE)),
            'out': str(out), 'code': str(code), 'model': str(model), 'train_file': str(TRAIN),
            'allocation': str(BASE / 'CHIP-ALLOCATION.json'), 'image_sha256': IMAGE,
            'container': f'nga-r3-formal-k1-s{seed}-20261031', 'command': command,
            'environment': {'ASCEND_RT_VISIBLE_DEVICES': '0', 'TASK_QUEUE_ENABLE': '2',
                            'PYTORCH_NPU_ALLOC_CONF': 'expandable_segments:True',
                            'NGA_R0_CODE': '/workspace/r0_code', 'PYTHONDONTWRITEBYTECODE': '1',
                            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'},
            'launcher': str(tool_dir / 'r3_formal_launcher.py'), 'adapter': str(tool_dir / 'r3_resource_adapter.py'),
            'driver': str(code / 'r3_formal_driver.py'), 'files': files,
            'review_path': str(out / 'ASTRA_REVIEW.json'), 'review_sha256': 'PENDING',
            'scientific_acceptance': False, 'test_read': False,
            'evaluation': {'seeds': [2, 3], 'decision_dev_min': .80, 'transfer_dev_min': .60,
                           'max_k0_regression_pp': 1.0, 'test_requires_separate_final_ticket': True},
            'engineering_evidence': str(BASE / 'r3_runs/formal_k1_prechecks_20261031/V12_REVERIFICATION.json'), 'engineering_evidence_scope': 'retrospective CPU recomputation; not independent Astra acceptance'}
    if engineering:
        plan.update(schema='r3-engineering-k1-plan-v1', execution_scope='engineering_only',
                    authorization='user_execute_engineering_when_ready_20261031',
                    container=f'nga-r3-eng-{out.parent.name}-s{seed}', stop_after=stop_after, arm=arm,
                    evaluation={'candidate_test_forbidden': True, 'formal_acceptance_requires_new_review': True})
    if shared:
        plan['k2_impl'] = 'shared'
    pin = hashlib.sha256((json.dumps(plan, indent=2, sort_keys=True) + '\n').encode()).hexdigest()
    write(out / 'plan.json', plan)
    (out / 'CANONICAL_PLAN_SHA256').write_text(pin + '\n')
    line = f"ssh npu 'python3.12 -P {plan['launcher']} start --plan {out}/plan.json --sha256 {pin}'\n"
    (out / 'LAUNCH_PENDING_REVIEW.txt').write_text(line)
    (out / 'RELAUNCH.txt').write_text(line.rstrip() + ' # append --attempt N inside SSH command after a failed, released attempt\n')
    (out / 'PREREGISTRATION.md').write_text(
        f'# {"Engineering" if engineering else "Formal"} K1 seed {seed}, prepared only\n\nTrain-only, 3116 steps / two epochs, reference kernel. '
        'No test mount; no network. Independent exact-plan Astra review remains pending. '
        'No approval file is generated by preparation.\n\n'
        'Resume: after a failed attempt and guarded release, rerun the launch command with --attempt N '
        '(N is the next integer). Retained containers and attempt logs remain; the trainer resumes '
        'from its last atomic checkpoint. A live or unobserved container is never restarted.\n')
    if engineering:
        with (out / 'PREREGISTRATION.md').open('a') as f:
            f.write('\nUser authorized engineering execution when ready on 2026-10-31. This generation tests sustained training, checkpoint writing and supervised resource release. It cannot establish a scientific baseline; independent review remains outstanding. No test access. Nonblocking findings go to the next generation.\n')
    return {'out': str(out), 'sha256': pin, 'launch': line.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parent', required=True)
    ap.add_argument('--engineering', action='store_true', help='Separate user-authorized engineering generation; never formal acceptance')
    args = ap.parse_args()
    parent = Path(args.parent)
    print(json.dumps([prepare(parent / f'seed{seed}', seed, chip, args.engineering) for seed, chip in ((2, 1), (3, 4))], indent=2))


if __name__ == '__main__':
    main()
