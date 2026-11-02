"""Pinned DEV-only BEV length-bucket equivalence/performance probe."""
import argparse
from collections import Counter
import contextlib
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import types

SCORING = dict(chunk=8, dtype='float32', head_fp32=False, hf32=False,
               max_sequence_tokens=4096, mode='rightpad', token_budget=16384)
PROTOCOL = dict(per_stratum=8, strata=['short', 'middle', 'long'], repetitions=3,
                warmup_passes=1, raw_score_tolerance=0.0, baseline_repeat_tolerance=0.0,
                input_mode='full', selection='type_length_tertiles_even_rank_v1',
                compared_dimension='outer_question_length_order', timing_unit='complete72_sweep',
                save_all_gate_operands=True)
BASELINE_SHA = '3fb4765a6533c05cb612c594524eec6ff75531d0d953fd8e57353f45af485e25'
SCORER_SHA = 'f1de708a28b47cdb513eb79c7306510df8312f6a92f96a75adcfe59ba0cf6a49'
CANDIDATE_SHA = '3fb4765a6533c05cb612c594524eec6ff75531d0d953fd8e57353f45af485e25'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
ENV = dict(ASCEND_RT_VISIBLE_DEVICES='0', HF_HUB_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
           TASK_QUEUE_ENABLE='2', TOKENIZERS_PARALLELISM='false', TRANSFORMERS_OFFLINE='1')


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p


def atomic(path, value, exclusive=False):
    path = Path(path); temp = path.with_name(path.name + '.pending-' + str(os.getpid()) + '-' + str(threading.get_ident()))
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with temp.open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    try:
        if exclusive: os.link(temp, path); temp.unlink()
        else: os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if temp.exists(): temp.unlink()


def fresh_measurement(out, attempt):
    require(type(attempt) is int and attempt == 1, 'only fresh attempt1 is supported; retries need separate review')
    out = safe(out)
    for name in ('trials', 'attempts', 'report.json', 'COMPLETE.json', 'FAILURE.json'):
        require(not os.path.lexists(out/name), 'existing measurement artifact refused: '+name)


def reserve_measurement(out, pin, attempt):
    """Host owns this fresh measurement generation before claiming a chip."""
    fresh_measurement(out, attempt)
    owner = Path(out)/'MEASUREMENT_OWNER.json'
    atomic(owner, dict(schema='bev-batch-dev-measurement-owner-v1', plan_sha256=pin,
                      attempt=1, owner_pid=os.getpid()), exclusive=True)
    # A competing artifact created while ownership was published still blocks claim.
    fresh_measurement(out, attempt)


def begin_measurement(out, pin, attempt):
    """Call under the runner lock; never import pre-existing measurements."""
    fresh_measurement(out, attempt)
    owner = safe(Path(out)/'MEASUREMENT_OWNER.json')
    value = json.loads(owner.read_text())
    require(value.get('schema') == 'bev-batch-dev-measurement-owner-v1' and
            value.get('plan_sha256') == pin and value.get('attempt') == 1, 'measurement owner differs')
    # Exclusive mkdir closes the check/create race. Per-trial exclusive writes
    # also reject artifacts injected later, without ever reading their timings.
    directory = Path(out)/'trials'; directory.mkdir(exist_ok=False)
    return directory


def module(entry, name):
    p = safe(entry['path']); require(sha(p) == entry['sha256'], 'code pin differs')
    m = types.ModuleType(name); m.__file__ = str(p)
    exec(compile(p.read_bytes(), str(p), 'exec', dont_inherit=True), m.__dict__)
    return m


