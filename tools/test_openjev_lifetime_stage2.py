#!/usr/bin/env python3
"""Bounded E41 derivation, case guards and identity tests; no NPU."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('stage2',HERE/'openjev_lifetime_stage2_prepare.py');prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)

def compiled(name,case):
 raw=prep.derive(name,(prep.E40/name).read_bytes(),case);m=types.ModuleType(name);m.__file__=str(prep.E40/name);exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

class Tests(unittest.TestCase):
 def plan(self,case):
  c=prep.CASES[case];old=json.loads((prep.E40/'plan.json').read_bytes());old.update(schema=f'e41-full-shape-lifetime-{case}-v1',case=case,base_id=f'Qwen/Qwen3.5-{c["model"]}B',core_shape=[c['batch'],c['length'],c['heads'],128],physical_chip=c['chip'])
  old['input'].update(index=c['index'],shape=[c['batch'],c['length']],candidate_order=[str(i) for i in range(c['batch'])])
  old['expected_core_names']=[str(i) for i in range(c['cores'])];return old
 def test_all_generated_sources_compile_and_only_known_cases(self):
  for case in prep.CASES:
   for name in prep.PINS:compile(prep.derive(name,(prep.E40/name).read_bytes(),case),name,'exec')
  with self.assertRaises(KeyError):prep.derive('openjev_lifetime_protocol.py',(prep.E40/'openjev_lifetime_protocol.py').read_bytes(),'openjev9_max')
 def test_unreviewed_source_rejected(self):
  with self.assertRaises(ValueError):prep.derive('openjev_lifetime_protocol.py',b'evil','openjev9_short')
 def test_exact_finite_cases_accept(self):
  for case in prep.CASES:compiled('openjev_lifetime_protocol.py',case).validate_plan(self.plan(case))
 def test_wrong_case_model_shape_chip_or_cores_rejected(self):
  for case in prep.CASES:
   proto=compiled('openjev_lifetime_protocol.py',case)
   for key,bad in [('case','wrong'),('base_id','Qwen/Qwen3.5-4B'),('core_shape',[15,186,16,128] if case=='openjev9_short' else [24,3480,32,128]),('physical_chip',7),('expected_core_names',['one'])]:
    p=self.plan(case);p[key]=bad
    with self.subTest(case=case,key=key),self.assertRaises(ValueError):proto.validate_plan(p)
 def test_candidate_count_and_input_index_rejected(self):
  for case in prep.CASES:
   proto=compiled('openjev_lifetime_protocol.py',case)
   for field,bad in [('candidate_order',['one']),('index',9027),('shape',[255,2156])]:
    p=self.plan(case);p['input'][field]=bad
    with self.subTest(case=case,field=field),self.assertRaises(ValueError):proto.validate_plan(p)
 def test_receipt_names_and_identities_bind_input(self):
  for case,c in prep.CASES.items():
   proto=compiled('openjev_lifetime_protocol.py',case);p=self.plan(case);t=proto.schedule()[0]
   self.assertEqual(proto.name(t),str(c['index'])+'_original_0')
   self.assertEqual(proto.identity(p,'pin',t)['index'],c['index'])
 def test_verifier_uses_case_index_and_complete_population(self):
  for case,c in prep.CASES.items():
   verifier=compiled('openjev_lifetime_verify.py',case)
   items={str(c['index'])+'_'+mode+'_'+str(rep)+'.json':{'prediction':{'logits':[0.,1.],'answer':{'choice':'b'}},'peak_allocated_gib':3.}
    for mode in ('original','L1','L2','L1L2') for rep in (0,1)}
   self.assertTrue(verifier.reconstruct(items)['exact_outputs'])
   wrong=items.pop(next(iter(items)));items['9027_original_0.json']=wrong
   with self.assertRaises(KeyError):verifier.reconstruct(items)
 def test_launcher_chip_literals_match_case(self):
  for case,c in prep.CASES.items():
   s=prep.derive('openjev_lifetime_launch.py',(prep.E40/'openjev_lifetime_launch.py').read_bytes(),case).decode()
   self.assertIn("'/dev/davinci"+str(c['chip'])+"'",s)
   self.assertIn('current,'+str(c['chip'])+',run',s)
   self.assertIn('physical_chip='+str(c['chip']),s)
 def test_model_runtime_shape_bound(self):
  for case,c in prep.CASES.items():
   s=prep.derive('openjev_lifetime_npu.py',(prep.E40/'openjev_lifetime_npu.py').read_bytes(),case).decode()
   self.assertIn(str([c['batch'],c['length'],c['heads'],128]),s)
   self.assertIn("'Qwen/Qwen3.5-"+str(c['model'])+"B'",s)
 def test_actual_runtime_wrapper_enforces_shape_and_core_order(self):
  for case,c in prep.CASES.items():
   driver=compiled('openjev_lifetime_npu.py',case)
   source=(prep.E40/'modeling_qwen3_5.py').read_bytes()
   original=lambda query,**kwargs:'executed'
   core=type('Qwen3_5GatedDeltaNet',(),{})();core.chunk_gated_delta_rule=original
   backbone=types.SimpleNamespace(training=False,named_modules=lambda:[('native.core',core)])
   cand=types.SimpleNamespace(build_arithmetic=lambda *a:original,validate_call=lambda *a:None)
   torch=types.SimpleNamespace(bfloat16='bf16')
   right=[c['batch'],c['length'],c['heads'],128]
   with patch.object(driver.inspect,'getsourcefile',return_value=str(prep.E40/'modeling_qwen3_5.py')):
    calls=[]
    with driver.lifetime_path(backbone,torch,source,'original',['native.core'],cand,calls):
     self.assertEqual(core.chunk_gated_delta_rule(types.SimpleNamespace(shape=right,dtype='bf16')),'executed')
    self.assertEqual(calls,['native.core']);self.assertIs(core.chunk_gated_delta_rule,original)
    with self.assertRaises(ValueError):
     with driver.lifetime_path(backbone,torch,source,'original',['native.core'],cand,[]):
      core.chunk_gated_delta_rule(types.SimpleNamespace(shape=[right[0]-1,*right[1:]],dtype='bf16'))
    self.assertIs(core.chunk_gated_delta_rule,original)
    with self.assertRaises(ValueError):
     with driver.lifetime_path(backbone,torch,source,'original',['wrong.core'],cand,[]):pass
 def test_input_helper_only_changes_input_functions(self):
  import ast
  for case in prep.CASES:
   a=ast.parse((prep.E40/'openjev_path_trace_run.py').read_bytes());b=ast.parse(prep.derive('openjev_path_trace_run.py',(prep.E40/'openjev_path_trace_run.py').read_bytes(),case))
   for left,right in zip(a.body,b.body):
    if getattr(left,'name',None) not in ('select','prepare_input','input_guard'):
     self.assertEqual(ast.dump(left),ast.dump(right))

if __name__=='__main__':unittest.main()
