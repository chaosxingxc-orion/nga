"""CPU managed DAG: actual panel release -> immutable package -> ready_for_review.
Event-driven RELEASE.json changes and worker completion, with600-second fallback.
Never issues NPU launch or resource-ledger writes. Exact independent CPU service
activation is supplied separately, avoiding circular graph/config receipt hashes.
"""
import argparse,ctypes,fcntl,hashlib,importlib.util,json,os,select,signal,socket,struct,subprocess,sys,time
from pathlib import Path
def need(v,s):
    if not v:raise ValueError(s)
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'unsafe path');return p
def sha(p):
    with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def ref(p):return dict(path=str(safe(p)),sha256=sha(p))
def pin(r):
    need(type(r)is dict and set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'pin differs');return read(r['path'])
def module(r):
    need(sha(r['path'])==r['sha256'],'module changed');s=importlib.util.spec_from_file_location(Path(r['path']).stem,r['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify(path,pinsha):
    need(sha(path)==pinsha,'config changed');c=read(path);need(set(c)=={'schema','host_name','output','graph','modules','interval_seconds','service_python','environment'},'config fields')
    need(c['schema']=='native-family-cpu-continuation-service-v1' and type(c['interval_seconds'])is int and c['interval_seconds']==600 and c['service_python']=='/usr/bin/python3.12' and c['host_name']=='k8s-node1','service scope')
    need(set(c['modules'])=={'dag','adapter','native','service'},'module roles');need(c['modules']['service']==ref(Path(__file__).resolve()),'service binding differs');safe(c['output'])
    D=module(c['modules']['dag']);A=module(c['modules']['adapter']);N=module(c['modules']['native']);g=pin(c['graph']);D.validate(g);need(g['policy']['poll_seconds']==600 and g['policy']['cpu_slots']==2,'graph cadence/slots')
    need(set(g['adapters'])=={A.ADAPTER_ID} and g['adapters'][A.ADAPTER_ID]['implementation']==c['modules']['adapter'],'graph adapter differs')
    table={n['id']:n for n in g['nodes']};need(set(table)=={'release_4b','bind_4b','release_9b','bind_9b'},'finite queue nodes');adapter=A.FamilyCPUAdapter(D,N);adapter.admission_errors={}
    for size in ('4b','9b'):
        release=table['release_'+size];bind=table['bind_'+size]
        need(release['depends_on']==[] and bind['depends_on']==[{'node':release['id'],'kind':'resource_release'}],'release dependencies differ')
        for n in (release,bind):
            need(n['action']is not None and n['missing']==[],'exact action required')
            try:
                b=pin(n['action']['binding']);r=pin(n['action']['review']);adapter.authorize(b,r,n,D.digest(g));need(b['environment']==c['environment'],'service/worker environment differs')
            except Exception as exc:
                adapter.bindings.pop(n['id'],None);adapter.admission_errors[n['id']]=dict(error_type=type(exc).__name__,reason=str(exc)[:180])
    return c,g,D,A,N,adapter
def approval(c,g,D,review_ref,config_ref):
    r=pin(review_ref)
    need(r.get('schema')=='native-family-cpu-service-independent-review-v1' and r.get('verdict')=='PASS' and r.get('cpu_activation_authorized')is True and r.get('npu_activation_authorized')is False and r.get('scientific_acceptance')is False,'CPU service review required')
    need(r.get('config')==config_ref and r.get('graph_sha256')==D.digest(g) and r.get('modules')==c['modules'] and r.get('host_name')==c['host_name'] and r.get('output')==c['output'],'service review identity')
    need(r.get('bindings')=={n['id']:n['action'] for n in g['nodes']},'service review exact bindings')
    for n in g['nodes']:
        for x in [*n['sources'],n['action']['binding'],n['action']['review']]:need(r.get('hashes',{}).get(x['path'])==x['sha256'],'unreviewed graph dependency')
    return r
def snapshot(c,g,D,A,N,adapter,query=True):
    obs={};errors=dict(getattr(adapter,'admission_errors',{}))
    for n in g['nodes']:
        if n['id'] in errors:
            obs[n['id']]=dict(state='uncertain',facts=[],failed_facts=[],evidence=[]);continue
        if not query:continue
        try:
            x=adapter.observe(n,None)
            if x['state']!='absent':obs[n['id']]=x
        except Exception as e:obs[n['id']]=dict(state='uncertain',facts=[],failed_facts=[],evidence=[]);errors[n['id']]=dict(error_type=type(e).__name__,reason=str(e)[:180])
    snap=dict(schema='nga-dag-observation-v1',graph_sha256=D.digest(g),as_of=str(time.time()),authority='adapter_observations' if query else 'digest_only',observations=obs,resources={str(i):'unknown' for i in range(8)});D.validate_snapshot(g,snap);return snap,errors
def tick(c,g,D,A,N,adapter,dispatch=False):
    out=safe(c['output']);out.mkdir(parents=True,exist_ok=True);s,errors=snapshot(c,g,D,A,N,adapter);registry={A.ADAPTER_ID:adapter};p=D.plan(g,s,registry)
    state=D.dispatch_once(g,s,registry,out/'controller') if dispatch else None
    D.atomic(out/'snapshot.json',s);D.atomic(out/'plan.json',p);D.atomic(out/'heartbeat.json',dict(utc_seconds=time.time(),nodes=len(g['nodes']),proposed=p['proposed'],errors=errors,cpu_dispatch=dispatch,npu_started=False))
    lines=['# CPU continuation queue','',f"Updated {s['as_of']}; interval600s plus release/worker events; no NPU launch authority."]
    for n in g['nodes']:
        status=p['nodes'][n['id']]['state'];lines.append(n['id']+': '+status)
    (out/'digest.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(utc_seconds=time.time(),proposed=p['proposed'],errors=errors,cpu_dispatch=dispatch)),flush=True)
    return p,state
class Wakeup:
    """Watch only final release filename; raw runtime log writes do not trigger a tick."""
    def __init__(self,paths):
        self.lib=ctypes.CDLL(None,use_errno=True);self.fd=self.lib.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC);need(self.fd>=0,'inotify unavailable')
        for p in paths:
            wd=self.lib.inotify_add_watch(self.fd,os.fsencode(p),0x80|0x8|0x400|0x800);need(wd>=0,'release watch directory missing')
        self.r,self.w=socket.socketpair();self.r.setblocking(False);self.w.setblocking(False);self.stopped=False
        self.old={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGUSR1)}
        def handler(sig,frame):
            if sig in (signal.SIGTERM,signal.SIGINT):self.stopped=True
            try:self.w.send(b'w')
            except BlockingIOError:pass
        for sig in self.old:signal.signal(sig,handler)
    def wait(self,seconds):
        end=time.monotonic()+seconds
        while not self.stopped:
            left=end-time.monotonic()
            if left<=0:return
            ready,_,_=select.select([self.fd,self.r],[],[],left)
            if not ready:return
            if self.r in ready:
                self.r.recv(4096);return
            if self.fd in ready:
                raw=os.read(self.fd,65536);pos=0
                while pos<len(raw):
                    wd,mask,cookie,n=struct.unpack_from('iIII',raw,pos);name=raw[pos+16:pos+16+n].split(b'\0',1)[0];pos+=16+n
                    if name==b'RELEASE.json' or mask&(0x400|0x800):return
    def close(self):
        os.close(self.fd);self.r.close();self.w.close()
        for sig,h in self.old.items():signal.signal(sig,h)
def reconcile_service(out,pinsha,review_ref,A,D):
    need((out/'SERVICE.json').exists(),'start intent without service receipt; reconcile externally, never replay')
    old=read(out/'SERVICE.json');intent=read(out/'SERVICE_START_INTENT.json')
    need(old.get('start_intent')==ref(out/'SERVICE_START_INTENT.json') and
         intent.get('config_sha256')==pinsha and intent.get('review')==review_ref,
         'uncertain service generation; never replay')
    need(old['config_sha256']==pinsha and old['review']==review_ref and not A.same_process(old),'previous service still live or identity differs')
    archive=out/'history'/sha(out/'SERVICE.json');archive.mkdir(parents=True,exist_ok=True);D.atomic(archive/'SERVICE.json',old)
    D.atomic(archive/'SERVICE_START_INTENT.json',intent)
    if (out/'EXIT.json').exists():
        D.atomic(archive/'EXIT.json',read(out/'EXIT.json'));(out/'EXIT.json').unlink()
    return old

def launch_service(c,args,review_ref,out,lock,A,D):
    """Caller holds service.lock. Intent survives every uncertain Popen outcome."""
    if args.op=='start':
        need(not any((out/n).exists() for n in ('SERVICE.json','SERVICE_START_INTENT.json','EXIT.json')),
             'service previously attempted; reconcile, never replay')
    else:
        reconcile_service(out,args.sha256,review_ref,A,D)
    argv=[c['service_python'],'-B','-P',str(Path(__file__).resolve()),'watch','--config',args.config,'--sha256',args.sha256,'--review',args.review,'--review-sha256',args.review_sha256]
    env=dict(os.environ);env.update(c['environment']);env['NGA_FAMILY_CPU_LOCK_FD']=str(lock.fileno())
    relaunch=list(argv);relaunch[4]='restart'
    D.atomic(out/'RELAUNCH.json',dict(command=relaunch,environment=c['environment'],automatic_retry=False,preserves_journal=True))
    intent=dict(schema='native-family-service-start-intent-v1',config_sha256=args.sha256,
                review=review_ref,command=argv,environment=c['environment'],utc_seconds=time.time())
    D.atomic(out/'SERVICE_START_INTENT.json',intent)
    intent_ref=ref(out/'SERVICE_START_INTENT.json')
    with (out/'service.log').open('ab') as log:
        p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                           start_new_session=True,pass_fds=(lock.fileno(),),env=env)
    D.atomic(out/'SERVICE.json',dict(A.identity(p.pid),command=argv,config_sha256=args.sha256,
                                    review=review_ref,start_intent=intent_ref))
    return p.pid
