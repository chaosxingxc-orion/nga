#!/usr/bin/env python3
"""Resolve retained identities and Docker observations for the packet collector."""
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import collector as B

def identities(cfg,root):
 cache=B.read(cfg['identity_cache']) if Path(cfg['identity_cache']).is_file() else {};out={}
 for name in B.ROLES:
  c=B.read(cfg['configs'][name]);role=next(r for r in c['roster'] if r['id']==name)
  run=B.read(Path(c['out'])/'RUN_IDENTITY.json');base=str(Path(role['model']).resolve());adapter=role['adapter']; model=str(Path(adapter or base).resolve())
  if run['model_sha256']!=role['identity_sha256'] or run['model_path']!=model or run['arm']!=role['arm']:raise ValueError('run identity differs')
  revision=(Path(base)/'.complete').read_text().splitlines()[0];suffixes=('.safetensors','.bin','.pt','.json') if adapter else ('.safetensors','.bin','.pt')
  files={}
  for dp,dn,fn in os.walk(model):
   dn[:]=sorted(d for d in dn if not d.startswith('.'))
   for f in sorted(fn):
    if f.startswith('.') or not f.endswith(suffixes):continue
    p=Path(dp)/f; st=p.stat();key=f'{p}|{st.st_size}|{st.st_mtime_ns}'
    files[str(p.relative_to(model))]=cache[key] if key in cache else B.sha(p)
  kind='lora-adapter-unmerged' if adapter else 'checkpoint'
  payload={'kind':kind,'adapter_files':files,'base_revision':revision,'base_path':base} if adapter else {'kind':kind,'weight_files':files,'revision':revision}
  if not files or revision=='unknown' or B.digest(payload)!=role['identity_sha256']:raise ValueError('cached identity digest differs')
  doc={'path':model,'kind':kind,'base_path':base,'base_revision':revision,'files':files,'sha256':B.digest(payload)}
  path=Path(root)/'identities'/(name+'.json');B.save(path,doc);out[name]=str(path.resolve())
 return out

def observations(cfg,root,K):
 out={}
 for name in B.ROLES:
  c=B.read(cfg['configs'][name]);container=c['container'];spec=container['spec'];launch=B.read(container['launch_receipt'])
  obs=json.loads(subprocess.check_output(['docker','inspect',launch['id']],text=True))[0]
  K.verify_observation(spec,obs,launch['id']);state=obs['State']
  if state['Status']!='exited' or type(state['ExitCode']) is not int or state['ExitCode']!=0 or state.get('OOMKilled',False):raise ValueError('retained container failed')
  path=Path(root)/'observations'/(name+'.json');B.save(path,obs);out[name]=str(path.resolve())
 return out

def capture_populations(cfg):
 root=Path(cfg['export_dir']);complete=B.read(root/'COMPLETE.json');capture=B.read(root/'CAPTURE.json')
 if complete['capture_sha256']!=B.sha(root/'CAPTURE.json'):raise ValueError('capture hash differs')
 c=B.read(cfg['configs'][cfg['export_member']]);report=Path(c['out'])/'K-REPORT.json'
 if complete['config_sha256']!=B.digest(c) or capture['config_sha256']!=B.digest(c) or complete['report_sha256']!=B.sha(report):raise ValueError('capture owner differs')
 out={}
 for key,p in capture['populations'].items():
  if B.sha(p['path'])!=p['sha256']:raise ValueError('population hash differs')
  out[key]=p['path']
 return out
