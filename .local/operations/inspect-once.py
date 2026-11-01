"""Local bounded routine inspection; shared 600s admission, never launches jobs."""
import collections
import datetime as dt
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess

R=Path('/home/xingchao/workspace/nga');B=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
policy=R/'.local/NPU-MONITORING.json'
now=dt.datetime.now(dt.timezone.utc)
with policy.with_suffix('.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    d=json.loads(policy.read_text())
    due=dt.datetime.fromisoformat(d['next_routine_inspection_utc'])
    if now<due:
        print('NOT_DUE '+due.isoformat());raise SystemExit(0)
    d.update(last_routine_inspection_utc=now.isoformat(),next_routine_inspection_utc=(now+dt.timedelta(seconds=600)).isoformat())
    temp=policy.with_suffix('.pending');temp.write_text(json.dumps(d,indent=2)+'\n');temp.replace(policy)

out=R/'.local/reports'/('inspection-'+now.strftime('%Y%m%dT%H%M%S')+'.json')
evidence={'utc':now.isoformat(),'next_routine_utc':d['next_routine_inspection_utc'],'errors':{},'scientific_acceptance':False}
def module(name):
    p=R/'tools'/(name+'.py');s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def section(name,fn):
    try:evidence[name]=fn()
    except Exception as e:evidence['errors'][name]=type(e).__name__+': '+str(e)[:300]
section('docker',lambda:subprocess.run(['ssh','-o','ConnectTimeout=15','npu','docker ps --format "{{json .}}"'],capture_output=True,text=True,check=True,timeout=35).stdout.splitlines())
section('cpu_process',lambda:subprocess.run(['ps','-p','2207331','-o','pid=,stat=,args='],capture_output=True,text=True,check=True).stdout.strip())
def train():
    m=module('r3_training_digest')
    roots=[B/'engineering_k2_08b_20261031_v1'/seed for seed in ('seed2','seed3')]
    roots += [B/name/seed for name in ('engineering_k1_4b_full_20261031_v1','engineering_k1_9b_full_20261031_v1') for seed in ('seed2','seed3') if any((B/name/seed/'attempts').glob('*/LAUNCH_RECEIPT.json'))]
    return [m.summarize(root) for root in roots]
section('training',train)
def progress():
    m=module('r3_inference_progress');p=m.population(R/'.local/reviews/inference-workload-20261031.json','671b93f94c055c2dc4c5c013bc372f9489a066f93a7ddb048762487704af9bd2')
    roots=[B/'posttrain_execution_queue_20261031_v3/evaluations'/f'{name}-s{seed}'/'results' for name in ('engineering_k1_08b_20261031_v2','engineering_k1_2b_full_20261031_v1','engineering_k2_shared_full_20261031_v1') for seed in (2,3)]
    roots += [B/'k0_current_rescore_20261031_v1'/size/'results' for size in ('08b','2b') if (B/'k0_current_rescore_20261031_v1'/size/'results').is_dir()]
    return [m.summarize(root,p) for root in roots]
section('inference',progress)
section('watchdog',lambda:(B/'combined_inference_watchdog_20261031_v1/digest.md').read_text().splitlines()[:2])
def readiness():
    """Expose only the bounded formal-admission state in routine digests.

    The readiness file is produced by the read-only audit.  Do not surface
    evidence payloads, logs, or any field that could be mistaken for
    scientific acceptance.
    """
    p=B/'formal_control_readiness_20261031_v1.json'
    d=json.loads(p.read_text())
    checks=d.get('checks',{})
    return {
        'status': d.get('status'),
        'scientific_acceptance': d.get('scientific_acceptance',False),
        'test_read': d.get('test_read',False),
        'missing': d.get('missing',[]),
        'checks': {k:v.get('status') for k,v in checks.items() if isinstance(v,dict)},
    }
section('formal_readiness',readiness)
for name in ('cpu_selection_queue_20261031_v10','posttrain_execution_queue_20261031_v3'):
    section(name,lambda name=name:json.loads((B/name/'digest.json').read_text()))
section('prefix_successor',lambda:json.loads((B/'prefix_current_successor_20261031_v4/digest.json').read_text()))
section('scoring_recovery_successor',lambda:json.loads((B/'dev_scoring_recovery_successor_20261031_v1/digest.json').read_text()))
for control_queue in ('control_training_successor_20261031_v1','control_posttrain_queue_20261031_v1','control_cpu_reports_20261031_v1','pt_r0_posttrain_queue_20261031_v1','pt_r0_cpu_reports_20261031_v2','instruct_k0_successor_20261031_v1','control_resume_successor_20261031_v1','control_resume_cpu_queue_20261031_v1'):
    section(control_queue,lambda name=control_queue:json.loads((B/name/'digest.json').read_text()))
out.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
print('UTC '+now.isoformat()+' evidence='+str(out.relative_to(R)))
print('Coverage: row-K2, launched 4B/9B training, first-wave inference and existing 0.8B/2B K0 results; not all queued successors.')
if 'docker' in evidence:
    rows=[json.loads(x) for x in evidence['docker']];train=[x for x in rows if x['Names'].startswith('nga-r3-eng-engineering_')];ev=[x for x in rows if x['Names'].startswith('nga-r3-eng-eval-')]
    print(f'Actual Docker running: training={len(train)} inference={len(ev)}')
for x in evidence.get('training',[]):print(Path(x['run']).parent.name+'/'+Path(x['run']).name+': '+str(x['completed_steps'])+'/3116 issues='+str(x['issues'])+' terminal='+str(x['terminal']))
for x in evidence.get('inference',[]):
    name=Path(x['run']).parent.name.replace('engineering_','').replace('_20261031_v1','').replace('_20261031_v2','')
    print(f"{name}: {x['receipt_reported_rows']}/{x['expected_rows']} ({x['record_percent']:.1f}%) flags={x['flags']}")
for name in ('cpu_selection_queue_20261031_v10','posttrain_execution_queue_20261031_v3'):
    if name in evidence:
        states=evidence[name]['jobs'];print(name+': '+str(dict(collections.Counter(x['status'] for x in states.values()))))
        for key,value in states.items():
            if value['status'] not in ('waiting_reports','waiting_inference','waiting_training','supervisor_live','done'):print('EVENT '+key+' '+str(value)[:350])
for line in evidence.get('watchdog',[]):print(line[:600])
print('errors='+str(evidence['errors'])+' next='+d['next_routine_inspection_utc'])
