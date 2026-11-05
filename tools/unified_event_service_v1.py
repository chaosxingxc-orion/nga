#!/usr/bin/env python3
"""Persistent event-driven coordinator. Resource provider is deliberately fail-closed."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

# -P prevents importing code from the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import experiment_dag as D
from tools import unified_cpu_consumer_v1 as C
from tools import unified_dag_adapter_v1 as A
from tools import unified_resource_lease_v1 as U
from tools import r3_resource_adapter as R
from tools import unified_container_host_v1 as H

HERE = Path(__file__).resolve()


def file_pin(p):
    return A.file_pin(p)


def exact_value(actual, expected):
    """Compare authoritative JSON recursively without Python's bool/int aliases."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(exact_value(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(exact_value(a, b) for a, b in zip(actual, expected))
    return actual == expected


def cpu_components():
    return [file_pin(p) for p in (HERE, D.__file__, C.__file__, A.__file__, U.__file__, R.__file__, H.__file__, HERE.parents[1] / 'docker/engineering-base/schema.json')]


def load_config(ref):
    c = D.read_pin(ref)
    D.exact(c, ('schema', 'graph', 'policy', 'state_dir', 'socket', 'review_pins', 'python', 'fallback_seconds'), 'service config')
    D.require(c['schema'] == 'unified-event-service-v1' and c['fallback_seconds'] == 600 and type(c['fallback_seconds']) is int, 'service version/cadence')
    for k in ('state_dir', 'socket', 'python'):
        C.safe(c[k])
    D.require(c['python'] == str(Path(sys.executable).resolve()) and Path(c['python']).is_file(), 'interpreter differs')
    D.require(Path(c['socket']).parent == Path(c['state_dir']), 'socket must be in state directory')
    D.require(type(c['review_pins']) is list and c['review_pins'], 'trusted review pins required')
    for p in c['review_pins']: D.pin(p)
    policy_path(c)
    g = D.read_pin(c['graph']); D.validate(g)
    D.require(g['policy']['poll_seconds'] == 600, 'graph cadence')
    for n in g['nodes']:
        D.require(n['adapter'] == ('unified_cpu_v1' if n['lane'] == 'cpu' else 'unified_npu_v1'), 'unsupported adapter')
        D.require(g['adapters'][n['adapter']]['implementation'] == file_pin(HERE if n['lane'] == 'cpu' else A.__file__), 'adapter pin differs')
    return c, g


def policy_path(c):
    p = c['policy']
    D.require(type(p) is dict and set(p) in ({'path'}, {'path', 'sha256'}), 'policy pointer')
    C.safe(p['path'])
    if 'sha256' in p: D.pin(p)
    return Path(p['path'])


@contextmanager
def policy_lock(c):
    path = policy_path(c)
    with C.lock(str(path) + '.lock'):
        yield


def current_policy(c):
    ref = c['policy']
    p = D.read_pin(ref) if 'sha256' in ref else C.read(policy_path(c))
    D.require(type(p) is dict and p.get('schema') == 'nga-engineering-release-policy-v1', 'policy version')
    return p


def policy_update(c, source):
    D.require(set(c['policy']) == {'path'}, 'policy-update requires mutable pointer')
    p = C.read(source)
    D.require(type(p) is dict and p.get('schema') == 'nga-engineering-release-policy-v1' and p.get('new_experiment_dispatch') in ('allow', 'hold'), 'invalid policy')
    with policy_lock(c):
        D.atomic(policy_path(c), p)


def held(c):
    # Any read, pin or schema error is a HOLD. Never retain an earlier decision.
    try:
        p = current_policy(c)
        return p['new_experiment_dispatch'] != 'allow'
    except Exception:
        return True


def notify(path):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s: s.sendto(b'wake', path)
    except OSError:
        pass  # durable state and fallback recover a lost notification


