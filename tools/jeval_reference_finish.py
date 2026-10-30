#!/usr/bin/env python3
"""Detached E33 independent verifier waiter with actual Docker identity checks."""
import argparse,fcntl,hashlib,http.client,json,socket,subprocess,sys,time
from pathlib import Path

def require(v,m):
 if not v:raise ValueError(m)
def load(p):return json.loads(Path(p).read_text())
def resource_mapping(host):
 # Docker may reorder these arrays; preserve every path, option and duplicate.
 binds=sorted(host.get('Binds') or [])
 devices=sorted((d['PathOnHost'],d['PathInContainer'],d['CgroupPermissions'])
                for d in host.get('Devices') or [])
 return binds,devices
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def inspect(name):
 c=http.client.HTTPConnection('localhost',timeout=30);c.sock=socket.socket(socket.AF_UNIX);c.sock.settimeout(30);c.sock.connect('/var/run/docker.sock')
 try:c.request('GET','/containers/'+name+'/json');r=c.getresponse();require(r.status==200,'Docker inspect');return json.loads(r.read())
 finally:c.close()
def main(path):
 c=load(path);ch=sha(path);run=Path(c['out']);out=Path(str(run)+'_finish');rc=1
 lock=(out/'finish.lock').open('w')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BaseException:lock.close();raise
 if any((out/n).exists() for n in ['COMPLETE.json','INDEPENDENT_AUDIT.json','EXIT']):lock.close();raise ValueError('Existing finisher evidence preserved')
 def frozen():
  require(sha(path)==ch,'Config changed')
  for p,h in c['files'].items():require(sha(p)==h,'Frozen finisher dependency changed')
 try:frozen()
 except BaseException:lock.close();raise
 def binding():
  require(sha(path)==ch,'Config changed');r=load(run/'LAUNCH_RECEIPT.json');d=inspect(c['container']);spec=load(run/'NPU_SPEC.json');require(d['Id']==r['container_id'] and d['Image']==c['image']==r['image'],'Container identity');require(d['Config']['Cmd']==r['command']==spec['Cmd'] and d['Config']['Entrypoint']==r['entrypoint']==spec['Entrypoint'],'Container command');require(resource_mapping(d['HostConfig'])==resource_mapping(spec['HostConfig']),'Container resources');return d
 try:
  while True:
   d=binding();state=d['State']['Status'];s=load(run/'STATUS.json') if (run/'STATUS.json').exists() else {};line=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' container='+state+' stage='+str(s.get('stage'))+' progress='+str(s.get('progress'))+'/'+str(s.get('total'))+' q/s/chip='+str(s.get('questions_per_second_per_chip'))+' chips=1 reserved_GiB='+str(s.get('reserved_gib'))+'\n';(out/'digest.md').write_text(line)
   with (out/'heartbeat.log').open('a') as f:f.write(line)
   if state=='exited':require(d['State']['ExitCode']==0,'Inference Docker failed');break
   require(state in ['created','running','restarting'],'Unexpected inference state');time.sleep(10)
  frozen()
  with (out/'audit.log').open('ab') as f:subprocess.run([sys.executable,'-P',str(run/'verify_jeval_reference_inference.py'),'--config',str(path),'--out',str(out/'INDEPENDENT_AUDIT.json')],stdout=f,stderr=f,check=True)
  frozen();d=binding();require(d['State']['Status']=='exited' and d['State']['ExitCode']==0,'Inference state changed');audit=load(out/'INDEPENDENT_AUDIT.json');require(audit['config_sha256']==ch,'Audit identity');rc=0
 finally:
  terminal=dict(rc=rc,config_sha256=ch,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
  if rc==0:terminal.update(status='COMPLETED_SCOPED_REVIEW_REQUIRED' if audit['review_flags'] else 'COMPLETED_SCOPED',audit_sha256=sha(out/'INDEPENDENT_AUDIT.json'),review_flags=audit['review_flags'])
  (out/'COMPLETE.json').write_text(json.dumps(terminal,indent=2)+'\n');lock.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);main(p.parse_args().config)
