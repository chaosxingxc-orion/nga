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


## 2026-11-08 prospective correction: exact hostfix and independent consumer

Status at preparation: NOT_STARTED. This additive correction applies to the minimum configuration-bound DEV requalification above. The amendment published in f156000 describes the historical initial unlaunched stage, not the corrected stage below. It remains part of the record. This correction and the prelaunch wiki entry must be published on origin/main before dispatch. No metrics, population, timing, gates, model, adapter, precision, runner or resource cap change; no TEST is authorized.

The exact review returned `PASS_EXACT_FIX_DISPATCH_CONDITIONAL` on 2026-11-08, accepting CPU preparation and the existing single DEV192 followup conditionally, with no new authority. Its original verdict SHA-256 is `580668c51d7c4cfde2d0a8330db6949be7751c5d89cd93002be4e5104003f8e6` and its full source-pin receipt SHA-256 is `bf1ab8bf1e576ba5c5ac6e262287397f0351f6a191b8427675b3a9ad1fc6335a`. The compact [review receipt](records/RC1-shared-prefix-hostfix-exact-review.json) records those pins and conditions. Inherited asset acceptance was not requalified. The host correction fixes the retained supervisor and allocator helper to `/usr/bin/python3.12 -B -P`; the container retains `python3 -B -P` and CANN `PYTHONPATH`.

Stage: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/shared-prefix-dev-requal-20261108-hostfix`. CPU package: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/shared-prefix-cpu-requal-20261108-hostfix`. The retained container is `shared-prefix-dev-rc1-s2-requal-20261108-hostfix`. No prior generation, output, authorization or claim is reused.

| Stage artifact | SHA-256 |
| --- | --- |
| `DOCKER-COMMAND.txt` | `a22e61f7b40e93fbef9006886cd7fba2e4724fdd4e90db41858ae07b9808ce75` |
| `FINALIZED.json` | `1eea543217d01a1dba9afe4a47a8c20fb1443510a6b3166d9cbe0c46c90a493a` |
| `PREPARED.json` | `71824ef40db46ded974cbeb4a751986f830690aa0fca48ddc927bc22c8d4f7b2` |
| `RELAUNCH.txt` | `7bea7a7314e98aa9f86412dde404af662b44d8d146c52189b371d81451f4da2d` |
| `RUNNER-READY.json` | `2a915d0d7daa880182398b259f37b7016c6b76d46ddb5d109142ed22d5c2a70f` |
| `adapter.py` | `f90ae21242b78c4c774ff5c12b5ff30d9e7b1bd927d42f910fc157c6538a574a` |
| `config.json` | `e88289c80304ce4b65233fb8dacc6fc5c5d6a42814f408d14c26447eb9b717a5` |
| `container-entry.sh` | `26aa7913034556004f4114e249b227b5315bab9ee57f15535d1eb94e163a0b9c` |
| `launcher.py` | `05dd1356b6709e5ccc2af4647dd0e266bb6a964a111e519b3d967d5fa52d5e54` |
| `probe.py` | `970990a82c773af9738c9e0f0a8fc89720271874e9a26ef6a2c27168cbc8a259` |
| `receipts/CPU-ACCOUNT.json` | `7d551f9d391d29f5cd80186dc30d69df8f5f008be99629ea4f7ef8430c5ca046` |
| `receipts/DEV-MANIFEST.json` | `66d02a54cef6a6d5e79f8d06c7774f9642f13940c150820d4bca3106c5a6870e` |
| `receipts/IMAGE-SOURCE-HANDOFF.md` | `e3d23676d17cee0a24d90800bb7d4cedb620f4a44e7043820d934e37b7520823` |
| `receipts/SOURCE-PINS.json` | `902f0d26477a153ecb35a1d9cac5f9e4eb246e1a8714b93a5fed4efb4029cc9f` |
| `receipts/TOKENIZER-IDENTITY-REUSE.json` | `5c1ea3315e4605b87d3e7db5df67912140ed69f72aa6c431b21bfa5ce717895a` |
| `source/compare.py` | `a32f76a83ad65f7ec2e558a153503ddbde348ed10b8a1a71f3d14b84755f3448` |
| `source/container-entry.sh` | `26aa7913034556004f4114e249b227b5315bab9ee57f15535d1eb94e163a0b9c` |
| `source/diagnostic.py` | `cd7a9c87937994b50fbd84508b16f7339a82544e3d3d81a30bb3c7a127ba451b` |
| `source/prompt.py` | `84c99aec2817de3365e650c7c6c846aeddc1ec675b3321cf80be267a7557f0fc` |
| `source/runner.py` | `4190a3ed7238eac3af4717cc77cc05570a681569ffaebb3a6df68ccad9b702a7` |
| `source/scorer_r3.py` | `f1de708a28b47cdb513eb79c7306510df8312f6a92f96a75adcfe59ba0cf6a49` |

| Independent CPU package artifact | SHA-256 |
| --- | --- |
| `BIND-COMMAND.txt` | `95c91aa9ca27d2fd0dcc5db5683ff6202dc733324f606aa0ab8ead1c56d6398b` |
| `CPU-COMMAND.txt` | `a8299800d71e895aee26f8a661157cd9759c5a447723d37c6676b17269f4a0e6` |
| `RELAUNCH.txt` | `65f3f486c18be91347e0821d53c6ec0eb4b831cb42073ec184baf71b4b93e9d3` |
| `bind.py` | `8238e21b63125180ec1e781edd5014484d246cf5e3d7aca347aa4e1f6cec3de1` |
| `config.json` | `3b24a7774c0b53e62b5e93f5b208b3e88252c02f3e980769b8b8baff0301199a` |
| `consumer/consume.py` | `f2862863ee6e8a5c5db1bb653ce9988f823ba397016173b4c0f843bf7702f8e5` |
| `static-scope.json` | `d323c32477e3b4e81236adfceba2065b9eb173df608b0cc9715479e2df314113` |
| `waiter.py` | `dc4a858cdd75628186dad09b6fb7f9f1b47c382bb1d8445da6601b69c94dabcc` |

Review snapshots: [config](records/RC1-shared-prefix-hostfix-config.json), [PREPARED](records/RC1-shared-prefix-hostfix-PREPARED.json), [FINALIZED](records/RC1-shared-prefix-hostfix-FINALIZED.json), [CPU config](records/RC1-shared-prefix-hostfix-cpu-config.json), [CPU static scope](records/RC1-shared-prefix-hostfix-cpu-static-scope.json). These snapshots must be published with this amendment.

Before dispatch, bind this exact review and the published amendment to a fresh DISPATCH-AUTHORIZATION.json using the existing authorized process, including the exact PREPARED and FINALIZED hashes. Recheck physical4 predecessor generation/release, allocator, ready TEST priority and Docker conflicts; protect H2 physical2/3 and other-project0/1/6/7. No reservation is made. Use actual authorized launch records for the container ID and generation. A successful process exit is insufficient: independent analysis requires numerical_pass AND timing_valid AND all_pairs_benefit. A failure or no-benefit is retained; rightpad remains fallback. Adoption requires independent result review and a separate explicit decision. Estimated 6.14 hours on one chip excluding load/lifecycle is historical planning, not a measurement of this run.
