"""Immutable CPU synthetic substitution for shell qualification, never production."""
import atexit, os, sys, types, importlib.util
from pathlib import Path
os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD']='0'
import transformers.utils.import_utils as iu, transformers.utils as tu
iu.is_torch_npu_available=lambda:False; tu.is_torch_npu_available=lambda:False
import torch, transformers
from transformers import Qwen3Config, Qwen3ForCausalLM
from trace_store import write_trace

import torch.optim.optimizer as _optim
_optim._get_foreach_kernels_supported_devices=lambda: ['cuda', 'xpu', 'cpu']
torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
sys.modules['torch_npu']=types.ModuleType('torch_npu')
torch.npu=types.SimpleNamespace(synchronize=lambda:None,max_memory_reserved=lambda:0,manual_seed_all=lambda _:None,get_amp_supported_dtype=lambda: [torch.bfloat16,torch.float16])
_autocast=torch.autocast
torch.autocast=lambda device_type,**kw: _autocast('cpu',**kw) if device_type=='npu' else _autocast(device_type,**kw)
class Tok:
    pad_token_id=0
    def __call__(self,s,**kw): return {'input_ids':[1+(ord(c)%30) for c in s]}
transformers.AutoTokenizer.from_pretrained=lambda *a,**kw:Tok()
cfg=Qwen3Config(vocab_size=32,hidden_size=16,intermediate_size=32,num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=8)
def pretrained(*args,**kwargs):
    assert kwargs['dtype']==torch.bfloat16 and kwargs['attn_implementation']=='sdpa'
    torch.manual_seed(123)
    return Qwen3ForCausalLM(cfg).to(torch.bfloat16)
transformers.AutoModelForCausalLM.from_pretrained=pretrained
preclip=[]; postclip=[]
_clip=torch.nn.utils.clip_grad_norm_
def clip(params,*a,**kw):
    params=list(params); preclip.append([p.grad.detach().cpu().clone() for p in params]); return _clip(params,*a,**kw)
torch.nn.utils.clip_grad_norm_=clip
_step=torch.optim.AdamW.step
def step(opt,*a,**kw):
    postclip.append([p.grad.detach().cpu().clone() for g in opt.param_groups for p in g['params']]); return _step(opt,*a,**kw)
torch.optim.AdamW.step=step

def patch_trainer(t):
    class Data:
        def __init__(self,args): self.rows=[None]*15576; self.sym=[]
        def steps_per_epoch(self): return 1558
        def step_units(self,step): return step//1558,[[{'prompt':'abc','response':'def'}] for _ in range(2)]
    t.Data=Data
    original=t.parse_args
    def parse(argv):
        parsed=original(argv); parsed.device='cpu'; parsed.expect_pairs=7; return parsed
    t.parse_args=parse
    t.file_sha256=lambda p:'synthetic'

def patch_family(family):
    training=family.training
    real_sha=training.sha
    training.verify_manifest=lambda *a:{'model_id':next(iter(family.RECIPES.values()))['model_id'],'files':next(iter(family.RECIPES.values()))['files']}
    training.sha=lambda p: training.DATA_SHA if str(p)=='/fixture-data' else real_sha(p)
    family.check_topology=lambda params,recipe:family.topology(params)
    def tiny_expected(_):
        spec=importlib.util.spec_from_file_location('retained_tiny',training.SOURCE/'train_r3.py'); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
        args=types.SimpleNamespace(model_path='/fixture-model',kernel='ref',seed=2,grad_ckpt=True,lora_r=16,lora_alpha=32,lora_dropout=.05,expect_pairs=7)
        _,named,_=t.build_model(args,torch)
        return family.topology(named)
    family.expected_topology=tiny_expected
    original=family.run
    def run(config,output):
        attempt=os.environ['NGA_QUAL_ATTEMPT']
        try:
            return original(config,output)
        finally:
            # Attempt is controller-assigned, and exclusive creation prevents retry overwrite.
            resume=config.get('resume'); start=int(Path(resume['path']).stem[5:]) if resume else 0
            write_trace(Path(output),attempt,start+len(postclip),preclip,postclip,torch.save)
    family.run=run
