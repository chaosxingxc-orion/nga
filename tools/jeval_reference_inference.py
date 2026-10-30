#!/usr/bin/env python3
"""E33 JEVal native inference and explicitly local paper-formula scoring."""
import argparse,collections,copy,fcntl,hashlib,importlib.util,json,math,os,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from jeval_reference_preflight import DATA_SHA,TOTAL,atomic,check,keys,request,require,schema,sha,stamp
CONTEXT={'max_state':8192,'max_branch':8192,'max_packed':16384}

def finite(v):return type(v) in (int,float) and math.isfinite(v)
def softmax(z,temp=1.):
 require(z and all(finite(v) for v in z) and finite(temp) and temp>0,'Invalid logits/temperature')
 e=[math.exp((x-max(z))/temp) for x in z];return [x/sum(e) for x in e]
def question(raw):return next(iter(request(raw)['questions'].items()))
def gold(raw):
 _,q=question(raw);g=json.loads(raw['label_json'])
 if q['type']=='choice':require(type(g)is str and g in keys(q),'Invalid choice gold')
 elif q['type']=='noul':require(type(g)in(int,bool) and g in (0,1),'Invalid noul gold');g=bool(g)
 else:require(finite(g) and 0<=g<=len(keys(q))-1,'Invalid score gold')
 return g

def response(q,answer):
 """Validate actual returned values; never repair or normalize probabilities."""
 kind=q['type'];ks=keys(q);require(isinstance(answer,dict) and answer.get('type')==kind,'Wrong answer type')
 allowed={'choice':{'type','choice','probabilities','confidence'},'noul':{'type','noul'},'score':{'type','score','probabilities','confidence','legend'}}[kind]
 require(set(answer)==allowed,'Unexpected/missing native response fields')
 if kind=='noul':
  p=answer['noul'];require(finite(p) and 0<=p<=1,'Invalid noul')
  return dict(returned=p>=.5,probabilities={'false':1-p,'true':p},confidence=p if p>=.5 else 1-p)
 p=answer['probabilities'];require(isinstance(p,dict) and list(p)==ks and all(finite(v) and 0<=v<=1 for v in p.values()),'Invalid probability vector')
 conf=answer['confidence'];require(finite(conf) and 0<=conf<=1,'Invalid confidence')
 if kind=='choice':
  selected=answer['choice'];require(type(selected)is str and selected in ks,'Invalid returned choice')
 else:
  selected=answer['score'];require(finite(selected) and 0<=selected<=len(ks)-1,'Invalid returned score')
  require(isinstance(answer['legend'],dict) and list(answer['legend'])==ks,'Invalid legend')
 return dict(returned=selected,probabilities=p,confidence=conf)

def summarize(rows,items):
 require(len(rows)==len(items),'Missing item');counts=collections.Counter();classification=[];scores=[];valid_class=0;class_total=0;score_total=0;correct=0
 for raw,item in zip(rows,items):
  _,q=question(raw);kind=q['type'];g=gold(raw);counts[item['status']]+=1
  if kind=='score':score_total+=1
  else:class_total+=1
  if item['status']!='valid':continue
  a=response(q,item['answer'])
  if kind=='score':scores.append(abs(a['returned']-g));continue
  target=('true' if g else 'false') if kind=='noul' else g
  ok=a['returned']==g;correct+=ok;valid_class+=1
  classification.append(dict(ok=int(ok),confidence=a['confidence'],brier=sum((p-int(k==target))**2 for k,p in a['probabilities'].items())))
 n=valid_class;bins=[[] for _ in range(10)]
 for x in classification:bins[min(int(x['confidence']*10),9)].append(x)
 return dict(rows=len(rows),status_counts=dict(counts),classification=dict(total=class_total,valid=n,invalid_or_ineligible=class_total-n,correct=correct,accuracy=correct/class_total if class_total else None,raw_brier=sum(x['brier'] for x in classification)/n if n else None,ece10=sum(abs(sum(x['ok']-x['confidence'] for x in b)) for b in bins)/n if n else None),score=dict(total=score_total,valid=len(scores),invalid_or_ineligible=score_total-len(scores),native_scale_mae=sum(scores)/len(scores) if scores else None),scope='Local native-response implementation of JEVal formulas; ECE native choice confidence/binary selected probability and right bin boundary are local conventions, not exact paper scorer reproduction.')

