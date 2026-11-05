"""Bounded parallel first-consumption CPU scorer, version one.

This is a successor for a future config. It consumes already-produced inference
records after a verified release and writes a fresh CPU summary without requiring
an older summary or terminal as an oracle. It never runs NPU inference.
"""
import argparse, hashlib, importlib.util, json, os, threading, time, traceback, fcntl, sys
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from pathlib import Path

def require(ok, why):
    if not ok: raise ValueError(why)
def sha(p):
    q=Path(p); require(q.is_absolute() and not any(x.is_symlink() for x in (q,*q.parents)), 'unsafe path')
    with q.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def canonical_directory(value):
    path=Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'noncanonical directory')
    require(not any(x.is_symlink() for x in (path,*path.parents)), 'unsafe directory symlink')
    resolved=path.resolve(strict=False)
    require(path==resolved, 'noncanonical directory')
    return resolved
def load(path,pin):
    require(sha(path)==pin,'consumer source changed')
    raw=Path(path).read_bytes();require(hashlib.sha256(raw).hexdigest()==pin,'consumer source changed')
    import types
    m=types.ModuleType('native_cpu_replay_pinned');m.__file__=path;sys.modules[m.__name__]=m
    exec(compile(raw,path,'exec'),m.__dict__);return m

def put(p,obj):
    q=Path(p); q.parent.mkdir(parents=True,exist_ok=True);tmp=q.with_name(q.name+'.pending')
    with tmp.open('w') as f:
        json.dump(obj,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,q)
    fd=os.open(q.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def parallel_options(options):
    require(type(options) is dict and set(options)=={'workers','chunk_size'},'parallel config fields differ')
    require(type(options['workers']) is int and 1<=options['workers']<=32,'workers must be 1..32')
    require(type(options['chunk_size']) is int and 1<=options['chunk_size']<=1024,'chunk_size must be 1..1024')
    return dict(options)

def ordered_chunks(fn, count, *, workers, chunk_size):
    """Bound submission and memory; yield in source order, propagate any failure.

    Each task owns only its chunk. Pending plus completed out-of-order chunks never
    exceed 2*workers; the caller alone updates summaries/receipts/progress.
    """
    options=parallel_options({'workers':workers,'chunk_size':chunk_size})
    require(type(count) is int and count>=0,'invalid item count')
    chunks=iter((i,min(i+chunk_size,count)) for i in range(0,count,chunk_size))
    if workers==1:
        for start,end in chunks:yield fn(start,end)
        return
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='numeric-score') as pool:
        pending=deque()
        try:
            for _ in range(2*workers):
                job=next(chunks,None)
                if job is None:break
                pending.append(pool.submit(fn,*job))
            while pending:
                result=pending.popleft().result()
                yield result
                job=next(chunks,None)
                if job is not None:pending.append(pool.submit(fn,*job))
        finally:
            for future in pending:future.cancel()

def check_imports(replay,C,d,progress,options):
    """Same imported-byte contract as frozen runtime; independent bounded I/O."""
    manifest=C.read(d['recovery']['manifest']['path']);recovery=d['recovery'];root=Path(d['out'])/'items'
    C.require(manifest['schema']=='native-panel-imported-commits-v1' and manifest['source_plan']==recovery['source_plan'] and manifest['source_out']==C.read(recovery['source_plan']['path'])['out'] and manifest['count']==recovery['imported_count'],'import provenance differs')
    C.require(len(manifest['items'])==manifest['count'] and [x['ordinal'] for x in manifest['items']]==list(range(manifest['count'])),'import ordinals differ')
    def chunk(start,end):
        for item in manifest['items'][start:end]:
            dest=root/f"{item['ordinal']:06d}"
            C.require(set(item)=={'ordinal','record_sha256','commit_sha256'},'import entry differs')
            C.require(C.sha(dest/'record.json')==item['record_sha256'] and C.sha(dest/'COMMITTED.json')==item['commit_sha256'],'imported bytes changed')
            C.require(C.read(dest/'COMMITTED.json')=={'record.json':item['record_sha256']},'import receipt changed')
        return end-start
    done=0
    for count in ordered_chunks(chunk,manifest['count'],**options):
        done+=count;progress.tick(done)
    return done


