#!/usr/bin/env python3
"""Bounded, read-only snapshot of Docker and host NPU process ownership on 175."""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

def run(*cmd):
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=20,check=True)
 if p.stderr.strip(): raise RuntimeError('command stderr: '+cmd[0])
 return p.stdout

def processes(s,chip):
 lines=[x.strip() for x in s.splitlines() if x.strip()]
 if len(lines)<4 or not re.fullmatch(r'NPU ID\s*:\s*'+str(chip),lines[0]) or not re.fullmatch(r'Chip Count\s*:\s*1',lines[1]) or not re.fullmatch(r'Chip ID\s*:\s*0',lines[-1]): raise ValueError('bad process header')
 body=lines[2:-1]
 if body==['No process in device.']: return []
 result=[]
 for line in body:
  m=re.fullmatch(r'Process id:([1-9][0-9]*)\s+Process name:(\S+)\s+Process memory\(MB\):([0-9]+)',line)
  if not m: raise ValueError('bad process record')
  result.append(int(m[1]))
 if not result or len(set(result))!=len(result): raise ValueError('empty or duplicate processes')
 return result

def listing(s,chips):
 if s.count('| NPU     Chip              | Process id')!=1 or 'npu-smi ' not in s: raise ValueError('missing process table')
 table=s.split('| NPU     Chip              | Process id',1)[1]
 rows={c:[] for c in chips}; empty=set()
 for line in table.splitlines()[1:]:
  line=line.strip()
  if not line or re.fullmatch(r'\+[=+-]+\+',line): continue
  m=re.fullmatch(r'\|\s*(\d+)\s+(\d+)\s*\|\s*([1-9][0-9]*)\s*\|\s*(\S+)\s*\|\s*(\d+)\s*\|\s*(NA|[0-9]+)\s*\|',line)
  if m:
   n=int(m[1]);
   if int(m[2])!=0 or n not in range(8): raise ValueError('bad process device')
   if n in rows: rows[n].append(int(m[3]))
   continue
  m=re.fullmatch(r'\|\s*No running processes found in NPU (\d+)\s*\|',line)
  if m:
   n=int(m[1]);
   if n in empty or n not in range(8): raise ValueError('bad empty row')
   empty.add(n); continue
  raise ValueError('unknown process table row')
 for c in chips:
  if c in empty and rows[c] or len(rows[c])!=len(set(rows[c])): raise ValueError('contradictory process table')
  if not rows[c] and c not in empty: raise ValueError('missing device process row')
 return rows

def containers(chips):
 ids=run('docker','ps','-aq','--no-trunc').split()
 if len(ids)!=len(set(ids)) or any(not re.fullmatch('[a-f0-9]{64}',x) for x in ids): raise ValueError('bad docker inventory')
 owners=[]
 for start in range(0,len(ids),128):
  batch=ids[start:start+128]; rows=json.loads(run('docker','inspect',*batch))
  if not isinstance(rows,list) or sorted(x.get('Id','') for x in rows)!=sorted(batch): raise ValueError('docker identities')
  for x in rows:
   state=x['State']['Status']; host=x['HostConfig']
   if state not in ('created','running','paused','restarting','removing','exited','dead'): raise ValueError('docker state')
   if state in ('exited','dead'): continue
   devices=host.get('Devices') or []; mounts=x.get('Mounts') or []
   if not isinstance(devices,list) or not isinstance(mounts,list): raise ValueError('docker devices')
   paths=[d['PathOnHost'] for d in devices]
   if not all(isinstance(v,str) for v in paths): raise ValueError('docker device path')
   if host.get('Privileged') or host.get('DeviceRequests') or host.get('DeviceCgroupRules') or any(v in ('/','/dev','/dev/davinci*') or v in ['/dev/davinci'+str(c) for c in chips] for v in paths) or any(m.get('Source') in ('/','/dev') or m.get('Source') in ['/dev/davinci'+str(c) for c in chips] for m in mounts): owners.append({'container':x['Id'],'state':state})
 return owners

def check(chips):
 if Path('/.dockerenv').exists() or Path('/proc/1/comm').read_text().strip()!='systemd' or os.uname().nodename!='k8s-node1': raise ValueError('host identity')
 owners=containers(chips)
 table=listing(run('/usr/local/sbin/npu-smi','info'),chips)
 for c in chips:
  pids=processes(run('/usr/local/sbin/npu-smi','info','-t','proc-mem','-i',str(c)),c)
  if sorted(pids)!=sorted(table[c]): raise ValueError('process snapshots differ')
  for pid in pids:
   if not Path('/proc',str(pid),'status').is_file(): raise ValueError('host pid unavailable')
   owners.append({'chip':c,'host_pid':pid})
 return {'chips':chips,'unmanaged_owners':owners,'certain':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--chips',required=True);a=p.parse_args()
 try:
  chips=[int(x) for x in a.chips.split(',')]
  if chips!=[0,1,2,3]: raise ValueError('unexpected selection')
  x=check(chips);print(json.dumps(x));sys.exit(1 if x['unmanaged_owners'] else 0)
 except Exception as e:
  print(json.dumps({'certain':False,'error':str(e)}));sys.exit(2)
