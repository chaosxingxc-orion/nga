"""Build and verify the complete final-evaluation code closure, never launch.

The original pinned closure is copied, deferred-publication patches applied,
and legacy R0 imports rebound to the sibling frozen directory. All resulting
files are hashed; no datasets, checkpoints, FINAL or approval are generated.
"""
import argparse
import builtins
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import types

SOURCE_MANIFEST = '1c2f7d59dc365cbe52dcffe3fd9b734a8c09dc0612d35fe192703649710261df'
COMPONENTS = ('r3_test_execution_guard', 'r3_test_transaction', 'r3_test_log_adapter',
              'r3_final_test_adapter', 'r3_final_metrics', 'r3_model_inventory', 'r3_final_admission', 'r3_final_driver',
              'r3_final_gain_compare', 'r3_final_campaign', 'r3_final_container', 'r3_final_supervisor', 'r3_resource_adapter', 'r3_final_closure')
RUNTIME = ('core_r3', 'full_eval_r3', 'testlock_r3', 'scorer_r3', 'admissible_store_r3',
           'selection_evidence_r3', 'degenerate_r3', 'prechecks_r3', 'variants_r3',
           'track_t_r3', 'provenance_r3', 'clauses_r3', 'common', 'split', 'thresholds',
           'metrics', 'prompt', 'scorer', 'decision', 'eval_r3', 'r3_final_admission',
           'r3_final_test_adapter', 'r3_final_metrics', 'r3_model_inventory')


def require(ok, message):
    if not ok: raise ValueError(message)


def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),
            'absolute nonsymlink path required')
    return p


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


class VerifiedRuntime:
    """Execute pinned source bytes, including later local imports, without pyc."""
    def __init__(self, sources, runtime_path):
        self.sources, self.loaded = sources, {}
        self.runtime_path = list(runtime_path)

    def load(self, name):
        if name in self.loaded:
            return self.loaded[name]
        path, raw = self.sources[name]
        value = types.ModuleType(name)
        value.__file__, value.__package__, value.__loader__ = str(path), '', self
        value.__dict__['__builtins__'] = dict(vars(builtins), __import__=self.import_hook)
        self.loaded[name] = value
        previous = list(sys.path)
        try:
            exec(compile(raw, str(path), 'exec', dont_inherit=True), value.__dict__)
        except BaseException:
            del self.loaded[name]
            raise
        finally:
            sys.path[:] = previous
        return value

    def import_hook(self, name, globals=None, locals=None, fromlist=(), level=0):
        require(level == 0, 'relative imports unsupported in flat final closure')
        head = name.split('.')[0]
        if head in self.sources:
            require(name == head, 'package import unsupported in flat final closure')
            return self.load(head)
        previous = list(sys.path)
        try:
            sys.path[:] = self.runtime_path
            return builtins.__import__(name, globals, locals, fromlist, level)
        finally:
            sys.path[:] = previous


