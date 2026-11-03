"""Pinned DEV72 native operand execution. No TEST, timing or scientific admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import types

PROBE_SHA = 'c91223dd74373aa4804efea3edfc6cd9c63ad4b37d4082dd64983d6aeba18ffb'
PLAN_SHA = '1ccedb5451ea0dd64154489f95a6522eecb50278410b900864b03527b6221098'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
LOADER = dict(dtype='float32', device='npu:0', eval=True, local_files_only=True,
              trust_remote_code=False, hf32=False, padding_side='left')
ENV = dict(PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
           HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TASK_QUEUE_ENABLE='2',
           ASCEND_RT_VISIBLE_DEVICES='0')

def require(ok, why):
    if not ok: raise ValueError(why)

def sha(p):
    p=Path(p)
    require(p.is_absolute() and not any(x.is_symlink() for x in [p,*p.parents]),'unsafe path')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''): h.update(b)
    return h.hexdigest()

def read(p): return json.loads(Path(p).read_bytes())
def exact_json(a,b):
    return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'module pin differs')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path']
    exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec',dont_inherit=True),m.__dict__)
    return m

def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending')
    with t.open('w') as f: json.dump(v,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p);fd=os.open(p.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def mounts(d, path, p):
    model=Path(p['model'])
    result=[dict(source=str(model),destination=str(model),readonly=True)]
    result += [dict(source=f,destination=f,readonly=True) for f in sorted(d['files']) if not Path(f).is_relative_to(model)]
    result += [dict(source=str(path),destination=str(path),readonly=True),dict(source=d['out'],destination=d['out'],readonly=False)]
    result += [dict(source=f,destination=f,readonly=True) for f in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']]
    return result

def verify(path,pin):
    require(sha(path)==pin,'host plan differs');d=read(path)
    require(d['schema']=='bev-native-dev-host-v1' and type(d['chip']) is int and d['chip'] in (0,7),'scope/chip differs')
    require(all(d[k] is False for k in ('test_read','scientific_acceptance','candidate_selection_allowed','timing_enabled')),'scope differs')
    require(json.dumps(d['loader'],sort_keys=True)==json.dumps(LOADER,sort_keys=True) and d['environment']==ENV and d['image_sha256']==IMAGE and d['poll_seconds']==600,'loader/image/environment differs')
    require(d['probe']['sha256']==PROBE_SHA and d['probe_plan']['sha256']==PLAN_SHA,'original probe differs')
    for f,h in d['files'].items():require(sha(f)==h,'dependency differs')
    for key in ('runtime','host','resource','probe','probe_plan'):
        require(d['files'].get(d[key]['path'])==d[key]['sha256'],'unbound dependency')
    require(d['runtime']['path']==str(Path(__file__).resolve()) and d['runtime']['sha256']==sha(__file__),'foreign runner')
    P=module(d['probe']);p,items,R=P.verify(d['probe_plan']['path'],d['probe_plan']['sha256'])
    required={p['inputs']['path']:p['inputs']['sha256']}
    for ref in [*p['files'].values(),*p['model_files'].values()]:required[ref['path']]=ref['sha256']
    for key in ('runtime','host','resource','probe','probe_plan'):required[d[key]['path']]=d[key]['sha256']
    require(d['files']==required,'incomplete or extra probe closure')
    require(d['mounts']==mounts(d,path,p),'mount closure differs')
    out=Path(d['out']);base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
    require(out.is_relative_to(base) and out.name=='output' and d['run']=='r3_runs/'+out.parent.name,'output identity differs')
    require(d['allocation']==str(base.parent/'CHIP-ALLOCATION.json'),'allocation differs')
    require(d['container'].startswith('nga-native-dev-') and all(x.isalnum() or x in '-_' for x in d['container']),'container differs')
    require(not any(x.is_symlink() for x in [out,*out.parents]),'unsafe output')
    return d,P,p,items,R

def load_operand(path,P,pin,item,R,variant):
    import numpy as np
    require(path.is_dir() and not path.is_symlink(),'missing operand')
    receipt=read(path/'COMMITTED.json')
    require(set(receipt)=={'operands.npz','result.json'},'incomplete operand receipt')
    for n,h in receipt.items():require(sha(path/n)==h,'operand changed')
    result=read(path/'result.json')
    require(result['variant']==variant and type(result['forwards']) is int and result['forwards']==1,'operand variant differs')
    pred=result['prediction']
    require(all(type(pred[k]) is int for k in ('i','index','first_index','reasoning_tokens')), 'prediction integer types differ')
    require(pred['contract_sha256']==pin and pred['request_sha256']==item['request_sha256'] and pred['i']==item['i'] and pred['qid']==item['qid'],'operand generation differs')
    with np.load(path/'operands.npz',allow_pickle=False) as z: arrays={k:z[k] for k in z.files}
    require(set(arrays)=={'input_ids','attention_mask','logits'},'operand fields differ')
    require(all(a.dtype==np.dtype('int64') and a.shape==(1,len(item['input_ids'])) for a in (arrays['input_ids'],arrays['attention_mask'])), 'input tensor shape/dtype differs')
    require(arrays['input_ids'].tolist()==[item['input_ids']] and arrays['attention_mask'].tolist()==[[1]*len(item['input_ids'])] and np.isfinite(arrays['logits']).all(),'operand inputs differ')
    require(arrays['logits'].ndim==2 and arrays['logits'].shape[0]==1 and str(arrays['logits'].dtype)=='float32','logit shape/dtype differs')
    expected=R.read_logits(item,arrays['logits'][0],mode='transformers_full_labels',contract_sha256=pin,prepared_sha256=R.digest(item))
    require(exact_json(pred,expected) and exact_json(result['restricted_logprobs'],expected['restricted_logprobs']),'persisted native output differs')
    return arrays,result

def execute(P,R,items,root,pin,attempt,collect,metadata):
    reused=0;completed=0
    for variant in ('reference','reference_repeat','adapter'):
        for item in items:
            key=R.digest(item);dest=root/'items'/variant/key
            if dest.exists():
                arrays,result=load_operand(dest,P,pin,item,R,variant);reused+=1
            else:
                arrays,result=collect(item,variant);dest.parent.mkdir(parents=True,exist_ok=True)
                P.persist_operand(dest,arrays,result)
                arrays,result=load_operand(dest,P,pin,item,R,variant)
            if variant!='reference':
                ref,rr=load_operand(root/'items/reference'/key,P,pin,item,R,'reference')
                P.compare_operands(ref,arrays,rr,result)
            completed+=1
            write(root/'heartbeat.json',dict(utc_seconds=time.time(),attempt=attempt,variant=variant,completed_items=completed,total_items=len(items)*3,runtime=metadata()))
    return dict(schema='bev-native-dev-result-v1',items=len(items),passes=3,completed_items=completed,reused_items=reused,all_raw_exact=True,runtime=metadata(),timing_claim=False,test_read=False,scientific_acceptance=False)

def load_model(p):
    import torch,torch_npu,transformers
    torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
    require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 enabled')
    tok=transformers.AutoTokenizer.from_pretrained(p['model'],local_files_only=True,trust_remote_code=False)
    tok.padding_side='left'
    model=transformers.AutoModelForCausalLM.from_pretrained(p['model'],dtype=torch.float32,local_files_only=True,trust_remote_code=False).to('npu:0').eval()
    require(not model.training and all(x.dtype==torch.float32 for x in model.parameters() if x.is_floating_point()),'model dtype/eval differs')
    return model,tok,torch,transformers,torch_npu

def run(path,pin,attempt):
    d=read(path);root=Path(d['out']);adir=root/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False);stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):write(adir/'heartbeat.json',dict(utc_seconds=time.time(),attempt=attempt,state='runtime_alive'))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        d,P,p,items,R=verify(path,pin);model,tok,torch,T,N=load_model(p)
        ref=R.reference(Path(p['upstream_root']));engine=P.upstream_engine(p['files']['upstream_tacit.py']['path'],p['files']['upstream_tacit.py']['sha256'],ref)
        def metadata():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,torch=torch.__version__,torch_npu=N.__version__,transformers=T.__version__,dtype='float32',hf32=False)
        def collect(item,variant):
            with torch.inference_mode():return P.collect_one(model,tok,item,R,ref,engine,pin,variant)
        result=execute(P,R,items,root,pin,attempt,collect,metadata)
        write(adir/'report.json',result);rc=0
    finally:
        stop.set();t.join(2);write(adir/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,utc_seconds=time.time(),scientific_acceptance=False))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','run']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('NATIVE_DEV_EXECUTION_VERIFIED')
    else:run(a.plan,a.sha256,a.attempt)
if __name__=='__main__':main()
