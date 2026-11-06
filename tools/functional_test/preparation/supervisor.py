#!/usr/bin/env python3
"""Reviewed RC1 host lifecycle. No resources are acquired by build/validate."""
import argparse, fcntl, hashlib, json, os, re, shlex, subprocess, sys, time
from pathlib import Path

REPO=Path('/mnt/cephfs/xingchao/experiments/jev/rc1-host-stage-20261106-2600925')
sys.path.insert(0,str(REPO/'tools'))
import r3_final_container as K
import r3_resource_adapter as R
import unified_resource_provider_v1 as P

ROOT=Path('/mnt/cephfs/xingchao/experiments/jev')
CLOSURE=ROOT/'r3_runs/combined_eval_closure_20261031_v1/r3_code'
R0=ROOT/'r0_code'

def need(x,s):
    if not x: raise RuntimeError(s)
def read(p): return json.loads(Path(p).read_text())
def sha(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def pin(x):
    need(set(x)=={'path','sha256'} and Path(x['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',x['sha256']) and sha(x['path'])==x['sha256'],'pin mismatch')
def save(p,x): R.write_atomic(p,x)
def log(p,msg):
    with open(p,'a',buffering=1) as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' '+msg+'\n'); f.flush(); os.fsync(f.fileno())
def run(a,**kw): return subprocess.run(a,check=True,text=True,timeout=30,**kw)
EXPORT_MEMBER='q0p8b-s2'
EXPORT_SCOPE='existing-host-cpu-verify-raw-frozen-train-calibration-test-population-export'

def cpu_entry(c):
    h=c['host']; entry=h.get('cpu_entry'); export=c.get('population_export')
    need((entry is None)==(export is None),'CPU export configuration incomplete')
    if entry is None: return h['entry']
    need(type(export)==dict and set(export)=={'producer','exporter','member','directory','scope'},'export configuration')
    need(c['member']==EXPORT_MEMBER and export['member']==EXPORT_MEMBER and export['scope']==EXPORT_SCOPE,'export scope/member differs')
    need(type(entry)==str and Path(entry).is_absolute() and str(Path(entry).resolve())==entry,'CPU entry path')
    need(export['exporter']['path']==entry and h['implementation_files'].get(entry)==export['exporter']['sha256'],'CPU entry implementation binding')
    pin(export['exporter']); pin(export['producer'])
    need(export['producer']['path']==h['entry'] and c['source_files'].get(h['entry'])==export['producer']['sha256'],'producer binding')
    directory=Path(export['directory']); campaign=Path(c['round_dir']).parent
    need(directory.is_absolute() and str(directory.resolve())==str(directory) and directory==campaign/'population-export','export directory')
    return entry

def validate(c,config):
    need(c['schema']=='rc1-trackk-v1','core config schema')
    h=c['host']; spec=c['container']['spec']; chip=c['container']['chip']
    entry=Path(h['entry']); need(entry.is_absolute() and str(entry.resolve())==str(entry) and str(entry) in c['source_files'],'entry source binding')
    need(type(chip)==int and 0<=chip<8,'chip')
    need(h['dependency_policy']=='wait-for-verified-free-resource','dependency policy')
    for ref in (c['review'],h['runtime_evidence'],h['matched_protocol'],c['protocol'],c['manifest']): pin(ref)
    need(h['matched_protocol']['path']==str(REPO/'experiments/RC1-MATCHED-K0.md'),'matched protocol path')
    core_review=read(c['review']['path'])
    need(core_review.get('reviewed') is True and core_review.get('schema')=='rc1-trackk-review-v1' and core_review.get('config_sha256')==digest({k:v for k,v in c.items() if k!='review'}),'core review')
    runtime=read(h['runtime_evidence']['path'])
    need(runtime.get('image')==c['image'] and all(spec['environment'].get(k)==v for k,v in runtime['environment'].items()),'runtime environment receipt differs')
    need(re.fullmatch('sha256:[0-9a-f]{64}',c['image']) and spec['image']==c['image'],'image')
    need(spec['cmd']==['-B','-P',str(entry),'infer','--config',str(Path(config).resolve())],'core command')
    need(spec['devices']==['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(chip)],'device mapping')
    need(all(spec['environment'].get(k)==v for k,v in K.ENV.items()),'required environment')
    pythonpath=spec['environment'].get('PYTHONPATH','')
    need('/usr/local/Ascend/cann-9.2.0/python/site-packages' in pythonpath.split(':') and '/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe' in pythonpath.split(':'),'CANN Python environment')
    mounts=spec['mounts']; need(type(mounts)==dict and all(type(v)==bool and K.path(p)==p for p,v in mounts.items()),'mount paths')
    required=[str(entry),str(CLOSURE),str(R0),str(REPO/'tools/r3_reference_metrics.py'),str(REPO/'tools/r3_final_container.py'),str(Path(config).resolve()),c['protocol']['path'],c['manifest']['path']]
    required += [str(ROOT/'KEV'/s/(p+suffix+'.jsonl')) for s,p,suffix in [('decision-v7','train',''),('decision-v7','calibration',''),('decision-v7','test',''),('decision-v7','test','.variants'),('transfer-v4','test',''),('transfer-v4','test','.variants')]]
    for row in c['roster']:
        if row['status']=='available':
            required += [row['model']] + ([row['adapter']] if row['adapter'] else []) + [x['path'] for x in row['evidence'].values()]
            for x in row['evidence'].values(): pin(x)
    required += [c['review']['path'],h['runtime_evidence']['path'],h['matched_protocol']['path']] + list(c['source_files'])
    need(all(mounts.get(x) is False for x in required),'missing exact read-only input mount')
    need(mounts.get(c['out']) is True and mounts.get(c['round_dir']) is True,'writable output mounts')
    for p,rw in mounts.items():
        if rw:
            need(p in (c['out'],c['round_dir']),'unexpected writable mount')
            need(not any(Path(x)==Path(p) or Path(p).is_relative_to(Path(x)) for x in required),'writable overlaps input')
    implementations=h['implementation_files']
    for path in (Path(__file__).resolve(),Path(K.__file__).resolve(),Path(R.__file__).resolve(),Path(P.__file__).resolve()):
        need(str(path) in implementations,'missing host implementation pin')
    for p,v in implementations.items(): pin({'path':p,'sha256':v})
    cpu_entry(c)
    for p,v in c['source_files'].items(): pin({'path':p,'sha256':v})
    r0files=h['r0_source_files']; need(set(r0files)=={str(p) for p in R0.glob('*.py')},'r0 pin set')
    for p,v in r0files.items(): pin({'path':p,'sha256':v})
    for key in ('launch_receipt','claim','release'):
        need(Path(c['container'][key]).is_absolute(),'receipt path')
    need(Path(h['state_dir']).is_absolute() and Path(h['state_dir']).is_relative_to(ROOT),'durable state path')
    need(Path(h['cpu_python']).is_absolute() and Path(h['cpu_python']).is_file(),'CPU python')
    need(type(h['cpu_environment'])==dict and all(isinstance(k,str) and isinstance(v,str) for k,v in h['cpu_environment'].items()),'CPU environment')
    return h

def build(template,output):
    c=read(template); validate(c,output)
    need(not Path(output).exists(),'config already exists')
    save(output,c)

def probe(chip,name,allocation=None):
    P.host_check(); inv=P.Inventory()
    need(inv.inspect(name) is None,'container name already exists; reconcile')
    live=inv.conflict(chip) or P.device_query(chip)
    if allocation is None: return not live
    doc=R.load(allocation); R.validate_doc(doc)
    return not live and sum(x.get('chip')==chip for x in doc['free'])==1

def wait_ready(chip,name,allocation,lg,interval=600):
    while not probe(chip,name,allocation):
        log(lg,'heartbeat progress=waiting-resource count=0')
        time.sleep(interval)

def wait_process(p,lg,phase,interval=600):
    while True:
        try: return p.wait(timeout=interval)
        except subprocess.TimeoutExpired: log(lg,'heartbeat progress='+phase+' count=0')

def long_phase(cmd,env,state,lg,phase):
    intent=state/(phase.upper()+'-INTENT.json')
    need(not intent.exists(),phase+' already attempted: reconcile before retry')
    save(intent,{'command':cmd})
    with (state/(phase+'.log')).open('a') as f:
        p=subprocess.Popen(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        log(lg,'heartbeat progress='+phase+' count=0 pid='+str(p.pid))
        code=wait_process(p,lg,phase)
        f.flush(); os.fsync(f.fileno())
    save(state/(phase.upper()+'-EXIT.json'),{'exit_code':code})
    need(code==0,phase+' failed')

def drive(config):
    c=read(config); h=validate(c,config); t=c['container']; spec=t['spec']; state=Path(h['state_dir'])/c['member']; state.mkdir(parents=True,exist_ok=True)
    with (state/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lg=state/'supervisor.log'; marker=state/'SUPERVISOR-EXIT.json'
        if marker.exists(): raise RuntimeError('terminal exists; inspect before any new attempt')
        relaunch=[sys.executable,'-P',str(Path(__file__).resolve()),'run','--config',str(Path(config).resolve())]
        (state/'RELAUNCH.txt').write_text(shlex.join(relaunch)+'\n')
        try:
            log(lg,'heartbeat progress=validate count=0')
            R.image_inspect(c['image'])
            if h.get('cpu_requires_numpy',False):
                run([h['cpu_python'],'-P','-c','import numpy'],env=dict(h['cpu_environment']),stdout=subprocess.DEVNULL)
            # Core prepare checks all metadata, identity and FINAL before any accelerator claim.
            long_phase([h['cpu_python'],'-P',h['entry'],'prepare','--config',str(Path(config).resolve())],dict(h['cpu_environment']),state,lg,'prepare')
            launchpath=Path(t['launch_receipt']); intent=state/'LAUNCH-INTENT.json'
            if not intent.exists():
                need(not launchpath.exists() and not Path(t['claim']).exists(),'existing transaction requires reconciliation')
                wait_ready(t['chip'],spec['name'],h['allocation'],lg)
                R.claim(argparse.Namespace(alloc=h['allocation'],run=t['run'],chip=t['chip'],owner=h['owner'],purpose='RC1 Track K inference',proof=t['claim'],plan=None,plan_sha256=None,precondition=None,precondition_sha256=None,controller=None,controller_sha256=None))
                need(probe(t['chip'],spec['name']),'resource became busy after claim')
                save(intent,{'config_sha256':digest(c),'name':spec['name']})
                # Intent is durable before launch. An ambiguous response is never retried.
                result=run(K.command(spec),capture_output=True)
                ident=result.stdout.strip(); need(re.fullmatch('[0-9a-f]{64}',ident),'Docker launch ID')
                save(launchpath,{'id':ident,'config_sha256':digest(c)})
            else:
                need(read(intent)=={'config_sha256':digest(c),'name':spec['name']},'launch intent differs')
                need(launchpath.exists(),'unknown launch: reconcile retained container and claim manually; no duplicate')
            launch=read(launchpath); need(launch.get('config_sha256')==digest(c),'launch receipt differs')
            observed=R.docker_inspect(spec['name']); K.verify_observation(spec,observed,launch['id'])
            # Stream independently of the Docker process; resume appends if supervisor restarts.
            stream_file=(state/'inference.log').open('a')
            stream=subprocess.Popen(['docker','logs','--follow','--timestamps',launch['id']],stdout=stream_file,stderr=subprocess.STDOUT,start_new_session=True)
            if observed['State']['Status'] in ('created','running','restarting'):
                with (state/'docker-wait.log').open('a') as wf:
                    waiter=subprocess.Popen(['docker','wait',launch['id']],stdout=wf,stderr=subprocess.STDOUT,start_new_session=True)
                    need(wait_process(waiter,lg,'inference')==0,'docker wait failed; reconcile')
                observed=R.docker_inspect(spec['name']); K.verify_observation(spec,observed,launch['id'])
            need(observed['State']['Status']=='exited','container state uncertain')
            stream.wait(timeout=30); stream_file.flush(); os.fsync(stream_file.fileno()); stream_file.close()
            need(stream.returncode==0,'Docker log collection failed')
            R.release(argparse.Namespace(alloc=h['allocation'],run=t['run'],chip=t['chip'],container=spec['name'],container_id=launch['id'],claim=t['claim'],proof=t['release']))
            need(observed['State']['ExitCode']==0 and not observed['State'].get('OOMKilled',False),'inference failed after release')
            # Check the core marker before starting CPU; host-cpu verifies it again.
            ready=Path(c['out'])/'INFERENCE-READY.json'
            expected={'schema':'rc1-infer-exit-v1','config_sha256':digest(c),'exit_code':0,'ready_sha256':sha(ready)}
            need(read(Path(c['out'])/'INFER-EXIT.json')==expected,'inference marker differs')
            log(lg,'heartbeat progress=cpu count=0 resource=released')
            env={**h['cpu_environment'],'ASCEND_RT_VISIBLE_DEVICES':'','CUDA_VISIBLE_DEVICES':''}
            cpu_intent=state/'CPU-LAUNCH-INTENT.json'
            need(not cpu_intent.exists(),'CPU launch already attempted: reconcile before retry')
            save(cpu_intent,{'config_sha256':digest(c),'container_id':launch['id']})
            with (state/'cpu.log').open('a') as f:
                p=subprocess.Popen([h['cpu_python'],'-P',cpu_entry(c),'host-cpu','--config',str(Path(config).resolve())],env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                need(wait_process(p,lg,'cpu')==0,'CPU phase failed; reconcile before restart')
            save(marker,{'schema':'rc1-host-exit-v1','config_sha256':digest(c),'exit_code':0})
            log(lg,'complete exit=0')
        except BaseException as exc:
            log(lg,'failed '+type(exc).__name__+': '+str(exc))
            save(marker,{'schema':'rc1-host-exit-v1','config_sha256':digest(c),'exit_code':1,'error':str(exc)})
            raise

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build'); b.add_argument('--template',required=True); b.add_argument('--output',required=True)
    for a in ('validate','run','start'):
        q=sub.add_parser(a); q.add_argument('--config',required=True)
    a=p.parse_args()
    if a.action=='build': build(a.template,a.output)
    elif a.action=='validate': validate(read(a.config),a.config)
    elif a.action=='run': drive(a.config)
    else:
        c=read(a.config); h=validate(c,a.config); state=Path(h['state_dir'])/c['member'];state.mkdir(parents=True,exist_ok=True)
        with (state/'launcher.log').open('a') as f:
            p=subprocess.Popen([sys.executable,'-P',str(Path(__file__).resolve()),'run','--config',str(Path(a.config).resolve())],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps({'pid':p.pid,'state_dir':str(state)}))
if __name__=='__main__':main()
