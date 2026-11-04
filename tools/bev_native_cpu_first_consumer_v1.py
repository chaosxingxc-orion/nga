"""First-consumption CPU scorer with invocation-local verified reference reuse.

This is a successor for a future config. It consumes already-produced inference
records after a verified release and writes a fresh CPU summary without requiring
an older summary or terminal as an oracle. It never runs NPU inference.
"""
import argparse, hashlib, importlib.util, json, os, threading, time, traceback, fcntl, sys
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

def run(cfg_path,cfg_pin):
    started=time.monotonic()
    require(sha(cfg_path)==cfg_pin,'config changed'); cfg=read(cfg_path)
    require(cfg.get('schema')=='native-first-cpu-consumer-v1' and cfg.get('read_only_saved_records') is True,'scope differs')
    require(set(cfg)=={'schema','read_only_saved_records','attempt','plan','output','consumer','replay_consumer','runtime_module','python'},'config fields differ')
    require(cfg['consumer']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'consumer identity differs')
    require(type(cfg.get('attempt')) is int and cfg['attempt']==1,'attempt differs')
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
        put(out/'SERVICE.json',{'schema':'native-first-cpu-service-v1','config_sha256':cfg_pin,'plan_sha256':plan['sha256'],'started_utc':time.time(),'pid':os.getpid(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':Path('/proc/self/stat').read_text().split(') ')[1].split()[19],'scientific_acceptance':False})
        progress.emit(); C=replay.load(original['modules']['runtime'])
        summary=replay.consume(C,plan['path'],plan['sha256'],cfg['attempt'],progress)
        require(summary['scientific_acceptance'] is False and summary['candidate_test_authority'] is False,'summary authority differs')
        # Recheck all plan closure sources before publishing the new summary.
        for path,pin in original['files'].items(): require(sha(path)==pin,'source changed during consume')
        require(sha(plan['path'])==plan['sha256'],'plan changed during consume')
        require(sha(cfg_path)==cfg_pin and sha(__file__)==cfg['consumer']['sha256'] and sha(cfg['replay_consumer']['path'])==cfg['replay_consumer']['sha256'],'consumer/config changed during consume')
        put(out/'summary.json',summary)
        put(out/'PARITY.json',{'schema':'native-first-cpu-parity-v1','status':'FIRST_CONSUMPTION_COMPLETE','records':summary['n'],'summary_sha256':sha(out/'summary.json'),'whole_process_seconds':time.monotonic()-started,'reference_initializations':1,'receipts_sha256':progress.receipts_sha256,'phase_timings':progress.timings,'old_summary_required':False,'test_inference_rerun':False,'production_modified':False,'scientific_acceptance':False})
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
