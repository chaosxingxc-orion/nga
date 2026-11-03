"""Registered native guarded-host DAG adapter; local host only, no shell actions.

Trusted composition pins this implementation and all allowed host implementations.
Readiness checks receipt/identity; the frozen host revalidates complete executable
and model closure and performs the locked live resource transaction before effect.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

KINDS = {'native_long_dev_v1': 'native-config-execution-v1', 'native_panel_v2': 'native-panel-execution-v2'}
ENV_KEYS = {'PYTHONDONTWRITEBYTECODE', 'PYTHONPATH', 'LD_LIBRARY_PATH', 'TORCH_DEVICE_BACKEND_AUTOLOAD'}

def need(v, why):
    if not v: raise ValueError(why)

def exact(d, fields, why):
    need(type(d) is dict and set(d) == set(fields), why)

def safe_path(p):
    need(type(p) is str and Path(p).is_absolute() and '..' not in Path(p).parts, 'absolute path required')
    q=Path(p);need(not any(x.is_symlink() for x in [q,*q.parents]), 'symlink path');return q

def sha(p):
    with safe_path(str(p)).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(p):return json.loads(safe_path(str(p)).read_bytes())

def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}

def pinned(x):
    exact(x,('path','sha256'),'pin fields');need(type(x['sha256']) is str and re.fullmatch('[0-9a-f]{64}',x['sha256']),'pin digest')
    need(sha(x['path'])==x['sha256'],'changed pin: '+x['path']);return read(x['path'])

def atomic(p,d):
    p=safe_path(str(p));tmp=p.with_name(p.name+'.pending');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(d,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p);fd=os.open(p.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def module(x):
    need(sha(x['path'])==x['sha256'],'host changed')
    spec=importlib.util.spec_from_file_location('pinned_native_host',x['path']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def inspect(name):
    need(type(name) is str and re.fullmatch('[a-zA-Z0-9_.-]+',name),'container name')
    r=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower():return None
        raise RuntimeError('container observation unavailable')
    a=json.loads(r.stdout);need(type(a) is list and len(a)==1,'ambiguous container');return a[0]

def environment(e):
    need(type(e) is dict and set(e)<=ENV_KEYS and e.get('PYTHONDONTWRITEBYTECODE')=='1','host environment')
    need(all(type(v) is str and '\0' not in v and '\n' not in v for v in e.values()),'environment value')
    for k in ('PYTHONPATH','LD_LIBRARY_PATH'):
        if k in e:
            for p in e[k].split(':'):safe_path(p)
    if 'TORCH_DEVICE_BACKEND_AUTOLOAD' in e:need(e['TORCH_DEVICE_BACKEND_AUTOLOAD']=='0','autoload setting')
    return e

def describe(binding, capabilities):
    exact(binding,('schema','node_id','kind','plan','review','attempt','model_sha256','inputs_sha256','protocol','host_python','host_environment'),'binding fields')
    need(binding['schema']=='nga-native-dag-binding-v1' and binding['kind'] in KINDS,'binding kind')
    need(type(binding['attempt']) is int and binding['attempt']>0,'attempt')
    need(type(binding['node_id']) is str and re.fullmatch('[a-z0-9_]+',binding['node_id']),'node id')
    d=pinned(binding['plan']);need(d['schema']==KINDS[binding['kind']],'plan schema')
    need(d['scientific_acceptance'] is False and type(d['chip']) is int and 0<=d['chip']<8,'scope/device')
    host=d['modules']['host'];need(host['sha256'] in capabilities[binding['kind']],'unregistered host implementation')
    need(d['files'].get(host['path'])==host['sha256'],'host outside closure');H=module(host)
    c=pinned(d['config'])
    if binding['kind']=='native_long_dev_v1':
        registry=pinned(d['registry']);m=registry['model'][c['model']]
        identity=(m['model_manifest_sha256'],c['inputs']['ordered_sha256'],c['protocol']);scope='synthetic_long_dev';split='DEV'
        need(d['test_read'] is False,'long DEV scope')
    else:
        identity=(d['model_sha256'],d['population']['ordered_inputs_sha256'],d['protocol']['id']);scope='public_fixed_base_test';split='TEST'
        need(d['scope']==scope and d['test_read'] is True and d['candidate_test_authority'] is False and d['candidate_selection_allowed'] is False,'panel scope')
        need(binding['host_python']==d['host_python'] and binding['host_environment']==d['host_environment'],'panel host environment changed')
    need(identity==(binding['model_sha256'],binding['inputs_sha256'],binding['protocol']),'model/input/protocol mismatch')
    safe_path(binding['host_python']);environment(binding['host_environment']);safe_path(d['out']);safe_path(d['allocation'])
    view={**d,'runtime':d['modules']['runtime'],'resource':d['modules']['resource'],'image_sha256':d['image'],'scope':scope}
    cmd=H.command(view,binding['plan']['path'],binding['plan']['sha256'],binding['attempt'])
    argv=[binding['host_python'],'-B','-P',host['path'],'start','--plan',binding['plan']['path'],'--sha256',binding['plan']['sha256'],'--review',binding['review']['path'],'--review-sha256',binding['review']['sha256'],'--attempt',str(binding['attempt'])]
    return d,cmd,argv,split

class NativeAdapter:
    def __init__(self, capabilities, service_root, query=inspect, launch=None, grant=None):
        self.implementation_sha256=sha(__file__);self.capabilities=capabilities;self.service_root=safe_path(str(service_root));self.query=query;self.launch=launch;self.grant=grant
        self.bindings={}
    def authorize(self,binding,review,node,graph_hash):
        d,cmd,argv,split=describe(binding,self.capabilities)
        need(node['id']==binding['node_id'] and node['lane']=='npu' and node['devices']==[d['chip']] and node['protocol']==binding['protocol'] and node['split']==split,'node identity')
        need(pinned(node['action']['binding'])==binding,'action binding differs')
        need(node['action']['review']==binding['review'] and pinned(binding['review'])==review,'review binding')
        need(review.get('verdict')=='PASS' and review.get('activation_authorized') is True and review.get('scientific_acceptance') is False and review.get('approved_plan_sha256')==binding['plan']['sha256'],'exact review required')
        need(type(review.get('attempts')) is list and all(type(a) is int for a in review['attempts']) and binding['attempt'] in review['attempts'],'review attempts')
        need(review.get('test_read') is d['test_read'] and review.get('candidate_test_authority',False) is False,'review scope')
        need(review.get('expected_commands',{}).get(str(binding['attempt']))==cmd,'reviewed command differs')
        for name,h in d['files'].items():need(review.get('hashes',{}).get(name)==h,'unreviewed executable/data closure')
        for x in d['modules'].values():
            need(sha(x['path'])==x['sha256'],'module changed')
        # Full source/model verification remains inside frozen host at dispatch.
        # Here we prove the accepted manifest is unchanged without re-reading tens
        # of GiB every monitoring tick. This receipt cannot bypass the host verify.
        self.bindings[node['id']]=(binding,d,cmd,argv,graph_hash)
        return True
    def observe(self,node,intent):
        binding,d,cmd,argv,gh=self.bindings[node['id']];a=binding['attempt'];root=Path(d['out']);h=root/'host_attempts'/str(a);name=d['container']+'-a'+str(a)
        actual=self.query(name);files=[]
        def obs(state,facts=(),failed=()):return {'state':state,'facts':list(facts),'failed_facts':list(failed),'evidence':files.copy()}
        if actual is None:
            return obs('uncertain') if h.exists() or intent else {'state':'absent'}
        if not all((h/f).exists() for f in ('LAUNCH_RECEIPT.json','LAUNCH_SPEC.json','CLAIM.json')):return obs('uncertain')
        receipt=read(h/'LAUNCH_RECEIPT.json');spec=read(h/'LAUNCH_SPEC.json');claim=read(h/'CLAIM.json')
        files.extend(ref(h/f) for f in ('LAUNCH_RECEIPT.json','LAUNCH_SPEC.json','CLAIM.json'))
        need(spec['command']==cmd,'launch specification differs')
        need(claim['schema']=='r3-resource-claim-v1' and claim['run']==d['run'] and type(claim['chip']) is int and claim['chip']==d['chip'] and claim['allocation']==d['allocation'] and claim.get('scientific_acceptance',False) is False and claim.get('execution_authorized',False) is False,'launch claim differs')
        need(actual['Id']==receipt['container_id'] and actual['Image']==d['image'] and actual['HostConfig'].get('AutoRemove') is False,'retained runtime differs')
        need(actual['Config']['Cmd']==cmd[cmd.index(d['image'])+1:]==receipt['command'],'runtime command differs')
        devices=actual['HostConfig'].get('Devices',[])
        expected=['/dev/'+x for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci'+str(d['chip']))]
        need(sorted(x['PathOnHost'] for x in devices)==sorted(expected) and all(x['PathInContainer']==x['PathOnHost'] for x in devices),'runtime device binding differs')
        need(actual['HostConfig'].get('Privileged') is False and actual['HostConfig'].get('NetworkMode')=='none','runtime isolation differs')
        need(receipt['plan_sha256']==binding['plan']['sha256'] and type(receipt['attempt']) is int and receipt['attempt']==a and receipt['scientific_acceptance'] is False,'receipt identity')
        if actual['State']['Status'] in ('running','created'):return obs('running')
        need(actual['State']['Status']=='exited' and actual['State']['Running'] is False and type(actual['State']['ExitCode']) is int,'runtime terminal uncertain')
        # Physical release and result success are independent facts. The frozen
        # host can release a crashed container before recording runtime validity.
        if not (h/'RELEASE.json').exists():return obs('uncertain')
        release=read(h/'RELEASE.json');files.append(ref(h/'RELEASE.json'));rc=actual['State']['ExitCode']
        need(release['schema']=='r3-resource-release-v1','release schema')
        need(release['run']==d['run'] and type(release['chip']) is int and release['chip']==d['chip'] and release.get('scientific_acceptance',False) is False,'resource identity')
        need(release['claim_sha256']==sha(h/'CLAIM.json') and release['container_id']==actual['Id'] and release['container']==name,'release generation')
        need(type(release['exit_code']) is int and release['exit_code']==rc,'release exit')
        required=[h/'EXIT.json',root/'attempts'/str(a)/'EXIT.json']
        if not all(p.exists() for p in required):
            return obs('failed',('resource_release',),('success',)) if rc else obs('released',('resource_release',))
        try:
            host,runtime=map(read,required);files.extend(ref(p) for p in required)
        except (OSError,ValueError,TypeError):return obs('failed',('resource_release',),('success',))
        if type(host) is not dict or type(runtime) is not dict:return obs('failed',('resource_release',),('success',))
        valid=True
        for x in (host,runtime):
            valid=valid and x.get('plan_sha256')==binding['plan']['sha256'] and type(x.get('attempt')) is int and x['attempt']==a and type(x.get('exit_code')) is int and x['exit_code']==rc and x.get('scientific_acceptance') is False
        valid=valid and host.get('container_id')==actual['Id'] and type(host.get('container_exit_code')) is int and host['container_exit_code']==rc and host.get('runner_terminal_matches') is True
        valid=valid and runtime.get('test_read',False) is d['test_read'] and runtime.get('execution_authorized',False) is False
        return obs('released',('resource_release','success')) if valid and rc==0 else obs('failed',('resource_release',),('success',))
    def reserve_and_start(self,binding,node,token):
        saved=self.bindings[node['id']];d=saved[1];argv=saved[3];gh=saved[4]
        need(node['managed_by']=='dag','external owner cannot start')
        need(binding==saved[0] and pinned(node['action']['binding'])==binding,'start binding differs')
        need(self.grant and self.grant.get('schema')=='nga-native-dag-activation-v1' and self.grant.get('verdict')=='PASS' and self.grant.get('activation_authorized') is True and self.grant.get('scientific_acceptance') is False and self.grant['graph_sha256']==gh and self.grant['bindings'].get(node['id'])==node['action'] and self.grant['capabilities']==self.capabilities,'controller activation does not cover action')
        need(socket.gethostname()==d['host_name'],'controller must run on owning host')
        need(not (Path(d['out'])/'host_attempts'/str(binding['attempt'])).exists(),'attempt already externally reserved')
        # The existing host owns both allocation lock and live conflict checks.
        # No resource ledger is ever written by this adapter.
        if self.launch:return self.launch(argv,binding['host_environment'],token)
        out=self.service_root/'launches'/node['id'];out.mkdir(parents=True,exist_ok=False)
        atomic(out/'INTENT.json',{'schema':'nga-native-launch-intent-v1','token':token,'binding':binding,'node':node,'graph_sha256':gh,'capabilities':self.capabilities,'grant':self.grant})
        env=dict(os.environ);env.update(environment(binding['host_environment']))
        with (out/'launch.log').open('ab') as log:
            wrapper=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--envelope',str(out/'INTENT.json')]
            p=subprocess.Popen(wrapper,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        return {'envelope_pid':p.pid,'token':token,'container_proof':False,'intent':str(out/'INTENT.json')}

def envelope(path):
    # Reconstruct a registered native host command from exact binding. No argv
    # or shell command is accepted from the intent or graph configuration.
    p=safe_path(path);x=read(p)
    exact(x,('schema','token','binding','node','graph_sha256','capabilities','grant'),'envelope fields')
    need(x['schema']=='nga-native-launch-intent-v1' and p.name=='INTENT.json','envelope schema')
    grant=x['grant'];need(grant.get('schema')=='nga-native-dag-activation-v1' and grant.get('verdict')=='PASS' and grant.get('activation_authorized') is True and grant.get('scientific_acceptance') is False,'envelope activation')
    need(grant['graph_sha256']==x['graph_sha256'] and grant['bindings'].get(x['node']['id'])==x['node']['action'] and grant['capabilities']==x['capabilities'],'envelope binding')
    adapter=NativeAdapter(x['capabilities'],p.parent,grant=grant)
    adapter.authorize(x['binding'],pinned(x['binding']['review']),x['node'],x['graph_sha256'])
    d,cmd,argv,split=describe(x['binding'],x['capabilities']);need(socket.gethostname()==d['host_name'],'envelope host')
    need(not (Path(d['out'])/'host_attempts'/str(x['binding']['attempt'])).exists(),'attempt externally reserved')
    rc=1
    try:
        env=dict(os.environ);env.update(environment(x['binding']['host_environment']))
        r=subprocess.run(argv,stdin=subprocess.DEVNULL,check=False,env=env);rc=r.returncode
    finally:atomic(p.parent/'EXIT.json',{'exit_code':rc,'token':x['token'],'plan_sha256':x['binding']['plan']['sha256'],'utc_seconds':time.time(),'scientific_acceptance':False})
    return rc

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--envelope',required=True);args=a.parse_args();raise SystemExit(envelope(args.envelope))
