"""Confirms, by construction, that verl's exact LoRA application (peft.get_peft_model with the
R3 config) freezes every base weight and trains only the adapters -- the mechanism the checkpoint
diff (inspect_ckpt.py) is corroborating, not re-deriving."""
import torch
import transformers
from peft import LoraConfig, TaskType, get_peft_model

path = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"
targets = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
           "in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b", "out_proj"]
model = transformers.AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16)
model = get_peft_model(model, LoraConfig(task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32,
                                          lora_dropout=0.05, target_modules=targets, bias="none"))
total = sum(p.numel() for p in model.parameters())
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"total params {total}, trainable {trainable} ({100 * trainable / total:.3f}%)")
trainable_names = {n for n, p in model.named_parameters() if p.requires_grad}
assert all("lora_" in n for n in trainable_names), "a non-LoRA param is trainable"
assert trainable_names, "no trainable params at all"
assert any("embed_tokens" in n for n, _ in model.named_parameters())  # embeddings exist
assert not any("embed_tokens" in n and p.requires_grad for n, p in model.named_parameters())  # frozen
assert not any(n.endswith("lm_head.weight") and p.requires_grad for n, p in model.named_parameters())
print("every trainable param is a LoRA adapter; embeddings and lm_head frozen: OK")