def consume(replay,C,path,pin,attempt,progress,options):
    d=C.verify(path,pin,cpu=True);view,L,N=C.plan_legacy_view(d);X=C.module(d['modules']['panel']);P=C.module(d['modules']['protocol'])
    # Frozen plan verifies its original consumer; this replay has its own pinned config.
    ref=replay.VerifiedReference.create(N,d['modules']['native'],d['upstream'])
    pop=d['population'];items=X.rows(pop['items']['path']);gold=X.rows(pop['gold']['path']);requests=X.rows(pop['requests']['path']);contract=C.read(pop['contract']['path'])
    P.validate_items(items);C.require(len(items)==len(gold)==len(requests)==pop['count'],'population incomplete')
    expected=P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=d['model_sha256'],runtime_protocol_sha256=view['protocol_binding_sha256'])
    C.require(contract==expected and P.sha256_value(contract)==pop['contract_sha256'],'contract differs')
    ref.check_sources();progress.stage('imports',d['recovery']['imported_count'])
    completion=replay.lifecycle(C,d,pin,attempt)
    count=check_imports(replay,C,d,progress,options);progress.tick(count)
    C.require(completion.get('imported_manifest_sha256')==d['recovery']['manifest']['sha256'] and completion.get('source_plan_sha256')==d['recovery']['source_plan']['sha256'],'completion source provenance differs')
    C.require(completion['reused']==count and completion['computed']==d['population']['count']-count,'completion import counts differ')
    ref.check_sources();progress.stage('records',len(items))
    root=Path(d['out']);pred=[];receipts=[]
    C.require({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(len(items))},'output population differs')
    def chunk(start,end):
        result=[]
        for i in range(start,end):
            item,req,g=items[i],requests[i],gold[i]
            X.item_check(req,i,8192);C.require(req['request_sha256']==P.request_hash(item),'input source join differs')
            C.require(g==dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)),'gold join differs')
            dest=root/'items'/f'{i:06d}';p=replay.load_item(dest,req,view,N,ref)
            C.require(type(p.get('i')) is int and p['i']==i and p['qid']==item['qid'] and p['request_sha256']==req['request_sha256'] and p['input_sha256']==N.digest(req) and 'gold' not in p and 'y' not in p,'prediction join differs')
            result.append((dict(p,y=item['y']),C.sha(dest/'COMMITTED.json')))
        return result
    done=0
    for batch in ordered_chunks(chunk,len(items),**options):
        for prediction,receipt in batch:
            pred.append(prediction);receipts.append(receipt)
        done+=len(batch);progress.tick(done)
    C.require(type(completion.get('completed')) is int and completion['completed']==len(items) and completion.get('receipts_sha256')==N.digest(receipts) and completion.get('contract_sha256')==pop['contract_sha256'] and completion.get('ordered_inputs_sha256')==pop['ordered_inputs_sha256'] and completion.get('model_sha256')==d['model_sha256'],'completion binding differs')
    C.require(all(type(completion.get(k)) is int and completion[k]>=0 for k in ('computed','reused')) and completion['computed']+completion['reused']==len(items) and type(completion.get('forwards_per_new_item')) is int and completion['forwards_per_new_item']==1,'completion counts differ')
    ref.check_sources();progress.stage('summary',len(items))
    progress.receipts_sha256=N.digest(receipts)
    raw=P.summarise(items,pred,contract=contract,contract_sha256=pop['contract_sha256']);kinds={}
    for kind in ('choice','yes_no','score'):
        selected=[(i,p) for i,p in zip(items,pred) if i['kind']==kind];correct=sum(i['y']==p['first_index'] for i,p in selected)
        kinds[kind]=dict(n=len(selected),correct=correct,accuracy=correct/len(selected) if selected else None,metric_origin='NGA additive stratification')
    return dict(schema='native-config-panel-summary-v2',n=len(items),one_forward=dict(**raw['one_forward'],accuracy=raw['one_forward']['correct']/len(items)),by_type=kinds,adaptive='NOT_EVALUATED',scientific_acceptance=False,candidate_test_authority=False,plan_sha256=pin,attempt=attempt,scope=d['scope'],model=C.read(d['config']['path'])['model']['name']+' fixed checkpoint',engine='Transformers full-label fp32 b1 HF32 off')


