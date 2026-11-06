#!/usr/bin/env python3
"""Wait read-only for selected finite train and configured inference lanes, then run controller."""
import argparse, fcntl, json, os, re, subprocess, sys, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import controller

def inspect(cid):
 if not re.fullmatch('[a-f0-9]{64}',cid): raise RuntimeError('invalid container id')
 p=subprocess.run(['docker','inspect',cid],capture_output=True,text=True,timeout=30,check=True)
 a=json.loads(p.stdout)
 if not isinstance(a,list) or len(a)!=1 or a[0].get('Id')!=cid: raise RuntimeError('container identity uncertain')
 return a[0]

def terminal(cid,chip,expected_name=None):
 o=inspect(cid); s=o['State']; h=o['HostConfig']
 if expected_name and o['Name']!='/'+expected_name: raise RuntimeError('container name mismatch')
 if not any(d.get('PathOnHost')=='/dev/davinci'+str(chip) for d in h.get('Devices') or []): raise RuntimeError('container chip mismatch')
 if h.get('AutoRemove') is not False: raise RuntimeError('container retention uncertain')
 if s['Status'] in ('running','created','paused','restarting'): return False
 if s['Status']!='exited' or type(s.get('ExitCode')) is not int or s['ExitCode']!=0: raise RuntimeError('container terminal failure or uncertainty')
 return True

def ready(c):
 pending=[]
 for lane in c['dependencies']:
  chip=lane['chip']; train=Path(lane['train']); dev=Path(lane['dev']); jid=lane['id']
  if not (train/'train-LAUNCH.json').is_file(): pending.append(jid+':train receipt');continue
  t=json.loads((train/'train-LAUNCH.json').read_text())
  if t.get('chip')!=chip or t.get('phase')!='train': raise RuntimeError('training receipt identity')
  if not terminal(t['container_id'],chip): pending.append(jid+':training');continue
  if not (train/'COMPLETE.json').is_file(): pending.append(jid+':train COMPLETE');continue
  if json.loads((train/'COMPLETE.json').read_text())!={'exit_code':0,'steps':3116,'scientific_acceptance':False}: raise RuntimeError('train COMPLETE invalid')
  spec=c['dev_dependency']
  launch=dev/spec['launch_file']; exit_file=dev/spec['exit_file']
  if not launch.is_file() or not exit_file.is_file(): pending.append(jid+':full DEV');continue
  r=json.loads(launch.read_text()); e=json.loads(exit_file.read_text())
  if r.get('chip')!=chip or e.get('container_id')!=r.get('container_id') or type(e.get('exit_code')) is not int or e['exit_code']!=0 or e.get('container_exit_code')!=0: raise RuntimeError('DEV receipt or exit invalid')
  if not terminal(r['container_id'],chip,spec['container_name_template'].format(id=jid,chip=chip)): pending.append(jid+':DEV actual exit');continue
  if not (dev/spec['artifact_file']).is_file(): pending.append(jid+':DEV artifact');continue
 return pending

def main(c):
 if c.get('queue_drained') is not False or [x['chip'] for x in c['dependencies']]!=[0,1,2,3]: raise ValueError('invalid waiting configuration')
 out=Path(c['out']);out.mkdir(parents=True,exist_ok=True)
 with (out/'waiter.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  controller.verify_pins(c)
  while True:
   pending=ready(c)
   controller.put(out/'WAITER-STATUS.json',{'state':'waiting_dependencies' if pending else 'dependencies_complete','pending':pending,'utc':time.time(),'pid':os.getpid()})
   if not pending: break
   time.sleep(600)
  c=dict(c,queue_drained=True)
  return controller.main(c)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text());out=Path(c['out']);out.mkdir(parents=True,exist_ok=True)
 try:
  code=main(c);controller.put(out/'WAITER-EXIT.json',{'exit_code':code,'utc':time.time()});sys.exit(code)
 except Exception as e:
  controller.put(out/'WAITER-EXIT.json',{'exit_code':1,'error':repr(e),'utc':time.time()});traceback.print_exc();sys.exit(1)
