#!/usr/bin/env python3
"""First-update fixture: stage on CPU, then admit a reviewed exact four-card attempt."""
import argparse, hashlib, importlib.util, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path

PURPOSE = 'engineering first-update fixture'
FILES = ['config.json','command.py','relaunch.sh','container_entry.sh','entry.py','hooks.py','raw_loading.py','TENSOR-DIFF.json']
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p, value):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_name('.'+p.name+'.tmp-'+str(os.getpid()))
    with open(tmp,'x') as f:
        json.dump(value,f,sort_keys=True,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY); os.fsync(fd); os.close(fd)
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def validate(c):
    if c.get('dispatchable') is not True or c.get('source_integration_review') != 'accepted' or not c.get('review_receipt') or not c.get('mapping_evidence'): raise ValueError('source integration and mapping review with receipt required')
    if c.get('phase') != 'phase1': raise ValueError('only phase1 supported; later work requires a separate reviewed attempt')
    chips=c['chips']
    if len(chips)!=4 or chips!=sorted(set(chips)) or any(type(x)!=int or x not in range(8) for x in chips): raise ValueError('four sorted distinct physical IDs required')
    mapping=c['device_mapping']
    if len(mapping)!=4 or [x['physical'] for x in mapping]!=chips or len(set(x['container'] for x in mapping))!=4 or any(type(x['container'])!=int or x['container'] not in range(8) for x in mapping): raise ValueError('invalid reviewed device mapping')
    if not re.fullmatch(r'[0-9]+(,[0-9]+){3}',c['visible_devices']): raise ValueError('explicit reviewed visible devices required')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*',c['name']): raise ValueError('invalid name')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',c['image']): raise ValueError('image must be digest')
    for k in ('candidate','out','allocation','probe','group_source','bridge_source'):
        if not Path(c[k]).is_absolute(): raise ValueError(k+' must be absolute')
    if set(c['candidate_pins'])!=set(FILES): raise ValueError('pin all runtime candidate files')
    for p,h in c['source_pins'].items():
        if not Path(p).is_absolute() or sha(p)!=h: raise ValueError('source pin differs: '+p)
    required={str(Path(c['probe'])),str(Path(c['group_source'])/'group_adapter.py'),str(Path(c['group_source'])/'r3_resource_adapter.py'),str(Path(c['bridge_source']))}
    if not required.issubset(c['source_pins']): raise ValueError('probe, adapter and bridge must be source pinned')
    for f,h in c['candidate_pins'].items():
        if sha(Path(c['candidate'])/f)!=h: raise ValueError('candidate pin differs: '+f)

def prepare(config, self_path):
    c=read(config); validate(c); out=Path(c['out']); out.mkdir(parents=True,exist_ok=True)
    attempt=out/'attempts'/c['name']; attempt.mkdir(parents=True,exist_ok=False)
    work=attempt/'work'; work.mkdir()
    for f in FILES: shutil.copyfile(Path(c['candidate'])/f,work/f)
    ad=attempt/'adapter'; ad.mkdir()
    for f in ('group_adapter.py','r3_resource_adapter.py'): shutil.copyfile(Path(c['group_source'])/f,ad/f)
    shutil.copyfile(c['bridge_source'],attempt/'marker_bridge.py')
    shutil.copyfile(self_path,attempt/'fixture.py')
    # Snapshot original inputs and check copied bytes before the waiter can run.
    put(attempt/'CONFIG.json',c)
    staged={str(p.relative_to(attempt)):sha(p) for p in list(work.iterdir())+list(ad.iterdir())+[attempt/'fixture.py',attempt/'marker_bridge.py',attempt/'CONFIG.json']}
    for f,h in c['candidate_pins'].items():
        if staged['work/'+f]!=h: raise RuntimeError('staging candidate changed')
    for f in ('group_adapter.py','r3_resource_adapter.py'):
        if staged['adapter/'+f]!=c['source_pins'][str(Path(c['group_source'])/f)]: raise RuntimeError('staging adapter changed')
    if staged['marker_bridge.py']!=c['source_pins'][c['bridge_source']]: raise RuntimeError('staging bridge changed')
    put(attempt/'STAGED.json',staged)
    cmd=[sys.executable,'-P',str(attempt/'fixture.py'),'run','--attempt',str(attempt)]
    (attempt/'RELAUNCH.txt').write_text(shlex.join(cmd)+'\n')
    put(attempt/'PREPARED.json',{'status':'cpu_ready','provenance':'pending independent review until accepted receipt is verified by main','time':time.time(),'run_argv':cmd})
    return attempt

