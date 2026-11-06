#!/usr/bin/env python3
"""Detached CPU-only supervisor for the reviewed matched-current watcher."""
import datetime, fcntl, json, os, signal, subprocess, sys, threading, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/matched-current-dev-comparison')
def save(name, data):
    p=OUT/name; tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2)+'\n'); os.replace(tmp,p)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'host-runner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        previous=OUT/'HOST-EXIT.json'
        if previous.exists():
            os.replace(previous,OUT/('HOST-EXIT.previous.'+str(time.time_ns())+'.json'))
        cmd=[sys.executable,'-B','-P',str(HERE/'watcher.py')]
        env=os.environ.copy(); env.update(CUDA_VISIBLE_DEVICES='',ASCEND_RT_VISIBLE_DEVICES='',NPU_VISIBLE_DEVICES='')
        child=None; received=[]
        def terminate(signum, frame):
            received.append(signum)
            if child is not None and child.poll() is None: child.terminate()
        previous_handlers={s:signal.signal(s,terminate) for s in (signal.SIGTERM,signal.SIGINT)}
        child=subprocess.Popen(cmd,env=env)
        if received: child.terminate()
        save('HOST-LAUNCH.json',{'pid':os.getpid(),'watcher_pid':child.pid,'start_ticks':Path('/proc/self/stat').read_text().split()[21],'watcher_start_ticks':Path('/proc'/Path(str(child.pid))/'stat').read_text().split()[21],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'command':cmd,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        stop=threading.Event()
        def beat():
            while not stop.is_set():
                p=OUT/'comparison.json'; status='WAITING_FOR_STATUS'; progress=0
                try:
                    data=json.loads(p.read_text()); status=data['status']; progress=sum(x.get('status')=='VALIDATED_OPERAND' for x in data.get('operands',[]))
                except (OSError,ValueError,KeyError): pass
                heartbeat={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'watcher_pid':child.pid,'status':status,'progress':progress,'completed':progress,'total':12}
                save('HOST-HEARTBEAT.json',heartbeat)
                save('heartbeat.json',heartbeat)
                stop.wait(600)
        thread=threading.Thread(target=beat,daemon=True);thread.start()
        code=1
        try:
            while True:
                try:
                    code=child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if received:
                        try: code=child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            child.kill();code=child.wait()
                        break
            code=128+received[0] if received else code
        finally:
            stop.set();thread.join();save('HOST-EXIT.json',{'exit_code':code,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
            for s,handler in previous_handlers.items(): signal.signal(s,handler)
        return code
if __name__=='__main__':sys.exit(main())
