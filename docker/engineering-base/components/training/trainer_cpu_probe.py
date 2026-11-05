"""Execute the actual pinned train_r3 loop with CPU-only synthetic dependencies."""
import importlib.util, os, sys, tempfile, types
from pathlib import Path
import torch
import family

root=Path(__file__).resolve().parents[2]/'source'/'train'
os.environ['NGA_R0_CODE']=str(root/'r0_code'); sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('trainer_probe',root/'train_r3.py'); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
sys.modules['torch_npu']=types.ModuleType('torch_npu')
fake=types.ModuleType('transformers'); fake.__version__='cpu-fixture'
fake.AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda _:types.SimpleNamespace(pad_token_id=0))
sys.modules['transformers']=fake
class NPU:
 def synchronize(self): pass
 def max_memory_reserved(self): return 0
 def manual_seed_all(self,seed): pass
torch.npu=NPU()
class Data:
 def __init__(self,args): self.rows=[None]*15576; self.sym=[]
 def steps_per_epoch(self): return 1558
 def step_units(self,step): return step//1558, [step]* (6 if step%1558==1557 else 10)
actual_data=t.Data.__new__(t.Data)
actual_data.steps_per_epoch=lambda:1558
actual_data.units=lambda epoch:list(range(15576))
for cursor in (0,1557,1558,2399,2400,2401,3000,3115):
 epoch, units=actual_data.step_units(cursor)
 assert epoch==cursor//1558 and len(units)==(6 if cursor%1558==1557 else 10)
t.Data=Data
class Model(torch.nn.Module):
 def __init__(self):
  super().__init__(); self.q_proj=torch.nn.Linear(2,1); self.base_model=types.SimpleNamespace(model=self)
 def save_pretrained(self,path): Path(path).mkdir()
model=Model()
t.build_model=lambda args,torch_:(model,list(model.named_parameters()),1)
def loss(torch_,core,tok,units,*args,**kwargs):
 v=core.q_proj(torch.tensor([[float(units[0])+1,1.]])); loss=(v**2).sum(); loss.backward(); return float(loss.detach()),{'rows':len(units),'tokens':len(units)}
t.step_loss=loss
t.seed_step=lambda torch_,seed,step: family.seed_step(torch_,seed,step)
with tempfile.TemporaryDirectory() as d:
 data=Path(d)/'data'; data.write_text('fixture'); t.TRAIN_FILE=str(data)
 t.file_sha256=lambda p:'fixture'; t.latest_ckpt=lambda _:None
 calls=[]
 def save(torch_,out,step,trainable,opt,sched,keep=2): calls.append((step,sched.state_dict()['total_steps']))
 t.save_ckpt=save
 r=next(iter(family.RECIPES.values())); c={'recipe_id':r['id'],'owner':'x','seed':2,'model':{'id':r['model_id'],'path':'/model','manifest':'/m','manifest_sha256':'0'*64},'dataset':{'id':'decision-v7-train','path':'/d','manifest':'/dm','manifest_sha256':'0'*64},'resume':None,'engineering_stop_after':3}
 args=t.parse_args(family.cli(c,d)+['--device','cpu']); result=t.run(args)
 assert result=={'step':3,'stopped':True} and calls==[(3,3116)],(result,calls)
 print('actual trainer loop CPU substitution: step 3, total 3116')
