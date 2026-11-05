"""Trained dependency closure and typed host mount checks, no Docker."""
import copy, hashlib, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import unified_cpu_pipeline_v1 as P
from tools import test_unified_container_host_v1 as HT

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v): Path(p).write_text(json.dumps(v)+'\n')

class Mounts(unittest.TestCase):
 def test_host_typed_readonly(self):
  h=HT.HostTest();h.setUp();self.addCleanup(h.doCleanups);c=h.host(h.c,'trained');data=h.root/'data';data.mkdir();pub=data/'adapter';pub.mkdir();cp=data/'step.pt';cp.write_bytes(b'x');(data/'dataset').write_bytes(b'x');(data/'contract').write_bytes(b'x');mod=Path(c['mounts'][0]['source']);(mod/'manifest').write_bytes(b'x')
  c['mounts'] += [dict(source=str(pub),target='/data/adapter'),dict(source=str(cp),target='/data/checkpoint'),dict(source=str(data/'dataset'),target='/data/dataset'),dict(source=str(data/'contract'),target='/data/contract')]
  c['task']=dict(schema='nga-unified-config-v1',adapter='trained-full-label-v1',runtime='npu',recipe_id='k1-base-0.8b-3116-v2',model=dict(id='Qwen3.5-0.8B-Base',path='/model',manifest='/model/manifest',manifest_sha256='a'*64),adapter_publication=dict(path='/data/adapter',checkpoint='/data/checkpoint',checkpoint_sha256='b'*64,seed=1,owner='fixture'),dataset=dict(path='/data/dataset',sha256='c'*64,count=3),panel=dict(contract='/data/contract',contract_file_sha256='d'*64,contract_sha256='e'*64,ordered_requests_sha256='f'*64,model_sha256='1'*64),image_sha256='a'*64,max_length=8192,batch_size=1,output='/run/nga/output/result')
  h.repin_host(c);HT.H.validate(c);d=HT.FakeDocker(h.q);ident=d.create(c,[0],HT.IMAGE);HT.H.verify(c,d,ident,[0],HT.IMAGE)
  for dest in ('/data/adapter','/data/checkpoint'):
   ob=next(x for x in d.objects['trained']['Mounts'] if x['Destination']==dest);self.assertFalse(ob['RW']);ob['RW']=True
   with self.assertRaisesRegex(ValueError,'container mounts differ'):HT.H.verify(c,d,ident,[0],HT.IMAGE)
   ob['RW']=False
  for key in ('path','checkpoint'):
   orig=c['task']['adapter_publication'][key];c['task']['adapter_publication'][key]='/model/wrong';h.repin_host(c)
   with self.assertRaisesRegex(ValueError,'typed namespace'):HT.H.validate(c)
   c['task']['adapter_publication'][key]=orig;h.repin_host(c)
 def test_dependencies(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);model=root/'model';model.mkdir();(model/'weight').write_bytes(b'x');pub=root/'adapter';pub.mkdir()
   for name in ('adapter_config.json','adapter_model.safetensors','PUBLICATION.json','BINDING.json'):(pub/name).write_bytes(b'x')
   put(pub/'PUBLICATION.json',{'files':{n:sha(pub/n) for n in ('adapter_config.json','adapter_model.safetensors')}})
   cp=root/'checkpoint';cp.write_bytes(b'x');out=root/'output';(out/'result').mkdir(parents=True)
   paths={}
   for n in ('dataset','contract','items','gold','requests'):
    p=root/n;p.write_text('{}');paths[n]=p
   mm=root/'model-manifest';put(mm,{'files':{'weight':sha(model/'weight')}})
   source=dict(adapter='trained-full-label-v1',model=dict(path='/model/base',manifest='/model/manifest',manifest_sha256=sha(mm)),dataset=dict(path='/data/dataset',sha256=sha(paths['dataset'])),panel=dict(contract='/data/contract',contract_file_sha256=sha(paths['contract'])),adapter_publication=dict(path='/data/adapter',checkpoint='/data/checkpoint',checkpoint_sha256=sha(cp)))
   sp=root/'source';put(sp,source);mp=root/'manifest';put(mp,{'population':{k:{'path':'/data/'+k,'sha256':sha(paths[k])} for k in ('contract','items','gold','requests')}})
   inputs=[dict(source=str(out),target='/run/nga/output'),dict(source=str(model),target='/model/base'),dict(source=str(mm),target='/model/manifest'),dict(source=str(sp),target='/data/source'),dict(source=str(mp),target='/data/manifest'),dict(source=str(pub),target='/data/adapter'),dict(source=str(cp),target='/data/checkpoint')]+[dict(source=str(p),target='/data/'+k) for k,p in paths.items()]
   export=dict(source='/run/nga/output/result',source_config='/data/source',source_config_sha256=sha(sp),panel_manifest='/data/manifest',panel_manifest_sha256=sha(mp))
   _,mounts=P.dependencies(inputs,export);self.assertTrue({'/data/adapter','/data/checkpoint','/data/nga-trained-source','/model/base'} <= {m['target'] for m in mounts})
   for target in ('/data/adapter','/data/checkpoint'):
    with self.assertRaises(ValueError): P.dependencies([m for m in inputs if m['target']!=target],export)
   cp.write_bytes(b'foreign')
   with self.assertRaises(ValueError):P.dependencies(inputs,export)
 def test_attempt_failure_does_not_replace_terminal(self):
  h=HT.HostTest();h.setUp();self.addCleanup(h.doCleanups)
  c=h.host(h.c,'history');d=HT.FakeDocker(h.q);result=HT.H.run(c,d)
  self.assertEqual(result['exit_code'],0);meta=HT.H.metadata_dir(c)
  terminal=(meta/'terminal.json').read_bytes();handoff=(meta/'cpu-handoff.json').read_bytes()
  bad=copy.deepcopy(c);bad['name']='rejected-launch'
  with self.assertRaisesRegex(ValueError,'launch identity'):HT.H.run(bad,d)
  records=list(meta.glob('attempt-failure-*.json'));self.assertEqual(len(records),1)
  record=json.loads(records[0].read_text());self.assertEqual(record['attempted_config_sha256'],HT.H.U.digest(bad));self.assertEqual(record['intended_launch_sha256'],HT.H.U.digest(HT.H.launch_spec(bad)))
  self.assertEqual(record['historical_terminal'],'not_the_result_of_this_attempt');self.assertEqual((meta/'terminal.json').read_bytes(),terminal);self.assertEqual((meta/'cpu-handoff.json').read_bytes(),handoff)
  self.assertEqual(HT.H.run(c,d),result);self.assertEqual(d.creates,1)
  (meta/'OWNER.json').unlink()
  with self.assertRaisesRegex(ValueError,'launch identity'):HT.H.run(bad,d)
  self.assertEqual(list(meta.glob('attempt-failure-*.json')),records)
if __name__=='__main__':unittest.main(verbosity=2)
