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

## 2026-10-31 engineering follow-up, before execution

The E38 driver/preparer/verifier implementation is being checked with CPU fixtures.
The test-only generation `e38_execution_cpu_tests_20261031_v1` will copy the exact
source and run the trace, receipt and launch-contract suites in retained container
`nga-e38-execution-cpu-tests-20261031-v1`, using the same fixed image above and no
NPU devices. Its purpose is to check native random-model hook/wrapper nesting,
independent receipt reconstruction, interruption preservation and fail-closed
resource guards. Model weights are not loaded and no E38 reference-checkpoint
forward is authorized by this CPU test. Terminal, wrapper EXIT, source hashes and
actual container exit will be retained with the fixture output. This is an
engineering check, not a scientific result or numerical admission.

## 2026-10-31 CPU execution evidence

The retained CPU engineering container `nga-e38-execution-cpu-tests-20261031-v1`
ran 63 tests with 61 passing and 2 environment skips, exited from Docker with code
0, and wrote its wrapper terminal. The source manifest was rehashed after exit.
Evidence: container ID `690d0f3aeef00e22386cfbcde29f17785ff79856d52b541f95603da714972ddb`,
terminal SHA-256 `741de8b7e2b81d3fdc541ccd9c579301dc46d80b9ccf8e8dc29d5e467d31e446`,
EXIT SHA-256 `3e7b8d844df114e3780396b5c805c15eb388341c18de44e21c0c7c3963eb5c42`,
and verification `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_execution_cpu_tests_20261031_v1/VERIFICATION.json`.
This is a CPU engineering fixture only; it did not load a reference checkpoint or
run an NPU forward. The native Qwen3.5 integration test was skipped because the
CPU fixture image did not expose that implementation; the existing fixed-image
v3 fixture remains the six-test native API evidence. E38 remains planned and has
not passed parent/independent scientific launch review.


## 2026-10-31 CPU fixture environment correction, before v2

The v1 native-import skips are not evidence of missing functionality in the fixed
image. v1 overrode the image PATH/environment and bypassed its native entrypoint;
the native tests therefore remain unverified in that generation. A new retained
`e38_execution_cpu_tests_20261031_v2` / `nga-e38-execution-cpu-tests-20261031-v2`
will preserve the fixed image environment and entrypoint, set
`TORCH_DEVICE_BACKEND_AUTOLOAD=0`, and rerun the current source closure with no NPU
mapping. It will also check explicit review-required terminal fields when exact
repeat/hook controls fail. The failed/skipped v1 evidence is preserved.

## 2026-10-31 CPU fixture v2 completion

The v1 environment correction was rerun as retained container
`nga-e38-execution-cpu-tests-20261031-v2` with the image's original environment and
entrypoint. It ran 64 tests, all passed, with no skips, and Docker exited 0. This
covers the native tiny Qwen3.5 path, wrapper nesting, cleanup, receipt
reconstruction, resource guards and review-required terminal contract. It remains
an engineering fixture; no reference checkpoint and no NPU forward were run.
Container ID: `23fd0603b5c4d999b952e108fcdf8b07a2408f4446e1bb7154d7f7fdb8479af0`.
Terminal SHA: `bc82943186c8438aafb21ece07dc1ed88d525002ccdbc5f297afbd3e556f5af0`.
EXIT SHA: `f7158d39b24310757864f5af4ef8c2393924298c42139e881712b71c8355e09d`.
Source manifest SHA: `2df9d40b8598a4454979ab9feb9bdc11f172952d04ba11c4c975ea3d9997bee1`.
Full verification is retained in `e38_execution_cpu_tests_20261031_v2/VERIFICATION.json`.
E38 NPU execution remains pending exact-plan parent and independent review.

## 2026-10-31 preparation requests created, no execution approval

After the CPU v2 closure, two E38 preparation requests were created for the
already accepted Open-Jev 2B and 9B E37 source plans. Both requests are detached
CPU preparation only; neither has a parent review, independent review, CPU
container, NPU container or allocation claim. The host check ran under the
allocation lock against physical chip 4 and required Docker and `npu-smi` idle;
the allocation file SHA remained
`01061b98a25df8a8ba9a3e301b13cdd7349db4ec77afb42797f884585a15d1cd` before and
after. Request hashes are 2B
`2820b5d6d8e304b0fa6f59aabb5837d186bdd190c366a7622fa3cdd8a892be38` and 9B
`e939d28029f15a4399deea1ef7fcb8232c513287f12b5de360eada0126791667`. These
requests do not authorize resource claim or an E38 forward.

A short CPU-only environment probe will additionally test the preparer's exact
`Entrypoint=['bash']` plus frozen-image environment, including import of native
Qwen3.5. It uses retained container `nga-e38-cpu-env-probe-20261031-v1` and no
NPU mappings. This resolves whether the CPU preparation path needs an environment
correction; no source plan or approval is changed by this probe.

## 2026-10-31 CPU entrypoint probe

A first CPU environment probe intentionally bypassed the fixed image entrypoint and
failed with `ImportError: libascend_hal.so`; that generation is retained as a failed
engineering probe. A second probe preserved the image entrypoint and completed with
exit 0, importing Torch `2.10.0+cpu`, Transformers `5.14.1`, and native Qwen3.5.
This confirms the E38 CPU preparation spec must retain the image entrypoint and invoke
`bash <wrapper>` as its command. Existing v1 preparation requests were not launched;
new requests must be regenerated after this source change.

Before reissuing preparation requests, the corrected closure will be checked in
`nga-e38-execution-cpu-tests-20261031-v3` / `e38_execution_cpu_tests_20261031_v3`,
using the original image entrypoint and no devices. v3 adds rejection of a
rehashed CPU spec that bypasses the native entrypoint. Earlier v1/v2 test and
preparation generations are preserved.
