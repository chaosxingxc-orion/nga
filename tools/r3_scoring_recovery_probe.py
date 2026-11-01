"""Engineering-only real scorer recovery on an explicitly pinned dev sample.

Run reference, interrupt, resume in separate retained processes/containers.
Interrupt deliberately SIGKILLs after a durable chunk; only the supervisor may
record its actual exit. No test ticket, FINAL, training gain or acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<22),b''):h.update(b)
    return h.hexdigest()


def module(name,path):
    # Execute the source checked by the frozen plan, never adjacent bytecode.
    import types
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe helper source')
    raw=path.read_bytes();m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(raw,str(path),'exec',dont_inherit=True),m.__dict__)
    return m


def validate_origin(m, root):
    require(Path(m.__file__).resolve()==root/'r3_code'/(m.__name__+'.py'),
            'runtime module outside closure: '+m.__name__)


def protocol_counts(plan):
    counts = {'r3-dev-scoring-recovery-v1': (4, 2),
              'r3-dev-scoring-recovery-v2': (32, 32)}
    require(plan.get('schema') in counts, 'probe schema differs')
    per_suite, chunk = counts[plan['schema']]
    require(plan['protocol'] == {'records_per_suite': per_suite, 'chunk': chunk,
            'mode': 'rightpad', 'dtype': 'float32', 'hf32': False,
            'token_budget': 16384, 'max_abs_nats': 1e-3}, 'protocol differs')
    return per_suite, chunk


def sample_rows(sources, core, per_suite=4):
    require(set(sources)=={'decision-v7','transfer-v4'},'source suite population differs')
    rows=[]
    for suite in ('decision-v7','transfer-v4'):
        source=sources[suite];path=Path(source['path'])
        require(path.name=='dev.jsonl' and path.parent.name==suite,'only native dev allowed')
        require(sha(path)==source['sha256'],'development source changed')
        population=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        require(source['indices']==list(range(per_suite)),'sample selection differs')
        require(len(population)>=per_suite,'development population too small')
        rows.extend(population[i] for i in source['indices'])
    require(len({core.kev_key(r) for r in rows})==2*per_suite,'cross-suite sample keys overlap')
    return rows


def validate_scores(rows, scores):
    require(isinstance(scores,list) and len(scores)==len(rows),'score batch population differs')
    for row, values in zip(rows,scores):
        require(isinstance(values,(list,tuple)) and len(values)==len(row['levels']) and len(values)>0,
                'score candidate population differs')
        require(all(type(v) in (int,float) and math.isfinite(v) for v in values),'nonfinite or invalid score')


def validate_readouts(rows, readouts, core):
    require([r.get('k') for r in readouts]==[core.kev_key(r) for r in rows],
            'readout population or order differs')
    validate_scores(rows,[r.get('s') for r in readouts])
    for row, readout in zip(rows,readouts):
        expected=core.readout_row(row,readout['s'])
        require(all(readout.get(k)==v for k,v in expected.items()),'readout metadata or decision differs')
        require(type(readout.get('argmax')) is int and type(readout.get('tie')) is bool,
                'readout decision type differs')


def compare_readouts(rows, reference, resumed, core):
    validate_readouts(rows,reference,core);validate_readouts(rows,resumed,core)
    delta=max(abs(a-b) for x,y in zip(reference,resumed) for a,b in zip(x['s'],y['s']))
    require(delta<=1e-3,'resumed numerical deviation exceeds fixed tolerance')
    require(all(x['argmax']==y['argmax'] and x['tie']==y['tie'] for x,y in zip(reference,resumed)),
            'resumed decision differs')
    return delta


def validate_interruption(marker, pin, rows, readouts, prefix, core, chunk=2):
    validate_readouts(rows[:chunk],readouts,core)
    require(marker=={'committed':chunk,'keys':sorted(core.kev_key(r) for r in rows[:chunk]),
                    'plan_sha256':pin,'prefix_sha256':hashlib.sha256(prefix).hexdigest()},
            'interruption marker binding differs')


def run(plan_path,pin,phase):
    require(sha(plan_path)==pin,'probe plan pin differs')
    p=json.loads(Path(plan_path).read_text())
    require(p['test_read'] is False
            and p['scientific_acceptance'] is False,'probe scope differs')
    require(phase in ('reference','interrupt','resume'),'unknown phase')
    require(p['probe_sha256']==sha(__file__),'probe implementation differs')
    per_suite, chunk = protocol_counts(p)
    root=Path(p['closure']['root'])
    CLOS=module('probe_closure',root/'r3_code/r3_final_closure.py')
    CLOS.verify(root,p['closure']['sha256'],True)
    M=module('probe_inventory',root/'r3_code/r3_model_inventory.py')
    require(sha(p['base_inventory']['path'])==p['base_inventory']['sha256'],'inventory artifact differs')
    inv=json.loads(Path(p['base_inventory']['path']).read_text())
    M.verify(p['model'],inv['inventory'],inv['inventory_sha256'])
    require(sha(p['adapter_inventory']['path'])==p['adapter_inventory']['sha256'],'adapter inventory artifact differs')
    adapter_inv=json.loads(Path(p['adapter_inventory']['path']).read_text())
    M.verify(p['adapter'],adapter_inv['inventory'],adapter_inv['inventory_sha256'])
    import core_r3 as C
    import eval_r3 as EVAL
    import full_eval_r3 as FULL
    import admissible_store_r3 as AS
    import provenance_r3 as PV
    import testlock_r3 as TL
    for m in (C,EVAL,FULL,AS,PV,TL):validate_origin(m,root)
    rows=sample_rows(p['sources'],C,per_suite)
    out=Path(p['out']);out.mkdir(parents=True,exist_ok=True)
    work=out/('reference' if phase=='reference' else 'interrupted');work.mkdir(exist_ok=True)
    file=str(work/'readouts.jsonl')
    require(not (work/'DONE.json').exists(),'completed phase cannot rescore')
    require(phase=='resume' or not Path(file).exists(),'new phase already has readouts')
    require(phase!='resume' or (work/'INTERRUPT_READY.json').exists(),'resume lacks committed interruption evidence')
    args=FULL.parse_full_args(['--model-path',p['model'],'--adapter',p['adapter'],'--out',str(work),'--scorer','rightpad',
        '--dtype','float32','--no-hf32','--require-record-grade','--device','npu',
        '--partitions','dev','--stages','k']);args.token_budget=16384
    scorer=EVAL.make_score_fn(args)
    identity=TL.model_identity(p['model'],adapter=p['adapter'],round_dir=str(work))
    descriptor=dict(scorer.describe())
    # v1 records its smaller caller explicitly. v2 preserves the production
    # descriptor and requires its advertised chunk size to match execution.
    if chunk == 2:
        descriptor['score_chunk_questions']=2
        descriptor['layout']='right-padded candidates, token budget 16384, engineering recovery calls of 2 questions'
    else:
        require(descriptor.get('score_chunk_questions') == chunk, 'production caller differs')
    descriptor['engineering_recovery_probe']=True
    seen=[]
    def recorded(batch,mode):
        keys=[C.kev_key(r) for r in batch];seen.extend(keys)
        with (work/('calls.'+phase+'.jsonl')).open('a') as f:
            f.write(json.dumps(keys)+'\n');f.flush();os.fsync(f.fileno())
        scores=scorer(batch,mode)
        validate_scores(batch,scores)
        return scores
    store=AS.VerifiedStore(str(work),file,identity['sha256'],descriptor)
    prefix=Path(file).read_bytes();previous=set(store.done)
    atomic=module('probe_driver',root/'r3_code/r3_final_driver.py').atomic
    def progress(done,total):
        store.commit()
        print(json.dumps({'utc':C.utc_now(),'heartbeat':True,'phase':phase,'done':done,'total':total}),flush=True)
        if phase=='interrupt':
            require(done==chunk and len(store.done)==chunk,'interruption boundary differs')
            atomic(work/'INTERRUPT_READY.json',{'committed':done,'keys':sorted(store.done),'plan_sha256':pin,
                                               'prefix_sha256':sha(file)})
            os.kill(os.getpid(),signal.SIGKILL)
    try:
        if phase=='resume':
            validate_interruption(json.loads((work/'INTERRUPT_READY.json').read_text()),pin,rows,
                                  list(store.done.values()),prefix,C,chunk)
        C.score_resumable(recorded,rows,C.kev_key,lambda r,s:PV.stamp(C.readout_row(r,s),identity['sha256']),
                          store,chunk=chunk,progress=progress)
    finally:store.close()
    readouts=AS.read_verified(str(work),file,identity['sha256'],descriptor)
    validate_readouts(rows,readouts,C)
    require(seen==[C.kev_key(r) for r in rows if C.kev_key(r) not in previous],
            'new scoring population differs')
    require(not previous.intersection(seen),'committed records rescored')
    require(Path(file).read_bytes().startswith(prefix),'committed bytes changed')
    result={'plan_sha256':pin,'phase':phase,'rows':len(readouts),'newly_scored':len(seen),'test_read':False,'scientific_acceptance':False}
    if phase=='resume':
        reference=AS.read_verified(str(out/'reference'),str(out/'reference/readouts.jsonl'),identity['sha256'],descriptor)
        delta=compare_readouts(rows,reference,readouts,C)
        result.update(max_abs_nats=delta,committed_reused=len(previous),status='ENGINEERING_RECOVERY_PASS')
    M.verify(p['model'],inv['inventory'],inv['inventory_sha256'])
    M.verify(p['adapter'],adapter_inv['inventory'],adapter_inv['inventory_sha256'])
    atomic(work/'DONE.json',result)
    print(json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    parser.add_argument('--sha256',required=True);parser.add_argument('--phase',required=True,choices=('reference','interrupt','resume'))
    a=parser.parse_args();run(a.plan,a.sha256,a.phase)
