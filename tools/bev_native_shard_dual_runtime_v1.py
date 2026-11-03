"""Registered original DEV72 dual-identity sequential shard runtime; no model aliases."""
import argparse,fcntl,hashlib,json,os,threading,time,types
from pathlib import Path

def need(ok,msg):
    if not ok:raise ValueError(msg)
def safe(path):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p
def sha(path):
    with safe(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(safe(path).read_bytes())
def module(ref):
    need(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(safe(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def pinned(ref):
    need(type(ref)is dict and set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'pin changed');return read(ref['path'])
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def full_operand(L,*args):
    a,r=L.load_operand(*args);need(a['logits'].shape==(1,248320) and str(a['logits'].dtype)=='float32','full248320 FP32 required');return a,r

def shard_interface(B,C,reference_plan,base_contract):
    def build_dev72(parent,requests,model,execution):
        pop=B.build(reference_plan,base_contract);b=pop['binding']
        need(parent==b['parent_population'] and requests==b['inputs'] and model==b['model_sha256'] and execution==reference_plan,'runner source projection differs')
        return pop
    return types.SimpleNamespace(validate=C.validate,merge_population=C.merge_population,build_dev72=build_dev72,digest=C.digest)

def verify(path,pin,weights=True,host=False):
    need(sha(path)==pin,'plan changed');d=read(path)
    need(set(d)=={'schema','mode','shards','modules','population','baseline_plan','baseline_attempt','baseline_result_review','baseline_evidence','baseline_summary','baseline_terminal','model','model_files','model_sha256','contract_sha256','tolerance','environment','image','allocation','queue','out','run','chip','container','host_name','poll_seconds','scientific_acceptance','test_read','cpu_python','cpu_environment','files','mounts'},'plan fields')
    need(d['schema']=='native-dev72-dual-shard-execution-v1' and d['test_read']is False and d['scientific_acceptance']is False,'scope')
    need(d['mode']=='single_chip_two_sequential_shards' and d['shards']==[0,1] and all(type(x)is int for x in d['shards']) and type(d['chip'])is int and 0<=d['chip']<8,'layout')
    need(type(d['baseline_attempt'])is int and d['baseline_attempt']>0,'reference attempt')
    need(set(d['modules'])=={'runtime','host','resource','consumer','shard','contract','dual_contract','reference_runtime','reference_contract','upstream_binding','loader','native','probe','resource_base'},'module set')
    need(d['modules']['runtime']==ref(__file__),'runtime identity')
    excluded=set() if host else cpu_only(d)
    for f,h in d['files'].items():
        if f not in excluded and (weights or f not in d['model_files']):need(sha(f)==h,'source changed')
    B=module(d['modules']['dual_contract']);bp,c,r,m,proto,L,N,P,A,items,up=B.reference(d['baseline_plan'])
    for k in ('loader','native','probe','resource_base','upstream_binding'):need(d['modules'][k]==bp['modules'][k],'reference implementation differs')
    need(d['modules']['reference_runtime']==bp['modules']['runtime'] and d['modules']['reference_contract']==bp['modules']['contract'],'registered reference interface differs')
    need(d['model']==m['path'] and d['model_files']==m['files'] and d['model_sha256']==m['model_manifest_sha256'] and d['contract_sha256']==bp['contract_sha256'],'model/numeric contract')
    need(d['contract_sha256']!=d['baseline_plan']['sha256'],'host plan is not numeric contract')
    if weights:need({str(x) for x in safe(d['model']).iterdir() if x.is_file()}==set(d['model_files']),'model inventory')
    C=module(d['modules']['contract']);S=module(d['modules']['shard']);pop=pinned(d['population'])
    need(N.digest(pop)==N.digest(B.build(d['baseline_plan'],d['modules']['contract'])),'population changed')
    B.acceptance(d['baseline_result_review'],d['baseline_plan'],d['baseline_evidence'],d['baseline_summary'],d['baseline_terminal'],d['baseline_attempt'],read_artifacts=host)
    need(d['image']==L.IMAGE and d['environment']==L.ENV and type(d['poll_seconds'])is int and d['poll_seconds']==600 and type(d['tolerance'])is int and d['tolerance']==0,'runtime contract')
    need(d['host_name']=='k8s-node1' and d['chip']==bp['chip'] and d['allocation']==bp['allocation'],'resource identity')
    need(d['out']==str(Path(path).parent/'output') and Path(d['out']).is_relative_to('/mnt/cephfs/xingchao/experiments/jev/r3_runs') and d['run']=='r3_runs/'+Path(path).parent.name,'output identity')
    need(d['cpu_python']==bp['cpu_python'] and d['cpu_environment']==bp['cpu_environment'],'CPU interpreter/environment')
    q=pinned(d['queue']);need(q['predecessor']['plan']==d['baseline_plan'] and q['attempt']==d['baseline_attempt'] and q['chip']==d['chip'] and q['run']==d['run'],'physical predecessor')
    expected=closure(d,bp,c,r)
    need(d['files']==expected and d['mounts']==mounts(d,path),'exact source/mount closure')
    p={**proto,'upstream_root':up['root'],'files':{'upstream_tacit.py':{'path':str(Path(up['root'])/'anyjev/tacit.py'),'sha256':N.PINS['tacit.py']}}}
    need(S.load_requests(pop['binding'])==items,'request identity')
    return d,p,pop,L,N,P,shard_interface(B,C,d['baseline_plan'],d['modules']['contract']),S,items

def cpu_only(d):return {d['modules']['consumer']['path'],d['baseline_evidence']['path'],d['baseline_summary']['path'],d['baseline_terminal']['path']}
def closure(d,bp,c,r):
    expected=dict(d['model_files']);refs=[d['population'],d['baseline_plan'],d['baseline_result_review'],d['baseline_evidence'],d['baseline_summary'],d['baseline_terminal'],d['queue'],bp['config'],bp['registry'],c['inputs'],r['population']['source_plan'],r['population']['source_inputs'],*d['modules'].values()]
    q=read(d['queue']['path']);refs += [*q['predecessor'].values(),*q['priority_refs']]
    for x in refs:expected[x['path']]=x['sha256']
    N=module(d['modules']['native']);up=pinned(d['modules']['upstream_binding'])
    for name,h in N.PINS.items():expected[str(Path(up['root'])/'anyjev'/name)]=h
    return expected

def mounts(d,path):
    excluded=cpu_only(d);model=Path(d['model']);out=[dict(source=str(model),destination=str(model),readonly=True)]
    out += [dict(source=f,destination=f,readonly=True) for f in sorted(d['files']) if not Path(f).is_relative_to(model) and f not in excluded]
    out += [dict(source=str(path),destination=str(path),readonly=True),dict(source=d['out'],destination=d['out'],readonly=False)]
    out += [dict(source=f,destination=f,readonly=True) for f in ('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info')]
    need(all(not Path(x).is_relative_to(m['source']) for x in excluded for m in out),'CPU artifact exposed to NPU');return out

class Predictor:
    def __init__(self,d,p,L,N,P,model,tok,torch,out):
        self.d=d;self.p=p;self.L=L;self.N=N;self.P=P;self.model=model;self.tok=tok;self.torch=torch;self.out=Path(out);self.ref=N.reference(Path(p['upstream_root']))
        self.engine=P.upstream_engine(p['files']['upstream_tacit.py']['path'],p['files']['upstream_tacit.py']['sha256'],self.ref);self.collect=module(d['modules']['reference_runtime']).collect
    def operand(self,item):return self.out/'operands'/self.N.digest(item)
    def __call__(self,item):
        target=self.operand(item)
        if target.exists():return full_operand(self.L,target,self.P,self.d['contract_sha256'],item,self.N,'adapter')[1]['prediction']
        with self.torch.inference_mode():arrays,result=self.collect(self.model,self.tok,item,'adapter',self.L,self.N,self.P,self.ref,self.engine,self.d['contract_sha256'],self.p['max_length'])
        self.P.persist_operand(target,arrays,result)
        return full_operand(self.L,target,self.P,self.d['contract_sha256'],item,self.N,'adapter')[1]['prediction']
    def validate(self,pred,item,binding):
        need(binding['contract_sha256']==self.d['contract_sha256'] and binding['model_sha256']==self.d['model_sha256'],'validator binding differs')
        a,r=full_operand(self.L,self.operand(item),self.P,self.d['contract_sha256'],item,self.N,'adapter')
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
    return dict(schema='native-dev72-dual-shards-complete-v1',plan_scope='DEV72',shards=reports,items=72,scientific_acceptance=False,test_read=False,numerical_equivalence_verified=False)

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
            result=execute(*v,root,attempt);S.write_json(adir/'report.json',dict(result,plan_sha256=pin,attempt=attempt,contract_sha256=d['contract_sha256'],reference_plan_sha256=d['baseline_plan']['sha256'],model_sha256=d['model_sha256']));rc=0
        finally:
            stop.set();t.join(2);put(adir/'EXIT.json',dict(exit_code=rc,plan_sha256=pin,attempt=attempt,utc_seconds=time.time(),scientific_acceptance=False,test_read=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('op',choices=('verify','run'));a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,default=1);x=a.parse_args()
    if x.op=='verify':verify(x.plan,x.sha256);print('NATIVE_DEV72_SHARD_VERIFIED')
    else:run(x.plan,x.sha256,x.attempt)
