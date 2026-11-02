#!/usr/bin/env python3
"""Configured four-role CPU capture/DEV preparation. Never launches or grants TEST."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import types

ROLES=('primary_s2','primary_s3','samechip_s2','diffchip_s2')
LATE=['TRAIN_EXIT.json','attempts/1/EXIT.json','attempts/1/RELEASE.json',
      'attempts/1/SUPERVISOR_DONE.json','manifest.json',
      'adapter/adapter_config.json','adapter/adapter_model.safetensors']
EXTRA=['attempts/1/CLAIM.json','attempts/1/LAUNCH_RECEIPT.json',
       'attempts/1/LAUNCH_SPEC.json','SUPERVISOR_RECEIPT.json','SUCCESSOR_PRECONDITION.json']

def require(ok, why):
    if not ok:
        raise ValueError(why)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and str(p) == str(path)
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    require(not any(x.lower().split('.')[0] == 'test' for x in p.parts), 'TEST path forbidden')
    return p


def raw(path, pin=None, limit=2**20):
    with safe(path).open('rb') as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit, 'metadata exceeds bound')
    require(pin is None or hashlib.sha256(value).hexdigest() == pin, 'pin changed: '+str(path))
    return value


def load(path, pin=None):
    return json.loads(raw(path, pin))


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, doc, exclusive=False):
    path = safe(path)
    data = (json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    if exclusive:
        # Publish complete bytes atomically; watcher never observes partial injection.
        import tempfile
        fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.pending',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.link(name,path) # no overwrite/adoption; fails if destination exists
        finally:
            Path(name).unlink(missing_ok=True)
    else:
        target=path.with_suffix('.pending')
        with target.open('wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        target.replace(path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def module(path,pin):
    code=raw(path,pin);m=types.ModuleType(Path(path).stem);m.__file__=str(path)
    exec(compile(code,str(path),'exec',dont_inherit=True),m.__dict__);return m

def identity(path,pin):
    b=load(path,pin)
    require(b['schema']=='r3-formal-wave-handoff-v1' and b['test_read'] is False
        and b['scientific_acceptance'] is False and b['evaluation_authorized'] is False,'handoff scope differs')
    require(type(b['poll_interval_seconds']) is int and b['poll_interval_seconds']>=600,'poll cadence too short')
    own=str(Path(__file__).absolute());require(b['source_files'].get(own)==sha(own),'different handoff executable')
    for f,h in b['source_files'].items():require(sha(f)==h,'source changed')
    q=load(b['queue']['path'],b['queue']['sha256']);require(q['schema']=='r3-formal-train-successor-v3','four-role queue required')
    S=module(q['controller'],q['controller_sha256']);S.verify(b['queue']['path'],b['queue']['sha256'],reviewed=True)
    closure=load(b['closure']['path'],b['closure']['sha256']);require(closure.get('evaluation_profile') in ('track_k','track_kt',None),'closure profile differs')
    require(len(b['jobs'])==4 and {j['role'] for j in b['jobs']}==set(ROLES),'four exact handoff roles required')
    require(len({j['out'] for j in b['jobs']})==4,'duplicate DEV output')
    schedule=load(q['formal_schedule'],q['formal_schedule_sha256']);nodes={n['id']:n for n in schedule['nodes']}
    source=Path(own).parent;binder=str(source/'r3_posttrain_eval_plan.py')
    require(binder in b['source_files'],'binder not pinned')
    state=safe(b['state_root']);jobs={}
    for item in b['jobs']:
        role=item['role'];matches=[j for j in q['jobs'] if j['formal_role']==role];require(len(matches)==1,'queue role differs')
        qj=matches[0];p=S.plan(qj,reviewed=True);node=nodes[role+'_dev']
        require(item['training']==p['out'] and item['chip']==p['chip']==node['chip']
            and item['out']==node['out'] and item['launch_dependencies']==node['depends_on'],'handoff role placement/order differs')
        out=safe(item['out']);training=safe(item['training'])
        require(not state.is_relative_to(training) and not training.is_relative_to(state)
            and not out.is_relative_to(state) and not state.is_relative_to(out),'state overlaps training/output')
        jobs[role]=dict(role=role,seed=p['seed'],training=p['out'],new_adapter=str(training/'adapter'),
            canonical_plan_sha256=qj['plan_sha256'],required_final_step=3116,
            training_plan={'path':qj['plan'],'sha256':qj['plan_raw_sha256']},
            fresh_eval_out=str(out),late_bound_hashes=LATE,launch_dependencies=item['launch_dependencies'],chip=item['chip'])
    b['_pin']=pin;b['_path']=str(path);b['_binder']=binder;return b,jobs,q

def capture(binding, job, plan):
    """Saved records are not proof of retained-container reality; independent gate follows."""
    root = safe(job['training']); terminal = root/'TRAIN_EXIT.json'
    if not terminal.exists():
        return {'status': 'waiting_training'}
    end = load(terminal)
    require(type(end.get('exit_code')) is int and end.get('attempt') == 1, 'invalid terminal')
    if end['exit_code'] != 0:
        return {'status': 'training_failed', 'exit_code': end['exit_code']}
    names = job['late_bound_hashes'] + EXTRA
    if not all(safe(root/name).is_file() for name in names):
        return {'status': 'waiting_completion_evidence'}
    hashes = {str(root/name): sha(root/name) for name in names}
    docs = {name: load(root/name, hashes[str(root/name)]) for name in names if name.endswith('.json')}
    require(docs['TRAIN_EXIT.json'] == end == docs['attempts/1/EXIT.json'], 'terminal mismatch')
    require(end.get('scientific_acceptance') is False and end.get('started_utc')
            and end.get('finished_utc') and end.get('source') != 'retained-container-exit', 'not genuine driver completion')
    release = docs['attempts/1/RELEASE.json']; done = docs['attempts/1/SUPERVISOR_DONE.json']
    launch = docs['attempts/1/LAUNCH_RECEIPT.json']; claim = docs['attempts/1/CLAIM.json']
    require(release.get('schema') == 'r3-resource-release-v1' and release['run'] == plan['run']
            and release['chip'] == plan['chip'] and release['container'] == plan['container']+'-a1'
            and release['container_id'] == launch['id'] and launch['image'] == plan['image_sha256']
            and launch['plan_sha256'] == job['canonical_plan_sha256']
            and release.get('claim_sha256') == hashes[str(root/'attempts/1/CLAIM.json')]
            and claim['run'] == plan['run'] and claim['chip'] == plan['chip'], 'release/launch/claim mismatch')
    for record in (release, done):
        require(type(record.get('exit_code')) is int and record['exit_code'] == 0
                and record.get('scientific_acceptance') is False, 'completion scope or exit differs')
    manifest = docs['manifest.json']; args = manifest.get('args', {})
    require(manifest.get('summary', {}).get('final_step') == job['required_final_step'] == 3116
            and manifest.get('arm') == args.get('arm') == 'k1' and args.get('seed') == job['seed']
            and manifest.get('model_path') == args.get('model_path') == plan['model'], 'manifest identity differs')
    adapter = safe(job['new_adapter'])
    for path in adapter.iterdir():
        require(not path.is_symlink() and path.is_file(), 'unexpected adapter entry')
        hashes[str(path)] = sha(path)
    hashes[job['training_plan']['path']] = job['training_plan']['sha256']
    require(all(sha(path) == pin for path, pin in hashes.items()), 'provenance changed during capture')
    return dict(schema='r3-formal-posttrain-capture-v1', status='REVIEW_REQUIRED', training=job['training'],
                queue_sha256=binding['queue']['sha256'], binding_sha256=binding['_pin'], role=job['role'], files=hashes,
                adapter_files={p: h for p, h in hashes.items() if Path(p).parent == adapter},
                test_read=False, scientific_acceptance=False, retained_container_verified=False,
                scope='CPU saved provenance only; independent actual postrun verification required')


def check_capture(doc,binding,job,plan):
    require(doc==capture(binding,job,plan) and doc['status']=='REVIEW_REQUIRED','capture changed or incomplete')

def review_check(state,ref,binding,job,plan):
    captured=load(state/'CAPTURE.json');check_capture(captured,binding,job,plan)
    review=load(ref['path'],ref['sha256'])
    require(review.get('schema')=='r3-formal-independent-postrun-v1' and review.get('verdict')=='PASS'
        and review.get('independent') is True and review.get('training')==job['training']
        and review.get('queue_sha256')==binding['queue']['sha256'] and review.get('binding_sha256')==binding['_pin']
        and review.get('capture_sha256')==sha(state/'CAPTURE.json') and review.get('files')==captured['files']
        and review.get('test_read') is False and review.get('scientific_acceptance') is False,'independent postrun review differs')
    required=('genuine_train_exit','retained_container_identity','claim_release_done_identity',
              'training_inputs_and_code','adapter_provenance','final_step_3116')
    require(all(review.get('checks',{}).get(k) is True for k in required),'postrun verification incomplete')
    review_path=safe(ref['path']);state_root=safe(binding['state_root'])
    require(not review_path.is_relative_to(state_root) and not review_path.is_relative_to(safe(job['training']))
            and review.get('evidence_files'),'review must be external with evidence')
    require(all(sha(p)==h for p,h in review['evidence_files'].items()),'independent evidence changed')
    return captured,review

def inject(path,pin,role,review,review_pin):
    b,jobs,_=identity(path,pin);require(role in jobs,'unknown role');job=jobs[role]
    state=safe(b['state_root'])/role;require(state.is_dir(),'capture first')
    ref={'path':str(safe(review)),'sha256':review_pin};plan=load(job['training_plan']['path'],job['training_plan']['sha256'])
    review_check(state,ref,b,job,plan)
    target=state/'REVIEW-REFERENCE.json'
    value=dict(ref,handoff_sha256=pin,role=role,scope='CPU prepare only; no evaluation launch')
    if target.exists():require(load(target)==value,'different review already injected')
    else:write(target,value,exclusive=True)
    return {'status':'review_injected','role':role,'evaluation_authorized':False}

def prepare(state,binding,job,plan):
    ref=load(state/'REVIEW-REFERENCE.json')
    require(ref['handoff_sha256']==binding['_pin'] and ref['role']==job['role'],'injected review scope changed')
    captured,review=review_check(state,ref,binding,job,plan)
    out=safe(job['fresh_eval_out'])
    if (state/'PREPARED.json').exists():
        receipt=load(state/'PREPARED.json')
        require(receipt['review_sha256']==ref['sha256'] and receipt['plan']==str(out/'plan.json')
            and sha(receipt['plan'])==receipt['sha256'],'prepared receipt changed');return receipt
    require(not (state/'PREPARE_INTENT.json').exists(),'uncertain binder attempt; explicit repair required')
    require(not out.exists(),'evaluation output exists; never adopt or clobber')
    binder=module(binding['_binder'],binding['source_files'][binding['_binder']])
    write(state/'PREPARE_INTENT.json',dict(review_sha256=ref['sha256'],binding_sha256=binding['_pin'],
        output=str(out),attempt=1),exclusive=True)
    result=binder.prepare(Path(job['training']),Path(binding['closure']['path']).parent,out)
    require(result.get('status')=='prepared','binder did not prepare')
    review_check(state,ref,binding,job,plan);identity(binding['_path'],binding['_pin'])
    spec=load(out/'plan.json')
    require(spec['training']==job['training'] and spec['adapter']==job['new_adapter']
        and spec['training_variant']['training_plan_sha256']==job['training_plan']['sha256']
        and spec['training_variant']['formal_role_identity']['role']==job['role']
        and all(spec['files'].get(p)==h for p,h in captured['adapter_files'].items())
        and spec['execution_review']==spec['chip_assignment']=='PENDING'
        and spec['test_read'] is False and spec['scientific_acceptance'] is False,'generated specification differs')
    require(result['plan']==str(out/'plan.json') and result['sha256']==sha(out/'plan.json'),'binder receipt differs')
    result.update(role=job['role'],review_sha256=ref['sha256'],evaluation_authorized=False,
        scientific_acceptance=False,test_read=False,chip=job['chip'],launch_dependencies=job['launch_dependencies'])
    write(state/'PREPARED.json',result,exclusive=True);return result

def cycle(path,pin):
    b,jobs,_=identity(path,pin);root=safe(b['state_root']);root.mkdir(parents=True,exist_ok=True);states={}
    for role,job in jobs.items():
        state=root/role;state.mkdir(exist_ok=True)
        try:
            if (state/'FAILURE.json').exists():
                states[role]=load(state/'FAILURE.json');continue
            p=load(job['training_plan']['path'],job['training_plan']['sha256'])
            if (state/'CAPTURE.json').exists():
                value=load(state/'CAPTURE.json');check_capture(value,b,job,p)
            else:
                value=capture(b,job,p)
                if value['status']=='REVIEW_REQUIRED':write(state/'CAPTURE.json',value,exclusive=True)
            if value['status']=='REVIEW_REQUIRED' and (state/'REVIEW-REFERENCE.json').exists():value=prepare(state,b,job,p)
            states[role]={k:v for k,v in value.items() if k in ('status','role','exit_code','plan','sha256')}
        except Exception as error:
            states[role]=dict(status='needs_repair',error_type=type(error).__name__,reason=str(error)[:240],automatic_retry=False)
            write(state/'FAILURE.json',states[role],exclusive=True)
        if states[role]['status'] in ('prepared','training_failed','needs_repair'):
            terminal=state/'EXIT.json';value=dict(states[role],exit_code=int(states[role]['status']!='prepared'),test_read=False,evaluation_authorized=False)
            if terminal.exists():require(load(terminal)==value,'terminal changed')
            else:write(terminal,value,exclusive=True)
    digest=dict(utc_seconds=time.time(),jobs=states,test_read=False,scientific_acceptance=False,evaluation_authorized=False)
    write(root/'digest.json',digest);write(root/'heartbeat.json',dict(digest,progress_count=sum(x['status']=='prepared' for x in states.values())))
    return b,digest

def watch(path,pin,once=False):
    b=load(path,pin);root=safe(b['state_root']);root.mkdir(parents=True,exist_ok=True)
    with (root/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not (root/'FAILURE.json').exists(),'prior global failure requires explicit repair')
        try:
            while True:
                b,d=cycle(path,pin)
                if all(x['status'] in ('prepared','training_failed','needs_repair') for x in d['jobs'].values()):
                    end=dict(d,exit_code=int(any(x['status']!='prepared' for x in d['jobs'].values())))
                    if (root/'EXIT.json').exists():
                        old=load(root/'EXIT.json');require(old['jobs']==end['jobs'],'handoff terminal changed')
                    else:write(root/'EXIT.json',end,exclusive=True)
                    return d
                if once:return d
                time.sleep(b['poll_interval_seconds'])
        except Exception as error:
            end=dict(status='needs_repair',error_type=type(error).__name__,reason=str(error)[:240],
                exit_code=1,automatic_retry=False,evaluation_authorized=False,test_read=False)
            write(root/'FAILURE.json',end,exclusive=True)
            if not (root/'EXIT.json').exists():write(root/'EXIT.json',end,exclusive=True)
            raise


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=('validate','watch','inject-review'))
    ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--once',action='store_true')
    ap.add_argument('--role',choices=ROLES);ap.add_argument('--review');ap.add_argument('--review-sha256');a=ap.parse_args()
    if a.op=='validate':identity(a.config,a.sha256);result={'status':'valid_cpu_prepare_only'}
    elif a.op=='inject-review':
        require(a.role and a.review and a.review_sha256,'role and externally authenticated review required')
        result=inject(a.config,a.sha256,a.role,a.review,a.review_sha256)
    else:result=watch(a.config,a.sha256,a.once)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
