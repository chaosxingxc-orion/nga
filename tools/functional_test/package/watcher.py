#!/usr/bin/env python3
"""Durable metadata polling; only completed reviewed inputs trigger packet assembly."""
import argparse, fcntl, json, os, sys, time, traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import collector as B
import integration as I

def tick(cfg,out):
 for name in B.ROLES:
  p=Path(cfg['configs'][name])
  if not p.is_file():return {'status':'pending','missing':'config','role':name}
  c=B.read(p);o=Path(c['out']);rd=Path(c['round_dir'])
  for q in (o/'INFERENCE-READY.json',o/'INFER-EXIT.json',o/'K-REPORT.json',o/'RUN_IDENTITY.json',o/'HOST-RELEASE-VERIFIED.json',rd/'FINAL.json',rd/'TEST-READS.log'):
   if not q.is_file():return {'status':'pending','missing':str(q),'role':name}
 if not (Path(cfg['export_dir'])/'COMPLETE.json').is_file():return {'status':'pending','missing':'completed population capture'}
 x=dict(cfg);x['populations']=I.capture_populations(cfg);x['identities']=I.identities(cfg,out)
 for d in cfg['module_dirs']:sys.path.insert(0,d)
 import r3_final_container as K
 x['observations']=I.observations(cfg,out,K)
 result=B.build(x,out)
 if result['status']=='ready_for_consumer':
  review=B.read(cfg['completed_access_review']);draft=B.read(Path(out)/'review-input.json')
  if review.get('accepted') is not True or any(review.get(k)!=v for k,v in draft.items()):
   result['status']='ready_for_review';return result
  import subprocess
  if B.sha(cfg['consumer'])!=cfg['consumer_sha256']:raise ValueError('consumer differs')
  p=subprocess.run([cfg.get('python',sys.executable),'-B','-P',cfg['consumer'],'--config',str(Path(out)/'consumer-config.json'),'--out',str(Path(out)/'comparison')])
  result['consumer_exit']=p.returncode
  if p.returncode not in (0,2):result['status']='error'
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--out',required=True);ap.add_argument('--once',action='store_true');a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with (out/'watcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);count=0
  while True:
   count+=1
   try:
    if not Path(a.config).is_file():result={'status':'pending','missing':'watcher config'}
    else:result=tick(B.read(a.config),out)
   except Exception as e:result={'status':'error','error':str(e)}
   result.update(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),poll=count);B.save(out/'heartbeat.json',result)
   print(json.dumps(result),flush=True)
   if a.once or result['status']=='error' or result['status']=='ready_for_consumer':
    B.save(out/'EXIT.json',{'exit_code':1 if result['status']=='error' else 0,'status':result['status']});return 1 if result['status']=='error' else 0
   time.sleep(600)
if __name__=='__main__':sys.exit(main())
