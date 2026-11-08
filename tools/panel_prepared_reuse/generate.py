#!/usr/bin/env python3
"""Create a fresh CPU panel package from an explicitly pinned accepted template/config."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL_RUNTIME = 'b56ff51bbe32a89dd27afa1e9357f1bbece2c8d50b076b761b1c5005f3f3ca26'
ORIGINAL_BINDER = '25ea7a5c2be89e4a340f9f78eb9b39d59e73889aef4352b29295279a2240e3b9'
BINDER_ROOT = '/home/xingchao/workspace/nga/.local/releases/engineering-base-rc1/tasks/execution/instruct-family-successor-packs-20261108/packs/instruct2b_devtools_successor_20261108'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, obj):
    Path(p).write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + '\n')

def generate(template, config_path, config_pin, dest):
    template, config_path, dest = map(lambda p: Path(p).resolve(), (template, config_path, dest))
    if dest.exists() or template == dest or template in dest.parents: raise ValueError('destination must be fresh and outside template')
    if sha(config_path) != config_pin: raise ValueError('config pin differs')
    if sha(template/'code/bev_native_dataset_panel_v1.py') != ORIGINAL_RUNTIME or sha(template/'bind.py') != ORIGINAL_BINDER:
        raise ValueError('template runtime or binder differs from reviewed source')
    if any(p.is_symlink() for p in (template/'code').rglob('*')): raise ValueError('template code contains symlink')
    c = json.loads(config_path.read_text())
    oldcode = Path(c['modules']['runtime']['path']).parent
    if c['resources']['chip'] is not None or c['resources']['policy'] is not None: raise ValueError('unbound CPU config required')
    if c['numeric'] != {'model':'2b','admission_sha256':'73589e71c7d463b2833e6559db4b4dc4d4a71a7fd1e40aaea3f9b770971807ce'} or c['population']['count'] != 1073:
        raise ValueError('reviewed binder is specific to the 2b devtools package')
    for path, pin in c['files'].items():
        if Path(path).parent == oldcode and sha(template/'code'/Path(path).name) != pin:
            raise ValueError('template dependency differs: '+path)
    dest.mkdir(parents=True, exist_ok=False)
    (dest/'cpu').mkdir(); (dest/'output').mkdir()
    shutil.copytree(template/'code', dest/'code')
    shutil.copyfile(HERE/'bev_native_dataset_panel_v1.py', dest/'code/bev_native_dataset_panel_v1.py')
    def relocate(path):
        p = Path(path)
        return str(dest/'code'/p.name) if p.parent == oldcode else path
    # The task config contains a source-bound pairs path, outside the CPU config.
    task = dest/'code/TASK-CONFIG.json'
    if task.exists():
        t = json.loads(task.read_text())
        t['pairs']['path'] = relocate(t['pairs']['path'])
        save(task, t)
    c['run_id'] = dest.name
    c['container'] = 'nga-' + dest.name.replace('_', '-')
    c['output'] = str(dest/'output')
    old_contract = c['population']['contract']['path']
    files = {}
    for path, pin in c['files'].items():
        if path == old_contract: continue
        new = relocate(path)
        if new != path: pin = sha(new)
        elif sha(path) != pin: raise ValueError('external dependency changed: '+path)
        files[new] = pin
    for ref in c['modules'].values():
        ref['path'] = relocate(ref['path']); ref['sha256'] = sha(ref['path'])
        if files.get(ref['path']) != ref['sha256']: raise ValueError('module outside closure')
    for key, ref in c['population'].items():
        if isinstance(ref, dict) and set(ref) == {'path','sha256'} and key != 'contract':
            ref['path'] = relocate(ref['path']); ref['sha256'] = files[ref['path']]
    c['cpu_only_paths'] = [relocate(p) for p in c['cpu_only_paths'] if p != old_contract]
    import importlib.util
    spec = importlib.util.spec_from_file_location('panel_generated', dest/'code/bev_native_dataset_panel_v1.py')
    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
    P=runtime.module(c['modules']['protocol']); N=runtime.module(c['modules']['native'])
    L=runtime.module(c['modules']['loader']); X=runtime.module(c['modules']['panel'])
    items=X.rows(c['population']['items']['path'])
    binding=N.digest(dict(native=c['modules']['native']['sha256'],runner=c['modules']['runtime']['sha256'],loader=c['modules']['loader']['sha256'],protocol=c['modules']['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=L.LOADER,image=c['image'],model_sha256=c['model']['manifest_sha256']))
    contract=P.make_contract(items,source_sha256=c['population']['source']['sha256'],model_sha256=c['model']['manifest_sha256'],runtime_protocol_sha256=binding)
    cp=dest/'cpu/CONTRACT.json'; save(cp,contract)
    c['population'].update(contract={'path':str(cp),'sha256':sha(cp)},contract_sha256=P.sha256_value(contract),protocol_binding_sha256=binding)
    files[str(cp)]=sha(cp); c['cpu_only_paths'].append(str(cp)); c['files']=files
    runtime.config_validate(c)
    save(dest/'CPU-CONFIG.json',c)
    binder=(HERE/'bind.py').read_text()
    if binder.count(BINDER_ROOT) != 1: raise ValueError('binder template root differs')
    (dest/'bind.py').write_text(binder.replace(BINDER_ROOT,str(dest)))
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',required=True); p.add_argument('--config',required=True)
    p.add_argument('--config-sha256',required=True); p.add_argument('--destination',required=True)
    a=p.parse_args(); dest=generate(a.template,a.config,a.config_sha256,a.destination)
    print(json.dumps({'package':str(dest),'cpu_config_sha256':sha(dest/'CPU-CONFIG.json'),'status':'GENERATED_PREPARE_AND_REVIEW_REQUIRED'}))

if __name__=='__main__': main()
