#!/usr/bin/env python3
"""E30 explicit-plan Docker reconciliation; no discovery, model selection or blind retry."""
import argparse,fcntl,hashlib,http.client,json,os,re,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path

def require(value,message):
    if not value:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def atomic(path,value):
    path=Path(path);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def utc():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def docker(method,path,body=None):
    c=http.client.HTTPConnection('localhost',timeout=30);c.sock=socket.socket(socket.AF_UNIX);c.sock.settimeout(30);c.sock.connect('/var/run/docker.sock')
    try:
        c.request(method,path,body=None if body is None else json.dumps(body),headers={'Content-Type':'application/json'})
        r=c.getresponse();data=r.read()
        if r.status==404 and method=='GET':return None
        require(r.status<300,'Docker HTTP '+str(r.status)+' '+path)
        return json.loads(data) if data else None
    finally:c.close()
def inspect(name):
    require(re.fullmatch('[A-Za-z0-9_.-]+',name) is not None,'Invalid container name')
    return docker('GET','/containers/'+name+'/json')
def chip_devices(info):return {x['PathOnHost'] for x in info['HostConfig'].get('Devices') or [] if re.fullmatch('/dev/davinci[0-9]+',x['PathOnHost'])}
def verify_files(files):
    for path,h in files.items():require(sha(path)==h,'Frozen file changed '+path)
def verify_binding(info,spec,receipt=None):
    require(info['Image']==spec['Image'],'Image differs')
    for key in ['Cmd','Entrypoint','WorkingDir']:
        require((info['Config'].get(key) or None)==(spec.get(key) or None),'Container '+key+' differs')
    device_tuple=lambda x:(x['PathOnHost'],x.get('PathInContainer',x['PathOnHost']),x.get('CgroupPermissions','rwm'))
    expected={device_tuple(x) for x in spec.get('HostConfig',{}).get('Devices') or []}
    require({device_tuple(x) for x in info['HostConfig'].get('Devices') or []}==expected,'Devices differ')
    actual_env=dict(x.split('=',1) for x in info['Config'].get('Env') or [])
    for entry in spec.get('Env',[]):
        key,value=entry.split('=',1);require(actual_env.get(key)==value,'Container environment differs')
    if 'NetworkMode' in spec.get('HostConfig',{}):require(info['HostConfig'].get('NetworkMode')==spec['HostConfig']['NetworkMode'],'Network mode differs')
    require(sorted(info['HostConfig'].get('Binds') or [])==sorted(spec.get('HostConfig',{}).get('Binds') or []),'Mounts differ')
    for k,v in spec.get('Labels',{}).items():require(info['Config'].get('Labels',{}).get(k)==v,'Intent label differs')
    if receipt:require(info['Id']==receipt['container_id'],'Foreign container identity')

def successful_terminal(run,config_hash,expected_count):
    p=run/'inference-COMPLETE.json';wrapper=run/'EXIT'
    if not p.exists():return False
    t=load(p)
    if t.get('rc')!=0:return False
    require(t.get('config_sha256')==config_hash and t.get('stage')=='completed','Success binding differs')
    require(type(t.get('progress')) is int and t['progress']==t.get('total')==expected_count and expected_count>0,'Success count differs')
    require(wrapper.exists() and re.fullmatch(r'rc=0 utc=\S+\n?',wrapper.read_text()),'Success wrapper missing/invalid')
    require(wrapper.stat().st_mtime_ns>=p.stat().st_mtime_ns,'Stale wrapper')
    require(t.get('outputs') and 'report.json' in t['outputs'],'Success output missing')
    for name,h in t['outputs'].items():
        require(Path(name).name==name,'Unsafe output name');require(sha(run/name)==h,'Success output differs')
    return True

