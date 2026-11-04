"""Isolated recovery provenance tests, with production numerical executor reuse."""
import unittest,tempfile,pathlib,types,json,hashlib,shutil,copy
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
# Recovery module's siblings use exact frozen module hashes in deployed packages.
def module_at(path):
 m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
  shutil.copyfile(HERE/'bev_native_panel_resume_v1.py',self.root/'bev_native_panel_resume_v1.py')
  src=pathlib.Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_9b_panel_config_20261103_v6/code/bev_native_config_panel.py');shutil.copyfile(src,self.root/'bev_native_config_panel.py');self.M=module_at(self.root/'bev_native_panel_resume_v1.py')
  self.old=self.root/'old';self.old.mkdir();self.out=self.root/'new';(self.out/'items/000000').mkdir(parents=True)
  p=self.out/'items/000000';(p/'record.json').write_text('{"x":1}');rp=self.M.sha(p/'record.json');(p/'COMMITTED.json').write_text(json.dumps({'record.json':rp}));cp=self.M.sha(p/'COMMITTED.json')
  self.source=self.root/'OLD.json';self.source.write_text(json.dumps({'out':str(self.old)}));self.man=self.root/'MAN.json';self.man.write_text(json.dumps({'schema':'native-panel-imported-commits-v1','source_plan':{'path':str(self.source),'sha256':self.M.sha(self.source)},'source_out':str(self.old),'count':1,'items':[{'ordinal':0,'record_sha256':rp,'commit_sha256':cp}]}));self.d={'out':str(self.out),'recovery':{'source_plan':{'path':str(self.source),'sha256':self.M.sha(self.source)},'manifest':{'path':str(self.man),'sha256':self.M.sha(self.man)},'imported_count':1}}
 def test_exact_import(self):self.assertEqual(self.M.check_imports(self.d),1)
 def test_changed_record_refused(self):
  (self.out/'items/000000/record.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'imported bytes'):self.M.check_imports(self.d)
 def test_changed_commit_refused(self):
  (self.out/'items/000000/COMMITTED.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'imported bytes'):self.M.check_imports(self.d)
 def test_wrong_source_refused(self):
  m=json.loads(self.man.read_text());m['source_out']='/foreign';self.man.write_text(json.dumps(m))
  with self.assertRaisesRegex(ValueError,'import provenance'):self.M.check_imports(self.d)
 def test_bad_ordinal_refused(self):
  m=json.loads(self.man.read_text());m['items'][0]['ordinal']=2;self.man.write_text(json.dumps(m))
  with self.assertRaisesRegex(ValueError,'import ordinals'):self.M.check_imports(self.d)
 def test_old_attempt2_refused_before_mutation(self):
  with self.assertRaisesRegex(ValueError,'fresh attempt1'):self.M.run('/doesnotexist','pin',2)
 def test_gold_ancestor_mount_refused(self):
  d={'model':'/model','files':{'/cpu':'pin'},'population':{k:{'path':'/cpu/'+k} for k in ['items','gold','source','contract']},'out':'/new/output'}
  with self.assertRaisesRegex(ValueError,'gold/source mounted'):self.M.mounts(d,'/new/PLAN.json')
 def test_source_readout_identity_preserved(self):
  old={'out':'old','run':'oldrun','container':'oldcontainer'};self.source.write_text(json.dumps(old));d={**self.d,'run':'newrun','container':'newcontainer'}
  with patch.object(self.M.C,'plan_legacy_view',return_value=({'protocol_binding_sha256':'unchanged','contract_sha256':'contract'},'loader','native')):
   v,l,n=self.M.plan_legacy_view(d);self.assertEqual(v['protocol_binding_sha256'],'unchanged');self.assertEqual(v['out'],str(self.out));self.assertEqual((l,n),('loader','native'))
if __name__=='__main__':unittest.main()
