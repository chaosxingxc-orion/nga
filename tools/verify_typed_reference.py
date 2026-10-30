#!/usr/bin/env python3
"""Independent E26 artifact and metric verification; no driver/native metric imports."""
import argparse,hashlib,json,math,os,re
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
def stamp(x,sort=True):return hashlib.sha256(json.dumps(x,sort_keys=sort,separators=(',',':'),allow_nan=False).encode()).hexdigest()
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
def candidate_keys(q):
    if q['type']=='noul':return ['false','true']
    if q['type']=='choice':return list(q['criteria'])
    require(q['type']=='score','Invalid type');return [str(i) for i in range(len(q['criteria']))]
def distribution(z,t):
    require(z and t>0 and math.isfinite(t) and all(type(v)in(int,float) and math.isfinite(v) for v in z.values()),'Invalid logits')
    e={k:math.exp((v-max(z.values()))/t) for k,v in z.items()};return {k:v/sum(e.values()) for k,v in e.items()}
def score(pred,gold):
    keys=list(gold['probabilities']);g=[float(gold['probabilities'][k]) for k in keys]
    p={('true' if k=='yes' else 'false' if k=='no' else k):v for k,v in pred.items()} if gold['type']=='noul' else pred
    vals=[float(p.get(k,0.)) for k in keys];total=sum(vals);vals=[v/total for v in vals] if total>0 else [1/len(keys)]*len(keys)
    return {'ok':max(range(len(vals)),key=vals.__getitem__)==max(range(len(g)),key=g.__getitem__),
            'kl':sum(q*math.log(q/max(p,1e-9)) for q,p in zip(g,vals) if q>0),'brier':sum((p-q)**2 for p,q in zip(vals,g)),'conf':max(vals)}
def summaries(rows,predictions,temp):
    cells=[]
    for raw,pred in zip(rows,predictions):
        for name,gold in json.loads(raw['gold']).items():
            z={k:v*pred['inference_temperature'] for k,v in pred['logits'][name].items()};prob=pred['probabilities'][name] if temp==pred['inference_temperature'] else distribution(z,temp);s=score(prob,gold);cells.append({**s,'type':gold['type'],'workflow':raw['workflow']})
    def aggregate(xs):
        bins=[[] for _ in range(10)]
        for x in xs:bins[min(int(x['conf']*10),9)].append(x)
        n=len(xs);return {'n':n,'accuracy':sum(x['ok'] for x in xs)/n,'kl_from_gold':sum(x['kl'] for x in xs)/n,'brier':sum(x['brier'] for x in xs)/n,
            'ece10':sum(abs(sum(x['ok'] for x in b)-sum(x['conf'] for x in b))/n for b in bins)}
    full=aggregate(cells)
    return {'original_arithmetic_raw_readout':full,'strict':{'expected':len(cells),'returned':len(cells),'valid':len(cells),'invalid':0,'unsupported':0,'overlength':0,'failed':0,**full},
            'by_type':{k:aggregate([x for x in cells if x['type']==k]) for k in sorted({x['type'] for x in cells})},
            'by_workflow':{k:aggregate([x for x in cells if x['workflow']==k]) for k in sorted({x['workflow'] for x in cells})}}
def validate_receipt(envelope,raw,index,identity,temp):
    value=envelope['payload'];require(stamp(value)==envelope['sha256'],'Receipt checksum differs')
    request={'state':json.loads(raw['state']),'questions':json.loads(raw['questions'])}
    require(value['index']==index and value['id']==raw['id'] and value['identity']==identity and value['input_sha256']==stamp(raw) and value['request_ordered_sha256']==stamp(request,False),'Receipt identity differs')
    pred=value['prediction'];require(list(pred['probabilities'])==list(pred['logits'])==list(request['questions']),'Question order differs');require(pred['inference_temperature']==temp,'Temperature differs')
    for name,q in request['questions'].items():
        p,z=pred['probabilities'][name],pred['logits'][name];require(list(p)==list(z)==candidate_keys(q),'Candidate order differs')
        expected=distribution(z,1.);require(all(type(x)in(int,float) and math.isfinite(x) and 0<=x<=1 for x in p.values()) and abs(sum(p.values())-1)<1e-5,'Invalid distribution')
        require(all(abs(p[k]-expected[k])<1e-5 for k in p),'Probability/logit differs')
    require(type(value['seconds'])in(int,float) and math.isfinite(value['seconds']) and value['seconds']>0,'Invalid duration')
    return pred

