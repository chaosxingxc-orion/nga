#!/usr/bin/env python3
"""Foreground, replay-from-start log capture for an already-bound CPU consumer.

Run under a durable supervisor. Each invocation creates a new attempt; Docker may
replay all prior bytes. Stream EOF is not proof of consumer completion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

try:
    from . import unified_cpu_consumer_v1 as C
except ImportError:
    import unified_cpu_consumer_v1 as C

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PIN_PATHS = [Path(__file__).resolve(), HERE/'unified_cpu_consumer_v1.py',
             HERE/'unified_resource_lease_v1.py', HERE/'unified_container_host_v1.py',
             HERE/'r3_resource_adapter.py',
             REPO/'docker/engineering-base/schema.json']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins():
    return {str(p): sha(p) for p in PIN_PATHS}


def separate(root, paths):
    for p in paths:
        p = C.safe(str(p))
        C.need(not (root == p or root.is_relative_to(p) or p.is_relative_to(root)), 'capture root overlaps input or controller')


def typed_equal(a, b):
    if type(a) is not type(b): return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def authorize(ref):
    c = C.pin(ref)
    event, host, task, mounts = C.validate(c)
    eid = event['event_id']
    jid = C.digest({'event_id':eid, 'stage':task['adapter'], 'config_sha256':c['config']['sha256']})
    name = 'nga-cpu-'+jid[:48]
    identity = {'schema':'unified-cpu-owner-v1','event_id':eid,'job_id':jid,'task':task,
                'config':c,'source_sha256':sha(HERE/'unified_cpu_consumer_v1.py'),'name':name}
    launch = C.digest(identity)
    job = C.safe(c['controller'])/'jobs'/jid
    C.need(typed_equal(C.read(job/'OWNER.json'), identity) and typed_equal(C.read(Path(c['output']+'.cpu-consumer-owner.json')), identity), 'consumer owner changed')
    if c['export_receipt'] is not None:
        receipt = C.pin(c['export_receipt'])
        rjob = C.safe(c['controller'])/'jobs'/receipt['job_id']
        ro = C.read(rjob/'OWNER.json'); rt = C.read(rjob/'TERMINAL.json'); ra = C.read(rjob/'ACK.json')
        C.need(type(ro) is dict and type(ro.get('config')) is dict and type(ro.get('task')) is dict, 'export owner invalid')
        revent, _, rtask, _ = C.validate(ro['config'])
        C.need(typed_equal(revent, event) and typed_equal(rtask, ro['task']) and rtask['adapter'] == 'native-panel-export-v2', 'export task differs')
        rid = C.digest({'event_id': event['event_id'], 'stage': 'native-panel-export-v2', 'config_sha256': ro['config']['config']['sha256']})
        rname = 'nga-cpu-'+rid[:48]
        expected_owner = {'schema':'unified-cpu-owner-v1','event_id':event['event_id'],'job_id':rid,'task':ro['task'],'config':ro['config'],'source_sha256':sha(HERE/'unified_cpu_consumer_v1.py'),'name':rname}
        C.need(rid == receipt['job_id'] and typed_equal(ro, expected_owner) and typed_equal(C.read(Path(receipt['output']+'.cpu-consumer-owner.json')), ro), 'export owner differs')
        rb = C.read(rjob/'BINDING.json'); rl = C.digest(ro)
        C.need(type(rb) is dict and set(rb) == {'launch_sha256','container_id','name'} and rb['launch_sha256'] == rl and rb['name'] == rname and type(rb['container_id']) is str and C.HEX.fullmatch(rb['container_id']), 'export binding differs')
        expected_t = {'schema':'unified-cpu-terminal-v1','event_id':event['event_id'],'launch_sha256':rl,'container_id':rb['container_id'],'exit_code':0,'scientific_acceptance':False}
        expected_a = {'schema':'unified-cpu-ack-v1','event_id':event['event_id'],'launch_sha256':rl,'container_id':rb['container_id'],'exit_code':0,'terminal_sha256':sha(rjob/'TERMINAL.json'),'scientific_acceptance':False,'meaning':'physical completion'}
        expected_r = {'schema':'unified-cpu-export-receipt-v1','event_id':event['event_id'],'job_id':rid,'output':ro['config']['output'],'manifest_sha256':sha(Path(receipt['output'])/'result/manifest.json'),'ack_sha256':sha(rjob/'ACK.json'),'scientific_acceptance':False}
        C.need(typed_equal(rt, expected_t) and typed_equal(ra, expected_a) and typed_equal(receipt, expected_r), 'export receipt ancestry differs')
    binding = C.read(job/'BINDING.json')
    C.need(type(binding) is dict and set(binding) == {'launch_sha256','container_id','name'} and binding['launch_sha256'] == launch and binding['name'] == name and type(binding['container_id']) is str and C.HEX.fullmatch(binding['container_id']), 'consumer binding changed')
    return c, event, mounts, job, name, launch, binding['container_id']


def inspect(c, mounts, name, launch, ident):
    ob = C.verify(C.Docker().inspect(name), c, mounts, name, launch)
    C.need(ob['Id'] == ident, 'container ID differs from binding')
    return ob


def completion(job, event, launch, ident, ob):
    tpath, apath = job/'TERMINAL.json', job/'ACK.json'
    if not tpath.exists() and not apath.exists(): return None
    C.need(tpath.exists() and apath.exists(), 'incomplete consumer completion evidence')
    t, a = C.read(tpath), C.read(apath)
    state = ob.get('State') or {}
    code = state.get('ExitCode')
    C.need(state.get('Status') == 'exited' and state.get('Running') is False and type(code) is int, 'physical completion uncertain')
    terminal = {'schema':'unified-cpu-terminal-v1','event_id':event['event_id'],'launch_sha256':launch,'container_id':ident,'exit_code':code,'scientific_acceptance':False}
    ack = {'schema':'unified-cpu-ack-v1','event_id':event['event_id'],'launch_sha256':launch,'container_id':ident,'exit_code':code,'terminal_sha256':sha(tpath),'scientific_acceptance':False,'meaning':'physical completion'}
    C.need(type(t) is dict and type(a) is dict and type(t.get('exit_code')) is int and type(a.get('exit_code')) is int and t.get('scientific_acceptance') is False and a.get('scientific_acceptance') is False and t == terminal and a == ack, 'consumer completion differs')
    return {'exit_code':code,'terminal_sha256':sha(tpath),'ack_sha256':sha(apath)}


def progress(task, mounts, attempt, streams, ident):
    result = {'schema':'unified-log-capture-heartbeat-v1','utc_seconds':time.time(),
              'state':'cpu_consuming', 'attempt':attempt,'bytes':streams,
              'capture_liveness':'following', 'source':{'container_id':ident,'task_output':task['output']}}
    matches = [(src, dst) for src, dst, rw in mounts if rw and Path(task['output']).is_relative_to(dst)]
    C.need(len(matches) == 1, 'task output mount ambiguous')
    src, dst = matches[0]
    p = Path(src)/Path(task['output']).relative_to(dst)/'heartbeat.json'
    try:
        C.safe(str(p))
        with p.open('rb') as f: raw = f.read(65537)
        if len(raw) > 65536: return result
        v = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        if type(v) is dict and type(v.get('completed')) is int and 0 <= v['completed'] <= 2**63-1:
            total = v.get('total')
            if total is None or (type(total) is int and v['completed'] <= total <= 2**63-1 and total > 0):
                result['completed'] = v['completed']
                if total is not None: result['total'] = total
    except (ValueError, OSError, UnicodeError, RecursionError): pass
    return result


def signatures(attempt_dir):
    # Bounded evidence pointers only, no copied log content or tracebacks.
    found = []
    for name in ('stdout.log','stderr.log'):
        with (attempt_dir/name).open('rb') as f:
            n = 1
            while True:
                line = f.readline(65536)
                if not line: break
                lower = line.lower()
                for sig in (b'traceback', b'error', b'exception', b'failed'):
                    if sig in lower:
                        found.append({'signature':sig.decode(),'file':name,'line':n})
                        break
                if len(found) >= 32: return found
                if line.endswith(b'\n'): n += 1
    return found


def run(ref, output, heartbeat_seconds=10, capture_config_path=None):
    C.need(type(heartbeat_seconds) is int and 10 <= heartbeat_seconds <= 30, 'heartbeat cadence must be 10-30 seconds')
    root = C.safe(output)
    C.need(root.is_dir() and root.stat().st_uid == os.geteuid() and root.stat().st_mode & 0o077 == 0, 'capture root must be preexisting private directory')
    # Validate before writing any capture ownership or attempting Docker.
    c, event, mounts, job, name, launch, ident = authorize(ref)
    host = C.pin(c['host_config'])
    ev = C.pin(c['event'])
    paths = [c['controller'],c['output'],ref['path'],c['config']['path'],c['event']['path'],c['host_config']['path'],host['output'],host['config']['path']]
    paths += [x['source'] for x in c['inputs']] + [v['path'] for v in ev['evidence'].values()]
    if capture_config_path is not None: paths.append(capture_config_path)
    if c['export_receipt'] is not None: paths.append(c['export_receipt']['path'])
    separate(root, paths + [str(p) for p in PIN_PATHS])
    with C.lock(job/'log-follower.lock', True), C.lock(root/'follower.lock', True):
        # Recheck after taking the single-owner lock and before binding output.
        c, event, mounts, job, name, launch, ident = authorize(ref)
        task = C.pin(c['config'])
        codepins = pins()
        owner = {'schema':'unified-log-capture-owner-v1','consumer_config':ref,'container_id':ident,'launch_sha256':launch,'code_pins':codepins}
        op = root/'OWNER.json'
        if op.exists(): C.need(typed_equal(C.read(op), owner), 'capture output owner changed')
        else: C.write(op, owner)
        C.write(root/'relaunch.json', {'argv':[sys.executable, str(Path(__file__).resolve()), '--config',ref['path'],'--sha256',ref['sha256'],'--output',str(root),'--heartbeat-seconds',str(heartbeat_seconds)], 'code_pins':codepins,'runtime_closure_claimed':False})
        nums = [int(p.name) for p in (root/'attempts').glob('[0-9]*') if p.is_dir() and p.name.isdigit()] if (root/'attempts').exists() else []
        number = max(nums, default=0)+1
        attempt = root/'attempts'/('%08d' % number); attempt.mkdir(parents=True, mode=0o700)
        C.write(attempt/'START.json', {'attempt':number,'container_id':ident,'replay':'from beginning; duplicates allowed','streams':'docker CLI stdout and stderr, raw bytes'})
        rc = None; proof = None; error = None; proc = None
        sizes = {'stdout':0,'stderr':0}
        try:
            inspect(c, mounts, name, launch, ident)
            C.need(pins() == codepins, 'code pins changed')
            authorize(ref)
            with (attempt/'stdout.log').open('xb', buffering=0) as out, (attempt/'stderr.log').open('xb', buffering=0) as err:
                proc = subprocess.Popen(['docker','logs','--follow','--timestamps',ident], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                sel = selectors.DefaultSelector()
                for pipe, dest, key in ((proc.stdout,out,'stdout'),(proc.stderr,err,'stderr')): sel.register(pipe, selectors.EVENT_READ, (dest,key))
                nextbeat = 0
                while sel.get_map():
                    now=time.monotonic()
                    if now >= nextbeat:
                        os.fsync(out.fileno()); os.fsync(err.fileno())
                        C.write(root/'heartbeat.json', progress(task,mounts,number,dict(sizes),ident)); nextbeat=now+heartbeat_seconds
                    for key, _ in sel.select(timeout=max(0, nextbeat-time.monotonic())):
                        data=os.read(key.fileobj.fileno(),65536)
                        if data:
                            dest, label=key.data; dest.write(data); sizes[label]+=len(data)
                        else: sel.unregister(key.fileobj); key.fileobj.close()
                rc=proc.wait()
                os.fsync(out.fileno()); os.fsync(err.fileno())
            C.need(pins() == codepins, 'code pins changed during capture')
            c2, event2, mounts2, job2, name2, launch2, ident2 = authorize(ref)
            C.need((job2,name2,launch2,ident2)==(job,name,launch,ident), 'consumer identity changed')
            ob=inspect(c2,mounts2,name2,launch2,ident2)
            proof=completion(job2,event2,launch2,ident2,ob)
        except Exception as exc:
            error=type(exc).__name__+': '+str(exc)[:500]
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            if proc is not None: rc=proc.returncode
        finally:
            for n in ('stdout.log','stderr.log'):
                p=attempt/n
                if not p.exists(): p.touch(mode=0o600)
            C.write(attempt/'DIGEST.json', {'signatures':signatures(attempt),'limit':32})
            status = 'error' if error else ('stream_failed' if rc != 0 else ('completed' if proof is not None else 'stream_eof_not_completion'))
            terminal={'schema':'unified-log-capture-terminal-v1','attempt':number,'stream_returncode':rc,'consumer_completion':proof,'status':status,'error':error,'bytes':sizes}
            C.write(attempt/'TERMINAL.json',terminal)
            beat=progress(task,mounts,number,dict(sizes),ident); beat['capture_liveness']='stopped'; C.write(root/'heartbeat.json',beat)
        return terminal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('op',nargs='?',choices=['serve']); p.add_argument('--config',required=True); p.add_argument('--sha256',required=True); p.add_argument('--output'); p.add_argument('--heartbeat-seconds',type=int,default=10)
    a=p.parse_args()
    try:
        if a.op == 'serve':
            C.need(a.output is None and a.heartbeat_seconds == 10, 'serve uses closed configuration')
            cfg=C.pin({'path':a.config,'sha256':a.sha256})
            C.need(type(cfg) is dict and set(cfg) == {'schema','consumer_config','output','heartbeat_seconds'} and cfg['schema'] == 'unified-log-capture-v1', 'closed capture config required')
            result=run(cfg['consumer_config'],cfg['output'],cfg['heartbeat_seconds'],a.config)
        else:
            C.need(a.output is not None, 'output required')
            result=run({'path':a.config,'sha256':a.sha256},a.output,a.heartbeat_seconds)
        print(json.dumps(result,sort_keys=True))
        return 0 if result['status']=='completed' and result['stream_returncode']==0 and result['consumer_completion']['exit_code']==0 else 1
    except Exception as e:
        print(type(e).__name__+': '+str(e),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
