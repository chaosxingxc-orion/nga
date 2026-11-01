#!/usr/bin/env python3
"""CPU reconstruction of completed restart distances from saved checkpoints.

The existing receipt validator runs first. This additional check never changes
the frozen contract, grants formal approval, or reads task evaluation data.
Torch is imported only when reading checkpoints, with weights_only=True.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


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


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def module(path, name):
    value = source_module(path, name)
    return value


def evidence_path(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),
            'unsafe reconstruction evidence path')
    require(p.name not in ('test.jsonl','test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl','.parquet')), 'test dataset dependency forbidden')
    return p


def records(path, start, steps):
    rows = [json.loads(line) for line in evidence_path(path).read_text().splitlines()]
    require([r.get('step') for r in rows] == list(range(start+1, start+steps+1)),
            'restart step population differs')
    for row in rows:
        for key in ('loss', 'grad_norm', 'lr'):
            require(type(row.get(key)) in (int, float) and math.isfinite(row[key]),
                    'nonfinite or missing restart measurement')
    return rows


def distance(left, right, left_rows, right_rows, final_step):
    import torch
    require(type(left.get('step')) is int and type(right.get('step')) is int
            and left['step'] == right['step'] == final_step, 'checkpoint step differs')
    x, y = left['lora'], right['lora']
    require(bool(x) and set(x) == set(y), 'empty or different LoRA inventory')
    numerators, denominators = [], []
    for name in sorted(x):
        a, b = x[name], y[name]
        require(isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor), 'non-tensor LoRA entry')
        require(a.shape == b.shape and a.dtype == b.dtype and a.numel() > 0
                and a.is_floating_point() and b.is_floating_point(), 'LoRA shape/dtype differs')
        require(bool(torch.isfinite(a).all()) and bool(torch.isfinite(b).all()), 'nonfinite LoRA tensor')
        a, b = a.to(device='cpu', dtype=torch.float64), b.to(device='cpu', dtype=torch.float64)
        numerators.append(float(torch.sum(torch.square(a-b))))
        denominators.append(float(torch.sum(torch.square(b))))
    num, den = math.fsum(numerators), math.fsum(denominators)
    require(math.isfinite(num) and math.isfinite(den), 'nonfinite tensor distance')
    require(len(left_rows) == len(right_rows) and bool(left_rows), 'loss population differs')
    loss = math.fsum(abs(a['loss']-b['loss']) for a,b in zip(left_rows,right_rows))/len(left_rows)
    weight = math.sqrt(num/max(den, 1e-60))
    require(math.isfinite(loss) and math.isfinite(weight), 'nonfinite reconstructed distance')
    return {'loss':loss, 'weight_relative_l2':weight}


def numerical_verdict(replicas, resumed, controls):
    require(len(replicas) == 3 and set(controls) == {'zero_moments','no_update'}, 'incomplete distances')
    keys = ('loss','weight_relative_l2')
    for row in [*replicas,resumed,*controls.values()]:
        require(set(row) == set(keys) and all(type(row[k]) in (int,float) and math.isfinite(row[k])
                and row[k] >= 0 for k in keys), 'invalid reconstructed distance')
    slack = {'loss':2.4e-7,'weight_relative_l2':1e-7}
    bars = {k:1.5*max(r[k] for r in replicas)+slack[k] for k in keys}
    require(all(math.isfinite(v) for v in bars.values()), 'reconstructed tolerance overflow')
    resume_pass = all(resumed[k] <= bars[k] for k in keys)
    rejected = {name:any(row[k] > bars[k] for k in keys) for name,row in controls.items()}
    return {'bars':bars,'resume_pass':resume_pass,'controls_rejected':rejected,
            'pass':resume_pass and all(rejected.values())}


def verify(root, pinned_files):
    for path in pinned_files:
        evidence_path(path)
    import torch
    root = Path(root)
    load = lambda p: json.loads(p.read_text())
    config = load(root/'CONTRACT.json')
    start, steps = config['source_step'], config['steps']
    require(steps == 20 and type(start) is int, 'unexpected restart protocol')
    names = ('replica_a','replica_b','replica_c','resumed','zero_moments','no_update')
    rows = {n:records(root/n/'losses.jsonl',start,steps) for n in names}
    for name in names:
        for a,b in zip(rows['replica_a'], rows[name]):
            require(all(k in a and k in b and a[k] == b[k] for k in
                        ('step','epoch','lr','base_questions','examples','tokens','chunks')),
                    'deterministic training fields differ: '+name)
    def checkpoint(name):
        path = root/name/'ckpt'/f'step_{start+steps:06d}.pt'
        require(str(path) in pinned_files, 'checkpoint lacks receipt-validation hash')
        return torch.load(path, map_location='cpu', weights_only=True)
    def pair(a,b):
        x,y = checkpoint(a),checkpoint(b)
        if a == 'resumed':
            require(x['sched'] == y['sched'], 'resumed scheduler differs')
        return distance(x,y,rows[a],rows[b],start+steps)
    replicas = [pair('replica_a','replica_b'),pair('replica_a','replica_c'),pair('replica_b','replica_c')]
    resumed = pair('resumed','replica_a')
    controls = {name:pair(name,'replica_a') for name in ('zero_moments','no_update')}
    verdict = numerical_verdict(replicas,resumed,controls)
    claimed = load(root/'CONTRACT_RESULT.json')
    for actual,reported in zip([*replicas,resumed,*controls.values()],
                               [*claimed['replicas'],claimed['resumed'],*[claimed['controls'][n] for n in controls]]):
        require(all(math.isclose(actual[k],reported[k],rel_tol=1e-9,abs_tol=1e-12) for k in actual),
                'stored distance differs from tensors/losses')
    require(verdict['pass'] and claimed['pass'] is True and
            verdict['resume_pass'] == claimed['resume_pass'] and
            verdict['controls_rejected'] == claimed['controls_rejected'], 'reconstructed contract fails')
    return {'replicas':replicas,'resumed':resumed,'controls':controls,**verdict,
            'scope':'bounded 20-step restart; no arbitrary-horizon or scientific approval',
            'scientific_acceptance':False,'test_read':False,'torch_version':torch.__version__}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True); p.add_argument('--plan-sha256',required=True)
    p.add_argument('--target',required=True); p.add_argument('--target-sha256',required=True)
    p.add_argument('--validator',required=True); p.add_argument('--validator-sha256',required=True)
    p.add_argument('--output',required=True)
    args = p.parse_args()
    for path in (args.validator,args.target,args.plan):
        evidence_path(path)
    digest = lambda path: hashlib.sha256(evidence_path(path).read_bytes()).hexdigest()
    require(digest(args.validator) == args.validator_sha256, 'validator code identity differs')
    require(digest(args.target) == args.target_sha256, 'target plan identity differs')
    validator = module(args.validator,'resume_receipt_validator')
    target = json.loads(Path(args.target).read_text())
    files = validator.validate(args.plan,args.plan_sha256,target)
    result = verify(Path(args.plan).parent,files)
    for path,pin in files.items():
        require(validator.sha(path) == pin, 'evidence changed during CPU reconstruction')
    result.update(inputs=files,plan_sha256=args.plan_sha256,target_sha256=args.target_sha256,
                  validator_sha256=args.validator_sha256,verifier_sha256=digest(__file__))
    output = Path(args.output)
    require(output.name not in ('CONTRACT_RESULT.json','digest.json','TRAIN_EXIT.json','ASTRA_REVIEW.json'),
            'reserved output filename')
    with output.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False); f.write('\n')
    print(json.dumps({'output':str(output),'pass':True,'scientific_acceptance':False}))


if __name__ == '__main__':
    main()
