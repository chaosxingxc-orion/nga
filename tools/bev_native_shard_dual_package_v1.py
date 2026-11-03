"""Bind a registered shard template only after actual reference acceptance; never launch."""
import argparse,hashlib,json,types
from pathlib import Path

def need(x,s):
    if not x:raise ValueError(s)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def pin(x):need(type(x)is dict and set(x)=={'path','sha256'} and sha(x['path'])==x['sha256'],'pin differs');return read(x['path'])
def module(x):
    need(sha(x['path'])==x['sha256'],'source changed');m=types.ModuleType(Path(x['path']).stem);m.__file__=x['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def write(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n')
def prepare(template_ref):
    t=pin(template_ref);need(set(t)=={'schema','reference_plan','modules','package_path','baseline_attempt','mode','shards','chip','scientific_acceptance','test_read'},'template fields')
    need(t['schema']=='native-dev72-dual-shard-template-v1' and t['scientific_acceptance']is False and t['test_read']is False and t['mode']=='single_chip_two_sequential_shards' and t['shards']==[0,1] and all(type(x)is int for x in t['shards']),'template scope/layout')
    need(type(t['baseline_attempt'])is int and t['baseline_attempt']>0 and type(t['chip'])is int,'template types')
    for x in t['modules'].values():need(sha(x['path'])==x['sha256'],'template source changed')
    B=module(t['modules']['dual_contract']);bp,c,r,m,proto,L,N,P,A,items,up=B.reference(t['reference_plan'])
    need(t['chip']==bp['chip'],'physical reference lane differs');path=B.safe(t['package_path'])
    need(path.parent==Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs') and path.name!='' and path!=Path(bp['out']).parent,'fresh package location')
    pop=B.build(t['reference_plan'],t['modules']['contract'])
    return t,B,bp,c,r,m,pop

def bind(template_ref,review_ref,allocation_snapshot_ref,priority_refs,selection):
    t,B,bp,c,r,m,pop=prepare(template_ref);review=pin(review_ref)
    B.acceptance(review_ref,t['reference_plan'],review['evidence'],review['summary'],review['terminal'],t['baseline_attempt'])
    # Full baseline CPU lifecycle/closure is checked without querying hardware.
    U=module(bp['modules']['consumer']);U.lifecycle(bp,t['reference_plan']['path'],t['reference_plan']['sha256'],t['baseline_attempt'])
    e=pin(review['evidence'])
    for f,h in e['files'].items():need(sha(f)==h,'reference evidence changed')
    need(type(priority_refs)is list and priority_refs and type(selection)is str and selection.strip(),'priority rationale required')
    for x in priority_refs:pin(x)
    alloc=pin(allocation_snapshot_ref);need(type(alloc.get('pending_claims'))is list,'allocation pending claims required')
    a=t['baseline_attempt'];h=Path(bp['out'])/'host_attempts'/str(a)
    predecessor={'plan':t['reference_plan'],**{k:ref(h/f) for k,f in [('claim','CLAIM.json'),('release','RELEASE.json'),('launch_spec','LAUNCH_SPEC.json'),('launch_receipt','LAUNCH_RECEIPT.json')]}}
    release=pin(predecessor['release']);free=[x for x in alloc['free'] if x['chip']==t['chip']]
    need(len(free)==1 and free==[x for x in release['allocation_after']['free'] if x['chip']==t['chip']] and not any(x['chip']==t['chip'] for x in alloc['allocation']),'stale allocation generation')
    need(free[0]['previous_run']==bp['run'] and free[0]['release_evidence']==predecessor['release']['path'],'release free identity')
    root=Path(t['package_path']);need(not root.exists(),'package exists; never overwrite a frozen generation');root.mkdir()
    # Deployment uses immutable package-local copies, never mutable /home source paths.
    code=root/'code';code.mkdir();modules=dict(t['modules'])
    for k in ('runtime','host','resource','consumer','dual_contract'):
        source=Path(modules[k]['path']);raw=source.read_bytes();need(hashlib.sha256(raw).hexdigest()==modules[k]['sha256'],'source changed while freezing')
        target=code/source.name
        with target.open('xb') as f:f.write(raw)
        modules[k]=ref(target)
    def freeze(source,name):
        raw=Path(source['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==source['sha256'],'artifact changed while freezing')
        target=root/name
        with target.open('xb') as f:f.write(raw)
        return ref(target)
    review_source=review_ref;review_ref=freeze(review_ref,'BASELINE-RESULT-REVIEW.json')
    allocation_snapshot_ref=freeze(allocation_snapshot_ref,'RELEASE-ALLOCATION-SNAPSHOT.json')
    write(root/'POPULATION.json',pop)
    q=dict(schema='native-dev72-dual-shard-resource-v1',scientific_acceptance=False,allocation=bp['allocation'],writer_lock=bp['allocation']+'.lock',chip=t['chip'],run='r3_runs/'+root.name,free_entry=free[0],pending_claims=alloc['pending_claims'],attempt=a,predecessor=predecessor,priority_refs=priority_refs+[allocation_snapshot_ref],selection=selection)
    write(root/'RESOURCE-POLICY.json',q)
    d=dict(schema='native-dev72-dual-shard-execution-v1',mode=t['mode'],shards=t['shards'],modules=modules,population=ref(root/'POPULATION.json'),baseline_plan=t['reference_plan'],baseline_attempt=a,baseline_result_review=review_ref,baseline_evidence=review['evidence'],baseline_summary=review['summary'],baseline_terminal=review['terminal'],model=m['path'],model_files=m['files'],model_sha256=m['model_manifest_sha256'],contract_sha256=bp['contract_sha256'],tolerance=0,environment=bp['environment'],image=bp['image'],allocation=bp['allocation'],queue=ref(root/'RESOURCE-POLICY.json'),out=str(root/'output'),run=q['run'],chip=t['chip'],container='nga-native-dual-shard-'+root.name.replace('_','-'),host_name=bp['host_name'],poll_seconds=600,scientific_acceptance=False,test_read=False,cpu_python=bp['cpu_python'],cpu_environment=bp['cpu_environment'])
    A=module(d['modules']['runtime']);d['files']=A.closure(d,bp,c,r);path=root/'PLAN.json';d['mounts']=A.mounts(d,str(path));write(path,d)
    A.verify(str(path),sha(path),weights=False,host=True)
    result={'schema':'native-dev72-dual-shard-bound-v1','plan':ref(path),'template':template_ref,'reference_result':review_ref,'reference_result_source':review_source,'launch_authorized':False,'independent_package_review_pending':True,'device_free_preflight_pending':True,'resource_reserved':False,'scientific_acceptance':False,'test_read':False}
    write(root/'BOUND.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=('prepare','bind'));p.add_argument('--template',required=True);p.add_argument('--sha256',required=True);p.add_argument('--result-review');p.add_argument('--result-review-sha256');p.add_argument('--allocation-snapshot');p.add_argument('--allocation-snapshot-sha256');p.add_argument('--priorities');p.add_argument('--selection');a=p.parse_args();tr={'path':a.template,'sha256':a.sha256}
    if a.op=='prepare':
        t,B,bp,c,r,m,pop=prepare(tr);print(json.dumps({'status':'STRUCTURE_PREPARED_NOT_READY','model_sha256':m['model_manifest_sha256'],'reference_plan_sha256':t['reference_plan']['sha256'],'contract_sha256':bp['contract_sha256'],'items':72,'shards':[36,36],'last_source_i':pop['binding']['source_indices'][-1],'required_for_bind':['actual reference evidence,summary,CPU terminal','independent numerical receipt','physical reference release and exact resource generation'],'required_before_activation':['independent new package review/device-free preflight'],'npu_started':False,'launch_authorized':False}));return
    need(all((a.result_review,a.result_review_sha256,a.allocation_snapshot,a.allocation_snapshot_sha256,a.priorities,a.selection)),'bind requires actual evidence and priority inputs')
    result=bind(tr,{'path':a.result_review,'sha256':a.result_review_sha256},{'path':a.allocation_snapshot,'sha256':a.allocation_snapshot_sha256},read(a.priorities),a.selection);print(json.dumps(result))
if __name__=='__main__':main()
