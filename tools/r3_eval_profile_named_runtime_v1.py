#!/usr/bin/env python3
"""Pinned DEV profiler runtime; resumable chunks, never resumed timing claims."""
import argparse, contextlib, hashlib, json, math, os, threading, time, types
from pathlib import Path

def require(ok,why):
    if not ok: raise ValueError(why)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending')
    with t.open('w') as f:json.dump(v,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p);fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'source pin changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec',dont_inherit=True),m.__dict__);return m

def verify(path,pin):
    require(sha(path)==pin,'host plan changed');d=read(path)
    require(d['schema']=='r3-profile-host-v1' and d['chip']==6 and d['test_read'] is False and d['scientific_acceptance'] is False and d['candidate_selection_allowed'] is False,'scope differs')
    for f,h in d['files'].items():require(sha(f)==h,'dependency changed')
    require(d['files'].get(str(Path(__file__).resolve()))==sha(__file__),'foreign runtime')
    P=module(d['profile_runner']);p,cells=P.verify(d['profile']['path'],d['profile']['sha256'])
    require(d['image_sha256']==read(p['source_spec']['path'])['image_sha256'],'image differs')
    return d,P,p,cells

def batches(P,sc,cells,root,attempt,plan_pin,profiler=None,metadata=None,forward_observer=None):
    root=Path(root);items=root/'items';items.mkdir(exist_ok=True);trials=[];reused=0;pass_walls={}
    for phase in ['cold_reference','split_gate','warmup','wall_0','wall_1','wall_2','trace']:
        phase_begin=time.perf_counter()
        directory=items/phase;directory.mkdir(exist_ok=True)
        instrument=P.Instrument(sc) if phase=='trace' else contextlib.nullcontext()
        ctx=profiler(root/'attempts'/str(attempt)/'trace') if phase=='trace' and profiler else contextlib.nullcontext()
        with instrument as inst,ctx:
            for cell,rows in cells.items():
                target=directory/(hashlib.sha256(cell.encode()).hexdigest()+'.json');receipt=target.with_suffix('.receipt.json')
                if receipt.exists():
                    r=read(receipt);require(r['plan_sha256']==plan_pin and sha(target)==r['operand_sha256'],'saved item identity changed');v=read(target)
                    require(v['cell']==cell and [x['id'] for x in v['rows']]==[x['id'] for x in rows],'saved item population changed');reused+=1
                else:
                    require(not target.exists(),'orphan operand requires reconciliation')
                    original=sc.encode;captured=[]
                    before_stats=dict(getattr(sc,'stats',{}))
                    def encode(*a,**kw):
                        enc=original(*a,**kw);captured.append(P.digest(enc));return enc
                    sc.encode=encode;start=time.perf_counter()
                    try:
                        inputs=[x['row'] for x in rows]
                        scope=forward_observer.scope(phase,cell,rows) if forward_observer else contextlib.nullcontext()
                        with scope:
                            scores=sc.score_enc(sc.encode(inputs),mode='rightpad') if phase=='split_gate' else sc.score_raw(inputs,mode='rightpad')
                        sc._sync()
                    finally:sc.encode=original
                    elapsed=time.perf_counter()-start
                    after_stats=dict(getattr(sc,'stats',{}))
                    delta={k:after_stats.get(k,0)-before_stats.get(k,0)
                           for k in set(before_stats)|set(after_stats)
                           if isinstance(after_stats.get(k,0),(int,float)) and
                           isinstance(before_stats.get(k,0),(int,float))}
                    require(len(captured)==1 and len(scores)==len(rows),'scorer population differs')
                    require(all(len(s)==len(row['row']['levels']) and all(math.isfinite(float(x)) for x in s) for s,row in zip(scores,rows)),'invalid score')
                    v={'cell':cell,'encoded_sha256':captured[0],'rows':[{'id':row['id'],'s':s,'index':max(range(len(s)),key=lambda i:s[i]),'tie':s.count(max(s))>1} for row,s in zip(rows,scores)]}
                    commit=time.perf_counter();write(target,v);commit=time.perf_counter()-commit
                    r={'plan_sha256':plan_pin,'operand_sha256':sha(target),'attempt':attempt,
                       'score_wall_seconds':elapsed,'commit_seconds':commit,
                       'counter_delta':delta,
                       'tokens_per_second_per_chip':(delta.get('tokens',0)/elapsed if elapsed else None)};write(receipt,r)
                if phase!='cold_reference':
                    ref=read(items/'cold_reference'/target.name);require(v['encoded_sha256']==ref['encoded_sha256'],'encoded operands differ');P.compare_outputs(ref['rows'],v['rows'])
                trials.append(dict(r,phase=phase,cell=cell,rows=len(rows)))
                write(root/'heartbeat.json',{'utc_seconds':time.time(),'attempt':attempt,'phase':phase,'completed_chunks':len(trials),'total_chunks':len(cells)*7,'chips':1,'tokens_per_second_per_chip':r.get('tokens_per_second_per_chip') if r['attempt']==attempt else None,'runtime':metadata() if metadata else {}})
        if inst:write(root/'attempts'/str(attempt)/'host-trace.json',{'events':inst.events,'nested_not_additive':True})
        pass_walls[phase]=time.perf_counter()-phase_begin
    phases={}
    for phase in ['cold_reference','split_gate','warmup','wall_0','wall_1','wall_2','trace']:
        ts=[x for x in trials if x['phase']==phase]
        secs=sum(x.get('score_wall_seconds',0) for x in ts)
        toks=sum(x.get('counter_delta',{}).get('tokens',0) for x in ts)
        phases[phase]={'chunks':len(ts),'score_wall_seconds':secs,'tokens':toks,
                       'tokens_per_second_per_chip':(toks/secs if secs else None),
                       'wall_seconds_including_commit_and_comparison':pass_walls[phase],
                       'end_to_end_tokens_per_second_per_chip':(toks/pass_walls[phase] if reused==0 and attempt==1 else None),
                       'complete':len(ts)==len(cells)}
    return {'schema':'r3-profile-runtime-report-v1','trials':trials,'phases':phases,
            'reused_chunks':reused,'timing_comparable':reused==0 and attempt==1,
            'profile_overhead_ratio':(pass_walls['trace']/(sum(pass_walls['wall_'+str(i)] for i in range(3))/3) if reused==0 and attempt==1 else None),
            'all_raw_exact':True,'runtime':metadata() if metadata else {},'test_read':False,
            'scientific_acceptance':False,'candidate_selection_allowed':False,
            'measurement_scope':'score includes encode hashing and explicit completion sync; commits are diagnostic JSON/fsync, not production VerifiedStore; device attribution unavailable without independent trace interpretation; resumed timings must not support throughput claims'}

