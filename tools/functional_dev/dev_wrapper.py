"""Fixed RC1 Track K entry; no Track T or TEST. Uses frozen evaluator stores."""
import argparse, json, math, os, sys
from pathlib import Path

CLOSURE='/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code'
sys.path.insert(0,CLOSURE)

def checked(score):
    def call(rows, mode='full'):
        out=score(rows,mode)
        if len(out)!=len(rows): raise ValueError('scorer count mismatch')
        for row, values in zip(rows,out):
            if len(values)!=len(row['levels']) or not all(type(v) in (int,float) and math.isfinite(v) for v in values):
                raise ValueError('invalid score vector')
        return out
    for name in ('describe','token_stats','dedup_stats'):
        if hasattr(score,name): setattr(call,name,getattr(score,name))
    return call

def persist(p, obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(obj,f,indent=1,sort_keys=True,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p)

def run(a, full, evaluator):
    # No caller-controlled split, stage, precision, or Track T option.
    args=full.parse_full_args(['--model-path',a.model,'--adapter',a.adapter,'--out',a.out,
        '--arm','K1','--partitions','dev,calibration','--stages','k','--scorer','rightpad',
        '--dtype','float32','--no-hf32','--require-record-grade','--device','npu',
        '--round-dir',os.path.join(a.out,'identity-cache'),'--limit',str(a.limit)])
    # parse_full_args lacks the eval CLI's token-budget argument: set explicitly.
    args.token_budget=16384
    report=full.run_full(args,checked(evaluator.make_score_fn(args)))
    parts=report['track_k']['partitions']
    expected={'decision-v7/dev':1264,'decision-v7/calibration':1148,'transfer-v4/dev':656}
    for name,n in expected.items():
        if parts[name]['n'] != (min(n,a.limit) if a.limit else n): raise ValueError('population mismatch: '+name)
    persist(Path(a.out)/'report.json',report)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--adapter',required=True);p.add_argument('--out',required=True)
    p.add_argument('--smoke',action='store_true',help='fixed first 2 DEV/calibration rows; separate output')
    a=p.parse_args();a.limit=2 if a.smoke else 0
    import full_eval_r3,eval_r3
    run(a,full_eval_r3,eval_r3)
if __name__=='__main__': main()
