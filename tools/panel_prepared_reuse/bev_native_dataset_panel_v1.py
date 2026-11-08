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
    require(set(ref) == {'path', 'sha256'}, 'module reference differs')
    source = safe(ref['path']).read_bytes()
    require(hashlib.sha256(source).hexdigest() == ref['sha256'], 'module identity differs')
    m = types.ModuleType(Path(ref['path']).stem)
    m.__file__ = ref['path']
    exec(compile(source, ref['path'], 'exec'), m.__dict__)
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
                 'resources', 'numeric', 'image', 'environment', 'files', 'scope', 'test_read', 'scientific_acceptance',
                 'candidate_test_authority', 'candidate_selection_allowed', 'poll_seconds', 'cpu_only_paths'}


def config_validate(c):
    require(type(c) is dict and set(c) == CONFIG_FIELDS and c['schema'] == 'native-dataset-panel-config-v1', 'config schema differs')
    require(type(c['run_id']) is str and type(c['container']) is str, 'run identity type differs')
    require(c['scope'] == 'public_fixed_instruct_test' and c['test_read'] is True, 'public fixed base scope required')
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
    safe(m['path']); require(m['kind'] == 'fixed_instruct' and type(m['name']) is str and m['name'], 'fixed base required')
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
    require(set(resources) == {'chip', 'allocation', 'policy'} and ((type(resources['chip']) is int and resources['chip'] in (4,5) and type(resources['policy']) is dict) or (resources['chip'] is None and resources['policy'] is None)), 'resource fields differ')
    require(c['numeric'] == {'model':'2b','admission_sha256':'73589e71c7d463b2833e6559db4b4dc4d4a71a7fd1e40aaea3f9b770971807ce'}, 'numeric identity differs')
    safe(resources['allocation'])
    require(type(c['files']) is dict and c['files'], 'files missing')
    require(set(c['modules']) == MODULES, 'module registry differs')
    for path,pin in c['files'].items():
        safe(path); require(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin), 'dependency pin differs')
    require(type(c['cpu_only_paths']) is list and c['cpu_only_paths'] and len(set(c['cpu_only_paths'])) == len(c['cpu_only_paths']), 'CPU-only registry differs')
    require(all(type(p) is str and p in c['files'] for p in c['cpu_only_paths']), 'CPU-only operand unbound')
    require({c['population'][k]['path'] for k in ('items','gold','source','contract')} <= set(c['cpu_only_paths']), 'CPU-only population incomplete')
    require(c['modules']['consumer']['path'] in c['cpu_only_paths'], 'CPU consumer must be excluded')
    require(not set(c['model']['files']) & set(c['files']), 'weights duplicated in execution closure')
    for ref in c['modules'].values(): ref_check(ref, c['files'])
    if resources['policy'] is not None: ref_check(resources['policy'], c['files'])
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
    excluded = set(d['cpu_only_paths'])
    result = [dict(source=model, destination=model, readonly=True)]
    result += [dict(source=p,destination=p,readonly=True) for p in sorted(d['files']) if p not in excluded and not Path(p).is_relative_to(model)]
    result += [dict(source=str(path),destination=str(path),readonly=True), dict(source=d['out'],destination=d['out'],readonly=False)]
    result += [dict(source=p,destination=p,readonly=True) for p in ('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info')]
    # Exclusion applies to the final mount set, including fixed system binds
    # and any directory in the executable closure, not only model/output.
    ancestors = [Path(m['source']) for m in result]
    require(all(not Path(x).is_relative_to(a) for x in excluded for a in ancestors), 'CPU-only path under inference mount ancestor')
    return result


