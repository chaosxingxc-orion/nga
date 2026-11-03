#!/usr/bin/env python3
"""Compose a native long-DEV package from pinned inputs; never launch or grant review."""
import argparse
import hashlib
import json
from pathlib import Path
import types

def require(ok, why):
    if not ok:
        raise ValueError(why)

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe(path):
    require(type(path) is str, 'path string required')
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in [p, *p.parents]), 'unsafe path')
    return p

def ref(path):
    return {'path': str(safe(str(path))), 'sha256': sha(path)}

def pinned(value):
    require(type(value) is dict and set(value) == {'path', 'sha256'}, 'reference fields differ')
    p = safe(value['path'])
    require(sha(p) == value['sha256'], 'source changed: ' + str(p))
    return json.loads(p.read_text())

def module(value):
    p = safe(value['path']); require(sha(p) == value['sha256'], 'module changed')
    m = types.ModuleType(p.stem); m.__file__ = str(p)
    exec(compile(p.read_bytes(), str(p), 'exec'), m.__dict__)
    return m

def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')

def prepare(spec_path, expected):
    spec = pinned({'path': str(safe(str(spec_path))), 'sha256': expected})
    require(set(spec) == {'schema','template','configuration','registry','resource_policy','upstream','root'}, 'prepare fields differ')
    require(spec['schema'] == 'native-config-prepare-v1', 'prepare schema differs')
    template = pinned(spec['template']); c = pinned(spec['configuration']); registry = pinned(spec['registry'])
    policy = pinned(spec['resource_policy']); upstream = pinned(spec['upstream'])
    require(template['schema'] == 'native-config-execution-v1', 'template schema differs')
    root = safe(spec['root']); require(not root.exists(), 'package exists')
    require(root.parent == Path(registry['platform']['output_root']) and c['output'] == str(root/'output'), 'package/output differ')
    require(c['run_id'] == root.name, 'run identity differs')
    modules = dict(template['modules']); modules['upstream_binding'] = spec['upstream']
    C = module(modules['contract']); C.validate(c, registry)
    R = module(modules['runtime']); L = module(modules['loader']); N = module(modules['native']); H = module(modules['host'])
    model = registry['model'][c['model']]; protocol = registry['protocol'][c['protocol']]; resource = registry['resources'][c['resources']]
    require(policy.get('run') == 'r3_runs/'+c['run_id'] and policy.get('chip') == resource['chip'], 'resource policy candidate differs')
    require(policy.get('scientific_acceptance') is False and policy.get('test_read') is False, 'policy scope differs')
    files = {x['path']:x['sha256'] for x in modules.values()}
    files.update({spec[k]['path']:spec[k]['sha256'] for k in ('configuration','registry','resource_policy')})
    files[c['inputs']['path']] = c['inputs']['sha256']; files.update(model['files'])
    for x in [*policy.get('predecessor', {}).values(), *policy.get('priority_refs', [])]:
        pinned(x); files[x['path']] = x['sha256']
    for name, h in N.PINS.items():
        p = str(Path(upstream['root'])/'anyjev'/name); require(sha(p) == h, 'upstream changed'); files[p] = h
    contract = N.digest({model['path']:model['model_manifest_sha256'],'protocol':protocol,'inputs':c['inputs'],'native':modules['native'],'loader':modules['loader'],'probe':modules['probe']})
    d = {'schema':'native-config-execution-v1','config':spec['configuration'],'registry':spec['registry'],'modules':modules,'files':files,'model_files':model['files'],'contract_sha256':contract,'environment':L.ENV,'image':L.IMAGE,'allocation':policy['allocation'],'queue':spec['resource_policy'],'out':c['output'],'run':'r3_runs/'+c['run_id'],'chip':resource['chip'],'container':'nga-native-config-'+c['run_id'].replace('_','-'),'host_name':template['host_name'],'poll_seconds':600,'scientific_acceptance':False,'test_read':False}
    root.mkdir(); (root/'output').mkdir(); p = root/'PLAN.json'
    try:
        d['mounts'] = R.mounts(d,p,model['path']); write(p,d); R.verify(str(p),sha(p))
        view = {**d,'runtime':modules['runtime'],'resource':modules['resource'],'image_sha256':d['image'],'scope':'synthetic_long_dev'}
        write(root/'COMMANDS.json', {'plan':ref(p),'docker':H.command(view,str(p),sha(p),1),'runtime_verify':['python3','-B','-P',modules['runtime']['path'],'verify','--plan',str(p),'--sha256',sha(p)],'host_preflight':['python3','-B','-P',modules['host']['path'],'preflight','--plan',str(p),'--sha256',sha(p)],'launch_authority':False})
        result = {'schema':'native-config-preparation-v1','status':'CPU_PREPARED_PENDING_EXACT_REVIEW','spec':ref(spec_path),'template':spec['template'],'plan':ref(p),'executable_modules_unchanged':all(modules[k]==template['modules'][k] for k in modules if k!='upstream_binding'),'questions':c['inputs']['count'],'forwards':c['inputs']['count']*len(protocol['variants']),'npu_launched':False,'scientific_acceptance':False,'resource_admission_checked':False,'test_read':False}
        write(root/'PREPARATION.json',result); return result
    except BaseException as exc:
        write(root/'PREPARATION-FAILED.json',{'status':'FAILED','error_type':type(exc).__name__,'message':str(exc)[:400],'npu_launched':False}); raise

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--sha256',required=True); a = ap.parse_args()
    print(json.dumps(prepare(a.config,a.sha256),indent=2))
