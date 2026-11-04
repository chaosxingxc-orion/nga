"""Saved-record parity and adversarial rejection checks; no model inference."""
import copy,dataclasses,hashlib,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('bev_native_cpu_replay_v1.py')
s=importlib.util.spec_from_file_location('cpu_replay',P);M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
PLAN=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/native_9b_panel_resume_20261104_v1/PLAN.json')

class ReplayOutputBoundary(unittest.TestCase):
 def test_worker_rejects_path_escape_before_any_output_write(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);prod=root/'production';prod.mkdir();(root/'scratch').mkdir()
   alias=root/'alias';alias.symlink_to(prod,target_is_directory=True)
   plan=root/'PLAN.json';M.put(plan,{'out':str(prod),'modules':{'runtime':{'path':'absent','sha256':'absent'}}})
   for target in (root/'scratch/../production/unintended',alias/'unintended'):
    cfg=root/'CONFIG.json';M.put(cfg,{'schema':'native-saved-cpu-replay-v1','read_only_saved_records':True,
      'consumer':{'path':str(P.resolve()),'sha256':M.sha(P.resolve())},
      'plan':{'path':str(plan),'sha256':M.sha(plan)},'output':str(target)})
    with self.assertRaisesRegex(ValueError,'noncanonical|symlink'):M.worker(str(cfg),M.sha(cfg))
    self.assertEqual(list(prod.iterdir()),[])

class ReferenceReuse(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=M.read(PLAN);cls.C=M.load(cls.d['modules']['runtime']);cls.view,_,cls.N=cls.C.plan_legacy_view(cls.d)
  cls.X=M.load(cls.d['modules']['panel']);cls.ref=M.VerifiedReference.create(cls.N,cls.d['modules']['native'],cls.d['upstream'])
  cls.requests=cls.X.rows(cls.d['population']['requests']['path']);cls.root=Path(cls.d['out'])/'items'
 def test_three_kinds_original_and_reuse_exact(self):
  seen=set()
  for req in self.requests:
   if req['kind'] in seen:continue
   seen.add(req['kind']);dest=self.root/f"{req['i']:06d}"
   self.assertEqual(self.X.load_item(dest,req,self.view,self.N),M.load_item(dest,req,self.view,self.N,self.ref))
  self.assertEqual(len(seen),3)
 def test_reference_initializes_once_for_multiple_records(self):
  calls=[]
  def profile(frame,event,arg):
   if event=='call' and frame.f_code.co_name=='reference' and frame.f_code.co_filename==self.N.__file__:calls.append(1)
  sys.setprofile(profile)
  try:
   ref=M.VerifiedReference.create(self.N,self.d['modules']['native'],self.d['upstream'])
   for req in self.requests[:4]:M.load_item(self.root/f"{req['i']:06d}",req,self.view,self.N,ref)
  finally:sys.setprofile(None)
  self.assertEqual(len(calls),1)
 def test_reference_required(self):
  req=self.requests[0];p=M.read(self.root/'000000/record.json')['prediction']
  with self.assertRaisesRegex(ValueError,'verified invocation'):M.validate_prediction(p,req,self.view,self.N,None)
 def test_foreign_native_rejected(self):
  other=M.load(self.d['modules']['native'])
  with self.assertRaisesRegex(ValueError,'foreign'):self.ref.for_native(other)
 def test_mutated_reference_rejected(self):
  ref=dataclasses.replace(self.ref,value=type('Fake',(),{'restricted_logprobs':lambda x:x,'Tacit':self.ref.value.Tacit})())
  with self.assertRaisesRegex(ValueError,'mutated'):ref.for_native(self.N)
 def test_wrong_native_pin(self):
  with self.assertRaisesRegex(ValueError,'native source'):M.VerifiedReference.create(self.N,dict(self.d['modules']['native'],sha256='0'*64),self.d['upstream'])
 def test_wrong_source_and_later_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'anyjev').mkdir();up={'root':str(root),'files':{}}
   for name,record in self.d['upstream']['files'].items():
    dest=root/'anyjev'/name;shutil.copyfile(record['path'],dest);up['files'][name]={'path':str(dest),'sha256':record['sha256']}
   ref=M.VerifiedReference.create(self.N,self.d['modules']['native'],up)
   with (root/'anyjev/question.py').open('a') as f:f.write('\n# mutation\n')
   with self.assertRaisesRegex(ValueError,'upstream source changed'):ref.check_sources()
   with self.assertRaisesRegex(ValueError,'upstream source differs'):M.VerifiedReference.create(self.N,self.d['modules']['native'],up)
 def test_nonfinite_operands(self):
  req=self.requests[0];saved=M.read(self.root/'000000/record.json')['prediction']
  for bad in [float('nan'),float('inf'),-float('inf'),'inf',1e300]:
   p=copy.deepcopy(saved);p['label_values'][0]=bad
   with self.assertRaises(ValueError):M.validate_prediction(p,req,self.view,self.N,self.ref)
 def test_prediction_integer_and_join_and_arithmetic(self):
  req=self.requests[0];saved=M.read(self.root/'000000/record.json')['prediction']
  for key,value in [('i',False),('first_index',False),('qid','wrong'),('request_sha256','0'*64),('first_margin',-1),('index',99)]:
   p=copy.deepcopy(saved);p[key]=value
   with self.assertRaises(ValueError):M.validate_prediction(p,req,self.view,self.N,self.ref)
 def test_corrupt_record_receipt_and_model(self):
  req=self.requests[0]
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'000000';shutil.copytree(self.root/'000000',dest)
   with (dest/'record.json').open('a') as f:f.write(' ')
   with self.assertRaisesRegex(ValueError,'changed record'):M.load_item(dest,req,self.view,self.N,self.ref)
   rec=M.read(dest/'record.json');rec['model_sha256']='0'*64;M.put(dest/'record.json',rec);M.put(dest/'COMMITTED.json',{'record.json':M.sha(dest/'record.json')})
   with self.assertRaisesRegex(ValueError,'generation'):M.load_item(dest,req,self.view,self.N,self.ref)
 def test_record_symlink(self):
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'000000';dest.symlink_to(self.root/'000000')
   with self.assertRaisesRegex(ValueError,'missing'):M.load_item(dest,self.requests[0],self.view,self.N,self.ref)

if __name__=='__main__':unittest.main(verbosity=2)
