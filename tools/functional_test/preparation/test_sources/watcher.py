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


def run(config,once=False):
    output=Path(config['output']);output.mkdir(parents=True,exist_ok=True)
    M.require(config['mode']=='production','watcher refuses fixture mode')
    M.require(type(config['poll_seconds']) is int and config['poll_seconds']==600,'production polling interval must be 600 seconds')
    with (output/'watcher.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
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
                    M.require(fingerprint(config)==before,'source/input changed during reconstruction; packet refused')
                    M.persist(output,result);last=fp
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
