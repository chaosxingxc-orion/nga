#!/usr/bin/env python3
"""CPU-only tokenizer/layout probe; never loads a model or produces scores."""
import argparse
from collections import OrderedDict
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
import traceback


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    tmp = p.with_suffix('.pending')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(p)


class CachedTokenizer:
    """Instance-scoped cache: bound to one tokenizer, exact text and fixed kwargs."""
    def __init__(self, tokenizer, capacity=4096):
        self.tokenizer, self.capacity = tokenizer, capacity
        self.cache = OrderedDict()
        self.hits = self.misses = 0

    def __call__(self, text, add_special_tokens=False):
        if add_special_tokens is not False or not isinstance(text, str):
            raise ValueError('probe supports exact text without special tokens only')
        if text in self.cache:
            self.hits += 1
            self.cache.move_to_end(text)
        else:
            self.misses += 1
            self.cache[text] = tuple(self.tokenizer(text, add_special_tokens=False)['input_ids'])
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
        return {'input_ids': list(self.cache[text])}


def layout(enc, scorer):
    reduced, maps, _, _ = scorer.dedup_enc(enc)
    rows = [(i,j,e.prefix+c,len(e.prefix)) for i,e in enumerate(reduced) for j,c in enumerate(e.cands)]
    order = sorted(range(len(rows)), key=lambda i:-len(rows[i][2]))
    batches = []
    pos = 0
    while pos < len(order):
        width = len(rows[order[pos]][2])
        size = max(1,16384//width)
        indices = order[pos:pos+size]
        batches.append({'width':width,'rows':indices})
        pos += size
    return {'batches':batches,'maps':maps,
            'forwarded_tokens':sum(x['width']*len(x['rows']) for x in batches),
            'unpadded_tokens':sum(len(x[2]) for x in rows),
            'repeated_prefix_tokens':sum(x[3] for x in rows),
            'unique_question_prefix_tokens':sum(len(x.prefix) for x in reduced)}


def run(a):
    source = Path(a.data)
    if source.name != 'dev.jsonl':
        raise ValueError('only dev.jsonl admitted')
    sys.dont_write_bytecode = True
    sys.path[:0] = [a.r3_code,a.r0_code]
    S = importlib.import_module('scorer_r3')
    P = importlib.import_module('prompt')
    if Path(S.__file__).parent != Path(a.r3_code) or Path(P.__file__).parent != Path(a.r0_code):
        raise ValueError('code origin differs')
    from transformers import AutoTokenizer
    model = Path(a.model)
    token_files = [p for p in model.iterdir() if p.is_file() and p.suffix in ('.json','.txt','.jinja')]
    inputs = {str(p):sha(p) for p in token_files+[source,Path(S.__file__),Path(P.__file__),Path(__file__)]}
    tok = AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
    with source.open() as f:
        rows = [json.loads(next(f)) for _ in range(64)]
    chunks=[]
    for name,transform in [('full',lambda r:r),('blank',P.blank_input),('drop',P.drop_input)]:
        values = [transform(r) for r in rows]
        chunks.extend((name,values[i:i+32]) for i in range(0,64,32))
    # Warm tokenizer internals before comparing the two implementations.
    tok('Tokenizer initialization warmup 中文 123',add_special_tokens=False)
    original=[]; seconds=0.
    for name,batch in chunks:
        t=time.perf_counter(); enc=S.encode_rows(tok,batch);seconds+=time.perf_counter()-t
        original.append((enc,layout(enc,S)))
    cache=CachedTokenizer(tok);timings={};totals={}
    for phase in ('cold','warm'):
        total=0.
        for index,(name,batch) in enumerate(chunks):
            t=time.perf_counter();enc=S.encode_rows(cache,batch);total+=time.perf_counter()-t
            if enc != original[index][0] or layout(enc,S) != original[index][1]:
                raise ValueError('token or batch layout changed')
            write(Path(a.out)/'heartbeat.json',{'utc_seconds':time.time(),'phase':phase,'done':index+1,'total':len(chunks)})
        timings[phase]=total;totals[phase]={'hits':cache.hits,'misses':cache.misses,'entries':len(cache.cache)}
    # Mutating a caller-owned token list cannot poison a cached entry.
    text='边界 café🙂\n\t'; expected=tok(text,add_special_tokens=False)['input_ids']
    got=cache(text)['input_ids'];got.append(-1)
    if cache(text)['input_ids'] != expected or cache('')['input_ids'] != tok('',add_special_tokens=False)['input_ids']:
        raise ValueError('cache text/mutation boundary failed')
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('input changed during probe')
    counters={k:sum(x[1][k] for x in original) for k in ('forwarded_tokens','unpadded_tokens','repeated_prefix_tokens','unique_question_prefix_tokens')}
    counters['forwards']=sum(len(x[1]['batches']) for x in original)
    result={'status':'PASS','records':64,'roles':3,'calls':len(chunks),'exact_tokens_and_batch_layout':True,
            'seconds':{'uncached':seconds,**timings},'cache_cumulative':totals,'layout':counters,'inputs':inputs,
            'test_read':False,'model_loaded':False,'scientific_acceptance':False,
            'limits':['single small CPU sample; timing includes prompt rendering and Python encoding only',
                      'warm pass repeats the same 64 records; not expected workload hit rate',
                      'no NPU speedup or score equivalence claimed; frozen scorer unchanged']}
    write(Path(a.out)/'digest.json',result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--model',required=True)
    p.add_argument('--r3-code',required=True);p.add_argument('--r0-code',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();code=1
    try:run(a);code=0
    except Exception:
        traceback.print_exc()
    finally:write(Path(a.out)/'EXIT.json',{'exit_code':code,'utc_seconds':time.time(),'scientific_acceptance':False})
    sys.exit(code)
