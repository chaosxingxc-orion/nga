#!/usr/bin/env python3
"""Offline qualification readiness and pinned CPU invocation; never grants authority.

The immutable config names prospective artifacts. Presence is only a wake hint.
Only the unchanged qualifier verifies a separately, independently pinned complete
bundle/adjudication. The watcher stops at READY_FOR_PINNED_CONSUMPTION.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import types


def require(ok, reason):
    if not ok: raise ValueError(reason)


def safe(value):
    p=Path(value)
    require(p.is_absolute() and '..' not in p.parts and str(p)==str(value)
            and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    require(not any(x.lower().split('.')[0]=='test' for x in p.parts), 'TEST path forbidden')
    return p


def digest(raw): return hashlib.sha256(raw).hexdigest()


def read(path, pin=None):
    raw=safe(path).read_bytes()
    require(pin is None or digest(raw)==pin, 'pin changed: '+str(path))
    return raw


def load(path, pin=None): return json.loads(read(path,pin))


def module(ref):
    raw=read(ref['path'],ref['sha256']);obj=types.ModuleType(Path(ref['path']).stem)
    obj.__file__=ref['path'];exec(compile(raw,ref['path'],'exec'),obj.__dict__);return obj


def write(path, doc, exclusive=False):
    path=safe(path);raw=(json.dumps(doc,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    temporary=path if exclusive else path.with_suffix('.pending')
    with temporary.open('xb' if exclusive else 'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if not exclusive:temporary.replace(path)


def verify(path,pin):
    config=load(path,pin)
    require(config.get('schema')=='r3-dev-qualification-service-v1'
            and config.get('branch')=='firstK1' and config.get('test_read') is False
            and config.get('scientific_acceptance') is False
            and config.get('activation_authorized') is False,'configuration scope differs')
    require(config['controller']==str(Path(__file__).resolve())
            and digest(read(config['controller']))==config['controller_sha256'],'controller differs')
    require(type(config['poll_interval_seconds']) is int and config['poll_interval_seconds']>=600,'poll interval differs')
    require(set(config['members'])=={'primary_s2','primary_s3','samechip_s2','diffchip_s2',
                                   'qo_s2','pt_s2','pt_s3','k0_base','k0_instruct'},'campaign membership differs')
    for name in ('qualifier','wake_source'):
        ref=config[name];require(set(ref)=={'path','sha256'},'source ref differs');read(ref['path'],ref['sha256'])
    for path,pin in config['immutable_files'].items():read(path,pin)
    for name,member in config['members'].items():
        require(member['arm']==('K0' if name.startswith('k0_') else 'K1-QO' if name=='qo_s2' else 'K1-PT' if name.startswith('pt_') else 'K1'),'member arm differs')
        require(member.get('seed')==(None if name.startswith('k0_') else 3 if name.endswith('s3') else 2),'member seed differs')
        if not name.startswith('k0_'):
            p=load(member['plan']['path'],member['plan']['sha256'])
            require(p['out']==member['training'] and p['seed']==member['seed'],'training binding differs')
        for field in ('evaluation_out','report','execution','descriptor'):safe(member[field])
        require(member['report']==str(Path(member['evaluation_out'])/'results/selection_report.json')
                and member['execution']==str(Path(member['evaluation_out'])/'execution.json'),'evaluation output differs')
    required=config['required_paths']
    require(required and len({x['path'] for x in required})==len(required),'duplicate prerequisite')
    for item in required:
        require(set(item)=={'path','member','purpose'} and item['member'] in set(config['members'])|{'campaign'},'prerequisite shape differs')
        safe(item['path']);require(item['purpose'],'prerequisite purpose missing')
    for field in ('bundle_path','adjudication_path','state_root'):safe(config[field])
    allowed={'EXIT.json','ENGINEERING_EVAL_EXIT.json','TRAIN_EXIT.json','EVAL_COMPLETE.track_kt.json','RELEASE.json','SUPERVISOR_DONE.json'}
    require(all(safe(p).name in allowed for p in config['event_wake_paths']),'wake event differs')
    return config


def status(config):
    missing=[item for item in config['required_paths'] if not safe(item['path']).is_file()]
    return {'schema':'r3-dev-qualification-readiness-v1','status':'WAIT' if missing else 'READY_FOR_PINNED_CONSUMPTION',
            'missing':missing,'present_count':len(config['required_paths'])-len(missing),
            'required_count':len(config['required_paths']),'test_read':False,'scientific_acceptance':False,
            'candidate_eligibility_granted':False,'activation_authorized':False,
            'scope':'Presence only; no producer result or origin authenticated. Complete externally pinned qualifier invocation remains required.'}


def bind_bundle(config,bundle):
    require(bundle.get('branch')==config['branch'] and set(bundle.get('entries',{}))==set(config['members']), 'bundle campaign differs')
    for name,member in config['members'].items():
        entry=bundle['entries'][name]
        require(entry.get('arm')==member['arm'] and entry.get('seed')==member.get('seed')
                and entry.get('report')==member['report'] and entry.get('execution')==member['execution'],'bundle member differs: '+name)
        require(entry.get('model',{}).get('base_path')==member['checkpoint'],'bundle checkpoint differs: '+name)
        if 'plan' in member:
            require(entry.get('plan')==member['plan']['path']
                    and bundle['files'].get(entry['plan'])==member['plan']['sha256'],'bundle training differs')
    for field in ('source_applicability','schedule','role_validator','resource_validator','selection_report_source'):
        require(bundle.get(field)==config[field],'bundle source binding differs: '+field)


def consume(config,bundle_pin,adjudication_pin,output):
    # Pins are explicit caller arguments. Never derive an authority pin from a
    # producer file or turn readiness into a fabricated independent approval.
    bundle=load(config['bundle_path'],bundle_pin);load(config['adjudication_path'],adjudication_pin)
    bind_bundle(config,bundle)
    qualifier=module(config['qualifier'])
    return qualifier.main(['--bundle',config['bundle_path'],'--bundle-sha256',bundle_pin,
        '--adjudication',config['adjudication_path'],'--adjudication-sha256',adjudication_pin,'--output',str(safe(output))])


def activation(config,path,pin,ref):
    value=load(ref['path'],ref['sha256'])
    require(value.get('schema')=='r3-dev-qualification-watch-activation-v1'
            and value.get('config_sha256')==pin and value.get('controller_sha256')==config['controller_sha256']
            and value.get('activation_authorized') is True and value.get('test_read') is False
            and value.get('scientific_acceptance') is False,'watch activation differs')
    review=load(value['review']['path'],value['review']['sha256'])
    receipt=load(value['parent_receipt']['path'],value['parent_receipt']['sha256'])
    require(review.get('verdict')=='PASS' and review.get('requested_model')=='gpt-6-astra'
            and review.get('config_sha256')==pin and review.get('controller_sha256')==config['controller_sha256']
            and receipt.get('review')==value['review'] and receipt.get('completion_received_by_parent') is True, 'watch exact review binding differs')


def watch(path,pin,activation_ref):
    config=verify(path,pin);activation(config,path,pin,activation_ref)
    state=safe(config['state_root']);state.mkdir(parents=True,exist_ok=True)
    require(not (state/'EXIT.json').exists(),'terminal watcher cannot restart')
    with (state/'LOCK').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        write(state/'RELAUNCH.json',{'command':[sys.executable,'-B','-P',config['controller'],'watch','--config',str(path),'--sha256',pin,'--activation',activation_ref['path'],'--activation-sha256',activation_ref['sha256']]})
        wake=module(config['wake_source']).CompletionWake(config['event_wake_paths'])
        try:
            tick=0
            while True:
                config=verify(path,pin);activation(config,path,pin,activation_ref)
                result=status(config);tick+=1;result.update(utc=dt.datetime.now(dt.timezone.utc).isoformat(),tick=tick)
                write(state/'digest.json',result);write(state/'heartbeat.json',{'utc':result['utc'],'tick':tick,'missing_count':len(result['missing'])})
                print(json.dumps({'utc':result['utc'],'tick':tick,'status':result['status'],'missing_count':len(result['missing'])}),flush=True)
                if result['status']!='WAIT':
                    write(state/'EXIT.json',dict(result,exit_code=0),exclusive=True);return 0
                wake.wait(config['poll_interval_seconds'])
        except BaseException as exc:
            write(state/'EXIT.json',{'exit_code':1,'status':'FAILED','error':type(exc).__name__+': '+str(exc),'test_read':False},exclusive=True)
            raise
        finally:wake.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('op',choices=('verify','inspect','consume','watch'))
    parser.add_argument('--config',required=True);parser.add_argument('--sha256',required=True)
    for field in ('bundle-sha256','adjudication-sha256','output','activation','activation-sha256'):parser.add_argument('--'+field)
    args=parser.parse_args(argv);config=verify(args.config,args.sha256)
    if args.op=='watch':
        require(args.activation and args.activation_sha256,'independent watch activation required')
        return watch(args.config,args.sha256,{'path':args.activation,'sha256':args.activation_sha256})
    if args.op=='consume':
        require(args.bundle_sha256 and args.adjudication_sha256 and args.output,'independent consumer pins/output required')
        return consume(config,args.bundle_sha256,args.adjudication_sha256,args.output)
    result=status(config) if args.op=='inspect' else {'status':'VALID_CONFIG','test_read':False,'activation_authorized':False}
    if args.output:write(args.output,result,exclusive=True)
    else:print(json.dumps(result,indent=2))
    return 2 if result['status']=='WAIT' else 0


if __name__=='__main__':raise SystemExit(main())
