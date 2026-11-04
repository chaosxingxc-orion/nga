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
 q=pinned(d['queue']);need(set(q)=={'schema','chip','run','allocation','free_entry','pending_claims','predecessor','selection','priority_refs','scientific_acceptance','test_read'},'resource policy fields differ')
 need(q['schema']=='native-dataset-physical-free-v1' and q['scientific_acceptance']is False and q['test_read']is False,'resource policy scope')
 need(d['schema']=='native-dataset-panel-execution-v1' and d['scope']=='public_fixed_base_test' and d['test_read']is True and d['scientific_acceptance']is False and d['candidate_test_authority']is False,'execution scope')
 chip=d['chip'];need(type(chip)is int and type(q['chip'])is int and q['chip']==chip and q['run']==d['run'] and q['allocation']==d['allocation'],'resource identity')
 R.validate_doc(allocation);free=[x for x in allocation['free'] if x['chip']==chip]
 need(len(free)==1 and exact(free[0],q['free_entry']) and not any(x['chip']==chip for x in allocation['allocation']),'free generation changed')
 need(exact(allocation.get('pending_claims'),q['pending_claims']),'pending priority changed')
 need(type(q['selection'])is str and bool(q['selection'].strip()) and type(q['priority_refs'])is list and bool(q['priority_refs']),'selection authority missing')
 for ref in q['priority_refs']:pinned(ref)
 refs=q['predecessor'];need(set(refs)=={'claim','release'},'predecessor fields')
 rel=pinned(refs['release']);claim=pinned(refs['claim'])
 need(refs['release']['path']==free[0]['release_evidence'] and str(Path(refs['release']['path']).with_name('CLAIM.json'))==refs['claim']['path'],'release path differs')
 need(rel['schema']=='r3-resource-release-v1' and claim['schema']=='r3-resource-claim-v1' and rel['run']==claim['run']==free[0]['previous_run'],'release lineage')
 need(type(rel['chip'])is int and type(claim['chip'])is int and rel['chip']==claim['chip']==chip and claim['allocation']==d['allocation'] and rel['claim_sha256']==refs['claim']['sha256'],'claim binding')
 need(exact([x for x in rel['allocation_after']['free'] if x['chip']==chip],free),'release free generation')
 need(rel['scientific_acceptance']is False and type(rel['exit_code'])is int,'release scope')
 actual=R.docker_inspect(rel['container']);need(actual and actual['Id']==rel['container_id'],'retained identity')
 state=actual['State'];need(state.get('Running')is False and state.get('Status')=='exited' and type(state.get('ExitCode'))is int and state['ExitCode']==rel['exit_code'],'retained physical exit')
 need(state.get('StartedAt')==rel['container_started_at'] and state.get('FinishedAt')==rel['container_finished_at'],'retained generation')
 need(actual['HostConfig'].get('AutoRemove')is False and actual.get('RestartCount')==0,'retained lifecycle')
 need(any(x.get('PathOnHost')=='/dev/davinci'+str(chip) and x.get('PathInContainer')==x.get('PathOnHost') for x in actual['HostConfig']['Devices']),'retained chip binding')
 need(not R.live_chip_conflict(chip,None),'live physical conflict')
 return dict(schema=q['schema'],policy_sha256=d['queue']['sha256'],free_entry=free[0],physical_release_verified=True,global_empty_queue_asserted=False)

def main():
 p=argparse.ArgumentParser();p.add_argument('op',choices=['claim','release']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,required=True);p.add_argument('--container-id');a=p.parse_args()
 raw=Path(a.plan).read_bytes();need(hashlib.sha256(raw).hexdigest()==a.sha256 and type(a.attempt)is int and a.attempt>0,'plan/attempt')
 d=json.loads(raw);R=module(d['modules']['resource_base']);h=Path(d['out'])/'host_attempts'/str(a.attempt)
 args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='configured fixed-base dataset panel',purpose=d['scope'],proof=str(h/('CLAIM.json' if a.op=='claim' else 'RELEASE.json')))
 if a.op=='claim':
  def factory(_):
   def check(allocation):need(Path(a.plan).read_bytes()==raw,'plan changed inside claim');return guard(d,R,allocation)
   return check
  R.successor_guard=factory;R.claim(args)
 else:args.container=d['container']+'-a'+str(a.attempt);args.container_id=a.container_id;args.claim=str(h/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
