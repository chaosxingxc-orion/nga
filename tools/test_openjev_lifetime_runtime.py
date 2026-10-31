"""Runtime integration using authenticated native arithmetic and native call AST.

The CPU tensor check uses one real full-shape GDN arithmetic call per mode,
not a full transformer, checkpoint, NPU or memory/throughput benchmark.
"""
import ast
import contextlib
import math
import time
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_native_static_source_20261031/modeling_qwen3_5.py')
def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
candidate=module('openjev_lifetime_candidate');driver=module('openjev_lifetime_npu');durable=module('e38_evidence')

class RejectedTests(unittest.TestCase):
    def test_rejected_memory_retained_without_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'attempts').mkdir();(root/'attempts'/'cell.json').write_text('intent')
            value={'prediction':{'logits':[1.]},'peak_reserved_gib':49.,'plan_sha256':'pin'}
            def reject(v,p):raise ValueError('Safety envelope exceeded')
            proto=types.SimpleNamespace(check_metrics=reject)
            with self.assertRaisesRegex(ValueError,'Safety'):
                driver.publish_measurement(root,'cell',value,{},durable,proto,lambda a,b:None)
            x=json.loads((root/'rejected'/'cell.json').read_text())
            self.assertEqual(x['observed_payload'],value);self.assertFalse(x['successful_prefix_eligible'])
            self.assertFalse((root/'items'/'cell.json').exists());self.assertTrue((root/'attempts'/'cell.json').exists())
    def test_nonfinite_prediction_retained_as_explicit_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def reject(a,b):raise ValueError('Invalid prediction')
            with self.assertRaisesRegex(ValueError,'Invalid'):
                driver.publish_measurement(root,'cell',{'prediction':{'logits':[float('nan'),float('inf'),-float('inf')]}},
                    {},durable,None,reject)
            values=json.loads((root/'rejected'/'cell.json').read_text())['observed_payload']['prediction']['logits']
            self.assertEqual(values,[{'nonfinite_float':'nan'},{'nonfinite_float':'inf'},{'nonfinite_float':'-inf'}])
    def test_valid_receipt_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);value={'prediction':{'logits':[1.]}}
            proto=types.SimpleNamespace(check_metrics=lambda a,b:None,stamp=lambda a:'hash')
            driver.publish_measurement(root,'cell',value,{},durable,proto,lambda a,b:None)
            self.assertEqual(json.loads((root/'items'/'cell.json').read_text()),{'payload':value,'sha256':'hash'})
            self.assertFalse((root/'rejected').exists())

class NativePredictFailureTests(unittest.TestCase):
    def native(self, logits):
        # Execute the actual frozen predict AST and its finite/softmax functions,
        # mocking only the completed tensor forward and surrounding model setup.
        source=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_openjev2_probe_20261030/jeval_reference_inference.py')
        plan=json.loads(Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference/e40_lifetime_npu_openjev2_20261031_v2/plan.json').read_text())
        raw=source.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),plan['files'][str(source)])
        tree=ast.parse(raw);klass=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Native')
        method=next(x for x in klass.body if isinstance(x,ast.FunctionDef) and x.name=='predict')
        def require(ok,msg):
            if not ok:raise ValueError(msg)
        ns={'math':math,'require':require,'keys':lambda q:list(q['criteria'])}
        functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('finite','softmax')]
        exec(compile(ast.Module(body=functions+[method],type_ignores=[]),str(source),'exec'),ns)
        obj=types.SimpleNamespace(family='openjev',c={'temperature':1.},consumed=None,
            native=(lambda state,questions:[{'record':1}],),format=lambda records,probs:{'answers':{'q':{'choice':'A'}}})
        class Tensor:
            def float(self):return self
            def cpu(self):return self
            def tolist(self):return list(logits)
        class Model:
            tokenizer=object()
            def __call__(self,records):obj.consumed=['tokens'];return [Tensor()]
        obj.model=Model();obj.predict=types.MethodType(ns['predict'],obj)
        obj.torch=types.SimpleNamespace(inference_mode=contextlib.nullcontext,
            npu=types.SimpleNamespace(synchronize=lambda:None,max_memory_allocated=lambda:7*2**30,
                max_memory_reserved=lambda:9*2**30))
        return obj
    def call(self,obj,root):
        return driver.predict_with_failure_record(obj,{'state':'state','questions':{'q':{'criteria':{'A':'a','B':'b'}}}},
            {'token_sha256':['tokens']},obj.torch,time.monotonic(),root,'4200_original_0',
            {'plan_sha256':'pin','generation':{'container_id':'test'},'attempt_sha256':'attempt'},
            {'shape':[15,186]},['core'],{'baseline_allocated_gib':4.},durable)
    def test_actual_native_nonfinite_predict_retains_logits_and_measurements(self):
        for bad,label in [(float('nan'),'nan'),(float('inf'),'inf'),(-float('inf'),'-inf')]:
            with self.subTest(bad=label),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);obj=self.native([bad,1.]);tokenizer=obj.model.tokenizer
                with self.assertRaisesRegex(ValueError,'Invalid logits'):
                    self.call(obj,root)
                value=json.loads((root/'rejected'/'4200_original_0.json').read_text())
                self.assertEqual(value['status'],'REJECTED_NATIVE_PREDICT')
                self.assertFalse(value['successful_prefix_eligible']);v=value['observed_payload']
                self.assertEqual(v['raw_logits'],[{'nonfinite_float':label},1.])
                self.assertTrue(v['raw_logits_available']);self.assertEqual(v['peak_reserved_gib'],9.)
                self.assertEqual(v['attempt_sha256'],'attempt');self.assertEqual(v['generation'],{'container_id':'test'})
                self.assertGreaterEqual(v['seconds'],0);self.assertFalse((root/'items').exists())
                self.assertIs(obj.model.tokenizer,tokenizer)
    def test_actual_native_success_unchanged_no_rejected_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);obj=self.native([1.,2.]);expected=obj.predict(
                {'state':'state','questions':{'q':{'criteria':{'A':'a','B':'b'}}}}, {'token_sha256':['tokens']})
            self.assertEqual(self.call(obj,root),expected);self.assertFalse((root/'rejected').exists())

