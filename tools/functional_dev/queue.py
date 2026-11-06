"""Detached host dispatcher; explicit review pin, one fixed smoke, then eight lanes."""
import concurrent.futures, datetime, fcntl, hashlib, json, os, re, subprocess, sys, threading, time, traceback
from pathlib import Path
R=Path(__file__).resolve().parent
C=json.loads((R/'config.json').read_text()); ROOT=Path(C['root']); OUT=ROOT/'followup-record-grade'

def put(p,obj):
    p=Path(p); tmp=p.with_name(p.name+'.tmp.'+str(os.getpid())+'.'+str(threading.get_ident()))
    with tmp.open('w') as f: json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def cmd(*args): return subprocess.run(args,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.strip()
def verify_sources():
    manifest=Path(C['closure'])/'manifest.json'
    if sha(manifest)!='69ec7d7c78df080eff6645393a00c6ab3b485fd16e5f99a5c347dc866354b64a': raise RuntimeError('closure manifest mismatch')
    if sha('/mnt/cephfs/xingchao/experiments/jev/KEV/manifest.json')!='c2e8cbc6e0c686be2cc730890928d803e3f4de1b9b745abbea90adb6f3903afd': raise RuntimeError('data manifest mismatch')
    for entry in json.loads(manifest.read_text())['code'].values():
        if sha(entry['snapshot'])!=entry['sha256']: raise RuntimeError('closure source mismatch: '+entry['snapshot'])
def reviewed():
    p=OUT/'REVIEW-APPROVED.json'
    if not p.is_file(): return False
    x=json.loads(p.read_text())
    return x.get('verdict')=='pass' and x.get('wrapper_sha256')==sha(R/'dev_wrapper.py') and x.get('queue_sha256')==sha(R/'queue.py') and x.get('config_sha256')==sha(R/'config.json') and bool(x.get('review_artifact'))
def free(chip):
    ids=cmd('docker','ps','-q').split()
    if ids:
        for c in json.loads(cmd('docker','inspect',*ids)):
            for d in c['HostConfig'].get('Devices') or []:
                if d.get('PathOnHost') in ('/dev/davinci'+str(chip),'/dev/davinci*'): return False
    return not re.search(r'^\|\s*'+str(chip)+r'\s+\d+\s+\d+\s+',cmd('npu-smi','info'),re.M)
def ready(j):
    base=ROOT/j['id']; launch=base/'train-LAUNCH.json'
    while not launch.exists():
        e=base/'smoke-EXIT.json'
        if e.exists() and json.loads(e.read_text())['exit_code']!=0: raise RuntimeError('training smoke failed')
        time.sleep(30)
    cid=json.loads(launch.read_text())['container_id']
    code=int(cmd('docker','wait',cid)); actual=json.loads(cmd('docker','inspect',cid))[0]
    if code or actual['State']['ExitCode']!=code: raise RuntimeError('training actual exit nonzero or inconsistent')
    for _ in range(60):
        if (base/'COMPLETE.json').is_file(): break
        time.sleep(2)
    done=base/'COMPLETE.json'; adapter=base/'result/adapter'; ck=base/'result/ckpt/step_003116.pt'
    if not done.is_file() or json.loads(done.read_text())!={'exit_code':0,'steps':3116,'scientific_acceptance':False} or not ck.is_file(): raise RuntimeError('missing terminal completion/checkpoint')
    pub=json.loads((adapter/'PUBLICATION.json').read_text()); bind=pub['binding']
    if bind['owner']!='rc1-functional-'+j['id'] or bind!=json.loads((adapter/'BINDING.json').read_text()) or bind['checkpoint_sha256']!=sha(ck): raise RuntimeError('publication binding mismatch')
    for name, h in pub['files'].items():
        if name not in ('adapter_config.json','adapter_model.safetensors') or sha(adapter/name)!=h: raise RuntimeError('publication file mismatch')
    if set(pub['files'])!={'adapter_config.json','adapter_model.safetensors'}: raise RuntimeError('incomplete publication')
    cfg=json.loads((adapter/'adapter_config.json').read_text())
    if cfg['base_model_name_or_path']!='Qwen3.5-'+j['size']+'-Base' or cfg['revision']!=(Path(j['model'])/'.complete').read_text().splitlines()[0]: raise RuntimeError('adapter base mismatch')
    return {'container_id':cid,'binding':bind,'publication_sha256':sha(adapter/'PUBLICATION.json')}
def launch(j,kind,binding):
    d=OUT/(kind+'-'+j['id']);d.mkdir(exist_ok=True); receipt=d/'LAUNCH.json'; term=d/'EXIT.json';name='nga-rc1-rg-'+kind+'-'+j['id']
    if term.exists():
        if json.loads(term.read_text())['exit_code']!=0: raise RuntimeError('prior failure retained; no automatic retry')
        return
    mounts=[(j['model'],j['model'],True),(str(ROOT/j['id']/'result/adapter'),str(ROOT/j['id']/'result/adapter'),True),('/usr/local/Ascend/driver','/usr/local/Ascend/driver',True),(str(R/'dev_wrapper.py'),'/run/dev_wrapper.py',True),(C['closure']+'/r3_code',C['closure']+'/r3_code',True),(C['closure']+'/r0_code','/mnt/cephfs/xingchao/experiments/jev/r0_code',True),(str(d),'/run/output',False)]
    kev='/mnt/cephfs/xingchao/experiments/jev/KEV'
    for f in ['manifest.json','decision-v7/train.jsonl','decision-v7/calibration.jsonl','decision-v7/dev.jsonl','decision-v7/dev.variants.jsonl','transfer-v4/dev.jsonl','transfer-v4/dev.variants.jsonl']: mounts.append((kev+'/'+f,kev+'/'+f,True))
    command=['docker','run','-d','--pull=never','--name',name,'--label','nga.rc1.record-grade='+C['deployment_id'],'--runtime','runc','--network','none','--shm-size','16g']
    for dev in ('davinci_manager','devmm_svm','hisi_hdc','davinci'+str(j['chip'])): command+=['--device','/dev/'+dev]
    for src,dst,ro in mounts: command+=['--mount','type=bind,src='+src+',dst='+dst+(',readonly' if ro else '')]
    for k,v in {'ASCEND_RT_VISIBLE_DEVICES':'0','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'4'}.items(): command+=['-e',k+'='+v]
    setup='source /usr/local/Ascend/ascend-toolkit/set_env.sh; source /usr/local/Ascend/cann-9.2.0/share/info/ascendnpu-ir/bin/set_env.sh; source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi=1; export PYTHONPATH=/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe; exec python3 -B -P /run/dev_wrapper.py "$@"'
    command+=['--entrypoint','/bin/bash',C['image'],'-c',setup,'--','--model',j['model'],'--adapter',str(ROOT/j['id']/'result/adapter'),'--out','/run/output/result']
    if kind=='smoke': command+=['--smoke']
    if receipt.exists():
        if not (d/'COMMAND.json').exists() or json.loads((d/'COMMAND.json').read_text())!=command or json.loads((d/'BINDING.json').read_text())!=binding: raise RuntimeError('existing receipt command or binding mismatch')
    else:
        put(d/'COMMAND.json',command);put(d/'BINDING.json',binding)
    if receipt.exists(): cid=json.loads(receipt.read_text())['container_id']
    else:
        # Never adopt an unreceipted name: launch may have succeeded before a crash.
        exists=subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
        if exists: raise RuntimeError('unreceipted container exists; manual inspection required')
        while not free(j['chip']): time.sleep(60)
        if not reviewed(): raise RuntimeError('review pin changed before launch')
        verify_sources()
        cid=cmd(*command);put(receipt,{'container_id':cid,'chip':j['chip'],'command_sha256':sha(d/'COMMAND.json')})
    info=json.loads(cmd('docker','inspect',cid))[0]
    if info['Name']!='/'+name or info['Image']!=C['image'] or info['Config']['Labels'].get('nga.rc1.record-grade')!=C['deployment_id'] or json.loads(receipt.read_text())['command_sha256']!=sha(d/'COMMAND.json'): raise RuntimeError('refuse foreign container attachment')
    with (d/'run.log').open('a') as log:
        logger=subprocess.Popen(['docker','logs','--follow',cid],stdout=log,stderr=subprocess.STDOUT)
        code=int(cmd('docker','wait',cid));logger.wait(timeout=30)
    actual=json.loads(cmd('docker','inspect',cid))[0]
    if actual['State']['ExitCode']!=code: raise RuntimeError('container exit mismatch')
    if code==0 and not (d/'result/report.json').is_file(): code=1
    put(term,{'exit_code':code,'container_exit_code':actual['State']['ExitCode'],'container_id':cid,'finished_at':actual['State']['FinishedAt']})
    if code: raise RuntimeError('evaluation failed; retained')

def lane(j):
    binding=ready(j)
    while not reviewed(): time.sleep(30)
    # first available completed training performs the single smoke under exclusive lock
    with (OUT/'smoke.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (OUT/'SMOKE-FAILED.json').exists(): raise RuntimeError('smoke failed; no full launch')
        if not (OUT/'SMOKE-PASS.json').exists():
            try: launch(j,'smoke',binding);put(OUT/'SMOKE-PASS.json',{'lane':j['id'],'report':str(OUT/('smoke-'+j['id'])/'result/report.json'),'wrapper_sha256':sha(R/'dev_wrapper.py')})
            except Exception as e: put(OUT/'SMOKE-FAILED.json',{'lane':j['id'],'error':str(e)});raise
    if not reviewed(): raise RuntimeError('review pin changed after smoke')
    launch(j,'full',binding)
    return 'complete'
def main():
    OUT.mkdir(exist_ok=True)
    with (OUT/'queue.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        put(OUT/'LAUNCH.json',{'pid':os.getpid(),'start_ticks':Path('/proc/self/stat').read_text().split()[21],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'queue_sha256':sha(R/'queue.py')})
        results={}
        stop=threading.Event()
        def heartbeat():
            while not stop.wait(60):
                put(OUT/'heartbeat.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed':len(results),'total':8,'reviewed':reviewed()})
        threading.Thread(target=heartbeat,daemon=True).start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            fs={pool.submit(lane,j):j['id'] for j in C['jobs']}
            for f in concurrent.futures.as_completed(fs):
                try: results[fs[f]]=f.result()
                except Exception as e: results[fs[f]]='FAILED: '+str(e);put(OUT/(fs[f]+'-ERROR.json'),{'error':str(e),'traceback':traceback.format_exc()})
                put(OUT/'digest.json',{'results':results,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        stop.set()
        code=0 if len(results)==8 and all(v=='complete' for v in results.values()) else 1
        put(OUT/'EXIT.json',{'exit_code':code,'results':results});return code
if __name__=='__main__': sys.exit(main())
