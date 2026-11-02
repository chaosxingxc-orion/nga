#!/usr/bin/env python3
"""Finite R3-training -> BEV successor, configured on the analysis host.

Reads terminal receipts every 600 seconds, then delegates to the original guarded
BEV launcher and fixed CPU handoff. Never claims resources or retries an uncertain
launch. Configuration and reviewed packages are trusted operator inputs.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value

W = module(Path(__file__).with_name('experiment_workflow.py'), 'successor_workflow')
E = W.E
SCHEMA = 'nga-bev-successor-v1'


def remote(args):
    r = subprocess.run(['ssh', 'npu', shlex.join(args)], capture_output=True, text=True, timeout=60)
    E.require(r.returncode == 0, 'remote observation uncertain: ' + r.stderr[-500:])
    return json.loads(r.stdout)


def atomic(path, data):
    temp = path.with_name(path.name + '.pending')
    with temp.open('w') as stream:
        json.dump(data, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def load(path, expected):
    c = E.read_json(E.pinned({'path': str(path), 'sha256': expected}))
    E.require(set(c) == {'schema','controller','entrypoint','workflow','previous','entry','cpu','consumer','output','poll_seconds'}, 'config fields differ')
    E.require(c['schema'] == SCHEMA and c['poll_seconds'] == 600, 'schema/poll differs')
    for key, actual in [('controller', __file__), ('entrypoint', E.__file__), ('workflow', W.__file__)]:
        E.require(E.pinned(c[key]) == Path(actual).resolve(), 'tool path differs')
    p = c['previous']
    E.require(set(p) == {'plan','supervisor','launch','attempt'}, 'predecessor fields differ')
    plan = E.read_json(E.pinned(p['plan']))
    E.pinned(p['supervisor']); E.pinned(p['launch'])
    E.require(type(p['attempt']) is int and p['attempt'] > 0 and plan['schema'] == 'r3-engineering-k1-plan-v1', 'training predecessor required')
    E.require(plan['scientific_acceptance'] is False and plan['test_read'] is False, 'previous scope differs')
    E.safe(c['output']); E.pinned(c['entry']); E.pinned(c['cpu']); E.pinned(c['consumer'])
    return c, plan


def validate_next(c, previous):
    entry, plan = E.load_config(c['entry']['path'], c['entry']['sha256'])
    E.require(entry['attempt'] == 1 and plan['chip'] == previous['chip'], 'next chip/attempt differs')
    review = E.read_json(E.pinned(entry['review']))
    E.require(review.get('deployment_suitable') is True and review.get('cpu_config_sha256') == c['cpu']['sha256']
              and review.get('consumer_sha256') == c['consumer']['sha256'], 'CPU review differs')
    consumer = module(E.pinned(c['consumer']), 'successor_consumer')
    cpu = consumer.verify_config(c['cpu']['path'], c['cpu']['sha256'])
    E.require(cpu['plan'] == entry['plan']['path'] and cpu['plan_sha256'] == entry['plan']['sha256'], 'CPU plan differs')
    return entry, plan


def previous_ready(c, plan, observe=remote):
    p = c['previous']; root = E.safe(plan['out']); number = p['attempt']; attempt = root/'attempts'/str(number)
    E.require(E.safe(p['plan']['path']) == root/'plan.json' and E.safe(p['supervisor']['path']) == root/'SUPERVISOR_RECEIPT.json'
              and E.safe(p['launch']['path']) == attempt/'LAUNCH_RECEIPT.json', 'previous paths differ')
    launch = E.read_json(E.pinned(p['launch'])); supervisor = E.read_json(E.pinned(p['supervisor']))
    canonical = dict(plan, review_sha256='PENDING')
    import hashlib
    pin = hashlib.sha256((json.dumps(canonical,indent=2,sort_keys=True)+'\n').encode()).hexdigest()
    E.require(launch['plan_sha256'] == pin, 'previous launch plan differs')
    command = supervisor['command']
    E.require(command[1:] == ['-P',plan['launcher'],'supervise','--plan',p['plan']['path'],'--sha256',pin,'--attempt',str(number)], 'previous supervisor differs')
    terminal, release = root/'TRAIN_EXIT.json', attempt/'RELEASE.json'
    if not terminal.exists() or not release.exists(): return None
    end = E.read_json(terminal); proof = E.read_json(release)
    E.require(end == E.read_json(attempt/'EXIT.json') and end['attempt'] == number and end['exit_code'] == 0, 'previous unsuccessful or markers differ')
    E.require(proof['schema'] == 'r3-resource-release-v1' and proof['exit_code'] == 0 and proof['chip'] == plan['chip']
              and proof['run'] == plan['run'] and proof['container_id'] == launch['id'] and proof['scientific_acceptance'] is False,
              'previous release identity differs')
    actual = observe(['docker','inspect',launch['id']])[0]
    E.require(actual['Id'] == launch['id'] and actual['Name'].lstrip('/') == plan['container']+'-a'+str(number)
              and actual['State']['Status'] == 'exited' and actual['State']['ExitCode'] == 0, 'previous retained state differs')
    E.require('/dev/davinci'+str(plan['chip']) in [x['PathOnHost'] for x in actual['HostConfig']['Devices']], 'previous device differs')
    allocation = E.read_json(E.safe(plan['allocation']))
    E.require(not any(x['chip'] == plan['chip'] for x in allocation['allocation']), 'chip allocated after predecessor')
    free = [x for x in allocation['free'] if x['chip'] == plan['chip']]
    E.require(len(free)==1 and free[0]['previous_run']==plan['run'] and free[0]['release_evidence']==str(release), 'free generation differs')
    return {'container_id':launch['id'],'release':W.pin(release),'terminal':W.pin(terminal),'free':free[0]}


def tick(c, previous, observe=remote):
    out = E.safe(c['output'])
    intent = out/'START_INTENT.json'; response = out/'START_RETURN.json'
    if intent.exists():
        # An uncertain call may already have started a supervisor. Never replay it.
        if not response.exists(): return {'status':'needs_reconciliation','reason':'start intent without verified return'}
        entry, plan = validate_next(c, previous)
    else:
        proof = previous_ready(c, previous, observe)
        if proof is None: return {'status':'waiting_predecessor_release'}
        entry, plan = validate_next(c, previous)
        E.require(not (E.safe(plan['out'])/'host_attempts/1').exists(), 'next attempt already exists outside this handoff')
        command = ['/usr/bin/python3.12','-B','-P',c['entrypoint']['path'],'start','--config',c['entry']['path'],'--config-sha256',c['entry']['sha256']]
        W.write(intent, {'previous':proof,'command':command,'utc_seconds':time.time()})
        result = observe(command)
        E.require(result.get('status') == 'guarded_start_returned', 'guarded start did not return success')
        W.write(response, {'result':result,'utc_seconds':time.time()})
    host = E.safe(plan['out'])/'host_attempts/1'; launch_path=host/'LAUNCH_RECEIPT.json'
    if (host/'SUPERVISOR_ERROR.json').exists(): return {'status':'needs_reconciliation','reason':'next supervisor failed'}
    if not launch_path.exists(): return {'status':'waiting_next_launch_receipt'}
    receipt = E.read_json(launch_path)
    E.require(receipt['plan_sha256']==entry['plan']['sha256'], 'next receipt plan differs')
    actual = observe(['docker','inspect',receipt['container_id']])[0]
    E.require(actual['Id']==receipt['container_id'] and actual['Name'].lstrip('/')==plan['container']+'-a1'
              and actual['State']['Status'] in ('running','exited'), 'next retained identity differs')
    E.require('/dev/davinci'+str(plan['chip']) in [x['PathOnHost'] for x in actual['HostConfig']['Devices']], 'next device differs')
    # cpu_start refuses uncertain existing writers. Preserve old preparation metadata
    # outside this controller before admission, rather than silently moving it here.
    cpu = W.cpu_start({'cpu':c['cpu'],'consumer':c['consumer']})
    return {'status':'handed_off','container_id':actual['Id'],'cpu':cpu,'scientific_acceptance':False}


def watch(path, pin):
    c, previous = load(path,pin); out=E.safe(c['output'])
    with (out/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            try:
                c, previous=load(path,pin); state=tick(c,previous)
            except Exception as error:
                state={'status':'needs_reconciliation','error':str(error)[:1000]}
            value=dict(state,utc_seconds=time.time(),config_sha256=pin)
            atomic(out/'digest.json',value)
            if state['status'] in ('handed_off','needs_reconciliation'):
                atomic(out/'EXIT.json',dict(value,exit_code=0 if state['status']=='handed_off' else 1)); return
            time.sleep(600)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=('validate','start','watch','status'))
    ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args(argv)
    try:
        c,p=load(a.config,a.sha256);out=E.safe(c['output'])
        if a.op=='validate': validate_next(c,p); value={'status':'validated'}
        elif a.op=='status': value={n:E.read_json(out/n) for n in ('SERVICE.json','digest.json','EXIT.json') if (out/n).exists()}
        elif a.op=='watch': watch(a.config,a.sha256);return 0
        else:
            validate_next(c,p);out.mkdir(exist_ok=True)
            command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--config',a.config,'--sha256',a.sha256]
            with (out/'start.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                E.require(not any((out/n).exists() for n in ('SERVICE.json','START_INTENT.json','EXIT.json')), 'existing service or run requires inspection')
                W.write(out/'RELAUNCH.json',{'command':[sys.executable,'-B','-P',str(Path(__file__).resolve()),'start','--config',a.config,'--sha256',a.sha256]})
                with (out/'service.log').open('ab') as log:
                    worker=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                W.write(out/'SERVICE.json',{'pid':worker.pid,'command':command});value={'status':'started','pid':worker.pid}
        print(json.dumps(value,indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'rejected','error':str(error)}));return 1

if __name__=='__main__':raise SystemExit(main())
