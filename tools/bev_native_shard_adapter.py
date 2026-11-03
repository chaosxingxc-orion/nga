"""Real native DEV72 adapter: exact immutable model, inputs and actual operands."""
import argparse,fcntl,hashlib,importlib.util,json,os,threading,time,types
from pathlib import Path

def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(path):
    p=safe(path)
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def safe(path):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in [p,*p.parents]),'unsafe path');return p
def read(path):return json.loads(safe(path).read_bytes())
def module(ref):
    need(sha(ref['path'])==ref['sha256'],'module pin differs');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def pinned(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'pin differs');return read(ref['path'])
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def verify(path,pin,weights=True,host=False):
    need(sha(path)==pin,'plan differs');d=read(path)
    need(set(d)=={'schema','mode','shards','modules','population','probe_plan','baseline_plan','baseline_review','baseline_evidence','model','model_files','model_sha256','contract_sha256','tolerance','environment','image','allocation','queue','out','run','chip','container','host_name','poll_seconds','scientific_acceptance','test_read','cpu_python','cpu_environment','files','mounts'},'plan fields differ')
    need(set(d['modules'])=={'runtime','host','resource','consumer','shard','contract','loader','native','probe','resource_base'},'module registry differs')
    need(d['schema']=='native-dev72-shard-execution-v1' and d['test_read'] is False and d['scientific_acceptance'] is False,'scope differs')
    need(d['mode']=='single_chip_two_sequential_shards' and d['shards']==[0,1] and all(type(x) is int for x in d['shards']) and type(d['chip']) is int and 0<=d['chip']<8,'execution layout differs')
    need(d['modules']['runtime']==ref(__file__),'runtime differs')
    for x in [d['population'],d['probe_plan'],d['baseline_plan'],d['baseline_review'],d['baseline_evidence'],d['queue'],*d['modules'].values()]:need(d['files'].get(x['path'])==x['sha256'],'unbound source')
    excluded=set() if host else cpu_only(d)
    for f,h in d['files'].items():
        if f not in excluded and (weights or f not in d['model_files']):need(sha(f)==h,'source changed')
    L=module(d['modules']['loader']);N=module(d['modules']['native']);P=module(d['modules']['probe']);C=module(d['modules']['contract']);S=module(d['modules']['shard'])
    need(d['image']==L.IMAGE and d['environment']==L.ENV and type(d['poll_seconds']) is int and d['poll_seconds']==600,'runtime environment differs')
    p=pinned(d['probe_plan']);need(p['schema']=='bev-native-dev-probe-v1' and p['test_read'] is False and p['scientific_acceptance'] is False and p['tolerance']==0,'probe scope differs')
    need(p['source_split']=='train_derived_dev' and type(p['batch_size']) is int and p['batch_size']==1 and p['max_length']==4096 and p['dtype']=='float32' and p['hf32'] is False and p['padding_side']=='left' and p['mode']=='transformers_full_labels' and p['passes']==['reference','reference_repeat','adapter'],'DEV numerical settings differ')
    need(d['modules']['native']==p['runtime'] and d['modules']['probe']==p['files']['bev_native_dev_probe.py'],'native source binding differs')
    model_files={v['path']:v['sha256'] for v in p['model_files'].values()};need(d['model_files']==model_files and d['model_sha256']==N.digest(model_files) and d['model']==p['model'],'model manifest differs')
    need(p['model'].endswith('/Qwen__Qwen3.5-0.8B-Base'),'DEV72 baseline only; register other models separately')
    if weights:need({str(x) for x in safe(d['model']).iterdir() if x.is_file()}==set(model_files),'model inventory differs')
    population=pinned(d['population']);b=C.validate(population);
    need(d['files'].get(b['inputs']['path'])==b['inputs']['sha256'],'request closure missing');
    need(b.get('source_kind')=='native_dev72' and b['parent_population']==d['probe_plan'] and b['model_sha256']==d['model_sha256'],'population kind/model differs')
    need(N.digest(population)==N.digest(C.build_dev72(d['probe_plan'],b['inputs'],d['model_sha256'],d['baseline_plan'])),'population transformed')
    baseline=pinned(d['baseline_plan']);review=pinned(d['baseline_review']);need(baseline['probe_plan']==d['probe_plan'] and baseline['runtime']==d['modules']['loader'],'baseline source differs')
    need(review.get('verdict')=='PASS' and review.get('approved_plan_sha256')==d['baseline_plan']['sha256'],'baseline review differs')
    need(d['tolerance']==0 and type(d['tolerance']) is int and d['contract_sha256']==d['baseline_plan']['sha256'],'numerical contract differs')
    safe(d['out']);need(Path(d['out']).is_relative_to('/mnt/cephfs/xingchao/experiments/jev/r3_runs'),'output root differs')
    need(d['out']==str(Path(path).parent/'output') and d['run']=='r3_runs/'+Path(path).parent.name and d['host_name']=='k8s-node1','run identity differs')
    need(d['allocation']=='/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json','allocation differs')
    need(d['cpu_python']=='/mnt/cephfs/xingchao/experiments/jev/r3_runs/reviewer_torch_runtime_20261101_v1/python/bin/python3.12','CPU interpreter differs')
    need(set(d['cpu_environment'])=={'LD_LIBRARY_PATH','PYTHONDONTWRITEBYTECODE','PYTHONPATH','TORCH_DEVICE_BACKEND_AUTOLOAD'} and d['cpu_environment']['PYTHONDONTWRITEBYTECODE']=='1' and d['cpu_environment']['TORCH_DEVICE_BACKEND_AUTOLOAD']=='0','CPU environment differs')
    for k in ('LD_LIBRARY_PATH','PYTHONPATH'):safe(d['cpu_environment'][k])
    q=pinned(d['queue']);need(q['run']==d['run'] and q['chip']==d['chip'],'resource policy identity differs')
    expected=dict(d['model_files'])
    refs=[d['population'],b['inputs'],d['probe_plan'],p['inputs'],d['baseline_plan'],d['baseline_review'],d['baseline_evidence'],d['queue'],*d['modules'].values(),*p['files'].values(),*q['predecessor'].values(),*q['priority_refs']]
    for x in refs:expected[x['path']]=x['sha256']
    need(d['files']==expected,'exact source closure differs')
    need(d['mounts']==mounts(d,path),'mount closure differs')
    items=S.load_requests(b);P.validate_items(items,N,p['ordered_input_sha256'])
    return d,p,population,L,N,P,C,S,items

