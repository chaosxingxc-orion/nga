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

## `AutoModelForVision2Seq` gap fixed with a shim; still no training step (2026-10-29, same day)

- Coordinator authorized a fix: a compatibility shim rather than editing verl's five files, since
  `AutoModelForImageTextToText` is `AutoModelForVision2Seq`'s direct successor with the same interface
  and Qwen3.5-0.8B (`Qwen3_5ForCausalLM`) never reaches any of those vision-to-sequence call sites
  anyway — they only block the import. Built as a **new tag**, `nga-verl-qwen35:20261029-shim`
  (`FROM nga-verl-qwen35:20261029`), so the previously-verified baseline stays untouched.
- Mechanism: `sitecustomize.py` in the image's site-packages (runs on every Python startup, before any
  application import, independent of `-I`/`-P`). A naive `setattr(transformers,
  "AutoModelForVision2Seq", ...)` was tried first and does **not** survive: partway through `import
  verl.workers.fsdp_workers`, `sys.modules["transformers"]` gets replaced with a newly-constructed
  `_LazyModule` instance (traced via `id()`; the exact trigger inside that import chain was not pinned
  down, but `transformers.utils.import_utils.clear_import_cache()` is the only code with this
  behaviour), which discards a plain instance attribute. The shim instead patches the **class** method
  `_LazyModule.__getattr__` once, so the alias survives the module-object replacement. Guarded: no-op
  if the old name already exists; raises loudly (not a silent wrong alias) if transformers drops
  `AutoModelForImageTextToText` too or stops using `_LazyModule`; idempotent; logs once at `INFO`
  naming what was aliased and why.
- Verified **without touching any NPU chip** (all 8 chips on `npu` were resident-busy with the R0
  baseline run throughout — confirmed via `npu-smi info`): a plain `docker run` mounting the Ascend
  driver read-only plus only the three management devices (`davinci_manager`, `devmm_svm`, `hisi_hdc`,
  no `/dev/davinci0..7`) is enough for `torch_npu`/`transformers`/`verl` to import. Results: `import
  verl`, `verl.workers.fsdp_workers`, `verl.utils.model`, `verl.utils.checkpoint.fsdp_checkpoint_manager`,
  `verl.model_merger.base_model_merger` all PASS; `vllm`/`vllm_ascend` still PASS; `verl.trainer.fsdp_sft_trainer`
  and `verl.trainer.main_ppo` import and their hydra configs (`sft_trainer`, `ppo_trainer`) compose.
  `npu_patch.py` family check, re-confirmed by identity comparison: 5 of 6 families (`qwen2`, `qwen3`,
  `qwen3_moe`, `qwen3_vl`, `qwen3_vl_moe`) fully patched; `qwen2_5_vl` partially patched (`Qwen2_5_VLMLP.forward`
  applied, `Qwen2RMSNorm.forward` skipped with the one expected warning) — unchanged from before, none of
  this touches Qwen3.5.
- **Still no verl training step has run.** Per instruction, stopped here deliberately: all 8 cards are
  committed to the R0 baseline run, which is the deliverable in progress; the training step (SFT/GRPO,
  loss values, peak HBM, seconds/step) is scheduled for once the cards free up.
- Environment note for that later step: inside these containers use `python3 -P`, never `python3 -I` —
  isolated mode discards `PYTHONPATH`, and CANN's `tbe` operator compiler is only reachable through
  `PYTHONPATH`, so `-I` fails dynamic op compilation with `No module named 'tbe'` then `GEInitialize`
  errors. Verified in-image: plain `python3` and `python3 -P` both work, `-I` fails. This supersedes
  earlier guidance to use `-I` inside these containers (the repo-wide `-I` convention for untrusted
  downloaded code on the host is unaffected).
- Deliverables added: `ctx2/Dockerfile`, `ctx2/sitecustomize.py`, `build-shim.sh`, `image-info-shim.txt`,
  `packages-image-shim.txt`, `verify-shim-norpu.log`, `npu-patch-families.log`, all in
  `/mnt/cephfs/xingchao/docker/verl_qwen35_20261029/`; `README.md` there updated with the full mechanism,
  the guard behaviour, and why the naive one-line alias was insufficient.