class CPUAdapter:
    def __init__(self, c, graph, ref, launch=True):
        self.c, self.graph, self.ref, self.launch = c, graph, ref, launch
        self.implementation_sha256 = file_pin(HERE)['sha256']

    def authorize(self, binding, review, node, graph_hash):
        D.exact(binding, ('schema', 'consumer_config'), 'CPU binding')
        D.require(binding['schema'] == 'unified-event-cpu-binding-v1' and node['lane'] == 'cpu', 'CPU binding')
        D.require(any(exact_value(node['action']['review'], p) for p in self.c['review_pins']) and exact_value(D.read_pin(node['action']['review']), review), 'untrusted review')
        D.exact(review, ('schema', 'decision', 'node', 'binding_sha256', 'components'), 'CPU review')
        D.require(exact_value(review, {'schema':'unified-event-cpu-review-v1', 'decision':'accept', 'node':node['id'], 'binding_sha256':D.digest(binding), 'components':cpu_components()}), 'CPU review differs')
        conf = D.read_pin(binding['consumer_config'])
        D.require(type(conf['slots']) is int and exact_value(conf['slots'], self.graph['policy']['cpu_slots']), 'slot capacity differs')
        D.require(conf['controller'] == str(Path(self.c['state_dir']) / 'cpu-controller'), 'CPU controller differs')
        return True

    def jobdir(self, node):
        return Path(self.c['state_dir']) / 'workers' / node['id']

    def spawn(self, node, token):
        root = self.jobdir(node); root.mkdir(parents=True, exist_ok=True)
        lock = (root/'worker.lock').open('a')
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close(); return {'already_running':True}
        base = [self.c['python'], '-B', '-P', str(HERE), 'relaunch', '--config', self.ref['path'], '--sha256', self.ref['sha256'], '--node', node['id'], '--token', token]
        args = [*base[:4], 'worker', *base[5:], '--lock-fd', str(lock.fileno())]
        D.atomic(root/'RELAUNCH.json', {'argv':base, 'meaning':'acquire lock and resume authorized CPU intent'})
        with (root/'worker.log').open('ab', buffering=0) as log:
            p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True, pass_fds=(lock.fileno(),))
        lock.close()
        return {'pid':p.pid}

    def reserve_and_start(self, binding, node, token):
        root=self.jobdir(node); root.mkdir(parents=True, exist_ok=True)
        with policy_lock(self.c):
            D.require(not held(self.c), 'HOLD')
            policy=current_policy(self.c)
            D.require(policy.get('new_experiment_dispatch') == 'allow', 'HOLD')
            authorization={'schema':'unified-event-cpu-authorization-v2','graph_sha256':D.digest(self.graph),'node':node['id'],'token':token,'action':node['action'],'policy_snapshot':policy,'policy_sha256':D.digest(policy)}
            path=root/'AUTHORIZATION.json'
            if path.exists(): D.require(exact_value(json.loads(path.read_bytes()), authorization), 'authorization differs')
            else: D.atomic(path, authorization)
        return self.spawn(node, token)

    def authorized_intent(self, node, token):
        a=json.loads((self.jobdir(node)/'AUTHORIZATION.json').read_bytes())
        D.exact(a, ('schema','graph_sha256','node','token','action','policy_snapshot','policy_sha256'), 'authorization')
        D.require(a['schema']=='unified-event-cpu-authorization-v2' and a['graph_sha256']==D.digest(self.graph) and a['node']==node['id'] and a['token']==token and exact_value(a['action'],node['action']), 'authorization identity')
        policy=a['policy_snapshot']
        D.require(D.digest(policy)==a['policy_sha256'], 'authorization policy digest')
        D.require(policy.get('schema')=='nga-engineering-release-policy-v1' and policy.get('new_experiment_dispatch')=='allow', 'authorization policy')

    def observe(self, node, rec):
        root = self.jobdir(node); terminal = root/'TERMINAL.json'
        if terminal.exists():
            t = json.loads(terminal.read_bytes())
            D.exact(t, ('schema','token','exit_code','outcome','time','scientific_acceptance'), 'worker terminal')
            D.require(t['schema']=='unified-event-worker-terminal-v1' and t['scientific_acceptance'] is False and t['token'] == rec['token'] and type(t['exit_code']) is int, 'worker terminal differs')
            if t.get('outcome') != 'physical':
                return {'state':'uncertain', 'facts':[], 'failed_facts':[], 'evidence':[file_pin(terminal)]}
            self.authorized_intent(node, rec['token'])
            b=D.read_pin(node['action']['binding']); self.authorize(b,D.read_pin(node['action']['review']),node,D.digest(self.graph))
            conf=D.read_pin(b['consumer_config']); event,host,task,mounts=C.validate(conf)
            eid=event['event_id']; jid=C.digest({'event_id':eid,'stage':task['adapter'],'config_sha256':conf['config']['sha256']}); name='nga-cpu-'+jid[:48]
            owner={'schema':'unified-cpu-owner-v1','event_id':eid,'job_id':jid,'task':task,'config':conf,'source_sha256':file_pin(C.__file__)['sha256'],'name':name}
            launch=C.digest(owner); job=Path(conf['controller'])/'jobs'/jid
            D.require(exact_value(C.read(job/'OWNER.json'),owner) and exact_value(C.read(Path(conf['output']+'.cpu-consumer-owner.json')),owner), 'owner differs')
            bound=C.read(job/'BINDING.json'); ident=bound.get('container_id')
            D.require(type(ident) is str and __import__('re').fullmatch('[0-9a-f]{64}',ident) and exact_value(bound,{'launch_sha256':launch,'container_id':ident,'name':name}), 'binding differs')
            expected={'schema':'unified-cpu-terminal-v1','event_id':eid,'launch_sha256':launch,'container_id':ident,'exit_code':t['exit_code'],'scientific_acceptance':False}
            D.require(exact_value(C.read(job/'TERMINAL.json'),expected), 'consumer terminal differs')
            ack={'schema':'unified-cpu-ack-v1','event_id':eid,'launch_sha256':launch,'container_id':ident,'exit_code':t['exit_code'],'terminal_sha256':file_pin(job/'TERMINAL.json')['sha256'],'scientific_acceptance':False,'meaning':'physical completion'}
            D.require(exact_value(C.read(job/'ACK.json'),ack), 'consumer ACK differs')
            ok = t['exit_code'] == 0
            return {'state':'accepted' if ok else 'failed', 'facts':['success'] if ok else [], 'failed_facts':[] if ok else ['success'], 'evidence':[file_pin(terminal),file_pin(job/'ACK.json')]}
        return {'state':'running', 'facts':[], 'failed_facts':[], 'evidence':[]}

    def recover(self, node, rec):
        root = self.jobdir(node); root.mkdir(parents=True, exist_ok=True)
        if (root/'TERMINAL.json').exists(): return
        self.authorized_intent(node, rec['token'])
        self.spawn(node, rec['token'])


