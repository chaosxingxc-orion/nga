import tempfile,unittest,json,types
from pathlib import Path
from unittest.mock import patch
from tools import r3_profile_cpu_continue as C
class Tests(unittest.TestCase):
 def test_correct_installed_module_api(self):
  fn=lambda profiler_path,max_process_number=128,export_type=None:None
  m=types.SimpleNamespace(__file__='/installed/profiler.py',analyse=fn)
  with patch.object(C.importlib,'import_module',return_value=m) as imp,patch.object(C,'sha',return_value=C.PROFILER_PIN):
   self.assertIs(C.profiler_api(),fn);imp.assert_called_once_with('torch_npu.profiler.profiler')
 def test_missing_wrong_api_and_source(self):
  for m,pin in [(types.SimpleNamespace(__file__='x'),C.PROFILER_PIN),(types.SimpleNamespace(__file__='x',analyse=lambda x:None),C.PROFILER_PIN),(types.SimpleNamespace(__file__='x',analyse=lambda *a,**k:None),'foreign')]:
   with patch.object(C.importlib,'import_module',return_value=m),patch.object(C,'sha',return_value=pin):
    with self.assertRaises((ValueError,TypeError)):C.profiler_api()
 def test_exports_nonempty_shape_and_hash(self):
  with tempfile.TemporaryDirectory() as x:
   for n in C.EXPORTS:Path(x,n).write_text('name,duration\nx,1\n')
   self.assertEqual(C.csv_evidence(x)['kernel_details.csv']['rows'],1)
   Path(x,C.EXPORTS[0]).write_text('name,duration\n')
   with self.assertRaisesRegex(ValueError,'empty CSV'):C.csv_evidence(x)
   Path(x,C.EXPORTS[0]).write_text('name,duration\nx\n')
   with self.assertRaisesRegex(ValueError,'width'):C.csv_evidence(x)
 def test_readonly_capture_and_cpu_command(self):
  d={'capture_plan':'/old/plan','environment':{'A':'1'},'container':'c','out':'/new/output','runtime':{'path':'/new/code.py'},'image':'image'}
  with patch.object(C,'read',return_value={'mounts':[{'source':'/old/output','destination':'/old/output'}]}):c=C.command(d,'/new/plan','pin')
  self.assertIn('-d',c)
  for flag in ['--device','--privileged','--rm']:self.assertNotIn(flag,c)
  self.assertIn('type=bind,src=/old/output,dst=/old/output,readonly',c)
  self.assertIn('type=bind,src=/new/output,dst=/new/output',c)
 def fixture(self,r):
  (r/'parse/trace/ASCEND_PROFILER_OUTPUT').mkdir(parents=True)
  for n in C.EXPORTS:(r/'parse/trace/ASCEND_PROFILER_OUTPUT'/n).write_text('n,v\na,1\n')
  d={'out':str(r),'capture_evidence':{'attempts/1/RAW-MANIFEST.json':'raw'}}
  C.put(r/'parse/EXIT.json',{'exit_code':0,'plan_sha256':'p','capture_plan_sha256':C.CAPTURE_PIN,'scientific_acceptance':False})
  report={'schema':'r3-profile-cpu-continuation-report-v1','plan_sha256':'p','capture_plan_sha256':C.CAPTURE_PIN,'raw_manifest_sha256':'raw','exports':C.csv_evidence(r/'parse/trace/ASCEND_PROFILER_OUTPUT'),'scientific_acceptance':False,'test_read':False,'coverage_adjudicated':False};C.put(r/'parse/report.json',report)
  return d,{'raw':'/old/trace'}
 def test_foreign_generation_bool_and_exports_rejected(self):
  for variant in ['valid','terminal','bool','report','raw','export','scope']:
   with self.subTest(variant=variant),tempfile.TemporaryDirectory() as x:
    r=Path(x);d,m=self.fixture(r)
    if variant in ['terminal','bool']:
     p=r/'parse/EXIT.json';v=C.read(p);v['plan_sha256' if variant=='terminal' else 'exit_code']='foreign' if variant=='terminal' else False;C.put(p,v)
    if variant in ['report','raw','scope']:
     p=r/'parse/report.json';v=C.read(p);v[{'report':'plan_sha256','raw':'raw_manifest_sha256','scope':'coverage_adjudicated'}[variant]]='foreign' if variant!='scope' else True;C.put(p,v)
    if variant=='export':(r/'parse/trace/ASCEND_PROFILER_OUTPUT/kernel_details.csv').write_text('n,v\nb,2\n')
    with patch.object(C,'verify',return_value=(d,None,m)):
     if variant=='valid':C.consume('p','p')
     else:
      with self.assertRaises(ValueError):C.consume('p','p')
 def test_approval_requires_exact_command_and_pins(self):
  d={'files':{'x':'h'}};r={'verdict':'PASS','plan_sha256':'p','activation_authorized':True,'scientific_acceptance':False,'expected_command':['cmd'],'files':d['files']}
  with patch.object(C,'sha',return_value='r'),patch.object(C,'read',return_value=r),patch.object(C,'command',return_value=['cmd']):
   C.approval(d,'plan','p','review','r');r['files']={}
   with self.assertRaises(ValueError):C.approval(d,'plan','p','review','r')
 def test_parse_success_and_failure_terminal(self):
  for fail in [False,True]:
   with self.subTest(fail=fail),tempfile.TemporaryDirectory() as x:
    r=Path(x);raw=r/'raw';raw.mkdir();(raw/'blob').write_text('capture');out=r/'output';out.mkdir()
    snapshot=lambda path:{p.name:p.read_text() for p in Path(path).iterdir() if p.is_file()}
    R=types.SimpleNamespace(snapshot=snapshot,accessible_tree=lambda p:None)
    d={'out':str(out),'capture_evidence':{'attempts/1/RAW-MANIFEST.json':'rawpin'}};m={'raw':str(raw),'files':snapshot(raw)}
    def parse_api(path,**kwargs):
     if fail:raise RuntimeError('parser failure')
     e=Path(path)/'ASCEND_PROFILER_OUTPUT';e.mkdir()
     for n in C.EXPORTS:(e/n).write_text('name,value\na,1\n')
    with patch.object(C,'verify',return_value=(d,R,m)),patch.object(C,'profiler_api',return_value=parse_api):
     if fail:
      with self.assertRaises(RuntimeError):C.parse('p','pin')
     else:C.parse('p','pin')
     self.assertEqual(C.read(out/'parse/EXIT.json')['exit_code'],1 if fail else 0)
     self.assertEqual(snapshot(raw),m['files'])
     with self.assertRaises(FileExistsError):C.parse('p','pin')
 def test_actual_rejects_npu_and_writable_capture(self):
  d={'image':'image'};cmd=['docker','run','--mount','type=bind,src=/old,dst=/old,readonly','image','parse']
  a={'Image':'image','Config':{'Cmd':['parse']},'HostConfig':{'Devices':[],'Privileged':False,'AutoRemove':False},'Mounts':[{'Source':'/old','RW':False}]}
  with patch.object(C,'command',return_value=cmd):
   C.validate_actual(a,d,'p','pin');a['Mounts'][0]['RW']=True
   with self.assertRaises(ValueError):C.validate_actual(a,d,'p','pin')
   a['Mounts'][0]['RW']=False;a['HostConfig']['Devices']=[{'PathOnHost':'/dev/davinci6'}]
   with self.assertRaises(ValueError):C.validate_actual(a,d,'p','pin')
if __name__=='__main__':unittest.main()
