"""Retained CPU reconstruction after a completed control restart; no approval.

prepare freezes receipt-validated inputs only after observing actual NPU exit
and release. start is idempotent and never relaunches an ambiguous intent.
An external finite queue may call prepare/start/observe at its normal cadence.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
VERIFIER='0b3963432140b0860dad92f14f5f8079b884d9d4e6e5114d7cd902f10254803e'
# New preparations require the strengthened complete-Docker-command validator.
# Deployed frozen generations retain their original pins and require a new
# reconstruction generation for acceptance under this implementation.
VALIDATOR='b205ba9fa9970c16a58a9869bd85962493b48f05e82671ec1733da9c11b063c2'

def require(ok,why):
    if not ok:raise ValueError(why)

def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p

def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<22),b''):h.update(block)
    return h.hexdigest()

def load(path):return json.loads(safe(path).read_text())

def atomic(path,value):
    p=safe(path);tmp=p.with_suffix('.pending')
    with tmp.open('w') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.chmod(0o644);tmp.replace(p)

def module(path):
    s=importlib.util.spec_from_file_location('control_cpu_receipts',path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def inspect(name):
    r=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower():return None
        raise RuntimeError('uncertain container observation')
    return json.loads(r.stdout)[0]

def released(plan_path,pin,validator):
    plan=load(plan_path);root=safe(plan_path).parent
    require(validator.identity(plan)==pin and plan.get('control_arm') in ('K1-QO','K1-PT')
            and plan.get('validation_kind')=='current_k1_resume_contract', 'control restart identity differs')
    target=root/'SOURCE_PLAN.json'
    files=validator.validate(plan_path,pin,load(target))
    end=load(root/'TRAIN_EXIT.json');attempt=root/'attempts'/str(end['attempt'])
    supervisor_path=root/'SUPERVISOR_RECEIPT.json';supervisor=load(supervisor_path)
    require(supervisor['command'][1:]==['-P',plan['launcher'],'supervise','--plan',str(plan_path),
            '--sha256',pin,'--attempt',str(end['attempt'])],'newer or different restart supervisor')
    launch=load(attempt/'LAUNCH_RECEIPT.json');proof=load(attempt/'RELEASE.json')
    actual=inspect(plan['container']+'-a'+str(end['attempt']))
    require(actual and actual['Id']==launch['id']==proof['container_id'] and actual['Image']==IMAGE,
            'retained restart identity differs')
    require(actual['State']['Status'] in ('exited','dead') and actual['State']['ExitCode']==end['exit_code']==0,
            'restart not actually complete')
    require(not actual['HostConfig'].get('AutoRemove',True),'restart container not retained')
    require(actual['Config'].get('Entrypoint')==['python3']
            and actual['Config'].get('Cmd')==['-P','/workspace/r3_formal_driver.py','--plan',str(plan_path),
                                            '--attempt',str(end['attempt'])], 'actual restart command differs')
    require({d['PathOnHost'] for d in actual['HostConfig'].get('Devices',[])}==
            {'/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(plan['chip'])},
            'actual restart devices differ')
    require(load(root/'TRAIN_EXIT.json')==end and load(supervisor_path)==supervisor,'restart changed during observation')
    files[str(supervisor_path)]=sha(supervisor_path)
    return plan,target,files,{'container_id':actual['Id'],'release_sha256':sha(attempt/'RELEASE.json')}

def prepare(plan_path,pin,out,container):
    require(re.fullmatch('[a-z0-9][a-z0-9_.-]{0,100}',container) is not None,'invalid CPU container name')
    validator_path=HERE/'r3_resume_evidence.py';verifier_path=HERE/'r3_resume_recompute.py'
    require(sha(validator_path)==VALIDATOR and sha(verifier_path)==VERIFIER,'CPU implementation differs')
    R=module(validator_path);plan,target,files,release=released(plan_path,pin,R)
    out=safe(out)
    require(not out.exists(),'new CPU output required')
    for filename in files:
        p=safe(filename)
        require(not p.is_relative_to(out) and not out.is_relative_to(p.parent),'CPU output overlaps input')
    out.mkdir(parents=True);code=out/'code';code.mkdir()
    for name in ('r3_control_resume_cpu.py','r3_resume_evidence.py','r3_resume_recompute.py'):
        shutil.copyfile(HERE/name,code/name)
    files={**files,str(target):sha(target),str(safe(plan_path)):sha(plan_path)}
    source=load(target)
    # The original target code is reopened by the pinned receipt validator.
    for relative in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
        p=safe(Path(source['code'])/relative);digest=sha(p)
        require(source['files'].get(str(p))==digest,'original target code changed')
        files[str(p)]=digest
    frozen={str(p):sha(p) for p in code.iterdir()}
    config={'schema':'r3-control-resume-cpu-v1','out':str(out),'container':container,'image':IMAGE,
        'plan':str(safe(plan_path)),'plan_sha256':pin,'target':str(target),'target_sha256':sha(target),
        'files':files,'tools':frozen,'release':release,'scientific_acceptance':False,'test_read':False}
    atomic(out/'CONFIG.json',config)
    config_path=out/'CONFIG.json';config_pin=sha(config_path)
    atomic(out/'RELAUNCH.json',{'command':[sys.executable,'-B','-P',str(code/'r3_control_resume_cpu.py'),
        'start','--config',str(config_path),'--sha256',config_pin]})
    return {'config':str(config_path),'sha256':config_pin,'scientific_acceptance':False}

def verify(path,pin):
    require(sha(path)==pin,'CPU config changed');c=load(path)
    require(c.get('schema')=='r3-control-resume-cpu-v1' and c.get('image')==IMAGE
            and c.get('scientific_acceptance') is False and c.get('test_read') is False,'CPU scope differs')
    require(safe(path)==safe(c['out'])/'CONFIG.json','CPU config ownership differs')
    require(c['tools'].get(str(Path(c['out'])/'code/r3_resume_recompute.py'))==VERIFIER
            and c['tools'].get(str(Path(c['out'])/'code/r3_resume_evidence.py'))==VALIDATOR,'CPU tools differ')
    require(set(c['tools'])=={str(Path(c['out'])/'code'/name) for name in
            ('r3_control_resume_cpu.py','r3_resume_recompute.py','r3_resume_evidence.py')},'CPU tool inventory differs')
    require(str(Path(__file__).resolve()) in c['tools'], 'CPU controller outside frozen closure')
    for filename,digest in {**c['files'],**c['tools']}.items():
        require(sha(filename)==digest,'CPU input changed: '+filename)
    return c

def command(c,path,pin):
    out=Path(c['out']);mounts={**{p:False for p in c['files']},**{p:False for p in c['tools']},str(out):True,str(path):False}
    cmd=['docker','run','-d','--pull=never','--name',c['container'],'--network=none',
         '-e','TORCH_DEVICE_BACKEND_AUTOLOAD=0']
    for p,rw in sorted(mounts.items(),key=lambda x:(len(Path(x[0]).parts),x[0])):
        cmd+=['--mount','type=bind,src='+p+',dst='+p+('' if rw else ',readonly')]
    args=['-B','-P',str(out/'code/r3_control_resume_cpu.py'),'worker','--config',str(path),'--sha256',pin]
    return cmd+['--entrypoint','python3',IMAGE,*args],mounts,args

def check_container(c,path,pin,actual):
    _,mounts,args=command(c,path,pin)
    require(actual['Image']==IMAGE and actual['Name'].lstrip('/')==c['container'],'CPU identity differs')
    host=actual['HostConfig'];cfg=actual['Config']
    require(host.get('AutoRemove') is False and not host.get('Devices') and not host.get('Privileged')
            and host.get('NetworkMode')=='none','CPU device/lifecycle differs')
    require(cfg.get('Entrypoint')==['python3'] and cfg.get('Cmd')==args
            and 'TORCH_DEVICE_BACKEND_AUTOLOAD=0' in cfg.get('Env',[]),'CPU command/environment differs')
    seen=actual.get('Mounts',[])
    require(len(seen)==len(mounts) and len({m['Destination'] for m in seen})==len(mounts)
        and all(m.get('Type')=='bind' and m['Source']==m['Destination'] and m['Source'] in mounts
                and m['RW'] is mounts[m['Source']] for m in seen),'CPU mounts differ')

def observe(path,pin):
    c=verify(path,pin);out=Path(c['out']);actual=inspect(c['container'])
    if actual is None:return {'status':'needs_repair','reason':'container absent; no automatic restart'}
    check_container(c,path,pin,actual)
    receipt=out/'LAUNCH_RECEIPT.json'
    if receipt.exists():require(load(receipt)['id']==actual['Id'],'CPU generation differs')
    if actual['State']['Status'] not in ('exited','dead'):return {'status':'running','id':actual['Id']}
    marker=out/'EXIT.json'
    if not marker.exists():
        return {'status':'needs_repair','reason':'container terminal without worker marker','id':actual['Id']}
    end=load(marker)
    require(end.get('exit_code')==actual['State']['ExitCode'] and end.get('config_sha256')==pin,'CPU terminal differs')
    if end['exit_code']==0:
        require(end.get('result_sha256')==sha(out/'RECOMPUTED.json'),'CPU result changed')
    return {'status':'done' if end['exit_code']==0 else 'failed','exit_code':end['exit_code'],'id':actual['Id']}

def start(path,pin):
    c=verify(path,pin);out=Path(c['out'])
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        intent=out/'START_INTENT.json'
        if intent.exists():return observe(path,pin)
        require(inspect(c['container']) is None,'CPU container name already exists')
        R=module(out/'code/r3_resume_evidence.py');released(c['plan'],c['plan_sha256'],R)
        cmd,_,_=command(c,path,pin);atomic(intent,{'command':cmd,'config_sha256':pin,'utc_seconds':time.time()})
        with (out/'launch.log').open('ab') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        actual=inspect(c['container']);require(actual is not None,'CPU launch observation uncertain')
        check_container(c,path,pin,actual);atomic(out/'LAUNCH_RECEIPT.json',{'id':actual['Id'],'config_sha256':pin})
        return {'status':'started','id':actual['Id']}

def worker(path,pin):
    out=safe(path).parent;rc=125
    try:
        c=verify(path,pin);code=out/'code'
        cmd=['python3','-B','-P',str(code/'r3_resume_recompute.py'),'--plan',c['plan'],
            '--plan-sha256',c['plan_sha256'],'--target',c['target'],'--target-sha256',c['target_sha256'],
            '--validator',str(code/'r3_resume_evidence.py'),'--validator-sha256',VALIDATOR,'--output',str(out/'RECOMPUTED.json')]
        with (out/'verification.log').open('ab',buffering=0) as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            while p.poll() is None:
                atomic(out/'heartbeat.json',{'stage':'reconstructing','pid':p.pid,'utc_seconds':time.time()})
                time.sleep(15)
            rc=p.returncode
    except BaseException as e:
        atomic(out/'FAILURE.json',{'type':type(e).__name__,'reason':str(e)[:500]})
    end={'exit_code':rc,'config_sha256':pin,'utc_seconds':time.time(),'scientific_acceptance':False}
    if rc==0:end['result_sha256']=sha(out/'RECOMPUTED.json')
    atomic(out/'EXIT.json',end)
    return rc

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=('prepare','start','observe','worker'))
    p.add_argument('--config');p.add_argument('--sha256');p.add_argument('--plan');p.add_argument('--plan-pin')
    p.add_argument('--out');p.add_argument('--container');a=p.parse_args()
    if a.op=='prepare':result=prepare(a.plan,a.plan_pin,a.out,a.container)
    elif a.op=='worker':raise SystemExit(worker(a.config,a.sha256))
    else:result=globals()[a.op](a.config,a.sha256)
    print(json.dumps(result))

if __name__=='__main__':main()
