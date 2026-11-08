"""Compare identity-bound ordered vector records, emitting complete candidate deltas."""
import json, math, sys

def compare(ref, new):
    if len(ref)!=len(new): raise ValueError('row count mismatch')
    if not ref: raise ValueError('empty rows')
    for records in (ref, new):
        seen=set()
        for row in records:
            if not isinstance(row,dict) or any(k not in row for k in ('key','candidate_ids','token_ids','gold','scores')): raise ValueError('missing fields')
            key=row['key']
            if not isinstance(key,str) or not key or key in seen: raise ValueError('missing or duplicate key')
            seen.add(key)
            ids, tokens, scores = row['candidate_ids'], row['token_ids'], row['scores']
            if not isinstance(ids,list) or not ids or len(ids)!=len(tokens) or len(ids)!=len(scores): raise ValueError('candidate dimensions')
            if any(not isinstance(c,str) or not c for c in ids) or len(set(ids))!=len(ids): raise ValueError('invalid candidate ids')
            if any(not isinstance(t,list) or not t or any(type(i) is not int or i<0 for i in t) for t in tokens): raise ValueError('invalid token ids')
            if type(row['gold']) is not int or not 0 <= row['gold'] < len(ids): raise ValueError('invalid gold')
            if any(type(s) not in (float,int) or not math.isfinite(s) for s in scores): raise ValueError('nonfinite or invalid score')
    details=[]; flips=[]; counts={str(x):0 for x in (0.001,0.01,0.1)}; failed=False
    for a,b in zip(ref,new):
        for k in ('key','candidate_ids','token_ids','gold'):
            if a[k]!=b[k]: raise ValueError('identity/order mismatch: '+k)
        x,y=a['scores'],b['scores']
        if not x or len(x)!=len(y) or len(x)!=len(a['candidate_ids']): raise ValueError('candidate dimensions')
        if not all(math.isfinite(v) for v in x+y): raise ValueError('nonfinite')
        groups={}
        for i,t in enumerate(a['token_ids']): groups.setdefault(tuple(t),[]).append(i)
        duplicates=[g for g in groups.values() if len(g)>1]
        if any(any(y[i]!=y[g[0]] or x[i]!=x[g[0]] for i in g) for g in duplicates): failed=True
        ia=max(range(len(x)),key=x.__getitem__); ib=max(range(len(y)),key=y.__getitem__)
        def gap(v):
            z=sorted(v,reverse=True);return z[0]-z[1] if len(z)>1 else math.inf
        ga,gb=gap(x),gap(y)
        for t in (0.001,0.01,0.1): counts[str(t)]+=ga<=t
        ds=[v-u for u,v in zip(x,y)]
        if max(map(abs,ds))>1e-3: failed=True
        if ia!=ib:
            flips.append({'key':a['key'],'reference':ia,'prototype':ib,'reference_margin':ga if math.isfinite(ga) else None,'prototype_margin':gb if math.isfinite(gb) else None})
            if ga>0.002: failed=True
        details.append({'key':a['key'],'candidates':[{'id':c,'tokens':len(t),'delta':d} for c,t,d in zip(a['candidate_ids'],a['token_ids'],ds)],'duplicates':duplicates,'reference_exact_tie':ga==0,'prototype_exact_tie':gb==0,'reference_r0_correct':ia==a['gold'] and ga!=0,'prototype_r0_correct':ib==a['gold'] and gb!=0})
    return {'pass':not failed,'near_ties':counts,'flips':flips,'rows':details}

if __name__=='__main__':
    with open(sys.argv[1]) as f: a=json.load(f)
    with open(sys.argv[2]) as f: b=json.load(f)
    result=compare(a,b); print(json.dumps(result,indent=2,allow_nan=False));sys.exit(0 if result['pass'] else 1)
