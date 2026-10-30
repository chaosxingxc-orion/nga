#!/usr/bin/env python3
"""Independent E28 population, prompt reconstruction, checkpoint and metric audit."""
import argparse,hashlib,json,math,os,re,sys
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
SCORER_SHA='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'
ADAPTER_SHA='ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b'
ADAPTER_REVISION='594dfdcfb6f94e3d0c0db7535180d3c71689169a'
BASE_REVISION='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
def require(v,m):
    if not v:raise ValueError(m)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def stamp(v,ordered=False):return hashlib.sha256(json.dumps(v,sort_keys=not ordered,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
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
def independent_input(raw):
    qs=json.loads(raw['questions']);schema={}
    for name,q in qs.items():
        candidates=keys(q);require(1<=len(candidates)<=26,'Unsupported candidate width')
        field={'description':q['instructions'],'type':'boolean' if q['type']=='noul' else 'enum','choices':[False,True] if q['type']=='noul' else candidates}
        definitions=dict(zip(candidates,q['criteria'])) if q['type']=='score' else q.get('criteria') or {}
        descriptions={k:v for k,v in definitions.items() if v is not None}
        if descriptions:field['choice_descriptions']=descriptions
        schema[name]=field
    state=json.loads(raw['state']);return state if isinstance(state,str) else json.dumps(state,ensure_ascii=False),schema

def prompt_fields(raw,tok,prepare):
    context,schema=independent_input(raw);p=prepare(tok,context,schema,2048,system_role=True)
    require(len(p.names)==len(p.choices)==len(p.full_ids)==len(p.candidate_ids)==5 and p.names==list(schema),'Prompt population differs')
    fields=[]
    for name,choices,ids,cids in zip(p.names,p.choices,p.full_ids,p.candidate_ids):
        names=[str(v).lower() if type(v)is bool else v for v in choices];require(names==keys(json.loads(raw['questions'])[name]),'Prompt candidate order differs')
        require(0<len(ids)<=2048 and len(cids)==len(names) and len(set(cids))==len(cids),'Prompt token/candidate shape differs')
        fields.append(dict(name=name,candidate_keys=names,candidate_token_ids=cids,tokens=len(ids),prompt_token_sha256=stamp(ids,True)))
    return fields

def prediction(raw,p,fields):
    qs=json.loads(raw['questions']);require(list(p['probabilities'])==list(p['logits'])==list(p['typed_output'])==list(qs),'Prediction questions differ');same(p['prompt_fields'],fields,'prompt fields');require(p['inference_temperature']==1.,'Temperature differs')
    for name,q in qs.items():
        ks=keys(q);prob,z=p['probabilities'][name],p['logits'][name];require(list(prob)==list(z)==ks,'Prediction candidates differ')
        require(all(type(v)in(int,float) and math.isfinite(v) for v in z.values()),'Invalid logits')
        require(all(type(v)in(int,float) and math.isfinite(v) and 0<=v<=1 for v in prob.values()) and abs(sum(prob.values())-1)<1e-5,'Invalid probability')
        exps=[math.exp(z[k]-max(z.values())) for k in ks];require(all(abs(prob[k]-e/sum(exps))<1e-5 for k,e in zip(ks,exps)),'Logit/probability differs')
        best=max(ks,key=lambda k:z[k]);output=(best=='true') if q['type']=='noul' else best
        require(type(p['typed_output'][name])is type(output) and p['typed_output'][name]==output,'Typed value differs')

def metric_panels(rows,predictions):
    cells=[]
    for row,pred in zip(rows,predictions):
        for name,gold in json.loads(row['gold']).items():
            ks=list(gold['probabilities']);g=[float(gold['probabilities'][k]) for k in ks];probs=pred['probabilities'][name]
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
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_reference_nimble.py','typed_nimble_inference.py','verify_typed_nimble.py','typed_nimble_finish.py','prepare_typed_nimble.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
    essentials={'base':['.complete','config.json','tokenizer.json'],'adapter':['adapter_config.json','adapter_model.safetensors','tokenizer.json'],'code':['nimble/scoring/parallel_schema.py','nimble/scoring/release_contract.py','nimble/scoring/cuda_scorer.py']}
    for role,names in essentials.items():
        root=Path(c[role]);require(root.is_dir(),'Missing dependency root')
        for n in names:require((root/n).is_file(),'Missing loader file '+str(root/n))
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    require(any(Path(c['base']).glob('*.safetensors')),'Missing base weights');return needed

def verify(config_path):
    c=load(config_path);out=Path(c['out']);ch=sha(config_path);identity=stamp(c);needed=dependencies(c)
    require(needed<=set(c['files']),'Required dependency omitted')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
    require(c['mode']=='inference' and c['max_length']==2048 and c['temperature']==1.,'Protocol differs')
    require(sha(c['data'])==DATA_SHA and sha(c['scorer'])==SCORER_SHA,'Data/scorer differs')
    require(c['adapter_revision']==ADAPTER_REVISION and sha(Path(c['adapter'])/'adapter_model.safetensors')==ADAPTER_SHA,'Adapter identity differs')
    require(c['base_revision']==BASE_REVISION and Path(c['base'],'.complete').read_text().splitlines()[0]==BASE_REVISION,'Base identity differs')
    require(load(Path(c['base'])/'config.json')['model_type']=='qwen3_5' and load(Path(c['adapter'])/'adapter_config.json')['peft_type']=='LORA','Model architecture differs')
    env=load(out/'ENVIRONMENT.json');same(env,dict(runtime=c['runtime'],adapter_revision=ADAPTER_REVISION,adapter_sha256=ADAPTER_SHA,base_revision=BASE_REVISION,temperature=1.,max_length=2048,model=dict(dtype='bfloat16',projection='float32',attention='sdpa',merge='safe',prompt='v1')),'environment')
    lc=load(out/'LAUNCH_RECEIPT.json');require(lc['config_sha256']==ch and lc['image']==c['image'] and lc['wrapper_sha256']==sha(out/'run.sh'),'Launch binding differs')
    require(not any((out/n).exists() for n in ['ERROR.json','FAILED']),'Conflicting failure')
    os.environ.update(TORCH_DEVICE_BACKEND_AUTOLOAD='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    from nimble.scoring.release_contract import prompt_builder
    from nimble.scoring.parallel_schema import prepare_prompts
    tok=AutoTokenizer.from_pretrained(c['adapter'],local_files_only=True);prepare=prompt_builder(c['adapter'],tok);require(prepare is prepare_prompts,'Prompt version differs')
    rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population differs')
    pre=load(out/'PREFLIGHT.json');require(pre['identity']==identity and pre['rows']==400 and pre['questions']==2000 and len(pre['items'])==400,'Preflight population differs')
    require(sorted(p.name for p in (out/'records').glob('*.json'))==[f'{i:06d}.json' for i in range(400)],'Receipt coverage differs')
    preds=[];max_tokens=0
    for i,row in enumerate(rows):
        qs=json.loads(row['questions']);gold=json.loads(row['gold']);require(row['split']=='test' and len(qs)==5 and list(qs)==list(gold),'Question population differs')
        for name,q in qs.items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(keys(q)),'Gold coverage differs')
        req={'state':json.loads(row['state']),'questions':qs};fields=prompt_fields(row,tok,prepare);max_tokens=max(max_tokens,max(f['tokens'] for f in fields))
        expected=dict(index=i,id=row['id'],input_sha256=stamp(row),request_ordered_sha256=stamp(req,True),fields=fields);same(pre['items'][i],expected,'independent preflight')
        envelope=load(out/'records'/f'{i:06d}.json');v=envelope['payload'];require(stamp(v)==envelope['sha256'],'Receipt checksum differs')
        require(v['identity']==identity and all(v[k]==expected[k] for k in ['index','id','input_sha256','request_ordered_sha256']),'Receipt identity differs')
        require(type(v['seconds'])in(int,float) and math.isfinite(v['seconds']) and v['seconds']>0,'Receipt duration invalid');prediction(row,v['prediction'],fields);preds.append(v['prediction'])
    require(pre['max_tokens']==max_tokens,'Preflight maximum differs')
    pr=load(out/'PROBE.json');require(pr['identity']==identity and pr['chips']==1 and pr['questions_per_pass']==5 and len(pr['passes'])==2,'Probe identity/count differs')
    require(pr['request_ordered_sha256']==stamp(pr['request'],True),'Probe request differs');require(set(q['type'] for q in pr['request']['questions'].values())=={'choice','noul','score'},'Probe typed coverage differs')
    require(type(pr['reserved_gib'])in(int,float) and math.isfinite(pr['reserved_gib']) and pr['reserved_gib']>0,'Probe memory invalid')
    raw={'state':json.dumps(pr['request']['state']),'questions':json.dumps(pr['request']['questions'])};fields=prompt_fields(raw,tok,prepare)
    for p in pr['passes']:
        require(type(p['seconds'])in(int,float) and math.isfinite(p['seconds']) and p['seconds']>0,'Probe timing invalid');prediction(raw,p['prediction'],fields)
    a,b=[x['prediction']['probabilities'] for x in pr['passes']];delta=max(abs(a[q][k]-b[q][k]) for q in a for k in a[q]);require(delta<=1e-5,'Probe drift');same(pr['max_probability_delta'],delta,'probe delta')
    report=load(out/'report.json');require(report['identity']==identity and report['rows']==400 and report['questions']==2000,'Report identity differs');panels=metric_panels(rows,preds);same(report['serving'],panels,'serving')
    flags=[]
    for group in ['by_type','by_workflow']:
        for cell,values in panels[group].items():
            if values['n']<30:flags.append(dict(group=group,cell=cell,reason='small_count'))
            for metric,value in values.items():
                if metric!='n' and value in (0.,1.):flags.append(dict(group=group,cell=cell,metric=metric,reason='extreme_metric'))
        for metric in ['accuracy','kl_from_gold','brier','ece10']:
            if len({v[metric] for v in panels[group].values()})==1:flags.append(dict(group=group,metric=metric,reason='identical_cells'))
    term=load(out/'inference-COMPLETE.json');require(type(term['rc'])is int and term['rc']==0 and term['config_sha256']==ch and term['stage']=='completed' and term['progress']==term['total']==400,'Terminal differs')
    for name in ['PREFLIGHT.json','PROBE.json','report.json']:require(term['outputs'][name]==sha(out/name),'Terminal output binding differs')
    require(re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?',(out/'EXIT').read_text()) and (out/'EXIT').stat().st_mtime_ns>=(out/'inference-COMPLETE.json').stat().st_mtime_ns>=max((out/n).stat().st_mtime_ns for n in ['PREFLIGHT.json','PROBE.json','report.json']),'Terminal chronology differs')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed during audit')
    require(sha(config_path)==ch,'Config changed during audit')
    return dict(status='VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED',rows=400,questions=2000,config_sha256=ch,report_sha256=sha(out/'report.json'),frozen_files=len(c['files']),required_files=len(needed),panels=panels,review_flags=flags,scope='Independent full prompt re-tokenization, artifact and metric audit; actual Docker identity checked by finisher. No hardware equivalence or training-benefit claim.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();require(not a.out.exists(),'Existing audit preserved');a.out.write_text(json.dumps(verify(a.config),indent=2,allow_nan=False)+'\n')
