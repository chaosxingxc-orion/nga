# verl + vllm-ascend training environment (2026-10-29)

Status: see full detail in `/mnt/cephfs/xingchao/docker/rl_ascend_verl_20261029/README.md`. This
file is the short pointer the orchestrator asked for; it is not committed by this agent.

## What the image is

`agentic-rl-ascend-verl:20261029`, built `FROM agentic-rl-ascend:20261026`
(torch 2.7.1 + torch_npu 2.7.1, vllm 0.11.0+empty, vllm-ascend 0.11.0rc2, ray 2.51.1,
transformers 4.57.1, Python 3.11, linux/arm64) with **verl v0.7.0**
(commit `f9c855f7cf04d603c9546bc01776c74806a879c1`) installed editable at `/opt/verl`,
`--no-deps --no-build-isolation`, FSDP backend only (no Megatron/MindSpeed). No change to any of
the base image's pinned torch/torch_npu/vllm/vllm-ascend/ray/transformers versions; only three
extra pure-dependency wheels were added (`mathruler`, `qwen_vl_utils`, `hf_transfer`, from a local
wheelhouse). Image id `sha256:c4a9850e2162aba5f84201cd0096adbe3ee8ad1720c98e1200de8c32841926aa`,
identical on both `npu` (100.100.135.175) and `npu2` (100.100.135.181) after `docker save`/`load`
via cephfs.

Why v0.7.0: it is the verl release whose own Ascend docs pin torch/torch_npu 2.7.1, vllm v0.11.0,
vllm-ascend v0.11.0rc1, CANN 8.3.RC1 — the closest match to this base image's pins (CANN 8.3.RC2,
vllm-ascend 0.11.0rc2). Newer verl releases (0.7.1+) move to torch/torch_npu 2.8.0, which would
require upgrading the base image; that was explicitly avoided.

## How to launch a pair

```bash
CODE_DIR=/abs/path/to/code bash /mnt/cephfs/xingchao/docker/rl_ascend_verl_20261029/start_pair.sh <k> [cmd...]
```

`k` in `0..3`; pair `k` is bound to physical NPUs `2k, 2k+1`, so one 8-NPU host runs 4 instances.
Unique container name `nga-verl-pair<k>`, unique Ray/TensorBoard/node-manager/object-manager/metrics
ports per pair (base port `20000 + 100k`), mounts `CODE_DIR` at `/workspace` and `/mnt/cephfs` at
the same path. Refuses to start on a busy NPU (checks `npu-smi info -t usages`), a name collision,
or a port collision; `DRY_RUN=1` prints the command without touching anything.

## What was validated, and how

CPU only (no NPU touched), passed: image imports (torch/torch_npu/vllm/vllm_ascend/ray/transformers/
tensordict all at the pinned versions, `verl 0.7.0.dev0` imports), hydra composes the GRPO/vllm
`ppo_trainer.yaml` config, the synthetic smoke dataset loads through verl's `RLHFDataset`, the
rule-based reward scores correct/incorrect answers correctly, `Qwen3-0.6B`'s `AutoConfig` reads
`model_type=qwen3`, and the full smoke training command composes correctly via Hydra `--cfg job`
(2 NPUs, `device=npu`, `adv_estimator=grpo`, `rollout.name=vllm`, 3 steps, correct data paths).

On NPU (confirmed idle, both hosts, then released): `torch_npu.npu.device_count()` reports exactly
2 for a pair, in both device-mount modes of the launcher. **Actual GRPO training could not be run**:
every NPU compute op — reproduced with a bare `torch.ones(..., device="npu")` directly in the
*unmodified* base image on both hosts (910B3 and 910B4-1 chips) — fails with
`Parse dynamic kernel config fail / Failed to ParseDynamicKernels`. Root cause found by inspection:
the base image's CANN 8.3.RC2 toolkit only ships op kernel binaries for SoC `ascend910_93`; it has
no kernel config for the `910B` family at all, which is what both NPU hosts actually have. This is
a **pre-existing base-image/host incompatibility, unrelated to verl or to this Dockerfile** — the
base image's own README already only ever validated CPU tensors and imports. No real training run
was possible on either host for this reason, not for lack of free NPUs (both hosts were idle, 0
NPU-resident processes at the time of testing).

## transformers 5.x (secondary)

