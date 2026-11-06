#!/usr/bin/env python3
"""CPU receipt-driven consumer; never launches model work or synthesizes review evidence."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('matched_watch_consumer',HERE/'consumer.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def fingerprint(config):
    """Stat only enumerated DEV sources, assets, receipts and readouts; no weights/logs/TEST."""
    paths={HERE/'config.json',HERE/'consumer.py',HERE/'legacy_consumer.py',HERE/'watcher.py',Path(config['review'])}
    paths.update(HERE/'numeric_sources'/(n+'.py') for n in config['numeric_sources'])
    paths.update(Path(p) for p in config['source_pins'])
    paths.add(Path(config['closure'])/'manifest.json')
    for root,name in ((config['k0_root'],'QUEUE-EXIT.json'),(config['adapter_root'],'EXIT.json')):
        paths.add(Path(root)/name);paths.update(Path(root).glob('*-ERROR.json'))
    recovery=Path(config['adapter_root']).parent/'dev-publication-recovery'
    paths.update(recovery.glob('*-disposition.json'))
    paths.add(recovery/'EXIT.json');paths.update(recovery.glob('*-ERROR.json'))
    package=Path(config['adapter_root']).parent/'cpu-separated'
    paths.update(package/n for n in ('queue_proposal.py','phase_wrapper.py','config.json'))
    paths.add(Path(config['adapter_root'])/'REVIEW-APPROVED.json')
    for model in config['models']:paths.update(Path(p) for p in model['asset_pins'])
    for model in config['models']:
        for lane in [None]+[x for x in config['lanes'] if x['baseline_id']==model['id']]:
            d=Path(config['k0_root'])/model['id'] if lane is None else Path(config['adapter_root'])/('full-'+lane['lane'])
            for phase in ('infer','score'):
                paths.update(d/(phase+'-'+kind+'.json') for kind in ('LAUNCH','EXIT','COMMAND',*(() if lane is None else ('BINDING',))))
            run=d/'result';paths.update(run/n for n in ('INFERENCE-READY.json','RUN_IDENTITY.json','clean-report.json' if lane is None else 'report.json'))
            for group in M.CLEAN if lane is None else M.ALL:
                suite,part,kind=group.split('/');p=run/'trackk'/(suite+'__'+part)/(kind+'.jsonl');paths.update((p,Path(str(p)+'.receipt.json')))
            if lane is not None:
                paths.update((run/'manifests').glob('*.json'))
                adapter=Path(lane['new_adapter']);paths.update(adapter/n for n in ('adapter_config.json','PUBLICATION.json','BINDING.json'))
                paths.update((adapter.parent/'OWNER.json',adapter.parents[1]/'COMPLETE.json'))
    paths.update(Path(p) for p in config['new_contract']['data_pins'])
    result=[]
    for p in sorted(paths):
        try:s=p.stat();result.append([str(p),s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns])
        except FileNotFoundError:result.append([str(p),None])
    return result


def review(config):
    p=Path(config['review'])
    if not p.is_file():return False
    value=M.obj(p);M.require(value.get('verdict')=='PASS_FOR_MATCHED_CURRENT_DEV_CONSUMPTION','review verdict is not a pass')
    expected=value.get('files_sha256',{})
    files=['consumer.py','watcher.py','legacy_consumer.py','config.json','producer-config.json']
    files += ['numeric_sources/'+n+'.py' for n in config['numeric_sources']]
    for name in files:M.require(expected.get(name)==M.sha(HERE/name),'review/source pin mismatch '+name)
    return True


def pending_store_writes(config,before,after,result,code):
    """Only unread stores of pending, still-producing operands may change."""
    operands=result.get('operands',[])
    if code!=2 or len(operands)!=12 or any(x['status'] not in ('PENDING_MISSING_INPUT','VALIDATED_OPERAND') for x in operands):return False
    pending={x['role'] for x in operands if x['status']=='PENDING_MISSING_INPUT'}
    old={x[0]:x[1:] for x in before};new={x[0]:x[1:] for x in after}
    changed={p for p in old.keys()|new.keys() if old.get(p)!=new.get(p)}
    allowed=set()
    for model in config['models']:
        for lane in [None]+[x for x in config['lanes'] if x['baseline_id']==model['id']]:
            if (model['id'] if lane is None else lane['lane']) not in pending:continue
            d=Path(config['k0_root'])/model['id'] if lane is None else Path(config['adapter_root'])/('full-'+lane['lane'])
            run=d/'result'
            # A published handoff or inference terminal freezes these stores even
            # when scoring has not yet supplied a validated operand.
            markers=(d/'infer-EXIT.json',run/'INFERENCE-READY.json')
            if any(old.get(str(p))!=[None] or new.get(str(p))!=[None] for p in markers):continue
            for group in M.CLEAN if lane is None else M.ALL:
                suite,part,kind=group.split('/');p=run/'trackk'/(suite+'__'+part)/(kind+'.jsonl')
                allowed.update((str(p),str(p)+'.receipt.json'))
    return bool(changed) and changed<=allowed and not any(str(Path(p).resolve()) in M._accesses for p in changed)


def pending_phase_publication(config,before,after,result,code):
    """Discard a poll crossing first publication; never validate its changed operand."""
    operands=result.get('operands',[])
    if code not in (0,2) or len(operands)!=12 or result.get('queue_failures') or any(x['status'] not in ('PENDING_MISSING_INPUT','VALIDATED_OPERAND') for x in operands):return None
    old={x[0]:x[1:] for x in before};new={x[0]:x[1:] for x in after}
    changed={p for p in old.keys()|new.keys() if old.get(p)!=new.get(p)}
    allowed=set();roles=[]
    for model in config['models']:
        for lane in [None]+[x for x in config['lanes'] if x['baseline_id']==model['id']]:
            role=model['id'] if lane is None else lane['lane']
            d=Path(config['k0_root'])/role if lane is None else Path(config['adapter_root'])/('full-'+role)
            required={str(d/(phase+'-'+kind+'.json')) for phase in ('infer','score') for kind in ('EXIT','LAUNCH','COMMAND')}
            missing={p for p in required if old.get(p)==[None]}
            if not any(p in changed and new.get(p) not in (None,[None]) for p in missing):continue
            roles.append(role);run=d/'result'
            owned=set(required)
            if lane is not None:
                owned.update(str(d/(phase+'-BINDING.json')) for phase in ('infer','score'))
                owned.update(str(p) for p in (run/'manifests').glob('*.json'))
            owned.update(str(run/n) for n in ('INFERENCE-READY.json','RUN_IDENTITY.json','clean-report.json' if lane is None else 'report.json'))
            stores=set()
            for group in M.CLEAN if lane is None else M.ALL:
                suite,part,kind=group.split('/');p=run/'trackk'/(suite+'__'+part)/(kind+'.jsonl')
                stores.update((str(p),str(p)+'.receipt.json'))
            owned.update(stores)
            # Existing receipts/readouts stay frozen. Only still-unpublished,
            # unread producer stores retain the existing write allowance.
            allowed.update(p for p in owned if old.get(p,[None])==[None])
            if all(old.get(str(p))==[None] for p in (d/'infer-EXIT.json',run/'INFERENCE-READY.json')):
                allowed.update(stores)
    if not changed or not changed<=allowed:return None
    changed_existing={str(Path(p).resolve()) for p in changed if old.get(p,[None])!=[None]}
    for path,signature in M._accesses.items():
        try:current=M.stat_signature(path)
        except OSError:return None
        if current!=signature:return None
        # A first-published input may have been read after the initial stat.
        # Any pre-existing input read by this poll remains strictly immutable.
        if path in changed_existing:return None
    return {'reason':'INITIAL_MISSING_PHASE_INPUT_PUBLISHED','roles':roles,'changed_paths':sorted(changed)}


def run(config,once=False):
    output=Path(config['output']);output.mkdir(parents=True,exist_ok=True)
    M.require(config['mode']=='production','watcher refuses fixture mode')
    M.require(type(config['poll_seconds']) is int and config['poll_seconds']==600,'production polling interval must be 600 seconds')
    with (output/'watcher.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        existing=output/'comparison.json'
        snapshot=M.obj(existing) if existing.is_file() else None
        if snapshot is not None and snapshot.get('status')=='REFUSED_CONTRADICTION':
            print(json.dumps({'status':'REFUSED_CONTRADICTION','detail':'Existing refusal retained; reconcile before relaunch.'}),flush=True)
            return 1
        last=None
        while True:
            if not review(config):
                M.persist(output,{'status':'PENDING_INDEPENDENT_REVIEW','scope':'No production consumption before independent source review'})
                if once:return 2
            else:
                fp=fingerprint(config)
                if fp!=last:
                    before=fp
                    result,code=M.assemble(M.Consumer(config))
                    after=fingerprint(config)
                    if after!=before:
                        transition=pending_phase_publication(config,before,after,result,code)
                        if transition is not None:
                            heartbeat={'utc_seconds':time.time(),'status':'INCOMPLETE_PENDING','exit_code':2,'retry_seconds':config['poll_seconds'],'snapshot_action':'DISCARDED_POLL_PREVIOUS_COMPARISON_RETAINED','snapshot_exists':snapshot is not None,'progress':sum(x['status']=='VALIDATED_OPERAND' for x in (snapshot or {}).get('operands',[])),'total':12,**transition}
                            p=output/'WATCHER-PENDING.json';tmp=p.with_suffix('.json.tmp');tmp.write_text(json.dumps(heartbeat,indent=2)+'\n');os.replace(tmp,p)
                            print(json.dumps(heartbeat),flush=True)
                            last=None
                            if once:return 2
                            time.sleep(config['poll_seconds'])
                            continue
                        M.require(pending_store_writes(config,before,after,result,code),'source/input changed during reconstruction; packet refused')
                        result['detail']='Unpublished producer stores changed during a pending poll; retry required; no validated snapshot accepted for changing stores.'
                        last=None
                    else:last=fp
                    M.persist(output,result)
                    snapshot=result
                    (output/'WATCHER-PENDING.json').unlink(missing_ok=True)
                    print(json.dumps({'utc_seconds':time.time(),'status':result['status'],'progress':sum(x['status']=='VALIDATED_OPERAND' for x in result['operands']),'total':12,'exit_code':code}),flush=True)
                    if code in (0,1) or once:return code
                else:print(json.dumps({'utc_seconds':time.time(),'status':'UNCHANGED_INPUTS_SKIPPED'}),flush=True)
            time.sleep(config['poll_seconds'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(HERE/'config.json'));p.add_argument('--once',action='store_true');a=p.parse_args();config=M.obj(a.config)
    try:return run(config,a.once)
    except Exception as e:
        M.persist(config['output'],{'status':'REFUSED_CONTRADICTION','detail':str(e)});print(json.dumps({'status':'REFUSED_CONTRADICTION','detail':str(e)}),flush=True);return 1

if __name__=='__main__':sys.exit(main())
