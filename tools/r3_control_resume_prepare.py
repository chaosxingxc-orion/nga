"""Prepare a QO/PT trained-state restart package; never launch or approve it.

The frozen contract keeps its original thresholds. Current general launcher
cannot launch control recovery plans, so the generated draft remains explicitly
nondeployable until a dedicated reviewed launcher contract is implemented.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
BASE='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'
INSTRUCT='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'
IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
def module(name):
    s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
R=module('r3_resume_evidence');C=module('r3_resume_contract')


def require(ok,reason):
    if not ok:raise ValueError(reason)


def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),
            'absolute nonsymlink path required')
    return p


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')


def source(path,pin):
    path=safe(path);plan=R.load(path)
    require(R.identity(plan)==pin,'source plan identity differs')
    arm=plan.get('control_arm');base=BASE if arm=='K1-QO' else INSTRUCT
    require(arm in ('K1-QO','K1-PT') and plan.get('model')==base,
            'registered QO/PT source required')
    require(plan.get('schema')=='r3-engineering-k1-plan-v1' and plan.get('seed')==2
            and plan.get('arm')=='k1' and plan.get('execution_scope')=='engineering_only'
            and plan.get('test_read') is False and plan.get('scientific_acceptance') is False
            and plan.get('image_sha256')==IMAGE and not plan.get('validation_kind')
            and plan.get('authorization')=='user_execute_engineering_when_ready_20261031',
            'source must be seed2 engineering control training')
    require(path.parent==safe(plan['out']),'source plan directory differs')
    cmd=['python3','-P','/workspace/train_r3.py','--out',plan['out'],'--arm','k1','--seed','2',
         '--model-path',base,'--kernel','ref','--grad-ckpt','--micro-tokens','12000','--max-len','4096',
         '--save-every','200','--no-merge','--epochs','2','--total-steps','3116','--expect-pairs','186']
    if arm=='K1-QO':cmd+=['--drop-state']
    require(plan['command']==cmd,'source control training recipe differs')
    C.validate_source_plan(plan)
    for file,digest in plan['files'].items():
        p=safe(file)
        require(p.name not in ('test.jsonl','test.variants.jsonl')
                and not ('test' in p.parts and p.suffix in ('.jsonl','.parquet')),
                'test dependency forbidden')
        require(R.sha(p)==digest,'source dependency changed')
    code=safe(plan['code'])
    require({str(p) for p in code.rglob('*') if p.is_file()}==
            {p for p in plan['files'] if p.startswith(str(code)+'/')},'source code inventory differs')
    model=safe(base)
    require({str(p):R.sha(p) for p in model.rglob('*') if p.is_file()}==
            {p:h for p,h in plan['files'].items() if p.startswith(base+'/')},'source model inventory differs')
    require(plan['train_file'] in plan['files'],'source train file unbound')
    return plan


def prepare(source_plan,source_pin,checkpoint,checkpoint_pin,source_step,out,chip):
    plan=source(source_plan,source_pin)
    require(type(source_step) is int and 20<=source_step<3096,'invalid trained-state step')
    require(type(chip) is int and chip in range(8),'invalid chip')
    checkpoint=safe(checkpoint);out=safe(out)
    require(checkpoint==Path(plan['out'])/'ckpt'/f'step_{source_step:06d}.pt','checkpoint owner/step differs')
    require(R.sha(checkpoint)==checkpoint_pin,'checkpoint pin differs')
    contract=HERE/'r3_resume_contract.py'
    require(R.sha(contract) in R.CONTRACT_SHA256,'unrecognized frozen contract')
    require(not out.exists(),'new output directory required')
    require(not any(out.is_relative_to(Path(plan[k])) for k in ('out','model','code')),
            'output overlaps training source')
    out.mkdir(parents=True);code=out/'code';code.mkdir()
    for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
        src=safe(Path(plan['code'])/rel)
        require(plan['files'].get(str(src))==R.sha(src),'source code not pinned')
        dst=code/rel;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst)
    shutil.copyfile(contract,code/contract.name)
    driver=safe(plan['driver']);require(plan['files'].get(str(driver))==R.sha(driver),'source driver unbound')
    shutil.copyfile(driver,code/'r3_formal_driver.py')
    shutil.copyfile(checkpoint,out/'SOURCE.pt')
    write(out/'SOURCE_PLAN.json',plan)
    write(out/'SOURCE.json',{'training':plan['out'],'checkpoint':str(checkpoint),'sha256':checkpoint_pin,'step':source_step})
    config={'source_sha256':checkpoint_pin,'source_step':source_step,'steps':20,'replicas':3,'split':10,
            'factor':1.5,'loss_slack':2.4e-7,'weight_relative_l2_slack':1e-7,
            'test_read':False,'scientific_acceptance':False}
    write(out/'CONTRACT.json',config)
    files={str(p):R.sha(p) for p in out.rglob('*') if p.is_file()}
    files.update({p:h for p,h in plan['files'].items() if p==plan['train_file'] or p.startswith(plan['model']+'/')})
    draft={k:plan[k] for k in ('schema','model','train_file','image_sha256','environment','authorization','execution_scope','test_read','scientific_acceptance')}
    draft.update(out=str(out),code=str(code),seed=2,arm='k1',chip=chip,control_arm=plan['control_arm'],
        validation_kind='current_k1_resume_contract',command=['python3','-P','/workspace/r3_resume_contract.py','--out',str(out)],
        files=files,review_sha256='PENDING',deployable=False,
        remaining=['dedicated control-recovery launcher admission and exact retained-container mounts',
                   'runtime checkpoint step/state verification and actual NPU execution',
                   'independent CPU tensor reconstruction and exact-plan review'])
    # Preparation is not a launch plan: no resource identity or launcher supplied.
    write(out/'DRAFT.json',draft)
    source(source_plan,source_pin)
    require(R.sha(checkpoint)==checkpoint_pin==R.sha(out/'SOURCE.pt'),'checkpoint changed during preparation')
    for p,digest in files.items():require(R.sha(p)==digest,'prepared dependency changed')
    result={'schema':'r3-control-resume-preparation-v1','control_arm':plan['control_arm'],
            'source_plan':str(source_plan),'source_plan_pin':source_pin,'draft':str(out/'DRAFT.json'),
            'draft_sha256':R.sha(out/'DRAFT.json'),'deployable':False,'scientific_acceptance':False,
            'test_read':False,'checkpoint_state_verified':False,'remaining':draft['remaining']}
    write(out/'PREPARATION.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source-plan','source-pin','checkpoint','checkpoint-pin','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-step',type=int,required=True);p.add_argument('--chip',type=int,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.source_plan,a.source_pin,a.checkpoint,a.checkpoint_pin,a.source_step,a.out,a.chip),indent=2))
