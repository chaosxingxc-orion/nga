#!/usr/bin/env python3
"""Prospective current-K0 identity control. No candidate TEST or scientific admission."""
import argparse, hashlib, importlib, json, math, os, sys, threading, time
from pathlib import Path
SUITES=('decision-v7','transfer-v4','T1/typed-decisions','T1/openjev-synth','T1/akhilaaa3')
MODELS=('base','instruct')
MODES=('exact','rp_c32','rp_c32s5','rp_c32s16')
TAU=0.001

def require(ok, why):
    if not ok: raise ValueError(why)
def read(p): return json.loads(Path(p).read_bytes())
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def digest(v): return hashlib.sha256(canonical(v).encode()).hexdigest()
def put(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending')
    with t.open('x') as f:json.dump(v,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def pin(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def bound(ref):
    p=Path(ref['path']);require(p.is_absolute() and not p.is_symlink() and sha(p)==ref['sha256'],'input changed: '+str(p));return read(p)
def scores(v,arity):
    require(isinstance(v,list) and len(v)==arity and arity>=2,'score candidate arity differs')
    require(all(type(x) in (int,float) and math.isfinite(x) for x in v),'nonfinite/non-numeric score')
    return v

def strict_compare(old,new):
    require(isinstance(old,list) and isinstance(new,list) and len(old)==len(new) and old,'question count differs')
    for a,b in zip(old,new):scores(a,len(a));scores(b,len(a))
    # Same registered bar and tie rules, with shape/finite checks before zip.
    gap=[sorted(s,reverse=True)[0]-sorted(s,reverse=True)[1] for s in old]
    listed=[i for i,g in enumerate(gap) if g<=TAU];eligible=[i for i,g in enumerate(gap) if g>TAU]
    def kev(s):return s.index(max(s))
    def r0(s):return None if s.count(max(s))>1 else kev(s)
    dk=[i for i in eligible if kev(old[i])!=kev(new[i])];dr=[i for i in eligible if r0(old[i])!=r0(new[i])]
    delta=max(abs(a-b) for x,y in zip(old,new) for a,b in zip(x,y))
    return dict(n=len(old),max_abs=delta,n_evaluated=len(eligible),n_listed_at_or_below_tau=len(listed),listed_idx=listed,dis_kev=len(dk),dis_r0=len(dr),dis_idx=sorted(set(dk)|set(dr)),bit_identical=sum(a==b for a,b in zip(old,new)),pass_bar=delta<=TAU and not dk and not dr)

def rows_jsonl(path,key):
    out={}
    with Path(path).open() as f:
        for line in f:
            require(line.endswith('\n'),'torn input line')
            if not line.strip():continue
            r=json.loads(line);k=key(r);require(type(k)is str and k not in out,'duplicate/invalid row key');out[k]=r
    require(out,'empty input');return out

def current_raw(raw,source,model_sha):
    receipt=read(str(raw)+'.receipt.json');require(receipt['path']==str(raw) and receipt['sha256']==sha(raw) and receipt['committed_bytes']==Path(raw).stat().st_size,'raw receipt differs')
    require(receipt['model_sha256']==model_sha and receipt['scorer']['record_grade'] is True,'raw identity/grade differs')
    rawrows=rows_jsonl(raw,lambda r:r['k']);require(type(receipt['rows'])is int and receipt['rows']==len(rawrows),'raw count differs')
    require(set(rawrows) <= set(source),'raw row outside actual DEV/task manifest')
    for k,r in rawrows.items():
        ids=[x['id'] for x in source[k]['levels']]
        require(r['ids']==ids and len(set(ids))==len(ids),'candidate ids/order differ')
        scores(r['s'],len(ids));require(r['m']==model_sha[:16],'raw model prefix differs')
    return rawrows

def validate_cell(c):
    require(len(c['keys'])==len(c['rows'])==len(c['stored'])==64 and len(set(c['keys']))==64,'sample shape/duplicate differs')
    for row,s in zip(c['rows'],c['stored']):
        ids=[v['id'] for v in row['levels']];require(len(set(ids))==len(ids),'duplicate candidate id');scores(s,len(ids))

def verify(path,pin_value):
    require(sha(path)==pin_value,'plan changed');d=read(path)
    require(d['schema']=='r3-k0-current-identity-v1' and d['scientific_acceptance'] is False and d['test_read'] is False,'scope differs')
    require(d['seed']==20261030 and d['n_per_cell']==64 and d['call']==32 and d['tau']==TAU and d['modes']==list(MODES),'registered constants differ')
    require(d['chip'] in (0,6,7) and type(d['chip'])is int and d['poll_seconds']==600,'chip/poll differs')
    require(d['files'][str(Path(__file__).resolve())]==sha(__file__),'foreign runtime')
    for f,h in d['files'].items():require(sha(f)==h,'pinned file changed: '+f)
    sample=bound(d['sample']);body=dict(sample);want=body.pop('sample_sha1')
    require(hashlib.sha1(json.dumps(body,sort_keys=True).encode()).hexdigest()==want,'sample sha1 differs')
    require(Path(d['sample_sha1_file']).read_text().strip()==want,'sample sidecar differs')
    cells=sample['cells'];require([(c['checkpoint'],c['suite']) for c in cells]==[(m,s) for m in MODELS for s in SUITES],'cell matrix/order differs')
    for c in cells:
        validate_cell(c)
        raw=rows_jsonl(c['raw']['path'],lambda r:r['k']);require(sha(c['raw']['path'])==c['raw']['sha256'],'sample raw changed')
        require(all(k in raw for k in c['keys']) and c['stored']==[raw[k]['s'] for k in c['keys']],'sample scores not bound to current raw')
        for k,row in zip(c['keys'],c['rows']):require(raw[k]['ids']==[x['id'] for x in row['levels']],'sample candidate order differs')
    for suite in SUITES:
        expected=[c for c in cells if c['suite']==suite]
        require(expected[0]['source']==expected[1]['source'],'model samples use different source generation')
    require(len(d['controls'])==10 and [(x['suite'],x['tag']) for x in d['controls']]==[(s,t) for s,t in [('decision-v7','adapter'),('decision-v7','base'),('transfer-v4','adapter'),('transfer-v4','base'),('T1/typed-decisions','adapter'),('T1/openjev-synth','adapter'),('T1/akhilaaa3','adapter'),('T1/typed-decisions','r0model'),('T1/openjev-synth','r0model'),('T1/akhilaaa3','r0model')]],'c32 matrix differs')
    for x in d['controls']:
        z=bound(x['data']);side=bound(x['historical_sample'])
        require(z['keys']==[m['key'] for m in side['meta']] and len(z['rows'])==side['n'],'historical control sample differs')
    for m in MODELS:
        target=d['targets'][m];ri=bound(target['identity']);require(ri['model_path']==target['model']['path'] and ri['model_sha256']==target['model']['sha256'] and ri['arm']=='K0','target identity differs')
        for ref in target['terminals']:
            require(type(bound(ref)['exit_code'])is int and bound(ref)['exit_code']==0,'target incomplete')
        bound(target['execution']);bound(target['report'])
    hist=bound(d['historical_identity']);require(hist['report_compared'] is True and hist['readout_of_record'] is False and hist['verdict']=='IDENTICAL','historical scope differs')
    return d,sample

def load_code(d):
    sys.path.insert(0,d['code_dir']);sys.path.insert(1,d['r0_dir'])
    for n in ('scorer_r3','eval_r3','sample_r3','chunk_groups','testlock_r3'):
        m=importlib.import_module(n);require(str(Path(m.__file__).resolve()) in d['files'] and sha(m.__file__)==d['files'][str(Path(m.__file__).resolve())],'unbound imported module '+n)
    return importlib.import_module('scorer_r3'),importlib.import_module('eval_r3')

def score_batches(out,context,rows,fn,groups):
    started=time.monotonic();computed=0
    out=Path(out);out.mkdir(parents=True,exist_ok=True);seen=[];parts=[]
    require(sorted(i for g in groups for i in g)==list(range(len(rows))),'batch coverage differs')
    for n,g in enumerate(groups):
        p=out/(str(n)+'.json');ident={'context':context,'indices':g,'rows_sha256':digest([rows[i] for i in g])}
        if p.exists():
            z=read(p);require(z['identity']==ident,'resume generation/rows differ');v=z['scores']
        else:
            v=fn([rows[i] for i in g]);computed+=len(g);require(len(v)==len(g),'scorer dropped question')
            for i,s in zip(g,v):scores(s,len(rows[i]['levels']))
            put(p,{'identity':ident,'scores':v})
        require(isinstance(v,list) and len(v)==len(g),'resume count differs')
        for i,s in zip(g,v):scores(s,len(rows[i]['levels']));seen.append((i,s))
        parts.append(pin(p));perf={'questions_per_second_per_chip':computed/max(time.monotonic()-started,1e-9),'reserved_gib':None}
        if 'torch' in sys.modules and hasattr(sys.modules['torch'],'npu'):
            perf['reserved_gib']=sys.modules['torch'].npu.memory_reserved()/2**30
        print(json.dumps({'utc_seconds':time.time(),'phase':context['phase'],'completed_questions':len(seen),'computed_questions':computed,'total':len(rows),'chips':1,**perf}),flush=True)
    return [s for i,s in sorted(seen)],parts

def run(path,pin_value,attempt):
    require(type(attempt)is int and attempt in (1,2),'attempt differs');d,sample=verify(path,pin_value);out=Path(d['out']);a=out/'attempts'/str(attempt);a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(60):put(a/'heartbeat.json',{'utc_seconds':time.time(),'state':'control_scoring','chips':1})
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        S,E=load_code(d);import torch;import torch_npu
        torch.npu.matmul.allow_hf32=False;torch.npu.conv.allow_hf32=False
        TL=importlib.import_module('testlock_r3');identity={}
        for m in MODELS:
            cache=a/('fresh_identity_'+m);require(not cache.exists(),'identity cache unexpectedly exists')
            identity[m]=TL.model_identity(d['targets'][m]['model']['path'],None,str(cache))
            require(identity[m]['sha256']==d['targets'][m]['model']['sha256'],'actual disk model identity differs')
        results=[];CG=importlib.import_module('chunk_groups');SM=importlib.import_module('sample_r3')
        # Current exact and each registered composition use the same original fixed rows.
        for c in d['controls']:
            z=bound(c['data']);side=bound(c['historical_sample']);rows=z['rows'];sc=S.R3Scorer(c['model'],adapter=c['adapter'],dtype='float32',device='npu:0',token_budget=16384).load();enc=sc.encode(rows)
            info=[{'prefix':len(e.prefix),'cand_lens':[len(v) for v in e.cands],'cand_hash':[SM.cand_hash(v) for v in e.cands]} for e in enc]
            require(SM.sample_sha1(side['meta'],info)==side['sample_sha1'],'current encoded control differs from original fixed sample')
            mode_scores={};part_pins={}
            for mode in MODES:
                groups=CG.call_groups(len(rows),8 if mode=='exact' else 32,0 if mode in ('exact','rp_c32') else int(mode.removeprefix('rp_c32s')))
                context={'plan_sha256':pin_value,'phase':'c32','cell':c['id'],'mode':mode,'data_sha256':c['data']['sha256']}
                fn=lambda rs,mode=mode:sc.score_raw(rs,'exact' if mode=='exact' else 'rightpad')
                v,pp=score_batches(out/'resumable'/'c32'/c['id']/mode,context,rows,fn,groups);mode_scores[mode]=v;part_pins[mode]=pp
            checks={m:strict_compare(mode_scores['exact'],mode_scores[m]) for m in MODES[1:]}
            historical=bound(c['historical_exact']);require(historical['keys']==z['keys'] and historical['sample_sha1']==side['sample_sha1'],'historical exact identity differs')
            checks['fresh_exact_vs_historical_exact']=strict_compare(historical['scores'],mode_scores['exact'])
            results.append({'id':c['id'],'checks':checks,'parts':part_pins});put(a/'C32-PROGRESS.json',results)
            require(all(v['pass_bar'] for v in checks.values()),'c32/exact control failed: '+c['id'])
            del sc,enc;import gc;gc.collect();torch.npu.empty_cache()
        rescores=[]
        for weights in MODELS:
            args=argparse.Namespace(model_path=d['targets'][weights]['model']['path'],adapter=None,device='npu:0',scorer='rightpad',token_budget=16384,dtype='float32',no_hf32=True,require_record_grade=True)
            fn=E.make_score_fn(args);require(fn.describe()['record_grade'] is True,'not record grade')
            for c in sample['cells']:
                context={'plan_sha256':pin_value,'phase':'rescore','checkpoint':c['checkpoint'],'suite':c['suite'],'weights':weights,'sample_sha1':sample['sample_sha1']}
                v,pp=score_batches(out/'resumable'/'rescore'/weights/c['checkpoint']/c['suite'].replace('/','__'),context,c['rows'],lambda rs:fn(rs,'full'),CG.call_groups(64,32))
                cmp=strict_compare(c['stored'],v);rescores.append(dict(context,comparison=cmp,parts=pp,describe=fn.describe()));put(a/'RESCORE-PROGRESS.json',rescores)
            del fn;gc.collect();torch.npu.empty_cache()
        own=[x for x in rescores if x['checkpoint']==x['weights']];cross=[x for x in rescores if x['checkpoint']!=x['weights']]
        failures=[(x['checkpoint'],x['suite']) for x in own if not x['comparison']['pass_bar']];cross_pass=[(x['checkpoint'],x['suite']) for x in cross if x['comparison']['pass_bar']]
        verdict='VOID' if cross_pass else 'K0_RERUN_IN_FULL' if len(failures)>1 else 'CELL_VOID_RESCORE' if failures else 'VERIFIED'
        report={'schema':'r3-k0-current-control-report-v1','plan_sha256':pin_value,'attempt':attempt,'identity':identity,'c32':results,'rescores':rescores,'verdict':verdict,'own_failures':failures,'cross_passes':cross_pass,'sample_sha1':sample['sample_sha1'],'scientific_acceptance':False,'test_read':False,'report_reconstruction_and_independent_adjudication_pending':True}
        put(a/'report.json',report);require(verdict=='VERIFIED','current identity control failed: '+verdict);rc=0
    finally:
        stop.set();t.join(2);put(a/'EXIT.json',{'exit_code':rc,'plan_sha256':pin_value,'attempt':attempt,'utc_seconds':time.time(),'scientific_acceptance':False,'scope':'NPU controls only; final COMPLETE requires CPU report reconstruction and independent adjudication'})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','run']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('CURRENT_K0_PLAN_VERIFIED')
    else:run(a.plan,a.sha256,a.attempt)
if __name__=='__main__':main()
