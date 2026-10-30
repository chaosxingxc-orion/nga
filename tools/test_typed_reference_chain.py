"""Actual verifier CLI over complete 400/2000 synthetic artifact trees.

The isolated fixture launcher substitutes only parquet/torch deserialization and
pinned fixture file hashes; production has no bypass or test flag. All identity,
coverage, arithmetic, terminal and dependency checks execute in a subprocess.
"""
import ast
import copy
import math
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixtures',ROOT/'test_typed_reference.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
v=f.v

class Fixture:
 def __init__(self,root):
  self.root=Path(root);self.run=self.root/'run';self.run.mkdir();self.config_path=self.run/'config.json'
  self.rows=[]
  for i in range(400):
   row=f.raw();row.update(id=f'case-{i:04d}',workflow=f'workflow-{i//100}');self.rows.append(row)
  self.data=self.root/'data.parquet';self.write(self.data,self.rows)
  self.scorer=self.root/'scorer.py';self.scorer.write_text('fixture only; original arithmetic independently checked by unit suite')
  base=self.root/'base';checkpoint=self.root/'checkpoint';code=self.root/'code';base.mkdir();checkpoint.mkdir();code.mkdir()
  (base/'.complete').write_text('revision\n');(base/'config.json').write_text('{}');(base/'tokenizer.json').write_text('{}');(base/'weights.safetensors').write_bytes(b'fixture weights')
  self.write(checkpoint/'head.pt',{'base':'base-id','base_revision':'revision','temperature':2.})
  (checkpoint/'adapter_model.safetensors').write_bytes(b'fixture adapter');(checkpoint/'adapter_config.json').write_text('{}');(code/'kev').mkdir()
  for name in ['api.py','model.py','predictors.py','checkpoint.py','data.py']:(code/'kev'/name).write_text('frozen fixture native code')
  for name in ['typed_reference_kev.py','verify_typed_reference.py','run.sh','LAUNCH_EXACT.sh','PREREGISTRATION.md']:(self.run/name).write_text('frozen fixture '+name)
  self.c={'out':str(self.run),'mode':'inference','base':str(base),'checkpoint':str(checkpoint),'kev_code':str(code),
   'data':str(self.data),'scorer':str(self.scorer),'preregistration':str(self.run/'PREREGISTRATION.md'),
   'base_id':'base-id','base_revision':'revision','temperature':2.,'context':f.m.CONTEXT,
   'image':'fixture-image','container':'fixture-container','physical_chip':0,'runtime':{'torch':'fixture','torch_npu':'fixture','transformers':'fixture','peft':'fixture'}}
  self.c['files']={str(p):v.sha(p) for p in self.root.rglob('*') if p.is_file()};self.write(self.config_path,self.c)
  self.identity=v.stamp(self.c);self.predictions=[];pre=[];(self.run/'records').mkdir()
  for i,row in enumerate(self.rows):
   pred=f.pred(row);pred['input_tokens']=100;self.predictions.append(pred)
   req=f.m.request(row);payload={'index':i,'id':row['id'],'identity':self.identity,'input_sha256':v.stamp(row),'request_ordered_sha256':v.stamp(req,False),'prediction':pred,'seconds':.1,'tokens':100,'tokens_sha256':'a'*64}
   self.write(self.run/'records'/f'{i:06d}.json',{'payload':payload,'sha256':v.stamp(payload)})
   pre.append({'index':i,'id':row['id'],'input_sha256':v.stamp(row),'request_ordered_sha256':v.stamp(req,False),'candidate_keys':[v.candidate_keys(q) for q in req['questions'].values()],'tokens':100,'state_tokens':30,'tokens_sha256':'a'*64})
  self.write(self.run/'PREFLIGHT.json',{'identity':self.identity,'rows':400,'questions':2000,'context':self.c['context'],'max_tokens':100,'items':pre})
  self.write(self.run/'ENVIRONMENT.json',{'temperature':2.,'head_sha256':v.sha(checkpoint/'head.pt'),'runtime':self.c['runtime'],'model':{'dtype':'float32','attention':'eager','backend':'torch'}})
  self.write(self.run/'LAUNCH_RECEIPT.json',{'container_id':'fixture-id','image':'fixture-image','config_sha256':v.sha(self.config_path),'wrapper_sha256':v.sha(self.run/'run.sh'),'command':['bash',str(self.run/'run.sh')],'entrypoint':None})
  original=Path('/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py')
  assert v.sha(original)==v.SCORER_SHA
  node=next(x for x in ast.parse(original.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='score_one');namespace={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),str(original),'exec'),namespace)
  self.write(self.run/'report.json',{'identity':self.identity,'rows':400,'questions':2000,'serving':f.m.native_score(self.rows,self.predictions,2.,namespace['score_one']),'raw_T1':f.m.native_score(self.rows,self.predictions,1.,namespace['score_one'])})
  req=f.m.request(self.rows[0]);probe_pred=copy.deepcopy(self.predictions[0])
  self.write(self.run/'PROBE.json',{'identity':self.identity,'request':req,'request_ordered_sha256':v.stamp(req,False),'questions_per_pass':5,'chips':1,'reserved_gib':1.,'tokens':100,'tokens_sha256':'a'*64,'passes':[{'prediction':probe_pred,'seconds':.1},{'prediction':probe_pred,'seconds':.1}],'max_probability_delta':0.})
  self.rebind()
  self.launcher=self.root/'fixture_verifier.py'
  self.launcher.write_text("""import importlib.util,json,sys,types
from pathlib import Path
class Table:
 def __init__(self,p):self.p=p
 def to_pylist(self):return json.loads(Path(self.p).read_text())
pq=types.ModuleType('pyarrow.parquet');pq.read_table=lambda p:Table(p)
pa=types.ModuleType('pyarrow');pa.parquet=pq;sys.modules['pyarrow']=pa;sys.modules['pyarrow.parquet']=pq
torch=types.ModuleType('torch')
def load(p,map_location=None,weights_only=None):
 assert map_location=='cpu' and weights_only is True
 return json.loads(Path(p).read_text())
torch.load=load;sys.modules['torch']=torch
"""+f"s=importlib.util.spec_from_file_location('auditor',{str(ROOT/'verify_typed_reference.py')!r})\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.DATA_SHA={v.sha(self.data)!r}\nm.SCORER_SHA={v.sha(self.scorer)!r}\nm.main()\n")
 def write(self,p,obj):Path(p).write_text(json.dumps(obj,allow_nan=False)+'\n')
 def rebind(self):
  self.write(self.run/'inference-COMPLETE.json',{'rc':0,'config_sha256':v.sha(self.config_path),'stage':'completed','progress':400,'total':400,'outputs':{n:v.sha(self.run/n) for n in ['PREFLIGHT.json','PROBE.json','report.json']}})
  (self.run/'EXIT').write_text('rc=0 utc=2026-10-30T17:00:00Z\n')
 def cli(self,out=None):
  return subprocess.run([sys.executable,'-P',str(self.launcher),'--config',str(self.config_path),'--out',str(out or self.root/'AUDIT.json')],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)

class ChainTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.fx=Fixture(self.temp.name)
 def assert_reject(self,fragment):
  result=self.fx.cli();self.assertNotEqual(result.returncode,0);self.assertIn(fragment,result.stderr);self.assertFalse((self.fx.root/'AUDIT.json').exists())
 def test_complete_real_cli(self):
  result=self.fx.cli();self.assertEqual(result.returncode,0,result.stderr);audit=v.load(self.fx.root/'AUDIT.json');self.assertEqual((audit['rows'],audit['questions']),(400,2000));self.assertTrue(audit['review_flags'])
 def test_existing_audit_not_overwritten(self):
  self.assertEqual(self.fx.cli().returncode,0);p=self.fx.root/'AUDIT.json';before=p.read_bytes();self.assertNotEqual(self.fx.cli().returncode,0);self.assertEqual(before,p.read_bytes())
 def test_hash_consistent_forged_report(self):
  p=self.fx.run/'report.json';x=v.load(p);x['serving']['original_arithmetic_raw_readout']['accuracy']=.125;self.fx.write(p,x);self.fx.rebind();self.assert_reject('Metric differs')
 def test_missing_receipt(self):
  (self.fx.run/'records/000100.json').unlink();self.assert_reject('Receipt coverage')
 def test_extra_receipt(self):
  (self.fx.run/'records/000400.json').write_text('{}');self.assert_reject('Receipt coverage')
 def test_hash_consistent_foreign_record(self):
  p=self.fx.run/'records/000100.json';x=v.load(p);x['payload']['index']=99;x['sha256']=v.stamp(x['payload']);self.fx.write(p,x);self.assert_reject('Receipt identity')
 def test_dependency_omission(self):
  c=copy.deepcopy(self.fx.c);del c['files'][str(Path(c['base'])/'config.json')];self.fx.write(self.fx.config_path,c);self.assert_reject('Required dependency omitted')
 def test_loader_file_deleted_and_removed_from_manifest(self):
  p=Path(self.fx.c['base'])/'config.json';p.unlink();c=copy.deepcopy(self.fx.c);del c['files'][str(p)];self.fx.write(self.fx.config_path,c);self.assert_reject('Missing required loader file')
 def test_wrong_checkpoint_temperature(self):
  p=self.fx.run/'ENVIRONMENT.json';x=v.load(p);x['temperature']=1.;self.fx.write(p,x);self.assert_reject('Environment/checkpoint')
 def test_probe_missing_pass(self):
  p=self.fx.run/'PROBE.json';x=v.load(p);x['passes']=x['passes'][:1];self.fx.write(p,x);self.fx.rebind();self.assert_reject('two passes')
 def test_hash_consistent_wrong_token_binding(self):
  p=self.fx.run/'records/000000.json';x=v.load(p);x['payload']['tokens']=99;x['sha256']=v.stamp(x['payload']);self.fx.write(p,x);self.assert_reject('Actual/preflight token')
 def test_wrong_runtime(self):
  p=self.fx.run/'ENVIRONMENT.json';x=v.load(p);x['runtime']['torch']='wrong';self.fx.write(p,x);self.assert_reject('runtime')
 def test_wrong_launch_binding(self):
  p=self.fx.run/'LAUNCH_RECEIPT.json';x=v.load(p);x['config_sha256']='0'*64;self.fx.write(p,x);self.assert_reject('Launch config')
 def test_failed_terminal(self):
  p=self.fx.run/'inference-COMPLETE.json';x=v.load(p);x['rc']=1;self.fx.write(p,x);self.assert_reject('Terminal differs')
 def test_stale_wrapper(self):
  os.utime(self.fx.run/'EXIT',ns=(1,1));self.assert_reject('chronology')
 def test_conflicting_failure(self):
  (self.fx.run/'FAILED').write_text('failed');self.assert_reject('Conflicting failure')
 def test_forged_preflight_maximum(self):
  p=self.fx.run/'PREFLIGHT.json';x=v.load(p);x['max_tokens']=99;self.fx.write(p,x);self.fx.rebind();self.assert_reject('Preflight maximum')