def run(path,pin,attempt):
    d=read(path);root=Path(d['out']);adir=root/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False);stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):
            write(adir/'heartbeat.json',{'utc_seconds':time.time(),'attempt':attempt,'state':'runtime_alive'})
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        d,P,p,cells=verify(path,pin);P.load_closure(p['files']);import torch,torch_npu
        torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
        require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 still enabled')
        SM=__import__('scorer_r3');sc=SM.R3Scorer(p['model'],adapter=p['adapter'],device='npu:0',dtype='float32',token_budget=16384)
        ts=time.perf_counter();sc.load();sc._sync();load_seconds=time.perf_counter()-ts
        def profiler(out):return torch_npu.profiler.profile(activities=[torch_npu.profiler.ProfilerActivity.CPU,torch_npu.profiler.ProfilerActivity.NPU],on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(str(out)))
        def metadata():return {'chips':1,'reserved_gib':torch.npu.memory_reserved()/2**30,'peak_reserved_gib':torch.npu.max_memory_reserved()/2**30,'model_load_seconds':load_seconds}
        result=batches(P,sc,cells,root,attempt,pin,profiler,metadata);write(adir/'report.json',result);rc=0
    finally:
        stop.set();t.join(2);write(adir/'EXIT.json',{'exit_code':rc,'attempt':attempt,'plan_sha256':pin,'utc_seconds':time.time(),'scientific_acceptance':False})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','run']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('PROFILE_HOST_INPUT_VERIFIED')
    else:require(a.attempt>0,'invalid attempt');run(a.plan,a.sha256,a.attempt)
if __name__=='__main__':main()
