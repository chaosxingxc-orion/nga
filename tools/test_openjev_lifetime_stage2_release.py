"""E41 generated release: reuse real E40 bind/transaction fixtures on both chips.

Docker and scientific reconstruction are fixtures; no live allocation is touched.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

HERE=Path(__file__).parent

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

g=load(HERE/'openjev_lifetime_stage2_release_prepare.py','e41_release_derivation')
SOURCE=(HERE/'release_openjev_lifetime.py').read_bytes()


def target(case):
    c=g.CASES[case];path=g.ROOT/('e41_'+case+'_fixture')/'plan.json'
    plan=dict(out=str(path.parent),schema='e41-full-shape-lifetime-'+case+'-v1',case=case,
        base_id=f"Qwen/Qwen3.5-{c['model']}B",physical_chip=c['chip'],candidate_batch_admission=False,
        input=dict(index=c['index'],shape=c['shape']),core_shape=c['shape']+[c['heads'],128],
        expected_core_names=['layer'+str(i) for i in range(c['cores'])])
    return plan,path


class DerivationTests(unittest.TestCase):
    def test_reject_changed_accepted_source(self):
        p,f=target('openjev9_short')
        with self.assertRaisesRegex(ValueError,'source identity'):
            g.derive(SOURCE+b'\n','openjev9_short',p,f,'a'*64)
    def test_reject_wrong_finite_case(self):
        for key,value in [('physical_chip',1),('base_id','Qwen/Qwen3.5-2B'),('candidate_batch_admission',True),('core_shape',[15,186,16,128])]:
            with self.subTest(key=key):
                p,f=target('openjev9_short');p[key]=value
                with self.assertRaises(ValueError):g.derive(SOURCE,'openjev9_short',p,f,'a'*64)
    def test_derived_ast_changes_constants_only(self):
        class Constants(ast.NodeTransformer):
            def visit_Constant(self,node):return ast.copy_location(ast.Constant(value='CONST'),node)
        for case in g.CASES:
            p,f=target(case);result=g.derive(SOURCE,case,p,f,'a'*64)
            self.assertEqual(ast.dump(Constants().visit(ast.parse(SOURCE)),include_attributes=False),
                ast.dump(Constants().visit(ast.parse(result)),include_attributes=False))
            self.assertIn(b"r['schema']=='e40-detached-cpu-verify-v1'",result)
            self.assertIn(b"'e41_release_'",result)
    def test_prepare_is_nonmutating_new_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan_dir=root/'e41_openjev9_short_fixture';plan_dir.mkdir()
            p,unused=target('openjev9_short');path=plan_dir/'plan.json';p['out']=str(plan_dir)
            path.write_text(json.dumps(p));pin=g.sha(path.read_bytes());before=path.read_bytes()
            from unittest.mock import patch
            with patch.object(g,'ROOT',root):
                result=g.prepare('openjev9_short',path,pin,HERE/'release_openjev_lifetime.py',HERE/'e38_evidence.py',root/'code')
                self.assertFalse(result['approved']);self.assertFalse(result['released'])
                self.assertEqual(path.read_bytes(),before)
                with self.assertRaises(FileExistsError):g.prepare('openjev9_short',path,pin,HERE/'release_openjev_lifetime.py',HERE/'e38_evidence.py',root/'code')
    def test_reject_wrong_external_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'plan.json';path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Caller-pinned'):
                g.prepare('openjev9_short',path,'a'*64,HERE/'release_openjev_lifetime.py',HERE/'e38_evidence.py',root/'code')
            self.assertFalse((root/'code').exists())


# Clone the accepted real bind/transaction fixture per finite case. Only chip and
# release-schema literals change. All generation, negative-result, crash-window,
# idempotence, owner-race and authentication assertions run unchanged.
TEMPORARIES=[]
fixture_source=(HERE/'test_release_openjev_lifetime.py').read_text()
for case in g.CASES:
    temp=tempfile.TemporaryDirectory();TEMPORARIES.append(temp);out=Path(temp.name)
    p,f=target(case);(out/'release_openjev_lifetime.py').write_bytes(g.derive(SOURCE,case,p,f,'a'*64))
    (out/'e38_evidence.py').write_bytes((HERE/'e38_evidence.py').read_bytes())
    release=load(out/'release_openjev_lifetime.py','e41_'+case)
    text=fixture_source.replace("r=module('release_openjev_lifetime');qmod=module('jeval_reference_queue')", "qmod=module('jeval_reference_queue')")
    text=text.replace("dict(chip=4,run='other')","dict(chip=7,run='other')")
    chip=g.CASES[case]['chip']
    text=text.replace('physical_chip=1',f'physical_chip={chip}').replace('dict(chip=1,',f'dict(chip={chip},')
    text=text.replace("'chip':1",f"'chip':{chip}").replace('chip=1)',f'chip={chip})')
    text=text.replace('e40-resource-release-','e41-resource-release-').replace("'e40_release_test'","'e41_release_test'")
    ns={'__name__':'e41_fixture_'+case,'__file__':str(HERE/'test_release_openjev_lifetime.py'),'r':release}
    exec(compile(text,str(HERE/'test_release_openjev_lifetime.py'),'exec'),ns)
    cls=ns['Fixture'];cls.__name__='Release_'+case;cls.__qualname__=cls.__name__;globals()[cls.__name__]=cls

del cls
if __name__=='__main__':unittest.main()
