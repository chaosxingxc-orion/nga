"""Fixed-base public TEST / synthetic long-DEV runner; no candidate TestTicket authority."""
import argparse, hashlib, json, os, time, threading, types
from pathlib import Path

def require(ok, why):
    if not ok: raise ValueError(why)
def sha(p):
    p=Path(p);require(p.is_absolute() and not any(x.is_symlink() for x in [p,*p.parents]),'unsafe path')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec'),m.__dict__);return m
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending')
    with t.open('w') as f:json.dump(v,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p);fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def exact(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def rows(path):
    with Path(path).open() as f:return [json.loads(line) for line in f]
def item_check(item, i, limit):
    require(set(item)=={'schema','i','qid','request_sha256','input_ids','rendered_prompt','labels','label_ids','options','kind'},'request fields differ')
    require(item['schema']=='bev-native-input-v1' and type(item['i']) is int and item['i']==i and type(item['qid']) is str,'request order/identity differs')
    require(type(item['input_ids']) is list and 0<len(item['input_ids'])<=limit and all(type(x) is int and x>=0 for x in item['input_ids']),'length/token differs')
    ids=item['label_ids'];require(type(ids) is list and len(ids)==len(set(ids))==len(item['options']) and len(ids)>=2 and all(type(x) is int and 0<=x<248320 for x in ids),'label ids differ')
    require(type(item['request_sha256']) is str and len(item['request_sha256'])==64,'request hash missing')
def fixed_base_name(model):
    p=Path(model)
    require(str(p)==model and p.parent in (Path('/mnt/cephfs/xingchao/models/jev'),Path('/mnt/cephfs/xingchao/omni/models/jev')),'fixed base mirror differs')
    require(p.name in ('Qwen__Qwen3.5-0.8B-Base','Qwen__Qwen3.5-2B-Base','Qwen__Qwen3.5-4B-Base'),'fixed base family member differs')
    return p.name.removeprefix('Qwen__')
def verify(path,pin):
    require(sha(path)==pin,'plan changed');d=read(path)
    require(d['schema']=='bev-native-panel-host-v1' and d['scope'] in ('public_fixed_base_test','synthetic_long_dev'),'scope differs')
    require(type(d['chip']) is int and d['chip'] in (0,5,6,7) and d['batch_size']==1 and type(d['batch_size']) is int and d['max_length']==8192,'chip/batch/length differs')
    require(d['scientific_acceptance'] is False and d['candidate_test_authority'] is False and d['candidate_selection_allowed'] is False,'candidate authority forbidden')
    require(d['test_read'] is (d['scope']=='public_fixed_base_test'),'public scope differs')
    require(d['poll_seconds']==600 and d['adapter'] is None,'poll/adapter differs')
    for f,h in d['files'].items():require(sha(f)==h,'dependency changed: '+f)
    for k in ('runtime','host','resource','loader_module','native','probe','inputs'):
        require(d['files'].get(d[k]['path'])==d[k]['sha256'],'dependency unbound')
    require(d['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'runner differs')
    L=module(d['loader_module']);require(exact(d['loader'],L.LOADER) and d['environment']==L.ENV and d['image_sha256']==L.IMAGE,'loader differs')
    require(d['mounts']==L.mounts(d,Path(path),{'model':d['model']}),'mount closure differs')
    model=Path(d['model']);actual={str(p):sha(p) for p in model.rglob('*') if p.is_file()}
    require(actual==d['model_files'],'model inventory differs')
    N=module(d['native']);require(N.digest(d['model_files'])==d['model_sha256'],'model manifest changed')
    expected={**d['model_files'],**{r['path']:r['sha256'] for r in d['upstream_files'].values()}}
    for k in ('runtime','host','resource','loader_module','native','probe','inputs'):expected[d[k]['path']]=d[k]['sha256']
    require(d['files']==expected,'closure differs')
    for n,h in N.PINS.items():require(d['upstream_files'][n]=={'path':str(Path(d['upstream_root'])/'anyjev'/n),'sha256':h},'upstream differs')
    items=rows(d['inputs']['path']);require(len(items)==d['count'],'population count differs')
    for i,item in enumerate(items):item_check(item,i,d['max_length'])
    require(N.digest(items)==d['ordered_inputs_sha256'],'ordered input hash differs')
    require(type(d['contract_sha256']) is str and len(d['contract_sha256'])==64,'contract missing')
    base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs');out=Path(d['out'])
    require(out.is_relative_to(base) and out.name=='output' and d['run']=='r3_runs/'+out.parent.name and not any(p.is_symlink() for p in [out,*out.parents]),'output identity differs')
    require(d['allocation']==str(base.parent/'CHIP-ALLOCATION.json') and d['container'].startswith('nga-native-panel-') and all(c.isalnum() or c in '-_' for c in d['container']),'lifecycle differs')
    fixed_base_name(d['model'])
    if d['scope']=='public_fixed_base_test':require(d['count']==46320,'full fixed-base TEST only')
    else:require(d['count']==3 and [len(x['input_ids']) for x in items]==[4097,5296,8192],'long DEV boundary panel differs')
    return d,L,N,items

def validate_prediction(pred,item,d,N):
    import numpy as np
    require(all(type(pred.get(k)) is int for k in ('i','index','first_index','reasoning_tokens')),'integer alias')
    require(pred.get('label_ids')==item['label_ids'] and all(type(x) is int for x in pred['label_ids']),'label ids differ')
    vals=pred.get('label_values');require(type(vals) is list and len(vals)==len(item['label_ids']) and all(type(x) in (int,float) and np.isfinite(x) for x in vals),'invalid restricted operands')
    # Reconstruction uses only compact selected operands; production checked full-vector finiteness.
    z=np.zeros(248320,dtype=np.float32);z[item['label_ids']]=vals
    expected=N.read_logits(item,z,mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_sha256=N.digest(item))
    require(exact(pred,expected),'compact prediction arithmetic or identity differs')
    require(type(pred['first_margin']) in (int,float) and np.isfinite(pred['first_margin']) and pred['first_margin']>=0,'strict margin differs')
    return pred

def load_item(dest,item,d,N):
    require(dest.is_dir() and not dest.is_symlink(),'item missing');receipt=read(dest/'COMMITTED.json')
    require(set(receipt)=={'record.json'} and receipt['record.json']==sha(dest/'record.json'),'partial/changed record')
    r=read(dest/'record.json');require(set(r)=={'schema','model_sha256','contract_sha256','prediction','forwards'} and r['schema']=='bev-native-compact-v1' and type(r['forwards']) is int and r['forwards']==1,'record shape differs')
    require(r['model_sha256']==d['model_sha256'] and r['contract_sha256']==d['contract_sha256'],'record generation differs')
    return validate_prediction(r['prediction'],item,d,N)

def execute(d,N,items,root,attempt,collect,metadata):
    started=time.monotonic();reused=0;computed=0;receipts=[]
    for i,item in enumerate(items):
        item_check(item,i,d['max_length']);dest=root/'items'/f'{i:06d}'
        if dest.exists():pred=load_item(dest,item,d,N);reused+=1
        else:
            pred=validate_prediction(collect(item),item,d,N);dest.mkdir(parents=True,exist_ok=False)
            write(dest/'record.json',dict(schema='bev-native-compact-v1',model_sha256=d['model_sha256'],contract_sha256=d['contract_sha256'],prediction=pred,forwards=1))
            write(dest/'COMMITTED.json',{'record.json':sha(dest/'record.json')});pred=load_item(dest,item,d,N);computed+=1
        receipts.append(sha(dest/'COMMITTED.json'))
        if (i+1)%100==0 or i+1==len(items):write(root/'heartbeat.json',dict(utc_seconds=time.time(),attempt=attempt,completed=i+1,total=len(items),computed=computed,reused=reused,questions_per_second_per_chip=computed/max(time.monotonic()-started,1e-9),runtime=metadata()))
    require({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(len(items))},'extra item directories')
    return dict(schema='bev-native-panel-completion-v1',completed=len(items),computed=computed,reused=reused,receipts_sha256=N.digest(receipts),contract_sha256=d['contract_sha256'],model_sha256=d['model_sha256'],ordered_inputs_sha256=d['ordered_inputs_sha256'],runtime=metadata(),scientific_acceptance=False,adaptive='NOT_EVALUATED')

def run(path,pin,attempt):
    d=read(path);root=Path(d['out']);adir=root/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False);stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):write(adir/'heartbeat.json',dict(utc_seconds=time.time(),attempt=attempt,state='runtime_alive'))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        d,L,N,items=verify(path,pin);model,tok,torch,T,TN=L.load_model({'model':d['model']});ref=N.reference(Path(d['upstream_root']))
        def metadata():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,torch=torch.__version__,torch_npu=TN.__version__,transformers=T.__version__,dtype='float32',hf32=False)
        if d['scope']=='synthetic_long_dev':
            P=module(d['probe']);engine=P.upstream_engine(d['upstream_files']['tacit.py']['path'],d['upstream_files']['tacit.py']['sha256'],ref)
            def collect(item):
                import numpy as np
                arrays=[];preds=[]
                for variant in ('reference','reference_repeat','adapter'):
                    capture=P.CaptureModel(model)
                    if variant=='adapter':pred=N.read_model_batch(capture,[item],tok,mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_pins=[N.digest(item)],max_length=8192,ref=ref)[0]
                    else:
                        lp=engine(capture,tok).read([item['rendered_prompt']],[item['label_ids']])[0]
                        require(len(capture.calls)==1,'forward count differs');pred=N.read_logits(item,capture.calls[0]['logits'][0],mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_sha256=N.digest(item),ref=ref)
                        require(np.array_equal(lp,np.asarray(pred['restricted_logprobs'])),'reference readout differs')
                    require(len(capture.calls)==1,'forward count differs');a=capture.calls[0]
                    require(a['input_ids'].tolist()==[item['input_ids']] and a['attention_mask'].tolist()==[[1]*len(item['input_ids'])],'long input differs')
                    P.persist_operand(root/'long_operands'/str(item['i'])/variant,a,dict(prediction=pred,restricted_logprobs=pred['restricted_logprobs'],variant=variant,forwards=1))
                    arrays.append(a);preds.append(pred)
                for a,p in zip(arrays[1:],preds[1:]):
                    require(all(arrays[0][k].dtype==a[k].dtype and np.array_equal(arrays[0][k],a[k]) for k in a) and exact(preds[0],p),'long DEV numerical equivalence failed')
                return preds[-1]
        else:
            def collect(item):return N.read_model_batch(model,[item],tok,mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_pins=[N.digest(item)],max_length=8192,ref=ref)[0]
        report=execute(d,N,items,root,attempt,collect,metadata);report['forwards_per_new_item']=3 if d['scope']=='synthetic_long_dev' else 1
        write(adir/'report.json',report);rc=0
    finally:
        stop.set();t.join(2);write(adir/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,utc_seconds=time.time(),scientific_acceptance=False))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('op',choices=['verify','run']);a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,default=1);v=a.parse_args()
    if v.op=='verify':verify(v.plan,v.sha256);print('NATIVE_PANEL_VERIFIED')
    else:run(v.plan,v.sha256,v.attempt)
