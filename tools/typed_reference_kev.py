#!/usr/bin/env python3
"""E26 native Kev Typed Decisions: full token preflight or frozen inference."""
import argparse,copy,fcntl,hashlib,importlib.util,json,math,os,sys,tempfile,threading,time
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
SCORER_SHA='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'
CONTEXT={'max_state':8192,'max_branch':8192,'max_packed':16384}
def require(v,m):
    if not v:raise ValueError(m)
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def objsha(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def orderedsha(x):return hashlib.sha256(json.dumps(x,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic(p,x):
    p=Path(p);fd,t=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
    with os.fdopen(fd,'w') as f:json.dump(x,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.chmod(t,0o644);os.replace(t,p)
def keys(q):
    if q['type']=='choice':return list(q['criteria'])
    if q['type']=='noul':return ['false','true']
    require(q['type']=='score','Unsupported type');return list(map(str,range(len(q['criteria']))))
def request(raw):
    qs=json.loads(raw['questions']);require(all(set(q)<= {'type','instructions','criteria'} for q in qs.values()),'Unexpected question input fields')
    return {'state':json.loads(raw['state']),'questions':qs}
def inference_record(raw):
    r=request(raw)
    for q in r['questions'].values():q.update(label=keys(q)[0] if q['type']=='choice' else 0,src='typed-decisions')
    return r
def dataset(c):
    import pyarrow.parquet as pq
    require(digest(c['data'])==DATA_SHA,'Wrong typed test')
    rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Wrong cases')
    for r in rows:
        q=request(r)['questions'];g=json.loads(r['gold']);require(r['split']=='test' and len(q)==5 and list(q)==list(g),'Question population/order differs')
        for name,x in q.items():require(g[name]['type']==x['type'] and set(g[name]['probabilities'])==set(keys(x)),'Gold candidates differ')
    return rows
def validate_prediction(raw,p,temp):
    qs=request(raw)['questions'];require(list(p['probabilities'])==list(p['logits'])==list(qs),'Wrong question order/set')
    require(p['inference_temperature']==temp,'Wrong temperature')
    for name,q in qs.items():
        pp,zz=p['probabilities'][name],p['logits'][name];require(list(pp)==list(zz)==keys(q),'Wrong candidate order')
        require(all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in pp.values()),'Invalid probability')
        require(all(type(v)in(int,float) and math.isfinite(v) for v in zz.values()),'Invalid logit')
        require(abs(sum(pp.values())-1)<1e-5,'Invalid mass');e=[math.exp(v-max(zz.values())) for v in zz.values()]
        require(max(abs(a/sum(e)-b) for a,b in zip(e,pp.values()))<1e-5,'Probability/logit mismatch')
def receipt(path,raw,index,identity,temp):
    e=json.loads(Path(path).read_text());v=e['payload'];require(objsha(v)==e['sha256'],'Receipt hash mismatch')
    require(v['index']==index and v['id']==raw['id'] and v['identity']==identity and v['input_sha256']==objsha(raw) and v['request_ordered_sha256']==orderedsha(request(raw)),'Foreign receipt')
    validate_prediction(raw,v['prediction'],temp);return v
def native_score(rows,predictions,temp,score_one):
    cells=[]
    for r,p in zip(rows,predictions):
        gold=json.loads(r['gold'])
        for q,g in gold.items():
            z=p['logits'][q];z={k:v*p['inference_temperature']/temp for k,v in z.items()};e={k:math.exp(v-max(z.values())) for k,v in z.items()};dist={k:v/sum(e.values()) for k,v in e.items()}
            if temp==p['inference_temperature']:dist=p['probabilities'][q]
            ok,kl,brier,conf=score_one({'probabilities':dist},g)
            cells.append({'workflow':r['workflow'],'type':g['type'],'ok':ok,'kl':kl,'brier':brier,'conf':conf})
    def summary(xs):
        n=len(xs);ece=0.
        for b in range(10):
            group=[x for x in xs if min(int(x['conf']*10),9)==b]
            if group:ece+=len(group)/n*abs(sum(x['ok'] for x in group)/len(group)-sum(x['conf'] for x in group)/len(group))
        return {'n':n,'accuracy':sum(x['ok'] for x in xs)/n,'kl_from_gold':sum(x['kl'] for x in xs)/n,'brier':sum(x['brier'] for x in xs)/n,'ece10':ece}
    overall=summary(cells)
    return {'original_arithmetic_raw_readout':overall,'strict':{'expected':len(cells),'returned':len(cells),'valid':len(cells),'invalid':0,'unsupported':0,'overlength':0,'failed':0,**overall},
            'by_type':{k:summary([x for x in cells if x['type']==k]) for k in sorted({x['type'] for x in cells})},'by_workflow':{k:summary([x for x in cells if x['workflow']==k]) for k in sorted({x['workflow'] for x in cells})}}
def closure(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_reference_kev.py','verify_typed_reference.py','run.sh','LAUNCH_EXACT.sh'])
    for role in ['base','checkpoint','kev_code']:
        needed.update(str(p.resolve()) for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    require(needed<=set(c['files']),'Missing frozen dependency');return len(needed)
def verify_files(c):
    closure(c)
    for p,h in c['files'].items():require(digest(p)==h,'Frozen file changed: '+p)
def preflight(c,rows,status):
    from transformers import AutoTokenizer
    from kev.api import SystemOneRequest,to_record
    from kev.model import encode
    tok=AutoTokenizer.from_pretrained(c['base'],local_files_only=True);items=[]
    synthetic={'state':{'nested':{'message':'中文 synthetic observation'}},'questions':{
        'a':{'type':'choice','instructions':'Choose a label','criteria':{'alpha':None,'beta':'second'}},
        'b':{'type':'noul','instructions':'Is the observation present?'},
        'c':{'type':'score','instructions':'Choose level','criteria':['low','medium','high']},
        'd':{'type':'choice','instructions':'Choose another label','criteria':{'x':'','y':'other'}},
        'e':{'type':'noul','instructions':'Needs review?','criteria':{'false':'No','true':'Yes'}}}}
    def encoded(req):
        internal,mapping=to_record(SystemOneRequest.model_validate(req));return encode(tok,internal,max_state=8192,max_branch=8192,strict=True),mapping
    first,mapping=encoded(synthetic);changed=copy.deepcopy(synthetic);changed['questions']['a']['criteria']={'beta':'second','alpha':None};second,changed_mapping=encoded(changed)
    require(first['ids']!=second['ids'] and mapping[0]['keys']!=changed_mapping[0]['keys'],'Candidate discrimination failed')
    require([x['keys'] for x in mapping]==[['alpha','beta'],['false','true'],['0','1','2'],['x','y'],['false','true']],'Synthetic typed mapping failed')
    for i,r in enumerate(rows):
        rec,meta=to_record(SystemOneRequest.model_validate(request(r)));enc=encode(tok,rec,max_state=8192,max_branch=8192,strict=True,option_isolation=False)
        require(len(enc['ids'])<=16384,'Packed context overflow')
        items.append({'index':i,'id':r['id'],'input_sha256':objsha(r),'request_ordered_sha256':orderedsha(request(r)),'tokens':len(enc['ids']),'tokens_sha256':orderedsha(enc['ids']),'state_tokens':enc['state_tokens'],'candidate_keys':[m['keys'] for m in meta]});status['progress']=i+1
    return {'synthetic_compile':{'question_count':5,'candidate_discrimination':True,'tokens':len(first['ids'])},'rows':len(rows),'questions':sum(len(request(r)['questions']) for r in rows),'items':items,'max_tokens':max(x['tokens'] for x in items),'context':CONTEXT}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--mode',choices=['preflight','inference'],required=True);a=ap.parse_args();config_bytes=Path(a.config).read_bytes();config_hash=hashlib.sha256(config_bytes).hexdigest();c=json.loads(config_bytes);out=Path(c['out']);out.mkdir(exist_ok=True)
    lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);terminal=out/(a.mode+'-COMPLETE.json');require(not terminal.exists(),'Existing terminal preserved')
    status={'stage':'verify','progress':0,'total':400,'chips':int(a.mode=='inference')};stop=threading.Event()
    def heartbeat():
        while not stop.wait(10):
            v={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',v)
            with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(v)+'\n')
    t=threading.Thread(target=heartbeat,daemon=True);t.start();rc=1;outputs={}
    try:
        require(digest(a.config)==config_hash,'Config changed before execution');require(c['context']==CONTEXT,'Context changed');require(a.mode=='preflight' or c.get('mode')=='inference','Config is not preregistered for inference');verify_files(c);require(digest(c['scorer'])==SCORER_SHA,'Wrong scorer');rows=dataset(c);identity=objsha(c)
        sys.path.insert(0,c['kev_code']);status['stage']='token_preflight';pre=preflight(c,rows,status);pre.update(identity=identity,data_sha256=DATA_SHA);atomic(out/'PREFLIGHT.json',pre);outputs['PREFLIGHT.json']=digest(out/'PREFLIGHT.json')
        if a.mode=='inference':
            import torch,torch_npu
            torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False;torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8)
            from kev.checkpoint import Checkpoint,LoadOptions
            import kev.predictors as predictors
            from kev.api import SystemOneRequest,to_record,to_answers
            meta=torch.load(Path(c['checkpoint'])/'head.pt',map_location='cpu',weights_only=True)
            require((meta['base'],meta['base_revision'],meta['temperature'])==(c['base_id'],c['base_revision'],c['temperature']),'Checkpoint metadata differs')
            require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base revision differs')
            ck=Checkpoint(c['checkpoint']);ck.meta.base,ck.meta.base_revision=c['base'],None;predictors.Checkpoint=lambda _:ck;predictors.sync=lambda _:torch.npu.synchronize()
            model=predictors.LocalPredictor(c['checkpoint'],'npu:0',LoadOptions(dtype=torch.float32,attn='eager',merge=True),context=CONTEXT)
            atomic(out/'ENVIRONMENT.json',{'temperature':model.temperature,'model':model.environment,'base_id':meta['base'],'base_revision':meta['base_revision'],'head_sha256':digest(Path(c['checkpoint'])/'head.pt')})
            folder=out/'records';folder.mkdir(exist_ok=True);require(all(p.name in {f'{i:06d}.json' for i in range(400)} for p in folder.glob('*.json')),'Extra receipts');preds=[];elapsed=0.;count=0;status.update(stage='inference',progress=0)
            for i,r in enumerate(rows):
                path=folder/f'{i:06d}.json'
                if path.exists():v=receipt(path,r,i,identity,c['temperature'])
                else:
                    started=time.monotonic();pred=model(inference_record(r));validate_prediction(r,pred,c['temperature']);duration=time.monotonic()-started
                    _,mapping=to_record(SystemOneRequest.model_validate(request(r)));wire=to_answers([list(pred['probabilities'][q].values()) for q in request(r)['questions']],mapping)
                    v={'index':i,'id':r['id'],'identity':identity,'input_sha256':objsha(r),'request_ordered_sha256':orderedsha(request(r)),'prediction':pred,'wire_answers':wire,'seconds':duration};atomic(path,{'payload':v,'sha256':objsha(v)});elapsed+=duration;count+=5
                preds.append(v['prediction']);status.update(progress=i+1,questions_per_second_per_chip=count/elapsed if elapsed else None,reserved_gib=torch.npu.memory_reserved()/2**30)
            s=importlib.util.spec_from_file_location('original_scorer',c['scorer']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
            report={'identity':identity,'rows':400,'questions':2000,'serving':native_score(rows,preds,c['temperature'],m.score_one),'raw_T1':native_score(rows,preds,1.,m.score_one),'wire_scope':'Preserved exact native wire answers; noul has no probabilities, so original wire scorer is incompatible. Serving metrics use stored native probabilities; T1 uses reconstructed logits.'}
            atomic(out/'report.json',report);outputs['report.json']=digest(out/'report.json')
        verify_files(c);require(digest(a.config)==config_hash,'Config changed during execution');status['stage']='completed';rc=0
    finally:
        stop.set();t.join();atomic(out/'STATUS.json',status);atomic(terminal,{'rc':rc,'config_sha256':config_hash,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status});lock.close()
if __name__=='__main__':main()
