"""Bounded CPU review: synthetic files only, frozen evaluator/store/calibration arithmetic.
Tests named reproduce_* assert the delivered defect, not desired production behavior.
"""
import contextlib, copy, importlib.util, io, json, os, runpy, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
PACKET=HERE
sys.path.insert(0,str(PACKET))
import producer as P
import core_r3 as C, full_eval_r3 as F, testlock_r3 as TL, prechecks_r3 as PC, eval_r3 as E
import variants_r3 as V, admissible_store_r3 as AS

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
Q=module('review_queue',PACKET/'queue.py')
HP=module('review_host_probe',HERE/'host_ownership_probe.py')
FIELDS=('path','sha256','kind','base_path','base_revision')
DESC={'scorer':'synthetic-review-only','record_grade':True,'mode':'rightpad','dtype':'float32','hf32':{'hf32':False},'token_budget':16384}

def synthetic_model(t):
 m=t/'synthetic-model';m.mkdir();(m/'.complete').write_text('synthetic-revision\n')
 # Tiny arbitrary bytes: exercises identity inventory/schema, never loads model weights.
 (m/'tiny.safetensors').write_bytes(b'synthetic inventory fixture, not a model')
 actual=TL.model_identity(str(m),None,str(t/'cache'))
 pin={k:actual[k] for k in FIELDS};return actual,pin

def row(i,source='synthetic'):
 return {'kev':{'id':f'q{i}','qindex':0},'source':source,'qname':'q','level_type':'nominal','candidate_set':'exclusive','task_definition':'Choose one option.','question':'Which?','input':f'example {i}', 'levels':[{'id':'a','name':'A','definition':'alpha'},{'id':'b','name':'B','definition':'beta'}],'gold':'a' if i%2==0 else 'b'}

def variants(rows):
 p=rows[0];out=[]
 for kind in ['permuted','none_present','none_absent']:
  r=copy.deepcopy(p);r['kev']={'id':p['kev']['id']+'-'+kind,'parent_id':p['kev']['id'],'qindex':0};r['variant']=kind
  if kind=='permuted':r['levels'].reverse()
  else:r['levels'].append({'id':'none','name':'NONE','definition':kind});r['input']+=' '+kind
  out.append(r)
 return out

