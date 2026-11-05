"""Versioned prospective adapters. No config supplied executable code."""
import argparse, hashlib, importlib.util, json, os, pathlib, sys
BASE=pathlib.Path(__file__).resolve().parent
ROOT=BASE/'source'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module
def digest(path):
    with open(path,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def config(path):
    import jsonschema
    with open(path) as f: obj=json.load(f, object_pairs_hook=unique)
    with open(BASE/'schema.json') as f: schema=json.load(f)
    jsonschema.Draft202012Validator(schema).validate(obj)
    return obj
def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValueError('duplicate field: '+k)
        out[k]=v
    return out
def run(c, config_path=None):
    if c['adapter']=='native-panel-export-v1':
        raise ValueError('v1 inference does not bind a panel contract before inference; export rejected before effects')
    if c['adapter']=='native-panel-export-v2':
        export=load(BASE/'panel_export.py','nga_panel_export'); export.run(c); return
    if c['adapter']=='native-panel-score-v1':
        panel=load(BASE/'panel_score.py','nga_panel_score'); panel.run(c,config_path); return
    if c['adapter']=='environment-check-v1':
        import importlib.util
        found=importlib.util.find_spec('nga_cwd_probe') is not None
        tbe=importlib.util.find_spec('tbe') is not None
        print(json.dumps({'cwd_probe_importable':found,'tbe_available':tbe,'pythonpath':os.environ.get('PYTHONPATH','')}))
        if found or not tbe: raise ValueError('environment isolation check failed')
        return
    if c['adapter'] in ('native-full-label-v1','native-full-label-v2','k1-full-train-v1'):
        kind='inference' if c['adapter'] in ('native-full-label-v1','native-full-label-v2') else 'training'
        name='native_inference' if kind=='inference' else 'training'
        component=load(BASE/'components'/kind/(name+'.py'),'nga_'+name)
        body={k:v for k,v in c.items() if k not in ('schema','output')}
        component.run(body,c['output']); return
    raise ValueError('adapter not implemented')
def main():
    p=argparse.ArgumentParser(); p.add_argument('config'); a=p.parse_args(); run(config(a.config),a.config)
if __name__=='__main__': main()
