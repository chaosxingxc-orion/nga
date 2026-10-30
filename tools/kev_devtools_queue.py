#!/usr/bin/env python3
"""Frozen CPU controller: wait for verified E20 exit, then claim its chip for E22."""
import argparse,fcntl,hashlib,http.client,json,os,re,socket,subprocess,sys,tempfile,time
from pathlib import Path


def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()


def atomic(p,o):
 fd,t=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 with os.fdopen(fd,'w') as f:json.dump(o,f,indent=2);f.flush();os.fsync(f.fileno())
 os.chmod(t,0o644);os.replace(t,p)


def docker(method,path,obj=None):
 c=http.client.HTTPConnection('localhost',timeout=30);c.sock=socket.socket(socket.AF_UNIX);c.sock.settimeout(30);c.sock.connect('/var/run/docker.sock')
 try:
  c.request(method,path,body=json.dumps(obj).encode() if obj is not None else None,headers={'Content-Type':'application/json'})
  r=c.getresponse();b=r.read()
  if r.status>=300:raise ValueError('Docker request failed '+str(r.status)+' '+path)
  return json.loads(b) if b else None
 finally:c.close()


def verify_previous(entry,out):
 p=Path(entry['previous_run']);c=docker('GET','/containers/'+entry['previous_container']+'/json')
 if c['State']['Status']!='exited':return None
 if c['State']['ExitCode']!=0:raise ValueError('Previous container failed')
 if (p/'FAILED').exists() or not re.fullmatch(r'rc=0 utc=\S+\n?',(p/'DONE').read_text()):raise ValueError('Previous wrapper failed')
 terminal=json.loads((p/'REFERENCE_COMPLETE.json').read_text());assert terminal['rc']==0
 cfg=json.loads((p/'config.json').read_text())
 launch=json.loads((p/'LAUNCH_RECEIPT.json').read_text())
 assert c['Id']==launch['container_id'] and sha(p/'config.json')==launch['config_sha256']
 assert c['Image']==cfg['image']==launch['image'] and c['Config']['Cmd']==launch['command'] and c['Config'].get('Entrypoint')==launch['entrypoint']
 assert {d['PathOnHost'] for d in c['HostConfig'].get('Devices') or [] if re.fullmatch(r'/dev/davinci\d+',d['PathOnHost'])}=={'/dev/davinci'+str(entry['chip'])}
 audit=out/(entry['name']+'-PREVIOUS_AUDIT.json')
 with (out/'audit.log').open('ab') as f:
  subprocess.run([sys.executable,'-P',str(p/'verify_reference_kev.py'),'--config',str(p/'config.json'),'--out',str(audit)],stdout=f,stderr=subprocess.STDOUT,check=True)
 assert json.loads(audit.read_text())['status']=='VERIFIED_SCOPED'
 return c


def launch(entry,previous,out):
 cfgpath=Path(entry['config']);cfg=json.loads(cfgpath.read_text());run=Path(cfg['out'])
 assert cfg['physical_chip']==entry['chip'] and cfg['image']==previous['Image']
 assert not (run/'LAUNCH_RECEIPT.json').exists(),'Prior launch requires manual reconciliation'
 for p,h in cfg['files'].items():assert sha(p)==h,p
 allocation=Path('/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json')
 with Path(str(allocation)+'.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);a=json.loads(allocation.read_text());chip=entry['chip'];device='/dev/davinci'+str(chip)
  live=docker('GET','/containers/json')
  for obj in live:
   inspect=docker('GET','/containers/'+obj['Id']+'/json')
   assert not any(d['PathOnHost']==device for d in inspect['HostConfig'].get('Devices') or []),'Live chip conflict'
  owners=[v for v in a['allocation'] if v['chip']==chip];free=[v for v in a['free'] if v['chip']==chip]
  assert (len(owners)==1 and owners[0]['run']=='reference_inference/'+Path(entry['previous_run']).name) or (not owners and len(free)==1),'Ownership changed'
  a['allocation']=[v for v in a['allocation'] if v['chip']!=chip];a['free']=[v for v in a['free'] if v['chip']!=chip]
  now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  a['allocation'].append({'chip':chip,'owner':'E22 devtools dual protocol','run':'reference_inference/'+run.name,'claimed_utc':now,'previous_run':entry['previous_run'],'release_when':'complete independent audit, wrapper and retained container exited'})
  a.update(updated_utc=now,updated_by='E22 dependency controller');atomic(allocation,a)
  host=previous['HostConfig'];host={k:host[k] for k in ['Binds','NetworkMode','ShmSize','Ulimits','Devices'] if k in host}
  spec={'Image':cfg['image'],'Cmd':['bash',str(run/'run.sh')],'Entrypoint':previous['Config']['Entrypoint'],'Env':previous['Config']['Env'],'WorkingDir':'/tmp','HostConfig':host}
  created=docker('POST','/containers/create?name='+entry['container'],spec);cid=created['Id']
  inspect=docker('GET','/containers/'+cid+'/json')
  atomic(run/'LAUNCH_RECEIPT.json',{'container_id':cid,'image':inspect['Image'],'command':inspect['Config']['Cmd'],'entrypoint':inspect['Config']['Entrypoint'],'config_sha256':sha(cfgpath),'wrapper_sha256':sha(run/'run.sh'),'utc':now})
  atomic(run/'TRANSFER_EVIDENCE.json',{'previous_container':previous['Id'],'previous_exit_code':previous['State']['ExitCode'],'previous_audit_sha256':sha(out/(entry['name']+'-PREVIOUS_AUDIT.json')),'chip':chip,'utc':now})
  docker('POST','/containers/'+cid+'/start')
 return cid


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);args=ap.parse_args();p=Path(args.plan);plan=json.loads(p.read_text());out=Path(plan['out']);lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for f,h in plan['files'].items():assert sha(f)==h,f
 assert not (out/'QUEUE_COMPLETE.json').exists() and not (out/'STATUS.json').exists(),'Existing queue state requires reviewed continuation'
 progress={};rc=1
 try:
  while len(progress)<len(plan['entries']):
   for e in plan['entries']:
    if e['name'] in progress:continue
    previous=verify_previous(e,out)
    if previous is not None:progress[e['name']]=launch(e,previous,out)
   status={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stage':'wait_dependencies','progress':len(progress),'total':len(plan['entries']),'launched':progress}
   atomic(out/'STATUS.json',status)
   with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(status)+'\n')
   if len(progress)<len(plan['entries']):time.sleep(15)
  rc=0
 finally:atomic(out/'QUEUE_COMPLETE.json',{'rc':rc,'launched':progress,'scope':'Launch completion only, not inference acceptance'})

if __name__=='__main__':main()
