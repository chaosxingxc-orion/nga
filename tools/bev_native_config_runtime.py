"""Composition entrypoint for registered native operand experiments; no model-name dispatch."""
import argparse,fcntl,hashlib,json,math,os,threading,time,traceback,types
from pathlib import Path

def require(ok,reason):
    if not ok:raise ValueError(reason)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def read(p):
    def pairs(xs):
        d={}
        for k,v in xs:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    value=json.loads(Path(p).read_bytes(),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    def finite(v):
        if isinstance(v,float):require(math.isfinite(v),'nonfinite JSON')
        elif isinstance(v,dict):
            for x in v.values():finite(x)
        elif isinstance(v,list):
            for x in v:finite(x)
    finite(value);return value
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'adapter source changed')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def put(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.pending')
    with q.open('w') as f:json.dump(v,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,p)
def safe(p):
    p=Path(p);require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in [p,*p.parents]),'unsafe path');return p

def verify(path,pin,model_files=True):
    require(sha(path)==pin,'execution plan changed');d=read(path)
    require(set(d)=={'schema','config','registry','modules','files','model_files','contract_sha256','environment','image','mounts','allocation','queue','out','run','chip','container','host_name','poll_seconds','scientific_acceptance','test_read'},'plan fields differ')
    require(d['schema']=='native-config-execution-v1' and d['scientific_acceptance']is False and d['test_read']is False,'scope differs')
    require(type(d['poll_seconds'])is int and d['poll_seconds']==600,'cadence differs')
    require(d['modules']['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'runtime binding differs')
    for p,h in d['files'].items():require(sha(safe(p))==h,'dependency changed')
    for ref in [d['config'],d['registry'],*d['modules'].values()]:require(d['files'].get(ref['path'])==ref['sha256'],'unbound source')
    C=module(d['modules']['contract']);c=C.strict_json(Path(d['config']['path']).read_bytes());r=C.strict_json(Path(d['registry']['path']).read_bytes());C.validate(c,r)
    model=r['model'][c['model']];protocol=r['protocol'][c['protocol']];resource=r['resources'][c['resources']]
    require(d['out']==c['output'] and d['chip']==resource['chip'] and type(d['chip'])is int and d['run']=='r3_runs/'+c['run_id'],'derived identity differs')
    safe(d['out']);require(d['image']==r['platform']['image'],'image differs')
    require(protocol['dtype']=='float32' and protocol['hf32']is False and protocol['variants']==['reference','reference_repeat','adapter'],'adapter protocol unsupported')
    require(type(protocol['max_length'])is int and max(protocol['lengths'])<=protocol['max_length'],'length differs')
    require(c['adapters']=={'predictor':'native_transformers_full_labels_v1','validator':'native_exact_operands_v1','executor':'ascend_detached_single_v1'},'unregistered implementation')
    require(d['model_files']==model['files'],'model manifest differs')
    if model_files:
        require(not any(p.is_symlink() for p in safe(model['path']).rglob('*')),'model symlink')
        actual={str(p):sha(p) for p in safe(model['path']).rglob('*') if p.is_file()};require(actual==model['files'],'model bytes differ')
    L=module(d['modules']['loader']);require(d['environment']==L.ENV and d['image']==L.IMAGE,'loader environment differs')
    require(d['mounts']==mounts(d,path,model['path']),'mount closure differs')
    N=module(d['modules']['native']);P=module(d['modules']['probe'])
    require(d['files'].get(c['inputs']['path'])==c['inputs']['sha256'],'inputs outside mounted closure')
    expected={model['path']:model['model_manifest_sha256'],'protocol':protocol,'inputs':c['inputs'],'native':d['modules']['native'],'loader':d['modules']['loader'],'probe':d['modules']['probe']}
    require(d['contract_sha256']==N.digest(expected),'numerical contract differs')
    upstream=read(d['modules']['upstream_binding']['path'])
    for name,h in N.PINS.items():require(d['files'].get(str(Path(upstream['root'])/'anyjev'/name))==h,'upstream closure differs')
    with Path(c['inputs']['path']).open() as f:items=[C.strict_json(x) for x in f]
    return d,c,r,model,protocol,L,N,P,items,upstream

def mounts(d,path,model):
    out=[{'source':model,'destination':model,'readonly':True}]
    out += [{'source':f,'destination':f,'readonly':True} for f in sorted(d['files']) if not Path(f).is_relative_to(model)]
    out += [{'source':str(path),'destination':str(path),'readonly':True},{'source':d['out'],'destination':d['out'],'readonly':False}]
    out += [{'source':f,'destination':f,'readonly':True} for f in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']]
    return out

def collect(model,tok,item,variant,L,N,P,ref,engine,pin,limit):
    import numpy as np
    require(tok.padding_side=='left' and tok.encode(item['rendered_prompt'],add_special_tokens=False)==item['input_ids'],'tokenizer differs')
    capture=P.CaptureModel(model)
    if variant=='adapter':pred=N.read_model_batch(capture,[item],tok,mode='transformers_full_labels',contract_sha256=pin,prepared_pins=[N.digest(item)],max_length=limit,ref=ref)[0];lp=np.asarray(pred['restricted_logprobs'])
    else:
        lp=engine(capture,tok).read([item['rendered_prompt']],[item['label_ids']])[0]
        require(len(capture.calls)==1,'forward count differs');pred=N.read_logits(item,capture.calls[0]['logits'][0],mode='transformers_full_labels',contract_sha256=pin,prepared_sha256=N.digest(item),ref=ref)
    require(len(capture.calls)==1,'forward count differs');a=capture.calls[0]
    require(a['input_ids'].tolist()==[item['input_ids']] and a['attention_mask'].tolist()==[[1]*len(item['input_ids'])],'input/mask differs')
    require(a['logits'].shape==(1,248320) and str(a['logits'].dtype)=='float32' and np.isfinite(a['logits']).all(),'full vocabulary differs')
    require(np.array_equal(lp,np.asarray(pred['restricted_logprobs'])),'upstream arithmetic differs')
    return a,{'prediction':pred,'restricted_logprobs':lp.tolist(),'variant':variant,'forwards':1}

def run(path,pin,attempt):
    require(sha(path)==pin and type(attempt)is int and attempt>0,'plan/attempt differs');d=read(path);root=safe(d['out']);root.mkdir(parents=True,exist_ok=True)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);a=root/'attempts'/str(attempt);a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
        def event(stage,**kw):print(json.dumps({'utc_seconds':time.time(),'stage':stage,'attempt':attempt,**kw}),flush=True)
        def beat():
            while not stop.wait(30):put(a/'heartbeat.json',{'utc_seconds':time.time(),'state':'runtime_alive','attempt':attempt})
        t=threading.Thread(target=beat,daemon=True);t.start()
        try:
            put(a/'heartbeat.json',{'utc_seconds':time.time(),'state':'runtime_alive','attempt':attempt});event('startup');d,c,r,m,proto,L,N,P,items,up=verify(path,pin)
            for i in range(1,attempt):
                e=read(root/'attempts'/str(i)/'EXIT.json');require(type(e['exit_code'])is int and e['exit_code']!=0 and e['plan_sha256']==pin and type(e['attempt'])is int and e['attempt']==i and e['scientific_acceptance']is False,'previous attempt differs')
            model,tok,torch,T,TN=L.load_model({'model':m['path']});event('model_ready')
            ref=N.reference(Path(up['root']));engine=P.upstream_engine(str(Path(up['root'])/'anyjev/tacit.py'),N.PINS['tacit.py'],ref)
            def metadata():return {'chips':1,'reserved_gib':torch.npu.memory_reserved()/2**30,'peak_reserved_gib':torch.npu.max_memory_reserved()/2**30,'dtype':'float32','hf32':False,'torch':torch.__version__,'torch_npu':TN.__version__,'transformers':T.__version__}
            start=time.monotonic();count=0
            def collect_item(item,variant):
                nonlocal count
                with torch.inference_mode():v=collect(model,tok,item,variant,L,N,P,ref,engine,d['contract_sha256'],proto['max_length'])
                count+=1;event('forward_complete',completed=count,total=len(items)*len(proto['variants']),questions_per_second_per_chip=count/max(time.monotonic()-start,1e-9),**metadata());return v
            original_load=L.load_operand
            def full_operand(*args):
                arrays,result=original_load(*args);require(arrays['logits'].shape==(1,248320),'resumed full vocabulary differs');return arrays,result
            L.load_operand=full_operand
            result=L.execute(P,N,items,root,d['contract_sha256'],attempt,collect_item,metadata)
            result.update(plan_sha256=pin,attempt=attempt,model_sha256=m['model_manifest_sha256'],contract_sha256=d['contract_sha256']);put(a/'report.json',result);rc=0;event('complete',completed=result['completed_items'],reused=result['reused_items'])
        except BaseException:
            event('failed');traceback.print_exc();raise
        finally:stop.set();t.join(2);put(a/'EXIT.json',{'exit_code':rc,'attempt':attempt,'plan_sha256':pin,'scientific_acceptance':False,'utc_seconds':time.time()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','run']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('CONFIG_RUNTIME_VERIFIED')
    else:run(a.plan,a.sha256,a.attempt)
