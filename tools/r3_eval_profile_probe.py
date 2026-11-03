#!/usr/bin/env python3
"""DEV-only evaluation phase profiler.

This module is a measurement harness, not a scorer or a scientific evaluator. It
never opens TEST files; the formal builder parses labels only to replay the frozen
population filter, and removes them before writing inference rows. The runner and never changes the frozen scorer.  A panel is made
from an already frozen DEV/calibration JSONL population.  The runner calls the
scorer's encode/score_enc methods once per batch and records host phase boundaries;
missing device-level timings are reported as ``unavailable`` rather than inferred.
"""
import argparse, contextlib, hashlib, importlib, json, math, os, statistics, sys, time
from pathlib import Path

SCHEMA='r3-eval-profile-plan-v1'
PHASES=('encode_pack','h2d','forward_head','d2h_sync','commit')

def require(ok, why):
    if not ok: raise ValueError(why)

def safe(path):
    p=Path(path).absolute()
    require(not any(x.is_symlink() for x in (p,*p.parents)), 'symlink path')
    return p

def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def _jsonable(v):
    if isinstance(v,dict): return {str(k):_jsonable(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_jsonable(x) for x in v]
    if hasattr(v,'_asdict'): return _jsonable(v._asdict())
    if isinstance(v,(str,int,float,bool)) or v is None:return v
    raise TypeError("non-JSON operand")
def canon(v): return json.dumps(_jsonable(v),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(v): return hashlib.sha256(canon(v).encode()).hexdigest()

def no_gold(value):
    if isinstance(value,dict):
        require(not any(k in value for k in ('gold','gold_id','gold_index','gold_probs')), 'gold field forbidden')
        for v in value.values():no_gold(v)
    elif isinstance(value,list):
        for v in value:no_gold(v)

def read_jsonl(path, *, allow_gold=False):
    p=safe(path); require(p.is_file(),'population missing')
    low=str(p).lower(); require('/test/' not in low and not p.name.lower().startswith('test'), 'TEST population forbidden')
    rows=[]
    for no,line in enumerate(p.read_text().splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line)
        require(isinstance(row,dict),f'row {no} not object')
        if not allow_gold:
            no_gold(row)
        rows.append(row)
    return rows

def row_key(row, i):
    for k in ('key','id','qid','group_id'):
        if isinstance(row.get(k),(str,int)): return f'{k}:{row[k]}'
    return f'row:{i}'

def make_panel(rows, output, *, cell_key='cell', chunk=32, panel_id='profile-v1'):
    """Select the middle complete chunk per cell, preserving input order.

    Each input row must carry ``cell`` (a stable K/T execution-cell label).  The
    output is a gold-free JSONL plus a manifest with exact IDs and source hash.
    """
    require(type(chunk) is int and chunk>0,'chunk must be positive')
    require(rows,'empty population')
    groups={}
    for i,r in enumerate(rows):
        require(isinstance(r,dict) and cell_key in r,'cell missing')
        no_gold(r)
        c=r[cell_key]; require(isinstance(c,str) and c and 'test' not in c.lower(),'invalid/TEST cell')
        groups.setdefault(c,[]).append((i,r))
    selected=[];cells={}
    for c,items in groups.items():
        n=len(items); full=n//chunk
        if full:
            mid=(full-1)//2; chosen=items[mid*chunk:(mid+1)*chunk]
        else:
            chosen=items
        start=len(selected); selected.extend(r for _,r in chosen)
        cells[c]={'input_n':n,'complete_chunks':full,'selected_n':len(chosen),'selected_start':start,
                  'selected_ids':[row_key(r,i) for i,r in chosen]}
    out=safe(output);out.parent.mkdir(parents=True,exist_ok=True)
    data=out.with_suffix('.jsonl')
    with data.open('x') as f:
        for r in selected:f.write(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
    manifest={'schema':SCHEMA,'panel_id':panel_id,'cell_key':cell_key,'chunk':chunk,
              'rows':len(selected),'cells':cells,'population_path':str(data),
              'population_sha256':sha(data),'test_read':False,'scientific_acceptance':False,
              'candidate_selection_allowed':False,'gold_read':False}
    mpath=out.with_suffix('.manifest.json');mpath.write_text(json.dumps(manifest,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    return manifest

class PhaseTrace:
    def __init__(self): self.events=[]
    def mark(self,phase,kind='start',**extra):
        require(phase in PHASES,'unknown phase');self.events.append(dict(phase=phase,kind=kind,monotonic_ns=time.monotonic_ns(),**extra))
    def span(self,phase,fn,*args,**kwargs):
        self.mark(phase,'start');t=time.monotonic_ns()
        try:return fn(*args,**kwargs)
        finally:
            self.events.append(dict(phase=phase,kind='end',monotonic_ns=time.monotonic_ns(),elapsed_ns=time.monotonic_ns()-t))
    def report(self):
        vals={}
        for phase in PHASES:
            xs=[e['elapsed_ns']/1e9 for e in self.events if e.get('phase')==phase and e.get('kind')=='end']
            vals[phase]={'n':len(xs),'seconds':sum(xs),'p50':statistics.median(xs) if xs else None,
                         'p95':sorted(xs)[max(0,(len(xs)*95+99)//100-1)] if xs else None,
                         'status':'measured' if xs else 'unavailable'}
        return vals

def _stable(v): return canon(v)
def output_hash(v): return hashlib.sha256(_stable(v).encode()).hexdigest()
def compare_outputs(reference, actual):
    require(len(reference)==len(actual),'output row count differs')
    diffs=[]
    for i,(a,b) in enumerate(zip(reference,actual)):
        if _stable(a)!=_stable(b): diffs.append(i)
    require(not diffs,'raw/typed output differs at rows '+','.join(map(str,diffs[:8])))
    return {'rows':len(reference),'sha256':output_hash(reference),'equivalent':True}

def score_batch(scorer, rows, mode='rightpad', trace=None):
    """Call frozen scorer methods once; no new barrier is inserted between phases."""
    tr=trace or PhaseTrace()
    tr.mark('encode_pack','start'); t=time.monotonic_ns(); enc=scorer.encode(rows);tr.events.append(dict(phase='encode_pack',kind='end',monotonic_ns=time.monotonic_ns(),elapsed_ns=time.monotonic_ns()-t))
    tr.mark('forward_head','start'); t=time.monotonic_ns(); scores=scorer.score_enc(enc,mode=mode);tr.events.append(dict(phase='forward_head',kind='end',monotonic_ns=time.monotonic_ns(),elapsed_ns=time.monotonic_ns()-t))
    return scores,tr

def write_report(path, manifest, runs, *, profile_overhead='unavailable'):
    out={'schema':'r3-eval-profile-report-v1','manifest_sha256':digest(manifest),'runs':runs,
         'phase_timing':{'status':'diagnostic_host_bound','profile_overhead':profile_overhead},
         'test_read':False,'gold_read':False,'scientific_acceptance':False,
         'candidate_selection_allowed':False,'resources_released':False}
    p=safe(path);p.write_text(json.dumps(out,indent=2,sort_keys=True,ensure_ascii=False)+'\n');return out

PROMPT_FIELDS=('input','task_definition','question','levels','level_type','candidate_set','prefix_questions')

def pin(p): return {'path':str(safe(p)), 'sha256':sha(p)}
def pinned(ref):
    p=safe(ref['path']);require(sha(p)==ref['sha256'],'input/source changed: '+str(p));return p

def source_binding(plan, manifest):
    """Bind actual loader arguments and inventory to the reviewed DEV spec."""
    require(plan['source_spec']==manifest['source_spec'],'source spec binding differs')
    spec=json.loads(pinned(plan['source_spec']).read_text())
    require(spec['schema']=='r3-posttrain-dev-spec-v1' and spec['test_read'] is False
            and spec['scientific_acceptance'] is False,'source spec scope differs')
    argv=spec['command']
    def argument(flag):
        require(argv.count(flag)==1,'ambiguous source argument: '+flag)
        i=argv.index(flag);require(i+1<len(argv),'missing source argument: '+flag)
        return argv[i+1]
    for field,flag in [('model','--model-path'),('adapter','--adapter')]:
        expected=argument(flag)
        require(plan[field]==spec[field]==expected,'loader '+field+' differs from source spec')
        root=safe(expected);require(root.is_dir(),'loader directory missing')
        registered={p:h for p,h in spec['files'].items() if Path(p).is_relative_to(root)}
        actual={str(safe(p)) for p in root.rglob('*') if p.is_file()}
        require(bool(registered) and actual==set(registered),'loader '+field+' inventory differs')
        names={Path(p).name for p in registered}
        require(('config.json' if field=='model' else 'adapter_config.json') in names
                and any(n.endswith('.safetensors') for n in names),'loader weights/config absent')
    for p,h in spec['files'].items():
        require(plan['files'].get(p)==h and sha(p)==h,'source dependency binding differs')
    require(argument('--partitions')=='dev,calibration' and argument('--scorer')==plan['mode']
            and argument('--dtype')==plan['dtype'] and argument('--token-budget')==str(plan['token_budget'])
            and argument('--device')==plan['device'] and argv.count('--no-hf32')==1,
            'source numerical contract differs')
    return spec

def publish(p, v):
    p=safe(p); tmp=p.with_name(p.name+'.pending')
    with tmp.open('x') as f:f.write(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    os.link(tmp,p);tmp.unlink()
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def load_closure(files):
    sources={Path(p).name:(p,h) for p,h in files.items() if '/source-closure/' in p and p.endswith('.py')}
    require(len(sources)==27,'expected 27 frozen sources')
    for p,h in sources.values():require(sha(p)==h,'source changed')
    r0=str(Path(sources['prompt.py'][0]).parent);r3=str(Path(sources['core_r3.py'][0]).parent)
    sys.path[:0]=[r0,r3]
    # Import R0 first: legacy core inserts the historical r0 path into sys.path.
    # Preloading and then checking __file__ prevents that path selecting code.
    for name in ('common','decision','split','thresholds','metrics','prompt','scorer','core_r3','track_t_r3','scorer_r3'):
        m=importlib.import_module(name);require(str(safe(m.__file__))==sources[name+'.py'][0],'foreign imported module '+name)
    return tuple(sys.modules[n] for n in ('common','core_r3','track_t_r3','prompt','scorer_r3'))

def build_formal(spec_path, spec_sha, output):
    spec=json.loads(pinned({'path':spec_path,'sha256':spec_sha}).read_text());argv=spec['command']
    def arg(k):return argv[argv.index(k)+1]
    require(arg('--partitions')=='dev,calibration' and arg('--track-t-config')=='r3' and arg('--num-shards')=='1','full DEV population required')
    require(arg('--scorer')=='rightpad' and arg('--dtype')=='float32' and '--no-hf32' in argv and arg('--token-budget')=='16384','scorer differs')
    for p,h in spec['files'].items(): require(sha(p)==h,'spec dependency changed')
    RC,C,T,P,SM=load_closure(spec['files']);population=[];used={}
    def source(path):
        path=str(path);require(path in spec['files'],'unregistered population');used[path]=spec['files'][path];return path
    def strip(r,cell,key,mode):
        v={k:r[k] for k in PROMPT_FIELDS if k in r};v['input_mode']=mode
        # Same transform as make_score_fn, with labels removed after selection.
        if mode in ('blank','drop'):v['input']=''
        require(P.build_prompt(v).text==P.build_prompt(r,input_mode=mode).text,'gold removal changed prompt')
        return {'id':key,'cell':cell,'row':v,'group_id':r.get('group_id')}
    for label in arg('--k-only').split(','):
        suite,split,kind=label.split('/');require(split in ('dev','calibration'),'TEST forbidden')
        path=source(C.partition_path(suite,split,kind=='variants'));rows=[json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
        mode={'question_only':'drop','empty_input':'blank'}.get(kind,'full')
        population.extend(strip(r,'K/'+label,C.kev_key(r),mode) for r in rows)
    for role,mode in T.MODEL_ROLES.items():
        for task in ('T1','T2','T3'):
            for src in arg('--track-t-sources').split(','):
                path=RC.task_path(arg('--data-root'),task,src)
                if task=='T3' and not Path(path).exists():continue
                rows=T.records_needed(RC.load_records(source(path)),T.CONFIGS['r3'])
                population.extend(strip(r,'T/'+role+'/'+task+'/'+src,r['key'],mode) for r in rows)
    out=safe(output);require(not out.exists(),'output exists');out.mkdir(parents=True)
    m=make_panel(population,out/'panel');require(len(m['cells'])==32 and m['rows']==1024,'unexpected actual panel')
    m.update(source_populations=used,source_population_rows=len(population),source_spec=pin(spec_path),
             gold_read=True,labels_parsed_during_population_replay=True,labels_used_for_metrics=False,
             population_note='Frozen records_needed uses presence of gold_id for tau fitting; no label-based sample optimization; emitted inference rows omit all gold.')
    # Replace only our just-created builder manifest before it is admitted.
    (out/'panel.manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
    files=dict(spec['files']);files[str(Path(__file__).resolve())]=sha(__file__)
    plan=dict(schema=SCHEMA,panel=pin(out/'panel.jsonl'),manifest=pin(out/'panel.manifest.json'),source_spec=pin(spec_path),files=files,
              model=arg('--model-path'),adapter=arg('--adapter'),device='npu:0',dtype='float32',mode='rightpad',token_budget=16384,
              repeats=3,chip=6,out=str(out/'run'),scientific_acceptance=False,test_read=False,candidate_selection_allowed=False)
    publish(out/'plan.json',plan);return pin(out/'plan.json')

class Instrument:
    """Host timing wrappers only; nested stages overlap and must not be summed."""
    def __init__(self,sc):self.sc=sc;self.old={};self.events=[]
    def __enter__(self):
        for name in ('load','encode','_score_flat_batch','_token_logprobs','_sync'):
            old=getattr(self.sc,name);self.old[name]=old
            def wrapped(*a,_fn=old,_name=name,**kw):
                t=time.perf_counter()
                try:return _fn(*a,**kw)
                finally:self.events.append({'method':_name,'host_seconds':time.perf_counter()-t})
            setattr(self.sc,name,wrapped)
        return self
    def __exit__(self,*exc):
        for k,v in self.old.items():setattr(self.sc,k,v)

def execute_batches(sc,cells,out,repeats=3,profiler=None,metadata=None):
    """Fresh generation only. Every comparison operand persists before validation."""
    out=safe(out);out.mkdir(exist_ok=False,parents=True);publish(out/'STARTED.json',{'whole_pass_resume':False})
    trials=[];reference={};reference_enc={};passes=[]
    try:
        for name in ['cold_reference','split_gate','warmup']+[f'wall_{i}' for i in range(repeats)]+['trace']:
            td=out/name;td.mkdir();instrument=Instrument(sc) if name=='trace' else contextlib.nullcontext()
            prof=profiler(td) if name=='trace' and profiler else contextlib.nullcontext()
            sc._sync();begin=time.perf_counter();before=dict(sc.stats)
            with instrument as inst,prof:
                for cell,items in cells.items():
                    rows=[r['row'] for r in items];t=time.perf_counter()
                    captured=[];original_encode=sc.encode
                    def capture_encode(*a,**kw):
                        enc=original_encode(*a,**kw);captured.append(digest(enc));return enc
                    sc.encode=capture_encode
                    try:raw_scores=sc.score_raw(rows,mode='rightpad') if name!='split_gate' else sc.score_enc(sc.encode(rows),mode='rightpad')
                    finally:sc.encode=original_encode
                    require(len(captured)==1,'encode call count changed')
                    seconds=time.perf_counter()-t
                    require(len(raw_scores)==len(rows) and all(len(s)==len(r['levels']) and all(math.isfinite(float(v)) for v in s) for r,s in zip(rows,raw_scores)),'malformed scores')
                    result=[dict(id=r['id'],s=s,index=max(range(len(s)),key=lambda i:s[i]),tie=s.count(max(s))>1) for r,s in zip(items,raw_scores)]
                    p=td/(hashlib.sha256(cell.encode()).hexdigest()+'.json');ct=time.perf_counter();publish(p,{'cell':cell,'encoded_sha256':captured[0],'rows':result});commit=time.perf_counter()-ct
                    if name=='cold_reference':reference[cell]=result;reference_enc[cell]=captured[0]
                    else:
                        require(captured[0]==reference_enc[cell],'encoded tokens/order changed');compare_outputs(reference[cell],result)
                    trials.append(dict(pass_id=name,cell=cell,rows=len(rows),score_wall_seconds=seconds,durable_commit_seconds=commit,operand=pin(p)))
                    # One bounded heartbeat per completed original outer chunk.
                    print(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'pass':name,'completed_chunks':len(list(td.glob('*.json'))),'total_chunks':len(cells)}),flush=True)
            sc._sync();elapsed=time.perf_counter()-begin
            delta={k:sc.stats[k]-before.get(k,0) for k in sc.stats if k!='rightpad_s'}
            passes.append({'pass_id':name,'wall_seconds_including_commit':elapsed,'tokens_per_second_per_chip':delta.get('tokens',0)/elapsed,'chips':1,'counter_delta':delta})
            publish(td/'PASS.json',{'wall_seconds_including_commit':elapsed,'counter_delta':{k:sc.stats[k]-before.get(k,0) for k in sc.stats if k not in ('rightpad_s',)},'host_trace':inst.events if inst else [],'device_stage_costs':'unavailable without independent trace interpretation','nested_host_stages_not_additive':True})
        publish(out/'report.json',{'trials':trials,'all_raw_exact':True,'scientific_acceptance':False,'test_read':False,'score_wall_includes':'original score call plus identical encode operand capture/hash; not uninstrumented production throughput','runtime':metadata() if metadata else {'chips':0,'reserved_gib':None,'synthetic':True},'passes':passes,'profile_overhead_ratio':passes[-1]['wall_seconds_including_commit']/statistics.mean(x['wall_seconds_including_commit'] for x in passes if x['pass_id'].startswith('wall_')),'commit_scope':'diagnostic exclusive JSON/fsync only; original VerifiedStore cost unavailable','device_phase_seconds':'unavailable; do not infer from nested host spans'})
        publish(out/'EXIT.json',{'exit_code':0,'report':pin(out/'report.json'),'scientific_acceptance':False})
    except BaseException as e:
        publish(out/'EXIT.json',{'exit_code':1,'error':str(e)[:500],'interrupted_pass_comparable':False,'restart':'new generation; never splice timing passes'})
        raise

def verify(plan_path,expected):
    plan=json.loads(pinned({'path':plan_path,'sha256':expected}).read_text())
    require(plan['schema']==SCHEMA and plan['repeats']==3 and plan['chip']==6 and plan['mode']=='rightpad' and plan['dtype']=='float32' and plan['token_budget']==16384 and plan['test_read'] is False and plan['scientific_acceptance'] is False and plan['candidate_selection_allowed'] is False,'profile scope differs')
    manifest=json.loads(pinned(plan['manifest']).read_text())
    source_binding(plan,manifest)
    for p,h in plan['files'].items():require(sha(p)==h,'dependency changed')
    require(plan['files'].get(str(Path(__file__).resolve()))==sha(__file__),'runner not pinned')
    pinned(plan['panel']);require(manifest['population_path']==plan['panel']['path'] and manifest['population_sha256']==plan['panel']['sha256'],'manifest panel differs');rows=read_jsonl(plan['panel']['path']);cells={}
    for r in rows:cells.setdefault(r['cell'],[]).append(r)
    require(len(cells)==32 and len(rows)==1024 and set(cells)==set(manifest['cells']),'panel incomplete')
    for label,items in cells.items():
        require(len(items)==manifest['cells'][label]['selected_n'] and ['id:'+str(r['id']) for r in items]==manifest['cells'][label]['selected_ids'],'panel cell order differs')
    return plan,cells

def run(plan_path,expected):
    plan,cells=verify(plan_path,expected)
    RC,C,T,P,SM=load_closure(plan['files'])
    import torch,torch_npu
    torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
    require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 still on')
    sc=SM.R3Scorer(plan['model'],adapter=plan['adapter'],device='npu:0',dtype='float32',token_budget=16384)
    load_start=time.perf_counter();sc.load();sc._sync();load_seconds=time.perf_counter()-load_start
    def metadata():return {'chips':1,'reserved_gib':torch.npu.memory_reserved()/2**30,'peak_reserved_gib':torch.npu.max_memory_reserved()/2**30,'model_load_seconds':load_seconds}
    def profiler(td):
        return torch_npu.profiler.profile(activities=[torch_npu.profiler.ProfilerActivity.CPU,torch_npu.profiler.ProfilerActivity.NPU],on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(str(td/'trace')))
    execute_batches(sc,cells,plan['out'],plan['repeats'],profiler,metadata)

def main(argv=None):
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='op',required=True)
    b=sub.add_parser('panel');b.add_argument('--input',required=True);b.add_argument('--output',required=True);b.add_argument('--chunk',type=int,default=32)
    b=sub.add_parser('build-formal');b.add_argument('--spec',required=True);b.add_argument('--sha256',required=True);b.add_argument('--output',required=True)
    for op in ('run','verify'):
        b=sub.add_parser(op);b.add_argument('--plan',required=True);b.add_argument('--sha256',required=True)
    a=ap.parse_args(argv)
    if a.op=='panel':print(json.dumps(make_panel(read_jsonl(a.input),a.output,chunk=a.chunk)))
    elif a.op=='build-formal':print(json.dumps(build_formal(a.spec,a.sha256,a.output)))
    elif a.op=='run':run(a.plan,a.sha256)
    elif a.op=='verify':
        plan,cells=verify(a.plan,a.sha256);print(json.dumps({'status':'PROFILE_SOURCE_INPUT_VERIFIED','cells':len(cells),'deployment_authorized':False}))
    return 0
if __name__=='__main__':raise SystemExit(main())
