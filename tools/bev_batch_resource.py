"""Exact BEV guard hook around the immutable accepted resource transaction."""
import hashlib,json
from pathlib import Path
import types
BASE='/mnt/cephfs/xingchao/experiments/jev/r3_runs/bev_batch_efficiency_probe_08b_20261102_v1/code/r3_resource_adapter.py'
BASE_SHA='c531413e8109a9eae1a3bb2dba6a914543d814131c90179bbb6b0974ed40051d'

def build():
    raw=Path(BASE).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise RuntimeError('accepted resource source differs')
    R=types.ModuleType('bev_resource_transaction');R.__file__=BASE
    exec(compile(raw,BASE,'exec'),R.__dict__)
    def guard(args):
        if not all(getattr(args,k,None) for k in ('plan','plan_sha256','precondition_sha256')):
            raise RuntimeError('BEV claim requires exact successor binding')
        plan_raw=R.read_bytes(args.plan);p=json.loads(plan_raw)
        if R.sha_bytes(plan_raw)!=args.plan_sha256:raise RuntimeError('plan pin differs')
        if (p['code']['resource']['path']!=str(Path(__file__).resolve()) or p['code']['resource']['sha256']!=R.sha_bytes(R.read_bytes(__file__)) or p['run']!=args.run or p['chip']!=args.chip or R.validated_path(p['allocation'])!=R.validated_path(args.alloc) or args.proof!=str(Path(p['out'])/'host_attempts/1/CLAIM.json')):raise RuntimeError('resource binding differs')
        entry=p['successor_guard']['controller'];controller_raw=R.read_bytes(entry['path'])
        if R.sha_bytes(controller_raw)!=entry['sha256']:raise RuntimeError('controller pin differs')
        S=types.ModuleType('bev_guard_controller');S.__file__=entry['path'];exec(compile(controller_raw,entry['path'],'exec'),S.__dict__)
        def check(allocation):
            if R.read_bytes(args.plan)!=plan_raw or R.read_bytes(entry['path'])!=controller_raw:raise RuntimeError('guard source changed')
            return S.claim_precondition(p,args.plan_sha256,args.precondition_sha256,allocation,R)
        return check
    R.successor_guard=guard
    return R

if __name__=='__main__':build().main()
