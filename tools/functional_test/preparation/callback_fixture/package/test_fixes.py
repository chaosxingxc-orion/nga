import hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import torch
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
import core, cpu_reference
spec=importlib.util.spec_from_file_location('controller',BASE/'controller.py'); controller=importlib.util.module_from_spec(spec); spec.loader.exec_module(controller)

class Tests(unittest.TestCase):
 def test_reference(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); x=torch.tensor([[1.,2.,3.],[2.,1.,0.],[0.,1.,2.]])
   torch.save(x,r/'logits.pt'); ids=[2,0]; score=sum(float(torch.log_softmax(x,dim=-1)[i,t]) for i,t in enumerate(ids))
   m={'candidate_token_ids':ids,'shape':list(x.shape),'npu_score':score,'absolute_tolerance':1e-4,'relative_tolerance':1e-5,'logits_sha256':hashlib.sha256((r/'logits.pt').read_bytes()).hexdigest()}; (r/'manifest.json').write_text(json.dumps(m))
   self.assertTrue(cpu_reference.evaluate(r)['pass']); m['npu_score']+=1; (r/'manifest.json').write_text(json.dumps(m)); self.assertFalse(cpu_reference.evaluate(r)['pass'])
 def test_counts(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); state={'skipped':0,'computed':0}; core.record_attempt(state,'skipped','a',d/'events',d/'progress'); core.record_attempt(state,'computed','b',d/'events',d/'progress'); self.assertEqual(json.loads((d/'progress').read_text()),{'skipped':1,'computed':1}); self.assertEqual([json.loads(x)['event'] for x in (d/'events').read_text().splitlines()],['skipped','computed'])
 def test_release_and_uncertainty(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); (d/'CONTAINER.json').write_text(json.dumps({'id':'id','name':'run'})); (d/'EXIT.json').write_text('{"exit_code":9}')
   class R:
    @staticmethod
    def docker_inspect(name): return {'Id':'id','Name':'/run','State':{'Status':'exited','ExitCode':9},'HostConfig':{'AutoRemove':False}}
    @staticmethod
    def write_atomic(path,obj): Path(path).write_text(json.dumps(obj))
   class G:
    r3=R; calls=[]
    @classmethod
    def transact(cls,*a,**kw): cls.calls.append((a,kw))
   with patch.object(controller,'host_clear',return_value={'certain':True}):
    self.assertEqual(controller.release(G,'alloc',[0,1,2,3],'run',d,'probe'),9)
   self.assertEqual(json.loads((d/'TERMINAL.json').read_text())['result'],'failed'); self.assertEqual(G.calls[0][0],('release','alloc',[0,1,2,3],'run',d/'RELEASE.json')); self.assertEqual(G.calls[0][1]['container_id'],'id')
   G.calls.clear()
   with patch.object(controller,'host_clear',side_effect=RuntimeError('uncertain')):
    with self.assertRaises(RuntimeError): controller.release(G,'alloc',[0,1,2,3],'run',d,'probe')
   self.assertFalse(G.calls)
 def test_pins(self):
  source=BASE/'launch.py'; good=hashlib.sha256(source.read_bytes()).hexdigest(); controller.verify_pins({'source_pins':{'launch.py':good}})
  with self.assertRaises(RuntimeError): controller.verify_pins({'source_pins':{'launch.py':'0'*64}})
if __name__=='__main__': unittest.main()
