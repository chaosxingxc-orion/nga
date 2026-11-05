"""CPU-only stochastic PEFT LoRA checkpoint fixture, executed as separate processes."""
import argparse, json
from pathlib import Path
import torch
from peft import LoraConfig, get_peft_model
import family, training

torch.set_num_threads(1)
torch.use_deterministic_algorithms(True)

class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.q_proj=torch.nn.Linear(8,8)
        self.v_proj=torch.nn.Linear(8,4)
    def forward(self, x): return self.v_proj(torch.tanh(self.q_proj(x)))

def run(out, stop, resume):
    torch.manual_seed(123)
    model=get_peft_model(Tiny(),LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,target_modules=['q_proj','v_proj'],bias='none'))
    named=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert all(p.dtype==torch.float32 and 'lora_' in n for n,p in named)
    assert all(not p.requires_grad for n,p in model.named_parameters() if 'lora_' not in n)
    opt=torch.optim.AdamW([p for _,p in named],lr=1e-4,weight_decay=.01)
    sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=1e-4,total_steps=3116,pct_start=.1)
    ident={'version':'fixture-peft-v1','seed':2,'fixture_source':training.sha(Path(__file__)),'family_source':training.sha(Path(family.__file__))}
    start=0; parent=None
    if resume:
        p=Path(resume); parent=training.sha(p)
        st=family.load_v2(torch,out,{'path':str(p),'sha256':parent},ident)
        start=family.validate_v2(st,ident,family.topology(named))
        with torch.no_grad():
            for n,p in named: p.copy_(st['lora'][n])
        opt.load_state_dict(st['opt']); sched.load_state_dict(st['sched'])
    x=torch.arange(64,dtype=torch.float32).view(8,8)/64
    y=torch.arange(32,dtype=torch.float32).view(8,4)/32
    trace=[]
    for step in range(start,stop):
        family.seed_step(torch,2,step,require_npu=False)
        opt.zero_grad(set_to_none=True)
        loss=torch.nn.functional.mse_loss(model(x),y); loss.backward()
        grads={n:p.grad.detach().clone() for n,p in named}
        torch.nn.utils.clip_grad_norm_([p for _,p in named],1.)
        opt.step(); sched.step()
        trace.append({'step':step+1,'loss':loss.detach().clone(),'grads':grads,'lr':opt.param_groups[0]['lr']})
    torch.save(trace,out/f'trace_{start}_{stop}.pt')
    family.save_v2(torch,out,stop,named,opt,sched,ident,parent)
    print(json.dumps({'start':start,'stop':stop,'fixture':'PEFT LoRA dropout .05, frozen tiny base','schedule':3116}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True); p.add_argument('--stop',type=int,required=True); p.add_argument('--resume')
    a=p.parse_args(); run(Path(a.output),a.stop,a.resume)
