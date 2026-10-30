#!/usr/bin/env python3
"""Detached CPU stage: wait for inference terminal, audit, then compare reference.

No model loading, training, inference restart or chip allocation. All subprocess
outputs persist in their own files. Nonzero or malformed terminals fail closed.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time


def atomic(path, value):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name+'.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(value, file, allow_nan=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def digest(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(4<<20),b''): h.update(chunk)
    return h.hexdigest()


def terminal_state(path):
    if not path.exists(): return 'pending'
    obj = json.loads(path.read_text())
    if type(obj.get('rc')) is not int:
        raise ValueError('Malformed inference terminal')
    if obj['rc'] != 0:
        raise ValueError('Inference failed; no aggregate acceptance')
    return 'ready'


def wrapper_state(run):
    if (run/'FAILED').exists():
        raise ValueError('Inference wrapper FAILED, including conflicting DONE/FAILED')
    done = run/'DONE'
    if not done.exists(): return 'pending'
    if not re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?', done.read_text()):
        raise ValueError('Malformed wrapper DONE')
    # A stale wrapper cannot certify a newer inference terminal.
    if done.stat().st_mtime_ns < (run/'REFERENCE_COMPLETE.json').stat().st_mtime_ns:
        raise ValueError('Wrapper DONE predates inference terminal')
    return 'ready'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',required=True,type=Path)
    a=ap.parse_args()
    plan=json.loads(a.plan.read_text());out=Path(plan['out']);out.mkdir(parents=True,exist_ok=True)
    lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    status={'stage':'verify_plan','progress':0,'total':3,'chips':0}
    stop=threading.Event()
    def hb():
        while not stop.wait(15):
            snapshot={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status}
            atomic(out/'STATUS.json',snapshot)
            with (out/'heartbeat.log').open('a') as f:
                f.write(snapshot['utc']+' stage='+status['stage']+f" done={status['progress']} total=3 chips=0\n")
    thread=threading.Thread(target=hb,daemon=True);thread.start()
    try:
        for path, expected in plan['files'].items():
            if digest(path)!=expected: raise ValueError('Changed finisher input: '+path)
        config=Path(plan['config']);run=Path(json.loads(config.read_text())['out'])
        status['stage']='waiting_for_inference_terminal'
        while terminal_state(run/'REFERENCE_COMPLETE.json')=='pending':
            if (run/'FAILED').exists(): raise ValueError('Inference wrapper FAILED')
            time.sleep(5)
        # The wrapper independently records process exit. Do not accept a marker
        # written just before a later process failure.
        status.update(stage='waiting_for_wrapper',progress=1)
        while wrapper_state(run)=='pending':
            time.sleep(5)
        status['stage']='independent_audit'
        with (out/'audit.log').open('ab') as log:
            subprocess.run([sys.executable,'-P',plan['auditor'],'--config',str(config),
                '--out',str(out/'INDEPENDENT_AUDIT.json')],stdout=log,stderr=subprocess.STDOUT,check=True)
        status.update(stage='published_comparison',progress=2)
        with (out/'comparison.log').open('ab') as log:
            subprocess.run([sys.executable,'-P',plan['comparison'],'--run',str(run),
                '--upstream',plan['upstream'],'--out',str(out/'PUBLISHED_COMPARISON.json')],
                stdout=log,stderr=subprocess.STDOUT,check=True)
        if wrapper_state(run)!='ready' or terminal_state(run/'REFERENCE_COMPLETE.json')!='ready':
            raise ValueError('Inference completion changed during audit')
        report={'status':'COMPLETED_SCOPED','inference_run':str(run),'config_sha256':digest(config),
            'auditor_sha256':digest(plan['auditor']),'comparison_sha256':digest(plan['comparison']),
            'outputs':{n:digest(out/n) for n in ['INDEPENDENT_AUDIT.json','PUBLISHED_COMPARISON.json']},
            'scope':'Main metric and provenance checks plus descriptive comparison; not Astra approval.'}
        atomic(out/'report.json',report)
        atomic(out/'FINISH_COMPLETE.json',{'rc':0,**report})
        status.update(stage='completed',progress=3)
        (out/'DONE').write_text('rc=0 utc='+time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+'\n')
    except BaseException as exc:
        atomic(out/'FINISH_COMPLETE.json',{'rc':1,'stage':status['stage'],'error':str(exc)})
        (out/'FAILED').write_text('rc=1\n');status['stage']='failed';raise
    finally:
        stop.set();thread.join();atomic(out/'STATUS.json',status)


if __name__=='__main__':main()
