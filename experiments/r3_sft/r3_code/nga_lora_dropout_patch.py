"""Monkeypatch: give verl's FSDP engine a configurable LoRA dropout.

verl's FSDP engine (workers/engine/fsdp/transformer_impl.py, `_build_lora_module`) builds
`peft.LoraConfig(task_type=..., r=..., lora_alpha=..., target_modules=..., exclude_modules=...,
bias="none")` with NO `lora_dropout` key, so every LoRA run on this stack silently gets peft's
default (0.0), regardless of any `+model.lora_dropout=...` override on the command line (there is
no such config field: workers/config/model.py's HFModelConfig has no `lora_dropout` attribute, and
the dict literal above is fixed at the five keys it lists). R3-SFT-PREREG §7.2 pre-registers
dropout 0.05, so this gap must be closed without editing verl's file.

No verl file is edited. The module object `verl.workers.engine.fsdp.transformer_impl` is the
Python namespace `_build_lora_module`'s `LoraConfig(...)` call resolves against at CALL time (not
def time), so replacing the attribute on that module object changes every subsequent call,
exactly like `nga_gdn_patch.py` replaces `Qwen3_5GatedDeltaNet.__init__` in the same style.

Enable: VERL_USE_EXTERNAL_MODULES=nga_lora_dropout_patch (comma-combine with nga_gdn_patch),
env NGA_LORA_DROPOUT=0.05 (default 0.0, i.e. unchanged peft behaviour if unset).
"""
import functools
import os

_INSTALLED = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    dropout = float(os.environ.get("NGA_LORA_DROPOUT", "0.0"))
    if dropout == 0.0:
        return
    from peft import LoraConfig as _LoraConfig
    import verl.workers.engine.fsdp.transformer_impl as _ti

    @functools.wraps(_LoraConfig)
    def _LoraConfigWithDropout(*a, **kw):
        kw.setdefault("lora_dropout", dropout)
        return _LoraConfig(*a, **kw)

    _ti.LoraConfig = _LoraConfigWithDropout
    _INSTALLED = True
    print(f"[nga_lora_dropout_patch] installed lora_dropout={dropout}", flush=True)


install()