class Review(unittest.TestCase):
 def test_safe_path_entrypoint_import(self):
  clean=[x for x in sys.path if Path(x or '.').resolve()!=PACKET.resolve()]
  with patch.object(sys,'path',clean),patch.dict(sys.modules):
   sys.modules.pop('producer',None)
   runpy.run_path(str(PACKET/'queue.py'),run_name='review_import_only')

 def test_actual_identity_and_header_schema(self):
  with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
   t=Path(tmp);actual,pin=synthetic_model(t)
   self.assertIsInstance(actual['files'],dict)
   P.check_identity(actual,{**pin,'weight_shard_pins':actual['files']})
   a=P.args_for(F,pin['path'],str(t/'out'));a.partitions=a.partitions.split(',');a.primary_mode='full'
   h=F.build_header(a,actual,DESC,{})
   self.assertEqual(h['model'],pin);self.assertNotIn('files',h['model']);P.check_header(h,pin,DESC)
   bad=copy.deepcopy(actual);bad['files']['tiny.safetensors']='0'*64
   with self.assertRaises(ValueError):P.check_identity(bad,{**pin,'weight_shard_pins':actual['files']})

 def test_actual_producer_frozen_evaluator_then_cpu(self):
  with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
   t=Path(tmp);actual,pin=synthetic_model(t);data=t/'kev';out=t/'result';loads=[]
   populations={('decision-v7','train'): [row(i) for i in range(4)],('decision-v7','calibration'):[row(i) for i in range(6)],('decision-v7','dev'):[row(i) for i in range(4)],('transfer-v4','dev'):[row(i,'transfer') for i in range(3)]}
   manifest={'suites':{}};data_pins={}
   for (suite,split),rows in populations.items():
    for var,rs in [(False,rows)]+([(True,variants(rows))] if split=='dev' else []):
     path=data/suite/(split+('.variants' if var else '')+'.jsonl');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(''.join(json.dumps(r)+'\n' for r in rs))
     data_pins[str(path)]=P.sha(path);outputs=manifest['suites'].setdefault(suite,{'partitions':{}})['partitions'].setdefault(split,{'outputs':{}})['outputs'];outputs['variants' if var else 'clean']={'path':str(path.relative_to(data)),'sha256':P.sha(path)}
   (data/'manifest.json').write_text(json.dumps(manifest))
   config=copy.deepcopy(P.CONFIG);config['models']=[{'id':'synthetic','model':pin,'weight_shard_pins':actual['files']}];config['data_pins']=data_pins
   real_load=C.load_partition;real_path=C.partition_path;real_manifest=PC.check_kev_manifest
   def path(suite,split,variants=False,kev_dir=None):return real_path(suite,split,variants,str(data))
   def load(suite,split,*args,**kw):
    self.assertNotEqual(split,'test');loads.append((suite,split));kw['kev_dir']=str(data);return real_load(suite,split,*args,**kw)
   calls=[]
   def scorer(rows,mode='full'):
    self.assertEqual(mode,'full');calls.append(len(rows));return [[0.,0.] if int(r['kev']['id'][1:])%3==0 else [-2.,-1.] for r in rows]
   scorer.describe=lambda:DESC
   with contextlib.ExitStack() as stack:
    for obj,key,value in [(P,'CONFIG',config),(P,'COUNTS',[6,4,3]),(C,'partition_path',path),(C,'load_partition',load),(PC,'check_kev_manifest',lambda paths,run_dir=None,hashes=None:real_manifest(paths,run_dir,hashes,str(data))),(E,'make_score_fn',lambda a:scorer),(F.TimedScorer,'reserved_gib',lambda self:None)]:stack.enter_context(patch.object(obj,key,value))
    # No backend/model import, including accidental imports during CPU scoring.
    stack.enter_context(patch.dict(sys.modules,{'torch':None,'torch_npu':None,'transformers':None}))
    with contextlib.redirect_stdout(io.StringIO()):P.run('infer','synthetic',str(out))
    self.assertEqual(calls,[6,4,3]);receipt=json.loads((out/'INFERENCE-READY.json').read_text());self.assertEqual(receipt['identity'],actual)
    with patch.object(E,'make_score_fn',side_effect=AssertionError('CPU must not construct scorer')):P.run('score','synthetic',str(out))
    report=json.loads((out/'clean-report.json').read_text());self.assertEqual(report['operator_fit']['n'],6)
    for group in P.GROUPS:
     suite,part,_=group.split('/');rows=populations[suite,part];b=report['partitions'][suite+'/'+part];scores=[x['s'] for x in b['vectors']]
     self.assertEqual(b['headline'],C.headline(rows,scores));self.assertGreater(b['headline']['tie_count'],0)
     self.assertEqual([x['p'] for x in b['vectors']],[C.softmax(s) for s in scores]);self.assertEqual([x['k'] for x in b['vectors']],[C.kev_key(r) for r in rows])
    self.assertEqual(report['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy'],.5)
    self.assertEqual(report['partitions']['decision-v7/dev']['headline']['r0_rule_accuracy'],.25)
    before=[P.sha(C.k_readout_path(str(out),*g.split('/'))) for g in P.GROUPS]
    with contextlib.redirect_stdout(io.StringIO()):P.run('infer','synthetic',str(out))
    self.assertEqual(calls,[6,4,3]);self.assertEqual(before,[P.sha(C.k_readout_path(str(out),*g.split('/'))) for g in P.GROUPS])
    pth=Path(C.k_readout_path(str(out),'decision-v7','dev','clean'));pth.write_text(pth.read_text()+'\n')
    with self.assertRaises(Exception):P.run('score','synthetic',str(out))
    self.assertNotIn(('decision-v7','test'),loads)

 def test_busy_host_is_not_free(self):
  table='npu-smi 25\n| NPU     Chip              | Process id | Process name | Process memory(MB) | status |\n| 4       0                 | 12345      | python       | 100                | NA     |\n'
  self.assertEqual(HP.listing(table,[4]),{4:[12345]})
  with patch.object(Q.HP,'check',return_value={'certain':True,'unmanaged_owners':[{'host_pid':12345}]}):self.assertFalse(Q.free(4))
  with patch.object(Q.HP,'check',side_effect=ValueError('malformed output')):
   with self.assertRaises(ValueError):Q.free(4)

 def test_wrong_dependency_rejected(self):
  with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
   root=Path(tmp);train=root/'q4b-s2';dev=root/'adapter/full-q4b-s2';train.mkdir();dev.mkdir(parents=True)
   P.save(train/'train-LAUNCH.json',{'container_id':'foreign-train','chip':0,'phase':'smoke'})
   P.save(train/'COMPLETE.json',{'exit_code':0,'steps':3116})
   P.save(dev/'infer-LAUNCH.json',{'container_id':'foreign-infer','chip':0})
   P.save(dev/'infer-EXIT.json',{'container_id':'foreign-infer','exit_code':0})
   with patch.object(Q,'ROOT',root),patch.object(Q,'ADAPTER',root/'adapter'):
    with self.assertRaises(ValueError):Q.ready('q4b-s2',4)

 def test_terminal_missing_artifact_rejected(self):
  with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
   root=Path(tmp);d=root/'08b-k0';d.mkdir();cp=d/'score-COMMAND.json'
   # Capture exact generated command before any Docker action; all subprocess calls mocked.
   class Stop(Exception):pass
   captured=[]
   with patch.object(Q,'OUT',root),patch.object(Q.subprocess,'run',return_value=type('R',(),{'returncode':1})()),patch.object(Q,'verify_sources'),patch.object(Q,'reviewed',return_value=True),patch.object(Q,'command',side_effect=lambda *a: (captured.append(list(a)),(_ for _ in ()).throw(Stop()))[1]):
    with self.assertRaises(Stop):Q.phase('08b-k0',4,'score')
   P.save(d/'score-LAUNCH.json',{'container_id':'cid','command_sha256':P.sha(cp)})
   P.save(d/'score-EXIT.json',{'container_id':'cid','exit_code':0,'container_exit_code':0})
   info={'Name':'/nga-rc1-matched-k0-08b-k0-score','Image':Q.C['image'],'Config':{'Labels':{'nga.rc1.matched-k0':'08b-k0'}},'State':{'Running':False,'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False}}
   with patch.object(Q,'OUT',root),patch.object(Q,'inspect',return_value=info),patch.object(Q,'command',side_effect=AssertionError('no subprocess expected')):
    with self.assertRaises(FileNotFoundError):Q.phase('08b-k0',4,'score')
   self.assertFalse((d/'result/clean-report.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
