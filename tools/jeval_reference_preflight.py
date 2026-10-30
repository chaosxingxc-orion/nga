#!/usr/bin/env python3
"""E31 full JEVal native input eligibility; token-only, never model inference."""
import argparse,collections,fcntl,hashlib,json,os,re,sys,tempfile,threading,time
from pathlib import Path
DATA_SHA='88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82'
TOTAL=11257

def require(v,m):
 if not v:raise ValueError(m)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def atomic(p,x):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 with os.fdopen(fd,'w') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o644);os.replace(tmp,p)
def request(raw):
 require(isinstance(raw['state'],str),'State must remain original string')
 qs=json.loads(raw['questions_json']);require(len(qs)==1,'Exactly one JEVal question required')
 for name,q in qs.items():
  require(isinstance(name,str) and name and set(q)<= {'type','instructions','criteria'},'Unexpected question shape')
  require(q['type'] in ('choice','noul','score') and isinstance(q['instructions'],str) and q['instructions'].strip(),'Question definition invalid')
 return {'state':raw['state'],'questions':qs}
def keys(q):
 if q['type']=='noul':return ['false','true']
 if q['type']=='choice':return list(q['criteria'])
 return [str(i) for i in range(len(q['criteria']))]
def schema(req):
 result={}
 for name,q in req['questions'].items():
  ks=keys(q);field={'description':q['instructions'],'type':'boolean' if q['type']=='noul' else 'enum','choices':[False,True] if q['type']=='noul' else ks}
  defs=dict(zip(ks,q['criteria'])) if q['type']=='score' else q.get('criteria') or {}
  require(all(k in ks and (v is None or isinstance(v,str)) for k,v in defs.items()),'Invalid level definition')
  clean={k:v for k,v in defs.items() if v is not None}
  if clean:field['choice_descriptions']=clean
  result[name]=field
 return result

def check(req,family,tok,native):
 q=next(iter(req['questions'].values()));ks=keys(q)
 if family=='nimble' and len(ks)>26:return {'status':'unsupported','reason':'native_v1_candidate_limit_26','candidate_count':len(ks)}
 if family=='nimble' and not req['state'].strip():return {'status':'unsupported','reason':'native_nonempty_context_required','candidate_count':len(ks)}
 if family=='kev':
  Request,to_record,encode,Overflow=native;rec,mapping=to_record(Request.model_validate(req));require(len(mapping)==1 and mapping[0]['keys']==ks,'Native candidate mapping differs')
  try:enc=encode(tok,rec,max_state=8192,max_branch=8192,strict=True,option_isolation=False)
  except Overflow as e:
   return {'status':'overlength','reason':'native_context_overflow','native_message':str(e),'state_tokens':getattr(e,'state_tokens',None),'candidate_count':len(ks)}
  n=len(enc['ids']);return {'status':'eligible' if n<=16384 else 'overlength','reason':'within_native_budget' if n<=16384 else 'packed_limit_16384','candidate_count':len(ks),'max_tokens':n,'state_tokens':enc['state_tokens'],'token_sha256':stamp(enc['ids'])}
 if family=='openjev':
  compile_request,candidate_prompts=native;records=compile_request(req['state'],req['questions']);require(len(records)==1 and records[0]['answer_keys']==ks,'Native candidate mapping differs')
  prompts=candidate_prompts(records[0]);lengths=[];hashes=[]
  # Bounded candidate memory; exact native chat template, no clipping or truncation.
  for prompt in prompts:
   text=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
   ids=tok(text,padding=False,truncation=False)['input_ids'];lengths.append(len(ids));hashes.append(stamp(ids))
  require(lengths and all(n>0 for n in lengths),'Empty tokenization')
  return {'status':'eligible' if max(lengths)<=4096 else 'overlength','reason':'within_native_budget' if max(lengths)<=4096 else 'candidate_limit_4096','candidate_count':len(ks),'max_tokens':max(lengths),'lengths':lengths,'token_sha256':hashes,'native_record_sha256':stamp(records[0])}
 require(family=='nimble','Unknown family')
 try:p=native(tok,req['state'],schema(req),2048,system_role=True)
 except ValueError as e:
  match=re.fullmatch(r'Longest prompt has (\d+) tokens; limit is 2048\. Nothing was truncated\.',str(e))
  if not match:raise
  return {'status':'overlength','reason':'native_prompt_limit_2048','candidate_count':len(ks),'max_tokens':int(match[1])}
 require(p.names==list(req['questions']) and len(p.full_ids)==1 and len(p.candidate_ids[0])==len(ks),'Native field shape differs')
 actual=[str(x).lower() if type(x)is bool else x for x in p.choices[0]];require(actual==ks,'Native candidate order differs')
 return {'status':'eligible','reason':'within_native_budget','candidate_count':len(ks),'max_tokens':len(p.full_ids[0]),'token_sha256':stamp(p.full_ids[0]),'candidate_token_ids':p.candidate_ids[0]}

