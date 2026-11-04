"""Isolated formal training continuation; unchanged trainer, explicit source and release.

One-shot activation only after independent exact-package review. This adapter
adds checkpoint import and resource prerequisites around the frozen launcher.
It does not alter the training command, model, optimizer or scheduler.
"""
import argparse, hashlib, json, os, subprocess, sys, time, types, fcntl, threading, socket
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)
def safe(path):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p
def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def read(path):return json.loads(safe(path).read_bytes())
def module(path,pin):
    path=safe(path);raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==pin,'source changed')
    m=types.ModuleType(path.stem);m.__file__=str(Path(__file__).resolve());exec(compile(raw,str(path),'exec'),m.__dict__);return m
def check_state_manifest(p):
    r=p['recovery'];root=safe(p['out']);origin=read(r['source_plan']['path'])
    need(sha(r['source_plan']['path'])==r['source_plan']['sha256'],'source plan changed')
    need(sha(r['original_checkpoint']['path'])==r['original_checkpoint']['sha256']==r['checkpoint']['sha256'],'original checkpoint changed')
    need(Path(r['original_checkpoint']['path'])==Path(origin['out'])/'ckpt/step_002400.pt','original checkpoint owner differs')
    failed=read(r['failed_release']['path']);need(sha(r['failed_release']['path'])==r['failed_release']['sha256'],'failed release changed')
    need(failed['run']==origin['run'] and failed['chip']==3 and failed['exit_code']==1 and failed['container']==origin['container']+'-a1','original failure identity differs')
    original_review=read(origin['review_path']);need(sha(origin['review_path'])==origin['review_sha256'] and original_review['approved_plan_sha256']==hashlib.sha256((json.dumps(dict(origin,review_sha256='PENDING'),sort_keys=True,indent=2)+'\n').encode()).hexdigest() and original_review['verdict']=='PASS','original training review differs')
    need(p['control_arm']==origin['control_arm']=='K1-PT' and p['seed']==origin['seed']==2,'control changed')
    need(p['chip']==origin['chip']==3 and p['formal_chips']==origin['formal_chips']==[3,4],'formal chip binding changed')
    command=list(origin['command']);command[command.index('--out')+1]=str(root)
    need(p['command']==command,'training recipe changed')
    for k in ('model','train_file','environment','image_sha256','evaluation','control'):
        need(p[k]==origin[k],'source field differs: '+k)
    for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
        need(sha(Path(p['code'])/rel)==origin['files'][str(Path(origin['code'])/rel)],'training source changed')
    need(sha(Path(p['code'])/'r3_original_formal_driver.py')==origin['files'][str(Path(origin['code'])/'r3_formal_driver.py')],'original driver changed')
    need(r['source_step']==2400 and r['total_steps']==3116,'resume cursor changed')
    need(sha(r['checkpoint']['path'])==r['checkpoint']['sha256'],'checkpoint changed')
    need(Path(r['checkpoint']['path'])==root/'SOURCE.pt','checkpoint location changed')
    binding=read(r['cpu_binding']['path']);need(sha(r['cpu_binding']['path'])==r['cpu_binding']['sha256'],'CPU binding changed')
    need(binding['status']=='PASS_CPU_STATE_BINDING' and binding['checkpoint_sha256']==r['checkpoint']['sha256'] and binding['step']==2400 and binding['parameter_count']==372 and binding['optimizer_state_exact_after_load'] and binding['scheduler_exact_after_load'],'CPU binding incomplete')
    return r

def verify_review(p,pin):
    ref=p['recovery']['review'];review=read(ref['path'])
    need(review.get('verdict')=='PASS' and review.get('approved_plan_sha256')==pin and review.get('scope')=='exact-pt2-step2400-recovery-no-scientific-acceptance','exact recovery review required')
    need(review.get('reviewer_agent_id') not in (None,'','/root','/root/pt2_resume_prepare','/root/pt2_resume_fix_v2') and review.get('scientific_acceptance') is False,'independent scope required')
    need(sha(ref['path'])==p['review_sha256'],'review pin differs')

