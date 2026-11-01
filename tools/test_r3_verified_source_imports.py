"""Actual poisoned-bytecode/preloaded-module probes against source-byte loader."""
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent

def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

R = module('r3_selection_report'); F = module('r3_fresh_prechecks')
NAMES = ['core_r3', 'selection_evidence_r3', 'degenerate_r3', 'prechecks_r3', 'variants_r3',
         'track_t_r3', 'provenance_r3', 'testlock_r3', 'common', 'split', 'thresholds', 'metrics', 'prompt', 'scorer']

def poison(path, code):
    cache=Path(importlib.util.cache_from_source(str(path)));cache.parent.mkdir(exist_ok=True)
    st=path.stat()
    cache.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack('<III',0,int(st.st_mtime),st.st_size)
                      + marshal.dumps(compile(code,str(path),'exec')))

class Imports(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.r3=self.root/'r3_code';self.r0=self.root/'r0_code'
        self.r3.mkdir();self.r0.mkdir();self.files={}
        self.previous={n:sys.modules.get(n) for n in NAMES}
        self.addCleanup(self.restore)
        for name in NAMES:
            path=self.r3/(name+'.py');path.write_text("VALUE='verified'\n")
            self.files[name]=path
        self.files['selection_evidence_r3'].write_text('import core_r3 as C\ndef later():\n import core_r3\n return core_r3.VALUE\n')
        self.manifest()
    def restore(self):
        for name,value in self.previous.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value
    def manifest(self):
        (self.root/'manifest.json').write_text(json.dumps({'code':{n:{'snapshot':str(p),'sha256':R.sha(p)} for n,p in self.files.items()}}))
    def test_valid_poisoned_cache_is_not_executed(self):
        sentinel=self.root/'executed'
        poison(self.files['core_r3'],f"open({str(sentinel)!r},'w').write('bad'); VALUE='poison'\n")
        C,E,*_=R.modules(self.r3)
        self.assertEqual(C.VALUE,'verified');self.assertIs(E.C,C)
        self.assertFalse(sentinel.exists())
    def test_preloaded_and_later_module_substitution_not_used(self):
        fake=types.ModuleType('core_r3');fake.__file__=str(self.files['core_r3']);fake.VALUE='poison'
        sys.modules['core_r3']=fake
        C,E,*_=R.modules(self.r3)
        self.assertEqual(C.VALUE,'verified');self.assertIsNot(C,fake)
        sys.modules['core_r3']=fake
        self.assertEqual(E.later(),'verified')
    def test_import_loader_executes_same_bytes_it_hashes(self):
        path=self.files['core_r3'];raw=path.read_bytes();pin=hashlib.sha256(raw).hexdigest()
        poison(path,"raise AssertionError('cache must not execute')")
        self.assertEqual(F.load_module(path,'fresh',pin).VALUE,'verified')
        path.write_text("VALUE='changed'\n")
        with self.assertRaisesRegex(ValueError,'pin differs'):F.load_module(path,'fresh',pin)
    def test_hashed_source_tampering_rejected_before_execution(self):
        self.files['core_r3'].write_text("raise AssertionError('must not execute')\n")
        with self.assertRaisesRegex(ValueError,'frozen code changed'):R.modules(self.r3)
    def test_sys_path_mutation_restored(self):
        self.files['core_r3'].write_text("import sys\nsys.path.insert(0,'/untrusted/history')\nVALUE='verified'\n")
        self.manifest();before=list(sys.path);R.modules(self.r3);self.assertEqual(sys.path,before)

if __name__=='__main__':unittest.main()
