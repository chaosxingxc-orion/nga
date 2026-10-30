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

## 2026-10-31 final CPU fixture and request review

The corrected v3 engineering closure ran 65/65 CPU tests with no skips in retained
container `nga-e38-execution-cpu-tests-20261031-v3`, Docker exit 0. Source manifest
SHA is `8e1e6509cfcb97f9cb6b8a8cfe6f953384cab6757bd5c73d9e00a0bc7384ecd1`;
terminal SHA `1eb0646d1ed3a096284e34e9d9c2d6abbadf184885a65cb0a1a813d5355595e0`,
EXIT SHA `d785f77453bccee61e9f9bc027bca5ea7ae2cf6ff16eb8d3b71128d25385bf97`.

New preparation requests are
`e38_openjev2_prepare_20261031_v2/request.json` (SHA
`389a7443ba675c66fa89d293a36e7693d22e52618f8a213a2af00bbaa966113b`) and
`e38_openjev9_prepare_20261031_v2/request.json` (SHA
`e40a1bb44f28c61788dcc48c054841cf5051dacb65efe41d3f19e4b203844dac`), under the
reference-inference root. The parent session checked both complete request hashes,
all 18 frozen files, no devices, network `none`, original image entrypoint,
`python3 -P`, and correspondence with the v3 source manifest. It approved only
these two detached CPU preparation jobs. This records the actual parent review;
it is not a claim of review by a named Fable model. NPU launch remains prohibited
until the resulting exact plans and closure receive the separate required review.

## 2026-10-31 detached CPU preparation completed

Both approved v2 CPU jobs completed full source/input hashing and native tokenizer
reconstruction, with matching wrapper/terminal reports and actual Docker exit 0.
The parent-checkable host binding was rerun after exit. Physical chip 4 remains
unclaimed and its allocation digest is unchanged; no NPU container was created.

| Checkpoint | Frozen target plan (under reference-inference root) | Plan SHA-256 | Frozen files | Scheduled forwards | Expected trace events |
| --- | --- | --- | ---: | ---: | ---: |
| 2B | `openjev_path_trace_openjev2_20261031_v2/plan.json` | `14b95a2f9c4f8c25aecd46c01077d2f94045d926c43b0535abd6bbd5ee81662f` | 196 | 8 | 696 |
| 9B | `openjev_path_trace_openjev9_20261031_v2/plan.json` | `0f839e1153a968f81c8033ff2463c982648ffc8152e381ef369eda6303c198b5` | 199 | 8 | 928 |

The exact canonical input digest in both plans is
`bb54ecd6f4dafbda582b4a81a5b9c9a68fc3b1a8f62f7b455f51506bb807c0bb`. CPU preparation
terminal SHAs are 2B `371f49022d78d6b5d26edf40f8ee412134d2c82fd77f9fde77035c763eb9db6d`
and 9B `19b1b1297a76ba151397724da0213934e3c452762ee735838d156a034fdc18c0`.
Each preparation directory contains its original report/terminal/EXIT and
`PARENT-CHECKABLE-EVIDENCE-v2.json`. A dated correction in that v2 evidence fixes
an auxiliary v1 `input_sha256` field that accidentally repeated the plan digest;
the frozen plans and CPU reports were never modified. Final plan parent review,
actual independent review and NPU execution are still pending.

### 2026-10-31 — actual Astra v2 BLOCK; implementation repair before any NPU launch

The actual Astra review blocks both frozen v2 plans. No v2 plan, review, or run receipt is amended. New generations must fix: native choice wire normalization and chance-adjusted confidence; logits/temperature/probability consistency; independently frozen trace execution order, dtype, row shape and folded layout; single-read parsed-byte/hash binding with unchanged file-object checks; durable forward attempts and explicit interrupted-generation semantics. Exact prediction repeat/hook comparisons remain exact. CPU regressions include eight verbatim E37 4200 predictions and the actual reported corruption/race cases. Per-test logs must accompany the next CPU package.

A durable attempt intent precedes each possible native forward. An intent without a committed matching receipt makes that generation uncertain and permanently ineligible for resume; it is never silently retried as an eight-attempt run. A report-without-terminal publication gap is explicitly failed as an incomplete generation, with all existing evidence preserved and receipts available only for reviewed forensic reconstruction; it cannot authorize a new NPU forward or a success marker. New runs require new reviewed generations. This repair is engineering admission work, not E36 admission or an experimental result.

