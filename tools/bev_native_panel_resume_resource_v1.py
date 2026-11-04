"""Recovery resource guard; original resource transaction remains unchanged."""
import json,types,hashlib
from pathlib import Path
BASE_SHA='4adf2e04d224e3c66d195bf93fc5c4c062bb4c194abe35404701db273602e62f'
p=Path(__file__).with_name('bev_native_config_panel_resource.py');raw=p.read_bytes()
if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise ValueError('original resource differs')
B=types.ModuleType('original_resource');B.__file__=str(p);exec(compile(raw,str(p),'exec'),B.__dict__)

def guard(d,R,allocation):
    def need(ok,why):
        if not ok:raise ValueError(why)
    def pinned(ref):
        raw=R.read_bytes(ref['path']);need(R.sha_bytes(raw)==ref['sha256']==d['files'].get(ref['path']),'resource evidence changed');return json.loads(raw)
    policy=pinned(d['queue']);r=d['recovery'];old=pinned(r['source_plan']);rel=pinned(r['release']);host=pinned(r['host_exit']);claim=pinned(r['claim']);receipt=pinned(r['receipt'])
    need(policy['schema']=='native-panel-recovery-resource-v1' and d['schema']=='native-panel-resume-execution-v1','recovery schema differs')
    need(d['candidate_test_authority']is False and d['scientific_acceptance']is False and policy['scientific_acceptance']is False,'authority differs')
    need(d['chip']==old['chip']==policy['chip']==0 and type(d['chip'])is int and policy['run']==d['run'] and policy['allocation']==d['allocation']==old['allocation'],'resource projection differs')
    R.validate_doc(allocation);free=[x for x in allocation['free'] if x['chip']==0]
    need(len(free)==1 and B.exact(free[0],policy['free_entry']) and not any(x['chip']==0 for x in allocation['allocation']),'chip generation differs')
    need(B.exact(allocation.get('pending_claims'),policy['pending_claims']),'pending priority changed')
    need(free[0]['previous_run']==old['run'] and free[0]['release_evidence']==r['release']['path'],'release free identity differs')
    need(B.exact(free[0],next(x for x in rel['allocation_after']['free'] if x['chip']==0)),'release free generation differs')
    need(rel['claim_sha256']==r['claim']['sha256'] and rel['container_id']==host['container_id']==receipt['container_id'] and rel['run']==claim['run']==old['run'],'original claim differs')
    need(type(rel['exit_code'])is int and rel['exit_code']==host['container_exit_code']==1 and host['runner_terminal_matches']is False and host['source']=='retained-container-exit','truthful failed release required')
    name=old['container']+'-a1';actual=R.docker_inspect(name)
    need(actual and actual['Id']==rel['container_id'] and actual['Image']==old['image'] and actual['State']['Status']=='exited' and actual['State']['Running']is False and type(actual['State']['ExitCode'])is int and actual['State']['ExitCode']==1 and actual['RestartCount']==0,'retained failed predecessor differs')
    need(actual['State']['StartedAt']==rel['container_started_at'] and actual['State']['FinishedAt']==rel['container_finished_at'] and actual['Config']['Cmd']==receipt['command'] and not actual['HostConfig']['AutoRemove'],'retained predecessor generation differs')
    for ref in policy['priority_refs']:pinned(ref)
    need(not R.live_chip_conflict(0,None),'live device conflict')
    return dict(policy=policy['schema'],policy_sha256=d['queue']['sha256'],source_plan_sha256=r['source_plan']['sha256'],free_entry=free[0],live_conflict=False,global_empty_queue_asserted=False)
B.dispatch_guard=guard
if __name__=='__main__':B.main()
