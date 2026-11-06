#!/usr/bin/env python3
"""Metadata-only fixed roster materializer. Never starts TEST or creates reviews."""
import argparse, contextlib, datetime, fcntl, importlib.util, json, os, shlex, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assembler as A, collector
C=A.C
DEV=collector.ROOT/'matched-current-dev-consumer-source'
OUT=Path('/mnt/cephfs/xingchao/experiments/jev/rc1-test-materializer-2651514')

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

@contextlib.contextmanager
def dev_imports():
 # DEV numerics use the same module names as TEST's accepted R0 closure.
 names=('common','split','decision','thresholds','metrics','core_r3','variants_r3','degenerate_r3','provenance_r3','matched_legacy','devwatch_for_materializer')
 saved={name:sys.modules.get(name) for name in names}; paths=list(sys.path)
 try:yield
 finally:
  sys.path[:]=paths
  for name,value in saved.items():
   if value is None:sys.modules.pop(name,None)
   else:sys.modules[name]=value

def pin(path):return {'path':str(path),'sha256':C.sha(path)}
def save(path,obj):C.save(path,obj)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def examine(config, comparison, train, devmod):
 """Check the consumer's output contract and bind its exact fixed identities."""
 ids=C.LANES+C.BASES; models={m['id']:m for m in config['models']}; lanes={x['lane']:x for x in config['lanes']}
 mapping={f'q{s}-base':b for s,b in [('0p8b','08b-k0'),('2b','2b-k0'),('4b','4b-k0'),('9b','9b-k0')]}
 if set(lanes)!=set(C.LANES) or set(mapping.values())!=set(models):raise ValueError('DEV fixed roster differs')
 if comparison.get('schema')!='matched-current-dev-comparison-v1' or comparison.get('synthetic_fixture') != (config['mode']=='synthetic-fixture'):raise ValueError('DEV comparison format')
 operands=comparison.get('operands',[]); index={x['role']:x for x in operands}
 if len(operands)!=12 or len(index)!=12 or set(index)!=set(lanes)|set(models):raise ValueError('DEV operand roster')
 statuses=[]
 for member in ids:
  lane=lanes.get(member); model=models[lane['baseline_id'] if lane else mapping[member]]; o=index[lane['lane'] if lane else mapping[member]]
  if o.get('size')!=model['size'] or o.get('seed')!=(lane['seed'] if lane else None):raise ValueError('DEV size or seed differs')
  reasons=[]; problems=[]
  if lane:
   if lane['size'] != model['size'] or lane['seed'] != int(member[-1]) or lane['new_adapter'] != str(collector.ROOT/member/'result/adapter'):raise ValueError('DEV lane identity differs')
   t=train[member]
   if t['status']=='pending':reasons.extend(t['missing'])
   elif t['status'] not in ('training_verified','training_metadata_ready'):problems.extend(t['errors'])
  if o.get('status')=='PENDING_MISSING_INPUT':reasons.append('DEV: '+o.get('detail','missing'))
  elif o.get('status')!='VALIDATED_OPERAND':problems.append('DEV: '+str(o.get('detail',o.get('status'))))
  else:
   if o.get('groups')!=list(devmod.ALL if lane else devmod.CLEAN):problems.append('DEV group set differs')
   if o.get('runtime',{}).get('image')!=config['image'] or o.get('runtime',{}).get('status')!='ALIGNED_INSTRUMENT':problems.append('DEV runtime differs')
  statuses.append({'id':member,'status':'contradiction' if problems else 'pending' if reasons else 'ready','pending':reasons,'errors':problems})
 if comparison.get('queue_failures'):raise ValueError('DEV queue failure')
 if comparison.get('status')=='REFUSED_CONTRADICTION':raise ValueError('DEV consumer refused')
 return statuses

def roster(config, statuses, train, evidence, identity_dir):
 models={m['id']:m for m in config['models']};lanes={x['lane']:x for x in config['lanes']};mapping={f'q{s}-base':b for s,b in [('0p8b','08b-k0'),('2b','2b-k0'),('4b','4b-k0'),('9b','9b-k0')]};rows=[]
 if any(x['status']!='ready' for x in statuses):raise ValueError('not all roles ready')
 for status in statuses:
  member=status['id'];lane=lanes.get(member);model=models[lane['baseline_id'] if lane else mapping[member]];base=model['model']['path'];adapter=lane['new_adapter'] if lane else None
  ident=C.TL.model_identity(base,adapter,str(identity_dir));ev={'base_inventory':pin(evidence['config']),'tokenizer':pin(Path(base)/'tokenizer.json'),'runtime':pin(A.STAGE/'runtime-environment.json'),'dev_consumer_review':pin(evidence['review']),'dev_comparison':pin(evidence['comparison'])}
  if lane:
   p=train[member]['pins'];ev.update(publication=p['result/adapter/PUBLICATION.json'],training_terminal=p['COMPLETE.json'],smoke_resume=p['train.json'],dev_review=pin(evidence['comparison']))
  rows.append({'id':member,'status':'available','arm':'K1' if lane else 'K0','size':member.split('-')[0],'seed':lane['seed'] if lane else None,'terminal_step':3116 if lane else None,'model':base,'adapter':adapter,'identity_sha256':ident['sha256'],'evidence':ev})
 return rows

