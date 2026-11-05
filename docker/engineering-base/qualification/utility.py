"""Image-side checkpoint advance and equality checks; synthetic counters only."""
import json, sys, warnings, hashlib
from pathlib import Path
import torch
sys.path.insert(0,'/opt/nga/components/training')
import family
from safetensors.torch import load_file
R=Path('/work')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def advance(out):
    ck=out/'ckpt/step_000006.pt'; st=torch.load(ck,weights_only=True)
    st['step']=3115; st['cursor']={'next_step':3115,'epoch':3115//1558,'batch':3115%1558,'step_seed':2*1000003+3115}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore'); p=torch.nn.Parameter(torch.zeros(())); opt=torch.optim.AdamW([p],lr=1e-4,weight_decay=.01); sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=1e-4,total_steps=3116,pct_start=.1)
        for _ in range(3115): sched.step()
    st['sched']=sched.state_dict(); ref=opt.state_dict()['param_groups'][0]; ref['params']=st['opt']['param_groups'][0]['params']; st['opt']['param_groups']=[ref]
    for v in st['opt']['state'].values(): v['step'].fill_(3115)
    dest=out/'ckpt/step_003115.pt';
    with dest.open('xb') as f: torch.save(st,f)
    family.validate_v2(st,st['identity'])
def eq(x,y): return len(x)==len(y) and all(len(a)==len(b) and all(torch.equal(u,v) for u,v in zip(a,b)) for a,b in zip(x,y))
def verify():
    a,b=R/'a',R/'b'
    traces=[torch.load(p,weights_only=True) for p in [a/'gradients-003116-a-final.pt',b/'gradients-003116-b-final.pt',a/'gradients-003116-a-retry.pt',b/'gradients-003116-b-retry.pt']]
    for k in ('preclip','postclip'):
        assert len(traces[0][k])==len(traces[1][k])==1 and traces[0][k][0] and eq(traces[0][k],traces[1][k])
        assert not traces[2][k] and not traces[3][k]
    tensors=[load_file(str(x/'adapter/adapter_model.safetensors')) for x in (a,b)]
    assert tensors[0].keys()==tensors[1].keys() and all(torch.equal(tensors[0][k],tensors[1][k]) for k in tensors[0])
    for out,tensor in zip((a,b),tensors):
        state=torch.load(out/'ckpt/step_003116.pt',weights_only=True)
        wanted={n.replace('.default.weight','.weight'):v for n,v in state['lora'].items()}
        assert tensor.keys()==wanted.keys() and all(torch.equal(tensor[n],v) for n,v in wanted.items())
        binding=json.loads((out/'adapter/BINDING.json').read_text()); receipt=json.loads((out/'adapter/PUBLICATION.json').read_text())
        assert receipt['binding']==binding and binding['checkpoint_sha256']==sha(out/'ckpt/step_003116.pt')
        assert receipt['files']=={n:sha(out/'adapter'/n) for n in ('adapter_config.json','adapter_model.safetensors')}
        assert binding['identity_sha256']==family.training.canonical(state['identity']) and binding['owner']=='cpu-fixture'
    (R/'verification.json').write_text(json.dumps({'status':'PASS','preclip_final_exact_nonempty':True,'postclip_final_exact_nonempty':True,'terminal_retry_zero_updates':True,'peft_tensors_exact_and_match_checkpoints':True,'receipt_binding_exact':True,'synthetic_counter':3115,'actual_previous_updates':6,'actual_final_updates':1,'schedule':3116},indent=2)+'\n')
if sys.argv[1]=='advance': advance(R/sys.argv[2])
elif sys.argv[1]=='verify': verify()
else: raise ValueError('bad command')
