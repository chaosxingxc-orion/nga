"""Task-local hooks for the pinned verl engine; no modifications to the checkout."""
import hashlib, json, os, time
from pathlib import Path
import torch
import torch.distributed as dist
import raw_loading as audit

OUT = Path(os.environ.get('FIXTURE_OUT', '/tmp/qwen38-fixture'))

def emit(kind, **data):
    OUT.mkdir(parents=True, exist_ok=True)
    rank = dist.get_rank() if dist.is_initialized() else 0
    record = {'event':kind, 'rank':rank, 'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **data}
    with (OUT / f'rank-{rank}.jsonl').open('a') as f:
        f.write(json.dumps(record, default=str, allow_nan=False)+'\n'); f.flush()
    print(json.dumps(record, default=str, allow_nan=False), flush=True)

def local(t):
    return t.to_local() if hasattr(t, 'to_local') else t

def inventory(module):
    names = [n for n,p in module.named_parameters() if p.requires_grad]
    if not names or any('lora_' not in n for n in names): raise RuntimeError('trainable parameters must be LoRA only')
    return {'text':[n for n in names if not (n.startswith('visual.') or '.visual.' in n)], 'vision':[n for n in names if (n.startswith('visual.') or '.visual.' in n)]}

def digest_base(module):
    # One shard at a time, no base-sized copy retained. This hashes all frozen parameter bytes.
    h=hashlib.sha256()
    for name,p in module.named_parameters():
        if not p.requires_grad:
            x=local(p).detach().contiguous().cpu()
            h.update(name.encode()); h.update(x.reshape(-1).view(torch.uint8).numpy().tobytes())
    return h.hexdigest()

def global_sum(value, device):
    t=torch.tensor(value, dtype=torch.int64, device=device)
    if dist.is_initialized(): dist.all_reduce(t)
    return int(t.item())

def before_update(module, optimizer):
    inv=inventory(module)
    wanted={id(p) for p in module.parameters() if p.requires_grad}
    got=[p for g in optimizer.param_groups for p in g['params']]
    if len(got)!=len(wanted) or {id(p) for p in got}!=wanted: raise RuntimeError('optimizer binding mismatch')
    saved={}; nonzero=0; text_nonzero=0; unused_vision=[]
    for n,p in module.named_parameters():
        if not p.requires_grad:
            if p.grad is not None: raise RuntimeError('frozen gradient: '+n)
            continue
        x=local(p); saved[n]=x.detach().clone()
        g=local(p.grad) if p.grad is not None else None
        if g is None:
            if (n.startswith('visual.') or '.visual.' in n): unused_vision.append(n)
            continue
        if not bool(torch.isfinite(g).all()): raise RuntimeError('nonfinite gradient: '+n)
        if bool(torch.count_nonzero(g)):
            nonzero+=1
            if not (n.startswith('visual.') or '.visual.' in n): text_nonzero+=1
    device=local(next(p for p in module.parameters() if p.requires_grad)).device
    if global_sum(nonzero,device)==0 or global_sum(text_nonzero,device)==0: raise RuntimeError('no global text LoRA gradient')
    return {'saved':saved, 'base':digest_base(module), 'unused_vision':unused_vision, 'inventory':inv}

def after_update(module, state):
    changed=0
    for n,p in module.named_parameters():
        if p.requires_grad:
            x=local(p).detach()
            if not bool(torch.isfinite(x).all()): raise RuntimeError('nonfinite adapter: '+n)
            changed += int(not torch.equal(x,state['saved'][n]))
    device=local(next(p for p in module.parameters() if p.requires_grad)).device
    total=global_sum(changed,device)
    if total==0: raise RuntimeError('no global LoRA update')
    if digest_base(module)!=state['base']: raise RuntimeError('frozen base changed')
    return {'local_changed':changed,'global_changed':total,'unused_vision':state['unused_vision']}

def install():
    import transformers
    from transformers import Qwen3_5ForConditionalGeneration
    import verl.utils.model as vm
    import verl.workers.engine.fsdp.transformer_impl as impl
    from verl.workers.config.optimizer import build_optimizer
    from verl.utils.checkpoint.checkpoint_handler import CheckpointHandler
    from verl.trainer.sft_trainer import SFTTrainer
    audit.source_check(transformers,Qwen3_5ForConditionalGeneration)
    class Audited(audit.CaptureBeforeFilter,Qwen3_5ForConditionalGeneration): pass
    original_selector=vm.get_hf_auto_model_class
    class Loader:
        @staticmethod
        def from_pretrained(*args,**kw):
            selected=original_selector(hf_config=kw['config'])
            if selected.__name__ != 'AutoModelForImageTextToText': raise RuntimeError('wrong auto selector')
            model, reported=Audited.from_pretrained(*args, output_loading_info=True, **kw)
            checkpoint, headers=audit.inventory(kw['pretrained_model_name_or_path'])
            state={k:{'shape':list(v.shape),'dtype':str(v.dtype).replace('torch.','')} for k,v in model.state_dict().items()}
            # account()'s class-FP32 assertion is specific to inference; shapes are dtype independent.
            state_for_account={k:{**v,'dtype':'float32'} for k,v in state.items()}
            allow=json.loads((Path(__file__).parent/'TENSOR-DIFF.json').read_text())['checkpoint_only']
            raw=getattr(model,'_raw_loading_info',None)
            result=audit.account(checkpoint,state_for_account,allow,raw,reported,getattr(model,'_raw_capture_count',0),list(model._keys_to_ignore_on_load_unexpected))
            emit('raw_loader', raw=audit.normalize(raw), reported=audit.normalize(reported), accounting=result, header_sha256=headers, requested_dtype=str(kw.get('torch_dtype')), actual_dtypes={d:sum(v['dtype']==d for v in state.values()) for d in sorted({v['dtype'] for v in state.values()})})
            if result['errors']: raise RuntimeError('raw loader audit failed')
            model.__class__ = Qwen3_5ForConditionalGeneration
            return model
    Loader.__name__='AuditedImageTextLoader'
    vm.get_hf_auto_model_class=lambda hf_config: Loader
    old_lora=impl.FSDPEngine._build_lora_module
    def build_lora(self,module):
        module=old_lora(self,module); emit('lora_inventory', **inventory(module)); return module
    impl.FSDPEngine._build_lora_module=build_lora
    def optimizer(self,module):
        params=[p for p in module.parameters() if p.requires_grad]
        inventory(module)
        return build_optimizer(params,self.optimizer_config)
    impl.FSDPEngine._build_optimizer=optimizer
    old_forward=impl.FSDPEngineWithLMHead.forward_step
    def forward(self,*args,**kw):
        loss,info=old_forward(self,*args,**kw)
        if not bool(torch.isfinite(loss).all()): raise RuntimeError('nonfinite loss')
        emit('loss',loss=float(loss.detach().item()))
        return loss,info
    impl.FSDPEngineWithLMHead.forward_step=forward
    old_step=impl.FSDPEngine.optimizer_step
    def step(self):
        state=before_update(self.module,self.optimizer)
        norm=old_step(self)
        if not torch.isfinite(torch.tensor(norm)): raise RuntimeError('nonfinite clipped norm')
        emit('update',grad_norm=norm,**after_update(self.module,state))
        return norm
    impl.FSDPEngine.optimizer_step=step
    old_fsdp=impl.FSDPEngine._build_fsdp_module
    def build_fsdp(self,module):
        module=old_fsdp(self,module)
        emit('fsdp_layout', mesh=str(self.device_mesh), units=[{'name':n,'class':type(m).__name__} for n,m in module.named_modules() if isinstance(m,impl.FSDPModule)], reserved_bytes=torch.npu.memory_reserved())
        return module
    impl.FSDPEngine._build_fsdp_module=build_fsdp
    old_batch=impl.FSDPEngine.train_batch
    def batch(self,data,loss_function):
        torch.npu.synchronize(); start=time.monotonic()
        ids=data['input_ids']; tokens=int(ids.offsets().diff().sum().item()) if ids.is_nested else int(data['attention_mask'].sum().item())
        result=old_batch(self,data,loss_function)
        torch.npu.synchronize(); elapsed=time.monotonic()-start
        emit('heartbeat',step=getattr(self,'_fixture_step',0)+1,tokens=tokens,seconds=elapsed,tokens_per_second_per_chip=tokens/elapsed,chip_count=dist.get_world_size(),reserved_bytes=torch.npu.memory_reserved(),peak_reserved_bytes=torch.npu.max_memory_reserved())
        self._fixture_step=getattr(self,'_fixture_step',0)+1
        return result
    impl.FSDPEngine.train_batch=batch
    old_load=CheckpointHandler.load_checkpoint
    def load(self):
        path=self._determine_resume_path()
        if path:
            rank=self.rank; world=dist.get_world_size()
            for name in (f'model_world_size_{world}_rank_{rank}.pt',f'optim_world_size_{world}_rank_{rank}.pt',f'extra_state_world_size_{world}_rank_{rank}.pt',f'data_{self.dp_rank}.pt'):
                if not (Path(path)/name).is_file(): raise RuntimeError('missing resume state '+name)
            extra=torch.load(Path(path)/f'extra_state_world_size_{world}_rank_{rank}.pt',map_location='cpu',weights_only=False)
            if extra.get('rng') is None or extra.get('lr_scheduler') is None: raise RuntimeError('missing RNG or scheduler')
            if not {'cpu','numpy','random','npu'} <= set(extra['rng']): raise RuntimeError('incomplete RNG state')
        step=old_load(self)
        if path and step!=1: raise RuntimeError('expected step 1 checkpoint')
        self.engine._fixture_step=step
        emit('resume',step=step,path=path)
        return step
    CheckpointHandler.load_checkpoint=load
    class Stopped(Exception): pass
    old_save=CheckpointHandler.save_checkpoint
    def save(self,step):
        old_save(self,step)
        path=Path(self.default_local_dir)/f'global_step_{step}'
        rank=self.rank; world=dist.get_world_size()
        for name in (f'model_world_size_{world}_rank_{rank}.pt', f'optim_world_size_{world}_rank_{rank}.pt', f'extra_state_world_size_{world}_rank_{rank}.pt', f'data_{self.dp_rank}.pt'):
            if not (path/name).is_file(): raise RuntimeError('missing saved state '+name)
        extra=torch.load(path/f'extra_state_world_size_{world}_rank_{rank}.pt',map_location='cpu',weights_only=False)
        if not extra.get('lr_scheduler') or not {'cpu','numpy','random','npu'} <= set(extra.get('rng',{})): raise RuntimeError('incomplete saved scheduler or RNG')
        emit('checkpoint_saved',step=step,path=str(path))
        if os.environ.get('FIXTURE_STOP_AFTER')=='1' and step==1: raise Stopped()
    CheckpointHandler.save_checkpoint=save
    old_fit=SFTTrainer.fit
    def fit(self):
        try: return old_fit(self)
        except Stopped: emit('controlled_stop',step=1)
    SFTTrainer.fit=fit
