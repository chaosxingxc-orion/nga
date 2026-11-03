"""Fixed native DAG composition. dry-run/once never launch; dispatch needs exact review.

Deploy this controller on the physical NPU host. No SSH shell strings, generic
command adapter, production CPU scorer, or scientific-admission adapter exists.
Existing CPU handoffs continue inside their frozen native hosts after release.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def need(v,s):
    if not v:raise ValueError(s)

def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in [p,*p.parents]),'unsafe path');return p

def sha(p):
    with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(p):return json.loads(safe(p).read_bytes())

def pinned(r):
    need(type(r) is dict and set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'pin differs');return load(r['path'])

def module(r,name):
    need(sha(r['path'])==r['sha256'],'implementation changed');s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def verify(path,pin):
    need(sha(path)==pin,'service config differs');c=load(path)
    need(set(c)=={'schema','host_name','output','graph','allocation','modules','capabilities','mode','activation','interval_seconds'},'service config fields')
    need(c['schema']=='nga-native-dag-service-v1' and c['mode'] in ('plan','dispatch'),'service schema/mode')
    need(type(c['interval_seconds']) is int and c['interval_seconds']==600,'600 second cadence')
    need(type(c['host_name']) is str and c['host_name'],'host required');safe(c['output']);safe(c['allocation'])
    need(set(c['modules'])=={'dag','native','service'},'source registry')
    need(c['modules']['service']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'service implementation differs')
    D=module(c['modules']['dag'],'native_composition_dag');N=module(c['modules']['native'],'native_composition_adapter');g=pinned(c['graph']);D.validate(g)
    need(set(c['capabilities'])==set(N.KINDS) and all(type(v) is list and v and all(type(h) is str and len(h)==64 for h in v) for v in c['capabilities'].values()),'capabilities')
    need(g['policy']['poll_seconds']==600,'graph cadence')
    for n in g['nodes']:
        need(n['lane']=='npu' and n['adapter']=='native_guarded_v1','unsupported node adapter/lane')
        need(g['adapters'][n['adapter']]['implementation']==c['modules']['native'],'graph adapter differs')
        if n['action']:
            b=pinned(n['action']['binding']);need(N.pinned(b['plan'])['allocation']==c['allocation'],'allocation binding')
    grant=None
    if c['mode']=='dispatch':
        need(c['activation'] is not None,'activation missing');grant=pinned(c['activation'])
        need(grant.get('schema')=='nga-native-dag-activation-v1' and grant.get('verdict')=='PASS' and grant.get('activation_authorized') is True and grant.get('scientific_acceptance') is False,'activation scope')
        need(grant.get('graph_sha256')==D.digest(g) and grant.get('modules')==c['modules'] and grant.get('capabilities')==c['capabilities'] and grant.get('host_name')==c['host_name'] and grant.get('allocation')==c['allocation'] and grant.get('output')==c['output'],'activation identity')
        need(grant.get('bindings')=={n['id']:n['action'] for n in g['nodes'] if n['managed_by']=='dag' and n['action'] is not None},'activation actions')
    else:need(c['activation'] is None,'plan config cannot activate')
    return c,g,D,N,grant

def make_snapshot(c,g,D,N,adapter,query_resources=True):
    obs={};resources={str(i):'unknown' for i in range(8)};errors={};gh=D.digest(g)
    if query_resources:
        # Advisory selection only: the frozen host rechecks under this same lock
        # at claim. No ownership can be inferred from digest/controller booleans.
        with safe(c['allocation']+'.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_SH);a=load(c['allocation'])
        need(type(a.get('allocation')) is list and type(a.get('free')) is list,'allocation structure')
        busy=[x['chip'] for x in a['allocation']];free=[x['chip'] for x in a['free']]
        need(all(type(i) is int and 0<=i<8 for i in busy+free) and len(set(busy+free))==len(busy+free),'ambiguous allocation')
        for i in busy:resources[str(i)]='busy'
        for i in free:resources[str(i)]='free_observed'
    for n in g['nodes']:
        if n['action'] is None:continue
        try:
            b=D.read_pin(n['action']['binding']);r=D.read_pin(n['action']['review']);adapter.authorize(b,r,n,gh)
            if not query_resources:continue
            o=adapter.observe(n,None)
            if o['state']!='absent':obs[n['id']]=o
        except Exception as e:
            errors[n['id']]=type(e).__name__+': '+str(e)[:180]
            # An unverified external owner is never equivalent to no owner.
            obs[n['id']]={'state':'uncertain','facts':[],'failed_facts':[],'evidence':[]}
    s={'schema':'nga-dag-observation-v1','graph_sha256':gh,'as_of':str(time.time()),'authority':'adapter_observations' if query_resources else 'digest_only','observations':obs,'resources':resources}
    D.validate_snapshot(g,s);return s,errors

def once(c,g,D,N,grant,do_dispatch=False):
    need(socket.gethostname()==c['host_name'],'controller must run on owning host')
    out=safe(c['output']);out.mkdir(parents=True,exist_ok=True);adapter=N.NativeAdapter(c['capabilities'],out,grant=grant);registry={'native_guarded_v1':adapter}
    snap,errors=make_snapshot(c,g,D,N,adapter)
    plan=D.plan(g,snap,registry)
    if do_dispatch:
        need(c['mode']=='dispatch' and grant is not None,'dispatch not authorized');D.dispatch_once(g,snap,registry,out/'controller')
    D.atomic(out/'snapshot.json',snap);D.atomic(out/'plan.json',plan)
    D.atomic(out/'heartbeat.json',{'utc_seconds':time.time(),'mode':c['mode'],'nodes':len(g['nodes']),'proposed':plan['proposed'],'admission_errors':errors,'scientific_acceptance':False})
    print(json.dumps({'utc_seconds':time.time(),'mode':c['mode'],'proposed':plan['proposed'],'errors':errors,'dispatched_tick':do_dispatch}),flush=True)
    return plan

def identity(pid):
    fields=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(fields[19])}

def pinned_service_identity(out,pin):
    previous=load(out/'SERVICE.json')
    need(previous.get('config_sha256')==pin,'restart config differs')
    need(type(previous.get('pid')) is int and previous['pid']>0 and type(previous.get('start_ticks')) is int and type(previous.get('boot_id')) is str,'previous service identity invalid')
    try:current=identity(previous['pid'])
    except FileNotFoundError:current=None
    need(current is None or any(current[k]!=previous[k] for k in ('pid','boot_id','start_ticks')),'previous service process still live')
    return previous

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=('dry-run','once','start','restart','watch'));ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();c,g,D,N,grant=verify(a.config,a.sha256)
    if a.op=='dry-run':
        adapter=N.NativeAdapter(c['capabilities'],c['output'],query=lambda name:None,grant=None)
        snap,errors=make_snapshot(c,g,D,N,adapter,False);p=D.plan(g,snap,{'native_guarded_v1':adapter})
        commands={k:{'host_argv':v[3],'docker_command':v[2]} for k,v in adapter.bindings.items()}
        print(json.dumps({'plan':p,'commands':commands,'admission_errors':errors,'no_device_query':True,'launched':False},indent=2));return
    need(socket.gethostname()==c['host_name'],'controller host differs');out=safe(c['output']);out.mkdir(parents=True,exist_ok=True)
    inherited=os.environ.pop('NGA_NATIVE_DAG_LOCK_FD',None) if a.op=='watch' else None
    need(a.op!='watch' or inherited is not None,'watch requires inherited service lock; use start')
    lockfile=os.fdopen(int(inherited),'a') if inherited else (out/'service.lock').open('a')
    with lockfile as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.op=='once':once(c,g,D,N,grant,False);return
        if a.op in ('start','restart'):
            old=None
            if a.op=='start':need(not (out/'SERVICE.json').exists(),'service identity exists; use explicit restart after reconciliation')
            else:
                old=pinned_service_identity(out,a.sha256)
                archive=out/'service_history'/sha(out/'SERVICE.json');archive.mkdir(parents=True,exist_ok=True)
                D.atomic(archive/'SERVICE.json',old)
                if (out/'EXIT.json').exists():D.atomic(archive/'EXIT.json',load(out/'EXIT.json'))
                D.atomic(archive/'RECONCILIATION.json',{'previous_service_sha256':sha(out/'SERVICE.json'),'utc_seconds':time.time(),'same_config':True,'prior_identity_not_live':True,'controller_journal_preserved':True})
                if (out/'EXIT.json').exists():(out/'EXIT.json').unlink()
            cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--config',a.config,'--sha256',a.sha256]
            env=dict(os.environ,NGA_NATIVE_DAG_LOCK_FD=str(lock.fileno()),PYTHONDONTWRITEBYTECODE='1')
            restart=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'restart','--config',a.config,'--sha256',a.sha256]
            D.atomic(out/'RELAUNCH.json',{'command':restart,'automatic_restart':False,'config_sha256':a.sha256,'requires_prior_identity_not_live':True,'preserves_controller_journal':True})
            with (out/'service.log').open('ab') as log:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=(lock.fileno(),),start_new_session=True)
            D.atomic(out/'SERVICE.json',{**identity(p.pid),'command':cmd,'config_sha256':a.sha256,'started_utc_seconds':time.time()});print(json.dumps({'pid':p.pid}));return
        rc=1
        def stop(*unused):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        try:
            while True:
                tick=time.monotonic();c,g,D,N,grant=verify(a.config,a.sha256);once(c,g,D,N,grant,c['mode']=='dispatch');time.sleep(max(0,600-(time.monotonic()-tick)))
        except KeyboardInterrupt:rc=0
        finally:D.atomic(out/'EXIT.json',{'exit_code':rc,'utc_seconds':time.time(),'config_sha256':a.sha256,'scientific_acceptance':False})

if __name__=='__main__':main()