def verify_probe(probe,identity,temp):
    require(probe['identity']==identity and probe['questions_per_pass']==5 and probe['chips']==1,'Probe identity/count differs')
    req=probe['request'];require(len(req['questions'])==5 and set(q['type'] for q in req['questions'].values())=={'choice','noul','score'},'Probe typed coverage differs')
    require(probe['request_ordered_sha256']==stamp(req,False),'Probe request hash differs')
    require(type(probe['tokens'])is int and 0<probe['tokens']<=16384 and re.fullmatch('[0-9a-f]{64}',probe['tokens_sha256']),'Probe token metadata differs')
    require(type(probe['reserved_gib'])in(int,float) and math.isfinite(probe['reserved_gib']) and probe['reserved_gib']>0,'Probe memory invalid')
    require(len(probe['passes'])==2,'Probe requires two passes')
    raw={'id':'probe','state':json.dumps(req['state']),'questions':json.dumps(req['questions'])}
    for item in probe['passes']:
        require(item['prediction']['input_tokens']==probe['tokens'],'Probe prediction token count differs')
        value={'index':0,'id':'probe','identity':identity,'input_sha256':stamp(raw),'request_ordered_sha256':stamp(req,False),'prediction':item['prediction'],'seconds':item['seconds']}
        validate_receipt({'payload':value,'sha256':stamp(value)},raw,0,identity,temp)
    a,b=[x['prediction']['probabilities'] for x in probe['passes']]
    delta=max(abs(a[q][k]-b[q][k]) for q in a for k in a[q])
    require(delta<=1e-5,'Probe repeat drift exceeds protocol');same(probe['max_probability_delta'],delta,'probe delta')

