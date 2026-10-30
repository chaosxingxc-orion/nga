"""E36 actual original-versus-chunked forwards, never full-test scoring."""
import argparse, contextlib, hashlib, importlib.util, json, math, sys, threading, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from openjev_candidate_chunks import candidate_chunks

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def atomic(p,x):
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2)+'\n');q.replace(p)
def check(v,m):
    if not v:raise ValueError(m)
def delta(a,b):
    check(len(a)==len(b),'numeric shape changed');return max([abs(x-y) for x,y in zip(a,b)]+[0.])
def numeric_wire(v):
    if isinstance(v,dict):return sum((numeric_wire(v[k]) for k in v),[])
    return [float(v)] if type(v) in (int,float) else []
def compare(a,b):
    pa,pb=a['prediction'],b['prediction']
    check(list(pa['native_probabilities'])==list(pb['native_probabilities']),'probability keys changed')
    aa,ab=pa['answer'],pb['answer'];kind=aa['type']
    check(list(aa)==list(ab) and aa['type']==ab['type'],'wire schema/order changed')
    for field in ['probabilities','legend']:
        if field in aa:check(list(aa[field])==list(ab[field]),'wire candidate order changed')
    if 'legend' in aa:check(aa['legend']==ab['legend'],'wire legend changed')
    selected=lambda x:x['choice'] if kind=='choice' else x['noul']>=.5 if kind=='noul' else max(x['probabilities'],key=x['probabilities'].get)
    return dict(logits=delta(pa['logits'],pb['logits']),probabilities=delta(list(pa['native_probabilities'].values()),list(pb['native_probabilities'].values())),wire=delta(numeric_wire(aa),numeric_wire(ab)),wire_exact=aa==ab,decision_same=selected(aa)==selected(ab),tokens_same=pa['consumed_token_sha256']==pb['consumed_token_sha256'])
