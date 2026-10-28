# Server 175 (k8s-node1) — probe on 2026-10-28

- 256 CPU cores, ~2 TB RAM, Python 3.10.12, `pyarrow` 21 present; `torch` is the CPU build; **no `torch_npu`, no `transformers`** in the system Python.
- 8 Ascend NPUs; at probe time **all 8 were held by a vLLM deployment** (`VLLMWorker_DP`, ~59 GB HBM each). Do not schedule on them without coordination.
- `/mnt/cephfs` mounted (66 TB, 91% used, 6 TB free); the dataset and model mirrors are visible. `/home` has 70 GB free.
- CANN toolkit is installed under `/usr/local/Ascend`; a container or venv with `torch_npu` + `transformers` is still needed for T4–T7.

What is needed from the owner of the box: which NPUs (or a time window) can be used, and whether a `torch_npu` image is available.
