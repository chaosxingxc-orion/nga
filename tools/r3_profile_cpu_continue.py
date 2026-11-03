#!/usr/bin/env python3
"""CPU-only, separately versioned continuation of a released profiler capture."""
import argparse,csv,fcntl,hashlib,importlib,inspect,json,os,shutil,socket,subprocess,sys,threading,time,types
from pathlib import Path
BASE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
CAPTURE=BASE/'profile_async_smoke_20261103_v4'
CAPTURE_PIN='b1770ee475a977b2b56534e2e68f555cfc14d0cb144059e1c4db53533c83693f'
PROFILER_PIN='1a04902572383b74a401449e73929b2c4ce728d6c81bb59341876b03c7a82168'
EXPORTS=('kernel_details.csv','operator_details.csv','step_trace_time.csv')
HOST_DRIVER_MOUNTS=frozenset(('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info'))
EVIDENCE=('attempts/1/EXIT.json','attempts/1/RAW-MANIFEST.json','attempts/1/report.json','host_attempts/1/EXIT.json','host_attempts/1/CLAIM.json','host_attempts/1/RELEASE.json','host_attempts/1/LAUNCH_RECEIPT.json','cpu/host_attempts/1/EXIT.json','cpu/attempts/1/EXIT.json')
def require(ok,why):
    if not ok:raise ValueError(why)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def put(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
    with tmp.open('w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType('capture_runtime');m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec'),m.__dict__);return m

def profiler_api():
    m=importlib.import_module('torch_npu.profiler.profiler')
    require(sha(m.__file__)==PROFILER_PIN,'installed profiler differs')
    fn=getattr(m,'analyse',None);require(callable(fn),'offline analyse unavailable')
    inspect.signature(fn).bind('/pinned/capture',max_process_number=4)
    return fn

def verify(path,pin,raw=True):
    path=Path(path);require(sha(path)==pin,'plan changed');d=read(path)
    require(d['schema']=='r3-profile-cpu-continuation-v1' and d['capture_plan']==str(CAPTURE/'HOST-PLAN.json') and d['capture_plan_sha256']==CAPTURE_PIN,'capture identity differs')
    require(sha(d['capture_plan'])==CAPTURE_PIN,'original plan changed');old=read(d['capture_plan'])
    require(d['runtime']['path']==str(Path(__file__).resolve()) and sha(__file__)==d['runtime']['sha256'],'continuation runtime differs')
    require(d['package']=='profile_cpu_continuation_20261103_v4' and d['out']==str(BASE/d['package']/'output') and str(path)==str(BASE/d['package']/'PLAN.json'),'continuation paths differ')
    require(d['max_process_number']==4 and type(d['max_process_number']) is int and d['poll_seconds']==600,'parser policy differs')
    require(all(d[k] is False for k in ['scientific_acceptance','test_read','coverage_adjudicated']),'scope differs')
    required=dict(old['files']);required.update({d['capture_plan']:CAPTURE_PIN,d['runtime']['path']:d['runtime']['sha256']})
    required.update({str(CAPTURE/'output'/p):d['capture_evidence'][p] for p in EVIDENCE})
    require(set(d['capture_evidence'])==set(EVIDENCE) and d['files']==required,'closure differs')
    for f,h in d['files'].items():
        p=Path(f);require(p.is_file() and not any(x.is_symlink() for x in (p,*p.parents)) and sha(p)==h,'input changed: '+f)
    require(d['image']==old['image_sha256'] and d['environment']==old['environment'] and d['container']=='nga-'+d['package'],'execution identity differs')
    R=module(old['runtime']);R.verify(d['capture_plan'],CAPTURE_PIN);m=R.released(old,CAPTURE_PIN,verify_raw=raw)
    ce=read(CAPTURE/'output/cpu/attempts/1/EXIT.json');he=read(CAPTURE/'output/cpu/host_attempts/1/EXIT.json')
    require(type(ce['exit_code']) is int and ce['exit_code']!=0 and ce['exit_code']==he['exit_code']==he['container_exit_code'] and he['runner_terminal_matches'] is True,'prior CPU attempt not failed')
    require(ce['plan_sha256']==he['plan_sha256']==CAPTURE_PIN and type(ce['attempt']) is int and ce['attempt']==1,'prior CPU generation differs')
    return d,R,m

