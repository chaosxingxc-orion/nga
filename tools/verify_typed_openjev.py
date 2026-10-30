#!/usr/bin/env python3
"""Independent E29 Open-Jev typed prompt, checkpoint and metric audit."""
import argparse,hashlib,json,math,os,re,sys
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
SCORER_SHA='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'
def require(v,m):
    if not v:raise ValueError(m)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def stamp(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def same(a,b,path=''):
    if isinstance(b,dict):
        require(isinstance(a,dict) and set(a)==set(b),'Keys differ '+path)
        for k in b:same(a[k],b[k],path+'/'+k)
    elif isinstance(b,list):
        require(isinstance(a,list) and len(a)==len(b),'Length differs '+path)
        for i,(u,v) in enumerate(zip(a,b)):same(u,v,path+'/'+str(i))
    elif type(b)is float:require(type(a)in(int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-11),'Metric differs '+path)
    else:require(type(a)is type(b) and a==b,'Value differs '+path)
def keys(q):
    if q['type']=='choice':return list(q['criteria'])
    if q['type']=='noul':return ['false','true']
    require(q['type']=='score','Unknown question type');return [str(i) for i in range(len(q['criteria']))]
def prompt_fields(raw,tok,compile_request,candidate_prompts):
    req={'state':json.loads(raw['state']),'questions':json.loads(raw['questions'])};records=compile_request(req['state'],req['questions']);require(len(records)==5 and [r['id'] for r in records]==list(req['questions']),'Native question identity differs');fields=[]
    for r,(name,q) in zip(records,req['questions'].items()):
        require(r['kind']==q['type'] and r['answer_keys']==keys(q) and 'target'not in r,'Native candidate mapping differs')
        prompts=candidate_prompts(r);require(len(prompts)==(1 if q['type']=='noul' else len(keys(q))),'Native prompt count differs')
        texts=[tok.apply_chat_template([{'role':'user','content':p}],tokenize=False,add_generation_prompt=True,enable_thinking=False) for p in prompts]
        ids=tok(texts,padding=False,truncation=False)['input_ids'];require(len(ids)==len(prompts) and all(0<len(x)<=4096 for x in ids),'Token overflow/shape differs')
        fields.append(dict(name=name,kind=q['type'],candidate_keys=keys(q),native_record_sha256=stamp(r),prompts_sha256=stamp(prompts),lengths=[len(x) for x in ids],token_sha256=[stamp(x) for x in ids]))
    return fields

def distribution(values,temp):
    require(type(temp)in(int,float) and math.isfinite(temp) and temp>0,'Invalid temperature');require(values and all(type(v)in(int,float) and math.isfinite(v) for v in values),'Invalid logits')
    exps=[math.exp((v-max(values))/temp) for v in values];return [v/sum(exps) for v in exps]
def prediction(raw,p,fields,temp,compile_request,format_response):
    qs=json.loads(raw['questions']);require(list(p['probabilities'])==list(p['logits'])==list(qs),'Prediction questions differ');same(p['prompt_fields'],fields,'prompt fields');require(p['inference_temperature']==temp,'Temperature differs')
    for name,q in qs.items():
        ks=keys(q);prob,z=p['probabilities'][name],p['logits'][name];require(list(prob)==list(z)==ks,'Prediction candidates differ')
        require(all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in prob.values()) and abs(sum(prob.values())-1)<1e-6,'Invalid probability')
        expected=distribution(list(z.values()),temp);require(all(abs(prob[k]-v)<1e-9 for k,v in zip(ks,expected)),'Logit/probability differs')
    require(p['input_tokens']==sum(sum(f['lengths']) for f in fields),'Input token count differs')
    records=compile_request(json.loads(raw['state']),qs);same(p['wire_response'],format_response(records,[list(p['probabilities'][r['id']].values()) for r in records]),'native wire')

