"""Adapter for the existing release binder/preparation queue; no NPU authority."""
import argparse
import hashlib
import json
from pathlib import Path
import types


def prepare(config):
    c=json.loads(Path(config).read_bytes())
    if c['schema']!='typed-static-bound-prepare-v1':raise ValueError('bound preparation schema')
    r=c['materializer'];raw=Path(r['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('materializer changed')
    m=types.ModuleType('typed_static_materializer');m.__file__=r['path'];exec(compile(raw,r['path'],'exec'),m.__dict__)
    return m.materialize(dict(schema='typed-static-materialize-config-v1',static_manifest=c['static_manifest'],root=c['root'],chip=c['chip'],resource_policy=m.ref(c['resource_policy'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.config)),flush=True)
