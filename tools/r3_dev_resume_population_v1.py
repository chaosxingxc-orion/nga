"""CPU-only population inventory using the exact frozen DEV scoring closure."""
import hashlib, importlib, json, sys
from pathlib import Path

def build(spec):
    sys.dont_write_bytecode=True
    mounts={Path(x['destination']).name:Path(x['source']) for x in spec['code_mounts']}
    for base in mounts.values():
        for f in base.glob('*.py'):
            assert hashlib.sha256(f.read_bytes()).hexdigest()==spec['files'][str(f)]
    sys.path[:0]=[str(mounts['r3_code']),str(mounts['r0_code'])]
    C=importlib.import_module('core_r3')
    sys.path[:]=[x for x in sys.path if x!='/mnt/cephfs/xingchao/experiments/jev/r0_code']
    sys.path.insert(0,str(mounts['r0_code']))
    T=importlib.import_module('track_t_r3');RC=importlib.import_module('common')
    out={}
    def static(row):return {k:v for k,v in row.items() if k not in ('s','p','argmax','tie','m')}
    def checked(path):
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==spec['files'][str(path)]
    cmd=spec['command'];ks=cmd[cmd.index('--k-only')+1].split(',')
    for entry in ks:
        suite,split,kind=entry.split('/');assert split in ('dev','calibration')
        path=C.partition_path(suite,split,kind=='variants');checked(path)
        rows,_=C.load_partition(suite,split,variants=kind=='variants')
        rel=str(Path(C.k_readout_path('/population',suite,split,kind)).relative_to('/population'))
        out[rel]={C.kev_key(r):static(C.readout_row(r,[0.]*len(C.level_ids(r)))) for r in rows}
        assert len(out[rel])==len(rows)
    data=cmd[cmd.index('--data-root')+1]
    for task in ('T1','T2','T3'):
        for src in cmd[cmd.index('--track-t-sources')+1].split(','):
            path=RC.task_path(data,task,src)
            if task=='T3' and not Path(path).exists():continue
            checked(path);rows=T.records_needed(RC.load_records(path),T.CONFIGS['r3'])
            expected={r['key']:static(T.make_readout(r,[0.]*len(r['levels']))) for r in rows}
            assert len(expected)==len(rows)
            for role in T.MODEL_ROLES:out[f'trackt/readouts/{role}__{task}__{src}__shard0of1.jsonl']=expected
    return {'schema':'r3-dev-resume-population-v1','files':out,'expected_rows':sum(len(x) for x in out.values()),'test_read':False}
