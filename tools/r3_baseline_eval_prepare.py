#!/usr/bin/env python3
"""Freeze a fresh model-only K0 dev/Track-T baseline; no training receipt fabricated."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def prepare(closure, model, out):
    loader=importlib.util.spec_from_file_location('launcher',Path(__file__).with_name('r3_posttrain_eval_launcher.py'))
    launcher=importlib.util.module_from_spec(loader);loader.loader.exec_module(launcher)
    doc=json.loads((closure/'manifest.json').read_text())
    if doc.get('evaluation_profile')!='track_kt':raise ValueError('full combined closure required')
    if model.name not in ('Qwen__Qwen3.5-0.8B-Base','Qwen__Qwen3.5-2B-Base','Qwen__Qwen3.5-4B-Base','Qwen__Qwen3.5-9B-Base'):
        raise ValueError('model outside sub-10B base family')
    files={}
    for filename,digest in doc['data'].items():
        p=Path(filename)
        if sha(p)!=digest:raise ValueError('frozen data changed')
        files[filename]=digest
    for entry in doc['code'].values():
        p=Path(entry['snapshot'])
        if sha(p)!=entry['sha256']:raise ValueError('frozen code changed')
        files[str(p)]=entry['sha256']
    for p in model.rglob('*'):
        if p.is_symlink():raise ValueError('model symlink')
        if p.is_file():files[str(p)]=sha(p)
    if not any(p.suffix=='.safetensors' for p in model.iterdir()):raise ValueError('model weights missing')
    spec={'schema':'r3-baseline-dev-spec-v1','evaluation_profile':'track_kt',
          'model':str(model),'files':files,'code_mounts':doc['mounts'],
          'readonly_data_mounts':list(doc['data']),'image_sha256':launcher.IMAGE,
          'network':'none','test_read':False,'scientific_acceptance':False,
          'scope':'fresh K0 raw dev/calibration and Track T readouts; CPU selection-half only',
          'baseline_identity':{'arm':'K0','model':str(model),'closure_manifest_sha256':sha(closure/'manifest.json')}}
    spec['command']=launcher.expected_command(spec,out)
    launcher.verify_spec(spec,out)
    out.mkdir(parents=True,exist_ok=False)
    p=out/'plan.json';p.write_text(json.dumps(spec,indent=2,sort_keys=True)+'\n')
    (out/'PREREGISTRATION.md').write_text('# K0 engineering rescore\n\nSame frozen scorer, data, formulas and readout populations as the candidate combined development evaluation. Fresh model-only scoring; historical rows are not reused or stamped retroactively. No test scoring, report-half metrics, model selection or formal acceptance. Resource assignment requires separate guarded launcher.\n')
    return {'plan':str(p),'sha256':sha(p),'scientific_acceptance':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('closure','model','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.closure,a.model,a.out)))
