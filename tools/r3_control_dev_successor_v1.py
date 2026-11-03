#!/usr/bin/env python3
"""Control-training to DEV binding, injected into the unchanged formal guard.

The frozen generic watcher, activation, durable intent and lock-time precondition
remain authoritative. This module supplies only exact control identity and its
already-registered terminal evidence implementation. No new numerical recipe.
"""
import hashlib
import json
from pathlib import Path
import types

CORE_SHA = 'a322ee71c9bc6a7e8238f69fd57b420b3c2fee421701c1fd7bfaa2304ea295f7'

def require(ok, why):
    if not ok: raise RuntimeError(why)

def load_source(path, pin):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(x.is_symlink() for x in (path,*path.parents)), 'unsafe source')
    raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==pin,'source changed')
    m=types.ModuleType(path.stem);m.__file__=str(path)
    exec(compile(raw,str(path),'exec',dont_inherit=True),m.__dict__);return m

def control_binding(p):
    g=p['successor_guard'];C=_core
    require(g['schema']=='r3-control-dev-guard-v1' and g['identity_mode']=='sha256_raw'
            and g['controller']==str(Path(__file__).resolve())
            and g['predecessor_kind']=='control_training','control guard identity differs')
    require(p['adapter']==p['resource_adapter'] and p['files']==p['tools'],'resource aliases differ')
    for name,pin in p['tools'].items():require(C.sha(name)==pin,'execution tool changed')
    require(C.sha(p['spec'])==p['spec_sha256'],'spec changed');spec=C.read(p['spec'])
    original_path=C.pinned(g['original_spec']);original=C.read(original_path)
    C.normalized_spec(spec,original,p['out'],original_path.parent)
    receipt=C.read(C.pinned(g['prepared']))
    require(receipt['status']=='prepared' and receipt['plan']==str(original_path)
            and receipt['sha256']==g['original_spec']['sha256']
            and receipt['role']==g['training_role']
            and receipt['evaluation_authorized']is False and receipt['test_read']is False
            and receipt['scientific_acceptance']is False,'prepared control binding differs')
    ctl=C.module(g['control_controller']);config=C.read(C.pinned(g['control_config']))
    require(config['controller']==g['control_controller'],'control config/controller differs')
    ctl.verify_controller(g['control_config']['path'],g['control_config']['sha256'])
    previous_job=ctl.by_id(config,g['previous_job']);previous=ctl.checked_plan(previous_job)
    target_job=ctl.by_id(config,g['training_job']);target=ctl.checked_plan(target_job)
    require(previous_job['chip']==target_job['chip']==p['chip']==3
            and previous_job['id']=='pt_seed2' and previous_job['arm']=='K1-PT'
            and previous_job['seed']==2 and target_job['id']=='qo_seed2'
            and target_job['arm']=='K1-QO' and target_job['seed']==2
            and previous_job['previous']=={'kind':'control','job':'qo_seed2'},'registered control edge differs')
    require(g['training_role']=='qo_s2' and spec['training']==target['out']
            and spec['training_variant']['arm']=='k1-qo' and spec['training_variant']['seed']==2
            and spec['training_variant']['training_plan_sha256']==target_job['raw_sha256']
            and spec['model']==target['model'] and spec['adapter']==str(Path(target['out'])/'adapter'),
            'control scoring identity differs')
    require(spec['test_read']is False and spec['scientific_acceptance']is False
            and spec['execution_review']==spec['chip_assignment']=='PENDING','scoring authority differs')
    generation=g['previous_generation'];root=Path(previous['out'])
    require(generation['attempt']==1 and generation['plan']=={'path':previous_job['plan'],'sha256':previous_job['raw_sha256']}
            and generation['canonical_plan_sha256']==previous_job['canonical_sha256'],'previous generation plan differs')
    expected={'claim':'attempts/1/CLAIM.json','launch_spec':'attempts/1/LAUNCH_SPEC.json',
              'launch_receipt':'attempts/1/LAUNCH_RECEIPT.json','supervisor':'SUPERVISOR_RECEIPT.json'}
    for key,relative in expected.items():
        require(C.pinned(generation[key])==root/relative,'previous generation path differs')
    launch=C.read(generation['launch_receipt']['path']);claim=C.read(generation['claim']['path'])
    require(generation['container_id']==launch['id'] and launch['plan_sha256']==previous_job['canonical_sha256']
            and claim['chip']==3 and claim['run']==previous['run'],'previous container/claim differs')
    start=C.read(C.pinned(generation['start_observation']))
    require(start['Status']=='running' and start['Running']is True
            and start['StartedAt']==generation['started_at'] and bool(generation['started_at']),
            'previous initial execution generation differs')
    require(sorted(x.name for x in (root/'attempts').iterdir())==['1'],'previous attempt generation changed')
    return ctl,config,previous_job,previous

def binding(p):
    ctl,config,job,previous=control_binding(p)
    return ctl.helper(config),previous

def predecessor(p,resource):
    ctl,config,job,previous=control_binding(p);root=Path(previous['out'])
    if not all((root/n).exists() for n in ['TRAIN_EXIT.json','attempts/1/EXIT.json',
                    'attempts/1/RELEASE.json','attempts/1/SUPERVISOR_DONE.json']):return None
    result=ctl.terminal_control(config,job,previous,resource)
    if result is None or result.get('status') in ('training','waiting_release','waiting_supervisor_exit','supervisor_live'):return None
    require(result.get('status')=='completed','control predecessor failed or uncertain')
    g=p['successor_guard']['previous_generation'];release=_core.read(root/'attempts/1/RELEASE.json')
    require(result['container_id']==g['container_id']==release['container_id']
            and release['container_started_at']==g['started_at']
            and isinstance(release.get('container_finished_at'),str) and bool(release['container_finished_at'])
            and release['container_finished_at']!='0001-01-01T00:00:00Z'
            and release['claim_sha256']==g['claim']['sha256'],'completed control generation differs')
    return result

def configure_core(core):
    # Explicitly composed new implementation; original core bytes stay untouched.
    core.__file__=str(Path(__file__).resolve());core.binding=binding;core.predecessor=predecessor
    return core

_core=configure_core(load_source(Path(__file__).with_name('core_formal_dev_successor.py'),CORE_SHA))
verify=_core.verify
authorize=_core.authorize
claim_precondition=_core.claim_precondition
tick=_core.tick
watch=_core.watch
main=_core.main
if __name__=='__main__':main()
