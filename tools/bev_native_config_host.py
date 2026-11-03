#!/usr/bin/env python3
"""Configured native long-DEV host lifecycle; stable runtime/resource composition."""
import argparse,fcntl,hashlib,json,os,socket,subprocess,sys,time,types
from pathlib import Path

def require(ok,why):
    if not ok:raise ValueError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec'),m.__dict__);return m
def put(path,v):
    path=Path(path);tmp=path.with_name(path.name+'.pending')
    with tmp.open('x') as f:json.dump(v,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path);fd=os.open(path.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def inspect(name):
    r=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower():return None
        raise RuntimeError('container observation uncertain')
    return json.loads(r.stdout)[0]
def command(d,path,pin,a):
    c=['docker','run','-d','--pull=never','--name',d['container']+'-a'+str(a),'--network=none','--shm-size','16g','--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
    for x in ['davinci_manager','devmm_svm','hisi_hdc','davinci'+str(d['chip'])]:c+=['--device','/dev/'+x]
    for k,v in sorted(d['environment'].items()):c+=['-e',k+'='+v]
    for m in d['mounts']:c+=['--mount','type=bind,src='+m['source']+',dst='+m['destination']+(',readonly' if m['readonly'] else '')]
    return c+[d['image_sha256'],'python3','-B','-P',d['runtime']['path'],'run','--plan',str(path),'--sha256',pin,'--attempt',str(a)]
def verify(path,pin):
    require(sha(path)==pin,'plan changed');d=read(path)
    require(d['modules']['host']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'host source differs')
    module(d['modules']['runtime']).verify(path,pin)
    return {**d,'runtime':d['modules']['runtime'],'resource':d['modules']['resource'],'image_sha256':d['image'],'scope':'synthetic_long_dev'}
def preflight(d):
    require(socket.gethostname()==d['host_name'],'wrong host')
    image=subprocess.run(['docker','image','inspect',d['image_sha256'],'--format','{{.Id}}'],capture_output=True,text=True,timeout=30,check=True)
    require(image.stdout.strip()==d['image_sha256'],'image absent or different')
    for m in d['mounts']:
        p=Path(m['source'])
        require(p.is_absolute() and p.exists() and not any(x.is_symlink() for x in [p,*p.parents]),'mount absent or symlink')
def approval(d,path,pin,review,rpin,a):
    require(sha(review)==rpin,'review changed');r=read(review)
    require(r['verdict']=='PASS' and r['approved_plan_sha256']==pin and r['activation_authorized']is True and r['scientific_acceptance']is False and r['test_read']is False,'exact review required')
    require(type(a)is int and a in r['attempts'] and r['expected_commands'][str(a)]==command(d,path,pin,a),'command/attempt not reviewed')
    for f,h in d['files'].items():require(r['hashes'].get(f)==h and sha(f)==h,'unreviewed dependency')

def exact_int(value,wanted=None):
    return type(value)is int and (wanted is None or value==wanted)
def runtime_terminal_matches(term,pin,attempt,actual,receipt):
    return (type(term)is dict and exact_int(term.get('exit_code'))
            and exact_int(actual['State'].get('ExitCode')) and term['exit_code']==actual['State']['ExitCode']
            and term.get('plan_sha256')==pin and exact_int(term.get('attempt'),attempt)
            and term.get('scientific_acceptance')is False and term.get('test_read',False)is False
            and term.get('execution_authorized',False)is False
            and term.get('container_id',actual['Id'])==actual['Id']
            and receipt.get('container_id')==actual['Id'] and receipt.get('plan_sha256')==pin
            and exact_int(receipt.get('attempt'),attempt) and receipt.get('scientific_acceptance')is False)
def previous(d,a,pin):
    require(exact_int(a) and a>0,'attempt differs');root=Path(d['out'])
    for i in range(1,a):
        h=root/'host_attempts'/str(i);rel=read(h/'RELEASE.json');actual=inspect(d['container']+'-a'+str(i));end=read(h/'EXIT.json');claim=read(h/'CLAIM.json');receipt=read(h/'LAUNCH_RECEIPT.json');spec=read(h/'LAUNCH_SPEC.json')
        require(rel.get('schema')=='r3-resource-release-v1' and claim.get('schema')=='r3-resource-claim-v1'
                and rel.get('run')==claim.get('run')==d['run'] and exact_int(rel.get('chip'),d['chip']) and exact_int(claim.get('chip'),d['chip'])
                and rel.get('claim_sha256')==sha(h/'CLAIM.json') and rel.get('scientific_acceptance')is False
                and claim.get('scientific_acceptance',False)is False and claim.get('execution_authorized',False)is False,'release identity differs')
        require(actual and actual['State']['Status']=='exited' and actual['State'].get('Running')is False
                and exact_int(actual['State'].get('ExitCode')) and exact_int(rel.get('exit_code'),actual['State']['ExitCode'])
                and actual['Id']==rel.get('container_id')==end.get('container_id')==receipt.get('container_id')
                and rel.get('container')==d['container']+'-a'+str(i),'previous not released')
        require(end.get('plan_sha256')==receipt.get('plan_sha256')==spec.get('plan_sha256')==pin
                and exact_int(end.get('attempt'),i) and exact_int(receipt.get('attempt'),i)
                and end.get('scientific_acceptance')is False and receipt.get('scientific_acceptance')is False
                and exact_int(end.get('exit_code')) and exact_int(end.get('container_exit_code'),actual['State']['ExitCode'])
                and type(end.get('runner_terminal_matches'))is bool,'previous generation differs')
        require(actual['Image']==d['image_sha256'] and receipt.get('command')==actual['Config']['Cmd']
                and spec['command'][spec['command'].index(d['image_sha256'])+1:]==actual['Config']['Cmd'],'previous command differs')
        require(end['exit_code']!=0,'completed run cannot resume')
    require(not (root/'host_attempts'/str(a)).exists(),'attempt exists; reconcile')
def supervise(args):
    d=verify(args.plan,args.sha256);approval(d,args.plan,args.sha256,args.review,args.review_sha256,args.attempt)
    preflight(d)
    root=Path(d['out']);h=root/'host_attempts'/str(args.attempt);R=module(d['modules']['resource_base']);name=d['container']+'-a'+str(args.attempt)
    with (root/'host.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(inspect(name) is None and not R.live_chip_conflict(d['chip'],None),'live conflict')
        adapter=[sys.executable,'-B','-P',d['resource']['path']]
        subprocess.run(adapter+['claim','--plan',args.plan,'--sha256',args.sha256,'--attempt',str(args.attempt)],check=True,capture_output=True)
        cmd=command(d,args.plan,args.sha256,args.attempt);put(h/'LAUNCH_SPEC.json',{'command':cmd,'plan_sha256':args.sha256})
        started=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        require(started.returncode==0,'launch uncertain; retain claim for reconciliation');a=inspect(name)
        require(a and a['Image']==d['image_sha256'] and not a['HostConfig']['AutoRemove'] and a['Config']['Cmd']==cmd[cmd.index(d['image_sha256'])+1:],'launched identity differs')
        put(h/'LAUNCH_RECEIPT.json',{'container_id':a['Id'],'plan_sha256':args.sha256,'attempt':args.attempt,'scientific_acceptance':False,'command':a['Config']['Cmd']})
        with (h/'runtime.log').open('ab') as log:
            logger=subprocess.Popen(['docker','logs','--follow',a['Id']],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
            try:
                while True:
                    a=inspect(name);require(a is not None,'retained container absent');put(h/'heartbeat.json',{'utc_seconds':time.time(),'state':a['State']['Status'],'container_id':a['Id']})
                    if a['State']['Status']=='exited':break
                    require(a['State']['Status'] in ('running','created'),'container uncertain')
                    try:subprocess.run(['docker','wait',a['Id']],capture_output=True,timeout=600,check=True)
                    except subprocess.TimeoutExpired:pass
            finally:
                try:logger.wait(timeout=5)
                except subprocess.TimeoutExpired:logger.terminate();logger.wait(timeout=5)
        subprocess.run(adapter+['release','--plan',args.plan,'--sha256',args.sha256,'--attempt',str(args.attempt),'--container-id',a['Id']],check=True,capture_output=True)
        term=root/'attempts'/str(args.attempt)/'EXIT.json'
        try:valid=term.exists() and runtime_terminal_matches(read(term),args.sha256,args.attempt,a,read(h/'LAUNCH_RECEIPT.json'))
        except (ValueError,KeyError,TypeError,OSError):valid=False
        rc=a['State']['ExitCode'] if valid else 1
        put(h/'EXIT.json',{'exit_code':rc,'container_exit_code':a['State']['ExitCode'],'runner_terminal_matches':valid,'container_id':a['Id'],'plan_sha256':args.sha256,'attempt':args.attempt,'scientific_acceptance':False})
        # Long DEV operands are consumed independently after release.
def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','preflight','start','supervise']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--review');ap.add_argument('--review-sha256');ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args();d=verify(a.plan,a.sha256)
    if a.op=='verify':print('NATIVE_PANEL_HOST_VERIFIED');return
    if a.op=='preflight':preflight(d);print('NATIVE_PANEL_HOST_PREFLIGHT_PASSED');return
    require(socket.gethostname()==d['host_name'] and type(a.attempt) is int and a.attempt>0,'host/attempt differs');approval(d,a.plan,a.sha256,a.review,a.review_sha256,a.attempt)
    root=Path(d['out']);root.mkdir(parents=True,exist_ok=True)
    if a.op=='supervise':
        try:supervise(a)
        except BaseException as e:
            h=root/'host_attempts'/str(a.attempt);put(h/'SUPERVISOR_ERROR.json',{'exit_code':1,'error_type':type(e).__name__,'status':'needs_reconciliation'});put(h/'EXIT.json',{'exit_code':1,'plan_sha256':a.sha256,'attempt':a.attempt,'scientific_acceptance':False,'status':'needs_reconciliation','utc_seconds':time.time()});raise
        return
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);previous(d,a.attempt,a.sha256);h=root/'host_attempts'/str(a.attempt);h.mkdir(parents=True)
        cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'supervise','--plan',a.plan,'--sha256',a.sha256,'--review',a.review,'--review-sha256',a.review_sha256,'--attempt',str(a.attempt)]
        put(h/'START_INTENT.json',{'command':cmd,'utc_seconds':time.time()});put(h/'RELAUNCH.json',{'command':cmd,'automatic_retry':False,'resume':'new reviewed attempt only after exact previous release; complete operand items retained; partial directories require explicit reconciliation; no timing claims'})
        with (h/'supervisor.log').open('ab') as log:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        put(h/'SERVICE.json',{'pid':p.pid,'command':cmd});print(json.dumps({'status':'STARTED','pid':p.pid}))
if __name__=='__main__':main()
