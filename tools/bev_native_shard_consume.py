"""Detached CPU-only DEV72 merge after physical release; raw equality, no science."""
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
    d=read(path);A=module(d['modules']['runtime']);v=A.verify(path,pin,weights=False,host=True);d,p,pop,L,N,P,C,S,items=v
    need(d['modules']['consumer']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'consumer source differs');lifecycle(d,path,pin,attempt)
    baseline=A.pinned(d['baseline_evidence']);need(baseline['plan']==d['baseline_plan'] and baseline['attempt']==1 and baseline['scientific_acceptance'] is False,'baseline evidence scope')
    for f,h in baseline['files'].items():need(sha(f)==h,'baseline evidence changed')
    bp=A.pinned(d['baseline_plan']);bh=Path(bp['out'])/'host_attempts/1';ba=Path(bp['out'])/'attempts/1'
    bt=read(ba/'EXIT.json');be=read(bh/'EXIT.json');br=read(bh/'RELEASE.json');bc=read(bh/'CLAIM.json');receipt=read(bh/'LAUNCH_RECEIPT.json')
    need(type(bt.get('exit_code')) is int and bt['exit_code']==0 and bt['plan_sha256']==d['baseline_plan']['sha256'] and bt['attempt']==1 and bt['scientific_acceptance'] is False,'baseline runtime absent')
    need(be['exit_code']==0 and be['container_exit_code']==0 and be['runner_terminal_matches'] is True and br['exit_code']==0 and br['claim_sha256']==sha(bh/'CLAIM.json') and br['run']==bc['run']==bp['run'] and br['chip']==bc['chip']==bp['chip'] and br['container_id']==be['container_id']==receipt['container_id'],'baseline release absent')
    root=Path(d['out']);results=[];allpred=[];compared=0
    for sid in (0,1):
        out=root/'shards'/str(sid);attempts=sorted((out/'attempts').glob('*/EXIT.json'),key=lambda x:int(x.parent.name));need(attempts,'shard terminal absent');t=read(attempts[-1]);need(type(t['exit_code']) is int and t['exit_code']==0 and t['generation_sha256']==S.digest({'population':d['population'],'shard_id':sid}) and t['scientific_acceptance'] is False and t['execution_authorized'] is False,'shard incomplete')
        ids=pop['shards'][sid]['global_ordinals'];need({x.name for x in (out/'items').iterdir()}=={f'{x:06d}' for x in ids},'shard item population differs');predictions=[]
        for pos in ids:
            item=items[pos];pred=S._load_item(out/'items'/f'{pos:06d}',item,pos,d['model_sha256'],d['contract_sha256'])
            a,r=L.load_operand(root/'operands'/N.digest(item),P,d['contract_sha256'],item,N,'adapter')
            need(L.exact_json(pred,r['prediction']),'merge arithmetic differs')
            baseline_path=Path(bp['out'])/'items/reference'/N.digest(item)
            need(all(str(baseline_path/n) in baseline['files'] for n in ('COMMITTED.json','operands.npz','result.json')),'baseline operand unbound')
            left,lr=L.load_operand(baseline_path,P,d['contract_sha256'],item,N,'reference');P.compare_operands(left,a,lr,r);compared+=1;predictions.append(pred)
        results.append(dict(shard_id=sid,manifest_sha256=S.digest(pop['shards'][sid]),exit_code=0,model_sha256=d['model_sha256'],contract_sha256=d['contract_sha256'],scientific_acceptance=False,predictions=predictions))
    merged=C.merge_population(pop,items,results);need(compared==72 and [x['i'] for x in merged['predictions']]==pop['binding']['source_indices'],'merged source order differs')
    return dict(schema='native-dev72-shard-comparison-v1',items=72,raw_operand_equal=72,zero_tolerance=True,model_sha256=d['model_sha256'],ordered_inputs_sha256=pop['binding']['ordered_inputs_sha256'],merged_predictions_sha256=N.digest(merged['predictions']),plan_sha256=pin,attempt=attempt,lifecycle_verified=True,numerical_equivalence_observed=True,scientific_acceptance=False,test_read=False,cross_card_equivalence=False,timing_claim=False)

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
