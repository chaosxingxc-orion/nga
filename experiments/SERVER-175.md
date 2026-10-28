# Server 175 (k8s-node1) — probe on 2026-10-28

- 256 CPU cores, ~2 TB RAM, Python 3.10.12, `pyarrow` 21 present; `torch` is the CPU build; **no `torch_npu`, no `transformers`** in the system Python.
- 8 Ascend NPUs; at probe time **all 8 were held by a vLLM deployment** (`VLLMWorker_DP`, ~59 GB HBM each). Do not schedule on them without coordination.
- `/mnt/cephfs` mounted (66 TB, 91% used, 6 TB free); the dataset and model mirrors are visible. `/home` has 70 GB free.
- CANN toolkit is installed under `/usr/local/Ascend`; a container or venv with `torch_npu` + `transformers` is still needed for T4–T7.

What is needed from the owner of the box: which NPUs (or a time window) can be used, and whether a `torch_npu` image is available.

## Images available on the NPU hosts — checked 2026-10-28

Both `npu` (100.100.135.175, k8s-node1, 910B3) and `npu2` (100.100.135.181, A800I-03, 910B4-1)
carry the two images built earlier this week. The build records live in
`/mnt/cephfs/xingchao/docker/` (shared disk, visible from both).

| image | where | state |
| --- | --- | --- |
| `agentic-rl-ascend:20261026` | both hosts, id `8a723f6bc41a` | loaded; id matches the recorded `sha256:8a723f6b…` in `rl_ascend_20261026/image-info.txt`; import smoke recorded in `smoke-test.log` (`RL_IMPORT_SMOKE_OK`) |
| `saea-base:20261027` | both hosts (175 `477228c6fb8b`, 181 `ebd6a3c104fc`) | built + smoke passed; `IMAGE_BUILD_DONE` in `saea-base/build-20261027T195734.log` |

`agentic-rl-ascend:20261026` is the default environment for initial experiments
(`rl_ascend_20261026/README.md`, `README_RL.txt`). Start it with
`start_rl_container.sh`, which mounts `/usr/local/Ascend/driver` and the `davinci`
devices; a bare `docker run` fails at `import torch_npu` with
`libascend_hal.so: cannot open shared object file`.

**Blocker for the smallest-model pair.** The RL image pins `transformers==4.57.1`
(`rl_ascend_20261026/packages-image.txt`). `Qwen3.5-0.8B` declares
`model_type: qwen3_5` / `Qwen3_5ForConditionalGeneration`, which first appears in
`transformers` 5.x — the 5.21.0 wheel staged under `saea-base/wheelhouse/` has
`models/qwen3_5`, 4.57.1 does not. So the RL image can load `Qwen3-0.6B`
(`model_type: qwen3`) but not its hybrid counterpart, i.e. it cannot run the
defect-11 control (T4) as a pair. Either add a `transformers` 5.x venv on top of
the RL image, or use `saea-base:20261027` (image python has `transformers` 5.21.0,
`torch` 2.10.0+cpu) and add `torch_npu` there.

NPU occupancy is unchanged: on both hosts all 8 chips sit at ~59 GB HBM per chip
under `VLLMWorker_DP`, plus a `minimax_m31_flash` container up on each. Nothing
is free to schedule on without coordination.
