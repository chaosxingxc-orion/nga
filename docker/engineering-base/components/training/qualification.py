"""CPU linear fixture for checkpoint mechanics, not LoRA or accelerator qualification."""
from pathlib import Path
import json
import torch
import training

RECIPE = 'cpu-linear-adamw-onecycle-2steps-v2'

def run(config, output, *, stop_after=None):
    required = {'adapter', 'steps', 'approved_full_recipe', 'owner', 'seed', 'resume'}
    if set(config) != required or config['adapter'] != 'k1-qualification-v1' or config['steps'] != 2 or config['approved_full_recipe'] is not False or not isinstance(config['owner'], str) or not config['owner'] or type(config['seed']) is not int or config['seed'] < 0:
        raise ValueError('invalid CPU linear qualification configuration')
    if stop_after not in (None, 1): raise ValueError('invalid fixture stop')
    out = Path(output)
    if not out.is_absolute() or not out.is_dir() or out.is_symlink(): raise ValueError('invalid output')
    identity = {'owner': config['owner'], 'output': str(out), 'seed': config['seed'], 'recipe': RECIPE, 'config_sha256': training.canonical({k:v for k,v in config.items() if k != 'resume'}), 'source_sha256': training.sha(Path(__file__))}
    training.claim_owner(out, identity, config['resume'] is not None)
    torch.manual_seed(config['seed'])
    model = torch.nn.Linear(2, 1)
    opt = torch.optim.AdamW(model.parameters(), lr=.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=.01, total_steps=2, pct_start=.1)
    start = 0
    if config['resume'] is not None:
        p = training.checked_checkpoint(torch, out, config['resume'], identity, 2)
        st = torch.load(p, map_location='cpu', weights_only=True)
        model.load_state_dict(st['lora'], strict=True)
        opt.load_state_dict(st['opt']); sched.load_state_dict(st['sched']); start = st['step']
    x = torch.tensor([[1., 2.], [-1., 1.]])
    y = torch.tensor([[1.], [0.]])
    for step in range(start, 2):
        opt.zero_grad(); loss = ((model(x)-y)**2).mean(); loss.backward(); opt.step(); sched.step()
        training.save_checkpoint(torch, str(out), step+1, list(model.named_parameters()), opt, sched, identity, 2)
        if stop_after == step+1: break
    return {'recipe': RECIPE, 'fixture': 'cpu-linear-not-lora', 'approved_full_recipe': False, 'final_step': step+1 if start < 2 else start}
