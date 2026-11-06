import concurrent.futures, datetime, fcntl, hashlib, json, os, subprocess, threading, time
from pathlib import Path

ROOT=Path(os.environ.get("NGA_CAMPAIGN_ROOT", str(Path(__file__).resolve().parent))).resolve()
C=json.loads((ROOT/'QUEUE.json').read_text())
def put(p,d):
    q=p.with_suffix(p.suffix+'.tmp')
    with q.open('w') as f:
        json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,p)
def call(args,**kw):return subprocess.run(args,check=True,text=True,**kw)
def run(j):
    out=ROOT/j['id'];out.mkdir(exist_ok=True);(out/'result').mkdir(exist_ok=True)
    lock=(out/'queue.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    c=json.loads((ROOT/j['config']).read_text())
    for phase in ['smoke','train']:
        terminal=out/(phase+'-EXIT.json')
        if terminal.exists():
            if json.loads(terminal.read_text())['exit_code']!=0:raise RuntimeError(f'{phase} previously failed; preserve attempt and diagnose before retry')
            continue
        if phase=='train':
            ck=out/'result/ckpt/step_000002.pt'
            if not ck.is_file():raise ValueError('smoke missing step2 checkpoint')
            c['resume']={'path':'/run/nga/output/result/ckpt/step_000002.pt','sha256':hashlib.sha256(ck.read_bytes()).hexdigest()}
            c['engineering_stop_after']=C['total_steps']-C['smoke_steps']
        config=out/(phase+'.json');put(config,c)
        name='nga-rc1-'+j['id']+'-'+phase
        cmd=['docker','run','-d','--pull=never','--name',name,'--runtime','runc','--network','none','--shm-size','16g','--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
        for dev in ['davinci_manager','devmm_svm','hisi_hdc','davinci'+str(j['chip'])]:cmd+=['--device','/dev/'+dev]
        for source,dest,ro in [(j['model'],'/model/base',True),(C['train'],'/data/train.jsonl',True),('/usr/local/Ascend/driver','/usr/local/Ascend/driver',True),(str(config),'/run-config.json',True),(str(out),'/run/nga/output',False)]:
            cmd+=['--mount','type=bind,src='+source+',dst='+dest+(',readonly' if ro else '')]
        for k,v in {'ASCEND_RT_VISIBLE_DEVICES':'0','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','TASK_QUEUE_ENABLE':'2','PYTORCH_NPU_ALLOC_CONF':'expandable_segments:True'}.items():cmd+=['-e',k+'='+v]
        cmd += [C['image'],'/run-config.json']
        put(out/(phase+'-COMMAND.json'),cmd)
        receipt=out/(phase+'-LAUNCH.json')
        if receipt.exists():cid=json.loads(receipt.read_text())['container_id']
        else:
            cid=call(cmd,capture_output=True).stdout.strip();put(receipt,{'container_id':cid,'chip':j['chip'],'phase':phase,'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        with (out/(phase+'.log')).open('a') as log:
            logger=subprocess.Popen(['docker','logs','--follow',cid],stdout=log,stderr=subprocess.STDOUT)
            code=int(call(['docker','wait',cid],capture_output=True).stdout.strip())
            logger.wait(timeout=30)
        actual=json.loads(call(['docker','inspect',cid],capture_output=True).stdout)[0]
        if actual['State']['ExitCode']!=code:raise ValueError('exit mismatch')
        put(terminal,{'exit_code':code,'container_id':cid,'image':actual['Image'],'finished_at':actual['State']['FinishedAt'],'phase':phase,'chip':j['chip']})
        if code:raise RuntimeError(f'{phase} failed with exit {code}; preserve attempt and diagnose before retry')
    put(out/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False})
def monitor(stop, once=False):
    while True:
        rows=[]
        for j in C['jobs']:
            out=ROOT/j['id'];row={k:j[k] for k in ['id','chip','size','seed']}
            for phase in ['smoke','train']:
                for suffix in ['LAUNCH','EXIT']:
                    p=out/(phase+'-'+suffix+'.json')
                    if p.exists():row[phase+'_'+suffix.lower()]=json.loads(p.read_text())
            p=out/'result/heartbeat.json'
            if p.exists():
                try:row['progress']=json.loads(p.read_text())
                except (ValueError,OSError):pass
            for phase in ['smoke','train']:
                p=out/(phase+'.log')
                if p.exists():
                    with p.open('rb') as f:
                        f.seek(max(0,p.stat().st_size-8192));b=f.read(8192)
                    row[phase+'_log']={'bytes':p.stat().st_size,'error_flag':any(x in b for x in [b'Traceback',b'RuntimeError',b'Error:']),'path':str(p)}
            rows.append(row)
        put(ROOT/'digest.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobs':rows})
        if once or stop.wait(C['monitor_seconds']): break
if __name__=='__main__':
    lock=(ROOT/'queue.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stop=threading.Event();watch=threading.Thread(target=monitor,args=(stop,),daemon=True);watch.start()
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        fs={pool.submit(run,j):j for j in C['jobs']}
        for f in concurrent.futures.as_completed(fs):
            try:f.result()
            except Exception as e:
                j=fs[f];errors.append({'job':j['id'],'error_type':type(e).__name__,'message':str(e)})
                put(ROOT/j['id']/'QUEUE-ERROR.json',errors[-1])
    stop.set();watch.join();monitor(threading.Event(), once=True)
    put(ROOT/'QUEUE-EXIT.json',{'exit_code':1 if errors else 0,'errors':errors,'note':'Per-job markers determine training completion'})