## Decision 2026-10-29: rebase onto the vllm-ascend 0.30 stack before running experiments

The first scored baseline was stopped mid-run and discarded, deliberately. It was scoring on a
**slow reference fallback** for Qwen3.5's gated-delta-rule (linear attention) layers, which capped
throughput at roughly 1,000 tokens per second per chip and forced a subsample of 10% of
`openjev-synth` and 70% of `typed-decisions`. Running an experiment on a known-defective engineering
base produces a weaker artifact than fixing the base first.

Measured before stopping, on one chip with left padding, so the fallback is confirmed as the limit
and not an input-starvation problem:

| Batch size | Sequence length | Throughput | Peak HBM |
| --- | --- | --- | --- |
| 1 | 500 | 930 tokens/s | 1.5 GiB |
| 8 | 500 | 1,060 tokens/s | 1.9 GiB |
| 32 | 500 | 1,130 tokens/s | 3.3 GiB |
| 128 | 128 | 1,150 tokens/s | 3.7 GiB |

Throughput is flat in batch size, so the chip is compute-bound per token. Raising the batch size
does not help, and `causal_conv1d` and `flash-linear-attention` are CUDA extensions that cannot be
used here.

**The fix already exists on the host.** `quay.io/ascend/vllm-ascend:v0.30.0rc2` is present on `npu`
and carries everything the current stack lacks:

| Component | Current stack | vllm-ascend 0.30.0rc2 |
| --- | --- | --- |
| CANN kernel sets | `ascend910b` only | `ascend910b` **and** `ascend910_93` |
| torch / torch_npu | 2.7.1 / 2.7.1 | 2.10.0 / 2.10.0.post7 |
| transformers | 4.57.6, needs a 5.x overlay plus a shim for Qwen3.5 | 5.14.1, **supports `qwen3_5` natively** |
| vllm / vllm-ascend | 0.11.0 / 0.11.0rc1 | 0.30.0 / 0.30.0rc2 |
| Qwen3.5 in vLLM | absent | `Qwen3_5ForCausalLM` and `Qwen3_5ForConditionalGeneration` registered |
| Fused linear attention | absent, reference fallback | triton FLA kernels present, including chunked delta-h and fused GDN gating |
| verl | 0.8.0.dev0 preinstalled | **absent, must be added** |

Rebasing therefore removes three problems at once: the slow fallback, the transformers 5.x overlay,
and the `AutoModelForVision2Seq` shim. It adds one task, installing verl against torch 2.10.

Host policy fixed on 2026-10-29: **only `npu` (100.100.135.175) may be used.** `npu2` is fully
occupied by other users, about 61 GB of HBM held on all 8 chips.

## Rebase executed on `v0.30.0rc2`: throughput confirmed, verl working, a real SFT step, fla gated out (2026-10-29)

