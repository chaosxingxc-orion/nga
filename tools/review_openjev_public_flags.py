#!/usr/bin/env python3
"""Read-only post-run reproduction of flagged Open-Jev public-test cohorts."""
import argparse, ast, collections, copy, hashlib, json, math, time
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,sort_keys=True,allow_nan=False).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if a.out.exists():raise ValueError('Existing diagnosis output preserved')
    c=load(a.run/'config.json');audit=load(a.audit);identity=stamp(c)
    assert identity==audit['identity'] and sha(a.run/'config.json')==audit['config_sha256']
    assert sha(a.run/'report.json')==audit['report_sha256']
    api=Path(c['code'])/'jev/api.py';model=Path(c['code'])/'jev/model.py'
    for p in [Path(c['data']),api,model]:assert sha(p)==c['files'][str(p)]
    # Only inspected rendering functions are compiled; no directory is on sys.path.
    tree=ast.parse(api.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_render','candidate_prompts')]
    assert {n.name for n in nodes}=={'_render','candidate_prompts'}
    ns={'json':json};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(api),'exec'),ns);render=ns['candidate_prompts']
    rows=[json.loads(x) for x in Path(c['data']).read_text().splitlines() if x.strip()];assert len(rows)==10356
    groups={name:[] for name in ['customer-control-v1','trex_runner-v1']};high=[];bindings=[]
    for i,row in enumerate(rows):
        p=a.run/('record-%06d.json'%i);envelope=load(p);v=envelope['payload'];assert stamp(v)==envelope['sha256']
        expected=dict(index=i,id=row['id'],input_sha256=stamp(row),identity=identity,options=row['options'],target=row['target'],source=row['source'],kind=row['kind'],group_id=row['group_id'])
        assert all(v.get(k)==x for k,x in expected.items())
        z=v['logits'];e=[math.exp((x-max(z))/c['temperature']) for x in z];probs=[x/sum(e) for x in e]
        assert len(probs)==len(row['target']) and all(abs(x-y)<=1e-12 for x,y in zip(probs,v['probabilities']))
        chosen=max(range(len(probs)),key=probs.__getitem__);gold=max(range(len(row['target'])),key=row['target'].__getitem__);hard=max(row['target'])==1
        item=dict(index=i,id=row['id'],source=row['source'],input_sha256=stamp(row),receipt_sha256=sha(p),predicted_index=chosen,gold_index=gold,hard=hard,correct=chosen==gold,expected_correctness=row['target'][chosen],confidence=max(probs),prediction=row['options'][chosen],gold=row['options'][gold])
        if max(probs)>=.99:high.append(item)
        if row['source'] not in groups:continue
        prompts=render(row);changed=copy.deepcopy(row);changed.update(target=list(reversed(row['target'])),id='changed',source='changed',group_id='changed',metadata={'changed':True})
        assert render(changed)==prompts
        item.update(prompt_sha256=stamp(prompts),gold_metadata_prompt_invariant=True,group_id=row['group_id'],kind=row['kind'],provenance_type=row.get('metadata',{}).get('provenance',{}).get('type'))
        groups[row['source']].append(item)
    summaries={}
    for name,items in groups.items():
        hard=[x for x in items if x['hard']]
        summaries[name]=dict(count=len(items),hard_count=len(hard),soft_count=len(items)-len(hard),hard_correct=sum(x['correct'] for x in hard),hard_accuracy=sum(x['correct'] for x in hard)/len(hard),expected_accuracy=sum(x['expected_correctness'] for x in items)/len(items),unique_groups=len({x['group_id'] for x in items}),unique_prompts=len({x['prompt_sha256'] for x in items}),prediction_counts=dict(collections.Counter(x['prediction'] for x in items)),gold_counts=dict(collections.Counter(x['gold'] for x in items)),kinds=dict(collections.Counter(x['kind'] for x in items)),provenance_types=dict(collections.Counter(x['provenance_type'] for x in items)),prompt_invariance_passed=sum(x['gold_metadata_prompt_invariant'] for x in items))
    assert summaries['customer-control-v1']['hard_correct']==574 and summaries['trex_runner-v1']['hard_correct']==1
    result=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),scope='Read-only post-run diagnosis; original review flags retained; no training overlap, deployment reliability or Astra approval claim.',source_hashes={str(p):sha(p) for p in [a.run/'config.json',a.run/'report.json',a.audit,Path(c['data']),api,model,Path(__file__)]},records_bound=len(rows),original_review_flags=audit['review_flags'],cohorts=summaries,cohort_items=groups,high_confidence_diagnostic=dict(threshold=.99,count=len(high),hard_count=sum(x['hard'] for x in high),correct=sum(x['correct'] for x in high),by_source=dict(collections.Counter(x['source'] for x in high))))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(output=str(a.out),sha256=sha(a.out),cohort_rows=sum(len(v) for v in groups.values()),records_bound=len(rows))))
if __name__=='__main__':main()
