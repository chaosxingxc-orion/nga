#!/usr/bin/env python3
"""Run a pinned model-level numerical contract before paired throughput probes.

No test data or scientific acceptance. Persist each stage, logs and training
checkpoints. A completed numerical contract does not prove training-trajectory
equivalence; throughput results remain a bounded engineering observation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time


def atomic(path,value):
    tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n');tmp.replace(path)


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def frozen_identity(out):
    plan_path = out/'plan.json'
    plan = json.loads(plan_path.read_text())
    for filename, expected in plan['files'].items():
        # External admission evidence is validated by the launcher; the stage
        # rechecks the code/model/data/output dependencies mounted in its container.
        if plan.get('code') and not (filename.startswith(plan['code']+'/') or
                filename.startswith(plan['out']+'/') or filename.startswith(plan['model']+'/') or
                filename == plan['train_file']):
            continue
        if file_sha(filename) != expected:
            raise RuntimeError('frozen input changed: '+filename)
    return hashlib.sha256(plan_path.read_bytes()).hexdigest()


def stage(out,name,command):
    identity = frozen_identity(out)
    marker=out/(name+'.json')
    if marker.exists():
        value=json.loads(marker.read_text())
        if value['exit_code']!=0:raise RuntimeError('failed stage requires explicit repair: '+name)
        if value.get('command') != command or value.get('input_identity') != identity:
            raise RuntimeError('stage identity mismatch: '+name)
        return
    intent=out/(name+'-INTENT.json')
    if intent.exists():raise RuntimeError('ambiguous stage requires inspection: '+name)
    atomic(intent,{'command':command,'input_identity':identity})
    with (out/(name+'.log')).open('ab') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        while child.poll() is None:
            atomic(out/'heartbeat.json',{'utc_seconds':time.time(),'stage':name,'pid':child.pid})
            time.sleep(10)
    atomic(marker,{'exit_code':child.returncode,'command':command,'input_identity':identity})
    if child.returncode!=0:raise RuntimeError('stage failed: '+name)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out)
    stage(out,'model_contract',['python3','-P','/workspace/r3_hf32_off.py','/workspace/r3_fastref_e2e.py','--device','npu:0'])
    # Numerical admission precedes any throughput comparison. Same seed,
    # recipe, data and 3116-step schedule; stop after the same first 45 steps.
    for impl in ('ref','fast_ref'):
        root=out/impl
        cmd=['python3','-P','/workspace/r3_hf32_off.py','/workspace/train_r3.py','--out',str(root),'--arm','k1','--seed','2',
             '--model-path','/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base',
             '--kernel','ref','--micro-tokens','3000','--max-len','4096','--save-every','0',
             '--no-merge','--epochs','2','--total-steps','3116','--expect-pairs','186',
             '--gdn-impl',impl,'--stop-after','45']
        stage(out,impl,cmd)
    summaries={}
    for impl in ('ref','fast_ref'):
        root=out/impl;rows=[json.loads(x) for x in (root/'losses.jsonl').read_text().splitlines()]
        assert [r['step'] for r in rows]==list(range(1,46))
        assert all(math.isfinite(r[k]) for r in rows for k in ('loss','grad_norm','step_s','tokens','base_questions'))
        measured=rows[5:];seconds=sum(r['step_s'] for r in measured)
        assert seconds>=60 and all(r['step_s']>0 for r in measured),'insufficient measurement window'
        perf=json.loads((root/'perf.json').read_text())
        summaries[impl]={'warmup_steps':5,'measured_steps':40,'step_seconds':seconds,'chips':1,
                         'questions_per_second_per_chip':sum(r['base_questions'] for r in measured)/seconds,
                         'tokens_per_second_per_chip':sum(r['tokens'] for r in measured)/seconds,
                         'trainer_perf':perf}
    result={'schema':'r3-fastref-probe-v1','numerical_contract_exit':0,'measurements':summaries,
            'questions_rate_ratio':summaries['fast_ref']['questions_per_second_per_chip']/summaries['ref']['questions_per_second_per_chip'],
            'scientific_acceptance':False,'test_read':False,
            'hf32':False,'contract_lora_dropout':0.0,'throughput_lora_dropout':0.05,
            'contract_chunk_overhead':4000,'throughput_chunk_overhead':2000,
            'scope':'same-data 45-step engineering comparison; not complete trajectory equivalence or task gain'}
    atomic(out/'digest.json',result);atomic(out/'RESULT.json',result)


if __name__=='__main__':main()