def main(path):
    plan=load(path);ch=sha(path);out=Path(plan['out']);check(not(out/'COMPLETE.json').exists(),'terminal exists')
    state=dict(stage='verify',progress=0,total=16,chips=1);stop=threading.Event();rc=1;error=None
    def beat():
        while not stop.wait(10):
            snap=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**state);atomic(out/'STATUS.json',snap)
            (out/'digest.md').write_text(json.dumps(snap)+'\n')
            with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(snap)+'\n')
    th=threading.Thread(target=beat,daemon=True);th.start()
    try:
        for p,h in plan['files'].items():check(sha(p)==h,'frozen file changed '+p)
        check(sha(plan['source_config'])==plan['source_config_sha256'],'source config changed')
        c=load(plan['source_config']);sys.path.insert(0,str(Path(c['out'])))
        import jeval_reference_inference as d
        eligible=d.verify_files(c)
        import pyarrow.parquet as pq
        rows=pq.read_table(c['data']).to_pylist();entries=[e for e in eligible['items'] if e['status']=='eligible']
        metrics={'max_length':lambda e:e['max_tokens'],'max_width':lambda e:len(e['lengths']),'max_padded':lambda e:len(e['lengths'])*e['max_tokens'],'max_attention_cells':lambda e:len(e['lengths'])*e['max_tokens']**2}
        selected={name:max(entries,key=lambda e:(fun(e),-e['index'])) for name,fun in metrics.items()}
        envelope=dict(eligible=len(entries),chunk_rows=plan['chunk_rows'],selection={n:{k:e[k] for k in ['index','id','candidate_count','max_tokens']} for n,e in selected.items()},max_chunk_padded=max(min(len(e['lengths']),plan['chunk_rows'])*e['max_tokens'] for e in entries),max_retained_hidden_tokens=max(len(e['lengths'])*e['max_tokens'] for e in entries),source_report_sha256=sha(c['eligibility_report']))
        atomic(out/'ENVELOPE.json',envelope)
        state['stage']='load_model';model=d.Native(c);torch=model.torch
        cases=[]
        for kind in ['choice','noul','score']:
            q={'type':kind,'instructions':'Choose the appropriate synthetic level.'}
            if kind!='noul':q['criteria']={'a':'first','b':'second'} if kind=='choice' else ['low','middle','high']
            req={'state':'Synthetic observation: choose the first level.','questions':{'q':q}}
            cases.append((kind,req,model.eligibility(req),True))
        used=set()
        for name,e in selected.items():
            if e['index'] in used:continue
            used.add(e['index']);req=d.request(rows[e['index']]);actual=model.eligibility(req)
            check(all(e.get(k)==v for k,v in actual.items()),'selected eligibility differs')
            cases.append((name+'_'+str(e['index']),req,actual,name=='max_length'))
        total=sum(4 if baseline else 2 for _,_,_,baseline in cases);state['total']=total;folder=out/'items';folder.mkdir(exist_ok=True);results={};count=0
        for name,req,e,baseline in cases:
            results[name]={}
            for mode in (['original','chunked'] if baseline else ['chunked']):
                results[name][mode]=[]
                for rep in range(2):
                    p=folder/(name+'_'+mode+'_'+str(rep)+'.json');state.update(stage=name+'/'+mode,progress=count)
                    if p.exists():
                        env=load(p);value=env['payload'];check(d.stamp(value)==env['sha256'] and value['plan_sha256']==ch and value['request_sha256']==d.stamp(req),'foreign receipt')
                    else:
                        torch.npu.empty_cache();torch.npu.reset_peak_memory_stats();torch.npu.synchronize();calls=[];start=time.monotonic()
                        ctx=candidate_chunks(model.model.backbone,plan['chunk_rows'],lambda a,b,l:calls.append([a,b,l])) if mode=='chunked' else contextlib.nullcontext()
                        with ctx:pred=model.predict(req,e)
                        torch.npu.synchronize();elapsed=time.monotonic()-start
                        d.response(next(iter(req['questions'].values())),pred['answer'])
                        check(all(math.isfinite(x) for x in pred['logits']),'nonfinite logits')
                        value=dict(plan_sha256=ch,request_sha256=d.stamp(req),name=name,mode=mode,rep=rep,prediction=pred,seconds=elapsed,questions_per_second_per_chip=1/elapsed,chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_allocated_gib=torch.npu.max_memory_allocated()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,calls=calls)
                        atomic(p,dict(payload=value,sha256=d.stamp(value)))
                    results[name][mode].append(value);count+=1;state.update(progress=count,questions_per_second_per_chip=value['questions_per_second_per_chip'],reserved_gib=value['reserved_gib'])
        comparisons={};admitted=True
        for name,modes in results.items():
            repeat=compare(*modes['chunked']);entry={'chunked_repeat':repeat};ok=repeat['probabilities']<=1e-5 and repeat['decision_same'] and repeat['tokens_same']
            if 'original' in modes:
                noise=compare(*modes['original']);cross=compare(modes['original'][0],modes['chunked'][0]);entry.update(original_repeat=noise,original_vs_chunked=cross)
                # No tolerance can conceal differences beyond the actually measured noise.
                exceeds=any(cross[k]>noise[k] for k in ['logits','probabilities','wire']);entry['exceeds_original_repeat_noise']=exceeds
                repeat_exceeds=any(repeat[k]>noise[k] for k in ['logits','probabilities','wire'])
                entry['chunked_repeat_exceeds_original_noise']=repeat_exceeds
                ok=ok and not exceeds and not repeat_exceeds and cross['decision_same'] and cross['tokens_same'] and noise['probabilities']<=1e-5 and (cross['wire_exact'] if noise['wire_exact'] else True)
            entry['engineering_admission']=ok;admitted=admitted and ok;comparisons[name]=entry
        d.verify_files(c)
        for p,h in plan['files'].items():check(sha(p)==h,'final frozen file changed')
        report=dict(plan_sha256=ch,source_config_sha256=sha(plan['source_config']),candidate_batch_admission=admitted,comparisons=comparisons,envelope=envelope,items={n:{m:[{k:v[k] for k in ['seconds','questions_per_second_per_chip','chips','reserved_gib','peak_allocated_gib','peak_reserved_gib']} for v in vs] for m,vs in modes.items()} for n,modes in results.items()},scope='Actual original/chunked forward comparison; no full-test score, gold optimization or Astra approval.')
        atomic(out/'report.json',report);state['stage']='completed';rc=0
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);state['stage']='failed';raise
    finally:
        stop.set();th.join();outputs={n:sha(out/n) for n in ['report.json','ENVELOPE.json'] if(out/n).exists()}
        atomic(out/'COMPLETE.json',dict(rc=rc,error=error,plan_sha256=ch,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),outputs=outputs,**state))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True,type=Path);main(p.parse_args().plan)
