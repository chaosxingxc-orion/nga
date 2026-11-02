#!/usr/bin/env python3
"""Freeze once, prepare/review primaries, then auxiliaries; never launches.

Only externally authenticated review artifacts may be supplied to attach. Hash
verification binds bytes, not author identity. No review is generated here.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types

ROLES=('primary_s2','primary_s3','samechip_s2','diffchip_s2')
PRIMARY=ROLES[:2]; AUX=ROLES[2:]
POLICY='requested-astra-parent-pinned-v1'
COLLAB_POLICY='requested-astra-collaboration-parent-pinned-v2'
TOOL_NAMES=('r3_formal_wave_prepare.py','r3_formal_wave_handoff.py','r3_formal_prepare.py',
 'r3_formal_train_successor.py','r3_formal_roles.py','r3_formal_launcher.py','r3_formal_driver.py',
 'r3_resource_adapter.py','r3_fresh_prechecks.py','r3_training_evidence.py',
 'r3_resume_evidence.py','r3_resume_reconstruction_evidence.py','r3_resume_recompute.py',
 'r3_posttrain_eval_plan.py')
SOURCE_NAMES=tuple('tools/'+n for n in TOOL_NAMES)+(
 'experiments/r3_sft/r3_code/train_r3.py','experiments/r3_sft/r3_code/build_kev_sft.py',
 'experiments/r3_sft/r3_code/kev_aug.py','experiments/r0_baseline/prompt.py',
 '.local/archive/2026-10-31/experiments/R3-SFT-PREREG.md',
 '.local/archive/2026-10-31/experiments/R3-TRAINING-WAVE-PREREG-2026-10-31.md')

def require(ok,why):
    if not ok: raise ValueError(why)

def safe(path):
    p=Path(path)
    require(p.is_absolute() and str(p)==str(path) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    require(not any(x.lower().split('.')[0]=='test' for x in p.parts),'TEST path forbidden')
    return p

def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def raw(doc):return (json.dumps(doc,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()

def load(path,pin=None):
    p=safe(path);b=p.read_bytes()
    require(len(b)<=8*2**20,'metadata too large')
    require(pin is None or hashlib.sha256(b).hexdigest()==pin,'pin changed: '+str(p))
    return json.loads(b)

def write(path,doc,replace=False):
    p=safe(path);b=raw(doc);temp=p.with_suffix(p.suffix+'.pending') if replace else p
    with temp.open('wb' if replace else 'xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    if replace:temp.replace(p)
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def module(path,pin):
    p=safe(path);code=p.read_bytes();require(hashlib.sha256(code).hexdigest()==pin,'source changed')
    m=types.ModuleType(p.stem);m.__file__=str(p)
    exec(compile(code,str(p),'exec',dont_inherit=True),m.__dict__);return m

def freeze(request,pin):
    d=load(request,pin);require(d['schema']=='r3-formal-wave-request-v1','request schema')
    repo=safe(d['repository']);root=safe(d['target_root'])
    require(not root.exists(),'fresh generation required')
    require(set(d['source_sha256'])==set(SOURCE_NAMES),'exact preparation source closure required')
    require(d['review_policy'] in (POLICY,COLLAB_POLICY) and type(d['poll_interval_seconds']) is int
            and d['poll_interval_seconds']>=600,'review policy/cadence differs')
    if d['review_policy']==COLLAB_POLICY:
        authority=d.get('review_authority',{})
        require(set(authority)=={'parent_agent_id','producer_agent_id'}
                and all(isinstance(x,str) and x for x in authority.values())
                and authority['parent_agent_id']!=authority['producer_agent_id'],
                'parent/producer authority separation required')
    for rel,h in d['source_sha256'].items():require(sha(repo/rel)==h,'source changed: '+rel)
    schedule=d['schedule'];roles=module(repo/'tools/r3_formal_roles.py',d['source_sha256']['tools/r3_formal_roles.py'])
    nodes=roles.validate_schedule(schedule)
    require(schedule['target_root']==str(root),'schedule generation differs')
    for role in ROLES:
        require(nodes[role]['out']==str(root/role) and nodes[role+'_dev']['out']==str(root/'evaluations'/role),'schedule path differs')
        if role in PRIMARY:
            ref=schedule['external_predecessors'][role];load(ref['path'],ref['sha256'])
    for k,v in d['inputs'].items():
        if not k.endswith('_sha256'):require(sha(v)==d['inputs'][k+'_sha256'],'input pin changed')
    closure=load(d['closure']['path'],d['closure']['sha256'])
    require(closure.get('evaluation_profile') in ('track_k','track_kt',None),'unsupported DEV closure')
    root.mkdir(parents=True);source=root/'source'
    for rel,h in d['source_sha256'].items():
        target=source/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/rel,target)
        require(sha(target)==h,'source changed during freeze')
    write(root/'SCHEDULE.json',schedule);(root/'guards').mkdir();(root/'stages').mkdir()
    config=dict(schema='r3-formal-staged-wave-v1',root=str(root),source_root=str(source),
        source_files={str(source/rel):h for rel,h in d['source_sha256'].items()},
        schedule={'path':str(root/'SCHEDULE.json'),'sha256':sha(root/'SCHEDULE.json')},
        inputs=d['inputs'],closure=d['closure'],review_policy=d['review_policy'],
        poll_interval_seconds=d['poll_interval_seconds'],test_read=False,scientific_acceptance=False,launch_authorized=False)
    if d['review_policy']==COLLAB_POLICY:config['review_authority']=dict(d['review_authority'])
    write(root/'WAVE.json',config)
    return {'config':str(root/'WAVE.json'),'sha256':sha(root/'WAVE.json'),'status':'source_frozen_no_plans'}

def context(path,pin):
    d=load(path,pin);require(d['schema']=='r3-formal-staged-wave-v1' and d['test_read'] is False
            and d['scientific_acceptance'] is False and d['launch_authorized'] is False,'wave scope differs')
    root=safe(d['root']);source=safe(d['source_root']);require(source==root/'source','source placement differs')
    require(set(d['source_files'])=={str(source/n) for n in SOURCE_NAMES},'source inventory differs')
    for f,h in d['source_files'].items():require(sha(f)==h,'frozen source changed')
    controller=source/'tools/r3_formal_train_successor.py';s=module(controller,d['source_files'][str(controller)])
    roles=module(source/'tools/r3_formal_roles.py',d['source_files'][str(source/'tools/r3_formal_roles.py')])
    schedule=load(d['schedule']['path'],d['schedule']['sha256']);nodes=roles.validate_schedule(schedule)
    require(schedule['target_root']==str(root),'generation changed')
    return d,root,source,s,schedule,nodes

def job_for(root,role,s):
    path=root/role/'plan.json';p=load(path)
    j=dict(id=role,formal_role=role,formal_schedule_sha256=p['formal_schedule_sha256'],
        chip=p['chip'],attempt=1,plan=str(path),plan_sha256=s.identity(p),plan_raw_sha256=sha(path),
        competitors=[],fresh_files=sorted(str(f.relative_to(path.parent)) for f in path.parent.rglob('*') if f.is_file()))
    j.update({k:v for k,v in p['successor_guard'].items() if k.startswith('previous_')})
    if role in AUX:j['depends_on']='primary_s2' if role=='samechip_s2' else 'primary_s3'
    return j

def reviewed_primaries(d,root,s):
    record=load(root/'stages/PRIMARY-ATTACHED.json')
    require(set(record['plans'])==set(PRIMARY),'primary attachment inventory differs')
    for role in PRIMARY:
        j=job_for(root,role,s);require(j['plan_raw_sha256']==record['plans'][role]['raw_sha256'],'attached primary changed')
        s.plan(j,reviewed=True)
    return record

def prepare_stage(path,pin,stage):
    d,root,source,s,schedule,nodes=context(path,pin);selected=PRIMARY if stage=='primary' else AUX
    if stage=='aux':reviewed_primaries(d,root,s)
    else:require(not any((root/r).exists() for r in AUX),'aux already exists; primary stage closed')
    producer=module(source/'tools/r3_formal_prepare.py',d['source_files'][str(source/'tools/r3_formal_prepare.py')])
    producer.ROOT=source # Explicit frozen configuration; no repository source transformation.
    inputs=dict(d['inputs']);inputs['fresh_prechecks']=inputs.pop('fresh_k0_prechecks');inputs['fresh_prechecks_sha256']=inputs.pop('fresh_k0_prechecks_sha256')
    for role in selected:
        receipt=root/'stages'/(role+'-PREPARED.json');out=root/role
        if receipt.exists():
            saved=load(receipt);p=load(out/'plan.json');require(s.identity(p)==saved['canonical_sha256'],'prepared identity changed')
            require(p['review_sha256']=='PENDING' and sha(out/'plan.json')==saved['prepared_raw_sha256'],'review already attached; use validate')
            continue
        intent=root/'stages'/(role+'-PREPARE-INTENT.json')
        require(not intent.exists() and not out.exists(),'uncertain or existing preparation; explicit fresh-generation repair required')
        guard=dict(controller=str(source/'tools/r3_formal_train_successor.py'),
            controller_sha256=d['source_files'][str(source/'tools/r3_formal_train_successor.py')],competitors=[])
        if role in PRIMARY:
            ref=schedule['external_predecessors'][role];guard.update(previous_execution=ref['path'],previous_execution_sha256=ref['sha256'])
        else:
            prior=job_for(root,'primary_s2' if role=='samechip_s2' else 'primary_s3',s)
            guard['previous_training']={k:prior[k] for k in ('plan','plan_sha256','plan_raw_sha256')}
        g=root/'guards'/(role+'.json');write(g,guard)
        write(intent,dict(role=role,config_sha256=pin,started_utc_seconds=time.time()))
        node=nodes[role];producer.prepare(out,node['seed'],node['chip'],formal_chips=tuple(schedule['physical_chips']),
            formal_schedule=d['schedule']['path'],formal_schedule_sha256=d['schedule']['sha256'],formal_role=role,
            successor_guard=str(g),successor_guard_sha256=sha(g),**inputs)
        p=load(out/'plan.json');p['review_policy']=d['review_policy']
        if d['review_policy']==COLLAB_POLICY:p['review_authority']=dict(d['review_authority'])
        write(out/'plan.json',p,replace=True)
        identity=s.identity(p);require(identity==sha(out/'plan.json'),'pending canonical/raw differ')
        (out/'CANONICAL_PLAN_SHA256').write_text(identity+'\n')
        launch=f"ssh npu 'python3.12 -P {p['launcher']} start --plan {out}/plan.json --sha256 {identity}'"
        (out/'LAUNCH_PENDING_REVIEW.txt').write_text(launch+'\n')
        (out/'RELAUNCH.txt').write_text(launch+' # explicit released-attempt resume only\n')
        s.plan(job_for(root,role,s),reviewed=False)
        write(receipt,dict(role=role,canonical_sha256=identity,prepared_raw_sha256=identity,test_read=False,launch_authorized=False))
    bundle=root/'stages'/(stage.upper()+'-PREPARED.json')
    value=dict(schema='r3-formal-staged-review-input-v1',controller=str(source/'tools/r3_formal_train_successor.py'),
        config_sha256=pin,stage=stage,jobs=[job_for(root,r,s) for r in selected],test_read=False,launch_authorized=False)
    if bundle.exists():require(load(bundle)==value,'prepared review input changed')
    else:write(bundle,value)
    return dict(status='review_required',review_input=str(bundle),sha256=sha(bundle),roles=list(selected))

def attach(path,pin,stage,reviews,reviews_pin):
    d,root,source,s,_,_=context(path,pin);selected=PRIMARY if stage=='primary' else AUX
    bundle=load(root/'stages'/(stage.upper()+'-PREPARED.json'));pending={j['id']:j for j in bundle['jobs']}
    ticket=load(reviews,reviews_pin);require(ticket.get('schema')=='r3-authenticated-review-injection-v1'
        and ticket.get('config_sha256')==pin and ticket.get('stage')==stage
        and set(ticket.get('reviews',{}))==set(selected),'review injection identity differs')
    # The caller authenticates the origin. This utility does not infer authorship from hashes.
    done=root/'stages'/(stage.upper()+'-ATTACHED.json')
    if done.exists():
        r=load(done);require(r['injection_sha256']==reviews_pin,'different already attached review')
        for role in selected:
            require(sha(root/role/'plan.json')==r['plans'][role]['raw_sha256'],'attached plan changed')
            s.plan(job_for(root,role,s),reviewed=True)
        return r
    if stage=='primary':require(not any((root/r).exists() for r in AUX),'never change primary after auxiliary creation')
    else:reviewed_primaries(d,root,s)
    candidates={}; review_bytes={}
    for role in selected:
        ref=ticket['reviews'][role];review=load(ref['path'],ref['sha256']);p=load(root/role/'plan.json')
        require(s.identity(p)==pending[role]['plan_sha256'] and p['review_sha256'] in ('PENDING',ref['sha256']),'unexpected plan or attached review')
        candidate=dict(p,review_sha256=ref['sha256']);oldpath=candidate['review_path'];candidate['review_path']=ref['path']
        s.verify_review(candidate,pending[role]['plan_sha256']);candidate['review_path']=oldpath
        require(s.identity(candidate)==pending[role]['plan_sha256'],'review changed canonical identity')
        candidates[role]=candidate;review_bytes[role]=safe(ref['path']).read_bytes()
        require(hashlib.sha256(review_bytes[role]).hexdigest()==ref['sha256'],'review changed during attachment')
    intent=root/'stages'/(stage.upper()+'-ATTACH-INTENT.json')
    iv=dict(injection_sha256=reviews_pin,attached_raw={r:hashlib.sha256(raw(p)).hexdigest() for r,p in candidates.items()})
    if intent.exists():require(load(intent)==iv,'uncertain different attachment')
    else:write(intent,iv)
    for role,p in candidates.items():
        destination=safe(p['review_path'])
        if destination.exists():require(destination.read_bytes()==review_bytes[role],'review destination differs')
        else:
            with destination.open('xb') as f:f.write(review_bytes[role]);f.flush();os.fsync(f.fileno())
        if load(root/role/'plan.json')!=p:write(root/role/'plan.json',p,replace=True)
        s.plan(job_for(root,role,s),reviewed=True)
    value=dict(status='attached',stage=stage,injection_sha256=reviews_pin,
        plans={r:dict(raw_sha256=sha(root/r/'plan.json'),canonical_sha256=s.identity(p)) for r,p in candidates.items()},launch_authorized=False)
    write(done,value);return value

def finalize(path,pin):
    d,root,source,s,_,nodes=context(path,pin);reviewed_primaries(d,root,s)
    for stage,roles in (('PRIMARY',PRIMARY),('AUX',AUX)):
        receipt=load(root/'stages'/(stage+'-ATTACHED.json'))
        for r in roles:require(sha(root/r/'plan.json')==receipt['plans'][r]['raw_sha256'],'final attachment differs')
    jobs=[job_for(root,r,s) for r in ROLES];bindings={d['schedule']['path']:d['schedule']['sha256']}
    for j in jobs:bindings.update(s.plan(j,reviewed=True)['files'])
    controller=str(source/'tools/r3_formal_train_successor.py')
    queue=dict(schema='r3-formal-train-successor-v3',controller=controller,controller_sha256=sha(controller),
        formal_schedule=d['schedule']['path'],formal_schedule_sha256=d['schedule']['sha256'],
        poll_interval_seconds=d['poll_interval_seconds'],test_read=False,scientific_acceptance=False,jobs=jobs,bindings=bindings)
    q=root/'QUEUE-ATTACHED.json'
    if q.exists():require(load(q)==queue,'final queue changed')
    else:write(q,queue)
    s.verify(str(q),sha(q),reviewed=True)
    handoff=dict(schema='r3-formal-wave-handoff-v1',queue={'path':str(q),'sha256':sha(q)},
        source_files=d['source_files'],closure=d['closure'],state_root=str(root/'dev-handoff'),
        poll_interval_seconds=d['poll_interval_seconds'],test_read=False,scientific_acceptance=False,
        evaluation_authorized=False,jobs=[dict(role=r,training=str(root/r),chip=nodes[r]['chip'],
          out=nodes[r+'_dev']['out'],launch_dependencies=nodes[r+'_dev']['depends_on']) for r in ROLES])
    h=root/'DEV-HANDOFF.json'
    if h.exists():require(load(h)==handoff,'handoff changed')
    else:write(h,handoff)
    return dict(status='reviewed_queue_prepared_activation_still_required',queue=str(q),queue_sha256=sha(q),handoff=str(h),handoff_sha256=sha(h))

def validate(path,pin):
    d,root,source,s,_,_=context(path,pin);states={}
    for r in ROLES:
        p=root/r/'plan.json'
        if not p.exists():states[r]='absent';continue
        j=job_for(root,r,s);v=load(p);s.plan(j,reviewed=v['review_sha256']!='PENDING')
        states[r]='review_required' if v['review_sha256']=='PENDING' else 'review_attached'
        if r in AUX:
            reviewed_primaries(d,root,s);s.training_binding(j,v)
    if (root/'QUEUE-ATTACHED.json').exists():s.verify(str(root/'QUEUE-ATTACHED.json'),sha(root/'QUEUE-ATTACHED.json'))
    return dict(status='validated',roles=states,activation_authorized=False)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=('freeze','primary','aux','attach-primary','attach-aux','finalize','validate'))
    ap.add_argument('--request');ap.add_argument('--config');ap.add_argument('--sha256',required=True)
    ap.add_argument('--reviews');ap.add_argument('--reviews-sha256');a=ap.parse_args()
    if a.op=='freeze':result=freeze(a.request,a.sha256)
    else:
        d=load(a.config,a.sha256);root=safe(d['root'])
        with (root/'stages/operation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if a.op in ('primary','aux'):result=prepare_stage(a.config,a.sha256,a.op)
            elif a.op.startswith('attach-'):
                require(a.reviews and a.reviews_sha256,'externally authenticated review injection required')
                result=attach(a.config,a.sha256,a.op[7:],a.reviews,a.reviews_sha256)
            elif a.op=='finalize':result=finalize(a.config,a.sha256)
            else:result=validate(a.config,a.sha256)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
