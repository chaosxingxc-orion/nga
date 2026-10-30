"""Monkeypatch: give verl's FSDP engine a OneCycleLR schedule.

verl's FSDP engine (workers/engine/fsdp/transformer_impl.py, `_build_lr_scheduler`) only implements
`lr_scheduler_type in {"constant", "cosine"}`; anything else raises NotImplementedError. R3-SFT-
PREREG §7.2 pre-registers Kev's own schedule, `OneCycleLR(max_lr=lr, pct_start=0.1)`
(kev/train.py:588: `torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[a.lr, a.head_lr or a.lr],
total_steps=max(steps, 1), pct_start=0.1)`; the two-entry max_lr is one value per param group, base
LoRA params and Kev's pointer head; this run has no pointer head, so a single scalar is the same
thing). No verl file is edited: the same technique as nga_gdn_patch.py / nga_lora_dropout_patch.py,
wrapping the bound method on the class object so every subsequent instance picks it up.

Enable: VERL_USE_EXTERNAL_MODULES=nga_onecycle_patch (comma-combine with the other patches),
env NGA_ONECYCLE=1. NOT triggered by `optim.lr_scheduler_type=onecycle`: `FSDPOptimizerConfig.
__post_init__` (workers/config/optimizer.py) asserts `lr_scheduler_type in ["constant", "cosine"]`
at CONFIG CONSTRUCTION time, before this patch's replaced `_build_lr_scheduler` ever runs, so
"onecycle" as the hydra value is rejected before the patch gets a chance (confirmed: the literal
AssertionError from that line, R3 smoke run 1, 2026-10-29). Pass `optim.lr_scheduler_type=cosine`
(a valid, otherwise-inert placeholder: the env flag below overrides it unconditionally) and set
NGA_ONECYCLE=1 instead.
"""
import functools
import os

_INSTALLED = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    if os.environ.get("NGA_ONECYCLE", "0") not in ("1", "true", "True"):
        return
    import torch
    import verl.workers.engine.fsdp.transformer_impl as ti

    cls = ti.FSDPEngine
    orig = cls._build_lr_scheduler

    @functools.wraps(orig)
    def patched(self, optimizer):
        optim_config = self.optimizer_config
        total_steps = optim_config.total_training_steps
        if self.rank == 0:
            print(f"[nga_onecycle_patch] OneCycleLR max_lr={optim_config.lr} total_steps={total_steps} pct_start=0.1", flush=True)
        return torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=optim_config.lr,
                                                    total_steps=max(total_steps, 1), pct_start=0.1)

    cls._build_lr_scheduler = patched
    _INSTALLED = True
    print("[nga_onecycle_patch] installed", flush=True)


install()