### 2026-10-31 — repaired execution candidate, CPU evidence only

Implemented native mass/temperature/softmax/wire/first-argmax/chance-confidence validation; exact repeat controls remain unchanged. The producer and verifier enforce separately frozen call order and event dtype/shape/source layout; actual tiny native Qwen mixed layers pass in FP32 and BF16. Evidence parsing and hashing share no-symlink snapshots with file-object checks. Durable intent/receipt binding rejects uncertain forwards, and report publication gaps explicitly fail a generation without rewriting its report, EXIT or receipts.

The retained fixed-image CPU candidate is `e38_execution_cpu_tests_20261031_v6`, container `8c153303208aee95f00444a1976c5d840d365309e5559a7a4c8d27d0a1564942`: actual start `2026-10-30T23:22:13.69293368Z`, finish `2026-10-30T23:22:44.61616423Z`, Docker exit 0, 85/85 tests, no skips, 85 separate test logs. `SOURCE-MANIFEST.json` SHA-256 `495c861f996064098f1df8d7e8eb743250137338caf843b483b8837d4e115f82` was verified unchanged after execution, with zero `.pyc` files. Terminal SHA-256 `ccfcb7181358d07d597fc940cc7436f00f336371904667b1ecbb6a434bc05353`. The package retains `PARENT-CHECKABLE-EVIDENCE.json`, report, per-test logs, heartbeat, wrapper, source manifest and actual Docker container. This is engineering evidence only.

Correction/disposition: earlier CPU v4 passed 84 tests; v5 passed 85, but its copied source manifest accidentally included generated Python caches and failed full immutability verification. Both remain inspectable and are superseded by the clean v6 package; no source/test `.py` change was required for this correction. The preparer v3 requests derived from v5 were not approved or launched. New v4 requests use v6 sources: Open-Jev2 request SHA `120296134a3779102bee629852ca93a147b9c26c54e40536de8868e8a967eb85`; Open-Jev9 request SHA `e96dfb54ae99529670abdab5ea98dd68d540f12da31b00b72b9755ea441fa46a`. These requests only authorize preparation after exact request review; generated plans still require actual Astra exact-plan re-review before any NPU execution. Frozen v2 remains blocked and unchanged. No E38 NPU forward was launched during repair.

### 2026-10-31 — v4 CPU preparation complete; actual Astra re-review preregistration

Both reviewed v4 CPU requests completed with marker rc 0 and actual retained Docker exit 0. Open-Jev2 target `openjev_path_trace_openjev2_20261031_v4/plan.json` SHA `882b686ba62c75f1bb41c670b18fb4785f439273bbd32b4c5de29ff9a512a8df` freezes 204 files and 696 trace events; Open-Jev9 target `openjev_path_trace_openjev9_20261031_v4/plan.json` SHA `b1afb0e81a5c3c77f6bb5892e8dfdb7da750220d6d44f17dc2a7e52b6d9afce3` freezes 207 files and 928 events. Each target retains a `PARENT-CHECKABLE-EVIDENCE.json` tying preparation request, plan, terminal, report, EXIT and actual CPU container. Both canonical input hashes remain `bb54ecd6f4dafbda582b4a81a5b9c9a68fc3b1a8f62f7b455f51506bb807c0bb`. Allocation SHA remains `01061b98a25df8a8ba9a3e301b13cdd7349db4ec77afb42797f884585a15d1cd`; neither target NPU container exists.

Before any NPU launch, submit the clean v6 CPU suite, its 85 per-test logs and original native prediction fixtures, and these exact v4 request/target plans to a new actual Astra review. New unique paths are `astra_reviews/e38_execution_candidate_20261031_v3` (bundle), `e38_execution_prepare_20261031_v3` (builder), and `e38_execution_astra_20261031_v3` (review runner). The reviewer is the actual `codex exec --model gpt-6-astra --sandbox read-only` process; a role label or another model's opinion is not a substitute. It must examine every previous P1/P2 finding: native numerical semantics and malformed predictions; source-derived trace contracts; atomic evidence parse/hash binding; durable attempt counts and failed-generation publication-gap behavior. It must check tests/fixtures, frozen closure and exact plan identity. It may produce a review verdict and evidence only, no NPU action or approval files. The previous actual v2 BLOCK and all its frozen artifacts remain intact. A new PASS must name the exact reviewed plans and does not itself constitute launch or E36 admission.