def cpu_only(d):return {d['modules']['consumer']['path'],d['baseline_evidence']['path']}

def mounts(d,path):
    excluded=cpu_only(d)
    model=Path(d['model']);out=[dict(source=str(model),destination=str(model),readonly=True)]
    out += [dict(source=f,destination=f,readonly=True) for f in sorted(d['files']) if not Path(f).is_relative_to(model) and f not in excluded]
    out += [dict(source=str(path),destination=str(path),readonly=True),dict(source=d['out'],destination=d['out'],readonly=False)]
    out += [dict(source=f,destination=f,readonly=True) for f in ('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info')]
    ancestors=[Path(x['source']) for x in out]
    need(all(not Path(x).is_relative_to(a) for x in excluded for a in ancestors),'CPU-only file under NPU mount ancestor')
    return out

class Predictor:
    def __init__(self,d,p,L,N,P,model,tok,torch,out):
        self.d=d;self.p=p;self.L=L;self.N=N;self.P=P;self.model=model;self.tok=tok;self.torch=torch;self.out=Path(out);self.ref=N.reference(Path(p['upstream_root']))
        self.engine=P.upstream_engine(p['files']['upstream_tacit.py']['path'],p['files']['upstream_tacit.py']['sha256'],self.ref)
    def operand(self,item):return self.out/'operands'/self.N.digest(item)
    def __call__(self,item):
        target=self.operand(item)
        if target.exists():return self.L.load_operand(target,self.P,self.d['contract_sha256'],item,self.N,'adapter')[1]['prediction']
        with self.torch.inference_mode():arrays,result=self.P.collect_one(self.model,self.tok,item,self.N,self.ref,self.engine,self.d['contract_sha256'],'adapter')
        self.P.persist_operand(target,arrays,result)
        return self.L.load_operand(target,self.P,self.d['contract_sha256'],item,self.N,'adapter')[1]['prediction']
    def validate(self,pred,item,binding):
        need(binding['contract_sha256']==self.d['contract_sha256'] and binding['model_sha256']==self.d['model_sha256'],'validator binding differs')
        a,r=self.L.load_operand(self.operand(item),self.P,self.d['contract_sha256'],item,self.N,'adapter')
        need(self.L.exact_json(pred,r['prediction']),'prediction differs from actual persisted full operands')

