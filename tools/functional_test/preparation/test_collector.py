import json,tempfile,unittest
from pathlib import Path
import collector as c
class TestCollector(unittest.TestCase):
 def test_producer_format_and_mutations(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);d=root/'q2b-s2';d.mkdir();model=root/'model';model.mkdir();(model/'.complete').write_text('rev\n')
   def put(n,x):
    p=d/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
   def file(n,x):
    p=d/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(x)
   file('result/ckpt/step_000002.pt',b'smoke');file('result/ckpt/step_003116.pt',b'end');file('result/adapter/adapter_model.safetensors',b'adapter')
   objects={}
   for phase in ('smoke','train'):
    cfg={'owner':'rc1-functional-q2b-s2','seed':2,'model':{'id':'Qwen3.5-2B-Base'},'recipe_id':'k1-base-2b-3116-v2','adapter':'k1-family-train-v2','engineering_stop_after':2 if phase=='smoke' else 3114,'resume':None if phase=='smoke' else {'path':'/run/nga/output/result/ckpt/step_000002.pt','sha256':c.sha(d/'result/ckpt/step_000002.pt')}}
    put(phase+'.json',cfg);put(phase+'-LAUNCH.json',{'phase':phase,'chip':2,'container_id':phase,'config_sha256':c.sha(d/(phase+'.json'))});put(phase+'-EXIT.json',{'phase':phase,'chip':2,'container_id':phase,'image':c.IMAGE,'exit_code':0})
    objects[phase]={'Id':phase,'Name':'/nga-rc1-q2b-s2-'+phase,'Image':c.IMAGE,'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci2'}]},'State':{'Status':'exited','ExitCode':0}}
   put('COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False});put('result/adapter/adapter_config.json',{'base_model_name_or_path':'Qwen3.5-2B-Base','revision':'rev'})
   b={'owner':'rc1-functional-q2b-s2','checkpoint_sha256':c.sha(d/'result/ckpt/step_003116.pt')};put('result/adapter/BINDING.json',b);put('result/adapter/PUBLICATION.json',{'binding':b,'files':{n:c.sha(d/'result/adapter'/n) for n in ('adapter_config.json','adapter_model.safetensors')}})
   def status():return c.collect(root,'q2b-s2','2B',2,model,objects.__getitem__)['status']
   self.assertEqual(status(),'training_verified');objects['train']['Image']='wrong';self.assertEqual(status(),'contradiction');objects['train']['Image']=c.IMAGE
   put('COMPLETE.json',{'exit_code':0,'steps':3115,'scientific_acceptance':False});self.assertEqual(status(),'contradiction');(d/'COMPLETE.json').unlink();self.assertEqual(status(),'pending')
   put('COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False});file('result/adapter/adapter_model.safetensors',b'wrong');self.assertEqual(status(),'contradiction')
if __name__=='__main__':unittest.main()