def required_files(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_reference_kev.py','verify_typed_reference.py','run.sh','LAUNCH_EXACT.sh'])
    essentials={'base':['.complete','config.json','tokenizer.json'],
                'checkpoint':['head.pt','adapter_config.json','adapter_model.safetensors'],
                'kev_code':['kev/api.py','kev/model.py','kev/predictors.py','kev/checkpoint.py','kev/data.py']}
    for role in ['base','checkpoint','kev_code']:
        root=Path(c[role]);require(root.is_dir(),'Missing dependency directory '+role)
        for name in essentials[role]:require((root/name).is_file(),'Missing required loader file '+str(root/name))
        needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    require(any(Path(c['base']).glob('*.safetensors')),'Missing base weights')
    return needed

def verify(config_path):
    import pyarrow.parquet as pq
    c=load(config_path);out=Path(c['out']);identity=stamp(c);ch=sha(config_path);needed=required_files(c)
    require(needed<=set(c['files']),'Required dependency omitted')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
    require(c.get('mode')=='inference','Not an inference config')
    require(not any((out/n).exists() for n in ('FAILED','ERROR.json')),'Conflicting failure marker')
    require(sha(c['data'])==DATA_SHA,'Wrong dataset');require(sha(c['scorer'])==SCORER_SHA,'Scorer differs')
    os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD']='0'
    import torch
    head=torch.load(Path(c['checkpoint'])/'head.pt',map_location='cpu',weights_only=True)
    require((head['base'],head['base_revision'],head['temperature'])==(c['base_id'],c['base_revision'],c['temperature']),'Checkpoint metadata mismatch')
    require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base revision mismatch')
    env=load(out/'ENVIRONMENT.json');require(env['temperature']==head['temperature'] and env['head_sha256']==sha(Path(c['checkpoint'])/'head.pt'),'Environment/checkpoint mismatch')
    same(env['runtime'],c['runtime'],'runtime')
    require(env['model']['dtype']=='float32' and env['model']['attention']=='eager' and env['model']['backend']=='torch','Execution precision/backend differs')
    launch=load(out/'LAUNCH_RECEIPT.json')
    require(launch['config_sha256']==ch and launch['image']==c['image'] and launch['wrapper_sha256']==sha(out/'run.sh'),'Launch config/image/wrapper binding differs')
    rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population mismatch')
    for raw in rows:
        qs=json.loads(raw['questions']);gold=json.loads(raw['gold'])
        require(raw['split']=='test' and len(qs)==5 and list(qs)==list(gold),'Dataset question population/order differs')
        for name,q in qs.items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(candidate_keys(q)),'Dataset gold candidates differ')
    names=[f'{i:06d}.json' for i in range(400)];require(sorted(p.name for p in (out/'records').glob('*.json'))==names,'Receipt coverage mismatch')
    predictions=[validate_receipt(load(out/'records'/name),raw,i,identity,c['temperature']) for i,(name,raw) in enumerate(zip(names,rows))]
    report=load(out/'report.json');require(report['identity']==identity and report['rows']==400 and report['questions']==2000,'Report identity mismatch')
    pre=load(out/'PREFLIGHT.json');require(pre['identity']==identity and pre['rows']==400 and pre['questions']==2000 and len(pre['items'])==400,'Preflight differs')
    require(pre['context']==c['context']=={'max_state':8192,'max_branch':8192,'max_packed':16384},'Context differs')
    for i,(item,row) in enumerate(zip(pre['items'],rows)):
        request={'state':json.loads(row['state']),'questions':json.loads(row['questions'])}
        require(item['index']==i and item['id']==row['id'] and item['input_sha256']==stamp(row) and item['request_ordered_sha256']==stamp(request,False),'Preflight identity differs')
        receipt_value=load(out/'records'/f'{i:06d}.json')['payload']
        require(receipt_value['tokens']==item['tokens'] and receipt_value['tokens_sha256']==item['tokens_sha256'] and receipt_value['prediction']['input_tokens']==item['tokens'],'Actual/preflight token binding differs')
        require(item['candidate_keys']==[candidate_keys(q) for q in request['questions'].values()] and type(item['tokens'])is int and 0<item['tokens']<=16384 and type(item['state_tokens'])is int and 0<item['state_tokens']<=8192 and re.fullmatch('[0-9a-f]{64}',item['tokens_sha256']),'Preflight token metadata differs')
    require(pre['max_tokens']==max(i['tokens'] for i in pre['items']),'Preflight maximum differs')
    verify_probe(load(out/'PROBE.json'),identity,c['temperature'])
    panels={};flags=[]
    for name,temp in [('serving',c['temperature']),('raw_T1',1.)]:
        panels[name]=summaries(rows,predictions,temp);same(report[name],panels[name],name)
        for group in ['by_type','by_workflow']:
            for cell,values in panels[name][group].items():
                if values['n']<30:flags.append({'panel':name,'group':group,'cell':cell,'reason':'small_count'})
                for metric,value in values.items():
                    if metric!='n' and value in (0.,1.):flags.append({'panel':name,'group':group,'cell':cell,'metric':metric,'reason':'extreme_metric'})
            for metric in ['accuracy','kl_from_gold','brier','ece10']:
                if len({v[metric] for v in panels[name][group].values()})==1:flags.append({'panel':name,'group':group,'metric':metric,'reason':'identical_cells'})
    terminal=load(out/'inference-COMPLETE.json');require(type(terminal['rc'])is int and terminal['rc']==0 and terminal['config_sha256']==ch and terminal['stage']=='completed' and terminal['progress']==terminal['total']==400,'Terminal differs')
    for name in ['PREFLIGHT.json','PROBE.json','report.json']:require(terminal['outputs'][name]==sha(out/name),'Terminal output binding differs')
    require(re.fullmatch(r'rc=0 utc=\S+\n?',(out/'EXIT').read_text()) and (out/'EXIT').stat().st_mtime_ns>=(out/'inference-COMPLETE.json').stat().st_mtime_ns>=max((out/n).stat().st_mtime_ns for n in ('PREFLIGHT.json','PROBE.json','report.json')),'Wrapper/terminal chronology differs')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed during audit')
    require(sha(config_path)==ch,'Config changed during audit')
    return {'status':'VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED','rows':400,'questions':2000,'config_sha256':ch,'report_sha256':sha(out/'report.json'),'frozen_files':len(c['files']),'required_files':len(needed),'panels':panels,'review_flags':flags,'scope':'Independent logits-to-metrics and artifact checks; token hashes provenance-bound, not independently retokenized; wire answers preserved but not independently validated; Docker identity must separately be verified.'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();require(not Path(a.out).exists(),'Existing audit output preserved');v=verify(a.config);Path(a.out).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
