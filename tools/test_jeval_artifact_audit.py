import importlib.util,tempfile,unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit_jeval_reference_preflight.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ArtifactAuditTests(unittest.TestCase):
 def test_population_requires_exact_data_bytes(self):
  rows=[{'id':str(i)} for i in range(m.TOTAL)]
  report={'rows':m.TOTAL,'data_sha256':'different'}
  terminal={'progress':m.TOTAL,'total':m.TOTAL}
  with self.assertRaisesRegex(ValueError,'Exact dataset'):m.population(report,terminal,rows,'different')
 def test_terminal_total_cannot_disagree_with_progress(self):
  rows=[{'id':str(i)} for i in range(m.TOTAL)]
  with self.assertRaisesRegex(ValueError,'Population'):m.population({'rows':m.TOTAL,'data_sha256':m.DATA_SHA},{'progress':m.TOTAL,'total':1},rows,m.DATA_SHA)
 def test_duplicate_original_ids_rejected(self):
  with self.assertRaisesRegex(ValueError,'Duplicate'):m.population({'rows':m.TOTAL,'data_sha256':m.DATA_SHA},{'progress':m.TOTAL,'total':m.TOTAL},[{'id':'same'}]*m.TOTAL,m.DATA_SHA)
 def test_missing_native_dependency_rejected_even_if_manifest_hashes_valid(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);c={'family':'kev','dependency_roles':['base','code','checkpoint'],'data':str(root/'data'),'preregistration':str(root/'protocol'),'files':{}}
   for role in c['dependency_roles']:
    p=root/role;p.mkdir();(p/'required.bin').write_text('frozen');c[role]=str(p)
   for n in ['data','protocol','jeval_reference_preflight.py','prepare_jeval_reference_preflight.py','test_jeval_reference_preflight.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh']:(root/n).write_text('frozen')
   c['files']={str(p):m.digest(p) for p in root.rglob('*') if p.is_file()}
   self.assertEqual(len(m.required_files(c,root)),11)
   del c['files'][str(root/'code/required.bin')]
   with self.assertRaisesRegex(ValueError,'Required dependency'):m.required_files(c,root)
 def test_roles_cannot_omit_checkpoint(self):
  with self.assertRaisesRegex(ValueError,'Dependency roles'):m.required_files({'family':'kev','dependency_roles':['base','code']},Path('/tmp'))
 def test_unsupported_width_must_preserve_reason_and_count(self):
  req={'state':'x','questions':{'q':{'type':'choice','criteria':{str(i):'' for i in range(27)}}}}
  item={'status':'unsupported','reason':'native_v1_candidate_limit_26','candidate_count':27}
  m.reason_check('nimble',req,item)
  item['status']='eligible'
  with self.assertRaisesRegex(ValueError,'Candidate-width'):m.reason_check('nimble',req,item)
 def test_length_status_must_match_native_limit(self):
  req={'state':'x','questions':{'q':{'type':'noul'}}}
  item={'status':'eligible','reason':'within_native_budget','candidate_count':2,'max_tokens':4097}
  with self.assertRaisesRegex(ValueError,'Length classification'):m.reason_check('openjev',req,item)

if __name__=='__main__':unittest.main()
