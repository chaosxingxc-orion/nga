#!/usr/bin/env python3
"""E32 immutable preparation; explicit reviewed launch only, never automatic chip adoption."""
import argparse,fcntl,hashlib,json,os,re,shlex,shutil,socket,subprocess,tempfile,time
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
FILES=['prepare_openjev_ood.py','openjev_ood_protocol.py','openjev_ood_eval.py','verify_openjev_ood.py','openjev_reference_eval.py','verify_reference_openjev.py','openjev_reference_finish.py','test_openjev_ood.py']
def require(v,m):
    if not v:raise ValueError(m)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,x):
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
    with os.fdopen(fd,'w') as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o644);os.replace(tmp,p)
def inspect(n):return json.loads(subprocess.check_output(['docker','inspect',n]))[0]
def shell(p,s):p.write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n'+s);p.chmod(0o755)
def verify(c):
    for p,h in c['files'].items():require(sha(p)==h,'Frozen dependency changed '+p)
def receipt(out,name,c,cp,wrapper):
    info=inspect(name);write(out/'LAUNCH_RECEIPT.json',dict(container_id=info['Id'],image=info['Image'],command=info['Config']['Cmd'],entrypoint=info['Config'].get('Entrypoint'),config_sha256=sha(cp),wrapper_sha256=sha(wrapper),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
def prepare(source,prereg,size,chip):
    require(socket.gethostname()=='k8s-node1','Prepare only on 175')
    parent=ROOT/('openjev2_test_20261030_v3' if size=='2' else 'openjev9_test_20261030');old=load(parent/'config.json');out=ROOT/('openjev'+size+'_original_ood_20261030');out.mkdir();pf=out/'preflight-container';pf.mkdir();finish=Path(str(out)+'_finish');finish.mkdir();q=lambda p:shlex.quote(str(p))
    for name in FILES:shutil.copy2(source/name,out/name)
    shutil.copy2(prereg,out/'PREREGISTRATION.md');shutil.copy2(parent/'launch.sh',out/'launch.sh')
    c=dict(old);restore=ROOT/'openjev_original_restore_20261030'
    c.update(out=str(out),container='nga-openjev'+size+'-original-ood',physical_chip=chip,data=str(restore/'release-v2/ood.jsonl'),restoration_report=str(restore/'report.json'),parent_config=str(parent/'config.json'),parent_config_sha256=sha(parent/'config.json'),expected_rows=15920,hard_count=15446,expected_split='ood',scope='Original full OOD15920 (15446 hard,474 soft); no projection or training',preregistration=str(out/'PREREGISTRATION.md'))
    cp=out/'config.json';builder=out/'prepare_openjev_ood.py';driver=out/'openjev_ood_eval.py'
    for mode in ['preflight','evaluate']:
        shell(out/(mode+'.sh'),'python3 -P '+q(driver)+' --config '+q(cp)+' --mode '+mode+' >> '+q(out/(mode+'.log'))+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/(mode+'-EXIT'))+'\nexit "$rc"\n')
    for name,stage in [('PREFLIGHT_EXACT.sh','preflight'),('LAUNCH_EXACT.sh','evaluate')]:shell(out/name,'set -e\npython3 -I '+q(builder)+' --launch '+q(cp)+' --stage '+stage+'\n')
    shell(out/'RESUME_EXACT.sh','set -e\npython3 -I '+q(out/'openjev_reference_eval.py')+' --config '+q(cp)+' --mode resume\n')
    shell(out/'PREFLIGHT_RESUME_EXACT.sh','set -e\npython3 -I '+q(builder)+' --resume-preflight '+q(cp)+'\n')
    template=inspect(old['container']);require(template['Image']==c['image'],'Template image differs')
    template_spec={k:template['HostConfig'][k] for k in ['Binds','Devices','ShmSize']};template_spec['Devices']=[{**d,'PathOnHost':'/dev/davinci'+str(chip),'PathInContainer':'/dev/davinci'+str(chip)} if re.fullmatch('/dev/davinci[0-9]+',d['PathOnHost']) else d for d in template_spec['Devices']]
    env=[e for e in template['Config']['Env'] if e.split('=',1)[0] in ['ASCEND_RT_VISIBLE_DEVICES','LD_LIBRARY_PATH','PYTHONPATH','PATH']]
    write(out/'NPU_SPEC.json',{'image':c['image'],'HostConfig':template_spec,'Env':env,'Entrypoint':template['Config']['Entrypoint']})
    shell(finish/'run.sh','python3 -P '+q(out/'openjev_reference_finish.py')+' --plan '+q(finish/'plan.json')+' >> '+q(finish/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(finish/'EXIT')+'\nexit "$rc"\n')
    shell(finish/'LAUNCH_EXACT.sh','set -e\npython3 -I '+q(builder)+' --launch '+q(cp)+' --stage finish\n')
    paths=[out/n for n in FILES+['launch.sh','preflight.sh','evaluate.sh','PREFLIGHT_EXACT.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh','PREFLIGHT_RESUME_EXACT.sh','PREREGISTRATION.md','NPU_SPEC.json']]+[finish/'run.sh',finish/'LAUNCH_EXACT.sh']+[Path(c[k]) for k in ['data','export_manifest','restoration_report','parent_config']]
    c['execution_files']=[str(p) for p in paths if p.suffix in ['.py','.sh']]
    for role in ['code','base','checkpoint']:paths.extend(p for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
    c['files']={str(p.resolve()):sha(p) for p in paths};write(cp,c)
    write(finish/'plan.json',dict(out=str(finish),config=str(cp),auditor=str(out/'verify_openjev_ood.py'),files={**c['files'],str(cp):sha(cp)}))
    print(json.dumps(dict(config=str(cp),sha256=sha(cp),frozen=len(c['files']),status='PREPARED_NOT_LAUNCHED',chip_not_claimed=chip)))
def check_preflight(c,cp):
    out=Path(c['out']);pf=out/'preflight-container';r=load(pf/'LAUNCH_RECEIPT.json');d=inspect(c['container']+'-preflight');t=load(out/'preflight-COMPLETE.json')
    require(d['Id']==r['container_id'] and d['Image']==c['image']==r['image'] and not d['HostConfig']['Devices'],'Preflight identity')
    require(d['Config']['Cmd']==r['command']==[str(out/'preflight.sh')] and d['Config']['Entrypoint']==r['entrypoint']==['bash'],'Preflight command')
    require(d['HostConfig']['NanoCpus']==2000000000 and d['HostConfig']['NetworkMode']=='none','Preflight CPU isolation');require(d['State']['Status']=='exited' and d['State']['ExitCode']==0 and t['rc']==0 and t['stage']=='ready','Preflight not successful')
    require(t['progress']==t['total']==15920 and t['config_sha256']==sha(cp)==r['config_sha256'],'Preflight coverage/binding')
    require(r['wrapper_sha256']==sha(out/'preflight.sh') and (out/'preflight-EXIT').read_text().startswith('rc=0 utc='),'Preflight wrapper')
    require(t['outputs']['PREFLIGHT.json']==sha(out/'PREFLIGHT.json'),'Preflight report changed')
    report=load(out/'PREFLIGHT.json');require(report['rows']==15920 and report['overlength_rows']==0 and report['max_length']==4096,'Preflight ineligible')
def launch(cp,stage):
    require(socket.gethostname()=='k8s-node1','Launch only on175');c=load(cp);out=Path(c['out']);verify(c)
    require(load(out/'PARENT_REVIEW.json')['approved_config_sha256']==sha(cp),'Parent review differs')
    if stage=='preflight':
        require(not(out/'preflight-container/LAUNCH_RECEIPT.json').exists(),'Existing preflight')
        name=c['container']+'-preflight';args=['docker','create','--name',name,'--network','none','--cpus','2','-e','TORCH_DEVICE_BACKEND_AUTOLOAD=0','-e','TOKENIZERS_PARALLELISM=false','-v','/mnt/cephfs:/mnt/cephfs','--entrypoint','bash',c['image'],str(out/'preflight.sh')]
        subprocess.check_output(args);receipt(out/'preflight-container',name,c,cp,out/'preflight.sh');subprocess.check_call(['docker','start',name]);return
    if stage=='finish':
        finish=Path(str(out)+'_finish');require((out/'LAUNCH_RECEIPT.json').exists(),'Inference not launched');plan=load(finish/'plan.json');require(plan==dict(out=str(finish),config=str(cp),auditor=str(out/'verify_openjev_ood.py'),files={**c['files'],str(cp):sha(cp)}),'Finish plan differs')
        name=c['container']+'-finish';subprocess.check_output(['docker','create','--name',name,'--network','none','-e','TORCH_DEVICE_BACKEND_AUTOLOAD=0','-v','/mnt/cephfs:/mnt/cephfs','-v','/var/run/docker.sock:/var/run/docker.sock','--entrypoint','bash',c['image'],str(finish/'run.sh')]);receipt(finish,name,c,cp,finish/'run.sh');subprocess.check_call(['docker','start',name]);return
    check_preflight(c,cp);require(not(out/'LAUNCH_RECEIPT.json').exists(),'Existing inference launch');spec=load(out/'NPU_SPEC.json');allocation=ROOT.parent/'CHIP-ALLOCATION.json'
    with Path(str(allocation)+'.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);a=load(allocation);chip=c['physical_chip'];require(not any(x['chip']==chip for x in a['allocation']) and sum(x['chip']==chip for x in a['free'])==1,'Chip must be explicitly released first')
        for cid in subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split():require('/dev/davinci'+str(chip) not in [d['PathOnHost'] for d in inspect(cid)['HostConfig'].get('Devices') or []],'Live chip conflict')
        args=['docker','create','--name',c['container'],'--network','host','--shm-size',str(spec['HostConfig']['ShmSize'])]
        for bind in spec['HostConfig']['Binds']:args+=['-v',bind]
        for d in spec['HostConfig']['Devices']:args+=['--device',d['PathOnHost']+':'+d['PathInContainer']+':'+d['CgroupPermissions']]
        for e in spec['Env']:args+=['-e',e]
        args +=[c['image'],'bash',str(out/'evaluate.sh')];subprocess.check_output(args);actual=inspect(c['container']);require(actual['Image']==c['image'] and actual['Config']['Entrypoint']==spec['Entrypoint'] and actual['Config']['Cmd']==['bash',str(out/'evaluate.sh')],'Created container differs');require(actual['HostConfig']['Devices']==spec['HostConfig']['Devices'] and sorted(actual['HostConfig']['Binds'])==sorted(spec['HostConfig']['Binds']),'Created resource mapping differs');receipt(out,c['container'],c,cp,out/'evaluate.sh')
        a['free']=[x for x in a['free'] if x['chip']!=chip];a['allocation'].append(dict(chip=chip,owner='E32 original OOD',run='reference_inference/'+out.name,claimed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),release_when='inference and independent audit verified'));write(allocation,a);subprocess.check_call(['docker','start',c['container']])
def resume_preflight(cp):
    c=load(cp);out=Path(c['out']);verify(c);r=load(out/'preflight-container/LAUNCH_RECEIPT.json');d=inspect(c['container']+'-preflight')
    require(d['Id']==r['container_id'] and d['Image']==c['image'] and not d['HostConfig']['Devices'],'Preflight resume identity');require(d['Config']['Cmd']==r['command']==[str(out/'preflight.sh')] and d['Config']['Entrypoint']==r['entrypoint']==['bash'],'Preflight resume command');require(sha(cp)==r['config_sha256'] and sha(out/'preflight.sh')==r['wrapper_sha256'],'Preflight resume configuration');require(d['State']['Status']=='exited' and d['State']['ExitCode']!=0,'Only failed preflight resumes')
    t=out/'preflight-COMPLETE.json'
    if t.exists():require(load(t)['rc']!=0,'Successful preflight preserved')
    archive=out/('preflight-resume-before-'+str(time.time_ns()));archive.mkdir()
    for n in ['preflight-COMPLETE.json','preflight-EXIT','preflight-STATUS.json','PREFLIGHT.json']:
        if(out/n).exists():shutil.move(str(out/n),str(archive/n))
    subprocess.check_call(['docker','start',d['Id']])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--preregistration',type=Path);p.add_argument('--size',choices=['2','9']);p.add_argument('--chip',type=int);p.add_argument('--launch',type=Path);p.add_argument('--stage',choices=['preflight','evaluate','finish']);p.add_argument('--resume-preflight',type=Path);a=p.parse_args()
    if a.launch:launch(a.launch,a.stage)
    elif a.resume_preflight:resume_preflight(a.resume_preflight)
    else:prepare(a.source,a.preregistration,a.size,a.chip)