class FinisherChainTests(unittest.TestCase):
 def setUp(self):
  import http.server,socketserver,threading
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.fx=Fixture(self.temp.name)
  self.out=self.fx.root/'finish';self.out.mkdir()
  self.info={'Id':'fixture-id','Image':'fixture-image','Config':{'Cmd':['bash',str(self.fx.run/'run.sh')],'Entrypoint':None},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0'}]},'State':{'Status':'exited','ExitCode':0}}
  outer=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def do_GET(self):
    outer.assertEqual(self.path,'/containers/fixture-container/json');body=json.dumps(outer.info).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  sock=self.fx.root/'docker.sock';server=socketserver.UnixStreamServer(str(sock),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  self.launcher=self.fx.root/'fixture_finisher.py'
  self.launcher.write_text('import importlib.util,functools\n'+f"s=importlib.util.spec_from_file_location('finish',{str(ROOT/'typed_reference_finish.py')!r})\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.container_info=functools.partial(m.container_info,socket_path={str(sock)!r})\nm.main()\n")
  self.plan=self.out/'plan.json';files=[self.fx.launcher,self.launcher,ROOT/'typed_reference_finish.py',ROOT/'verify_typed_reference.py',self.fx.config_path,self.fx.run/'LAUNCH_RECEIPT.json']
  self.fx.write(self.plan,{'out':str(self.out),'config':str(self.fx.config_path),'auditor':str(self.fx.launcher),'files':{str(p):v.sha(p) for p in files}})
 def run_chain(self):return subprocess.run([sys.executable,'-P',str(self.launcher),'--plan',str(self.plan)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
 def test_full_chain_and_successful_terminal_preserved(self):
  result=self.run_chain();self.assertEqual(result.returncode,0,result.stderr);path=self.out/'FINISH_COMPLETE.json';before=path.read_bytes();terminal=json.loads(before);self.assertEqual(terminal['rc'],0);self.assertEqual(terminal['status'],'COMPLETED_SCOPED_REVIEW_REQUIRED')
  self.assertEqual(v.load(self.out/'INDEPENDENT_AUDIT.json')['questions'],2000)
  for name,h in terminal['outputs'].items():self.assertEqual(v.sha(self.out/name),h)
  self.assertNotEqual(self.run_chain().returncode,0);self.assertEqual(path.read_bytes(),before)
 def test_forged_report_fails_real_audit_stage(self):
  p=self.fx.run/'report.json';x=v.load(p);x['serving']['original_arithmetic_raw_readout']['accuracy']=.125;self.fx.write(p,x);self.fx.rebind()
  result=self.run_chain();self.assertNotEqual(result.returncode,0);terminal=v.load(self.out/'FINISH_COMPLETE.json');self.assertEqual(terminal['rc'],1);self.assertEqual(terminal['stage'],'independent_audit');self.assertFalse((self.out/'INDEPENDENT_AUDIT.json').exists())
 def test_wrong_container_identity(self):
  self.info['Id']='wrong';self.assertNotEqual(self.run_chain().returncode,0);self.assertIn('identity',v.load(self.out/'FINISH_COMPLETE.json')['error'])
 def test_wrong_device(self):
  self.info['HostConfig']['Devices']=[{'PathOnHost':'/dev/davinci1'}];self.assertNotEqual(self.run_chain().returncode,0);self.assertIn('device',v.load(self.out/'FINISH_COMPLETE.json')['error'])
 def test_stale_wrapper(self):
  os.utime(self.fx.run/'EXIT',ns=(1,1));self.assertNotEqual(self.run_chain().returncode,0);self.assertIn('Stale wrapper',v.load(self.out/'FINISH_COMPLETE.json')['error'])

if __name__=='__main__':unittest.main()
