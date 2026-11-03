"""Configured panel resource policy for exact native-config predecessors.
Versioned policy preserves the original locked claim/release transaction.
"""
import argparse,hashlib,json,types
from pathlib import Path

def load_module(ref):
    raw=Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('resource implementation changed')
    m=types.ModuleType('pinned_resource');m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

def exact(value, other):
    # JSON equality alone accepts False as chip 0 and True as generation 1.
    return json.dumps(value,sort_keys=True,allow_nan=False)==json.dumps(other,sort_keys=True,allow_nan=False)

def exact_predecessor_guard(d,R,allocation):
    """Narrow, reviewed successor selection; makes no global queue-empty claim.

    Called twice by resource_base.claim while its allocation lock is held.
    Mutable priority references are rehashed, not copied into fictitious queues.
    """
    def need(ok,why):
        if not ok:raise ValueError(why)
    def pinned(ref):
        need(type(ref)is dict and set(ref)=={'path','sha256'},'invalid policy reference')
        raw=R.read_bytes(ref['path'])
        need(R.sha_bytes(raw)==ref['sha256'] and d['files'].get(ref['path'])==ref['sha256'],'policy dependency changed or unbound')
        return json.loads(raw)
    policy=pinned(d['queue'])
    need(set(policy)=={'schema','allocation','writer_lock','chip','run','predecessor_run','attempt','free_entry','pending_claims','predecessor','priority_refs','selection','scientific_acceptance','test_read','purpose','predecessor_format'},'policy fields differ')
    need(policy['schema']=='native-panel-exact-predecessor-v2' and policy['scientific_acceptance']is False and policy['test_read']is False,'policy scope differs')
    need(d.get('schema')=='native-panel-execution-v2' and d.get('scope')=='public_fixed_base_test' and d.get('test_read')is True and d.get('scientific_acceptance')is False and d.get('candidate_test_authority')is False,'candidate scope differs')
    need(policy['purpose']==d['scope'] and policy['predecessor_format']=='native-config-execution-v1','resource policy version differs')
    need(policy['allocation']==d['allocation'] and policy['writer_lock']==d['allocation']+'.lock','policy allocation differs')
    need(type(d['chip'])is int and type(policy['chip'])is int and policy['chip']==d['chip'] and policy['run']==d['run'],'policy candidate differs')
    need(type(policy['attempt'])is int and policy['attempt']>0 and type(policy['predecessor_run'])is str,'predecessor identity differs')
    need(type(policy['selection'])is str and bool(policy['selection'].strip()),'dispatch selection reason missing')
    need(type(allocation)is dict,'locked allocation required');R.validate_doc(allocation)
    chip=d['chip'];free=[x for x in allocation['free'] if x['chip']==chip]
    need(not any(x['chip']==chip for x in allocation['allocation']),'chip owned')
    need(len(free)==1 and exact(free[0],policy['free_entry']),'free entry generation changed')
    need(type(policy['pending_claims'])is list and exact(allocation.get('pending_claims'),policy['pending_claims']),'pending priority changed')
    refs=policy['predecessor'];need(type(refs)is dict and set(refs)=={'plan','claim','release','host_exit','runtime_exit','acceptance'},'predecessor references differ')
    sources={k:pinned(v) for k,v in refs.items()}
    accept=sources['acceptance']
    need(accept.get('verdict')=='PASS' and accept.get('schema')=='native9b-long-actual-independent-v1' and accept.get('status')=='PASS_EXACT_SYNTHETIC_LONG_DEV' and accept.get('lifecycle_verified')is True and accept.get('all_tensors_and_restricted_arithmetic_exact')is True and accept.get('plan_sha256')==refs['plan']['sha256'] and accept.get('scientific_acceptance')is False and accept.get('test_read')is False and accept.get('fullpanel_launch_authorized')is False,'predecessor acceptance missing or unbound')
    plan,claim,release,host,runtime=[sources[k] for k in ('plan','claim','release','host_exit','runtime_exit')]
    run=policy['predecessor_run'];attempt=policy['attempt']
    need(plan.get('schema')=='native-config-execution-v1' and plan.get('test_read')is False and plan.get('scientific_acceptance')is False and 'image_sha256' not in plan,'predecessor schema differs')
    need(plan.get('run')==run and type(plan.get('chip'))is int and plan['chip']==chip and plan.get('allocation')==d['allocation'],'predecessor plan differs')
    root=Path(plan['out']);name=plan['container']+'-a'+str(attempt)
    paths={'claim':root/'host_attempts'/str(attempt)/'CLAIM.json','release':root/'host_attempts'/str(attempt)/'RELEASE.json','host_exit':root/'host_attempts'/str(attempt)/'EXIT.json','runtime_exit':root/'attempts'/str(attempt)/'EXIT.json'}
    need(all(refs[k]['path']==str(v) for k,v in paths.items()),'predecessor attempt paths differ')
    for obj,schema in [(claim,'r3-resource-claim-v1'),(release,'r3-resource-release-v1')]:
        need(obj.get('schema')==schema and obj.get('run')==run and type(obj.get('chip'))is int and obj['chip']==chip,'predecessor resource identity differs')
    need(claim.get('allocation')==d['allocation'] and release.get('claim_sha256')==refs['claim']['sha256'],'predecessor claim binding differs')
    need(release.get('scientific_acceptance')is False and host.get('scientific_acceptance')is False and runtime.get('scientific_acceptance')is False,'predecessor scope differs')
    need(free[0].get('previous_run')==run and free[0].get('release_evidence')==refs['release']['path'],'predecessor free binding differs')
    released=[x for x in release.get('allocation_after',{}).get('free',[]) if type(x.get('chip'))is int and x['chip']==chip]
    need(len(released)==1 and exact(released[0],free[0]),'release generation differs')
    for obj in (release,host,runtime):need(type(obj.get('exit_code'))is int and obj['exit_code']==0,'predecessor not successful')
    need(type(host.get('container_exit_code'))is int and host['container_exit_code']==0 and host.get('runner_terminal_matches')is True,'host terminal differs')
    need(runtime.get('plan_sha256')==refs['plan']['sha256'] and type(runtime.get('attempt'))is int and runtime['attempt']==attempt,'runtime terminal differs')
    need(release.get('container')==name and host.get('container_id')==release.get('container_id'),'predecessor container identity differs')
    actual=R.docker_inspect(name)
    need(actual and actual['Id']==release['container_id'] and actual['Image']==plan['image'] and actual['State'].get('Status')=='exited' and actual['State'].get('Running')is False and type(actual['State'].get('ExitCode'))is int and actual['State']['ExitCode']==0,'predecessor container not exited successfully')
    priority=policy['priority_refs'];need(type(priority)is list and len(priority)>0,'priority evidence missing')
    for ref in priority:pinned(ref)
    need(not R.live_chip_conflict(chip,None),'device not free')
    return {'policy':'native-panel-exact-predecessor-v2','policy_sha256':d['queue']['sha256'],'predecessor_plan_sha256':refs['plan']['sha256'],'free_entry':free[0],'live_conflict':False,'global_empty_queue_asserted':False}

def dispatch_guard(d,R,allocation):
    schema=R.load(d['queue']['path']).get('schema')
    if schema=='native-panel-exact-predecessor-v2':return exact_predecessor_guard(d,R,allocation)
    raise ValueError('unregistered panel resource policy')

def main():
    a=argparse.ArgumentParser();a.add_argument('op',choices=['claim','release']);a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,required=True);a.add_argument('--container-id');x=a.parse_args()
    raw=Path(x.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=x.sha256 or x.attempt<1:raise ValueError('plan differs')
    d=json.loads(raw);R=load_module(d['modules']['resource_base']);root=Path(d['out'])/'host_attempts'/str(x.attempt)
    args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='registered native runtime',purpose=d['scope'],proof=str(root/('CLAIM.json' if x.op=='claim' else 'RELEASE.json')))
    if x.op=='claim':
        def guard_factory(_):
            def check(allocation):
                if Path(x.plan).read_bytes()!=raw:raise ValueError('plan changed in claim')
                return dispatch_guard(d,R,allocation)
            return check
        R.successor_guard=guard_factory;R.claim(args)
    else:
        args.container=d['container']+'-a'+str(x.attempt);args.container_id=x.container_id;args.claim=str(root/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
