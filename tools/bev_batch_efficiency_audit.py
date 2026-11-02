"""CPU-only, gold-free BEV batch-shape audit; never launches or claims NPU."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import types


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)
def module(entry, name):
    raw=Path(entry['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==entry['sha256'], 'source hash differs')
    m=types.ModuleType(name);m.__file__=entry['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m


def shapes(records, budget=16384, chunk=8, order='original'):
    require(budget>0 and chunk>0, 'invalid budget/chunk')
    require(order in ('original','length'), 'unknown order')
    require(len({r['id'] for r in records})==len(records), 'duplicate IDs')
    rows=records if order=='original' else sorted(records,key=lambda r:(max(r['lengths']),r['id']))
    counts=Counter(); histogram=Counter(); widths=[]; batches=[]
    for start in range(0,len(rows),chunk):
        outer=rows[start:start+chunk];flat=[]
        for r in outer:
            require(r['lengths'] and min(r['lengths'])>0,'empty sequence')
            flat.extend((r['id'],i,n) for i,n in enumerate(r['lengths']))
        flat.sort(key=lambda x:-x[2]);pos=0
        while pos<len(flat):
            width=flat[pos][2];size=max(1,budget//width);batch=flat[pos:pos+size];pos+=size
            useful=sum(r[2] for r in batch);forwarded=width*len(batch)
            counts.update(forwards=1,forwarded_tokens=forwarded,useful_tokens=useful,padded_tokens=forwarded-useful,candidate_rows=len(batch))
            histogram[len(batch)]+=1;widths.append(width)
            batches.append({'width':width,'rows':[(x[0],x[1]) for x in batch]})
    require(counts['candidate_rows']==sum(len(r['lengths']) for r in records),'population mismatch')
    return dict(counts,padding_fraction=counts['padded_tokens']/counts['forwarded_tokens'],questions=len(rows),outer_calls=(len(rows)+chunk-1)//chunk,
                batch_rows_histogram=dict(sorted(histogram.items())),width_min=min(widths),width_max=max(widths),layout_sha256=hashlib.sha256(json.dumps(batches,separators=(',',':')).encode()).hexdigest())


def quantiles(xs):
    xs=sorted(xs)
    return {str(p):xs[round((len(xs)-1)*p)] for p in (0,.1,.25,.5,.75,.9,.95,.99,1)}


def audit(args):
    from tokenizers import Tokenizer
    plan_path=Path(args.plan);require(sha(plan_path)==args.plan_sha256,'plan differs');plan=json.loads(plan_path.read_text())
    require(plan['scope']=='train_derived_dev' and plan['test_read'] is False,'DEV only')
    require(sha(args.requests)==args.requests_sha256,'requests differ')
    rows=[json.loads(x) for x in Path(args.requests).read_text().splitlines()]
    require(len(rows)==6516 and all(set(r)=={'id','request'} for r in rows),'exact DEV population required')
    sample=json.loads(Path(plan['inputs']['sample']['path']).read_text())
    require(sample['source_requests_sha256']==args.requests_sha256,'DEV source binding differs')
    prompt=module(plan['code']['prompt'],'shape_prompt');sys.modules['prompt']=prompt
    scorer=module(plan['code']['scorer'],'shape_scorer');bridge=module(plan['code']['bridge'],'shape_bridge')
    tokenizer_path=plan['model_files']['tokenizer.json']['path'];require(sha(tokenizer_path)==plan['model_files']['tokenizer.json']['sha256'],'tokenizer differs')
    tokenizer=Tokenizer.from_file(tokenizer_path)
    class Adapter:
        def __call__(self,text,add_special_tokens=False):return {'input_ids':tokenizer.encode(text,add_special_tokens=add_special_tokens).ids}
    enc=scorer.encode_rows(Adapter(),[bridge.to_r3_row(r['request']) for r in rows],render='record_name')
    mapping={r['id']:e for r,e in zip(rows,enc)}
    for i in range(9):
        gate=json.loads((Path(plan['out'])/'attempts/1'/f'equivalence-{i}.json').read_text())
        require(gate['baseline_repeat_exact'] and gate['candidate_exact'],'NPU gate failed')
        actual=[dict(prefix=mapping[k].prefix,cands=mapping[k].cands) for k in gate['reference']['ids']]
        require(actual==gate['reference']['layout'][0]['enc'],'CPU tokenizer differs from actual NPU encodings')
    reduced,maps,nq,nr=scorer.dedup_enc(enc)
    require(nr==0,'unexpected duplicate candidates')
    records=[dict(id=r['id'],type=r['request']['type'],prefix=len(e.prefix),lengths=[len(e.prefix)+len(c) for c in e.cands]) for r,e in zip(rows,reduced)]
    require(max(max(r['lengths']) for r in records)<=4096,'unsupported rows')
    by_id={r['id']:r for r in records};samples=[by_id[k] for k in sample['ordered_ids']]
    result={'schema':'bev-cpu-batch-shape-audit-v1','scope':'TRAIN-derived DEV inputs only','test_read':False,'npu_used':False,'scientific_acceptance':False,
            'plan_sha256':args.plan_sha256,'source_requests':{'path':args.requests,'sha256':args.requests_sha256},'cpu_tokenizer_matches_actual_probe_rows':72,
            'populations':{}}
    for label,rr in [('full_dev',records),('probe72',samples)]:
        result['populations'][label]={'types':dict(Counter(r['type'] for r in rr)),
             'question_max_length_quantiles':quantiles([max(r['lengths']) for r in rr]),
             'candidate_count_quantiles':quantiles([len(r['lengths']) for r in rr]),
             'scenarios':{}}
        for order,budget in [('original',16384),('length',16384),('original',8192),('original',32768)]:
            result['populations'][label]['scenarios'][order+'-'+str(budget)]=shapes(rr,budget=budget,order=order)
    verified=[]
    for population,rr in [('full_dev',records),('probe72',samples)]:
        for order in ('original','length'):
            sequence=rr if order=='original' else sorted(rr,key=lambda r:(max(r['lengths']),r['id']))
            observed=Counter();driver=scorer.R3Scorer('unused',token_budget=16384)
            def capture(batch,width,out):
                useful=sum(len(row[2]) for row in batch)
                observed.update(forwards=1,forwarded_tokens=len(batch)*width,useful_tokens=useful,padded_tokens=len(batch)*width-useful,candidate_rows=len(batch))
            driver._score_flat_batch=capture
            for start in range(0,len(sequence),8):
                driver._rightpad([mapping[r['id']] for r in sequence[start:start+8]])
            expected=result['populations'][population]['scenarios'][order+'-16384']
            require(all(expected[k]==v for k,v in observed.items()),'shape simulator differs from frozen scorer')
            verified.append(dict(population=population,order=order,actual_frozen_rightpad_matches=True))
    result['frozen_scorer_cpu_layout_replay']=verified
    result['evidence_hashes']={str(plan_path):sha(plan_path),tokenizer_path:sha(tokenizer_path),__file__:sha(__file__)}
    for item in plan['code'].values():result['evidence_hashes'][item['path']]=item['sha256']
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'CPU_SHAPES_COMPLETE','output':args.out,'questions':len(records)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--requests',required=True);p.add_argument('--requests-sha256',required=True);p.add_argument('--out',required=True);audit(p.parse_args())
