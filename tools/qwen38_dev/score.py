#!/usr/bin/env python3
"""Four-NPU task smoke, item-atomic raw candidate scores."""
import argparse, ctypes, json, os, sys, threading, time, traceback, resource, hashlib, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import core, raw_loading as audit

def main(a,state):
 import torch, torch_npu, transformers
 from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
 out=Path(a.out); mask_bytes=Path(a.mask).read_bytes(); work_bytes=Path(a.workload).read_bytes(); work=json.loads(work_bytes)
 if core.digest_bytes(mask_bytes)!=work['mask_sha256'] or work['mask_sha256']!='df9da52a09bed12d562aad304d59863f9c90cc7a46c27b87c818a580774db03d': raise ValueError('mask mismatch')
 rows=core.read_dev(json.loads(mask_bytes),a.dev_root)
 identity=core.digest(dict(workload=core.digest_bytes(work_bytes),model=work['revision'],code=a.code_hash,devices=a.count))
 state.update(identity=identity,total=len(work['items'])*len(work['modes']),stage='loading')
 if torch.npu.device_count()!=a.count or os.environ.get('ASCEND_RT_VISIBLE_DEVICES')!=','.join(map(str,range(a.count))): raise RuntimeError('logical visibility mismatch')
 lib=ctypes.CDLL('libascendcl.so'); query=lib.aclrtGetPhyDevIdByUserDevId; query.argtypes=[ctypes.c_int32,ctypes.POINTER(ctypes.c_int32)]; query.restype=ctypes.c_int
 mapping=[]
 for i in range(a.count):
  physical=ctypes.c_int32(); rc=query(i,ctypes.byref(physical))
  if rc: raise RuntimeError('physical device query failed')
  mapping.append(physical.value)
 if mapping!=list(map(int,a.physical.split(','))): raise RuntimeError('physical device mapping mismatch: '+str(mapping))
 core.put(out/'device-visibility.json',{'logical_to_physical':mapping})
 torch.npu.set_device(0)
 torch.npu.matmul.allow_hf32=False
 torch.npu.conv.allow_hf32=False
 if torch.npu.matmul.allow_hf32 or torch.npu.conv.allow_hf32: raise RuntimeError('HF32 disable failed')
 for i in range(a.count): torch.npu.reset_peak_memory_stats(i)
 receipt={'failure':None}
 try:
  receipt['source']=audit.source_check(transformers,Qwen3_5ForConditionalGeneration)
  class AuditedQwen(audit.CaptureBeforeFilter,Qwen3_5ForConditionalGeneration): pass
  model,info=AuditedQwen.from_pretrained(a.model,local_files_only=True,trust_remote_code=False,dtype=torch.float32,device_map='balanced',max_memory={**{i:'56GiB' for i in range(a.count)},'cpu':'0GiB'},attn_implementation='sdpa',low_cpu_mem_usage=True,output_loading_info=True)
  raw=getattr(model,'_raw_loading_info',None); receipt['raw']=audit.normalize(raw); receipt['filtered']=audit.normalize(info)
  checkpoint,headers=audit.inventory(a.model); state_dict={k:{'shape':list(v.shape),'dtype':str(v.dtype).replace('torch.','')} for k,v in model.state_dict().items()}
  receipt['header_sha256']=headers; receipt['accounting']=audit.account(checkpoint,state_dict,json.loads(Path(a.tensor_diff).read_text())['checkpoint_only'],raw,info,getattr(model,'_raw_capture_count',0),list(model._keys_to_ignore_on_load_unexpected))
  if getattr(model,'_raw_capture_error',None): receipt['accounting']['errors'].append(model._raw_capture_error)
  if receipt['accounting']['errors']: raise RuntimeError('loader accounting failed')
 except Exception as e:
  receipt['failure']=repr(e); raise
 finally: core.put(out/'raw-loading-accounting.json',receipt)
 devices=set()
 for d in model.hf_device_map.values():
  s=str(d).removeprefix('npu:')
  if s not in set(map(str,range(a.count))): raise RuntimeError('CPU/disk/unexpected placement '+str(d))
  devices.add(int(s))
 if devices!=set(range(a.count)): raise RuntimeError('placement does not use all devices')
 core.put(out/'placement.json',{'device_map':{k:str(v) for k,v in model.hf_device_map.items()},'input_device':str(model.get_input_embeddings().weight.device)})
 core.put(out/'runtime.json',{'dtype_state_counts':{d:sum(1 for v in state_dict.values() if v['dtype']==d) for d in sorted({v['dtype'] for v in state_dict.values()})},'hf32_matmul':bool(torch.npu.matmul.allow_hf32),'hf32_conv':bool(torch.npu.conv.allow_hf32),'requested_dtype':'float32','logical_to_physical':mapping})
 model.eval(); tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,trust_remote_code=False)
 max_context=int(model.config.text_config.max_position_embeddings)
 ref_item=max(work['items'],key=lambda x:(x['prefix_length']+max(x['candidate_lengths']),x['source_key'],x['row']))
 ref_index=next(i for i,n in enumerate(ref_item['candidate_lengths']) if n>1)
 attempt=Path(a.attempt); events=attempt/'items.jsonl'
 def event(kind,name):
  with events.open('a') as f: f.write(json.dumps({'event':kind,'item':name,'utc':time.time()})+'\n'); f.flush(); os.fsync(f.fileno())
 def count(kind,name):
  core.record_attempt(state,kind,name,events,attempt/'progress.json')
 for item in work['items']:
  key=item['source_key']; index=item['row']; row=rows[key][index]
  if core.digest(row)!=item['row_sha256']: raise ValueError('workload row mismatch')
  for mode in work['modes']:
   ident=core.expected(row,key,index,mode,identity); name=core.digest([key,index,mode]); path=out/'items'/(name+'.json')
   if core.load_completed(path,ident) is not None: state['completed']+=1; count('skipped',name); continue
   event('start',name)
   p,pre,cands=core.encode(row,tok,mode)
   if mode=='full' and (len(pre)!=item['prefix_length'] or list(map(len,cands))!=item['candidate_lengths']): raise ValueError('frozen tokenization differs')
   scores=[]; timings=[]; elapsed=0; state.update(stage='forward',item=name,mode=mode)
   for j,c in enumerate(cands):
    seq=pre+c
    if len(seq)>max_context or len(seq)>a.sequence_limit: raise ValueError(f'sequence length {len(seq)} exceeds limit')
    state.update(candidate=j+1,candidates=len(cands),sequence_length=len(seq))
    ids=torch.tensor([seq],dtype=torch.long,device=model.get_input_embeddings().weight.device); mask=torch.ones_like(ids)
    for i in range(a.count): torch.npu.synchronize(i)
    start=time.monotonic()
    with torch.inference_mode():
     logits=model(input_ids=ids,attention_mask=mask,use_cache=False,logits_to_keep=len(c)+1).logits
     if tuple(logits.shape[:2])!=(1,len(c)+1): raise RuntimeError('unexpected logits shape')
     score=core.continuation_sum(logits[0],seq,len(pre))
    for i in range(a.count): torch.npu.synchronize(i)
    seconds=time.monotonic()-start; elapsed+=seconds; scores.append(score); timings.append(seconds)
    if item is ref_item and mode=='full' and j==ref_index:
     ref=out/'reference'; ref.mkdir(exist_ok=True)
     tensor=logits[0].detach().to(device='cpu',dtype=torch.float32).contiguous()
     fd,tmp=tempfile.mkstemp(dir=ref,prefix='.logits-',suffix='.pt'); os.close(fd)
     try:
      torch.save(tensor,tmp); os.replace(tmp,ref/'logits.pt')
     finally:
      if os.path.exists(tmp): os.unlink(tmp)
     core.put(ref/'manifest.json',{'schema':'same-npu-logits-v1','source_key':key,'row':index,'mode':mode,'candidate_index':j,'candidate_id':ident['candidate_ids'][j],'candidate_token_ids':c,'prefix_length':len(pre),'shape':list(tensor.shape),'dtype':'float32','logits_sha256':hashlib.sha256((ref/'logits.pt').read_bytes()).hexdigest(),'npu_score':score,'absolute_tolerance':0.0001,'relative_tolerance':0.00001})
    state.update(tokens_per_second_per_chip=len(seq)/seconds/a.count,reserved_peak_bytes=[torch.npu.max_memory_reserved(i) for i in range(a.count)])
    if max(state['reserved_peak_bytes'])>=56*1024**3: raise RuntimeError('memory ceiling exceeded')
   rec=dict(ident,raw_scores=scores,prefix_length=len(pre),candidate_lengths=list(map(len,cands)),sequence_lengths=[len(pre)+len(c) for c in cands],seconds=elapsed,candidate_seconds=timings,card_seconds=elapsed*a.count,peak_allocated_bytes=[torch.npu.max_memory_allocated(i) for i in range(a.count)],peak_reserved_bytes=[torch.npu.max_memory_reserved(i) for i in range(a.count)],cpu_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
   core.validate_record(rec,ident); core.put(path,rec); state['completed']+=1; count('computed',name); event('commit',name)
 state.update(stage='finished'); core.put(out/'complete.json',dict(state))

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for x in ('model','dev-root','mask','workload','tensor-diff','out','physical','code-hash','attempt'): p.add_argument('--'+x,required=True)
 p.add_argument('--count',type=int,choices=(2,4),default=4); p.add_argument('--sequence-limit',type=int,required=True); a=p.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True); state={'stage':'starting','completed':0,'computed':0,'skipped':0,'total':None}; stop=threading.Event()
 def heartbeat():
  while not stop.is_set():
   core.put(out/'heartbeat.json',dict(state,utc=time.time())); print(json.dumps(dict(state,utc=time.time())),flush=True); stop.wait(30)
 threading.Thread(target=heartbeat,daemon=True).start()
 try: main(a,state)
 except BaseException:
  state['stage']='failed'; traceback.print_exc(); raise
 finally:
  stop.set(); core.put(Path(a.attempt)/'progress.json',dict(state,utc=time.time())); core.put(out/'heartbeat.json',dict(state,utc=time.time()))
