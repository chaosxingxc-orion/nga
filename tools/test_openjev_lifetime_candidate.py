"""CPU-only structural checks; no tensor numerical/memory equivalence claimed."""
import ast
import copy
import importlib.util
import inspect
from pathlib import Path
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lifetime', Path(__file__).with_name('openjev_lifetime_candidate.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
SOURCE = Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_native_static_source_20261031/modeling_qwen3_5.py')


class LifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_bytes()

    def test_all_variants_only_insert_deletes_and_compile(self):
        original = m.native_tree(self.source)
        for variant in m.VARIANTS:
            with self.subTest(variant=variant):
                candidate = m.candidate_tree(self.source, variant)
                self.assertTrue(any(isinstance(s, ast.Delete) for s in candidate.body))
                stripped = copy.deepcopy(candidate)
                stripped.body = [s for s in stripped.body if not isinstance(s, ast.Delete)]
                self.assertEqual(m.tree_dump(stripped), m.tree_dump(original))
                compile(ast.Module(body=[candidate], type_ignores=[]), '<test>', 'exec')

    def test_l1_deletes_after_last_use_and_before_rebinding(self):
        candidate = m.candidate_tree(self.source, 'L1')
        deletes = [tuple(n.id for n in s.targets) for s in candidate.body if isinstance(s, ast.Delete)]
        self.assertEqual(deletes, [('value','beta'), ('row','sub'), ('v_beta',), ('k_beta','attn')])
        # Every later load must be preceded by rebinding that deleted name.
        for i, stmt in enumerate(candidate.body):
            if not isinstance(stmt, ast.Delete): continue
            dead = {n.id for n in stmt.targets}
            for later in candidate.body[i+1:]:
                if isinstance(later, ast.Assign):
                    loads = {n.id for n in ast.walk(later.value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                    self.assertFalse(dead & loads)
                    dead -= set(m.assigned_names(later))
                elif isinstance(later, ast.For):
                    # Recurrent body rebinds attn before reading it.
                    for item in later.body:
                        if isinstance(item, ast.Assign):
                            loads = {n.id for n in ast.walk(item.value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                            self.assertFalse(dead & loads)
                            dead -= set(m.assigned_names(item))

    def test_l2_includes_loop_views_and_no_l1_double_delete(self):
        l2 = m.candidate_tree(self.source, 'L2')
        combo = m.candidate_tree(self.source, 'L1L2')
        groups = [[n.id for n in s.targets] for s in l2.body if isinstance(s, ast.Delete)]
        self.assertEqual(len(groups), 1)
        self.assertTrue(set(['q_i','k_i','v_i','v_beta','k_beta','row','sub']) <= set(groups[0]))
        combo_groups = [[n.id for n in s.targets] for s in combo.body if isinstance(s, ast.Delete)]
        self.assertFalse(set(['beta','v_beta','k_beta','row','sub']) & set(combo_groups[-1]))

    def test_source_mutation_and_unknown_variant_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            m.candidate_tree(self.source+b'\n', 'L1')
        with self.assertRaises(ValueError): m.candidate_tree(self.source, 'L3')

    def fixture(self):
        class Tensor:
            def __init__(self, shape):
                self.shape=shape; self.ndim=len(shape); self.device='npu:0'; self.requires_grad=False
        torch=types.SimpleNamespace(Tensor=Tensor, is_inference_mode_enabled=lambda:True, is_grad_enabled=lambda:False)
        args=dict(query=Tensor((15,186,16,128)), key=Tensor((15,186,16,128)), value=Tensor((15,186,16,128)),
                  g=Tensor((15,186,16)), beta=Tensor((15,186,16)), chunk_size=64,
                  initial_state=None, output_final_state=False, use_qk_l2norm_in_kernel=True, kwargs={})
        return torch, types.SimpleNamespace(arguments=args)

    def test_supported_shape_guard_and_rejected_modes(self):
        torch,bound=self.fixture(); m.validate_call(torch,bound)
        bound.arguments['kwargs']={'cu_seqlens':None}; m.validate_call(torch,bound)
        for key,value in [('chunk_size',1),('chunk_size',64.0),('initial_state',object()),
                          ('output_final_state',True),('kwargs',{'cache':True}),('kwargs',{'cu_seqlens':[0,1]}),('use_qk_l2norm_in_kernel',1)]:
            torch,bound=self.fixture();bound.arguments[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_call(torch,bound)
        torch,bound=self.fixture();torch.is_grad_enabled=lambda:True
        with self.assertRaises(ValueError):m.validate_call(torch,bound)
        torch,bound=self.fixture();torch.is_inference_mode_enabled=lambda:False
        with self.assertRaises(ValueError):m.validate_call(torch,bound)

    def test_empty_shape_and_alias_gradient_inputs_rejected(self):
        for key in ['query','key','value','g','beta']:
            torch,bound=self.fixture();bound.arguments[key].requires_grad=True
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_call(torch,bound)
        torch,bound=self.fixture();bound.arguments['query'].shape=(15,0,16,128)
        with self.assertRaises(ValueError):m.validate_call(torch,bound)
        torch,bound=self.fixture();bound.arguments['g'].device='cpu'
        with self.assertRaises(ValueError):m.validate_call(torch,bound)

    def test_build_rejects_unrelated_callable_without_running_it(self):
        def unrelated(*args, **kwargs): raise AssertionError('must not execute')
        with self.assertRaises(ValueError):m.build_candidate(self.source, unrelated, 'L1')

if __name__ == '__main__': unittest.main()
