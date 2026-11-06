#!/usr/bin/env python3
"""Read-only operational predecessor checks; never claim or wait for CPU scoring."""
import argparse, hashlib, importlib.util, json, re, subprocess
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106')
K0=ROOT/'matched-k0-source'
QROOT=Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/qwen38-dev-host-rc1')
KPINS={'queue.py':'9fe8aaee0e32c0afc8971013201c943c7b3031faeb937692840e37443d3aba23','producer.py':'3416d76eb32e61a43deeec1797401c01dd5544d8f59c7f04d875848fdc7a2179','config.json':'168ad5806028142e7f81f3dc232f8640157fa043d38c7aa5b4a2dccd9a76053f','host_ownership_probe.py':'970990a82c773af9738c9e0f0a8fc89720271874e9a26ef6a2c27168cbc8a259'}
QCONFIG='45da9f7207cbfffd016458ae192da418fe42b8f8fc275d299f3bf3cd16a9b81d'
KIMAGE='sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d'
QIMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,msg):
 if not v:raise ValueError(msg)
def mod(p):
 s=importlib.util.spec_from_file_location('accepted_k0_queue',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def inspect(cid):return json.loads(subprocess.run(['docker','inspect',cid],check=True,capture_output=True,text=True,timeout=30).stdout)[0]
def retained(cid,name,image,chips):
 need(isinstance(cid,str) and re.fullmatch('[a-f0-9]{64}',cid),'invalid container id')
 o=inspect(cid);s=o['State']; h=o['HostConfig'];need(o['Id']==cid and o['Name']=='/'+name and o['Image']==image and h.get('AutoRemove') is False,'retained container binding')
 ds=sorted(int(m.group(1)) for d in h.get('Devices') or [] if (m:=re.fullmatch(r'/dev/davinci(\d+)',d.get('PathOnHost',''))))
 need(ds==chips,'container devices')
 if s['Status'] in ('created','running','paused','restarting'):return False
 need(s['Status']=='exited' and type(s['ExitCode']) is int and s['ExitCode']==0,'retained container failed');return True
def k0(chip):
 need(chip in (4,5,6,7),'K0 chip scope')
 for n,h in KPINS.items():
  if not (K0/n).is_file():return 'pending'
  need(sha(K0/n)==h,'K0 source pin '+n)
 q=mod(K0/'queue.py');need(q.C['image']==KIMAGE,'K0 image config')
 if not (q.OUT/'REVIEW-APPROVED.json').is_file():return 'pending'
 need(q.reviewed(),'K0 review pin')
 mid,_,_=next(j for j in q.JOBS if j[1]==chip);d=q.OUT/mid
 paths=[d/'infer-LAUNCH.json',d/'infer-EXIT.json',d/'infer-COMMAND.json',d/'result/INFERENCE-READY.json']
 if (q.OUT/(mid+'-ERROR.json')).exists():raise ValueError('K0 lane failed')
 if paths[0].exists():
  launch=read(paths[0]);need(launch.get('chip')==chip and isinstance(launch.get('container_id'),str) and re.fullmatch('[a-f0-9]{64}',launch['container_id']) and isinstance(launch.get('command_sha256'),str),'K0 launch binding')
 if paths[2].exists():need(isinstance(read(paths[2]),list),'K0 command malformed')
 if paths[1].exists():
  t=read(paths[1]);need(type(t.get('exit_code')) is int and t['exit_code']==0 and type(t.get('container_exit_code')) is int and t['container_exit_code']==0,'K0 inference failed')
  need(all(p.is_file() for p in paths),'K0 terminal missing predecessor')
 if not all(p.is_file() for p in paths):return 'pending'
 l,t,cmd,artifact=map(read,paths);cid=l['container_id']
 need(l.get('chip')==chip and l.get('command_sha256')==sha(paths[2]) and t.get('container_id')==cid,'K0 inference receipt')
 need(isinstance(cmd,list) and cmd[:3]==['docker','run','-d'] and '--model-id' in cmd and cmd[cmd.index('--model-id')+1]==mid and '--phase' in cmd and cmd[cmd.index('--phase')+1]=='infer' and KIMAGE in cmd and '--device' in cmd and '/dev/davinci'+str(chip) in cmd,'K0 command')
 need(retained(cid,'nga-rc1-matched-k0-'+mid+'-infer',KIMAGE,[chip]),'K0 terminal container not exited')
 need(t.get('artifact_evidence')==q.artifact_evidence(mid,d/'result','infer'),'K0 artifact pins')
 return 'ready' if q.free(chip) else 'pending'
def transaction(x,op,c):
 need(x.get('schema')=='qwen38-group-transaction-v1' and x.get('op')==op and x.get('run')==c['name'] and x.get('chips')==c['chips'] and x.get('allocation')==c['allocation'] and x.get('absent') is False,'27B '+op+' binding')
 after=x['after'];raw=(json.dumps(after,indent=2,sort_keys=True,allow_nan=False)+'\n').encode();need(hashlib.sha256(raw).hexdigest()==x.get('after_sha256'),'27B transaction signature')
 entries=x['entries'];need(isinstance(entries,list) and [e.get('chip') for e in entries]==c['chips'] and all(e.get('run')==c['name'] for e in entries),'27B transaction entries')
 if op=='claim':need(all(e in after['allocation'] for e in entries) and not any(e['chip'] in c['chips'] for e in after['free']) and x.get('claim_sha256') is None,'27B claim state')
 else:need(not any(e['chip'] in c['chips'] for e in after['allocation']) and all(sum(e.get('chip')==i and e.get('previous_run')==c['name'] for e in after['free'])==1 for i in c['chips']),'27B release state')
def qwen(chip):
 need(chip in (0,1,2,3),'27B chip scope')
 cp=QROOT/'CONFIG.json'
 if not cp.is_file():return 'pending'
 need(sha(cp)==QCONFIG,'27B config pin');c=read(cp);need(c.get('chips')==[0,1,2,3] and c.get('schema')=='qwen38-dev-controller-v1','27B config')
 base=QROOT/'package'
 for n,h in c['source_pins'].items():
  if not (base/n).is_file():return 'pending'
  need(sha(base/n)==h,'27B source pin '+n)
 out=Path(c['out']);d=out/'attempts'/c['name']; paths=[d/x for x in ('CONTAINER.json','EXIT.json','TERMINAL.json','CLAIM.json','RELEASE.json','HOST-RELEASE-CHECK.json','COMMAND.json')]
 if (out/'CONTROLLER-ESCALATION.json').exists():raise ValueError('27B controller escalation')
 if paths[0].exists():
  rec=read(paths[0]);need(rec.get('name')==c['name'] and isinstance(rec.get('id'),str) and re.fullmatch('[a-f0-9]{64}',rec['id']),'27B container receipt')
 if paths[3].exists():transaction(read(paths[3]),'claim',c)
 if paths[1].exists():need(type(read(paths[1]).get('exit_code')) is int and read(paths[1])['exit_code']==0,'27B inference failed')
 if paths[2].exists():
  term=read(paths[2]);need(term.get('result')=='success' and term.get('exit_marker_present') is True and type(term.get('exit_code')) is int and term['exit_code']==0,'27B terminal failed or unknown')
  need(all(p.is_file() for p in (paths[0],paths[1],paths[3],paths[6])),'27B terminal missing predecessor')
 if paths[4].exists():need(all(p.is_file() for p in paths),'27B release missing predecessor')
 if not all(p.is_file() for p in paths):return 'pending'
 rec,exit_,term,claim,release,host,command=map(read,paths);cid=rec['id'];name=c['name'];chips=c['chips']
 need(rec.get('name')==name and term.get('container_id')==cid and term.get('name')==name,'27B terminal binding')
 transaction(claim,'claim',c);transaction(release,'release',c)
 need(release.get('claim_sha256')==sha(paths[3]) and release.get('entries')==claim.get('entries') and release.get('container')==name and release.get('container_id')==cid,'27B release binding')
 need(host.get('certain') is True and host.get('chips')==chips and host.get('unmanaged_owners')==[],'27B release host check')
 cmd=command['docker'];need(command.get('chips')==chips and isinstance(cmd,list) and QIMAGE in cmd and all('/dev/davinci'+str(i) in cmd for i in chips) and '--model' in cmd and cmd[cmd.index('--model')+1]=='/run/model' and any('src=/mnt/cephfs/models/Qwen3.8-27B,dst=/run/model,readonly' in x for x in cmd),'27B command binding')
 need(retained(cid,name,QIMAGE,chips),'27B terminal container not exited')
 probe=subprocess.run([c['host_ownership_probe'],'--chips',','.join(map(str,chips))],capture_output=True,text=True,timeout=60)
 h=json.loads(probe.stdout);need(h.get('certain') is True and h.get('chips')==chips and isinstance(h.get('unmanaged_owners'),list),'27B host uncertain')
 need(probe.returncode==0 or bool(h['unmanaged_owners']),'27B probe failed')
 if h['unmanaged_owners']:return 'pending'
 ledger=read(c['allocation']);need(isinstance(ledger.get('free'),list) and isinstance(ledger.get('allocation'),list),'27B ledger malformed')
 vals=[x['chip'] for x in ledger['free']+ledger['allocation']];need(all(type(i) is int and i in range(8) for i in vals) and len(vals)==len(set(vals)),'27B ledger contradictory')
 return 'ready' if all(i in [e['chip'] for e in ledger['free']] for i in chips) else 'pending'
def main():
 p=argparse.ArgumentParser();p.add_argument('dependency',choices=['K0','27B']);p.add_argument('--chip',required=True,type=int);a=p.parse_args()
 try: print(json.dumps({'status':(k0 if a.dependency=='K0' else qwen)(a.chip)}))
 except Exception as e:print(json.dumps({'status':'failed','error':str(e)}))
if __name__=='__main__':main()
