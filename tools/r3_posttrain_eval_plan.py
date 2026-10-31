#!/usr/bin/env python3
"""Bind completed training artifacts to dev/calibration evaluation specifications.

CPU-only, detached watcher supported. Never launches, claims a chip or opens test.
Output specifications require an execution review and resource assignment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


BASE_MODEL='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'
PT_MODEL='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'


def semantic_arm(plan, manifest):
    """Control identity comes from completed training, never an output label."""
    args=manifest.get('args',{});control=plan.get('control_arm')
    is_control=control is not None or args.get('drop_state') or plan['model']==PT_MODEL
    if not is_control:return plan.get('arm','k1').upper()
    if control not in ('K1-QO','K1-PT') or plan.get('arm')!='k1' or manifest.get('arm')!='k1' or args.get('arm')!='k1':
        raise RuntimeError('control training objective or explicit identity differs')
    if args.get('model_path')!=plan['model'] or manifest.get('model_path')!=plan['model']:
        raise RuntimeError('control training model differs')
    if type(args.get('seed')) is not int or args['seed']!=plan.get('seed'):
        raise RuntimeError('control training seed differs')
    command=plan.get('command',[])
    if control=='K1-QO':
        if plan['model']!=BASE_MODEL or args['seed']!=2 or args.get('drop_state') is not True or command.count('--drop-state')!=1:
            raise RuntimeError('QO requires Base seed 2 and dropped training state')
    elif plan['model']!=PT_MODEL or args['seed'] not in (2,3) or args.get('drop_state') is not False or '--drop-state' in command:
        raise RuntimeError('PT requires instruct seeds 2/3 with full training state')
    return control


def prepare(training, closure, out):
    terminal=training/'TRAIN_EXIT.json'
    if not terminal.exists():return {'status':'waiting_training'}
    end=load(terminal)
    if end['exit_code']!=0:return {'status':'training_failed','exit_code':end['exit_code']}
    plan=load(training/'plan.json');manifest=load(training/'manifest.json')
    if plan.get('stop_after') or manifest.get('summary',{}).get('final_step')!=3116:
        return {'status':'not_complete_training','reason':'probe or missing final 3116-step summary'}
    evaluation_arm=semantic_arm(plan,manifest)
    adapter=training/'adapter'
    required=[adapter/'adapter_config.json',adapter/'adapter_model.safetensors']
    if not all(p.is_file() for p in required):raise RuntimeError('successful training lacks complete adapter')
    config=load(closure/'manifest.json')
    files={str(terminal):sha(terminal),str(training/'manifest.json'):sha(training/'manifest.json')}
    for path,digest in config['data'].items():
        if '/test' in path or sha(path)!=digest:raise RuntimeError('data differs or test data included')
        files[path]=digest
    for entry in config['code'].values():
        if sha(entry['snapshot'])!=entry['sha256']:raise RuntimeError('evaluator code changed')
        files[entry['snapshot']]=entry['sha256']
    for path,digest in plan['files'].items():
        if path.startswith(plan['model']+'/'):
            if sha(path)!=digest:raise RuntimeError('base model changed since training')
            files[path]=digest
    for path in adapter.iterdir():
        if path.is_symlink():raise RuntimeError('adapter symlink')
        if path.is_file():files[str(path)]=sha(path)
    command=list(config['command_template'])
    replacements={'<FROZEN_BASE_MODEL>':plan['model'],'<COMPLETED_ADAPTER>':str(adapter),
                  '<FRESH_EVAL_OUTPUT>':str(out/'results'),'<FRESH_IDENTITY_CACHE>':str(out/'identity')}
    command=[replacements.get(x,x) for x in command]
    command[command.index('--arm')+1]=evaluation_arm
    if evaluation_arm in ('K1-QO','K1-PT'):
        files[str(training/'plan.json')]=sha(training/'plan.json')
    spec={'schema':'r3-posttrain-dev-spec-v1','training':str(training),'training_exit':end,
          'training_variant': {'arm':evaluation_arm.lower(), 'k2_impl':plan.get('k2_impl','rows'),
                               'seed':manifest.get('args',{}).get('seed'),
                               'training_plan_sha256':sha(training/'plan.json'),
                               'pooling_policy':'never pool shared and rows implementations as seeds of one candidate'},
          'evaluation_profile':config.get('evaluation_profile', 'track_k'),
          'command':command,'files':files,'code_mounts':config['mounts'],
          'readonly_data_mounts':list(config['data']), 'model':plan['model'],'adapter':str(adapter),
          'image_sha256':plan['image_sha256'],'network':'none','test_read':False,
          'scientific_acceptance':False,'execution_review':'PENDING','chip_assignment':'PENDING',
          'scope':config.get('scope','Track K dev/calibration; Track T selection evidence still required')}
    out.mkdir(parents=True,exist_ok=True)
    with (out/'plan.json').open('x') as f:json.dump(spec,f,indent=2);f.write('\n')
    return {'status':'prepared','plan':str(out/'plan.json'),'sha256':sha(out/'plan.json')}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--training',action='append',required=True)
    ap.add_argument('--closure',required=True);ap.add_argument('--out',required=True);ap.add_argument('--watch',action='store_true')
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    states={}
    while True:
        for training in map(Path,a.training):
            key=training.parent.name+'-'+training.name
            if states.get(key,{}).get('status') in ('prepared','training_failed','not_complete_training'):continue
            target=out/key
            try:
                if (target/'plan.json').exists():
                    states[key]={'status':'prepared','plan':str(target/'plan.json'),'sha256':sha(target/'plan.json')}
                else:states[key]=prepare(training,Path(a.closure),target)
            except Exception as e:states[key]={'status':'needs_repair','error':str(e)}
        temp=out/'digest.pending';temp.write_text(json.dumps({'utc_seconds':time.time(),'jobs':states},indent=2)+'\n');temp.replace(out/'digest.json')
        if not a.watch or all(x['status'] in ('prepared','training_failed','not_complete_training') for x in states.values()):return
        time.sleep(30)


if __name__=='__main__':main()
