"""Configuration-driven complete BEV dataset population, version one.

The reviewed config pins the population; build authenticates every mapped source
item and rendered request. No default-dataset counts are inherited. Numerical
protocol, model loader, length admission and lifecycle remain unchanged.

Host validation uses only the standard library. Model imports occur only in run.
This new capability does not widen any v1 long-DEV or frozen panel schema.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import time
import traceback
import types
from pathlib import Path


def require(ok, why):
    if not ok: raise ValueError(why)


def read(path):
    def pairs(values):
        result = {}
        for k, v in values:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    def finite(v):
        if type(v) is float: require(math.isfinite(v), 'nonfinite JSON')
        elif type(v) is dict:
            for child in v.values(): finite(child)
        elif type(v) is list:
            for child in v: finite(child)
    finite(value)
    return value


def safe(path):
    require(type(path) is str and path.startswith('/') and '..' not in path.split('/'), 'unsafe path')
    p = Path(path)
    require(str(p) == path and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(str(path)).open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''): h.update(block)
    return h.hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def module(ref):
    require(set(ref) == {'path', 'sha256'} and sha(ref['path']) == ref['sha256'], 'module identity differs')
    m = types.ModuleType(Path(ref['path']).stem)
    m.__file__ = ref['path']
    exec(compile(Path(m.__file__).read_bytes(), m.__file__, 'exec'), m.__dict__)
    return m


def put(path, obj):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.pending')
    with tmp.open('x') as f:
        json.dump(obj, f, sort_keys=True, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    fd = os.open(p.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def ref_check(ref, files):
    require(type(ref) is dict and set(ref) == {'path', 'sha256'}, 'reference shape differs')
    require(files.get(ref['path']) == ref['sha256'], 'reference outside closure')
    safe(ref['path'])


MODULES = {'runtime', 'host', 'resource', 'resource_base', 'loader', 'native', 'panel', 'protocol', 'consumer'}
CONFIG_FIELDS = {'schema', 'run_id', 'output', 'container', 'host_name', 'host_environment', 'host_python',
                 'cpu_python', 'cpu_environment', 'model', 'population', 'protocol', 'modules', 'upstream',
                 'resources', 'image', 'environment', 'files', 'scope', 'test_read', 'scientific_acceptance',
                 'candidate_test_authority', 'candidate_selection_allowed', 'poll_seconds'}


def config_validate(c):
    require(type(c) is dict and set(c) == CONFIG_FIELDS and c['schema'] == 'native-dataset-panel-config-v1', 'config schema differs')
    require(type(c['run_id']) is str and type(c['container']) is str, 'run identity type differs')
    require(c['scope'] == 'public_fixed_base_test' and c['test_read'] is True, 'public fixed base scope required')
    for k in ('scientific_acceptance', 'candidate_test_authority', 'candidate_selection_allowed'):
        require(c[k] is False, 'candidate/scientific authority forbidden')
    require(type(c['poll_seconds']) is int and c['poll_seconds'] == 600, 'poll differs')
    require(re.fullmatch('[a-z0-9][a-z0-9_-]*', c['run_id']) and re.fullmatch('[a-z0-9][a-z0-9_-]*', c['container']), 'run/container identity differs')
    require(safe(c['output']).name == 'output' and Path(c['output']).parent.name == c['run_id'], 'output identity differs')
    require(type(c['host_name']) is str and c['host_name'], 'host missing')
    for k in ('host_python', 'cpu_python'): safe(c[k])
    for k in ('environment', 'host_environment', 'cpu_environment'):
        require(type(c[k]) is dict and all(type(a) is str and type(b) is str for a,b in c[k].items()), 'environment differs')
    m = c['model']; require(set(m) == {'path', 'files', 'manifest_sha256', 'family', 'name', 'kind'}, 'model fields differ')
    safe(m['path']); require(m['kind'] == 'fixed_base' and type(m['name']) is str and m['name'], 'fixed base required')
    require(type(m['files']) is dict and m['files'], 'model manifest missing')
    for p,h in m['files'].items():
        require(safe(p).is_relative_to(m['path']) and re.fullmatch('[0-9a-f]{64}',h), 'model reference differs')
    require(m['manifest_sha256'] == digest(m['files']), 'model manifest digest differs')
    proto = c['protocol']
    require(set(proto) == {'id', 'family', 'max_length', 'batch_size', 'dtype', 'hf32', 'vocabulary', 'adapter'}, 'protocol fields differ')
    require(proto == dict(id='native-full-label-panel-v2', family=m['family'], max_length=8192, batch_size=1,
                          dtype='float32', hf32=False, vocabulary=248320, adapter='transformers_full_labels'), 'unsupported registered protocol')
    require(m['family']=='qwen3.5_decoder', 'loader family unsupported')
    require(type(proto['max_length']) is int and type(proto['batch_size']) is int and proto['hf32'] is False and type(proto['vocabulary']) is int, 'protocol types differ')
    resources = c['resources']
    require(set(resources) == {'chip', 'allocation', 'policy'} and type(resources['chip']) is int and resources['chip'] >= 0, 'resource fields differ')
    safe(resources['allocation'])
    require(type(c['files']) is dict and c['files'], 'files missing')
    require(set(c['modules']) == MODULES, 'module registry differs')
    for path,pin in c['files'].items():
        safe(path); require(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin), 'dependency pin differs')
    require(not set(c['model']['files']) & set(c['files']), 'weights duplicated in execution closure')
    for ref in c['modules'].values(): ref_check(ref, c['files'])
    ref_check(resources['policy'], c['files'])
    require(set(c['upstream'])=={'root','files'} and set(c['upstream']['files'])=={'question.py','readout.py','tacit.py'}, 'upstream registry differs')
    safe(c['upstream']['root'])
    for name,ref in c['upstream']['files'].items():
        require(ref['path']==str(Path(c['upstream']['root'])/'anyjev'/name), 'upstream location differs')
    for ref in c['upstream']['files'].values(): ref_check(ref, c['files'])
    pop = c['population']
    require(set(pop) == {'requests','items','gold','source','contract','count','source_rows','semantic_duplicates','kinds','ordered_inputs_sha256','contract_sha256','protocol_binding_sha256'}, 'population fields differ')
    for key in ('requests','items','gold','source','contract'): ref_check(pop[key], c['files'])
    require(type(pop['count']) is int and pop['count'] > 0 and type(pop['source_rows']) is int and pop['source_rows'] > 0 and type(pop['semantic_duplicates']) is int and 0 <= pop['semantic_duplicates'] < pop['count'], 'registered population differs')
    require(type(pop['kinds']) is dict and set(pop['kinds']) == {'choice','yes_no','score'} and all(type(v) is int and v >= 0 for v in pop['kinds'].values()) and sum(pop['kinds'].values()) == pop['count'], 'kind population differs')
    for key in ('ordered_inputs_sha256','contract_sha256','protocol_binding_sha256'):
        require(type(pop[key]) is str and re.fullmatch('[0-9a-f]{64}',pop[key]), 'population pin differs')
    require(type(c['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}', c['image']), 'image differs')
    return c


def mounts(d, path):
    model = d['model']; population = d['population']
    # Gold/source are CPU-only; inference receives requests and executable closure.
    excluded = {population[k]['path'] for k in ('items','gold','source','contract')}
    result = [dict(source=model, destination=model, readonly=True)]
    result += [dict(source=p,destination=p,readonly=True) for p in sorted(d['files']) if p not in excluded and not Path(p).is_relative_to(model)]
    result += [dict(source=str(path),destination=str(path),readonly=True), dict(source=d['out'],destination=d['out'],readonly=False)]
    result += [dict(source=p,destination=p,readonly=True) for p in ('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info')]
    # Exclusion applies to the final mount set, including fixed system binds
    # and any directory in the executable closure, not only model/output.
    ancestors = [Path(m['source']) for m in result]
    require(all(not Path(x).is_relative_to(a) for x in excluded for a in ancestors), 'CPU-only path under inference mount ancestor')
    return result


def build(config_path, config_pin, plan_path):
    require(sha(config_path) == config_pin, 'config changed')
    c = config_validate(read(config_path)); p = safe(str(plan_path))
    require(Path(c['modules']['consumer']['path']).with_name('bev_native_dataset_panel_v1.py')==Path(c['modules']['runtime']['path']), 'consumer/runtime package siblings differ')
    require(not p.exists() and p.name=='PLAN.json' and p.parent==Path(c['output']).parent, 'plan already exists or location differs')
    for source,h in c['files'].items(): require(sha(source)==h,'configuration dependency changed')
    validate_population(c)
    d = dict(schema='native-dataset-panel-execution-v1', config={'path':str(config_path),'sha256':config_pin},
             modules=c['modules'], files=dict(c['files'], **{str(config_path):config_pin}),
             model=c['model']['path'], model_files=c['model']['files'], model_sha256=c['model']['manifest_sha256'],
             population=c['population'], protocol=c['protocol'], upstream=c['upstream'],
             chip=c['resources']['chip'], allocation=c['resources']['allocation'], queue=c['resources']['policy'],
             out=c['output'], run='r3_runs/'+c['run_id'], container=c['container'], host_name=c['host_name'],
             host_python=c['host_python'], host_environment=c['host_environment'], cpu_python=c['cpu_python'], cpu_environment=c['cpu_environment'],
             image=c['image'], environment=c['environment'], scope=c['scope'],test_read=True,scientific_acceptance=False,
             candidate_test_authority=False,candidate_selection_allowed=False,poll_seconds=600)
    d['mounts'] = mounts(d,p)
    put(p,d)
    return d


def validate_population(c):
    """CPU preparation authenticates the complete source and rerenders every item.

    This is called once by build, before the final plan can be reviewed. It does
    not load a model or inspect resources. Duplicate semantic requests stay as
    distinct ordinals, exactly as the registered upstream population defines.
    """
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    X=module(c['modules']['panel']);N=module(c['modules']['native']);P=module(c['modules']['protocol']);L=module(c['modules']['loader'])
    pop=c['population'];raw=pq.read_table(pop['source']['path']).to_pylist()
    require(len(raw)==pop['source_rows'],'source rows differ')
    items=P.bev_items(raw);P.validate_items(items);saved=X.rows(pop['items']['path']);gold=X.rows(pop['gold']['path']);requests=X.rows(pop['requests']['path'])
    require(len(items)==len(saved)==len(gold)==len(requests)==pop['count'] and X.exact(items,saved),'mapped source differs')
    require({kind:sum(i['kind']==kind for i in items) for kind in pop['kinds']}==pop['kinds'],'source kinds differ')
    semantic=[N.digest({k:v for k,v in i.items() if k not in ('i','qid','y')}) for i in items]
    require(len(semantic)-len(set(semantic))==pop['semantic_duplicates'],'semantic duplicate count differs')
    tok=AutoTokenizer.from_pretrained(c['model']['path'],local_files_only=True,trust_remote_code=False);tok.padding_side='left'
    ref=N.reference(Path(c['upstream']['root']))
    for i,(item,req,g) in enumerate(zip(items,requests,gold)):
        X.item_check(req,i,8192)
        require(X.exact(g,dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item))),'gold identity differs')
        require(X.exact(N.prepare_request({k:v for k,v in item.items() if k!='y'},tok,ref),req),'rendered population differs')
        if i%5000==0:print(json.dumps({'stage':'population_preparing','completed':i,'total':len(items)}),flush=True)
    require(N.digest(requests)==pop['ordered_inputs_sha256'],'ordered requests differ')
    binding=N.digest(dict(native=c['modules']['native']['sha256'],runner=c['modules']['runtime']['sha256'],loader=c['modules']['loader']['sha256'],protocol=c['modules']['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=L.LOADER,image=c['image'],model_sha256=c['model']['manifest_sha256']))
    require(binding==pop['protocol_binding_sha256'],'protocol binding differs')
    expected=P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=c['model']['manifest_sha256'],runtime_protocol_sha256=binding)
    require(X.exact(read(pop['contract']['path']),expected) and P.sha256_value(expected)==pop['contract_sha256'],'population contract differs')


def verify(path,pin,model_files=True, cpu=False):
    require(sha(path)==pin,'plan changed');d=read(path)
    require(d['schema']=='native-dataset-panel-execution-v1' and d['scope']=='public_fixed_base_test' and d['test_read'] is True,'scope differs')
    require(all(d[k] is False for k in ('scientific_acceptance','candidate_test_authority','candidate_selection_allowed')),'authority differs')
    require(d['modules']['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'runtime differs')
    require(sha(d['config']['path'])==d['config']['sha256'],'config changed');c=config_validate(read(d['config']['path']))
    # Compare against the exact deterministic projection without creating a second plan.
    expected_keys={'schema','config','modules','files','model','model_files','model_sha256','population','protocol','upstream','chip','allocation','queue','out','run','container','host_name','host_python','host_environment','cpu_python','cpu_environment','image','environment','scope','test_read','scientific_acceptance','candidate_test_authority','candidate_selection_allowed','poll_seconds','mounts'}
    require(set(d)==expected_keys,'plan fields differ')
    for key in ('modules','population','protocol','upstream','container','host_name','host_python','host_environment','cpu_python','cpu_environment','image','environment','scope','test_read','scientific_acceptance','candidate_test_authority','candidate_selection_allowed','poll_seconds'):
        require(type(d[key]) is type(c[key]) and d[key]==c[key],'config projection differs: '+key)
    require(d['model']==c['model']['path'] and d['model_files']==c['model']['files'] and d['model_sha256']==c['model']['manifest_sha256'],'model projection differs')
    require(type(d['chip']) is int and d['chip']==c['resources']['chip'] and d['allocation']==c['resources']['allocation'] and d['queue']==c['resources']['policy'],'resource projection differs')
    require(d['out']==c['output'] and d['run']=='r3_runs/'+c['run_id'],'run projection differs')
    require(d['files']==dict(c['files'],**{d['config']['path']:d['config']['sha256']}) and d['mounts']==mounts(d,path),'closure differs')
    excluded=set() if cpu else {d['population'][k]['path'] for k in ('items','gold','source','contract')}
    for p,h in d['files'].items():
        if p not in excluded: require(sha(p)==h,'source changed')
    if model_files:
        actual={str(p):sha(p) for p in safe(d['model']).rglob('*') if p.is_file()}
        require(actual==d['model_files'],'model bytes differ')
    require(Path(path).name=='PLAN.json' and Path(path).parent==Path(d['out']).parent,'plan location differs')
    # Loader has no model imports at module import time. Numerical libraries remain runtime-only.
    L=module(d['modules']['loader'])
    require(d['environment']==L.ENV and d['image']==L.IMAGE,'loader environment/image differs')
    return d


def plan_legacy_view(d):
    c=read(d['config']['path']);pop=d['population'];L=module(d['modules']['loader']);N=module(d['modules']['native'])
    binding=N.digest(dict(native=d['modules']['native']['sha256'],runner=d['modules']['runtime']['sha256'],loader=d['modules']['loader']['sha256'],protocol=d['modules']['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=L.LOADER,image=d['image'],model_sha256=d['model_sha256']))
    require(binding==pop['protocol_binding_sha256'],'protocol binding differs')
    # Numerical identity is source-bound config: full contract stays CPU-only.
    result={**d, 'runtime':d['modules']['runtime'],'host':d['modules']['host'],'native':d['modules']['native'],
            'loader_module':d['modules']['loader'],'inputs':pop['requests'],'image_sha256':d['image'],
            'upstream_root':d['upstream']['root'],'upstream_files':d['upstream']['files'],'count':pop['count'],
            'max_length':8192,'batch_size':1,'loader':L.LOADER,'ordered_inputs_sha256':pop['ordered_inputs_sha256'],
            'contract_sha256':pop['contract_sha256'],'protocol_binding_sha256':binding}
    return result,L,N


def admission(d,r,path,pin,attempt):
    gate=r['long_dev_acceptance'];require(sha(gate['path'])==gate['sha256'],'long DEV review changed');g=read(gate['path'])
    require(r.get('hashes',{}).get(gate['path'])==gate['sha256'],'unreviewed long DEV acceptance')
    if g.get('schema')=='native-panel-long-dev-admission-v2':
        require(g.get('verdict')=='PASS' and g.get('scientific_acceptance') is False and g.get('test_read') is False,'long DEV gate differs')
        for k,v in {'model_sha256':d['model_sha256'],'native_sha256':d['modules']['native']['sha256'],'loader_sha256':d['modules']['loader']['sha256'],'image':d['image'],'protocol':d['protocol']}.items():require(g.get(k)==v,'long DEV protocol differs')
        require(g.get('scope')=='synthetic_long_dev' and g.get('candidate_test_authority') is False,'long DEV authority differs')
        require(g.get('independent_operands_verified') is True and type(g.get('forwards')) is int and g['forwards']==9,'long DEV operands not accepted')
    else:
        # Authenticate the actual older accepted plan; never rewrite its review
        # into the newer schema or infer qualification from an accuracy result.
        old_ref=r['long_dev_source_plan'];require(sha(old_ref['path'])==old_ref['sha256']==g.get('plan_sha256') and r['hashes'].get(old_ref['path'])==old_ref['sha256'],'older long DEV plan changed')
        old=read(old_ref['path'])
        require(old.get('schema')=='bev-native-panel-host-v1' and old.get('scope')=='synthetic_long_dev' and old.get('test_read') is False and old.get('scientific_acceptance') is False,'older qualification scope')
        require(g.get('verdict')=='PASS' and g.get('status')=='PASS_EXACT_SYNTHETIC_LONG_DEV' and g.get('scientific_acceptance') is False and g.get('test_read') is False and g.get('all_tensors_and_restricted_arithmetic_exact') is True and g.get('lifecycle_verified') is True,'older qualification acceptance')
        require(g.get('lengths')==[4097,5296,8192] and type(g.get('operands')) is int and g['operands']==9 and type(g.get('full_vocabulary_width')) is int and g['full_vocabulary_width']==248320,'older qualification operands')
        require(old['model_sha256']==g['model_sha256']==d['model_sha256'] and old['model_files']==d['model_files'] and old['native']['sha256']==g['native_sha256']==d['modules']['native']['sha256'] and old['loader_module']['sha256']==d['modules']['loader']['sha256'],'older model or implementation differs')
        require(old['image_sha256']==g['image_sha256']==d['image'] and old['environment']==d['environment'] and old['max_length']==g['max_length']==8192 and old['batch_size']==1 and type(old['batch_size']) is int,'older execution protocol differs')
        L=module(d['modules']['loader']);require(old['loader']==L.LOADER,'older loader semantics differ')
        require(old['protocol_binding_sha256']==g['protocol_binding_sha256'] and g.get('evidence',{}).get(old_ref['path'])==old_ref['sha256'],'older acceptance lineage differs')
        for key in ('native','loader_module'):
            ref=old[key];require(g['evidence'].get(ref['path'])==ref['sha256'] and sha(ref['path'])==ref['sha256'],'older accepted implementation changed')
    require(r.get('cpu_command')==cpu_command(d,path,pin,attempt),'CPU command differs')


def cpu_command(d,path,pin,attempt):
    return [d['cpu_python'],'-B','-P',d['modules']['consumer']['path'],'--plan',str(path),'--sha256',pin,'--attempt',str(attempt)]


def start_cpu(d,path,pin,attempt):
    h=Path(d['out'])/'host_attempts'/str(attempt);end=read(h/'EXIT.json');release=read(h/'RELEASE.json');claim=read(h/'CLAIM.json')
    require(type(end.get('exit_code')) is int and end['exit_code']==0 and end.get('runner_terminal_matches') is True,'host not successful')
    require(type(release.get('exit_code')) is int and release['exit_code']==0 and release.get('scientific_acceptance') is False and release.get('schema')=='r3-resource-release-v1' and claim.get('schema')=='r3-resource-claim-v1','successful release required')
    require(type(release.get('chip')) is int and release['chip']==d['chip'] and type(claim.get('chip')) is int and claim['chip']==d['chip'],'release device differs')
    require(release.get('claim_sha256')==sha(h/'CLAIM.json') and release.get('container_id')==end.get('container_id') and release.get('run')==d['run'] and claim.get('run')==d['run'],'release differs')
    root=Path(d['out'])/'cpu';root.mkdir(exist_ok=True)
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);out=root/str(attempt);out.mkdir(exist_ok=False)
        cmd=cpu_command(d,path,pin,attempt);put(out/'RELAUNCH.json',{'command':cmd,'automatic_retry':False})
        with (out/'runtime.log').open('ab') as log:
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,**d['cpu_environment']))
        put(out/'SERVICE.json',{'pid':proc.pid,'command':cmd,'plan_sha256':pin})


def run(path,pin,attempt):
    require(sha(path)==pin and type(attempt) is int and attempt>0,'attempt differs');d=read(path);root=safe(d['out']);root.mkdir(parents=True,exist_ok=True)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);a=root/'attempts'/str(attempt);a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
        def event(stage,**extra):print(json.dumps(dict(stage=stage,utc_seconds=time.time(),attempt=attempt,**extra)),flush=True)
        def heartbeat():
            while not stop.wait(30):put(a/'heartbeat.json',dict(state='runtime_alive',utc_seconds=time.time(),attempt=attempt))
        t=threading.Thread(target=heartbeat,daemon=True);t.start()
        try:
            event('startup');verify(path,pin);view,L,N=plan_legacy_view(d);X=module(d['modules']['panel'])
            items=X.rows(d['population']['requests']['path']);require(len(items)==d['population']['count'] and N.digest(items)==d['population']['ordered_inputs_sha256'],'population differs')
            for name,h in N.PINS.items():require(d['upstream']['files'][name]['sha256']==h,'upstream source differs')
            for previous in range(1,attempt):
                e=read(root/'attempts'/str(previous)/'EXIT.json');require(type(e.get('exit_code')) is int and e['exit_code']!=0 and e.get('plan_sha256')==pin and type(e.get('attempt')) is int and e['attempt']==previous and e.get('scientific_acceptance') is False,'resume generation differs')
            for i,item in enumerate(items):X.item_check(item,i,8192)
            model,tok,torch,T,TN=L.load_model({'model':d['model']});event('model_ready');ref=N.reference(Path(d['upstream']['root']))
            def metadata():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,dtype='float32',hf32=False,torch=torch.__version__,torch_npu=TN.__version__,transformers=T.__version__)
            def collect(item):
                with torch.inference_mode():return N.read_model_batch(model,[item],tok,mode='transformers_full_labels',contract_sha256=view['contract_sha256'],prepared_pins=[N.digest(item)],max_length=8192,ref=ref)[0]
            result=X.execute(view,N,items,root,attempt,collect,metadata);result.update(forwards_per_new_item=1,plan_sha256=pin,attempt=attempt)
            put(a/'report.json',result);rc=0;event('complete',completed=result['completed'])
        except BaseException:event('failed');traceback.print_exc();raise
        finally:stop.set();t.join(2);put(a/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,scientific_acceptance=False,test_read=True,utc_seconds=time.time()))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('op',choices=['build','verify','run']);a.add_argument('--config');a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,default=1);v=a.parse_args()
    if v.op=='build':build(v.config,v.sha256,v.plan)
    elif v.op=='verify':verify(v.plan,v.sha256);print('PANEL_V2_VERIFIED')
    else:run(v.plan,v.sha256,v.attempt)
