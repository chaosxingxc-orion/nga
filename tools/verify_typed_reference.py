#!/usr/bin/env python3
"""Independent E26 artifact and metric verification; no driver/native metric imports."""
import argparse,hashlib,json,math,os,re
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
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

def required_files(c):
    needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
    needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_reference_kev.py','verify_typed_reference.py','run.sh','LAUNCH_EXACT.sh'])
    for role in ['base','checkpoint','kev_code']:
        needed.update(str(p.resolve()) for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    return needed

def verify(config_path):
    import pyarrow.parquet as pq
    c=load(config_path);out=Path(c['out']);identity=stamp(c);ch=sha(config_path);needed=required_files(c)
    require(needed<=set(c['files']),'Required dependency omitted')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
    require(sha(c['data'])==DATA_SHA,'Wrong dataset');require(sha(c['scorer'])=='6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8','Scorer differs')
    os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD']='0'
    import torch
    head=torch.load(Path(c['checkpoint'])/'head.pt',map_location='cpu',weights_only=True)
    require((head['base'],head['base_revision'],head['temperature'])==(c['base_id'],c['base_revision'],c['temperature']),'Checkpoint metadata mismatch')
    require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base revision mismatch')
    env=load(out/'ENVIRONMENT.json');require(env['temperature']==head['temperature'] and env['head_sha256']==sha(Path(c['checkpoint'])/'head.pt'),'Environment/checkpoint mismatch')
    rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Population mismatch')
    names=[f'{i:06d}.json' for i in range(400)];require(sorted(p.name for p in (out/'records').glob('*.json'))==names,'Receipt coverage mismatch')
    predictions=[validate_receipt(load(out/'records'/name),raw,i,identity,c['temperature']) for i,(name,raw) in enumerate(zip(names,rows))]
    report=load(out/'report.json');require(report['identity']==identity and report['rows']==400 and report['questions']==2000,'Report identity mismatch')
    pre=load(out/'PREFLIGHT.json');require(pre['identity']==identity and pre['rows']==400 and pre['questions']==2000 and len(pre['items'])==400,'Preflight differs')
    require(pre['context']==c['context']=={'max_state':8192,'max_branch':8192,'max_packed':16384},'Context differs')
    for i,(item,row) in enumerate(zip(pre['items'],rows)):
        request={'state':json.loads(row['state']),'questions':json.loads(row['questions'])}
        require(item['index']==i and item['id']==row['id'] and item['input_sha256']==stamp(row) and item['request_ordered_sha256']==stamp(request,False),'Preflight identity differs')
        require(item['candidate_keys']==[candidate_keys(q) for q in request['questions'].values()] and 0<item['tokens']<=16384 and re.fullmatch('[0-9a-f]{64}',item['tokens_sha256']),'Preflight token metadata differs')
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
    terminal=load(out/'inference-COMPLETE.json');require(terminal['rc']==0 and terminal['config_sha256']==ch and terminal['stage']=='completed','Terminal differs')
    for name in ['PREFLIGHT.json','report.json']:require(terminal['outputs'][name]==sha(out/name),'Terminal output binding differs')
    require(re.fullmatch(r'rc=0 utc=\S+\n?',(out/'EXIT').read_text()) and (out/'EXIT').stat().st_mtime_ns>=(out/'inference-COMPLETE.json').stat().st_mtime_ns,'Wrapper differs')
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed during audit')
    require(sha(config_path)==ch,'Config changed during audit')
    return {'status':'VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED','rows':400,'questions':2000,'config_sha256':ch,'report_sha256':sha(out/'report.json'),'frozen_files':len(c['files']),'required_files':len(needed),'panels':panels,'review_flags':flags,'scope':'Independent logits-to-metrics and artifact checks; token hashes provenance-bound, not independently retokenized; wire answers preserved but not independently validated; Docker identity must separately be verified.'}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();v=verify(a.config);Path(a.out).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
