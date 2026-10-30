#!/usr/bin/env python3
"""Fixed original Nimble public benchmark inference on native candidate-token readout."""
import argparse, fcntl, hashlib, json, math, os, sys, tempfile, threading, time
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()


def identity(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,allow_nan=False).encode()).hexdigest()


def require(ok,msg):
    if not ok:raise ValueError(msg)


def atomic(path,obj):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def verify_receipt(envelope,row,stamp,prepared,index=None,config=None):
    v=envelope['payload'];require(identity(v)==envelope['sha256'],'Receipt checksum differs')
    require(v['identity']==stamp and v['input_sha256']==identity(row) and v['id']==row['id'],'Receipt identity differs')
    require(index is None or v.get('index')==index,'Receipt index differs')
    field=v['result']['raw_student']['fields']['decision']
    keys=[str(x).lower() if type(x) is bool else x for x in prepared.choices[0]]
    require(list(field['logits'])==keys==list(field['scores']),'Candidate key order differs')
    require(field['candidate_token_ids']==prepared.candidate_ids[0], 'Candidate order differs')
    require(field['prompt_token_sha256']==identity_tokens(prepared.full_ids[0]),'Prompt differs')
    z=list(field['logits'].values());p=list(field['scores'].values())
    require(len(z)==len(p)==len(prepared.choices[0]) and all(math.isfinite(x) for x in z+p),'Invalid logits')
    e=[math.exp(x-max(z)) for x in z];total=sum(e)
    require(all(abs(x/total-y)<1e-6 for x,y in zip(e,p)),'Probability/logit differs')
    result=v['result']
    best=max(range(len(p)),key=p.__getitem__);choice=prepared.choices[0][best]
    require(field.get('value')==choice and result['raw_student'].get('output',{}).get('decision')==choice,'Stored choice differs')
    require(result['raw_student'].get('temperature')==1.0,'Stored temperature differs')
    if config is not None:
        require(result['raw_student'].get('model')==config['model_id'] and result['raw_student'].get('revision')==config['adapter_revision'],'Stored checkpoint differs')
    require('reference' in row,'Input reference missing')
    from nimble.evaluation.evaluate_pilot import assess
    from nimble.evaluation.evaluate_public import distribution_metrics
    kind=row['input']['questions']['decision']['type']
    expected=assess(field['scores'],row['reference']['target'],kind)
    require(result['student']==expected,'Stored student metrics differ')
    require(result['reference']==row['reference'] and result['id']==row['id'] and result['type']==kind
            and result['domain']==row['domain'] and result['family']==row['family'] and result['split']==row.get('split','test'),'Stored result input differs')
    if 'distribution' in row['reference']:
        require(result['distribution']==distribution_metrics(expected['probabilities'],row['reference']['distribution']),
                'Stored distribution metrics differ')
    return result


