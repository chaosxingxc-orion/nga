# Shared-prefix DEV feasibility — preregistration

Status: preregistered before NPU results, NOT_OF_RECORD and DEV-only. CPU preparation is complete; final integration review is separate and must bind this exact prepared package before dispatch. This diagnostic creates no dependency for current TEST execution or CPU result publication.

Purpose: defect12 measurement-instrument efficiency. The degenerate speed optimum is a constant/lookup scorer or omitted candidates; its discrimination counterpart is complete ordered continuation-score equivalence to the existing FP32 rightpad scorer. The current twelve-role TEST campaign and its results remain unchanged.

Fixed scope: Qwen3.5-9B Base with the exact unmerged RC1 seed2 terminal3116 adapter, existing image4726 and accepted data/tokenizer/model receipts. Decision-v7 DEV physical rows33–96 (64 questions), each under clean, question-only and blank input (192 question-conditions). Reuse the diagnosed first96-row metadata/key/prompt fingerprints and all candidates; no score-dependent selection, new TEST access, truncation or precision change. Dataset label names containing /test/ within frozen DEV archives do not change the registered DEV population.

Candidate implementation: one unpadded question prefill, isolated writable hybrid KV/conv/recurrent caches and metadata, bounded candidate forks, first-token score at prefix endpoint and continuation c[:-1], original candidate ordering and duplicate expansion, sequential summed continuation log probabilities. Accepted rightpad baseline source remains unchanged. Both paths use FP32, matmul/conv HF32 off with readback, exact same loaded model and unmerged adapter.

Numerical criteria: full ordered finite vectors with exact key/gold/candidate/token identity; max absolute candidate-score delta <=0.001 nat; report all argmax flips, both margins, exact top ties and R0, duplicate groups and near-tie census at0.001/0.01/0.1. A flip with reference top gap>0.002 nat fails. Parent/sibling mutation, missing/extra rows, nonfinite scores or incorrect duplicate expansion fails. Near-tie flips remain visible and do not authorize automatic substitution into the frozen campaign.

Timing: one untimed full-workload warmup per path, then three measured paired passes in orders rightpad/shared-prefix, shared-prefix/rightpad, rightpad/shared-prefix. Use synchronized comparable scoring and explicit end-to-end wall timing; separately record encoding, checkpoint commits and available component timing. Report every pair, per-chip question-conditions/s with chip count1, peak/current reserved memory, cache budget/cap and actual forwarded positions as layout-dependent diagnostics. Do not treat forwarded-token rates or theoretical ratios as measured speedup. Numerical success plus lower comparable wall time in all three pairs supports a scoped feasibility benefit. Otherwise report failed/inconclusive/no benefit without expanding scope or tuning on TEST.

Resource plan: one compatible free chip via existing guarded allocator; no partial reservation, preemption or change to27B group gate. CPU preparation, identity reuse, launch rendering and configuration checks precede claim. Actual model loading and free-memory readback occur within the experiment. Proposed post-model budget8GiB, fixed workspace allowance2GiB, per-row allowance16MiB and cap8 must be bound to the final runner and tested CPU estimate; they are not measured safe headroom. Refuse insufficient memory or unsupported cache; do not reduce precision or lengths. Record OOM explicitly and any later batch-cap change as a new diagnostic attempt with unchanged population, retaining all evidence.

Execution: existing detached retained container pattern, fixed unique name, ceph output/log, periodic heartbeat during long chunks, item-level resume and exit marker, exact relaunch command. DEV/model/adapter/source inputs read-only; diagnostic output only writable; no current TEST store writable. Resume can retain numerical work but invalidates a controlled timing series spanning restarts. Failure must produce a terminal marker and explicit rejected numerical status. No full dataset/model rehash.

CPU readiness evidence: actual image model/cache/masking source binding; tiny random hybrid CPU equivalence in image Transformers 5.14.1 max delta 2.384185791015625e-7 using fallback kernels. The runner independently passed the scoped numerical/timing/failure checks, including raw wall-time comparisons and invalidation of stale success on failure. The exact-image device-free CANN/import check and retained-container wrapper failure mock passed. Configuration was changed from physical chip0 to chip4 before dispatch, reusing all dataset/model receipts. None of this establishes 9B/NPU equivalence or Ascend operator performance.

Result decisions: (1) numerical failure -> no adoption; (2) numerical pass without consistent speed benefit -> no efficiency claim; (3) both pass -> scoped9Bseed2DEV feasibility only. Any later adoption requires an explicit protocol/layout decision, never a silent continuation of rightpad output with a different scorer. Current TEST completion and publication proceed independently.

## Exact prepared execution

- Release: engineering-base-rc1, unchanged.
- Host: server175. One physical chip4 mapped to container device0; no reservation before readiness. Group0–3 remains available to the existing 27B gate.
- Image: `sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d`.
- Dataset: `/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/dev.jsonl`.
- Model: `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-9B-Base`.
- Adapter: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/q9b-s2/result/adapter`.
- Prepared stage and durable output parent: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/shared-prefix-dev-launcher-2902800`.
- Retained container: `shared-prefix-dev-rc1-s2-2902800`.

| Artifact | SHA-256 |
| --- | --- |
| config.json | `ce5bb206358a8ad3605c09e7c21f18fde196e4775e1bb000bd7c4e27f2641598` |
| PREPARED.json | `b4fd0d75cefed9c15f073bf14ecba86ac9a5486d4ac520bd9978632cb6975d05` |
| FINALIZED.json | `8ad8f8f97ba76a0fc23ee521101821944a030c9cd18315285e00136ee5fb251b` |
| RUNNER-READY.json | `2a915d0d7daa880182398b259f37b7016c6b76d46ddb5d109142ed22d5c2a70f` |
| DOCKER-COMMAND.txt | `4b138c9c492734793f781a364026c0abceaf9983af88d906dc614be423c8e080` |
| RELAUNCH.txt | `1c8b25970c21f5ee5629b51dd587e7600ef038637e977dd8c9a7dc5b6b98c9eb` |
| source/runner.py | `4190a3ed7238eac3af4717cc77cc05570a681569ffaebb3a6df68ccad9b702a7` |

Prepared receipts and the retained relaunch command remain in the durable stage. The dispatch record will identify this published preregistration and the exact integration review. Source/config changes after registration require a dated amendment before new device execution; changing resource assignment alone does not authorize numerical or population changes.
