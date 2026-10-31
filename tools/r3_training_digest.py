#!/usr/bin/env python3
"""CPU engineering summary from structured trainer records, never a quality verdict."""
import argparse
import json
import math
from pathlib import Path


def summarize(root):
    plan=json.loads((root/'plan.json').read_text())
    terminal=root/'TRAIN_EXIT.json'
    exit_record=json.loads(terminal.read_text()) if terminal.exists() else None
    records=[];incomplete_tail=False
    raw=(root/'losses.jsonl').read_bytes() if (root/'losses.jsonl').exists() else b''
    for index,line in enumerate(raw.splitlines(keepends=True)):
        if not line.endswith(b'\n'):
            incomplete_tail=True;break
        records.append(json.loads(line))
    issues=[]
    steps=[r['step'] for r in records]
    if steps != list(range(1,len(steps)+1)):issues.append('noncontiguous_or_duplicate_steps')
    for r in records:
        if not all(isinstance(r.get(k),(int,float)) and math.isfinite(r[k]) for k in ('loss','grad_norm','step_s','tokens','base_questions')):
            issues.append('nonfinite_or_missing_training_measurement');break
        if r['step_s']<=0 or r['tokens']<=0 or r['base_questions']<=0:
            issues.append('nonpositive_work_measurement');break
    expected=plan.get('stop_after') or 3116
    if exit_record and exit_record['exit_code']==0 and (not steps or steps[-1]!=expected):
        issues.append('successful_exit_without_expected_final_step')
    if exit_record and incomplete_tail:issues.append('terminal_with_partial_record')
    measured=records[5:]
    seconds=sum(x['step_s'] for x in measured)
    rates=None
    if measured and seconds>0 and not issues:
        rates={'measured_steps':len(measured),'warmup_steps_excluded':5,'step_seconds':seconds,
               'tokens_per_second_per_chip':sum(x['tokens'] for x in measured)/seconds,
               'questions_per_second_per_chip':sum(x['base_questions'] for x in measured)/seconds,
               'token_unit': 'logical prompt-plus-option tokens (repeated prompt counted per option); not physically forwarded tokens' if plan.get('k2_impl')=='shared' else 'trainer-recorded tokens; padding excluded',
               'mature_window': len(measured)>=10 and seconds>=60,
               'chips':1,'measurement_scope':'sum of trainer step times, excludes startup/checkpoint overhead'}
    return {'run':str(root),'arm':plan.get('arm','k1'),'model':Path(plan['model']).name,
            'completed_steps':steps[-1] if steps else 0,'invocation_target':expected,
            'schedule_steps':3116,'terminal':exit_record,'issues':issues,'partial_tail_ignored':incomplete_tail,
            'throughput':rates,'scientific_acceptance':False,'test_read':False,
            'scope':'engineering finite-value/progress/throughput check only; not loss improvement or task-quality evidence'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',action='append',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=[summarize(Path(x)) for x in a.run]
    with Path(a.output).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    for x in result:print(json.dumps(x))