Full detail and all deliverables: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/README.md`.

- **Throughput, one chip, stock image, before touching verl.** The old ~1,100 tok/s/chip ceiling
  was the torch 2.7/CANN 8.3 stack, not the hardware: transformers alone (still on the torch
  reference fallback for gated-delta-rule/causal-conv) reaches ~18,557 tok/s/chip at batch 32 in
  the 0.30 stack — the gain is batch scaling coming back (batch 1 barely moved, 930->1,197), not a
  per-token compute change. vLLM reaches ~34,000-50,000 tok/s/chip; its gated-delta-rule core runs
  as one CANN fused operator, `aclnnChunkGatedDeltaRuleFwd` (44% of device time), not a triton
  kernel — triton kernels do run elsewhere in the same profile (seven of them, ~6% of device time),
  so triton is confirmed usable on this stack, just not for that specific op in this engine.
  Profiler evidence: both engines run on NPU cores; the only `AI_CPU` tasks seen were two 0.4 ms
  `ViewCopy` ops, not a host fallback. See the corrected section above
  ("Measured on the vllm-ascend 0.30 stack...") for the full, superseding numbers and the
  `logs/profile_vllm.log`-vs-trace discrepancy. Conclusion: **use vLLM for the readout harness**;
  this does not change training, which stays on transformers/FSDP.
- **verl added on top, torch 2.10 untouched.** verl's tree (commit `e9405d70b77...`) copied out of
  the official `verl-8.3.rc1-910b` image. The two fixes from the earlier (2026-10-29, same day,
  pre-rebase) derived image were needed again, unchanged: the `npu_patch.py` `hasattr` guard around
  the renamed `Qwen2RMSNorm`, and the `AutoModelForVision2Seq` -> `AutoModelForImageTextToText`
  `_LazyModule` shim (ported, re-hooked at `verl/__init__.py` import time instead of
  `sitecustomize.py` since this is a source tree, not a baked image). Dependencies (hydra, datasets,
  tensordict, wandb, etc., none present in the stock image) installed as `--no-deps` wheels into a
  side directory on `PYTHONPATH`; base image pins (torch, torch_npu, vllm, vllm_ascend, numpy, CANN)
  untouched. Two extra pins were needed beyond upstream's "latest": `pyarrow==23.0.0`/
  `datasets==4.5.0` (default-latest pyarrow needs NumPy >= 2.0, and the base numpy 1.26.4 pin was
  correctly left alone), and `hydra-core==1.3.2`/`omegaconf==2.3.0`/`antlr4-python3-runtime==4.9.3`
  (an ANTLR grammar-version mismatch between hydra-latest and antlr-latest).
- **A real verl SFT step, fallback path, chips 6+7.** A third gap, new and unrelated to the two
  above: verl's default `MultiTurnSFTDataset` fails rendering Qwen3.5's chat template on a lone
  assistant turn (`jinja2.exceptions.TemplateError: No user query found in messages`); fixed with a
  small custom dataset class via verl's own `data.custom_cls` extension point (no verl file edited),
  matching the raw-completion format the R0 scoring harness already uses. Data: 4,096 train / 256
  val records rendered from jev T1 `typed-decisions` through the existing `r0_code.prompt`
  renderer. Run: `torchrun --nproc_per_node=2` FSDP, `attn_implementation=sdpa` (fallback, as
  ordered), 20 steps, detached per section 7 (`docker run -d`, fixed name, no `--rm`, log+heartbeat
  on cephfs, `DONE` marker, relaunch command recorded). Result: losses not identical across steps
  (1.78 -> 0.43 -> ... -> 0.32, noisy-decreasing), val/loss 0.467 at step 20, ~6.9-7.4 s/it steady
  state, peak HBM ~31.4 GiB (chip 6, rank 0) / ~21.8 GiB (chip 7, rank 1) by 3s external `npu-smi`
  sampling — **superseded below**: this was the allocator's reserved pool plus idle-chip baseline,
  not live tensor memory; see "Round 2" for the corrected breakdown. Open point sent back to the
  coordinator: the brief's "generation vs. update time split"
  applies to a PPO/GRPO step (vLLM rollout + FSDP update); this proof is SFT, which has no
  generation phase, so that split does not apply here — flagging rather than assuming which was
  wanted. **Coordinator's judgement on this point: SFT is correct for this project's goal
  (continued training), the split does not apply, drop that part of the brief.**
- **The fused `flash-linear-attention` path: a clean negative, confirmed architectural.** The image
  already ships an Ascend-specific triton port (`flash-linear-attention-npu-a2`, module `fla_npu`,
  same kernel family as vLLM's fused ops), not upstream `fla`. That distinction turned out not to
  matter: transformers 5.14.1's own gates,
  `is_flash_linear_attention_available()`/`is_causal_conv1d_available()`, unconditionally require
  `is_torch_cuda_available()` before even checking for the `fla`/`causal_conv1d` package — confirmed
  `False` on this NPU host regardless of what is installed. Training through transformers/FSDP
  therefore cannot reach the fused path on this stack as released; it is not a missing-package
  problem, and `pip install`-ing upstream `fla` would not change the outcome. Stopped here per the
  brief: no numerical-agreement or backward-pass test (moot, the forward fast path is unreachable),
  no patch to transformers' gate function.
- **Task 6 (recording a built image) deliberately not done.** Whether `flash-linear-attention`
  belongs in the image is now answered (no, the gate blocks it regardless), but the coordinator
  asked to hold off on building/committing the image until this question was settled; it now is,
  and image assembly is the next task, not done in this round.

## Measured on the vllm-ascend 0.30 stack: the old ceiling was the stack, not the chip (2026-10-29)

Evidence, scripts and raw profiler output: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/`
(`throughput.jsonl`, `logs/`, `profiler/*.summary.json`, `code/`, `launch.sh`). Everything below was
measured in the **stock** `quay.io/ascend/vllm-ascend:v0.30.0rc2` image on host `npu`
(100.100.135.175), **one 910B3 chip**, `Qwen3.5-0.8B` in bf16 from
`/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B`, nothing installed on top. Stack as measured
(`packages-base-v030.txt`): torch 2.10.0 / torch_npu 2.10.0.post7, CANN 9.2.0, transformers 5.14.1,
vllm 0.30.0 / vllm-ascend 0.30.0rc2, triton 3.6.0 + `triton_ascend` 3.6.0+dev20260923.

