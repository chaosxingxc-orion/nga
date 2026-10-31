"""Retained-container final evaluation entry; exact-plan inputs only.

Does not create approvals, select models, allocate devices or start containers.
Run only through a reviewed supervisor. Success is publication completion, not
scientific acceptance. Attempt output is durable and an active attempt is locked.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import threading
import traceback


def local(name):
    path=Path(__file__).with_name(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


C=local('r3_final_closure')


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,value):
    import tempfile
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def evaluate(plan,pin,review):
    """All checks precede construction of a lazy real scorer and every commit."""
    root=C.safe(plan['closure']['root'])
    C.require(Path(__file__).resolve()==root/'r3_code/r3_final_driver.py','driver outside pinned closure')
    C.verify(root,plan['closure']['sha256'],import_runtime=True)
    import r3_final_admission as admission
    import full_eval_r3 as evaluator
    import eval_r3
    import r3_final_test_adapter as adapter
    C.require(Path(eval_r3.__file__).resolve()==root/'r3_code/eval_r3.py','scorer factory outside closure')
    def validate():
        admission.verify(plan,pin,review)
        C.require(Path(plan['dataset_manifest']['path'])==Path(evaluator.C.KEV_DIR)/'manifest.json',
                  'runtime dataset root differs from plan manifest')
    validate()
    args=evaluator.parse_full_args(['--model-path',plan['model'],'--out',plan['out'],
        '--arm',plan['arm'],'--partitions','calibration,test','--stages','k','--round-dir',plan['round_dir'],
        '--dtype','float32','--no-hf32','--require-record-grade','--scorer','rightpad','--device','npu']
        +(['--adapter',plan['adapter']] if plan['adapter'] else []))
    args.token_budget=16384
    # Do not instantiate/configure an NPU scorer when merely reconciling an
    # already staged publication. The transaction must never call this fallback.
    if (Path(plan['out'])/'TEST-STAGED-RESULTS.json').exists():
        def scorer(*args,**kwargs):raise RuntimeError('recovery must never score')
    else:
        scorer=eval_r3.make_score_fn(args)
    owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,
               final_sha256=plan['final']['sha256'])
    result=adapter.run(args,scorer,evaluator,owner=owner,validate_admission=validate,
                       validate_publication=validate)
    C.require(result.get('state')=='completed','publication transaction incomplete')
    return result


def run(plan_path,pin,review,attempt):
    import hashlib
    C.require(type(attempt) is int and attempt>0,'positive attempt required')
    plan_path=C.safe(plan_path);plan=json.loads(plan_path.read_text())
    actual=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    C.require(actual==pin,'plan differs before opening output')
    out=C.safe(plan['out']);out.mkdir(parents=True,exist_ok=True)
    lockpath=C.safe(out/'final-driver.lock')
    fd=os.open(lockpath,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=C.safe(out/'final-attempts'/str(attempt));directory.mkdir(parents=True,exist_ok=False)
        started=utc();stop=threading.Event()
        def heartbeat():
            count=0
            while not stop.is_set():
                count+=1
                atomic(directory/'heartbeat.json',{'utc':utc(),'count':count,'pid':os.getpid(),
                    'state':'driver_alive','progress_source':str(out/'heartbeat.log')})
                stop.wait(30)
        worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
        rc=125;result=None
        command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--plan',str(plan_path),
                 '--sha256',pin,'--review',review['path'],'--review-sha256',review['sha256'],'--attempt',str(attempt)]
        (directory/'COMMAND.txt').write_text(shlex.join(command)+'\n')
        (directory/'RECOVERY.txt').write_text('Use the reviewed supervisor with the same plan/pins and next attempt after actual exit/release.\n')
        try:
            with (directory/'run.log').open('a',buffering=1) as log, redirect_stdout(log),redirect_stderr(log):
                try:
                    result=evaluate(plan,pin,review)
                    atomic(directory/'RESULT.json',result)
                    rc=0
                except BaseException:
                    traceback.print_exc();rc=1
        finally:
            stop.set();worker.join(5)
            terminal={'exit_code':rc,'attempt':attempt,'plan_sha256':pin,'started_utc':started,'finished_utc':utc(),
                      'publication_complete':rc==0,'scientific_acceptance':False}
            atomic(directory/'EXIT.json',terminal)
            atomic(out/'FINAL_EVAL_EXIT.json',terminal)
        return rc
    finally:os.close(fd)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--review',required=True);parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--attempt',required=True,type=int)
    a=parser.parse_args()
    sys.exit(run(a.plan,a.sha256,{'path':a.review,'sha256':a.review_sha256},a.attempt))
