# E40 — Open-Jev full-shape GDN lifetime candidate

> Status: planned, draft protocol; no NPU launch · Round: reference engineering · Date: 2026-10-31
> Draft: [E40 protocol](../experiments/OPENJEV-LIFETIME-E40-DRAFT-2026-10-31.md)

## 1. Purpose

Prepare a native full-candidate memory path for remaining Open-Jev JEVal reference inference; defect 12/16. E38 success does not establish this admission. Current E36 `candidate_batch_admission=false` remains unchanged.

## 2. Hypothesis

Deleting last-use references may lower allocated peak while preserving full outputs. The minimum-memory degenerate solution skips work; full candidate/token/output identity and exact paired repeats prevent it. A numerical mismatch or no memory improvement is reported as a candidate failure or negative result without relaxing the protocol.

## 3. Setup

Candidate generation is in `tools/openjev_lifetime_candidate.py`, tests in `tools/test_openjev_lifetime_candidate.py`. Only the fixed native source SHA `0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded` is accepted. L1, L2 and their combination insert only AST Delete nodes. Inference/no-cache/C64/nonempty native 2B/9B shape conditions are enforced externally. Proposed later NPU input identities are 4200, 9027, 8409; exact model/data/code/launch and headroom registration remains to be frozen. No actual run directory or NPU launch exists.

## 4. Results

Seven pure CPU tests pass: Delete-only AST preservation/compilation, insertion locations/remaining reads, loop-view cleanup and no double deletion, native source mutation/variant rejection, supported-mode and shape guards, gradient/empty/device rejection, unrelated callable rejection. The tests read the fixed source as data and execute no tensor operation. No numerical, memory or throughput result exists.

## 5. Verdict

Implementation candidate ready for review and fixed-image tensor verification. Not numerical admission, no JEVal result, no training gain and no resource-release permission. Next steps: independent code review, fixed-image tests, complete driver/receipt/verifier integration, freeze exact plan and obtain actual Astra review before any NPU work.

## 2026-10-31 CPU tensor preflight preregistration

Before launch, freeze `e40_lifetime_cpu_20261031_v1/PLAN.json` under the reference
inference CephFS tree. This CPU-only fixed-image check imports the installed native
function and authenticates its full module source SHA. It tests original/L1/L2/L1L2,
two repeats each, across fp32/bf16, H=16/32, L=1/63/64/65, qk normalization off/on:
32 cells and 256 forwards. B=1, D=128, seed=20261031+cell index. Require exact
output bytes (including signed zero), finite outputs, same dtype/shape, state None,
and unchanged input bytes. No weights, benchmark labels, NPU device or allocation
access. Container has two CPU cores, 4 GiB RAM, network none; fixed image is
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
Detached retained container, per-cell durable records, heartbeat progress, report,
COMPLETE, wrapper EXIT and actual Docker exit are required. This test cannot establish
NPU output equivalence, memory improvement, throughput or full JEVal admission.

CPU v1 exited 1 before any tensor cell: PyTorch attempted automatic torch_npu
extension loading without a driver mount. Zero items were produced. Preserve v1;
v2 adds `TORCH_DEVICE_BACKEND_AUTOLOAD=0` to the CPU-only environment, without
changing source, tensor population or assertions. No NPU driver is mounted to
work around a CPU import issue. This amendment precedes the new v2 launch.

CPU v2 also exited 1 before tensor work: importing the entire transformers model
module still probes an NPU integration requiring `libascend_hal.so`. v3 instead
locates the installed source, authenticates its full fixed SHA, and compiles only
the unchanged `l2norm` and `torch_chunk_gated_delta_rule` AST nodes with torch/F
globals. Original filename and line locations are retained for `inspect` identity
comparison in `build_candidate`. This is a CPU test of the installed source
functions, not a successful full transformers-module import. Population and exact
acceptance remain unchanged. Both failed generations and their zero-item evidence
remain retained. This amendment precedes v3 launch.

## 2026-10-31 CPU v3 result

The retained CPU-only container `nga-e40-lifetime-cpu-20261031-v3`, ID
`a410d7e428357bfe8d3376c6293e528b507615bf8644b0b23b36a97002b051dc`,
actually exited 0 (StartedAt `2026-10-31T03:24:14.16796443Z`, FinishedAt
`2026-10-31T03:24:25.54675867Z`). No accelerator device was exposed and network
was none. All 32 cells / 256 forwards completed: original and three candidates,
including both repetitions, had identical output-byte hashes in every cell.
Input tensors were unchanged, outputs finite with expected shape/dtype and None
final state. Plan SHA is
`792fa12860cb07171bc93268732b1220dc201944fdc6fcb1e2778f17adc02406`;
report SHA is `c9ea4eb1229422785d6c29755a61bc1f1e2e9375e2dda1396c542e7022114396`.
The output directory retains all 32 item records, plan/source hashes, wrapper,
progress lines, COMPLETE, EXIT, actual Docker observation and `CHECK.json`.
The host check independently verified all identities, per-cell population and
hash equality; it did not independently rerun tensor arithmetic. Full output
tensors were not saved. This establishes bounded CPU tensor behavior only,
not NPU equivalence, memory savings, throughput or JEVal admission. No allocation
record was changed; v1/v2 failures remain visible.

Parent verification rehashed all 32 cell files, checked their exact registered
shape/dtype/normalization identities and 256 output digests, and queried the
retained container's actual exited/0 state again. Machine-readable bindings are
in `experiments/E40-LIFETIME-CPU-RESULT-2026-10-31.json`. This was a first complete
run; interruption/resume and cached-item authenticity were not tested. The CPU
driver's resume branch checks only plan/index and must not be described as a
validated unattended recovery path or reused as the NPU experiment controller.