### 1. The earlier "compute-bound" reading was wrong

Prefill throughput per chip, transformers path (`logs/bench_hf.log`, `logs/bench_hf_oldprotocol.log`,
`throughput.jsonl`), against the previous section's table for the same model on the old stack:

| Batch × length | Old stack | New stack | New stack, old protocol re-run | Speedup |
| --- | --- | --- | --- | --- |
| 1 × 500 | 930 tok/s | 1,197 tok/s | 1,259 tok/s | 1.3× |
| 8 × 500 | 1,060 tok/s | 9,535 tok/s | 10,016 tok/s | 9.0× |
| 32 × 500 | 1,130 tok/s | 18,557 tok/s | 19,362 tok/s | 16.4× |
| 128 × 128 | 1,150 tok/s | 16,938 tok/s | 18,814 tok/s | 14.7× |

The third column is the *old* benchmark script re-run unchanged on the new stack
(`code/bench_hf_oldprotocol.py`: `attention_mask`, `use_cache=False`, `logits_to_keep=3`, peak-memory
counter reset per cell), so the 16× is the stack and not the measurement. Peak HBM from that run is
1.5 / 1.8 / 3.0 / 3.5 GiB, i.e. unchanged from the old stack; the peaks in `throughput.jsonl` are
higher only because `code/bench_hf.py` never resets the peak counter between cells.

**The earlier conclusion that the chip was compute-bound per token was a misdiagnosis, and so was the
attribution to the "slow reference fallback".** transformers still reports `The fast path is not
available because one of the required library is not installed. Falling back to torch
implementation` on the new stack, naming the same two missing packages (`flash-linear-attention`,
`causal-conv1d`) as before (first line of `logs/bench_hf.log` and of `logs/module_time.log`), and the
attention implementation is still `sdpa` — the same reference gated-delta-rule path is running, and
it is now 16× faster at batch 32. What was flat was the old CANN 8.3 / torch_npu 2.7.1 stack's
behaviour under batching, not the hardware: single-row latency barely moved (1.3×), while batch
scaling came back from nothing to roughly linear up to batch 32.

Diagnostic lesson for next time: on Ascend, **throughput that is flat in batch size does not
establish a hardware or algorithmic limit until the measurement has been repeated on a newer CANN
and torch_npu.** Flatness is equally consistent with a host- or runtime-side serialization bug, and
that is what it was here. Re-run the same script on the newest available image before concluding
anything about the chip.

### 2. Where the operations run: both engines are fully on the NPU

