"""Original DEV72 shard contract: numeric contract and reference host identity differ.
CPU-only construction/admission. No claim, model load, or launch authority.
"""
import hashlib,json,types
from pathlib import Path

def need(ok,why):
    if not ok:raise ValueError(why)
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p
def sha(p):
    with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def pinned(r):
    need(type(r)is dict and set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'pin changed');return read(r['path'])
def module(r):
    need(sha(r['path'])==r['sha256'],'module changed');m=types.ModuleType(Path(r['path']).stem);m.__file__=r['path'];exec(compile(safe(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def reference(refplan):
    d=pinned(refplan);need(d['schema']=='native-dev72-reference-execution-v1' and d['test_read']is False and d['scientific_acceptance']is False,'reference schema/scope')
    C=module(d['modules']['contract']);c=pinned(d['config']);r=pinned(d['registry']);C.validate(c,r)
    m=r['model'][c['model']];p=r['protocol'][c['protocol']]
    need(d['model_files']==m['files'] and d['host_name']=='k8s-node1','reference model/host')
    need(type(d['chip'])is int and d['chip']==r['resources'][c['resources']]['chip'],'reference chip')
    need(d['out']==c['output'] and d['run']=='r3_runs/'+c['run_id'],'reference run identity')
    for x in (d['config'],d['registry'],*d['modules'].values()):need(d['files'].get(x['path'])==x['sha256'],'reference source not bound')
    L=module(d['modules']['loader']);N=module(d['modules']['native']);P=module(d['modules']['probe']);A=module(d['modules']['runtime'])
    need(d['image']==L.IMAGE and d['environment']==L.ENV and d['poll_seconds']==600,'reference environment')
    expect={m['path']:m['model_manifest_sha256'],'protocol':p,'inputs':c['inputs'],'native':d['modules']['native'],'loader':d['modules']['loader'],'probe':d['modules']['probe']}
    need(d['contract_sha256']==N.digest(expect),'numeric contract identity')
    with safe(c['inputs']['path']).open() as f:items=[C.strict_json(x) for x in f]
    P.validate_items(items,N,r['population']['ordered_input_sha256'])
    up=pinned(d['modules']['upstream_binding'])
    return d,c,r,m,p,L,N,P,A,items,up

def build(refplan,shard_contract):
    d,c,r,m,p,L,N,P,A,items,up=reference(refplan);C=module(shard_contract)
    indices=[x['i'] for x in items];identities=[C.request_identity(x,i,indices) for i,x in enumerate(items)]
    b=dict(parent_population=r['population']['source_plan'],inputs={k:c['inputs'][k] for k in ('path','sha256')},model_sha256=m['model_manifest_sha256'],contract_sha256=d['contract_sha256'],source_protocol_binding_sha256=r['population']['source_plan']['sha256'],source_execution=refplan,reference_plan_sha256=refplan['sha256'],reference_config=d['config'],reference_registry=d['registry'],global_count=72,ordered_inputs_sha256=N.digest(items),global_request_identities_sha256=C.digest(identities),shard_count=2,strategy='contiguous_equal_count',execution_authorized=False,scientific_acceptance=False,candidate_test_authority=False,source_kind='native_dev72',source_indices=indices,test_read=False)
    shards=[]
    for sid in (0,1):
        ids=list(range(sid*36,(sid+1)*36));shards.append(dict(b,schema='bev-native-shard-manifest-v1',shard_id=sid,global_ordinals=ids,ordinals_sha256=C.digest(ids),assigned_count=36,input_tokens=sum(len(items[i]['input_ids']) for i in ids),assigned_request_identities_sha256=C.digest([identities[i] for i in ids])))
    population=dict(schema='bev-native-shard-population-v1',binding=b,shards=shards,scientific_acceptance=False,execution_authorized=False,numerical_equivalence_verified=False)
    C.validate(population);return population

def acceptance(receipt_ref,refplan,evidence_ref,summary_ref,terminal_ref,attempt,read_artifacts=True):
    """Independent result acceptance is required; producer's boolean is insufficient."""
    bp,c,r,m,p,L,N,P,A,items,up=reference(refplan);v=pinned(receipt_ref)
    need(v.get('schema')=='native-dev72-independent-result-v1' and v.get('verdict')=='PASS','independent result receipt required')
    need(v.get('plan')==refplan and type(v.get('attempt'))is int and v['attempt']==attempt and type(attempt)is int and attempt>0,'independent result generation')
    need(v.get('contract_sha256')==bp['contract_sha256'] and v.get('model_sha256')==m['model_manifest_sha256'],'independent numeric/model identity')
    need(v.get('evidence')==evidence_ref and v.get('summary')==summary_ref and v.get('terminal')==terminal_ref,'independent artifact pins')
    need(type(v.get('items'))is int and v['items']==72 and type(v.get('raw_operand_comparisons'))is int and v['raw_operand_comparisons']==144 and v.get('zero_tolerance')is True and v.get('numerical_equivalence_verified')is True,'independent equality scope')
    need(v.get('scientific_acceptance')is False and v.get('test_read')is False and type(v.get('reviewer'))is str and bool(v['reviewer'].strip()),'independent authority scope')
    root=Path(bp['out'])/'cpu'/str(attempt)
    for x,name in ((evidence_ref,'REFERENCE-EVIDENCE.json'),(summary_ref,'summary.json'),(terminal_ref,'EXIT.json')):need(x['path']==str(root/name),'reference artifact path')
    if not read_artifacts:return v
    e=pinned(evidence_ref);s=pinned(summary_ref);t=pinned(terminal_ref)
    need(e.get('schema')=='native-dev72-reference-evidence-v1' and e.get('plan')==refplan and e.get('contract_sha256')==bp['contract_sha256'] and e.get('model_sha256')==m['model_manifest_sha256'],'reference evidence dual identity')
    need(type(e.get('attempt'))is int and e['attempt']==attempt and e.get('scientific_acceptance')is False and e.get('test_read')is False,'evidence scope')
    need(e.get('source_population')==r['population']['source_plan'] and e.get('source_inputs')==r['population']['source_inputs'] and e.get('source_indices')==[x['i'] for x in items] and e.get('ordered_input_sha256')==[N.digest(x) for x in items],'evidence population')
    need(s.get('schema')=='native-dev72-reference-comparison-v1' and s.get('plan_sha256')==refplan['sha256'] and s.get('contract_sha256')==bp['contract_sha256'] and s.get('model_sha256')==m['model_manifest_sha256'],'reference summary identity')
    for x in (s,t):need(type(x.get('attempt'))is int and x['attempt']==attempt and x.get('scientific_acceptance')is False,'CPU generation')
    need(type(t.get('exit_code'))is int and t['exit_code']==0 and t.get('plan_sha256')==refplan['sha256'],'CPU terminal')
    need(s.get('items')==72 and type(s['items'])is int and s.get('raw_operand_comparisons')==144 and type(s['raw_operand_comparisons'])is int and s.get('counts')=={'reference':72,'reference_repeat':72,'adapter':72} and s.get('zero_tolerance')is True and s.get('lifecycle_verified')is True and s.get('numerical_equivalence_observed')is True and s.get('test_read')is False,'CPU numerical scope')
    expected={str(Path(bp['out'])/'items'/variant/N.digest(item)/f) for variant in ('reference','reference_repeat','adapter') for item in items for f in ('COMMITTED.json','operands.npz','result.json')}
    need(type(e.get('files'))is dict and expected<=set(e['files']),'reference operand closure')
    return v
