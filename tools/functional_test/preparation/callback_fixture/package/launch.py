#!/usr/bin/env python3
"""Invoke only after main schedules an atomic free group. The detached controller observes and releases the claim."""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--chips',required=True,help='physical IDs, comma separated'); p.add_argument('--out',required=True,help='new or resumed Ceph run directory'); p.add_argument('--name',required=True,help='unique retained container name'); p.add_argument('--probe',required=True); a=p.parse_args()
chips=[int(x) for x in a.chips.split(',')]
if len(chips) != 4 or len(set(chips))!=len(chips) or any(x not in range(8) for x in chips): raise SystemExit('need 4 distinct chip IDs (2 is experimental)')
chips.sort(); out=Path(a.out).resolve(); base=Path(__file__).resolve().parent
if not str(out).startswith('/mnt/cephfs/') or any(x in str(out) for x in (',','\n')) or not a.name.replace('-','').isalnum(): raise SystemExit('out must be on Ceph and name alphanumeric/hyphen')
source=base/'adapter'
alloc='/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json'; image='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
inputs=[base/'DEV-MASKS.json',base/'WORKLOAD.json',base/'TENSOR-DIFF.json',base/'code',Path('/mnt/cephfs/models/Qwen3.8-27B'),Path('/mnt/cephfs/xingchao/experiments/jev/KEV'),Path(alloc),source/'group_adapter.py',Path('/usr/local/Ascend/driver'),Path('/etc/ascend_install.info')]
for x in inputs:
 if not x.exists(): raise SystemExit('missing input: '+str(x))
if subprocess.run(['docker','image','inspect',image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode: raise SystemExit('accepted image unavailable')
if subprocess.run(['docker','inspect',a.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0: raise SystemExit('container name already exists')
out.mkdir(parents=True,exist_ok=True); package=out/'package'; files=['DEV-MASKS.json','WORKLOAD.json','TENSOR-DIFF.json','code/core.py','code/prompt.py','code/raw_loading.py','code/score.py','code/inner.sh','code/cpu_reference.py','launch.py','controller.py','adapter/group_adapter.py','adapter/r3_resource_adapter.py']
for f in files:
 data=(base/f).read_bytes(); target=package/f; target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and target.read_bytes()!=data: raise SystemExit('resumed package differs: '+f)
 if not target.exists(): target.write_bytes(data)
pins={f:hashlib.sha256((package/f).read_bytes()).hexdigest() for f in files}
code_hash=hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest()
attempt=out/'attempts'/a.name; attempt.mkdir(parents=True,exist_ok=False)
mounts=[(str(package),'/run/package',True),(str(out),'/run/output',False),('/mnt/cephfs/models/Qwen3.8-27B','/run/model',True),('/usr/local/Ascend/driver','/usr/local/Ascend/driver',True),('/usr/local/sbin','/usr/local/sbin',True),('/etc/ascend_install.info','/etc/ascend_install.info',True)]
for suite in ('decision-v7','transfer-v4'):
 for name in ('dev','dev.variants'):
  src=f'/mnt/cephfs/xingchao/experiments/jev/KEV/{suite}/{name}.jsonl'
  if not Path(src).is_file(): raise SystemExit('missing '+src)
  mounts.append((src,f'/run/dev/{suite}/{name}.jsonl',True))
cmd=['docker','run','-d','--pull=never','--name',a.name,'--network=none','--runtime','ascend','--restart','no','--ipc','private','--shm-size','16g','--memory','192g','--cpus','16','--pids-limit','4096','--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
for d in ['davinci_manager','devmm_svm','hisi_hdc']+['davinci'+str(i) for i in chips]:
 if not Path('/dev/'+d).exists(): raise SystemExit('missing /dev/'+d)
 cmd+=['--device','/dev/'+d]
for src,dst,ro in mounts: cmd+=['--mount','type=bind,src='+src+',dst='+dst+(',readonly' if ro else '')]
cmd+=['-e','ASCEND_RT_VISIBLE_DEVICES='+','.join(map(str,range(len(chips)))),'-e','OMP_NUM_THREADS=1','--entrypoint','/bin/bash',image,'/run/package/code/inner.sh','/run/output/attempts/'+a.name,'--model','/run/model','--dev-root','/run/dev','--mask','/run/package/DEV-MASKS.json','--workload','/run/package/WORKLOAD.json','--tensor-diff','/run/package/TENSOR-DIFF.json','--out','/run/output','--physical',','.join(map(str,chips)),'--count',str(len(chips)),'--sequence-limit','2048','--code-hash',code_hash]
(attempt/'RELAUNCH.txt').write_text(' '.join(__import__('shlex').quote(x) for x in [sys.executable,str(base/'launch.py'),'--chips',','.join(map(str,chips)),'--out',str(out),'--name',a.name,'--probe',a.probe])+'\n')
(attempt/'COMMAND.json').write_text(json.dumps({'docker':cmd,'source_pins':pins,'relaunch_argv':sys.argv,'chips':chips,'note':'claim retained until detached controller confirms and releases'},indent=2)+'\n')
spec=importlib.util.spec_from_file_location('group_adapter',package/'adapter/group_adapter.py'); group=importlib.util.module_from_spec(spec); spec.loader.exec_module(group)
proof=attempt/'CLAIM.json'; group.transact('claim',alloc,chips,a.name,proof)
try:
 observed=subprocess.run([a.probe,'--chips',','.join(map(str,chips))],text=True,capture_output=True,check=True,timeout=60)
 observation=json.loads(observed.stdout)
 if observation.get('chips')!=chips or observation.get('certain') is not True or observation.get('unmanaged_owners')!=[]: raise RuntimeError('host ownership uncertain or busy after claim')
 for c in chips:
  if group.r3.live_chip_conflict(c,None): raise RuntimeError('launch-time live device conflict')
 result=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=120)
 (attempt/'CONTAINER.json').write_text(json.dumps({'id':result.stdout.strip(),'name':a.name})+'\n')
 print('launched',result.stdout.strip(),'claim',proof,flush=True)
except BaseException:
 print('Launch failed or uncertain; claim remains held. Reconcile container and claim before release.',file=sys.stderr); raise
