#!/usr/bin/env python3
"""Longest-development-record resource probe before native Kev extended test."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_kev_eval import atomic, objhash, sha, validate_prediction, verify_files


def validate_saved(envelope, row, identity, index, packed_tokens):
    item = envelope['payload']
    if envelope['sha256'] != objhash(item):
        raise ValueError('Probe receipt checksum mismatch')
    if (item['identity'], item['input_hash'], item['index'], item['packed_tokens']) != (
            identity, objhash(row), index, packed_tokens):
        raise ValueError('Foreign probe resume')
    if len(item['predictions']) != 2 or len(item['seconds']) != 2:
        raise ValueError('Probe requires two completed passes')
    if not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in item['seconds']):
        raise ValueError('Invalid probe duration')
    for prediction in item['predictions']:
        validate_prediction(row, prediction)
        if prediction['input_tokens'] != packed_tokens:
            raise ValueError('Probe token count mismatch')
    return item


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True); a = ap.parse_args()
    path = Path(a.config); c = json.loads(path.read_text()); identity = objhash(c)
    out = Path(c['out']) / 'longest_dev_probe'; out.mkdir(exist_ok=True)
    lock = (out/'driver.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    status = {'stage':'verify', 'progress':0, 'total':len(c['suites']), 'chips':1}
    stop = threading.Event(); config_hash = sha(path)
    def heartbeat():
        while not stop.wait(15):
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            atomic(out/'STATUS.json', {'utc':now, **status})
            with (out/'heartbeat.log').open('a') as f:
                f.write(now+' '+' '.join(f'{k}={v}' for k,v in status.items())+'\n')
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    rc = 1; error = None; outputs = {}
    try:
        verify_files(c)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
        sys.dont_write_bytecode = True
        import torch
        import torch_npu
        torch.npu.set_device('npu:0'); torch.npu.config.allow_internal_format = False
        torch.npu.conv.allow_hf32 = False; torch.npu.matmul.allow_hf32 = False; torch.set_num_threads(8)
        sys.path.insert(0, c['kev_code'])
        import kev.predictors as predictors
        from kev.checkpoint import Checkpoint, LoadOptions
        from kev.suite import load_split, read_manifest
        from kev.data import materialize
        ck = Checkpoint(c['checkpoint'])
        if (ck.meta.base, ck.meta.base_revision) != (c['base_id'], c['base_revision']):
            raise ValueError('Checkpoint identity mismatch')
        if Path(c['base'],'.complete').read_text().splitlines()[0] != c['base_revision']:
            raise ValueError('Local base revision mismatch')
        ck.meta.base, ck.meta.base_revision = c['base'], None
        predictors.Checkpoint = lambda _: ck
        predictors.sync = lambda _: torch.npu.synchronize()
        status['stage'] = 'loading'
        predictor = predictors.LocalPredictor(c['checkpoint'],'npu:0',
            LoadOptions(dtype=torch.float32,attn='eager',merge=True),
            context=read_manifest(c['suites'][0]['path'])['context'])
        results = []
        for i,suite in enumerate(c['suites']):
            context = read_manifest(suite['path'])['context']; predictor.context = context
            records = load_split(suite['path'],'development')
            status.update(stage=suite['name']+':tokenize_all_dev')
            lengths = []
            for row in records:
                encoded = predictor.model.encode(predictor.tok,materialize(row),
                    max_state=context['max_state'],max_branch=context['max_branch'],strict=True)
                n = len(encoded['ids'])
                if n > context['max_packed']: raise ValueError('Development packed overflow')
                lengths.append(n)
            index = max(range(len(records)), key=lambda k:lengths[k]); row = records[index]
            target = out/(suite['name']+'.json')
            if target.exists():
                item = validate_saved(json.loads(target.read_text()), row, identity, index, lengths[index])
                results.append(item); status['progress']=i+1; continue
            status.update(stage=suite['name']+':longest_dev_inference',packed_tokens=lengths[index])
            predictions = []; seconds = []
            for repeat in range(2):
                start=time.monotonic(); prediction=predictor(row); elapsed=time.monotonic()-start
                validate_prediction(row,prediction)
                if prediction['input_tokens']!=lengths[index]: raise ValueError('Token count mismatch')
                predictions.append(prediction);seconds.append(elapsed)
            item={'identity':identity,'suite':suite['name'],'index':index,'id':row['_meta']['id'],
                  'input_hash':objhash(row),'dev_records_tokenized':len(records),'packed_tokens':lengths[index],
                  'context':context,'predictions':predictions,'seconds':seconds,'chips':1,
                  'repeat_questions_per_second_per_chip':len(row['questions'])/seconds[1],
                  'reserved_memory_gib':torch.npu.memory_reserved()/2**30}
            envelope = {'payload': item, 'sha256': objhash(item)}
            validate_saved(envelope, row, identity, index, lengths[index])
            atomic(target,envelope);results.append(item)
            status.update(progress=i+1,questions_per_second_per_chip=item['repeat_questions_per_second_per_chip'],
                          reserved_gib=item['reserved_memory_gib'])
        verify_files(c)
        if sha(path)!=config_hash:raise ValueError('Config changed')
        atomic(out/'report.json',{'identity':identity,'test_metrics':False,'results':results,
               'scope':'Longest development records, native strict contexts; not complete test or hardware equivalence.'})
        outputs['report.json']=sha(out/'report.json');rc=0;status['stage']='completed'
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc);status['stage']='failed';raise
    finally:
        stop.set();thread.join()
        terminal={'rc':rc,'error':error,'identity':identity,'config_sha256':config_hash,'outputs':outputs,**status}
        atomic(out/'STATUS.json',terminal);atomic(out/'PROBE_COMPLETE.json',terminal)


if __name__=='__main__': main()
