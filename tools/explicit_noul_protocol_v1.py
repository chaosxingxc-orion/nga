"""Explicit Noul definitions preserved in a versioned single-question protocol.

This is source-formula compatibility, not a Tacit inference implementation.
The strict summary wrapper adds identity/completeness checks; it never launches a model.
"""
from __future__ import annotations
import hashlib,json,math

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def bev_items(rows):
    out=[]
    for row in rows:
        try: qs=json.loads(row['questions_json'])
        except Exception: continue
        # Intentionally matches upstream failure for parsed non-object values.
        for qid,spec in qs.items():
            kind,crit,lab=spec.get('type'),spec.get('criteria'),spec.get('label')
            try:
                if kind=='choice':
                    if not isinstance(crit,dict) or not 2<=len(crit)<=26 or lab not in crit: continue
                    keys=list(crit);options=[str(crit[k]) for k in keys]
                    if len(set(options))!=len(options): continue
                    y=keys.index(lab)
                elif kind=='noul':
                    if not isinstance(lab,bool): continue
                    options=['Yes','No']; y=0 if lab else 1
                elif kind=='score':
                    if not isinstance(crit,list) or not 2<=len(crit)<=10: continue
                    if not isinstance(lab,int) or not 0<=lab<len(crit): continue
                    options=[str(x) for x in crit];y=lab
                else: continue
                instruction=spec['instructions']
                if kind=='noul' and crit is not None:
                    if not (type(crit) is dict and set(crit)=={'true','false'} and all(type(v) is str and v for v in crit.values())):
                        raise ValueError('explicit Noul definitions require true and false')
                    # Same definition rendering as the accepted Typed single-question
                    # adapter; fixed Yes/No tokens and inference arithmetic unchanged.
                    instruction += '\nCandidate definitions (true = Yes; false = No):\n' + json.dumps(crit,ensure_ascii=False,separators=(',',':'))
            except Exception: continue
            out.append(dict(i=len(out),qid=qid,y=y,state=row['state'],question=instruction,options=options,kind={'noul':'yes_no'}.get(kind,kind)))
    return out

PROTOCOL = 'nga-explicit-noul-bound-summary-v1'

def sha256_value(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def require(ok, why):
    if not ok: raise ValueError(why)

def pin(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def request_hash(item):
    # Gold-free request identity includes ordinal/qid and option order.
    return sha256_value({k:v for k,v in item.items() if k != 'y'})

def validate_items(items):
    require(type(items) is list and bool(items), 'empty or invalid population')
    for i,item in enumerate(items):
        require(type(item) is dict and type(item.get('i')) is int and item['i']==i, 'invalid ordinal identity')
        require(type(item.get('qid')) is str and bool(item['qid']), 'invalid qid')
        require(type(item.get('state')) is str and type(item.get('question')) is str, 'invalid request text')
        opts=item.get('options')
        require(type(opts) is list and 2<=len(opts)<=26 and all(type(x) is str for x in opts), 'invalid options')
        require(item.get('kind') in ('choice','yes_no','score'), 'invalid kind')
        require(type(item.get('y')) is int and 0<=item['y']<len(opts), 'invalid gold index')

def make_contract(items, *, source_sha256, model_sha256, runtime_protocol_sha256, tau=0.5):
    """Preparation helper. Caller must freeze and externally pin BEFORE inference.

Hash equality establishes identity, not authorship or trusted pre-registration.
The raw mapper preserves upstream bool-score-label behavior; strict records reject
that ambiguous label type. Nonfinite native margins are also deliberately rejected.
"""
    validate_items(items)
    require(type(tau) in (int,float) and math.isfinite(tau) and tau>=0, 'invalid tau')
    require(all(pin(x) for x in (source_sha256,model_sha256,runtime_protocol_sha256)), 'invalid source/model/runtime pin')
    return dict(schema=PROTOCOL, count=len(items), items_sha256=sha256_value(items),
                source_sha256=source_sha256,model_sha256=model_sha256,
                runtime_protocol_sha256=runtime_protocol_sha256,tau=tau)

def summarise(items,rows,*,contract,contract_sha256):
    """Native arithmetic under an externally pinned, complete population contract.

Prediction producer must emit contract_sha256/request_sha256 at inference time.
This function cannot authenticate the caller's expected contract pin; attaching
new identities to old upstream predictions is not evidence of native execution.
"""
    require(pin(contract_sha256) and sha256_value(contract)==contract_sha256, 'contract pin differs')
    expected=make_contract(items,source_sha256=contract['source_sha256'],model_sha256=contract['model_sha256'],runtime_protocol_sha256=contract['runtime_protocol_sha256'],tau=contract['tau'])
    require(sha256_value(contract)==sha256_value(expected),'population or protocol contract differs')
    tau=contract['tau']
    require(type(rows) is list and len(rows)==len(items), 'incomplete population')
    for i,(item,row) in enumerate(zip(items,rows)):
        require(type(row) is dict and type(row.get('i')) is int and row['i']==i and type(row.get('y')) is int and row['y']==item['y'] and row.get('qid')==item['qid'], 'identity/order/gold mismatch')
        require(row.get('contract_sha256')==contract_sha256 and row.get('request_sha256')==request_hash(item), 'prediction input/protocol binding differs')
        for key in ('index','first_index'):
            require(type(row.get(key)) is int and 0<=row[key]<len(item['options']), 'invalid predicted index')
        require(row.get('route') in ('one_forward','cot'),'invalid native route')
        require(type(row.get('reasoning_tokens')) is int and row['reasoning_tokens']>=0, 'invalid token count')
        margin=row.get('first_margin')
        require(type(margin) in (int,float) and math.isfinite(margin) and margin>=0, 'invalid finite nonnegative margin')
        if row['route']=='one_forward':
            require(row['index']==row['first_index'] and row['reasoning_tokens']==0,'inconsistent one_forward record')
        else:
            require(margin<tau,'cot without strict below-tau eligibility')
    cot=[r for r in rows if r['route']=='cot'];n=len(rows)
    return dict(n=n,one_forward=dict(correct=sum(r['first_index']==r['y'] for r in rows)),
      adaptive=dict(correct=sum(r['index']==r['y'] for r in rows),escalated=len(cot),below_tau=sum(r['first_margin']<tau for r in rows),reasoning_tokens=sum(r['reasoning_tokens'] for r in rows)),
      escalated_decisions=dict(correct_before=sum(r['first_index']==r['y'] for r in cot),correct_after=sum(r['index']==r['y'] for r in cot)))

if __name__=='__main__':
    import argparse,pathlib
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--items',required=True)
    ap.add_argument('--predictions',required=True)
    ap.add_argument('--contract',required=True,help='Prospectively frozen population/model/runtime contract')
    ap.add_argument('--contract-sha256',required=True,help='Externally trusted canonical contract pin')
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    ip=pathlib.Path(a.items);rp=pathlib.Path(a.predictions);cp=pathlib.Path(a.contract)
    ir,rr,cr=ip.read_bytes(),rp.read_bytes(),cp.read_bytes()
    report=summarise(json.loads(ir),json.loads(rr),contract=json.loads(cr),contract_sha256=a.contract_sha256)
    report.update(protocol=PROTOCOL,contract_sha256=a.contract_sha256,items_file_sha256=hashlib.sha256(ir).hexdigest(),predictions_file_sha256=hashlib.sha256(rr).hexdigest(),contract_file_sha256=hashlib.sha256(cr).hexdigest(),native_runtime_equivalence=False,scientific_acceptance=False)
    with open(a.output,'x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
