import copy, hashlib, importlib.util, json, pathlib, sys
from unittest import mock
import pytest

BASE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('root_adapter',BASE/'adapter.py')
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
registry=json.loads((BASE/'components/training/family-registry-v2.json').read_text())['recipes']
assets=BASE/'components/training/family-assets-v2'

def config(size):
    r=registry[size]
    def ref(name):
        p=assets/name
        return {'manifest':str(p),'manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    return {'schema':'nga-unified-config-v1','adapter':'k1-family-train-v2','owner':'test','seed':2,
            'recipe_id':r['id'],'engineering_stop_after':1,'output':'/run/nga/output',
            'model':dict(id=r['model_id'],path='/model',**ref('model-'+size+'.json')),
            'dataset':dict(id='decision-v7-train',path='/data/input.jsonl',**ref('dataset.json')),'resume':None}

def test_actual_family_route_all_registered_sizes(tmp_path):
    for size in registry:
        c=config(size); p=tmp_path/'config.json'; p.write_text(json.dumps(c)); validated=a.config(p)
        # Only the physical training operation is intercepted; the real family
        # module, validation, recipe selection, CLI and root routing execute.
        with mock.patch('builtins.__import__', wraps=__import__):
            sys.path.insert(0,str(BASE/'components/training'))
            try:
                import training
                with mock.patch.object(training,'verify_manifest',side_effect=RuntimeError('entered family.run')):
                    with mock.patch('pathlib.Path.is_dir',return_value=True):
                        with pytest.raises(RuntimeError,match='entered family.run'):
                            a.run(validated,str(p))
            finally: sys.path.pop(0)

def test_closed_schema_and_asset_authentication(tmp_path):
    c=config('2B'); p=tmp_path/'config.json'
    for change in ('extra','stop','asset'):
        d=copy.deepcopy(c)
        if change=='extra': d['executable']='/model/code'
        elif change=='stop': d['engineering_stop_after']=3117
        else: d['model']['manifest_sha256']='0'*64
        p.write_text(json.dumps(d))
        if change=='asset':
            with pytest.raises(ValueError,match='manifest'): a.run(a.config(p))
        else:
            with pytest.raises(Exception): a.config(p)