def loaded(attempt):
    a=Path(attempt).resolve(); pins=read(a/'STAGED.json')
    for p,h in pins.items():
        if sha(a/p)!=h: raise RuntimeError('staged source changed: '+p)
    c=read(a/'CONFIG.json'); validate(c)
    return a,c,module(a/'adapter/group_adapter.py','fixture_group')

def host(c):
    p=subprocess.run([c['probe'],'--chips',','.join(map(str,c['chips']))],capture_output=True,text=True,check=True,timeout=60)
    x=json.loads(p.stdout)
    if x.get('chips')!=c['chips'] or x.get('certain') is not True or x.get('unmanaged_owners')!=[]: raise RuntimeError('host busy or uncertain')
    return x

def docker_command(a,c):
    out=c['out']; work=str(a/'work')
    cmd=['docker','run','-d','--pull=never','--restart','no','--name',c['name'],'--network','host','--shm-size','64g','--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864','-v','/mnt/cephfs:/mnt/cephfs','-v','/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro']
    for dev in ('davinci_manager','devmm_svm','hisi_hdc'): cmd+=['--device','/dev/'+dev]
    for m in c['device_mapping']: cmd+=['--device',f"/dev/davinci{m['physical']}:/dev/davinci{m['container']}"]
    for p in ('/usr/local/sbin','/etc/ascend_install.info'):
        if Path(p).exists(): cmd+=['-v',p+':'+p+':ro']
    for k,v in {'ASCEND_RT_VISIBLE_DEVICES':c['visible_devices'],'FIXTURE_OUT':out,'FIXTURE_WORK':work,'FIXTURE_PHASE':'phase1','PYTHONPATH':'/mnt/cephfs/xingchao/docker/verl_v030_20261029/site:/mnt/cephfs/xingchao/docker/verl_v030_20261029/src/verl','PYTHONSAFEPATH':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_OFFLINE':'1'}.items(): cmd+=['-e',k+'='+v]
    return cmd+[c['image'],'bash',work+'/container_entry.sh']

def run(attempt, poll=10):
    a,c,g=loaded(attempt); chips=c['chips']; name=c['name']
    staged_hash=sha(a/'STAGED.json')
    def check_bindings():
        if sha(a/'STAGED.json') != staged_hash: raise RuntimeError('staged manifest changed')
        checked_a,checked_c,_=loaded(a)
        if checked_a != a or checked_c != c: raise RuntimeError('attempt configuration changed')
    if any((a/x).exists() for x in ('CLAIM.json','CLAIM.json.intent','LAUNCH-INTENT.json','CONTAINER.json','RELEASE.json')): raise RuntimeError('prior admission or launch evidence: reconcile; never retry')
    if Path(c['out'],'exit-phase1.marker').exists(): raise RuntimeError('phase marker already exists')
    cmd=docker_command(a,c); put(a/'COMMAND.json',{'docker_argv':cmd,'chips':chips,'mapping':c['device_mapping'],'visible_devices':c['visible_devices']})
    if g.r3.docker_inspect(name) is not None: raise RuntimeError('container name already exists')
    while True:
        try:
            observation=host(c)
            doc=read(c['allocation']); g.r3.validate_doc(doc)
            if any(sum(e['chip']==x for e in doc['free'])!=1 for x in chips): raise RuntimeError('ledger busy')
            if any(g.r3.live_chip_conflict(x,None) for x in chips): raise RuntimeError('docker busy')
            break
        except Exception as e:
            put(a/'HEARTBEAT.json',{'status':'waiting_unclaimed','time':time.time(),'reason':str(e)})
            time.sleep(poll)
    put(a/'HOST-PRECLAIM.json',observation)
    # Ledger lock and physical conflict checks live in the existing atomic transaction.
    g.transact('claim',c['allocation'],chips,name,a/'CLAIM.json',claim_guard=lambda doc: check_bindings(),purpose=PURPOSE)
    put(a/'HOST-POSTCLAIM.json',host(c))
    if any(g.r3.live_chip_conflict(x,None) for x in chips): raise RuntimeError('post-claim conflict; retain claim')
    check_bindings()
    put(a/'LAUNCH-INTENT.json',{'docker_argv':cmd,'time':time.time()})
    result=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=120)
    cid=result.stdout.strip()
    if not re.fullmatch('[a-f0-9]{64}',cid): raise RuntimeError('uncertain docker ID; retain claim')
    put(a/'CONTAINER.json',{'id':cid,'name':name,'time':time.time()})
    return observe(a)

