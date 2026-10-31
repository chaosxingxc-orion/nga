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


def prepare(training, closure, out):
    terminal=training/'TRAIN_EXIT.json'
    if not terminal.exists():return {'status':'waiting_training'}
    end=load(terminal)
    if end['exit_code']!=0:return {'status':'training_failed','exit_code':end['exit_code']}
    plan=load(training/'plan.json');manifest=load(training/'manifest.json')
    if plan.get('stop_after') or manifest.get('summary',{}).get('final_step')!=3116:
        return {'status':'not_complete_training','reason':'probe or missing final 3116-step summary'}
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
    command[command.index('--arm')+1]=plan.get('arm','k1').upper()
    spec={'schema':'r3-posttrain-dev-spec-v1','training':str(training),'training_exit':end,
          'command':command,'files':files,'code_mounts':config['mounts'],
          'readonly_data_mounts':list(config['data']), 'model':plan['model'],'adapter':str(adapter),
          'image_sha256':plan['image_sha256'],'network':'none','test_read':False,
          'scientific_acceptance':False,'execution_review':'PENDING','chip_assignment':'PENDING',
          'scope':'clean dev/calibration readouts; full variants and Track T remain required for selection'}
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
