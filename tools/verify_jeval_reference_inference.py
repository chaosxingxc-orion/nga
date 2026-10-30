#!/usr/bin/env python3
"""Independent E33 full-population artifact and metric arithmetic audit."""
import argparse,collections,hashlib,json,math,re
from pathlib import Path
DATA_SHA='88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82'
def require(x,msg):
 if not x:raise ValueError(msg)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def validate_probe(probes,eligible,rows):
 require(isinstance(probes,list) and len(probes)==4,'Probe population')
 for i,kind in enumerate(['choice','noul','score']):
  req=probes[i]['request'];q={'type':kind,'instructions':'Choose the appropriate synthetic level.'}
  if kind!='noul':q['criteria']={'a':'first','b':'second'} if kind=='choice' else ['low','middle','high']
  require(req=={'state':'Synthetic observation: choose the first level.','questions':{'q':q}},'Synthetic probe identity')
 boundary=max((e for e in eligible['items'] if e['status']=='eligible'),key=lambda e:(e.get('max_tokens',0),-e['index']))
 b=probes[3];require(b['boundary_index']==boundary['index'] and b['input_sha256']==stamp(rows[boundary['index']]) and b['max_tokens']==boundary['max_tokens'],'Boundary probe identity')
 require(b['chips']==1 and math.isfinite(b['reserved_gib']) and b['reserved_gib']>0,'Probe memory/chips')
 for probe in probes:
  passes=probe['passes'];require(len(passes)==2,'Probe repetitions')
  for one in passes:
   require(type(one['seconds']) in (float,int) and math.isfinite(one['seconds']) and one['seconds']>0,'Probe duration')
   pp=one['prediction']['native_probabilities'];require(pp and all(math.isfinite(v) and 0<=v<=1 for v in pp.values()),'Probe probabilities')
  a=passes[0]['prediction']['native_probabilities'];b=passes[1]['prediction']['native_probabilities'];require(list(a)==list(b) and max(abs(a[k]-b[k]) for k in a)<=1e-5,'Probe drift')
 return True

def checkpoint_binding(c):
 require(c['runtime']=={'torch':'2.10.0+cpu','torch_npu':'2.10.0.post7','transformers':'5.14.1','peft':'0.21.2'},'Frozen runtime protocol')
 if c['family']=='kev':
  import torch
  meta=torch.load(Path(c['checkpoint'])/'head.pt',map_location='cpu',weights_only=True)
  require((meta['base'],meta['base_revision'],meta['temperature'])==(c['base_id'],c['base_revision'],c['temperature']),'Kev checkpoint metadata')
 elif c['family']=='openjev':
  meta=load(Path(c['checkpoint'])/'model.json');require((meta['model_id'],meta['revision'],meta['max_length'])==(c['base_id'],c['base_revision'],4096),'OpenJev checkpoint metadata')
  require(load(Path(c['checkpoint'])/'temperature.json')['temperature']==c['temperature'],'OpenJev checkpoint temperature')
 else:require(c['temperature']==1.,'Nimble native temperature')

