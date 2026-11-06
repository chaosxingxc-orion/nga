"""torch.distributed.run entry. Imports torch_npu before verl device detection."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
import torch_npu  # registers the real npu device before verl import
from verl.utils.device import get_device_name
if get_device_name() != 'npu' or not torch.npu.is_available():
    raise RuntimeError('NPU unavailable; this entry requires actual Ascend devices')
import hooks
hooks.install()
from verl.trainer.sft_trainer import main
main()