def metric_panels(rows,predictions,temp):
    cells=[]
    for row,pred in zip(rows,predictions):
        for name,gold in json.loads(row['gold']).items():
            ks=list(gold['probabilities']);g=[float(gold['probabilities'][k]) for k in ks];probs=pred['probabilities'][name] if temp==pred['inference_temperature'] else dict(zip(pred['logits'][name],distribution(list(pred['logits'][name].values()),temp)))
            probs={('true' if k=='yes' else 'false' if k=='no' else k):v for k,v in probs.items()} if gold['type']=='noul' else probs
            p=[float(probs.get(k,0.)) for k in ks];total=sum(p);p=[v/total for v in p] if total>0 else [1/len(ks)]*len(ks)
            cells.append(dict(type=gold['type'],workflow=row['workflow'],correct=max(range(len(p)),key=p.__getitem__)==max(range(len(g)),key=g.__getitem__),confidence=max(p),kl=sum(v*math.log(v/max(u,1e-9)) for v,u in zip(g,p) if v>0),brier=sum((v-u)**2 for v,u in zip(g,p))))
    def aggregate(xs):
        n=len(xs);bins=[[] for _ in range(10)]
        for x in xs:bins[min(int(x['confidence']*10),9)].append(x)
        return dict(n=n,accuracy=sum(x['correct'] for x in xs)/n,kl_from_gold=sum(x['kl'] for x in xs)/n,brier=sum(x['brier'] for x in xs)/n,ece10=sum(abs(sum(x['correct'] for x in b)-sum(x['confidence'] for x in b))/n for b in bins))
    overall=aggregate(cells)
    return dict(original_arithmetic_raw_readout=overall,strict=dict(expected=len(cells),returned=len(cells),valid=len(cells),invalid=0,unsupported=0,overlength=0,failed=0,**overall),by_type={k:aggregate([x for x in cells if x['type']==k]) for k in sorted({x['type'] for x in cells})},by_workflow={k:aggregate([x for x in cells if x['workflow']==k]) for k in sorted({x['workflow'] for x in cells})})

