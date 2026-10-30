#!/usr/bin/env python3
"""Independent stdlib Nimble artifact/metric audit, without importing native scoring code."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import string

COUNTS={'massive-en-US':350,'massive-de-DE':350,'paws':250,'civil_comments':300,'aegis2':250,'summeval-relevance':240,'summeval-consistency':144}
ADAPTER_SHA='ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b'
REVISION='594dfdcfb6f94e3d0c0db7535180d3c71689169a'
BASE_REVISION='c202236235762e1c871ad0ccb60c8ee5ba337b9a'

def require(ok,msg):
    if not ok: raise ValueError(msg)
def load(p): return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''): h.update(b)
    return h.hexdigest()
def stamp(v): return hashlib.sha256(json.dumps(v,sort_keys=True,allow_nan=False).encode()).hexdigest()
def same(a,b,where='value'):
    if isinstance(b,dict):
        require(isinstance(a,dict) and set(a)==set(b),where+': keys differ')
        for k in b: same(a[k],b[k],where+'/'+k)
    elif isinstance(b,list):
        require(isinstance(a,list) and len(a)==len(b),where+': size differs')
        for i,(x,y) in enumerate(zip(a,b)):same(x,y,where+'/'+str(i))
    elif type(b) is float: require(type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),where+': numeric differs')
    else: require(type(a) is type(b) and a==b,where+': differs')

def assess(p,target,kind):
    require(p and all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in p.values()) and abs(sum(p.values())-1)<=1e-6,'Invalid probabilities')
    gold=str(target).lower() if kind=='noul' else str(target)
    require(gold in p,'Gold missing')
    best=max(p,key=p.get)
    prediction=(best=='true') if kind=='noul' else int(best) if kind=='score' else best
    result={'prediction':prediction,'correct':best==gold,'probabilities':p,'reference_probability':p[gold],'top_probability':p[best],
            'negative_log_likelihood':-math.log(max(p[gold],1e-15)), 'multiclass_brier':sum((v-int(k==gold))**2 for k,v in p.items())}
    if kind=='noul':result['binary_brier']=(p['true']-int(target))**2
    if kind=='score':
        expected=sum(int(k)*v for k,v in p.items());result.update(expected_score=expected,absolute_score_error=abs(expected-target))
    return result

def distribution_metrics(p,q):
    require(set(p)==set(q) and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in q.values()) and abs(sum(q.values())-1)<=1e-6,'Human distribution differs')
    js=0.
    for k in p:
        m=(p[k]+q[k])/2
        if p[k]>0:js+=p[k]*math.log2(p[k]/m)/2
        if q[k]>0:js+=q[k]*math.log2(q[k]/m)/2
    return {'jensen_shannon_bits':min(max(js,0.),1.),'total_variation':sum(abs(p[k]-q[k]) for k in p)/2,
            'human_entropy_bits':-sum(v*math.log2(v) for v in q.values() if v>0)}

def summarize(rows):
    result={}
    for kind in ('all','choice','noul','score'):
        selected=[r['student'] for r in rows if kind=='all' or r['type']==kind]
        if not selected:continue
        d={'count':len(selected),'correct':sum(r['correct'] for r in selected)};d['accuracy']=d['correct']/d['count']
        for k in ('negative_log_likelihood','multiclass_brier','binary_brier','absolute_score_error'):
            if all(k in r for r in selected):d['mean_'+k]=statistics.mean(r[k] for r in selected)
        result[kind]=d
    return result

def aggregate(rows):
    require(bool(rows),'Empty rows')
    times=sorted(r['elapsed_seconds'] for r in rows);ece=0.
    for i in range(10):
        selected=[r['student'] for r in rows if i/10<=r['student']['top_probability'] and (r['student']['top_probability']<(i+1)/10 or i==9 and r['student']['top_probability']<=1)]
        ece+=abs(sum(v['top_probability']-v['correct'] for v in selected))/len(rows)
    codes=Counter()
    for r in rows:
        f=r['raw_student']['fields']['decision'];codes.update([next(k for k,v in f['code_to_choice'].items() if v==f['value'])])
    result={'count':len(rows),'summary':summarize(rows),'calibration':{'ece10':ece,'bins':10,'confidence':'top candidate probability; no temperature has been fitted'},
            'selected_code_counts':dict(sorted(codes.items())),'by_domain':{d:summarize([r for r in rows if r['domain']==d]) for d in sorted({r['domain'] for r in rows})},
            'timing':{'total_scoring_seconds':sum(times),'median_seconds':statistics.median(times),'p95_seconds':times[math.ceil(.95*len(times))-1]}}
    soft=[r['distribution'] for r in rows if 'distribution' in r]
    if soft:result['distribution_agreement']={'count':len(soft),**{'mean_'+k:statistics.mean(v[k] for v in soft) for k in ('jensen_shannon_bits','total_variation','human_entropy_bits')},'note':'Base-2 Jensen-Shannon and total variation against the human label distribution'}
    return result

def verify_receipt(envelope,row,index,identity,c,vocab):
    v=envelope['payload'];require(stamp(v)==envelope['sha256'],'Receipt checksum differs')
    for k,x in {'id':row['id'],'index':index,'identity':identity,'input_sha256':stamp(row)}.items():same(v[k],x,'receipt/'+k)
    q=row['input']['questions']['decision'];kind=q['type'];criteria=q['criteria']
    choices=[False,True] if kind=='noul' else list(criteria) if kind=='choice' else [str(i) for i in range(len(criteria))]
    keys=[str(x).lower() if type(x)is bool else x for x in choices]
    require(len(choices)<=26,'Unsupported candidate width')
    r=v['result'];raw=r['raw_student'];f=raw['fields']['decision']
    require(list(f['scores'])==list(f['logits'])==keys,'Candidate order differs')
    same(f['code_to_choice'],dict(zip(string.ascii_uppercase,choices)),'code mapping')
    same(f['candidate_token_ids'],[vocab[x] for x in string.ascii_uppercase[:len(keys)]],'candidate token IDs')
    z=list(f['logits'].values());p=f['scores']
    require(all(type(x) in (int,float) and math.isfinite(x) for x in z),'Invalid logits')
    weights=[math.exp(x-max(z)) for x in z];total=sum(weights)
    require(all(abs(a/total-b)<=1e-6 for a,b in zip(weights,p.values())),'Probability/logit mismatch')
    best=max(range(len(z)),key=z.__getitem__);same(f['value'],choices[best],'typed prediction');same(raw['output'],{'decision':choices[best]},'output')
    same(raw['temperature'],1.0,'temperature');same(raw['revision'],c['adapter_revision'],'revision');same(raw['model'],c['model_id'],'model')
    require(type(f['prompt_token_count'])is int and 0<f['prompt_token_count']<=2048 and re.fullmatch('[0-9a-f]{64}',f['prompt_token_sha256']),'Prompt metadata invalid')
    for k,x in {'id':row['id'],'reference':row['reference'],'type':kind,'domain':row['domain'],'family':row['family'],'split':row.get('split','test')}.items():same(r[k],x,'row/'+k)
    student=assess(p,row['reference']['target'],kind);same(r['student'],student,'student')
    rebuilt={**r,'student':student}
    if 'distribution' in row['reference']:
        d=distribution_metrics(p,row['reference']['distribution']);same(r['distribution'],d,'distribution');rebuilt['distribution']=d
    else:require('distribution' not in r,'Unexpected human distribution')
    require(type(r['elapsed_seconds']) in (int,float) and math.isfinite(r['elapsed_seconds']) and r['elapsed_seconds']>0,'Invalid timing')
    return rebuilt

def terminal(run,config_sha,identity):
    t=load(run/'COMPLETE.json');require(type(t.get('rc'))is int and t['rc']==0 and not t.get('error'),'Failed terminal')
    require(t['config_sha256']==config_sha and t['identity']==identity and t['stage']=='completed','Terminal identity differs')
    require(t['progress']==t['total']==1884,'Terminal coverage differs')
    for n in ('report.json','PREFLIGHT.json'):require(t['outputs'][n]==sha(run/n),'Output hash differs')
    require(re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?',(run/'EXIT').read_text()),'Wrapper failed')
    require((run/'EXIT').stat().st_mtime_ns>=(run/'COMPLETE.json').stat().st_mtime_ns>=(run/'report.json').stat().st_mtime_ns,'Stale terminal/wrapper')
    require(not any((run/n).exists() for n in ('FAILED','ERROR.json')),'Conflicting failure')

def required_files(c):
    run=Path(c['out']);needed={str(run/n) for n in ('nimble_reference_eval.py','test_nimble_reference_eval.py','launch.sh','run.sh','LAUNCH_EXACT.sh','PREREGISTRATION.md')}
    for key in ('base','adapter','code'):
        root=Path(c[key]);require(root.is_dir(),'Missing dependency root')
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for s in c['suites']:needed.update([s['data'],s['manifest']])
    return needed

def review_flags(audited, run):
    """Flag suspicious metric values; aliases do not count as independent cells."""
    flags=[]; across={}
    metric_names={'accuracy','ece10','mean_negative_log_likelihood','mean_multiclass_brier',
                  'mean_binary_brier','mean_absolute_score_error','mean_jensen_shannon_bits',
                  'mean_total_variation','mean_human_entropy_bits'}
    for suite, report in audited.items():
        base=str(run/suite/'report.json')+'#'
        def walk(node, pointer):
            if not isinstance(node,dict):return
            if type(node.get('count')) is int and node['count']<30:
                flags.append({'reason':'small_count','pointer':pointer+'/count'})
            for key, value in node.items():
                path=pointer+'/'+key
                if key in metric_names and type(value) in (int,float) and value in (0.,1.):
                    flags.append({'reason':'extreme_metric','pointer':path})
                if isinstance(value,dict):walk(value,path)
        walk(report,base)
        # Use one all-summary cell per real suite, not all/type aliases or domains.
        canonical={**report['summary']['all'], **report['calibration'],
                   **report.get('distribution_agreement',{})}
        for key,value in canonical.items():
            if key in metric_names and type(value) in (int,float):
                across.setdefault(key,[]).append((suite,value))
    for key, cells in across.items():
        if len(cells)>1 and len({value for _,value in cells})==1:
            flags.append({'reason':'identical_metric_across_suites','metric':key,
                          'pointers':[str(run/suite/'report.json')+'#' for suite,_ in cells]})
    return flags

def verify(config_path):
    c=load(config_path);run=Path(c['out']);config_sha=sha(config_path);identity=stamp(c);needed=required_files(c)
    require(needed<=set(c['files']),'Required frozen dependency missing')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed: '+p)
    require(c['adapter_revision']==REVISION and sha(Path(c['adapter'])/'adapter_model.safetensors')==ADAPTER_SHA,'Wrong original adapter')
    require(c['base_revision']==BASE_REVISION and Path(c['base'],'.complete').read_text().splitlines()[0]==BASE_REVISION,'Base revision differs')
    launch=load(run/'LAUNCH_RECEIPT.json');require(launch['config_sha256']==config_sha and launch['wrapper_sha256']==sha(run/'run.sh') and launch['image']==c['image'],'Launch binding differs')
    terminal(run,config_sha,identity);report=load(run/'report.json');pre=load(run/'PREFLIGHT.json')
    require({s['name']:s['count'] for s in c['suites']}==COUNTS,'Suite population differs')
    same(pre['suite_counts'],COUNTS,'preflight counts');require(pre['identity']==identity and pre['rows']==1884 and pre['max_tokens']<=2048,'Preflight differs')
    vocab=load(Path(c['adapter'])/'tokenizer.json')['model']['vocab'];audited={};flags=[];maximum=0
    for suite in c['suites']:
        name=suite['name'];data=Path(suite['data']);manifest=load(suite['manifest']);rows=[json.loads(x) for x in data.read_text().splitlines()]
        require(sha(data)==suite['dataset_sha256']==manifest['dataset_sha256'],'Dataset hash differs')
        require(len(rows)==COUNTS[name]==manifest['count'] and [r['id'] for r in rows]==sorted(manifest['ids']) and len({r['id'] for r in rows})==len(rows),'Dataset IDs/count differ')
        folder=run/name;names=[f'{i:06d}.json' for i in range(len(rows))]
        require(sorted(p.name for p in folder.glob('[0-9]*.json'))==names,'Receipt coverage differs')
        rebuilt=[]
        for i,(row,n) in enumerate(zip(rows,names)):
            r=verify_receipt(load(folder/n),row,i,identity,c,vocab);rebuilt.append(r);maximum=max(maximum,r['raw_student']['fields']['decision']['prompt_token_count'])
        expected=aggregate(rebuilt);expected.update(dataset_sha256=suite['dataset_sha256'],identity=identity)
        same(load(folder/'report.json'),expected,name+'/report');same(report['suites'][name],expected,name+'/aggregate')
        audited[name]=expected
    flags=review_flags(audited,run)
    require(report['identity']==identity and report['rows']==1884 and set(report['suites'])==set(COUNTS),'Final coverage differs')
    require(pre['max_tokens']==maximum,'Prompt length summary differs')
    terminal(run,config_sha,identity);require(sha(config_path)==config_sha,'Config changed during audit')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed during audit: '+p)
    return {'status':'VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED','records_verified':1884,'frozen_files_verified':len(c['files']),'required_files_verified':len(needed),'config_sha256':config_sha,'report_sha256':sha(run/'report.json'),'metrics':audited,'review_flags':flags,'scope':'Independent arithmetic and artifact verification from raw scores. Candidate IDs checked against frozen tokenizer vocabulary. Prompt hashes are format/provenance-bound, not independently retokenized; no CUDA equivalence, upstream contamination or Astra approval.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();result=verify(a.config)
    Path(a.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'records_verified':result['records_verified']}))
if __name__=='__main__':main()