`torch_npu.profiler` Level1, one batch-8 × length-500 input, core-type breakdown of every executed
kernel. Source files: `profiler/hf_B8_L500.summary.json` (run
`profiler/hf_B8_L500/k8s-node1_1_20261029093219854_ascend_pt`) and
`profiler/vllm_B8_L500.summary.json` (run
`profiler/vllm_B8_L500/rank0_124_20261029093704194_ascend_pt`), both produced by
`code/analyze_prof.py` from the profiler's own `kernel_details.csv`.

| Accelerator core | transformers: kernels / device time | vLLM: kernels / device time |
| --- | --- | --- |
| AI_VECTOR_CORE | 11,591 / 208,830 µs (73.93%) | 1,384 / 23,163 µs (26.53%) |
| MIX_AIV | 1,341 / 41,540 µs (14.71%) | 36 / 5,045 µs (5.78%) |
| AI_CORE | 979 / 30,901 µs (10.94%) | 230 / 19,278 µs (22.08%) |
| MIX_AIC | 6 / 830 µs (0.29%) | 48 / 39,826 µs (45.61%) |
| **AI_CPU** | **2 / 378 µs (0.13%)** | **0 / 0 µs (0%)** |

Quotable: on the transformers path the device's AI CPU accounts for **0.13%** of device time, in
exactly **two** task instances, both of the same copy operation
(`ViewCopy` / `aclnnInplaceCopy_ViewCopyAiCpu_ViewCopy`); on the vLLM path there are **no** AI CPU
tasks at all. No kernel on either path runs anywhere other than the NPU's AI core, AI vector core or
(for the two copies) its AI CPU; nothing falls back to the host. The remaining 1,280 `ViewCopy`
kernels on the transformers path (23,231 µs, 8.2% of its device time) are device-side copies on the
AI vector core. This is the evidence for the requirement that all model operations sit on the NPU
chips, and it holds for both engines.

### 3. Why the two engines still differ, and what follows

Same input (batch 8 × length 500), same chip, same files as above:

| | transformers | vLLM |
| --- | --- | --- |
| Kernels per model forward | 13,919 | 849 |
| Mean kernel duration | 20.3 µs | 80.6 µs (larger forward) |
| Device-busy time | 282,480 µs (one forward) | 87,312 µs (whole profiled window, two forwards of 849 kernels) |
| Device free / stage, same window | 216,961 / 499,437 µs = 43% idle | 218,294 / 305,606 µs |

Reading the vLLM column: its profiled window contains **two** model forwards of 849 kernels each
(18,879 µs and 68,433 µs of device time; they differ in matmul kernel choice, so they carried
different token counts — shapes were not recorded, so the split of the 4,000 prompt tokens between
them cannot be recovered). Its free/stage figures therefore include the scheduler and sampler gaps
between two engine steps and are **not** comparable with the single-forward transformers figure; the
transformers 43% idle is a within-one-forward number.

The training path decomposes the gated delta rule into **13,919 kernels averaging 20 µs** and leaves
the device idle **43%** of the profiled forward. Its device time is spent on `Slice` (3,709 kernels,
21.0%), `Mul` (19.3%), `ReduceSum` (13.2%), `ViewCopy` (8.2%) and `Tril` (6.5%), with under 10% in
matmuls (`MatMulV3` 6.2% + `BatchMatMulV2` 3.4%) — the signature of an unfused reference
implementation, not of a saturated chip. Per-module timing confirms where it sits
(`logs/module_time.log`, `code/module_time.py`, synchronised hooks, batch 8 × length 500): of a
418 ms forward, the 18 **linear-attention layers take 367 ms (87.8%)**, the 24 MLPs 14 ms (3.3%) and
the 6 full-attention layers 12 ms (2.8%).