def execute(d,p,pop,L,N,P,C,S,items,root,attempt,model_bundle=None):
    model,tok,torch,T,TN=L.load_model({'model':d['model']}) if model_bundle is None else model_bundle
    adapter=Predictor(d,p,L,N,P,model,tok,torch,root)
    def metadata():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,dtype='float32',hf32=False)
    reports=[]
    for sid in d['shards']:
        out=root/'shards'/str(sid)
        previous=sorted((out/'attempts').glob('*/EXIT.json'),key=lambda x:int(x.parent.name)) if (out/'attempts').exists() else []
        if previous and type(S.read_json(previous[-1]).get('exit_code')) is int and S.read_json(previous[-1])['exit_code']==0:
            a=S.read_json(previous[-1]);need(type(a.get('attempt')) is int and a['attempt']==int(previous[-1].parent.name) and type(a.get('shard_id')) is int and a['shard_id']==sid,'prior shard terminal identity differs');need(a['generation_sha256']==S.digest({'population':d['population'],'shard_id':sid}) and a['scientific_acceptance'] is False and a['execution_authorized'] is False,'prior shard identity differs')
            for pos in pop['shards'][sid]['global_ordinals']:
                item=items[pos];pred=S._load_item(out/'items'/f'{pos:06d}',item,pos,d['model_sha256'],d['contract_sha256']);adapter.validate(pred,item,pop['binding'])
            reports.append(dict(shard_id=sid,reused_successful_shard=True));continue
        local_attempt=int(previous[-1].parent.name)+1 if previous else 1
        reports.append(S.run_shard(d['population'],sid,out,adapter,adapter.validate,attempt=local_attempt,metadata=metadata,contract=C))
    return dict(schema='native-dev72-shards-complete-v1',plan_scope='DEV72',shards=reports,items=72,scientific_acceptance=False,test_read=False,numerical_equivalence_verified=False)

def run(path,pin,attempt):
    need(type(attempt) is int and attempt>0 and sha(path)==pin,'attempt/plan differs');d=read(path);root=safe(d['out']);root.mkdir(parents=True,exist_ok=True)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);adir=root/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
        def put(p,x):
            tmp=p.with_name(p.name+'.pending')
            with tmp.open('w') as f:json.dump(x,f);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,p);fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        def beat():
            while not stop.wait(30):put(adir/'heartbeat.json',dict(utc_seconds=time.time(),state='native_shard_runtime',attempt=attempt))
        t=threading.Thread(target=beat,daemon=True);t.start()
        try:
            put(adir/'heartbeat.json',dict(utc_seconds=time.time(),state='startup',attempt=attempt));v=verify(path,pin);d,p,pop,L,N,P,C,S,items=v
            for prior in range(1,attempt):
                e=read(root/'attempts'/str(prior)/'EXIT.json');need(type(e['exit_code']) is int and e['exit_code']!=0 and e['plan_sha256']==pin and type(e['attempt']) is int and e['attempt']==prior and e['scientific_acceptance'] is False,'previous attempt differs')
            print(json.dumps(dict(stage='verified',attempt=attempt,items=len(items))),flush=True)
            result=execute(*v,root,attempt);S.write_json(adir/'report.json',dict(result,plan_sha256=pin,attempt=attempt));rc=0
        finally:
            stop.set();t.join(2);put(adir/'EXIT.json',dict(exit_code=rc,plan_sha256=pin,attempt=attempt,utc_seconds=time.time(),scientific_acceptance=False,test_read=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('op',choices=('verify','run'));a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,default=1);x=a.parse_args()
    if x.op=='verify':verify(x.plan,x.sha256);print('NATIVE_DEV72_SHARD_VERIFIED')
    else:run(x.plan,x.sha256,x.attempt)
