import copy, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
import torch
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import family, training

def config(recipe):
 return {'recipe_id':recipe['id'],'owner':'fixture','seed':2,'model':{'id':recipe['model_id'],'path':'/model','manifest':'/manifest','manifest_sha256':'0'*64},'dataset':{'id':'decision-v7-train','path':'/data','manifest':'/data-manifest','manifest_sha256':'0'*64},'resume':None,'engineering_stop_after':3}

def equal(a,b):
 if isinstance(a,torch.Tensor): return isinstance(b,torch.Tensor) and torch.equal(a,b)
 if isinstance(a,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
 if isinstance(a,(tuple,list)): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 return a==b

class FamilyTests(unittest.TestCase):
 def test_registry_and_cli(self):
  for r in family.RECIPES.values():
   c=config(r); argv=family.cli(c,'/out')
   self.assertEqual(argv[argv.index('--total-steps')+1],'3116'); self.assertEqual(argv[argv.index('--stop-after')+1],'3'); self.assertEqual(argv[argv.index('--expect-pairs')+1],str(r['pairs']))
   other=next(x for x in family.RECIPES.values() if x['id']!=r['id']); bad=copy.deepcopy(c); bad['model']['id']=other['model_id']
   with self.assertRaises(ValueError): family.validate(bad)
   for key,val in [('engineering_stop_after',True),('engineering_stop_after',0),('recipe_id','unknown')]:
    bad=copy.deepcopy(c); bad[key]=val
    with self.assertRaises(Exception): family.validate(bad)
 def test_numeric_and_fail_closed(self):
  r=next(iter(family.RECIPES.values())); c=config(r)
  c['seed']=2.0; c['engineering_stop_after']=3.0
  argv=family.cli(c,'/out')
  self.assertEqual(argv[argv.index('--seed')+1],'2')
  self.assertEqual(argv[argv.index('--stop-after')+1],'3')
  c['seed']=(2**64-1-family.TOTAL)//1000003+1
  with self.assertRaises(Exception): family.validate(c)
  c['seed']=2
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises((FileNotFoundError,ValueError)): family.run(c,d)
   self.assertEqual(list(Path(d).iterdir()),[])
  with self.assertRaisesRegex(ValueError,'unexpected ordered'):
   family.check_topology([('wrong.lora_B',torch.nn.Parameter(torch.zeros(1)))],r)
  for recipe in family.RECIPES.values():
   top=family.expected_topology(recipe)
   self.assertEqual(len(top),2*recipe['pairs'])
 def test_semantic_state_rejection(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)
   subprocess.run([sys.executable,str(HERE/'family_qualification.py'),'--output',str(out),'--stop','3'],check=True,timeout=60,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   st=torch.load(out/'ckpt/step_000003.pt',weights_only=True); ident=st['identity']
   family.validate_v2(st,ident)
   def altered(fn):
    bad=copy.deepcopy(st); fn(bad)
    with self.assertRaises((ValueError,KeyError,OverflowError)): family.validate_v2(bad,ident)
   altered(lambda x:x['sched']['_schedule_phases'][0].update(end_step=1))
   altered(lambda x:x['opt']['param_groups'][0].update(lr=.5))
   altered(lambda x:x['opt']['state'][0]['step'].fill_(3.5))
   altered(lambda x:x['opt']['state'][0]['exp_avg'].fill_(float('nan')))
   altered(lambda x:next(iter(x['lora'].values())).fill_(float('inf')))
 def test_seed_failures(self):
  class Bad:
   class npu:
    @staticmethod
    def manual_seed_all(s): raise RuntimeError('seed failed')
   @staticmethod
   def manual_seed(s): pass
  with self.assertRaisesRegex(RuntimeError,'seed failed'): family.seed_step(Bad,2,0)
  class Missing:
   @staticmethod
   def manual_seed(s): pass
  with self.assertRaisesRegex(RuntimeError,'unavailable'): family.seed_step(Missing,2,0)
  self.assertIn('CPU diagnostic',family.seed_step(Missing,2,0,require_npu=False))
 def test_separate_process_lora(self):
  with tempfile.TemporaryDirectory() as td:
   a=Path(td)/'a'; b=Path(td)/'b'; a.mkdir(); b.mkdir()
   def call(out,stop,resume=None):
    cmd=[sys.executable,str(HERE/'family_qualification.py'),'--output',str(out),'--stop',str(stop)]
    if resume: cmd+=['--resume',str(resume)]
    subprocess.run(cmd,check=True,timeout=60,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   call(a,6); call(b,3); call(b,6,b/'ckpt/step_000003.pt')
   load=lambda p:torch.load(p,weights_only=True)
   self.assertTrue(equal(load(a/'trace_0_6.pt'),load(b/'trace_0_3.pt')+load(b/'trace_3_6.pt')))
   x=load(a/'ckpt/step_000006.pt'); y=load(b/'ckpt/step_000006.pt')
   for k in ('lora','opt','sched','identity','topology','cursor'): self.assertTrue(equal(x[k],y[k]),k)
   self.assertEqual(y['parent_sha256'],training.sha(b/'ckpt/step_000003.pt'))
   bad=copy.deepcopy(y); bad['identity']['seed']=3
   with self.assertRaises(ValueError): family.validate_v2(bad,y['identity'])
   bad=copy.deepcopy(y); del bad['opt']['state'][0]['exp_avg']
   with self.assertRaises((ValueError,KeyError)): family.validate_v2(bad,y['identity'])
   bad=copy.deepcopy(y); bad['topology'].reverse()
   with self.assertRaises(ValueError): family.validate_v2(bad,y['identity'])
   with self.assertRaises(ValueError): family.load_v2(torch,a,{'path':str(b/'ckpt/step_000003.pt'),'sha256':training.sha(b/'ckpt/step_000003.pt')},y['identity'])

if __name__=='__main__': unittest.main()
