#!/usr/bin/env python3
"""Prepare fresh train-only K1 plans, never launches and never creates review approval."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path('/home/xingchao/workspace/nga')
BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base')
PT_MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B')
TRAIN = BASE / 'KEV/decision-v7/train.jsonl'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'


def source_module(path, name):
    """Compile the actual source bytes; never execute import-cache bytecode."""
    import types
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('unsafe helper source')
    raw = path.read_bytes()
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), value.__dict__)
    return value


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def control_settings(control_arm, *, engineering, model, seed, arm, shared, validate_shared, formal=False):
    if control_arm is None:
        if Path(model) == PT_MODEL:
            raise ValueError('instruct checkpoint requires explicit K1-PT control')
        return None
    if control_arm not in ('K1-QO', 'K1-PT') or (not engineering and not formal) or arm != 'k1' or shared or validate_shared:
        raise ValueError('controls require K1 reference recipe')
    expected_model = MODEL if control_arm == 'K1-QO' else PT_MODEL
    seeds = (2,) if control_arm == 'K1-QO' else (2, 3)
    if Path(model) != expected_model or type(seed) is not int or seed not in seeds:
        raise ValueError('control model or seed differs from registered scope')
    return {'control_arm':control_arm, 'candidate_for_adoption':False,
            'primary_input_mode':'drop' if control_arm == 'K1-QO' else 'full',
            'registered_seeds':list(seeds)}


def formal_control_container(out, control_arm, seed):
    """Bind a distinct retained container namespace to each fresh control generation."""
    suffix = hashlib.sha256(str(Path(out).absolute()).encode()).hexdigest()[:16]
    return f'nga-r3-formal-{control_arm.lower()}-s{seed}-{suffix}'


def prepare(out, seed, chip, engineering=False, model=MODEL, stop_after=0, arm='k1', shared=False, validate_shared=False, fresh_prechecks=None, fresh_prechecks_sha256=None, training_evidence=None, training_evidence_sha256=None, resume_plan=None, resume_plan_sha256=None, control_arm=None, resume_reconstruction=None, resume_reconstruction_sha256=None, reconstruction_target=None, reconstruction_target_sha256=None, formal_chips=(1, 4), formal_schedule=None, formal_schedule_sha256=None, formal_role=None):
    role_binding=any(x is not None for x in (formal_schedule,formal_schedule_sha256,formal_role))
    if role_binding and (engineering or control_arm or not all((formal_schedule,formal_schedule_sha256,formal_role))):
        raise ValueError('complete formal Base role binding required')
    control = control_settings(control_arm, engineering=engineering, model=model, seed=seed,
                               arm=arm, shared=shared, validate_shared=validate_shared, formal=not engineering)
    if arm not in ('k1', 'k2'):
        raise ValueError('unsupported loss arm')
    if not engineering and (Path(model) != (PT_MODEL if control_arm == 'K1-PT' else MODEL)
                            or stop_after or arm != 'k1' or shared or validate_shared):
        raise ValueError('formal recipe cannot be overridden')
    if not engineering and (type(chip) is not int or chip not in tuple(formal_chips)
                            or type(seed) is not int or seed not in (2, 3)):
        raise ValueError('unregistered formal seed/chip')
    fresh = None
    if not engineering:
        if not fresh_prechecks or not fresh_prechecks_sha256:
            raise ValueError('formal preparation requires externally pinned fresh K0 prechecks')
        helper = source_module(ROOT/'tools/r3_fresh_prechecks.py', 'fresh_prechecks')
        fresh = helper.validate_bundle(fresh_prechecks, fresh_prechecks_sha256, model)
        if not training_evidence or not training_evidence_sha256:
            raise ValueError('formal preparation requires pinned augmentation/LoRA evidence')
        if not resume_plan or not resume_plan_sha256:
            raise ValueError('formal preparation requires a pinned completed NPU resume plan')
        if not all((resume_reconstruction, resume_reconstruction_sha256,
                    reconstruction_target, reconstruction_target_sha256)):
            raise ValueError('formal preparation requires pinned CPU resume reconstruction and target')
    out.mkdir(parents=True, exist_ok=False)
    code = out / 'code'
    code.mkdir()
    source = BASE / 'r3_code' if shared else ROOT / 'experiments/r3_sft/r3_code'
    names = ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py', 'gdn_fast_ref.py', 'k2_shared.py') if shared else ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py')
    for name in names:
        shutil.copy2(source / name, code / name)
    if validate_shared:
        if not shared:
            raise ValueError('shared validation needs modern shared code')
        for name in ('test_k2_shared.py', 'test_train_r3.py'):
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
    if fresh:
        # Replace the six K0 checks, preserving separate augmentation evidence.
        # Exact train-code/LoRA/restart review is still required before launch.
        for filename in fresh['checks']:
            shutil.copy2(filename, out/'prechecks'/Path(filename).name)
        shutil.copy2(ROOT/'tools/r3_fresh_prechecks.py', tool_dir/'r3_fresh_prechecks.py')
    training_files = {}
    if not engineering:
        helper = source_module(ROOT/'tools/r3_training_evidence.py', 'training_evidence')
        training_files = helper.validate(training_evidence, training_evidence_sha256, code, model, TRAIN, IMAGE,
                                        control_arm=control_arm,
                                        input_mode=control['primary_input_mode'] if control else 'full')
        shutil.copy2(ROOT/'tools/r3_training_evidence.py', tool_dir/'r3_training_evidence.py')
    if not engineering:
        for name in ('r3_resume_evidence.py', 'r3_resume_reconstruction_evidence.py', 'r3_resume_recompute.py'):
            shutil.copy2(ROOT/'tools'/name, tool_dir/name)
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
               '--save-every', '200', '--no-merge', '--epochs', '2', '--total-steps', '3116', '--expect-pairs', '186' if model in (MODEL, PT_MODEL) else '0']
    if stop_after:
        command += ['--stop-after', str(stop_after)]
    if control_arm == 'K1-QO':
        command += ['--drop-state']
    if shared:
        if not engineering or arm != 'k2' or stop_after not in (0, 45):
            raise ValueError('shared path must be engineering K2, full or 45-step validation')
        command.remove('--grad-ckpt')
        command[command.index('--micro-tokens')+1] = '3000'
        command += ['--k2-impl', 'shared', '--gdn-impl', 'ref', '--k2-rows', '48']
    formal_chip_pair = tuple(int(x) for x in formal_chips)
    if not engineering:
        if len(formal_chip_pair) != 2 or len(set(formal_chip_pair)) != 2 or any(x < 0 or x >= 8 for x in formal_chip_pair):
            raise ValueError('formal chip pair must contain two distinct Ascend chip ids')
    plan = {'schema': 'r3-formal-k1-plan-v1', 'seed': seed, 'chip': chip,
            'formal_chips': list(formal_chip_pair) if not engineering else None,
            'run': str(out.relative_to(BASE)),
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
    if role_binding:
        helper_path=tool_dir/'r3_formal_roles.py'
        shutil.copy2(ROOT/'tools/r3_formal_roles.py',helper_path)
        helper=source_module(helper_path,'formal_roles')
        schedule=Path(formal_schedule).absolute()
        if helper.sha(schedule)!=formal_schedule_sha256: raise ValueError('schedule changed')
        doc=json.loads(schedule.read_text());nodes=helper.validate_schedule(doc)
        plan.update(formal_schedule=str(schedule),formal_schedule_sha256=formal_schedule_sha256,formal_role=formal_role)
        plan['container']=nodes[formal_role]['container']
        plan['evaluation']['candidate_for_adoption']=nodes[formal_role]['candidate_for_seed_mean']
        plan['files'].update({str(helper_path):sha(helper_path),str(schedule):formal_schedule_sha256})
        helper.validate_plan(plan)
    if control:
        plan.update(control_arm=control_arm, control=control)
        plan['evaluation'].update(control_arm=control_arm, primary_input_mode=control['primary_input_mode'],
                                  candidate_for_adoption=False, registered_seeds=control['registered_seeds'],
                                  seeds=control['registered_seeds'])
        if not engineering:
            plan['container'] = formal_control_container(out, control_arm, seed)
    if not engineering:
        helper = source_module(ROOT/'tools/r3_resume_evidence.py', 'resume_evidence')
        plan.update(resume_plan=str(Path(resume_plan).absolute()), resume_plan_sha256=resume_plan_sha256)
        plan['files'].update(helper.validate(plan['resume_plan'], resume_plan_sha256, plan))
        helper = source_module(ROOT/'tools/r3_resume_reconstruction_evidence.py', 'resume_reconstruction')
        plan.update(resume_reconstruction=str(Path(resume_reconstruction).absolute()),
                    resume_reconstruction_sha256=resume_reconstruction_sha256,
                    reconstruction_target=str(Path(reconstruction_target).absolute()),
                    reconstruction_target_sha256=reconstruction_target_sha256)
        plan['files'].update(helper.validate(plan['resume_reconstruction'], resume_reconstruction_sha256,
            resume_plan=plan['resume_plan'], resume_pin=resume_plan_sha256, target=plan,
            reconstruction_target=plan['reconstruction_target'],
            reconstruction_target_sha256=reconstruction_target_sha256))
    if training_files:
        plan.update(training_evidence=str(Path(training_evidence).resolve()), training_evidence_sha256=training_evidence_sha256)
        plan['files'].update(training_files)
    if fresh:
        plan.update(fresh_k0_prechecks=str(Path(fresh_prechecks).resolve()),
                    fresh_k0_prechecks_sha256=fresh_prechecks_sha256)
        plan['files'][plan['fresh_k0_prechecks']] = fresh_prechecks_sha256
        plan['files'].update(fresh['inputs']); plan['files'].update(fresh['checks'])
    if engineering:
        plan.update(schema='r3-engineering-k1-plan-v1', execution_scope='engineering_only',
                    authorization='user_execute_engineering_when_ready_20261031',
                    container=f'nga-r3-eng-{out.parent.name}-s{seed}', stop_after=stop_after, arm=arm,
                    evaluation={'candidate_test_forbidden': True, 'formal_acceptance_requires_new_review': True})
    if control:
        # Engineering scope replacement above needs the same explicit control metadata.
        plan['evaluation'].update(control_arm=control_arm, primary_input_mode=control['primary_input_mode'],
                                  candidate_for_adoption=False, registered_seeds=control['registered_seeds'])
    if shared:
        plan['k2_impl'] = 'shared'
        if not stop_after:
            evidence = BASE / 'r3_runs/k2_shared_contract_20261031_v2/seed2/CONTRACT_DIGEST.json'
            verdict = json.loads(evidence.read_text())
            if verdict.get('status') != 'CONTRACT_PASS' or len(verdict.get('results', [])) != 4:
                raise ValueError('shared numerical contract incomplete')
            plan['shared_contract'] = str(evidence)
            plan['files'][str(evidence)] = sha(evidence)
    if validate_shared:
        plan['validation_kind'] = 'shared_k2_reference_contract'
        plan['command'] = ['python3', '-P', '/workspace/test_k2_shared.py', '--device', 'npu:0', '--impls', 'ref']
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
    if control:
        with (out / 'PREREGISTRATION.md').open('a') as f:
            f.write('\nControl '+control_arm+': no adoption; registered seeds '+str(control['registered_seeds'])+
                    '; training/evaluation primary input mode '+control['primary_input_mode']+'.\n')
    return {'out': str(out), 'sha256': pin, 'launch': line.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parent', required=True)
    ap.add_argument('--engineering', action='store_true', help='Separate user-authorized engineering generation; never formal acceptance')
    ap.add_argument('--fresh-prechecks')
    ap.add_argument('--fresh-prechecks-sha256')
    ap.add_argument('--training-evidence')
    ap.add_argument('--training-evidence-sha256')
    ap.add_argument('--resume-plan')
    ap.add_argument('--resume-plan-sha256')
    ap.add_argument('--resume-reconstruction')
    ap.add_argument('--resume-reconstruction-sha256')
    ap.add_argument('--reconstruction-target')
    ap.add_argument('--reconstruction-target-sha256')
    ap.add_argument('--control-arm', choices=('K1-QO','K1-PT'))
    ap.add_argument('--model')
    ap.add_argument('--formal-schedule')
    ap.add_argument('--formal-schedule-sha256')
    ap.add_argument('--formal-role',choices=('primary_s2','primary_s3','samechip_s2','diffchip_s2'))
    ap.add_argument('--formal-chips', nargs=2, type=int, metavar=('CHIP_SEED2', 'CHIP_SEED3'), default=(1, 4),
                    help='formal chip pair; must be supplied from a live allocation snapshot and adapter claim, never edited in the plan')
    args = ap.parse_args()
    parent = Path(args.parent)
    model = Path(args.model) if args.model else (PT_MODEL if args.control_arm == 'K1-PT' else MODEL)
    if any((args.formal_schedule,args.formal_schedule_sha256,args.formal_role)):
        if not all((args.formal_schedule,args.formal_schedule_sha256,args.formal_role)) or args.engineering or args.control_arm:
            raise ValueError('complete formal Base role arguments required')
        helper=source_module(ROOT/'tools/r3_formal_roles.py','roles')
        if helper.sha(args.formal_schedule)!=args.formal_schedule_sha256: raise ValueError('schedule changed')
        schedule=json.loads(Path(args.formal_schedule).read_text());nodes=helper.validate_schedule(schedule)
        node=nodes[args.formal_role]
        if Path(node['out']).parent != parent.absolute(): raise ValueError('schedule output parent differs')
        print(json.dumps(prepare(Path(node['out']),node['seed'],node['chip'],model=model,
            fresh_prechecks=args.fresh_prechecks,fresh_prechecks_sha256=args.fresh_prechecks_sha256,
            training_evidence=args.training_evidence,training_evidence_sha256=args.training_evidence_sha256,
            resume_plan=args.resume_plan,resume_plan_sha256=args.resume_plan_sha256,
            resume_reconstruction=args.resume_reconstruction,resume_reconstruction_sha256=args.resume_reconstruction_sha256,
            reconstruction_target=args.reconstruction_target,reconstruction_target_sha256=args.reconstruction_target_sha256,
            formal_chips=tuple(schedule['physical_chips']),formal_schedule=args.formal_schedule,
            formal_schedule_sha256=args.formal_schedule_sha256,formal_role=args.formal_role),indent=2))
        return
    seeds = (2,) if args.control_arm == 'K1-QO' else (2,3)
    print(json.dumps([prepare(parent / f'seed{seed}', seed, chip, args.engineering, model=model, control_arm=args.control_arm, fresh_prechecks=args.fresh_prechecks, fresh_prechecks_sha256=args.fresh_prechecks_sha256, training_evidence=args.training_evidence, training_evidence_sha256=args.training_evidence_sha256, resume_plan=args.resume_plan, resume_plan_sha256=args.resume_plan_sha256,
        resume_reconstruction=args.resume_reconstruction, resume_reconstruction_sha256=args.resume_reconstruction_sha256,
        reconstruction_target=args.reconstruction_target, reconstruction_target_sha256=args.reconstruction_target_sha256,
        formal_chips=tuple(args.formal_chips)) for seed, chip in zip(seeds, tuple(args.formal_chips))], indent=2))


if __name__ == '__main__':
    main()
