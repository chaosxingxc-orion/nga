#!/usr/bin/env python3
"""Bounded fp32 prefix-reuse engineering probe; no model-quality verdict."""
import argparse
from collections import defaultdict
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import threading
import time
import traceback


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(p):
    return json.loads(Path(p).read_text())


def save(p, value):
    p = Path(p); tmp = p.with_suffix('.pending')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')
    tmp.replace(p)


def select(rows, count=6):
    """Round-robin exact candidate-count strata; original order within each stratum."""
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        require(len(row['levels']) >= 2, 'at least two candidates required')
        groups[len(row['levels'])].append(index)
    sizes=sorted(groups)
    if len(sizes)>count:
        sizes=[sizes[i*(len(sizes)-1)//(count-1)] for i in range(count)]
    chosen = []; depth = 0
    while len(chosen) < count:
        before = len(chosen)
        for size in sizes:
            if depth < len(groups[size]):
                chosen.append(groups[size][depth])
                if len(chosen) == count:
                    break
        require(len(chosen) > before, 'insufficient development records')
        depth += 1
    return chosen


def validate_scores(scores, enc):
    require(len(scores) == len(enc) and bool(enc), 'incomplete score population')
    for values, row in zip(scores, enc):
        require(len(values) == len(row.cands), 'incomplete candidate population')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in values), 'nonfinite score')
        seen = {}
        for tokens, value in zip(row.cands, values):
            key = tuple(tokens)
            require(key not in seen or seen[key] == value, 'duplicate candidates diverged')
            seen[key] = value
    return len(scores)


def compare(reference, candidate, threshold=1e-3):
    require(len(reference) == len(candidate) and reference, 'population differs')
    maximum = 0.; disagreements = []; near = []
    for i, (a, b) in enumerate(zip(reference, candidate)):
        require(len(a) == len(b) and len(a) >= 2, 'candidate count differs')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in a+b), 'nonfinite score')
        maximum = max(maximum, max(abs(x-y) for x,y in zip(a,b)))
        top = sorted(a, reverse=True); gap = top[0]-top[1]
        if gap <= threshold:
            near.append({'row':i,'reference_gap':gap})
        elif a.index(max(a)) != b.index(max(b)) or b.count(max(b)) != 1:
            disagreements.append(i)
    return {'pass':maximum <= threshold and not disagreements, 'max_abs_nats':maximum,
            'far_gap_argmax_disagreements':disagreements, 'near_ties':near, 'threshold_nats':threshold}


