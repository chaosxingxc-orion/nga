"""Registered resource adapter: queue and hardware checks inside allocation claim lock."""
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
    need(set(policy)=={'schema','allocation','writer_lock','chip','run','predecessor_run','attempt','free_entry','pending_claims','predecessor','priority_refs','selection','scientific_acceptance','test_read'},'policy fields differ')
    need(policy['schema']=='native-exact-predecessor-v1' and policy['scientific_acceptance']is False and policy['test_read']is False,'policy scope differs')
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
    need(sources['acceptance'].get('verdict')=='PASS','predecessor acceptance missing')
    plan,claim,release,host,runtime=[sources[k] for k in ('plan','claim','release','host_exit','runtime_exit')]
    run=policy['predecessor_run'];attempt=policy['attempt']
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
    need(actual and actual['Id']==release['container_id'] and actual['Image']==plan.get('image_sha256',plan.get('image')) and actual['State'].get('Status')=='exited' and actual['State'].get('Running')is False and type(actual['State'].get('ExitCode'))is int and actual['State']['ExitCode']==0,'predecessor container not exited successfully')
    priority=policy['priority_refs'];need(type(priority)is list and len(priority)>0,'priority evidence missing')
    for ref in priority:pinned(ref)
    need(not R.live_chip_conflict(chip,None),'device not free')
    return {'policy':'native-exact-predecessor-v1','policy_sha256':d['queue']['sha256'],'predecessor_plan_sha256':refs['plan']['sha256'],'free_entry':free[0],'live_conflict':False,'global_empty_queue_asserted':False}

def dispatch_guard(d,R,allocation):
    schema=R.load(d['queue']['path']).get('schema')
    if schema=='profile-formal-evaluation-predecessor-v1':return formal_evaluation_guard(d,R,allocation)
    if schema=='native-exact-predecessor-v1':return exact_predecessor_guard(d,R,allocation)
    return queue_guard(d,R)

def formal_evaluation_guard(d,R,allocation):
    """Exact adapter for the existing formal evaluation lifecycle layout."""
    def need(ok,why):
        if not ok:raise ValueError(why)
    def pinned(ref):
        need(set(ref)=={'path','sha256'},'invalid exact reference')
        raw=R.read_bytes(ref['path']);need(R.sha_bytes(raw)==ref['sha256'] and d['files'].get(ref['path'])==ref['sha256'],'changed or unbound predecessor')
        return json.loads(raw)
    q=pinned(d['queue']);R.validate_doc(allocation)
    need(q['schema']=='profile-formal-evaluation-predecessor-v1' and q['scientific_acceptance'] is False and q['test_read'] is False,'resource scope differs')
    need(q['allocation']==d['allocation'] and q['writer_lock']==d['allocation']+'.lock' and q['run']==d['run'],'resource namespace differs')
    need(type(q['chip']) is int and q['chip']==d['chip']==1 and q['attempt']==1 and type(q['attempt']) is int,'resource identity differs')
    free=[x for x in allocation['free'] if x['chip']==1]
    need(not any(x['chip']==1 for x in allocation['allocation']) and len(free)==1 and exact(free[0],q['free_entry']),'free generation changed')
    need(exact(allocation.get('pending_claims'),q['pending_claims']),'pending priority changed')
    refs=q['predecessor'];need(set(refs)=={'execution','spec','claim','release','runtime_exit','aggregate_exit','launch'},'predecessor shape differs')
    x={k:pinned(v) for k,v in refs.items()};e=x['execution'];run=q['predecessor_run'];base=Path(e['out']);a=base/'attempts/1'
    need(e['schema']=='r3-engineering-posttrain-execution-v1' and e['run']==run and e['chip']==1 and type(e['chip']) is int and e['allocation']==d['allocation'],'formal execution differs')
    need(e['scientific_acceptance'] is False and e['test_read'] is False and e['spec']==refs['spec']['path'] and e['spec_sha256']==refs['spec']['sha256'],'formal spec differs')
    need(all(refs[k]['path']==str(v) for k,v in {'execution':base/'execution.json','spec':base/'plan.json','claim':a/'CLAIM.json','release':a/'RELEASE.json','runtime_exit':a/'EXIT.json','aggregate_exit':base/'ENGINEERING_EVAL_EXIT.json','launch':a/'LAUNCH_RECEIPT.json'}.items()),'formal exact paths differ')
    for k in ('runtime_exit','aggregate_exit','release'):
        need(type(x[k]['exit_code']) is int and x[k]['exit_code']==0 and x[k]['scientific_acceptance'] is False,'formal predecessor failure')
    for k in ('runtime_exit','aggregate_exit'):need(type(x[k]['attempt']) is int and x[k]['attempt']==1,'formal attempt differs')
    claim,release=x['claim'],x['release']
    need(claim['schema']=='r3-resource-claim-v1' and release['schema']=='r3-resource-release-v1' and claim['run']==release['run']==run and claim['chip']==release['chip']==1,'formal ownership differs')
    need(release['claim_sha256']==refs['claim']['sha256'] and claim['allocation']==d['allocation'],'claim binding differs')
    released=[v for v in release['allocation_after']['free'] if v['chip']==1]
    need(len(released)==1 and exact(released[0],free[0]) and free[0]['previous_run']==run and free[0]['release_evidence']==refs['release']['path'],'formal release generation differs')
    need(x['launch']['id']==release['container_id'] and x['launch']['image']==x['spec']['image_sha256'],'launch receipt differs')
    name=e['container']+'-a1';actual=R.docker_inspect(name)
    need(release['container']==name and actual and actual['Id']==release['container_id'] and actual['Image']==x['spec']['image_sha256'],'retained identity differs')
    state=actual['State'];need(state['Status']=='exited' and state['Running'] is False and type(state['ExitCode']) is int and state['ExitCode']==0 and state['StartedAt']==release['container_started_at'] and state['FinishedAt']==release['container_finished_at'],'retained terminal differs')
    for ref in q['priority_refs']:pinned(ref)
    need(bool(q['priority_refs']) and bool(q['selection']) and not R.live_chip_conflict(1,None),'priority or live ownership differs')
    return {'policy':q['schema'],'policy_sha256':d['queue']['sha256'],'predecessor_execution_sha256':refs['execution']['sha256'],'free_entry':free[0],'live_conflict':False,'global_empty_queue_asserted':False}