The inference path needs 849 kernels for the same work. Its device time is dominated by one CANN
fused operator, `aclnnChunkGatedDeltaRuleFwd` (36 launches, 38,491 µs, 44.1%), plus `CausalConv1d`
(5.8%) and `FusedInferAttentionScore` (1.5%). **Triton-compiled kernels do execute on this
hardware**: 230 launches across seven of them appear by name in the profile —
`l2norm_fwd_kernel2`, `_layer_norm_fwd_1pass_kernel_npu`, `split_qkv_rmsnorm_mrope_kernel`,
`fused_gdn_gating_kernel`, `_gather_ssm_states_kernel`, `_scatter_ssm_states_kernel`,
`_compute_slot_mapping_kernel` — together 5,532 µs, 6.3% of device time. Note for anyone reading the
engine log rather than the profile: `logs/profile_vllm.log` line 69 announces `Using Triton/FLA GDN
prefill kernel (requested=auto, head_k_dim=128)`, but the kernel that actually ran for the GDN core
is the `aclnn` fused operator above. The profile, not the log line, is the source of truth for what
executed.

Two consequences:

- Triton on Ascend is a usable route for a fused kernel here, demonstrated by measured kernels rather
  than by documentation.
- The inference engine's working kernels are **forward-only**. They say nothing about the backward
  pass that training needs, so none of this transfers to the training path without new work.

For completeness, the vLLM prefill/decode rates on the same chip (`throughput.jsonl`,
`logs/bench_vllm.log`, `code/bench_vllm.py`): prefill 5,140 / 16,929 / 33,997 / 34,943 / 50,553
tok/s at batch 1, 8, 32, 128 (×128), 256; decode 96 / 2,241 / 5,176 generated tok/s at batch 1, 32,
128. One engine-side caveat worth knowing before choosing vLLM for decode-heavy work
(`logs/profile_vllm.log` line 52): `NPU Triton causal_conv1d_update is unavailable ... falling back
to the PyTorch implementation, which syncs per request and therefore stalls ACL graph capture at
decode-FULL`.

### Decisions recorded with these numbers

- **The readout harness stays on the transformers path.** vLLM prefill is about 1.8× the transformers
  rate at batch 32 and more at larger batches, but the frozen R0 input is about 59 million prompt
  tokens, which at the measured 18.6 k tok/s per chip is on the order of one chip-hour of prefill —
  comfortably inside a detached multi-chip run. A second scorer implementation would buy speed we do
  not need while putting a correctness risk on the numbers the whole baseline rests on. Revisit only
  if the input scale grows by an order of magnitude.
- **Training gets the fused-kernel question asked once, with a bound.** The reasoning is finding 3:
  triton kernels run on this hardware, but the inference engine's are forward-only, so a fused
  gated-delta-rule kernel usable for training is new work of unknown size. Ask it once, inside a
  fixed time box, and **record a negative result as a result** — the transformers path is already
  fast enough for the readout harness, so a failed attempt closes the question instead of inviting a
  retry.

## Round 2 (2026-10-29, same day): data loading measured, peak memory explained, a direct `fla_npu` test