def dependencies(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_openjev_preflight.py','typed_openjev_inference.py','verify_typed_openjev.py','typed_openjev_finish.py','prepare_typed_openjev.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
    essentials={'base':['.complete','config.json','tokenizer.json'],'checkpoint':['model.json','temperature.json','head.pt','adapter/adapter_config.json','adapter/adapter_model.safetensors'],'code':['jev/api.py','jev/model.py','jev/metrics.py']}
    for role,names in essentials.items():
        root=Path(c[role]);require(root.is_dir(),'Missing dependency root')
        for n in names:require((root/n).is_file(),'Missing loader file '+str(root/n))
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    require(any(Path(c['base']).glob('*.safetensors')),'Missing base weights');return needed

def verify(config_path):
    c=load(config_path);out=Path(c['out']);ch=sha(config_path);identity=stamp(c);needed=dependencies(c)
    require(needed<=set(c['files']),'Required dependency omitted')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
    require(c['mode']=='inference' and c['max_length']==4096,'Protocol differs')
    require(sha(c['data'])==DATA_SHA and sha(c['scorer'])==SCORER_SHA,'Data/scorer differs')
    meta=load(Path(c['checkpoint'])/'model.json');require((meta['model_id'],meta['revision'],meta['max_length'])==(c['base_id'],c['base_revision'],4096),'Checkpoint metadata differs')
    require(load(Path(c['checkpoint'])/'temperature.json')['temperature']==c['temperature'],'Checkpoint temperature differs');require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base identity differs')
    require(load(Path(c['base'])/'config.json')['model_type']=='qwen3_5' and load(Path(c['checkpoint'])/'adapter/adapter_config.json')['peft_type']=='LORA','Model architecture differs')
    env=load(out/'ENVIRONMENT.json');same(env,dict(runtime=c['runtime'],base_id=c['base_id'],base_revision=c['base_revision'],temperature=c['temperature'],model=dict(dtype='bfloat16',head='float32',attention='sdpa',adapter='unmerged',max_length=4096)),'environment')
    lc=load(out/'LAUNCH_RECEIPT.json');require(lc['config_sha256']==ch and lc['image']==c['image'] and lc['wrapper_sha256']==sha(out/'run.sh'),'Launch binding differs')
    require(not any((out/n).exists() for n in ['ERROR.json','FAILED']),'Conflicting failure')
    os.environ.update(TORCH_DEVICE_BACKEND_AUTOLOAD='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    from jev.api import compile_request,candidate_prompts,format_response
    tok=AutoTokenizer.from_pretrained(c['base'],local_files_only=True);tok.padding_side='right'
    if tok.pad_token_id is None:tok.pad_token=tok.eos_token
    rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population differs')
    pre=load(out/'PREFLIGHT.json');require(pre['identity']==identity and pre['rows']==400 and pre['questions']==2000 and len(pre['items'])==400,'Preflight population differs')
    require(sorted(p.name for p in (out/'records').glob('*.json'))==[f'{i:06d}.json' for i in range(400)],'Receipt coverage differs')
    preds=[];max_tokens=0
    for i,row in enumerate(rows):
        qs=json.loads(row['questions']);gold=json.loads(row['gold']);require(row['split']=='test' and len(qs)==5 and list(qs)==list(gold),'Question population differs')
        for name,q in qs.items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(keys(q)),'Gold coverage differs')
        req={'state':json.loads(row['state']),'questions':qs};fields=prompt_fields(row,tok,compile_request,candidate_prompts);max_tokens=max(max_tokens,max(n for f in fields for n in f['lengths']))
        expected=dict(index=i,id=row['id'],input_sha256=stamp(row),request_sha256=stamp(req),fields=fields);same(pre['items'][i],expected,'independent preflight')
        envelope=load(out/'records'/f'{i:06d}.json');v=envelope['payload'];require(stamp(v)==envelope['sha256'],'Receipt checksum differs')
        require(v['identity']==identity and all(v[k]==expected[k] for k in ['index','id','input_sha256','request_sha256']),'Receipt identity differs')
        require(type(v['seconds'])in(int,float) and math.isfinite(v['seconds']) and v['seconds']>0,'Receipt duration invalid');prediction(row,v['prediction'],fields,c['temperature'],compile_request,format_response);preds.append(v['prediction'])
    require(pre['max_tokens']==max_tokens,'Preflight maximum differs')
    pr=load(out/'PROBE.json');require(pr['identity']==identity and pr['chips']==1 and pr['questions_per_pass']==5 and len(pr['passes'])==2,'Probe identity/count differs')
    require(pr['request_sha256']==stamp(pr['request']),'Probe request differs');require(set(q['type'] for q in pr['request']['questions'].values())=={'choice','noul','score'},'Probe typed coverage differs')
    require(type(pr['reserved_gib'])in(int,float) and math.isfinite(pr['reserved_gib']) and pr['reserved_gib']>0,'Probe memory invalid')
    raw={'state':json.dumps(pr['request']['state']),'questions':json.dumps(pr['request']['questions'])};fields=prompt_fields(raw,tok,compile_request,candidate_prompts)
    for p in pr['passes']:
        require(type(p['seconds'])in(int,float) and math.isfinite(p['seconds']) and p['seconds']>0,'Probe timing invalid');prediction(raw,p['prediction'],fields,c['temperature'],compile_request,format_response)
    a,b=[x['prediction']['probabilities'] for x in pr['passes']];delta=max(abs(a[q][k]-b[q][k]) for q in a for k in a[q]);require(delta<=1e-5,'Probe drift');same(pr['max_probability_delta'],delta,'probe delta')
    require(pre['candidate_prompts']==sum(len(f['lengths']) for x in pre['items'] for f in x['fields']),'Candidate prompt total differs')
    report=load(out/'report.json');require(report['identity']==identity and report['rows']==400 and report['questions']==2000,'Report identity differs');panels={};flags=[]
    for panel,temp in [('serving',c['temperature']),('raw_T1',1.)]:
        panels[panel]=metric_panels(rows,preds,temp);same(report[panel],panels[panel],panel)
        for group in ['by_type','by_workflow']:
            for cell,values in panels[panel][group].items():
                if values['n']<30:flags.append(dict(panel=panel,group=group,cell=cell,reason='small_count'))
                for metric,value in values.items():
                    if metric!='n' and value in (0.,1.):flags.append(dict(panel=panel,group=group,cell=cell,metric=metric,reason='extreme_metric'))
            for metric in ['accuracy','kl_from_gold','brier','ece10']:
                if len({v[metric] for v in panels[panel][group].values()})==1:flags.append(dict(panel=panel,group=group,metric=metric,reason='identical_cells'))
    term=load(out/'inference-COMPLETE.json');require(type(term['rc'])is int and term['rc']==0 and term['config_sha256']==ch and term['stage']=='completed' and term['progress']==term['total']==400,'Terminal differs')
    for name in ['PREFLIGHT.json','PROBE.json','report.json']:require(term['outputs'][name]==sha(out/name),'Terminal output binding differs')
    require(re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?',(out/'EXIT').read_text()) and (out/'EXIT').stat().st_mtime_ns>=(out/'inference-COMPLETE.json').stat().st_mtime_ns>=max((out/n).stat().st_mtime_ns for n in ['PREFLIGHT.json','PROBE.json','report.json']),'Terminal chronology differs')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed during audit')
    require(sha(config_path)==ch,'Config changed during audit')
    return dict(status='VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED',rows=400,questions=2000,config_sha256=ch,report_sha256=sha(out/'report.json'),frozen_files=len(c['files']),required_files=len(needed),panels=panels,review_flags=flags,scope='Independent native prompt re-tokenization, wire reconstruction, artifact and metric audit; actual Docker identity checked by finisher. No hardware equivalence or training-benefit claim.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();require(not a.out.exists(),'Existing audit preserved');a.out.write_text(json.dumps(verify(a.config),indent=2,allow_nan=False)+'\n')