def queue_guard(d,R):
    ref=d['queue'];q=R.load(ref['path'])
    if q.get('schema')!='native-ready-queue-v1' or q.get('allocation')!=d['allocation'] or q.get('writer_lock')!=d['allocation']+'.lock':raise ValueError('authoritative queue contract missing')
    if q.get('accepted_for_dispatch')is not True:raise ValueError('queue coverage not admitted')
    if q.get('coverage')=='chip_ready_tasks':
        if q.get('chips')!=[d['chip']] or any(type(x)is not int for x in q['chips']):raise ValueError('queue chip scope differs')
        # Trusted executable composition pins an independent admission; the
        # controller remains responsible for updating under the allocation lock.
        admission=d['queue'].get('admission');writer=q.get('writer')
        if not admission or not writer:raise ValueError('scoped queue admission/writer missing')
        if R.sha_bytes(R.read_bytes(admission['path']))!=admission['sha256'] or R.sha_bytes(R.read_bytes(writer['path']))!=writer['sha256']:raise ValueError('scoped queue authority changed')
        auth=R.load(admission['path'])
        if (auth.get('schema')!='native-chip-queue-admission-v1' or auth.get('accepted_for_dispatch')is not True
            or auth.get('scientific_acceptance')is not False or auth.get('allocation')!=d['allocation']
            or auth.get('writer_lock')!=q['writer_lock'] or auth.get('queue_path')!=ref['path']
            or auth.get('chips')!=q['chips'] or any(type(x)is not int for x in auth['chips'])
            or auth.get('writer')!=writer):raise ValueError('scoped queue admission differs')
    elif q.get('coverage')!='all_ready_tasks':raise ValueError('queue coverage not admitted')
    if type(q.get('generation'))is not int or q['generation']<1 or not isinstance(q.get('tasks'),list):raise ValueError('queue generation/tasks invalid')
    ids=[]
    for t in q['tasks']:
        if set(t)!={'id','state','chips'} or t['state'] not in ('preparing','ready','running','complete','blocked'):raise ValueError('queue task schema differs')
        if type(t['id'])is not str or not isinstance(t['chips'],list) or any(type(x)is not int for x in t['chips']):raise ValueError('queue task identity differs')
        ids.append(t['id'])
        if t['state']=='ready' and d['chip'] in t['chips'] and t['id']!=d['run']:raise ValueError('ready predecessor has priority')
    if len(ids)!=len(set(ids)):raise ValueError('queue duplicate task')
    if R.live_chip_conflict(d['chip'],None):raise ValueError('device not free')
    return {'queue_sha256':R.sha_bytes(R.read_bytes(ref['path'])),'queue_generation':q['generation'],'live_conflict':False}

def main():
    a=argparse.ArgumentParser();a.add_argument('op',choices=['claim','release']);a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,required=True);a.add_argument('--container-id');x=a.parse_args()
    raw=Path(x.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=x.sha256 or x.attempt<1:raise ValueError('plan differs')
    d=json.loads(raw);R=load_module(d['modules']['resource_base']);root=Path(d['out'])/'host_attempts'/str(x.attempt)
    args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='named forward profile',purpose='fixed DEV32 diagnostic; no selection',proof=str(root/('CLAIM.json' if x.op=='claim' else 'RELEASE.json')))
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
