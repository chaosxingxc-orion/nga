# Fixed rc1 Qwen3.8 DEV scorer

These source files preserve the exact reviewed scorer running in the four-chip reference-save retry. The repair gives the reference-logits temporary file a `.pt` suffix accepted by PyTorch's writer; scoring, tensor dtype and reference tolerances are unchanged. The retained failed attempt and its three completed items remain historical evidence. The fresh attempt uses its own source identity and recomputes those items.

Run the focused regression from the repository root:

```sh
TORCH_DEVICE_BACKEND_AUTOLOAD=0 PYTHONDONTWRITEBYTECODE=1 python3 tools/qwen38_dev/test_reference_export.py
```

It executes the scorer's reference-export branch with a fake model/tokenizer/device layer and real CPU PyTorch serialization. It checks exact tensors and scores, manifest shape/dtype/token IDs/checksum, atomic replacement and cleanup, including failure before replacement preserving the previous target. It does not run a model or establish NPU numerical accuracy. `test_cpu.py` supplies fixture helpers; its historical standalone suite also references a separate scorer package and is not the command for this snapshot.

`SOURCE-PINS.json` binds these exact files and the accepted deployment manifest/review. This is source preservation, not a standalone launcher or a new release. Production launch remains configuration-driven through the existing fixed rc1 stage and resource controller. Actual completion and scientific acceptance require the retained run's own terminal and report evidence.