Full detail and all deliverables: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/README.md`,
section "Round 2". Chips 6,7 only; containers removed after each run.

- **Data loading: measured, not a bottleneck, nothing changed.** Instrumented verl's SFT trainer
  (gated on an env var, default off) to time the dataloader fetch separately from the compute call.
  Config at measurement: `num_workers=8`, `pin_memory=False` (both were hardcoded in verl; now
  config-overridable, defaulting to the same values). Result: after a one-time ~0.75-1.0s worker
  startup cost on step 1, the dataloader is idle **under 0.5% of every subsequent step**. No stall
  to fix, so nothing was tuned — per the brief's own instruction to report "no problem here" rather
  than run a tuning exercise with no baseline.
- **Peak memory: the 31 GiB was mostly allocator reservation, not live tensors, and nothing is
  unsharded.** Re-measured with `torch.npu.max_memory_allocated/reserved` (reset after a 2-step
  warmup) instead of host-side `npu-smi`. Qwen3.5-0.8B is 752.4M params; fp32
  params+grad+Adam(m,v) unsharded = 11.21 GiB, ideally 5.61 GiB/rank once FSDP-sharded over 2
  ranks — that is the floor. Measured **allocated**: ~9.1 GiB/rank steady state (gradient
  checkpointing on, the default, confirmed active). Measured **reserved** (the caching allocator's
  pool): up to ~27.6 GiB — + the ~3.4 GiB idle-chip baseline ≈ 31 GiB, matching the earlier
  `npu-smi` figure almost exactly. So the 31 GiB tracked the allocator's reserved pool, not live
  tensors; actual allocated memory is only ~3.5 GiB above the sharded floor (a plausible activation
  footprint), not a sharding bug. **Checked checkpointing is doing real work rather than assuming**:
  disabling it raised allocated peak to ~21-23 GiB (2.3-2.5x) and reserved to ~33.9 GiB, and made
  each step faster (recompute's speed-for-memory trade, as expected). **Training throughput**:
  ~730-880 tokens/s/rank with checkpointing on (the run item 4's losses came from), ~1,065-1,345
  tokens/s/rank with it off — 13-25x slower than the 18,557 tok/s/chip batch-32 **inference**
  prefill figure above, expected for forward+backward plus a small micro-batch (4, vs 32 for the
  inference number). HBM headroom is large (9.1 of 64 GiB), so raising `micro_batch_size_per_gpu`
  is the next lever for training throughput, not attempted this round.
- **A direct `fla_npu` kernel test: clean, confirmed negative — and a silent-failure hazard, not
  just an absence of capability.** Called `torch_npu.npu_chunk_gated_delta_rule` directly (outside
  transformers, the exact op the profiler saw as `aclnnChunkGatedDeltaRuleFwd`): forward runs and
  matches its own documented inference-only contract (`L_i <= 8` per call, a decode-shaped
  constraint). Its `grad_fn` is literally PyTorch's `WarnNotImplemented` placeholder;
  `.backward()` does not raise, but `q.grad`/`k.grad`/`v.grad` stay `None`. **This is silent, not
  just safe**: nothing raises, every other layer (full attention, MLP, embeddings) still gets real
  gradients, so the loss keeps moving and a training run looks completely normal end to end while
  the gated-delta-rule parameters receive zero gradient forever. Loss behaviour is not a way to
  catch this; only checking per-parameter gradients directly catches it, which is what this test
  did. Searched the rest of `fla_npu`: it ships the individual
  CANN kernel *sources* for both forward and backward pieces of this exact op (on disk, not
  Python-callable), but no module wires them into an autograd-capable function the way it does for
  `causal_conv1d`/`l2norm`/`fast_gelu`, or for KDA (a different algorithm, autograd-wired via
  triton). **`fla_npu` has no backward-capable, callable gated-delta-rule kernel for training as
  shipped.** Stopped here per the brief; no numerical or speed comparison was possible or
  attempted, since there is no backward path to compare. Transformers/FSDP training on this stack
  stays on the reference fallback for two independent, now-confirmed reasons: the CUDA-gated fast
  path (round 1) and no backward kernel for this op on this NPU stack at all (round 2).
- **Task 6 still blocked**, per the coordinator, until this round is reviewed.

## Round 3 (2026-10-29, same day): the throughput-optimal step configuration, a sweep bug fixed first

Full detail: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/README.md`, "Round 3".

- **Three defects in the sweep harness, fixed before trusting any number**: (1) `run_sft.sh` only
  wrote its `DONE`/`FAILED` marker when `torchrun` exited on its own, so externally killing a cell
  skipped the marker entirely — fixed with a `TERM` trap, and the driver no longer kills cells
  externally at all (each is bounded by `trainer.total_training_steps` instead, so natural
  completion always runs). (2) `local a=$1 b=$2 c="...${a}..."` fails under `set -u` because bash
  expands every right-hand side before any assignment in a multi-variable `local` line — split
  into one `local` per variable. (3) **The actual cause of two "no marker found" timeouts**: the
  sweep script polled `runs/sweep/<cell>/DONE`, but the launcher it calls writes to the flat
  `runs/<cell>/DONE` — a path mismatch, not a filesystem timing issue as first suspected. Proved
  the fix on one fully-populated cell before running the rest, per instruction.