def verify_import(p,claim_phase=False):
    r=check_state_manifest(p);root=Path(p['out'])
    need((claim_phase or not (root/'attempts').exists()) and not (root/'adapter').exists() and not (root/'TRAIN_EXIT.json').exists(),'fresh attempt required')
    need(sorted(x.name for x in (root/'ckpt').iterdir())==['step_002400.pt'],'checkpoint inventory differs')
    need(sha(root/'ckpt/step_002400.pt')==r['checkpoint']['sha256'],'working checkpoint differs')
    need(sha(root/'losses.jsonl')==r['loss_prefix']['sha256'],'loss prefix changed')

def ready(p,observe):
    ref=p['recovery']['resource_predecessor'];root=Path(ref['out'])
    receipt=read(root/'attempts/1/LAUNCH_RECEIPT.json');claim=read(root/'attempts/1/CLAIM.json')
    need(sha(root/'attempts/1/LAUNCH_RECEIPT.json')==ref['receipt_sha256'] and receipt['id']==ref['container_id'],'predecessor generation changed')
    need(sha(root/'attempts/1/CLAIM.json')==ref['claim_sha256'] and claim['chip']==3,'predecessor claim changed')
    if not (root/'attempts/1/RELEASE.json').exists():return False
    release=read(root/'attempts/1/RELEASE.json')
    need(release.get('container_id')==receipt['id'] and release.get('chip')==3 and release.get('run')==claim['run'],'release identity differs')
    need(release.get('claim_sha256')==ref['claim_sha256'],'release claim differs')
    value=observe(ref['container'])
    need(value is not None and value['Id']==receipt['id'],'retained predecessor missing/different')
    need(value['State']['Status'] in ('exited','dead') and value['State']['Running'] is False,'predecessor still running')
    need(release.get('exit_code')==value['State']['ExitCode'],'release exit differs')
    need(value['State']['StartedAt']==release['container_started_at'] and value['State']['FinishedAt']==release['container_finished_at'] and value.get('RestartCount')==0,'predecessor timestamps/restarts differ')
    return True

def canonical(p):return hashlib.sha256((json.dumps(dict(p,review_sha256='PENDING'),sort_keys=True,indent=2)+'\n').encode()).hexdigest()
def put(path,value,exclusive=False):
    path=Path(path);temp=path if exclusive else path.with_suffix(path.suffix+'.tmp')
    with temp.open('x' if exclusive else 'w') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    if not exclusive:os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def successor_binding(p,pin,precondition_pin,required=True):
    need(p.get('successor_guard')=={'schema':'pt2-recovery-successor-v2','controller':p['launcher']},'guard differs')
    need(p['files'].get(p['launcher'])==sha(p['launcher']),'controller changed')
    if precondition_pin is None:
        need(not required,'precondition required');return
    pre=Path(p['out'])/'SUCCESSOR_PRECONDITION.json';need(sha(pre)==precondition_pin,'precondition changed')
    d=read(pre);need(d['plan_sha256']==pin and d['checkpoint_sha256']==p['recovery']['checkpoint']['sha256'],'precondition identity differs')

def claim_precondition(p,pin,precondition_pin,allocation,R):
    successor_binding(p,pin,precondition_pin);verify_review(p,pin);verify_import(p,claim_phase=True)
    need(ready(p,R.docker_inspect),'QO not released')
    ref=p['recovery']['resource_predecessor'];relpath=Path(ref['out'])/'attempts/1/RELEASE.json';release=read(relpath)
    pre=read(Path(p['out'])/'SUCCESSOR_PRECONDITION.json')
    need(pre['release_sha256']==sha(relpath),'release changed')
    free=[x for x in allocation['free'] if x['chip']==p['chip']]
    expected=[x for x in release['allocation_after']['free'] if x['chip']==p['chip']]
    need(len(free)==len(expected)==1 and free==expected and free[0]['previous_run']==release['run'] and free[0]['release_evidence']==str(relpath),'foreign free lineage')
    need(not any(x['chip']==p['chip'] for x in allocation['allocation']),'occupied chip')
    need(R.docker_inspect(p['container']+'-a1') is None and not R.live_chip_conflict(p['chip'],None),'live device/target conflict')
    return {'schema':'pt2-recovery-claim-v2','release_sha256':sha(relpath),'container_id':ref['container_id'],'checkpoint_sha256':p['recovery']['checkpoint']['sha256'],'precondition_sha256':precondition_pin}