class Gate:
    def __init__(self, inner, c, fresh):
        self.inner, self.c, self.fresh = inner, c, fresh
        self.implementation_sha256 = inner.implementation_sha256
    def authorize(self, *a): return self.inner.authorize(*a)
    def observe(self, *a): return self.inner.observe(*a)
    def reserve_and_start(self, binding, node, token):
        D.require(not held(self.c) and self.fresh(), 'HOLD or resource observation expired')
        return self.inner.reserve_and_start(binding, node, token)


def unknown_snapshot(g):
    """Deployment seam: no physical provider is registered by this service."""
    return {'schema':'nga-dag-observation-v1', 'graph_sha256':D.digest(g), 'as_of':str(time.time()), 'authority':'adapter_observations', 'observations':{}, 'resources':{str(i):'unknown' for i in range(8)}}


def iteration(ref, provider=None, npu=None, cpu_factory=CPUAdapter, clock=time.monotonic):
    c,g = load_config(ref); root = Path(c['state_dir']); root.mkdir(parents=True, exist_ok=True)
    cpu = cpu_factory(c,g,ref)
    # Provider is an injected integration seam, never selected by configuration.
    diagnostics=[]; started = clock()
    try:
        snap = (provider or unknown_snapshot)(g); D.validate_snapshot(g,snap)
    except Exception as exc:
        diagnostics.append({'component':'provider','error':type(exc).__name__}); snap=unknown_snapshot(g); provider=None
    try:
        observed = float(snap['as_of'])
    except (ValueError, TypeError):
        observed = 0
    fresh = lambda: provider is not None and 0 <= clock()-started <= 5 and 0 <= time.time()-observed <= 5 and snap['authority'] == 'adapter_observations'
    if not fresh(): snap['resources'] = {str(i):'unknown' for i in range(8)}
    npu = npu or A.UnifiedDagAdapter(trusted_review_pins=c['review_pins'])
    gated = Gate(npu,c,fresh)
    registry = {'unified_cpu_v1':cpu, 'unified_npu_v1':gated}
    state_path=root/'dag'/'state.json'
    if state_path.exists():
        state=json.loads(state_path.read_bytes())
        for n in g['nodes']:
            if n['lane']=='cpu' and n['id'] in state['attempts']:
                try: cpu.recover(n,state['attempts'][n['id']])
                except Exception as exc: diagnostics.append({'component':'recovery','node':n['id'],'error':type(exc).__name__})
    # D.dispatch_once reconciles existing attempts even under HOLD. Block all new
    # admission with a transient registry gate; do not modify the pinned graph.
    if held(c):
        class HoldGate:
            def __init__(self, inner): self.inner=inner; self.implementation_sha256=inner.implementation_sha256
            def authorize(self,*a): raise ValueError('HOLD')
            def observe(self,*a): return self.inner.observe(*a)
            def reserve_and_start(self,*a): raise ValueError('HOLD')
        registry={k:HoldGate(v) for k,v in registry.items()}
    state = D.dispatch_once(g,snap,registry,root/'dag')
    D.atomic(root/'HEARTBEAT.json', {'time':time.time(), 'attempts':len(state['attempts']), 'hold':held(c), 'resource_provider':provider is not None, 'scientific_acceptance':False})
    D.atomic(root/'heartbeat.json', {'utc_seconds':time.time(),'completed':sum(x.get('status') in ('accepted','failed') for x in state['attempts'].values()),'state':'running','degraded':bool(diagnostics)})
    D.atomic(root/'diagnostic.json', {'errors':diagnostics,'utc_seconds':time.time()})
    return state


