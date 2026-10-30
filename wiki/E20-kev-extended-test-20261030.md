# E20 — Kev hard-v1 and documents-v1 native reference tests

Preregistered 2026-10-30 before launch. Models: released Kev 0.8B, 4B and 9B.

## Purpose and hypothesis

Defects 12 and 16 require valid measurements and comparable reference evidence. Evaluate
the existing released checkpoints on the exact frozen official test files. Memorizing
labels is the unconstrained optimum; this evaluation does not demonstrate unseen
generalization or NGA training benefit. Constant outputs can pass structural checks;
preserve per-task metrics and independent metric recomputation. Accuracy is not consistency.

## Frozen setup

Use original Kev pointer head, release temperature, fp32 backbone, eager attention,
merged adapter, reference GDN, HF32 disabled, same pinned bases as E7/E9/E12. No test
tuning, calibration, omission or truncation. Host 175 and existing immutable image only.

| Suite | Test records/questions | Test SHA256 | Context state/branch/packed |
| --- | ---: | --- | --- |
| hard-v1 | 700/1088 | `246ee92234d33f8e3f10ac6e1542651531b128fd7cc66f3a9964589b77dfa22b` | 7552/8192/9216 |
| documents-v1 | 574/936 | `742d04a1abc2207bd3e4f24b281f483cdc69238e4da747cbbc3774e836f2e557` | 8192/8192/16384 |

Both are under the Kev source repo `evals/`; every test ID is unique. Devtools-v1 is
excluded from this run because its historical ID collisions need a separate protocol.
Headline n is 1088/936. Native question-micro accuracy, one-hot summed Brier, ECE10
and NLL are reported at saved temperature and raw T=1 separately. Additional original
diagnostics remain labeled as native outputs unless independently recomputed.

## Execution and acceptance

Each size uses a new `reference_inference/kev{08,4,9}_extended_20261030/` directory.
Before its formal inference, tokenize every official development record in both suites,
select the longest packed record per suite (first index breaks ties), and infer it twice.
Strict native encoding must succeed without truncation and produce finite normalized
probabilities; record per-chip throughput, chip count and reserved memory. OOM or any
error blocks that model's full tests. This measures a bounded resource check, not a
complete input-length safety proof or test score. The original driver also checks each
test record's strict context and fails rather than skipping an overflowing record.

Freeze model/base/tokenizer, native source, data/manifests, driver, probe, verifier,
wrapper, registration and exact launch/relaunch before launch. Retained detached fixed
containers use independently claimed free chips after allocation-lock and live-device
checks; never chips 1/2 running Open-Jev or others' chips 6/7. CephFS stores logs,
heartbeats, atomic item receipts and terminal markers. The wrapper automatically runs
full inference only after probe success, then independent verifier only after full success.
Success requires complete records/questions, independent metrics and identities, wrapper
and container exit 0. Only then release resources. Errors preserve all evidence.

Published hard_test and docs1_test comparisons use the correct release entries where
available. A missing released panel is not substituted with a different split. The
decision/transfer-specific comparison helper is not used for these suites.

## Results

2026-10-30 execution: all frozen files were rehashed on 175 before each claim/launch.
The allocation lock and live Docker maps were checked before assigning chips 0/4/5.

| Model | Chip | Frozen files | Retained container ID |
| --- | ---: | ---: | --- |
| 0.8B | 0 | 68 | `484fc43d4d7a1f0a031046b28462501153c5e8158fa6c78bad59ebe48b43ae7d` |
| 4B | 4 | 73 | `6c7cd28f088cedcba511b50e67247dc763e27264d3b0a3800540e65a32dfd699` |
| 9B | 5 | 72 | `f0e7f012c9f38515447cfc319bd5a39b53db71f686770a114322573780a17030` |

Names are `nga-reference-kev08-extended`, `nga-reference-kev4-extended`, and
`nga-reference-kev9-extended`. Each launch receipt records actual command/entrypoint,
container ID, immutable image, config and wrapper hashes. The automatic wrapper first
executes the frozen probe, then full evaluation and independent audit, stopping on failure.

At 16:06:43 UTC, 0.8B had advanced into full hard-v1 test, 19/700 records,
3.4302 questions/s/chip, one chip, reserved 6.334 GiB. Its longest-dev probe completed
both suites: 5,086 packed tokens hard / 5,164 documents, repeat throughput 1.55657 /
1.60443 questions/s/chip, reserved 7.84375 / 10.96484 GiB. Full development tokenization
covered all 700 / 568 records before selecting these inputs.

4B also completed its longest-dev probe: same longest token counts, repeat throughput
0.69582 / 0.65999 questions/s/chip, one chip, reserved 26.27148 / 32.50977 GiB. Probe
terminal and report hash were checked. 9B was still loading at 16:06:49 UTC.
No full test score or successful final audit is claimed at this point.

16:08 UTC update: 9B longest-development probe also completed, with report hash and
terminal verified. Hard/documents repeat throughput was 0.51986 / 0.49713 questions/s/chip,
one chip, reserved 40.68164 / 46.91992 GiB. It automatically entered full-evaluation model
loading at 16:08:17 UTC. The 0.8B and 4B full hard-v1 jobs had reached 104/700 and 19/700
records at 16:07:43 / 16:07:31 UTC respectively. All three retained containers were running.

