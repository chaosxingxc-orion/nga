#!/usr/bin/env python3
"""E29 native Open-Jev five-question compilation and full CPU token admission."""
import argparse,copy,fcntl,hashlib,json,os,sys,tempfile,threading,time
from pathlib import Path
DATA_SHA='4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c'
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def atomic(p,x):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 try:
  with os.fdopen(fd,'w') as f:json.dump(x,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o644);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def keys(q):
 if q['type']=='noul':return ['false','true']
 if q['type']=='choice':return list(q['criteria'])
 require(q['type']=='score','Unsupported type');return [str(i) for i in range(len(q['criteria']))]
def request(raw):return {'state':json.loads(raw['state']),'questions':json.loads(raw['questions'])}
def compile_five(raw,compile_request):
 req=request(raw);require(len(req['questions'])==5,'Exactly five questions required')
 records=compile_request(req['state'],req['questions'])
 require(len(records)==5 and [r['id'] for r in records]==list(req['questions']),'Question order/count differs')
 for r,(name,q) in zip(records,req['questions'].items()):
  require(r['kind']==q['type'] and r['answer_keys']==keys(q),'Candidate identity/order differs')
  require('target'not in r and 'gold'not in r and 'factors'not in r,'Gold entered native record')
 return records
def encode(raw,tokenizer,compile_request,candidate_prompts):
 records=compile_five(raw,compile_request);items=[]
 for record in records:
  prompts=candidate_prompts(record)
  require(len(prompts)==(1 if record['kind']=='noul' else len(record['answer_keys'])),'Native candidate prompt count differs')
  chats=[tokenizer.apply_chat_template([{'role':'user','content':p}],tokenize=False,add_generation_prompt=True,enable_thinking=False) for p in prompts]
  ids=tokenizer(chats,padding=False,truncation=False)['input_ids']
  require(len(ids)==len(prompts) and all(0<len(x)<=4096 for x in ids),'Candidate context overflow or malformed')
  items.append({'name':record['id'],'kind':record['kind'],'candidate_keys':record['answer_keys'],'native_record_sha256':stamp(record),'prompts_sha256':stamp(prompts),'lengths':[len(x) for x in ids],'token_sha256':[stamp(x) for x in ids]})
 return items
def synthetic():
 return {'id':'synthetic','state':json.dumps({'nested':{'text':'中文','n':3}}),'questions':json.dumps({'route':{'type':'choice','instructions':'Choose route','criteria':{'a':None,'b':''}},'allow':{'type':'noul','instructions':'Allow?'},'level':{'type':'score','instructions':'Choose level','criteria':['low','medium','high']},'extra':{'type':'choice','instructions':'Choose extra','criteria':{'x':'first','y':'second'}},'flag':{'type':'noul','instructions':'Flag?','criteria':{'false':'Absent','true':'Present'}}})}
