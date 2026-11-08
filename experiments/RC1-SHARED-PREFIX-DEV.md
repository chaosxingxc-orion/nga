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


## 2026-11-08 prospective amendment: configuration-bound DEV requalification

Registered before this fresh attempt's device execution. The independently accepted result review of the previous attempt requires one explicit configuration-bound DEV requalification before any scoped scorer adoption. This amendment instantiates that minimum followup; it does not change the population, numerical criteria, timing order, model, adapter, precision, cache bounds or decision rules above. The prior result remains a distinct completed experiment.

Use Qwen3.5-9B Base with the exact unmerged RC1 seed2 terminal3116 adapter, fixed image4726, DEV physical rows33–96 and all three transforms (192 conditions/path). Run on physical chip4 mapped to logical0, one chip. Keep budget8GiB, allowance2GiB, extra16MiB/row and cap8. One warmup per path precedes AB/BA/AB measured pairs; maximum score delta remains0.001nat and a flip at baseline margin>0.002nat fails. All three shared-prefix raw wall measurements must be lower; resumed timing is invalid. Rightpad remains the fallback. No TEST, global default or cross-model adoption is authorized.

Fresh stage: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/shared-prefix-dev-requal-20261108`.
Retained container: `shared-prefix-dev-rc1-s2-requal-20261108`.
No old output, timing, claim, authorization or container is reused. The only intended differences are the fresh stage/container identities and derived preparation/launch records. The accepted numerical runner is unchanged.

| Fresh artifact | SHA-256 |
| --- | --- |
| config.json | `73bd0d807211f3ab9d0062989e4560c6e3e57e25615e62faa8129f9c337b427a` |
| PREPARED.json | `e3b8bf3c56bfc0c9b221c8a9392bfa537c5d3f4ec4c82016cb7ecc3021e2c0ff` |
| FINALIZED.json | `5c82b682f1b290903efdaa6c2e0f80e7c4dd9d291ad8463ecf53eae09012b89e` |
| DOCKER-COMMAND.txt | `cad68a7ad256a42acbf2035471a7b8181dd6b7ed466b790d3ec2c16c23ab28f3` |
| RELAUNCH.txt | `04e6fc567d570f9d501603ce4ac7d4028de82ba76d0dc4a90aeff0b30f2ab62b` |
| source/runner.py | `4190a3ed7238eac3af4717cc77cc05570a681569ffaebb3a6df68ccad9b702a7` |

At registration these files were read back from175 and their small-file hashes matched preparation. No claim, container, dispatch authorization or terminal existed for this attempt. Exact-package independent review is pending. This prospective registration grants no dispatch authority: the actual accepted review must be bound to a fresh DISPATCH-AUTHORIZATION.json, with exact PREPARED/FINALIZED hashes and this published amendment. Publish the prelaunch purpose/hypothesis/setup in the remote wiki before dispatch. Recheck current predecessor release, generation, pending priority and Docker occupancy through the existing allocator; protect H2 chips2/3 and the other project's0/1/6/7. No chip is reserved by this amendment.

Use the existing retained detached supervisor with `/usr/bin/python3.12 -B -P` on host175. Preserve runner logs, heartbeat, terminal.marker, supervisor terminal and release. Reconcile uncertain execution before any relaunch. Inherited historical runtime suggests approximately6.14hours on one chip excluding load/lifecycle; this is a planning estimate, not a new measurement. Independent actual-result review is required before any adoption decision.