def check(path):
 import pyarrow.parquet as pq
 c=load(path);require(c['family'] in ('kev','openjev','nimble'),'Unsupported family');run=Path(c['out']);ch=sha(path);term=load(run/'COMPLETE.json');report=load(run/'report.json');lc=load(run/'LAUNCH_RECEIPT.json')
 require(term['rc']==0 and term['stage']=='completed' and term['progress']==term['total']==11257,'Inference incomplete')
 require(ch==term['config_sha256']==report['config_sha256']==lc['config_sha256'],'Config identity')
 require(lc['command']==['bash',str(run/'run.sh')] and lc['image']==c['image'] and lc['wrapper_sha256']==sha(run/'run.sh'),'Launch binding')
 require(re.fullmatch(r'rc=0 utc=\S+\n?',(run/'EXIT').read_text()),'Wrapper failure')
 require((run/'report.json').stat().st_mtime_ns<=(run/'COMPLETE.json').stat().st_mtime_ns<=(run/'EXIT').stat().st_mtime_ns,'Terminal chronology')
 require(set(term['outputs'])=={'report.json','PROBE.json'},'Required terminal outputs')
 for name,h in term['outputs'].items():require(Path(name).name==name and sha(run/name)==h,'Output hash')
 roles=['base','code','adapter' if c['family']=='nimble' else 'checkpoint'];needed={str(Path(c[k]).resolve()) for k in ['data','preregistration','eligibility_config','eligibility_report']}
 needed.update(str((run/n).resolve()) for n in ['jeval_reference_inference.py','jeval_reference_preflight.py','verify_jeval_reference_inference.py','prepare_jeval_reference_inference.py','jeval_reference_finish.py','test_jeval_reference_inference.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 needed.update(str(Path(c[k]).resolve()) for k in ['probe_config','probe_report','probe_review'])
 for role in roles:
  root=Path(c[role]);require(root.is_dir(),'Missing native root');needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
 require(needed<=set(c['files']),'Required dependency omitted')
 for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency')
 checkpoint_binding(c)
 require(sha(c['data'])==DATA_SHA,'Wrong data');rows=pq.read_table(c['data']).to_pylist();require(len(rows)==11257 and len({r['id'] for r in rows})==11257,'Dataset population')
 require(c['mode']=='inference','Final inference mode')
 pc=load(c['probe_config']);pt=load(Path(pc['out'])/'COMPLETE.json');pr=load(c['probe_review']);require(pt['rc']==0 and pt['stage']=='probe_completed' and pt['config_sha256']==pr['approved_probe_config_sha256']==sha(c['probe_config']),'Probe approval identity')
 require(sha(run/'PROBE.json')==sha(c['probe_report'])==pt['outputs']['PROBE.json']==pr['approved_probe_sha256'],'Approved probe report')
 eligible=load(c['eligibility_report']);validate_probe(load(run/'PROBE.json'),eligible,rows);ec=load(c['eligibility_config']);require(eligible['config_sha256']==sha(c['eligibility_config']),'Eligibility binding')
 for role in roles:
  require(c[role]==ec[role],'Native path changed');prefix=str(Path(c[role]).resolve())+'/'
  require({p:h for p,h in c['files'].items() if p.startswith(prefix)}=={p:h for p,h in ec['files'].items() if p.startswith(prefix)},'Native closure changed')
 paths=sorted((run/'records').glob('*.json'));require([p.name for p in paths]==[f'{i:06d}.json' for i in range(11257)],'Receipt coverage');counts=collections.Counter();ct=st=correct=0;bs=[];se=[];bins=[[] for _ in range(10)]
 for i,(raw,p) in enumerate(zip(rows,paths)):
  env=load(p);v=env['payload'];qs=json.loads(raw['questions_json']);require(len(qs)==1,'Question count');name,q=next(iter(qs.items()));kind=q['type'];ks=['false','true'] if kind=='noul' else list(q['criteria']) if kind=='choice' else list(map(str,range(len(q['criteria']))));g=json.loads(raw['label_json']);req={'state':raw['state'],'questions':qs};e=eligible['items'][i]
  require(stamp(v)==env['sha256'] and v['index']==i and v['id']==raw['id'] and v['input_sha256']==stamp(raw) and v['request_sha256']==stamp(req) and v['config_sha256']==ch,'Receipt identity')
  require(e['index']==i and e['id']==raw['id'] and e['input_sha256']==stamp(raw),'Eligibility item identity')
  actual=v['eligibility'];require(all(e.get(k)==x for k,x in actual.items()),'Eligibility values changed')
  counts[v['status']]+=1
  if kind=='score':st+=1
  else:ct+=1
  if e['status']!='eligible':require(v['status']==e['status'] and 'answer'not in v,'Ineligible inference fabricated');continue
  require(v['status']=='valid' and v['seconds']>0 and math.isfinite(v['seconds']),'Eligible result missing')
  require(v['consumed_token_sha256']==e['token_sha256'],'Consumed tokens')
  z=v['logits'];require(len(z)==len(ks) and all(math.isfinite(x) for x in z),'Logit shape');temp=1 if c['family']=='kev' else c['temperature'];ex=[math.exp((x-max(z))/temp) for x in z];prob=[x/sum(ex) for x in ex];native=v['native_probabilities'];require(list(native)==ks and max(abs(native[k]-x) for k,x in zip(ks,prob))<1e-5,'Native probability/logit arithmetic')
  a=v['answer'];require(a['type']==kind,'Answer type')
  # Independent native wire reconstruction from saved probabilities.
  pp=list(native.values());best=max(range(len(ks)),key=pp.__getitem__)
  rounder=(lambda x:round(float(x),4)) if c['family']=='kev' else float
  if kind=='noul':
   require(set(a)=={'type','noul'} and abs(a['noul']-rounder(pp[1]))<1e-8,'Noul wire');ret=a['noul']>=.5;probs={'false':1-a['noul'],'true':a['noul']};conf=a['noul'] if ret else 1-a['noul'];target='true' if g else 'false'
  else:
   require(list(a['probabilities'])==ks,'Wire candidate order');probs=a['probabilities'];wirepp=pp if c['family']!='openjev' else [x/sum(pp) for x in pp]
   require(max(abs(probs[k]-rounder(x)) for k,x in zip(ks,wirepp))<1e-8,'Wire probabilities')
   conf=a['confidence'];require(math.isfinite(conf) and 0<=conf<=1,'Wire confidence')
   if kind=='choice':
    require(set(a)=={'type','choice','probabilities','confidence'} and a['choice']==ks[best],'Returned choice');ret=a['choice'];target=g
    expect=wirepp[best] if c['family']=='nimble' else 1. if len(ks)==1 else (max(wirepp)/sum(wirepp)-1/len(ks))/(1-1/len(ks));require(abs(conf-rounder(expect))<1e-7,'Native choice confidence')
   else:
    require(set(a)=={'type','score','probabilities','confidence','legend'} and list(a['legend'])==ks,'Score response schema')
    require(list(a['legend'].values())==q['criteria'],'Score legend differs')
    expect=best if c['family']=='nimble' else sum(j*x for j,x in enumerate(wirepp));require(abs(a['score']-rounder(expect))<1e-7,'Returned score')
    if c['family']=='nimble':expected_conf=wirepp[best]
    elif len(ks)==1:expected_conf=1.
    else:
     norm=[x/sum(wirepp) for x in wirepp];deviation=sum(abs(j-(len(ks)-1)/2) for j in range(len(ks)))/len(ks);expected_conf=max(0.,1-sum(x*abs(j-best) for j,x in enumerate(norm))/deviation)
    require(abs(conf-rounder(expected_conf))<1e-7,'Score native confidence');se.append(abs(a['score']-g));continue
  ok=int(ret==g);correct+=ok;bs.append(sum((probs[k]-int(k==target))**2 for k in ks));bins[min(int(conf*10),9)].append((ok,conf))
 require(ct==10938 and st==319,'Metric population');n=len(bs);computed=dict(total=ct,valid=n,invalid_or_ineligible=ct-n,correct=correct,accuracy=correct/ct,raw_brier=sum(bs)/n if n else None,ece10=sum(abs(sum(a-b for a,b in group)) for group in bins)/n if n else None);score=dict(total=st,valid=len(se),invalid_or_ineligible=st-len(se),native_scale_mae=sum(se)/len(se) if se else None)
 for actual,expected in [(report['classification'],computed),(report['score'],score)]:
  require(set(actual)==set(expected),'Metric keys')
  for k,x in expected.items():require(actual[k]is None if x is None else abs(actual[k]-x)<1e-10,'Metric differs '+k)
 require(report['status_counts']==dict(counts),'Status counts');flags=[]
 if computed['accuracy'] in (0,1):flags.append('classification accuracy at exact boundary')
 return dict(status='VERIFIED_SCOPED',config_sha256=ch,report_sha256=sha(run/'report.json'),rows=11257,classification=computed,score=score,status_counts=dict(counts),review_flags=flags,required_files=len(needed),scope='Independent native-response reconstruction and metric arithmetic; consumed-token hash binding, not independent retokenization; Docker state checked by finisher.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(check(a.config),indent=2)+'\n')