def worker(ref, key, token, lock_fd):
    c,g=load_config(ref); table=D.validate(g); n=table[key]
    D.require(n['lane']=='cpu', 'worker lane')
    state=json.loads((Path(c['state_dir'])/'dag'/'state.json').read_bytes())
    D.require(state['graph_sha256']==D.digest(g) and state['attempts'][key]['token']==token, 'worker intent')
    adapter=CPUAdapter(c,g,ref); root=adapter.jobdir(n); root.mkdir(parents=True,exist_ok=True)
    adapter.authorized_intent(n,token)
    D.require(lock_fd is not None, 'worker requires inherited lock')
    with os.fdopen(lock_fd, 'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'TERMINAL.json').exists(): return
        rc=1; outcome='uncertain'
        stop=threading.Event()
        def heartbeat():
            while not stop.is_set():
                try:
                    D.atomic(root/'heartbeat.json', {'utc_seconds':time.time(), 'state':'running', 'completed':0, 'phase':'consumer_wait_or_validation'})
                except Exception as exc:
                    print('heartbeat: '+type(exc).__name__+': '+str(exc),flush=True)
                stop.wait(10)
        thread=threading.Thread(target=heartbeat,daemon=True)
        thread.start()
        try:
            b=D.read_pin(n['action']['binding']); adapter.authorize(b,D.read_pin(n['action']['review']),n,D.digest(g))
            result=C.Consumer().run(D.read_pin(b['consumer_config']))
            rc=result['exit_code']; outcome='physical'
            print(json.dumps(result),flush=True)
        except Exception as exc:
            print(type(exc).__name__+': '+str(exc),flush=True)
        finally:
            stop.set(); thread.join()
            D.atomic(root/'TERMINAL.json', {'schema':'unified-event-worker-terminal-v1','token':token,'exit_code':rc,'outcome':outcome,'time':time.time(),'scientific_acceptance':False})
            notify(c['socket'])


def serve(ref):
    c,_=load_config(ref); root=Path(c['state_dir']); root.mkdir(parents=True,exist_ok=True)
    with (root/'service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        sockpath=Path(c['socket'])
        if sockpath.exists():
            D.require(sockpath.is_socket(), 'socket path occupied'); sockpath.unlink()
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
            sock.bind(str(sockpath)); os.chmod(sockpath,0o600); sock.settimeout(600)
            try:
                while True:
                    try: iteration(ref)
                    except Exception as exc:
                        print(type(exc).__name__+': '+str(exc),flush=True)
                    try: sock.recv(4096)
                    except socket.timeout: pass
            finally: sockpath.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=['serve','wake','worker','relaunch','policy-update']);p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);p.add_argument('--node');p.add_argument('--token');p.add_argument('--lock-fd',type=int);p.add_argument('--policy-source');a=p.parse_args()
    ref={'path':a.config,'sha256':a.sha256}
    if a.op=='serve': serve(ref)
    elif a.op=='wake': notify(load_config(ref)[0]['socket'])
    elif a.op=='policy-update':
        D.require(a.policy_source is not None, 'policy source required')
        c,_=load_config(ref); policy_update(c,a.policy_source); notify(c['socket'])
    elif a.op=='relaunch':
        c,g=load_config(ref); n=D.validate(g)[a.node]; adapter=CPUAdapter(c,g,ref); adapter.authorized_intent(n,a.token); adapter.spawn(n,a.token)
    else: worker(ref,a.node,a.token,a.lock_fd)

if __name__ == '__main__': main()
