"""Paired NPU benchmark for deferred scalar transfer; never updates model weights.

One chip, training rows only, original forward/backward/dropout order. Three
warmup pairs then ten measured pairs. Exact loss and every gradient must match
both the reference repeat and candidate; failure cannot authorize replacement.
Run detached under a resource-owning supervisor with a retained container.
"""
import argparse
import ast
import hashlib
import json
import math
import os
import random
from pathlib import Path
import time
import types


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok, message):
    if not ok:raise ValueError(message)
def atomic(path, value):
    temp=path.with_suffix('.pending')
    with temp.open('w') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    temp.replace(path)
def source(path, name):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe source')
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),m.__dict__)
    return m


def seed_and_snapshot(torch, seed, step):
    """Same registered seed formula, with accelerator failures made explicit."""
    value = seed * 1000003 + step
    random.seed(value)
    torch.manual_seed(value)
    torch.npu.manual_seed_all(value)
    return rng_snapshot(torch)


def rng_snapshot(torch):
    def digest(state):
        return hashlib.sha256(bytes(state.cpu().tolist())).hexdigest()
    return {'python': hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),
            'torch_cpu': digest(torch.get_rng_state()),
            'npu': [digest(state) for state in torch.npu.get_rng_state_all()]}


def equality_diagnostic(torch, a, ga, b, gb):
    """Bounded diagnostic only; exact equality remains the admission rule."""
    names = sorted(ga.keys() & gb.keys())
    differing = []
    mismatched_elements = 0
    largest = 0.
    shapes_equal = True
    for name in names:
        x, y = ga[name], gb[name]
        if torch.equal(x, y):
            continue
        if len(differing) < 8:
            differing.append(name)
        if x.shape != y.shape:
            shapes_equal = False
            continue
        mismatched_elements += int(torch.count_nonzero(x != y).item())
        largest = max(largest, float((x.double() - y.double()).abs().max().item()))
    flags = {'loss_equal': a['loss'] == b['loss'], 'statistics_equal': a['stats'] == b['stats'],
             'gradient_keys_equal': ga.keys() == gb.keys(),
             'gradient_values_equal': not differing and ga.keys() == gb.keys()}
    return {**flags, 'exact': all(flags.values()),
            'loss_abs_difference': abs(a['loss'] - b['loss']),
            'gradient_shapes_equal': shapes_equal, 'first_differing_gradients': differing,
            'gradient_key_count': [len(ga), len(gb)],
            'mismatched_gradient_elements': mismatched_elements,
            'gradient_max_abs_difference': largest,
            'scientific_acceptance': False, 'test_read': False}


