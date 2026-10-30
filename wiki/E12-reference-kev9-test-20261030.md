# E12 — Native Kev-9B official test reproduction

Status: preregistered 2026-10-30 before launch. Host 175; physical chip 1.

## Purpose and hypothesis

Complete the released Kev size ladder below 10B on decision-v7 and transfer-v4 official
test partitions. Defect registry rows 12 and 16 require measurement validity and comparable
evidence. E11's four development records established execution and approximately 31.11 GiB
reserved memory; they did not establish full-suite throughput or numerical equivalence.

Perfect accuracy could come from test memorization. This is a fixed released-checkpoint
reproduction, not proof of generalization or NGA training benefit. Keep native pointer head,
encoder, candidate order and checkpoint temperature; no test-based tuning or selection.
Verifier counterparts include complete valid artifacts and corrupted/foreign/incomplete
artifacts. No aggregate accuracy is called consistency or an invariance gate.

## Frozen setup

- Native released Kev-9B, Qwen3.5-9B-Base revision
  `68c46c4b3498877f3ef123c856ecfde50c39f404`, serving temperature 2.193649959389252
  as observed in E11; runtime metadata must agree with local base revision.
- Existing immutable Ascend image, float32/eager/reference GDN, HF32 disabled, merged LoRA.
  All model/base files, tokenizer/config, native Python source, data and execution scripts
  are frozen by hash before launch. Use the corrected atomic writer and heartbeat join.
- Same full suites as E7/E9: decision-v7 1,176 records/1,440 questions; transfer-v4
  764 records/questions. Clean headline denominators 1,200 and 656; variants separate.
- Two development records per suite precede its full test inference. Check arithmetic,
  valid options and provenance, with repeat deltas diagnostic only. No truncation or
  silent omission of failed/overlong records.
- Original scoring: micro accuracy, one-hot sum-squares Brier, ECE10, NLL and separate
  native diagnostics. Report serving temperature and raw temperature one separately.

## Execution and acceptance

Run `/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev9_test_20261030/`, fixed
retained detached container `nga-reference-kev9-test`. Claim chip 1 only after allocation
and live device checks. Record exact launch, actual container identity/entrypoint, wrapper
and config hashes; guarded recovery requires these identities and current ownership.
CephFS stores per-record receipts, heartbeat/progress, throughput per chip (one chip), reserved
memory, report hashes, structured terminal and wrapper DONE/FAILED. No training is launched.

A separate fixed retained CPU container `nga-reference-kev9-finish` waits for inference
terminal and wrapper success, independently audits required dependency coverage, all question
identities and primary native/raw metrics, then compares the correct Kev-9B release. Frozen
plan and scripts live in the sibling `kev9_test_20261030_finish/` directory. It uses no NPU.
Any failed dependency blocks downstream acceptance. Terminal, wrapper and Docker exit must
agree; output hashes must verify. Calibration discrepancies stay visible, with no invented
cross-device parity threshold. Astra substantive review remains a separate unmet requirement.

## Results

**2026-10-30 launch update:** all 71 inference input/executable hashes were frozen before
launch. Container `6f20f7b48c44495f7789b4351dae13ebdc07e56de66967ff54a0550dc89d9a80`
was launched on chip 1 after allocation and live device checks; its launch receipt records
the actual container ID, command, image, CANN entrypoint and config/wrapper hashes.
The CPU finisher container is
`bc09a4e431f86f0ec62625d7739fdf66f2e0490137361f5d906ec09f9de175ba`.
At 15:15:06 UTC the inference status was loading_model and the finisher was waiting for
the inference terminal. No final test result is claimed.

Before launching this finisher, its wrapper checks were tightened to reject conflicting
DONE/FAILED, malformed DONE and a DONE older than the structured inference terminal;
the check is repeated after audit/comparison. Three CPU tests cover marker failures and
real subprocess success/failure chaining. These are engineering checks, not an Astra verdict.
This record does not certify upstream contamination or all diagnostic metrics.

**Progress, 15:17:51 UTC:** decision-v7 test reached 200/1,176 records, observed throughput
1.9191 questions/s/chip, one chip, reserved memory 31.1094 GiB. The retained container is
still running; no terminal or final metric is claimed by this progress observation.

## Verdict

**2026-10-30 15:37 UTC completion update:** full inference wrote rc 0 at 15:36:38 UTC;
both retained inference and CPU finisher containers exited 0, both wrapper DONE markers
agree. The automated chain completed independent audit and published comparison without
an attached session. Its `FINISH_COMPLETE.json` is `COMPLETED_SCOPED`; both output hashes
were independently checked. Audit verified 71 frozen files including 62 required dependencies,
all 1,940 records / 2,204 questions, and the clean native/raw accuracy, Brier, ECE10 and NLL.

| Suite | Clean n | Accuracy | Serving Brier | Serving ECE10 | Serving NLL | Raw T=1 Brier | Raw T=1 ECE10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| decision-v7 | 1,200 | .8725 | .1776655017981041 | .027077989164865014 | .339478203947507 | .20231737456027105 | .07500830174427692 |
| transfer-v4 | 656 | .8521341463414634 | .19894883566876465 | .036219392757287576 | .3704156037175742 | .21639385494682906 | .08249244753079352 |

Accuracy matches the published values. Serving Brier local-minus-published is
-0.000001322659 / -0.000087501089, and ECE10 is -0.000326640848 / +0.001798387157.
Decision upstream rows are unavailable. Transfer matches all 764 upstream question keys
and metadata; its 656 clean questions have zero argmax disagreements, maximum probability
delta 0.004895507443 and two confidence-bin changes. This is descriptive agreement, not
an invented numerical equivalence gate or contamination audit. Other diagnostics have not
all been independently recomputed. No NGA training benefit or substantive Astra approval
is claimed. Chip 1 was released under the allocation lock after checking terminal, hashes,
wrappers, exited containers and absence of a live mapping.
