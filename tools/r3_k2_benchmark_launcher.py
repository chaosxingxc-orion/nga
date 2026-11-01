"""Detached, retained, resource-bound K2 engineering benchmark on host175.

No automatic retry after an uncertain launch. Resume observation of the same
container; a new benchmark plan/output is required after a failed benchmark.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import types

BASE=Path('/mnt/cephfs/xingchao/experiments/jev')
IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
TOOLS=('r3_k2_benchmark_launcher.py','r3_resource_adapter.py','r3_final_container.py','r3_formal_launcher.py')
TRAIN=str(BASE/'KEV/decision-v7/train.jsonl')
MODEL='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'

def require(ok,why):
    if not ok:raise ValueError(why)
def safe(value):
    p=Path(value)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    require(not any(x=='test' or x.startswith('test.') for x in p.parts),'test path forbidden')
    return p
def sha(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def load(p):return json.loads(safe(p).read_text())
def atomic(p,d):
    p=Path(p);tmp=p.with_suffix('.pending');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(p)
def module(p):
    p=safe(p);m=types.ModuleType(p.stem);m.__file__=str(p)
    exec(compile(p.read_bytes(),str(p),'exec',dont_inherit=True),m.__dict__);return m

def verify(path,pin):
    require(sha(path)==pin,'execution pin differs');p=load(path);out=safe(p['out'])
    boundary = p['schema'] == 'r3-k2-reference-trace-execution-v2'
    trace = p['schema'] in ('r3-k2-reference-trace-execution-v1','r3-k2-reference-trace-execution-v2')
    require(p['schema'] in ('r3-k2-benchmark-execution-v1','r3-k2-reference-trace-execution-v1','r3-k2-reference-trace-execution-v2') and p['scientific_acceptance'] is False
            and p['test_read'] is False,'execution scope differs')
    require(out==safe(path).parent and out.is_relative_to(BASE/'r3_runs'),'output ownership differs')
    require(p['run']==str(out.relative_to(BASE)) and p['allocation']==str(BASE/'CHIP-ALLOCATION.json'),'ledger differs')
    require(type(p['chip']) is int and p['chip'] in range(8) and p['image']==IMAGE,'chip/image differs')
    require(p['container']==('nga-k2-trace-' if trace else 'nga-k2-sync-')+p['benchmark_sha256'][:16],'container identity differs')
    require(p['launcher']==str(Path(__file__).resolve()),'frozen launcher differs')
    require(set(p['tools'])=={str(out/'tools'/n) for n in TOOLS},'tools differ')
    for f,h in p['tools'].items():require(sha(f)==h,'tool changed')
    require(sha(p['benchmark_plan'])==p['benchmark_sha256'],'benchmark changed');q=load(p['benchmark_plan'])
    require(q['schema']==('r3-k2-reference-trace-plan-v2' if boundary else 'r3-k2-reference-trace-plan-v1' if trace else 'r3-k2-deferred-sync-benchmark-v1') and q['test_read'] is False
            and q['scientific_acceptance'] is False and q['model']==MODEL,'benchmark scope differs')
    require(safe(q['out'])==out/'results','benchmark output differs')
    protocol = ({'seed':2,'step':0,'reference_evaluations':2,'max_questions':32,
                 'max_reference_bytes':2*1024**3,'chips':1,'diagnostic_only':True} if trace else
                {'seed':2,'warmup_pairs':3,'measured_pairs':10,'min_measured_seconds':60,
                 'exact_loss_and_gradients':True,'minimum_speedup':1.05,'chips':1})
    if boundary:
        protocol.update(reference_evaluations=4, boundary_observers=True, control_reference_evaluations=2)
    require(q['protocol']==protocol,'protocol differs')
    code=safe(q['trainer']).parent
    require(code==out/'code' and q['candidate']==str(code/'candidate_train_r3.py')
            and q['transform']==str(code/'r3_k2_deferred_sync.py'),'code paths differ')
    require(p['benchmark']==str(code/('r3_k2_reference_trace_run.py' if trace else 'r3_k2_sync_benchmark.py')),'benchmark executable differs')
    names = ('train_r3.py','candidate_train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py','r3_k2_deferred_sync.py','r3_k2_sync_benchmark.py')
    if trace:names += ('r3_k2_reference_trace.py','r3_k2_reference_trace_run.py')
    if boundary:names += ('r3_k2_boundary_trace.py',)
    require(set(q['files'])=={str(code/n) for n in names} | {TRAIN} |
        {str(f) for f in Path(MODEL).iterdir() if f.is_file()}, 'input inventory differs')
    for f,h in q['files'].items():require(sha(f)==h,'benchmark input changed')
    return p,q

def spec(p,q,path,pin):
    code=str(Path(q['trainer']).parent)
    K=module(Path(p['out'])/'tools/r3_final_container.py')
    return {'name':p['container']+'-a1','image':IMAGE,'cmd':['-B','-P',p['benchmark'],
        '--plan',p['benchmark_plan'],'--sha256',p['benchmark_sha256']],
        'mounts':{p['out']:True,code:False,MODEL:False,TRAIN:False,
                  p['benchmark_plan']:False,str(path):False,str(Path(p['out'])/'tools'):False},
        'devices':['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(p['chip'])],
        'environment':{**K.ENV,'NGA_R0_CODE':code+'/r0_code'}}

def verify_container(p,s,a,cid=None):
    root=Path(p['out'])/'tools';K=module(root/'r3_final_container.py');L=module(root/'r3_formal_launcher.py')
    K.verify_observation(s,a,cid)
    image=json.loads(subprocess.check_output(['docker','image','inspect',IMAGE],text=True))[0]
    L.verify_effective_policy(a,image,s['environment'])
    require(all(m.get('Propagation')=='rprivate' for m in a['Mounts']),'nonprivate propagation')
    host=a['HostConfig']
    require(host.get('ShmSize')==64*1024**3,'shared memory differs')
    limits=host.get('Ulimits') or []
    require(len(limits)==2 and {(v.get('Name'),v.get('Soft'),v.get('Hard')) for v in limits}==
        {('memlock',-1,-1),('stack',67108864,67108864)},'ulimits differ')
    devices=host.get('Devices',[])
    require(len(devices)==len(s['devices']) and {(v.get('PathOnHost'),v.get('PathInContainer'),v.get('CgroupPermissions')) for v in devices}==
        {(p,p,'rwm') for p in s['devices']},'device mapping differs')
    return a

def args(p,proof,name):
    root=Path(p['out'])/'attempts/1'
    return types.SimpleNamespace(alloc=p['allocation'],run=p['run'],chip=p['chip'],container=name,
        owner='K2 engineering',purpose=('Reference-only gradient repeat diagnostic' if p.get('schema','').startswith('r3-k2-reference-trace-execution-') else 'Paired scalar-transfer correctness and throughput'),
        claim=str(root/'CLAIM.json'),proof=str(root/(proof+'.json')),
        container_id=load(root/'LAUNCH_RECEIPT.json')['id'] if proof=='RELEASE' else None)

def supervise(path,pin):
    p,q=verify(path,pin);out=Path(p['out']);attempt=out/'attempts/1';attempt.mkdir(parents=True,exist_ok=True)
    with (out/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (attempt/'SUPERVISOR_DONE.json').exists():return load(attempt/'SUPERVISOR_DONE.json')
        R=module(out/'tools/r3_resource_adapter.py');K=module(out/'tools/r3_final_container.py')
        s=spec(p,q,path,pin);intent=attempt/'LAUNCH_INTENT.json';receipt=attempt/'LAUNCH_RECEIPT.json'
        if (attempt/'RELEASE.json').exists():
            terminal=load(attempt/'EXIT.json');proof=load(attempt/'RELEASE.json')
            require(terminal.get('plan_sha256')==pin and proof.get('run')==p['run'] and proof.get('chip')==p['chip'] and proof.get('exit_code')==terminal.get('container_exit_code') and proof.get('container_id')==load(receipt)['id'],'released evidence differs')
            atomic(attempt/'SUPERVISOR_DONE.json',terminal);return terminal
        if (attempt/'RELEASE.json.intent').exists():
            terminal=load(attempt/'EXIT.json');require(terminal.get('plan_sha256')==pin,'release intent terminal differs')
            R.release(args(p,'RELEASE',s['name']));proof=load(attempt/'RELEASE.json')
            require(proof.get('container_id')==load(receipt)['id'] and proof.get('exit_code')==terminal.get('container_exit_code'),'release recovery differs')
            atomic(attempt/'SUPERVISOR_DONE.json',terminal);return terminal
        while not (attempt/'CLAIM.json').exists():
            ledger=R.load(p['allocation']);R.validate_doc(ledger)
            if (attempt/'CLAIM.json.intent').exists() or (any(x['chip']==p['chip'] for x in ledger['free']) and not R.live_chip_conflict(p['chip'],'')):
                R.claim(args(p,'CLAIM',''));break
            atomic(out/'digest.json',{'state':'waiting_resource','utc_seconds':time.time()});time.sleep(15)
        require(any(x['chip']==p['chip'] and x['run']==p['run'] for x in R.load(p['allocation'])['allocation']),'ownership changed')
        command=K.command(s);a=R.docker_inspect(s['name'])
        if not intent.exists():
            require(a is None and not receipt.exists() and not Path(q['out']).exists(),'existing execution evidence')
            verify(path,pin);require(not R.live_chip_conflict(p['chip'],s['name']),'device conflict')
            atomic(intent,{'command':command,'pin':pin})
            try:subprocess.run(command,capture_output=True,check=True,timeout=90)
            except (OSError,subprocess.SubprocessError):pass  # inspect same name, never launch twice
        else:require(load(intent)=={'command':command,'pin':pin},'intent differs')
        cid=load(receipt)['id'] if receipt.exists() else None
        while True:
            try:
                a=R.docker_inspect(s['name'])
                if a is None:raise RuntimeError('launch observation pending; no duplicate launch')
                verify_container(p,s,a,cid)
            except (OSError,subprocess.SubprocessError,RuntimeError) as e:
                atomic(out/'digest.json',{'state':'observation_uncertain','reason':str(e)[:200],'utc_seconds':time.time()});time.sleep(30);continue
            if cid is None:
                cid=a['Id'];atomic(receipt,{'id':cid,'image':IMAGE,'sha256':pin})
            if a['State']['Status'] in ('exited','dead'):break
            atomic(out/'digest.json',{'state':'running','container_id':cid,'utc_seconds':time.time()});time.sleep(30)
        marker=Path(q['out'])/'EXIT.json';driver=load(marker) if marker.exists() else None
        code=a['State']['ExitCode'];valid=driver is not None and driver.get('plan_sha256')==p['benchmark_sha256'] and driver.get('exit_code')==code
        trace = p.get('schema','').startswith('r3-k2-reference-trace-execution-')
        result=Path(q['out'])/('TRACE.json' if trace else 'RESULT.json');ok=valid and code==0 and result.exists()
        if ok:
            d=load(result)
            evidence_ok = (d.get('schema')=='r3-k2-reference-trace-v1' and d.get('complete') is True
                           and d.get('truncated') is False and type(d.get('reference_questions')) is int
                           and 0<d['reference_questions']<=32 and d.get('repeat_questions')==d['reference_questions']
                           and len(d.get('comparisons',[]))==d['reference_questions']) if trace else d.get('exact_loss_and_gradients') is True
            if p.get('schema') == 'r3-k2-reference-trace-execution-v2':
                evidence_ok = evidence_ok and d.get('boundary',{}).get('complete') is True and d.get('control',{}).get('complete') is True
            ok=evidence_ok and d.get('plan_sha256')==p['benchmark_sha256'] and d.get('test_read') is False and d.get('scientific_acceptance') is False
        terminal={'exit_code':0 if ok else (code or 125),'container_exit_code':code,'attempt':1,'plan_sha256':pin,
            'benchmark_complete':ok and not trace,'result_sha256':sha(result) if ok else None,'test_read':False,'scientific_acceptance':False}
        if trace:terminal['diagnostic_complete']=ok
        atomic(attempt/'EXIT.json',terminal);atomic(out/'ENGINEERING_EVAL_EXIT.json',terminal)
        with (attempt/'container.log').open('wb') as f:subprocess.run(['docker','logs',cid],stdout=f,stderr=subprocess.STDOUT,timeout=30)
        R.release(args(p,'RELEASE',s['name']));atomic(attempt/'SUPERVISOR_DONE.json',terminal);atomic(out/'digest.json',terminal)
        return terminal

def start(path,pin):
    require(socket.gethostname()=='k8s-node1','host175 only');p,q=verify(path,pin);out=Path(p['out'])
    cmd=[sys.executable,'-P',p['launcher'],'supervise','--plan',str(path),'--sha256',pin,'--attempt','1']
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);receipt=out/'SUPERVISOR_RECEIPT.json'
        if receipt.exists():
            old=load(receipt);proc=Path('/proc')/str(old['pid'])/'cmdline'
            if proc.exists() and proc.read_bytes().rstrip(b'\0').split(b'\0')==[os.fsencode(x) for x in cmd]:return old
            require(not (out/'attempts/1/SUPERVISOR_DONE.json').exists(),'already complete')
        with (out/'supervisor.log').open('ab') as log:child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        value={'pid':child.pid,'command':cmd};atomic(receipt,value)
        atomic(out/'RELAUNCH.json',{'command':[sys.executable,'-P',p['launcher'],'start','--plan',str(path),'--sha256',pin],'note':'same-container observation only; never clear intents'})
        return value

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('op',choices=('verify','start','supervise'));parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--attempt',type=int,default=1);a=parser.parse_args()
    require(a.attempt==1,'only first attempt')
    if a.op=='verify':verify(a.plan,a.sha256);print('K2_BENCHMARK_VERIFIED')
    else:print(json.dumps(start(a.plan,a.sha256) if a.op=='start' else supervise(a.plan,a.sha256)))
