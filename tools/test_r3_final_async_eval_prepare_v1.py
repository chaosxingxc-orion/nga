"""Execute generated verification-only entry with synthetic source dependencies."""
import importlib.util,json,sys,tempfile,types,unittest,hashlib
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('async_prepare',Path(__file__).with_name('r3_final_async_eval_prepare_v1.py'));P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
s=importlib.util.spec_from_file_location('async_transaction',Path(__file__).with_name('r3_final_async_transaction_v1.py'));X=importlib.util.module_from_spec(s);s.loader.exec_module(X)

class Generated(unittest.TestCase):
 def test_verification_entry_executes_first_source_read_without_ticket_escape(self):
  with tempfile.TemporaryDirectory() as td,ExitStack() as stack:
   root=Path(td);run=root/'run';run.mkdir();rnd=root/'round';rnd.mkdir();final=rnd/'FINAL.json';final.write_text('{}');finalpin=hashlib.sha256(final.read_bytes()).hexdigest()
   owner=dict(run_dir=str(run),model_sha256='a'*64,execution_sha256='b'*64,final_sha256=finalpin)
   leases={s:stack.enter_context(X.G.execution(str(rnd),suite=s,**owner)) for s in X.SUITES}
   producer={'header':{'model':'synthetic'}};result={'n':1200,'headline_accuracy':.5,'producer_report_sha256':X.G.digest(producer)}
   X.G.atomic(run/'TEST-PRODUCER-REPORT.json',producer)
   X.G.atomic(run/X.SCORED,dict(X.binding(owner),results={s:result for s in X.SUITES},producer_report_sha256=X.G.digest(producer),scientific_acceptance=False))
   calls=[];token=object()
   class Ticket:
    def __init__(self,identity,suite,split,secret):
     self.identity,self.suite,self.split=identity,suite,split
     if secret is not token:raise ValueError('token differs')
   def verify(ticket,out,**kw):
    calls.append(('verify',ticket.suite));return {'source_verification':{'checked':True},'paired_vector':{},'reference_metrics':{}}
   fm=types.ModuleType('r3_final_metrics');fm.verify=verify;fm.validate_header=lambda *a,**k:None
   prompt=types.ModuleType('prompt')
   identity={'sha256':'a'*64,'path':str(root/'model')}
   env={'__builtins__':__builtins__,'json':json,'tempfile':__import__('tempfile'),'FINAL_NAME':'FINAL.json','C':types.SimpleNamespace(sha256_file=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest(),KEV_DIR='never-opened'),
     'model_identity':lambda *a:identity,'_abs':lambda p:str(Path(p).resolve()),'is_named':lambda f,i:True,'read_final':lambda p:{},'TestTicket':Ticket,'_TOKEN':token,'verify_test_result':lambda *a:None}
   exec(P.extension(),env)
   args=types.SimpleNamespace(out=str(run),round_dir=str(rnd),model_path=str(root/'model'),adapter=None,arm='K0')
   log=types.SimpleNamespace(model_sha='a'*64,execution_sha='b'*64,final_sha=finalpin,run=run,root=rnd,model_path=str(root/'model'),read=lambda s:None)
   with patch.dict(sys.modules,{'r3_test_transaction':X.T,'r3_final_metrics':fm,'prompt':prompt}):
    response=env['verify_scored_test_result'](args,suite='decision-v7',result=result,leases=leases,owner=owner,completion_log=log)
    self.assertEqual(calls,[('verify','decision-v7')]);self.assertEqual(set(response),{'source','metrics'})
    self.assertFalse((run/'TEST-STAGED-RESULTS.json').exists())
    changed=json.loads((run/X.SCORED).read_text());changed['owner']['execution_sha256']='f'*64;X.G.atomic(run/X.SCORED,changed)
    with self.assertRaisesRegex(ValueError,'staging identity'):
     env['verify_scored_test_result'](args,suite='decision-v7',result=result,leases=leases,owner=owner,completion_log=log)
    self.assertEqual(len(calls),1)
 def test_builder_preserves_existing_verified_recovery_and_rejects_bad_pin(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'source.py';p.write_text(P.P.RECOVERY);out=Path(td)/'new.py';pin=hashlib.sha256(p.read_bytes()).hexdigest()
   with self.assertRaisesRegex(ValueError,'source changed'):P.prepare(p,out,'0'*64)
   P.prepare(p,out,pin);self.assertTrue(out.read_bytes().startswith(p.read_bytes()))
   self.assertEqual(out.read_text().count('def verify_reserved_test_result('),1)
   self.assertEqual(out.read_text().count('def verify_scored_test_result('),1)

if __name__=='__main__':unittest.main()
