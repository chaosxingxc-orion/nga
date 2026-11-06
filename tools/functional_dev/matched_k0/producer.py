#!/usr/bin/env python3
"""Matched K0 clean DEV/calibration producer. Infer and score are separate processes."""
import argparse, hashlib, importlib.util, json, math, os, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'config.json').read_text())
CLOSURE=CONFIG['closure']; sys.path.insert(0,CLOSURE+'/r3_code'); sys.path.insert(1,CLOSURE+'/r0_code')
GROUPS=['decision-v7/calibration/clean','decision-v7/dev/clean','transfer-v4/dev/clean']
COUNTS=[1148,1264,656]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
 with t.open('w') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def require(x,msg):
 if not x:raise ValueError(msg)
def args_for(full,model,out):
 a=full.parse_full_args(['--model-path',model,'--out',out,'--arm','K0','--partitions','dev,calibration','--stages','k_score','--scorer','rightpad','--dtype','float32','--no-hf32','--require-record-grade','--device','npu','--round-dir',out+'/identity-cache','--limit','0','--k-only',','.join(GROUPS)])
 a.token_budget=16384
 require(a.adapter is None,'adapter must be None');return a
def checked(fn):
 def call(rows,mode='full'):
  v=fn(rows,mode);require(len(v)==len(rows),'scorer row count')
  for row,s in zip(rows,v):require(isinstance(s,list) and len(s)==len(row['levels']) and all(type(x) in (int,float) and math.isfinite(x) for x in s),'bad score vector')
  return v
 for name in ('describe','token_stats','dedup_stats'):
  if hasattr(fn,name):setattr(call,name,getattr(fn,name))
 return call
def check_header(h,model,desc):
 require(h['model']=={k:model[k] for k in ('path','sha256','kind','base_path','base_revision')},'header identity')
 require(h['arm']=='K0' and h['stages']=='k_score' and h['device']=='npu' and h['dtype']=='float32' and h['limit']==0 and h['limit_groups']==0 and set(h['partitions'])=={'dev','calibration'} and h['primary_input_mode']=='full','header scope')
 require(h['scorer']==desc and desc.get('record_grade') is True and desc.get('mode')=='rightpad' and desc.get('token_budget')==16384,'header descriptor')
 require(not h['dry_run_warnings'],'header warnings')
def populations(core):
 result={}
 for group,n in zip(GROUPS,COUNTS):
  suite,part,_=group.split('/');rows,path=core.load_partition(suite,part)
  require(len(rows)==n,'population count '+group);require(sha(path)==CONFIG['data_pins'][path],'population hash '+group);result[group]=rows
 return result
def verify(out,identity,desc,expected=None):
 import core_r3 as C, admissible_store_r3 as AS, selection_evidence_r3 as SE
 spec=importlib.util.spec_from_file_location('compare_dev',str(HERE/'compare_dev.py')); compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)
 pops=populations(C);evidence={};ordered={}
 for group,rows in pops.items():
  s,p,k=group.split('/');path=C.k_readout_path(out,s,p,k);receipt=AS.receipt_path(path)
  require(os.path.isfile(path) and os.path.isfile(receipt),'missing receipt '+group)
  raw=AS.check_receipt(path,identity['sha256'],desc,recover=False);raw=SE.validate_population(raw,rows,C.kev_key)
  compare.score_rows(rows,raw,identity['sha256'])
  evidence[group]={'store_sha256':sha(path),'receipt_sha256':sha(receipt),'rows':len(raw)};ordered[group]=raw
 if expected is not None:require(evidence==expected,'inference store evidence mismatch')
 return pops,ordered,evidence
def check_identity(actual,model):
 for k in ('path','sha256','kind','base_path','base_revision'):require(actual.get(k)==model[k],'model identity '+k)
 require(actual.get('files')==model['weight_shard_pins'],'model weight inventory')
def run(phase,model_id,out):
 import full_eval_r3 as F, core_r3 as C, testlock_r3 as TL, variants_r3 as V
 model=next(x for x in CONFIG['models'] if x['id']==model_id);m=model['model'];out=str(Path(out).resolve());Path(out).mkdir(parents=True,exist_ok=True)
 start=time.monotonic();receipt=Path(out)/'INFERENCE-READY.json';a=args_for(F,m['path'],out)
 actual=TL.model_identity(m['path'],None,out+'/identity-cache');check_identity(actual,{**m,'weight_shard_pins':model['weight_shard_pins']})
 if phase=='infer':
  receipt.unlink(missing_ok=True)
  import eval_r3, prompt, scorer_r3
  bindings={k:{'path':str(Path(v.__file__).resolve()),'sha256':sha(v.__file__)} for k,v in [('full_eval_r3',F),('eval_r3',eval_r3),('core_r3',C),('prompt',prompt),('scorer_r3',scorer_r3)]}
  scorer=checked(eval_r3.make_score_fn(a));desc=scorer.describe();r=F.run_full(a,scorer);require('track_k' not in r,'unexpected statistics');check_header(r['header'],m,desc)
  _,_,ev=verify(out,actual,desc)
  save(receipt,{'version':1,'model_id':model_id,'identity':actual,'out':out,'groups':GROUPS,'descriptor':desc,'stores':ev,'inference_header':r['header'],'elapsed_seconds':time.monotonic()-start,'config_sha256':sha(HERE/'config.json'),'import_bindings':bindings,'weight_pins_origin':'reviewed runtime bridge PLAN.json sha256 '+CONFIG['plan_sha256'],'source_pins_origin':'rc1-base-reuse/SOURCE-PINS.json sha256 '+CONFIG['source_pins_sha256']})
  return
 h=json.loads(receipt.read_text());require(h['version']==1 and h['model_id']==model_id and h['out']==out and h['identity']==actual and h['groups']==GROUPS and h['config_sha256']==sha(HERE/'config.json'),'receipt identity')
 desc=h['descriptor'];check_header(h['inference_header'],m,desc)
 pops,ordered,ev=verify(out,actual,desc,h['stores']);cal=GROUPS[0];fitted=V.fit_operator(pops[cal],[x['s'] for x in ordered[cal]])
 result={'schema':'matched-k0-clean-dev-v1','scope':'clean calibration and DEV only; no DEV variants/drop/blank','model_id':model_id,'identity':actual,'inference_receipt_sha256':sha(receipt),'inference_header':h['inference_header'],'stores':ev,'operator_fit':{'partition':cal,'n':len(pops[cal]),'fitted':fitted.summary()},'partitions':{}}
 for group in GROUPS:
  rows=pops[group];saved=ordered[group];scores=[x['s'] for x in saved];name=group.rsplit('/',1)[0]
  block={'n':len(rows),'headline':C.headline(rows,scores),'near_tie_census':C.near_tie_census(scores,gold=[C.gold_index(r) for r in rows],keys=[C.kev_key(r) for r in rows],option_ids=[C.level_ids(r) for r in rows]),'gold_position_distribution':C.gold_position_distribution(rows),'duplicate_option_audit':C.duplicate_option_audit(rows),'vectors':[{'k':x['k'],'ids':x['ids'],'gold':x['gold'],'s':x['s'],'p':C.softmax(x['s'])} for x in saved]}
  if group!=cal:block['operator']=V.operator_column(rows,scores,fitted,name)
  result['partitions'][name]=block
 result['cpu_elapsed_seconds']=time.monotonic()-start;save(Path(out)/'clean-report.json',result)
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['infer','score'],required=True);p.add_argument('--model-id',choices=[x['id'] for x in CONFIG['models']],required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.phase,a.model_id,a.out)
if __name__=='__main__':main()
