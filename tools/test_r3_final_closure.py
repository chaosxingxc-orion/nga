import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('closure',HERE/'r3_final_closure.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2')


class Closure(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('source closure missing')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'closure';self.receipt=M.prepare(SOURCE,self.root)
        self.pin=self.receipt['manifest_sha256']

    def test_real_runtime_imports_are_all_frozen(self):
        p=subprocess.run([sys.executable,'-B','-I',str(HERE/'r3_final_closure.py'),'verify',
            '--root',str(self.root),'--sha256',self.pin,'--import-runtime'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        self.assertGreaterEqual(len(result['origins']),23)
        self.assertTrue(all(Path(p).is_relative_to(self.root) for p in result['origins'].values()))

    def test_changed_added_or_removed_file_refused(self):
        path=self.root/'r3_code/core_r3.py';raw=path.read_bytes();path.write_bytes(raw+b'\n')
        with self.assertRaisesRegex(ValueError,'file differs'):M.verify(self.root,self.pin)
        path.write_bytes(raw);extra=self.root/'r3_code/extra.py';extra.write_text('')
        with self.assertRaisesRegex(ValueError,'inventory'):M.verify(self.root,self.pin)
        extra.unlink();path.unlink()
        with self.assertRaisesRegex(ValueError,'inventory'):M.verify(self.root,self.pin)

    def test_preloaded_module_from_external_path_refused(self):
        script='''import importlib.util,sys,types
from pathlib import Path
s=importlib.util.spec_from_file_location('check',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
sys.modules['prompt']=types.SimpleNamespace(__file__='/outside/prompt.py')
try:m.verify(Path(sys.argv[2]),sys.argv[3],True)
except ValueError as e:
 assert 'preloaded module escaped' in str(e);print('refused')
else:raise AssertionError('foreign module accepted')
'''
        p=subprocess.run([sys.executable,'-B','-I','-c',script,str(HERE/'r3_final_closure.py'),str(self.root),self.pin],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'refused')


if __name__=='__main__':unittest.main()
