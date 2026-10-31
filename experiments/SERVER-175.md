# Server 175 (k8s-node1) — probe on 2026-10-28

## Connection correction, 2026-10-31

Use SSH alias **`npu`**, which resolves to `100.100.135.175`, and verify
`hostname` is `k8s-node1`. The literal command `ssh 175` resolved to `0.0.0.175`
in the current environment and timed out; that failure is not evidence that the
actual server is unavailable. A fresh `ssh npu` observation succeeded on
2026-10-31. Current allocation and container identity must still be checked
before launching; the older occupancy notes below are dated observations.

Read-only observation saved at
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_live_observation_20261031T030502Z/OBSERVATION.json`
(SHA256 `3af993b83c57ce668932d9152838b1d80b39de3d410b2ed5c5bc7c852ef65bef`).
All eight NPUs had no running process at this observation; chip 4 remained
allocated to E38 2B and chip 1 was the only entry in `free[]`. The E38 2B NPU and
CPU verifier containers were both actually exited/0 with their recorded
StartedAt/FinishedAt. This observation is not a release approval.

## Historical probe, 2026-10-28

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

## Update 2026-10-29

Two facts above have changed, and one new blocker was found.

**NPUs are free.** Both hosts now report 8 idle chips: no NPU-resident processes, 0% AICore,
only the ~3.4 GB baseline HBM reservation per chip. The vLLM deployment and the
`minimax_m31_flash` containers that held all cards on 2026-10-28 are gone. The machine owner has
not granted an allocation, so this is an opportunity to confirm, not a reservation.

**Chip family and the CANN kernel mismatch.** `npu` is `910B3`, `npu2` is `910B4-1`. The CANN
8.3.RC2 toolkit inside `agentic-rl-ascend:20261026` ships op kernels for SoC `ascend910_93` only,
which is the A3 family; it has no `ascend910b` kernel set. No Ascend op can execute inside that
image on either host, which is why `import torch_npu` succeeds while a bare
`torch.ones(..., device="npu")` fails with `Failed to ParseDynamicKernels`. The base image's own
README only ever claimed CPU tensor and import validation, so this was never caught before.

**Where the working stack is.** `npu2` already holds
`quay.io/ascend/verl:verl-8.3.rc1-910b-ubuntu22.04-py3.11-latest`, which carries the matching
`ascend910b` kernels with torch 2.7.1, torch_npu 2.7.1, vllm 0.11.0, vllm-ascend 0.11.0rc1 and
verl 0.8.0.dev0 preinstalled. See `ENV-VERL.md` for the comparison and the recommended rebase.

**Transformers remains split.** The 4.57.x line cannot load `Qwen3.5-0.8B` (`model_type: qwen3_5`).
Under transformers 5.21.0 that model loads and runs a CPU forward pass, but verl 0.7.0 fails to
import because `AutoModelForVision2Seq` was renamed; a one-line alias fixes the import and has not
been validated further.
