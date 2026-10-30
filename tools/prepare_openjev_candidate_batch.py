"""Prepare/launch immutable E36 engineering probes, host 175 only."""
import argparse,fcntl,hashlib,json,os,re,shlex,shutil,socket,subprocess,time
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def atomic(p,x):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,indent=2)+'\n');os.replace(q,p)
def require(v,m):
 if not v:raise ValueError(m)
def inspect(n):return json.loads(subprocess.check_output(['docker','inspect',n]))[0]
def maps(x):return sorted(x.get('Binds') or []),sorted((d['PathOnHost'],d['PathInContainer'],d['CgroupPermissions']) for d in x.get('Devices') or [])
def chips(d):return {x['PathOnHost'] for x in d['HostConfig'].get('Devices') or [] if re.fullmatch(r'/dev/davinci[0-9]+',x['PathOnHost'])}
def prepare(source,key):
 require(socket.gethostname()=='k8s-node1','175 only');src=ROOT/('jeval_'+key+'_probe_20261030');c=load(src/'config.json');review=load(src/'PROBE_REVIEW.json');require(review['approved_probe_config_sha256']==sha(src/'config.json'),'Probe config review')
 out=ROOT/('openjev_candidate_batch_'+key+'_20261030');out.mkdir();names=['openjev_candidate_chunks.py','openjev_candidate_batch_probe.py','prepare_openjev_candidate_batch.py','test_openjev_candidate_chunks.py','OPENJEV-CANDIDATE-BATCH-2026-10-30.md']
 for name in names:shutil.copy2(source/name,out/name)
 plan=dict(out=str(out),source_config=str(src/'config.json'),source_config_sha256=sha(src/'config.json'),key=key,chunk_rows=8,image=c['image'],chip=1,container='nga-e36-'+key,files=dict(c['files']))
 spec=load(src/'NPU_SPEC.json');spec['Cmd']=['bash',str(out/'run.sh')];atomic(out/'NPU_SPEC.json',spec)
 q=lambda p:shlex.quote(str(p));(out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'openjev_candidate_batch_probe.py')+' --plan '+q(out/'plan.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
 for name,flag in [('LAUNCH_EXACT.sh','--launch'),('RESUME_EXACT.sh','--resume')]:
  (out/name).write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(out/'prepare_openjev_candidate_batch.py')+' '+flag+' '+q(out/'plan.json')+'\n')
 for p in [out/n for n in names+['NPU_SPEC.json','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh']]+[src/n for n in ['config.json','COMPLETE.json','PROBE.json','PROBE_REVIEW.json']]:plan['files'][str(p)]=sha(p)
 atomic(out/'plan.json',plan);print(json.dumps(dict(plan=str(out/'plan.json'),sha256=sha(out/'plan.json'),files=len(plan['files']))))
def launch(path,resume=False):
 require(socket.gethostname()=='k8s-node1','175 only');p=load(path);out=Path(p['out']);ph=sha(path)
 for f,h in p['files'].items():require(sha(f)==h,'Frozen file changed '+f)
 spec=load(out/'NPU_SPEC.json');require(spec['Image']==p['image'] and chips(spec)=={'/dev/davinci1'},'Image/chip')
 a_path=ROOT.parent/'CHIP-ALLOCATION.json'
 with Path(str(a_path)+'.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);a=load(a_path)
  for cid in subprocess.check_output(['docker','ps','-q'],text=True).split():require('/dev/davinci1' not in chips(inspect(cid)),'Live conflict')
  if resume:
   receipt=load(out/'LAUNCH_RECEIPT.json');d=inspect(receipt['container_id']);require(receipt['plan_sha256']==ph and d['State']['Status']=='exited' and d['State']['ExitCode']!=0,'Not matching failed run');require(any(x['chip']==1 and x['run']=='reference_inference/'+out.name for x in a['allocation']),'Owner differs')
   archive=out/('resume-before-'+str(time.time_ns()));archive.mkdir()
   for n in ['COMPLETE.json','EXIT','STATUS.json','report.json']:
    if(out/n).exists():shutil.move(str(out/n),archive/n)
   cid=d['Id']
  else:
   require(not(out/'LAUNCH_RECEIPT.json').exists(),'Already launched');require(not any(x['chip']==1 for x in a['allocation']) and sum(x['chip']==1 for x in a['free'])==1,'Chip1 not free')
   args=['docker','create','--name',p['container'],'--network',spec['HostConfig']['NetworkMode'],'--shm-size',str(spec['HostConfig']['ShmSize'])]
   for b in spec['HostConfig']['Binds']:args+=['-v',b]
   for d in spec['HostConfig']['Devices']:args+=['--device',d['PathOnHost']+':'+d['PathInContainer']+':'+d['CgroupPermissions']]
   for e in spec['Env']:args+=['-e',e]
   args+=[p['image']]+spec['Cmd'];cid=subprocess.check_output(args,text=True).strip();d=inspect(cid)
  require(d['Image']==p['image'] and d['Config']['Cmd']==spec['Cmd'] and d['Config']['Entrypoint']==spec['Entrypoint'] and maps(d['HostConfig'])==maps(spec['HostConfig']),'Actual Docker differs')
  if not resume:
   atomic(out/'LAUNCH_RECEIPT.json',dict(container_id=cid,plan_sha256=ph,wrapper_sha256=sha(out/'run.sh'),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
   a['free']=[x for x in a['free'] if x['chip']!=1];a['allocation'].append(dict(chip=1,owner='E36 candidate batch probe',run='reference_inference/'+out.name,release_when='actual exit plus terminal outputs checked'));atomic(a_path,a)
  subprocess.check_call(['docker','start',cid]);print(cid)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--key',choices=['openjev2','openjev9']);p.add_argument('--launch',type=Path);p.add_argument('--resume',type=Path);a=p.parse_args()
 if a.launch:launch(a.launch)
 elif a.resume:launch(a.resume,True)
 else:prepare(a.source,a.key)