def build(config_path, config_pin, plan_path, cpu_prepare=False, *, prepared_plan=None, prepared_pin=None):
    require((prepared_plan is None) == (prepared_pin is None), 'prepared plan and pin required together')
    require(not (cpu_prepare and prepared_plan is not None), 'prepared reuse requires final build')
    require(sha(config_path) == config_pin, 'config changed')
    c = config_validate(read(config_path)); p = safe(str(plan_path))
    require(Path(c['modules']['consumer']['path']).with_name('bev_native_dataset_panel_v1.py')==Path(c['modules']['runtime']['path']), 'consumer/runtime package siblings differ')
    require(not p.exists() and p.name==('CPU-PREPARE.json' if cpu_prepare else 'PLAN.json') and p.parent==Path(c['output']).parent, 'plan already exists or location differs')
    require((c['resources']['chip'] is None) == cpu_prepare, 'resource binding required for executable plan')
    for source,h in c['files'].items(): require(sha(source)==h,'configuration dependency changed')
    if prepared_plan is None:
        validate_population(c)
    else:
        previous = verify(prepared_plan, prepared_pin, cpu=True, prepare=True)
        original = config_validate(read(previous['config']['path']))
        policy_ref = c['resources']['policy']
        policy = read(policy_ref['path'])
        refs = [policy_ref, policy['predecessor']['claim'], policy['predecessor']['release']]
        for ref in refs:
            ref_check(ref, c['files'])
        paths = {ref['path'] for ref in refs}
        require(len(paths) == 3 and not paths.intersection(original['files']), 'resource files differ')
        require(set(c['files']) - set(original['files']) == paths, 'resource file additions differ')
        normalized = dict(c, files={k:v for k,v in c['files'].items() if k not in paths},
                          resources=dict(c['resources'], chip=None, policy=None))
        require(json.dumps(normalized, sort_keys=True, allow_nan=False) ==
                json.dumps(original, sort_keys=True, allow_nan=False), 'prepared config differs')
    d = dict(schema='native-dataset-panel-execution-v1', config={'path':str(config_path),'sha256':config_pin},
             modules=c['modules'], files=dict(c['files'], **{str(config_path):config_pin}),
             model=c['model']['path'], model_files=c['model']['files'], model_sha256=c['model']['manifest_sha256'],
             population=c['population'], protocol=c['protocol'], upstream=c['upstream'],
             chip=c['resources']['chip'], allocation=c['resources']['allocation'], queue=c['resources']['policy'],
             out=c['output'], run='r3_runs/'+c['run_id'], container=c['container'], host_name=c['host_name'],
             host_python=c['host_python'], host_environment=c['host_environment'], cpu_python=c['cpu_python'], cpu_environment=c['cpu_environment'],
             image=c['image'], environment=c['environment'], cpu_only_paths=c['cpu_only_paths'], scope=c['scope'],test_read=True,scientific_acceptance=False,
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


def verify(path,pin,cpu=False,prepare=False):
    require(sha(path)==pin,'plan changed');d=read(path)
    require(d['schema']=='native-dataset-panel-execution-v1' and d['scope']=='public_fixed_instruct_test' and d['test_read'] is True,'scope differs')
    require(all(d[k] is False for k in ('scientific_acceptance','candidate_test_authority','candidate_selection_allowed')),'authority differs')
    require(d['modules']['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'runtime differs')
    require(sha(d['config']['path'])==d['config']['sha256'],'config changed');c=config_validate(read(d['config']['path']))
    # Compare against the exact deterministic projection without creating a second plan.
    expected_keys={'schema','config','modules','files','model','model_files','model_sha256','population','protocol','upstream','chip','allocation','queue','out','run','container','host_name','host_python','host_environment','cpu_python','cpu_environment','image','environment','scope','test_read','scientific_acceptance','candidate_test_authority','candidate_selection_allowed','poll_seconds','mounts','cpu_only_paths'}
    require(set(d)==expected_keys,'plan fields differ')
    for key in ('modules','population','protocol','upstream','container','host_name','host_python','host_environment','cpu_python','cpu_environment','image','environment','scope','test_read','scientific_acceptance','candidate_test_authority','candidate_selection_allowed','poll_seconds','cpu_only_paths'):
        require(type(d[key]) is type(c[key]) and d[key]==c[key],'config projection differs: '+key)
    require(d['model']==c['model']['path'] and d['model_files']==c['model']['files'] and d['model_sha256']==c['model']['manifest_sha256'],'model projection differs')
    require(d['chip']==c['resources']['chip'] and d['allocation']==c['resources']['allocation'] and d['queue']==c['resources']['policy'] and ((prepare and d['chip'] is None and d['queue'] is None) or (not prepare and type(d['chip']) is int and d['chip'] in (4,5) and type(d['queue']) is dict)), 'resource projection differs')
    require(d['out']==c['output'] and d['run']=='r3_runs/'+c['run_id'],'run projection differs')
    require(d['files']==dict(c['files'],**{d['config']['path']:d['config']['sha256']}) and d['mounts']==mounts(d,path),'closure differs')
    excluded=set() if cpu else set(d['cpu_only_paths'])
    for p,h in d['files'].items():
        if p not in excluded: require(sha(p)==h,'source changed')
    # Accepted byte manifest, metadata continuity, and small-file hashes; no weight rehash.
    asset_path='/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_rc1_family_numeric_20261107/2b/package/assets/ASSET-RECEIPT.json'
    require(asset_path in d['files'] and sha(asset_path)==d['files'][asset_path], 'asset receipt unbound')
    asset=read(asset_path)
    require(asset['model_byte_pins_inherited_from_accepted_launch']==d['model_files'], 'accepted manifest differs')
    stats=asset['model_stat_continuity']
    require({str(p) for p in safe(d['model']).rglob('*') if p.is_file()}==set(d['model_files'])==set(stats),'model inventory differs')
    for name,h in d['model_files'].items():
        st=safe(name).stat(); old=stats[name]
        require(all(getattr(st,'st_'+k)==old[k] for k in ('size','mtime_ns','ctime_ns')) and st.st_ino==old['inode'],'model stat differs')
        if not name.endswith('.safetensors'): require(sha(name)==h,'model metadata bytes differ')
    require(Path(path).name==('CPU-PREPARE.json' if prepare else 'PLAN.json') and Path(path).parent==Path(d['out']).parent,'plan location differs')
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
    require(r.get('numeric_admission_sha256')==read(d['config']['path'])['numeric']['admission_sha256'],'numeric review differs')
    numeric_check(d)
    require(r.get('cpu_command')==cpu_command(d,path,pin,attempt),'CPU command differs')


def numeric_check(d):
    cfg=read(d['config']['path'])['numeric']
    checker=Path(__file__).with_name('numeric_admission.py')
    m=module({'path':str(checker),'sha256':'8374b08568794b4a2716f821063c4f398884cdb72f20a88e02ce83d57e1c1d0d'})
    base='/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_rc1_family_numeric_20261107/2b'
    result=m.check(base+'/package',base+'/output/cpu/ADMISSION.json',cfg['admission_sha256'],cfg['model'])
    require(result['model_sha256']==d['model_sha256'], 'numeric/model mismatch')
    return result


def build_child_config(d,path,pin,attempt,intent_path):
    """Build a deterministic child config after the external intent exists.

    The caller must independently pin/review that intent; it is never synthesized here.
    """
    require(sha(path)==pin and type(attempt) is int and attempt>0, 'plan or attempt differs')
    require(read(path)==d, 'plan object differs')
    out=safe(d['out'])/'cpu'/str(attempt)
    intent=safe(str(intent_path)); require(intent == out/'PARENT-INTENT.json', 'intent location differs')
    require(read(intent)=={'schema':'kev-generic-parent-intent-v1','plan_sha256':pin,'attempt':attempt}, 'parent intent differs')
    base=Path(__file__).parent
    bootstrap=safe(str(base/'bootstrap.py')); loader=safe(str(base/'loader.py'))
    exe=os.path.realpath(d['cpu_python']); safe(exe)
    return {'bootstrap':{'path':str(bootstrap),'sha256':sha(bootstrap)},
            'loader':{'path':str(loader),'sha256':sha(loader)},
            'plan':{'path':str(path),'sha256':pin}, 'interpreter':exe,
            'environment':d['cpu_environment'], 'action':'generic',
            'target':d['modules']['consumer']['path'],
            'kwargs':{'path':str(path),'pin':pin,'attempt':attempt}, 'output':None,
            'parent_intent':{'path':str(intent),'sha256':sha(intent)},
            'service_path':str(out/'SERVICE.json'), 'service_wait_seconds':30}


def cpu_command(d,path,pin,attempt):
    out=safe(d['out'])/'cpu'/str(attempt); config=out/'CHILD-CONFIG.json'
    expected=build_child_config(d,path,pin,attempt,out/'PARENT-INTENT.json')
    require(read(config)==expected, 'child config differs')
    return [expected['interpreter'],'-B','-P',expected['bootstrap']['path'],
            '--config',str(config),'--sha256',sha(config)]


def start_cpu(d,path,pin,attempt):
    h=Path(d['out'])/'host_attempts'/str(attempt);end=read(h/'EXIT.json');release=read(h/'RELEASE.json');claim=read(h/'CLAIM.json')
    require(type(end.get('exit_code')) is int and end['exit_code']==0 and end.get('runner_terminal_matches') is True,'host not successful')
    require(type(release.get('exit_code')) is int and release['exit_code']==0 and release.get('scientific_acceptance') is False and release.get('schema')=='r3-resource-release-v1' and claim.get('schema')=='r3-resource-claim-v1','successful release required')
    require(type(release.get('chip')) is int and release['chip']==d['chip'] and type(claim.get('chip')) is int and claim['chip']==d['chip'],'release device differs')
    require(release.get('claim_sha256')==sha(h/'CLAIM.json') and release.get('container_id')==end.get('container_id') and release.get('run')==d['run'] and claim.get('run')==d['run'],'release differs')
    root=safe(d['out'])/'cpu'; root.mkdir(exist_ok=True)
    with (root/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); out=root/str(attempt)
        cmd=cpu_command(d,path,pin,attempt)
        service=out/'SERVICE.json'; require(not service.exists() and not (out/'RELAUNCH.json').exists(), 'already launched')
        put(out/'RELAUNCH.json',{'command':cmd,'automatic_retry':False})
        with (out/'runtime.log').open('ab') as log:
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,**d['cpu_environment']))
        try:
            stat=Path(f'/proc/{proc.pid}/stat').read_text(); ticks=int(stat[stat.rfind(')')+2:].split()[19])
            actual=Path(f'/proc/{proc.pid}/cmdline').read_bytes()
            require(actual==b'\0'.join(os.fsencode(x) for x in cmd)+b'\0', 'child command differs')
            intent=out/'PARENT-INTENT.json'
            record={'schema':'kev-bootstrap-service-v1','pid':proc.pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'start_ticks':ticks,'command':cmd,'plan_sha256':pin,'parent_intent_path':str(intent),'parent_intent_sha256':sha(intent)}
            tmp=out/'SERVICE.json.pending'
            with tmp.open('x') as f:
                json.dump(record,f,sort_keys=True,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
            os.link(tmp,service); tmp.unlink()
            fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
            return proc
        except BaseException:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            raise


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
    a=argparse.ArgumentParser();a.add_argument('op',choices=['build','prepare','verify','run']);a.add_argument('--config');a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--prepared-plan');a.add_argument('--prepared-sha256');a.add_argument('--attempt',type=int,default=1);v=a.parse_args()
    if v.op in ('build','prepare'):build(v.config,v.sha256,v.plan,cpu_prepare=v.op=='prepare',prepared_plan=v.prepared_plan,prepared_pin=v.prepared_sha256)
    elif v.prepared_plan is not None or v.prepared_sha256 is not None: a.error('prepared references are for build only')
    elif v.op=='verify':verify(v.plan,v.sha256);print('PANEL_V2_VERIFIED')
    else:run(v.plan,v.sha256,v.attempt)
