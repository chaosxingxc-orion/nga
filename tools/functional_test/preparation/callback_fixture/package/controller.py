#!/usr/bin/env python3
"""Detached group controller. External host ownership probe and queue drain are required."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys, time, traceback, shlex
from pathlib import Path
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('group_adapter',BASE/'adapter/group_adapter.py'); group=importlib.util.module_from_spec(spec); spec.loader.exec_module(group)

def put(path,obj): group.r3.write_atomic(path,obj)
def host_clear(probe,chips):
 # Main supplies an authoritative host-owner probe: exit 0 and exact JSON only on certain absence.
 p=subprocess.run([probe,'--chips',','.join(map(str,chips))],capture_output=True,text=True,timeout=60,check=True)
 o=json.loads(p.stdout)
 if o.get('chips')!=chips or o.get('unmanaged_owners')!=[] or o.get('certain') is not True: raise RuntimeError('host ownership uncertain or busy')
 return o

def release(group,alloc,chips,name,attempt,probe):
 rec=json.loads((attempt/'CONTAINER.json').read_text()); cid=rec['id']
 if rec['name']!=name: raise RuntimeError('container name mismatch')
 obj=group.r3.docker_inspect(name)
 if obj is None or obj['Id']!=cid or obj['Name'].lstrip('/')!=name or obj['State'].get('Status') not in ('exited','dead') or obj['HostConfig'].get('AutoRemove') is not False: raise RuntimeError('terminal identity uncertain')
 code=obj['State'].get('ExitCode')
 if type(code)!=int: raise RuntimeError('missing container exit code')
 marker=attempt/'EXIT.json'; recorded=json.loads(marker.read_text()) if marker.exists() else None
 if recorded is not None and recorded.get('exit_code')!=code: raise RuntimeError('exit marker differs')
 put(attempt/'TERMINAL.json',{'container_id':cid,'name':name,'exit_code':code,'result':'unknown' if recorded is None else ('success' if code==0 else 'failed'),'exit_marker_present':recorded is not None,'utc':time.time()})
 host=host_clear(probe,chips); put(attempt/'HOST-RELEASE-CHECK.json',host)
 group.transact('release',alloc,chips,name,attempt/'RELEASE.json',claim_path=attempt/'CLAIM.json',container=name,container_id=cid)
 return code

def verify_pins(c):
 for name, expected in c['source_pins'].items():
  if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected: raise RuntimeError('source pin differs: '+name)

def main(c,observe=False):
 chips=c['chips']; name=c['name']; out=Path(c['out']); attempt=out/'attempts'/name
 verify_pins(c)
 if chips!=[0,1,2,3]: raise ValueError('first smoke requires selected chips 0..3')
 out.mkdir(parents=True,exist_ok=True)
 # Scheduling integration must stop refilling selected lanes before this controller starts.
 if c.get('queue_drained') is not True: raise ValueError('main must set queue_drained after coordination')
 deadline=time.monotonic()+600
 while not observe:
  try:
   host_clear(c['host_ownership_probe'],chips)
   if any(group.r3.live_chip_conflict(x,None) for x in chips): raise RuntimeError('docker ownership busy')
   doc=json.loads(Path(c['allocation']).read_text()); group.r3.validate_doc(doc)
   if any(sum(e['chip']==x for e in doc['free'])!=1 for x in chips): raise RuntimeError('ledger busy')
   break
  except Exception:
   if time.monotonic()>=deadline: raise RuntimeError('group unavailable or uncertain for 600 seconds')
   time.sleep(10)
 cmd=[sys.executable,'-B','-P',str(BASE/'launch.py'),'--chips',','.join(map(str,chips)),'--out',str(out),'--name',name,'--probe',c['host_ownership_probe']]
 if not observe: subprocess.run(cmd,check=True)
 # wait is event-driven; 600 seconds is only a bounded reconnect/heartbeat, never a stop limit.
 cid=json.loads((attempt/'CONTAINER.json').read_text())['id']
 while True:
  try:
   p=subprocess.run(['docker','wait',cid],capture_output=True,text=True,timeout=600,check=True)
   int(p.stdout.strip()); break
  except subprocess.TimeoutExpired:
   put(attempt/'observer-heartbeat.json',{'utc':time.time(),'container_id':cid,'status':'waiting'})
 code=release(group,c['allocation'],chips,name,attempt,c['host_ownership_probe'])
 if (out/'reference/manifest.json').exists():
  p=subprocess.run([c['cpu_python'],'-B','-P',str(BASE/'code/cpu_reference.py'),str(out/'reference'),'--release',str(attempt/'RELEASE.json')],capture_output=True,text=True)
  put(attempt/'CPU-REFERENCE-STATUS.json',{'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-4000:]})
 return code
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--observe',action='store_true'); a=p.parse_args(); c=json.loads(Path(a.config).read_text()); out=Path(c['out']); out.mkdir(parents=True,exist_ok=True)
 try: sys.exit(main(c,a.observe))
 except Exception as e:
  put(out/'CONTROLLER-ESCALATION.json',{'status':'held_or_not_claimed_reconcile','error':repr(e),'utc':time.time()}); traceback.print_exc(); sys.exit(1)
