"""Full E29 verifier CLI and real finisher subprocess chain; fixture dependencies only."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_typed_openjev_execution as f
v=f.v;d=f.d;ROOT=f.ROOT
class Fixture:
 def write(self,p,x):Path(p).write_text(json.dumps(x,allow_nan=False)+'\n')
 def __init__(self,root):
  self.root=Path(root);self.run=self.root/'run';self.run.mkdir();self.cpath=self.run/'config.json';self.rows=[];self.preds=[];self.pre=[]
  base=self.root/'base';ck=self.root/'checkpoint';code=self.root/'code';base.mkdir();(ck/'adapter').mkdir(parents=True);(code/'jev').mkdir(parents=True)
  self.write(base/'config.json',{'model_type':'qwen3_5'});(base/'tokenizer.json').write_text('{}');(base/'.complete').write_text('revision');(base/'model.safetensors').write_text('weights')
  self.write(ck/'model.json',dict(model_id='base-id',revision='revision',max_length=4096));self.write(ck/'temperature.json',dict(temperature=2.));self.write(ck/'adapter/adapter_config.json',dict(peft_type='LORA'));(ck/'adapter/adapter_model.safetensors').write_text('adapter');(ck/'head.pt').write_text('head')
  for n in ['api.py','model.py','metrics.py']:(code/'jev'/n).write_text('native fixture')
  for n in d.SCRIPTS+['run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh','PREREGISTRATION.md']:(self.run/n).write_text('frozen '+n)
  data=self.root/'data.parquet';scorer=self.root/'scorer.py';scorer.write_text('fixture')
  for i in range(400):
   raw,pred,fields,_=f.fixture();raw['id']='case'+str(i);self.rows.append(raw);self.preds.append(pred);self.pre.append(dict(index=i,id=raw['id'],input_sha256=v.stamp(raw),request_sha256=v.stamp(d.request(raw)),fields=fields))
  self.write(data,self.rows)
  self.c=dict(out=str(self.run),mode='inference',base=str(base),checkpoint=str(ck),code=str(code),data=str(data),scorer=str(scorer),preregistration=str(self.run/'PREREGISTRATION.md'),base_revision='revision',base_id='base-id',max_length=4096,temperature=2.,runtime={'fixture':'runtime'},image='image',physical_chip=0,container='fixture')
  self.c['files']={str(p):v.sha(p) for p in self.root.rglob('*') if p.is_file()};self.write(self.cpath,self.c);identity=v.stamp(self.c);(self.run/'records').mkdir()
  for i,(raw,pred) in enumerate(zip(self.rows,self.preds)):
   payload=dict(identity=identity,index=i,id=raw['id'],input_sha256=v.stamp(raw),request_sha256=v.stamp(d.request(raw)),prediction=pred,seconds=.1);self.write(self.run/'records'/f'{i:06d}.json',dict(payload=payload,sha256=v.stamp(payload)))
  self.write(self.run/'PREFLIGHT.json',dict(identity=identity,rows=400,questions=2000,max_tokens=max(n for x in self.pre for fld in x['fields'] for n in fld['lengths']),candidate_prompts=sum(len(fld['lengths']) for x in self.pre for fld in x['fields']),items=self.pre))
  self.write(self.run/'ENVIRONMENT.json',dict(runtime=self.c['runtime'],base_id='base-id',base_revision='revision',temperature=2.,model=dict(dtype='bfloat16',head='float32',attention='sdpa',adapter='unmerged',max_length=4096)))
  self.write(self.run/'LAUNCH_RECEIPT.json',dict(container_id='fixture-id',image='image',config_sha256=v.sha(self.cpath),wrapper_sha256=v.sha(self.run/'run.sh'),command=['bash',str(self.run/'run.sh')],entrypoint=None))
  self.write(self.run/'PROBE.json',dict(identity=identity,request=d.request(self.rows[0]),request_sha256=v.stamp(d.request(self.rows[0])),passes=[dict(prediction=self.preds[0],seconds=.1)]*2,max_probability_delta=0.,chips=1,questions_per_pass=5,reserved_gib=1.))
  self.write(self.run/'report.json',dict(identity=identity,rows=400,questions=2000,serving=v.metric_panels(self.rows,self.preds,2.),raw_T1=v.metric_panels(self.rows,self.preds,1.)));self.rebind()
  self.launcher=self.root/'fixture_verifier.py';self.launcher.write_text('''import importlib.util,json,sys,types
from pathlib import Path
sys.path.insert(0,'''+repr(str(ROOT))+''')
import test_typed_openjev_execution as fixture
class Table:
 def __init__(self,p):self.p=p
 def to_pylist(self):return json.loads(Path(self.p).read_text())
pq=types.ModuleType('pyarrow.parquet');pq.read_table=lambda p:Table(p)
pa=types.ModuleType('pyarrow');pa.parquet=pq;sys.modules['pyarrow']=pa;sys.modules['pyarrow.parquet']=pq
tr=types.ModuleType('transformers')
class Tok(fixture.f.Tokenizer):
 pad_token_id=0
 @classmethod
 def from_pretrained(cls,*a,**kw):return cls()
tr.AutoTokenizer=Tok;sys.modules['transformers']=tr
'''+f"s=importlib.util.spec_from_file_location('audit',{str(ROOT/'verify_typed_openjev.py')!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.DATA_SHA={v.sha(data)!r};m.SCORER_SHA={v.sha(scorer)!r}\nimport argparse\np=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--out');a=p.parse_args();m.require(not Path(a.out).exists(),'Existing audit preserved');Path(a.out).write_text(json.dumps(m.verify(a.config)))\n")
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
  p=self.f.run/'records/000050.json';x=v.load(p);x['payload']['prediction']['prompt_fields'][0]['token_sha256'][0]='0'*64;x['sha256']=v.stamp(x['payload']);self.f.write(p,x)
  p=self.f.run/'PREFLIGHT.json';x=v.load(p);x['items'][50]['fields'][0]['token_sha256'][0]='0'*64;self.f.write(p,x);self.f.rebind();self.rejects('independent preflight')
 def test_required_dependency_omission(self):
  x=copy.deepcopy(self.f.c);del x['files'][str(Path(x['base'])/'config.json')];self.f.write(self.f.cpath,x);self.rejects('Required dependency omitted')
 def test_stale_wrapper(self):
  os.utime(self.f.run/'EXIT',ns=(1,1));self.rejects('chronology')
 def test_failed_terminal(self):
  p=self.f.run/'inference-COMPLETE.json';x=v.load(p);x['rc']=1;self.f.write(p,x);self.rejects('Terminal differs')
 def test_wrong_runtime(self):
  p=self.f.run/'ENVIRONMENT.json';x=v.load(p);x['runtime']['fixture']='wrong';self.f.write(p,x);self.rejects('environment/runtime')
 def test_wrong_temperature(self):
  p=Path(self.f.c['checkpoint'])/'temperature.json';self.f.write(p,dict(temperature=1.));self.f.c['files'][str(p)]=v.sha(p);self.f.write(self.f.cpath,self.f.c);self.rejects('Checkpoint temperature')
class FinisherChainTests(unittest.TestCase):
 def setUp(self):
  import http.server,socketserver,threading
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.fx=Fixture(self.temp.name);self.out=self.fx.root/'finish';self.out.mkdir()
  self.info={'Id':'fixture-id','Image':'image','Config':{'Cmd':['bash',str(self.fx.run/'run.sh')],'Entrypoint':None},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0'}]},'State':{'Status':'exited','ExitCode':0}}
  outer=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def do_GET(self):
    outer.assertEqual(self.path,'/containers/fixture/json');body=json.dumps(outer.info).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  sock=self.fx.root/'docker.sock';server=socketserver.UnixStreamServer(str(sock),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  self.launcher=self.fx.root/'fixture_finisher.py';self.launcher.write_text('import importlib.util,functools\n'+f"s=importlib.util.spec_from_file_location('finish',{str(ROOT/'typed_openjev_finish.py')!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.container_info=functools.partial(m.container_info,socket_path={str(sock)!r});m.main()\n")
  self.plan=self.out/'plan.json';files=[self.fx.launcher,self.launcher,ROOT/'typed_openjev_finish.py',ROOT/'verify_typed_openjev.py',self.fx.cpath,self.fx.run/'LAUNCH_RECEIPT.json'];self.fx.write(self.plan,dict(out=str(self.out),config=str(self.fx.cpath),auditor=str(self.fx.launcher),files={str(p):v.sha(p) for p in files}))
 def run_chain(self):return subprocess.run([sys.executable,'-P',str(self.launcher),'--plan',str(self.plan)],capture_output=True,text=True,timeout=30)
 def test_full_chain(self):
  r=self.run_chain();self.assertEqual(r.returncode,0,r.stderr);p=self.out/'FINISH_COMPLETE.json';before=p.read_bytes();self.assertEqual(v.load(p)['rc'],0);self.assertEqual(v.load(self.out/'INDEPENDENT_AUDIT.json')['questions'],2000);self.assertNotEqual(self.run_chain().returncode,0);self.assertEqual(p.read_bytes(),before)
 def test_forged_report_fails_audit(self):
  p=self.fx.run/'report.json';x=v.load(p);x['raw_T1']['strict']['accuracy']=.125;self.fx.write(p,x);self.fx.rebind();self.assertNotEqual(self.run_chain().returncode,0);self.assertEqual(v.load(self.out/'FINISH_COMPLETE.json')['stage'],'independent_audit')
 def test_wrong_container(self):
  self.info['Id']='foreign';self.assertNotEqual(self.run_chain().returncode,0);self.assertIn('identity',v.load(self.out/'FINISH_COMPLETE.json')['error'])
 def test_wrong_device(self):
  self.info['HostConfig']['Devices']=[dict(PathOnHost='/dev/davinci1')];self.assertNotEqual(self.run_chain().returncode,0);self.assertIn('device',v.load(self.out/'FINISH_COMPLETE.json')['error'])
if __name__=='__main__':unittest.main()