def identity_tokens(ids):return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);args=ap.parse_args()
    config_path=Path(args.config);c=json.loads(config_path.read_text());out=Path(c['out']);stamp=identity(c);config_hash=sha(config_path)
    lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    require(not (out/'COMPLETE.json').exists() and not (out/'EXIT').exists(),'Existing terminal requires reviewed fresh retry')
    status={'stage':'verify','progress':0,'total':1884,'chips':1};stop=threading.Event()
    def heartbeat():
        while not stop.wait(15):
            now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());atomic(out/'STATUS.json',{'utc':now,**status})
            with (out/'heartbeat.log').open('a') as f:f.write(now+' '+' '.join(f'{k}={v}' for k,v in status.items())+'\n')
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start();rc=1;error=None;outputs={}
    try:
        for path,h in c['files'].items():require(sha(path)==h,'Frozen file changed: '+path)
        require(sha(c['adapter']+'/adapter_model.safetensors')=='ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b','Wrong initial adapter')
        require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Wrong base')
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
        import torch,torch_npu
        from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
        from peft import PeftModel
        from nimble.scoring.release_contract import prompt_builder
        from nimble.scoring.cuda_scorer import candidate_projection
        from nimble.scoring.serving_schema import codes_for
        from nimble.scoring.parallel_schema import choice_key
        from nimble.evaluation.evaluate_public import model_input,evaluate_records,summarize_rows
        tokenizer=AutoTokenizer.from_pretrained(c['adapter'],local_files_only=True);prepare=prompt_builder(c['adapter'],tokenizer)
        suites=[];count=0;status['stage']='whole_test_token_preflight'
        for suite in c['suites']:
            raw=Path(suite['data']).read_bytes();manifest=json.loads(Path(suite['manifest']).read_text())
            require(hashlib.sha256(raw).hexdigest()==manifest['dataset_sha256'],'Dataset differs from published manifest')
            rows=[json.loads(x) for x in raw.decode().split('\n') if x.strip()]
            require(len(rows)==manifest['count'] and [r['id'] for r in rows]==sorted(manifest['ids']),'Input IDs differ')
            prompts=[]
            for row in rows:
                context,schema=model_input(row);p=prepare(tokenizer,context,schema,2048,system_role=True)
                require(len(p.names)==1 and max(map(len,p.full_ids))<=2048,'Invalid native prompt')
                prompts.append(p)
            suites.append((suite,rows,prompts));count+=len(rows)
        require(count==1884,'Incomplete benchmark selection')
        atomic(out/'PREFLIGHT.json',{'identity':stamp,'rows':count,'max_tokens':max(len(p.full_ids[0]) for _,_,ps in suites for p in ps),'suite_counts':{s['name']:len(r) for s,r,_ in suites}})
        torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False;torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8)
        status['stage']='load_and_merge';start=time.monotonic()
        base,loading=Qwen3_5ForConditionalGeneration.from_pretrained(c['base'],local_files_only=True,dtype=torch.bfloat16,device_map='cpu',attn_implementation='sdpa',output_loading_info=True)
        require(not any(loading.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']),'Base loading changed')
        model=PeftModel.from_pretrained(base,c['adapter'],local_files_only=True).merge_and_unload(safe_merge=True).eval().to('npu:0');head=model.get_output_embeddings().weight
        class Scorer:
            def score(self,context,schema,mode='independent'):
                p=prepare(tokenizer,context,schema,2048,system_role=True);choices=p.choices[0];ids=p.full_ids[0];candidates=p.candidate_ids[0];keys=[choice_key(v) for v in choices]
                with torch.inference_mode():
                    hidden=model.model(input_ids=torch.tensor([ids],device='npu:0'),use_cache=False).last_hidden_state[:,-1,:]
                    z=candidate_projection(hidden,head,candidates)[0];prob=torch.softmax(z,dim=-1);torch.npu.synchronize()
                best=z.argmax().item();field={'value':choices[best],'scores':dict(zip(keys,prob.cpu().tolist())),'logits':dict(zip(keys,z.cpu().tolist())),'candidate_token_ids':candidates,'code_to_choice':dict(zip(codes_for(len(choices),tokenizer),choices)),'prompt_token_count':len(ids),'prompt_token_sha256':identity_tokens(ids)}
                return {'model':c['model_id'],'revision':c['adapter_revision'],'backend':'npu_native_candidate_projection','temperature':1.0,'fields':{'decision':field},'output':{'decision':choices[best]}}
        scorer=Scorer();load_seconds=time.monotonic()-start;start=time.monotonic();done=0;newly_computed=0;reports={}
        for suite,rows,prompts in suites:
            folder=out/suite['name'];folder.mkdir(exist_ok=True);expected=[f'{i:06d}.json' for i in range(len(rows))]
            existing=sorted(x.name for x in folder.glob('[0-9]*.json'));require(existing==expected[:len(existing)],'Invalid receipt prefix')
            results=[]
            for i,(row,prompt) in enumerate(zip(rows,prompts)):
                status.update(stage='inference',suite=suite['name'],current_index=i)
                path=folder/expected[i]
                if path.exists():result=verify_receipt(json.loads(path.read_text()),row,stamp,prompt,i,c)
                else:
                    result=evaluate_records([row],scorer)[0];value={'identity':stamp,'input_sha256':identity(row),'id':row['id'],'index':i,'result':result};envelope={'payload':value,'sha256':identity(value)}
                    verify_receipt(envelope,row,stamp,prompt,i,c);atomic(path,envelope);newly_computed+=1
                results.append(result);done+=1;status.update(progress=done,questions_per_second_per_chip=newly_computed/(time.monotonic()-start),reserved_gib=torch.npu.memory_reserved()/2**30)
            report=summarize_rows(results);report.update(dataset_sha256=suite['dataset_sha256'],identity=stamp);atomic(folder/'report.json',report);reports[suite['name']]=report
        elapsed=time.monotonic()-start
        for path,h in c['files'].items():require(sha(path)==h,'Frozen file changed: '+path)
        require(identity(json.loads(config_path.read_text()))==stamp,'Config changed')
        atomic(out/'report.json',{'identity':stamp,'rows':done,'suites':reports,'load_seconds':load_seconds,'inference_seconds':elapsed,'questions_per_second_per_chip':newly_computed/elapsed,'reused_rows':done-newly_computed,'chips':1,'reserved_gib':torch.npu.memory_reserved()/2**30,'scope':'Seven original true-test subsets; not the mixed 3880-row benchmark; no training benefit or Astra approval'})
        outputs={n:sha(out/n) for n in ['report.json','PREFLIGHT.json']};rc=0;status['stage']='completed'
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
    finally:
        stop.set();thread.join();terminal={'rc':rc,'error':error,'identity':stamp,'config_sha256':config_hash,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',terminal);atomic(out/'COMPLETE.json',terminal)

if __name__=='__main__':main()
