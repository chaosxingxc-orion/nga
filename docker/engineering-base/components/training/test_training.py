import copy, hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
import torch
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import training as m
import qualification as q

class ContractTests(unittest.TestCase):
 def test_manifest_content_check(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'model'; root.mkdir(); (root/'a').write_text('x')
   manifest=Path(d)/'manifest.json'; manifest.write_text(json.dumps({'model_id':'x','files':{'a':m.sha(root/'a')}}))
   digest=m.sha(manifest); self.assertEqual(m.verify_manifest(root,manifest,digest)['model_id'],'x')
   (root/'a').write_text('y')
   with self.assertRaises(ValueError): m.verify_manifest(root,manifest,digest)
   (root/'a').write_text('x'); (root/'extra').write_text('x')
   with self.assertRaises(ValueError): m.verify_manifest(root,manifest,digest)
 def test_source_closure(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   from shutil import copytree
   copytree(HERE.parent.parent/'source/train',root,dirs_exist_ok=True)
   m.verify_source(root); (root/'kev_aug.py').write_text('changed')
   with self.assertRaises(ValueError): m.verify_source(root)
 def test_qualification_exact_next_update_and_rejections(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a'; b=Path(d)/'b'; a.mkdir(); b.mkdir()
   c={'adapter':'k1-qualification-v1','steps':2,'approved_full_recipe':False,'owner':'o','seed':4,'resume':None}
   self.assertEqual(q.run(c,str(a))['final_step'],2)
   self.assertEqual(q.run(c,str(b),stop_after=1)['final_step'],1)
   p=b/'ckpt/step_000001.pt'; resume={'path':str(p),'sha256':m.sha(p)}
   for k,v in [('owner','wrong'),('seed',5)]:
    bad=dict(c, resume=resume); bad[k]=v
    with self.assertRaises(ValueError): q.run(bad,str(b))
   partial=b/'ckpt/.partial-2'; partial.write_bytes(b'partial')
   with self.assertRaises(ValueError): q.run(dict(c,resume=resume),str(b))
   partial.unlink()
   with self.assertRaises(ValueError): q.run(dict(c,resume=dict(resume,sha256='0'*64)),str(b))
   st=torch.load(p,weights_only=True); changed=copy.deepcopy(st); changed['identity']['recipe']='wrong'; torch.save(changed,b/'ckpt/step_000003.pt')
   wrong=b/'ckpt/step_000003.pt'
   with self.assertRaises(ValueError): q.run(dict(c,resume={'path':str(wrong),'sha256':m.sha(wrong)}),str(b))
   wrong.write_bytes(b'torn')
   with self.assertRaises(ValueError): q.run(dict(c,resume={'path':str(wrong),'sha256':m.sha(wrong)}),str(b))
   self.assertEqual(q.run(dict(c,resume=resume),str(b))['final_step'],2)
   x=torch.load(a/'ckpt/step_000002.pt',weights_only=True); y=torch.load(b/'ckpt/step_000002.pt',weights_only=True)
   for name in x['lora']: self.assertTrue(torch.equal(x['lora'][name],y['lora'][name]))
   self.assertEqual(x['sched'],y['sched']); self.assertEqual(x['opt']['param_groups'],y['opt']['param_groups'])
   for i in x['opt']['state']:
    for k in x['opt']['state'][i]: self.assertTrue(torch.equal(x['opt']['state'][i][k],y['opt']['state'][i][k]))
 def test_lifecycle_success_and_failure(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d); self.assertEqual(m.lifecycle(out, {'owner':'o'}, lambda: 42),42)
   with self.assertRaisesRegex(RuntimeError, 'failure'): m.lifecycle(out, {'owner':'o'}, lambda: (_ for _ in ()).throw(RuntimeError('failure')))
   attempts=list((out/'attempts').iterdir()); self.assertEqual(len(attempts),2)
   self.assertEqual(sorted(json.loads((x/'terminal.json').read_text())['exit_code'] for x in attempts),[0,1])
   for x in attempts: self.assertTrue((x/'start.json').exists()); self.assertTrue((x/'heartbeat.json').exists())
 def test_validate_incomplete_state(self):
  with self.assertRaises(ValueError): m.validate_state({'identity':{},'step':1,'lora':{'x':1}}, {}, 2)

if __name__=='__main__': unittest.main()
