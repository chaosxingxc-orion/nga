#!/usr/bin/env python3
"""Current-configuration, trained-state restart contract; no task evaluation.

Three uninterrupted replicas establish a local measured floor. A split run
must stay within it. Reset optimizer and skipped-update controls must fail.
This bounded test is not a claim of arbitrary-horizon trajectory equivalence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time


def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, value):
    tmp = p.with_suffix('.pending');tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n');tmp.replace(p)


def command(plan, out, count):
    cmd = list(plan['command'])
    cmd[cmd.index('--out')+1] = str(out)
    # Stop-after saves a complete checkpoint while preserving the full schedule.
    if '--stop-after' in cmd:
        cmd[cmd.index('--stop-after')+1] = str(count)
    else:
        cmd += ['--stop-after', str(count)]
    return cmd


def judge(loss_floor, weight_floor, resume_loss, resume_weight, controls):
    # Frozen numerical slack plus a replicate-derived tolerance, never fitted
    # to the resumed result. Controls test that the bar can reject corruption.
    if set(controls) != {'zero_moments', 'no_update'}:
        raise ValueError('both registered corruption controls are required')
    values = [loss_floor, weight_floor, resume_loss, resume_weight]
    for row in controls.values():
        values.extend((row['loss'], row['weight_relative_l2']))
    if not all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values):
        raise ValueError('contract distances must be finite and nonnegative')
    bars = {'loss': 1.5*loss_floor + 2.4e-7, 'weight_relative_l2':1.5*weight_floor + 1e-7}
    if not all(math.isfinite(x) for x in bars.values()):
        raise ValueError('contract tolerance overflow')
    resume_ok = resume_loss <= bars['loss'] and resume_weight <= bars['weight_relative_l2']
    rejected = {name: row['loss'] > bars['loss'] or row['weight_relative_l2'] > bars['weight_relative_l2']
                for name,row in controls.items()}
    return {'bars':bars,'resume_pass':resume_ok,'controls_rejected':rejected,
            'pass':resume_ok and bool(rejected) and all(rejected.values())}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);config=load(out/'CONTRACT.json');source=out/'SOURCE.pt'
    expected = {'steps':20, 'replicas':3, 'split':10, 'factor':1.5,
                'loss_slack':2.4e-7, 'weight_relative_l2_slack':1e-7,
                'test_read':False, 'scientific_acceptance':False}
    if any(config.get(k) != v or type(config.get(k)) is not type(v) for k,v in expected.items()):
        raise ValueError('frozen contract differs from implemented protocol')
    assert sha(source)==config['source_sha256']
    import torch
    state=torch.load(source,map_location='cpu',weights_only=False)
    start=state['step'];steps=20;split=10
    assert start==config['source_step'] and start+steps<3116
    plan=load(out/'SOURCE_PLAN.json')
    assert plan['arm']=='k1' and plan['seed']==2 and '--grad-ckpt' in plan['command']
    assert plan['command'][plan['command'].index('--micro-tokens')+1]=='12000'
    directories={name:out/name for name in ['replica_a','replica_b','replica_c','resumed','zero_moments','no_update']}
    stages=[]
    for name,root in directories.items():
        root.mkdir(exist_ok=True);(root/'ckpt').mkdir(exist_ok=True)
        init=root/'ckpt'/f'step_{start:06d}.pt'
        if not list((root/'ckpt').glob('step_*.pt')):
            if name=='zero_moments':
                broken=torch.load(source,map_location='cpu',weights_only=False)
                for item in broken['opt']['state'].values():
                    for key in ('exp_avg','exp_avg_sq'):
                        if key in item:item[key].zero_()
                torch.save(broken,init)
            else:shutil.copyfile(source,init)
        stages += [(name,split,0),(name,split,1)] if name=='resumed' else [(name,steps,0)]
    for index,(name,count,part) in enumerate(stages):
        receipt=out/f'STAGE-{index}.json'
        if receipt.exists():
            assert load(receipt)['exit_code']==0,'failed stage needs explicit repair'
            continue
        root=directories[name]
        # A stage killed after advancing but before its receipt is ambiguous;
        # do not silently advance it another count steps on relaunch.
        intent=out/f'STAGE-{index}-INTENT.json'
        assert not intent.exists(),'interrupted stage requires checkpoint inspection'
        cmd=command(plan,root,count)
        if name=='no_update':
            code="import runpy,sys,torch;torch.optim.AdamW.step=lambda self,*a,**k:None;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
            cmd=['python3','-P','-c',code]+cmd[2:]
        save(intent,{'command':cmd,'stage':index,'name':name})
        with (root/f'part{part}.log').open('ab') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
            while child.poll() is None:
                save(out/'heartbeat.json',{'utc_seconds':time.time(),'stage':index,'total_stages':len(stages),'name':name,'pid':child.pid})
                time.sleep(10)
        save(receipt,{'exit_code':child.returncode,'name':name,'stage':index})
        assert child.returncode==0,f'{name} failed'
    checkpoints,records={},{}
    for name,root in directories.items():
        checkpoints[name]=torch.load(root/'ckpt'/f'step_{start+steps:06d}.pt',map_location='cpu',weights_only=False)
        records[name]=[json.loads(x) for x in (root/'losses.jsonl').read_text().splitlines()]
        if not all(type(r.get(k)) in (int,float) and math.isfinite(r[k])
                   for r in records[name] for k in ('loss','grad_norm','lr')):
            raise ValueError(f'nonfinite training measurement in {name}')
        assert [r['step'] for r in records[name]]==list(range(start+1,start+steps+1))
        assert checkpoints[name]['step']==start+steps
    reference=records['replica_a']
    for name,rows in records.items():
        for a,b in zip(reference,rows):
            for key in ('step','epoch','lr','base_questions','examples','tokens','chunks'):
                assert a[key]==b[key],f'deterministic field mismatch {name} {key}'
    assert checkpoints['resumed']['sched']==checkpoints['replica_a']['sched']

    def delta(a,b):
        x,y=checkpoints[a]['lora'],checkpoints[b]['lora'];assert set(x)==set(y)
        assert all(torch.isfinite(t).all() for t in [*x.values(),*y.values()])
        num=sum(float((x[k].double()-y[k].double()).square().sum()) for k in x)
        den=sum(float(y[k].double().square().sum()) for k in y)
        return {'weight_relative_l2':(num/max(den,1e-60))**.5,
                'loss':sum(abs(r['loss']-s['loss']) for r,s in zip(records[a],records[b]))/steps}
    floor=[delta('replica_a','replica_b'),delta('replica_a','replica_c'),delta('replica_b','replica_c')]
    resumed=delta('resumed','replica_a');controls={n:delta(n,'replica_a') for n in ['zero_moments','no_update']}
    result=judge(max(x['loss'] for x in floor),max(x['weight_relative_l2'] for x in floor),resumed['loss'],resumed['weight_relative_l2'],controls)
    result.update(scope='20-step restart from trained K1 checkpoint; not arbitrary-horizon equivalence',
                  replicas=floor,resumed=resumed,controls=controls,source_sha256=sha(source),source_step=start,
                  scientific_acceptance=False,test_read=False)
    save(out/'CONTRACT_RESULT.json',result)
    save(out/'digest.json',result)
    return 0 if result['pass'] else 2


if __name__=='__main__':sys.exit(main())
