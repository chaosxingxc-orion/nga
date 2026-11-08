"""Exact free-generation resource binding for configured fixed-base TEST jobs.

Scientific/numerical qualification is checked by host admission, independently of
physical ownership. A successful historical numerical experiment is not required
for a physically exited predecessor to release a chip.
"""
import argparse,hashlib,json,types
from pathlib import Path

def need(ok,why):
 if not ok:raise ValueError(why)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def exact(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def module(ref):
 need(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType('resource_base');m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m

def guard(d,R,allocation):
 def pinned(ref):
  need(set(ref)=={'path','sha256'} and d['files'].get(ref['path'])==ref['sha256']==sha(ref['path']),'policy source unbound or changed')
  return json.loads(Path(ref['path']).read_bytes())
 q=pinned(d['queue'])
 need(q['schema']=='instruct08-documents-resource-v1' and d['chip'] in (4,5) and q['chip']==d['chip'] and q['run']==d['run'] and q['allocation']==d['allocation'],'resource identity')
 need(d['scope']=='public_fixed_instruct_test' and d['test_read'] is True and d['scientific_acceptance'] is False and d['candidate_test_authority'] is False,'scope differs')
 R.validate_doc(allocation); free=[x for x in allocation['free'] if x['chip']==d['chip']]
 need(free==[q['free_entry']] and not any(x['chip']==d['chip'] for x in allocation['allocation']),'free generation changed')
 need(exact(allocation.get('pending_claims'),q['pending_claims']),'pending claims changed')
 import sys
 sys.path.insert(0,str(Path(__file__).parent))
 import unified_resource_lease_v1 as U
 refs=q['predecessor']; pinned(refs['claim']); pinned(refs['release'])
 U.predecessor({'allocation':d['allocation']},free[0],U.DockerQuery(),{'claim':refs['claim'],'release':refs['release'],'container':None,'terminal':None})
 return dict(schema=q['schema'],policy_sha256=d['queue']['sha256'],free_entry=free[0],physical_release_verified=True,global_empty_queue_asserted=False)

def main():
 p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','claim','release']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,required=True);p.add_argument('--container-id');a=p.parse_args()
 raw=Path(a.plan).read_bytes();need(hashlib.sha256(raw).hexdigest()==a.sha256 and type(a.attempt)is int and a.attempt>0,'plan/attempt')
 d=json.loads(raw);R=module(d['modules']['resource_base']);h=Path(d['out'])/'host_attempts'/str(a.attempt)
 args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='configured fixed-base dataset panel',purpose=d['scope'],proof=str(h/('CLAIM.json' if a.op=='claim' else 'RELEASE.json')))
 if a.op=='verify':
  print(json.dumps(guard(d,R,json.loads(Path(d['allocation']).read_bytes())),sort_keys=True));return
 if a.op=='claim':
  def factory(_):
   def check(allocation):need(Path(a.plan).read_bytes()==raw,'plan changed inside claim');return guard(d,R,allocation)
   return check
  R.successor_guard=factory;R.claim(args)
 else:args.container=d['container']+'-a'+str(a.attempt);args.container_id=a.container_id;args.claim=str(h/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
