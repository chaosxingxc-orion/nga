"""Render commands; no model loading or device probing."""
import argparse,json,shlex
from pathlib import Path

def command(config, output, phase):
    c=config; root=c['verl_root']; out=Path(output)
    args=[f"model.path={c['model']}",'model.trust_remote_code=False','engine.strategy=fsdp2','engine.fsdp_size=4','engine.model_dtype=bf16','engine.ulysses_sequence_parallel_size=1','engine.use_torch_compile=False','engine.seed=42','engine.full_determinism=True','model.lora_rank=8','model.lora_alpha=16','model.target_modules=all-linear','model.use_remove_padding=False','+model.override_config.attn_implementation=sdpa',f'data.train_files={root}/data/sft_train.parquet','data.val_files=null',f'data.custom_cls.path={root}/code/raw_sft_dataset.py','data.custom_cls.name=RawCompletionSFTDataset','data.train_batch_size=4','data.micro_batch_size_per_gpu=1','data.max_length=256','data.use_dynamic_bsz=False','optim.lr=1e-5','trainer.logger=console','trainer.total_epochs=1','trainer.total_training_steps=2','trainer.n_gpus_per_node=4','trainer.save_freq=1','trainer.test_freq=-1','trainer.device=npu',f'trainer.default_local_dir={out}/ckpt','checkpoint.save_contents=[model,optimizer,extra]','checkpoint.load_contents=[model,optimizer,extra]']
    args += ['trainer.resume_mode=resume_path',f'trainer.resume_from_path={out}/ckpt/global_step_1'] if phase=='resume' else ['trainer.resume_mode=disable']
    return ['python3','-P','-m','torch.distributed.run','--standalone','--nnodes=1','--nproc_per_node=4',str(Path(__file__).parent/'entry.py'),*args]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--phase',choices=['phase1','resume','continuous'],default='phase1');p.add_argument('--config',default=str(Path(__file__).parent/'config.json'));a=p.parse_args()
    print(shlex.join(command(json.loads(Path(a.config).read_text()),a.output,a.phase)))