def command(d,path,pin):
    old=read(d['capture_plan']);c=['docker','run','-d','--pull=never','--name',d['container'],'--network=none','--shm-size','16g']
    for k,v in sorted(d['environment'].items()):c+=['-e',k+'='+v]
    # Device-free CANN export must use the image toolkit, not host driver libraries.
    mounts=[x for x in old['mounts'] if x['source'] not in HOST_DRIVER_MOUNTS and x['destination'] not in HOST_DRIVER_MOUNTS]
    for x in mounts:c+=['--mount','type=bind,src='+x['source']+',dst='+x['destination']+',readonly']
    # Only the continuation output is writable. Old capture and failed parser stay read-only.
    mounted={x['destination'] for x in mounts}
    for f in [d['capture_plan'],d['runtime']['path'],str(path)]:
        if f in mounted:continue
        c+=['--mount','type=bind,src='+f+',dst='+f+',readonly']
    c+=['--mount','type=bind,src='+d['out']+',dst='+d['out']]
    return c+[d['image'],'python3','-B','-P',d['runtime']['path'],'parse','--plan',str(path),'--sha256',pin]

def csv_evidence(export):
    out={}
    for n in EXPORTS:
        p=Path(export)/n
        require(p.is_file() and not p.is_symlink() and p.stat().st_size>0,'missing export: '+n)
        with p.open(newline='') as f:
            reader=csv.reader(f);header=next(reader,None);require(header and len(set(header))==len(header),'invalid CSV header: '+n)
            count=0
            for row in reader:
                require(len(row)==len(header),'CSV width differs: '+n);count+=1
        require(count>0,'empty CSV: '+n);out[n]={'sha256':sha(p),'rows':count,'columns':header}
    return out

def parse(path,pin):
    # Verify before creating any output; parse is fresh and never silently overwrites.
    d,R,m=verify(path,pin);out=Path(d['out'])/'parse';out.mkdir(exist_ok=False);stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):put(out/'heartbeat.json',{'utc_seconds':time.time(),'state':'offline_parsing','plan_sha256':pin})
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        require(not list(Path('/dev').glob('davinci*')),'CPU parser has NPU devices')
        fn=profiler_api();work=out/Path(m['raw']).name;shutil.copytree(m['raw'],work)
        require(R.snapshot(work)==m['files'],'raw copy differs');started=time.time();fn(str(work),max_process_number=4)
        exports=csv_evidence(work/'ASCEND_PROFILER_OUTPUT')
        require(R.snapshot(m['raw'])==m['files'],'capture changed');R.accessible_tree(work)
        put(out/'report.json',{'schema':'r3-profile-cpu-continuation-report-v1','plan_sha256':pin,'capture_plan_sha256':CAPTURE_PIN,'raw_manifest_sha256':d['capture_evidence']['attempts/1/RAW-MANIFEST.json'],'exports':exports,'parser_seconds':time.time()-started,'scientific_acceptance':False,'test_read':False,'coverage_adjudicated':False,'coverage_scope':'nonempty well-formed exports only; independent raw-to-trace coverage review still required'});rc=0
    finally:
        stop.set();t.join(2);put(out/'EXIT.json',{'exit_code':rc,'plan_sha256':pin,'capture_plan_sha256':CAPTURE_PIN,'utc_seconds':time.time(),'scientific_acceptance':False})

def consume(path,pin):
    d,R,m=verify(path,pin,raw=False);out=Path(d['out']);e=read(out/'parse/EXIT.json');r=read(out/'parse/report.json')
    require(type(e['exit_code']) is int and e['exit_code']==0 and e['plan_sha256']==r['plan_sha256']==pin and e['capture_plan_sha256']==r['capture_plan_sha256']==CAPTURE_PIN,'terminal/report generation differs')
    require(e['scientific_acceptance'] is False and r['schema']=='r3-profile-cpu-continuation-report-v1' and r['scientific_acceptance'] is False and r['test_read'] is False and r['coverage_adjudicated'] is False,'report scope differs')
    require(r['raw_manifest_sha256']==d['capture_evidence']['attempts/1/RAW-MANIFEST.json'],'raw binding differs')
    export=out/'parse'/Path(m['raw']).name/'ASCEND_PROFILER_OUTPUT'
    require(not any(x.is_symlink() for x in (export,*export.parents)),'export symlink')
    require(r['exports']==csv_evidence(export),'exports changed')
    return r

def actual(name):
    p=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    if p.returncode:
        require('no such' in p.stderr.lower(),'container observation uncertain');return None
    return json.loads(p.stdout)[0]
def approval(d,path,pin,review,rpin):
    require(sha(review)==rpin,'review changed');r=read(review)
    require(r['verdict']=='PASS' and r['plan_sha256']==pin and r['activation_authorized'] is True and r['scientific_acceptance'] is False,'independent exact review required')
    require(r['expected_command']==command(d,path,pin) and r['files']==d['files'],'unreviewed command/closure')
