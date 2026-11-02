#!/usr/bin/env python3
"""Detached CPU-only control handoff bootstrap; one immutable start per generation."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types


def require(ok,why):
    if not ok: raise ValueError(why)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,d):
    with Path(p).open('x') as f:
        json.dump(d,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
def load(path,pin):
    require(sha(path)==pin,'config changed'); b=read(path)
    require(b['deployment']['service']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'service changed')
    require(sha(b['controller'])==b['controller_sha256'],'controller changed')
    m=types.ModuleType('control'); m.__file__=b['controller']
    exec(compile(Path(b['controller']).read_bytes(),b['controller'],'exec'),m.__dict__)
    m.identity(path,pin)
    return b,m

def argv(b,op,path,pin):
    return [b['deployment']['python'],'-B','-P',b['deployment']['service']['path'],op,'--config',str(path),'--sha256',pin]
def process(pid):
    root=Path('/proc')/str(pid)
    stat=(root/'stat').read_text(); fields=stat[stat.rfind(')')+2:].split()
    return dict(pid=pid,start_ticks=fields[19],command=[x.decode() for x in (root/'cmdline').read_bytes().split(b'\0') if x],session=os.getsid(pid))
def start(path,pin):
    b,_=load(path,pin);root=Path(b['state_root']);root.mkdir(parents=True,exist_ok=True)
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not any((root/x).exists() for x in ['START_INTENT.json','SERVICE.json','EXIT.json','FAILURE.json','watch.lock']), 'existing generation requires reconciliation')
        boot=argv(b,'boot',path,pin);command=['/usr/bin/nohup','/usr/bin/setsid','--fork']+boot
        write(root/'START_INTENT.json',dict(config_sha256=pin,command=command,boot_command=boot,utc_seconds=time.time()))
        write(root/'DEPLOY-RELAUNCH.json',dict(command=argv(b,'start',path,pin),policy='Never replay this generation after START_INTENT; reconcile and create a separately reviewed successor.',log=str(root/'watch.log'),terminal=str(root/'EXIT.json')))
        with (root/'watch.log').open('ab') as log:
            result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=15)
        require(result.returncode==0,'setsid launcher failed; reconcile intent')
    return dict(status='start_requested_not_verified',config_sha256=pin)
def boot(path,pin):
    # START_INTENT locates a safe terminal even if controller initialization fails.
    require(sha(path)==pin,'config changed');b=read(path);root=Path(b['state_root'])
    intent=read(root/'START_INTENT.json');require(intent['config_sha256']==pin,'intent changed')
    with (root/'bootstrap.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not (root/'SERVICE.json').exists() and not (root/'EXIT.json').exists(),'boot replay forbidden')
        try:
            b,m=load(path,pin)
            actual=process(os.getpid());require(actual['command']==intent['boot_command'],'boot argv differs')
            write(root/'SERVICE.json',dict(actual,config_sha256=pin,utc_seconds=time.time()))
            m.watch(path,pin)
        except BaseException as e:
            if not (root/'EXIT.json').exists():write(root/'EXIT.json',dict(exit_code=1,status='bootstrap_failed',error=str(e)[:400],config_sha256=pin,utc_seconds=time.time()))
            raise

def status(path,pin):
    b,_=load(path,pin);root=Path(b['state_root'])
    if (root/'EXIT.json').exists():return dict(status='terminal',terminal=read(root/'EXIT.json'))
    receipt=read(root/'SERVICE.json');actual=process(receipt['pid'])
    require(receipt['config_sha256']==pin and all(receipt[k]==actual[k] for k in actual),'process identity differs')
    require(actual['command']==argv(b,'boot',path,pin),'runtime argv differs')
    require((root/'digest.json').is_file() and (root/'heartbeat.json').is_file(),'startup digest absent')
    require(time.time()-(root/'heartbeat.json').stat().st_mtime<=b['poll_interval_seconds']+120,'heartbeat stale')
    return dict(status='running_verified',process=actual,digest=read(root/'digest.json'))

def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=['start','boot','status']);p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    result=globals()[a.op](a.config,a.sha256);print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
