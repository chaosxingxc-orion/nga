"""Run a frozen probe stage with explicit NPU HF32 disabled."""
import runpy
import sys
from pathlib import Path
import torch
import torch_npu  # noqa: F401

torch.npu.conv.allow_hf32 = False
torch.npu.matmul.allow_hf32 = False
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
