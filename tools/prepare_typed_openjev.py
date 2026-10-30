#!/usr/bin/env python3
"""E29 immutable preparation and locked, identity-bound launch/resume on 175."""
import argparse,fcntl,hashlib,json,os,re,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
SCRIPTS=['typed_openjev_preflight.py','typed_openjev_inference.py','verify_typed_openjev.py','typed_openjev_finish.py','prepare_typed_openjev.py']
def require(v,m):
    if not v:raise ValueError(m)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def atomic(p,v):
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
    with os.fdopen(fd,'w') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o644);os.replace(tmp,p)
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def devices(info):return {d['PathOnHost'] for d in info['HostConfig'].get('Devices') or [] if re.fullmatch(r'/dev/davinci\d+',d['PathOnHost'])}
def live_conflict(chip):
    for cid in subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split():require('/dev/davinci'+str(chip) not in devices(inspect(cid)),'Live device conflict')
def verify_files(c):
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
def prepare(source,prereg,mode,size,chip):
    c=load(ROOT/('typed_openjev'+size+'_preflight_20261030/config.json'));out=ROOT/('typed_openjev'+size+'_'+mode+'_20261030');out.mkdir()
    for n in SCRIPTS+['test_typed_openjev_preflight.py','test_typed_openjev_execution.py','test_typed_openjev_chain.py']:shutil.copy2(source/n,out/n)
    shutil.copy2(prereg,out/'PREREGISTRATION.md');q=lambda p:shlex.quote(str(p))
    c.update(out=str(out),mode=mode,container='nga-typed-openjev'+size+'-'+mode,physical_chip=chip,size=size,previous_run=('typed_kev'+{0:'08',4:'4',5:'9'}[chip]+'_inference_20261030' if mode=='probe' else 'typed_openjev'+size+'_probe_20261030'),preregistration=str(out/'PREREGISTRATION.md'),scorer='/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py',runtime={'torch':'2.10.0+cpu','torch_npu':'2.10.0.post7','transformers':'5.14.1','peft':'0.21.2'})
    (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'typed_openjev_inference.py')+' --config '+q(out/'config.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
    for n,flag in [('LAUNCH_EXACT.sh','--launch-config'),('RESUME_EXACT.sh','--resume-config')]:
        (out/n).write_text('#!/usr/bin/env bash\nset -e\npython3 -I '+q(out/'prepare_typed_openjev.py')+' '+flag+' '+q(out/'config.json')+'\n')
    paths=[out/n for n in SCRIPTS+['test_typed_openjev_preflight.py','test_typed_openjev_execution.py','test_typed_openjev_chain.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh','PREREGISTRATION.md']]+[Path(c['data']),Path(c['scorer'])]
    for role in ['base','checkpoint','code']:paths.extend(p for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    c['files']={str(p.resolve()):sha(p) for p in paths};atomic(out/'config.json',c);print(json.dumps(dict(prepared=str(out),config_sha256=sha(out/'config.json'),frozen=len(c['files']))))
def verify_probe(c):
    p=ROOT/c['previous_run'];pc=load(p/'config.json');lc=load(p/'LAUNCH_RECEIPT.json');info=inspect(pc['container']);term=load(p/'probe-COMPLETE.json')
    require(info['Id']==lc['container_id'] and info['Image']==lc['image']==c['image'] and info['Config']['Cmd']==lc['command'] and info['Config'].get('Entrypoint')==lc['entrypoint'],'Probe container binding differs')
    require(info['State']['Status']=='exited' and info['State']['ExitCode']==0 and devices(info)=={'/dev/davinci'+str(c['physical_chip'])},'Probe not completed on expected chip')
    require(lc['config_sha256']==sha(p/'config.json')==term['config_sha256'] and lc['wrapper_sha256']==sha(p/'run.sh'),'Probe configuration binding differs')
    require(term['rc']==0 and (p/'EXIT').read_text().startswith('rc=0 '),'Probe terminal failure')
    for n,h in term['outputs'].items():require(sha(p/n)==h,'Probe output changed')
    verify_files(pc)
    for k in ['base','checkpoint','code','base_id','base_revision','temperature','max_length','runtime','image']:require(c[k]==pc[k],'Probe protocol differs '+k)
    for role in ['base','checkpoint','code']:
        prefix=str(Path(c[role]).resolve())+'/'
        require({p:h for p,h in c['files'].items() if p.startswith(prefix)}=={p:h for p,h in pc['files'].items() if p.startswith(prefix)},'Probe source hashes differ')
    pr=load(p/'PROBE.json');require(len(pr['passes'])==2 and pr['max_probability_delta']<=1e-5 and all(x['seconds']>0 for x in pr['passes']),'Probe admission differs')
    return p,info

def launch(config):
    c=load(config);out=Path(c['out']);verify_files(c);require(not(out/'LAUNCH_RECEIPT.json').exists(),'Existing launch preserved')
    require(c['mode'] in ('probe','inference') and c['physical_chip'] in (0,4,5),'Unsupported launch')
    require(load(out/'PARENT_REVIEW.json')['approved_config_sha256']==sha(config),'Implementation review differs')
    previous=ROOT/c['previous_run']
    if c['mode']=='inference':previous,template=verify_probe(c)
    else:
        original=previous;oc=load(original/'config.json');ol=load(original/'LAUNCH_RECEIPT.json');template=inspect(oc['container']);finish=Path(str(original)+'_finish');ft=load(finish/'FINISH_COMPLETE.json');terminal=load(original/'inference-COMPLETE.json')
        require(template['Id']==ol['container_id'] and template['Image']==ol['image']==c['image'] and template['Config']['Cmd']==ol['command'] and template['Config'].get('Entrypoint')==ol['entrypoint'],'Original template identity differs')
        require(template['State']['Status']=='exited' and template['State']['ExitCode']==0 and ol['config_sha256']==sha(original/'config.json') and ol['wrapper_sha256']==sha(original/'run.sh'),'Original template completion differs')
        require(terminal['rc']==0 and terminal['config_sha256']==ol['config_sha256'] and (original/'EXIT').read_text().startswith('rc=0 '),'Original inference terminal differs')
        for name,h in terminal['outputs'].items():require(sha(original/name)==h,'Original inference output changed')
        require(ft['rc']==0 and ft['status']=='COMPLETED_SCOPED' and ft['review_flag_count']==0 and ft['config_sha256']==ol['config_sha256'],'Original accepted audit differs')
        for name,h in ft['outputs'].items():require(sha(finish/name)==h,'Original audit output changed')
        fi=inspect(oc['container']+'-finish');require(fi['State']['Status']=='exited' and fi['State']['ExitCode']==0 and (finish/'EXIT').read_text().startswith('rc=0 '),'Original audit wrapper/container failed')
    alloc=ROOT.parent/'CHIP-ALLOCATION.json'
    with Path(str(alloc)+'.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);a=load(alloc);chip=c['physical_chip'];live_conflict(chip)
        owners=[x for x in a['allocation'] if x['chip']==chip];free=[x for x in a['free'] if x['chip']==chip]
        require((len(owners)==1 and owners[0]['run']=='reference_inference/'+previous.name) or (not owners and len(free)==1),'Previous allocation differs')
        args=['docker','create','--name',c['container'],'--network','host','--shm-size',str(template['HostConfig']['ShmSize'])]
        for bind in template['HostConfig']['Binds']:args+=['-v',bind]
        for d in template['HostConfig']['Devices']:args+=['--device',d['PathOnHost']+':'+d['PathInContainer']+':'+d['CgroupPermissions']]
        require(devices(template)=={'/dev/davinci'+str(c['physical_chip'])} and template['Image']==c['image'],'Template device/image differs')
        for env in template['Config']['Env']:args+=['-e',env]
        args +=[c['image'],'bash',str(out/'run.sh')]
        cid=subprocess.check_output(args,universal_newlines=True).strip();actual=inspect(cid);require(actual['Image']==c['image'] and devices(actual)=={'/dev/davinci'+str(c['physical_chip'])},'Created container binding differs')
        now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());atomic(out/'LAUNCH_RECEIPT.json',dict(container_id=cid,image=actual['Image'],command=actual['Config']['Cmd'],entrypoint=actual['Config'].get('Entrypoint'),config_sha256=sha(config),wrapper_sha256=sha(out/'run.sh'),utc=now))
        a['allocation']=[x for x in a['allocation'] if x['chip']!=chip]+[dict(chip=chip,owner='E29 typed Open-Jev '+c['mode'],run='reference_inference/'+out.name,claimed_utc=now,release_when='terminal, wrapper, audit if inference, and retained container exit reviewed')];a['free']=[x for x in a['free'] if x['chip']!=chip];a.update(updated_utc=now,updated_by='E29 guarded '+c['mode']+' launch');atomic(alloc,a)
        subprocess.check_call(['docker','start',cid]);print(json.dumps(dict(launched=cid,run=str(out))))
def resume(config):
    c=load(config);out=Path(c['out']);lc=load(out/'LAUNCH_RECEIPT.json');info=inspect(c['container']);verify_files(c)
    require(info['Id']==lc['container_id'] and info['Image']==lc['image']==c['image'] and devices(info)=={'/dev/davinci'+str(c['physical_chip'])},'Resume container differs')
    require(info['Config']['Cmd']==lc['command'] and info['Config'].get('Entrypoint')==lc['entrypoint'] and lc['config_sha256']==sha(config) and lc['wrapper_sha256']==sha(out/'run.sh'),'Resume binding differs')
    require(info['State']['Status']=='created' or (info['State']['Status']=='exited' and info['State']['ExitCode']!=0),'Successful or live run cannot resume')
    terminal=out/(c['mode']+'-COMPLETE.json')
    if terminal.exists():require(load(terminal)['rc']!=0,'Successful terminal preserved')
    alloc=ROOT.parent/'CHIP-ALLOCATION.json'
    with Path(str(alloc)+'.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);a=load(alloc);require(any(x['chip']==c['physical_chip'] and x['run']=='reference_inference/'+out.name for x in a['allocation']),'Resume allocation differs');live_conflict(c['physical_chip'])
        archive=out/('resume-before-'+str(time.time_ns()));archive.mkdir()
        for n in [c['mode']+'-COMPLETE.json','STATUS.json','EXIT','PROBE.json','PREFLIGHT.json','ENVIRONMENT.json','report.json']:
            if (out/n).exists():shutil.move(str(out/n),str(archive/n))
        atomic(archive/'RESUME.json',dict(container_id=info['Id'],config_sha256=sha(config)));subprocess.check_call(['docker','start',info['Id']])
def finish(config,source):
    c=load(config);out=Path(c['out']+'_finish');out.mkdir();q=lambda p:shlex.quote(str(p))
    for n in ['typed_openjev_finish.py','verify_typed_openjev.py']:shutil.copy2(source/n,out/n)
    (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'typed_openjev_finish.py')+' --plan '+q(out/'plan.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
    (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\ndocker run -d --name '+c['container']+'-finish --network none -e TORCH_DEVICE_BACKEND_AUTOLOAD=0 -v /mnt/cephfs:/mnt/cephfs -v /var/run/docker.sock:/var/run/docker.sock --entrypoint bash '+c['image']+' '+q(out/'run.sh')+'\n')
    paths=[out/n for n in ['typed_openjev_finish.py','verify_typed_openjev.py','run.sh','LAUNCH_EXACT.sh']]+[config,Path(c['out'])/'LAUNCH_RECEIPT.json']
    atomic(out/'plan.json',dict(out=str(out),config=str(config),auditor=str(out/'verify_typed_openjev.py'),files={str(p):sha(p) for p in paths}));print(json.dumps(dict(finisher=str(out))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--prereg',type=Path);p.add_argument('--mode',choices=['probe','inference']);p.add_argument('--size',choices=['2','9']);p.add_argument('--chip',type=int,choices=[0,4,5]);p.add_argument('--launch-config',type=Path);p.add_argument('--resume-config',type=Path);p.add_argument('--finish-config',type=Path);a=p.parse_args()
    if a.launch_config:launch(a.launch_config)
    elif a.resume_config:resume(a.resume_config)
    elif a.finish_config:finish(a.finish_config,a.source)
    else:prepare(a.source,a.prereg,a.mode,a.size,a.chip)
