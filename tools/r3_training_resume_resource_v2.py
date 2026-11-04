"""Frozen resource transaction with mandatory PT2 exact recovery guard."""
import hashlib,types
from pathlib import Path
CORE_SHA='c531413e8109a9eae1a3bb2dba6a914543d814131c90179bbb6b0974ed40051d'
def successor_guard(args):
 R=_resource
 values=[getattr(args,k,None) for k in ('plan','plan_sha256','precondition_sha256')]
 if not all(values):raise RuntimeError('recovery claim requires full binding')
 path,pin,prepin=values;raw=R.read_bytes(path);p=R.load(path)
 if hashlib.sha256((__import__('json').dumps(dict(p,review_sha256='PENDING'),sort_keys=True,indent=2)+'\n').encode()).hexdigest()!=pin:raise RuntimeError('plan identity differs')
 if p['run']!=args.run or p['chip']!=args.chip or args.chip!=3 or p['allocation']!=args.alloc or p['adapter']!=str(Path(__file__).resolve()) or p['files'].get(p['adapter'])!=R.sha_bytes(R.read_bytes(__file__)) or args.proof!=str(Path(p['out'])/'attempts/1/CLAIM.json'):raise RuntimeError('resource scope differs')
 controller=p['successor_guard']['controller'];source=R.read_bytes(controller)
 if Path(controller).name!='r3_training_resume_v2.py' or p['files'].get(controller)!=R.sha_bytes(source):raise RuntimeError('controller differs')
 m=types.ModuleType('pt2_claim');m.__file__=controller;exec(compile(source,controller,'exec'),m.__dict__)
 def check(allocation):
  if R.read_bytes(path)!=raw or R.read_bytes(controller)!=source:raise RuntimeError('claim source changed')
  return m.claim_precondition(p,pin,prepin,allocation,types.SimpleNamespace(**R.__dict__))
 return check
core=Path(__file__).with_name('base_resource_adapter.py');raw=core.read_bytes()
if hashlib.sha256(raw).hexdigest()!=CORE_SHA:raise RuntimeError('resource core changed')
_resource=types.ModuleType('pt2_resource');_resource.__file__=str(Path(__file__).resolve());exec(compile(raw,str(core),'exec'),_resource.__dict__);_resource.successor_guard=successor_guard
def __getattr__(name):return getattr(_resource,name)
if __name__=='__main__':raise SystemExit(_resource.main())