def run_service(args):
    c,g,D,A,N,adapter=verify(args.config,args.sha256)
    if args.op in ('verify','dry-run'):
        s,err=snapshot(c,g,D,A,N,adapter,False);p=D.plan(g,s,{A.ADAPTER_ID:adapter});print(json.dumps(dict(plan=p,no_device_query=True,npu_started=False,cpu_dispatch=False),indent=2));return
    need(socket.gethostname()==c['host_name'] and sys.version_info[:2]==(3,12),'owning host Python3.12 required')
    review_ref=dict(path=args.review,sha256=args.review_sha256);grant=approval(c,g,D,review_ref,dict(path=args.config,sha256=args.sha256));adapter.review=grant;adapter.review_ref=review_ref;adapter.service_config=dict(path=args.config,sha256=args.sha256);adapter.service_module=c['modules']['service']
    out=safe(c['output']);out.mkdir(parents=True,exist_ok=True);inherited=os.environ.pop('NGA_FAMILY_CPU_LOCK_FD',None) if args.op=='watch' else None;need(args.op!='watch' or inherited is not None,'watch requires inherited lock')
    fd=os.fdopen(int(inherited),'a') if inherited else (out/'service.lock').open('a')
    with fd as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.op in ('start','restart'):
            pid=launch_service(c,args,review_ref,out,lock,A,D)
            print(json.dumps(dict(pid=pid,cpu_only=True)));return
        adapter.service_identity=A.identity(os.getpid())
        if args.op=='once':tick(c,g,D,A,N,adapter,False);return
        paths=[]
        for n in g['nodes']:
            if n['id'] not in adapter.bindings:continue
            b=adapter.bindings[n['id']][0]
            if b['role']=='physical_release':
                v=A.describe(b)[4];paths.append(Path(v['out'])/'host_attempts'/str(b['attempt']))
        wake=Wakeup(paths);rc=1
        try:
            while not wake.stopped:
                c,g,D,A,N,adapter=verify(args.config,args.sha256);adapter.review=approval(c,g,D,review_ref,dict(path=args.config,sha256=args.sha256));adapter.service_identity=A.identity(os.getpid());adapter.review_ref=review_ref;adapter.service_config=dict(path=args.config,sha256=args.sha256);adapter.service_module=c['modules']['service'];tick(c,g,D,A,N,adapter,True);wake.wait(600)
            rc=0
        finally:wake.close();D.atomic(out/'EXIT.json',dict(exit_code=rc,config_sha256=args.sha256,review=review_ref,utc_seconds=time.time(),npu_started=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','dry-run','once','start','restart','watch']);p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);p.add_argument('--review');p.add_argument('--review-sha256');run_service(p.parse_args())