- **Hazard correction, carried over from round 2**: the `WarnNotImplemented` gated-delta-rule
  gradient is a **silent** failure, not merely a safe one — every other layer keeps training, so
  the aggregate loss has no reason to plateau and nothing looks wrong. Only a direct per-parameter
  gradient check catches it. The earlier "loss would never move" phrasing was wrong and is
  corrected in both this file and the deliverable README.
- **The sweep, chips 6/7, bounded to 10 steps/cell** (stable by step 3 in earlier runs; no
  gradient accumulation, so one micro-batch = one step): gradient checkpointing x
  `micro_batch_size_per_gpu` in {4,8,16,24,32,48...} until OOM. Device HBM is 60.96 GiB usable, not
  64. Checkpointing on peaked at **3,770.9 tokens/s/chip at micro_bs=24** (OOM at 48); checkpointing
  off peaked at 1,843.5 tok/s/chip at micro_bs=8 (OOM at 16) — checkpointing on wins by 2.0x because
  it buys three more batch-size doublings before its own wall, and this stack rewards batch size
  enough (round 1: 1,197 -> 18,557 tok/s/chip from batch 1 to 32) that the larger reachable batch
  wins over the per-step speed checkpointing gives up. **Binding constraint at the optimum: the
  allocator's reserved pool (55.4 of 60.96 GiB, 91%), not live tensors** (allocated is only 23.4
  GiB) — and the reserved figure is not monotonic in batch size across the grid, consistent with
  round 2's fragmentation finding, so the wall should be expected to move a few GiB either way
  between nearby batch sizes rather than sit where a linear estimate puts it. Both OOMs confirmed
  as genuine `torch.OutOfMemoryError` in the logs, not inferred from a timeout.
- **Two guards checked, not assumed**: loss at the chosen configuration strictly decreases
  (1.868->0.361), same range as every other cell; and throughput does **not** scale linearly with
  batch size (it even drops from micro_bs=24 to 32, right where the allocator wall tightens), which
  rules out a trivial "measuring the batch, not the step" artifact.
- **Watch path given to the coordinator**: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/runs/`;
  each sweep cell carries its own `WATCH.json` (`tier: fast`, `expected_total_steps: 10`).
- **Item 2 (8-chip scaling) still waiting** on chips 0-5 releasing from the R0 baseline. **Item 3
  (image build) is next**, baking in `micro_batch_size_per_gpu=24`, gradient checkpointing on, and
  the three required fixes (`npu_patch.py` guard, `AutoModelForVision2Seq` shim, the custom
  raw-completion dataset class).

## Round 3 addendum: both follow-up diagnoses resolved, image built (2026-10-29, same day)

Full detail: `/mnt/cephfs/xingchao/docker/verl_v030_20261029/image/README.md` and the "Round 3
addendum" in that directory's own top-level `README.md`.

- **`micro_bs=48`'s failure is a genuine `torch.OutOfMemoryError`**, on the first backward pass —
  found in the raw log above the generic `ERR99999` torchrun-exit wrapper the CSV's note column
  had truncated to. Not a shape or sequence-length bug; no hidden headroom above `micro_bs=24`.
- **`micro_bs=32`'s slower-than-24 throughput is a real, late-onset allocator-pressure event, not
  a uniform per-batch cost**: steps 1-8 run normally, steps 9-10 spike to 3x the per-step time
  exactly when reserved memory ticks up to within 1.1 GiB of the 60.96 GiB device ceiling.
  `micro_bs=24` keeps 5.6 GiB of headroom and never hits this; that margin, not just the measured
  peak, is why it is the right pick.
- **Image built and verified**: `nga-verl-qwen35-v030:20261029`. Carries all three required fixes;
  records both closed questions (CUDA-gated transformers fast path, the CANN op's backward-free,
  silent-failure hazard) in its own README. `import verl` passes with the driver mounted; a real
  training step through the built image's own `/opt/verl` on chips 6,7 reproduces the sweep's
  `micro_bs=24` numbers (losses 1.868->0.361, ~3,770-4,200 tok/s/chip, clean `DONE`).
- **8-chip scaling (item 2) still waiting** on chips 0-5.
