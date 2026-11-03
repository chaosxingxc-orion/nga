"""Configuration-driven detached CPU continuation host with inherited lock ownership."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path

LOCK_ENV='NGA_CPU_CONTINUATION_LOCK_FD'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate JSON key')
        d[k]=v
    return d
def read(p):return json.loads(Path(p).read_bytes(),object_pairs_hook=unique)
def put(p,d):
    p=Path(p);q=p.with_suffix(p.suffix+'.pending')
    with q.open('w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,p)
def identity(pid):
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(fields[19])}
def event(root,stage,**fields):
    with (root/'supervisor.log').open('a') as f:f.write(json.dumps({'utc_seconds':time.time(),'stage':stage,**fields},allow_nan=False)+'\n')
def terminal(root,pin,rc):put(root/'EXIT.json',{'exit_code':rc,'operations_sha256':pin,'scientific_acceptance':False,'utc_seconds':time.time()})
def verify_files(o):
    for p,h in o['files'].items():
        if sha(p)!=h:raise ValueError('source changed')
def supervise(o,root,pin):
    cmd=o['docker_command'];r=subprocess.run(cmd,capture_output=True,text=True,timeout=60,check=True);cid=r.stdout.strip()
    actual=json.loads(subprocess.run(['docker','inspect',cid],capture_output=True,text=True,timeout=30,check=True).stdout)[0]
    if actual['Image']!=o['image'] or actual['Config']['Cmd']!=cmd[cmd.index(o['image'])+1:] or actual['HostConfig']['Devices'] or actual['HostConfig']['Privileged'] or actual['HostConfig']['AutoRemove']:raise ValueError('CPU isolation/identity differs')
    put(root/'LAUNCH_RECEIPT.json',{'container_id':cid,'command':actual['Config']['Cmd'],'operations_sha256':pin})
    event(root,'cpu_container_started',container_id=cid)
    with (root/'runtime.log').open('ab') as log:
        logger=subprocess.Popen(['docker','logs','--follow',cid],stdout=log,stderr=subprocess.STDOUT)
        try:
            while True:
                put(root/'heartbeat.json',{'utc_seconds':time.time(),'state':'cpu_consuming'})
                try:
                    waited=subprocess.run(['docker','wait',cid],capture_output=True,text=True,timeout=600,check=True);code=int(waited.stdout.strip());break
                except subprocess.TimeoutExpired:pass
        finally:
            try:logger.wait(timeout=5)
            except subprocess.TimeoutExpired:logger.terminate();logger.wait(timeout=5)
    end=read(o['runtime_terminal'])
    if type(end.get('exit_code'))is not int or end['exit_code']!=code or end['config_sha256']!=o['config_sha256']:raise ValueError('runtime terminal differs')
    return code

def execute(op,path,pin):
    # Until a configuration pin is verified no output path is trusted.
    if sha(path)!=pin:raise ValueError('operations changed')
    o=read(path);root=Path(o['host_output'])
    if not root.is_absolute():raise ValueError('absolute host output required')
    root.mkdir(parents=True,exist_ok=True)
    fd=os.environ.pop(LOCK_ENV,None) if op=='run' else None
    lock=os.fdopen(int(fd),'a') if fd is not None else (root/'LOCK').open('a')
    with lock:
        if fd is not None:
            a,b=os.fstat(lock.fileno()),(root/'LOCK').stat()
            if (a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino):raise ValueError('inherited lock differs')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # A duplicate caller must not overwrite the existing worker's terminal.
        if op=='start' and (root/'START.json').exists():raise ValueError('existing intent; reconcile')
        if op=='run' and fd is None:raise ValueError('run requires inherited lock')
        rc=1;delegated=False
        try:
            event(root,'host_validation_start',operations_sha256=pin)
            put(root/'heartbeat.json',{'utc_seconds':time.time(),'state':'cpu_consuming'})
            verify_files(o)
            cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'run','--operations',str(Path(path).resolve()),'--sha256',pin]
            if op=='start':
                put(root/'START.json',{'command':cmd,'utc_seconds':time.time(),'operations_sha256':pin})
                env=dict(os.environ);env[LOCK_ENV]=str(lock.fileno())
                with (root/'supervisor.log').open('ab') as log:
                    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(lock.fileno(),),env=env)
                delegated=True
                put(root/'SERVICE.json',{**identity(p.pid),'command':cmd,'operations_sha256':pin})
                return
            # Child confirms its own identity even if the parent exits immediately.
            put(root/'WORKER.json',{**identity(os.getpid()),'command':cmd,'operations_sha256':pin})
            rc=supervise(o,root,pin);event(root,'host_complete',exit_code=rc)
        except BaseException:
            event(root,'host_failed')
            with (root/'supervisor.log').open('a') as f:traceback.print_exc(file=f)
            raise
        finally:
            if not delegated:terminal(root,pin,rc)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['start','run']);ap.add_argument('--operations',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();execute(a.op,a.operations,a.sha256)
if __name__=='__main__':main()
