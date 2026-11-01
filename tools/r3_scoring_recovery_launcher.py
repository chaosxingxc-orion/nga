"""Host-175 engineering-only three-container dev scoring recovery experiment.

One guarded claim spans reference -> deliberate child SIGKILL -> resume. The
wrapper mirrors child SIGKILL as container exit 137. Every phase is retained.
A supervisor may resume observation with the SAME attempt after disconnect;
uncertain launches never cause another docker run. Scientific acceptance and
candidate test access are outside this experiment.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

BASE=Path('/mnt/cephfs/xingchao/experiments/jev')
IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
PHASES=('reference','interrupt','resume')
TOOLS=('r3_scoring_recovery_launcher.py','r3_resource_adapter.py','r3_final_container.py')


def require(ok,message):
    if not ok:raise ValueError(message)
def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(c in str(p) for c in ',\n\r'),'unsafe absolute path')
    require(not any(q.is_symlink() for q in (p,*p.parents)),'symlink path')
    return p

def atomic(path,value):
    path=Path(path);fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        os.fchmod(fd,0o644)
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def module(path,name):
    # Execute the source checked by the frozen plan, never adjacent bytecode.
    import types
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe helper source')
    raw=path.read_bytes();m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(raw,str(path),'exec',dont_inherit=True),m.__dict__)
    return m

def protocol_counts(q):
    counts = {'r3-dev-scoring-recovery-v1': (4, 2),
              'r3-dev-scoring-recovery-v2': (32, 32)}
    require(q.get('schema') in counts, 'probe schema differs')
    per_suite, chunk = counts[q['schema']]
    require(q['protocol'] == {'records_per_suite': per_suite, 'chunk': chunk,
            'mode': 'rightpad', 'dtype': 'float32', 'hf32': False,
            'token_budget': 16384, 'max_abs_nats': 1e-3}, 'probe protocol differs')
    return per_suite, chunk


def verify(path,pin):
    path=safe(path);require(sha(path)==pin,'execution plan changed');p=load(path)
    require(p['schema']=='r3-scoring-recovery-execution-v1' and p['test_read'] is False
            and p['scientific_acceptance'] is False,'execution scope differs')
    out=safe(p['out']);require(path.parent==out and out.is_relative_to(BASE/'r3_runs'),'output differs')
    require(p['run']==str(out.relative_to(BASE)) and p['allocation']==str(BASE/'CHIP-ALLOCATION.json'),'ledger identity differs')
    require(type(p['chip']) is int and p['chip'] in range(8),'invalid chip')
    require(re.fullmatch(r'nga-r3-eng-recovery-[a-z0-9-]+',p['container']) is not None,'invalid container')
    require(p['image']==IMAGE,'image differs')
    require(Path(p['launcher'])==Path(__file__).resolve(),'launcher outside frozen tools')
    require(set(p['tools'])=={str(out/'execution-tools'/n) for n in TOOLS},'tool inventory differs')
    for filename,pinned in p['tools'].items():require(sha(safe(filename))==pinned,'execution tool differs')
    require(p['resource_adapter']==str(out/'execution-tools/r3_resource_adapter.py'),'adapter differs')
    require(sha(safe(p['probe_plan']))==p['probe_plan_sha256'],'probe plan changed');q=load(p['probe_plan'])
    require(q['test_read'] is False and q['scientific_acceptance'] is False,'probe scope differs')
    require(safe(q['out'])==out/'results','probe output differs')
    require(sha(safe(p['probe']))==q['probe_sha256'],'probe implementation differs')
    per_suite, chunk = protocol_counts(q)
    require(set(q['sources'])=={'decision-v7','transfer-v4'},'source suites differ')
    for suite,entry in q['sources'].items():
        source=safe(entry['path'])
        require(source==BASE/'KEV'/suite/'dev.jsonl' and sha(source)==entry['sha256'] and entry['indices']==list(range(per_suite)),'native dev source differs')
    root=safe(q['closure']['root']);require(sha(root/'manifest.json')==q['closure']['sha256'],'closure manifest differs')
    manifest=load(root/'manifest.json')
    require(manifest['schema']=='r3-final-closure-v1','closure schema differs')
    require({str(f.relative_to(root)) for f in root.rglob('*') if f.is_file() and f!=root/'manifest.json'}==set(manifest['files']),'closure file inventory differs')
    for rel,pinned in manifest['files'].items():
        source=safe(root/rel);require(source.is_relative_to(root) and sha(source)==pinned,'closure code differs')
    require(sha(safe(q['base_inventory']['path']))==q['base_inventory']['sha256'],'inventory artifact differs')
    require(safe(q['model'])==safe(load(q['base_inventory']['path'])['inventory']['root']),'model inventory root differs')
    require(sha(safe(q['adapter_inventory']['path']))==q['adapter_inventory']['sha256'],'adapter inventory artifact differs')
    require(safe(q['adapter'])==safe(load(q['adapter_inventory']['path'])['inventory']['root']),'adapter inventory root differs')
    return p,q


def bind(probe_plan,probe,chip,container):
    source=safe(probe_plan);out=source.parent;q=load(source)
    require(out.is_relative_to(BASE/'r3_runs') and safe(q['out'])==out/'results','output must be fresh r3_runs/results')
    require(not (out/'results').exists() and not (out/'execution.json').exists(),'existing experiment output')
    frozen=out/'execution-tools';frozen.mkdir()
    for name in TOOLS:shutil.copy2(Path(__file__).with_name(name),frozen/name)
    p={'schema':'r3-scoring-recovery-execution-v1','out':str(out),'run':str(out.relative_to(BASE)),
       'chip':chip,'container':container,'image':IMAGE,'allocation':str(BASE/'CHIP-ALLOCATION.json'),
       'launcher':str(frozen/TOOLS[0]),'resource_adapter':str(frozen/TOOLS[1]),
       'tools':{str(frozen/n):sha(frozen/n) for n in TOOLS},'probe':str(safe(probe)),
       'probe_plan':str(source),'probe_plan_sha256':sha(source),'test_read':False,'scientific_acceptance':False}
    path=out/'execution.json';atomic(path,p);return path,sha(path)


def contract(p,q,path,pin,phase,attempt):
    require(phase in PHASES and attempt==1,'only first attempt; same-attempt observation recovery supported')
    out=safe(p['out']);root=safe(q['closure']['root']);model=safe(q['model'])
    # No general dataset mount. Exactly two development files are exposed.
    sources=[safe(x['path']) for x in q['sources'].values()]
    require(len(sources)==2 and all(x.name=='dev.jsonl' for x in sources),'dev-only mounts required')
    for frozen in (root,model,safe(q['adapter']),*sources):
        require(out!=frozen and not out.is_relative_to(frozen) and not frozen.is_relative_to(out),'writable/frozen overlap')
    mounts={str(out):True,str(root):False,str(model):False,str(safe(q['adapter'])):False,
        str(safe(q['adapter_inventory']['path'])):False,str(safe(path)):False,
        str(safe(p['probe_plan'])):False,str(safe(p['probe'])):False,
        str(out/'execution-tools'):False,str(safe(q['base_inventory']['path'])):False,
        **{str(x):False for x in sources}}
    name=p['container']+'-a1'+('' if phase=='resume' else '-'+phase)
    K=module(out/'execution-tools/r3_final_container.py','recovery_contract')
    return {'name':name,'image':IMAGE,'mounts':mounts,'environment':K.ENV.copy(),
        'devices':['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc',f"/dev/davinci{p['chip']}"],
        'cmd':['-B','-P',p['launcher'],'drive','--plan',str(path),'--sha256',pin,'--phase',phase,'--attempt','1']}


def outcome(p,q,phase,observed):
    per_suite, chunk = protocol_counts(q)
    total = 2 * per_suite
    require(observed['State']['Status'] in ('exited','dead'),'phase container still live')
    code=observed['State']['ExitCode'];require(type(code) is int,'noninteger actual exit')
    work=Path(q['out'])/('reference' if phase=='reference' else 'interrupted')
    if phase=='interrupt':
        require(code==137,'interrupt did not exit with expected SIGKILL 137')
        evidence=load(work/'INTERRUPT_READY.json')
        require(evidence.get('plan_sha256')==p['probe_plan_sha256'] and evidence.get('committed')==chunk
                and len(evidence.get('keys',[]))==chunk and len(set(evidence['keys']))==chunk,'missing or invalid interruption proof')
    else:
        require(code==0,'reference/resume failed')
        evidence=load(work/'DONE.json')
        require(evidence.get('plan_sha256')==p['probe_plan_sha256'] and evidence.get('phase')==phase and evidence.get('rows')==total and evidence.get('test_read') is False
                and evidence.get('scientific_acceptance') is False,'phase completion evidence differs')
        require(evidence.get('newly_scored')==(total if phase=='reference' else total-chunk),'scoring count differs')
        if phase=='resume':
            require(evidence.get('status')=='ENGINEERING_RECOVERY_PASS' and evidence.get('committed_reused')==chunk,'resume result differs')
            value=evidence.get('max_abs_nats');require(type(value) in (float,int) and 0<=value<=1e-3,'resume score deviation differs')
    return {'phase':phase,'container_id':observed['Id'],'container_exit_code':code,
            'expected_exit':True,'evidence':evidence,'scientific_acceptance':False,'test_read':False}


def drive(path,pin,phase):
    p,q=verify(path,pin);directory=Path(p['out'])/'attempts/1'/phase;directory.mkdir(parents=True,exist_ok=True)
    with (directory/'driver.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return drive_locked(path,pin,phase)


def drive_locked(path,pin,phase):
    p,q=verify(path,pin);directory=Path(p['out'])/'attempts/1'/phase;directory.mkdir(parents=True,exist_ok=True)
    cmd=['python3','-B','-P',p['probe'],'--plan',p['probe_plan'],'--sha256',p['probe_plan_sha256'],'--phase',phase]
    require(not (directory/'DRIVER_EXIT.json').exists(),'phase driver already terminal')
    atomic(directory/'COMMAND.json',{'command':cmd});process=None;rc=125
    try:
        with (directory/'run.log').open('ab',buffering=0) as log:
            process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd='/tmp')
            def stop(sig,frame):
                try:os.killpg(process.pid,sig)
                except ProcessLookupError:pass
            signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
            count=0
            while process.poll() is None:
                count+=1
                heartbeat={'utc':utc(),'phase':phase,'pid':process.pid,'heartbeat_count':count,
                    'readout_bytes':sum(f.stat().st_size for f in Path(q['out']).rglob('readouts.jsonl'))}
                atomic(directory/'heartbeat.json',heartbeat)
                log.write((json.dumps(heartbeat)+'\n').encode())
                time.sleep(15)
            rc=process.returncode if process.returncode>=0 else 128-process.returncode
    except BaseException as error:
        rc=125
        atomic(directory/'DRIVER_ERROR.json',{'type':type(error).__name__,'reason':str(error)[:300]})
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        atomic(directory/'DRIVER_EXIT.json',{'exit_code':rc,'phase':phase,'plan_sha256':pin,'utc':utc()})
    return rc


def observe(R,K,spec,cid,digest,sleep=time.sleep):
    while True:
        try:
            actual=R.docker_inspect(spec['name'])
            if actual is None:raise RuntimeError('retained container missing')
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
            atomic(digest,{'utc':utc(),'state':'observation_unknown','container':spec['name'],
                'action':'observe_same_container_without_relaunch','error':str(error)[:200]})
            sleep(30);continue
        return K.verify_observation(spec,actual,cid)


def phase_run(p,q,path,pin,phase,R,K,directory):
    spec=contract(p,q,path,pin,phase,1);directory.mkdir(exist_ok=True)
    intent=directory/'LAUNCH_INTENT.json';receipt=directory/'LAUNCH_RECEIPT.json';digest=directory/'digest.json'
    command=K.command(spec);expected={'plan_sha256':pin,'phase':phase,'command':command}
    actual=R.docker_inspect(spec['name'])
    if actual is None and not intent.exists() and not receipt.exists():
        require(not R.live_chip_conflict(p['chip'],spec['name']),'another phase or job still owns device')
        require(not (directory/'DRIVER_EXIT.json').exists(),'phase driver already exists')
        atomic(intent,expected)
        try:subprocess.run(command,check=True,capture_output=True,timeout=90)
        except (subprocess.SubprocessError,OSError) as error:
            atomic(digest,{'utc':utc(),'state':'launch_uncertain','error':str(error)[:200]})
        actual=observe(R,K,spec,None,digest)
    else:
        require(intent.exists() and load(intent)==expected,'unexpected retained phase or intent')
        cid=load(receipt)['id'] if receipt.exists() else None
        actual=observe(R,K,spec,cid,digest) if actual is None else K.verify_observation(spec,actual,cid)
    if receipt.exists():require(load(receipt)['id']==actual['Id'],'phase generation changed')
    else:atomic(receipt,{'id':actual['Id'],'image':actual['Image'],'sha256':pin})
    cid=actual['Id']
    while actual['State']['Status'] not in ('exited','dead'):
        atomic(digest,{'utc':utc(),'state':'running','container_id':cid});time.sleep(30)
        actual=observe(R,K,spec,cid,digest)
    with (directory/'container.log').open('wb') as f:
        subprocess.run(['docker','logs',cid],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=30)
    # Actual container exit is durable even if the wrapper was killed externally.
    marker=directory/'DRIVER_EXIT.json'
    if marker.exists():require(load(marker)=={'exit_code':actual['State']['ExitCode'],'phase':phase,'plan_sha256':pin,'utc':load(marker)['utc']},'wrapper/container exit mismatch')
    atomic(directory/'ACTUAL_EXIT.json',{'container_id':cid,'exit_code':actual['State']['ExitCode'],'phase':phase,'plan_sha256':pin})
    try:result=outcome(p,q,phase,actual)
    except (ValueError,KeyError,FileNotFoundError,TypeError) as error:
        result={'phase':phase,'expected_exit':False,'container_id':cid,'container_exit_code':actual['State']['ExitCode'],'error':str(error)[:300]}
    atomic(directory/'RESULT.json',result)
    return spec,actual,result


def resource_args(p,directory,name,op):
    return SimpleNamespace(alloc=p['allocation'],run=p['run'],chip=p['chip'],container=name,
        owner='R3 scoring recovery',purpose='Eight dev records; real scoring process interruption recovery',
        claim=str(directory/'CLAIM.json'),proof=str(directory/(op.upper()+'.json')))


def supervise(path,pin,attempt):
    require(socket.gethostname()=='k8s-node1' and attempt==1,'host175 first attempt required')
    p,q=verify(path,pin);out=Path(p['out']);directory=out/'attempts/1';directory.mkdir(parents=True,exist_ok=True)
    lock=(out/'supervisor.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    R=module(p['resource_adapter'],'recovery_resource');K=module(out/'execution-tools/r3_final_container.py','recovery_container')
    try:
        if (directory/'SUPERVISOR_DONE.json').exists():return load(directory/'SUPERVISOR_DONE.json')
        if (directory/'RELEASE.json.intent').exists() and not (directory/'RELEASE.json').exists():
            terminal=load(directory/'EXIT.json');last_phase=terminal['phases'][-1]['phase']
            require(terminal['plan_sha256']==pin,'release-intent terminal differs')
            spec=contract(p,q,path,pin,last_phase,1)
            # Adapter reconciles its exact before/after ledger snapshots.
            R.release(resource_args(p,directory,spec['name'],'release'))
        if (directory/'RELEASE.json').exists():
            # Crash after release must not revisit device ownership now held by
            # another job. Complete only the already durable terminal record.
            terminal=load(directory/'EXIT.json');proof=load(directory/'RELEASE.json')
            require(terminal['plan_sha256']==pin and proof['run']==p['run'] and proof['chip']==p['chip']
                    and terminal['container_exit_code']==proof['exit_code'],'released terminal differs')
            atomic(directory/'SUPERVISOR_DONE.json',terminal);atomic(out/'digest.json',terminal)
            return terminal
        require(subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()==IMAGE,'actual image differs')
        while not (directory/'CLAIM.json').exists():
            ledger=R.load(p['allocation']);R.validate_doc(ledger)
            if (directory/'CLAIM.json.intent').exists() or (any(x['chip']==p['chip'] for x in ledger['free']) and not R.live_chip_conflict(p['chip'],'')):
                R.claim(resource_args(p,directory,'','claim'));break
            atomic(out/'digest.json',{'utc':utc(),'state':'waiting_resource','test_read':False});time.sleep(15)
        claim=load(directory/'CLAIM.json');require(claim['run']==p['run'] and claim['chip']==p['chip'],'claim identity differs')
        require(any(x['chip']==p['chip'] and x['run']==p['run'] for x in R.load(p['allocation'])['allocation']) or (directory/'RELEASE.json').exists(),'claim ownership differs')
        results=[];last=None
        for phase in PHASES:
            # Revalidate code/data before exposing a new process to its inputs.
            verify(path,pin)
            require(any(x['chip']==p['chip'] and x['run']==p['run'] for x in R.load(p['allocation'])['allocation']),
                    'claim ownership changed between phases')
            spec,actual,result=phase_run(p,q,path,pin,phase,R,K,directory/phase)
            results.append(result);last=(spec,actual)
            if not result['expected_exit']:break
        success=len(results)==3 and all(r['expected_exit'] for r in results)
        spec,actual=last
        terminal={'exit_code':0 if success else (actual['State']['ExitCode'] or 125),
            'container_exit_code':actual['State']['ExitCode'],'attempt':1,'plan_sha256':pin,
            'engineering_recovery_complete':success,'phases':results,'scientific_acceptance':False,'test_read':False}
        atomic(directory/'EXIT.json',terminal);atomic(out/'ENGINEERING_EVAL_EXIT.json',terminal)
        # One claim spans phases. All preceding phases have proved actual exit.
        atomic(directory/'LAUNCH_RECEIPT.json',{'id':actual['Id'],'image':IMAGE,'sha256':pin})
        R.release(resource_args(p,directory,spec['name'],'release'))
        atomic(directory/'SUPERVISOR_DONE.json',terminal);atomic(out/'digest.json',terminal)
        return terminal
    except BaseException as error:
        atomic(out/'digest.json',{'utc':utc(),'state':'supervisor_needs_repair','error':str(error)[:300],
            'action':'inspect bounded diagnosis; do not clear launch intents or infer device release',
            'scientific_acceptance':False,'test_read':False})
        raise
    finally:lock.close()


def start(path,pin,attempt):
    require(socket.gethostname()=='k8s-node1' and attempt==1,'host175 first attempt required')
    p,q=verify(path,pin);out=Path(p['out'])
    command=[sys.executable,'-P',p['launcher'],'supervise','--plan',str(path),'--sha256',pin,'--attempt','1']
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'SUPERVISOR_RECEIPT.json').exists():
            old=load(out/'SUPERVISOR_RECEIPT.json');proc=Path('/proc')/str(old['pid'])/'cmdline'
            if proc.exists() and proc.read_bytes().rstrip(b'\0').split(b'\0')==[os.fsencode(x) for x in command]:return old
            require(not (out/'attempts/1/SUPERVISOR_DONE.json').exists(),'experiment already complete')
        with (out/'supervisor.log').open('ab',buffering=0) as log:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        receipt={'pid':process.pid,'command':command};atomic(out/'SUPERVISOR_RECEIPT.json',receipt)
        atomic(out/'RELAUNCH.json',{'command':[sys.executable,'-P',p['launcher'],'start','--plan',str(path),'--sha256',pin,'--attempt','1'],
            'note':'Resume observation with same attempt only; never clear intents or repeat failed phase.'})
        return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('op',choices=('bind','verify','start','supervise','drive'))
    parser.add_argument('--plan',required=True);parser.add_argument('--sha256');parser.add_argument('--attempt',type=int,default=1)
    parser.add_argument('--phase',choices=PHASES);parser.add_argument('--probe');parser.add_argument('--chip',type=int);parser.add_argument('--container')
    a=parser.parse_args()
    if a.op=='bind':
        path,pin=bind(a.plan,a.probe,a.chip,a.container);print(json.dumps({'plan':str(path),'sha256':pin}))
    elif a.op=='drive':sys.exit(drive(a.plan,a.sha256,a.phase))
    elif a.op=='verify':verify(a.plan,a.sha256);print('DEV_SCORING_RECOVERY_VERIFIED')
    elif a.op=='start':print(json.dumps(start(a.plan,a.sha256,a.attempt)))
    else:print(json.dumps(supervise(a.plan,a.sha256,a.attempt)))
