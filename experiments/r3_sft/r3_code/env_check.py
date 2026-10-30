"""Environment and model-structure check inside the training image (short, attached). Not part of the pipeline."""
import os
import sys
import time

t0 = time.time()
import torch
import torch_npu  # noqa: F401
import transformers
import peft

print("torch", torch.__version__, "transformers", transformers.__version__, "peft", peft.__version__, flush=True)
try:
    import fla
    print("fla", getattr(fla, "__version__", "?"), flush=True)
except Exception as e:  # noqa: BLE001
    print("fla import failed:", repr(e)[:200], flush=True)
print("PYTHONPATH", os.environ.get("PYTHONPATH"), flush=True)
print("npu count", torch.npu.device_count(), flush=True)
path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"
from transformers import AutoModelForCausalLM, AutoTokenizer
tok = AutoTokenizer.from_pretrained(path)
model, info = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, output_loading_info=True)
print("class", type(model).__name__, "missing", len(info.get("missing_keys", [])), "unexpected", len(info.get("unexpected_keys", [])), flush=True)
print("config model_type", model.config.model_type, "archs", getattr(model.config, "architectures", None), flush=True)
from collections import Counter
suffix = Counter()
for n, m in model.named_modules():
    if isinstance(m, torch.nn.Linear):
        suffix[n.split(".")[-1]] += 1
print("linear suffix counts", dict(suffix), flush=True)
print("any visual module:", any("visual" in n for n, _ in model.named_modules()), flush=True)
print("n params", sum(p.numel() for p in model.parameters()), flush=True)
print("first state keys", list(model.state_dict().keys())[:4], flush=True)
print("tie_word_embeddings", getattr(model.config, "tie_word_embeddings", None), flush=True)
cfg = model.config
tc = getattr(cfg, "text_config", cfg)
print("layer_types", getattr(tc, "layer_types", None)[:8] if getattr(tc, "layer_types", None) else None, "n_layers", tc.num_hidden_layers, flush=True)
ids = tok(" yes", add_special_tokens=False)["input_ids"], tok(" card_arrival", add_special_tokens=False)["input_ids"]
print("tok", ids, "eos", tok.eos_token_id, tok.eos_token, "pad", tok.pad_token_id, flush=True)
x = torch.randint(0, 1000, (2, 64)).npu()
model = model.npu().eval()
with torch.no_grad():
    out = model(input_ids=x, logits_to_keep=3)
print("logits", tuple(out.logits.shape), out.logits.dtype, "elapsed", round(time.time() - t0, 1), flush=True)
