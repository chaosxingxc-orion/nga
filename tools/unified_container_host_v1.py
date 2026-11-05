#!/usr/bin/env python3
"""Retained engineering-base Docker lifecycle; launch authority remains external."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid
from contextlib import ExitStack

try:
    from . import unified_resource_lease_v1 as U
    from . import r3_resource_adapter as R
except ImportError:
    import unified_resource_lease_v1 as U
    import r3_resource_adapter as R

ENTRYPOINTS = {'nga-engineering-v1': ['/opt/nga/entrypoint.sh']}
DRIVERS = ('/usr/local/Ascend/driver', '/usr/local/sbin', '/etc/ascend_install.info')
COMMON_DEVICES = ('/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc')
CONFIG_TARGET = '/run/nga/config.json'
OUTPUT_TARGET = '/run/nga/output'
DATA_TARGETS = ('/model', '/data')


def fixed_env(chips):
    return {'ASCEND_RT_VISIBLE_DEVICES': ','.join(map(str, chips)), 'HF_HUB_OFFLINE': '1',
            'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false', 'TASK_QUEUE_ENABLE': '2'}


def env_map(entries):
    U.need(type(entries) is list, 'environment missing')
    result = {}
    for entry in entries:
        U.need(type(entry) is str and '=' in entry, 'invalid environment entry')
        key, value = entry.split('=', 1)
        U.need(bool(key) and key not in result, 'duplicate or empty environment key')
        result[key] = value
    return result


def contained(path, root):
    return path == root or path.startswith(root + '/')


def task_path(path, source, target):
    # Absolute symlinks resolve in the container, not relative to the host bind.
    # Refuse all symlink components instead of guessing at container resolution.
    relative = path[len(target):].lstrip('/')
    current = Path(source)
    for part in Path(relative).parts:
        current = current / part
        U.need(not current.is_symlink(), 'task path contains symlink')


def launch_spec(c):
    # The lease acceptance pins task_sha256; bind the entire immutable launch to it.
    return {k: c[k] for k in ('name', 'image', 'entrypoint', 'mounts', 'task', 'config', 'output')}


def mount_list(c):
    return [(m['source'], m['target'], False) for m in c['mounts']] + [
        (c['config']['path'], CONFIG_TARGET, False), (c['output'], OUTPUT_TARGET, True)] + [(p, p, False) for p in DRIVERS]


def device_list(chips):
    return list(COMMON_DEVICES) + [f'/dev/davinci{x}' for x in chips]


def create_args(c, chips, image_id):
    labels = {'nga.lease_id': c['lease']['lease_id'], 'nga.task_sha256': c['lease']['task_sha256'],
              'nga.launch_sha256': U.digest(launch_spec(c))}
    args = ['create', '--name', c['name'], '--network=none', '--shm-size', '16g',
            '--ulimit', 'memlock=-1:-1', '--ulimit', 'stack=67108864:67108864']
    for k, v in sorted(labels.items()): args += ['--label', k+'='+v]
    for d in device_list(chips): args += ['--device', d+':'+d+':rwm']
    for key, value in fixed_env(chips).items():
        args += ['--env', key+'='+value]
    for src, dst, rw in mount_list(c):
        args += ['--mount', f'type=bind,src={src},dst={dst}' + ('' if rw else ',readonly')]
    # The pinned image supplies its entrypoint. Override it explicitly to make the
    # inspected contract independent of an accidental image default.
    args += ['--entrypoint', ENTRYPOINTS[c['entrypoint']][0], image_id, CONFIG_TARGET]
    return args


class Docker(U.DockerQuery):
    def call(self, *args):
        return subprocess.run(['docker', *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    def image_id(self, ref):
        result = json.loads(self.call('image', 'inspect', ref))
        U.need(type(result) is list and len(result)==1, 'image inspection uncertain')
        ident = result[0].get('Id'); U.need(isinstance(ident, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', ident), 'image ID')
        if ref.startswith('sha256:'): U.need(ref == ident, 'local image ID differs')
        else: U.need(ref in (result[0].get('RepoDigests') or []), 'registry image digest differs')
        return ident
    def image_env(self, ident):
        result = json.loads(self.call('image', 'inspect', ident))
        U.need(type(result) is list and len(result)==1 and result[0].get('Id')==ident, 'image inspection uncertain')
        cfg = result[0].get('Config')
        U.need(type(cfg) is dict and 'Env' in cfg, 'image environment missing')
        return env_map(cfg['Env'] if cfg['Env'] is not None else [])
    def create(self, c, chips, image_id): return self.call(*create_args(c, chips, image_id)).strip()
    def start(self, name): self.call('start', name)
    def follow_logs(self, name, path):
        # A separate file per attempt makes replay after a crash explicit.
        with open(path, 'ab', buffering=0) as log:
            return subprocess.Popen(['docker','logs','--timestamps','--follow',name],
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                    start_new_session=True, close_fds=True)
    def wait(self, name): return int(self.call('wait', name).strip())


def path_ok(s):
    return type(s) is str and os.path.isabs(s) and os.path.normpath(s)==s and ',' not in s and not any(p.is_symlink() for p in (Path(s), *Path(s).parents))


def validate(c):
    U.need(type(c) is dict and set(c)=={'schema','lease','name','image','entrypoint','mounts','task','config','output','poll_seconds'}, 'host config fields')
    U.need(c['schema']=='unified-container-host-v1', 'host schema')
    U.validate_config(c['lease']); U.accepted_identity(c['lease'])
    U.need(type(c['name']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', c['name']), 'container name')
    U.need(type(c['image']) is str and re.fullmatch(r'(?:sha256:[0-9a-f]{64}|[^\s@]+@sha256:[0-9a-f]{64})', c['image']), 'immutable image required')
    U.need(c['entrypoint'] in ENTRYPOINTS, 'unregistered entrypoint')
    U.need(type(c['task']) is dict and U.ref(c['config'])==c['task'], 'pinned adapter config differs')
    U.need(path_ok(c['config']['path']), 'config path')
    U.need(U.digest(launch_spec(c))==c['lease']['task_sha256'], 'launch identity')
    U.need(type(c['mounts']) is list and path_ok(c['output']) and Path(c['output']).is_dir(), 'output directory or mounts')
    for m in c['mounts']:
        U.need(type(m) is dict and set(m)=={'source','target'} and path_ok(m['source']) and path_ok(m['target']) and Path(m['source']).exists(), 'mount')
        U.need(any(contained(m['target'], root) for root in DATA_TARGETS), 'mount target outside data namespaces')
    mounts = mount_list(c)
    targets = [x[1] for x in mounts]
    U.need(all(not (a==b or a.startswith(b+'/') or b.startswith(a+'/')) for i,a in enumerate(targets) for b in targets[i+1:]), 'overlapping mount targets')
    U.need(all(not (src==c['output'] or src.startswith(c['output']+'/') or c['output'].startswith(src+'/')) for src,_,rw in mounts if not rw), 'output overlaps read-only source')
    U.need(type(c['poll_seconds']) in (float,int) and 0<c['poll_seconds']<=600, 'poll interval')
    # Validate exactly the schema used by the image, prior to claiming a device.
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[1]/'docker/engineering-base/schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(c['task'])
    if 'output' in c['task']:
        output = c['task']['output']
        U.need(type(output) is str and os.path.isabs(output) and os.path.normpath(output)==output and contained(output, OUTPUT_TARGET), 'adapter output outside writable bind')
        task_path(output, c['output'], OUTPUT_TARGET)
    # All absolute task paths (apart from output) must resolve through a
    # declared read-only bind; hashes inside the adapter remain its responsibility.
    def paths(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key != 'output': yield from paths(item)
        elif isinstance(value, list):
            for item in value: yield from paths(item)
        elif isinstance(value, str) and value.startswith('/'):
            yield value
    task=c['task']
    family=task.get('adapter')=='k1-family-train-v2'
    if family:
        recipes={'k1-base-0.8b-3116-v2':'0.8B','k1-base-2b-3116-v2':'2B',
                 'k1-base-4b-3116-v2':'4B','k1-base-9b-3116-v2':'9B'}
        assets='/opt/nga/components/training/family-assets-v2/'
        expected=(assets+'model-'+recipes[task['recipe_id']]+'.json',assets+'dataset.json')
        for obj, asset in zip((task['model'],task['dataset']),expected):
            U.need(obj['manifest']==asset, 'unregistered image manifest')
        for obj, root in ((task['model'],'/model'),(task['dataset'],'/data')):
            U.need(contained(obj['path'],root), 'family input outside typed namespace')
        if task['resume'] is not None:
            checkpoint=task['resume']['path']
            U.need(os.path.dirname(checkpoint)==task['output']+'/ckpt' and
                   re.fullmatch(r'step_\d{6}\.pt',os.path.basename(checkpoint)) is not None,
                   'checkpoint outside owned output')
            task_path(checkpoint,c['output'],OUTPUT_TARGET)
    image_assets=set(expected) if family else set()
    checkpoint=task['resume']['path'] if family and task['resume'] is not None else None
    for path in paths(task):
        U.need(os.path.normpath(path)==path, 'task path not normalized')
        if path in image_assets or path==checkpoint:
            continue
        matches = [m for m in c['mounts'] if contained(path, m['target'])]
        U.need(len(matches)==1, 'task path outside read-only mounts')
        task_path(path, matches[0]['source'], matches[0]['target'])
    U.locked_config(c['lease'])
    return c


def verify(c, docker, ident, chips, image_id):
    ob=U.retained(docker, c['name'], ident, chips)
    U.need(ob.get('Image')==image_id, 'container image differs')
    cfg=ob.get('Config') or {}; labels=cfg.get('Labels') or {}
    U.need(cfg.get('Entrypoint')==ENTRYPOINTS[c['entrypoint']] and cfg.get('Cmd')==[CONFIG_TARGET], 'container entrypoint or config differs')
    U.need(labels.get('nga.launch_sha256')==U.digest(launch_spec(c)), 'launch digest differs')
    U.need(labels.get('nga.lease_id')==c['lease']['lease_id'] and labels.get('nga.task_sha256')==c['lease']['task_sha256'], 'container task binding differs')
    expected=sorted(mount_list(c)); actual=ob.get('Mounts')
    U.need(type(actual) is list and all(x.get('Type')=='bind' for x in actual), 'container mounts missing')
    U.need(sorted((x.get('Source'),x.get('Destination'),x.get('RW')) for x in actual)==expected, 'container mounts differ')
    host=ob['HostConfig']
    U.need(host.get('Privileged') is False and host.get('NetworkMode')=='none', 'container privilege or network differs')
    U.need(host.get('RestartPolicy')=={'Name':'no','MaximumRetryCount':0}, 'container restart policy differs')
    U.need(all(k in host and host[k] in (None, []) for k in ('DeviceCgroupRules','DeviceRequests')), 'extra or uncertain device grants')
    devices=host['Devices']
    U.need(sorted((x.get('PathOnHost'),x.get('PathInContainer'),x.get('CgroupPermissions')) for x in devices)==sorted((d,d,'rwm') for d in device_list(chips)), 'container device map differs')
    expected_env=docker.image_env(image_id).copy(); expected_env.update(fixed_env(chips))
    U.need(env_map(cfg.get('Env'))==expected_env, 'container environment differs')
    U.need(U.ref(c['config'])==c['task'], 'pinned adapter config changed')
    return ob


def verify_binding_owned(c, docker, claim, image_id):
    """Check the committed binding and its current ledger generation under lock."""
    lease=c['lease']; b=R.load(U.paths(lease,'binding')[1])
    expected=dict(schema='unified-resource-binding-v1',config_sha256=U.config_hash(lease),
                  lease_id=lease['lease_id'],task_sha256=lease['task_sha256'],
                  chips=claim['chips'],container=c['name'],container_id=b.get('container_id'))
    U.need(b==expected and claim.get('config_sha256')==U.config_hash(lease) and
           claim.get('op')=='claim', 'binding or claim identity differs')
    doc=R.load(lease['allocation']); R.validate_doc(doc)
    U.need([x for x in doc['allocation'] if x['chip'] in claim['chips']]==claim['entries'] and
           not any(x['chip'] in claim['chips'] for x in doc['free']), 'claim generation differs')
    return b, verify(c,docker,b['container_id'],claim['chips'],image_id)


def observe_binding(c, docker, claim, image_id, start=False):
    lease=c['lease']; alloc=U.locked_config(lease)
    with R.locked(alloc):
        U.accepted_identity(lease)
        pins=U.authority_files(lease)
        snapshot=U.authorize(lease) if start else None
        b, ob=verify_binding_owned(c,docker,claim,image_id)
        if start:
            U.need(ob['State'].get('Status')=='created' and ob['State'].get('Running') is False, 'container state changed before start')
            U.accepted_identity(lease)
            U.need(U.authorize(lease)==snapshot and U.authority_files(lease)==pins, 'dispatch policy or pin changed')
            # Cooperative policy writers use this same lock through the actual start.
            docker.start(c['name'])
        return b, ob


def metadata_dir(c):
    return Path(c['output'] + '.host-v1')


def owner_identity(c):
    return {'schema':'unified-container-owner-v1', 'launch_spec':launch_spec(c),
            'lease_config_sha256':U.config_hash(c['lease']),
            'lease_id':c['lease']['lease_id'], 'output':c['output']}


def establish_owner(c, stack):
    # Two independent locks prevent both same-output/different-lease and
    # same-lease/different-output supervisors from racing.
    meta=metadata_dir(c); lease_dir=Path(c['lease']['journal'])/c['lease']['lease_id']
    for p in (meta, lease_dir):
        U.need(not any(x.is_symlink() for x in (p,*p.parents)), 'symlink host metadata path')
        p.mkdir(parents=True,exist_ok=True)
    for p in sorted((meta/'supervisor.lock',lease_dir/'host-supervisor.lock'),key=str):
        f=stack.enter_context(open(p,'a+'))
        try: fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('supervisor already active')
    identity=owner_identity(c)
    for p in (meta/'OWNER.json',lease_dir/'host-owner.json'):
        if p.exists(): U.need(R.load(p)==identity, 'host owner differs')
    for p in (meta/'OWNER.json',lease_dir/'host-owner.json'):
        if not p.exists(): R.write_atomic(p,identity)
    return meta


def publish_handoff(c, meta, terminal, release):
    t=R.read_bytes(terminal); r=R.read_bytes(release)
    result=R.load(terminal); rel=R.load(release)
    U.need(result['container_id']==rel['binding']['container_id'] and result['exit_code']==rel['exit_code'] and
           result['launch_sha256']==U.digest(launch_spec(c)) and rel['op']=='release' and
           rel['config_sha256']==U.config_hash(c['lease']) and rel['scientific_acceptance'] is False, 'handoff evidence differs')
    evidence={'terminal':{'path':str(terminal),'sha256':R.sha_bytes(t)},
              'release':{'path':str(release),'sha256':R.sha_bytes(r)}}
    record={'schema':'unified-cpu-handoff-v1','event_id':U.digest(evidence),
            'evidence':evidence,'scientific_acceptance':False}
    path=meta/'cpu-handoff.json'
    if path.exists(): U.need(R.load(path)==record,'handoff event differs')
    else: R.write_atomic(path,record)
    return record


def heartbeat(c, meta, ident, state):
    adapter=Path(c['output'])
    target=c['task'].get('output',OUTPUT_TARGET)
    if isinstance(target,str) and (target==OUTPUT_TARGET or target.startswith(OUTPUT_TARGET+'/')):
        adapter=adapter / target[len(OUTPUT_TARGET):].lstrip('/')
    path=adapter/'heartbeat.json'; progress=None
    if path.is_file() and not path.is_symlink():
        try:
            safe=R.validated_path(path)
            with safe.open('rb') as f: raw=f.read(65537)
            if len(raw)<=65536:
                data=json.loads(raw)
                if isinstance(data,dict):
                    progress={'path':str(path),'sha256':R.sha_bytes(raw),
                              'phase':data.get('phase'), 'completed':data.get('completed',data.get('completed_items'))}
        except (OSError,ValueError,RuntimeError): pass
    R.write_atomic(meta/'heartbeat.json',{'utc':R.utc(),'phase':'supervising',
                   'host_alive':True,'container_status':state.get('Status'),
                   'container_id':ident,'adapter_heartbeat':progress})


def run(c, docker=None, event=None, relaunch=None):
    validate(c); docker=docker or Docker(); event=event or threading.Event()
    with ExitStack() as stack:
        meta=establish_owner(c,stack)
        return run_owned(c,docker,event,meta,relaunch)


def run_owned(c, docker, event, meta, relaunch):
    lease=c['lease']; terminal=meta/'terminal.json'; binding=U.paths(lease,'binding')[1]
    if relaunch is not None:
        path=meta/'RELAUNCH.json'
        if path.exists(): U.need(R.load(path)==relaunch,'relaunch pins differ')
        else: R.write_atomic(path,relaunch)
    try:
        image_id=docker.image_id(c['image'])
        if terminal.exists():
            b=R.load(binding); verify(c,docker,b['container_id'],b['chips'],image_id)
            result=R.load(terminal)
            U.need(result.get('container_id')==b['container_id'] and result.get('launch_sha256')==U.digest(launch_spec(c)), 'terminal identity differs')
            U.retained(docker,c['name'],b['container_id'],b['chips'],result['exit_code'])
            U.release(lease,docker); publish_handoff(c,meta,terminal,U.paths(lease,'release')[1]); event.set(); return result
        existing=docker.inspect(c['name'])
        if existing is not None:
            # Refuse an incompatible retained name before creating an allocation.
            chips=U.devices(existing)
            U.need(len(chips)==lease['device_count'] and all(x in lease['eligible_device_ids'] for x in chips), 'existing device selection differs')
            verify(c,docker,existing['Id'],chips,image_id)
        cl=U.claim(lease,docker)
        if not binding.exists():
            existing=docker.inspect(c['name'])
            ident=docker.create(c,cl['chips'],image_id) if existing is None else existing['Id']
            verify(c,docker,ident,cl['chips'],image_id)
            U.bind_container(lease,docker,c['name'],ident)
        b, ob=observe_binding(c,docker,cl,image_id); ident=b['container_id']; state=ob['State']
        if state['Status']=='created': observe_binding(c,docker,cl,image_id,start=True)
        attempt=uuid.uuid4().hex
        log=meta/('container-log-'+attempt+'.log')
        follower=docker.follow_logs(c['name'],log)
        R.write_atomic(meta/('log-'+attempt+'.json'),{'container_id':ident,'path':str(log),
                       'follower_pid':follower.pid,'initial_offset':0,'replay':'full history; overlaps other attempts'})
        done=threading.Event(); wait_result=[]
        def waiter():
            try: wait_result.append((True,docker.wait(c['name'])))
            except Exception as exc: wait_result.append((False,exc))
            finally: done.set()
        threading.Thread(target=waiter,daemon=True).start()
        while True:
            ob=verify(c,docker,ident,cl['chips'],image_id); state=ob['State']
            heartbeat(c,meta,ident,state)
            if done.is_set():
                ok,code=wait_result[0]
                if not ok: raise code
                ob=verify(c,docker,ident,cl['chips'],image_id); state=ob['State']
                U.need(type(code) is int and state.get('Status')=='exited' and state.get('Running') is False and code==state.get('ExitCode'), 'exit disagreement')
                U.retained(docker,c['name'],ident,cl['chips'],code)
                try: log_rc=follower.wait(timeout=5)
                except subprocess.TimeoutExpired: log_rc=None
                R.write_atomic(meta/('log-'+attempt+'.json'),{'container_id':ident,'path':str(log),
                               'follower_pid':follower.pid,'initial_offset':0,'observed_offset':log.stat().st_size,
                               'follower_exit_code':log_rc,'replay':'full history; overlaps other attempts'})
                result={'schema':'unified-container-terminal-v1','container_id':ident,'exit_code':code,'launch_sha256':U.digest(launch_spec(c)),'output_success':None,'metric_validity':None,'utc':R.utc()}
                R.write_atomic(terminal,result); U.release(lease,docker); publish_handoff(c,meta,terminal,U.paths(lease,'release')[1]); event.set(); return result
            U.need(state.get('Status') in ('running','exited'), 'container state uncertain')
            done.wait(c['poll_seconds'])
    except Exception as exc:
        R.write_atomic(meta/'host-failure.json',{'schema':'unified-container-host-failure-v1','utc':R.utc(),'error':str(exc),'lease_status':'uncertain'})
        event.set(); raise


def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['validate','start','supervise']); p.add_argument('--config',required=True); p.add_argument('--sha256',required=True); args=p.parse_args()
    raw=R.read_bytes(args.config); U.need(R.sha_bytes(raw)==args.sha256, 'host config pin differs'); c=json.loads(raw); validate(c)
    argv=[sys.executable,os.path.abspath(__file__),'supervise','--config',os.path.abspath(args.config),'--sha256',args.sha256]
    sources=[Path(__file__).resolve(),Path(U.__file__).resolve(),Path(R.__file__).resolve(),
             Path(__file__).resolve().parents[1]/'docker/engineering-base/schema.json']
    relaunch={'schema':'unified-host-relaunch-v1','argv':argv,'config':{'path':os.path.abspath(args.config),'sha256':args.sha256},
              'sources':[{'path':str(p),'sha256':R.sha_bytes(R.read_bytes(p))} for p in sources]}
    if args.command=='start':
        # Local detached supervisor owns the wait; no inherited SSH pipes or session.
        with ExitStack() as stack:
            meta=establish_owner(c,stack)
            path=meta/'RELAUNCH.json'
            if path.exists(): U.need(R.load(path)==relaunch,'relaunch pins differ')
            else: R.write_atomic(path,relaunch)
        with open(meta/'supervisor.log','ab',buffering=0) as log:
            proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
        print(json.dumps({'status':'supervisor-started','pid':proc.pid}))
    elif args.command=='validate': print(json.dumps({'status':'VALID'}))
    else: print(json.dumps(run(c,relaunch=relaunch)),flush=True)
if __name__=='__main__': main()