Not the default. In a side `--system-site-packages` venv with transformers 5.21.0 (CPU only):
torch_npu/vllm/vllm_ascend still import; `Qwen3.5-0.8B` config/tokenizer load, a meta-device model
builds, and a real CPU forward pass runs. verl 0.7.0 itself fails to import under transformers 5.x
(`AutoModelForVision2Seq` was removed/renamed to `AutoModelForImageTextToText` in 5.x); a one-line
monkey-patch alias fixes the import, but was not carried further (not patched into the shipped
image, not tested through verl's actual model-loading path, not tested against vllm's own
assumptions about the transformers version).

## Deliverable paths

- `/mnt/cephfs/xingchao/docker/rl_ascend_verl_20261029/` — `Dockerfile`, `build.sh`,
  `start_pair.sh`, `smoke_test.py`, `packages-image.txt`, `base-packages.txt`,
  `package-diff-vs-base.txt`, `image-info.txt`, `build.log`, `smoke-test.log`,
  `smoke-test-npu175.log`, `smoke-test-npu-pair3.log`, `README.md` (full detail, including the
  CANN/910B root-cause finding and the transformers 5.x results).
- `verl_smoke/` under the same directory: `make_data.py`, `run.sh`, `check_data_and_config.py`, and
  their logs (`dryrun.log`, `check_data_and_config.log`, `run-pair3.log`).
- `agentic-rl-ascend-verl_20261029_arm64.tar.gz` + `SHA256SUMS` — exported archive, kept (cephfs had
  5.1 TB free at the time).
- Generated smoke-run output (not committed, cephfs only, per repository convention):
  `/mnt/cephfs/xingchao/experiments/jev/verl_smoke/pair3_20261029T072718/run.log`.

## Orchestrator verification and the way forward (2026-10-29)

The blocking finding above was re-checked independently and holds:

- Both hosts carry **910B** silicon: `npu` reports `910B3`, `npu2` reports `910B4-1`.
- The base image's CANN 8.3.RC2 ships exactly one SoC kernel directory,
  `ascend910_93`, which is the A3 family. There is no `ascend910b` directory. A 910B chip
  therefore has no executable op kernels in this image, which is consistent with the
  `Failed to ParseDynamicKernels` error. The custom image cannot run a single Ascend op on
  either host, and no verl or vllm-ascend version would change that.

**A ready-made replacement already exists on `npu2`.** The image
`quay.io/ascend/verl:verl-8.3.rc1-910b-ubuntu22.04-py3.11-latest` carries the matching
`ascend910b` kernel set and an otherwise near-identical stack:

| Component | Custom image (`agentic-rl-ascend-verl:20261029`) | Official Ascend verl 910b image |
| --- | --- | --- |
| CANN kernels | `ascend910_93` only, wrong family | `ascend910b`, matches both hosts |
| CANN version | 8.3.RC2 | 8.3.RC1 |
| torch / torch_npu | 2.7.1 / 2.7.1 | 2.7.1 / 2.7.1 |
| vllm / vllm-ascend | 0.11.0+empty / 0.11.0rc2 | 0.11.0+empty / 0.11.0rc1 |
| transformers | 4.57.1 | 4.57.6 |
| ray | 2.51.1 | 2.53.0 |
| verl | 0.7.0, installed by us | 0.8.0.dev0, preinstalled |

A sibling tag ending `-a3-` is also present on `npu2`; that one is for the A3 family and is
**not** the one to use here.

**Recommended next step**, to be confirmed before anyone spends time on it: rebase the work on
the official 910b image and keep from the custom build only the parts that carry our own
decisions, namely `start_pair.sh` (the 2-NPU pair launcher) and `verl_smoke/`. Two things must
be checked on the rebased image before it is adopted: whether its
`vllm_ascend/device_allocator/camem.py` already contains the sleep-mode GC backport the team
added to the current base image (the file exists at `/vllm-ascend/vllm_ascend/device_allocator/camem.py`),
and whether a real GRPO step now runs on a 2-NPU pair. The custom image stays on cephfs as a
record; it should not be used for training.

**Block 2 has changed.** At the time of this check both hosts were idle: all 8 chips on each
report no NPU-resident processes, 0% AICore, and only the ~3.4 GB baseline HBM reservation. The
vLLM deployment and the `minimax_m31_flash` container that held the cards on 2026-10-28 are
gone. This has not been confirmed with the machine owner, so it should be treated as an
opportunity to be checked rather than as a granted allocation.

**Housekeeping note.** Host `npu` was left running 16 idle `saea-base:20261027` containers
created during this session's build window, none of which hold a davinci device. They are
harmless but should be cleaned up by whoever created them.

