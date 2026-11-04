"""Matched DEV adapter for the unchanged retained native host lifecycle."""
import hashlib,json,types
from pathlib import Path
BASE='/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_dev72_registry_20261103_v2/code/bev_native_dev72_host_v1.py'
PIN='768b49e7d0b03b0c418e77b5c05335a3d2e36b7880ceb4b5fa4a53f2d7271726'
raw=Path(BASE).read_bytes()
if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('host base changed')
H=types.ModuleType('matched_host');H.__file__=__file__;exec(compile(raw,BASE,'exec'),H.__dict__)
def verify(path,pin):
    H.require(H.sha(path)==pin,'plan changed');d=H.read(path)
    H.require(d['modules']['host']=={'path':str(Path(__file__).resolve()),'sha256':H.sha(__file__)},'host binding')
    H.module(d['modules']['runtime']).verify(path,pin,host=True)
    return {**d,'runtime':d['modules']['runtime'],'resource':d['modules']['resource'],'image_sha256':d['image']}
def previous(d,a,pin):
    H.require(type(a)is int and a==1,'fresh timing attempt1 only')
    H.require(not (Path(d['out'])/'host_attempts').exists() and not (Path(d['out'])/'measurement').exists(),'never resume timing or uncertain start')
original_supervise=H.supervise
def supervise(args):
    d=verify(args.plan,args.sha256);h=Path(d['out'])/'host_attempts/1'
    H.require(h.is_dir() and (h/'START_INTENT.json').is_file(),'start intent required')
    intent=H.read(h/'START_INTENT.json');expected=[H.sys.executable,'-B','-P',str(Path(__file__).resolve()),'supervise','--plan',args.plan,'--sha256',args.sha256,'--review',args.review,'--review-sha256',args.review_sha256,'--attempt','1']
    H.require(intent['command']==expected,'start intent command differs')
    H.require(not any((h/n).exists() for n in ('CLAIM.json','LAUNCH_SPEC.json','LAUNCH_RECEIPT.json','EXIT.json')),'uncertain or previous execution cannot replay')
    return original_supervise(args)
H.verify=verify;H.previous=previous;H.supervise=supervise
if __name__=='__main__':H.main()
