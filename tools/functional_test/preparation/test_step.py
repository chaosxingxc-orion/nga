"""Actual step and watcher with receipt-shaped fixtures; no production admission."""
import contextlib, copy, io, json, os, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import materializer as P, collector as T, fixture_dev as F, dispatcher as D
C=P.C
class Step(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='integrated-step-fixture-',dir=str(P.A.H.ROOT));self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.addCleanup(setattr,T,'ROOT',T.ROOT);T.ROOT=self.root/'train'
  with P.dev_imports():self.config,self.inspections=F.build(self.root)
  self.objects={};jobs=[]
  for lane in self.config['lanes']:
   ident=lane['lane'];size=lane['size'];seed=lane['seed'];model=next(x for x in self.config['models'] if x['id']==lane['baseline_id']);d=T.ROOT/ident
   jobs.append({'id':ident,'model':model['model']['path']})
   for phase in ('smoke','train'):
    cfg={'owner':'rc1-functional-'+ident,'seed':seed,'model':{'id':'Qwen3.5-'+size+'-Base'},'recipe_id':'k1-base-'+size.lower()+'-3116-v2','adapter':'k1-family-train-v2','engineering_stop_after':2 if phase=='smoke' else 3114,'resume':None if phase=='smoke' else {'path':'/run/nga/output/result/ckpt/step_000002.pt','sha256':T.sha(d/'result/ckpt/step_000002.pt')}}
    F.put(d/(phase+'.json'),cfg);cid=ident+phase
    F.put(d/(phase+'-LAUNCH.json'),{'phase':phase,'chip':2,'container_id':cid,'config_sha256':T.sha(d/(phase+'.json'))});F.put(d/(phase+'-EXIT.json'),{'phase':phase,'chip':2,'container_id':cid,'image':T.IMAGE,'exit_code':0})
    self.objects[cid]={'Id':cid,'Name':'/nga-rc1-'+ident+'-'+phase,'Image':T.IMAGE,'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci2'}]},'State':{'Status':'exited','ExitCode':0}}
  F.put(T.ROOT/'QUEUE.json',{'jobs':jobs})
  self.dev=self.root/'dev-source';shutil.copytree(F.HERE,self.dev)
  F.put(self.dev/'config.json',self.config)
  pins={str(p.relative_to(self.dev)):T.sha(p) for p in self.dev.rglob('*') if p.is_file()}
  F.put(Path(self.config['review']),{'verdict':'PASS_FOR_MATCHED_CURRENT_DEV_CONSUMPTION','files_sha256':pins,'fixture_only':True})
  with P.dev_imports():
   result,code=F.M.assemble(F.M.Consumer(self.config,inspector=self.inspections.__getitem__,allow_fixture=True))
  self.assertEqual(code,0,result);self.result=result;self.comp=Path(self.config['output'])/'comparison.json';F.put(self.comp,result)
  self.out=self.root/'materializer';self.loads=0;original_load=P.load
  def load(name,path):
   # Load exact real watcher/review/consumer; only inject Docker observations and fixture opt-in.
   w=original_load(name,path);ctor=w.M.Consumer
   w.M.Consumer=lambda c:ctor(c,inspector=self.inspections.__getitem__,allow_fixture=True)
   self.loads+=1;return w
  self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
  self.stack.enter_context(patch.object(P,'load',side_effect=load));self.stack.enter_context(patch.object(T,'docker_inspect',side_effect=self.objects.__getitem__))
 def test_actual_step_pending_then_materializes_and_dispatch_review_barrier(self):
  sources=C.required_sources();modules={n:sys.modules.get(n) for n in C.R0_NAMES};seen=[];sha=T.sha
  def observe(p):
   seen.append(str(p));return sha(p)
  pending=copy.deepcopy(self.result);pending['status']='INCOMPLETE_PENDING';pending['operands'][0].update(status='PENDING_MISSING_INPUT',detail='fixture missing DEV')
  F.put(self.comp,pending)
  with patch.object(T,'sha',side_effect=observe):
   for _ in range(2):self.assertEqual(P.step(self.out,self.dev),'pending')
  self.assertFalse(any(p.endswith(('.pt','.safetensors')) for p in seen));self.assertFalse((self.out/'ASSEMBLY-INTENT.json').exists())
  self.assertTrue(all(t['status']=='training_metadata_ready' for t in C.read(self.out/'pending.json')['training']))
  F.put(self.comp,self.result)
  with patch.object(T,'sha',side_effect=observe):self.assertEqual(P.step(self.out,self.dev),'materialized')
  self.assertTrue(any(p.endswith('step_003116.pt') for p in seen));self.assertEqual(C.required_sources(),sources)
  for n,m in modules.items():self.assertIs(sys.modules.get(n),m,n)
  graph=C.read(self.out/'campaign/graph.json');self.assertEqual(list(graph['members']),sorted(C.LANES+C.BASES));self.assertEqual(len({r['identity_sha256'] for r in C.read(self.out/'roster.json')}),12)
  calls=[]
  with patch.object(D,'callback',side_effect=AssertionError('callback before review')):
   status=D.step(graph,{},start=lambda c:calls.append(c))
  self.assertEqual(set(status.values()),{'waiting-review'});self.assertEqual(calls,[])
  for member,node in graph['members'].items():
   draft=C.read(node['draft']);self.assertEqual(draft['member'],member)
   self.assertEqual(C.campaign_digest(draft),graph['campaign_sha256'])
   self.assertEqual('population_export' in draft,member=='q0p8b-s2')
   if member=='q0p8b-s2':
    self.assertEqual(draft['host']['cpu_entry'],draft['population_export']['exporter']['path'])
    self.assertEqual(draft['population_export']['producer']['sha256'],draft['source_files'][draft['host']['entry']])
    self.assertNotIn(draft['host']['cpu_entry'],draft['source_files'])
   self.assertEqual(draft['container']['spec']['cmd'][2],draft['host']['entry'])
   F.put(node['review'],{'schema':'rc1-trackk-review-v1','reviewed':True,'config_sha256':C.digest(draft),'fixture_only':True})
   draft['review']=P.pin(node['review']);P.A.H.validate(draft,node['config']);C.validate(draft)
  with patch.object(D,'callback',return_value={'status':'pending'}):
   self.assertEqual(set(D.step(graph,{k:['fixture'] for k in ('K0','TRAIN_DEV','QWEN27B_ENVFIX')}).values()),{'waiting-dependency'})
  # Exercise actual dispatcher validation and durable intents, substituting only process launch.
  with patch.object(D,'callback',return_value={'status':'ready'}):
   def start(path):
    c=C.read(path);calls.append(path);return {'pid':os.getpid(),'state_dir':str(Path(c['host']['state_dir'])/c['member'])}
   self.assertEqual(set(D.step(graph,{k:['fixture'] for k in ('K0','TRAIN_DEV','QWEN27B_ENVFIX')},start).values()),{'started'})
   self.assertEqual(len(calls),12)
   self.assertEqual(set(D.step(graph,{},start).values()),{'started'});self.assertEqual(len(calls),12)
  self.assertFalse((self.out/'campaign/round/TEST-READS.log').exists())
 def test_review_real_reject_and_final_deep_check(self):
  (self.dev/'producer-config.json').write_text('changed')
  with self.assertRaisesRegex(ValueError,'review/source pin mismatch'):P.step(self.out,self.dev)
  self.assertFalse((self.out/'ASSEMBLY-INTENT.json').exists())
 def test_deep_checkpoint_failure_at_readiness(self):
  p=T.ROOT/'q0p8b-s2/result/ckpt/step_003116.pt';p.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'training contradiction'):P.step(self.out,self.dev)
  self.assertFalse((self.out/'ASSEMBLY-INTENT.json').exists())
 def test_actual_main_pending_and_terminal(self):
  F.put(self.comp,{**self.result,'status':'INCOMPLETE_PENDING'})
  actual_step=P.step
  with patch.object(P,'step',side_effect=lambda out:actual_step(out,self.dev)),patch.object(sys,'argv',['materializer','--out',str(self.out),'--once']),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(P.main(),2)
  self.assertEqual(C.read(self.out/'heartbeat.json')['status'],'pending');self.assertEqual(C.read(self.out/'heartbeat.json')['completed'],12);self.assertFalse((self.out/'EXIT.json').exists())
  F.put(self.comp,self.result)
  with patch.object(P,'step',side_effect=lambda out:actual_step(out,self.dev)),patch.object(sys,'argv',['materializer','--out',str(self.out),'--once']),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(P.main(),0)
  self.assertEqual(C.read(self.out/'EXIT.json')['exit_code'],0)
  with patch.object(sys,'argv',['materializer','--out',str(self.out),'--once']),self.assertRaisesRegex(RuntimeError,'terminal or assembly intent'):P.main()
if __name__=='__main__':unittest.main(verbosity=2)
