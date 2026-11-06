"""Fixed RC1 Track K inference and offline CPU statistics; separate processes."""
import argparse, hashlib, json, math, os, sys, time
from pathlib import Path
CLOSURE='/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code'
sys.path.insert(0,CLOSURE)
# Match run_track_k's calibration-first consumer and per-partition call order.
PLAN=[('decision-v7','calibration'),('decision-v7','dev'),('transfer-v4','dev')]
GROUPS=[f'{s}/{p}/{k}' for s,p in PLAN for k in (('clean',) if p=='calibration' else ('clean','variants','question_only','empty_input'))]

def save(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()

def checked(score):
    def call(rows, mode='full'):
        values=score(rows,mode)
        if len(values)!=len(rows):raise ValueError('scorer count mismatch')
        for row, v in zip(rows,values):
            if len(v)!=len(row['levels']) or not all(type(x) in (int,float) and math.isfinite(x) for x in v):raise ValueError('invalid score vector')
        return values
    for name in ('describe','token_stats','dedup_stats'):
        if hasattr(score,name):setattr(call,name,getattr(score,name))
    return call

class Offline:
    def __init__(self, desc):self.desc=desc
    def describe(self):return self.desc
    def __call__(self,*args,**kwargs):raise RuntimeError('offline scorer forbidden: missing readout')

def arguments(a, full, stage):
    argv=['--model-path',a.model,'--adapter',a.adapter,'--out',a.out,'--arm','K1',
          '--partitions','dev,calibration','--stages',stage,'--scorer','rightpad',
          '--dtype','float32','--no-hf32','--require-record-grade','--device',('npu' if stage=='k_score' else 'cpu'),
          '--round-dir',os.path.join(a.out,'identity-cache'),'--limit',str(a.limit)]
    if stage=='k_score':argv += ['--k-only',','.join(GROUPS)]
    args=full.parse_full_args(argv);args.token_budget=16384
    return args

def populations(full):
    import core_r3 as C
    result={}
    for s,p in PLAN:
        clean,_=C.load_partition(s,p)
        var,_=C.load_partition(s,p,variants=True) if p!='calibration' else ([],None)
        clean,var=full.limit_partition(clean,var,full_limit[0])
        for kind in (('clean',) if p=='calibration' else ('clean','variants','question_only','empty_input')):
            result[f'{s}/{p}/{kind}']=var if kind=='variants' else clean
    return result
# Temporary single-call context; process is single-threaded and independent per job.
full_limit=[0]

def verify(a,full,desc,expected=None):
    import core_r3 as C, admissible_store_r3 as AS, selection_evidence_r3 as SE
    identity=json.loads((Path(a.out)/'RUN_IDENTITY.json').read_text())['model_sha256']
    full_limit[0]=a.limit
    populations_=populations(full); evidence={}
    for group, rows in populations_.items():
        s,p,k=group.split('/'); path=C.k_readout_path(a.out,s,p,k); receipt=AS.receipt_path(path)
        if not os.path.isfile(path) or not os.path.isfile(receipt):raise RuntimeError('missing store or receipt: '+group)
        # Read only: unlike VerifiedStore(recover=True), never truncate interrupted data.
        read=AS.check_receipt(path,identity,desc,recover=False)
        SE.validate_population(read,rows,C.kev_key)
        evidence[group]={'store_sha256':sha(path),'receipt_sha256':sha(receipt),'rows':len(read)}
    if expected is not None and evidence!=expected:raise RuntimeError('store evidence differs from inference handoff')
    return evidence

def run(a,full,evaluator):
    receipt=Path(a.out)/'INFERENCE-READY.json'; start=time.monotonic()
    if a.phase=='infer':
        # A previous success is invalidated before any resume writes.
        receipt.unlink(missing_ok=True)
        args=arguments(a,full,'k_score'); scorer=checked(evaluator.make_score_fn(args));desc=scorer.describe()
        result=full.run_full(args,scorer)
        if 'track_k' in result:raise RuntimeError('inference unexpectedly calculated statistics')
        evidence=verify(a,full,desc)
        save(receipt,{'version':1,'model':a.model,'adapter':a.adapter,'out':a.out,'limit':a.limit,'groups':GROUPS,'descriptor':desc,'stores':evidence,'inference_header':result['header'],'inference_elapsed_seconds':time.monotonic()-start})
        return result
    handoff=json.loads(receipt.read_text())
    for key,value in [('version',1),('model',a.model),('adapter',a.adapter),('out',a.out),('limit',a.limit),('groups',GROUPS)]:
        if handoff.get(key)!=value:raise RuntimeError('inference handoff mismatch: '+key)
    verify(a,full,handoff['descriptor'],handoff['stores'])
    args=arguments(a,full,'k'); result=full.run_full(args,Offline(handoff['descriptor']))
    parts=result['track_k']['partitions']
    if not a.limit:
        for name,n in {'decision-v7/dev':1264,'decision-v7/calibration':1148,'transfer-v4/dev':656}.items():
            if parts[name]['n']!=n:raise ValueError('population mismatch: '+name)
    result['header']['phase_separation']={'inference_receipt_sha256':sha(receipt),'inference_header':handoff['inference_header'],'cpu_score_elapsed_seconds':time.monotonic()-start,'note':'Scorer descriptor is from inference; throughput and dedup counts are per process.'}
    save(Path(a.out)/'report.json',result)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',required=True,choices=['infer','score']);p.add_argument('--model',required=True);p.add_argument('--adapter',required=True);p.add_argument('--out',required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();a.limit=2 if a.smoke else 0
    import full_eval_r3,eval_r3
    run(a,full_eval_r3,eval_r3)
if __name__=='__main__':main()
