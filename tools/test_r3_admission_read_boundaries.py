"""Production-entry counterexamples from Astra v4; no real dataset access."""
import importlib.util
import importlib.machinery
import marshal
import struct
import types
from pathlib import Path
from unittest.mock import patch
import unittest

HERE=Path(__file__).resolve().parent

def module(name):
    p=HERE/(name+'.py');m=types.ModuleType(name);m.__file__=str(p)
    exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m

class Boundaries(unittest.TestCase):
    def test_outer_reconstruction_cannot_be_replaced_by_valid_pyc(self):
        L=module('r3_formal_launcher');p=HERE/'r3_resume_reconstruction_evidence.py'
        st=p.stat();cache=importlib.util.cache_from_source(str(p))
        payload=importlib.util.MAGIC_NUMBER+struct.pack('<III',0,int(st.st_mtime),st.st_size)+marshal.dumps(compile('def validate(*a,**kw): return {}\n',str(p),'exec'))
        original=importlib.machinery.SourceFileLoader.get_data
        def poisoned(loader,filename):return payload if filename==cache else original(loader,filename)
        plan={'files':{str(p):L.sha(p),'/synthetic/report.json':'r','/synthetic/target.json':'t'},
              'resume_reconstruction':'/synthetic/report.json','resume_reconstruction_sha256':'r',
              'reconstruction_target':'/synthetic/target.json','reconstruction_target_sha256':'t',
              'resume_plan':'/synthetic/plan.json','resume_plan_sha256':'p'}
        with patch.object(importlib.machinery.SourceFileLoader,'get_data',poisoned):
            with self.assertRaisesRegex(ValueError,'missing resume evidence'):L.verify_resume_reconstruction(plan)

    def test_all_outer_source_loaders_ignore_bytecode_loader(self):
        original=importlib.machinery.SourceFileLoader.get_code
        def guarded(loader,fullname):
            if Path(loader.path).parent==HERE:
                raise AssertionError('local cache loader entered')
            return original(loader,fullname)
        for name in ('r3_formal_launcher','r3_formal_prepare','r3_formal_control_readiness',
                     'r3_control_resume_prepare','r3_control_resume_cpu','r3_control_resume_cpu_queue',
                     'r3_control_resume_successor','r3_resume_recompute'):
            with self.subTest(name=name),patch.object(importlib.machinery.SourceFileLoader,'get_code',guarded):
                m=module(name);v=m.source_module(HERE/'r3_resume_evidence.py','validator')
                self.assertTrue(callable(v.validate))

    def test_nested_test_inventory_rejected_before_any_hash(self):
        R=module('r3_resume_evidence')
        p={'out':'/synthetic/resume','validation_kind':'current_k1_resume_contract',
           'schema':'r3-engineering-k1-plan-v1','seed':2,'test_read':False,'scientific_acceptance':False,
           'files':{'/synthetic/train.jsonl':'x','/synthetic/test.jsonl':'x'}}
        with patch.object(R,'load',return_value=p),patch.object(R,'sha') as hashed:
            with self.assertRaisesRegex(ValueError,'test dataset'):R.validate('/synthetic/resume/plan.json',R.identity(p),{})
            hashed.assert_not_called()

    def test_separate_review_path_refused_before_hash_or_read(self):
        R=module('r3_formal_control_readiness')
        p={'review_path':'/synthetic/test.jsonl'}
        with patch.object(R,'sha') as hashed:
            with self.assertRaisesRegex(ValueError,'test dataset'):R.target_identity(p,R.canonical_plan_sha256(p))
            hashed.assert_not_called()
        for name in ('r3_resume_evidence','r3_formal_control_readiness','r3_control_resume_cpu'):
            m=module(name)
            with patch.object(Path,'open',side_effect=AssertionError('forbidden content opened')):
                for fn in (m.sha,m.load):
                    with self.assertRaisesRegex(ValueError,'test dataset'):fn('/synthetic/test.jsonl')

if __name__=='__main__':unittest.main()
