"""Synthetic acceptance fixtures; never reads datasets or runs an accelerator."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

VERIFIER = Path(__file__).with_name('verify_r3_efficiency.py')

class Verification(unittest.TestCase):
    def fixture(self, root):
        (root/'code').mkdir()
        source=root/'code/train.py'; source.write_text('fixture')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        plan={'out':str(root),'command':['--total-steps','15'],'code_dir':str(root/'code'),
              'files':{str(source):digest,'train.jsonl':'fake-sha'}}
        manifest={'arm':'k1','args':{'seed':2},'total_steps':15,'summary':{'final_step':15,'peak_reserved_gib':6.65},
                  'train_file':{'path':'train.jsonl','sha256':'fake-sha'},'code_sha256':{'train.py':digest}}
        (root/'plan.json').write_text(json.dumps(plan));(root/'manifest.json').write_text(json.dumps(manifest))
        (root/'DONE').write_text('rc=0 utc=fixture')
        (root/'progress.log').write_text('reserved_gib 6.7\n')
        rows=[{'step':i,'loss':1.,'step_s':7.,'tok_s_chip':10.,'q_s_chip':1.,'tokens':70,'base_questions':7} for i in range(1,16)]
        self.rows(root,rows)
        return rows
    def rows(self,root,rows):
        (root/'losses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    def invoke(self,root):
        return subprocess.run([sys.executable,str(VERIFIER),'--run',str(root),'--plan',str(root/'plan.json'),
                               '--output',str(root/'result.json')],capture_output=True,text=True)
    def test_valid_memory_forms_and_no_overwrite(self):
        for memory in ('reserved_gib 6.7','reserved_gib=6.7'):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);self.fixture(root);(root/'progress.log').write_text(memory)
                self.assertEqual(self.invoke(root).returncode,0)
                result=json.loads((root/'result.json').read_text());self.assertEqual(result['tokens_per_second_per_chip'],10)
                self.assertFalse(result['scientific_acceptance']);self.assertNotEqual(self.invoke(root).returncode,0)
    def test_rejects_invalid_evidence(self):
        for case in ('nan','missing','duplicate','memory','marker','failed','code','manifest'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as td:
                root=Path(td);rows=self.fixture(root)
                if case=='nan': rows[7]['loss']=float('nan');self.rows(root,rows)
                if case=='missing': self.rows(root,rows[:-1])
                if case=='duplicate': rows[-1]['step']=14;self.rows(root,rows)
                if case=='memory': (root/'progress.log').write_text('no memory')
                if case=='marker': (root/'DONE').write_text('rc=01')
                if case=='failed': (root/'FAILED').write_text('rc=1')
                if case=='code': (root/'code/train.py').write_text('changed')
                if case=='manifest':
                    p=root/'manifest.json';d=json.loads(p.read_text());d['summary']['final_step']=14;p.write_text(json.dumps(d))
                self.assertNotEqual(self.invoke(root).returncode,0)
                self.assertFalse((root/'result.json').exists())

if __name__=='__main__': unittest.main()
