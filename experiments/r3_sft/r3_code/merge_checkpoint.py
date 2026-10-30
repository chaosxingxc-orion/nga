"""Merge an R3 LoRA checkpoint into a plain HF directory the shared scorer can load directly.

    python3 -P merge_checkpoint.py <verl ckpt global_step_N dir> <out dir> [--lora-alpha 32]

verl's own `python -m verl.model_merger merge --backend fsdp` does NOT fold a LoRA delta into the
base weights: it pops every `lora_*` key out of the gathered state dict into a separate
`lora_adapter/` (safetensors + a `adapter_config.json` that hardcodes `"lora_alpha": 0`, i.e. a
scaling of 0/r -- the adapter it writes is a documented no-op if loaded as-is: see
base_model_merger.py `save_lora_adapter`'s own comment, "lora_alpha is not set. An error should be
raised to inform the user to set it manually" -- no such error is raised). Tried first (see git
history / this task's report): fixing the written `lora_alpha` and reloading the adapter with
`peft.PeftModel.from_pretrained` + `merge_and_unload()` -- that path FAILS differently: peft reports
"Found missing adapter keys while loading the checkpoint" for every single LoRA tensor (a key-
naming mismatch between what verl's exporter writes and what this peft version's loader expects
for this HF wrapper class), so the reloaded model is silently un-merged (confirmed: probe logits
identical to the untouched base, caught by this script's own pre-save assertion, not missed).

This script avoids that export/reload round trip entirely: it calls verl's own `FSDPModelMerger`
far enough to get the gathered (unsharded) state dict -- the exact same dict `merge_and_save` would
pass to `save_hf_model_and_tokenizer` -- then folds every LoRA pair into its base weight ITSELF
(`W' = W + (lora_alpha / r) * B @ A`, the standard LoRA merge, r and alpha from this round's
training config) before handing the already-plain (no `lora_*` keys left) dict to verl's own
`save_hf_model_and_tokenizer` (so `save_lora_adapter` inside it is a no-op: `len(lora_params_names)
== 0`) for the HF config/tokenizer/safetensors writing verl already gets right.
"""
import argparse
import json
import os
import sys


def gather_state_dict(ckpt_dir):
    from verl.model_merger.base_model_merger import ModelMergerConfig
    from verl.model_merger.fsdp_model_merger import FSDPModelMerger

    config = ModelMergerConfig(operation="merge", backend="fsdp", target_dir="unused", local_dir=ckpt_dir,
                                hf_model_config_path=os.path.join(ckpt_dir, "huggingface"))
    merger = FSDPModelMerger(config)
    world_size = merger._get_world_size()
    rank0 = merger._load_rank_zero_state_dict(world_size)
    mesh, mesh_dim_names = merger._extract_device_mesh_info(rank0, world_size)
    total_shards, mesh_shape = merger._calculate_shard_configuration(mesh, mesh_dim_names)
    print(f"gathering {total_shards} FSDP shard(s), mesh {mesh_shape}", flush=True)
    state_dict = merger._load_and_merge_state_dicts(world_size, total_shards, mesh_shape, mesh_dim_names)
    return merger, state_dict


def fold_lora(state_dict, lora_alpha, lora_r):
    import torch
    pairs = {}
    for k in list(state_dict.keys()):
        if k.endswith(".lora_A.default.weight"):
            pairs.setdefault(k[: -len(".lora_A.default.weight")], {})["A"] = state_dict.pop(k)
        elif k.endswith(".lora_B.default.weight"):
            pairs.setdefault(k[: -len(".lora_B.default.weight")], {})["B"] = state_dict.pop(k)
    if not pairs:
        raise SystemExit("no lora_A/lora_B keys found in the gathered state dict: not a LoRA checkpoint?")
    scaling = lora_alpha / lora_r
    print(f"folding {len(pairs)} LoRA pairs, scaling = lora_alpha/r = {lora_alpha}/{lora_r} = {scaling}", flush=True)
    for rest, d in pairs.items():
        assert "A" in d and "B" in d, rest
        base_key = rest + ".base_layer.weight"
        assert base_key in state_dict, f"no base weight for {rest}"
        A, B = d["A"].float(), d["B"].float()
        observed_r = min(A.shape[0], B.shape[1])
        assert observed_r == lora_r, f"{rest}: observed rank {observed_r} != --lora-r {lora_r}"
        delta = scaling * (B @ A)
        base = state_dict[base_key].float()
        assert delta.shape == base.shape, (rest, delta.shape, base.shape)
        state_dict[base_key] = (base + delta).to(torch.bfloat16)
    clean = {}
    for k, v in state_dict.items():
        nk = (k.replace("base_model.model.", "", 1)
                .replace(".base_layer.weight", ".weight")
                .replace(".base_layer.bias", ".bias"))
        clean[nk] = v
    return clean, len(pairs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ckpt_dir", help="e.g. .../ckpt/global_step_40")
    ap.add_argument("out_dir")
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-r", type=int, default=16)
    a = ap.parse_args()

    import torch

    merger, state_dict = gather_state_dict(a.ckpt_dir)

    # probe BEFORE folding (base-only forward, via the raw tensors) to compare against after
    probe_key_q = next(k for k in state_dict if k.endswith("layers.3.self_attn.q_proj.base_layer.weight"))
    before_sample = state_dict[probe_key_q].clone().float()

    clean, n_pairs = fold_lora(state_dict, a.lora_alpha, a.lora_r)
    probe_key_q_clean = probe_key_q.replace("base_model.model.", "", 1).replace(".base_layer.weight", ".weight")
    after_sample = clean[probe_key_q_clean].float()
    max_abs_diff = float((after_sample - before_sample).abs().max())
    print(f"sample weight max|after_fold - before_fold| ({probe_key_q_clean}) = {max_abs_diff:.6f}", flush=True)
    assert max_abs_diff > 1e-4, "folding left the sampled base weight unchanged: LoRA was not applied"

    os.makedirs(a.out_dir, exist_ok=True)
    merger.config.target_dir = a.out_dir
    merger.save_hf_model_and_tokenizer(clean)
    json.dump({"source_ckpt": a.ckpt_dir, "lora_alpha": a.lora_alpha, "lora_r": a.lora_r,
               "n_lora_pairs_folded": n_pairs, "sample_weight_max_abs_delta": max_abs_diff},
              open(os.path.join(a.out_dir, "r3_merge_manifest.json"), "w"), indent=2)
    print(f"merged HF model at {a.out_dir}")


if __name__ == "__main__":
    main()
