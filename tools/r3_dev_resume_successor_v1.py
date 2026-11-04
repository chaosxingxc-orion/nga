"""Resume a formal DEV with unchanged data identity and exact failed-release lineage."""
import hashlib,json,types
from pathlib import Path
CORE_SHA='a322ee71c9bc6a7e8238f69fd57b420b3c2fee421701c1fd7bfaa2304ea295f7'
def load(p,pin):
    p=Path(p);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise RuntimeError('source changed')
    m=types.ModuleType(p.stem);m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

def binding(p):
    C=_core;g=p['successor_guard'];C.require(g['schema']=='r3-dev-resume-guard-v1' and g['controller']==str(Path(__file__).resolve()) and g['identity_mode']=='sha256_raw','guard differs')
    C.require(p['adapter']==p['resource_adapter'] and p['files']==p['tools'],'resource alias differs')
    for f,h in p['tools'].items():C.require(C.sha(f)==h,'tool changed')
    source=C.read(C.pinned(g['source_execution']));old=C.read(C.pinned(g['source_spec']));spec=C.read(p['spec']);C.require(C.sha(p['spec'])==p['spec_sha256'],'spec changed')
    C.require(source['spec']==g['source_spec']['path'] and source['spec_sha256']==g['source_spec']['sha256'],'source spec binding differs')
    C.normalized_spec(spec,old,p['out'],source['out'])
    C.require(source['chip']==p['chip']==2 and source['test_read']is False and source['scientific_acceptance']is False,'source scope differs')
    C.require(spec['training_variant']['formal_role_identity']['role']=='diffchip_s2','formal role differs')
    launcher=C.module({'path':source['launcher'],'sha256':source['tools'][source['launcher']]});launcher.verify(g['source_execution']['path'],g['source_execution']['sha256'])
    core=C.module(g['training_evidence']);return core,source

def predecessor(p,resource):
    C=_core;core,source=binding(p);g=p['successor_guard'];root=Path(source['out']);refs=g['physical_release']
    paths={'claim':root/'attempts/1/CLAIM.json','release':root/'attempts/1/RELEASE.json','terminal':root/'ENGINEERING_EVAL_EXIT.json','attempt_terminal':root/'attempts/1/EXIT.json','supervisor_done':root/'attempts/1/SUPERVISOR_DONE.json','receipt':root/'attempts/1/LAUNCH_RECEIPT.json','spec':root/'attempts/1/LAUNCH_SPEC.json','supervisor':root/'SUPERVISOR_RECEIPT.json'}
    C.require(set(refs)==set(paths),'source evidence set differs')
    for k,v in paths.items():C.require(C.pinned(refs[k])==v,'source evidence path differs')
    ds={k:C.read(v['path']) for k,v in refs.items()};cl=ds['claim'];rel=ds['release'];end=ds['terminal'];local=ds['attempt_terminal'];done=ds['supervisor_done'];receipt=ds['receipt']
    C.require(sorted(x.name for x in (root/'attempts').iterdir())==['1'],'source attempt inventory differs')
    C.require(not core.process_matches(ds['supervisor']),'source supervisor live')
    C.require(end==local and end['source']=='retained-container-exit' and end['runtime_terminal_present']is False and end['exit_code']==done['exit_code']==rel['exit_code']==1 and done['source']=='retained-container-reconciliation','failure provenance differs')
    C.require(end['release_sha256']==refs['release']['sha256'] and rel['claim_sha256']==refs['claim']['sha256'] and end['raw_plan_sha256']==g['source_execution']['sha256'],'failure binding differs')
    name=source['container']+'-a1';a=resource.docker_inspect(name)
    C.require(a and a['Id']==receipt['id']==rel['container_id']==end['container_id']==done['container_id'] and a['Image']==receipt['image'] and receipt['sha256']==g['source_execution']['sha256'],'retained identity differs')
    C.require(a['State']['Status']=='exited' and a['State']['Running']is False and type(a['State']['ExitCode'])is int and a['State']['ExitCode']==1 and a['RestartCount']==0,'retained failure differs')
    C.require(a['State']['StartedAt']==rel['container_started_at'] and a['State']['FinishedAt']==rel['container_finished_at'] and a['Config']['Cmd']==ds['spec']['command'][ds['spec']['command'].index(a['Image'])+1:],'generation command differs')
    C.require(rel['run']==cl['run']==source['run'] and rel['chip']==cl['chip']==p['chip'] and rel['scientific_acceptance']is False,'release scope differs')
    free=[x for x in rel['allocation_after']['free'] if x['chip']==p['chip']];C.require(len(free)==1 and free[0]['previous_run']==source['run'] and free[0]['release_evidence']==str(paths['release']),'release free lineage differs')
    C.require(not resource.live_chip_conflict(p['chip'],None),'device conflict')
    return dict(status='failed_dev_physically_released',run=source['run'],container_id=a['Id'],free_entry=free[0],exit_code=1,source_execution=g['source_execution'],release=refs['release'],scientific_acceptance=False)

def configure(c):
    c.__file__=str(Path(__file__).resolve());c.binding=binding;c.predecessor=predecessor;return c
_core=configure(load(Path(__file__).with_name('core_formal_dev_successor.py'),CORE_SHA))
verify=_core.verify;authorize=_core.authorize;claim_precondition=_core.claim_precondition;tick=_core.tick;watch=_core.watch;main=_core.main
if __name__=='__main__':main()
