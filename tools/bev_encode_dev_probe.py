"""Pinned DEV-only BEV encode-once equivalence/performance probe."""
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
                input_mode='full', selection='type_length_tertiles_even_rank_v1')
BASELINE_SHA = 'ef089be6a044e983f1032af3216158ca95c1a6d885a8fddd13f891758fe8af79'
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
    atomic(owner, dict(schema='bev-encode-dev-measurement-owner-v1', plan_sha256=pin,
                      attempt=1, owner_pid=os.getpid()), exclusive=True)
    # A competing artifact created while ownership was published still blocks claim.
    fresh_measurement(out, attempt)


def begin_measurement(out, pin, attempt):
    """Call under the runner lock; never import pre-existing measurements."""
    fresh_measurement(out, attempt)
    owner = safe(Path(out)/'MEASUREMENT_OWNER.json')
    value = json.loads(owner.read_text())
    require(value.get('schema') == 'bev-encode-dev-measurement-owner-v1' and
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
    require(d['schema'] == 'bev-encode-dev-probe-v2' and d['scope'] == 'train_derived_dev'
            and d['test_read'] is False and d['scientific_acceptance'] is False, 'scope differs')
    require(d['attempts'] == [1] and d['resume_allowed'] is False, 'attempt policy differs')
    require(d['scoring'] == SCORING and d['protocol'] == PROTOCOL, 'protocol differs')
    require(d['chip'] == 7 and d['chips'] == 1 and d['device'] == 'npu:0' and d['image_sha256'] == IMAGE, 'device/image differs')
    require(d['environment'] == ENV, 'environment differs')
    require(Path(d['model']).name == 'Qwen__Qwen3.5-0.8B-Base', 'model differs')
    require(set(d['code']) == {'runner','host','resource','baseline','candidate','scorer','prompt','bridge'}, 'code inventory differs')
    require(set(d['inputs']) == {'requests','sample','preregistration'}, 'input inventory differs')
    require(d['code']['runner']['path'] == str(Path(__file__).resolve()), 'wrong runner')
    require(d['code']['baseline']['sha256'] == BASELINE_SHA and d['code']['scorer']['sha256'] == SCORER_SHA, 'baseline/scorer differs')
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
    return d


def load_components(plan):
    prompt = module(plan['code']['prompt'], 'probe_prompt')
    previous = sys.modules.get('prompt'); paths = list(sys.path); sys.modules['prompt'] = prompt
    try: scorer = module(plan['code']['scorer'], 'probe_scorer')
    finally:
        sys.path[:] = paths
        if previous is None: sys.modules.pop('prompt', None)
        else: sys.modules['prompt'] = previous
    return prompt, scorer, module(plan['code']['bridge'], 'probe_bridge'), {
        v: module(plan['code'][v], 'probe_'+v) for v in ('baseline','candidate')}


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


def trial_specs():
    result = []
    for repetition in range(3):
        variants = ['baseline','candidate'] if repetition % 2 == 0 else ['candidate','baseline']
        for batch in range(9):
            for variant in variants:
                result.append(dict(key=f'r{repetition}-b{batch}-{variant}',repetition=repetition,batch=batch,variant=variant))
    return result


def compare(reference, actual):
    require(reference['ids'] == actual['ids'], 'pair IDs/order differ')
    require(reference['layout'] == actual['layout'], 'token/layout differ')
    require(digest(reference['outputs']) == digest(actual['outputs']), 'raw score or typed output differs')


def summarize(trials):
    specs = trial_specs(); require(len(trials) == len(specs), 'missing/extra trial')
    by = {t['key']:t for t in trials}; require(len(by)==len(trials) and set(by)=={s['key'] for s in specs}, 'trial keys differ')
    for spec in specs:
        t = by[spec['key']]; require(all(t.get(k)==v for k,v in spec.items()), 'trial binding differs')
        require(type(t.get('attempt')) is int and t['attempt'] == 1, 'foreign trial attempt refused')
        require(t.get('status')=='PASS' and t.get('exit_code')==0, 'failed trial')
        require(all(type(t[k]) in (int,float) and math.isfinite(t[k]) and t[k]>0
                    for k in ('score_seconds','host_only_seconds','reserved_gib')), 'invalid measurement')
        mate = by[f"r{spec['repetition']}-b{spec['batch']}-{'candidate' if spec['variant']=='baseline' else 'baseline'}"]
        require(t['ids']==mate['ids'] and t['output_sha256']==mate['output_sha256'], 'pair mismatch')
        require(t['counts']==mate['counts'], 'paired workload differs')
    totals = {}
    for variant in ('baseline','candidate'):
        selected = [t for t in trials if t['variant']==variant]
        seconds = sum(t['score_seconds'] for t in selected)
        tokens = sum(t['counts']['tokens'] for t in selected)
        totals[variant] = dict(trials=len(selected),score_seconds=seconds,host_only_seconds=sum(t['host_only_seconds'] for t in selected),
            forwarded_tokens=tokens,forwarded_tokens_per_second_per_chip=tokens/seconds,chips=1)
    per_repetition = []
    for repetition in range(3):
        seconds={v:sum(t['score_seconds'] for t in trials if t['variant']==v and t['repetition']==repetition) for v in ('baseline','candidate')}
        per_repetition.append(dict(repetition=repetition,score_seconds=seconds,ratio=seconds['baseline']/seconds['candidate']))
    return dict(measurements=totals,per_repetition=per_repetition,whole_score_time_ratio=totals['baseline']['score_seconds']/totals['candidate']['score_seconds'],
        host_only_time_ratio=totals['baseline']['host_only_seconds']/totals['candidate']['host_only_seconds'],
        process_peak_reserved_gib=max(t['reserved_gib'] for t in trials),
        memory_note='Cumulative same-process high-water mark across both variants; not an independent per-variant memory comparison.',
        scientific_acceptance=False,test_read=False,scope='72 fixed TRAIN-derived DEV inputs; three repetitions; encoding-only engineering diagnostic',
        timing_note='Whole-score covers score_batch and final synchronization, excludes persistence. Separate host-only path replaces score_enc with zeros; includes rendering, tokenization, eligibility and decode, not pure tokenizer time. No device speedup assertion.')


def run(plan_path, pin, attempt):
    started=time.perf_counter()
    require(type(attempt) is int and attempt == 1, 'only fresh attempt1 is supported; retries need separate review')
    plan=verify(plan_path,pin);out=Path(plan['out']);out.mkdir(exist_ok=True)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=begin_measurement(out,pin,attempt)
        adir=out/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False)
        state=dict(status='loading',completed=0,total=54,attempt=attempt,scientific_acceptance=False,test_read=False);stop=threading.Event()
        def beat():
            value=dict(state,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-started)
            atomic(adir/'heartbeat.json',value);print(json.dumps(value),flush=True)
        def loop():
            while not stop.wait(30):beat()
        beat();thread=threading.Thread(target=loop,daemon=True);thread.start();rc=1
        try:
            import torch
            import torch_npu
            torch.npu.set_device('npu:0');torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
            prompt,sm,bridge,variants=load_components(plan)
            scorer=sm.R3Scorer(plan['model'],device='npu:0',dtype='float32',token_budget=16384,head_fp32=False,render='record_name').load()
            rows=[json.loads(x) for x in Path(plan['inputs']['requests']['path']).read_text().splitlines()]
            batches=[rows[i:i+8] for i in range(0,len(rows),8)]
            def call(variant,batch,capture=False,host_only=False):
                proxy=ProbeScorer(scorer,sm,host_only,capture)
                result=variants[variant].score_batch(batch,proxy,prompt,bridge,plan)
                require(all(p['status']=='ok' for _,_,p in result),'sample unsupported')
                return dict(ids=[r['id'] for r,_,_ in result],outputs=[dict(id=r['id'],raw=s,prediction=p) for r,s,p in result],layout=proxy.layouts)
            state['status']='equivalence';references=[]
            # All reference and measured results are produced in this one fresh attempt.
            for index,batch in enumerate(batches):
                reference=call('baseline',batch,True);repeat=call('baseline',batch,True);compare(reference,repeat)
                candidate=call('candidate',batch,True);compare(reference,candidate);references.append(reference)
                atomic(adir/f'equivalence-{index}.json',dict(status='PASS',baseline_repeat_exact=True,candidate_exact=True,reference=reference))
                state['gate_batches']=index+1;beat()
            state['status']='warmup'
            for batch in batches:
                for variant in ('baseline','candidate'):call(variant,batch)
            state['status']='measuring'
            require(not any(directory.iterdir()),'existing trial artifact refused')
            trials=[]
            for spec in trial_specs():
                path=directory/(spec['key']+'.json')
                require(not os.path.lexists(path),'existing trial artifact refused')
                batch=batches[spec['batch']];torch.npu.synchronize();before=dict(scorer.stats);t=time.perf_counter()
                actual=call(spec['variant'],batch);torch.npu.synchronize();seconds=time.perf_counter()-t
                require(digest(actual['outputs'])==digest(references[spec['batch']]['outputs']),'measured score differs')
                counts={k:scorer.stats[k]-before.get(k,0) for k in ('tokens','forwards','head_positions','items')}
                t=time.perf_counter();call(spec['variant'],batch,host_only=True);host_seconds=time.perf_counter()-t
                value=dict(spec,status='PASS',exit_code=0,attempt=attempt,plan_sha256=pin,ids=actual['ids'],
                    output_sha256=digest(actual['outputs']),score_seconds=seconds,host_only_seconds=host_seconds,counts=counts,
                    reserved_gib=torch.npu.max_memory_reserved()/2**30,chips=1)
                atomic(path,value,exclusive=True)
                trials.append(value);state.update(completed=len(trials),reserved_gib=value['reserved_gib'],
                    forwarded_tokens_per_second_per_chip=value['counts']['tokens']/value['score_seconds']);beat()
            result=summarize(trials);verify(plan_path,pin)
            result.update(plan_sha256=pin,attempt=attempt,run_seconds=time.perf_counter()-started,baseline_repeat_exact=True,candidate_exact=True,exit_code=0)
            atomic(out/'report.json',result);atomic(out/'COMPLETE.json',result,exclusive=True);rc=0;state['status']='complete'
        except BaseException as error:
            state.update(status='failed',error_type=type(error).__name__,error=str(error)[:800])
            atomic(out/'FAILURE.json',dict(state,plan_sha256=pin,exit_code=1),exclusive=True);raise
        finally:
            stop.set();thread.join(timeout=2);beat();atomic(adir/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,scientific_acceptance=False,test_read=False))
    return rc


def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','run']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('BEV_ENCODE_DEV_VERIFIED');return 0
    d=json.loads(Path(a.plan).read_text());out=safe(d['out']);(out/'logs').mkdir(parents=True,exist_ok=True)
    with (out/'logs'/f'attempt-{a.attempt}.log').open('a',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        return run(a.plan,a.sha256,a.attempt)


if __name__=='__main__':raise SystemExit(main())
