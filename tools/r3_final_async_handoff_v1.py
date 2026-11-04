"""Exact-plan post-release CPU dispatch; never allocates or invokes a scorer.

Launch intent is durable before Popen. An uncertain dispatch is never blindly
repeated. A new attempt/config is required after reconciliation of a failed CPU
process; existing scientific reservations and score records remain authoritative.
"""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time,traceback,threading
from pathlib import Path


def sibling(name):
    loader=globals().get('__loader__')
    if hasattr(loader,'sources') and hasattr(loader,'load'):return loader.load(name)
    import types
    p=Path(__file__).with_name(name+'.py');m=types.ModuleType(name);m.__file__=str(p)
    exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
D=sibling('r3_final_driver');A=sibling('r3_final_admission');K=sibling('r3_final_container')
R=sibling('r3_resource_adapter');V=sibling('r3_final_async_release_v1')


def validate_cpu(plan):
    cfg=plan.get('cpu_execution');A.require(isinstance(cfg,dict) and set(cfg)=={'python','environment'},'CPU execution config required')
    A.C.safe(cfg['python']);A.require(Path(cfg['python']).is_file(),'CPU interpreter absent')
    env=cfg['environment'];A.require(isinstance(env,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in env.items()),'CPU environment differs')
    A.require(env.get('PYTHONDONTWRITEBYTECODE')=='1' and env.get('TORCH_DEVICE_BACKEND_AUTOLOAD')=='0','CPU environment must disable bytecode/device autoload')
    return cfg


def verify_release(plan,path,pin,review,attempt):
    owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,final_sha256=plan['final']['sha256'])
    mp=V.G.digest(V.X.load_scored(Path(plan['out']),owner))
    spec=K.contract(plan,str(path),pin,review,attempt)
    return V.validate(plan,pin,attempt,owner,mp,spec=spec,observe=R.docker_inspect)


def cpu_command(plan,path,pin,review,attempt):
    return [plan['cpu_execution']['python'],'-B','-P',str(Path(__file__).resolve()),'consume','--plan',str(path),'--sha256',pin,'--review',review['path'],'--review-sha256',review['sha256'],'--attempt',str(attempt)]

def process_generation(pid):
    p=Path('/proc')/str(pid)
    return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'start_ticks':int((p/'stat').read_text().rsplit(')',1)[1].split()[19]),
        'command':(p/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')}


def generation_gone(record):
    # Read failures are uncertainty, not proof of exit. Zombies have exited.
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if record['boot_id']!=boot:return True
    p=Path('/proc')/str(record['pid'])
    try:stat=(p/'stat').read_text().rsplit(')',1)[1].split()
    except FileNotFoundError:return True
    return int(stat[19])!=record['start_ticks'] or stat[0]=='Z'


def acquire(root,name,blocking=False):
    fd=os.open(A.C.safe(root/name),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|(0 if blocking else fcntl.LOCK_NB))
    except BaseException:os.close(fd);raise
    return fd


def reconcile_prior_cpu(plan,pin,attempt):
    """Fence an exited failed consumer before a later NPU attempt may start."""
    for number in range(1,attempt):
        root=A.C.safe(Path(plan['out'])/'cpu-final-attempts'/str(number))
        previous=Path(plan['out'])/'supervisor-attempts'/str(number)
        done=json.loads((previous/'DONE.json').read_text())
        if not root.exists():
            A.require(done.get('exit_code')!=0 and not (previous/'CPU-DISPATCH.json').exists(),
                      'prior successful score lacks reconciled CPU dispatch')
            continue
        dispatch=acquire(root,'dispatch.lock')
        try:
            consumer=acquire(root,'consumer.lock')
            try:
                A.require((root/'EXIT.json').exists(),'prior CPU dispatch unresolved')
                terminal=json.loads((root/'EXIT.json').read_text())
                A.require(terminal.get('plan_sha256')==pin and terminal.get('attempt')==number and
                          type(terminal.get('exit_code')) is int,'prior CPU terminal differs')
                A.require(terminal.get('publication_complete') is False and terminal['exit_code']!=0,
                          'completed CPU publication cannot restart')
                records=[]
                for name in ('SERVICE.json','CONSUMER.json'):
                    if (root/name).exists():records.append(json.loads((root/name).read_text()))
                A.require(records,'prior CPU has no process generation evidence')
                for record in records:
                    A.require(record.get('plan_sha256')==pin and record.get('attempt')==number,
                              'prior CPU process binding differs')
                    A.require(generation_gone(record),'prior CPU process still live')
                # Prevent a delayed duplicate consumer from starting after checks.
                D.atomic(root/'FENCED.json',{'plan_sha256':pin,'attempt':number,'next_attempt':attempt})
            finally:os.close(consumer)
        finally:os.close(dispatch)


def start_cpu(plan,path,pin,review,attempt):
    A.verify(plan,pin,review);cfg=validate_cpu(plan);verify_release(plan,path,pin,review,attempt)
    root=A.C.safe(Path(plan['out'])/'cpu-final-attempts'/str(attempt));root.mkdir(parents=True,exist_ok=True)
    lock=acquire(root,'dispatch.lock')
    try:
        A.require(not (root/'FENCED.json').exists(),'CPU attempt fenced')
        if (root/'EXIT.json').exists():
            terminal=json.loads((root/'EXIT.json').read_text());A.require(terminal.get('plan_sha256')==pin and terminal.get('attempt')==attempt,'CPU terminal differs');return {'state':'terminal','terminal':terminal}
        intent=root/'START-INTENT.json';service=root/'SERVICE.json'
        if intent.exists():
            return {'state':'already_dispatched_or_uncertain','intent':str(intent),'service':str(service) if service.exists() else None}
        cmd=cpu_command(plan,path,pin,review,attempt)
        D.atomic(intent,{'plan_sha256':pin,'attempt':attempt,'review':review,'command':cmd,'environment':cfg['environment'],'automatic_retry':False})
        try:
            D.atomic(root/'RELAUNCH.json',{'command':cmd,'environment':cfg['environment'],'policy':'Reconcile existing dispatch; do not blindly repeat.'})
            with (root/'consumer.log').open('ab',buffering=0) as log:
                process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,**cfg['environment']))
            generation=process_generation(process.pid)
            D.atomic(service,{**generation,'plan_sha256':pin,'attempt':attempt,'started_utc_seconds':time.time(),'scientific_acceptance':False})
            return {'state':'cpu_dispatched','pid':process.pid,'scientific_acceptance':False}
        except BaseException as error:
            # Do not write EXIT: spawn or service-write failure can leave a live child.
            D.atomic(root/'LAUNCH-ERROR.json',{'state':'launch_uncertain','error_type':type(error).__name__,
                'plan_sha256':pin,'attempt':attempt,'automatic_retry':False,'process_exit_confirmed':False,'utc_seconds':time.time()})
            raise
    finally:os.close(lock)