def select_sample(rows, bridge):
    require(len({r['id'] for r in rows}) == len(rows), 'source IDs duplicate')
    for r in rows:
        require(set(r) == {'id', 'request'}, 'gold-free envelope required')
        bridge.to_r3_row(r['request'])
    def length(r):
        q = r['request']; return len(q['input']) + len(q['question']) + sum(map(len, q['definitions']))
    selected, strata = [], []
    for kind in ('choice', 'noul', 'score'):
        ordered = sorted((r for r in rows if r['request']['type'] == kind), key=lambda r: (length(r), r['id']))
        require(len(ordered) >= 24, 'stratum too small')
        for s, label in enumerate(PROTOCOL['strata']):
            pool = ordered[len(ordered)*s//3:len(ordered)*(s+1)//3]
            chosen = [pool[i*(len(pool)-1)//7] for i in range(8)]
            selected.extend(chosen)
            strata.append(dict(type=kind, length_stratum=label, ids=[r['id'] for r in chosen],
                               input_character_lengths=[length(r) for r in chosen]))
    return selected, strata


def verify(plan_path, pin):
    p = safe(plan_path); require(sha(p) == pin, 'plan changed'); d = json.loads(p.read_text())
    require(d['schema'] == 'bev-batch-efficiency-probe-v1' and d['scope'] == 'train_derived_dev'
            and d['test_read'] is False and d['scientific_acceptance'] is False, 'scope differs')
    require(d['attempts'] == [1] and d['resume_allowed'] is False, 'attempt policy differs')
    require(d['scoring'] == SCORING and d['protocol'] == PROTOCOL, 'protocol differs')
    require(d['chip'] == 7 and d['chips'] == 1 and d['device'] == 'npu:0' and d['image_sha256'] == IMAGE, 'device/image differs')
    require(d['environment'] == ENV, 'environment differs')
    require(Path(d['model']).name == 'Qwen__Qwen3.5-0.8B-Base', 'model differs')
    require(set(d['code']) == {'runner','host','resource','candidate','scorer','prompt','bridge'}, 'code inventory differs')
    require(set(d['inputs']) == {'requests','sample','batches','preregistration'}, 'input inventory differs')
    require(d['code']['runner']['path'] == str(Path(__file__).resolve()), 'wrong runner')
    require(d['code']['scorer']['sha256'] == SCORER_SHA, 'scorer differs')
    require(d['code']['candidate']['sha256'] == CANDIDATE_SHA, 'candidate differs from reviewed source')
    for group in ('code','inputs','model_files'):
        for v in d[group].values(): require(sha(safe(v['path'])) == v['sha256'], 'dependency changed: '+v['path'])
    root = p.parent
    require(safe(d['out']) == root/'output', 'output placement differs')
    for group, sub in (('code','code'),('inputs','inputs')):
        require(all(safe(v['path']).parent == root/sub for v in d[group].values()), 'package placement differs')
    require(d['mounts'] == [dict(source=str(root),destination=str(root),readonly=True),
            dict(source=d['out'],destination=d['out'],readonly=False),
            dict(source=d['model'],destination=d['model'],readonly=True)], 'mounts differ')
    require({x.name for x in safe(d['model']).iterdir() if x.is_file()} == set(d['model_files']), 'model inventory differs')
    require(all(Path(v['path']).parent == Path(d['model']) and Path(v['path']).name == n for n,v in d['model_files'].items()), 'model paths differ')
    bridge = module(d['code']['bridge'], 'probe_bridge')
    rows = [json.loads(x) for x in Path(d['inputs']['requests']['path']).read_text().splitlines()]
    require(len(rows) == 72 and len({r['id'] for r in rows}) == 72, 'sample count differs')
    for r in rows:
        require(set(r) == {'id','request'}, 'gold-free sample required'); bridge.to_r3_row(r['request'])
    sample = json.loads(Path(d['inputs']['sample']['path']).read_text())
    require(sample['ordered_ids'] == [r['id'] for r in rows] and sample['selection'] == PROTOCOL['selection']
            and sample['source_requests_sha256'] == '200142967c3db8a6704bacf41d987b127398c31fb9acb90b8f8524cf1aa7ea0a'
            and sample['scope'] == 'train_derived_dev', 'sample binding differs')
    require([r['id'] for s in sample['strata'] for r in rows if r['id'] in s['ids']] == sample['ordered_ids'], 'strata order differs')
    require([(s['type'],s['length_stratum'],len(s['ids'])) for s in sample['strata']] ==
            [(k,s,8) for k in ('choice','noul','score') for s in PROTOCOL['strata']], 'strata population differs')
    batches = json.loads(Path(d['inputs']['batches']['path']).read_text())
    validate_orders(batches, sample['ordered_ids'])
    return d


def load_components(plan):
    prompt = module(plan['code']['prompt'], 'probe_prompt')
    previous = sys.modules.get('prompt'); paths = list(sys.path); sys.modules['prompt'] = prompt
    try: scorer = module(plan['code']['scorer'], 'probe_scorer')
    finally:
        sys.path[:] = paths
        if previous is None: sys.modules.pop('prompt', None)
        else: sys.modules['prompt'] = previous
    return prompt, scorer, module(plan['code']['bridge'], 'probe_bridge'), module(plan['code']['candidate'], 'probe_candidate')


def layout(enc, scorer_module, budget):
    reduced, maps, nq, nr = scorer_module.dedup_enc(enc)
    flat = [(i,j,e.prefix+c,len(c)) for i,e in enumerate(reduced) for j,c in enumerate(e.cands)]
    order = sorted(range(len(flat)), key=lambda i: -len(flat[i][2])); pos = 0; batches = []
    while pos < len(order):
        width = len(flat[order[pos]][2]); size = max(1,budget//width)
        part = [flat[i] for i in order[pos:pos+size]]; pos += size
        batches.append(dict(width=width, rows=[dict(question=i,candidate=j,tokens=t,
            mask=[1]*len(t)+[0]*(width-len(t)),candidate_tokens=n) for i,j,t,n in part]))
    return dict(enc=[dict(prefix=e.prefix,cands=e.cands) for e in enc], maps=maps,
                duplicate_questions=nq, removed=nr, batches=batches)


class ProbeScorer:
    def __init__(self, scorer, scorer_module, host_only=False, capture=False):
        self.scorer, self.module, self.host_only, self.capture = scorer, scorer_module, host_only, capture
        self.tok = scorer.tok; self.layouts = []
    def encode(self, rows): return self.scorer.encode(rows)
    def score_raw(self, rows, mode): return self.score_enc(self.encode(rows), mode=mode)
    def score_enc(self, enc, mode):
        if self.capture: self.layouts.append(layout(enc, self.module, self.scorer.token_budget))
        if self.host_only: return [[0.] * len(e.cands) for e in enc]
        return self.scorer.score_enc(enc, mode=mode)


def validate_orders(orders, ids):
    require(set(orders)=={'baseline','bucketed'}, 'variant set differs')
    require(len(ids)==72 and len(set(ids))==72,'population differs')
    for name,batches in orders.items():
        flat=[x for b in batches for x in b]
        require(len(batches)==9 and all(len(b)==8 for b in batches),'batch shape differs')
        require(len(flat)==72 and len(set(flat))==72 and set(flat)==set(ids),'missing/duplicate/foreign ID')
    require([x for b in orders['baseline'] for x in b]==ids,'baseline order differs')


def trial_specs():
    return [dict(key=f'r{rep}-{variant}',repetition=rep,variant=variant)
            for rep in range(3) for variant in (('baseline','bucketed') if rep%2==0 else ('bucketed','baseline'))]


def canonical_outputs(outputs,ids):
    require(len(outputs)==len(ids),'output population differs')
    require(all(set(x)=={'id','raw','prediction'} for x in outputs),'output schema differs')
    by={x['id']:x for x in outputs};require(len(by)==len(ids) and set(by)==set(ids),'missing/duplicate/foreign output ID')
    for x in outputs:
        require(type(x['raw']) is list and len(x['raw'])>=2 and all(type(v) in (int,float) and math.isfinite(v) for v in x['raw']),'nonfinite/malformed raw')
        require(x['prediction'].get('id')==x['id'] and x['prediction'].get('status')=='ok','prediction identity/status differs')
    return [by[i] for i in ids]


def compare(reference,actual,ids,tokens=True):
    require(digest(canonical_outputs(reference['outputs'],ids))==digest(canonical_outputs(actual['outputs'],ids)), 'raw score or typed output differs')
    if tokens:
        require(reference['tokens']==actual['tokens'],'per-ID token mapping differs')


def sweep(rows,orders,variant,scorer,sm,prompt,bridge,candidate,plan,capture):
    ids=[r['id'] for r in rows];by={r['id']:r for r in rows};outputs=[];tokens={};layouts=[]
    for batch_ids in orders[variant]:
        batch=[by[i] for i in batch_ids];proxy=ProbeScorer(scorer,sm,capture=capture)
        result=candidate.score_batch(batch,proxy,prompt,bridge,plan)
        require([r['id'] for r,_,_ in result]==batch_ids,'batch results reordered or missing')
        require(all(p['status']=='ok' for _,_,p in result),'sample unsupported')
        outputs.extend(dict(id=r['id'],raw=raw,prediction=p) for r,raw,p in result)
        if capture:
            require(len(proxy.layouts)==1 and len(proxy.layouts[0]['enc'])==8,'captured encoding differs')
            for identifier,e in zip(batch_ids,proxy.layouts[0]['enc']):
                require(identifier not in tokens,'duplicate captured ID');tokens[identifier]=e
            layouts.append(dict(ids=batch_ids,layout=proxy.layouts[0]))
    return dict(outputs=canonical_outputs(outputs,ids),tokens=tokens,layouts=layouts,variant=variant)


def summarize(trials,ids,pin):
    specs=trial_specs();require(len(trials)==6,'six complete measured sweeps required')
    by={t['key']:t for t in trials};require(len(by)==6 and set(by)=={s['key'] for s in specs},'trial keys differ')
    first=trials[0]
    for t in trials:
        require(t['output_sha256']==first['output_sha256'], 'cross-repetition outputs differ')
    for s in specs:
        t=by[s['key']];require(all(t.get(k)==v for k,v in s.items()),'trial binding differs')
        require(type(t.get('attempt')) is int and t['attempt']==1 and t['plan_sha256']==pin,'foreign trial generation')
        require(t['status']=='PASS' and t['exit_code']==0 and t['chips']==1,'failed trial')
        require(all(type(t[k]) in (int,float) and math.isfinite(t[k]) and t[k]>0 for k in ('score_seconds','reserved_gib')),'invalid timing/memory')
        actual=canonical_outputs(t['outputs'],ids);require(digest(actual)==t['output_sha256'],'output hash differs')
        require(all(type(t['counts'][k]) is int and t['counts'][k]>=0 for k in ('tokens','padded_tokens','forwards','head_positions','items')),'counts invalid')
        require(t['counts']['tokens']>t['counts']['padded_tokens'] and t['counts']['items']==72 and t['counts']['forwards']>0 and t['counts']['head_positions']>0,'workload differs')
        mate=by[f"r{s['repetition']}-{'bucketed' if s['variant']=='baseline' else 'baseline'}"]
        require(t['output_sha256']==mate['output_sha256'],'paired outputs differ')
        for k in ('head_positions','items'):require(t['counts'][k]==mate['counts'][k],'paired useful workload differs')
        require(t['counts']['tokens']-t['counts']['padded_tokens']==mate['counts']['tokens']-mate['counts']['padded_tokens'],'paired useful tokens differ')
    totals={}
    for v in ('baseline','bucketed'):
        selected=[t for t in trials if t['variant']==v];seconds=sum(t['score_seconds'] for t in selected)
        counts={k:sum(t['counts'][k] for t in selected) for k in selected[0]['counts']}
        totals[v]=dict(sweeps=3,score_seconds=seconds,counts=counts,chips=1,forwarded_tokens_per_second_per_chip=counts['tokens']/seconds,useful_tokens_per_second_per_chip=(counts['tokens']-counts['padded_tokens'])/seconds)
    reps=[dict(repetition=r,baseline_seconds=by[f'r{r}-baseline']['score_seconds'],bucketed_seconds=by[f'r{r}-bucketed']['score_seconds'],ratio=by[f'r{r}-baseline']['score_seconds']/by[f'r{r}-bucketed']['score_seconds']) for r in range(3)]
    return dict(measurements=totals,per_repetition=reps,whole_sweep_time_ratio=totals['baseline']['score_seconds']/totals['bucketed']['score_seconds'],process_peak_reserved_gib=max(t['reserved_gib'] for t in trials),memory_note='Same-process cumulative high-water mark; not independent variant memory comparison',scientific_acceptance=False,test_read=False,scope='fixed72 TRAIN-derived DEV diagnostic; not full population qualification',timing_note='Synchronized whole72-row score sweep includes same encode-once runner in both arms; excludes persistence. No significance/production speedup claim.')


def run(plan_path,pin,attempt):
    started=time.perf_counter();require(type(attempt) is int and attempt==1,'only fresh attempt1 supported')
    plan=verify(plan_path,pin);out=Path(plan['out']);out.mkdir(exist_ok=True)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);directory=begin_measurement(out,pin,attempt)
        adir=out/'attempts/1';adir.mkdir(parents=True,exist_ok=False)
        state=dict(status='loading',completed=0,total=6,attempt=1,scientific_acceptance=False,test_read=False);stop=threading.Event();rc=1
        def beat():
            v=dict(state,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-started);atomic(adir/'heartbeat.json',v);print(json.dumps(v),flush=True)
        def loop():
            while not stop.wait(30):beat()
        beat();thread=threading.Thread(target=loop,daemon=True);thread.start()
        try:
            import torch
            import torch_npu
            torch.npu.set_device('npu:0');torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
            prompt,sm,bridge,candidate=load_components(plan)
            scorer=sm.R3Scorer(plan['model'],device='npu:0',dtype='float32',token_budget=16384,head_fp32=False,render='record_name').load()
            rows=[json.loads(x) for x in Path(plan['inputs']['requests']['path']).read_text().splitlines()];ids=[r['id'] for r in rows]
            orders=json.loads(Path(plan['inputs']['batches']['path']).read_text());validate_orders(orders,ids)
            state['status']='equivalence';operands={}
            for name,variant in (('baseline','baseline'),('repeat','baseline'),('bucketed','bucketed')):
                value=sweep(rows,orders,variant,scorer,sm,prompt,bridge,candidate,plan,True)
                value.update(plan_sha256=pin,attempt=1,operand=name)
                atomic(adir/(name+'-operand.json'),value,exclusive=True);operands[name]=value;state['operand']=name;beat()
            lengths={k:len(v['prefix'])+max(map(len,v['cands'])) for k,v in operands['baseline']['tokens'].items()}
            require([x for b in orders['bucketed'] for x in b]==sorted(ids,key=lambda x:(lengths[x],x)),'bucket order not token-length order')
            compare(operands['baseline'],operands['repeat'],ids);compare(operands['baseline'],operands['bucketed'],ids)
            gate=dict(status='PASS',plan_sha256=pin,attempt=1,baseline_repeat_exact=True,bucketed_exact=True,operands={k:{'path':str(adir/(k+'-operand.json')),'sha256':sha(adir/(k+'-operand.json'))} for k in operands})
            atomic(adir/'GATES.json',gate,exclusive=True)
            state['status']='warmup'
            for variant in ('baseline','bucketed'):
                value=sweep(rows,orders,variant,scorer,sm,prompt,bridge,candidate,plan,False);compare(operands['baseline'],value,ids,False)
            state['status']='measuring';require(not any(directory.iterdir()),'existing trial artifact refused');trials=[]
            for spec in trial_specs():
                path=directory/(spec['key']+'.json');require(not os.path.lexists(path),'existing trial artifact refused')
                torch.npu.synchronize();before=dict(scorer.stats);t=time.perf_counter()
                value=sweep(rows,orders,spec['variant'],scorer,sm,prompt,bridge,candidate,plan,False);torch.npu.synchronize();seconds=time.perf_counter()-t
                counts={k:scorer.stats[k]-before.get(k,0) for k in ('tokens','padded_tokens','forwards','head_positions','items')}
                record=dict(spec,status='PENDING_GATE',exit_code=1,attempt=1,plan_sha256=pin,outputs=value['outputs'],output_sha256=digest(value['outputs']),score_seconds=seconds,counts=counts,reserved_gib=torch.npu.max_memory_reserved()/2**30,chips=1)
                # Persist measured operand before checking equality; failed outputs remain independently inspectable.
                atomic(adir/(spec['key']+'-operand.json'),record,exclusive=True)
                compare(operands['baseline'],value,ids,False);record.update(status='PASS',exit_code=0)
                atomic(path,record,exclusive=True);trials.append(record);state.update(completed=len(trials),forwarded_tokens_per_second_per_chip=counts['tokens']/seconds,reserved_gib=record['reserved_gib']);beat()
            result=summarize(trials,ids,pin);verify(plan_path,pin)
            result.update(plan_sha256=pin,attempt=1,run_seconds=time.perf_counter()-started,baseline_repeat_exact=True,bucketed_exact=True,gate_sha256=sha(adir/'GATES.json'),exit_code=0)
            atomic(out/'report.json',result,exclusive=True);atomic(out/'COMPLETE.json',result,exclusive=True);rc=0;state['status']='complete'
        except BaseException as error:
            state.update(status='failed',error_type=type(error).__name__,error=str(error)[:800]);atomic(out/'FAILURE.json',dict(state,plan_sha256=pin,exit_code=1),exclusive=True);raise
        finally:
            stop.set();thread.join(timeout=2);beat();atomic(adir/'EXIT.json',dict(exit_code=rc,attempt=1,plan_sha256=pin,scientific_acceptance=False,test_read=False),exclusive=True)
    return rc


def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','run']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('BEV_BATCH_DEV_VERIFIED');return 0
    d=json.loads(Path(a.plan).read_text());out=safe(d['out']);(out/'logs').mkdir(parents=True,exist_ok=True)
    with (out/'logs'/f'attempt-{a.attempt}.log').open('a',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):return run(a.plan,a.sha256,a.attempt)


if __name__=='__main__':raise SystemExit(main())
