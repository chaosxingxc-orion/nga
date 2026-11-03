"""Exact resource-only DEV72 shard successor; reuse existing locked claim/release."""
import argparse,hashlib,json,types
from pathlib import Path

def need(v,s):
    if not v:raise ValueError(s)
def load_module(ref):
    raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'source changed');m=types.ModuleType('shard_resource');m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def exact(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def guard(d,R,allocation):
    def pinned(ref):
        raw=R.read_bytes(ref['path']);need(d['files'].get(ref['path'])==ref['sha256']==R.sha_bytes(raw),'unbound policy source');return json.loads(raw)
    q=pinned(d['queue']);need(set(q)=={'schema','scientific_acceptance','allocation','writer_lock','chip','run','free_entry','pending_claims','attempt','predecessor','priority_refs','selection'},'policy fields');need(q['schema']=='native-dev72-resource-successor-v1' and q['scientific_acceptance'] is False,'policy scope')
    need(d['schema']=='native-dev72-reference-execution-v1' and d['test_read'] is False and d['scientific_acceptance'] is False,'candidate scope')
    need(q['allocation']==d['allocation'] and q['writer_lock']==d['allocation']+'.lock' and type(q['chip']) is int and type(d['chip']) is int and q['chip']==d['chip'] and q['run']==d['run'],'candidate identity')
    R.validate_doc(allocation);free=[x for x in allocation['free'] if x['chip']==d['chip']]
    need(len(free)==1 and exact(free[0],q['free_entry']) and not any(x['chip']==d['chip'] for x in allocation['allocation']),'free generation differs')
    need(exact(allocation.get('pending_claims'),q['pending_claims']),'pending priority changed')
    p=q['predecessor'];need(set(p)=={'plan','claim','release','launch_spec','launch_receipt'},'predecessor fields');v={k:pinned(x) for k,x in p.items()};plan=v['plan'];claim=v['claim'];release=v['release'];spec=v['launch_spec'];receipt=v['launch_receipt']
    need(plan['schema']=='bev-native-panel-host-v1' and type(plan['chip']) is int and plan['chip']==d['chip'] and plan['allocation']==d['allocation'],'predecessor plan')
    a=q['attempt'];need(type(a) is int and a>0,'predecessor attempt');root=Path(plan['out'])/'host_attempts'/str(a);name=plan['container']+'-a'+str(a)
    need(all(p[k]['path']==str(root/f) for k,f in [('claim','CLAIM.json'),('release','RELEASE.json'),('launch_spec','LAUNCH_SPEC.json'),('launch_receipt','LAUNCH_RECEIPT.json')]),'predecessor paths')
    need(claim.get('schema')=='r3-resource-claim-v1' and release.get('schema')=='r3-resource-release-v1' and claim['run']==release['run']==plan['run'],'predecessor resource identity')
    need(type(claim['chip']) is int and type(release['chip']) is int and claim['chip']==release['chip']==d['chip'] and claim['allocation']==d['allocation'] and claim.get('scientific_acceptance',False) is False and claim.get('execution_authorized',False) is False and release['claim_sha256']==p['claim']['sha256'],'claim binding')
    need(free[0]['previous_run']==plan['run'] and free[0]['release_evidence']==p['release']['path'],'release generation')
    released=[x for x in release['allocation_after']['free'] if type(x.get('chip')) is int and x['chip']==d['chip']];need(released==free,'released free generation')
    actual=R.docker_inspect(name);need(actual and actual['Id']==release['container_id']==receipt['container_id'] and actual['Image']==plan['image_sha256'] and actual['State']['Status']=='exited' and actual['State']['Running'] is False and type(actual['State']['ExitCode']) is int and type(release['exit_code']) is int and actual['State']['ExitCode']==release['exit_code'],'retained predecessor')
    need(type(release.get('container_started_at')) is str and bool(release['container_started_at']) and type(release.get('container_finished_at')) is str and bool(release['container_finished_at']) and actual['State'].get('StartedAt')==release['container_started_at'] and actual['State'].get('FinishedAt')==release['container_finished_at'],'predecessor runtime generation differs')
    need(release['container']==name and release['scientific_acceptance'] is False and spec['plan_sha256']==receipt['plan_sha256']==p['plan']['sha256'],'launch identity')
    need(actual['Config']['Cmd']==receipt['command']==spec['command'][spec['command'].index(plan['image_sha256'])+1:] and actual['HostConfig']['AutoRemove'] is False,'retained launch command differs')
    need(any(x.get('PathOnHost')=='/dev/davinci'+str(d['chip']) for x in actual['HostConfig']['Devices']),'predecessor device differs')
    need(q['priority_refs'] and q['selection'].strip(),'priority evidence missing')
    for x in q['priority_refs']:pinned(x)
    need(not R.live_chip_conflict(d['chip'],None),'device conflict')
    return dict(policy=q['schema'],physical_release_verified=True,scientific_acceptance_required=False,global_empty_queue_asserted=False,free_entry=free[0])
def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['claim','release']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,required=True);ap.add_argument('--container-id');a=ap.parse_args();raw=Path(a.plan).read_bytes();need(hashlib.sha256(raw).hexdigest()==a.sha256 and a.attempt>0,'plan/attempt');d=json.loads(raw);R=load_module(d['modules']['resource_base']);h=Path(d['out'])/'host_attempts'/str(a.attempt)
    args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='registered native DEV72 reference',purpose='original DEV72 numerical reference/repeat/adapter',proof=str(h/('CLAIM.json' if a.op=='claim' else 'RELEASE.json')))
    if a.op=='claim':
        def factory(_):
            def check(allocation):need(Path(a.plan).read_bytes()==raw,'plan changed in lock');return guard(d,R,allocation)
            return check
        R.successor_guard=factory;R.claim(args)
    else:args.container=d['container']+'-a'+str(a.attempt);args.container_id=a.container_id;args.claim=str(h/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
