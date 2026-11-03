"""CPU validation of prospective native experiments via a pinned capability registry.
No registry entry or validated configuration grants launch/scientific authority.
"""
import hashlib,json,math,re
from pathlib import Path

def strict_json(data):
    def pairs(xs):
        out={}
        for k,v in xs:
            if k in out:raise ValueError('duplicate key')
            out[k]=v
        return out
    def finite(x):
        if isinstance(x,float) and not math.isfinite(x):raise ValueError('nonfinite number')
        if isinstance(x,dict):
            for v in x.values():finite(v)
        elif isinstance(x,list):
            for v in x:finite(v)
    result=json.loads(data,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite number')));finite(result);return result

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def require(test,reason):
    if not test:raise ValueError(reason)

def fields(value,required,reason):
    require(type(value)is dict and set(value)==set(required),reason)

def names(value,reason):
    require(type(value)is list and value and all(type(x)is str and x for x in value) and len(value)==len(set(value)),reason)

def canonical_path(value):
    require(type(value)is str and value and str(Path(value))==value,'noncanonical path')
    p=Path(value)
    require(p.is_absolute() and not any(x in ('.','..') for x in value.split('/')) and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path')
    return p

def registry_shape(r):
    fields(r,('schema','platform','model','protocol','resources','adapters'),'registry fields differ')
    require(r['schema']=='native-capability-registry-v1','registry schema differs')
    fields(r['platform'],('chips','output_root','image'),'platform fields differ')
    p=r['platform'];canonical_path(p['output_root'])
    require(type(p['chips'])is list and p['chips'] and all(type(x)is int and x>=0 for x in p['chips']) and len(set(p['chips']))==len(p['chips']),'platform chips differ')
    require(type(p['image'])is str and p['image'].startswith('sha256:'),'platform image differs')
    for key in ('model','protocol','resources','adapters'):
        require(type(r[key])is dict and r[key] and all(type(k)is str and k for k in r[key]),'registry identities differ')
    for m in r['model'].values():
        fields(m,('family','path','files','model_manifest_sha256'),'model fields differ')
        require(type(m['family'])is str and m['family'],'model family differs');canonical_path(m['path'])
        require(type(m['files'])is dict and m['files'],'model files differ')
        for path,pin in m['files'].items():canonical_path(path);require(type(pin)is str and re.fullmatch('[0-9a-f]{64}',pin),'model pin differs')
        require(type(m['model_manifest_sha256'])is str and re.fullmatch('[0-9a-f]{64}',m['model_manifest_sha256']),'model manifest differs')
    for a in r['adapters'].values():
        fields(a,('interface','implemented'),'adapter fields differ')
        require(type(a['interface'])is str and a['interface'] and type(a['implemented'])is bool,'adapter capability differs')
    for p in r['protocol'].values():
        fields(p,('adapters','batch_size','compatible_families','dtype','hf32','lengths','max_length','variants'),'protocol fields differ')
        names(p['compatible_families'],'families differ');names(p['variants'],'variants differ')
        require(type(p['max_length'])is int and p['max_length']>0 and type(p['lengths'])is list and p['lengths'] and all(type(x)is int and 0<x<=p['max_length'] for x in p['lengths']),'protocol lengths differ')
        require(type(p['batch_size'])is int and p['batch_size']>0 and type(p['dtype'])is str and p['dtype'] and type(p['hf32'])is bool,'protocol numerical types differ')
        require(type(p['adapters'])is dict and p['adapters'] and all(type(k)is str and k and type(v)is str and v in r['adapters'] and r['adapters'][v]['interface']==k for k,v in p['adapters'].items()),'protocol adapters differ')
    for v in r['resources'].values():
        fields(v,('chip','chips','requires_idle_and_no_ready_queue'),'resource fields differ')
        require(type(v['chip'])is int and v['chip'] in r['platform']['chips'] and type(v['chips'])is int and v['chips']==1 and type(v['requires_idle_and_no_ready_queue'])is bool,'resource types differ')

def validate(config,registry):
    registry_shape(registry)
    require(type(config)is dict,'configuration object required')
    require(set(config)=={'schema','run_id','registry_sha256','model','protocol','resources','adapters','inputs','output','scope'},'configuration keys differ')
    require(config['schema']=='native-experiment-config-v1','schema differs')
    require(config['registry_sha256']==hashlib.sha256(json.dumps(registry,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'registry differs')
    require(config['scope']=={'test_read':False,'scientific_acceptance':False,'launch_authority':False},'scope differs')
    require(all(v is False for v in config['scope'].values()),'scope types differ')
    for kind in ('model','protocol','resources'):
        require(type(config[kind]) is str and config[kind] in registry[kind],'unknown registered '+kind)
    model=registry['model'][config['model']];protocol=registry['protocol'][config['protocol']];resource=registry['resources'][config['resources']]
    require(set(config['adapters'])==set(protocol['adapters']),'adapter kinds differ')
    for kind,identity in config['adapters'].items():
        require(identity==protocol['adapters'][kind] and identity in registry['adapters'],'adapter binding differs')
        require(registry['adapters'][identity]['interface']==kind,'adapter interface differs')
    require(model['family'] in protocol['compatible_families'],'model protocol differs')
    require(type(resource['chip'])is int and resource['chip'] in registry['platform']['chips'],'device differs')
    require(type(resource['chips'])is int and resource['chips']==1,'single chip contract')
    require(resource['requires_idle_and_no_ready_queue'] is True,'resource prerequisite absent')
    require(protocol['batch_size']==1 and type(protocol['batch_size'])is int,'batch differs')
    require(type(config['run_id'])is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',config['run_id']),'run identity differs')
    root=canonical_path(registry['platform']['output_root']);out=canonical_path(config['output'])
    require(out.is_absolute() and out.is_relative_to(root) and out==root/config['run_id']/'output','output differs')
    request_ref=config['inputs'];require(set(request_ref)=={'path','sha256','count','ordered_sha256'},'input reference differs')
    require(type(request_ref['count'])is int and request_ref['count']==len(protocol['lengths']),'population count differs')
    require(sha(request_ref['path'])==request_ref['sha256'],'input bytes changed')
    with Path(request_ref['path']).open() as f:items=[strict_json(line) for line in f]
    require(hashlib.sha256(json.dumps(items,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()==request_ref['ordered_sha256'],'input order changed')
    require(len(items)==len(protocol['lengths']),'input population differs')
    for i,(item,length) in enumerate(zip(items,protocol['lengths'])):
        require(type(item['i'])is int and item['i']==i,'ordinal differs')
        require('gold' not in item and 'y' not in item,'labels forbidden')
        require(len(item['input_ids'])==length and all(type(v)is int and v>=0 for v in item['input_ids']),'tokens differ')
    return {'status':'CONFIG_STRUCTURE_VALID','items':len(items),'forward_variants':protocol['variants'],'forwards':len(items)*len(protocol['variants']),'launch_authority':False,'scientific_acceptance':False,'runtime_available':all(registry['adapters'][v]['implemented'] for v in config['adapters'].values())}
