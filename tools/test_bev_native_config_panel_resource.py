"""Tests exercise dispatch invariants, including the original allocation lock."""
import copy,fcntl,hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_config_panel_resource as Q, r3_resource_adapter as R

class ExactPredecessor(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.files={}
  self.alloc=str(self.root/'allocation.json');self.run='old';self.name='old-a1';out=self.root/'old'
  self.free={'chip':0,'previous_run':'old','release_evidence':str(out/'host_attempts/1/RELEASE.json'),'released_utc':'generation1'}
  self.ledger={'allocation':[{'chip':2,'run':'unrelated'}],'free':[self.free],'pending_claims':[{'who':'blocked historical'}]}
  def put(name,obj):
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj));h=hashlib.sha256(p.read_bytes()).hexdigest();self.files[str(p)]=h;return {'path':str(p),'sha256':h}
  self.put=put
  plan=put('old/plan.json',{'run':'old','chip':0,'allocation':self.alloc,'out':str(out),'container':'old','image':'image','schema':'native-config-execution-v1','test_read':False,'scientific_acceptance':False})
  claim=put('old/host_attempts/1/CLAIM.json',{'schema':'r3-resource-claim-v1','chip':0,'run':'old','allocation':self.alloc})
  release=put('old/host_attempts/1/RELEASE.json',{'schema':'r3-resource-release-v1','chip':0,'run':'old','claim_sha256':claim['sha256'],'scientific_acceptance':False,'exit_code':0,'container':'old-a1','container_id':'id','allocation_after':{'free':[self.free]}})
  host=put('old/host_attempts/1/EXIT.json',{'exit_code':0,'container_exit_code':0,'runner_terminal_matches':True,'container_id':'id','scientific_acceptance':False})
  runtime=put('old/attempts/1/EXIT.json',{'exit_code':0,'attempt':1,'plan_sha256':plan['sha256'],'scientific_acceptance':False})
  self.p={'schema':'native-panel-exact-predecessor-v2','purpose':'public_fixed_base_test','predecessor_format':'native-config-execution-v1','allocation':self.alloc,'writer_lock':self.alloc+'.lock','chip':0,'run':'new','predecessor_run':'old','attempt':1,'free_entry':self.free,'pending_claims':self.ledger['pending_claims'],'predecessor':{'plan':plan,'claim':claim,'release':release,'host_exit':host,'runtime_exit':runtime,'acceptance':put('acceptance.json',{'verdict':'PASS','schema':'native9b-long-actual-independent-v1','status':'PASS_EXACT_SYNTHETIC_LONG_DEV','lifecycle_verified':True,'all_tensors_and_restricted_arithmetic_exact':True,'plan_sha256':plan['sha256'],'scientific_acceptance':False,'test_read':False,'fullpanel_launch_authorized':False})},'priority_refs':[put('priority.json',{'chip':2,'state':'ready'})],'selection':'Single-card continuation selected; other-chip priorities preserved.','scientific_acceptance':False,'test_read':False}
  self.d={'schema':'native-panel-execution-v2','scope':'public_fixed_base_test','test_read':True,'scientific_acceptance':False,'candidate_test_authority':False,'allocation':self.alloc,'chip':0,'run':'new','queue':put('policy.json',self.p),'files':self.files}
  self.actual={'Id':'id','Image':'image','State':{'Status':'exited','Running':False,'ExitCode':0}}
  self.base=types.SimpleNamespace(**{k:getattr(R,k) for k in ['load','read_bytes','sha_bytes','validate_doc']},docker_inspect=lambda n:self.actual,live_chip_conflict=lambda c,n:False)
 def call(self):return Q.dispatch_guard(self.d,self.base,self.ledger)
 def rewrite(self):self.d['queue']=self.put('policy.json',self.p)
 def test_accepts_unrelated_chip_and_no_global_queue_claim(self):
  self.assertFalse(self.call()['global_empty_queue_asserted']);self.ledger['allocation'][0]['run']='other progressing';self.call()
 def test_wrong_free_generation_and_owner(self):
  for key,value in [('previous_run','foreign'),('released_utc','generation2'),('chip',False)]:
   old=copy.deepcopy(self.ledger)
   self.ledger['free'][0]=dict(self.free,**{key:value})
   with self.assertRaises((ValueError,RuntimeError)):self.call()
   self.ledger=old
  self.ledger['allocation'].append({'chip':0,'run':'owner'})
  with self.assertRaises((ValueError,RuntimeError)):self.call()
 def test_pending_and_priority_source_changes(self):
  self.ledger['pending_claims']=[{'who':'new ready priority'}]
  with self.assertRaisesRegex(ValueError,'pending'):self.call()
  self.ledger['pending_claims']=self.p['pending_claims'];Path(self.p['priority_refs'][0]['path']).write_text('{}')
  with self.assertRaisesRegex(ValueError,'dependency'):self.call()
 def test_boolean_aliases_and_failed_predecessor(self):
  for key,val in [('chip',False),('attempt',True),('scientific_acceptance',0)]:
   old=copy.deepcopy(self.p);self.p[key]=val;self.rewrite()
   with self.assertRaises(ValueError):self.call()
   self.p=old;self.rewrite()
  for key in ['host_exit','runtime_exit','release']:
   ref=self.p['predecessor'][key];obj=R.load(ref['path']);obj['exit_code']=False;self.p['predecessor'][key]=self.put(str(Path(ref['path']).relative_to(self.root)),obj);self.rewrite()
   with self.assertRaises(ValueError):self.call()
 def test_live_holder_and_uncertain_actual_reject(self):
  self.base.live_chip_conflict=lambda c,n:True
  with self.assertRaisesRegex(ValueError,'device'):self.call()
  self.base.live_chip_conflict=lambda c,n:False;self.actual['State']['ExitCode']=False
  with self.assertRaisesRegex(ValueError,'container'):self.call()
 def test_version_scope_and_acceptance_reject(self):
  for key,val in [('purpose','synthetic_long_dev'),('predecessor_format','unknown')]:
   old=copy.deepcopy(self.p);self.p[key]=val;self.rewrite()
   with self.assertRaises(ValueError):self.call()
   self.p=old;self.rewrite()
  ref=self.p['predecessor']['acceptance'];obj=R.load(ref['path']);obj['plan_sha256']='foreign';self.p['predecessor']['acceptance']=self.put(str(Path(ref['path']).relative_to(self.root)),obj);self.rewrite()
  with self.assertRaisesRegex(ValueError,'acceptance'):self.call()
 def test_original_claim_calls_guard_twice_inside_lock(self):
  Path(self.alloc).write_text(json.dumps(self.ledger));seen=[]
  def factory(args):
   def check(doc):
    with open(self.alloc+'.lock','a+') as f:
     with self.assertRaises(BlockingIOError):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    seen.append(copy.deepcopy(doc));return Q.dispatch_guard(self.d,self.base,doc)
   return check
  args=types.SimpleNamespace(alloc=self.alloc,run='new',chip=0,owner='test',purpose='test',proof=str(self.root/'proof.json'))
  with patch.object(R,'successor_guard',side_effect=factory):R.claim(args)
  self.assertEqual(len(seen),2);self.assertEqual(seen[0],self.ledger);self.assertEqual(R.load(args.proof)['successor_precondition']['policy'],'native-panel-exact-predecessor-v2')

if __name__=='__main__':unittest.main()
