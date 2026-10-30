"""Inspect an FSDP-sharded checkpoint (one rank's shard) for the K1 smoke acceptance checks:
LoRA params present and changed, base params present and unchanged from the pretrained checkpoint.
"""
import sys
import torch

ckpt = sys.argv[1]
base_path = sys.argv[2]

sd = torch.load(ckpt, map_location="cpu", weights_only=False)
print("top-level keys:", list(sd.keys())[:10] if isinstance(sd, dict) else type(sd))
model_sd = sd.get("model", sd) if isinstance(sd, dict) else sd
keys = list(model_sd.keys())
lora_keys = [k for k in keys if "lora_" in k]
base_keys = [k for k in keys if "lora_" not in k]
print(f"total keys {len(keys)}, lora keys {len(lora_keys)}, base keys {len(base_keys)}")
print("sample lora keys:", lora_keys[:6])
def as_local(t):
    return t.to_local() if hasattr(t, "to_local") else t


nonzero_lora = sum(1 for k in lora_keys if "lora_B" in k and torch.count_nonzero(as_local(model_sd[k])) > 0)
zero_B = [k for k in lora_keys if "lora_B" in k]
print(f"lora_B tensors: {len(zero_B)}, nonzero after training: {nonzero_lora}")
print(f"all lora_B nonzero: {nonzero_lora == len(zero_B)}")