def required(c):
 needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
 needed.update(str(Path(c['out'],n).resolve()) for n in ['typed_openjev_preflight.py','test_typed_openjev_preflight.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 for role in ['base','checkpoint','code']:
  root=Path(c[role]);require(root.is_dir(),'Missing dependency directory')
  needed.update(str(p.resolve()) for p in root.rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
 for role,names in {'base':['.complete','config.json','tokenizer.json'],'checkpoint':['model.json','temperature.json'],'code':['jev/api.py','jev/model.py','jev/metrics.py']}.items():
  for name in names:require(Path(c[role],name).is_file(),'Missing loader input '+name)
 return needed
def verify(c):
 require(required(c)<=set(c['files']),'Missing frozen dependency')
 for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency differs: '+p)
 require(sha(c['data'])==DATA_SHA,'Wrong data');meta=json.loads(Path(c['checkpoint'],'model.json').read_text())
 require((meta['model_id'],meta['revision'],meta['max_length'])==(c['base_id'],c['base_revision'],4096),'Native checkpoint protocol differs')
 require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'],'Base revision differs')
 require(json.loads(Path(c['checkpoint'],'temperature.json').read_text())['temperature']==c['temperature'],'Temperature differs')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);a=ap.parse_args();path=Path(a.config);blob=path.read_bytes();ch=hashlib.sha256(blob).hexdigest();c=json.loads(blob);out=Path(c['out'])
 with (out/'driver.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);require(c['mode']=='preflight_only','Only CPU admission is implemented');verify(c)
  terminal=out/'COMPLETE.json'
  if terminal.exists():
   old=json.loads(terminal.read_text());require(old['rc']!=0,'Existing successful terminal preserved');archive=out/('failed-before-resume-'+str(time.time_ns()));archive.mkdir()
   for name in ['COMPLETE.json','EXIT','STATUS.json']:
    if (out/name).exists():os.replace(out/name,archive/name)
  status={'stage':'verify','progress':0,'total':400,'chips':0};stop=threading.Event();rc=1;error=None;outputs={}
  def heartbeat():
   while not stop.wait(10):
    value={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',value)
    with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(value)+'\n')
  thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
  try:
   os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TORCH_DEVICE_BACKEND_AUTOLOAD='0');sys.dont_write_bytecode=True;sys.path.insert(0,c['code'])
   import pyarrow.parquet as pq
   from transformers import AutoTokenizer
   from jev.api import compile_request,candidate_prompts
   tokenizer=AutoTokenizer.from_pretrained(c['base'],local_files_only=True);tokenizer.padding_side='right'
   if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
   raw=synthetic();first=encode(raw,tokenizer,compile_request,candidate_prompts);changed=copy.deepcopy(raw);changed.update(gold='SECRET',factors='PRIVATE',id='other');require(first==encode(changed,tokenizer,compile_request,candidate_prompts),'Gold/metadata leakage')
   req=request(raw);req['questions']['route']['criteria']={'b':'','a':None};changed=copy.deepcopy(raw);changed['questions']=json.dumps(req['questions']);require(first!=encode(changed,tokenizer,compile_request,candidate_prompts),'Candidate order discrimination failed')
   changed=copy.deepcopy(raw);q=request(changed)['questions'];q['route']['criteria']['a']='changed content';changed['questions']=json.dumps(q);require(first!=encode(changed,tokenizer,compile_request,candidate_prompts),'Candidate content discrimination failed')
   rows=pq.read_table(c['data']).to_pylist();require(len(rows)==400 and len({r['id'] for r in rows})==400,'Wrong state population');folder=out/'records';folder.mkdir(exist_ok=True);require(all(p.name in {f'{i:06d}.json' for i in range(400)} for p in folder.glob('*.json')),'Unexpected item receipt')
   status['stage']='whole_test_token_preflight';items=[]
   for i,row in enumerate(rows):
    req=request(row);gold=json.loads(row['gold']);require(row['split']=='test' and list(req['questions'])==list(gold) and len(gold)==5,'Wrong test question population')
    for name,q in req['questions'].items():require(gold[name]['type']==q['type'] and set(gold[name]['probabilities'])==set(keys(q)),'Gold candidate mismatch')
    value={'index':i,'id':row['id'],'config_sha256':ch,'input_sha256':stamp(row),'request_sha256':stamp(req),'fields':encode(row,tokenizer,compile_request,candidate_prompts)};p=folder/f'{i:06d}.json'
    if p.exists():
     env=json.loads(p.read_text());require(env['sha256']==stamp(env['payload']) and env['payload']==value,'Invalid persisted item')
    else:atomic(p,{'payload':value,'sha256':stamp(value)})
    items.append(value);status['progress']=i+1
   report={'config_sha256':ch,'rows':400,'questions':2000,'candidate_prompts':sum(len(f['lengths']) for x in items for f in x['fields']),'max_tokens':max(n for x in items for f in x['fields'] for n in f['lengths']),'overlength':0,'items':items,'synthetic':{'five_questions':True,'gold_isolated':True,'candidate_order_discrimination':True,'candidate_content_discrimination':True},'scope':'CPU-only native compilation and token lengths; native API isolates questions and candidates. No test predictions or joint-schema claim.'}
   verify(c);require(sha(path)==ch,'Config changed');atomic(out/'PREFLIGHT.json',report);outputs['PREFLIGHT.json']=sha(out/'PREFLIGHT.json');status['stage']='completed';rc=0
  except BaseException as exc:error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
  finally:
   stop.set();thread.join();result={'rc':rc,'config_sha256':ch,'error':error,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',result);atomic(terminal,result)
if __name__=='__main__':main()
