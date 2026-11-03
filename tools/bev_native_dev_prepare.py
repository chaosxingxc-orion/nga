"""Prepare fresh native DEV execution from one configuration; never launch."""
import argparse,json,shutil
from pathlib import Path
from tools import bev_native_dev_runner as R

def pin(p):return dict(path=str(Path(p).resolve()),sha256=R.sha(Path(p).resolve()))
def prepare(path,digest):
    R.require(R.sha(path)==digest,'config differs');c=R.read(path)
    R.require(set(c)=={'schema','root','container','chip','probe_plan','probe','runtime','host','resource'},'config keys differ')
    R.require(c['schema']=='bev-native-dev-prepare-v1' and c['chip'] in (0,7),'config scope differs')
    root=Path(c['root']);base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
    R.require(root.is_absolute() and root.is_relative_to(base) and root!=base and not root.exists() and not any(x.is_symlink() for x in [root,*root.parents]),'fresh root required')
    for k in ('probe_plan','probe','runtime','host','resource'):R.require(R.sha(c[k]['path'])==c[k]['sha256'],'config source differs')
    P=R.module(c['probe']);p,items,_=P.verify(c['probe_plan']['path'],c['probe_plan']['sha256'])
    root.mkdir();(root/'code').mkdir();refs={}
    for key in ('runtime','host','resource'):
        dst=root/'code'/Path(c[key]['path']).name;shutil.copyfile(c[key]['path'],dst);refs[key]=pin(dst)
    files={v['path']:v['sha256'] for v in [*refs.values(),c['probe'],c['probe_plan'],p['inputs'],*p['files'].values(),*p['model_files'].values()]}
    (root/'output').mkdir()
    d=dict(schema='bev-native-dev-host-v1',**refs,probe=c['probe'],probe_plan=c['probe_plan'],files=files,chip=c['chip'],image_sha256=R.IMAGE,environment=R.ENV,loader=R.LOADER,container=c['container'],out=str(root/'output'),run='r3_runs/'+root.name,allocation=str(base.parent/'CHIP-ALLOCATION.json'),poll_seconds=600,test_read=False,scientific_acceptance=False,timing_enabled=False,candidate_selection_allowed=False)
    hp=root/'HOST-PLAN.json';d['mounts']=R.mounts(d,hp,p);R.write(hp,d);d=R.read(hp)
    RR=R.module(refs['runtime']);RR.verify(str(hp),R.sha(hp));H=R.module(refs['host']);H.verify(str(hp),R.sha(hp))
    result=dict(status='PREPARED_NOT_ADMITTED',config=pin(path),plan=pin(hp),npu_started=False,scientific_acceptance=False,test_read=False,items=len(items),expected_commands={'1':H.command(d,str(hp),R.sha(hp),1)},hashes=dict(files,**{str(hp):R.sha(hp)}))
    R.write(root/'REVIEW-INPUT.json',result);return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();print(json.dumps(prepare(a.config,a.sha256),indent=2))
