#!/usr/bin/env python3
"""Use unchanged resource transactions with one explicit control DEV guard."""
import hashlib
from pathlib import Path
import types

CORE_SHA='f90ae21242b78c4c774ff5c12b5ff30d9e7b1bd927d42f910fc157c6538a574a'

def successor_guard(args):
    R=_resource
    values=[getattr(args,key,None) for key in ('plan','plan_sha256','precondition_sha256')]
    if not all(values):raise RuntimeError('control DEV requires complete successor claim binding')
    path,plan_pin,precondition_pin=values;plan_raw=R.read_bytes(path);p=R.load(path)
    if R.sha_bytes(plan_raw)!=plan_pin or p.get('successor_guard',{}).get('identity_mode')!='sha256_raw':
        raise RuntimeError('control DEV raw plan identity differs')
    if (p.get('run')!=args.run or p.get('chip')!=args.chip or args.chip!=3
        or R.validated_path(p['allocation'])!=R.validated_path(args.alloc)
        or Path(p['adapter']).resolve()!=Path(__file__).resolve()
        or p['files'].get(p['adapter'])!=R.sha_bytes(R.read_bytes(__file__))
        or args.proof!=str(Path(p['out'])/'attempts/1/CLAIM.json')):
        raise RuntimeError('control DEV resource scope differs')
    controller=p['successor_guard'].get('controller')
    if not controller or Path(controller).name!='r3_control_dev_successor_v1.py':
        raise RuntimeError('registered control DEV controller required')
    raw=R.read_bytes(controller)
    if p['files'].get(controller)!=R.sha_bytes(raw):raise RuntimeError('control DEV controller pin differs')
    module=types.ModuleType('control_dev_claim_guard');module.__file__=controller
    exec(compile(raw,controller,'exec',dont_inherit=True),module.__dict__)
    def check(allocation):
        if R.read_bytes(path)!=plan_raw or R.read_bytes(controller)!=raw:
            raise RuntimeError('control DEV claim binding changed during transaction')
        result=module.claim_precondition(p,plan_pin,precondition_pin,allocation,types.SimpleNamespace(**R.__dict__))
        return dict(result,plan_sha256=plan_pin,controller_sha256=R.sha_bytes(raw))
    return check

core=Path(__file__).with_name('core_resource_adapter.py');raw=core.read_bytes()
if hashlib.sha256(raw).hexdigest()!=CORE_SHA:raise RuntimeError('frozen resource core changed')
_resource=types.ModuleType('control_dev_resource_core');_resource.__file__=str(Path(__file__).resolve())
exec(compile(raw,str(core),'exec',dont_inherit=True),_resource.__dict__)
_resource.successor_guard=successor_guard
def __getattr__(name):return getattr(_resource,name)
if __name__=='__main__':raise SystemExit(_resource.main())
