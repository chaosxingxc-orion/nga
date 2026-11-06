import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('subject',Path(__file__).with_name('consumer.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Recovery(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); r=Path(self.tmp.name); self.root=r/'followup';self.root.mkdir(); self.pkg=r/'cpu-separated';self.pkg.mkdir();self.rec=r/'dev-publication-recovery';self.rec.mkdir(); self.lane='q0p8b-s2'; self.adapter=r/self.lane/'result/adapter';self.adapter.mkdir(parents=True)
  self.path=self.root/(self.lane+'-ERROR.json'); self.err="[Errno 13] Permission denied: '"+str(self.adapter/'PUBLICATION.json')+"'"; self.write(self.path,{'error':self.err,'traceback':"binding=ready(j)\npub=json.loads((adapter/'PUBLICATION.json').read_text())\nPermissionError: "+self.err})
  pins={}
  for k,n in [('queue_sha256','queue_proposal.py'),('wrapper_sha256','phase_wrapper.py'),('config_sha256','config.json')]:
   p=self.pkg/n; self.write(p,{'jobs':[{'id':self.lane,'model':'/model','size':'0.8B','seed':2}]});pins[k]=m.sha(p)
  self.write(self.root/'REVIEW-APPROVED.json',pins)
  self.disp={'schema':'rc1-dev-publication-recovery-v1','lane':self.lane,'state':'pending_retry','error_path':str(self.path),'error_sha256':m.sha(self.path),'original_error':self.err,**pins,'phase_directory_full':str(self.root/('full-'+self.lane)),'phase_directory_smoke':str(self.root/('smoke-'+self.lane))}
  self.dp=self.rec/(self.lane+'-disposition.json');self.write(self.dp,self.disp)
  self.c=type('C',(),{'config':{'adapter_root':str(self.root),'adapter_wrapper_sha256':pins['wrapper_sha256'],'lanes':[{'lane':self.lane,'new_adapter':str(self.adapter),'baseline_id':'base','size':'0.8B','seed':2}]},'refs':{'base':{'model':{'path':'/model'}}}})()
 def tearDown(self):self.tmp.cleanup();m._accesses.clear()
 def write(self,p,x):p.write_text(json.dumps(x))
 def check(self,status='PENDING_MISSING_INPUT'):m._accesses.clear();return m.recovery_disposition(self.c,self.path,{'status':status})
 def test_pending(self):self.assertEqual(self.check()['status'],'PENDING_RETRY')
 def test_unbound_error_refused(self):
  self.disp['error_sha256']='bad';self.write(self.dp,self.disp)
  with self.assertRaises(ValueError):self.check()
 def test_recipe_change_refused(self):
  (self.pkg/'queue_proposal.py').write_text('changed')
  with self.assertRaises(ValueError):self.check()
 def test_real_phase_failure_refused(self):
  with self.assertRaises(ValueError):self.check('REFUSED_CONTRADICTION')
 def test_complete_requires_validated_artifacts_and_bound_receipts(self):
  self.disp['state']='complete';self.write(self.dp,self.disp)
  with self.assertRaises(ValueError):self.check()
  with self.assertRaises((ValueError,KeyError,m.Pending)):self.check('VALIDATED_OPERAND')
  d=self.root/('full-'+self.lane);d.mkdir(); pins={}
  for phase in ('infer','score'):
   for kind in ('LAUNCH','COMMAND','BINDING','EXIT'):
    p=d/(phase+'-'+kind+'.json');self.write(p,{});pins[str(p)]=m.sha(p)
  self.disp['phase_receipts']=pins;self.write(self.dp,self.disp)
  self.assertEqual(self.check('VALIDATED_OPERAND')['status'],'RECOVERED_VALIDATED')
  (d/'score-EXIT.json').write_text('{}\n')
  with self.assertRaises(ValueError):self.check('VALIDATED_OPERAND')
 def test_unknown_permission_failure_refused(self):
  self.write(self.path,{'error':self.err,'traceback':'different failure'})
  m._accesses.clear();self.disp['error_sha256']=m.sha(self.path);self.write(self.dp,self.disp)
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
