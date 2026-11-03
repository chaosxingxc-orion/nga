"""Narrow compatibility regression tests; no campaign or TEST authority."""
import ast
import unittest
from unittest.mock import patch
from tools import r3_dev_qualification as Q

class Compatibility(unittest.TestCase):
 def test_only_exact_directed_source_pairs(self):
  for name,(old,new) in Q.SOURCE_COMPATIBILITY.items():
   self.assertTrue(Q.compatible_source(name,old,new))
   self.assertFalse(Q.compatible_source(name,new,old))
   self.assertFalse(Q.compatible_source('foreign',old,new))
   self.assertFalse(Q.compatible_source(name,old,'0'*64))
   self.assertFalse(Q.compatible_source(name,'0'*64,new))
  self.assertTrue(Q.compatible_source('unchanged','a'*64,'a'*64))
 def test_legacy_report_retains_full_checks(self):
  q=Q.legacy()
  src=(Q.LEGACY/'consumer.py').read_text()
  old=next(x for x in ast.parse(src).body if isinstance(x,ast.FunctionDef) and x.name=='report')
  self.assertEqual(q.report.__code__.co_filename,str(Q.LEGACY/'consumer.py'))
  self.assertIn('report_compatible_source',q.report.__code__.co_names)
  for name in ('evaluation_lineage','verified_report','bound','exact'):
   self.assertIn(name,q.report.__code__.co_names)
  self.assertNotIn('selected_files',q.report.__code__.co_names)
  self.assertGreater(len(old.body),20)
 def test_helper_unbound_refused_before_loading(self):
  with self.assertRaisesRegex(ValueError,'unbound'):
   Q.k0_ownership({}, {}, {},'a','/release',{}, {},next(iter(Q.K0_EXECUTIONS)))
 def test_unknown_execution_refused_before_loading(self):
  with self.assertRaisesRegex(ValueError,'unsupported'):
   Q.k0_ownership({}, {}, {},'a','/release',{}, {},'f'*64)
 def test_actual_evaluation_branch_has_no_exception_fallback(self):
  from pathlib import Path
  node=next(x for x in ast.parse(Path(Q.__file__).read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='evaluation_runtime')
  self.assertFalse(any(isinstance(x,ast.ExceptHandler) for x in ast.walk(node)))
  self.assertEqual(sum(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='k0_ownership' for x in ast.walk(node)),1)
  self.assertEqual(sum(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='ownership' for x in ast.walk(node)),1)

if __name__=='__main__':unittest.main()
