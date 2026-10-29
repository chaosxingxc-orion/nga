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


## Outcome: official 910b image working on `npu` (2026-10-29)

- Image `quay.io/ascend/verl:verl-8.3.rc1-910b-ubuntu22.04-py3.11-latest`, id `sha256:6023dda1d354...`, now present and identical on `npu` and `npu2` (transferred via `docker save` to cephfs, then `docker load`).
- Real NPU compute verified on `npu` (910B3): device_count, ones/arithmetic/`.cpu()` round trip, fp32 and bf16 matmul all pass, both in a plain container and through the ported pair launcher (pair 3, NPUs 6,7: exactly 2 visible devices). This replaces the failing `agentic-rl-ascend-verl:20261029`. A real GRPO step has not yet been run.
- The image's `camem.py` does NOT contain the team sleep-mode backport (`gc.collect`, `empty_cache`, `synchronize`); it must be applied.
- transformers 4.57.6 cannot load `qwen3_5`. transformers 5.21.0 (installed side-by-side) loads Qwen3.5-0.8B and runs a bf16 forward and generate on NPU, and vllm/vllm_ascend still import, but `import verl` fails in `verl/models/transformers/npu_patch.py:241` (`Qwen2RMSNorm` missing from `modeling_qwen2_5_vl` in tf 5.x). Default stays 4.57.6; Qwen3.5 training needs a patched `npu_patch.py`.
- Deliverables, launcher, logs and details: `/mnt/cephfs/xingchao/docker/verl_910b_20261029/` (see its `README.md`).

## Derived image `nga-verl-qwen35:20261029`: npu_patch.py made resilient, new verl-side gap found (2026-10-29)

- Built `FROM` the official 910b image on host `npu`: derived image id
  `sha256:0a0a2f5c2c2cdd1ef39d9b9dfece40ea8606de486c6437c6d9e758326f7c10c0`, tag
  `nga-verl-qwen35:20261029`. Only the HF stack is upgraded (`transformers` 4.57.6 -> 5.21.0,
  `huggingface_hub` -> 2.3.0, `tokenizers` -> 0.23.3, `safetensors` -> 0.8.0, plus the HF-stack
  packages these import at module load time: `httpx2`/`httpcore2`/`anyio`/`h11`/`idna`, `hf_xet`, and
  a `rich`/`typer`/`click`/`pygments`/`markdown-it-py`/`mdurl`/`shellingham`/`truststore`/
  `annotated-doc` CLI chain), all installed `--no-deps` from the offline wheelhouse already staged at
  `/mnt/cephfs/xingchao/docker/rl_ascend_verl_20261029/wheelhouse-tf5/`. torch/torch_npu/vllm/
  vllm_ascend/CANN/verl's own code are untouched; `numpy` deliberately excluded and left at the base
  pin.
- `verl/models/transformers/npu_patch.py` unconditionally reaches into named classes in six
  `transformers.models.*` modules (`qwen2`, `qwen2_5_vl`, `qwen3`, `qwen3_moe`, `qwen3_vl`,
  `qwen3_vl_moe`) to install NPU-optimised RMSNorm/SiLU/RoPE. None of these is `qwen3_5`, so none of
  this ever helped our model — but under transformers 5.21.0 one target
  (`modeling_qwen2_5_vl.Qwen2RMSNorm`) was renamed, and the unconditional assignment raised
  `AttributeError` at `import verl` time. Patched (`npu_patch.resilient.patch`, applied in the
  Dockerfile via `git apply`/`patch` fallback) with one helper, `_patch(module, attr_path, value)`,
  that walks `attr_path` with `hasattr` and only `setattr`s if every component exists; otherwise it
  logs `logger.warning(...)` naming exactly what was skipped and returns, instead of raising. No
  patch is deleted; behaviour for every family whose symbols are present is unchanged (verified: the
  other five families still patch silently under transformers 5.21.0). `import verl` now succeeds,
  logging exactly one expected warning for the renamed `Qwen2RMSNorm`.
- **New blocker, found right after, unrelated to `npu_patch.py`:** `import verl.workers.fsdp_workers`
  fails with `ImportError: cannot import name 'AutoModelForVision2Seq' from 'transformers'`.
  transformers 5.21.0 removed this class outright (successor: `AutoModelForImageTextToText`, confirmed
  present). verl imports the old name at module level in five files (`verl/utils/model.py`,
  `verl/utils/checkpoint/fsdp_checkpoint_manager.py`, `verl/experimental/vla/fsdp_workers.py`,
  `verl/model_merger/base_model_merger.py`, `verl/workers/fsdp_workers.py`), about a dozen call sites
  total. The fix looks mechanical (rename to `AutoModelForImageTextToText`, same `_model_mapping`/
  `.register()` interface, no logic change) but was **not applied** — it is outside this task's scope
  (`npu_patch.py` only) and edits verl's own code, so it is reported rather than fixed, per the "no
  elaborate workaround without asking first" instruction.
- Consequently **no verl training step ran** (SFT/GRPO both route through `fsdp_workers`): no loss
  values, no peak-HBM or step-time numbers to report yet. What did verify on NPU in the derived image
  (pair 0, physical NPUs 0,1, both idle before/after): `import verl`, `import vllm`, `import
  vllm_ascend` all pass; `Qwen3.5-0.8B` loads, runs a bf16 forward (finite logits) and greedy
  `generate` ("The capital of France is Paris.") on `npu:0` — this path does not go through
  `fsdp_workers`, so it is unaffected by the blocker above.
- Deliverables: `/mnt/cephfs/xingchao/docker/verl_qwen35_20261029/` — `ctx/Dockerfile`, `build.sh`,
  `npu_patch.resilient.patch`, `image-info.txt`, `packages-image.txt`, `model-test-pair0.log`,
  `README.md` (full detail, including the exact launch command and the five file/line list for the
  `AutoModelForVision2Seq` gap).
