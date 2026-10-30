#!/usr/bin/env python3
"""Native Open-Jev synthetic device probe; no benchmark or calibration."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import time


def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()


def stamp(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,allow_nan=False).encode()).hexdigest()


def atomic(p,obj):
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
    try:
        os.fchmod(fd,0o644)
        with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);a=ap.parse_args()
    c=json.loads(Path(a.config).read_text());out=Path(c['out']);out.mkdir(exist_ok=True)
    lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    identity=stamp(c);status={'stage':'verify','progress':0,'total':3,'chips':1};stop=threading.Event()
    def heartbeat():
        while not stop.wait(15):
            now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());atomic(out/'STATUS.json',{'utc':now,**status})
            with (out/'heartbeat.log').open('a') as f:f.write(now+' '+' '.join(f'{k}={v}' for k,v in status.items())+'\n')
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        for p,h in c['files'].items():
            if digest(p)!=h:raise ValueError('Frozen input changed: '+p)
        for k in ['JEV_LOAD_8BIT','JEV_LOAD_4BIT','JEV_DEVICE_MAP','JEV_MAX_MEMORY']:os.environ.pop(k,None)
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',JEV_TORCH_DTYPE='bfloat16')
        import torch
        import torch_npu
        torch.npu.set_device('npu:0');torch.npu.config.allow_internal_format=False
        torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False;torch.set_num_threads(8)
        sys.path.insert(0,c['code'])
        from jev.model import DecisionModel
        from jev.api import compile_request,format_response
        class LocalDecisionModel(DecisionModel):
            def __init__(self,model_id,revision,**kwargs):
                if model_id!=c['base_id'] or revision!=c['base_revision']:raise ValueError('Checkpoint identity mismatch')
                if Path(c['base'],'.complete').read_text().splitlines()[0]!=revision:raise ValueError('Base revision mismatch')
                super().__init__(c['base'],None,**kwargs)
        status['stage']='loading';start=time.monotonic()
        model=LocalDecisionModel.load(c['checkpoint'],device='npu:0');torch.npu.synchronize();load=time.monotonic()-start
        temperature=json.loads(Path(c['checkpoint'],'temperature.json').read_text())['temperature']
        fixtures=json.loads(Path(c['fixtures']).read_text());results=[]
        for i,fixture in enumerate(fixtures):
            p=out/f'record-{i:04d}.json';records=compile_request(fixture['state'],fixture['questions'])
            if p.exists():
                env=json.loads(p.read_text());saved=env['payload']
                if stamp(saved)!=env['sha256'] or saved['stamp']!=identity or saved['input_hash']!=stamp(fixture):raise ValueError('Invalid persisted evidence')
                results.append(saved);continue
            status['stage']='synthetic_inference';runs=[]
            for repeat in range(2):
                torch.npu.synchronize();t=time.monotonic()
                with torch.inference_mode():z=model(records)
                torch.npu.synchronize();elapsed=time.monotonic()-t
                logits=[v.float().cpu().tolist() for v in z]
                probs=[torch.softmax(v.float()/temperature,-1).cpu().tolist() for v in z]
                if any(not math.isfinite(v) for row in logits for v in row):raise ValueError('Nonfinite logits')
                format_response(records,probs)
                runs.append({'logits':logits,'probabilities':probs,'seconds':elapsed})
            delta=max(abs(v-w) for row,other in zip(runs[0]['probabilities'],runs[1]['probabilities']) for v,w in zip(row,other))
            saved={'stamp':identity,'input_hash':stamp(fixture),'records':records,'runs':runs,'repeat_max_abs_probability_delta':delta,
                   'questions_per_second_per_chip':len(records)/runs[1]['seconds'],'reserved_memory_gib':torch.npu.memory_reserved()/2**30}
            atomic(p,{'payload':saved,'sha256':stamp(saved)});results.append(saved)
            status.update(progress=i+1,questions_per_second_per_chip=saved['questions_per_second_per_chip'],reserved_gib=saved['reserved_memory_gib'])
        for p,h in c['files'].items():
            if digest(p)!=h:raise ValueError('Frozen input changed during probe: '+p)
        atomic(out/'report.json',{'stamp':identity,'kind':'synthetic_native_probe','test_metrics':False,'load_seconds':load,'temperature':temperature,'chips':1,'results':results,
            'runtime':{'torch':torch.__version__,'torch_npu':torch_npu.__version__},'limitations':'Three synthetic requests establish execution only; no cross-device equivalence or test quality claim.'})
        atomic(out/'PROBE_COMPLETE.json',{'rc':0,'records':len(results),'stamp':identity});status['stage']='complete'
    except BaseException as exc:
        atomic(out/'PROBE_COMPLETE.json',{'rc':1,'error':str(exc),'stamp':identity,'stage':status['stage']});status['stage']='failed';raise
    finally:
        stop.set();thread.join();atomic(out/'STATUS.json',status)


if __name__=='__main__':main()
