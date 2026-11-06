import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import producer as p
import core_r3 as C, full_eval_r3 as F, admissible_store_r3 as AS, provenance_r3 as PV, selection_evidence_r3 as SE
class Checks(unittest.TestCase):
 def test_args(self):
  a=p.args_for(F,'mock-base','/tmp/matched-k0-example');self.assertIsNone(a.adapter);self.assertEqual(a.arm,'K0');self.assertEqual(a.k_only.split(','),p.GROUPS);self.assertEqual(a.token_budget,16384)
 def test_header_and_identity(self):
  model=dict(path='m',base_path='m',sha256='a',base_revision='b',kind='checkpoint',weight_shard_pins={'x':'y'});ident={**model,'files':{'x':'y'}};p.check_identity(ident,model)
  for key in ('sha256','base_revision','kind','files'):
   bad=copy.deepcopy(ident);bad[key]='wrong'
   with self.assertRaises(ValueError):p.check_identity(bad,model)
  d={'record_grade':True,'mode':'rightpad','token_budget':16384};h=dict(model={k:model[k] for k in ('path','sha256','kind','base_path','base_revision')},arm='K0',stages='k_score',device='npu',dtype='float32',limit=0,limit_groups=0,partitions=['dev','calibration'],primary_input_mode='full',scorer=d,dry_run_warnings=[]);p.check_header(h,model,d)
  for key,value in [('arm','K1'),('stages','k'),('limit',1),('dtype','bfloat16'),('partitions',['test'])]:
   b=copy.deepcopy(h);b[key]=value
   with self.assertRaises(ValueError):p.check_header(b,model,d)
 def test_batch_validation(self):
  rows=[{'levels':[1,2]},{'levels':[1,2]}]
  for bad in ([[1,2]],[[1,2],[1,float('nan')]],[[1,2],[True,2]]):
   with self.assertRaises(ValueError):p.checked(lambda r,m:bad)(rows)
 def test_real_store_interruption_resume(self):
  rows=[{'kev':{'id':'q'+str(i),'qindex':0},'levels':[{'id':'a'},{'id':'b'}],'gold':'a','source':'x','qname':'q','level_type':'nominal'} for i in range(70)]
  seen=[];desc={'scorer':'mock'}
  def scoring(batch,mode):seen.append([C.kev_key(x) for x in batch]);return [[2.,1.] for x in batch]
  with tempfile.TemporaryDirectory() as t:
   path=C.k_readout_path(t,'decision-v7','dev','clean');s=AS.VerifiedStore(t,path,'a'*64,desc,False)
   try:
    def interrupt(done,total):
     s.commit()
     if done==32:raise RuntimeError('interrupted')
    with self.assertRaises(RuntimeError):C.score_resumable(scoring,rows,C.kev_key,lambda r,v:PV.stamp(C.readout_row(r,v),'a'*64),s,'full',32,interrupt)
   finally:s.close()
   s=AS.VerifiedStore(t,path,'a'*64,desc,False)
   try:C.score_resumable(scoring,rows,C.kev_key,lambda r,v:PV.stamp(C.readout_row(r,v),'a'*64),s,'full',32,lambda d,n:s.commit())
   finally:s.close()
   got=AS.check_receipt(path,'a'*64,desc,recover=False);self.assertEqual(len(SE.validate_population(got,rows,C.kev_key)),70);self.assertEqual(list(map(len,seen)),[32,32,6]);self.assertEqual(seen[1][0],'q32/0')
   with self.assertRaises(Exception):SE.validate_population(got,rows[:-1],C.kev_key)
   got[0]['ids'].reverse()
   with self.assertRaises(Exception):SE.validate_population(got,rows,C.kev_key)
if __name__=='__main__':unittest.main()