def run(plan_path, pin):
    require(sha(plan_path)==pin,'plan changed');plan=json.loads(Path(plan_path).read_text())
    require(plan['schema']=='r3-k2-deferred-sync-benchmark-v1' and plan['test_read'] is False
            and plan['scientific_acceptance'] is False,'scope differs')
    require(plan['protocol']=={'seed':2,'warmup_pairs':3,'measured_pairs':10,'min_measured_seconds':60,
            'exact_loss_and_gradients':True,'minimum_speedup':1.05,'chips':1},'protocol differs')
    require(plan['files'].get(str(Path(__file__).resolve()))==sha(__file__),'benchmark not pinned')
    for filename in plan['files']:
        p=Path(filename)
        require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe dependency')
        require(not any(x=='test' or x.startswith('test.') for x in p.parts),'test dependency forbidden')
    for p,h in plan['files'].items():require(sha(p)==h,'input changed: '+p)
    for key in ('trainer','candidate','transform'):
        require(plan[key] in plan['files'],'required source not pinned')
    builder=source(plan['transform'],'sync_transform')
    require(builder.transform(Path(plan['trainer']).read_bytes())==Path(plan['candidate']).read_bytes(), 'candidate is not exact allowed transformation')
    out=Path(plan['out']);require(not out.exists(),'fresh benchmark output required');out.mkdir()
    import torch
    import torch_npu
    import transformers
    T=source(plan['trainer'],'sync_reference')
    require(T.file_sha256(T.TRAIN_FILE)==plan['files'][T.TRAIN_FILE],'training data changed')
    # Candidate differs only in step_loss, retaining the verified trainer namespace.
    candidate=types.ModuleType('sync_candidate');candidate.__dict__.update(T.__dict__)
    tree=ast.parse(Path(plan['candidate']).read_bytes())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='step_loss')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),plan['candidate'],'exec'),candidate.__dict__)
    args=T.parse_args(['--out',str(out),'--arm','k2','--seed','2','--model-path',plan['model'],
                      '--kernel','ref','--grad-ckpt','--micro-tokens','12000','--max-len','4096',
                      '--expect-pairs','186','--no-merge'])
    tok=transformers.AutoTokenizer.from_pretrained(args.model_path)
    data=T.Data(args);pm,trainable,pairs=T.build_model(args,torch);pm.to(args.device);pm.train()
    core=pm.base_model.model;pad=tok.pad_token_id if tok.pad_token_id is not None else 0
    def evaluate(fn,step):
        pm.zero_grad(set_to_none=True);rng_before=seed_and_snapshot(torch,2,step)
        units=data.step_units(step)[1];torch.npu.synchronize();torch.npu.reset_peak_memory_stats()
        begin=time.perf_counter()
        loss,stats=fn(torch,core,tok,units,'k2',args.device,pad,4096,12000,{},backward=True)
        torch.npu.synchronize();elapsed=time.perf_counter()-begin
        gradients={n:p.grad.detach().cpu().clone() for n,p in trainable if p.grad is not None}
        require(len(gradients)==len(trainable),'missing gradient')
        require(math.isfinite(loss) and all(torch.isfinite(g).all().item() for g in gradients.values()),'nonfinite result')
        return {'loss':loss,'seconds':elapsed,'stats':stats,'reserved_gib':torch.npu.max_memory_reserved()/1024**3,
                'rng_before':rng_before,'rng_after':rng_snapshot(torch)},gradients
    def same(a,ga,b,gb):
        return a['loss']==b['loss'] and a['stats']==b['stats'] and ga.keys()==gb.keys() and all(torch.equal(ga[n],gb[n]) for n in ga)
    reference,gr=evaluate(T.step_loss,0);repeat,gg=evaluate(T.step_loss,0)
    diagnostic=equality_diagnostic(torch,reference,gr,repeat,gg)
    atomic(out/'REFERENCE_REPEAT.json',dict(diagnostic,plan_sha256=pin,
           reference_rng={k:reference[k] for k in ('rng_before','rng_after')},
           repeat_rng={k:repeat[k] for k in ('rng_before','rng_after')}))
    require(same(reference,gr,repeat,gg),'reference repeat not bit-exact; candidate not admissible under this protocol')
    del gr,gg
    rows=[]
    for step in range(13):
        order=('reference','candidate') if step%2==0 else ('candidate','reference');observed={};grads={}
        for name in order:
            observed[name],grads[name]=evaluate(T.step_loss if name=='reference' else candidate.step_loss,step)
        exact=same(observed['reference'],grads['reference'],observed['candidate'],grads['candidate'])
        if not exact:
            atomic(out/'CANDIDATE_MISMATCH.json',dict(
                equality_diagnostic(torch,observed['reference'],grads['reference'],observed['candidate'],grads['candidate']),
                plan_sha256=pin,step=step))
        rows.append({'step':step,'order':order,'exact':exact,**observed})
        atomic(out/'heartbeat.json',{'completed_pairs':len(rows),'total_pairs':13,'last':rows[-1],
                                   'utc_seconds':time.time(),'chips':1,'test_read':False})
        require(exact,'candidate changed loss/gradients/statistics')
        del grads
    measured=rows[3:];seconds={n:sum(x[n]['seconds'] for x in measured) for n in ('reference','candidate')}
    require(min(seconds.values())>=60,'measured window too short')
    speedup=seconds['reference']/seconds['candidate']
    performance={name:{'questions_per_second_per_chip':100/seconds[name],
        'tokens_per_second_per_chip':sum(x[name]['stats']['tokens'] for x in measured)/seconds[name],
        'reserved_gib_peak':max(x[name]['reserved_gib'] for x in measured),'chips':1}
        for name in ('reference','candidate')}
    result={'schema':'r3-k2-sync-benchmark-result-v1','rows':rows,'seconds':seconds,'speedup':speedup,
            'engineering_speed_candidate':speedup>=1.05,'chips':1,'exact_loss_and_gradients':True,
            'performance':performance,'plan_sha256':pin,'scientific_acceptance':False,'test_read':False,
            'limitations':['initial LoRA state, fixed thirteen training steps; not full training trajectory equivalence']}
    atomic(out/'RESULT.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text());rc=1
    try:
        run(a.plan,a.sha256);rc=0
    finally:
        root=Path(plan['out'])
        if root.exists():atomic(root/'EXIT.json',{'exit_code':rc,'plan_sha256':a.sha256,'scientific_acceptance':False,'test_read':False})
