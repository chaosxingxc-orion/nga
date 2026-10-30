# E22 — Kev devtools-v1 dual-population reference inference

Preregistered 2026-10-30 before launch. Normative protocol: [devtools dual population](../experiments/KEV-DEVTOOLS-DUAL-PROTOCOL-2026-10-30.md).

## Purpose and setup

Defects 12/16: reproduce fixed Kev 0.8B/4B/9B references without losing two distinct records sharing an upstream ID. The degenerate label lookup optimum prevents claims of unseen generalization. Valid collision preservation and rejected wrong population/corrupt identity are verifier counterparts. All 900 records/1,073 questions are inferred; original release drop policy yields a separate 1,071-question panel. No training, threshold fitting, truncation or post-result exclusion.

Preserve native pointer head, original released base revisions, fp32/eager/merged LoRA and serving temperatures from E7/E9/E12. Strict suite context and two repeated development records precede formal inference. Full and release accuracy/Brier/ECE10/NLL plus raw T=1 are reported separately. An independent stdlib verifier checks ordered identity, exact coverage, source hashes and metric arithmetic.

## Execution

175 only, existing immutable image. Each `reference_inference/kev{08,4,9}_devtools_20261030/` uses fixed retained `nga-reference-kev{08,4,9}-devtools`. CPU controller at `reference_inference/kev_devtools_queue_20261030/` waits for corresponding E20 jobs on chips 0/4/5, reruns their independent audit, checks wrapper and exited-container identity, then transfers ownership under flock and checks live devices. It never stops E20. The model wrapper runs full inference, then independent dual-population verifier; logs, heartbeat, terminal and exact guarded relaunch persist. In this initial implementation any dependency exception stops the whole controller and writes a failed terminal; already launched inference continues. Unlaunched independent entries need reviewed continuation, not a fabricated success.

## Results

2026-10-30 16:27 UTC: ten CPU tests passed, covering collision preservation, both exclusions,
full original counts, missing collision record, rehashed wrong record position, rehashed wrong
release metric and rehashed wrong excluded-index list. Three model configurations froze
68/73/72 files respectively. The dedicated driver and independent verifier do not relax the
shared Kev driver or alter the original dataset.

Retained CPU controller `nga-reference-kev-devtools-queue`, ID
`1de4a8a9a57f637860e6789bbd2d41d72b2d3ac7ba039c2ceb22afd85ead0ef2`, was launched.
It independently re-audited completed E20 0.8B, verified wrapper/Docker exit and prior launch
identity, transferred chip 0 under lock, and launched `nga-reference-kev08-devtools`, ID
`4b8d7c22e9f68fdcf2e30021aa94b9686b2410e73eaaab0d831f749b8f091d6c` at 16:26:58 UTC.
At 16:27:28 UTC it reached 17/900 records, 2.8621 questions/s/chip, one chip, reserved
3.5059 GiB. `TRANSFER_EVIDENCE.json` binds prior audit hash; `LAUNCH_RECEIPT.json` binds
actual image/container/command/entrypoint/config/wrapper. The queue still waits for 4B/9B
E20 completion. No full devtools score or final audit is claimed.

Controller caveat: this initial queue deliberately refuses restarting over existing state;
a controller crash needs reviewed reconciliation of already-created/started handles and
allocation, not blind re-execution. Its launch command creates containers through Docker API,
which is a privileged operation; it inspects live mappings and owns only explicitly listed
E20-to-E22 transfers. Any exception stops this controller and records nonzero terminal; it
does not terminate inference. This is not a general production scheduler or tested crash
recovery of the controller.

## Verdict

Pending. No Astra approval or NGA training benefit.

Same-day post-launch correction: repository driver checks an existing terminal before starting
a heartbeat or entering its exception handler, so an accidental direct rerun cannot overwrite
a successful terminal with a failure. The frozen initial execution keeps its original code;
its guarded `RESUME_EXACT.sh` refuses successful runs. Do not directly invoke the frozen
driver over any existing terminal. No successful-run restart was performed.

**2026-10-30 16:36 UTC update:** the CPU queue completed all three launches with
`QUEUE_COMPLETE.json rc=0` at 16:32:35 UTC. This certifies launches only. The 0.8B
inference completed at 16:35:42, wrapper DONE at 16:35:51; retained container exited/0.
Independent audit verified 68 frozen files, 59 required dependencies, all 900 records and
1,073 questions with ordered collision identities retained.

| Population | n | Accuracy | Serving Brier | Serving ECE10 | Serving NLL | Raw Brier | Raw ECE10 | Raw NLL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 1073 | 0.636533084809 | 0.442394041397 | 0.084400356512 | 0.778104694919 | 0.455260263178 | 0.101732827602 | 0.799732281089 |
| release | 1071 | 0.636788048553 | 0.442355104015 | 0.084701033785 | 0.778333869209 | 0.455251658744 | 0.101601232564 | 0.800022254312 |

Release accuracy matches upstream .636788048553; no full-population equivalence is inferred.
4B and 9B remain running at 437/900 and 223/900 records at 16:36 UTC. Final results for
those sizes remain pending. No substantive Astra approval or training benefit is claimed.

2026-10-30 16:42 UTC: 4B completed, wrapper rc 0 at 16:41:50 and retained
container exited/0. Independent audit VERIFIED_SCOPED checks 73 frozen files,
64 required dependencies and all 900 records / 1,073 questions. Full/release
accuracy .755824790308 / .756302521008; release matches upstream. Both native/raw
probability metric tables are in the reference results report. 9B remains running.

2026-10-30 16:45 UTC: 9B also completed with wrapper rc 0 at 16:44:49,
retained container exited/0 and VERIFIED_SCOPED audit (72 frozen / 63 required
files, 900 records / 1,073 questions). Full/release accuracy .791239515377 /
.791783380019. Release is one correct question above upstream .790849673203;
retain the difference. All three E22 inferences are now completed with scoped
arithmetic/artifact verification, not substantive Astra approval.