def prepare(source, output):
    source,output=safe(source),safe(output)
    require(not output.exists(), 'closure output already exists')
    manifest=source/'manifest.json'
    require(sha(manifest)==SOURCE_MANIFEST,'source manifest differs')
    doc=json.loads(manifest.read_text());sources={}
    for entry in doc['code'].values():
        p=safe(entry['snapshot'])
        require(p.is_relative_to(source) and sha(p)==entry['sha256'],'source dependency differs')
        sources[str(p.relative_to(source))]=p
    require(set(sources)=={str(p.relative_to(source)) for d in ('r0_code','r3_code')
                          for p in (source/d).rglob('*.py')},'source inventory differs')
    here=Path(__file__).resolve().parent
    preparer=here/'r3_final_eval_prepare.py'
    P=types.ModuleType('final_prepare');P.__file__=str(preparer)
    exec(compile(preparer.read_bytes(),str(preparer),'exec',dont_inherit=True),P.__dict__)
    generated={};changes={}
    old='R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"'
    new='R0_CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "r0_code")'
    for rel,path in sources.items():
        text=path.read_text()
        if rel=='r3_code/full_eval_r3.py':text=P.transform(path.read_bytes());changes[rel]=['deferred publication']
        if rel=='r3_code/testlock_r3.py':
            require(sha(path)==P.TESTLOCK_SHA256,'testlock source differs')
            text+='\n'+P.RECOVERY;changes[rel]=['verified recovery only']
        if old in text:
            require(text.count(old)==1 and 'import os' in text,'R0 import anchor differs')
            text=text.replace(old,new);changes.setdefault(rel,[]).append('sibling frozen R0 imports')
        if rel=='r3_code/r3_scoring_entry.py':
            text=text.replace("sys.path.insert(0, '/mnt/cephfs/xingchao/experiments/jev/r0_code')",
                              "sys.path.insert(0, str(root.parent / 'r0_code'))")
            changes.setdefault(rel,[]).append('sibling frozen R0 entry imports')
        generated[rel]=text.encode()
    for name in COMPONENTS:generated['r3_code/'+name+'.py']=(here/(name+'.py')).read_bytes()
    output.mkdir(parents=True)
    for rel,raw in generated.items():
        path=output/rel;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    result={'schema':'r3-final-closure-v1','source_manifest_sha256':SOURCE_MANIFEST,
            'files':{rel:hashlib.sha256(raw).hexdigest() for rel,raw in sorted(generated.items())},
            'changes':changes,'scientific_acceptance':False,'deployable':False,
            'remaining':['exact-plan launcher and full model byte verification',
                         'real scorer interrupted-resume validation','formal eligibility and independent review']}
    target=output/'manifest.json';target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return {'root':str(output),'manifest_sha256':sha(target),'files':len(generated),'deployable':False}


def verify(root, pin, import_runtime=False):
    root=safe(root);manifest=safe(root/'manifest.json')
    require(sha(manifest)==pin,'final closure manifest differs')
    doc=json.loads(manifest.read_text())
    require(doc.get('schema')=='r3-final-closure-v1','final closure schema differs')
    # Importing the frozen modules during admission creates interpreter bytecode
    # caches beside the sources.  They are runtime by-products, not closure
    # inputs, and must not make an otherwise byte-identical closure unverifiable.
    actual={str(p.relative_to(root)) for p in root.rglob('*')
            if p.is_file() and p!=manifest and '__pycache__' not in p.parts}
    require(actual==set(doc['files']),'final closure inventory differs')
    sources={}
    for rel,pin_value in doc['files'].items():
        path=safe(root/rel)
        require(path.is_relative_to(root), 'final closure path escaped: '+rel)
        raw=path.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==pin_value,'final closure file differs: '+rel)
        if path.suffix=='.py':
            require(path.parent in (root/'r3_code',root/'r0_code') and path.stem.isidentifier()
                    and path.stem not in sources,'flat unique Python modules required')
            sources[path.stem]=(path,raw)
    origins={}
    if import_runtime:
        sys.dont_write_bytecode=True
        names={Path(rel).stem for rel in doc['files'] if rel.endswith('.py')}
        for name in names:
            if name in sys.modules:
                m=sys.modules[name];p=getattr(m,'__file__',None)
                require(p is not None and Path(p).resolve().is_relative_to(root),'preloaded module escaped closure: '+name)
        runtime_path=[p for p in sys.path if p and Path(p).resolve() not in
                      (root/'r3_code',root/'r0_code')]
        loader=VerifiedRuntime(sources,runtime_path)
        for name in RUNTIME:loader.load(name)
        sys.modules.update(loader.loaded)
        origins={name:str(sources[name][0]) for name in loader.loaded}
    return {'files':len(doc['files']),'origins':origins,'scientific_acceptance':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('verify');p.add_argument('--root',required=True);p.add_argument('--sha256',required=True);p.add_argument('--import-runtime',action='store_true')
    a=parser.parse_args()
    print(json.dumps(prepare(a.source,a.output) if a.action=='prepare' else verify(a.root,a.sha256,a.import_runtime),indent=2))
