"""CPU-testable matched native performance protocol; no host/claim/launch authority."""
import hashlib,json,math,time,os,fcntl
from pathlib import Path

SCHEMA='native-matched-dev6516-performance-v1'
TRIALS=[(0,'reference'),(0,'adapter_sequential'),(1,'adapter_sequential'),(1,'reference')]
def need(v,s):
 if not v:raise ValueError(s)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pin(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def pinned(r):
 need(set(r)=={'path','sha256'} and Path(r['path']).is_absolute() and '..' not in Path(r['path']).parts,'pin fields/path')
 need(not any(x.is_symlink() for x in (Path(r['path']),*Path(r['path']).parents)) and sha(r['path'])==r['sha256'],'pin differs')
 return json.loads(Path(r['path']).read_bytes())

def map_request(row,ordinal,bridge):
 """Explicit new native mapping from existing gold-free typed requests."""
 need(type(row)is dict and set(row)=={'id','request'} and type(row['id'])is str and row['id'],'source row')
 r=row['request'];bridge.to_r3_row(r)
 need(type(ordinal)is int and ordinal>=0,'ordinal')
 k=r['type'];options=['Yes','No'] if k=='noul' else list(r['definitions'])
 need((k!='choice' or len(options)<=26) and (k!='score' or len(options)<=10),'native candidate count')
 x={'i':ordinal,'qid':row['id'],'state':r['input'],'question':r['question'],'options':options,'kind':'yes_no' if k=='noul' else k}
 # Preserve ordinal source index0..K-1 explicitly, distinct from original DEV72's1-based labels.
 if k=='score':x['first_level']=0
 return x

def validate_population(rows,source_rows,N):
 need(len(rows)==len(source_rows)==6516,'full6516 required')
 need(len({x['id'] for x in source_rows})==6516,'duplicate source IDs')
 for i,(row,src) in enumerate(zip(rows,source_rows)):
  need(set(row)=={'schema','i','qid','request_sha256','input_ids','rendered_prompt','labels','label_ids','options','kind'},'gold/foreign fields')
  need(type(row['i'])is int and row['i']==i and row['qid']==src['id'],'original order/id')
  need(row['kind']==src['request']['type'],'kind')
  need(type(row['input_ids'])is list and 0<len(row['input_ids'])<=4096 and all(type(v)is int and 0<=v<248320 for v in row['input_ids']),'no token truncation or overflow')
  need(len(row['label_ids'])==len(set(row['label_ids']))==len(row['labels'])==len(row['options'])==len(src['request']['candidate_keys']),'candidate order/count')
  need(row['options']==(['Yes','No'] if row['kind']=='noul' else src['request']['definitions']),'candidate definitions')
  if row['kind']=='score':need(row['labels']==src['request']['candidate_keys'],'zero-based score level labels')
 return {'count':6516,'ordered_inputs_sha256':N.digest(rows),'ordered_input_sha256':[N.digest(x) for x in rows],'ordered_source_ids_sha256':digest([x['id'] for x in source_rows]),'total_input_tokens':sum(len(x['input_ids']) for x in rows),'max_tokens':max(len(x['input_ids']) for x in rows)}

def schedule(n):
 need(type(n)is int and n==6516,'registered workload count')
 return [{'trial':i,'pair':pair,'arm':arm,'ranges':[[0,n]] if arm=='reference' else [[0,n//2],[n//2,n]],'count':n} for i,(pair,arm) in enumerate(TRIALS)]

def warmup_indices(rows):
 ids=sorted(range(len(rows)),key=lambda i:(len(rows[i]['input_ids']),i))
 need(len(rows)==6516,'warmup original population')
 return [ids[0],ids[(len(ids)-1)//2],ids[-1]]

def full(arrays,result,item):
 import numpy as np
 need(set(arrays)=={'input_ids','attention_mask','logits'},'operand fields')
 need(arrays['input_ids'].dtype==np.int64 and arrays['attention_mask'].dtype==np.int64 and arrays['logits'].dtype==np.float32,'operand dtype')
 need(arrays['input_ids'].tolist()==[item['input_ids']] and arrays['attention_mask'].tolist()==[[1]*len(item['input_ids'])],'input/mask exact')
 need(arrays['logits'].shape==(1,248320) and np.isfinite(arrays['logits']).all(),'full finite FP32 logits')
 need(result['forwards']==1 and type(result['forwards'])is int and result['prediction']['input_sha256']==digest(item),'forward/input identity')

def put(path,value):
 """Durable new report; never overwrite an accepted or uncertain generation."""
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.pending')
 with q.open('x') as f:json.dump(value,f,sort_keys=True,allow_nan=False);f.write(chr(10));f.flush();os.fsync(f.fileno())
 os.link(q,p);q.unlink();fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

def execute_fresh(root,plan_ref,rows,load_backend,clock=time.perf_counter):
 """Injected registered backend only; this function never claims/launches devices.

 Backend methods: synchronize,collect,persist,memory,reset_peak,progress.
 persist(target,item,arrays,result) must commit actual full operands and return pins.
 Host integration must externally bind the backend/source closure and resource
 generation. No schema/name aliases, cached timings or attempt resume are provided.
 """
 root=Path(root);need(root.is_absolute() and '..' not in root.parts and not any(x.is_symlink() for x in (root,*root.parents)),'safe output')
 need(type(plan_ref)is dict and set(plan_ref)=={'path','sha256'} and sha(plan_ref['path'])==plan_ref['sha256'],'exact plan pin')
 schedule(len(rows));warm=warmup_indices(rows)
 need(not root.exists(),'fresh performance experiment required')
 root.mkdir(parents=True,exist_ok=False)
 with (root/'writer.lock').open('x') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);begin=clock();rc=1
  try:
   put(root/'START.json',{'plan':plan_ref,'attempt':1,'scope':'native collect path matched performance','warmup_indices':warm,'timing_reuse_allowed':False,'scientific_acceptance':False,'test_read':False})
   before=clock();backend=load_backend();backend.synchronize();load_s=clock()-before;need(math.isfinite(load_s) and load_s>0,'model load timing')
   starting_memory=backend.memory();warm_start=clock()
   for arm in ('reference','adapter_sequential'):
    for ordinal in warm:
     item=rows[ordinal];backend.synchronize();arrays,result=backend.collect(arm,item);backend.synchronize();full(arrays,result,item);backend.persist(root/'warmup'/arm/str(ordinal),item,arrays,result)
   backend.synchronize();warm_s=clock()-warm_start;need(math.isfinite(warm_s) and warm_s>0,'warmup timing')
   trials=[]
   for trial in schedule(len(rows)):
    dest=root/'trials'/str(trial['trial']);dest.mkdir(parents=True,exist_ok=False)
    put(dest/'START.json',{'plan':plan_ref,'trial':trial,'fresh':True,'timing_reuse_allowed':False})
    def persist(ordinal,item,arrays,result):return backend.persist(dest/'items'/str(ordinal),item,arrays,result)
    report=measure_trial(trial,rows,backend.collect,persist,backend.synchronize,backend.memory,backend.reset_peak,backend.progress,clock)
    put(dest/'report.json',dict(report,plan=plan_ref));put(dest/'EXIT.json',{'exit_code':0,'plan':plan_ref,'trial':trial['trial'],'scientific_acceptance':False,'test_read':False});trials.append(report)
   backend.synchronize();occupied=clock()-begin
   need(math.isfinite(occupied) and occupied>=load_s+warm_s+sum(x['wall_seconds'] for x in trials),'occupied service accounting')
   result={'schema':SCHEMA,'plan':plan_ref,'attempt':1,'model_load_seconds':load_s,'warmup_seconds':warm_s,'warmup_forwards':6,'whole_occupied_seconds':occupied,'whole_occupied_chip_hours':occupied/3600,'measured_trial_chip_hours':sum(x['chip_hours'] for x in trials),'chips':1,'starting_memory':starting_memory,'process_trial_peak_reserved_bytes':max(x['peak_reserved_bytes'] for x in trials),'process_trial_peak_allocated_bytes':max(x['peak_allocated_bytes'] for x in trials),'trials':[pin(root/'trials'/str(x['trial'])/'report.json') for x in trials],'full_operand_equality_pending':True,'timing_acceptance':False,'scientific_acceptance':False,'test_read':False}
   put(root/'report.json',result);rc=0;return result
  except BaseException as error:
   put(root/'FAILURE.json',{'error_type':type(error).__name__,'timing_eligible':False,'resume_requires_new_complete_experiment':True,'plan':plan_ref,'scientific_acceptance':False,'test_read':False});raise
  finally:put(root/'EXIT.json',{'exit_code':rc,'plan':plan_ref,'attempt':1,'timing_acceptance':False,'scientific_acceptance':False,'test_read':False})

def measure_trial(trial,rows,collect,persist,synchronize,memory,reset_peak,progress,clock=time.perf_counter):
 """Measure collect (excluding subsequent full check) and same persistence separately.

 No reused item may enter a valid timing. Caller enforces an exclusive fresh trial.
 Synchronize immediately before/after each collect, and total workload boundaries.
 """
 need(type(trial.get('trial'))is int and 0<=trial['trial']<4 and trial==schedule(len(rows))[trial['trial']],'trial registration')
 actual=[i for lo,hi in trial['ranges'] for i in range(lo,hi)]
 need(actual==list(range(len(rows))),'exact once ordered coverage')
 synchronize();reset_peak();start=clock();compute=0.;store=0.;tokens=0;observations=[]
 for ordinal in actual:
  item=rows[ordinal];synchronize();before=clock();arrays,result=collect(trial['arm'],item);synchronize();after=clock()
  full(arrays,result,item);elapsed=after-before;need(math.isfinite(elapsed) and elapsed>0,'invalid collect timing')
  before_store=clock();identity=persist(ordinal,item,arrays,result);after_store=clock();persist_s=after_store-before_store
  need(math.isfinite(persist_s) and persist_s>=0 and type(identity)is dict,'invalid persistence timing')
  compute+=elapsed;store+=persist_s;tokens+=len(item['input_ids']);observations.append({'ordinal':ordinal,'input_sha256':digest(item),'collect_seconds':elapsed,'persist_seconds':persist_s,'persisted':identity})
  progress(ordinal+1,compute,tokens)
 synchronize();wall=clock()-start;mem=memory()
 need(math.isfinite(wall) and wall>=compute+store and set(mem)=={'peak_allocated_bytes','peak_reserved_bytes'},'timing/memory accounting')
 need(all(type(x)is int and x>=0 for x in mem.values()) and mem['peak_reserved_bytes']>=mem['peak_allocated_bytes'],'memory shape')
 return {**trial,'items':len(rows),'tokens':tokens,'chips':1,'compute_seconds':compute,'persist_seconds':store,'wall_seconds':wall,'items_per_second_per_chip':len(rows)/wall,'tokens_per_second_per_chip':tokens/wall,'compute_items_per_second_per_chip':len(rows)/compute,'compute_tokens_per_second_per_chip':tokens/compute,'chip_hours':wall/3600,**mem,'observations':observations,'reused_items':0,'numerical_acceptance':False,'timing_acceptance':False}

def summarize(trials,population,independent_equality):
 need(independent_equality.get('verdict')=='PASS' and independent_equality.get('population_sha256')==population['ordered_inputs_sha256'] and type(independent_equality.get('full_operand_comparisons'))is int and independent_equality['full_operand_comparisons']==3*6516 and independent_equality.get('zero_tolerance')is True,'independent full raw equality required')
 need(len(trials)==4,'all four trials')
 for actual,expected in zip(trials,schedule(6516)):
  need(all(actual[k]==v and type(actual[k])is type(v) for k,v in expected.items()),'trial order/ranges')
  need(actual['items']==6516 and type(actual['items'])is int and type(actual['tokens'])is int and actual['tokens']==population['total_input_tokens'] and actual['chips']==1 and type(actual['chips'])is int and type(actual['reused_items'])is int and actual['reused_items']==0,'trial count/token/chip/reuse')
  for key in ['compute_seconds','wall_seconds','items_per_second_per_chip','tokens_per_second_per_chip','chip_hours']:need(type(actual[key])in (int,float) and math.isfinite(actual[key]) and actual[key]>0,'invalid timing')
  obs=actual['observations'];need([x['ordinal'] for x in obs]==list(range(6516)) and [x['input_sha256'] for x in obs]==population['ordered_input_sha256'],'item population')
  for x in obs:
   need(type(x['ordinal'])is int and type(x['collect_seconds'])in (int,float) and math.isfinite(x['collect_seconds']) and x['collect_seconds']>0 and type(x['persist_seconds'])in (int,float) and math.isfinite(x['persist_seconds']) and x['persist_seconds']>=0,'observation timing')
  close=lambda x,y:math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-9)
  need(close(actual['compute_seconds'],sum(x['collect_seconds'] for x in obs)) and close(actual['persist_seconds'],sum(x['persist_seconds'] for x in obs)) and actual['wall_seconds']>=actual['compute_seconds']+actual['persist_seconds'],'whole trial timing decomposition')
  need(close(actual['items_per_second_per_chip'],6516/actual['wall_seconds']) and close(actual['tokens_per_second_per_chip'],actual['tokens']/actual['wall_seconds']) and close(actual['chip_hours'],actual['wall_seconds']/3600),'rate and cost arithmetic')
  need(all(type(actual[k])is int and actual[k]>=0 for k in ['peak_allocated_bytes','peak_reserved_bytes']) and actual['peak_reserved_bytes']>=actual['peak_allocated_bytes'],'trial memory')
 ratios=[]
 for pair in (0,1):
  a={x['arm']:x for x in trials if x['pair']==pair};ratios.append({'pair':pair,'wall_reference_over_adapter_sequential':a['reference']['wall_seconds']/a['adapter_sequential']['wall_seconds'],'compute_reference_over_adapter_sequential':a['reference']['compute_seconds']/a['adapter_sequential']['compute_seconds']})
 return {'schema':'native-matched-dev6516-performance-summary-v1','paired_ratios':ratios,'pooled_wall_reference_over_adapter_sequential':sum(x['wall_seconds'] for x in trials if x['arm']=='reference')/sum(x['wall_seconds'] for x in trials if x['arm']=='adapter_sequential'),'chips':1,'total_measured_trial_chip_hours':sum(x['chip_hours'] for x in trials),'scope':'native reference collect versus adapter collect in two sequential segments; not full accepted shard-runner overhead','statistical_significance_claim':False,'production_speedup_acceptance':False,'scientific_acceptance':False,'test_read':False}
