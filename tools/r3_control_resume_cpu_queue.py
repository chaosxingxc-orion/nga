"""Finite CPU reconstruction queue after control restart release; no NPU claims."""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
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


def module(name, root=HERE):
    m = source_module(root/(name+'.py'), name);return m
C=module('r3_control_resume_cpu');S=module('r3_eval_successor')
TOOLS={'r3_control_resume_cpu_queue.py','r3_control_resume_cpu.py','r3_resume_recompute.py',
       'r3_resume_evidence.py','r3_eval_successor.py','r3_formal_launcher.py'}


def verify(path,pin):
    C.require(C.sha(path)==pin,'CPU queue changed');d=C.load(path)
    C.require(d.get('schema')=='r3-control-resume-cpu-queue-v1' and d.get('interval_seconds')==600
              and d.get('scientific_acceptance') is False and d.get('test_read') is False,'CPU queue scope differs')
    C.require({Path(p).name for p in d['tools']}==TOOLS,'CPU queue closure differs')
    C.require(str(Path(__file__).resolve()) in d['tools'],'CPU queue executable differs')
    for p,h in d['tools'].items():
        C.require(C.safe(p).parent==HERE and C.sha(p)==h,'CPU queue code changed')
    C.require(C.sha(d['successor_queue'])==d['successor_queue_sha256'],'restart successor queue changed')
    successor=C.load(d['successor_queue']);sources=successor['jobs'];jobs=d['jobs']
    C.require(jobs and len({j['id'] for j in jobs})==len(jobs),'duplicate/empty CPU jobs')
    for field in ('out','container','restart_out'):
        C.require(len({j[field] for j in jobs})==len(jobs),'duplicate CPU '+field)
    for j in jobs:
        C.safe(j['out']);C.safe(j['restart_out'])
        direct=successor.get('schema')=='r3-eval-successor-v1'
        if direct:
            matched=[r for r in sources if r['id']==j['id']
                     and r.get('next_kind')=='training'
                     and r.get('next_execution')==str(Path(j['restart_out'])/'plan.json')]
        else:
            matched=[r for r in sources if r['id']==j['id'] and r['out']==j['restart_out']]
        C.require(len(matched)==1,'CPU restart not bound to successor')
        C.require(j['out']!=j['restart_out'],'CPU output overlaps restart')
        receipt=Path(j['restart_out'])/'LAUNCH_PREPARATION.json'
        if receipt.exists():
            R=module('r3_resume_evidence');r=matched[0]
            actual=C.load(Path(j['restart_out'])/'plan.json')
            source_bound=(R.identity(actual)==r['next_sha256'] if direct else
                          R.identity(C.load(Path(j['restart_out'])/'SOURCE_PLAN.json'))==r['source_pin'])
            C.require(actual.get('chip')==r['chip'] and actual.get('out')==j['restart_out'] and source_bound,
                      'CPU restart source differs from queue')
        elif direct:
            C.require(False,'direct restart preparation missing')
    return d


def tick(job):
    root=C.safe(job['restart_out']);out=C.safe(job['out'])
    prepared=out.with_name(out.name+'.PREPARED.json');intent=out.with_name(out.name+'.PREPARE_INTENT.json')
    if prepared.exists():
        record=C.load(prepared);C.require(record['job']==job,'CPU prepared job changed')
        config=record['config'];frozen=module('r3_control_resume_cpu',out/'code')
        C.require(config['config']==str(out/'CONFIG.json'),'CPU config path differs')
        cfg=C.load(config['config'])
        C.require(cfg['plan']==str(root/'plan.json') and cfg['container']==job['container'],'CPU prepared scope differs')
        return frozen.start(config['config'],config['sha256'])
    if intent.exists() or out.exists():
        return {'status':'needs_repair','reason':'partial CPU preparation; no automatic overwrite'}
    receipt=root/'LAUNCH_PREPARATION.json';plan=root/'plan.json'
    if not receipt.exists() or not plan.exists() or not (root/'TRAIN_EXIT.json').exists():
        return {'status':'waiting_restart'}
    launch=C.load(receipt);R=module('r3_resume_evidence')
    C.require(launch['plan']==str(plan) and R.identity(C.load(plan))==launch['plan_sha256'],
              'restart plan identity differs')
    end=C.load(root/'TRAIN_EXIT.json')
    if end.get('exit_code')!=0:return {'status':'restart_failed','exit_code':end.get('exit_code')}
    attempt=root/'attempts'/str(end['attempt'])
    if not all((attempt/name).exists() for name in ('RELEASE.json','SUPERVISOR_DONE.json')):
        return {'status':'waiting_restart_release'}
    C.released(plan,launch['plan_sha256'],R)
    C.atomic(intent,{'job':job,'plan_sha256':launch['plan_sha256']})
    config=C.prepare(plan,launch['plan_sha256'],out,job['container'])
    C.atomic(prepared,{'job':job,'config':config})
    return tick(job)


def watch(path,pin):
    with (path.parent/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            d=verify(path,pin);states={}
            for j in d['jobs']:
                try:states[j['id']]=tick(j)
                except Exception as e:states[j['id']]={'status':'observation_or_preparation_uncertain','error':str(e)[:300]}
                if states[j['id']]['status'] in ('started','running'):
                    break  # CPU reconstruction workers are deliberately ordered.
            value={'jobs':states,'utc_seconds':time.time(),'scientific_acceptance':False,'test_read':False}
            C.atomic(path.parent/'digest.json',value)
            if len(states)==len(d['jobs']) and all(x['status']=='done' for x in states.values()):
                C.atomic(path.parent/'DONE.json',value);return
            time.sleep(600)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=('verify','start','watch'))
    p.add_argument('--manifest',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    path=C.safe(a.manifest);verify(path,a.sha256)
    if a.op=='verify':print('CPU_CONTROL_QUEUE_VERIFIED');return
    C.require(socket.gethostname()=='k8s-node1','host175 only')
    if a.op=='watch':watch(path,a.sha256);return
    cmd=[sys.executable,'-P',str(Path(__file__).resolve()),'watch','--manifest',str(path),'--sha256',a.sha256]
    with (path.parent/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt=path.parent/'SERVICE.json';intent=path.parent/'SERVICE_START_INTENT.json'
        if receipt.exists():
            old=C.load(receipt);C.require(old['command']==cmd and S.process_matches(old),'prior CPU service not live')
            print(json.dumps({'status':'ALREADY_LIVE','pid':old['pid']}));return
        C.require(not intent.exists(),'uncertain prior CPU start')
        C.atomic(intent,{'command':cmd})
        with (path.parent/'service.log').open('ab') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        C.atomic(receipt,{'pid':proc.pid,'command':cmd})
        C.atomic(path.parent/'RELAUNCH.json',{'command':[sys.executable,'-P',str(Path(__file__).resolve()),
            'start','--manifest',str(path),'--sha256',a.sha256]})
        print(json.dumps({'status':'STARTED','pid':proc.pid}))


if __name__=='__main__':main()