def run(cfg_path,cfg_pin):
    started=time.monotonic()
    require(sha(cfg_path)==cfg_pin,'config changed'); cfg=read(cfg_path)
    require(cfg.get('schema')=='native-parallel-cpu-consumer-v1' and cfg.get('read_only_saved_records') is True,'scope differs')
    require(set(cfg)=={'schema','read_only_saved_records','attempt','plan','output','consumer','replay_consumer','runtime_module','python','parallel'},'config fields differ')
    require(cfg['consumer']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'consumer identity differs')
    require(type(cfg.get('attempt')) is int and cfg['attempt']==1,'attempt differs')
    options=parallel_options(cfg['parallel'])
    plan=cfg['plan']; require(sha(plan['path'])==plan['sha256'],'plan changed')
    out=canonical_directory(cfg['output'])
    original=read(plan['path']); prod=canonical_directory(original['out'])
    require(not out.is_relative_to(prod) and not prod.is_relative_to(out),'output overlaps production')
    require(original['test_read'] is True and original['scientific_acceptance'] is False,'plan authority differs')
    require(original['modules']['runtime']==cfg['runtime_module'],'runtime binding differs')
    out.parent.mkdir(parents=True,exist_ok=True)
    lock=(out.parent/(out.name+'.lock')).open('a')
    stop=None; t=None; progress=None; rc=1; owned=False
    try:
        # Every path after lock acquisition is covered by the same cleanup
        # boundary.  In particular, a duplicate/occupied output must not
        # leak the advisory lock when admission rejects it.
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not out.exists(),'output must be new')
        replay=load(cfg['replay_consumer']['path'],cfg['replay_consumer']['sha256'])
        out.mkdir(); owned=True
        progress=replay.Progress(out); stop=threading.Event()
        def beat():
            while not stop.wait(30): progress.emit()
        t=threading.Thread(target=beat,daemon=True);t.start()
        put(out/'RELAUNCH.json',{'argv':[cfg['python'],str(Path(__file__).resolve()),'--config',str(cfg_path),'--sha256',cfg_pin],'automatic_retry':False,'scientific_acceptance':False})
        put(out/'SERVICE.json',{'schema':'native-parallel-cpu-service-v1','config_sha256':cfg_pin,'plan_sha256':plan['sha256'],'started_utc':time.time(),'pid':os.getpid(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':Path('/proc/self/stat').read_text().split(') ')[1].split()[19],'scientific_acceptance':False})
        progress.emit(); C=replay.load(original['modules']['runtime'])
        summary=consume(replay,C,plan['path'],plan['sha256'],cfg['attempt'],progress,options)
        require(summary['scientific_acceptance'] is False and summary['candidate_test_authority'] is False,'summary authority differs')
        # Recheck all plan closure sources before publishing the new summary.
        for path,pin in original['files'].items(): require(sha(path)==pin,'source changed during consume')
        require(sha(plan['path'])==plan['sha256'],'plan changed during consume')
        require(sha(cfg_path)==cfg_pin and sha(__file__)==cfg['consumer']['sha256'] and sha(cfg['replay_consumer']['path'])==cfg['replay_consumer']['sha256'],'consumer/config changed during consume')
        put(out/'summary.json',summary)
        put(out/'PARITY.json',{'schema':'native-parallel-cpu-parity-v1','parallel':options,'scoring_records_seconds':progress.timings.get('records'),'cpu_only':True,'status':'FIRST_CONSUMPTION_COMPLETE','records':summary['n'],'summary_sha256':sha(out/'summary.json'),'whole_process_seconds':time.monotonic()-started,'reference_initializations':1,'receipts_sha256':progress.receipts_sha256,'phase_timings':progress.timings,'old_summary_required':False,'test_inference_rerun':False,'production_modified':False,'scientific_acceptance':False})
        rc=0
    except BaseException as e:
        # Admission failures do not own this output and must never overwrite
        # another worker's terminal (including a completed prior generation).
        if not owned:
            raise
        try:
            put(out/'ERROR.json',{'error':str(e),'phase':getattr(progress,'phase',None),'completed':getattr(progress,'completed',None),'traceback':traceback.format_exc(),'scientific_acceptance':False})
        finally:
            traceback.print_exc()
    finally:
        try:
            if stop is not None:
                stop.set()
            if t is not None and t.ident is not None:
                t.join(2)
            if owned:
                put(out/'EXIT.json',{'exit_code':rc,'config_sha256':cfg_pin,'plan_sha256':plan['sha256'],'summary_sha256':sha(out/'summary.json') if rc==0 else None,'old_summary_required':False,'utc_seconds':time.time(),'elapsed_seconds':time.monotonic()-started,'scientific_acceptance':False})
        finally:
            # Closing releases flock even if failure-reporting itself fails.
            lock.close()
    return rc

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();raise SystemExit(run(a.config,a.sha256))
