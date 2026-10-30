#!/usr/bin/env python3
"""Read-only ordered Kev-9B reference comparison at common temperatures."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def objsha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require(ok, message):
    if not ok: raise ValueError(message)


def softmax(z):
    require(z and all(math.isfinite(x) for x in z), 'Invalid logits')
    e=[math.exp(x-max(z)) for x in z]; total=math.fsum(e)
    return [x/total for x in e]


def probs(row, temperature):
    t=row.get('inference_temperature') or 1.0
    require(math.isfinite(t) and t>0 and temperature>0, 'Invalid temperature')
    return softmax([x*t/temperature for x in row['logits']])


def argmax(p): return max(range(len(p)), key=p.__getitem__)
def margin(p):
    values=sorted(p,reverse=True)
    return values[0]-values[1] if len(values)>1 else 1.0

def bin10(conf):
    for i in range(10):
        if conf>=i*.1 and (conf<(i+1)*.1 or i==9 and conf<=1):return i
    raise ValueError('Invalid confidence')


def metrics(rows, temperature):
    ps=[probs(r,temperature) for r in rows]; n=len(rows)
    require(n>0,'Empty population')
    ok=[argmax(p)==r['label'] for p,r in zip(ps,rows)]
    ece=sum(abs(math.fsum(int(correct)-max(p) for p,correct in zip(ps,ok) if bin10(max(p))==i))/n for i in range(10))
    nll=[]
    for row in rows:
        t=row.get('inference_temperature') or 1.0
        z=[x*t/temperature for x in row['logits']]; hi=max(z)
        nll.append(math.log(math.fsum(math.exp(x-hi) for x in z))+hi-z[row['label']])
    return {'n':n,'correct':sum(ok),'acc':sum(ok)/n,'brier':math.fsum(math.fsum((x-int(i==r['label']))**2 for i,x in enumerate(p)) for p,r in zip(ps,rows))/n,
            'ece10':ece,'nll':math.fsum(nll)/n}


def aligned(upstream, local, records):
    expected=[]
    for i,record in enumerate(records):
        for j,(qid,q) in enumerate(record['questions'].items()):
            keys=list(q['criteria']) if q['type']=='choice' else ['false','true'] if q['type']=='noul' else [str(k) for k in range(len(q['criteria']))]
            label=keys.index(q['label']) if q['type']=='choice' else int(q['label'])
            expected.append({'id':record['_meta']['id'],'question':qid,'keys':keys,'label':label,'source':record['_meta']['source'],
                             'variant':record['_meta']['variant'],'type':q['type'],'task':q['src'],'record_index':i,'question_index':j,'input_sha256':objsha(record)})
    require(len(upstream)==len(local)==len(expected),'Ordered population count differs')
    for i,(u,l,e) in enumerate(zip(upstream,local,expected)):
        for key in ('id','question','keys','label','source','variant','type','task'):
            require(u[key]==l[key]==e[key],f'Identity differs at {i}/{key}')
        for key in ('group','control_id','pair_id','sibling','parent'):
            require(u.get(key)==l.get(key),f'Optional metadata differs at {i}/{key}')
        for key in ('record_index','question_index','input_sha256'):
            if key in l:require(l[key]==e[key],f'Local source binding differs at {i}/{key}')
        for row in (u,l):
            require(len(row['p'])==len(row['logits'])==len(e['keys']),f'Candidate length differs at {i}')
            t=row.get('inference_temperature') or 1.0
            require(all(abs(a-b)<1e-5 for a,b in zip(row['p'],probs(row,t))),f'Saved probability mismatch at {i}')
    return expected


def compare(upstream,local,records,drop,serving):
    identities=aligned(upstream,local,records); result={}
    for population,indices in [('full',list(range(len(local)))),('release',[i for i,r in enumerate(local) if r['id'] not in drop])]:
        u=[upstream[i] for i in indices];l=[local[i] for i in indices]
        panels={}
        for name,temp in [('raw_T1',1.0),('serving',serving)]:
            up=[probs(r,temp) for r in u];lp=[probs(r,temp) for r in l]
            changes=[]
            for index,a,b in zip(indices,up,lp):
                if argmax(a)!=argmax(b):
                    e=identities[index];changes.append({**e,'row_index':index,'upstream_choice':e['keys'][argmax(a)],'local_choice':e['keys'][argmax(b)],
                        'gold_choice':e['keys'][e['label']],'upstream_correct':argmax(a)==e['label'],'local_correct':argmax(b)==e['label'],
                        'upstream_top_margin':margin(a),'local_top_margin':margin(b),'upstream_probabilities':a,'local_probabilities':b})
            panels[name]={'temperature':temp,'upstream':metrics(u,temp),'local':metrics(l,temp),'argmax_changes':changes,
                'max_probability_delta':max(abs(a-b) for aa,bb in zip(up,lp) for a,b in zip(aa,bb)),
                'ece_bin_changes':sum(bin10(max(a))!=bin10(max(b)) for a,b in zip(up,lp))}
        result[population]=panels
    return {'rows_verified':len(local),'ordered_identity_sha256':objsha(identities),'excluded_row_indices':[i for i,r in enumerate(local) if r['id'] in drop],
            'upstream_saved_temperatures':sorted({r.get('inference_temperature') or 1. for r in upstream}),
            'local_saved_temperatures':sorted({r.get('inference_temperature') or 1. for r in local}),'populations':result}


def execute(root,out):
    repo=root/'repos/jev/jaredpalmer__kev'; runs=root/'experiments/jev/reference_inference'
    spec=repo/'experiments/releases/kev-9b-r27.json'; release=repo/'runs/release/kev-9b-r27.json'
    policy=json.loads(spec.read_text());published=json.loads(release.read_text())['candidate'];temp=published['temperature']
    inputs={str(p):sha(p) for p in [Path(__file__).resolve(),spec,release,repo/'kev/metrics.py',repo/'kev/predictors.py']}; suites={}
    for suite,key,run in [('hard-v1','hard_test','kev9_extended_20261030'),('documents-v1','docs1_test','kev9_extended_20261030'),('devtools-v1','devtools_test','kev9_devtools_20261030')]:
        paths={'upstream_rows':repo/policy['candidate'][key]/'rows.json','upstream_report':repo/policy['candidate'][key]/'report.json',
               'local_rows':runs/run/suite/'rows.json','dataset':repo/'evals'/suite/'test.jsonl','local_audit':runs/run/'INDEPENDENT_AUDIT.json',
               'local_config':runs/run/'config.json'}
        inputs.update({str(p):sha(p) for p in paths.values()})
        u=json.loads(paths['upstream_rows'].read_text());l=json.loads(paths['local_rows'].read_text());data=[json.loads(x) for x in paths['dataset'].read_text().splitlines()]
        comparison=compare(u,l,data,policy['drop_ids'],temp)
        raw=comparison['populations']['full']['raw_T1']['upstream'];reported=json.loads(paths['upstream_report'].read_text())['clean']
        require(raw['n']==reported['n'] and abs(raw['acc']-reported['acc'])<1e-12,'Upstream full accuracy differs')
        kept=comparison['populations']['release']['serving']['upstream'];pub=published[key]
        require(kept['n']==pub['n'] and abs(kept['acc']-pub['acc'])<1e-12,'Published release accuracy differs')
        require(abs(kept['brier']-pub['brier'])<1e-10 and abs(kept['ece10']-pub['ece'])<1e-10,'Published probability metrics differ')
        audit=json.loads(paths['local_audit'].read_text())['suites'][suite]
        local_expected=audit['release']['native'] if suite=='devtools-v1' else audit['native']
        got=comparison['populations']['release']['serving']['local']
        require(got['n']==local_expected['n'] and abs(got['acc']-local_expected['acc'])<1e-12 and all(abs(got[k]-local_expected[k])<1e-6 for k in ['brier','nll']) and abs(got['ece10']-local_expected['ece'])<1e-6,'Local audit mismatch')
        comparison.update(source_paths={k:str(v) for k,v in paths.items()},published_release_verified=True,local_audit_metrics_verified=True,local_softmax_reconstruction_deltas={k:got[k]-local_expected[('ece' if k=='ece10' else k)] for k in ['acc','brier','ece10','nll']},probability_metric_reconstruction_tolerance=1e-6);suites[suite]=comparison
    for p,h in inputs.items():require(sha(p)==h,'Input changed during comparison')
    report={'status':'VERIFIED_ORDERED_ROW_COMPARISON','inputs_sha256':inputs,'suites':suites,
            'scope':'Same ordered question identities and common-temperature numerical comparison. Does not establish hardware causality, upstream input-text identity, or Astra approval.'}
    out.parent.mkdir(parents=True,exist_ok=True)
    require(not out.exists(),'Preserve existing comparison output')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:{p:{'n':v['serving']['local']['n'],'flips':len(v['serving']['argmax_changes']),'max_delta':v['serving']['max_probability_delta']} for p,v in s['populations'].items()} for k,s in suites.items()}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/mnt/cephfs/xingchao'));parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();execute(args.root,args.out)
