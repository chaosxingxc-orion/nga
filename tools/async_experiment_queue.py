#!/usr/bin/env python3
"""Reviewed finite NPU FIFO + ordered CPU lane. No scientific decisions here.

Actions must be short, identity-pinned, idempotent detached-launch/release adapters.
The controller itself never edits CHIP-ALLOCATION. An operational release adapter
is a separately reviewed prerequisite; a scientific verifier is not a substitute.
"""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import shlex
import subprocess
import time


def require(ok, message):
    if not ok: raise ValueError(message)


def read(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Symlink evidence')
    with path.open('rb') as f:
        before = os.fstat(f.fileno()); raw = f.read(); after = os.fstat(f.fileno())
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'Read changed')
    return raw


def sha(path): return hashlib.sha256(read(path)).hexdigest()
def load(path): return json.loads(read(path))
def stamp(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def atomic(path,value):
    path=Path(path); temp=path.with_name(path.name+'.pending')
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    # Mutable scheduler snapshots may replace an interrupted write; immutable job
    # evidence is never written here. The exclusive controller lock serializes it.
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path); fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def inspect(name):
    require(name and all(c.isalnum() or c in '_.-' for c in name),'Invalid container')
    connection=http.client.HTTPConnection('localhost',timeout=10)
    connection.sock=socket.socket(socket.AF_UNIX);connection.sock.settimeout(10)
    connection.sock.connect('/var/run/docker.sock')
    try:
        connection.request('GET','/containers/'+name+'/json');r=connection.getresponse();raw=r.read()
        if r.status==404:return None
        require(r.status==200,'Docker inspection failed');return json.loads(raw)
    finally:connection.close()


def checked_action(action, output):
    require(action['idempotent'] is True and 1 <= action['timeout_seconds'] <= 45,'Short idempotent adapter required')
    require(action['argv'] and all(type(x) is str and x for x in action['argv']),'Invalid argv')
    require(action['files'],'Action executable closure required')
    for p,h in action['files'].items():require(sha(p)==h,'Action dependency changed: '+p)
    # The approved argv may use a short SSH hop to the physical-host launcher.
    # No shell interpolation, detached experiment output belongs in its own log.
    with Path(output).open('ab') as stream:
        try:
            result=subprocess.run(action['argv'],stdin=subprocess.DEVNULL,stdout=stream,
                                  stderr=stream,timeout=action['timeout_seconds'],check=False)
            return {'returncode':result.returncode,'uncertain':result.returncode!=0}
        except subprocess.TimeoutExpired:return {'returncode':None,'uncertain':True}


def validate(manifest):
    require(manifest['schema']=='async-experiment-queue-v1','Queue schema')
    require(manifest['analysis_policy']=='ordered_single_lane' and manifest['npu_policy']=='fifo_per_chip','Policy differs')
    jobs=manifest['jobs'];require(jobs and len({j['id'] for j in jobs})==len(jobs),'Duplicate/empty jobs')
    require(len({j['npu']['container'] for j in jobs})==len(jobs),'Reused NPU container')
    require(len({j['cpu']['container'] for j in jobs})==len(jobs),'Reused CPU container')
    require(not ({j['npu']['container'] for j in jobs}&{j['cpu']['container'] for j in jobs}),'Cross-lane container collision')
    for job in jobs:
        require(type(job['chip']) is int and 0<=job['chip']<8,'Invalid chip')
        require(job['release_policy']=='operational_exit_before_scientific_analysis','CPU analysis must not gate release')
        require(job['plan_sha256']==sha(job['plan']),'Changed frozen job plan')
        for lane in ('npu','cpu'):
            require(job[lane]['receipt'] and job[lane]['terminal'],'Evidence paths missing')
        require(job['ready_review']['approved_plan_sha256']==job['plan_sha256'] and
                job['ready_review']['approved'] is True and sha(job['ready_review']['path'])==job['ready_review']['sha256'],
                'Exact approved job required')


