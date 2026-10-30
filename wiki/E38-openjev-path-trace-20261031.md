# E38 — Open-Jev native path trace

> Status: planned · Round: diagnostic after E37 · Date: 2026-10-31 · Run dir: not allocated
> Pre-registration: `experiments/OPENJEV-PATH-TRACE-E38-2026-10-31.md`

## 1. Purpose

Localize the first observed intermediate divergence between the native Open-Jev
15-candidate original path and the frozen 8+7 candidate wrapper after E36/E37
showed `candidate_batch_admission=false`. Defects 12/16. This entry is prepared
before any NPU launch and does not authorize JEVal.

## 2. Hypothesis

Passive hooks preserve serialized predictions and identify a reproducible decoder
boundary. The discrimination counterpart requires complete ordered candidate and
event populations, exact shape/dtype, signed-zero-aware fingerprints, and failed
closed on omission or overlap. A first event is descriptive, not causal.

## 3. Setup

Fixed short input: index 4200 only, 15 candidates × width 186. Native BF16
backbone, FP32 head, original mask/token hashes, frozen
temperature and checkpoints from E37. Original full-batch and chunked 8+7 paths
are compared with exact serialized prediction checks. `tools/openjev_path_trace.py`
is the proposed instrumentation helper; a frozen runtime driver and launcher are
still required. Each of 2B and 9B receives 8 forwards (two untraced and two traced
per path), 16 forwards total. No NPU run, model prediction, or test score has yet
been produced. The fixed-image CPU test ran six checks and exited 0, including
the tiny native mixed-attention Qwen3.5 API compatibility test. This is a random
fixture, not either reference checkpoint.

CPU evidence: retained container `nga-e38-path-trace-cpu-test-20261031-v3`, image
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`,
read-only fixture directory
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_cpu_tests_20261031_v3`.
Entrypoint command: `bash -lc 'python3 -P /e38/test_openjev_path_trace.py -v'`,
with `TORCH_DEVICE_BACKEND_AUTOLOAD=0`, no device mapping; execution took under
one minute. Host Python lacks torch, so its skipped tensor tests are not used as
the passing evidence. Earlier shell-launch failures and v2 CPU containers remain
inspectable; v3 is the six-test evidence version.

## 4. Results

No scientific results yet. Any future result must include plan/source/image hashes,
complete event and candidate counts, first observed differing event, exact
prediction controls, and retained Docker/terminal evidence. Timing and memory from
hooked passes will be labelled diagnostic and excluded from throughput claims.

## 5. Verdict

**Pending.** The instrumentation is ready for parent review, but no NPU execution
or admission decision is complete. Even a clean trace cannot amend E36 or permit
Open-Jev JEVal; that requires a separate pre-registered numerical evaluation and
independent acceptance.
