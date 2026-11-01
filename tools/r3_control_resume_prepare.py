"""Prepare a Base/QO/PT trained-state restart package; never launch or approve it.

The frozen contract keeps its original thresholds. Preparation emits an immutable
draft; finalize binds a separate engineering launch plan without granting review.
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
RUN_ROOT=Path('/mnt/cephfs/xingchao/experiments/jev')
ALLOCATION=str(RUN_ROOT/'CHIP-ALLOCATION.json')
ENVIRONMENT={'ASCEND_RT_VISIBLE_DEVICES':'0','HF_HUB_OFFLINE':'1','NGA_R0_CODE':'/workspace/r0_code',
 'PYTHONDONTWRITEBYTECODE':'1','PYTORCH_NPU_ALLOC_CONF':'expandable_segments:True',
 'TASK_QUEUE_ENABLE':'2','TOKENIZERS_PARALLELISM':'false','TRANSFORMERS_OFFLINE':'1'}
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
    arm=plan.get('control_arm');base=INSTRUCT if arm=='K1-PT' else BASE
    require(arm in (None,'K1-QO','K1-PT') and plan.get('model')==base,
            'registered Base/QO/PT source required')
    require(plan.get('schema')=='r3-engineering-k1-plan-v1' and plan.get('seed')==2
            and plan.get('arm','k1')=='k1' and plan.get('execution_scope')=='engineering_only'
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
    draft.update(out=str(out),code=str(code),seed=2,arm='k1',chip=chip,control_arm=plan.get('control_arm'),
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
    result={'schema':'r3-control-resume-preparation-v1','control_arm':plan.get('control_arm'),
            'source_plan':str(source_plan),'source_plan_pin':source_pin,'draft':str(out/'DRAFT.json'),
            'draft_sha256':R.sha(out/'DRAFT.json'),'deployable':False,'scientific_acceptance':False,
            'test_read':False,'checkpoint_state_verified':False,'remaining':draft['remaining']}
    write(out/'PREPARATION.json',result)
    return result


def verify_launch(plan):
    """Validate a complete engineering control restart package before launch."""
    out=safe(plan['out']);code=safe(plan['code'])
    require(code==out/'code' and plan.get('deployable') is True,'control restart not finalized')
    require(plan.get('validation_kind')=='current_k1_resume_contract' and plan.get('seed')==2
            and plan.get('arm')=='k1' and plan.get('control_arm') in (None,'K1-QO','K1-PT'), 'control restart scope differs')
    prep_path=safe(plan['preparation']);require(prep_path==out/'PREPARATION.json','preparation location differs')
    require(plan['files'].get(str(prep_path))==R.sha(prep_path),'preparation not bound')
    prep=R.load(prep_path)
    require(prep.get('schema')=='r3-control-resume-preparation-v1' and prep.get('deployable') is False
            and prep.get('test_read') is False and prep.get('scientific_acceptance') is False,'preparation scope differs')
    draft_path=out/'DRAFT.json'
    require(prep['draft']==str(draft_path) and prep['draft_sha256']==R.sha(draft_path)
            and plan['files'].get(str(draft_path))==R.sha(draft_path),'draft binding differs')
    draft=R.load(draft_path)
    for field in ('out','code','model','train_file','image_sha256','environment','command','seed','chip',
                  'control_arm','validation_kind','schema','authorization','execution_scope','test_read','scientific_acceptance'):
        require(plan.get(field)==draft.get(field),'draft execution differs: '+field)
    require(all(plan['files'].get(p)==h for p,h in draft['files'].items()),'draft dependency binding differs')
    original=source(prep['source_plan'],prep['source_plan_pin'])
    require(R.load(out/'SOURCE_PLAN.json')==original,'source plan snapshot differs')
    require(plan['files'].get(prep['source_plan'])==R.sha(prep['source_plan']),'original source plan unbound')
    for key in ('model','train_file','image_sha256','environment','control_arm'):
        require(plan.get(key)==original.get(key),'source configuration differs: '+key)
    require(plan['environment']==ENVIRONMENT,'control restart environment differs')
    origin=R.load(out/'SOURCE.json');cfg=R.load(out/'CONTRACT.json')
    expected={'steps':20,'replicas':3,'split':10,'factor':1.5,'loss_slack':2.4e-7,
              'weight_relative_l2_slack':1e-7,'test_read':False,'scientific_acceptance':False}
    require(set(cfg)==set(expected)|{'source_step','source_sha256'} and
            all(type(cfg.get(k)) is type(v) and cfg[k]==v for k,v in expected.items()),'control restart contract differs')
    step=cfg['source_step'];require(type(step) is int and 20<=step<3096,'control restart source step differs')
    checkpoint=safe(origin['checkpoint'])
    require(origin=={'training':original['out'],'checkpoint':str(checkpoint),'sha256':cfg['source_sha256'],'step':step}
            and checkpoint==Path(original['out'])/'ckpt'/f'step_{step:06d}.pt','control restart checkpoint owner differs')
    require(R.sha(checkpoint)==cfg['source_sha256']==R.sha(out/'SOURCE.pt')
            and plan['files'].get(str(checkpoint))==cfg['source_sha256'],'control restart checkpoint changed')
    require(plan['files'].get(str(code/'r3_resume_contract.py')) in R.CONTRACT_SHA256,'unrecognized restart contract')
    for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
        require(plan['files'].get(str(code/rel))==original['files'].get(str(Path(original['code'])/rel)),
                'control restart training code differs')
    require(plan.get('run')==str(out.relative_to(RUN_ROOT)) and plan.get('allocation')==ALLOCATION,
            'control restart resource identity differs')
    require(plan.get('container')==container_name(out,plan['control_arm']),'control restart container identity differs')
    require(plan.get('launcher')==str(out/'tools/r3_formal_launcher.py')
            and plan.get('adapter')==str(out/'tools/r3_resource_adapter.py')
            and plan.get('driver')==str(code/'r3_formal_driver.py'),'control restart tool paths differ')
    for path,pin in plan['files'].items():require(R.sha(path)==pin,'control restart dependency changed')
    return plan


def container_name(out,arm):
    import hashlib
    return 'nga-r3-resume-'+(arm or 'base').lower()+'-'+hashlib.sha256(str(out).encode()).hexdigest()[:16]


def finalize(preparation_path,preparation_pin):
    path=safe(preparation_path);require(R.sha(path)==preparation_pin,'preparation pin differs')
    prep=R.load(path);out=path.parent
    require(path.name=='PREPARATION.json' and out.is_relative_to(RUN_ROOT),'preparation root differs')
    require(not (out/'plan.json').exists() and not (out/'tools').exists(),'new finalization required')
    require(R.sha(prep['draft'])==prep['draft_sha256'],'draft pin differs')
    draft=R.load(prep['draft']);original=source(prep['source_plan'],prep['source_plan_pin'])
    require(original['environment']==ENVIRONMENT,'control restart environment differs')
    tools=out/'tools';tools.mkdir()
    for name in ('r3_formal_launcher.py','r3_resource_adapter.py','r3_control_resume_prepare.py',
                 'r3_resume_evidence.py','r3_resume_contract.py'):
        shutil.copyfile(HERE/name,tools/name)
    plan=dict(draft);plan['files']=dict(draft['files'])
    for file in (path,out/'DRAFT.json',*tools.iterdir(),Path(prep['source_plan']),Path(R.load(out/'SOURCE.json')['checkpoint'])):
        plan['files'][str(file)]=R.sha(file)
    seeds=[2] if plan['control_arm']=='K1-QO' else [2,3]
    plan.update(deployable=True,preparation=str(path),run=str(out.relative_to(RUN_ROOT)),allocation=ALLOCATION,
                container=container_name(out,plan['control_arm']),launcher=str(tools/'r3_formal_launcher.py'),
                adapter=str(tools/'r3_resource_adapter.py'),driver=str(out/'code/r3_formal_driver.py'),
                control={'control_arm':plan['control_arm'],'candidate_for_adoption':False,
                         'primary_input_mode':'drop' if plan['control_arm']=='K1-QO' else 'full','registered_seeds':seeds})
    if plan['control_arm'] is None:
        plan.pop('control')
        plan['evaluation']={'candidate_test_forbidden':True,'formal_acceptance_requires_new_review':True}
    else:
        plan['evaluation']=dict(plan['control'],candidate_test_forbidden=True)
    plan['remaining']=['actual bounded NPU restart execution','independent CPU tensor reconstruction','formal eligibility and review']
    verify_launch(plan)
    write(out/'plan.json',plan)
    command=['python3','-B','-P',plan['launcher'],'start','--plan',str(out/'plan.json'),'--sha256',R.identity(plan)]
    import shlex
    (out/'RELAUNCH.sh').write_text(shlex.join(command)+'\n')
    result={'schema':'r3-control-resume-launch-preparation-v1','plan':str(out/'plan.json'),
            'plan_sha256':R.identity(plan),'deployable':True,'scientific_acceptance':False,
            'test_read':False,'command':command,'checkpoint_state_verified':False}
    write(out/'LAUNCH_PREPARATION.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True)
    prep=sub.add_parser('prepare')
    for name in ('source-plan','source-pin','checkpoint','checkpoint-pin','out'):prep.add_argument('--'+name,required=True)
    prep.add_argument('--source-step',type=int,required=True);prep.add_argument('--chip',type=int,required=True)
    final=sub.add_parser('finalize');final.add_argument('--preparation',required=True);final.add_argument('--sha256',required=True)
    a=p.parse_args()
    result=finalize(a.preparation,a.sha256) if a.operation=='finalize' else prepare(a.source_plan,a.source_pin,a.checkpoint,a.checkpoint_pin,a.source_step,a.out,a.chip)
    print(json.dumps(result,indent=2))
