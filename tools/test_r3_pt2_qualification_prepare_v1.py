import copy, hashlib, json, tempfile, unittest
from pathlib import Path
from tools import r3_pt2_qualification_prepare_v1 as M

class Prepare(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  def doc(name,value):
   p=self.root/name;p.write_text(json.dumps(value));return M.ref(p)
  self.doc=doc
  controller=self.root/'controller.py';controller.write_text('import json\nfrom pathlib import Path\ndef verify(p,h):\n return json.loads(Path(p).read_text())\n')
  q=self.root/'qualifier.py';q.write_text('# synthetic verifier fixture only\n');qref=M.ref(q)
  files={str(q):qref['sha256']};members={};accepted={}
  for name in M.NAMES:
   p=self.root/(name+'.json')
   if name!='pt_s2':p.write_text(json.dumps({'member':name,'original':True}));accepted[name]=M.ref(p);files[str(p)]=M.sha(p)
   members[name]={'descriptor':str(p),'arm':'K1-PT' if name=='pt_s2' else 'fixture','seed':2}
  required=[];changes=[];wake=[]
  for i in range(16):
   old=str(self.root/('old'+str(i)));new=self.root/('new'+str(i));new.write_text('{}')
   required.append({'path':old,'member':'pt_s2','purpose':'fixture'});changes.append({'field':'required_paths','index':i,'old':old,'new':str(new)})
   if i<3:wake.append(old);changes.append({'field':'event_wake_paths','index':i,'old':old,'new':str(new)})
  base={'members':members,'required_paths':required,'event_wake_paths':wake,'immutable_files':files,'controller':str(controller),'controller_sha256':M.sha(controller),'bundle_path':str(self.root/'BUNDLE.json'),'adjudication_path':str(self.root/'ADJUDICATION.json'),'state_root':str(self.root/'state'),'qualifier':qref,'activation_authorized':False,'test_read':False,'scientific_acceptance':False}
  bref=doc('base.json',base);migration={'source_config':bref,'unchanged_accepted_members':accepted,'changes':changes};mref=doc('migration.json',migration)
  plan=doc('plan.json',{'out':str(self.root/'training')});execution=doc('execution.json',{});report=doc('selection_report.json',{})
  entry={'arm':'K1-PT','seed':2,'plan':plan['path'],'execution':execution['path'],'report':report['path'],'model':{'base_path':'fixture-base'}}
  training={'entry_fields':{'arm':'K1-PT','seed':2,'plan':plan['path']},'files':{plan['path']:plan['sha256']}}
  tref=doc('training.json',training);self.entry=entry
  auth=doc('auth.json',{'scientific_acceptance':False,'test_read':False});bundle=doc('member-bundle.json',{'member':'pt_s2','entry':entry,'independent_decision':{'fixture':True},'files':{r['path']:r['sha256'] for r in [plan,execution,report]},'scientific_acceptance':False,'test_read':False})
  b=M.read(bundle['path']);descriptor=doc('descriptor.json',{'member':'pt_s2','status':'EXACT_MEMBER_ACCEPTED_PENDING_PARENT_BINDING','entry':entry,'decision':b['independent_decision'],'files':b['files'],'consumer':qref,'authentication':auth,'bundle':bundle,'scientific_acceptance':False,'test_read':False})
  check=doc('check.json',{'full_member_passed':True});end=doc('exit.json',{'exit_code':0})
  acceptance=doc('acceptance.json',{'status':'PASS','full_member_passed':True,'full_report_exact':True,'consumer':qref,'consumer_check':check,'consumer_exit':end,'authentication':auth,'bundle':bundle,'descriptor':descriptor,'scientific_acceptance':False,'test_read':False})
  index=doc('index.json',{'acceptance':acceptance,'authentication':auth,'bundle':bundle,'descriptor':descriptor})
  self.c={'schema':'pt2-next-qualification-prepare-v1','activation_authorized':False,'base':bref,'migration':mref,'training_inputs':tref,'member_index':index,'qualifier':qref,'qualifier_dependencies':[],'pt2_execution':execution['path'],'pt2_report':report['path'],'output':str(self.root/'output')}
 def test_missing_member_is_wait_and_no_config(self):
  self.c['member_index']=None;self.assertEqual(M.build(self.c)['status'],'WAIT');self.assertFalse(Path(self.c['output']).exists())
 def test_missing_actual_artifact_is_wait(self):
  Path(M.bound(self.c['migration'])['changes'][0]['new']).unlink();self.assertEqual(M.build(self.c)['status'],'WAIT')
 def test_build_migrates_and_preserves_eight_bytes_without_authority(self):
  result=M.build(self.c);self.assertEqual(result['unchanged_accepted_descriptors'],8)
  c=M.read(result['configuration']['path']);m=M.bound(self.c['migration'])
  for name,r in m['unchanged_accepted_members'].items():self.assertEqual(Path(c['members'][name]['descriptor']).read_bytes(),Path(r['path']).read_bytes())
  old={x['old'] for x in m['changes']};self.assertFalse(old.intersection([x['path'] for x in c['required_paths']]+c['event_wake_paths']))
  self.assertFalse(Path(c['bundle_path']).exists());self.assertFalse(Path(c['adjudication_path']).exists());self.assertFalse(result['candidate_eligibility_granted'])
  self.assertTrue(all(c['immutable_files'][p]==h for p,h in M.bound(self.c['base'])['immutable_files'].items()))
 def test_changed_descriptor_rejected(self):
  r=next(iter(M.bound(self.c['migration'])['unchanged_accepted_members'].values()));Path(r['path']).write_text('{}')
  with self.assertRaisesRegex(ValueError,'descriptor'):M.status(self.c)
 def test_bad_member_binding_rejected(self):
  self.c['pt2_report']='/different'
  with self.assertRaisesRegex(ValueError,'DEV path'):M.build(self.c)
 def test_existing_output_not_overwritten(self):
  Path(self.c['output']).mkdir()
  with self.assertRaisesRegex(ValueError,'output exists'):M.build(self.c)
 def test_closure_mutation_rejected_before_output(self):
  Path(self.entry['execution']).write_text('{"changed":true}')
  with self.assertRaisesRegex(ValueError,'closure'):M.build(self.c)
  self.assertFalse(Path(self.c['output']).exists())
 def test_migration_old_path_mismatch_rejects(self):
  m=M.bound(self.c['migration']);m['changes'][0]['old']='/wrong';self.c['migration']=self.doc('wrong-migration.json',m)
  with self.assertRaisesRegex(ValueError,'stale migration'):M.status(self.c)
if __name__=='__main__':unittest.main()