The unchanged reference-driver CPU tests passed all seven cases. Probe compilation passed;
actual strict encoding and runtime execution provide its resource evidence. No training
or Astra approval is claimed.

## Verdict

Pending.

**2026-10-30 16:12 UTC review correction:** the first frozen probe stored plain per-suite
JSON and did not enforce exactly two saved passes on resume. Fresh runs did execute both
passes; the orchestrator checked both entries in each report, positive timings and terminal
report hashes for all three sizes. These observations do not validate arbitrary resumed
probe receipts. Repository code now uses a checksum envelope and checks exactly two passes,
positive finite timings and matching token counts; five valid/corrupt/empty/timing/token
tests passed. Running frozen code remains unchanged. Do not automatically restart these
three runs through the old probe reuse branch: independently review existing probe evidence
first, or register a corrected new run. No actual crash/recovery claim is made for E20.


**2026-10-30 16:29 UTC completion update:** 0.8B completed at 16:23:51 UTC,
with wrapper `DONE rc=0` at 16:24:00 and retained container exited/0.
`INDEPENDENT_AUDIT.json` reports `VERIFIED_SCOPED`, 68 frozen files and 58 required
dependencies checked, all 1,274 records / 2,024 questions covered.

| Suite | n | Accuracy | Serving Brier | Serving ECE10 | Serving NLL | Raw T=1 Brier | Raw ECE10 | Raw NLL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| hard-v1 | 1088 | .666360294118 | .459719074612 | .125548387874 | .862586683630 | .435635256853 | .045529391553 | .810524748249 |
| documents-v1 | 936 | .851495726496 | .244001496780 | .071009331426 | .491122215279 | .249443193413 | .078570712270 | .575928811965 |

Hard accuracy is one correct question above release .665441176471; documents accuracy
matches release. Upstream 0.8B hard/documents per-row files were not available, so the
flipped question cannot be identified from aggregate scores. This is a scoped reference
reproduction with retained differences, not exact numerical equivalence or NGA benefit.
At 16:28:47 / 16:28:48 UTC, 4B / 9B remained in documents test at 535/574 and 454/574
records. Their complete results and final verdict remain pending. E22 has taken chip 0
through its dependency-checked controller and started devtools inference; E20 evidence
remains retained. No substantive Astra approval is claimed.

**2026-10-30 16:36 UTC completion update (supersedes the running status above):**
All three sizes completed both suites and scoped independent audits. Wrapper completion times
were 16:24:00 / 16:29:54 / 16:31:50 UTC for 0.8B / 4B / 9B. Retained containers exited/0;
launch identities and successful structured terminals were checked. Frozen/required dependency
counts are 68/58, 73/63 and 72/62. Each model covers 1,274 records / 2,024 questions.

| Model | Test | n | Temperature | Accuracy % | Brier | ECE10 | NLL |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| Kev-0.8B | hard-v1 | 1,088 | Released serving temperature | 66.636029 | 0.459719075 | 0.125548388 | 0.862586684 |
| Kev-0.8B | hard-v1 | 1,088 | raw T=1 | 66.636029 | 0.435635257 | 0.045529392 | 0.810524748 |
| Kev-0.8B | documents-v1 | 936 | Released serving temperature | 85.149573 | 0.244001497 | 0.071009331 | 0.491122215 |
| Kev-0.8B | documents-v1 | 936 | raw T=1 | 85.149573 | 0.249443193 | 0.078570712 | 0.575928812 |
| Kev-4B | hard-v1 | 1,088 | Released serving temperature | 80.330882 | 0.277582963 | 0.084146933 | 0.510298577 |
| Kev-4B | hard-v1 | 1,088 | raw T=1 | 80.330882 | 0.266842485 | 0.048480941 | 0.488188227 |
| Kev-4B | documents-v1 | 936 | Released serving temperature | 90.277778 | 0.170655143 | 0.100830150 | 0.356801403 |
| Kev-4B | documents-v1 | 936 | raw T=1 | 90.277778 | 0.152238923 | 0.043752814 | 0.327753587 |
| Kev-9B | hard-v1 | 1,088 | Released serving temperature | 83.455882 | 0.233743052 | 0.054294197 | 0.425359759 |
| Kev-9B | hard-v1 | 1,088 | raw T=1 | 83.455882 | 0.240956076 | 0.062900228 | 0.451785035 |
| Kev-9B | documents-v1 | 936 | Released serving temperature | 89.957265 | 0.151423755 | 0.017013200 | 0.297516503 |
| Kev-9B | documents-v1 | 936 | raw T=1 | 89.957265 | 0.165813476 | 0.062541371 | 0.412029369 |

9B hard accuracy is also one correct question above upstream .833639705882; 4B hard and
all documents accuracies agree with the corresponding upstream aggregates. This is not
per-item or probability equivalence. For 4B documents, the supplementary upstream report
supports accuracy only until calibration comparability is established. Full native/raw tables
are independently recomputed; no NGA training benefit or substantive Astra approval follows.
All three released chips have been transferred by E22's guarded dependency controller.
