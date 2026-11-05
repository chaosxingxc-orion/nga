#!/usr/bin/env python3
"""Durable CPU consumer for unified host events; ACK records physical exit only.

Invoke `run --config ... --sha256 ...` in a durable supervisor. All consumers
sharing a capacity must use the same controller directory and slot count.
Physical ACK is not scientific acceptance; real Docker and NPU remain unqualified.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import tempfile
from contextlib import contextmanager, ExitStack

ENTRY = '/opt/nga/entrypoint.sh'
CONFIG = '/run/nga/config.json'
OUTPUT = '/run/nga/output'
EXPORT = '/run/nga/export'
SCORE = '/run/nga/score'
CPU_ENV = {'TORCH_DEVICE_BACKEND_AUTOLOAD':'0', 'HF_HUB_OFFLINE':'1', 'TRANSFORMERS_OFFLINE':'1'}
ACTIONS = {'native-panel-export-v2', 'native-panel-score-v1'}
HEX = re.compile(r'[0-9a-f]{64}\Z')


def need(v, msg):
    if not v: raise ValueError(msg)


def digest(v):
    return hashlib.sha256((json.dumps(v, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()).hexdigest()


def safe(s):
    need(type(s) is str and os.path.isabs(s) and os.path.normpath(s) == s and ',' not in s, 'invalid path')
    p = Path(s)
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path')
    return p


def read(p):
    return json.loads(safe(str(p)).read_bytes())


def pin(ref):
    need(type(ref) is dict and set(ref) == {'path', 'sha256'} and type(ref['sha256']) is str and HEX.fullmatch(ref['sha256']), 'invalid pin')
    data = safe(ref['path']).read_bytes()
    need(hashlib.sha256(data).hexdigest() == ref['sha256'], 'pinned file changed')
    return json.loads(data)


def write(path, value):
    path = safe(str(path)); path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
        d = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(d)
        finally: os.close(d)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


@contextmanager
def lock(path, nonblock=False):
    path = safe(str(path)); path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblock else 0))
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)


def evidence(c):
    event = pin(c['event']); host = pin(c['host_config'])
    need(set(event) == {'schema','event_id','evidence','scientific_acceptance'} and event['schema'] == 'unified-cpu-handoff-v1' and event['scientific_acceptance'] is False, 'event schema')
    ev = event['evidence']; need(type(ev) is dict and set(ev) == {'terminal','release'} and event['event_id'] == digest(ev), 'event identity')
    t, r = pin(ev['terminal']), pin(ev['release'])
    lease = host['lease']; launch = {k:host[k] for k in ('name','image','entrypoint','mounts','task','config','output')}
    # Lease identity intentionally follows the host's accepted config hash convention.
    try:
        from . import unified_resource_lease_v1 as U
    except ImportError:
        import unified_resource_lease_v1 as U
    need(ev['terminal']['path'] == str(Path(host['output'] + '.host-v1')/'terminal.json') and ev['release']['path'] == str(U.paths(lease, 'release')[1]), 'host evidence paths differ')
    b = r.get('binding', {}); chips = r.get('chips')
    need(t.get('schema') == 'unified-container-terminal-v1' and type(t.get('exit_code')) is int and t['exit_code'] == 0 and t.get('launch_sha256') == digest(launch) == lease['task_sha256'], 'terminal identity or failure')
    need(r.get('schema') == 'unified-resource-transaction-v1' and r.get('allocation') == lease['allocation'] and r.get('after_sha256') == digest(r.get('after')) and b.get('schema') == 'unified-resource-binding-v1' and r.get('op') == 'release' and r.get('scientific_acceptance') is False and r.get('config_sha256') == U.config_hash(lease) and b.get('config_sha256') == r['config_sha256'] and b.get('lease_id') == lease['lease_id'] and b.get('task_sha256') == lease['task_sha256'] and b.get('container') == host['name'] and b.get('container_id') == t.get('container_id') and r.get('exit_code') == t['exit_code'] and type(chips) is list and chips and b.get('chips') == chips, 'release identity')
    need(all(x.get('run') == lease['run'] for x in r.get('entries', [])) and len(r.get('entries', [])) == len(chips) and sorted(x.get('chip') for x in r['entries']) == sorted(chips), 'release run')
    need(all(len([x for x in r['after']['free'] if x.get('chip') == chip and x.get('previous_run') == lease['run'] and x.get('release_evidence') == ev['release']['path']]) == 1 and not any(x.get('chip') == chip for x in r['after']['allocation']) for chip in chips), 'release snapshot')
    return event, host


def validate(c):
    need(type(c) is dict and set(c) == {'schema','event','host_config','image','image_env','config','inputs','output','controller','slots','export_receipt'}, 'consumer fields')
    need(c['schema'] == 'unified-cpu-consumer-v1' and type(c['image']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', c['image']), 'immutable image ID required')
    need(type(c['slots']) is int and 1 <= c['slots'] <= 1024, 'slot count')
    controller = safe(c['controller']); out = safe(c['output']); need(out.is_dir(), 'output directory')
    need(not (str(controller) == str(out) or str(controller).startswith(str(out)+'/') or str(out).startswith(str(controller)+'/')), 'controller overlaps output')
    task = pin(c['config']); event, host = evidence(c)
    env = c['image_env']
    need(type(env) is list and all(type(x) is str and '=' in x and x.split('=',1)[0] for x in env) and len({x.split('=',1)[0] for x in env}) == len(env), 'image environment')
    need(task.get('schema') == 'nga-unified-config-v1' and task.get('runtime') == 'cpu' and task.get('adapter') in ACTIONS, 'unregistered action')
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[1]/'docker/engineering-base/schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(task)
    need(type(c['inputs']) is list and c['inputs'], 'input mounts')
    mounts = []
    for m in c['inputs']:
        need(type(m) is dict and set(m) == {'source','target'} and safe(m['source']).exists(), 'input mount')
        src=safe(m['source']); dst=safe(m['target'])
        need(not (stat.S_ISCHR(src.stat().st_mode) or stat.S_ISBLK(src.stat().st_mode)), 'device source')
        need(all(not (src == Path(p) or src.is_relative_to(p) or Path(p).is_relative_to(src)) for p in ('/dev','/proc','/sys')), 'device source')
        allowed = ('/data','/model',OUTPUT) if task['adapter'] == 'native-panel-export-v2' else ('/data','/model',EXPORT)
        need(any(dst == Path(p) or dst.is_relative_to(p) for p in allowed), 'input target outside registered namespace')
        mounts.append((m['source'],m['target'],False))
    base = EXPORT if task['adapter'] == 'native-panel-export-v2' else SCORE
    mounts += [(c['config']['path'], CONFIG, False), (c['output'], base, True)]
    for i, (src,dst,rw) in enumerate(mounts):
        for s,d,_ in mounts[:i]:
            need(not (dst == d or dst.startswith(d+'/') or d.startswith(dst+'/')), 'overlapping targets')
            need(not ((rw or s == c['output']) and (src == s or src.startswith(s+'/') or s.startswith(src+'/'))), 'overlapping output')
    safe(task['output']); need(task['output'] == base+'/result', 'output must be stage result child')
    for key in (('source','source_config','panel_manifest') if task['adapter'] == 'native-panel-export-v2' else ('manifest',)):
        p = task[key]; safe(p)
        need(any(p == m['target'] or p.startswith(m['target']+'/') for m in c['inputs']), 'input outside mount')
    if task['adapter'] == 'native-panel-export-v2':
        need(c['export_receipt'] is None, 'export cannot depend on receipt')
        need(task['source'] == OUTPUT+'/result' and any(m['target'] == OUTPUT and m['source'] == host['output'] for m in c['inputs']), 'export source differs from event host output')
        need(any(Path(task['source_config']).is_relative_to(m['target']) and str(Path(m['source'])/Path(task['source_config']).relative_to(m['target'])) == host['config']['path'] for m in c['inputs']) and task['source_config_sha256'] == host['config']['sha256'], 'export source config differs from host')
    else:
        receipt=pin(c['export_receipt'])
        need(receipt.get('schema') == 'unified-cpu-export-receipt-v1' and receipt.get('event_id') == event['event_id'] and receipt.get('scientific_acceptance') is False, 'export receipt event')
        need(type(receipt.get('job_id')) is str and HEX.fullmatch(receipt['job_id']), 'export job identity')
        need(task['manifest'] == EXPORT+'/result/manifest.json' and task['manifest_sha256'] == receipt.get('manifest_sha256'), 'export manifest differs')
        need(any(m['target'] == EXPORT and m['source'] == receipt.get('output') for m in c['inputs']), 'export mount differs')
        root=safe(c['controller'])/'jobs'/receipt['job_id']
        need(c['export_receipt']['path'] == str(root/'EXPORT.json'), 'export receipt path')
        owner=read(root/'OWNER.json'); terminal=read(root/'TERMINAL.json'); ack=read(root/'ACK.json')
        need(owner.get('event_id') == event['event_id'] and owner.get('job_id') == receipt['job_id'] and owner['config']['output'] == receipt['output'] and owner['task']['adapter'] == 'native-panel-export-v2' and terminal.get('exit_code') == 0 and ack.get('terminal_sha256') == hashlib.sha256((root/'TERMINAL.json').read_bytes()).hexdigest() and receipt.get('ack_sha256') == hashlib.sha256((root/'ACK.json').read_bytes()).hexdigest(), 'export receipt ancestry')
        need(hashlib.sha256((Path(receipt['output'])/'result/manifest.json').read_bytes()).hexdigest() == receipt['manifest_sha256'], 'export manifest changed')
        need(read(Path(receipt['output'])/'result/manifest.json').get('records') == EXPORT+'/result/records', 'export records outside stage')
    return event, host, task, mounts


def args(c, mounts, name, launch):
    a = ['create','--name',name,'--runtime=runc','--network=none','--restart=no','--ipc=private','--cgroupns=private','--label','nga.cpu.launch='+launch]
    for k,v in CPU_ENV.items(): a += ['--env',k+'='+v]
    for src,dst,rw in mounts: a += ['--mount',f'type=bind,src={src},dst={dst}'+('' if rw else ',readonly')]
    return a + ['--entrypoint',ENTRY,c['image'],CONFIG]


class Docker:
    def call(self, *args):
        return subprocess.run(['docker',*args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    def inspect(self, name):
        need(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name), 'invalid container name')
        p = subprocess.run(['docker','inspect',name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode:
            # Match one complete known diagnostic for this name, with no other output.
            missing = (f'error: no such object: {name}', f'Error: No such object: {name}',
                       f'Error response from daemon: No such container: {name}')
            if p.stdout in ('', '[]', '[]\n', '[]\r\n') and any(p.stderr in (s, s+'\n', s+'\r\n') for s in missing): return None
            raise RuntimeError('docker inspect failed: '+p.stderr.strip())
        v=json.loads(p.stdout); need(type(v) is list and len(v)==1 and type(v[0]) is dict, 'inspect result'); return v[0]
    def create(self, c, mounts, name, launch): return self.call(*args(c,mounts,name,launch)).strip()
    def image_env(self, image):
        v=json.loads(self.call('image','inspect',image))
        need(len(v)==1 and v[0].get('Id')==image, 'image identity differs')
        return (v[0].get('Config') or {}).get('Env') or []
    def start(self, name): self.call('start',name)
    def wait(self, name): return int(self.call('wait',name).strip())


def verify(ob,c,mounts,name,launch):
    need(type(ob) is dict and type(ob.get('Id')) is str and re.fullmatch(r'[0-9a-f]{64}',ob['Id']), 'container ID')
    cfg=ob.get('Config') or {}; hc=ob.get('HostConfig') or {}
    need(ob.get('Name','').lstrip('/') == name and ob.get('Image') == c['image'] and cfg.get('Entrypoint') == [ENTRY] and cfg.get('Cmd') == [CONFIG] and (cfg.get('Labels') or {}).get('nga.cpu.launch') == launch, 'container launch differs')
    need(hc.get('NetworkMode') == 'none' and not hc.get('Devices') and not hc.get('Privileged') and not hc.get('DeviceRequests'), 'container resource configuration differs')
    need(all(hc.get(k) == v for k,v in {'PidMode':'', 'IpcMode':'private', 'UTSMode':'', 'UsernsMode':'', 'CgroupnsMode':'private'}.items()), 'container namespaces differ')
    expected=dict(x.split('=',1) for x in c['image_env']); expected.update(CPU_ENV)
    actual=cfg.get('Env'); need(type(actual) is list and all(type(x) is str and '=' in x for x in actual) and len({x.split('=',1)[0] for x in actual}) == len(actual) and dict(x.split('=',1) for x in actual) == expected, 'container environment differs')
    need(hc.get('Runtime') == 'runc' and (hc.get('RestartPolicy') or {}).get('Name') == 'no' and not hc.get('DeviceCgroupRules') and not hc.get('CapAdd') and not hc.get('GroupAdd'), 'container runtime differs')
    need(sorted((m.get('Source'),m.get('Destination'),m.get('RW')) for m in ob.get('Mounts',[]) if m.get('Type') == 'bind') == sorted(mounts) and len(ob.get('Mounts',[])) == len(mounts), 'container mounts differ')
    need((ob.get('State') or {}).get('Status') in ('created','running','exited'), 'container state uncertain')
    return ob


class Consumer:
    def __init__(self, docker=None, validate_result=None):
        self.docker = docker or Docker()
        # Optional post-exit inspection, never a scientific acceptance decision.
        self.validate_result = validate_result or (lambda c, terminal: None)

    def run(self, c):
        event, host, task, mounts = validate(c)
        image_env=self.docker.image_env(c['image'])
        need(type(image_env) is list and len(image_env)==len(c['image_env']) and sorted(image_env)==sorted(c['image_env']), 'image environment baseline differs')
        ctl = safe(c['controller']); ctl.mkdir(parents=True, exist_ok=True)
        eid=event['event_id']; jid=digest({'event_id':eid,'stage':task['adapter'],'config_sha256':c['config']['sha256']}); name='nga-cpu-'+jid[:48]
        source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        identity={'schema':'unified-cpu-owner-v1','event_id':eid,'job_id':jid,'task':task,'config':c,'source_sha256':source_hash,'name':name}
        launch=digest(identity); root=ctl/'jobs'/jid; root.mkdir(parents=True,exist_ok=True)
        # An output lock prevents different events sharing a writable destination.
        with ExitStack() as stack:
            for path in sorted((root/'owner.lock', Path(c['output']+'.cpu-consumer.lock')),key=str): stack.enter_context(lock(path,True))
            owner=root/'OWNER.json'
            output_owner=Path(c['output']+'.cpu-consumer-owner.json')
            if output_owner.exists(): need(read(output_owner)==identity, 'output owner changed')
            else: write(output_owner,identity)
            if owner.exists(): need(read(owner)==identity, 'owner identity changed')
            else: write(owner,identity)
            pending=root/'PENDING.json'; binding=root/'BINDING.json'; terminal=root/'TERMINAL.json'; ack=root/'ACK.json'
            if not pending.exists(): write(pending,{'launch_sha256':launch,'event_id':eid})
            else: need(read(pending)=={'launch_sha256':launch,'event_id':eid}, 'pending identity')
            # Slot files are durable and count reservations including uncertain creates.
            slot=ctl/'slots'/ (jid+'.json')
            with lock(ctl/'controller.lock'):
                settings=ctl/'CONTROLLER.json'; expected={'schema':'unified-cpu-controller-v1','slots':c['slots']}
                if settings.exists(): need(read(settings)==expected, 'controller capacity changed')
                else: write(settings,expected)
                if not terminal.exists() and not slot.exists():
                    active=list((ctl/'slots').glob('*.json')) if (ctl/'slots').exists() else []
                    need(len(active)<c['slots'], 'CPU slots full')
                    write(slot,{'event_id':eid,'launch_sha256':launch})
                if slot.exists(): need(read(slot)=={'event_id':eid,'launch_sha256':launch}, 'slot identity')
            # Revalidate all pins before touching the physical boundary, including on recovery.
            validate(c)
            ob=self.docker.inspect(name)
            if ob is None:
                need(not binding.exists() and not terminal.exists(), 'retained container missing')
                ident=self.docker.create(c,mounts,name,launch)
                ob=self.docker.inspect(name); verify(ob,c,mounts,name,launch)
                need(ob['Id']==ident, 'create identity differs')
            verify(ob,c,mounts,name,launch); ident=ob['Id']
            bound={'launch_sha256':launch,'container_id':ident,'name':name}
            if binding.exists(): need(read(binding)==bound, 'binding changed')
            else: write(binding,bound)
            state=ob['State']['Status']
            if state == 'created':
                need(not terminal.exists(), 'terminal container restarted')
                validate(c); self.docker.start(name)
            running=root/'RUNNING.json'
            if state != 'exited':
                record={'launch_sha256':launch,'container_id':ident}
                if running.exists(): need(read(running)==record, 'running identity')
                else: write(running,record)
                self.docker.wait(name)
            ob=verify(self.docker.inspect(name),c,mounts,name,launch)
            need(ob['Id'] == ident, 'container ID changed during wait')
            state=ob['State']; need(state.get('Status')=='exited' and state.get('Running') is False and type(state.get('ExitCode')) is int, 'physical exit uncertain')
            result={'schema':'unified-cpu-terminal-v1','event_id':eid,'launch_sha256':launch,'container_id':ident,'exit_code':state['ExitCode'],'scientific_acceptance':False}
            if terminal.exists(): need(read(terminal)==result, 'terminal changed')
            else: write(terminal,result)
            # Release capacity before result validation; crash recovery also performs this step.
            with lock(ctl/'controller.lock'):
                if slot.exists():
                    need(read(slot)=={'event_id':eid,'launch_sha256':launch}, 'slot identity')
                    slot.unlink(); fd=os.open(slot.parent,os.O_RDONLY|os.O_DIRECTORY)
                    try: os.fsync(fd)
                    finally: os.close(fd)
            validate(c)
            receipt={'schema':'unified-cpu-ack-v1','event_id':eid,'launch_sha256':launch,'container_id':ident,'exit_code':state['ExitCode'],'terminal_sha256':hashlib.sha256(terminal.read_bytes()).hexdigest(),'scientific_acceptance':False,'meaning':'physical completion'}
            if ack.exists(): need(read(ack)==receipt, 'ACK changed')
            else: write(ack,receipt)
            if task['adapter'] == 'native-panel-export-v2' and state['ExitCode'] == 0:
                manifest=Path(c['output'])/'result/manifest.json'
                if manifest.is_file():
                    need(read(manifest).get('records') == EXPORT+'/result/records', 'export records outside stage')
                    export_receipt={'schema':'unified-cpu-export-receipt-v1','event_id':eid,'job_id':jid,'output':c['output'],'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'ack_sha256':hashlib.sha256(ack.read_bytes()).hexdigest(),'scientific_acceptance':False}
                    path=root/'EXPORT.json'
                    if path.exists(): need(read(path)==export_receipt, 'export receipt changed')
                    else: write(path,export_receipt)
            self.validate_result(c,result)
            return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('op',choices=['run']); p.add_argument('--config',required=True); p.add_argument('--sha256',required=True)
    a=p.parse_args(); c=pin({'path':a.config,'sha256':a.sha256}); print(json.dumps(Consumer().run(c),sort_keys=True))


if __name__ == '__main__': main()
