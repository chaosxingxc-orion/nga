import ast
import contextlib
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('compat', HERE / 'compat.py')
compat = importlib.util.module_from_spec(spec); spec.loader.exec_module(compat)

class Embedding: pass
class A: pass
class B: pass
class Other: pass
class Model:
    def __init__(self, default, tied):
        self._no_split_modules = default
        self.config = types.SimpleNamespace(tie_word_embeddings=tied)
        self.a, self.b, self.e, self.other = A(), B(), Embedding(), Other()
    def named_modules(self):
        return iter([('', self), ('a', self.a), ('other', self.other), ('b', self.b), ('e', self.e)])

class Regression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = Path(self.tmp.name)/'upstream.py'
        p.write_text((HERE/'upstream_apply_fsdp2.py.txt').read_text())
        self.calls = []
        ns = {'CPUOffloadPolicy': object(), 'nn': types.SimpleNamespace(Embedding=Embedding),
              'maybe_patch_fsdp_module': lambda x: contextlib.nullcontext(),
              'fully_shard': lambda m, **kw: self.calls.append((m, kw))}
        exec(compile(p.read_text(), str(p), 'exec'), ns)
        self.impl = types.SimpleNamespace(apply_fsdp2=ns['apply_fsdp2'])
        self.addCleanup(self.tmp.cleanup)
    def test_original_set_fails_before_sharding(self):
        with self.assertRaisesRegex(TypeError, 'set.*not subscriptable'):
            self.impl.apply_fsdp2(Model({'A','B'}, False), {'mesh':'m'}, {})
        self.assertEqual(self.calls, [])
    def test_installed_binding_and_selection(self):
        old = self.impl.apply_fsdp2
        installed = compat.install_fsdp2_set_compat(self.impl)
        self.assertIs(self.impl.apply_fsdp2, installed); self.assertIsNot(old, installed)
        for default, override, selected in [({'A','B'}, None, ('a','b')), ({'Other'}, {'A','B'}, ('a','b')), ({'Other'}, 'A', ('a',)), ({'Other'}, ['A','B'], ('a','b')), ({'Other'}, ('A','B'), ('a','b'))]:
            for tied in (False, True):
                with self.subTest(default=default, override=override, tied=tied):
                    self.calls.clear(); m=Model(default,tied); kw={'mesh':object(), 'reshard_after_forward':False}
                    cfg={} if override is None else {'wrap_policy': {'transformer_layer_cls_to_wrap':override}}
                    self.impl.apply_fsdp2(m,kw,cfg)
                    wanted=[getattr(m,x) for x in selected]+([] if tied else [m.e])+[m]
                    self.assertEqual([x for x,_ in self.calls],wanted)
                    self.assertTrue(all(k == kw and k['mesh'] is kw['mesh'] for _,k in self.calls))
    def test_invalid_before_sharding(self):
        compat.install_fsdp2_set_compat(self.impl)
        for invalid in (None, [], set(), (), [None], ['A',None], {None,'A'}):
            with self.subTest(invalid=invalid):
                self.calls.clear()
                with self.assertRaises(AssertionError): self.impl.apply_fsdp2(Model(invalid,False),{}, {})
                self.assertEqual(self.calls,[])
    def test_candidate_installs_at_actual_call_binding(self):
        root=HERE.parents[2]
        candidate=root/'.local/releases/engineering-base-rc1/tasks/execution/qwen38-fsdp-set-fix/candidate/hooks.py'
        tree=ast.parse(candidate.read_text())
        local_tree=ast.parse((HERE/'compat.py').read_text())
        embedded=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_fsdp2_set_compat')
        standalone=next(n for n in local_tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_fsdp2_set_compat')
        self.assertEqual(ast.dump(embedded,include_attributes=False),ast.dump(standalone,include_attributes=False))
        install=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install')
        calls=[ast.unparse(n) for n in ast.walk(install) if isinstance(n,ast.Call)]
        self.assertIn('install_fsdp2_set_compat(impl)',calls)
        evidence=(root/'.local/releases/engineering-base-rc1/tasks/science/qwen38-first-update-rootcause/source-functions.txt').read_text()
        self.assertIn('apply_fsdp2(module, fsdp_kwargs, self.engine_config)',evidence)
        self.assertIn("impl.apply_fsdp2 = namespace['apply_fsdp2']", candidate.read_text())
    def test_fail_closed_on_source_drift(self):
        p=Path(self.tmp.name)/'drift.py'; p.write_text((HERE/'upstream_apply_fsdp2.py.txt').read_text()+'# drift\n')
        text=p.read_text().replace('model: AutoModelForCausalLM', 'model: changed')
        p.write_text(text); ns={}
        exec(compile(text,str(p),'exec'),ns); self.impl.apply_fsdp2=ns['apply_fsdp2']
        with self.assertRaises(RuntimeError): compat.install_fsdp2_set_compat(self.impl)

if __name__ == '__main__': unittest.main(verbosity=2)