def prepare(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    rows = []; sources = {}; selected = []
    for suite in ('decision-v7','transfer-v4'):
        path = Path(a.kev)/suite/'dev.jsonl'
        source = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        sources[str(path)] = sha(path)
        for index in select(source):
            row = source[index]; rows.append(row)
            selected.append({'suite':suite,'index':index,'group_id':row['group_id'],
                             'question':row['question'],'candidate_count':len(row['levels'])})
    save(out/'sample.json', rows)
    files = dict(sources)
    for root in (Path(a.model), Path(a.adapter), Path(a.r3_code), Path(a.r0_code)):
        require(root.is_absolute() and root.is_dir(), 'absolute existing input directory required')
        for p in root.rglob('*'):
            require(not p.is_symlink(), 'symlink input')
            if p.is_file(): files[str(p)] = sha(p)
    files[str(out/'sample.json')] = sha(out/'sample.json')
    files[str(Path(__file__).resolve())] = sha(__file__)
    plan = {'schema':'r3-prefix-probe-v1','model':a.model,'adapter':a.adapter,'r3_code':a.r3_code,
            'r0_code':a.r0_code,'out':str(out),'sample':str(out/'sample.json'),'selection':selected,
            'files':files,'threshold_nats':1e-3,'roles':['full','blank','drop'],
            'orders':['original','reversed'],'passes':['first','warm'],'token_budget':16384,
            'dtype':'float32','hf32':False,'scientific_acceptance':False,'test_read':False}
    save(out/'plan.json', plan)
    (out/'PLAN_SHA256').write_text(sha(out/'plan.json')+'\n')
    print(json.dumps({'plan':str(out/'plan.json'),'sha256':sha(out/'plan.json'),'records':len(rows)}))


def run(a):
    require(sha(a.plan) == a.sha256, 'plan pin differs')
    p = load(a.plan); out = Path(p['out'])
    require(p['schema'] == 'r3-prefix-probe-v1' and p['test_read'] is False and p['scientific_acceptance'] is False, 'scope differs')
    require(p['threshold_nats'] == 1e-3 and p['token_budget'] == 16384 and p['dtype']=='float32' and p['hf32'] is False, 'protocol differs')
    require(p['roles']==['full','blank','drop'] and p['orders']==['original','reversed'] and p['passes']==['first','warm'], 'case schedule differs')
    for path, digest in p['files'].items(): require(sha(path)==digest, 'input changed: '+path)
    require(p['files'].get(str(Path(__file__).resolve()))==sha(__file__), 'probe executable not pinned')
    sys.dont_write_bytecode = True
    sys.path[:0] = [p['r3_code'],p['r0_code']]
    S = importlib.import_module('scorer_r3'); P = importlib.import_module('prompt')
    require(Path(S.__file__).parent==Path(p['r3_code']) and Path(P.__file__).parent==Path(p['r0_code']), 'module escaped closure')
    import torch
    import torch_npu  # noqa: F401
    torch.npu.matmul.allow_hf32 = False; torch.npu.conv.allow_hf32 = False
    require(not torch.npu.matmul.allow_hf32 and not torch.npu.conv.allow_hf32, 'HF32 remains enabled')
    scorer = S.R3Scorer(p['model'], adapter=p['adapter'], device='npu:0',dtype='float32',token_budget=16384)
    rows=load(p['sample']); require(len(rows)==12, 'twelve frozen rows required')
    scorer.load(); cases={}; start=time.time()
    for role in p['roles']:
        transform={'full':lambda r:r,'blank':P.blank_input,'drop':P.drop_input}[role]
        for order in p['orders']:
            batch=[transform(r) for r in (rows if order=='original' else rows[::-1])]
            enc=scorer.encode(batch)
            for mode in ('rightpad','fast'):
                for phase in p['passes']:
                    name=f'{role}-{order}-{mode}-{phase}'; target=out/(name+'.json');receipt=out/(name+'.complete.json')
                    if receipt.exists():
                        r=load(receipt);require(r['plan_sha256']==a.sha256 and r['sha256']==sha(target), 'case receipt differs')
                        record=load(target)
                        validate_scores(record['scores'], enc)
                        cases[name]=record;continue
                    intent=out/(name+'.intent.json');require(not intent.exists(), 'interrupted case requires explicit new generation')
                    save(intent,{'plan_sha256':a.sha256,'utc_seconds':time.time()})
                    stop=threading.Event()
                    def heartbeat():
                        while True:
                            save(out/'heartbeat.json',{'utc_seconds':time.time(),'case':name,'completed':len(cases),'total':24})
                            if stop.wait(15):return
                    watcher=threading.Thread(target=heartbeat,daemon=True);watcher.start()
                    try:
                        torch.npu.synchronize(); t=time.perf_counter();scores=scorer.score_enc(enc,mode);torch.npu.synchronize();elapsed=time.perf_counter()-t
                    finally:
                        stop.set();watcher.join()
                    samples = validate_scores(scores, enc)
                    record={'scores':scores,'seconds':elapsed,'reserved_gib':torch.npu.memory_reserved()/2**30,
                            'peak_reserved_gib':torch.npu.max_memory_reserved()/2**30,'chips':1,'mode':mode,'phase':phase,
                            'samples':samples,'questions_per_second_per_chip':samples/elapsed,'invocation_started_utc_seconds':start,
                            'peak_memory_scope':'process cumulative; not reset per case'}
                    save(target,record);save(receipt,{'plan_sha256':a.sha256,'sha256':sha(target)});cases[name]=record
    judgments={}
    for role in p['roles']:
        reference=cases[f'{role}-original-rightpad-first']['scores']
        for order in p['orders']:
            for mode in ('rightpad','fast'):
                for phase in p['passes']:
                    name=f'{role}-{order}-{mode}-{phase}';values=cases[name]['scores']
                    judgments[name]=compare(reference,values if order=='original' else values[::-1])
        corrupt=[[v+0.01*(i+1) for i,v in enumerate(row)] for row in reference]
        require(not compare(reference,corrupt)['pass'], 'corruption control not rejected')
    for path, digest in p['files'].items(): require(sha(path)==digest, 'input changed during probe: '+path)
    ok=all(x['pass'] for x in judgments.values())
    save(out/'digest.json',{'status':'PASS' if ok else 'FAIL','judgments':judgments,
         'timings':{k:{x:v[x] for x in ('seconds','reserved_gib','peak_reserved_gib','chips','questions_per_second_per_chip')} for k,v in cases.items()},
         'wall_seconds':time.time()-start,'model_loaded_once_per_invocation':True,'corruption_control_rejected':True,
         'peak_memory_scope':'process cumulative; not reset per case',
         'scientific_acceptance':False,'test_read':False,'plan_sha256':a.sha256,
         'limits':['12 fixed development records; not full scorer admissibility','rightpad comparator, not independent exact scorer',
                   'first means first call of that case; model is already loaded','restarted cases may mix process timing environments; receipts expose provenance']})
    return 0 if ok else 2


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='op',required=True)
    p=sub.add_parser('prepare')
    for key in ('out','kev','model','adapter','r3-code','r0-code'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('run');p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True)
    a=ap.parse_args()
    if a.op=='prepare':prepare(a);return
    code=1
    try:code=run(a)
    except Exception:traceback.print_exc()
    finally:save(Path(load(a.plan)['out'])/'EXIT.json',{'exit_code':code,'utc_seconds':time.time(),'scientific_acceptance':False})
    sys.exit(code)


if __name__=='__main__':main()
