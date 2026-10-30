#!/usr/bin/env python3
"""E10 real native development inference with a preregistered interruption barrier."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    a = ap.parse_args()
    config = json.loads(Path(a.config).read_text())
    root = Path(config['out'])
    spec = importlib.util.spec_from_file_location('frozen_eval', config['eval_code'])
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    lock = (root/'driver.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stamp = ev.objhash(config)
    status = {'stage': 'verify', 'progress': 0, 'total': 8, 'chips': 1}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(5):
            ev.atomic(root/'STATUS.json', {'utc': ev.utc(), **status})
            with (root/'heartbeat.log').open('a') as f:
                f.write(ev.utc()+' '+' '.join(f'{k}={v}' for k,v in status.items())+'\n')
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        ev.verify_files(config)
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        import torch
        import torch_npu
        torch.npu.set_device('npu:0')
        torch.npu.config.allow_internal_format=False
        torch.npu.conv.allow_hf32=False
        torch.npu.matmul.allow_hf32=False
        torch.set_num_threads(8)
        sys.path.insert(0,config['kev_code'])
        import kev.predictors as predictors
        from kev.checkpoint import Checkpoint, LoadOptions
        from kev.suite import load_split, read_manifest
        from kev.benchmark import prediction_rows
        records=load_split(config['suite'],'development')[:8]
        ev.record_keys(records)
        ck=Checkpoint(config['checkpoint'])
        assert ck.meta.base==config['base_id']
        assert ck.meta.base_revision==Path(config['base'],'.complete').read_text().splitlines()[0]
        ck.meta.base,ck.meta.base_revision=config['base'],None
        predictors.Checkpoint=lambda _:ck
        predictors.sync=lambda _:torch.npu.synchronize()
        status['stage']='load'
        predictor=predictors.LocalPredictor(config['checkpoint'],'npu:0',LoadOptions(dtype=torch.float32,attn='eager',merge=True),context=read_manifest(config['suite'])['context'])
        items=root/'records'
        items.mkdir(exist_ok=True)
        expected={f'{i:06d}.json' for i in range(len(records))}
        if any(p.name not in expected for p in items.glob('*.json')):raise ValueError('Unexpected record')
        reused,computed=[],[]
        for i,record in enumerate(records):
            p=items/f'{i:06d}.json'
            if p.exists():
                payload=ev.read_record(p,record,stamp)
                prediction_rows(record,payload['prediction'])
                reused.append(i)
            else:
                status['stage']='inference'
                start=time.monotonic()
                pred=predictor(record)
                ev.validate_prediction(record,pred)
                prediction_rows(record,pred)
                duration=time.monotonic()-start
                payload={'stamp':stamp,'input_sha256':ev.objhash(record),'prediction':pred,'seconds':duration}
                ev.atomic(p,{'payload':payload,'sha256':ev.objhash(payload)})
                computed.append(i)
                status.update(questions_per_second_per_chip=len(record['questions'])/duration,reserved_gib=torch.npu.memory_reserved()/2**30)
            status['progress']=i+1
            if i==1 and not (root/'CONTINUE_AFTER_CRASH').exists():
                status['stage']='awaiting_preregistered_crash'
                ev.atomic(root/'INTERRUPT_READY.json',{'stamp':stamp,'records':2,'utc':ev.utc()})
                while not (root/'CONTINUE_AFTER_CRASH').exists():time.sleep(.25)
        if len(list(items.glob('*.json')))!=8:raise ValueError('Incomplete records')
        for i,record in enumerate(records):ev.read_record(items/f'{i:06d}.json',record,stamp)
        ev.verify_files(config)
        ev.atomic(root/'report.json',{'stamp':stamp,'split':'development','records':8,'reused':reused,'computed':computed,'test_metrics':False,'record_hashes':{p.name:ev.sha(p) for p in sorted(items.glob('*.json'))}})
        ev.atomic(root/'REFERENCE_COMPLETE.json',{'rc':0,'stamp':stamp,'records':8,'utc':ev.utc()})
        status['stage']='completed'
    except BaseException as exc:
        ev.atomic(root/'REFERENCE_COMPLETE.json',{'rc':1,'error':str(exc),'stamp':stamp,'utc':ev.utc()})
        status['stage']='failed'
        raise
    finally:
        stop.set()
        heartbeat_thread.join()
        ev.atomic(root/'STATUS.json',{'utc':ev.utc(),**status})


if __name__=='__main__':main()
