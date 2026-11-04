"""Two narrow CPU actions: authenticate original panel release, bind DEV72 package.
No NPU start method, arbitrary command, allocation write or scientific acceptance.
"""
import argparse,fcntl,hashlib,importlib.util,json,os,re,socket,subprocess,time,threading
from pathlib import Path

ADAPTER_ID='family_cpu_bind_v1'
def need(v,s):
    if not v:raise ValueError(s)
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'unsafe path');return p
def sha(p):
    with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def ref(p):return dict(path=str(safe(p)),sha256=sha(p))
def pinned(r):
    need(type(r)is dict and set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'pin differs');return read(r['path'])
def module(r):
    need(sha(r['path'])==r['sha256'],'implementation changed');s=importlib.util.spec_from_file_location(Path(r['path']).stem,r['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def identity(pid):
    f=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(f[19]))
def same_process(record):
    try:return identity(record['pid'])=={k:record[k] for k in ('pid','boot_id','start_ticks')}
    except (FileNotFoundError,ProcessLookupError):return False

def capability_review(candidate_ref,c,r):
    """Consume the reviewer's real preparation receipt, never promote its scope."""
    need(r.get('schema')=='native-dev72-family-registration-independent-v1' and
         r.get('verdict')=='PASS_PREPARATION_AND_BINDING_CAPABILITY_ONLY',
         'independent family preparation review required')
    for key in ('activation_authorized','scientific_acceptance','numerical_acceptance',
                'physical_release_asserted','resource_claimed','npu_used','test_read'):
        need(r.get(key)is False,'family review scope differs')
    need(c['model'] in ('4B','9B'),'unregistered family model')
    ri=pinned(r['review_inputs'][c['model']])
    need(ri.get('schema')=='native-dev72-family-registration-review-input-v1' and
         ri.get('candidate')==candidate_ref and pinned(candidate_ref)==c,
         'review candidate differs')
    for key in ('launch_authorized','scientific_acceptance','physical_release_asserted','npu_launched','test_read'):
        need(ri.get(key)is False,'review input scope differs')
    need(ri.get('source_files')==c['source_files'] and len(c['source_files'])==4,
         'reviewed family implementations differ')
    for source in c['source_files']:
        need(sha(source['path'])==source['sha256'],'reviewed source changed')
    return ri

def describe(b):
    need(set(b)=={'schema','node_id','role','candidate','family_review','attempt','host_name','python','environment','output'},'CPU binding fields')
    need(b['schema']=='native-family-cpu-binding-v1' and b['role'] in ('physical_release','bind_reference') and b['host_name']=='k8s-node1' and b['python']=='/usr/bin/python3.12','CPU binding scope')
    need(type(b['attempt'])is int and b['attempt']==1,'original predecessor attempt1 only');safe(b['output']);c=pinned(b['candidate']);s=pinned(c['spec']);t=pinned(s['template']);projection=pinned(s['predecessor_projection']);Q=module(t['modules']['resource']);plan=pinned(projection['source']);view=Q.project(projection['source'],plan,projection)
    need(c['model'] in ('4B','9B') and projection['model_size']==c['model'],'candidate model differs');need(b['environment']==t['cpu_environment'] and b['environment'].get('PYTHONDONTWRITEBYTECODE')=='1' and b['environment'].get('TORCH_DEVICE_BACKEND_AUTOLOAD')=='0' and all(k in b['environment'] for k in ('PYTHONPATH','LD_LIBRARY_PATH')),'complete CPU environment differs')
    for k in ('PYTHONPATH','LD_LIBRARY_PATH'):
        for p in b['environment'][k].split(':'):safe(p)
    need(c['prepare']['sha256']==sha(c['prepare']['path']),'prepare implementation differs')
    for r in c['source_files']:need(sha(r['path'])==r['sha256'],'candidate source changed')
    return c,s,t,projection,view

def release_evidence(b,query):
    c,s,t,projection,v=describe(b);h=Path(v['out'])/'host_attempts'/str(b['attempt']);release=h/'RELEASE.json'
    if not release.exists():return None
    refs={k:ref(h/n) for k,n in [('claim','CLAIM.json'),('release','RELEASE.json'),('launch_spec','LAUNCH_SPEC.json'),('launch_receipt','LAUNCH_RECEIPT.json')]};docs={k:pinned(x) for k,x in refs.items()};cl=docs['claim'];rel=docs['release'];spec=docs['launch_spec'];rec=docs['launch_receipt'];a=b['attempt'];name=v['container']+'-a'+str(a)
    need(cl['schema']=='r3-resource-claim-v1' and rel['schema']=='r3-resource-release-v1' and cl['run']==rel['run']==v['run'] and type(cl['chip'])is int and type(rel['chip'])is int and cl['chip']==rel['chip']==v['chip'],'release ownership differs')
    need(cl['allocation']==v['allocation'] and rel['claim_sha256']==refs['claim']['sha256'] and rel['scientific_acceptance']is False and type(rel['exit_code'])is int,'release lineage differs')
    need(rec['plan_sha256']==spec['plan_sha256']==projection['source']['sha256'] and type(rec['attempt'])is int and rec['attempt']==a and rec['scientific_acceptance']is False and rel['container_id']==rec['container_id'] and rel['container']==name,'release generation differs')
    need(rec['command']==spec['command'][spec['command'].index(v['image_sha256'])+1:],'command differs')
    actual=query(name);need(actual and actual['Id']==rel['container_id'] and actual['Image']==v['image_sha256'] and actual['Config']['Cmd']==rec['command'],'retained container differs')
    need(actual['State']['Status']=='exited' and actual['State']['Running']is False and type(actual['State']['ExitCode'])is int and actual['State']['ExitCode']==rel['exit_code'],'physical exit absent')
    for key,field in [('container_started_at','StartedAt'),('container_finished_at','FinishedAt')]:need(type(rel.get(key))is str and bool(rel[key]) and actual['State'].get(field)==rel[key],'runtime generation differs')
    expected=sorted('/dev/'+x for x in ['davinci_manager','devmm_svm','hisi_hdc','davinci'+str(v['chip'])]);hc=actual['HostConfig'];need(sorted(x['PathOnHost'] for x in hc['Devices'])==expected and all(x['PathInContainer']==x['PathOnHost'] for x in hc['Devices']) and hc['Privileged']is False and hc['NetworkMode']=='none' and hc['AutoRemove']is False,'container isolation differs')
    free=[x for x in rel['allocation_after']['free'] if type(x.get('chip'))is int and x['chip']==v['chip']];need(len(free)==1 and free[0]['previous_run']==v['run'] and free[0]['release_evidence']==str(release) and not any(x['chip']==v['chip'] for x in rel['allocation_after']['allocation']),'physical release free generation differs')
    return dict(schema='native-family-authenticated-release-v1',predecessor=refs,source_plan=projection['source'],attempt=a,container_id=actual['Id'],container_started_at=rel['container_started_at'],container_finished_at=rel['container_finished_at'],exit_code=rel['exit_code'],test_quality_required=False,scientific_acceptance=False)

class FamilyCPUAdapter:
    def __init__(self,core,native,review=None,query=None,launch=None,service_identity=None):
        self.implementation_sha256=sha(__file__);self.D=core;self.N=native;self.review=review;self.query=query or native.inspect;self.launch=launch;self.service_identity=service_identity;self.bindings={};self.review_ref=None;self.service_config=None;self.service_module=None
    def authorize(self,b,r,n,gh):
        c,s,t,projection,v=describe(b);need(n['id']==b['node_id'] and n['adapter']==ADAPTER_ID and n['split']=='DEV' and n['protocol']=='original_dev72_family_bind_v1','CPU node identity')
        need((n['lane']=='cpu' and n['devices']==[] and n['managed_by']=='dag') if b['role']=='bind_reference' else (n['lane']=='npu' and n['devices']==[v['chip']] and n['managed_by']=='external_frozen'),'CPU/external roles')
        need(pinned(n['action']['binding'])==b,'exact node binding differs')
        need(n['action']['review']==b['family_review'] and pinned(b['family_review'])==r,'family review binding differs')
        capability_review(b['candidate'],c,r)
        self.bindings[n['id']]=(b,c,s,gh);return True
    def observe(self,n,intent):
        b,c,s,gh=self.bindings[n['id']]
        if b['role']=='physical_release':
            e=release_evidence(b,self.query)
            return dict(state='released',facts=['resource_release'],failed_facts=[],evidence=list(e['predecessor'].values())) if e else dict(state='running',facts=[],failed_facts=[],evidence=[])
        root=Path(b['output']);end=root/'EXIT.json'
        if end.exists():
            e=read(end);need(e['binding_sha256']==digest(b) and e['graph_sha256']==gh and type(e['exit_code'])is int and e['npu_started']is False,'CPU terminal generation differs')
            if e['exit_code']!=0:return dict(state='failed',facts=[],failed_facts=['success'],evidence=[ref(end)])
            ready=pinned(e['ready']);need(ready['status']=='ready_for_review' and ready['binding_sha256']==digest(b) and ready['activation_authorized']is False and ready['npu_started']is False,'ready artifact differs');bound=pinned(ready['bound']);plan=pinned(ready['plan']);need(bound['plan']==ready['plan'] and bound['spec']==c['spec'] and plan['out']==s['root']+'/output' and ready['graph_sha256']==gh and ready['model']==c['model'],'produced package identity differs');return dict(state='released',facts=['success','artifact'],failed_facts=[],evidence=[ref(end),e['ready'],ready['bound'],ready['plan']])
        if root.exists() or intent:
            service=root/'SERVICE.json'
            state='running' if service.exists() and same_process(read(service)) else 'uncertain'
            return dict(state=state,facts=[],failed_facts=[],evidence=[ref(service)] if service.exists() else [])
        return {'state':'absent'}
    def reserve_and_start(self,b,n,token):
        saved=self.bindings[n['id']];need(b==saved[0] and b['role']=='bind_reference' and n['managed_by']=='dag','only CPU bind may execute')
        r=self.review;need(r and r.get('verdict')=='PASS' and r.get('cpu_activation_authorized')is True and r.get('npu_activation_authorized')is False and r.get('scientific_acceptance')is False and r.get('graph_sha256')==saved[3] and r.get('bindings',{}).get(n['id'])==n['action'],'exact CPU queue review required')
        need(socket.gethostname()==b['host_name'],'owning host required');need(release_evidence(b,self.query) is not None,'physical release not ready');need(not Path(saved[2]['root']).exists(),'execution package already exists; reconcile')
        root=safe(b['output']);root.mkdir(parents=True,exist_ok=False);env=dict(os.environ);env.update(b['environment']);envelope=dict(schema='native-family-cpu-intent-v1',binding=b,node=n,graph_sha256=saved[3],token=token,review=r,core=ref(self.D.__file__),native=ref(self.N.__file__),service_identity=self.service_identity,review_ref=self.review_ref,service_config=self.service_config,service_module=self.service_module)
        self.D.atomic(root/'INTENT.json',envelope);cmd=[b['python'],'-B','-P',str(Path(__file__).resolve()),'--envelope',str(root/'INTENT.json')]
        if self.launch:return self.launch(cmd,env,token)
        with (root/'worker.log').open('ab') as log:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        self.D.atomic(root/'SERVICE.json',dict(identity(p.pid),command=cmd,token=token,binding_sha256=digest(b)));return dict(pid=p.pid,token=token,intent=str(root/'INTENT.json'),npu_started=False)

def worker(path):
    root=safe(path).parent
    with (root/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not (root/'EXIT.json').exists(),'worker already terminal; no replay')
        return execute_worker(path)
def execute_worker(path):
    x=read(path);need(x['schema']=='native-family-cpu-intent-v1','intent schema');b=x['binding'];root=Path(path).parent;need(root==Path(b['output']),'worker output differs');D=module(x['core']);rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(30):D.atomic(root/'heartbeat.json',dict(stage='binding',utc_seconds=time.time(),token=x['token']))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        D.atomic(root/'heartbeat.json',dict(stage='validating',utc_seconds=time.time(),token=x['token']))
        N=module(x['native']);need(x.get('review_ref') is not None and pinned(x['review_ref'])==x['review'],'worker review pin');S=module(x['service_module']);sc,sg,sd,sa,sn,_=S.verify(x['service_config']['path'],x['service_config']['sha256']);S.approval(sc,sg,sd,x['review_ref'],x['service_config']);need(sd.digest(sg)==x['graph_sha256'],'worker graph differs');need(x['core']==sc['modules']['dag'] and x['native']==sc['modules']['native'] and x['service_module']==sc['modules']['service'],'worker composition differs');need(x['node']==next(n for n in sg['nodes'] if n['id']==b['node_id']),'worker node differs');need(x['token']==digest({'graph':x['graph_sha256'],'node':b['node_id'],'action':x['node']['action']}),'worker token differs');a=FamilyCPUAdapter(D,N,x['review']);a.authorize(b,pinned(b['family_review']),x['node'],x['graph_sha256']);need(socket.gethostname()==b['host_name'],'worker host')
        c,s,tpl,p,v=describe(b);e=release_evidence(b,N.inspect);need(e is not None,'release disappeared');D.atomic(root/'RELEASE-EVIDENCE.json',e);binding=dict(schema='native-dev72-family-actual-release-binding-v1',predecessor=e['predecessor'],attempt=e['attempt']);D.atomic(root/'ACTUAL-BINDING.json',binding)
        K=module(c['prepare']);result=K.bind(c['spec'],ref(root/'ACTUAL-BINDING.json'));plan=pinned(result['plan']);ready=dict(schema='native-family-ready-for-review-v1',status='ready_for_review',binding_sha256=digest(b),graph_sha256=x['graph_sha256'],model=c['model'],plan=result['plan'],bound=ref(Path(s['root'])/'BOUND.json'),commands=ref(Path(s['root'])/'COMMANDS.json'),release=ref(root/'RELEASE-EVIDENCE.json'),activation_authorized=False,npu_started=False,scientific_acceptance=False,test_read=False);D.atomic(root/'READY-FOR-REVIEW.json',ready);rc=0
    except BaseException as exc:D.atomic(root/'ERROR.json',dict(error_type=type(exc).__name__,message=str(exc)[:400],needs_reconciliation=True,npu_started=False));raise
    finally:
        stop.set();t.join(2)
        end=dict(exit_code=rc,binding_sha256=digest(b),graph_sha256=x['graph_sha256'],token=x['token'],utc_seconds=time.time(),npu_started=False,scientific_acceptance=False)
        if rc==0:end['ready']=ref(root/'READY-FOR-REVIEW.json')
        D.atomic(root/'EXIT.json',end)
        si=x.get('service_identity')
        if si and same_process(si):
            import signal
            try:os.kill(si['pid'],signal.SIGUSR1)
            except ProcessLookupError:pass
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--envelope',required=True);a=p.parse_args();worker(a.envelope)