class Controller:
    def __init__(self,plan_path):
        self.path=Path(plan_path);blob=self.path.read_bytes();self.hash=hashlib.sha256(blob).hexdigest();self.plan=json.loads(blob);self.out=Path(self.plan['out']);self.out.mkdir(exist_ok=True)
        require(load(self.out/'PARENT_REVIEW.json')['approved_plan_sha256']==self.hash,'Plan not approved')
        require(self.plan['schema']==1 and self.plan['max_retries'] in (0,1,2,3),'Retry limit invalid')
        require(set(self.plan['retry_exit_codes'])<=set([137,143]),'Only explicitly allowed signal exit codes may retry')
        require(str(Path(__file__).resolve()) in self.plan['files'],'Controller not frozen')
        require(self.plan['verifier'] in self.plan['files'],'Verifier not frozen')
        require(set(self.plan.get('preparation_files',{}))=={'controller_wrapper','launch','resume','preregistration'},'Preparation dependencies missing')
        for path in self.plan['preparation_files'].values():require(path in self.plan['files'],'Preparation dependency not frozen')
        verify_files(self.plan['files']);self.config_path=Path(self.plan['config']);require(str(self.config_path) in self.plan['files'],'Config not frozen')
        config_blob=self.config_path.read_bytes();self.ch=hashlib.sha256(config_blob).hexdigest();self.c=json.loads(config_blob);self.run=Path(self.c['out'])
        require(self.ch==self.plan['files'][str(self.config_path)] and sha(self.config_path)==self.ch,'Config snapshot differs')
        require(type(self.c.get('expected_count')) is int and self.c['expected_count']>0,'Expected count missing/invalid')
        require(self.c['mode']=='inference','Only inference managed');require(str(self.run/'run.sh') in self.plan['files'],'Wrapper not frozen')
        require(self.plan['inference']['Image']==self.c['image'],'Plan/config image differs')
        require(self.plan['inference']['Cmd']==['bash',str(self.run/'run.sh')],'Unexpected inference command')
        require(self.plan['kind'] in ('npu','cpu_fixture'),'Unknown resource kind')
        dev={d['PathOnHost'] for d in self.plan['inference'].get('HostConfig',{}).get('Devices') or [] if re.fullmatch('/dev/davinci[0-9]+',d['PathOnHost'])}
        require(dev==({'/dev/davinci'+str(self.c['physical_chip'])} if self.plan['kind']=='npu' else set()),'Plan chip mismatch')
        self.state_path=self.out/'STATE.json';self.state=load(self.state_path) if self.state_path.exists() else dict(plan_sha256=self.hash,retries=0,phase='new',audit_generation=0)
        require(self.state['plan_sha256']==self.hash,'State plan differs')
    def save(self):self.state.update(utc=utc());atomic(self.state_path,self.state)
    def spec(self):
        s=json.loads(json.dumps(self.plan['inference']));s.setdefault('Labels',{}).update({'nga.recovery.plan':self.hash,'nga.recovery.role':'inference'});return s
    def resource_lock(self):
        p=Path(self.plan['allocation']) if self.plan['kind']=='npu' else self.out/'CPU-RESOURCE.json'
        lock=Path(str(p)+'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX);return lock
    def check_resource(self,own_id=None):
        if self.plan['kind']=='cpu_fixture':return
        a=load(self.plan['allocation']);chip=self.c['physical_chip'];owners=[x for x in a['allocation'] if x['chip']==chip]
        require(len(owners)==1 and owners[0]['run']==self.plan['allocation_run'],'Allocation owner differs')
        for obj in docker('GET','/containers/json'):
            if obj['Id']==own_id:continue
            require('/dev/davinci'+str(chip) not in chip_devices(inspect(obj['Id'])),'Live chip conflict')
    def reconcile_inference(self):
        spec=self.spec();name=self.c['container'];receipt_path=self.run/'RECOVERY_LAUNCH_RECEIPT.json'
        with self.resource_lock():
            info=inspect(name);receipt=load(receipt_path) if receipt_path.exists() else None
            if info is None:
                require(receipt is None and self.state['phase'] in ('new','creating'),'Missing established container')
                verify_files(self.c['files']);verify_files(self.plan['files']);self.check_resource();self.state['phase']='creating';self.save()
                docker('POST','/containers/create?name='+name,spec);info=inspect(name)
            verify_binding(info,spec,receipt)
            # Adoption without receipt is permitted only for controller intent-labelled created containers.
            if receipt is None:
                require(info['State']['Status']=='created' and self.state['phase']=='creating','Unreceipted container cannot be adopted')
                receipt=dict(container_id=info['Id'],image=info['Image'],command=info['Config']['Cmd'],entrypoint=info['Config'].get('Entrypoint'),config_sha256=self.ch,wrapper_sha256=sha(self.run/'run.sh'),utc=utc())
                atomic(receipt_path,receipt)
            native=self.run/'LAUNCH_RECEIPT.json'
            if native.exists():require(load(native)==receipt,'Native launch receipt differs')
            else:
                require(info['State']['Status']=='created' and self.state['phase'] in ('creating','starting'),'Missing native launch receipt after execution')
                atomic(native,receipt)
            require(receipt['config_sha256']==self.ch and receipt['wrapper_sha256']==sha(self.run/'run.sh'),'Launch receipt binding differs')
            self.check_resource(info['Id']);state=info['State'];status=state['Status']
            if status in ('running','restarting','paused'):
                self.state['phase']='running';self.save();return 'running'
            if status=='exited' and state['ExitCode']==0:
                require(successful_terminal(self.run,self.ch,self.c['expected_count']),'Exited0 without successful terminal');verify_files(self.c['files']);self.state['phase']='inference_complete';self.save();return 'complete'
            if (self.run/'inference-COMPLETE.json').exists() and load(self.run/'inference-COMPLETE.json').get('rc')==0:raise ValueError('Successful terminal forbids inference retry')
            require(status in ('created','exited'),'Unsupported container state')
            if status=='exited':
                require(state['ExitCode'] in self.plan['retry_exit_codes'],'Non-retryable inference exit')
                require(not any((self.run/n).exists() for n in ['FAILED','ERROR.json']),'Semantic failure marker requires review')
                term=self.run/'inference-COMPLETE.json'
                if term.exists():require(not load(term).get('error'),'Recorded semantic error requires review')
                pending=self.state.get('restart')
                if not pending or pending['started_at']!=state['StartedAt']:
                    require(self.state['retries']<self.plan['max_retries'],'Retry limit reached')
                    self.state['retries']+=1;pending=dict(started_at=state['StartedAt'],archive=str(self.out/('retry-'+str(self.state['retries']))));self.state['restart']=pending;self.save()
                archive=Path(pending['archive']);archive.mkdir(exist_ok=True)
                for n in ['inference-COMPLETE.json','EXIT','STATUS.json','PREFLIGHT.json','PROBE.json','ENVIRONMENT.json','report.json']:
                    if (self.run/n).exists():require(not(archive/n).exists(),'Conflicting archive');shutil.move(str(self.run/n),str(archive/n))
            verify_files(self.c['files']);verify_files(self.plan['files']);self.state['phase']='starting';self.save();docker('POST','/containers/'+info['Id']+'/start');return 'started'
    def audit_context(self,generation,create=False):
        # Each allowed interrupted audit is retained; a new deterministic generation is created.
        out=self.out/('audit-'+str(generation))
        if create:out.mkdir(exist_ok=True)
        name=self.c['container']+'-recovery-audit-'+str(generation)
        ap=out/'audit-plan.json'
        a=dict(out=str(out),config=str(self.config_path),config_sha256=self.ch,verifier=self.plan['verifier'],files=self.plan['files'])
        if create and not ap.exists():atomic(ap,a)
        require(load(ap)==a,'Audit plan changed')
        spec=dict(Image=self.c['image'],Cmd=['python3','-P',str(Path(__file__).resolve()),'--audit',str(ap)],Entrypoint=[],WorkingDir='/tmp',Env=['TORCH_DEVICE_BACKEND_AUTOLOAD=0','HF_HUB_OFFLINE=1'],HostConfig={'Binds':self.plan['audit_binds'],'NetworkMode':'none','Devices':[]},Labels={'nga.recovery.plan':self.hash,'nga.recovery.role':'audit-'+str(generation),'nga.recovery.audit_plan':sha(ap)})
        return out,name,ap,spec
    def verify_inference_complete(self):
        verify_files(self.plan['files']);verify_files(self.c['files'])
        require(sha(self.config_path)==self.ch,'Config changed')
        receipt=load(self.run/'RECOVERY_LAUNCH_RECEIPT.json')
        require(load(self.run/'LAUNCH_RECEIPT.json')==receipt,'Native launch receipt differs')
        require(receipt['config_sha256']==self.ch and receipt['wrapper_sha256']==sha(self.run/'run.sh'),'Launch receipt binding differs')
        info=inspect(self.c['container']);require(info is not None,'Completed inference container missing')
        verify_binding(info,self.spec(),receipt)
        require(info['State']['Status']=='exited' and info['State']['ExitCode']==0,'Completed inference container state differs')
        require(successful_terminal(self.run,self.ch,self.c['expected_count']),'Inference success changed')
    def verify_audit_complete(self,generation):
        self.verify_inference_complete()
        out,name,ap,spec=self.audit_context(generation)
        info=inspect(name);require(info is not None,'Completed audit container missing')
        rp=out/'LAUNCH_RECEIPT.json';verify_binding(info,spec,load(rp))
        require(info['State']['Status']=='exited' and info['State']['ExitCode']==0,'Completed audit container state differs')
        terminal=out/'AUDIT_COMPLETE.json';report=out/'INDEPENDENT_AUDIT.json';require(terminal.exists(),'Audit exited0 without marker');t=load(terminal)
        require(t['rc']==0 and t['config_sha256']==self.ch and t['audit_sha256']==sha(report),'Audit completion differs')
        require(t.get('audit_plan_sha256')==sha(ap) and t.get('inference_terminal_sha256')==sha(self.run/'inference-COMPLETE.json'),'Audit terminal binding differs')
        require(max(rp.stat().st_mtime_ns,ap.stat().st_mtime_ns,(self.run/'inference-COMPLETE.json').stat().st_mtime_ns)<=report.stat().st_mtime_ns<=terminal.stat().st_mtime_ns,'Stale audit terminal/report')
        audit=load(report);require(audit['config_sha256']==self.ch,'Audit config differs')
        return t,audit
    def audit(self):
        generation=self.state['audit_generation'];out,name,ap,spec=self.audit_context(generation,create=True)
        info=inspect(name)
        if info is None:docker('POST','/containers/create?name='+name,spec);info=inspect(name)
        rp=out/'LAUNCH_RECEIPT.json';receipt=load(rp) if rp.exists() else None;verify_binding(info,spec,receipt)
        if receipt is None:require(info['State']['Status']=='created','Unreceipted audit changed');atomic(rp,{'container_id':info['Id']})
        status=info['State']['Status']
        if status=='created':docker('POST','/containers/'+info['Id']+'/start');return 'audit_started'
        if status in ('running','restarting','paused'):return 'audit_running'
        require(status=='exited','Unexpected audit state');terminal=out/'AUDIT_COMPLETE.json'
        if info['State']['ExitCode']==0:
            t,audit=self.verify_audit_complete(generation)
            flags=audit['review_flags'];self.state.update(phase='complete',status='COMPLETED_SCOPED_REVIEW_REQUIRED' if flags else 'COMPLETED_SCOPED');self.save();atomic(self.out/'COMPLETE.json',dict(rc=0,plan_sha256=self.hash,audit_generation=generation,audit_sha256=t['audit_sha256'],audit_terminal_sha256=sha(terminal),review_flags=flags,status=self.state['status'],utc=utc()));return 'complete'
        require(info['State']['ExitCode'] in self.plan['retry_exit_codes'] and not terminal.exists(),'Non-retryable audit failure')
        require(generation<self.plan['max_retries'],'Audit retry limit reached');self.state['audit_generation']+=1;self.save();return 'audit_retry_registered'
    def step(self):
        require(sha(self.path)==self.hash,'Plan changed')
        if (self.out/'COMPLETE.json').exists():
            complete=load(self.out/'COMPLETE.json');require(complete['rc']==0 and complete['plan_sha256']==self.hash,'Controller terminal differs')
            t,audit=self.verify_audit_complete(complete['audit_generation'])
            require(t['audit_sha256']==complete['audit_sha256'] and sha(self.out/('audit-'+str(complete['audit_generation']))/'AUDIT_COMPLETE.json')==complete['audit_terminal_sha256'],'Completed audit changed')
            require(audit['review_flags']==complete['review_flags'],'Completed audit flags differ')
            return 'complete'
        result=self.reconcile_inference()
        return self.audit() if result=='complete' else result

def audit_worker(path):
    a=load(path);out=Path(a['out']);require(not(out/'AUDIT_COMPLETE.json').exists(),'Audit marker preserved');rc=1;error=None
    try:
        verify_files(a['files']);require(sha(a['config'])==a['config_sha256'],'Config changed')
        with (out/'audit.log').open('ab') as f:subprocess.run([sys.executable,'-P',a['verifier'],'--config',a['config'],'--out',str(out/'INDEPENDENT_AUDIT.json')],stdout=f,stderr=subprocess.STDOUT,check=True)
        verify_files(a['files']);rc=0
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        t=dict(rc=rc,config_sha256=a['config_sha256'],error=error,utc=utc())
        if rc==0:t.update(audit_sha256=sha(out/'INDEPENDENT_AUDIT.json'),audit_plan_sha256=sha(path),inference_terminal_sha256=sha(Path(load(a['config'])['out'])/'inference-COMPLETE.json'))
        atomic(out/'AUDIT_COMPLETE.json',t)
def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path);p.add_argument('--audit',type=Path);p.add_argument('--once',action='store_true');a=p.parse_args()
    if a.audit:return audit_worker(a.audit)
    controller=Controller(a.plan)
    with (controller.out/'controller.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            try:stage=controller.step()
            except Exception as exc:
                atomic(controller.out/'BLOCKED.json',{'utc':utc(),'type':type(exc).__name__,'error':str(exc)});raise
            snapshot=dict(utc=utc(),stage=stage,retries=controller.state['retries'],audit_generation=controller.state['audit_generation']);atomic(controller.out/'STATUS.json',snapshot)
            with (controller.out/'heartbeat.log').open('a') as f:f.write(json.dumps(snapshot)+'\n')
            (controller.out/'digest.md').write_text(snapshot['utc']+' '+stage+' retries='+str(snapshot['retries'])+'\n')
            if stage=='complete' or a.once:break
            time.sleep(5)
if __name__=='__main__':main()
