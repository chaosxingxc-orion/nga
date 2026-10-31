# R3 engineering-base milestone — 2026-10-31

## Status

The engineering base validation is accepted. This milestone validates detached execution, frozen-code launch, resource claim/release, heartbeat/progress recording, and a measured post-warmup throughput window. It is not a training-gain result and it did not read the test split.

Authoritative run: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/eff_validation_k1_08b_20261031_v12/`

- Model: Qwen3.5-0.8B-Base
- Arm: K1 LoRA, seed 2
- Kernel: reference fallback
- NPU: chip 1 on host 175, one chip
- Steps: 45 total; first 5 warmup, 40 measured
- Measured wall time: 134.825 s
- Mean throughput: 865.703 tokens/s/chip; 3.3306 questions/s/chip
- Peak reserved memory: 6.7 GiB
- Terminal marker: `DONE`, rc=0
- Resource release: `RELEASED.json`, guarded release after container exit
- Scientific acceptance: false
- Test read: false

The independent CPU acceptance record is `EFFICIENCY_ACCEPTED.json`. Its parser uses the recorded progress values and reports the full 40-step post-warmup window. The earlier verifier rejected shorter windows and had a parsing mismatch for the space-separated `reserved_gib 6.7` field; this was corrected outside the frozen run and is recorded as a tool defect for the next generation.

## Launch defects found and disposition

1. v2: Docker environment variables were passed as one malformed argument. The adapter abort path returned chip 1 safely.
2. v3: The management node had no NPU device or local image. The target host `npu` already held the pinned image digest; execution was moved there.
3. v4/v5: Target-host Python is 3.12 while `python3` is a 3.10 wrapper without `-P`. The launcher and adapter invocation were pinned to `python3.12`.
4. v6: The frozen training file lacked executable permission. This was caught by the retained container and fixed in the next closure.
5. v8: Direct execution of a Python file without a shebang produced `Exec format error`. The command now invokes `python3 -P /workspace/train_r3.py` explicitly.
6. v9/v11: The initial 10/20-step verifier windows were shorter than 60 seconds. The run was extended to 45 total steps; the final 40-step window is above the registered wall-time threshold.
7. v12: The verifier expected `reserved_gib=` while the trainer records `reserved_gib 6.7`. The run itself is valid; the parser mismatch is a next-generation tool fix, not a scientific failure.

Every failed or superseded generation retained its launch evidence and was either aborted before container creation or released after container exit. No manual edit was made to `CHIP-ALLOCATION.json`.

## What this proves

The frozen Qwen3.5 K1 path can run detached on the target NPU host, write resumable run evidence, record per-chip throughput and reserved memory, and release the claimed chip safely. It does not prove K1 improves any test metric, does not select a seed, and does not establish production readiness.

## Next milestone plan

1. Freeze the corrected verifier/parser and launcher as a new code snapshot; add a regression test for both `reserved_gib=6.7` and `reserved_gib 6.7` forms.
2. Prepare the formal K1 seed-2 and seed-3 plans from the accepted engineering closure. Keep dev scoring and baseline locking on the CPU lane while NPU jobs remain queued.
3. Launch formal training only after each plan has a fresh canonical hash, operator authorization, detached retained container, and guarded release path.
4. Score dev asynchronously with the registered decision-level protocol. Select using the preregistered dev gate; do not inspect test during selection.
5. Produce the next cumulative report, then run the one-time locked test evaluation and update the remote wiki with conclusions only.

## Scope decisions preserved

D1 remains the frozen reference-metric matrix with separate formulas, temperatures, targets and denominators. D2 compute budgeting remains suspended. D3/D4 real business integration remains out of scope; business-gap datasets and RL are later milestones after direct-readout and SFT/LoRA baselines.
