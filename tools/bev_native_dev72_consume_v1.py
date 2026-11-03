"""Detached CPU-only DEV72 reference validation after physical release; raw equality, no science."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,threading,time,types
from pathlib import Path

def need(v,msg):
    if not v:raise ValueError(msg)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def module(ref):
    need(sha(ref['path'])==ref['sha256'],'source changed');m=types.ModuleType('native_shard_cpu');m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def put(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.pending')
    with q.open('w') as f:json.dump(x,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,p);fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def lifecycle(d,path,pin,attempt):
    root=Path(d['out']);h=root/'host_attempts'/str(attempt);a=root/'attempts'/str(attempt);host=read(h/'EXIT.json');runtime=read(a/'EXIT.json');receipt=read(h/'LAUNCH_RECEIPT.json');claim=read(h/'CLAIM.json');release=read(h/'RELEASE.json');spec=read(h/'LAUNCH_SPEC.json')
    eq=lambda x,v:type(x) is int and x==v
    need(all(eq(x.get('exit_code'),0) and x.get('scientific_acceptance') is False for x in (host,runtime,release)),'successful lifecycle absent')
    for x in (host,runtime,receipt):need(x.get('plan_sha256')==pin and eq(x.get('attempt'),attempt),'terminal generation differs')
    need(host.get('runner_terminal_matches') is True and eq(host.get('container_exit_code'),0) and runtime.get('test_read') is False,'terminal scope differs')
    need(claim['schema']=='r3-resource-claim-v1' and release['schema']=='r3-resource-release-v1' and claim['run']==release['run']==d['run'] and eq(claim['chip'],d['chip']) and eq(release['chip'],d['chip']) and claim['allocation']==d['allocation'],'resource lineage differs')
    need(release['claim_sha256']==sha(h/'CLAIM.json') and release['container_id']==host['container_id']==receipt['container_id'] and release['container']==d['container']+'-a'+str(attempt),'release generation differs')
    H=module(d['modules']['host']);expected=H.command(dict(d,runtime=d['modules']['runtime'],image_sha256=d['image']),path,pin,attempt)
    need(spec['plan_sha256']==pin and spec['command']==expected and receipt['command']==expected[expected.index(d['image'])+1:],'command lineage differs')
    report=read(a/'report.json');need(report['plan_sha256']==pin and eq(report['attempt'],attempt) and eq(report['items'],72) and report['scientific_acceptance'] is False and report['test_read'] is False,'report differs')

def consume(path,pin,attempt):
    d=read(path);A=module(d['modules']['runtime'])
    d,c,r,m,proto,L,N,P,items,up=A.verify(path,pin,model_files=False,host=True)
    need(d['modules']['consumer']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'consumer source differs');lifecycle(d,path,pin,attempt)
    root=Path(d['out']);evidence={};counts={};predictions=[]
    expected={N.digest(x) for x in items}
    for variant in proto['variants']:
        folder=root/'items'/variant
        need({x.name for x in folder.iterdir()}==expected,'operand population differs')
        count=0
        for item in items:
            key=N.digest(item);dest=folder/key
            arrays,result=L.load_operand(dest,P,d['contract_sha256'],item,N,variant)
            need(arrays['logits'].shape==(1,248320),'full vocabulary differs')
            if variant!='reference':
                left,lr=L.load_operand(root/'items/reference'/key,P,d['contract_sha256'],item,N,'reference');P.compare_operands(left,arrays,lr,result)
            else:predictions.append(result['prediction'])
            for name in ('COMMITTED.json','operands.npz','result.json'):evidence[str(dest/name)]=sha(dest/name)
            count+=1
        counts[variant]=count
    for sub in ('attempts','host_attempts'):
        for f in (root/sub/str(attempt)).glob('*.json'):
            if f.name!='heartbeat.json':evidence[str(f)]=sha(f)
    manifest=dict(schema='native-dev72-reference-evidence-v1',plan={'path':path,'sha256':pin},contract_sha256=d['contract_sha256'],attempt=attempt,model_sha256=m['model_manifest_sha256'],source_population=r['population']['source_plan'],source_inputs=r['population']['source_inputs'],source_indices=[x['i'] for x in items],ordered_input_sha256=[N.digest(x) for x in items],files=evidence,scientific_acceptance=False,test_read=False)
    put(root/'cpu'/str(attempt)/'REFERENCE-EVIDENCE.json',manifest)
    return dict(schema='native-dev72-reference-comparison-v1',items=72,passes=3,counts=counts,raw_operand_comparisons=144,zero_tolerance=True,model_sha256=m['model_manifest_sha256'],prediction_sha256=N.digest(predictions),plan_sha256=pin,contract_sha256=d['contract_sha256'],attempt=attempt,lifecycle_verified=True,numerical_equivalence_observed=True,scientific_acceptance=False,test_read=False,candidate_selection_allowed=False,cross_card_equivalence=False,timing_claim=False)

def start(d,path,pin,attempt):
    need(type(attempt) is int and attempt>0 and sha(path)==pin,'CPU plan/attempt differs');lifecycle(d,path,pin,attempt)
    root=Path(d['out'])/'cpu';root.mkdir(exist_ok=True)
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);out=root/str(attempt);out.mkdir(exist_ok=False)
        cmd=[d['cpu_python'],'-B','-P',d['modules']['consumer']['path'],'--plan',path,'--sha256',pin,'--attempt',str(attempt)]
        env=dict(os.environ);env.update(d['cpu_environment']);put(out/'INTENT.json',dict(command=cmd,plan_sha256=pin,attempt=attempt,scientific_acceptance=False))
        with (out/'runtime.log').open('ab') as log:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        put(out/'SERVICE.json',dict(pid=p.pid,command=cmd,plan_sha256=pin,attempt=attempt))
def worker(path,pin,attempt):
    d=read(path);out=Path(d['out'])/'cpu'/str(attempt);need(out.is_dir() and not (out/'EXIT.json').exists(),'CPU attempt unavailable');rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(30):put(out/'heartbeat.json',dict(utc_seconds=time.time(),state='merging_exact_operands',attempt=attempt))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:put(out/'heartbeat.json',dict(utc_seconds=time.time(),state='startup',attempt=attempt));r=consume(path,pin,attempt);put(out/'summary.json',r);rc=0
    finally:stop.set();t.join(2);put(out/'EXIT.json',dict(exit_code=rc,plan_sha256=pin,attempt=attempt,scientific_acceptance=False,utc_seconds=time.time()))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',required=True,type=int);x=a.parse_args();worker(x.plan,x.sha256,x.attempt)
