#!/usr/bin/env python3
"""E30 deterministic CPU worker and independently recomputed audit fixture."""
import argparse,hashlib,json,os,signal,tempfile,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic(p,x):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 with os.fdopen(fd,'w') as f:json.dump(x,f);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def worker(path):
 c=json.loads(path.read_text());out=Path(c['out']);records=out/'records';records.mkdir(exist_ok=True);values=[]
 for i in range(24):
  p=records/(str(i).zfill(6)+'.json');item={'index':i,'value':i*i,'config_sha256':sha(path)}
  if p.exists():
   x=json.loads(p.read_text());assert x['payload']==item and x['sha256']==stamp(item)
  else:atomic(p,{'payload':item,'sha256':stamp(item)})
  values.append(i*i);atomic(out/'STATUS.json',{'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stage':'inference','progress':i+1,'total':24,'chips':0});print('heartbeat',i+1,flush=True);time.sleep(.5)
 atomic(out/'report.json',{'count':24,'sum_squares':sum(values)})
 atomic(out/'inference-COMPLETE.json',{'rc':0,'stage':'completed','progress':24,'total':24,'config_sha256':sha(path),'outputs':{'report.json':sha(out/'report.json')}})
def verify(path,out):
 c=json.loads(path.read_text());run=Path(c['out']);assert not out.exists();time.sleep(8)
 ps=sorted((run/'records').glob('*.json'));assert [p.name for p in ps]==[str(i).zfill(6)+'.json' for i in range(24)];total=0
 for i,p in enumerate(ps):
  x=json.loads(p.read_text());assert x['sha256']==stamp(x['payload']);assert x['payload']=={'index':i,'value':i*i,'config_sha256':sha(path)};total+=x['payload']['value']
 assert json.loads((run/'report.json').read_text())=={'count':24,'sum_squares':total};atomic(out,{'config_sha256':sha(path),'review_flags':[],'records':24,'sum_squares':total})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args();verify(a.config,a.out) if a.out else worker(a.config)
