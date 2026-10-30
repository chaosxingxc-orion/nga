#!/usr/bin/env python3
"""Frozen E28 native Nimble typed inference; no model fitting."""
import argparse,fcntl,hashlib,importlib.util,json,math,os,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from typed_reference_nimble import (ADAPTER_REVISION,ADAPTER_SHA,BASE_REVISION,DATA_SHA,
    NativeFieldScorer,atomic,candidate_keys,model_input,preflight,prepared_receipt,request,require,sha,stamp)
SCORER_SHA='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'
SCRIPTS=['typed_reference_nimble.py','typed_nimble_inference.py','verify_typed_nimble.py','typed_nimble_finish.py','prepare_typed_nimble.py']
def required_files(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in SCRIPTS+['run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
    essentials={'base':['config.json','tokenizer.json','.complete'], 'adapter':['adapter_config.json','adapter_model.safetensors','tokenizer.json'],
                'code':['nimble/scoring/parallel_schema.py','nimble/scoring/release_contract.py','nimble/scoring/cuda_scorer.py']}
    for role,names in essentials.items():
        root=Path(c[role]);require(root.is_dir(),'Missing dependency directory '+role)
        for name in names:require((root/name).is_file(),'Missing loader file '+str(root/name))
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    require(any(Path(c['base']).glob('*.safetensors')),'Missing base weights')
    return needed

def validate_prediction(raw,p,fields):
    qs=request(raw)['questions'];require(list(p['probabilities'])==list(p['logits'])==list(p['typed_output'])==list(qs),'Question order differs')
    require(p['inference_temperature']==1.0 and p['prompt_fields']==fields,'Prompt/temperature differs')
    for name,q in qs.items():
        keys=candidate_keys(q);probs,z=p['probabilities'][name],p['logits'][name]
        require(list(probs)==list(z)==keys,'Candidate order differs')
        require(all(type(v) in (int,float) and math.isfinite(v) for v in z.values()),'Invalid logits')
        require(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in probs.values()) and abs(sum(probs.values())-1)<1e-5,'Invalid probabilities')
        e=[math.exp(z[k]-max(z.values())) for k in keys]
        require(max(abs(v/sum(e)-probs[k]) for k,v in zip(keys,e))<1e-5,'Probability/logit mismatch')
        best=max(range(len(keys)),key=lambda i:z[keys[i]]);expected=(keys[best]=='true') if q['type']=='noul' else keys[best]
        require(type(p['typed_output'][name]) is type(expected) and p['typed_output'][name]==expected,'Typed output differs')
def receipt(envelope,raw,index,identity,fields):
    v=envelope['payload'];require(stamp(v)==envelope['sha256'],'Receipt checksum differs')
    require(v['identity']==identity and v['index']==index and v['id']==raw['id'] and v['input_sha256']==stamp(raw) and v['request_ordered_sha256']==stamp(request(raw),True),'Foreign receipt')
    require(type(v['seconds']) in (int,float) and math.isfinite(v['seconds']) and v['seconds']>0,'Invalid duration')
    validate_prediction(raw,v['prediction'],fields);return v

def score(rows,predictions,score_one):
    cells=[]
    for raw,pred in zip(rows,predictions):
        for name,gold in json.loads(raw['gold']).items():
            ok,kl,brier,conf=score_one({'probabilities':pred['probabilities'][name]},gold)
            cells.append(dict(ok=ok,kl=kl,brier=brier,conf=conf,type=gold['type'],workflow=raw['workflow']))
    def aggregate(xs):
        n=len(xs);bins=[[x for x in xs if min(int(x['conf']*10),9)==i] for i in range(10)]
        return dict(n=n,accuracy=sum(x['ok'] for x in xs)/n,kl_from_gold=sum(x['kl'] for x in xs)/n,brier=sum(x['brier'] for x in xs)/n,ece10=sum(abs(sum(x['ok']-x['conf'] for x in b))/n for b in bins))
    all_=aggregate(cells)
    return dict(original_arithmetic_raw_readout=all_,strict=dict(expected=len(cells),returned=len(cells),valid=len(cells),invalid=0,unsupported=0,overlength=0,failed=0,**all_),
        by_type={k:aggregate([x for x in cells if x['type']==k]) for k in sorted({x['type'] for x in cells})},by_workflow={k:aggregate([x for x in cells if x['workflow']==k]) for k in sorted({x['workflow'] for x in cells})})

def synthetic():
    return {'id':'synthetic','state':json.dumps({'message':'中文 observation','nested':{'value':3}}),'questions':json.dumps({
        'route':{'type':'choice','instructions':'Choose route','criteria':{'a':'first','b':'second'}},
        'allow':{'type':'noul','instructions':'Allow?'},'level':{'type':'score','instructions':'Choose level','criteria':['low','medium','high']},
        'extra':{'type':'choice','instructions':'Choose extra','criteria':{'x':'one','y':'two'}},'flag':{'type':'noul','instructions':'Flag?'}})}
def probe(scorer,identity,status):
    import torch
    raw=synthetic();passes=[]
    for i in range(2):
        torch.npu.synchronize();start=time.monotonic();pred=scorer(raw);torch.npu.synchronize();elapsed=time.monotonic()-start
        validate_prediction(raw,pred,pred['prompt_fields']);passes.append(dict(prediction=pred,seconds=elapsed));status.update(stage='synthetic_probe',progress=i+1,total=2,questions_per_second_per_chip=5/elapsed,reserved_gib=torch.npu.memory_reserved()/2**30)
    a,b=[p['prediction'] for p in passes];require(a['prompt_fields']==b['prompt_fields'],'Probe prompt drift')
    delta=max(abs(a['probabilities'][q][k]-b['probabilities'][q][k]) for q in a['probabilities'] for k in a['probabilities'][q]);require(delta<=1e-5,'Probe repeat drift')
    return dict(identity=identity,request=request(raw),request_ordered_sha256=stamp(request(raw),True),passes=passes,max_probability_delta=delta,chips=1,questions_per_pass=5,reserved_gib=torch.npu.memory_reserved()/2**30)

def run(config_path):
    cbytes=config_path.read_bytes();config_hash=hashlib.sha256(cbytes).hexdigest();c=json.loads(cbytes);out=Path(c['out']);mode=c['mode'];require(mode in ('probe','inference'),'Invalid execution mode')
    with (out/'driver.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);terminal=out/(mode+'-COMPLETE.json');require(not terminal.exists(),'Existing terminal preserved')
        status=dict(stage='verify',progress=0,total=400,chips=1);stop=threading.Event();outputs={};rc=1;error=None
        def heartbeat():
            while not stop.wait(10):
                snap=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status);atomic(out/'STATUS.json',snap)
                with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(snap)+'\n')
        t=threading.Thread(target=heartbeat,daemon=True);t.start()
        try:
            require(sha(config_path)==config_hash,'Config changed before execution')
            require(required_files(c)<=set(c['files']),'Required dependency omitted')
            for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
            require(c['max_length']==2048 and c['temperature']==1.0,'Protocol differs')
            require(c['adapter_revision']==ADAPTER_REVISION and sha(Path(c['adapter'])/'adapter_model.safetensors')==ADAPTER_SHA,'Wrong adapter')
            require(c['base_revision']==BASE_REVISION and Path(c['base'],'.complete').read_text().splitlines()[0]==BASE_REVISION,'Wrong base')
            require(sha(c['data'])==DATA_SHA and sha(c['scorer'])==SCORER_SHA,'Data/scorer differs')
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
            import torch,torch_npu,transformers,peft,pyarrow.parquet as pq
            from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
            from peft import PeftModel
            from nimble.scoring.release_contract import prompt_builder
            from nimble.scoring.parallel_schema import prepare_prompts
            from nimble.scoring.cuda_scorer import candidate_projection
            runtime={k:m.__version__ for k,m in [('torch',torch),('torch_npu',torch_npu),('transformers',transformers),('peft',peft)]};require(runtime==c['runtime'],'Runtime differs')
            tok=AutoTokenizer.from_pretrained(c['adapter'],local_files_only=True);prepare=prompt_builder(c['adapter'],tok);require(prepare is prepare_prompts,'Not original v1 prompt contract')
            rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population differs')
            for r in rows:
                qs=request(r)['questions'];g=json.loads(r['gold']);require(r['split']=='test' and len(qs)==5 and list(qs)==list(g),'Question population differs')
                for name,q in qs.items():require(g[name]['type']==q['type'] and set(g[name]['probabilities'])==set(candidate_keys(q)),'Gold candidates differ')
            identity=stamp(c);status['stage']='full_token_preflight';pre=preflight(c,rows,tok,prepare,status);pre.update(identity=identity);atomic(out/'PREFLIGHT.json',pre);outputs['PREFLIGHT.json']=sha(out/'PREFLIGHT.json')
            torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False;torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8);status['stage']='load_model'
            base,loading=Qwen3_5ForConditionalGeneration.from_pretrained(c['base'],local_files_only=True,dtype=torch.bfloat16,device_map='cpu',attn_implementation='sdpa',output_loading_info=True)
            require(not any(loading.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']),'Base loading changed')
            model=PeftModel.from_pretrained(base,c['adapter'],local_files_only=True).merge_and_unload(safe_merge=True).eval().to('npu:0')
            scorer=NativeFieldScorer(model,tok,prepare,candidate_projection)
            atomic(out/'ENVIRONMENT.json',dict(runtime=runtime,adapter_revision=ADAPTER_REVISION,adapter_sha256=ADAPTER_SHA,base_revision=BASE_REVISION,temperature=1.,max_length=2048,model=dict(dtype='bfloat16',projection='float32',attention='sdpa',merge='safe',prompt='v1')))
            pr=probe(scorer,identity,status);atomic(out/'PROBE.json',pr);outputs['PROBE.json']=sha(out/'PROBE.json')
            if mode=='inference':
                folder=out/'records';folder.mkdir(exist_ok=True);expected={f'{i:06d}.json' for i in range(400)};require(all(p.name in expected for p in folder.glob('*.json')),'Extra receipts')
                predictions=[];elapsed=0.;count=0;status.update(stage='inference',progress=0,total=400)
                for i,r in enumerate(rows):
                    context,schema=model_input(r);actual=prepared_receipt(r,i,prepare(tok,context,schema,2048,system_role=True));require(actual==pre['items'][i],'Actual/preflight prompts differ');path=folder/f'{i:06d}.json'
                    if path.exists():v=receipt(json.loads(path.read_text()),r,i,identity,actual['fields'])
                    else:
                        torch.npu.synchronize();start=time.monotonic();pred=scorer(r);torch.npu.synchronize();seconds=time.monotonic()-start
                        v=dict(identity=identity,index=i,id=r['id'],input_sha256=stamp(r),request_ordered_sha256=stamp(request(r),True),seconds=seconds,prediction=pred);envelope=dict(payload=v,sha256=stamp(v));receipt(envelope,r,i,identity,actual['fields']);atomic(path,envelope);elapsed+=seconds;count+=5
                    predictions.append(v['prediction']);status.update(progress=i+1,questions_per_second_per_chip=count/elapsed if elapsed else None,reserved_gib=torch.npu.memory_reserved()/2**30)
                spec=importlib.util.spec_from_file_location('original_scorer',c['scorer']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                report=dict(identity=identity,rows=400,questions=2000,serving=score(rows,predictions,module.score_one),scope='Original arithmetic on native probabilities; not wire/vLLM equivalence; no expected-score MAE.')
                atomic(out/'report.json',report);outputs['report.json']=sha(out/'report.json')
            for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
            require(sha(config_path)==config_hash,'Config changed');status['stage']='completed';rc=0
        except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
        finally:
            stop.set();t.join();atomic(out/'STATUS.json',dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status));atomic(terminal,dict(rc=rc,error=error,config_sha256=config_hash,outputs=outputs,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);run(parser.parse_args().config)