def verify(c):
 needed={str(Path(c[k]).resolve()) for k in ['data','preregistration']}
 needed.update(str(Path(c['out'],n).resolve()) for n in ['jeval_reference_preflight.py','test_jeval_reference_preflight.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 for role in c['dependency_roles']:
  root=Path(c[role]);require(root.is_dir(),'Missing dependency root')
  needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
 require(needed<=set(c['files']),'Required dependency omitted')
 for p,h in c['files'].items():require(sha(p)==h,'Frozen file changed '+p)
 require(sha(c['data'])==DATA_SHA,'Wrong dataset')
 return len(needed)
def run(path):
 blob=path.read_bytes();ch=hashlib.sha256(blob).hexdigest();c=json.loads(blob);out=Path(c['out']);lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 require(not(out/'COMPLETE.json').exists(),'Existing terminal preserved');status={'stage':'verify','progress':0,'total':TOTAL,'chips':0};stop=threading.Event();rc=1;error=None;outputs={}
 def heartbeat():
  while not stop.wait(15):
   v={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',v)
   with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(v)+'\n')
   (out/'digest.md').write_text(v['utc']+' '+v['stage']+' '+str(v['progress'])+'/'+str(TOTAL)+'\n')
 t=threading.Thread(target=heartbeat,daemon=True);t.start()
 try:
  require(sha(path)==ch,'Config changed before execution');needed=verify(c);require(c['mode']=='token_only','Only token eligibility admitted')
  os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TORCH_DEVICE_BACKEND_AUTOLOAD='0',TOKENIZERS_PARALLELISM='false');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
  import torch,pyarrow.parquet as pq
  from transformers import AutoTokenizer
  torch.set_num_threads(2);tok=AutoTokenizer.from_pretrained(c.get('adapter',c['base']),local_files_only=True)
  if c['family']=='kev':
   from kev.api import SystemOneRequest,to_record
   from kev.model import encode,ContextOverflow
   native=(SystemOneRequest,to_record,encode,ContextOverflow)
  elif c['family']=='openjev':
   from jev.api import compile_request,candidate_prompts
   native=(compile_request,candidate_prompts)
  else:
   from nimble.scoring.parallel_schema import prepare_prompts
   from nimble.scoring.release_contract import prompt_builder
   native=prompt_builder(c['adapter'],tok);require(native is prepare_prompts,'Not native Nimble v1')
  rows=pq.read_table(c['data']).to_pylist();require(len(rows)==TOTAL and len({r['id'] for r in rows})==TOTAL,'Population differs')
  folder=out/'records';folder.mkdir(exist_ok=True);names={f'{i:06d}.json' for i in range(TOTAL)};require(all(p.name in names for p in folder.glob('*.json')),'Extra receipt')
  items=[];status['stage']='token_eligibility'
  for i,row in enumerate(rows):
   req=request(row);q=next(iter(req['questions'].values()));identity={'index':i,'id':row['id'],'input_sha256':stamp(row),'request_sha256':stamp(req),'config_sha256':ch,'type':q['type'],'source':row.get('source'),'source_item_id':row.get('source_item_id')};p=folder/f'{i:06d}.json'
   if p.exists():
    e=json.loads(p.read_text());v=e['payload'];require(e['sha256']==stamp(v) and all(v.get(k)==x for k,x in identity.items()),'Foreign or corrupt receipt')
   else:v={**identity,**check(req,c['family'],tok,native)};atomic(p,{'payload':v,'sha256':stamp(v)})
   require(v['status']in('eligible','unsupported','overlength'),'Invalid item status');items.append(v);status['progress']=i+1
  counts=dict(collections.Counter(v['status'] for v in items));by_type={typ:dict(collections.Counter(v['status'] for v in items if v['type']==typ)) for typ in ('choice','noul','score')}
  require(sum(counts.values())==TOTAL,'Summary coverage differs');report={'config_sha256':ch,'data_sha256':DATA_SHA,'rows':TOTAL,'counts':counts,'by_type':by_type,'max_observed_tokens':max((v.get('max_tokens',0) for v in items),default=0),'frozen_files':len(c['files']),'required_files':needed,'items':items,'scope':'CPU native eligibility only; unsupported precedes tokenization; no inference, metric result, truncation or paper extended-budget reproduction'}
  verify(c);require(sha(path)==ch,'Config changed during execution');atomic(out/'report.json',report);outputs['report.json']=sha(out/'report.json');status.update(stage='completed');rc=0
 except BaseException as e:error=type(e).__name__+': '+str(e);status['stage']='failed';raise
 finally:
  stop.set();t.join();v={'rc':rc,'error':error,'config_sha256':ch,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',v);atomic(out/'COMPLETE.json',v);(out/'digest.md').write_text(v['utc']+' '+v['stage']+' '+str(v['progress'])+'/'+str(TOTAL)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);run(p.parse_args().config)
