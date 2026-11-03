#!/usr/bin/env python3
"""Exact successful-training or successful-DEV to DEV handoff; never grants scientific eligibility.

Only new prospective execution packages may opt into this guard. No running
training plan is changed. The resource adapter calls claim_precondition twice
while holding its allocation flock. Unknown starts require reconciliation.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def require(ok, why):
    if not ok: raise RuntimeError(why)


def raw(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p.read_bytes()


def sha(path): return hashlib.sha256(raw(path)).hexdigest()
def read(path): return json.loads(raw(path))
def pinned(ref):
    require(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'], 'source pin differs')
    return Path(ref['path'])


def module(ref):
    p=pinned(ref);s=importlib.util.spec_from_file_location('formal_dev_'+p.stem,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def put(path,value,exclusive=False):
    p=Path(path);b=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    q=p.with_name(p.name+'.pending')
    with q.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    if exclusive:os.link(q,p);q.unlink()
    else:os.replace(q,p)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def binding(p):
    g=p['successor_guard']
    require(g['identity_mode']=='sha256_raw' and g['controller']==str(Path(__file__).resolve()), 'guard identity differs')
    require(p['adapter']==p['resource_adapter'] and p['files']==p['tools'], 'resource guard tool aliases differ')
    for path,h in p['tools'].items():require(sha(path)==h,'execution tool changed')
    spec=read(p['spec']);require(sha(p['spec'])==p['spec_sha256'],'spec changed')
    core=module(g['training_evidence'])
    if g.get('predecessor_kind') == 'evaluation':
        return evaluation_binding(p, spec, core)
    require(g.get('predecessor_kind', 'training') == 'training', 'unknown predecessor kind')
    schedule=read(pinned(g['schedule']));ref=g['previous_training'];previous=core.load(ref['plan'],ref['plan_raw_sha256'])
    require(core.identity(previous)==ref['plan_sha256'] and previous['schema']=='r3-formal-k1-plan-v1'
            and previous.get('control_arm') is None and previous['test_read'] is False
            and previous['scientific_acceptance'] is False,'previous training identity differs')
    require(previous['formal_role']==g['previous_role'] and previous['formal_schedule_sha256']==g['schedule']['sha256']
            and previous['formal_schedule']==g['schedule']['path'],'previous schedule differs')
    nodes={n['id']:n for n in schedule['nodes']};node=nodes[g['target_node']]
    require(node['kind']=='dev_calibration_track_t_readout' and node['depends_on']==[g['previous_role']+'_release']
            and node['training_id']==g['training_role'] and node['chip']==p['chip']==previous['chip'], 'registered DEV edge differs')
    role=spec['training_variant']['formal_role_identity']
    require(role['role']==g['training_role'] and role['schedule_sha256']==g['schedule']['sha256']
            and role['chip']==p['chip'] and spec['training']==nodes[g['training_role']]['out'], 'DEV candidate differs')
    require(previous['out']==nodes[g['previous_role']]['out'] and Path(ref['plan']).parent==Path(previous['out']), 'previous role path differs')
    for k in ('launcher','adapter','driver'):core.content(previous[k],previous['files'][previous[k]])
    core.source(previous['launcher'],previous['files'][previous['launcher']]).formal_target_identity(previous)
    return core,previous


def normalized_spec(spec, original, actual_out, original_out):
    """Only declared source-copy paths and two output argv operands may differ."""
    value=json.loads(json.dumps(spec))
    mounts={m['destination']:m for m in original['code_mounts']}
    require(len(mounts)==len(original['code_mounts'])==len(value['code_mounts']), 'source mount count differs')
    mapping={}
    for m in value['code_mounts']:
        require(m['destination'] in mounts, 'source mount destination differs')
        old=mounts[m['destination']]
        require({k:v for k,v in m.items() if k!='source'}=={k:v for k,v in old.items() if k!='source'}, 'source mount policy differs')
        mapping[m['source']]=old['source'];m['source']=old['source']
    files={}
    for path,h in value['files'].items():
        matches=[(a,b) for a,b in mapping.items() if Path(path).is_relative_to(a)]
        require(len(matches)<=1, 'overlapping source mounts')
        new=str(Path(matches[0][1])/Path(path).relative_to(matches[0][0])) if matches else path
        require(new not in files, 'source alias collision');files[new]=h
    value['files']=files
    for flag,leaf in (('--out','results'),('--round-dir','identity')):
        require(value['command'].count(flag)==1, 'output flag differs');i=value['command'].index(flag)+1
        require(value['command'][i]==str(Path(actual_out)/leaf), 'actual output differs')
        value['command'][i]=str(Path(original_out)/leaf)
    require(value==original, 'predecessor changed beyond source/output relocation')
    return value


def evaluation_binding(p,spec,core):
    g=p['successor_guard'];ref=g['previous_evaluation'];path=pinned(ref['execution']);previous=read(path)
    launcher=module({'path':previous['launcher'],'sha256':previous['tools'][previous['launcher']]})
    launcher.verify(path,ref['execution']['sha256'])
    require(previous['out']==str(path.parent) and previous['test_read'] is False
            and previous['scientific_acceptance'] is False,'previous evaluation scope differs')
    schedule=read(pinned(g['schedule']));nodes={n['id']:n for n in schedule['nodes']}
    node=nodes[g['target_node']];priornode=nodes[g['previous_role']+'_dev']
    require(node['kind']==priornode['kind']=='dev_calibration_track_t_readout'
            and node['depends_on']==[g['previous_role']+'_dev_release']
            and node['training_id']==g['training_role'] and priornode['training_id']==g['previous_role']
            and node['chip']==priornode['chip']==p['chip']==previous['chip'], 'registered evaluation edge differs')
    prior_spec=read(previous['spec']);original_path=pinned(ref['original_spec']);original=read(original_path)
    require(str(original_path)==str(Path(priornode['out'])/'plan.json'), 'original DEV location differs')
    for current,role_name in ((spec,g['training_role']),(prior_spec,g['previous_role']),(original,g['previous_role'])):
        identity=current['training_variant']['formal_role_identity']
        require(identity['role']==role_name and identity['schedule_sha256']==g['schedule']['sha256']
                and identity['chip']==p['chip'] and current['training']==nodes[role_name]['out'], 'evaluation role identity differs')
    normalized_spec(prior_spec,original,previous['out'],priornode['out'])
    derivation=read(pinned(ref['derivation']))
    require(derivation['new_execution']==ref['execution']
            and derivation['new_spec']=={'path':previous['spec'],'sha256':previous['spec_sha256']}, 'predecessor derivation differs')
    return core,previous


def evaluation_predecessor(p,resource,core,previous):
    ref=p['successor_guard']['previous_evaluation'];root=Path(previous['out'])
    # Formal roles are attempt1-only. A later directory/receipt is not a successful old generation.
    attempts=root/'attempts'
    if attempts.exists():
        require(sorted(x.name for x in attempts.iterdir())==['1']
                and (attempts/'1').is_dir() and not (attempts/'1').is_symlink(), 'unexpected evaluation attempts')
    marker=root/'ENGINEERING_EVAL_EXIT.json'
    if marker.exists():
        end=read(marker)
        require(type(end.get('attempt')) is int and end['attempt']==1
                and type(end.get('exit_code')) is int and end['exit_code']==0
                and end.get('scientific_acceptance') is False
                and end.get('source')!='retained-container-exit', 'evaluation predecessor failed or synthetic')
    evidence=core.predecessor({'previous_execution':ref['execution']['path'],
                              'previous_execution_sha256':ref['execution']['sha256']},resource)
    if evidence is None:return None
    require(evidence['attempt']==1, 'wrong evaluation attempt')
    claim=root/'attempts/1/CLAIM.json';release=read(root/'attempts/1/RELEASE.json')
    require(release.get('claim_sha256')==sha(claim),'evaluation release claim binding differs')
    if previous.get('successor_guard'):
        pre=root/'SUCCESSOR_PRECONDITION.json';claim_doc=read(claim)
        require(claim_doc['successor_precondition']['precondition_sha256']==sha(pre)
                and read(pre)['execution_sha256']==ref['execution']['sha256'],'predecessor own claim binding differs')
    require(not attempts.exists() or sorted(x.name for x in attempts.iterdir())==['1'], 'evaluation attempt inventory changed')
    return evidence


def predecessor(p,resource):
    core,previous=binding(p)
    if p['successor_guard'].get('predecessor_kind') == 'evaluation':
        return evaluation_predecessor(p,resource,core,previous)
    return core.training_predecessor_evidence(p['successor_guard']['previous_training'],previous,resource)


def claim_precondition(p,plan_pin,precondition_pin,allocation,resource):
    execution=Path(p['out'])/'execution.json'
    require(sha(execution)==plan_pin and read(execution)==p,'claim execution differs')
    pre=Path(p['out'])/'SUCCESSOR_PRECONDITION.json'
    require(sha(pre)==precondition_pin,'precondition changed');value=read(pre)
    require(value['execution_sha256']==plan_pin,'precondition execution differs')
    current=predecessor(p,resource)
    require(current is not None and current==value['previous'],'training evidence changed at claim')
    free=[x for x in allocation['free'] if x['chip']==p['chip']]
    require(not any(x['chip']==p['chip'] for x in allocation['allocation'])
            and free==[current['free_entry']]==[value['free_entry']], 'free predecessor generation differs')
    require(resource.docker_inspect(p['container']+'-a1') is None
            and not resource.live_chip_conflict(p['chip'],None),'live target or competing device holder')
    require(sha(execution)==plan_pin and sha(pre)==precondition_pin,'claim identity changed')
    return dict(precondition_sha256=precondition_pin,previous=current,free_entry=free[0])


def verify(path,pin):
    require(sha(path)==pin,'config changed');c=read(path)
    require(c['schema']=='r3-formal-dev-successor-v1' and type(c['poll_interval_seconds']) is int
            and c['poll_interval_seconds']>=600 and c['test_read'] is False and c['scientific_acceptance'] is False,'config scope differs')
    expected=hashlib.sha256((json.dumps({k:v for k,v in c.items() if k!='config_identity'},sort_keys=True,indent=2)+'\n').encode()).hexdigest()
    require(c['config_identity']==expected,'config canonical identity differs')
    execution=pinned(c['execution']);p=read(execution)
    launcher=module({'path':p['launcher'],'sha256':p['tools'][p['launcher']]});launcher.verify(execution,c['execution']['sha256'])
    binding(p);module(c['wake_source']);return c,p,launcher


def authorize(c,ref):
    a=read(pinned(ref));require(a['schema']=='r3-formal-dev-activation-v1' and a['execution']==c['execution']
        and a['config']==c['config_identity'] and a['launch_authorized'] is True and a['test_read'] is False,'activation differs')
    r=read(pinned(a['review']));require(r['verdict']=='PASS' and r['execution']==c['execution']
        and r['config']==c['config_identity'],'exact independent review differs')
    # The caller must authenticate who created these externally supplied pins.
    return a


def tick(c,p,launcher):
    state=Path(c['state_root']);intent=state/'START_INTENT.json';receipt=Path(p['out'])/'SUPERVISOR_RECEIPT.json'
    if intent.exists():
        v=read(intent);require(v['execution']==c['execution'],'start intent differs')
        if not receipt.exists():return {'status':'needs_repair','reason':'intent without receipt; never replay'}
        r=read(receipt);core,_=binding(p)
        expected=[sys.executable,'-P',p['launcher'],'supervise','--plan',c['execution']['path'],'--sha256',c['execution']['sha256'],'--attempt','1']
        require(r['command']==expected,'supervisor command differs')
        return {'status':'supervisor_live' if core.process_matches(r) else 'needs_repair','pid':r['pid']}
    require(not receipt.exists(),'target started outside guard')
    resource=launcher.resource_module(p);prior=predecessor(p,resource)
    if prior is None:return {'status':'waiting_successful_evaluation' if p.get('successor_guard',{}).get('predecessor_kind')=='evaluation' else 'waiting_successful_training'}
    allocation=resource.load(p['allocation']);resource.validate_doc(allocation)
    if any(x['chip']==p['chip'] for x in allocation['allocation']):return {'status':'waiting_resource'}
    require([x for x in allocation['free'] if x['chip']==p['chip']]==[prior['free_entry']], 'free lineage differs')
    require(not (Path(p['out'])/'attempts').exists(),'target has prior attempts')
    pre=Path(p['out'])/'SUCCESSOR_PRECONDITION.json'
    put(pre,dict(execution_sha256=c['execution']['sha256'],previous=prior,free_entry=prior['free_entry']),True)
    command=[sys.executable,'-B','-P',p['launcher'],'start','--plan',c['execution']['path'],'--sha256',c['execution']['sha256'],'--attempt','1']
    put(intent,dict(execution=c['execution'],precondition_sha256=sha(pre),command=command),True)
    with (state/'launch.log').open('ab') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1800,
                       env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    return {'status':'launch_requested'}


def watch(path,pin,activation):
    require(socket.gethostname()=='k8s-node1','host175 only');c,p,launcher=verify(path,pin);authorize(c,activation)
    state=Path(c['state_root']);state.mkdir(parents=True,exist_ok=True)
    with (state/'LOCK').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);require(not (state/'EXIT.json').exists(),'watcher terminal; no restart')
        wake=module(c['wake_source']).CompletionWake(c['event_wake_paths'])
        put(state/'RELAUNCH.json',{'command':[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--config',str(path),'--sha256',pin,'--activation',activation['path'],'--activation-sha256',activation['sha256']]})
        try:
            while True:
                c,p,launcher=verify(path,pin);authorize(c,activation)
                result=tick(c,p,launcher);result.update(utc_seconds=time.time(),test_read=False,scientific_acceptance=False)
                put(state/'digest.json',result);put(state/'heartbeat.json',result)
                if result['status'] in ('launch_requested','supervisor_live','needs_repair'):
                    put(state/'EXIT.json',dict(result,exit_code=0 if result['status']!='needs_repair' else 2),True);return
                wake.wait(c['poll_interval_seconds'])
        except BaseException as e:
            put(state/'EXIT.json',dict(exit_code=1,status='blocked_or_uncertain',error=str(e)[:400]),True);raise
        finally:wake.close()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','start','watch']);ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True)
    ap.add_argument('--activation');ap.add_argument('--activation-sha256');a=ap.parse_args()
    c,p,l=verify(a.config,a.sha256)
    if a.op=='verify':print(json.dumps({'status':'FORMAL_DEV_GUARD_VERIFIED','launch_authorized':False}));return
    require(a.activation and a.activation_sha256,'external activation required');ref={'path':a.activation,'sha256':a.activation_sha256};authorize(c,ref)
    if a.op=='watch':return watch(a.config,a.sha256,ref)
    state=Path(c['state_root']);state.mkdir(parents=True,exist_ok=True)
    # Serialize the parent launch transaction and publish intent before Popen.
    # A crash after Popen but before SERVICE.json must remain an uncertain
    # generation requiring reconciliation; a second caller must never spawn a
    # second watcher merely because the service receipt is not present yet.
    with (state/'START.lock').open('a') as start_lock:
        fcntl.flock(start_lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (state/'SERVICE.json').exists() and not (state/'EXIT.json').exists(),
                'watcher previously started; reconcile')
        start_intent=state/'SERVICE_START_INTENT.json'
        require(not start_intent.exists(),'start intent requires reconciliation')
        command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--config',a.config,'--sha256',a.sha256,'--activation',a.activation,'--activation-sha256',a.activation_sha256]
        put(start_intent,dict(schema='r3-formal-dev-start-intent-v1',config={'path':a.config,'sha256':a.sha256},activation={'path':a.activation,'sha256':a.activation_sha256},command=command,utc_seconds=time.time()),True)
        with (state/'watch.log').open('ab') as f:
            child=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        put(state/'SERVICE.json',dict(pid=child.pid,command=command,start_intent=str(start_intent),start_intent_sha256=sha(str(start_intent))),True)
        print(json.dumps({'status':'STARTED','pid':child.pid}))
        return


if __name__=='__main__':main()
