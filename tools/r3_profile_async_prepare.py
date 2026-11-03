#!/usr/bin/env python3
"""Freeze a separate 32-question async-profile lifecycle smoke configuration."""
import argparse,hashlib,json,shutil,types
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def put(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def pin(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def module(ref):
    assert sha(ref['path'])==ref['sha256'];m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec'),m.__dict__);return m
def prepare(config,expected):
    assert sha(config)==expected;c=read(config);original=read(c['original_plan']['path']);assert sha(c['original_plan']['path'])==c['original_plan']['sha256']
    assert original['schema']=='r3-profile-host-v1';root=Path(c['root']);assert root.is_absolute() and root.parent==Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs') and not root.exists()
    root.mkdir();(root/'code').mkdir();(root/'output').mkdir();refs={}
    for k in ('runtime','host'):
        src=c[k];assert sha(src['path'])==src['sha256'];dest=root/'code'/Path(src['path']).name;shutil.copyfile(src['path'],dest);refs[k]=pin(dest)
    d=dict(original);d.update(refs);d.update(schema='r3-profile-async-host-v1',package=root.name,container=c['container'],run='r3_runs/'+root.name,out=str(root/'output'),selection='first_original_chunk_all_seven_phases',parse_attempts=[1,2],max_process_number=4,original_runtime=original['runtime'],original_plan=c['original_plan'])
    P=module(original['profile_runner']);p,cells=P.verify(original['profile']['path'],original['profile']['sha256']);d['selected_cell']=next(iter(cells));d['files']=dict(original['files']);d['files'].update({v['path']:v['sha256'] for v in [*refs.values(),c['original_plan']]})
    models=[Path(p['model']),Path(p['adapter'])];d['mounts']=[dict(source=str(x),destination=str(x),readonly=True) for x in models]
    d['mounts'] += [dict(source=f,destination=f,readonly=True) for f in sorted(d['files']) if not any(Path(f).is_relative_to(x) for x in models)]
    d['mounts'] += [dict(source=d['out'],destination=d['out'],readonly=False)]
    for x in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']:d['mounts'].append(dict(source=x,destination=x,readonly=True))
    hp=root/'HOST-PLAN.json';d['mounts'].append(dict(source=str(hp),destination=str(hp),readonly=True));put(hp,d);d=read(hp);H=module(refs['host']);H.verify(hp,sha(hp))
    hashes=dict(d['files']);hashes[str(hp)]=sha(hp)
    review={'status':'PENDING_INDEPENDENT_REVIEW_NOT_ACTIVATED','plan':pin(hp),'hashes':hashes,'expected_commands':{'1':H.command(d,hp,sha(hp),1)},'cpu_commands':{str(i):H.cpu_command(d,hp,sha(hp),i) for i in (1,2)},'scope':'32 original DEV questions, all seven phases; CPU parser no devices, explicit retry only','scientific_acceptance':False,'test_read':False}
    put(root/'REVIEW-INPUT.json',review);put(root/'PREPARATION.json',{'config':pin(config),'original_plan':c['original_plan'],'plan':pin(hp),'selected_cell':d['selected_cell'],'questions':32,'npu_started':False,'scientific_acceptance':False})
    return pin(hp)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();print(json.dumps(prepare(a.config,a.sha256)))