def consume(path,pin,review,attempt):
    path=A.C.safe(path);plan=json.loads(path.read_text());A.require(A.identity(plan)==pin,'CPU plan differs')
    root=A.C.safe(Path(plan['out'])/'cpu-final-attempts'/str(attempt));A.require(root.is_dir() and (root/'START-INTENT.json').exists(),'CPU dispatch intent absent')
    # Authenticate output ownership before writing even an error terminal.
    intent=json.loads((root/'START-INTENT.json').read_text())
    A.require(intent.get('plan_sha256')==pin and intent.get('attempt')==attempt,'foreign CPU intent')
    dispatch=acquire(root,'dispatch.lock',blocking=True)
    try:
        lock=acquire(root,'consumer.lock')
        try:
            A.require(not (root/'EXIT.json').exists() and not (root/'FENCED.json').exists(),'CPU terminal exists or attempt fenced')
            rc=1;state='preflight_rejected';stop=threading.Event();worker=None
            try:
                D.atomic(root/'CONSUMER.json',{**process_generation(os.getpid()),'plan_sha256':pin,'attempt':attempt})
                validate_cpu(plan)
                A.require(intent=={'plan_sha256':pin,'attempt':attempt,'review':review,'command':cpu_command(plan,path,pin,review,attempt),'environment':plan['cpu_execution']['environment'],'automatic_retry':False},'CPU dispatch intent differs')
                A.require(Path(__file__).resolve()==Path(plan['closure']['root'])/'r3_code/r3_final_async_handoff_v1.py','CPU consumer outside closure')
                def heartbeat():
                    while not stop.is_set():
                        D.atomic(root/'heartbeat.json',{'state':'cpu_verifying','plan_sha256':pin,'attempt':attempt,'utc_seconds':time.time(),'scientific_acceptance':False});stop.wait(30)
                worker=threading.Thread(target=heartbeat,daemon=True);worker.start();state='verification_failed'
                # Release dispatch lock only after ownership and consumer lock are established.
                os.close(dispatch);dispatch=None
                A.verify(plan,pin,review);verify_release(plan,path,pin,review,attempt)
                result=D.evaluate_cpu(plan,pin,review,path,attempt)
                A.require(result.get('state')=='completed','CPU publication incomplete');D.atomic(root/'RESULT.json',result);rc=0;state='completed'
            except BaseException:traceback.print_exc()
            finally:
                stop.set()
                if worker is not None:worker.join(5)
                D.atomic(root/'EXIT.json',{'exit_code':rc,'state':state,'plan_sha256':pin,'attempt':attempt,'publication_complete':rc==0,'scientific_acceptance':False,'finished_utc':D.utc()})
            return rc
        finally:os.close(lock)
    finally:
        if dispatch is not None:os.close(dispatch)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['consume']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--review',required=True);p.add_argument('--review-sha256',required=True);p.add_argument('--attempt',type=int,required=True);a=p.parse_args()
    raise SystemExit(consume(a.plan,a.sha256,{'path':a.review,'sha256':a.review_sha256},a.attempt))