def observe(attempt):
    a,c,g=loaded(attempt); rec=read(a/'CONTAINER.json'); name=c['name']; cid=rec['id']
    if rec['name']!=name: raise RuntimeError('container receipt differs')
    while True:
        try:
            p=subprocess.run(['docker','wait',cid],capture_output=True,text=True,check=True,timeout=60)
            wait_code=int(p.stdout.strip()); break
        except subprocess.TimeoutExpired: put(a/'HEARTBEAT.json',{'status':'running','time':time.time(),'container_id':cid})
    obj=g.r3.docker_inspect(name)
    if obj is None or obj['Id']!=cid or obj['Name'].lstrip('/')!=name or obj['State'].get('Status') not in ('exited','dead') or obj['HostConfig'].get('AutoRemove') is not False: raise RuntimeError('terminal container identity uncertain')
    code=obj['State'].get('ExitCode')
    if type(code)!=int or code!=wait_code: raise RuntimeError('docker exit disagreement')
    bridge=module(a/'marker_bridge.py','fixture_bridge'); exitfile=a/'EXIT.json'
    if exitfile.exists():
        if read(exitfile).get('exit_code')!=code: raise RuntimeError('existing exit evidence differs')
        # Recheck the original marker even on observer restart.
        marker=Path(c['out'])/'exit-phase1.marker'; raw=marker.read_text(encoding='ascii').strip()
        if not raw.isascii() or not raw.isdecimal() or int(raw)!=code or int(raw)>255: raise RuntimeError('phase marker differs')
    else: bridge.bridge(Path(c['out'])/'exit-phase1.marker',exitfile,code)
    put(a/'TERMINAL.json',{'container_id':cid,'exit_code':code,'status':'success' if code==0 else 'failed','time':time.time()})
    put(a/'HOST-RELEASE.json',host(c))
    g.transact('release',c['allocation'],c['chips'],name,a/'RELEASE.json',claim_path=a/'CLAIM.json',container=name,container_id=cid)
    put(a/'HEARTBEAT.json',{'status':'released','exit_code':code,'time':time.time()})
    return code

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='op',required=True)
    q=sub.add_parser('prepare'); q.add_argument('--config',required=True)
    for op in ('run','observe'):
        q=sub.add_parser(op); q.add_argument('--attempt',required=True)
    args=p.parse_args()
    if args.op=='prepare': print(prepare(args.config,Path(__file__).resolve())); return 0
    try: return run(args.attempt) if args.op=='run' else observe(args.attempt)
    except Exception as e:
        put(Path(args.attempt)/'ESCALATION.json',{'status':'reconcile_claim_and_container','error':repr(e),'time':time.time()}); raise
if __name__=='__main__': sys.exit(main())
