import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('prepare_typed_kev.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class GuardTests(unittest.TestCase):
 def test_existing_launch_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);c=p/'config.json';c.write_text(json.dumps({'out':str(p),'mode':'inference'}));(p/'LAUNCH_RECEIPT.json').write_text('{}')
   with self.assertRaisesRegex(AssertionError,'Existing launch'):m.launch(c)
 def test_successful_container_resume_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);c=p/'config.json';c.write_text(json.dumps({'out':str(p),'mode':'inference','container':'same','image':'image','physical_chip':0}));(p/'run.sh').write_text('script')
   receipt={'container_id':'id','image':'image','command':['bash','script'],'entrypoint':None,'config_sha256':m.sha(c),'wrapper_sha256':m.sha(p/'run.sh')};(p/'LAUNCH_RECEIPT.json').write_text(json.dumps(receipt))
   info={'Id':'id','Image':'image','Config':{'Cmd':receipt['command'],'Entrypoint':None},'State':{'Status':'exited','ExitCode':0},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0'}]}}
   with patch.object(m,'inspect',return_value=info),self.assertRaisesRegex(AssertionError,'Successful or live'):m.resume(c)
 def test_foreign_container_resume_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);c=p/'config.json';c.write_text(json.dumps({'out':str(p),'mode':'inference','container':'same','image':'image','physical_chip':0}));(p/'LAUNCH_RECEIPT.json').write_text(json.dumps({'container_id':'original','image':'image'}))
   with patch.object(m,'inspect',return_value={'Id':'foreign'}),self.assertRaises(AssertionError):m.resume(c)

class ExecutionGuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'reference_inference';self.root.mkdir()
  self.run=self.root/'typed_kev08_inference_20261030';self.run.mkdir()
  self.previous=self.root/'typed_kev08_probe_20261030';self.previous.mkdir()
  self.c={'out':str(self.run),'mode':'inference','container':'inference','image':'image','physical_chip':0,
          'base':str(self.root/'base'),'checkpoint':str(self.root/'checkpoint'),'kev_code':str(self.root/'code'),
          'base_id':'base','base_revision':'rev','temperature':2.,'context':{},'runtime':{},'files':{}}
  self.config=self.run/'config.json';self.write(self.config,self.c)
  for p in [self.run,self.previous]:(p/'run.sh').write_text('script')
  self.write(self.previous/'config.json',self.c)
  self.receipt={'container_id':'id','image':'image','command':['bash','script'],'entrypoint':None,'config_sha256':m.sha(self.config),'wrapper_sha256':m.sha(self.run/'run.sh')}
  self.write(self.run/'LAUNCH_RECEIPT.json',self.receipt)
  self.info={'Id':'id','Image':'image','Config':{'Cmd':['bash','script'],'Entrypoint':None,'Env':[]},'State':{'Status':'exited','ExitCode':1},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0','PathInContainer':'/dev/davinci0','CgroupPermissions':'rwm'}],'ShmSize':1024,'Binds':[]}}
  self.alloc=self.root.parent/'CHIP-ALLOCATION.json';self.write(self.alloc,{'allocation':[{'chip':0,'run':'reference_inference/'+self.run.name}]})
  self.write(self.run/'inference-COMPLETE.json',{'rc':1});(self.run/'EXIT').write_text('rc=1 old');self.write(self.run/'STATUS.json',{'stage':'failed'})
  (self.run/'records').mkdir();self.item=self.run/'records/000000.json';self.item.write_text('preserve receipt bytes')
  self.addCleanup(patch.stopall);patch.object(m,'ROOT',self.root).start()
 def write(self,path,value):path.write_text(json.dumps(value))
 def test_failed_resume_archives_terminal_and_preserves_items(self):
  old=(self.run/'inference-COMPLETE.json').read_bytes()
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_output',return_value=''),patch.object(m.subprocess,'check_call') as start:
   m.resume(self.config)
  start.assert_called_once_with(['docker','start','id'])
  archives=list(self.run.glob('resume-before-*'));self.assertEqual(len(archives),1)
  self.assertEqual((archives[0]/'inference-COMPLETE.json').read_bytes(),old)
  self.assertTrue((archives[0]/'EXIT').exists());self.assertTrue((archives[0]/'STATUS.json').exists())
  self.assertFalse((self.run/'inference-COMPLETE.json').exists());self.assertEqual(self.item.read_text(),'preserve receipt bytes')
 def test_wrong_device_resume_refused_without_mutation(self):
  self.info['HostConfig']['Devices'][0]['PathOnHost']='/dev/davinci4'
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_call') as start,self.assertRaises(AssertionError):m.resume(self.config)
  start.assert_not_called();self.assertTrue((self.run/'inference-COMPLETE.json').exists());self.assertFalse(list(self.run.glob('resume-before-*')))
 def test_live_conflict_resume_refused_without_mutation(self):
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_output',return_value='live-id\n'),patch.object(m.subprocess,'check_call') as start,self.assertRaises(AssertionError):m.resume(self.config)
  start.assert_not_called();self.assertTrue((self.run/'EXIT').exists());self.assertFalse(list(self.run.glob('resume-before-*')))
 def setup_launch(self):
  (self.run/'LAUNCH_RECEIPT.json').unlink();self.info['State']['ExitCode']=0
  old=dict(self.receipt,config_sha256=m.sha(self.previous/'config.json'),wrapper_sha256=m.sha(self.previous/'run.sh'))
  self.write(self.previous/'LAUNCH_RECEIPT.json',old)
  self.write(self.run/'PARENT_REVIEW.json',{'approved_config_sha256':m.sha(self.config)})
  self.write(self.previous/'PROBE.json',{'passes':[{},{}],'max_probability_delta':0.})
  self.write(self.previous/'probe-COMPLETE.json',{'rc':0,'outputs':{'PROBE.json':m.sha(self.previous/'PROBE.json')}});(self.previous/'EXIT').write_text('rc=0 old')
  self.write(self.alloc,{'allocation':[{'chip':0,'run':'reference_inference/'+self.previous.name}]})
 def test_predecessor_identity_mismatch_blocks_launch(self):
  self.setup_launch();self.info['Id']='foreign'
  before=self.alloc.read_bytes()
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_call') as start,self.assertRaises(AssertionError):m.launch(self.config)
  start.assert_not_called();self.assertEqual(self.alloc.read_bytes(),before);self.assertFalse((self.run/'LAUNCH_RECEIPT.json').exists())
 def test_predecessor_protocol_mismatch_blocks_launch(self):
  self.setup_launch();old=dict(self.c,temperature=3.);self.write(self.previous/'config.json',old)
  receipt=json.loads((self.previous/'LAUNCH_RECEIPT.json').read_text());receipt['config_sha256']=m.sha(self.previous/'config.json');self.write(self.previous/'LAUNCH_RECEIPT.json',receipt)
  before=self.alloc.read_bytes()
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_call') as start,self.assertRaisesRegex(AssertionError,'Probe protocol mismatch: temperature'):m.launch(self.config)
  start.assert_not_called();self.assertEqual(self.alloc.read_bytes(),before)
 def test_formal_launch_records_correct_release_condition(self):
  self.setup_launch()
  with patch.object(m,'inspect',return_value=self.info),patch.object(m.subprocess,'check_output',side_effect=['','id']),patch.object(m.subprocess,'check_call') as start:
   m.launch(self.config)
  start.assert_called_once_with(['docker','start','id'])
  allocation=json.loads(self.alloc.read_text());self.assertEqual(allocation['updated_by'],'E26 guarded inference launch');self.assertIn('independent audit',allocation['allocation'][0]['release_when'])

if __name__=='__main__':unittest.main()
