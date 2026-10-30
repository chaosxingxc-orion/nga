#!/usr/bin/env python3
"""Initial Nimble v1 five-field adapter and full Typed Decisions token preflight.

This command never performs model inference. NativeFieldScorer is an unlaunched
forward implementation for subsequent reviewed inference wiring.
"""
import argparse,copy,fcntl,hashlib,json,os,sys,tempfile,threading,time
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
ADAPTER_SHA='ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b'
ADAPTER_REVISION='594dfdcfb6f94e3d0c0db7535180d3c71689169a'
BASE_REVISION='c202236235762e1c871ad0ccb60c8ee5ba337b9a'

def require(v,message):
    if not v:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def stamp(value,ordered=False):return hashlib.sha256(json.dumps(value,sort_keys=not ordered,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def atomic(path,value):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def request(raw):
    return {'state':json.loads(raw['state']),'questions':json.loads(raw['questions'])}
def candidate_keys(question):
    if question['type']=='noul':return ['false','true']
    if question['type']=='choice':return list(question['criteria'])
    require(question['type']=='score','Unsupported question type')
    return [str(i) for i in range(len(question['criteria']))]
def model_input(raw):
    """All fields retained; metadata/gold never enter this mapping."""
    req=request(raw);schema={}
    for name,q in req['questions'].items():
        require(set(q)<= {'type','instructions','criteria'},'Unexpected question fields')
        require(isinstance(q.get('instructions'),str) and q['instructions'].strip(),'Missing field definition')
        keys=candidate_keys(q);require(1<=len(keys)<=26,'Initial v1 supports at most 26 candidates')
        field={'description':q['instructions']}
        criteria=q.get('criteria')
        if q['type']=='noul':
            field.update(type='boolean',choices=[False,True]);descriptions=criteria or {}
        elif q['type']=='choice':
            field.update(type='enum',choices=keys);descriptions=criteria
        else:
            field.update(type='enum',choices=keys);descriptions=dict(zip(keys,criteria))
        require(all(k in keys and (v is None or isinstance(v,str)) for k,v in descriptions.items()),'Unsupported level definition')
        # Missing/null description remains absent, not the invented string "None".
        clean={k:v for k,v in descriptions.items() if v is not None}
        if clean:field['choice_descriptions']=clean
        schema[name]=field
    state=req['state'];context=state if isinstance(state,str) else json.dumps(state,ensure_ascii=False)
    return context,schema

def prepared_receipt(raw,index,prepared):
    req=request(raw);names=list(req['questions']);require(prepared.names==names,'Native field order differs')
    fields=[]
    for name,choices,ids,candidates in zip(prepared.names,prepared.choices,prepared.full_ids,prepared.candidate_ids):
        keys=[str(v).lower() if type(v)is bool else v for v in choices]
        require(keys==candidate_keys(req['questions'][name]),'Native candidate order differs')
        require(len(ids)<=2048 and len(candidates)==len(keys),'Native prompt shape differs')
        fields.append({'name':name,'candidate_keys':keys,'candidate_token_ids':candidates,
                       'tokens':len(ids),'prompt_token_sha256':stamp(ids,True)})
    require(len(fields)==len(names)==len(prepared.full_ids)==len(prepared.candidate_ids)==len(prepared.choices),'Native field count differs')
    return {'index':index,'id':raw['id'],'input_sha256':stamp(raw),'request_ordered_sha256':stamp(req,True),'fields':fields}

class NativeFieldScorer:
    """Native per-field projection with full shared schema; not yet runtime-admitted."""
    def __init__(self,model,tokenizer,prepare,projection,device='npu:0'):
        self.model,self.tokenizer,self.prepare,self.projection,self.device=model,tokenizer,prepare,projection,device
    def __call__(self,raw):
        import torch
        context,schema=model_input(raw);p=self.prepare(self.tokenizer,context,schema,2048,system_role=True)
        evidence=prepared_receipt(raw,0,p);probabilities={};logits={};outputs={}
        head=self.model.get_output_embeddings().weight
        with torch.inference_mode():
            for field,choices,ids,candidates in zip(evidence['fields'],p.choices,p.full_ids,p.candidate_ids):
                hidden=self.model.model(input_ids=torch.tensor([ids],device=self.device),use_cache=False).last_hidden_state[:,-1,:]
                z=self.projection(hidden,head,candidates)[0];prob=torch.softmax(z,dim=-1)
                keys=field['candidate_keys'];name=field['name'];logits[name]=dict(zip(keys,z.float().cpu().tolist()));probabilities[name]=dict(zip(keys,prob.cpu().tolist()));outputs[name]=choices[z.argmax().item()]
        return {'probabilities':probabilities,'logits':logits,'inference_temperature':1.0,'typed_output':outputs,'prompt_fields':evidence['fields']}

def required_files(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_reference_nimble.py','test_typed_reference_nimble.py','run.sh','LAUNCH_EXACT.sh'])
    for role in ['base','adapter','code']:
        needed.update(str(p.resolve()) for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    return needed

def preflight(c,rows,tokenizer,prepare,status):
    synth={'id':'synthetic','state':json.dumps({'text':'中文 nested state','nested':{'n':1}}),'questions':json.dumps({
        'route':{'type':'choice','instructions':'Choose route','criteria':{'a':None,'b':'second'}},
        'allow':{'type':'noul','instructions':'Allow?'},
        'level':{'type':'score','instructions':'Choose level','criteria':['low','medium','high']},
        'extra':{'type':'choice','instructions':'Choose extra','criteria':{'x':'first','y':''}},
        'flag':{'type':'noul','instructions':'Flag?','criteria':{'false':'absent','true':'present'}}})}
    ctx,schema=model_input(synth);p=prepare(tokenizer,ctx,schema,2048,system_role=True);prepared_receipt(synth,0,p)
    changed=copy.deepcopy(synth);qs=json.loads(changed['questions']);qs['route']['criteria']={'b':'second','a':None};changed['questions']=json.dumps(qs)
    cctx,cschema=model_input(changed);other=prepare(tokenizer,cctx,cschema,2048,system_role=True)
    require(p.full_ids!=other.full_ids,'Candidate discrimination failed')
    changed=copy.deepcopy(synth);changed.update(gold='hidden replacement',factors='hidden');ctx2,schema2=model_input(changed)
    require((ctx,schema)==(ctx2,schema2),'Gold leakage')
    items=[]
    for i,raw in enumerate(rows):
        context,schema=model_input(raw);prepared=prepare(tokenizer,context,schema,2048,system_role=True)
        items.append(prepared_receipt(raw,i,prepared));status['progress']=i+1
    return {'rows':len(items),'questions':sum(len(x['fields']) for x in items),'max_tokens':max(f['tokens'] for x in items for f in x['fields']),
            'items':items,'synthetic':{'fields':5,'gold_isolated':True,'candidate_discrimination':True},'scope':'Token-only full-schema preflight; no inference or metric result'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);a=ap.parse_args();path=Path(a.config);b=path.read_bytes();config_hash=hashlib.sha256(b).hexdigest();c=json.loads(b);out=Path(c['out'])
    with (out/'driver.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);require(not(out/'COMPLETE.json').exists(),'Existing terminal preserved')
        status={'stage':'verify','progress':0,'total':400,'chips':0};stop=threading.Event()
        def heartbeat():
            while not stop.wait(10):
                snap={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',snap)
                with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(snap)+'\n')
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start();rc=1;error=None;outputs={}
        try:
            require(c['mode']=='preflight_only','Only preflight is admitted');require(c['max_length']==2048 and c['temperature']==1.0,'Native protocol changed')
            require(required_files(c)<=set(c['files']),'Required dependency omitted')
            for p,h in c['files'].items():require(sha(p)==h,'Frozen input changed '+p)
            require(c['adapter_revision']==ADAPTER_REVISION and sha(Path(c['adapter'])/'adapter_model.safetensors')==ADAPTER_SHA,'Wrong initial adapter')
            require(c['base_revision']==BASE_REVISION and Path(c['base'],'.complete').read_text().splitlines()[0]==BASE_REVISION,'Wrong original base')
            require(sha(c['data'])==DATA_SHA,'Wrong dataset')
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TORCH_DEVICE_BACKEND_AUTOLOAD='0');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
            import pyarrow.parquet as pq
            from transformers import AutoTokenizer
            from nimble.scoring.release_contract import prompt_builder
            from nimble.scoring.parallel_schema import prepare_prompts
            tok=AutoTokenizer.from_pretrained(c['adapter'],local_files_only=True);prepare=prompt_builder(c['adapter'],tok)
            require(prepare is prepare_prompts,'Expected original v1 prompt contract')
            rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Wrong full population')
            for row in rows:
                req=request(row);gold=json.loads(row['gold']);require(row['split']=='test' and len(req['questions'])==5 and list(req['questions'])==list(gold),'Wrong question population')
                for name,q in req['questions'].items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(candidate_keys(q)),'Gold candidate coverage differs')
            status['stage']='whole_test_token_preflight';report=preflight(c,rows,tok,prepare,status);report.update(config_sha256=config_hash,data_sha256=DATA_SHA)
            for p,h in c['files'].items():require(sha(p)==h,'Frozen input changed '+p)
            require(sha(path)==config_hash,'Config changed during execution');atomic(out/'PREFLIGHT.json',report);outputs['PREFLIGHT.json']=sha(out/'PREFLIGHT.json');rc=0;status['stage']='completed'
        except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
        finally:
            stop.set();thread.join();terminal={'rc':rc,'error':error,'config_sha256':config_hash,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',terminal);atomic(out/'COMPLETE.json',terminal)
if __name__=='__main__':main()
