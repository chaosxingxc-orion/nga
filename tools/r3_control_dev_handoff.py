#!/usr/bin/env python3
"""Control CPU capture/review/DEV binder composition; no launch or TEST interface."""
import argparse
import fcntl
import hashlib
import json
import shlex
from pathlib import Path
import sys
import time
import types

ROLES={'qo_s2':('K1-QO',2),'pt_s2':('K1-PT',2),'pt_s3':('K1-PT',3)}


def require(ok,why):
    if not ok:raise ValueError(why)


def safe(path):
    p=Path(path)
    require(p.is_absolute() and str(p)==str(path) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    require(not any(x.lower().split('.')[0]=='test' for x in p.parts),'TEST forbidden')
    return p


def raw(path,pin=None):
    value=safe(path).read_bytes()
    require(pin is None or hashlib.sha256(value).hexdigest()==pin,'pin changed: '+str(path))
    return value


def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()
def load(path,pin=None):return json.loads(raw(path,pin))


def module(ref):
    code=raw(ref['path'],ref['sha256']);m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path']
    exec(compile(code,ref['path'],'exec',dont_inherit=True),m.__dict__);return m


def identity(path,pin):
    b=load(path,pin)
    require(b.get('schema')=='r3-control-dev-handoff-v1' and b.get('test_read') is False
            and b.get('scientific_acceptance') is False and b.get('evaluation_authorized') is False,'scope differs')
    require(b['controller']==str(Path(__file__).resolve()) and sha(b['controller'])==b['controller_sha256'],'controller differs')
    require(type(b['poll_interval_seconds']) is int and b['poll_interval_seconds']>=600,'cadence differs')
    require(b['deployment']['python']=='/usr/bin/python3.11','deployment interpreter differs')
    for ref in b['sources'].values():raw(ref['path'],ref['sha256'])
    q=load(b['queue']['path'],b['queue']['sha256'])
    require(q['schema']=='r3-formal-control-successor-v1','control queue differs')
    closure=load(b['closure']['path'],b['closure']['sha256'])
    require(closure['evaluation_profile']=='track_kt','combined DEV closure required')
    require(len(b['jobs'])==3 and {j['role'] for j in b['jobs']}==set(ROLES)
            and len({j['out'] for j in b['jobs']})==3,'three distinct control outputs required')
    Q=module(b['sources']['qualifier']);jobs={};state=safe(b['state_root'])
    H=module(b['sources']['handoff'])
    for item in b['jobs']:
        role=item['role'];p=load(item['training_plan']['path'],item['training_plan']['sha256'])
        require((Q.label(p),p['seed'])==ROLES[role] and p['out']==item['training'],'control identity differs')
        matches=[j for j in q['jobs'] if j['plan']==item['training_plan']['path']]
        require(len(matches)==1,'queue member differs');j=matches[0]
        require(j['raw_sha256']==item['training_plan']['sha256'] and j['arm']==ROLES[role][0]
                and j['canonical_sha256']==Q.ledger_digest(dict(p,review_sha256='PENDING')),'queue plan binding differs')
        review=load(p['review_path'],p['review_sha256'])
        require(review.get('verdict')=='PASS' and review.get('approved_plan_sha256')==j['canonical_sha256'],'exact review differs')
        training=safe(p['out']);out=safe(item['out'])
        require(item['training_plan']['path']==str(training/'plan.json') and 'successor_guard' not in p,'unexpected control plan interface')
        require(not any(a==c or a.is_relative_to(c) or c.is_relative_to(a) for a,c in ((state,training),(state,out),(training,out))),'state/output overlaps')
        jobs[role]=dict(role=role,seed=p['seed'],training=p['out'],new_adapter=str(training/'adapter'),
            queue_job=j,canonical_plan_sha256=j['canonical_sha256'],required_final_step=3116,training_plan=item['training_plan'],
            fresh_eval_out=str(out),late_bound_hashes=H.LATE,chip=p['chip'],launch_dependencies=item['launch_dependencies'])
    b.update(_pin=pin,_path=str(path));return b,jobs,q


def prerequisite(binding,job,plan):
    """Validate immutable claim-time proof; never consult today's free ledger."""
    root=safe(job['training']);claim=load(root/'attempts/1/CLAIM.json')
    q=load(binding['queue']['path'],binding['queue']['sha256']);j=job['queue_job']
    require(j in q['jobs'] and j['plan']==job['training_plan']['path']
            and j['canonical_sha256']==job['canonical_plan_sha256'],'prerequisite queue member differs')
    guard=claim.get('successor_precondition')
    require(isinstance(guard,dict) and guard.get('config_sha256')==binding['queue']['sha256']
            and guard.get('job')==j['id'] and guard.get('canonical_sha256')==j['canonical_sha256'],
            'claim prerequisite identity missing or differs')
    prev=guard.get('previous',{});free=guard.get('free_entry',{});pins=prev.get('hashes',{})
    require(pins and free==prev.get('free_entry') and free.get('chip')==plan['chip']
            and free.get('previous_run')==prev.get('run') and free.get('release_evidence')==prev.get('release_path'),
            'prerequisite free-entry binding differs')
    prior=j['previous'];extra={}
    if prior['kind']=='evaluation':
        require(pins.get(prior['path'])==prior['sha256'],'prerequisite evaluation identity differs')
        previous_plan=load(prior['path'],prior['sha256']);previous_root=safe(prior['path']).parent
        require(type(prev.get('attempt')) is int and prev['attempt']>=1,'prerequisite attempt differs')
        attempt=prev['attempt'];terminal=previous_root/'ENGINEERING_EVAL_EXIT.json'
    else:
        require(prior['kind']=='control' and prev.get('status')=='completed','prerequisite control incomplete')
        matches=[x for x in q['jobs'] if x['id']==prior['job']];require(len(matches)==1,'prerequisite control unknown')
        pj=matches[0];previous_plan=load(pj['plan'],pj['raw_sha256']);extra[pj['plan']]=pj['raw_sha256']
        previous_root=safe(previous_plan['out']);attempt=1;terminal=previous_root/'TRAIN_EXIT.json'
    a=previous_root/'attempts'/str(attempt)
    paths=[terminal,a/'EXIT.json',a/'CLAIM.json',a/'RELEASE.json',a/'LAUNCH_RECEIPT.json',a/'SUPERVISOR_DONE.json']
    require(all(str(p) in pins for p in paths),'prerequisite evidence inventory incomplete')
    require(all(sha(p)==h for p,h in pins.items()),'prerequisite evidence changed')
    end,local,old_claim,release,launch,done=[load(p,pins[str(p)]) for p in paths]
    require(end==local and type(end.get('exit_code')) is int and end['exit_code']==0
            and release.get('exit_code')==done.get('exit_code')==0
            and release.get('scientific_acceptance') is False and done.get('scientific_acceptance') is False,
            'prerequisite terminal differs')
    require(prev.get('run')==previous_plan['run']==old_claim.get('run')==release.get('run')
            and previous_plan['chip']==plan['chip']==old_claim.get('chip')==release.get('chip')
            and release.get('container')==previous_plan['container']+'-a'+str(attempt)
            and release.get('container_id')==launch.get('id')==prev.get('container_id')
            and prev.get('release_path')==str(a/'RELEASE.json'), 'prerequisite ownership differs')
    require([x for x in release.get('allocation_after',{}).get('free',[]) if x.get('chip')==plan['chip']]==[free]
            and not any(x.get('chip')==plan['chip'] for x in release['allocation_after'].get('allocation',[])),
            'prerequisite free-entry not in release')
    if prior['kind']=='control':
        require(release.get('claim_sha256')==pins[str(a/'CLAIM.json')]
                and launch.get('plan_sha256')==pj['canonical_sha256'],'prerequisite control claim differs')
    return dict(pins,**extra)


def configured_handoff(binding):
    H=module(binding['sources']['handoff'])
    # Actual control launchers use the separately pinned control queue, with
    # prerequisite proof inside CLAIM.json; they do not emit the K1 guard file.
    H.EXTRA=[x for x in H.EXTRA if x!='SUCCESSOR_PRECONDITION.json']
    base_capture=H.capture
    def capture(b,job,plan):
        result=base_capture(b,job,plan)
        names=job['late_bound_hashes']+H.EXTRA
        if result['status'].startswith('waiting_'):
            result['missing']=[str(Path(job['training'])/n) for n in names if not safe(Path(job['training'])/n).is_file()]
        if result['status']=='REVIEW_REQUIRED':
            result['files'].update(prerequisite(b,job,plan))
            Q=module(b['sources']['qualifier']);Q.label(plan)
            binder=module(b['sources']['binder']);manifest=H.load(Path(job['training'])/'manifest.json')
            require(binder.semantic_arm(dict(plan,arm=Q.actual_arm(plan)),manifest)==ROLES[job['role']][0],'manifest control differs')
        return result
    base_review_check=H.review_check
    def review_check(state,ref,b,job,plan):
        captured,review=base_review_check(state,ref,b,job,plan)
        require(review.get('checks',{}).get('control_prerequisite_identity_and_release') is True,
                'independent prerequisite verification incomplete')
        return captured,review
    H.review_check=review_check
    H.capture=capture
    H.identity=identity
    H.prepare=lambda state,b,job,p:prepare(state,b,job,p,H)
    return H


def prepare(state,binding,job,plan,H=None):
    H=configured_handoff(binding) if H is None else H
    ref=H.load(state/'REVIEW-REFERENCE.json')
    require(ref['handoff_sha256']==binding['_pin'] and ref['role']==job['role'],'review reference differs')
    captured,_=H.review_check(state,ref,binding,job,plan);out=safe(job['fresh_eval_out'])
    if (state/'PREPARED.json').exists():
        receipt=H.load(state/'PREPARED.json')
        require(receipt['review_sha256']==ref['sha256'] and receipt['plan']==str(out/'plan.json')
                and H.sha(out/'plan.json')==receipt['sha256'],'prepared receipt differs');return receipt
    require(not (state/'PREPARE_INTENT.json').exists(),'uncertain binder attempt; explicit repair required')
    require(not out.exists(),'output exists; never adopt or clobber')
    binder=module(binding['sources']['binder']);Q=module(binding['sources']['qualifier'])
    original=binder.semantic_arm
    def semantic(p,m):
        require(p==plan and Q.label(p)==ROLES[job['role']][0],'binder control plan differs')
        return original(dict(p,arm=Q.actual_arm(p)),m)
    binder.semantic_arm=semantic
    H.write(state/'PREPARE_INTENT.json',dict(review_sha256=ref['sha256'],binding_sha256=binding['_pin'],output=str(out),attempt=1),exclusive=True)
    result=binder.prepare(Path(job['training']),Path(binding['closure']['path']).parent,out)
    require(result['status']=='prepared','binder not prepared')
    H.review_check(state,ref,binding,job,plan);identity(binding['_path'],binding['_pin'])
    spec=H.load(out/'plan.json');arm=ROLES[job['role']][0]
    require(spec['training']==job['training'] and spec['adapter']==job['new_adapter']
            and spec['training_variant']['arm']==arm.lower() and spec['training_variant']['seed']==job['seed']
            and spec['training_variant']['training_plan_sha256']==job['training_plan']['sha256']
            and spec['command'][spec['command'].index('--arm')+1]==arm
            and all(spec['files'].get(p)==h for p,h in captured['adapter_files'].items())
            and spec['execution_review']==spec['chip_assignment']=='PENDING'
            and spec['test_read'] is False and spec['scientific_acceptance'] is False,'generated control spec differs')
    require(result['plan']==str(out/'plan.json') and result['sha256']==H.sha(out/'plan.json'),'binder receipt differs')
    result.update(role=job['role'],review_sha256=ref['sha256'],evaluation_authorized=False,scientific_acceptance=False,
                  test_read=False,launch_dependencies=job['launch_dependencies'])
    H.write(state/'PREPARED.json',result,exclusive=True);return result


def inspect(path,pin):
    b,jobs,_=identity(path,pin);H=configured_handoff(b)
    return {'jobs':{role:H.capture(b,j,load(j['training_plan']['path'],j['training_plan']['sha256'])) for role,j in jobs.items()},
            'test_read':False,'evaluation_authorized':False,'scientific_acceptance':False}


def inject(path,pin,role,review,review_pin):
    b,_,_=identity(path,pin);return configured_handoff(b).inject(path,pin,role,review,review_pin)


def cycle(path,pin,H):
    b,d=H.cycle(path,pin)
    # Retain specific dependencies in the bounded digest; the reused wave
    # cycle intentionally kept only coarse state names. No missing artifact
    # is generated here and no terminal/review flag is inferred from presence.
    _,jobs,_=identity(path,pin)
    for role,value in d['jobs'].items():
        if value['status'].startswith('waiting_'):
            job=jobs[role]
            value['missing']=[str(Path(job['training'])/name) for name in job['late_bound_hashes']+H.EXTRA
                              if not safe(Path(job['training'])/name).is_file()]
        elif value['status']=='REVIEW_REQUIRED':
            value['missing']=[str(Path(b['state_root'])/role/'REVIEW-REFERENCE.json')]
    root=safe(b['state_root'])
    H.write(root/'digest.json',d)
    H.write(root/'heartbeat.json',dict(d,progress_count=sum(x['status']=='prepared' for x in d['jobs'].values())))
    return b,d


def invocation(binding,path,pin):
    root=safe(binding['state_root']);python=binding['deployment']['python']
    require(safe(python).is_file(),'deployment interpreter absent')
    command=[python,'-B','-P',binding['controller'],'watch','--config',str(path),'--sha256',pin]
    log=root/'watch.log'
    detached='mkdir -p '+shlex.quote(str(root))+' && nohup '+shlex.join(command)+' >> '+shlex.quote(str(log))+' 2>&1 < /dev/null &'
    return dict(command=command,detached_command=detached,durable_log=str(log),terminal=str(root/'EXIT.json'),
                heartbeat=str(root/'heartbeat.json'),exclusive_identity=str(root/'watch.lock'),
                relaunch_policy='Use exact detached command only after reconciling absent live watcher; terminal or uncertain prepare intent requires new reviewed generation.')


def watch(path,pin,once=False):
    b,_,_=identity(path,pin);H=configured_handoff(b);root=safe(b['state_root']);root.mkdir(parents=True,exist_ok=True)
    with (root/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not (root/'EXIT.json').exists() and not (root/'FAILURE.json').exists(),'terminal watcher cannot restart')
        H.write(root/'RELAUNCH.json',invocation(b,path,pin))
        Wake=module(b['sources']['wake']).CompletionWake
        wakes=[str(Path(j['training'])/n) for j in b['jobs'] for n in ('TRAIN_EXIT.json','attempts/1/RELEASE.json')]
        wakes += [str(root/j['role']/'REVIEW-REFERENCE.json') for j in b['jobs']]
        wake=Wake(wakes)
        try:
            while True:
                _,d=cycle(path,pin,H)
                print(json.dumps({'utc_seconds':time.time(),'jobs':{k:v['status'] for k,v in d['jobs'].items()}}),flush=True)
                if all(v['status'] in ('prepared','training_failed','needs_repair') for v in d['jobs'].values()):
                    H.write(root/'EXIT.json',dict(d,exit_code=int(any(v['status']!='prepared' for v in d['jobs'].values()))),exclusive=True);return d
                if once:return d
                wake.wait(b['poll_interval_seconds'])
        except BaseException as exc:
            if not (root/'EXIT.json').exists():H.write(root/'EXIT.json',{'exit_code':1,'status':'needs_repair','error':str(exc)[:240]},exclusive=True)
            raise
        finally:wake.close()


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=('validate','inspect','watch','inject-review'))
    ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--once',action='store_true')
    ap.add_argument('--role',choices=ROLES);ap.add_argument('--review');ap.add_argument('--review-sha256');a=ap.parse_args(argv)
    if a.op=='validate':identity(a.config,a.sha256);result={'status':'valid_cpu_prepare_only'}
    elif a.op=='inspect':result=inspect(a.config,a.sha256)
    elif a.op=='inject-review':
        require(a.role and a.review and a.review_sha256,'independent review pin required');result=inject(a.config,a.sha256,a.role,a.review,a.review_sha256)
    else:result=watch(a.config,a.sha256,a.once)
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
