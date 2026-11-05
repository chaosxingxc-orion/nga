import sys,os,json,hashlib,pathlib,subprocess,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent));import panel_score as S
B=pathlib.Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/unified_score_20261105_v4')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def put(p,v):pathlib.Path(p).write_text(json.dumps(v,sort_keys=True)+'\n')
def lines(p):return [json.loads(x) for x in open(p)]
@unittest.skipUnless(pathlib.Path('/opt/nga/entrypoint.sh').is_file() and (B/'manifest.json').is_file(), 'requires installed image entrypoint and retained read-only fixture inputs')
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory(prefix='nga-panel-score-test-');self.addCleanup(tmp.cleanup);self.d=pathlib.Path(tmp.name); (self.d/'input').mkdir(); original=json.load(open(B/'manifest.json'));op=original['population'];items=lines(op['items']['path'])[:3];reqs=lines(op['requests']['path'])[:3];g=lines(op['gold']['path'])[:3]
  contract=S.P.make_contract(items,source_sha256=op['source']['sha256'],model_sha256=original['model_sha256'],runtime_protocol_sha256=op['protocol_binding_sha256']);pin=S.P.sha256_value(contract);pop=dict(op,count=3,kinds=dict(__import__('collections').Counter(x['kind'] for x in items)),contract_sha256=pin,ordered_inputs_sha256=S.N.digest(reqs))
  for name,value in [('items',items),('requests',reqs),('gold',g)]:
   p=self.d/'input'/(name+'.jsonl');p.write_text(''.join(json.dumps(x)+'\n' for x in value));pop[name]={'path':str(p),'sha256':sha(p)}
  p=self.d/'input'/'contract.json';put(p,contract);pop['contract']={'path':str(p),'sha256':sha(p)}
  records=self.d/'records';records.mkdir();receipts=[]
  import numpy as np
  ref=S.N.reference(S.ROOT)
  for i,req in enumerate(reqs):
   r=json.load(open(pathlib.Path(original['records'])/f'{i:06d}'/'record.json')); z=np.zeros(248320,dtype=np.float32);z[req['label_ids']]=r['prediction']['label_values'];r['contract_sha256']=pin;r['prediction']=S.N.read_logits(req,z,mode='transformers_full_labels',contract_sha256=pin,prepared_sha256=S.N.digest(req),ref=ref);d=records/f'{i:06d}';d.mkdir();put(d/'record.json',r);put(d/'COMMITTED.json',{'record.json':sha(d/'record.json')});receipts.append(sha(d/'COMMITTED.json'))
  self.m={**original,'population':pop,'records':str(records),'receipts_sha256':S.N.digest(receipts)};self.mp=self.d/'manifest.json';put(self.mp,self.m);self.config={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':str(self.mp),'manifest_sha256':sha(self.mp),'output':str(self.d/'out'),'workers':2,'chunk_size':1};self.cp=self.d/'config.json';put(self.cp,self.config)
 def invoke(self):return subprocess.run(['/opt/nga/entrypoint.sh',str(self.cp)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def test_success(self):
  r=self.invoke();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.load(open(self.d/'out'/'summary.json'))['n'],3)
 def test_hash(self):
  self.config['manifest_sha256']='0'*64;put(self.cp,self.config);self.assertNotEqual(self.invoke().returncode,0)
 def test_invalid_population(self):
  self.m['population']['count']=4;put(self.mp,self.m);self.config['manifest_sha256']=sha(self.mp);put(self.cp,self.config);self.assertNotEqual(self.invoke().returncode,0)
 def test_partial(self):
  (self.d/'records'/'000001'/'COMMITTED.json').unlink();self.assertNotEqual(self.invoke().returncode,0);self.assertEqual(json.load(open(self.d/'out'/'EXIT.json'))['exit_code'],1)
 def test_crash_resume(self):
  d=self.d/'out';import time,signal
  proc=subprocess.Popen(['/opt/nga/entrypoint.sh',str(self.cp)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  deadline=time.monotonic()+30
  while not (d/'OWNER.json').exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.005)
  self.assertTrue((d/'OWNER.json').exists());os.kill(proc.pid,signal.SIGKILL);proc.wait();self.assertNotEqual(proc.returncode,0)
  r=self.invoke();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.load(open(d/'EXIT.json'))['exit_code'],0)
 def test_wrong_output_owner(self):
  d=self.d/'out';d.mkdir();put(d/'OWNER.json',{'other':'owner'});self.assertNotEqual(self.invoke().returncode,0);self.assertEqual(json.load(open(d/'OWNER.json')),{'other':'owner'})
if __name__=='__main__':unittest.main(verbosity=2)