def validate_actual(a,d,path,pin):
    cmd=command(d,path,pin);cfg=a['HostConfig']
    require(a['Image']==d['image'] and a['Config']['Cmd']==cmd[cmd.index(d['image'])+1:] and not cfg.get('Devices') and not cfg.get('Privileged') and not cfg.get('AutoRemove'),'actual CPU isolation/identity differs')
    expected={}
    for i,x in enumerate(cmd):
        if x=='--mount':
            fields=cmd[i+1].split(',');source=next(v[4:] for v in fields if v.startswith('src='));expected[source]='readonly' not in fields
    observed={x['Source']:x['RW'] for x in a['Mounts']}
    require(observed==expected,'actual mounts differ')
def preflight(d):
    require(socket.gethostname()=='k8s-node1','wrong host')
    h=read(CAPTURE/'output/host_attempts/1/EXIT.json');p=read(CAPTURE/'output/cpu/host_attempts/1/EXIT.json')
    for e,code in [(h,0),(p,1)]:
        a=actual(e['container_id']);require(a and a['State']['Status']=='exited' and a['State']['ExitCode']==code and a['Id']==e['container_id'],'original container state differs')
    require(actual(d['container']) is None,'continuation already exists')
def supervise(a):
    d,R,m=verify(a.plan,a.sha256,raw=False);approval(d,a.plan,a.sha256,a.review,a.review_sha256);preflight(d);out=Path(d['out'])
    with (out/'host.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);require(not (out/'host').exists(),'host already exists');h=out/'host';h.mkdir()
        cmd=command(d,a.plan,a.sha256);put(h/'LAUNCH_SPEC.json',{'command':cmd,'plan_sha256':a.sha256})
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);require(p.returncode==0,'launch uncertain; inspect before retry')
        state=actual(d['container']);validate_actual(state,d,a.plan,a.sha256);put(h/'LAUNCH_RECEIPT.json',{'container_id':state['Id'],'started_at':state['State']['StartedAt'],'plan_sha256':a.sha256,'devices':state['HostConfig']['Devices'],'privileged':state['HostConfig']['Privileged']})
        with (h/'runtime.log').open('ab') as log:
            logger=subprocess.Popen(['docker','logs','--follow',state['Id']],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
            try:
                while True:
                    state=actual(d['container']);require(state is not None,'retained container missing');put(h/'heartbeat.json',{'utc_seconds':time.time(),'state':state['State']['Status']})
                    if state['State']['Status']=='exited':break
                    require(state['State']['Status'] in ['created','running'],'container uncertain')
                    try:subprocess.run(['docker','wait',state['Id']],capture_output=True,timeout=600,check=True)
                    except subprocess.TimeoutExpired:pass
            finally:
                try:logger.wait(timeout=5)
                except subprocess.TimeoutExpired:logger.terminate();logger.wait(timeout=5)
        validate_actual(state,d,a.plan,a.sha256);rc=1
        if state['State']['ExitCode']==0:
            try:consume(a.plan,a.sha256);rc=0
            except Exception as e:put(h/'VALIDATION_ERROR.json',{'error':type(e).__name__+': '+str(e)})
        put(h/'EXIT.json',{'exit_code':rc,'container_exit_code':state['State']['ExitCode'],'container_id':state['Id'],'plan_sha256':a.sha256,'scientific_acceptance':False})
        if rc==0:put(out/'COMPLETE.json',{'exit_code':0,'plan_sha256':a.sha256,'report_sha256':sha(out/'parse/report.json'),'coverage_adjudicated':False,'scientific_acceptance':False})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','parse','consume','start','supervise']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--review');ap.add_argument('--review-sha256');a=ap.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('VERIFIED_WITH_RAW');return
    if a.op=='parse':parse(a.plan,a.sha256);return
    if a.op=='consume':print(json.dumps(consume(a.plan,a.sha256)));return
    if a.op=='supervise':supervise(a);return
    d,_,_=verify(a.plan,a.sha256,raw=False);approval(d,a.plan,a.sha256,a.review,a.review_sha256);preflight(d);out=Path(d['out']);out.mkdir(exist_ok=True)
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);require(not (out/'SERVICE.json').exists(),'service already requested')
        cmd=[sys.executable,'-B','-P',__file__,'supervise','--plan',a.plan,'--sha256',a.sha256,'--review',a.review,'--review-sha256',a.review_sha256]
        put(out/'RELAUNCH.json',{'command':cmd,'retry':'No automatic retries; reconcile existing host/container first'})
        with (out/'supervisor.log').open('ab') as f:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        put(out/'SERVICE.json',{'pid':p.pid,'command':cmd,'plan_sha256':a.sha256})
if __name__=='__main__':main()