def observe(spec, query):
    """Actual retained generation + durable terminal, not digest text."""
    actual=query(spec['container']);receipt_path=Path(spec['receipt'])
    if actual is None:
        require(not receipt_path.exists(),'Receipt without retained container')
        return None
    require(receipt_path.exists(),'Container without bound launch receipt')
    receipt=load(receipt_path)
    require(actual['Id']==receipt['container_id'],'Receipt/container differs')
    require(not actual['HostConfig'].get('AutoRemove'),'Container must be retained')
    state=actual['State'];status=state['Status']
    binding=dict(container_id=actual['Id'],started_at=state['StartedAt'],receipt_sha256=sha(receipt_path))
    if status in ('created','running'):return dict(status=status,**binding)
    require(status=='exited','Unknown Docker terminal state')
    require(Path(spec['terminal']).exists(),'Exited without terminal; quarantine')
    terminal=load(spec['terminal'])
    require(type(terminal['rc']) is int and terminal['rc']==state['ExitCode'],'Exit/terminal mismatch')
    return dict(status='exited',rc=terminal['rc'],finished_at=state['FinishedAt'],
                terminal_sha256=sha(spec['terminal']),**binding)


def operational_proof(job,observation):
    proof=load(job['release_marker'])
    require(proof['status']=='OPERATIONALLY_RELEASED' and proof['job_id']==job['id']
        and proof['plan_sha256']==job['plan_sha256'] and proof['chip']==job['chip'],'Wrong operational release')
    for key in ('container_id','started_at','finished_at','terminal_sha256','receipt_sha256'):
        require(proof[key]==observation[key],'Release generation differs: '+key)
    require(proof['scientific_acceptance'] is False,'Operational release is not scientific acceptance')
    require(proof['retained_evidence_manifest_sha256']==sha(proof['retained_evidence_manifest']),
            'Retained evidence commitment differs')
    entries=load(proof['retained_evidence_manifest'])
    for name,h in entries.items():require(sha(name)==h,'Retained source evidence changed')
    require(entries.get(job['npu']['terminal'])==observation['terminal_sha256']
            and entries.get(job['npu']['receipt'])==observation['receipt_sha256'],'Missing retained generation evidence')
    require(proof['allocation_transition_sha256']==sha(proof['allocation_transition']),'Release transition changed')
    return sha(job['release_marker'])


def tick(manifest,state,save,query=inspect,action=checked_action):
    """Advance NPU lanes first; CPU progress never gates unrelated NPU jobs."""
    jobs=manifest['jobs'];records=state['jobs']
    def checkpoint():save(state)
    for job in jobs:
        rec=records[job['id']]
        if rec['npu'] in ('done','quarantined'):continue
        # FIFO only within the assigned chip; a blocked chip cannot hold others.
        earlier=[records[x['id']] for x in jobs[:jobs.index(job)] if x['chip']==job['chip']]
        if any(x['npu']!='done' for x in earlier):continue
        try:
            obs=observe(job['npu'],query)
            if obs is None:
                rec['npu']='launch_intent';checkpoint()
                rec['last_launch']=action(job['launch'],job['action_log']);checkpoint();continue
            if obs['status'] in ('created','running'):
                rec['npu']='running';rec['generation']=obs;checkpoint()
                if obs['status']=='created':rec['last_launch']=action(job['launch'],job['action_log']);checkpoint()
                continue
            rec['generation']=obs
            if obs['rc']!=0:
                rec['npu']='quarantined';rec['error']='Nonzero NPU exit requires separate operational disposition';checkpoint();continue
            # Save completed identity before calling the release adapter. Lost
            # responses are reconciled from its immutable proof next tick.
            rec['npu']='release_pending';checkpoint()
            if not Path(job['release_marker']).exists():
                rec['last_release']=action(job['operational_release'],job['action_log']);checkpoint()
            if Path(job['release_marker']).exists():
                rec['release_sha256']=operational_proof(job,obs);rec['npu']='done';checkpoint()
        except Exception as exc:
            rec['npu']='quarantined';rec['error']=type(exc).__name__+': '+str(exc);checkpoint()
    # Strict original queue order for CPU analysis; independent of NPU assignment.
    for job in jobs:
        rec=records[job['id']]
        if rec['cpu']=='done':continue
        if rec['cpu']=='quarantined' or rec['npu']!='done':break
        try:
            obs=observe(job['cpu'],query)
            if obs is None:
                rec['cpu']='launch_intent';checkpoint();rec['last_cpu_launch']=action(job['cpu_launch'],job['action_log']);checkpoint()
            elif obs['status'] in ('created','running'):
                require(not query(job['cpu']['container'])['HostConfig'].get('Devices'),'CPU lane exposes accelerator')
                rec['cpu']='running';rec['cpu_generation']=obs;checkpoint()
                if obs['status']=='created':rec['last_cpu_launch']=action(job['cpu_launch'],job['action_log']);checkpoint()
            else:
                rec['cpu_generation']=obs;rec['cpu']='done' if obs['rc']==0 else 'quarantined';checkpoint()
        except Exception as exc:rec['cpu']='quarantined';rec['cpu_error']=type(exc).__name__+': '+str(exc);checkpoint()
        break
    return state


