"""Real E28 verifier subprocess over full synthetic 400/2000 artifact fixture.
Test-only launcher substitutes dependency deserialization; production has no bypass.
"""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_typed_nimble_execution as f
v=f.v;d=f.d;ROOT=f.ROOT
class Fixture:
 def write(self,p,x):Path(p).write_text(json.dumps(x,allow_nan=False)+'\n')
 def __init__(self,root):
  self.root=Path(root);self.run=self.root/'run';self.run.mkdir();self.cpath=self.run/'config.json';self.rows=[];self.preds=[];self.pre=[]
  base=self.root/'base';adapter=self.root/'adapter';code=self.root/'code';base.mkdir();adapter.mkdir();(code/'nimble/scoring').mkdir(parents=True)
  self.write(base/'config.json',{'model_type':'qwen3_5'});(base/'tokenizer.json').write_text('{}');(base/'.complete').write_text(v.BASE_REVISION);(base/'model.safetensors').write_text('weights')
  self.write(adapter/'adapter_config.json',{'peft_type':'LORA'});(adapter/'adapter_model.safetensors').write_text('adapter');(adapter/'tokenizer.json').write_text('{}')
  for n in ['parallel_schema.py','release_contract.py','cuda_scorer.py']:(code/'nimble/scoring'/n).write_text('native fixture')
  for n in d.SCRIPTS+['run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh','PREREGISTRATION.md']:(self.run/n).write_text('frozen '+n)
  data=self.root/'data.parquet';scorer=self.root/'scorer.py';scorer.write_text('fixture')
  for i in range(400):
   raw,pred,fields,_=f.fixture();raw['id']='case'+str(i);self.rows.append(raw);self.preds.append(pred);self.pre.append(dict(index=i,id=raw['id'],input_sha256=v.stamp(raw),request_ordered_sha256=v.stamp(d.request(raw),True),fields=fields))
  self.write(data,self.rows)
  self.c=dict(out=str(self.run),mode='inference',base=str(base),adapter=str(adapter),code=str(code),data=str(data),scorer=str(scorer),preregistration=str(self.run/'PREREGISTRATION.md'),base_revision=v.BASE_REVISION,adapter_revision=v.ADAPTER_REVISION,max_length=2048,temperature=1.,runtime={'fixture':'runtime'},image='image',physical_chip=3,container='fixture')
  self.c['files']={str(p):v.sha(p) for p in self.root.rglob('*') if p.is_file()};self.write(self.cpath,self.c);identity=v.stamp(self.c);(self.run/'records').mkdir()
  for i,(raw,pred) in enumerate(zip(self.rows,self.preds)):
   payload=dict(identity=identity,index=i,id=raw['id'],input_sha256=v.stamp(raw),request_ordered_sha256=v.stamp(d.request(raw),True),prediction=pred,seconds=.1);self.write(self.run/'records'/f'{i:06d}.json',dict(payload=payload,sha256=v.stamp(payload)))
  self.write(self.run/'PREFLIGHT.json',dict(identity=identity,rows=400,questions=2000,max_tokens=3,items=self.pre))
  self.write(self.run/'ENVIRONMENT.json',dict(runtime=self.c['runtime'],adapter_revision=v.ADAPTER_REVISION,adapter_sha256=v.sha(adapter/'adapter_model.safetensors'),base_revision=v.BASE_REVISION,temperature=1.,max_length=2048,model=dict(dtype='bfloat16',projection='float32',attention='sdpa',merge='safe',prompt='v1')))
  req=d.request(self.rows[0]);self.write(self.run/'PROBE.json',dict(identity=identity,request=req,request_ordered_sha256=v.stamp(req,True),chips=1,questions_per_pass=5,reserved_gib=1.,passes=[dict(prediction=self.preds[0],seconds=.1),dict(prediction=self.preds[0],seconds=.1)],max_probability_delta=0.))
  self.write(self.run/'report.json',dict(identity=identity,rows=400,questions=2000,serving=v.metric_panels(self.rows,self.preds)))
  self.write(self.run/'LAUNCH_RECEIPT.json',dict(container_id='fixture-id',image='image',command=['bash',str(self.run/'run.sh')],entrypoint=None,config_sha256=v.sha(self.cpath),wrapper_sha256=v.sha(self.run/'run.sh')));self.rebind()
  self.launcher=self.root/'fixture_launcher.py';self.launcher.write_text('''import json,sys,types,importlib.util,argparse
from pathlib import Path
class Table:
 def __init__(self,p):self.p=p
 def to_pylist(self):return json.loads(Path(self.p).read_text())
pq=types.ModuleType('pyarrow.parquet');pq.read_table=Table;pa=types.ModuleType('pyarrow');pa.parquet=pq;sys.modules['pyarrow']=pa;sys.modules['pyarrow.parquet']=pq
tr=types.ModuleType('transformers');tr.AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a,**kw:object());sys.modules['transformers']=tr
ns=types.ModuleType('nimble');sc=types.ModuleType('nimble.scoring');par=types.ModuleType('nimble.scoring.parallel_schema');rel=types.ModuleType('nimble.scoring.release_contract')
def prepare(tok,context,schema,max_length,system_role=True):
 return types.SimpleNamespace(names=list(schema),choices=[x['choices'] for x in schema.values()],full_ids=[[1,2,3] for x in schema],candidate_ids=[[7,8] for x in schema])
par.prepare_prompts=prepare;rel.prompt_builder=lambda *a:prepare
sys.modules.update({'nimble':ns,'nimble.scoring':sc,'nimble.scoring.parallel_schema':par,'nimble.scoring.release_contract':rel})
'''+f"spec=importlib.util.spec_from_file_location('audit',{str(ROOT/'verify_typed_nimble.py')!r});m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nm.DATA_SHA={v.sha(data)!r};m.SCORER_SHA={v.sha(scorer)!r};m.ADAPTER_SHA={v.sha(adapter/'adapter_model.safetensors')!r}\na=argparse.ArgumentParser();a.add_argument('--config');a.add_argument('--out');p=a.parse_args();m.require(not Path(p.out).exists(),'Existing audit preserved');Path(p.out).write_text(json.dumps(m.verify(p.config)))\n")
 def rebind(self):
  self.write(self.run/'inference-COMPLETE.json',dict(rc=0,stage='completed',progress=400,total=400,config_sha256=v.sha(self.cpath),outputs={n:v.sha(self.run/n) for n in ['PREFLIGHT.json','PROBE.json','report.json']}));(self.run/'EXIT').write_text('rc=0 utc=2026-10-30T17:00:00Z\n')
 def cli(self):return subprocess.run([sys.executable,'-P',str(self.launcher),'--config',str(self.cpath),'--out',str(self.root/'AUDIT.json')],capture_output=True,text=True,timeout=30)
class ChainTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=Fixture(self.temp.name)
 def rejects(self,fragment):
  r=self.f.cli();self.assertNotEqual(r.returncode,0);self.assertIn(fragment,r.stderr);self.assertFalse((self.f.root/'AUDIT.json').exists())
 def test_full_2000_cli(self):
  r=self.f.cli();self.assertEqual(r.returncode,0,r.stderr);a=v.load(self.f.root/'AUDIT.json');self.assertEqual(a['questions'],2000);self.assertTrue(a['review_flags'])
 def test_forged_report_rehashed(self):
  p=self.f.run/'report.json';x=v.load(p);x['serving']['strict']['accuracy']=.125;self.f.write(p,x);self.f.rebind();self.rejects('Metric differs')
 def test_missing_receipt(self):
  (self.f.run/'records/000050.json').unlink();self.rejects('Receipt coverage')
 def test_extra_receipt(self):
  (self.f.run/'records/000400.json').write_text('{}');self.rejects('Receipt coverage')
 def test_prompt_forged_in_both_receipt_and_preflight(self):
  p=self.f.run/'records/000050.json';x=v.load(p);x['payload']['prediction']['prompt_fields'][0]['prompt_token_sha256']='0'*64;x['sha256']=v.stamp(x['payload']);self.f.write(p,x)
  p=self.f.run/'PREFLIGHT.json';x=v.load(p);x['items'][50]['fields'][0]['prompt_token_sha256']='0'*64;self.f.write(p,x);self.f.rebind();self.rejects('independent preflight')
 def test_required_dependency_omission(self):
  x=copy.deepcopy(self.f.c);del x['files'][str(Path(x['base'])/'config.json')];self.f.write(self.f.cpath,x);self.rejects('Required dependency omitted')
 def test_stale_wrapper(self):
  os.utime(self.f.run/'EXIT',ns=(1,1));self.rejects('chronology')
 def test_failed_terminal(self):
  p=self.f.run/'inference-COMPLETE.json';x=v.load(p);x['rc']=1;self.f.write(p,x);self.rejects('Terminal differs')
 def test_wrong_runtime(self):
  p=self.f.run/'ENVIRONMENT.json';x=v.load(p);x['runtime']['fixture']='wrong';self.f.write(p,x);self.rejects('environment/runtime')
class FinisherChainTests(unittest.TestCase):
 def setUp(self):
  import http.server,socketserver,threading
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.fx=Fixture(self.temp.name)
  self.out=self.fx.root/'finish';self.out.mkdir()
  self.info={'Id':'fixture-id','Image':'image','Config':{'Cmd':['bash',str(self.fx.run/'run.sh')],'Entrypoint':None},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci3'}]},'State':{'Status':'exited','ExitCode':0}}
  outer=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def do_GET(self):
    outer.assertEqual(self.path,'/containers/fixture/json');body=json.dumps(outer.info).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  sock=self.fx.root/'docker.sock';server=socketserver.UnixStreamServer(str(sock),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  self.launcher=self.fx.root/'fixture_finisher.py'
  self.launcher.write_text('import importlib.util,functools\n'+f"s=importlib.util.spec_from_file_location('finish',{str(ROOT/'typed_nimble_finish.py')!r})\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.container_info=functools.partial(m.container_info,socket_path={str(sock)!r})\nm.main()\n")
  self.plan=self.out/'plan.json';files=[self.fx.launcher,self.launcher,ROOT/'typed_nimble_finish.py',ROOT/'verify_typed_nimble.py',self.fx.cpath,self.fx.run/'LAUNCH_RECEIPT.json']
  self.fx.write(self.plan,{'out':str(self.out),'config':str(self.fx.cpath),'auditor':str(self.fx.launcher),'files':{str(p):v.sha(p) for p in files}})
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
