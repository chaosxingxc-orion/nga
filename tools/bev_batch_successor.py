#!/usr/bin/env python3
"""One-shot public-TEST release -> fixed DEV probe handoff on host175.

No result acceptance, retries or resource mutation: delegates one attempt to the
exact independently reviewed host. Operator-pinned review origin is a trust boundary.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import types

SCHEMA = 'bev-batch-successor-v2'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and not any(x.is_symlink() for x in (p, *p.parents)), 'absolute non-symlink path required')
    return p


def sha(path):
    return hashlib.sha256(safe(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(safe(path).read_text())


def pinned(item):
    p = safe(item['path'])
    require(sha(p) == item['sha256'], 'pin differs: ' + str(p))
    return p


def pin(path):
    return {'path': str(path), 'sha256': sha(path)}


def write(path, value, exclusive=False):
    path = safe(path)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
    else:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name): os.unlink(name)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def module(path):
    m = types.ModuleType('exact_successor_host'); m.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), m.__dict__)
    return m


def load(path, digest, review_required=True):
    c = read(pinned({'path': path, 'sha256': digest}))
    require(c['schema'] == SCHEMA and c['poll_seconds'] == 600, 'schema or polling differs')
    require(pinned(c['controller']) == Path(__file__).resolve(), 'controller differs')
    require(c['host'] == 'k8s-node1' and c['python'] == '/usr/bin/python3.12', 'host runtime differs')
    previous = read(pinned(c['previous']['plan']))
    nxt = read(pinned(c['next']['plan']))
    require(previous['schema'] == 'bev-public-test-plan-v1' and nxt['schema'] == 'bev-batch-efficiency-probe-v1', 'plan schema differs')
    require(previous['chip'] == nxt['chip'] == 7 and previous['allocation'] == nxt['allocation'], 'resource differs')
    require(nxt['test_read'] is False and nxt['scope'] == 'train_derived_dev' and nxt['attempts'] == [1], 'DEV-only fresh probe required')
    require(nxt['scientific_acceptance'] is False, 'scientific scope differs')
    host = module(pinned(nxt['code']['host']))
    require(nxt['successor_guard']['controller']==c['controller'] and nxt['successor_guard']['previous']==c['previous'],'guard plan/config binding differs')
    if review_required:host.review(c['next']['plan']['path'], c['next']['plan']['sha256'], c['next']['review']['path'], sha(c['next']['review']['path']))
    else:host.runner(nxt).verify(c['next']['plan']['path'],c['next']['plan']['sha256'])
    root = safe(previous['out']); h = root/'host_attempts/1'
    for key, name in [('claim','CLAIM.json'),('launch','LAUNCH_RECEIPT.json'),('spec','LAUNCH_SPEC.json')]:
        require(pinned(c['previous'][key]) == h/name, 'predecessor artifact path differs')
    claim = read(c['previous']['claim']['path']); receipt = read(c['previous']['launch']['path']); spec = read(c['previous']['spec']['path'])
    require(claim['schema'] == 'r3-resource-claim-v1' and claim['run'] == previous['run'] and claim['chip'] == 7 and claim['allocation'] == previous['allocation'], 'predecessor claim differs')
    cmd = ['python3','-B','-P',previous['code']['runner']['path'],'run','--plan',c['previous']['plan']['path'],'--sha256',c['previous']['plan']['sha256'],'--attempt','1']
    require(receipt['plan_sha256'] == spec['plan_sha256'] == c['previous']['plan']['sha256'] and receipt['command'] == cmd and spec['command'][-len(cmd):] == cmd, 'predecessor launch differs')
    require(receipt['container_id'] == c['previous']['container_id'], 'predecessor container differs')
    safe(c['output'])
    return c, previous, nxt


def activation(path, digest, c, config_pin):
    a = read(pinned({'path': path, 'sha256': digest}))
    require(a['schema'] == 'bev-batch-successor-activation-v1' and a['config_sha256'] == config_pin, 'activation binding differs')
    require(a['activation_authorized'] is True and a['scientific_acceptance'] is False, 'activation not authorized')
    r = read(pinned(a['review']))
    require(r['verdict'] == 'PASS' and r['config_sha256'] == config_pin and r['activation_authorized'] is True and r['scientific_acceptance'] is False, 'exact external successor review required')
    require(a['preregistration'] == read(c['next']['plan']['path'])['inputs']['preregistration'], 'preregistration differs')
    pinned(a['preregistration'])
    require(a['probe_review']['path']==c['next']['review']['path'],'probe review path differs')
    pinned(a['probe_review'])
    require(isinstance(a['wiki_commit'], str) and len(a['wiki_commit']) == 40 and all(x in '0123456789abcdef' for x in a['wiki_commit']), 'published full wiki commit required')
    return a


def inspect(cid):
    r = subprocess.run(['docker','inspect',cid], capture_output=True, text=True, timeout=30)
    require(r.returncode == 0, 'retained container observation uncertain')
    values = json.loads(r.stdout); require(len(values) == 1, 'ambiguous retained container')
    return values[0]


def runner_command(p, plan_binding):
    return ['python3','-B','-P',p['code']['runner']['path'],'run','--plan',plan_binding['path'],'--sha256',plan_binding['sha256'],'--attempt','1']


def actual_matches(actual, p, receipt, exited, expected):
    require(actual['Id'] == receipt['container_id'] and actual['Name'].lstrip('/') == p['container']+'-a1', 'retained identity differs')
    require(actual['Image'] == p['image_sha256'] and not actual['HostConfig'].get('AutoRemove'), 'retained image/lifecycle differs')
    devices = [x['PathOnHost'] for x in actual['HostConfig']['Devices'] if x['PathOnHost'].removeprefix('/dev/davinci').isdigit()]
    require(devices == ['/dev/davinci7'], 'retained device mapping differs')
    require(actual['Config']['Cmd'] == receipt['command'] == expected, 'retained command differs')
    if exited:
        require(actual['State']['Status'] == 'exited' and actual['State']['ExitCode'] == 0, 'predecessor has not exited successfully')
    else:
        require(actual['State']['Status'] in ('created','running','exited'), 'successor state uncertain')


def previous_ready(c, p, observe=inspect, allocation=None):
    for key in ('plan','claim','launch','spec'):
        if key in c['previous']:pinned(c['previous'][key])
    root = safe(p['out']); h = root/'host_attempts/1'
    paths = [h/'EXIT.json',h/'RELEASE.json',root/'attempts/1/EXIT.json',root/'COMPLETE.json']
    for end in (h/'EXIT.json', root/'attempts/1/EXIT.json'):
        if end.exists(): require(read(end).get('exit_code') == 0, 'predecessor failed')
    if not all(x.is_file() for x in paths): return None
    raws={str(x):x.read_bytes() for x in paths}
    end, release, runner, complete = [json.loads(raws[str(x)]) for x in paths]
    receipt = read(pinned(c['previous']['launch'])); claim = pinned(c['previous']['claim'])
    require(end.get('runner_terminal_matches') is True and end['container_exit_code'] == 0 and end['container_id'] == receipt['container_id'], 'host terminal differs')
    require(runner['attempt'] == complete['attempt'] == 1 and runner['plan_sha256'] == complete['plan_sha256'] == c['previous']['plan']['sha256'], 'runner completion differs')
    require(complete['exit_code'] == 0 and complete['schema'] == 'bev-public-test-completion-v1' and complete['rows'] == p['expected_questions'] and len(complete['items']) == p['expected_questions'], 'incomplete predecessor population')
    require(release['schema'] == 'r3-resource-release-v1' and release['exit_code'] == 0 and release['run'] == p['run'] and release['chip'] == p['chip'] and release['container_id'] == receipt['container_id'] and release['claim_sha256'] == sha(claim), 'release lineage differs')
    actual = observe(receipt['container_id']); actual_matches(actual,p,receipt,True,runner_command(p,c['previous']['plan']))
    require(release['container'] == p['container']+'-a1' and release['container_started_at'] == actual['State']['StartedAt'] and release['container_finished_at'] == actual['State']['FinishedAt'], 'release retained timestamps differ')
    allocation = read(p['allocation']) if allocation is None else allocation
    require(not any(x['chip'] == 7 for x in allocation['allocation']), 'predecessor chip not free')
    free = [x for x in allocation['free'] if x['chip'] == 7]
    require(len(free) == 1 and free[0]['previous_run'] == p['run'] and free[0]['release_evidence'] == str(h/'RELEASE.json'), 'free generation differs')
    require(free == [x for x in release['allocation_after']['free'] if x['chip']==p['chip']], 'free entry differs from release snapshot')
    require(all(safe(x).read_bytes()==raw for x,raw in raws.items()),'predecessor changed during validation')
    return {'evidence':[{'path':x,'sha256':hashlib.sha256(raw).hexdigest()} for x,raw in raws.items()], 'free':free[0], 'container_id':receipt['container_id']}


def claim_precondition(p, plan_pin, precondition_pin, allocation, resource):
    path=safe(p['out'])/'SUCCESSOR_PRECONDITION.json'
    value=read(pinned({'path':str(path),'sha256':precondition_pin}))
    require(value['plan_sha256']==plan_pin,'precondition plan differs')
    previous=p['successor_guard']['previous']; prior=read(pinned(previous['plan']))
    proof=previous_ready({'previous':previous},prior,resource.docker_inspect,allocation)
    require(proof is not None and proof==value['previous'],'predecessor evidence changed at claim')
    require(resource.docker_inspect(p['container']+'-a1') is None,'container collision at claim')
    require(not resource.live_chip_conflict(p['chip'],None),'competing device at claim')
    # All file evidence is rechecked on each locked callback, including before commit.
    for item in proof['evidence']:pinned(item)
    return dict(precondition_sha256=precondition_pin,previous=proof,plan_sha256=plan_pin)


def validate_claim(claim,p,plan_pin):
    require(claim.get('schema')=='r3-resource-claim-v1' and claim['run']==p['run'] and claim['chip']==p['chip'] and claim['allocation']==p['allocation'],'successor claim differs')
    for label in ('before','after'):
        raw=(json.dumps(claim['allocation_'+label],indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
        require(hashlib.sha256(raw).hexdigest()==claim['allocation_'+label+'_sha256'],'claim snapshot differs')
    before=claim['allocation_before'];after=claim['allocation_after'];entry=claim['entry']
    require(entry['run']==p['run'] and entry['chip']==p['chip'] and not any(x['chip']==p['chip'] for x in before['allocation']),'claim owner differs')
    require(after['allocation']==sorted(before['allocation']+[entry],key=lambda x:x['chip']) and after['free']==[x for x in before['free'] if x['chip']!=p['chip']],'claim transition differs')
    pre=read(safe(p['out'])/'SUCCESSOR_PRECONDITION.json')
    require(pre['plan_sha256']==plan_pin and claim['successor_precondition']==dict(precondition_sha256=sha(safe(p['out'])/'SUCCESSOR_PRECONDITION.json'),previous=pre['previous'],plan_sha256=plan_pin),'claim prerequisite differs')
    require([x for x in before['free'] if x['chip']==p['chip']]==[pre['previous']['free']],'claim free generation differs')


def command(c, n):
    return [c['python'],'-B','-P',n['code']['host']['path'],'start','--plan',c['next']['plan']['path'],'--sha256',c['next']['plan']['sha256'],'--review',c['next']['review']['path'],'--review-sha256',sha(c['next']['review']['path']),'--attempt','1','--precondition',str(safe(n['out'])/'SUCCESSOR_PRECONDITION.json'),'--precondition-sha256',sha(safe(n['out'])/'SUCCESSOR_PRECONDITION.json')]


def run_command(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    require(p.returncode == 0, 'successor start failed; reconcile without retry')
    return json.loads(p.stdout)


def tick(c, p, n, observe=inspect, launch=run_command):
    out = safe(c['output']); intent = out/'LAUNCH_INTENT.json'; response = out/'LAUNCH_RETURN.json'
    if intent.exists():
        require(response.exists(), 'uncertain launch intent; never replay')
        require(read(intent)['command'] == command(c,n), 'existing intent differs')
    else:
        proof = previous_ready(c,p,observe)
        if proof is None: return {'status':'waiting_predecessor_release'}
        require(not (safe(n['out'])/'host_attempts/1').exists(), 'successor attempt already exists')
        safe(n['out']).mkdir(parents=True,exist_ok=True)
        write(safe(n['out'])/'SUCCESSOR_PRECONDITION.json', {'previous':proof,'plan_sha256':c['next']['plan']['sha256']}, exclusive=True)
        write(intent, {'previous':proof,'command':command(c,n),'utc_seconds':time.time()}, exclusive=True)
        result = launch(command(c,n))
        require(result.get('status') == 'supervisor_started' and result.get('attempt') == 1 and type(result.get('pid')) is int, 'start return differs')
        write(response, {'result':result,'utc_seconds':time.time()}, exclusive=True)
    h = safe(n['out'])/'host_attempts/1'
    require(not (h/'SUPERVISOR_ERROR.json').exists(), 'successor supervisor failed')
    if not (h/'LAUNCH_RECEIPT.json').exists(): return {'status':'waiting_successor_receipt'}
    receipt = read(h/'LAUNCH_RECEIPT.json')
    require(receipt['plan_sha256'] == c['next']['plan']['sha256'], 'successor receipt differs')
    actual_matches(observe(receipt['container_id']),n,receipt,False,runner_command(n,c['next']['plan']))
    claim = read(h/'CLAIM.json')
    validate_claim(claim,n,c['next']['plan']['sha256'])
    return {'status':'handed_off','container_id':receipt['container_id'],'scientific_acceptance':False}


def watch(args):
    c,p,n = load(args.config,args.sha256); out=safe(c['output'])
    with (out/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not (out/'EXIT.json').exists(), 'terminal service cannot replay')
        while True:
            try:
                # Revalidate static source/review bindings before each possible launch.
                c,p,n=load(args.config,args.sha256)
                activation(args.activation,args.activation_sha256,c,args.sha256)
                state=tick(c,p,n)
            except Exception as error:
                state={'status':'needs_reconciliation','error':str(error)[:800]}
            state.update(utc_seconds=time.time(),config_sha256=args.sha256,scientific_acceptance=False)
            write(out/'digest.json',state)
            print(json.dumps(state),flush=True)
            if state['status'] in ('handed_off','needs_reconciliation'):
                write(out/'EXIT.json',dict(state,exit_code=0 if state['status']=='handed_off' else 1),exclusive=True)
                return
            time.sleep(c['poll_seconds'])


def start(args,c):
    out=safe(c['output']); out.mkdir(parents=True,exist_ok=True)
    base=[c['python'],'-B','-P',str(Path(__file__).resolve())]
    flags=['--config',args.config,'--sha256',args.sha256,'--activation',args.activation,'--activation-sha256',args.activation_sha256]
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not any((out/x).exists() for x in ('SERVICE_INTENT.json','SERVICE.json','LAUNCH_INTENT.json','EXIT.json')), 'existing service needs reconciliation')
        cmd=base+['watch']+flags
        write(out/'RELAUNCH.json',{'command':base+['start']+flags,'policy':'No replay after an intent; reconcile existing process and immutable generation first.'},exclusive=True)
        write(out/'SERVICE_INTENT.json',{'command':cmd,'utc_seconds':time.time()},exclusive=True)
        with (out/'service.log').open('ab') as log:
            process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        write(out/'SERVICE.json',{'pid':process.pid,'command':cmd},exclusive=True)
        return {'status':'started','pid':process.pid}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op',choices=['validate','inspect','inspect-preparation','start','watch'])
    parser.add_argument('--config',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--activation');parser.add_argument('--activation-sha256')
    args=parser.parse_args(argv)
    try:
        c,p,n=load(args.config,args.sha256,review_required=args.op!='inspect-preparation')
        if args.op=='validate': result={'status':'validated','activation_required':True}
        elif args.op in ('inspect','inspect-preparation'): result={'status':'ready' if previous_ready(c,p) else 'waiting_predecessor_release'}
        else:
            require(socket.gethostname()==c['host'],'host175 required')
            activation(args.activation,args.activation_sha256,c,args.sha256)
            if args.op=='watch': watch(args); return 0
            result=start(args,c)
        print(json.dumps(result));return 0
    except Exception as error:
        failure={'status':'rejected','error':str(error)[:800],'exit_code':1,'scientific_acceptance':False,'utc_seconds':time.time()}
        if args.op=='watch' and 'c' in locals():
            out=safe(c['output'])
            if out.is_dir() and not (out/'EXIT.json').exists():
                write(out/'EXIT.json',failure,exclusive=True)
        print(json.dumps(failure));return 1


if __name__=='__main__': raise SystemExit(main())
