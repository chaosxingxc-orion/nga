#!/usr/bin/env python3
"""175 E26 immutable preparation and guarded launch; does not auto-approve inference."""
import argparse,fcntl,hashlib,json,os,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
TOOLS=['typed_reference_kev.py','verify_typed_reference.py','typed_reference_finish.py','prepare_typed_kev.py','test_typed_reference.py']
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def atomic(p,x):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 with os.fdopen(fd,'w') as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o644);os.replace(tmp,p)
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def prepare(source,prereg,size,mode):
 old=json.loads((ROOT/('typed_kev'+size+'_preflight_20261030/config.json')).read_text());run=ROOT/('typed_kev'+size+'_'+mode+'_20261030');run.mkdir()
 for name in TOOLS:shutil.copy2(source/name,run/name)
 shutil.copy2(prereg,run/'PREREGISTRATION.md');chip={'08':0,'4':4,'9':5}[size]
 old.update(out=str(run),container='nga-typed-kev'+size+'-'+mode,physical_chip=chip,mode=mode,preregistration=str(run/'PREREGISTRATION.md'))
 q=lambda p:shlex.quote(str(p))
 (run/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(run/'typed_reference_kev.py')+' --config '+q(run/'config.json')+' --mode '+mode+' >> '+q(run/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(run/'EXIT')+'\nexit "$rc"\n')
 (run/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(run/'prepare_typed_kev.py')+' --launch-config '+q(run/'config.json')+'\n')
 (run/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(run/'prepare_typed_kev.py')+' --resume-config '+q(run/'config.json')+'\n')
 files=[run/n for n in TOOLS]+[run/'run.sh',run/'LAUNCH_EXACT.sh',run/'RESUME_EXACT.sh',Path(old['preregistration']),Path(old['data']),Path(old['scorer'])]
 for role in ['base','checkpoint','kev_code']:files.extend(p for p in Path(old[role]).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
 old['files']={str(p.resolve()):sha(p) for p in files};atomic(run/'config.json',old)
 print(json.dumps({'prepared':str(run),'frozen':len(old['files']),'mode':mode}))
def launch(config_path):
 c=json.loads(config_path.read_text());run=Path(c['out']);assert c['mode'] in ('probe','inference'),'Invalid mode'
 assert not (run/'LAUNCH_RECEIPT.json').exists(),'Existing launch requires reviewed continuation'
 for p,h in c['files'].items():assert sha(p)==h,p
 chip=c['physical_chip'];size={0:'08',4:'4',5:'9'}[chip];previous=ROOT/(('kev'+size+'_devtools_20261030') if c['mode']=='probe' else ('typed_kev'+size+'_probe_20261030'));old=inspect(('nga-reference-kev'+size+'-devtools') if c['mode']=='probe' else ('nga-typed-kev'+size+'-probe'));lc=json.loads((previous/'LAUNCH_RECEIPT.json').read_text())
 assert old['Id']==lc['container_id'] and old['State']['Status']=='exited' and old['State']['ExitCode']==0
 assert old['Image']==lc['image']==c['image'] and old['Config']['Cmd']==lc['command'] and old['Config']['Entrypoint']==lc['entrypoint']
 assert sha(previous/'config.json')==lc['config_sha256'] and sha(previous/'run.sh')==lc['wrapper_sha256']
 assert {d['PathOnHost'] for d in old['HostConfig']['Devices'] if d['PathOnHost'].startswith('/dev/davinci') and d['PathOnHost'][12:].isdigit()}=={'/dev/davinci'+str(chip)}
 if c['mode']=='probe':
  assert (previous/'DONE').read_text().startswith('rc=0 ') and json.loads((previous/'INDEPENDENT_AUDIT.json').read_text())['status']=='VERIFIED_SCOPED'
 else:
  assert (run/'PARENT_REVIEW.json').exists(),'Formal inference requires recorded implementation review'
  review=json.loads((run/'PARENT_REVIEW.json').read_text());assert review['approved_config_sha256']==sha(config_path),'Review config differs'
  term=json.loads((previous/'probe-COMPLETE.json').read_text());assert term['rc']==0 and (previous/'EXIT').read_text().startswith('rc=0 ')
  for n,h in term['outputs'].items():assert sha(previous/n)==h
  probe=json.loads((previous/'PROBE.json').read_text());assert len(probe['passes'])==2 and probe['max_probability_delta']<=1e-5
  previous_config=json.loads((previous/'config.json').read_text())
  for key in ['base','checkpoint','kev_code','base_id','base_revision','temperature','context','runtime','image']:assert c[key]==previous_config[key],'Probe protocol mismatch: '+key
  for role in ['base','checkpoint','kev_code']:
   prefix=str(Path(c[role]).resolve())+'/'
   assert {p:h for p,h in c['files'].items() if p.startswith(prefix)}=={p:h for p,h in previous_config['files'].items() if p.startswith(prefix)},'Probe model/code hashes differ'
 alloc=ROOT.parent/'CHIP-ALLOCATION.json'
 with Path(str(alloc)+'.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);a=json.loads(alloc.read_text());owners=[v for v in a['allocation'] if v['chip']==chip];assert len(owners)==1 and owners[0]['run']=='reference_inference/'+previous.name
  for cid in subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split():assert not any(d['PathOnHost']=='/dev/davinci'+str(chip) for d in inspect(cid)['HostConfig'].get('Devices') or []),'Live device conflict'
  now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  release_when=('probe terminal and retained container exit reviewed' if c['mode']=='probe' else 'inference terminal, retained container exit and independent audit reviewed')
  owners[0].update(owner='E26 typed '+c['mode'],run='reference_inference/'+run.name,claimed_utc=now,release_when=release_when);a.update(updated_utc=now,updated_by='E26 guarded '+c['mode']+' launch');atomic(alloc,a)
  args=['docker','create','--name',c['container'],'--network','host','--shm-size',str(old['HostConfig']['ShmSize'])]
  for bind in old['HostConfig']['Binds']:args+=['-v',bind]
  for dev in old['HostConfig']['Devices']:args+=['--device',dev['PathOnHost']+':'+dev['PathInContainer']+':'+dev['CgroupPermissions']]
  for env in old['Config']['Env']:args+=['-e',env]
  args += [c['image'],'bash',str(run/'run.sh')]
  cid=subprocess.check_output(args,universal_newlines=True).strip();actual=inspect(cid)
  assert actual['Image']==c['image']
  atomic(run/'LAUNCH_RECEIPT.json',{'container_id':cid,'image':actual['Image'],'command':actual['Config']['Cmd'],'entrypoint':actual['Config']['Entrypoint'],'config_sha256':sha(config_path),'wrapper_sha256':sha(run/'run.sh'),'utc':now})
  atomic(run/'TRANSFER_EVIDENCE.json',{'previous_container':old['Id'],'previous_evidence_sha256':sha(previous/('INDEPENDENT_AUDIT.json' if c['mode']=='probe' else 'probe-COMPLETE.json')),'chip':chip,'utc':now})
  subprocess.check_call(['docker','start',cid]);print(json.dumps({'launched':cid,'run':str(run)}))
def resume(config_path):
 c=json.loads(config_path.read_text());run=Path(c['out']);receipt=json.loads((run/'LAUNCH_RECEIPT.json').read_text());actual=inspect(c['container']);mode=c['mode']
 assert actual['Id']==receipt['container_id'] and actual['Image']==receipt['image']==c['image']
 assert actual['Config']['Cmd']==receipt['command'] and actual['Config']['Entrypoint']==receipt['entrypoint']
 assert {d['PathOnHost'] for d in actual['HostConfig']['Devices'] if d['PathOnHost'].startswith('/dev/davinci') and d['PathOnHost'][12:].isdigit()}=={'/dev/davinci'+str(c['physical_chip'])}
 assert receipt['config_sha256']==sha(config_path) and receipt['wrapper_sha256']==sha(run/'run.sh')
 assert actual['State']['Status']=='exited' and actual['State']['ExitCode']!=0,'Successful or live run cannot resume'
 terminal=run/(mode+'-COMPLETE.json')
 if terminal.exists():assert json.loads(terminal.read_text())['rc']!=0,'Successful terminal cannot resume'
 for path,h in c['files'].items():assert sha(path)==h,path
 alloc=ROOT.parent/'CHIP-ALLOCATION.json'
 with Path(str(alloc)+'.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);a=json.loads(alloc.read_text());chip=c['physical_chip'];assert any(x['chip']==chip and x['run']=='reference_inference/'+run.name for x in a['allocation'])
  for cid in subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split():assert not any(d['PathOnHost']=='/dev/davinci'+str(chip) for d in inspect(cid)['HostConfig'].get('Devices') or [])
  archive=run/('resume-before-'+str(time.time_ns()));archive.mkdir()
  for n in [mode+'-COMPLETE.json','EXIT','STATUS.json']:
   if (run/n).exists():shutil.move(str(run/n),archive/n)
  atomic(archive/'RESUME.json',{'container_id':actual['Id'],'config_sha256':sha(config_path),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
  subprocess.check_call(['docker','start',actual['Id']])
def prepare_finish(config_path,source):
 c=json.loads(config_path.read_text());run=Path(c['out']);out=Path(str(run)+'_finish');out.mkdir()
 for n in ['typed_reference_finish.py','verify_typed_reference.py']:shutil.copy2(source/n,out/n)
 q=lambda p:shlex.quote(str(p))
 (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'typed_reference_finish.py')+' --plan '+q(out/'plan.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
 (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\ndocker run -d --name '+c['container']+'-finish --network none -e TORCH_DEVICE_BACKEND_AUTOLOAD=0 -v /mnt/cephfs:/mnt/cephfs -v /var/run/docker.sock:/var/run/docker.sock --entrypoint bash '+c['image']+' '+q(out/'run.sh')+'\n')
 files=[out/'typed_reference_finish.py',out/'verify_typed_reference.py',out/'run.sh',out/'LAUNCH_EXACT.sh',config_path,run/'LAUNCH_RECEIPT.json']
 atomic(out/'plan.json',{'out':str(out),'config':str(config_path),'auditor':str(out/'verify_typed_reference.py'),'files':{str(p):sha(p) for p in files}})
 print(json.dumps({'finisher_prepared':str(out)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--prereg',type=Path);p.add_argument('--size',choices=['08','4','9']);p.add_argument('--mode',choices=['probe','inference'],default='probe');p.add_argument('--launch-config',type=Path);p.add_argument('--resume-config',type=Path);p.add_argument('--finish-config',type=Path);a=p.parse_args()
 if a.resume_config:resume(a.resume_config)
 elif a.finish_config:prepare_finish(a.finish_config,a.source)
 elif a.launch_config:launch(a.launch_config)
 else:prepare(a.source,a.prereg,a.size,a.mode)