@unittest.skipUnless(os.environ.get('E40_TENSOR_TEST')=='1','fixed-image CPU tensor integration only')
class NativeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import torch.nn.functional as F
        cls.torch=torch;torch.set_num_threads(2);torch.set_num_interop_threads(1)
        source=SOURCE.read_bytes();candidate.native_tree(source);cls.source=source
        tree=ast.parse(source)
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('l2norm',candidate.FUNCTION)]
        ns={'torch':torch,'F':F};exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),ns)
        cls.original=staticmethod(ns[candidate.FUNCTION])
        klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Qwen3_5GatedDeltaNet')
        calls=[n for n in ast.walk(klass) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and n.func.attr=='chunk_gated_delta_rule']
        assert len(calls)==1
        cls.native_call=compile(ast.Expression(body=calls[0]),str(SOURCE),'eval')
        torch.manual_seed(4071);shape=(15,186,16,128)
        cls.tensors=[torch.randn(shape,dtype=torch.bfloat16)*.1 for _ in range(3)]
        cls.tensors += [-torch.rand(shape[:3])*.1,torch.rand(shape[:3],dtype=torch.bfloat16)]
    def fixture(self):
        cls=type('Qwen3_5GatedDeltaNet',(),{})
        core=cls();core.chunk_gated_delta_rule=self.original
        backbone=types.SimpleNamespace(training=False,named_modules=lambda:[('core',core)])
        return core,backbone
    def call(self,core,extra=None):
        q,k,v,g,b=self.tensors
        return eval(self.native_call,{'self':core,'query':q,'key':k,'value':v,'g':g,'beta':b,
            'recurrent_state':None,'use_precomputed_states':False,'cache_params':None,'kwargs':extra or {}})
    def test_full_shape_native_call_all_modes_one_guard_exact(self):
        outputs={}
        for mode in ('original','L1','L2','L1L2'):
            core,backbone=self.fixture();calls=[]
            with self.torch.inference_mode(),patch.object(candidate,'validate_call',wraps=candidate.validate_call) as guard:
                with driver.lifetime_path(backbone,self.torch,self.source,mode,['core'],candidate,calls):
                    result,state=self.call(core)
                self.assertEqual(guard.call_count,1);self.assertIsNone(state)
                self.assertEqual(tuple(result.shape),(15,186,16,128))
                outputs[mode]=hashlib.sha256(result.contiguous().view(self.torch.uint8).numpy().tobytes()).hexdigest()
            self.assertEqual(calls,['core']);self.assertIs(core.chunk_gated_delta_rule,self.original)
        self.assertEqual(len(set(outputs.values())),1)
        print(json.dumps({'native_call_full_shape':[15,186,16,128],'outputs':outputs,'guard_calls_per_mode':1}),flush=True)
    def test_non_none_native_kwarg_rejected_and_patch_restored(self):
        for mode in ('original','L1','L2','L1L2'):
            core,backbone=self.fixture()
            with self.torch.inference_mode(),self.assertRaisesRegex(ValueError,'cu_seqlens'):
                with driver.lifetime_path(backbone,self.torch,self.source,mode,['core'],candidate,[]):
                    self.call(core,{'cu_seq_lens_q':[0,186]})
            self.assertIs(core.chunk_gated_delta_rule,self.original)
    def test_arithmetic_without_guard_requires_authenticated_native(self):
        with self.assertRaises(ValueError):candidate.build_arithmetic(self.source,lambda:None,'L1')

if __name__=='__main__':unittest.main()