def configure(path):
    p=read(path);base=module(p['recovery']['launcher_base']['path'],p['recovery']['launcher_base']['sha256']);original=base.verify
    def verify(path,pin,reviewed=True):
        p=original(path,pin,reviewed=False);check_state_manifest(p)
        if reviewed:verify_review(p,pin)
        return p
    base.verify=verify;base.successor_binding=successor_binding
    return base

def watch(path,pin):
    root=Path(read(path)['out']);service_lock=(root/'service.lock').open('a')
    try:fcntl.flock(service_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:service_lock.close();raise
    rc=1;status='failed';stop=threading.Event()
    def beat():
        while not stop.wait(30):put(root/'SERVICE_HEARTBEAT.json',{'status':'service_alive','utc_seconds':time.time()})
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        with service_lock:
            need(not (root/'SERVICE_EXIT.json').exists() and not (root/'LAUNCH-INTENT.json').exists(),'service terminal/uncertain launch exists')
            intent=read(root/'SERVICE-START-INTENT.json');need(intent['plan']==path and intent['sha256']==pin,'service intent differs')
            B=configure(path);p=B.verify(path,pin);verify_import(p)
            def observe(name):
                try:return B.inspect(name)
                except (RuntimeError,ValueError) as error:raise OSError('docker observation unavailable: '+str(error)) from error
            while True:
                try:released=ready(p,observe)
                except (subprocess.TimeoutExpired,OSError) as error:
                    put(root/'SERVICE_STATUS.json',{'status':'observation_unknown','error':str(error)[:200],'action':'wait_same_generation'});time.sleep(600);continue
                if released:break
                put(root/'SERVICE_STATUS.json',{'status':'waiting_qo_release','utc_seconds':time.time()});time.sleep(600)
            verify_import(p)
            rel=Path(p['recovery']['resource_predecessor']['out'])/'attempts/1/RELEASE.json'
            pre=root/'SUCCESSOR_PRECONDITION.json';put(pre,{'plan_sha256':pin,'checkpoint_sha256':p['recovery']['checkpoint']['sha256'],'release_sha256':sha(rel)},True)
            put(root/'LAUNCH-INTENT.json',{'plan':path,'sha256':pin,'precondition_sha256':sha(pre)},True)
            B.supervisor(path,pin,1,sha(pre));rc=0;status='supervisor_complete'
    except BaseException as error:
        put(root/'SERVICE_ERROR.json',{'error':str(error)[:500],'automatic_retry':False});raise
    finally:
        stop.set();thread.join(2);put(root/'SERVICE_EXIT.json',{'exit_code':rc,'status':status,'utc_seconds':time.time(),'scientific_acceptance':False})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','start','watch']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);ap.add_argument('--unreviewed',action='store_true');a=ap.parse_args()
    need(a.attempt==1,'fresh recovery attempt1 only');need(not a.unreviewed or a.op=='verify','unreviewed launch forbidden')
    if a.op=='watch':return watch(a.plan,a.sha256)
    B=configure(a.plan);p=B.verify(a.plan,a.sha256,reviewed=not a.unreviewed);root=Path(p['out']);verify_import(p)
    if a.op=='verify':print(json.dumps({'status':'VERIFIED','launch_authorized':False}));return
    need(socket.gethostname()=='k8s-node1','host175 only')
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not (root/'SERVICE_EXIT.json').exists(),'terminal service')
        put(root/'SERVICE-START-INTENT.json',{'plan':a.plan,'sha256':a.sha256},True)
        cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--plan',a.plan,'--sha256',a.sha256]
        put(root/'RELAUNCH.json',{'command':cmd,'automatic_retry':False,'instructions':'Inspect exact live service and markers; no replay after uncertain launch'},True)
        try:
            with (root/'service.log').open('ab') as log:child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
            put(root/'SERVICE.json',{'pid':child.pid,'command':cmd,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[19])},True)
        except BaseException as error:
            put(root/'START-ERROR.json',{'error':str(error)[:300],'automatic_retry':False});raise
    print(json.dumps({'status':'WAITING_RELEASE','pid':child.pid}))
if __name__=='__main__':main()
