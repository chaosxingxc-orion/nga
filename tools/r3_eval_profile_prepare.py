#!/usr/bin/env python3
"""Build a fresh pinned host package for the already reviewed DEV profile panel."""
import argparse,hashlib,json,shutil,types
from pathlib import Path
BASE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)
def read(p):return json.loads(Path(p).read_bytes())
def pin(p):return {'path':str(p),'sha256':sha(p)}
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'pin differs');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec'),m.__dict__);return m
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def prepare(path,digest):
    require(sha(path)==digest,'config differs');c=read(path)
    require(set(c)=={'schema','profile','profile_runner','runtime','host','resource','root','container'},'config fields differ');require(c['schema']=='r3-profile-prepare-v1','schema differs')
    for k in ['profile','profile_runner','runtime','host','resource']:require(sha(c[k]['path'])==c[k]['sha256'],'source changed')
    P=module(c['profile_runner']);p,cells=P.verify(c['profile']['path'],c['profile']['sha256']);root=Path(c['root'])
    require(root.is_absolute() and root.is_relative_to(BASE) and root!=BASE and not root.exists() and not any(x.is_symlink() for x in [root,*root.parents]),'fresh safe output required')
    require(c['container'].startswith('nga-r3-profile-') and all(x.isalnum() or x in '-_' for x in c['container']),'container differs')
    root.mkdir();(root/'code').mkdir();refs={}
    for key in ['runtime','host','resource']:
        dest=root/'code'/Path(c[key]['path']).name;shutil.copyfile(c[key]['path'],dest);refs[key]=pin(dest)
    files=dict(p['files'])
    for ref in [c['profile'],c['profile_runner'],p['manifest'],p['panel'],p['source_spec'],*refs.values()]:files[ref['path']]=ref['sha256']
    # Readonly exact paths preserve the frozen source __file__ admission checks.
    roots=[Path(p['model']),Path(p['adapter'])]
    mounts=[{'source':str(x),'destination':str(x),'readonly':True} for x in roots]
    mounts += [{'source':f,'destination':f,'readonly':True} for f in files if not any(Path(f).is_relative_to(x) for x in roots)]
    out=root/'output';out.mkdir();mounts += [{'source':str(out),'destination':str(out),'readonly':False}]
    for x in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']:mounts.append({'source':x,'destination':x,'readonly':True})
    doc={'schema':'r3-profile-host-v1',**refs,'profile':c['profile'],'profile_runner':c['profile_runner'],'files':files,'image_sha256':read(p['source_spec']['path'])['image_sha256'],'chip':6,'container':c['container'],'run':'r3_runs/'+root.name,'out':str(out),'allocation':str(BASE.parent/'CHIP-ALLOCATION.json'),'poll_seconds':600,'environment':{'PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'},'mounts':mounts,'test_read':False,'scientific_acceptance':False,'candidate_selection_allowed':False}
    hp=root/'HOST-PLAN.json';doc['mounts'].append({'source':str(hp),'destination':str(hp),'readonly':True});write(hp,doc)
    module(refs['host']).verify(hp,sha(hp));write(root/'PREPARATION.json',{'status':'CPU_PREPARED_PENDING_INDEPENDENT_REVIEW','config':pin(path),'plan':pin(hp),'original_profile':c['profile'],'panel_unchanged':True,'cells':len(cells),'rows':sum(map(len,cells.values())),'npu_started':False,'claim_created':False,'scientific_acceptance':False,'resume':'completed original outer chunks persist; recovered measurements excluded from throughput conclusions'})
    return pin(hp)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();print(json.dumps(prepare(a.config,a.sha256),indent=2))
if __name__=='__main__':main()