def run(path,pin,out,once=False):
    require(sha(path)==pin,'Externally pinned queue differs');manifest=load(path);validate(manifest)
    out.mkdir(parents=True,exist_ok=True)
    fd=os.open(out/'controller.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=out/'state.json'
        state=load(state_path) if state_path.exists() else dict(queue_sha256=pin,jobs={j['id']:dict(npu='queued',cpu='queued') for j in manifest['jobs']})
        require(state['queue_sha256']==pin and set(state['jobs'])=={j['id'] for j in manifest['jobs']},'Queue state identity differs')
        while True:
            require(sha(path)==pin,'Queue changed during execution')
            tick(manifest,state,lambda s:atomic(state_path,s))
            digest=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),queue_sha256=pin,
                jobs={k:{a:b for a,b in v.items() if a in ('npu','cpu','error','cpu_error')} for k,v in state['jobs'].items()})
            atomic(out/'digest.json',digest)
            with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(digest)+'\n')
            if all(x['cpu']=='done' for x in state['jobs'].values()):
                atomic(out/'COMPLETE.json',dict(rc=0,queue_sha256=pin,state_sha256=sha(state_path)));return 0
            if once:return 0
            time.sleep(5)


def prepare_detached(manifest_path,pin,out,image):
    """Create review artifacts only; caller reviews spec and starts retained Docker."""
    require(sha(manifest_path)==pin,'Queue pin differs');validate(load(manifest_path))
    require(image=='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7','Fixed image only')
    require(not out.exists(),'New controller generation required');out.mkdir()
    source=out/'async_experiment_queue.py';source.write_bytes(read(__file__))
    command=['/usr/local/python3.12.13/bin/python3','-B','-I',str(source),'--manifest',str(manifest_path),'--sha256',pin,'--out',str(out/'state')]
    # The stdlib-only controller does not import CANN or Torch; isolated mode is
    # intentionally limited to this device-free orchestration process.
    wrapper=("#!/usr/bin/env bash\nset -uo pipefail\ncd /\n"+shlex.join(command)+" >> "+shlex.quote(str(out/'controller.log'))+" 2>&1\nrc=$?\nset -o noclobber\nprintf 'rc=%s\\n' \"$rc\" > "+shlex.quote(str(out/'EXIT'))+"\nexit \"$rc\"\n")
    (out/'run.sh').write_text(wrapper)
    spec=dict(Image=image,Entrypoint=['/bin/bash'],Cmd=[str(out/'run.sh')],HostConfig=dict(AutoRemove=False,NetworkMode='host',Devices=[],
        Binds=['/mnt/cephfs:/mnt/cephfs','/var/run/docker.sock:/var/run/docker.sock'],NanoCpus=1000000000,Memory=2*2**30))
    atomic(out/'DOCKER_SPEC.json',spec)
    atomic(out/'PREPARATION.json',dict(queue_sha256=pin,controller_sha256=sha(source),wrapper_sha256=sha(out/'run.sh'),
        spec_sha256=sha(out/'DOCKER_SPEC.json'),launched=False,approved=False,
        note='Exact controller/spec/manifest and operational-release adapters need independent review before launch.'))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args()
    raise SystemExit(run(a.manifest.absolute(),a.sha256,a.out.absolute(),a.once))
