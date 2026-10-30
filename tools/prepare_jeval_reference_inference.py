#!/usr/bin/env python3
"""E33 immutable preparation and explicit, resource-locked launches."""
import argparse,fcntl,hashlib,json,os,re,shlex,shutil,socket,subprocess,tempfile,time
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
FILES=['jeval_reference_inference.py','jeval_reference_preflight.py','prepare_jeval_reference_inference.py','verify_jeval_reference_inference.py','jeval_reference_finish.py','test_jeval_reference_inference.py','test_jeval_reference_chain.py','test_jeval_resource_binding.py']
def require(x,m):
 if not x:raise ValueError(m)
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
def load(p):return json.loads(Path(p).read_text())
def atomic(p,x):
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 with os.fdopen(fd,'w') as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o644);os.replace(tmp,p)
def inspect(n):return json.loads(subprocess.check_output(['docker','inspect',n]))[0]
def device_chips(info):return {d['PathOnHost'] for d in info['HostConfig'].get('Devices') or [] if re.fullmatch(r'/dev/davinci[0-9]+',d['PathOnHost'])}
def verify_files(c):
 for p,h in c['files'].items():require(sha(p)==h,'Frozen file changed '+p)
def prepare(source,prereg,key,chip,mode,revision='',probe_config=None):
 require(not revision or re.fullmatch(r'v[0-9]+',revision),'Invalid revision')
 run_suffix='_'+revision if revision else '';container_suffix='-'+revision if revision else ''
 require(socket.gethostname()=='k8s-node1','175 only');suffix='_v2' if key=='nimble' else '';ep=ROOT/('jeval_'+key+'_preflight_20261030'+suffix);e=load(ep/'config.json');et=load(ep/'COMPLETE.json');el=load(ep/'LAUNCH_RECEIPT.json');ed=inspect(e['container'])
 require(et['rc']==0 and et['stage']=='completed' and et['progress']==et['total']==11257 and et['config_sha256']==el['config_sha256']==sha(ep/'config.json'),'Eligibility incomplete')
 require(ed['Id']==el['container_id'] and ed['State']['Status']=='exited' and ed['State']['ExitCode']==0,'Eligibility actual container')
 require(sha(ep/'report.json')==et['outputs']['report.json'],'Eligibility report changed');verify_files(e)
 out=ROOT/('jeval_'+key+'_'+mode+'_20261030'+run_suffix);out.mkdir();finish=Path(str(out)+'_finish');finish.mkdir();c={k:v for k,v in e.items() if k not in ['out','files','container','mode','preregistration']}
 c.update(out=str(out),container='nga-jeval-'+key+'-'+mode+container_suffix,mode=mode,key=key,physical_chip=chip,eligibility_config=str(ep/'config.json'),eligibility_report=str(ep/'report.json'),preregistration=str(out/'PREREGISTRATION.md'))
 c['runtime']={'torch':'2.10.0+cpu','torch_npu':'2.10.0.post7','transformers':'5.14.1','peft':'0.21.2'}
 if mode=='inference':
  probe=Path(probe_config).parent if probe_config else ROOT/('jeval_'+key+'_probe_20261030');pc=load(probe/'config.json');pt=load(probe/'COMPLETE.json');pr=load(probe/'PROBE_REVIEW.json');pd=inspect(pc['container'])
  pl=load(probe/'LAUNCH_RECEIPT.json');binding(pd,pc,load(probe/'NPU_SPEC.json'),pl)
  require(pt['rc']==0 and pt['stage']=='probe_completed' and pt['progress']==pt['total']==4 and pd['State']['Status']=='exited' and pd['State']['ExitCode']==0,'Probe not completed')
  require((probe/'EXIT').read_text().startswith('rc=0 utc=') and sha(probe/'run.sh')==pl['wrapper_sha256'] and sha(probe/'config.json')==pl['config_sha256'],'Probe launch/exit binding')
  require(pt['config_sha256']==pr['approved_probe_config_sha256']==sha(probe/'config.json') and sha(probe/'PROBE.json')==pr['approved_probe_sha256']==pt['outputs']['PROBE.json'],'Probe approval differs');verify_files(pc)
  c.update(probe_config=str(probe/'config.json'),probe_report=str(probe/'PROBE.json'),probe_review=str(probe/'PROBE_REVIEW.json'))
 for n in FILES:shutil.copy2(source/n,out/n)
 shutil.copy2(prereg,out/'PREREGISTRATION.md');q=lambda p:shlex.quote(str(p));cp=out/'config.json'
 (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'jeval_reference_inference.py')+' --config '+q(cp)+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
 for n,flag in [('LAUNCH_EXACT.sh','--launch'),('RESUME_EXACT.sh','--resume')]:
  (out/n).write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(out/'prepare_jeval_reference_inference.py')+' '+flag+' '+q(cp)+'\n')
 old=ROOT/('typed_'+key+'_inference_20261030');oc=load(old/'config.json');d=inspect(oc['container']);require(d['Image']==c['image'],'Template image')
 spec={'Image':c['image'],'Cmd':['bash',str(out/'run.sh')],'Entrypoint':d['Config'].get('Entrypoint'),'Env':d['Config'].get('Env'), 'HostConfig':{k:d['HostConfig'][k] for k in ['Binds','Devices','ShmSize','NetworkMode']}}
 spec['HostConfig']['Devices']=[dict(x,PathOnHost='/dev/davinci'+str(chip),PathInContainer='/dev/davinci'+str(chip)) if re.fullmatch(r'/dev/davinci[0-9]+',x['PathOnHost']) else x for x in spec['HostConfig']['Devices']]
 atomic(out/'NPU_SPEC.json',spec)
 (finish/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\npython3 -P '+q(out/'jeval_reference_finish.py')+' --config '+q(cp)+' >> '+q(finish/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(finish/'EXIT')+'\nexit "$rc"\n')
 (finish/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(out/'prepare_jeval_reference_inference.py')+' --finish '+q(cp)+'\n')
 paths=[out/n for n in FILES+['PREREGISTRATION.md','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh','NPU_SPEC.json']]+[finish/'run.sh',finish/'LAUNCH_EXACT.sh']+[Path(c[k]) for k in ['data','eligibility_config','eligibility_report']]
 if mode=='inference':paths.extend(Path(c[k]) for k in ['probe_config','probe_report','probe_review'])
 for role in c['dependency_roles']:paths.extend(p for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
 c['files']={str(p.resolve()):sha(p) for p in paths}
 if mode=='inference':
  for n in FILES:require(sha(out/n)==pc['files'][str(probe/n)],'Probe executable differs '+n)
  for role in c['dependency_roles']:
   require(c[role]==pc[role],'Probe native source path changed');prefix=str(Path(c[role]).resolve())+'/'
   require({p:h for p,h in c['files'].items() if p.startswith(prefix)}=={p:h for p,h in pc['files'].items() if p.startswith(prefix)},'Probe native source hashes changed')
 atomic(cp,c);print(json.dumps(dict(config=str(cp),config_sha256=sha(cp),frozen=len(c['files']),status='PREPARED_NOT_LAUNCHED')))
def binding(info,c,spec,receipt):
 require(info['Id']==receipt['container_id'] and info['Image']==receipt['image']==c['image'],'Container identity')
 require(info['Config']['Cmd']==receipt['command']==spec['Cmd'] and info['Config'].get('Entrypoint')==receipt['entrypoint']==spec['Entrypoint'],'Container command')
 require(resource_mapping(info['HostConfig'])==resource_mapping(spec['HostConfig']),'Resource mapping differs')
 require(device_chips(info)=={'/dev/davinci'+str(c['physical_chip'])},'Physical chip differs')
def acquire(c):
 p=ROOT.parent/'CHIP-ALLOCATION.json';lock=Path(str(p)+'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX);a=load(p)
 for cid in subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split():require('/dev/davinci'+str(c['physical_chip']) not in device_chips(inspect(cid)),'Live chip conflict')
 return p,lock,a
def launch(cp):
 require(socket.gethostname()=='k8s-node1','175 only');c=load(cp);out=Path(c['out']);verify_files(c);spec=load(out/'NPU_SPEC.json');require(load(out/'PARENT_REVIEW.json')['approved_config_sha256']==sha(cp),'Parent review');require(not(out/'LAUNCH_RECEIPT.json').exists(),'Existing launch')
 require(spec['Image']==c['image'] and spec['Cmd']==['bash',str(out/'run.sh')] and device_chips(spec)=={'/dev/davinci'+str(c['physical_chip'])},'Approved native specification')
 p,lock,a=acquire(c)
 with lock:
  chip=c['physical_chip'];require(not any(x['chip']==chip for x in a['allocation']) and sum(x['chip']==chip for x in a['free'])==1,'Chip not explicitly free')
  args=['docker','create','--name',c['container'],'--network',spec['HostConfig']['NetworkMode'],'--shm-size',str(spec['HostConfig']['ShmSize'])]
  for b in spec['HostConfig']['Binds']:args+=['-v',b]
  for d in spec['HostConfig']['Devices']:args+=['--device',d['PathOnHost']+':'+d['PathInContainer']+':'+d['CgroupPermissions']]
  for e in spec['Env']:args+=['-e',e]
  args+=[c['image']]+spec['Cmd'];cid=subprocess.check_output(args,universal_newlines=True).strip();info=inspect(cid);r=dict(container_id=cid,image=info['Image'],command=info['Config']['Cmd'],entrypoint=info['Config'].get('Entrypoint'),config_sha256=sha(cp),wrapper_sha256=sha(out/'run.sh'));binding(info,c,spec,r);atomic(out/'LAUNCH_RECEIPT.json',r)
  a['free']=[x for x in a['free'] if x['chip']!=chip];a['allocation'].append(dict(chip=chip,owner='E33 JEVal '+c['key'],run='reference_inference/'+out.name,claimed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),release_when='inference and independent audit accepted'));atomic(p,a);subprocess.check_call(['docker','start',cid]);print(cid)
def resume(cp):
 c=load(cp);out=Path(c['out']);verify_files(c);r=load(out/'LAUNCH_RECEIPT.json');d=inspect(c['container']);binding(d,c,load(out/'NPU_SPEC.json'),r);require(sha(cp)==r['config_sha256'] and sha(out/'run.sh')==r['wrapper_sha256'],'Resume immutable binding');require(d['State']['Status']=='exited' and d['State']['ExitCode']!=0,'Not failed')
 term=out/'COMPLETE.json'
 if term.exists():require(load(term)['rc']!=0,'Successful terminal preserved')
 p,lock,a=acquire(c)
 with lock:
  require(any(x['chip']==c['physical_chip'] and x['run']=='reference_inference/'+out.name for x in a['allocation']),'Allocation owner')
  archive=out/('resume-before-'+str(time.time_ns()));archive.mkdir()
  for n in ['COMPLETE.json','STATUS.json','EXIT','report.json','PROBE.json']:
   if(out/n).exists():shutil.move(str(out/n),str(archive/n))
  subprocess.check_call(['docker','start',d['Id']])
def finish(cp):
 c=load(cp);require(c['mode']=='inference','No finisher for probe');verify_files(c);out=Path(c['out']);finish=Path(str(out)+'_finish');require((out/'LAUNCH_RECEIPT.json').exists(),'Inference not launched')
 args=['docker','create','--name',c['container']+'-finish','--network','none','-e','TORCH_DEVICE_BACKEND_AUTOLOAD=0','-v','/mnt/cephfs:/mnt/cephfs','-v','/var/run/docker.sock:/var/run/docker.sock','--entrypoint','bash',c['image'],str(finish/'run.sh')];cid=subprocess.check_output(args,universal_newlines=True).strip();info=inspect(cid);atomic(finish/'LAUNCH_RECEIPT.json',dict(container_id=cid,image=info['Image'],command=info['Config']['Cmd'],entrypoint=info['Config']['Entrypoint'],config_sha256=sha(cp),wrapper_sha256=sha(finish/'run.sh')));subprocess.check_call(['docker','start',cid]);print(cid)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--preregistration',type=Path);p.add_argument('--key',choices=['kev08','kev4','kev9','openjev2','openjev9','nimble']);p.add_argument('--chip',type=int);p.add_argument('--mode',choices=['probe','inference'],default='probe');p.add_argument('--revision',default='');p.add_argument('--probe-config',type=Path);p.add_argument('--launch',type=Path);p.add_argument('--resume',type=Path);p.add_argument('--finish',type=Path);a=p.parse_args()
 if a.launch:launch(a.launch)
 elif a.resume:resume(a.resume)
 elif a.finish:finish(a.finish)
 else:prepare(a.source,a.preregistration,a.key,a.chip,a.mode,a.revision,a.probe_config)
