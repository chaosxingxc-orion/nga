#!/usr/bin/env python3
"""Detached E40 CPU verification. New request after NPU exit; no device/release writes.

Docker socket access is for inspected generations, not an isolation boundary.
Uncertain CPU generations are retained and never restarted by this tool.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import threading
import time
import types

IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
HELPER='12a5e895d6fa16df0506418dfbad0affe584cd06e62993a40bee0b4d86ee5b77'


def require(ok,message):
    if not ok: raise ValueError(message)


def raw(path):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in [path,*path.parents]),'Symlink evidence')
    with path.open('rb') as f:
        before=os.fstat(f.fileno()); data=f.read(); after=os.fstat(f.fileno())
    require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
            (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'Changed during read')
    return data


def sha(path): return hashlib.sha256(raw(path)).hexdigest()
def load(path): return json.loads(raw(path))

def module(path,digest):
    data=raw(path);require(hashlib.sha256(data).hexdigest()==digest,'Executable hash differs: '+str(path))
    m=types.ModuleType('e40_cpu_'+Path(path).stem);m.__file__=str(path)
    exec(compile(data,str(path),'exec'),m.__dict__);return m


def safe_spec(spec,out):
    host=spec['HostConfig']
    require(spec['Image']==IMAGE and spec['Cmd']==['bash',str(out/'run.sh')],'CPU image/command differs')
    require(host==dict(Binds=['/mnt/cephfs:/mnt/cephfs','/var/run/docker.sock:/var/run/docker.sock'],
        Devices=[],NetworkMode='none',AutoRemove=False,NanoCpus=2000000000,Memory=4*2**30,ShmSize=64*2**20), 'CPU exposure differs')
    require('TORCH_DEVICE_BACKEND_AUTOLOAD=0' in spec['Env'],'CPU autoload guard missing')


def actual_binding(q,actual,spec,receipt=None):
    q.binding(actual,spec,receipt)
    for key in ('AutoRemove','NanoCpus','Memory','ShmSize'):
        require(actual['HostConfig'].get(key)==spec['HostConfig'][key],'Actual CPU limit/retention differs: '+key)


def prepare(plan,pin,out,name,source=None):
    require(sha(plan)==pin,'Plan pin differs');p=load(plan);run=plan.parent
    require(p['out']==str(run),'Plan location differs')
    source=Path(__file__) if source is None else source
    e=module(run/'e38_evidence.py',HELPER);q=module(run/'jeval_reference_queue.py',p['files'][str(run/'jeval_reference_queue.py')])
    actual=q.inspect(p['container']);require(actual is not None and actual['State']['Status']=='exited'
        and actual['State']['ExitCode']==0,'NPU must already be exited/0')
    npu_terminal=load(run/'COMPLETE.json');require(npu_terminal['rc']==0,'NPU terminal failed')
    require(not out.exists(),'New CPU request generation required');out.mkdir()
    for src,dst in [(source,out/'openjev_lifetime_verify_launch.py'),(run/'e38_evidence.py',out/'e38_evidence.py'),
                    (run/'jeval_reference_queue.py',out/'jeval_reference_queue.py')]:dst.write_bytes(raw(src))
    wrapper=('#!/usr/bin/env bash\nset -uo pipefail\ncd /\n'
        'unset PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP\n'
        'export PYTHONNOUSERSITE=1\n'
        'export PYTHONPATH=/usr/local/python3.12.13/lib/python3.12/site-packages:/usr/local/Ascend/ascend-toolkit/latest/python/site-packages:/usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe:/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe\n'
        'pin=$(cat '+shlex.quote(str(out/'REQUEST.sha256'))+')\n'
        '/usr/local/python3.12.13/bin/python3 -B -S -s -P '+shlex.quote(str(out/'openjev_lifetime_verify_launch.py'))+' --run '+shlex.quote(str(out/'request.json'))+
        ' --sha256 "$pin" >> '+shlex.quote(str(out/'run.log'))+' 2>&1\nrc=$?\nset -o noclobber\n'
        'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+shlex.quote(str(out/'EXIT'))+'\nexit "$rc"\n')
    (out/'run.sh').write_text(wrapper)
    base=load(p['container_spec'])
    env=[x for x in base['Env'] if not x.startswith(('ASCEND_RT_VISIBLE_DEVICES=','TORCH_DEVICE_BACKEND_AUTOLOAD='))]
    spec=dict(Image=IMAGE,Entrypoint=base['Entrypoint'],Env=env+['TORCH_DEVICE_BACKEND_AUTOLOAD=0'],
        Cmd=['bash',str(out/'run.sh')],Labels={'nga.e40.cpu':name},HostConfig=dict(
        Binds=['/mnt/cephfs:/mnt/cephfs','/var/run/docker.sock:/var/run/docker.sock'],Devices=[],
        NetworkMode='none',AutoRemove=False,NanoCpus=2000000000,Memory=4*2**30,ShmSize=64*2**20))
    safe_spec(spec,out);e.publish_new(out/'CPU_SPEC.json',spec)
    files={str(f):sha(f) for f in out.iterdir() if f.is_file()}
    files.update({str(plan):pin,**{str(run/n):sha(run/n) for n in
        ('COMPLETE.json','EXIT','report.json','LAUNCH_RECEIPT.json','GENERATION.json')}})
    files.update({k:v for k,v in p['files'].items() if k.endswith('.py')})
    request=dict(schema='e40-detached-cpu-verify-v1',out=str(out),container=name,plan=str(plan),plan_sha256=pin,
        npu_id=actual['Id'],npu_started_at=actual['State']['StartedAt'],npu_finished_at=actual['State']['FinishedAt'],files=files)
    e.publish_new(out/'request.json',request);rh=sha(out/'request.json');(out/'REQUEST.sha256').write_text(rh+'\n')
    (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\n'+shlex.join(['python3','-B','-I',str(out/'openjev_lifetime_verify_launch.py'),'--launch',str(out/'request.json'),'--sha256',rh])+'\n')
    (out/'RELAUNCH.md').write_text('Only retry LAUNCH_EXACT.sh while its exact container is created/running. Never restart exited or uncertain generations. New request required on failure.\n')
    return dict(request=str(out/'request.json'),sha256=rh,launched=False)


def context(request,pin):
    require(sha(request)==pin,'Request pin differs');r=load(request);out=request.parent
    require(r['schema']=='e40-detached-cpu-verify-v1' and r['out']==str(out),'Request location/schema differs')
    require(sha(Path(__file__))==r['files'][str(out/'openjev_lifetime_verify_launch.py')],'Runner identity differs')
    e=module(out/'e38_evidence.py',HELPER);bound=e.Evidence();bound.frozen(r['files'])
    q=module(out/'jeval_reference_queue.py',r['files'][str(out/'jeval_reference_queue.py')]);spec=bound.load(out/'CPU_SPEC.json')
    safe_spec(spec,out);p=bound.load(r['plan']);actual=q.inspect(p['container'])
    require(actual is not None and actual['Id']==r['npu_id'] and actual['State']['Status']=='exited'
        and actual['State']['ExitCode']==0 and actual['State']['StartedAt']==r['npu_started_at']
        and actual['State']['FinishedAt']==r['npu_finished_at'],'NPU exit generation differs')
    return r,out,e,bound,q,spec


def launch(request,pin):
    r,out,e,bound,q,spec=context(request,pin)
    require(socket.gethostname()=='k8s-node1','Physical CPU verification host differs')
    fd=os.open(out/'launch.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        require(not any((out/n).exists() for n in ('COMPLETE.json','EXIT','report.json')),'Prior terminal/output retained')
        review=bound.load(out/'PARENT_REVIEW.json')
        require(review.get('approved') is True and review.get('approved_request_sha256')==pin,'Exact request approval missing')
        require((out/'REQUEST.sha256').read_text()==pin+'\n','Wrapper pin differs')
        actual=q.inspect(r['container']);intent=out/'LAUNCH_INTENT.json'
        value=dict(request_sha256=pin,spec_sha256=sha(out/'CPU_SPEC.json'))
        if intent.exists():require(load(intent)==value,'Intent differs')
        else:
            require(actual is None,'Preexisting unowned container');e.publish_new(intent,value)
        if actual is None:
            require(not (out/'LAUNCH_RECEIPT.json').exists(),'Receipt without container')
            bound.verify();q.docker('POST','/containers/create?name='+r['container'],spec);actual=q.inspect(r['container'])
        actual_binding(q,actual,spec);require(actual['State']['Status'] in ('created','running'),'CPU restart forbidden')
        receipt=out/'LAUNCH_RECEIPT.json'
        if not receipt.exists():
            require(actual['State']['Status']=='created','Started CPU lacks receipt')
            e.publish_new(receipt,dict(container_id=actual['Id'],request_sha256=pin,image=IMAGE,command=spec['Cmd'],
                entrypoint=spec['Entrypoint'],wrapper_sha256=sha(out/'run.sh'),parent_review_sha256=sha(out/'PARENT_REVIEW.json')))
        saved=load(receipt);actual_binding(q,actual,spec,saved);require(saved['request_sha256']==pin,'Receipt request differs')
        if actual['State']['Status']=='created':bound.verify();q.docker('POST','/containers/'+actual['Id']+'/start')
        return dict(container_id=actual['Id'],status=q.inspect(r['container'])['State']['Status'])


def run(request,pin):
    r,out,e,bound,q,spec=context(request,pin);rc=1;error=None;stop=threading.Event();errors=[]
    fd=os.open(out/'task.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not any((out/n).exists() for n in ('COMPLETE.json','report.json','EXIT')),'CPU generation already used')
        actual=q.inspect(r['container']);receipt=bound.load(out/'LAUNCH_RECEIPT.json');actual_binding(q,actual,spec,receipt)
        review=bound.load(out/'PARENT_REVIEW.json')
        require(review.get('approved') is True and review.get('approved_request_sha256')==pin
            and receipt['parent_review_sha256']==bound.sha(out/'PARENT_REVIEW.json'),'CPU approval binding differs')
        require(actual['State']['Status']=='running' and receipt['request_sha256']==pin,'CPU generation not running')
        def beat():
            while not stop.is_set():
                try:q.atomic(out/'digest.json',dict(utc=q.utc(),stage='verifying',progress=0,total=1,chips=0))
                except Exception as exc:errors.append(str(exc));return
                stop.wait(10)
        thread=threading.Thread(target=beat,daemon=True);thread.start()
        try:
            plan=Path(r['plan']);p=load(plan)
            verifier=module(plan.parent/'openjev_lifetime_verify.py',p['files'][str(plan.parent/'openjev_lifetime_verify.py')])
            verifier.verify(plan,r['plan_sha256'],out/'report.json');bound.verify()
            now=q.inspect(r['container']);require(now['Id']==actual['Id'] and now['State']['StartedAt']==actual['State']['StartedAt'],'CPU changed')
            require(not errors,'Heartbeat failed');rc=0
        except BaseException as exc:error=type(exc).__name__+': '+str(exc)
        finally:
            stop.set();thread.join(15)
            if errors:rc=1;error='Heartbeat failed: '+repr(errors)
            e.publish_new(out/'COMPLETE.json',dict(rc=rc,error=error,request_sha256=pin,
                cpu_id=actual['Id'],cpu_started_at=actual['State']['StartedAt'],
                outputs={'report.json':sha(out/'report.json')} if (out/'report.json').exists() else {}))
            q.atomic(out/'digest.json',dict(utc=q.utc(),stage='completed' if rc==0 else 'failed',progress=int(rc==0),total=1,chips=0,rc=rc))
    return rc


def attest(request,pin):
    r,out,e,bound,q,spec=context(request,pin);terminal=bound.load(out/'COMPLETE.json')
    require(terminal['rc']==0 and terminal['request_sha256']==pin,'CPU terminal failed')
    bound.frozen({str(out/n):h for n,h in terminal['outputs'].items()})
    require(raw(out/'EXIT').decode().startswith('rc=0 utc='),'CPU wrapper failed')
    actual=q.inspect(r['container']);actual_binding(q,actual,spec,bound.load(out/'LAUNCH_RECEIPT.json'))
    require(actual['State']['Status']=='exited' and actual['State']['ExitCode']==0
        and actual['Id']==terminal['cpu_id'] and actual['State']['StartedAt']==terminal['cpu_started_at'],'CPU final generation differs')
    result=dict(request_sha256=pin,report_sha256=sha(out/'report.json'),terminal_sha256=sha(out/'COMPLETE.json'),
        receipt_sha256=sha(out/'LAUNCH_RECEIPT.json'),exit_sha256=sha(out/'EXIT'),container_id=actual['Id'],
        started_at=actual['State']['StartedAt'],finished_at=actual['State']['FinishedAt'],actual_exit=0,devices=[])
    bound.verify();again=q.inspect(r['container']);require(again['Id']==actual['Id'] and again['State']==actual['State'],'CPU changed after exit')
    e.publish_new(out/'CPU_EXIT_BINDING.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    for flag in ('prepare','launch','run','attest'):g.add_argument('--'+flag,type=Path)
    p.add_argument('--sha256',required=True);p.add_argument('--out',type=Path);p.add_argument('--container')
    a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.prepare.absolute(),a.sha256,a.out.absolute(),a.container)))
    elif a.launch:print(json.dumps(launch(a.launch.absolute(),a.sha256)))
    elif a.attest:print(json.dumps(attest(a.attest.absolute(),a.sha256)))
    else:raise SystemExit(run(a.run.absolute(),a.sha256))
