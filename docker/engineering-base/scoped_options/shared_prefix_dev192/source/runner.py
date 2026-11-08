"""DEV-only paired diagnostic draft. No device selection or launch side effects on import."""
import argparse, hashlib, json, math, os, sys, time, traceback, threading
from pathlib import Path
import prompt
from compare import compare
from scorer_r3 import R3Scorer, dedup_enc
from diagnostic import score_encoded

def digest(x):
    return hashlib.sha256(json.dumps(x,separators=(',', ':'),ensure_ascii=False).encode()).hexdigest()
def put(path, obj):
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(obj,f,allow_nan=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
def read_rows(data, metadata):
    rows=[]
    with open(data) as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
            if len(rows)==96: break
    if len(rows)!=96 or digest(rows)!=metadata['source_sample_sha256']: raise ValueError('DEV sample identity mismatch')
    return rows

def prepare(rows, metadata, tok):
    expected={(x['row'],x['mode']):x for x in metadata['metadata']}
    if len(expected)!=192 or set(expected)!={(i,m) for i in range(33,97) for m in ('clean','question_only','empty_input')}: raise ValueError('manifest conditions')
    result=[]
    from scorer_r3 import encode_rows
    for mode,transform in [('clean',lambda x:x),('question_only',prompt.drop_input),('empty_input',prompt.blank_input)]:
        for index in range(33,97):
            raw=rows[index-1]; r=transform(raw); p=prompt.build_prompt(r); e=encode_rows(tok,[r])[0]; meta=expected[index,mode]
            key=digest([raw.get('group_id'),raw.get('qname'),raw.get('variant')])
            ids=[x['id'] for x in r['levels']]
            checks=(key==meta['key_sha256'], hashlib.sha256(p.text.encode()).hexdigest()==meta['prompt_sha256'],len(e.prefix)==meta['prompt_tokens'],len(ids)==meta['candidate_count'],len(dedup_enc([e])[0][0].cands)==meta['distinct_candidates'], sum(map(len,e.cands))==meta['candidate_tokens_sum'],min(map(len,e.cands))==meta['candidate_tokens_min'],max(map(len,e.cands))==meta['candidate_tokens_max'])
            if not all(checks): raise ValueError(f'metadata mismatch {index} {mode} {checks}')
            identity={'key':f'{mode}:{index}:{key}','candidate_ids':ids,'token_ids':e.cands,'gold':ids.index(r['gold'])}
            result.append((identity,e))
    return result

def hf32(device):
    if device=='cpu': return {'device':'cpu','matmul':None,'conv':None}
    import torch_npu, torch
    torch.npu.matmul.allow_hf32=False
    torch.npu.conv.allow_hf32=False
    x={'device':device,'matmul':torch.npu.matmul.allow_hf32,'conv':torch.npu.conv.allow_hf32}
    if x['matmul'] is not False or x['conv'] is not False: raise RuntimeError('HF32 readback failed')
    return x

class Progress:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = dict(rep='loading', path='none', completed=0, total=192, lastprogress=time.time())
    def update(self, **kw):
        with self.lock:
            self.state.update(kw, lastprogress=time.time())
    def snapshot(self):
        with self.lock: return dict(self.state)

def memory_stats(torch):
    result = {'current_allocated_bytes': int(torch.npu.memory_allocated()),
              'peak_allocated_bytes': int(torch.npu.max_memory_allocated()),
              'current_reserved_bytes': int(torch.npu.memory_reserved()),
              'peak_reserved_bytes': int(torch.npu.max_memory_reserved())}
    if any(not math.isfinite(v) or v < 0 for v in result.values()): raise ValueError('invalid device memory measurement')
    return result

def main(a, fixture=None, progress=None):
    import torch
    progress = progress or Progress()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    cfg=vars(a).copy(); cfg['manifest_sha256']=hashlib.sha256(Path(a.manifest).read_bytes()).hexdigest()
    cfg_hash=digest(cfg); binding=out/'binding.json'
    resume_existing=binding.exists()
    if binding.exists():
        if json.loads(binding.read_text())['sha256']!=cfg_hash: raise ValueError('resume binding changed')
    else: put(binding,{'sha256':cfg_hash,'config':cfg})
    (out/'EXIT.json').unlink(missing_ok=True)
    manifest=json.loads(Path(a.manifest).read_text())
    if a.data != manifest['dataset'] or a.model != manifest['model'] or a.adapter != manifest['adapter']: raise ValueError('model, adapter or DEV path mismatch')
    progress.update(rep='preparing', path='metadata', completed=0, total=96)
    rows = None if fixture else read_rows(a.data, manifest)
    progress.update(rep='loading', path='model', completed=0, total=192)
    flags=hf32(a.device)
    s=(fixture.scorer() if fixture else R3Scorer(a.model,adapter=a.adapter,device=a.device,dtype='float32',token_budget=16384)).load()
    if a.device.startswith('npu'):
        free,total=torch.npu.mem_get_info()
        if a.budget_bytes>free: raise MemoryError('configured post-model budget exceeds free device memory')
        put(out/'memory-at-load.json',{'free_bytes':free,'total_bytes':total,'reserved_bytes':torch.npu.memory_reserved(),'budget_bytes':a.budget_bytes})
    schedule=[('warmup', 'rightpad'),('warmup','shared_prefix')]+[(str(i),p) for i,ps in enumerate((('rightpad','shared_prefix'),('shared_prefix','rightpad'),('rightpad','shared_prefix')),1) for p in ps]
    # Completed chunks are reused for numerical progress; resumed timing is invalid.
    previous=None
    for rep,path in schedule:
        progress.update(rep=rep, path=path, completed=0, total=192)
        dest=out/f'{rep}-{path}.json'
        if dest.exists():
            previous=rep
            continue
        if previous != rep and rep != 'warmup':
            # An interrupted/relaunched series is retained for numerical checks, never speed claims.
            pass
        previous=rep
        records=[]; secs=0.; positions=0; wall=time.perf_counter(); resumed=False; commit_seconds=0.; max_parent_state_bytes=0; cache_check_seconds=0.; cache_checks=0
        progress.update(rep=rep, path=path, completed=0, total=192)
        encoding_start=time.perf_counter()
        items=fixture.prepare() if fixture else prepare(rows,manifest,s.tok)
        encoding_seconds=time.perf_counter()-encoding_start
        progress.update(completed=0,total=len(items))
        if a.device.startswith('npu'): torch.npu.reset_peak_memory_stats()
        for offset in range(0,len(items),32):
            subset=items[offset:offset+32]; enc=[e for _,e in subset]
            itemfile=out/f'{rep}-{path}-{offset:03d}.json'
            if itemfile.exists():
                item=json.loads(itemfile.read_text())
                if item['binding']!=cfg_hash or [dict((k,r[k]) for k in ('key','candidate_ids','token_ids','gold')) for r in item['records']]!=[x for x,_ in subset]: raise ValueError('resume item identity mismatch')
                records.extend(item['records']); secs+=item['seconds']; positions+=item['positions']; resumed=True
                max_parent_state_bytes=max(max_parent_state_bytes,item.get('max_parent_state_bytes',0))
                progress.update(completed=len(records))
                continue
            s.stats.clear(); s._sync(); start=time.perf_counter()
            scores=s.score_enc(enc,mode='rightpad') if path=='rightpad' else score_encoded(s,enc,budget_bytes=a.budget_bytes,allowance_bytes=a.allowance_bytes,per_row_extra=a.per_row_extra,max_rows=a.max_rows)
            if fixture: scores=fixture.adjust_scores(rep,path,scores)
            s._sync(); elapsed=time.perf_counter()-start; check_elapsed=s.stats.get('cache_check_seconds',0.); cache_check_seconds+=check_elapsed; cache_checks+=s.stats.get('cache_checks',0); secs+=elapsed; positions+=s.stats['tokens']; max_parent_state_bytes=max(max_parent_state_bytes,s.stats.get('max_parent_state_bytes',0))
            if len(scores)!=len(subset): raise ValueError("scorer row count mismatch")
            chunk=[dict(identity,scores=score) for (identity,_),score in zip(subset,scores)]
            compare(chunk,chunk)
            commit_start=time.perf_counter()
            put(itemfile,{'binding':cfg_hash,'records':chunk,'seconds':elapsed,'positions':s.stats['tokens'],'max_parent_state_bytes':s.stats.get('max_parent_state_bytes',0)})
            records.extend(chunk)
            commit_seconds+=time.perf_counter()-commit_start
            progress.update(rep=rep,path=path,completed=len(records),total=len(items))
            if fixture: fixture.after_chunk(rep,path,offset)
        memory=memory_stats(torch) if a.device.startswith('npu') else None
        put(dest,{'binding':cfg_hash,'records':records,'seconds':secs,'wall_seconds':time.perf_counter()-wall,'cache_check_seconds':cache_check_seconds,'cache_checks':cache_checks,'encoding_seconds':encoding_seconds,'commit_seconds':commit_seconds,'questions_per_s_per_chip':len(items)/secs,'chips':1,'forwarded_positions':positions,'memory':memory,'max_parent_state_bytes':max_parent_state_bytes,'hf32':flags,'resumed':resumed})
    reports=[]
    for rep in ('1','2','3'):
        x=json.loads((out/f'{rep}-rightpad.json').read_text()); y=json.loads((out/f'{rep}-shared_prefix.json').read_text())
        result=compare(x['records'],y['records']); reports.append({'pass':rep,'comparison':result,'rightpad_seconds':x['wall_seconds'],'shared_seconds':y['wall_seconds'],'rightpad_score_seconds':x['seconds'],'shared_score_seconds':y['seconds']})
    timing_valid=not resume_existing and not any(json.loads((out/f'{rep}-{path}.json').read_text())['resumed'] for rep,path in schedule)
    put(out/'report.json',{'comparisons':reports,'numerical_pass':all(x['comparison']['pass'] for x in reports),'lower_all_pairs':all(x['shared_seconds']<x['rightpad_seconds'] for x in reports) if timing_valid else None, 'timing_valid':timing_valid,'status':'accepted' if all(x['comparison']['pass'] for x in reports) else 'rejected','resume_note':'completed passes and chunks reused; timing across resumed process is not a controlled paired series'})
    return all(x['comparison']['pass'] for x in reports)

def cli():
    p=argparse.ArgumentParser()
    for k in ('data','model','adapter','manifest','output','device'): p.add_argument('--'+k,required=True)
    for k in ('budget-bytes','allowance-bytes','per-row-extra','max-rows'): p.add_argument('--'+k,type=int,required=True)
    a=p.parse_args()
    if min(a.budget_bytes,a.allowance_bytes,a.per_row_extra,a.max_rows)<=0: p.error('memory values must be positive')
    code=1
    progress=Progress()
    fixture=None
    # Explicit, CPU-only seam for process integration tests; normal CLI has no injected imports.
    fixture_name=os.environ.get('NGA_RUNNER_TEST_FIXTURE')
    stop=threading.Event()
    def heartbeat():
        while not stop.wait(10):
            print(json.dumps(dict(heartbeat_utc=time.time(), **progress.snapshot())),flush=True)
    thread=threading.Thread(target=heartbeat,daemon=True); thread.start()
    try:
        out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
        put(out/'report.json',{'status':'rejected','numerical_pass':False,'numerical_status':'incomplete','timing_valid':False,'lower_all_pairs':None,'reason':'attempt in progress'})
        (out/'EXIT.json').unlink(missing_ok=True)
        if fixture_name:
            if a.device != 'cpu': raise ValueError('test fixture requires CPU')
            import importlib
            fixture=importlib.import_module(fixture_name)
        code=0 if main(a, fixture, progress) else 2
    except Exception as exc:
        traceback.print_exc()
        out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
        put(out/'report.json',{'status':'rejected','numerical_pass':False,'numerical_status':'incomplete','timing_valid':False,'lower_all_pairs':None,'reason':'execution exception','error_category':type(exc).__name__[:128]})
    finally:
        stop.set(); thread.join()
        out=Path(a.output); out.mkdir(parents=True,exist_ok=True); put(out/'EXIT.json',{'exit_code':code,'utc':time.time()})
    return code
if __name__=='__main__': sys.exit(cli())
