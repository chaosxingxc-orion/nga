#!/usr/bin/env python3
"""E29 native Open-Jev typed reference probe/inference with immutable item receipts."""
import argparse,fcntl,hashlib,importlib.util,json,math,os,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from typed_openjev_preflight import DATA_SHA,atomic,compile_five,encode,keys,request,require,sha,stamp,synthetic
SCORER_SHA='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'
SCRIPTS=['typed_openjev_preflight.py','typed_openjev_inference.py','verify_typed_openjev.py','typed_openjev_finish.py','prepare_typed_openjev.py']
def required_files(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in SCRIPTS+['run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
    essentials={'base':['.complete','config.json','tokenizer.json'],'checkpoint':['model.json','temperature.json','head.pt','adapter/adapter_config.json','adapter/adapter_model.safetensors'],'code':['jev/api.py','jev/model.py','jev/metrics.py']}
    for role,names in essentials.items():
        root=Path(c[role]);require(root.is_dir(),'Missing dependency directory '+role)
        for n in names:require((root/n).is_file(),'Missing loader file '+str(root/n))
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    require(any(Path(c['base']).glob('*.safetensors')),'Missing base weights');return needed

def probabilities(z,temp):
    require(type(temp)in(int,float) and math.isfinite(temp) and temp>0,'Invalid temperature')
    require(z and all(type(v)in(int,float) and math.isfinite(v) for v in z),'Invalid logits')
    e=[math.exp((v-max(z))/temp) for v in z];return [v/sum(e) for v in e]

def prediction(raw,p,fields,temp):
    qs=request(raw)['questions'];require(list(p['probabilities'])==list(p['logits'])==list(qs),'Question order differs')
    require(p['inference_temperature']==temp and p['prompt_fields']==fields,'Prompt/temperature differs')
    for name,q in qs.items():
        ks=keys(q);prob,z=p['probabilities'][name],p['logits'][name];require(list(prob)==list(z)==ks,'Candidate order differs')
        expected=probabilities(list(z.values()),temp)
        require(all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in prob.values()) and abs(sum(prob.values())-1)<1e-6,'Invalid probabilities')
        require(all(abs(prob[k]-v)<1e-9 for k,v in zip(ks,expected)),'Probability/logit differs')
    require(p['input_tokens']==sum(sum(f['lengths']) for f in fields),'Input token count differs')

def receipt(envelope,raw,index,identity,fields,temp):
    v=envelope['payload'];require(stamp(v)==envelope['sha256'],'Receipt checksum differs')
    require(v['identity']==identity and v['index']==index and v['id']==raw['id'] and v['input_sha256']==stamp(raw) and v['request_sha256']==stamp(request(raw)),'Foreign receipt')
    require(type(v['seconds'])in(int,float) and math.isfinite(v['seconds']) and v['seconds']>0,'Invalid duration')
    prediction(raw,v['prediction'],fields,temp);return v

class TokenRecorder:
    """Observe the exact native tokenizer output consumed by each forward."""
    def __init__(self,tokenizer):self.inner=tokenizer;self.calls=[]
    def __getattr__(self,name):return getattr(self.inner,name)
    def __call__(self,*args,**kwargs):
        result=self.inner(*args,**kwargs)
        require(kwargs.get('truncation') is False and kwargs.get('padding') is True and kwargs.get('return_tensors')=='pt','Native tokenization changed')
        ids=result['input_ids'].tolist();masks=result['attention_mask'].tolist();clean=[]
        for row,mask in zip(ids,masks):
            n=sum(mask);require(mask==[1]*n+[0]*(len(mask)-n),'Native padding changed');clean.append(row[:n])
        self.calls.append(clean);return result

class NativeScorer:
    def __init__(self,model,compile_request,candidate_prompts,format_response,temp):
        self.model=model;self.compile=compile_request;self.prompts=candidate_prompts;self.format=format_response;self.temp=temp
        self.tokenizer=model.tokenizer;self.recorder=TokenRecorder(self.tokenizer);self.model.tokenizer=self.recorder
    def __call__(self,raw):
        import torch
        fields=encode(raw,self.tokenizer,self.compile,self.prompts);records=compile_five(raw,self.compile);zs={};ps={};total=0
        with torch.inference_mode():
            for record,field in zip(records,fields):
                self.recorder.calls=[];output=self.model([record]);require(len(output)==1 and len(self.recorder.calls)==1,'Native forward call shape changed')
                actual=self.recorder.calls[0];require([len(x) for x in actual]==field['lengths'] and [stamp(x) for x in actual]==field['token_sha256'],'Actual native tokens differ')
                require(self.model.last_input_tokens==sum(field['lengths']),'Native token total differs')
                z=output[0].float().cpu().tolist();require(len(z)==len(record['answer_keys']),'Native candidate output differs')
                prob=probabilities(z,self.temp);zs[record['id']]=dict(zip(record['answer_keys'],z));ps[record['id']]=dict(zip(record['answer_keys'],prob));total+=self.model.last_input_tokens
        value=dict(probabilities=ps,logits=zs,inference_temperature=self.temp,prompt_fields=fields,input_tokens=total,wire_response=self.format(records,[list(ps[r['id']].values()) for r in records]))
        prediction(raw,value,fields,self.temp);return value

def summarize(rows,preds,temp,score_one):
    cells=[]
    for row,pred in zip(rows,preds):
        for name,gold in json.loads(row['gold']).items():
            prob=pred['probabilities'][name] if temp==pred['inference_temperature'] else dict(zip(pred['logits'][name],probabilities(list(pred['logits'][name].values()),temp)))
            ok,kl,brier,conf=score_one({'probabilities':prob},gold);cells.append(dict(ok=ok,kl=kl,brier=brier,conf=conf,type=gold['type'],workflow=row['workflow']))
    def aggregate(xs):
        n=len(xs);bins=[[] for _ in range(10)]
        for x in xs:bins[min(int(x['conf']*10),9)].append(x)
        return dict(n=n,accuracy=sum(x['ok'] for x in xs)/n,kl_from_gold=sum(x['kl'] for x in xs)/n,brier=sum(x['brier'] for x in xs)/n,ece10=sum(abs(sum(x['ok']-x['conf'] for x in b))/n for b in bins))
    overall=aggregate(cells)
    return dict(original_arithmetic_raw_readout=overall,strict=dict(expected=len(cells),returned=len(cells),valid=len(cells),invalid=0,unsupported=0,overlength=0,failed=0,**overall),by_type={k:aggregate([x for x in cells if x['type']==k]) for k in sorted({x['type'] for x in cells})},by_workflow={k:aggregate([x for x in cells if x['workflow']==k]) for k in sorted({x['workflow'] for x in cells})})

def probe(scorer,identity,status):
    import torch
    raw=synthetic();passes=[]
    for i in range(2):
        torch.npu.synchronize();start=time.monotonic();pred=scorer(raw);torch.npu.synchronize();seconds=time.monotonic()-start
        require(math.isfinite(seconds) and seconds>0,'Invalid probe timing');passes.append(dict(prediction=pred,seconds=seconds));status.update(stage='synthetic_probe',progress=i+1,total=2,questions_per_second_per_chip=5/seconds,reserved_gib=torch.npu.memory_reserved()/2**30)
    a,b=[x['prediction'] for x in passes];require(a['prompt_fields']==b['prompt_fields'],'Probe prompt drift')
    delta=max(abs(a['probabilities'][q][k]-b['probabilities'][q][k]) for q in a['probabilities'] for k in a['probabilities'][q]);require(delta<=1e-5,'Probe repeat drift')
    return dict(identity=identity,request=request(raw),request_sha256=stamp(request(raw)),passes=passes,max_probability_delta=delta,chips=1,questions_per_pass=5,reserved_gib=torch.npu.memory_reserved()/2**30)

def run(path):
    blob=path.read_bytes();ch=hashlib.sha256(blob).hexdigest();c=json.loads(blob);out=Path(c['out']);mode=c['mode'];require(mode in ('probe','inference'),'Invalid mode')
    with (out/'driver.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);terminal=out/(mode+'-COMPLETE.json');require(not terminal.exists(),'Existing terminal preserved')
        status=dict(stage='verify',progress=0,total=400,chips=1);stop=threading.Event();outputs={};rc=1;error=None
        def heartbeat():
            while not stop.wait(10):
                v=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status);atomic(out/'STATUS.json',v)
                with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(v)+'\n')
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
        try:
            require(sha(path)==ch,'Config changed before execution');require(required_files(c)<=set(c['files']),'Required dependency omitted')
            for p,h in c['files'].items():require(sha(p)==h,'Frozen input changed '+p)
            require(sha(c['data'])==DATA_SHA and sha(c['scorer'])==SCORER_SHA,'Data/scorer differs');require(c['max_length']==4096,'Native context changed')
            meta=json.loads(Path(c['checkpoint'],'model.json').read_text());require((meta['model_id'],meta['revision'],meta['max_length'])==(c['base_id'],c['base_revision'],4096),'Checkpoint metadata differs')
            require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base identity differs');require(json.loads(Path(c['checkpoint'],'temperature.json').read_text())['temperature']==c['temperature'],'Temperature differs')
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',JEV_TORCH_DTYPE='bfloat16');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
            for key in ['JEV_LOAD_8BIT','JEV_LOAD_4BIT','JEV_DEVICE_MAP','JEV_MAX_MEMORY']:os.environ.pop(key,None)
            import torch,torch_npu,transformers,peft,pyarrow.parquet as pq
            from transformers import AutoTokenizer
            from jev.api import compile_request,candidate_prompts,format_response
            from jev.model import DecisionModel
            runtime={k:m.__version__ for k,m in [('torch',torch),('torch_npu',torch_npu),('transformers',transformers),('peft',peft)]};require(runtime==c['runtime'],'Runtime differs')
            tokenizer=AutoTokenizer.from_pretrained(c['base'],local_files_only=True);tokenizer.padding_side='right'
            if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
            rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population differs');items=[];status['stage']='full_token_preflight'
            for i,row in enumerate(rows):
                req=request(row);gold=json.loads(row['gold']);require(row['split']=='test' and len(req['questions'])==5 and list(req['questions'])==list(gold),'Question population differs')
                for name,q in req['questions'].items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(keys(q)),'Gold coverage differs')
                items.append(dict(index=i,id=row['id'],input_sha256=stamp(row),request_sha256=stamp(req),fields=encode(row,tokenizer,compile_request,candidate_prompts)));status['progress']=i+1
            identity=stamp(c);pre=dict(identity=identity,rows=400,questions=2000,items=items,max_tokens=max(n for x in items for f in x['fields'] for n in f['lengths']),candidate_prompts=sum(len(f['lengths']) for x in items for f in x['fields']));atomic(out/'PREFLIGHT.json',pre);outputs['PREFLIGHT.json']=sha(out/'PREFLIGHT.json')
            torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False;torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8);status['stage']='load_model'
            class LocalDecisionModel(DecisionModel):
                def __init__(self,model_id,revision,**kwargs):
                    require((model_id,revision)==(c['base_id'],c['base_revision']),'Native base binding differs');super().__init__(c['base'],None,**kwargs)
            model=LocalDecisionModel.load(c['checkpoint'],device='npu:0');require(model.max_length==4096 and model.lora_rank==meta['lora_rank']>0,'Native model differs')
            require(str(model.head.weight.dtype)=='torch.float32' and str(next(model.backbone.parameters()).dtype)=='torch.bfloat16','Native precision differs')
            require(model.backbone.config._attn_implementation=='sdpa','Native attention differs')
            require(hasattr(model.backbone,'peft_config') and not any(getattr(m,'merged',False) for m in model.backbone.modules()),'Adapter was merged')
            scorer=NativeScorer(model,compile_request,candidate_prompts,format_response,c['temperature'])
            atomic(out/'ENVIRONMENT.json',dict(runtime=runtime,base_id=c['base_id'],base_revision=c['base_revision'],temperature=c['temperature'],model=dict(dtype='bfloat16',head='float32',attention='sdpa',adapter='unmerged',max_length=4096)))
            pr=probe(scorer,identity,status);atomic(out/'PROBE.json',pr);outputs['PROBE.json']=sha(out/'PROBE.json')
            if mode=='inference':
                folder=out/'records';folder.mkdir(exist_ok=True);require(all(p.name in {f'{i:06d}.json' for i in range(400)} for p in folder.glob('*.json')),'Extra receipts');preds=[];elapsed=0.;count=0;status.update(stage='inference',progress=0,total=400)
                for i,row in enumerate(rows):
                    fields=encode(row,tokenizer,compile_request,candidate_prompts);require(fields==pre['items'][i]['fields'],'Prompt binding changed');p=folder/f'{i:06d}.json'
                    if p.exists():v=receipt(json.loads(p.read_text()),row,i,identity,fields,c['temperature'])
                    else:
                        torch.npu.synchronize();start=time.monotonic();pred=scorer(row);torch.npu.synchronize();seconds=time.monotonic()-start
                        v=dict(identity=identity,index=i,id=row['id'],input_sha256=stamp(row),request_sha256=stamp(request(row)),seconds=seconds,prediction=pred);env=dict(payload=v,sha256=stamp(v));receipt(env,row,i,identity,fields,c['temperature']);atomic(p,env);elapsed+=seconds;count+=5
                    preds.append(v['prediction']);status.update(progress=i+1,questions_per_second_per_chip=count/elapsed if elapsed else None,reserved_gib=torch.npu.memory_reserved()/2**30)
                spec=importlib.util.spec_from_file_location('original_scorer',c['scorer']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
                report=dict(identity=identity,rows=400,questions=2000,serving=summarize(rows,preds,c['temperature'],m.score_one),raw_T1=summarize(rows,preds,1.,m.score_one),scope='Original arithmetic on raw native probabilities; original wire answers retained separately, not original wire scorer equivalence.')
                atomic(out/'report.json',report);outputs['report.json']=sha(out/'report.json')
            for p,h in c['files'].items():require(sha(p)==h,'Frozen input changed during execution '+p)
            require(sha(path)==ch,'Config changed');rc=0;status['stage']='completed'
        except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
        finally:
            stop.set();thread.join();value=dict(rc=rc,error=error,config_sha256=ch,outputs=outputs,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status);atomic(out/'STATUS.json',value);atomic(terminal,value)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);run(p.parse_args().config)