def step(out,devdir=DEV):
 out.mkdir(parents=True,exist_ok=True); config_path=devdir/'config.json';config=collector.read(config_path)
 # Keep review and reconstruction imports out of the accepted TEST closure.
 with dev_imports():
  w=load('devwatch_for_materializer',devdir/'watcher.py');m=w.M
  reviewed=w.review(config)
 queue=collector.read(collector.ROOT/'QUEUE.json');jobs={x['id']:x for x in queue['jobs']}
 train={i:collector.collect(collector.ROOT,i,s,n,Path(jobs[i]['model']),deep=False) for i,s,n in collector.JOBS}
 comp_path=Path(config['output'])/'comparison.json'; comparison=collector.read(comp_path) if comp_path.exists() else None
 if comparison is None or not reviewed:
  statuses=[{'id':i,'status':'pending','pending':['existing DEV consumer review or comparison pending'],'errors':[]} for i in C.LANES+C.BASES]
 else:statuses=examine(config,comparison,train,m)
 save(out/'pending.json',{'utc':now(),'roles':statuses,'training':list(train.values()),'consumer_reviewed':reviewed})
 if any(x['status']=='contradiction' for x in statuses):raise ValueError('role contradiction; see pending.json')
 if any(x['status']!='ready' for x in statuses) or comparison.get('status')!='MATCHED_CURRENT_DESCRIPTIVE_DEV':return 'pending'
 # Reconstruct independently using the reviewed consumer and check its stat fingerprint.
 # Deep checkpoints/adapter payload validation happens only at all-role readiness.
 train={i:collector.collect(collector.ROOT,i,s,n,Path(jobs[i]['model']),deep=True) for i,s,n in collector.JOBS}
 statuses=examine(config,comparison,train,m)
 save(out/'pending.json',{'utc':now(),'roles':statuses,'training':list(train.values()),'consumer_reviewed':reviewed})
 if any(x['status']=='contradiction' for x in statuses):raise ValueError('training contradiction at readiness; see pending.json')
 if any(x['status']!='ready' for x in statuses):return 'pending'
 before=w.fingerprint(config)
 with dev_imports():fresh,code=m.assemble(m.Consumer(config))
 if w.fingerprint(config)!=before:raise ValueError('DEV evidence changed during reconstruction')
 if code!=0:raise ValueError('DEV reconstruction no longer complete')
 statuses=examine(config,fresh,train,m)
 for t in train.values():
  for v in t['pins'].values():C.pinfile(v)
 if any(x['status']!='ready' for x in statuses):raise ValueError('DEV reconstructed status differs')
 snapshot=out/'dev-comparison.json';save(snapshot,fresh)
 evidence={'config':config_path,'review':Path(config['review']),'comparison':snapshot}
 rows=roster(config,statuses,train,evidence,out/'identity-cache');rp=out/'roster.json';save(rp,rows)
 resources={i:{'chip':k%8,'dependencies':(['K0','QWEN27B_ENVFIX'] if k%8<4 else ['TRAIN_DEV'])} for k,i in enumerate(C.LANES+C.BASES)};res=out/'resources.json';save(res,resources)
 # Exclusive intent: a crash during assembly requires human reconciliation, never re-invoke.
 intent=out/'ASSEMBLY-INTENT.json';fd=os.open(intent,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
 with os.fdopen(fd,'w') as f:json.dump({'utc':now(),'roster':pin(rp),'resources':pin(res)},f);f.flush();os.fsync(f.fileno())
 g=A.assemble(str(rp),str(res),str(out/'campaign'));save(out/'MATERIALIZED.json',{'utc':now(),'graph':pin(out/'campaign/graph.json'),'members':len(g['members']),'status':'needs_independent_review'})
 return 'materialized'

def result_tick(config, out):
 # Isolate the two unrelated collector modules in separate CPU processes.
 runner=Path(__file__).resolve().parent.parent/'package/watcher.py'
 command=[sys.executable,'-B','-P',str(runner),'--config',str(config),'--out',str(out/'same-test'),'--once']
 result=subprocess.run(command,check=False)
 if result.returncode:raise ValueError('same-TEST collector failed; see same-test/heartbeat.json')
 status=collector.read(out/'same-test/heartbeat.json')
 if status['status']=='error':raise ValueError('same-TEST collector failed; see same-test/heartbeat.json')
 return status

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=OUT);p.add_argument('--once',action='store_true');p.add_argument('--result-config',type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 with (out/'watcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if (out/'EXIT.json').exists() or (out/'ASSEMBLY-INTENT.json').exists():raise RuntimeError('terminal or assembly intent exists; reconcile')
  cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--out',str(out)];cmd+=['--result-config',str(a.result_config.resolve())] if a.result_config else [];(out/'RELAUNCH.sh').write_text('#!/bin/sh\nexec '+shlex.join(cmd)+'\n')
  save(out/'LAUNCH.json',{'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'utc':now(),'command':cmd})
  try:
   materialized=False
   while True:
    result='materialized' if materialized else step(out);materialized=result=='materialized';roles=collector.read(out/'pending.json')['roles'];beat={'utc':now(),'status':result,'completed':sum(x['status']=='ready' for x in roles),'total':12};save(out/'heartbeat.json',beat);print(json.dumps(beat),flush=True)
    if a.result_config:
     collected=result_tick(a.result_config,out)
     beat['result_collector']=collected['status'];save(out/'heartbeat.json',beat)
     if collected['status']=='ready_for_consumer':save(out/'EXIT.json',{'exit_code':0,'utc':now(),'status':'collected','consumer_exit':collected['consumer_exit']});return 0
    if result=='materialized' and not a.result_config:save(out/'EXIT.json',{'exit_code':0,'utc':now(),'status':result});return 0
    if a.once:return 2
    time.sleep(600)
  except BaseException as e:
   save(out/'EXIT.json',{'exit_code':1,'utc':now(),'error':str(e)});raise
if __name__=='__main__':sys.exit(main())
