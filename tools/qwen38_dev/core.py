"""DEV-only data, encoding, score and durable item helpers."""
import hashlib, json, math, os, tempfile
from pathlib import Path
import prompt

def digest_bytes(b): return hashlib.sha256(b).hexdigest()
def digest(obj): return digest_bytes(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
def put(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.pending-')
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            json.dump(obj,f,sort_keys=True,ensure_ascii=False,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(d)
        finally: os.close(d)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def read_dev(mask,root):
    result={}
    if set(mask)!={f'{s}/{n}' for s in ('decision-v7','transfer-v4') for n in ('dev','dev.variants')}: raise ValueError('DEV mask suite mismatch')
    for key,entry in sorted(mask.items()):
        suite,name=key.split('/'); path=Path(root)/suite/(name+'.jsonl')
        data=path.read_bytes()
        if digest_bytes(data)!=entry['source_sha256']: raise ValueError('DEV file hash mismatch: '+key)
        lines=data.splitlines(); records=entry['rows']
        if len(lines)!=len(records): raise ValueError('DEV count mismatch: '+key)
        rows=[]
        for m in records:
            i=m['row']
            if i!=len(rows) or digest_bytes(lines[i])!=m['sha256']: raise ValueError('DEV row mismatch: '+key)
            row=json.loads(lines[i])
            if any(row.get(k)!=m[k] for k in ('group_id','variant','qname')): raise ValueError('DEV identity mismatch')
            validate_row(row); rows.append(row)
        result[key]=rows
    return result

def validate_row(row):
    ids=[x['id'] for x in row['levels']]; names=[x['name'] for x in row['levels']]
    if not ids or len(set(ids))!=len(ids) or len(set(names))!=len(names) or row['gold'] not in ids: raise ValueError('invalid candidate IDs, names or gold')
    return ids

def encode(row,tok,mode='full'):
    validate_row(row)
    if mode=='blank': row=prompt.blank_input(row)
    elif mode=='drop': row=prompt.drop_input(row)
    elif mode!='full': raise ValueError('unknown mode')
    p=prompt.build_prompt(row,'record_name')
    pre=tok(p.text,add_special_tokens=False)['input_ids']
    candidates=[tok(c,add_special_tokens=False)['input_ids'] for c in p.candidates]
    if not pre or any(not c for c in candidates): raise ValueError('empty prefix or candidate')
    return p,pre,candidates

def continuation_sum(logits, seq, prefix_length):
    """logits are the final n+1 rows, like HFScorer; log-softmax in fp32."""
    import torch
    n=len(seq)-prefix_length
    if prefix_length<1 or n<1 or logits.ndim!=2 or logits.shape[0]!=n+1: raise ValueError('logit/sequence length mismatch')
    logp=torch.log_softmax(logits.float(),dim=-1)
    return sum(float(logp[q,seq[prefix_length+q]]) for q in range(n))

def expected(row,key,index,mode,run_id):
    ids=validate_row(row)
    return dict(run_identity=run_id,source_key=key,row=index,row_sha256=digest(row),group_id=row['group_id'],variant=row['variant'],qname=row['qname'],mode=mode,candidate_ids=ids,candidate_names=[x['name'] for x in row['levels']],gold_id=row['gold'],gold_index=ids.index(row['gold']))

def validate_record(record,ident):
    if any(record.get(k)!=v for k,v in ident.items()): raise ValueError('resume identity, candidate order or gold mismatch')
    n=len(ident['candidate_ids']); scores=record.get('raw_scores'); lengths=record.get('candidate_lengths')
    if not isinstance(scores,list) or len(scores)!=n or not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) for x in scores): raise ValueError('bad scores')
    if not isinstance(lengths,list) or len(lengths)!=n or not all(type(x)==int and x>0 for x in lengths) or type(record.get('prefix_length'))!=int or record['prefix_length']<1: raise ValueError('bad lengths')
    return record

def load_completed(path,ident):
    path=Path(path)
    if not path.exists(): return None
    return validate_record(json.loads(path.read_text()),ident)

def record_attempt(state, kind, name, events, progress):
    import time
    state[kind] += 1
    with Path(events).open("a") as f:
        f.write(json.dumps({"event":kind,"item":name,"utc":time.time()})+"\n"); f.flush(); os.fsync(f.fileno())
    put(progress,dict(state))