def input_record(req):
 value=copy.deepcopy(req)
 for q in value['questions'].values():q.update(label=keys(q)[0] if q['type']=='choice' else 0,src='jeval-reference')
 return value

def verify_files(c):
 require(c['family'] in ('kev','openjev','nimble'),'Unsupported family')
 roles={'kev':{'base','code','checkpoint'},'openjev':{'base','code','checkpoint'},'nimble':{'base','code','adapter'}}[c['family']]
 needed={str(Path(c[k]).resolve()) for k in ['data','preregistration','eligibility_config','eligibility_report']}
 needed.update(str(Path(c['out'],n).resolve()) for n in ['jeval_reference_inference.py','jeval_reference_preflight.py','prepare_jeval_reference_inference.py','verify_jeval_reference_inference.py','jeval_reference_finish.py','test_jeval_reference_inference.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 for role in roles:
  root=Path(c[role]);require(root.is_dir(),'Missing native dependency root');needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
 if c['mode']=='inference':needed.update(str(Path(c[k]).resolve()) for k in ['probe_config','probe_report','probe_review'])
 require(needed<=set(c['files']),'Missing frozen dependency')
 for p,h in c['files'].items():require(sha(p)==h,'Frozen file differs '+p)
 require(sha(c['data'])==DATA_SHA,'Wrong JEVal dataset')
 e=json.loads(Path(c['eligibility_config']).read_text());report=json.loads(Path(c['eligibility_report']).read_text())
 require(report['config_sha256']==sha(c['eligibility_config']) and report['rows']==TOTAL and report['data_sha256']==DATA_SHA,'Eligibility report binding')
 for role in roles:
  require(c[role]==e[role],'Eligibility native path differs')
  prefix=str(Path(c[role]).resolve())+'/'
  require({p:h for p,h in c['files'].items() if p.startswith(prefix)}=={p:h for p,h in e['files'].items() if p.startswith(prefix)},'Eligibility native source differs')
 require(c['temperature']==e['temperature'],'Eligibility temperature differs')
 return report

class Native:
 def __init__(self,c):
  import torch,torch_npu,transformers,peft
  from transformers import AutoTokenizer
  self.c=c;self.torch=torch;sys.path.insert(0,c['code']);self.family=c['family'];require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base revision differs')
  require({k:m.__version__ for k,m in [('torch',torch),('torch_npu',torch_npu),('transformers',transformers),('peft',peft)]}==c['runtime'],'Runtime differs')
  torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False;torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8)
  self.tok=AutoTokenizer.from_pretrained(c.get('adapter',c['base']),local_files_only=True)
  if self.family=='kev':
   from kev.api import SystemOneRequest,to_record,to_answers
   from kev.model import encode,ContextOverflow
   from kev.checkpoint import Checkpoint,LoadOptions
   import kev.predictors as predictors
   meta=torch.load(Path(c['checkpoint'])/'head.pt',map_location='cpu',weights_only=True)
   require((meta['base'],meta['base_revision'],meta['temperature'])==(c['base_id'],c['base_revision'],c['temperature']),'Kev metadata differs')
   ck=Checkpoint(c['checkpoint']);ck.meta.base,ck.meta.base_revision=c['base'],None;predictors.Checkpoint=lambda _:ck;predictors.sync=lambda _:torch.npu.synchronize()
   self.model=predictors.LocalPredictor(c['checkpoint'],'npu:0',LoadOptions(dtype=torch.float32,attn='eager',merge=True),context=CONTEXT)
   require(all(p.dtype==torch.float32 for p in self.model.model.parameters() if p.is_floating_point()),'Kev native FP32 parameters')
   self.tok=self.model.tok;self.native=(SystemOneRequest,to_record,encode,ContextOverflow);self.to_answers=to_answers
   self.original_encode=self.model.model.encode
   def recorded(*a,**kw):
    enc=self.original_encode(*a,**kw);self.consumed=stamp(enc['ids']);return enc
   self.model.model.encode=recorded
  elif self.family=='openjev':
   from jev.api import compile_request,candidate_prompts,format_response
   from jev.model import DecisionModel
   self.native=(compile_request,candidate_prompts);self.format=format_response
   os.environ['JEV_TORCH_DTYPE']='bfloat16'
   for key in ['JEV_LOAD_8BIT','JEV_LOAD_4BIT','JEV_DEVICE_MAP','JEV_MAX_MEMORY']:os.environ.pop(key,None)
   class Local(DecisionModel):
    def __init__(self,model_id,revision,**kw):
     require((model_id,revision)==(c['base_id'],c['base_revision']),'OpenJev base differs');super().__init__(c['base'],None,**kw)
   require(json.loads(Path(c['checkpoint'],'temperature.json').read_text())['temperature']==c['temperature'],'OpenJev temperature differs')
   require(json.loads(Path(c['checkpoint'],'temperature.json').read_text())['temperature']==c['temperature'],'OpenJev checkpoint temperature')
   self.model=Local.load(c['checkpoint'],device='npu:0');self.tok=self.model.tokenizer
   require(self.model.max_length==4096 and str(self.model.head.weight.dtype)=='torch.float32' and str(next(self.model.backbone.parameters()).dtype)=='torch.bfloat16','OpenJev native precision/context')
   require(hasattr(self.model.backbone,'peft_config') and not any(getattr(m,'merged',False) for m in self.model.backbone.modules()),'OpenJev adapter merged')
   require(self.model.backbone.config._attn_implementation=='sdpa','OpenJev attention')
  else:
   require(c['temperature']==1.,'Nimble release temperature')
   from transformers import Qwen3_5ForConditionalGeneration
   from peft import PeftModel
   from nimble.scoring.release_contract import prompt_builder
   from nimble.scoring.parallel_schema import prepare_prompts
   from nimble.scoring.cuda_scorer import candidate_projection
   self.native=prompt_builder(c['adapter'],self.tok);require(self.native is prepare_prompts,'Not Nimble v1');self.projection=candidate_projection
   base,loading=Qwen3_5ForConditionalGeneration.from_pretrained(c['base'],local_files_only=True,dtype=torch.bfloat16,device_map='cpu',attn_implementation='sdpa',output_loading_info=True)
   require(not any(loading.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']),'Nimble base loading')
   self.model=PeftModel.from_pretrained(base,c['adapter'],local_files_only=True).merge_and_unload(safe_merge=True).eval().to('npu:0')
 def eligibility(self,req):return check(req,self.family,self.tok,self.native)
 def predict(self,req,eligible):
  name,q=next(iter(req['questions'].items()));ks=keys(q);torch=self.torch
  if self.family=='kev':
   self.consumed=None;p=self.model(input_record(req));require(self.consumed==eligible['token_sha256'],'Kev consumed tokens differ')
   require(p['input_tokens']==eligible['max_tokens'] and p['inference_temperature']==self.c['temperature'],'Kev output provenance')
   z=list(p['logits'][name].values());probs=list(p['probabilities'][name].values());require(list(p['logits'][name])==list(p['probabilities'][name])==ks,'Kev candidate order')
   require(max(abs(a-b) for a,b in zip(softmax(z),probs))<1e-5,'Kev softmax')
   _,meta=self.native[1](self.native[0].model_validate(req));answer=self.to_answers([probs],meta)[name]
   return dict(answer=answer,native_probabilities=dict(zip(ks,probs)),logits=z,logits_temperature='already_scaled',consumed_token_sha256=self.consumed)
  if self.family=='openjev':
   record=self.native[0](req['state'],req['questions'])[0]
   owner=self;original=self.model.tokenizer
   class Recorder:
    def __getattr__(self,k):return getattr(original,k)
    def __call__(self,*a,**kw):
     result=original(*a,**kw);require(kw.get('truncation')is False,'OpenJev truncation');ids=result['input_ids'].tolist();masks=result['attention_mask'].tolist();clean=[]
     for row,mask in zip(ids,masks):
      n=sum(mask);require(mask==[1]*n+[0]*(len(mask)-n),'OpenJev padding');clean.append(row[:n])
     owner.consumed=[stamp(x) for x in clean];return result
   self.model.tokenizer=Recorder();self.consumed=None
   try:
    with torch.inference_mode():z=self.model([record])[0].float().cpu().tolist()
   finally:self.model.tokenizer=original
   require(self.consumed==eligible['token_sha256'],'OpenJev consumed tokens differ');probs=softmax(z,self.c['temperature']);answer=self.format([record],[probs])['answers'][name]
   return dict(answer=answer,native_probabilities=dict(zip(ks,probs)),logits=z,logits_temperature='unscaled',consumed_token_sha256=self.consumed)
  p=self.native(self.tok,req['state'],schema(req),2048,system_role=True);ids=p.full_ids[0];require(stamp(ids)==eligible['token_sha256'] and p.candidate_ids[0]==eligible['candidate_token_ids'],'Nimble consumed tokens differ')
  with torch.inference_mode():
   hidden=self.model.model(input_ids=torch.tensor([ids],device='npu:0'),use_cache=False).last_hidden_state[:,-1,:];z=self.projection(hidden,self.model.get_output_embeddings().weight,p.candidate_ids[0])[0];probs=torch.softmax(z,dim=-1).cpu().tolist();z=z.float().cpu().tolist()
  best=max(range(len(z)),key=z.__getitem__)
  # Nimble typed enum is argmax, including numeric level enums. No expectation substitution.
  if q['type']=='noul':answer={'type':'noul','noul':probs[1]}
  elif q['type']=='choice':answer={'type':'choice','choice':ks[best],'probabilities':dict(zip(ks,probs)),'confidence':probs[best]}
  else:answer={'type':'score','score':best,'probabilities':dict(zip(ks,probs)),'confidence':probs[best],'legend':dict(zip(ks,q['criteria']))}
  return dict(answer=answer,native_probabilities=dict(zip(ks,probs)),logits=z,logits_temperature='unscaled',consumed_token_sha256=stamp(ids))

def run(path):
 blob=path.read_bytes();ch=hashlib.sha256(blob).hexdigest();c=json.loads(blob);out=Path(c['out']);lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 require(not(out/'COMPLETE.json').exists(),'Existing terminal preserved');status=dict(stage='verify',progress=0,total=TOTAL,chips=1);stop=threading.Event();outputs={};rc=1;error=None
 def heartbeat():
  while not stop.wait(10):
   snap=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status);atomic(out/'STATUS.json',snap)
   (out/'digest.md').write_text(snap['utc']+' '+snap['stage']+' '+str(snap['progress'])+'/'+str(snap['total'])+' q/s/chip='+str(snap.get('questions_per_second_per_chip'))+' chips=1 reserved_GiB='+str(snap.get('reserved_gib'))+'\n')
   with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(snap)+'\n')
 t=threading.Thread(target=heartbeat,daemon=True);t.start()
 try:
  require(c['mode'] in ('probe','inference'),'Mode differs');elig=verify_files(c);os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');sys.dont_write_bytecode=True
  import pyarrow.parquet as pq
  rows=pq.read_table(c['data']).to_pylist();require(len(rows)==TOTAL and len({r['id'] for r in rows})==TOTAL,'Population differs');require(collections.Counter(question(r)[1]['type'] for r in rows)=={'choice':9582,'noul':1356,'score':319},'Type denominator differs')
  status['stage']='load_model';model=Native(c);folder=out/'records';folder.mkdir(exist_ok=True);require(all(p.name in {f'{i:06d}.json' for i in range(TOTAL)} for p in folder.glob('*.json')),'Extra receipt')
  if c['mode']=='probe':
   # A fixed synthetic request probes each type twice before any test forward.
   probes=[]
   for kind in ['choice','noul','score']:
    q={'type':kind,'instructions':'Choose the appropriate synthetic level.'}
    if kind!='noul':q['criteria']={'a':'first','b':'second'} if kind=='choice' else ['low','middle','high']
    req={'state':'Synthetic observation: choose the first level.','questions':{'q':q}};e=model.eligibility(req);require(e['status']=='eligible','Synthetic ineligible');passes=[]
    for _ in range(2):
     model.torch.npu.synchronize();start=time.monotonic();p=model.predict(req,e);model.torch.npu.synchronize();passes.append(dict(prediction=p,seconds=time.monotonic()-start));response(q,p['answer'])
    require(max(abs(x-y) for x,y in zip(passes[0]['prediction']['native_probabilities'].values(),passes[1]['prediction']['native_probabilities'].values()))<=1e-5,'Synthetic probability drift');probes.append(dict(request=req,passes=passes))
   # Deterministic largest eligible input is a correctness/efficiency admission,
   # selected from token metadata before looking at any predictions.
   boundary=max((e for e in elig['items'] if e['status']=='eligible'),key=lambda e:(e['max_tokens'],-e['index']))
   raw=rows[boundary['index']];req=request(raw);be=model.eligibility(req);require(all(boundary.get(k)==v for k,v in be.items()),'Boundary eligibility differs');passes=[];status['stage']='longest_eligible_probe'
   for _ in range(2):
    model.torch.npu.synchronize();start=time.monotonic();p=model.predict(req,be);model.torch.npu.synchronize();seconds=time.monotonic()-start;response(question(raw)[1],p['answer']);passes.append(dict(prediction=p,seconds=seconds));status.update(questions_per_second_per_chip=1/seconds,reserved_gib=model.torch.npu.memory_reserved()/2**30)
   require(max(abs(x-y) for x,y in zip(passes[0]['prediction']['native_probabilities'].values(),passes[1]['prediction']['native_probabilities'].values()))<=1e-5,'Longest eligible repeat drift')
   probes.append(dict(boundary_index=boundary['index'],input_sha256=stamp(raw),max_tokens=boundary['max_tokens'],passes=passes,chips=1,reserved_gib=model.torch.npu.memory_reserved()/2**30))
   require(all(finite(x['seconds']) and x['seconds']>0 for p in probes for x in p['passes']),'Probe duration')
   verify_files(c);require(sha(path)==ch,'Probe config changed');atomic(out/'PROBE.json',probes);outputs['PROBE.json']=sha(out/'PROBE.json');rc=0;status.update(stage='probe_completed',progress=4,total=4);return
  pc=json.loads(Path(c['probe_config']).read_text());pt=json.loads(Path(pc['out'],'COMPLETE.json').read_text());pr=json.loads(Path(c['probe_review']).read_text())
  require(pt['rc']==0 and pt['stage']=='probe_completed' and pt['config_sha256']==sha(c['probe_config'])==pr['approved_probe_config_sha256'],'Probe approval binding')
  require(sha(c['probe_report'])==pt['outputs']['PROBE.json']==pr['approved_probe_sha256'],'Probe result changed')
  for k in ['family','base','code','temperature','runtime','eligibility_config','eligibility_report']:require(c[k]==pc[k],'Probe native configuration changed '+k)
  probes=json.loads(Path(c['probe_report']).read_text());atomic(out/'PROBE.json',probes);outputs['PROBE.json']=sha(out/'PROBE.json');items=[];elapsed=0.;count=0;status['stage']='inference'
  for i,raw in enumerate(rows):
   req=request(raw);e=elig['items'][i];require(e['index']==i and e['id']==raw['id'] and e['input_sha256']==stamp(raw) and e['request_sha256']==stamp(req),'Eligibility row binding')
   p=folder/f'{i:06d}.json';identity=dict(index=i,id=raw['id'],input_sha256=stamp(raw),request_sha256=stamp(req),config_sha256=ch)
   if p.exists():
    envelope=json.loads(p.read_text());v=envelope['payload'];require(stamp(v)==envelope['sha256'] and all(v.get(k)==x for k,x in identity.items()),'Foreign receipt')
   else:
    actual=model.eligibility(req);require(all(e.get(k)==x for k,x in actual.items()),'Runtime eligibility changed')
    v={**identity,'eligibility':actual,'status':actual['status']}
    if actual['status']=='eligible':
     model.torch.npu.synchronize();start=time.monotonic();prediction=model.predict(req,actual);model.torch.npu.synchronize();seconds=time.monotonic()-start;response(question(raw)[1],prediction['answer']);v.update(status='valid',seconds=seconds,**prediction);elapsed+=seconds;count+=1
    atomic(p,dict(payload=v,sha256=stamp(v)))
   require(v['status'] in ['valid','unsupported','overlength'],'Unexpected status');require(all(e.get(k)==x for k,x in v['eligibility'].items()),'Resumed eligibility differs');require(v['status']==('valid' if e['status']=='eligible' else e['status']),'Resumed status differs');items.append(v);status.update(progress=i+1,questions_per_second_per_chip=count/elapsed if elapsed else None,reserved_gib=model.torch.npu.memory_reserved()/2**30)
  report=summarize(rows,items);require(report['classification']['total']==10938 and report['score']['total']==319,'Final denominators');report.update(config_sha256=ch,data_sha256=DATA_SHA,family=c['family']);atomic(out/'report.json',report);outputs['report.json']=sha(out/'report.json');verify_files(c);require(sha(path)==ch,'Config changed');rc=0;status['stage']='completed'
 except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
 finally:
  stop.set();t.join();value=dict(rc=rc,error=error,config_sha256=ch,outputs=outputs,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status);atomic(out/'STATUS.json',value);atomic(out/'COMPLETE.json',value)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);run(p.parse_args().config)
