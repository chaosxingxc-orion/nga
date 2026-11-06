#!/usr/bin/env python3
"""Collect producer metadata; never opens TEST data or starts work."""
import argparse, datetime, hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106')
IMAGE='sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d'
JOBS=[(f'q{s}-s{seed}',size,seed) for s,size in [('0p8b','0.8B'),('2b','2B'),('4b','4B'),('9b','9B')] for seed in (2,3)]
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def collect(root, ident, size, seed, model, inspect=None, deep=True):
 d=root/ident; missing=[]; errors=[]; pins={}; inspect=inspect or docker_inspect
 def get(name):
  p=d/name
  if not p.is_file():missing.append(str(p));return None
  try:
   obj=read(p);pins[name]={'path':str(p),'sha256':sha(p)};return obj
  except (OSError,ValueError) as e:errors.append(str(p)+': '+str(e));return None
 def check(condition,msg):
  if not condition: errors.append(msg)
 smoke=get('smoke.json'); train=get('train.json'); done=get('COMPLETE.json')
 for phase,c in [('smoke',smoke),('train',train)]:
  if c is not None:
   check(c.get('owner')=='rc1-functional-'+ident and c.get('seed')==seed and c.get('model',{}).get('id')=='Qwen3.5-'+size+'-Base' and c.get('recipe_id')=='k1-base-'+size.lower()+'-3116-v2' and c.get('adapter')=='k1-family-train-v2',phase+' config identity')
   check((c.get('engineering_stop_after')==2 and c.get('resume') is None) if phase=='smoke' else (c.get('engineering_stop_after')==3114 and isinstance(c.get('resume'),dict) and c['resume'].get('path')=='/run/nga/output/result/ckpt/step_000002.pt'),phase+' stop/resume')
  launch=get(phase+'-LAUNCH.json');ex=get(phase+'-EXIT.json')
  if launch is not None:
   check(launch.get('phase')==phase and c is not None and launch.get('config_sha256')==sha(d/(phase+'.json')),phase+' launch config')
   try:
    obj=inspect(launch['container_id']);state=obj['State'];devices={x.get('PathOnHost') for x in obj['HostConfig'].get('Devices') or []}
    check(obj['Id']==launch['container_id'] and obj['Name']=='/nga-rc1-'+ident+'-'+phase and obj['Image']==IMAGE and obj['HostConfig'].get('AutoRemove') is False and '/dev/davinci'+str(launch['chip']) in devices,phase+' container identity')
    if state['Status'] in ('created','running','paused','restarting'):missing.append(phase+' container terminal')
    else:check(state['Status']=='exited' and state['ExitCode']==0,phase+' container exit')
   except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:errors.append(phase+' inspect: '+str(e))
  if ex is not None:
   check(launch is not None and ex.get('container_id')==launch.get('container_id') and ex.get('chip')==launch.get('chip') and ex.get('phase')==phase and ex.get('image')==IMAGE and ex.get('exit_code')==0,phase+' exit receipt')
 if done is not None:check(done=={'exit_code':0,'steps':3116,'scientific_acceptance':False},'terminal mismatch')
 if done is not None:
  pub=get('result/adapter/PUBLICATION.json');binding=get('result/adapter/BINDING.json');cfg=get('result/adapter/adapter_config.json')
  ck=d/'result/ckpt/step_003116.pt';smoke_ck=d/'result/ckpt/step_000002.pt';adapter=d/'result/adapter'
  files=[ck,smoke_ck,adapter/'adapter_model.safetensors',model/'.complete']
  for p in files:
   if not p.is_file():missing.append(str(p))
  if pub is not None and binding is not None:
   check(pub.get('binding')==binding and binding.get('owner')=='rc1-functional-'+ident and set(pub.get('files',{}))=={'adapter_config.json','adapter_model.safetensors'},'publication binding')
   if deep and all(p.is_file() for p in files) and cfg is not None and train is not None:
    check(binding.get('checkpoint_sha256')==sha(ck) and isinstance(train.get('resume'),dict) and train['resume'].get('sha256')==sha(smoke_ck),'checkpoint ancestry')
    for name in ('adapter_config.json','adapter_model.safetensors'):check(pub.get('files',{}).get(name)==sha(adapter/name),'publication payload '+name)
    check(cfg.get('base_model_name_or_path')=='Qwen3.5-'+size+'-Base' and cfg.get('revision')==(model/'.complete').read_text().splitlines()[0],'adapter revision')
 return {'id':ident,'status':'contradiction' if errors else 'pending' if missing else 'training_verified' if deep else 'training_metadata_ready','missing':missing,'errors':errors,'pins':pins}
def docker_inspect(cid):
 return json.loads(subprocess.run(['docker','inspect',cid],check=True,text=True,capture_output=True,timeout=30).stdout)[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 queue=read(a.root/'QUEUE.json');jobs={j['id']:j for j in queue['jobs']}
 rows=[collect(a.root,i,s,n,Path(jobs[i]['model'])) for i,s,n in JOBS]
 result={'schema':'rc1-training-collection-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lanes':rows,'training_verified':sum(x['status']=='training_verified' for x in rows),'note':'Training evidence only; no TEST admission or scientific review.'}
 a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\n');os.replace(tmp,a.output)
 print(json.dumps({'training_verified':result['training_verified'],'pending':sum(x['status']=='pending' for x in rows),'contradiction':sum(x['status']=='contradiction' for x in rows)}))
if __name__=='__main__':main()
