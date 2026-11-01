# Reference baseline — latest results

Restored and synchronized: **2026-11-01 UTC**. This is the current repository entry point for reference test/OOD metrics. It consolidates the frozen matrix and its accepted additive results without changing historical readings. The [GitHub Wiki](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions) maintains the wider four-dimensional conclusions, current engineering status and next steps. Process records remain local and are archived every three days.

**Coverage: 36 of the fixed 38 model × dataset units have results; 2 remain blocked with null metrics.** The base matrix has 58 protocol panels over 30 units (Kev 15, Nimble 7, Typed Decisions 6, Open-Jev original test 2). The increment adds four JEVal units and two Open-Jev OOD units. Temperature variants and full/release masks are separate panels, not additional model × dataset units. This is the agreed reference scope, not a complete cross-product of every model and every dataset.

These are reference inference results. They do not establish an NGA training gain, decision consistency, a research gate pass or production business benefit. Development/calibration results from current training are reported separately in the Wiki; they are not inserted into these test tables. No new inference or training was run to restore this page.

Coverage note — 2026-11-02 v5 review: the frozen D1 values below remain unchanged. The candidate scope is being widened beyond the Jev-specific matrix because the current 38 units do not cover all required capability axes. Additional source candidates include AppliedMachineLearning-Lab Jev benchmarking (37 public task panels), JevBench public-231, Intern-Decision, Jevals, prevalence-shift, coherence, OOD-calibration and order-robustness repositories. These candidates have no Qwen3.5 results in this file until each panel passes source/split/input/metric/denominator/TEST-exposure admission. Native formulas remain separate; candidate rows are not read or reported as zero while they are `needs_review`.

Coverage note — 2026-11-02 v6 review: the user identified that the v5 candidate set was still too narrow. The provisional register now covers approximately 25–30 source/task families and 70+ native panels, pending manifest/hash/lineage/TEST-exposure closure. New capability axes include ordinary routing and complete-message accuracy, business-style typed decisions, numeric/temporal counterfactuals, prevalence shift, known/unknown calibration, ranking/order sensitivity, hierarchical coherence, refusal/selective prediction, web/closed-loop actions and independent multimodal matrices. These remain candidates only; no Qwen3.5 result is added here, no frozen D1 value changes, and no candidate TEST row is read while its panel is `needs_review`. The P0–P2 admission order is documented in [`proposal/18-dataset-coverage-expansion-v6-status-2026-11-02.md`](../proposal/18-dataset-coverage-expansion-v6-status-2026-11-02.md).

Coverage note — 2026-11-02 v7 review: the first common-text admission wave is now explicit rather than implicit. P0 contains ten source/task families: AppliedMachineLearning-Lab Jev benchmarking (about 37 native panels), JevBench public-231, Intern-Decision, Jevals, canonical/legacy DecisionBench, Decision Model Benchmark, BEV Decision, LocalLLaMA typed decisions, TDM prevalence-shift and Jev OOD calibration. The planning range remains approximately 25–30 source/task families and 70+ native panels; it is not a completed experiment count. The five v6-audited families and 18 declared panels remain `needs_review`, with zero `ready_for_inference`; no candidate TEST row or Qwen3.5 result is added here. The updated admission order is documented in [`../proposal/19-dataset-coverage-expansion-v7-status-2026-11-02.md`](../proposal/19-dataset-coverage-expansion-v7-status-2026-11-02.md).

Coverage note — 2026-11-02 P0 metadata milestone: six additional common-text source families were audited from documentation/manifests only: AppliedMachineLearning-Lab Jev benchmarking, Intern-Decision, Jevals, Hanno-Labs DecisionBench, Praveenrajus JevBench and akhilaaa3 DecisionBench. All remain `needs_review` with zero `ready_for_inference`; no candidate TEST row, model output or Qwen3.5 metric is added. The per-panel contract and lineage work must close before any of these sources enters the FIFO. Evidence is local in `.local/reports/p0-common-text-metadata-audit-20261102.{md,json}`.

Coverage note — 2026-11-02 dataset inventory revision: the local CephFS inventory contains 24 Jev-related top-level directories, but directory count is not independent-dataset count because it includes versions, result mirrors, subpanels and separate modalities. The expanded register therefore separates frozen D1, P0 text/typed/routing, P1 capability/risk and P2 multimodal/web/closed-loop/business-gap layers. P0 now names BEV Decision, LocalLLaMA typed decisions, canonical/legacy DecisionBench, Praveenrajus JevBench, Applied ML Jev panels, JevBench/Intern-Decision/Jevals, prevalence shift and OOD calibration; P1 names Eikos, Korean JEV, behavior, DecisionPivot, DecisionRobust, safety/guardrails, spatial/complex and order/coherence; P2 keeps OneJev/Imajev/WebJev and self-built Chinese rules, evidence, fallback, escalation and cost suites separate. The planning range remains approximately 25–30 source/task families and 70+ native panels, pending source/hash/split/input/metric/denominator/lineage/TEST-exposure closure. All candidate panels remain `needs_review` with zero `ready_for_inference`; no candidate TEST row or Qwen3.5 result is added here. See [`../proposal/21-status-decisions-next-plan-2026-11-02-dataset-coverage-revision.md`](../proposal/21-status-decisions-next-plan-2026-11-02-dataset-coverage-revision.md).

P0 panel register milestone — 2026-11-02: the six audited P0 families have a local machine-readable admission register. Their declared task/config count is 114, explicitly not an independent panel count; lineage and native protocol closure remain pending. All six stay `needs_review`, with zero `ready_for_inference`; no candidate TEST row or Qwen3.5 result is added.

Execution progress — 2026-11-01 21:29 UTC: formal K1 v15 remains train-only and running. Seed2 is `650/3116` (20.86%, about 954.5 tok/s/chip) and seed3 is `580/3116` (18.61%, about 845.0 tok/s/chip); fresh heartbeats and no terminal markers are present. The allocation ledger binds seed2/seed3 to chip2/chip3. AICore windows are about 53.0%/53.6%, so active execution is evidenced but sustained full load is not claimed. No TEST or Qwen3.5 result is added.

Efficiency note — 2026-11-02: possible host-side gaps in sequence/index construction, per-chunk synchronization, `micro_tokens` sizing and the reference kernel are recorded for a separate engineering benchmark. The formal arm is unchanged; no Qwen3.5 metric is added.

Execution progress — 2026-11-01 21:49 UTC: formal K1 v15 remains train-only and running. Seed2 is `1050/3116` (33.7%) and seed3 is `980/3116` (31.5%), with fresh heartbeats and no terminal markers. No TEST or Qwen3.5 result is added.

Execution progress — 2026-11-01 21:59 UTC: formal K1 v15 remains train-only and running. Seed2 is `1250/3116` (40.1%) and seed3 is `1170/3116` (37.5%), with fresh heartbeats and no terminal markers. No TEST or Qwen3.5 result is added.

Execution note — 2026-11-02: formal K1 v15 train-only seed2/seed3 is now running on host 175, bound to chip2/chip3 after reviewed `PLAN_VERIFIED` outputs and atomic resource claims. This does not add a reference or Qwen3.5 test metric; `test_read=false` and scientific acceptance remains false. The watchdog currently has fewer than three utilization passes, so the initial AICore means are not a sustained full-load verdict. Launch receipts and claims are recorded in local `.local/reports/formal-k1-launch-milestone-20261102.json`.

Execution progress — 2026-11-02 21:05 UTC: both v15 seeds remain `running` with fresh heartbeats and no terminal markers. Watchdog progress is seed2 150/3116 (4.8%, about 855.5 tok/s/chip) and seed3 120/3116 (3.9%, about 795.0 tok/s/chip); these are training-throughput observations, not test metrics. No TEST read or Qwen3.5 result is added to this reference file until DEV selection, a separate final TEST ticket and independent scoring are complete.

## Evidence and reading conventions

- [REFERENCE-BASELINE-MATRIX-2026-10-31.json](REFERENCE-BASELINE-MATRIX-2026-10-31.json) — SHA256 `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`.
- [REFERENCE-BASELINE-INCREMENT-2026-10-31.json](REFERENCE-BASELINE-INCREMENT-2026-10-31.json) — SHA256 `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`.

Source-location correction, 2026-11-01: [REFERENCE-SOURCE-LOCATIONS.json](REFERENCE-SOURCE-LOCATIONS.json) maps six archived path/hash versions without rewriting either snapshot. A CPU byte-identity check matched all 96 unique path/hash references: 90 at their original locations, five in the local archive, and one historical version recovered byte-for-byte from Git. This is artifact identity verification only; it does not independently recompute predictions or repair the missing historical audit-terminal bindings described below.

The JSON records preserve exact values, dataset identities, report hashes, source paths, audit scope and evidence pointers. The increment supersedes six pending entries in the immutable base snapshot; the two remaining blocked entries below are current. Base snapshot date: 2026-10-31; increment last update: `2026-10-30T23:03:37.980383+00:00`. Snapshot timestamps are reproduced as stored and are not new-run timestamps.

Accuracy columns use percent; all other metrics retain native units. Display rounding is 3 decimals for percentages and 6 for other metrics; exact JSON values remain authoritative. `—` means unavailable/not applicable, never zero. There are no cross-dataset averages. Native/serving temperatures are inherited from the references, not fitted on these tests.

## Kev original tests

Question-weighted hard accuracy, summed one-hot multiclass Brier, top-confidence ECE10 and NLL. `clean` is the frozen clean mask. The devtools full mask has 1,073 questions; the release-aligned mask has 1,071. NLL uses recorded logits where available, otherwise probability floor 1e-9. Accuracy agreement does not imply identical item predictions or calibration.

### Native temperatures

| Model | Dataset/mask | n | T | Accuracy | Brier | ECE10 | NLL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | decision-v7/clean | 1200 | 2.3510958126 | 83.750% | 0.230501 | 0.018981 | 0.432025 |
| Kev-0.8B | transfer-v4/clean | 656 | 2.3510958126 | 69.665% | 0.396638 | 0.046375 | 0.673409 |
| Kev-0.8B | hard-v1/clean | 1088 | 2.3510958126 | 66.636% | 0.459719 | 0.125548 | 0.862587 |
| Kev-0.8B | documents-v1/clean | 936 | 2.3510958126 | 85.150% | 0.244001 | 0.071009 | 0.491122 |
| Kev-0.8B | devtools-v1/full | 1073 | 2.3510958126 | 63.653% | 0.442394 | 0.084400 | 0.778105 |
| Kev-0.8B | devtools-v1/release | 1071 | 2.3510958126 | 63.679% | 0.442355 | 0.084701 | 0.778334 |
| Kev-4B | decision-v7/clean | 1200 | 2.4060500722 | 86.500% | 0.186240 | 0.019310 | 0.349845 |
| Kev-4B | transfer-v4/clean | 656 | 2.4060500722 | 83.841% | 0.224157 | 0.016704 | 0.416391 |
| Kev-4B | hard-v1/clean | 1088 | 2.4060500722 | 80.331% | 0.277583 | 0.084147 | 0.510299 |
| Kev-4B | documents-v1/clean | 936 | 2.4060500722 | 90.278% | 0.170655 | 0.100830 | 0.356801 |
| Kev-4B | devtools-v1/full | 1073 | 2.4060500722 | 75.582% | 0.341848 | 0.077334 | 0.601769 |
| Kev-4B | devtools-v1/release | 1071 | 2.4060500722 | 75.630% | 0.341743 | 0.077588 | 0.601792 |
| Kev-9B | decision-v7/clean | 1200 | 2.1936499594 | 87.250% | 0.177666 | 0.027078 | 0.339478 |
| Kev-9B | transfer-v4/clean | 656 | 2.1936499594 | 85.213% | 0.198949 | 0.036219 | 0.370416 |
| Kev-9B | hard-v1/clean | 1088 | 2.1936499594 | 83.456% | 0.233743 | 0.054294 | 0.425360 |
| Kev-9B | documents-v1/clean | 936 | 2.1936499594 | 89.957% | 0.151424 | 0.017013 | 0.297517 |
| Kev-9B | devtools-v1/full | 1073 | 2.1936499594 | 79.124% | 0.309081 | 0.097420 | 0.570114 |
| Kev-9B | devtools-v1/release | 1071 | 2.1936499594 | 79.178% | 0.309009 | 0.096861 | 0.570192 |

### Raw T=1

| Model | Dataset/mask | n | T | Accuracy | Brier | ECE10 | NLL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | decision-v7/clean | 1200 | 1 | 83.750% | 0.261037 | 0.100331 | 0.608459 |
| Kev-0.8B | transfer-v4/clean | 656 | 1 | 69.665% | 0.416445 | 0.099264 | 0.737529 |
| Kev-0.8B | hard-v1/clean | 1088 | 1 | 66.636% | 0.435635 | 0.045529 | 0.810525 |
| Kev-0.8B | documents-v1/clean | 936 | 1 | 85.150% | 0.249443 | 0.078571 | 0.575929 |
| Kev-0.8B | devtools-v1/full | 1073 | 1 | 63.653% | 0.455260 | 0.101733 | 0.799732 |
| Kev-0.8B | devtools-v1/release | 1071 | 1 | 63.679% | 0.455252 | 0.101601 | 0.800022 |
| Kev-4B | decision-v7/clean | 1200 | 1 | 86.500% | 0.210427 | 0.080424 | 0.486820 |
| Kev-4B | transfer-v4/clean | 656 | 1 | 83.841% | 0.241839 | 0.085532 | 0.565516 |
| Kev-4B | hard-v1/clean | 1088 | 1 | 80.331% | 0.266842 | 0.048481 | 0.488188 |
| Kev-4B | documents-v1/clean | 936 | 1 | 90.278% | 0.152239 | 0.043753 | 0.327754 |
| Kev-4B | devtools-v1/full | 1073 | 1 | 75.582% | 0.343589 | 0.071655 | 0.609042 |
| Kev-4B | devtools-v1/release | 1071 | 1 | 75.630% | 0.343650 | 0.071547 | 0.609270 |
| Kev-9B | decision-v7/clean | 1200 | 1 | 87.250% | 0.202317 | 0.075008 | 0.467006 |
| Kev-9B | transfer-v4/clean | 656 | 1 | 85.213% | 0.216394 | 0.082492 | 0.464311 |
| Kev-9B | hard-v1/clean | 1088 | 1 | 83.456% | 0.240956 | 0.062900 | 0.451785 |
| Kev-9B | documents-v1/clean | 936 | 1 | 89.957% | 0.165813 | 0.062541 | 0.412029 |
| Kev-9B | devtools-v1/full | 1073 | 1 | 79.124% | 0.295619 | 0.059792 | 0.564034 |
| Kev-9B | devtools-v1/release | 1071 | 1 | 79.178% | 0.295580 | 0.059480 | 0.564235 |

### Published reference comparison (native protocol only)

Upstream means the release artifact recorded in each JSON row, not an inferred paper-exact result. Full-mask devtools has no matched published value. Kev-4B/9B documents-v1 upstream calibration/temperature comparability is unestablished, so only accuracy is compared there.

| Model | Dataset/mask | Local accuracy | Upstream accuracy | Upstream Brier | Upstream ECE10 | Upstream NLL |
| --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | decision-v7/clean | 83.750% | 83.750% | 0.230489 | 0.018160 | — |
| Kev-0.8B | transfer-v4/clean | 69.665% | 69.665% | 0.396632 | 0.044841 | — |
| Kev-0.8B | hard-v1/clean | 66.636% | 66.544% | 0.459717 | 0.124636 | — |
| Kev-0.8B | documents-v1/clean | 85.150% | 85.150% | 0.243963 | 0.071048 | — |
| Kev-0.8B | devtools-v1/release | 63.679% | 63.679% | 0.442331 | 0.084693 | — |
| Kev-4B | decision-v7/clean | 86.500% | 86.500% | 0.186253 | 0.019285 | — |
| Kev-4B | transfer-v4/clean | 83.841% | 83.841% | 0.224210 | 0.016767 | — |
| Kev-4B | hard-v1/clean | 80.331% | 80.331% | 0.277644 | 0.084266 | — |
| Kev-4B | documents-v1/clean | 90.278% | 90.278% | — | — | — |
| Kev-4B | devtools-v1/release | 75.630% | 75.630% | 0.341793 | 0.077716 | — |
| Kev-9B | decision-v7/clean | 87.250% | 87.250% | 0.177667 | 0.027405 | — |
| Kev-9B | transfer-v4/clean | 85.213% | 85.213% | 0.199036 | 0.034421 | — |
| Kev-9B | hard-v1/clean | 83.456% | 83.364% | 0.233727 | 0.054144 | — |
| Kev-9B | documents-v1/clean | 89.957% | 89.957% | 0.151425 | 0.017012 | — |
| Kev-9B | devtools-v1/release | 79.178% | 79.085% | 0.309060 | 0.097879 | — |

Sources: `jaredpalmer/kev` release files `kev-08b-r15.json`, `kev-4b-r10.json`, `kev-9b-r27.json` and the two `fam-4b/9b-docs1test/report.json` artifacts. Exact local source paths, hashes and JSON pointers are in each matrix row’s `upstream.source`.

## Nimble native tests

Nimble-9B uses native T=1 over seven subsets (1,884 items). Hard-reference argmax accuracy, one-hot summed multiclass Brier, binary Noul Brier `(p_true−y)²`, top-confidence ECE10, reference-class NLL and expected-score MAE in original level units remain separate. No cross-subset pooled number is reported.

| Subset | n | Accuracy | Brier (sum) | Binary Brier | ECE10 | NLL | Score MAE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| massive-en-US | 350 | 86.857% | 0.215612 | — | 0.069903 | 0.566445 | — |
| massive-de-DE | 350 | 84.000% | 0.256619 | — | 0.081899 | 0.664881 | — |
| paws | 250 | 82.800% | 0.279648 | 0.139824 | 0.100160 | 0.541911 | — |
| civil_comments | 300 | 70.000% | 0.413404 | 0.206702 | 0.135851 | 0.641568 | — |
| aegis2 | 250 | 81.600% | 0.289384 | 0.144692 | 0.098642 | 0.568026 | — |
| summeval-relevance | 240 | 48.750% | 0.676896 | — | 0.090175 | 1.305991 | 0.695520 |
| summeval-consistency | 144 | 75.000% | 0.419423 | — | 0.171724 | 0.905904 | 0.567382 |

Published rounded values from `bespokelabsai/nimble/docs/PUBLIC_BENCHMARKS.md` (source hash and restored subset identities in the matrix):

| Subset | Upstream accuracy | Upstream Brier | Upstream ECE10 | Upstream score MAE |
| --- | --- | --- | --- | --- |
| massive-en-US | 86.900% | 0.216000 | 0.061000 | — |
| massive-de-DE | 83.400% | 0.256000 | 0.079000 | — |
| paws | 82.800% | 0.280000 | 0.100000 | — |
| civil_comments | 70.300% | 0.413000 | 0.133000 | — |
| aegis2 | 81.200% | 0.289000 | 0.102000 | — |
| summeval-relevance | 49.200% | 0.678000 | 0.102000 | 0.698000 |
| summeval-consistency | 75.700% | 0.421000 | 0.177000 | 0.569000 |

Civil Comments also compares predicted and human label distributions on n=300: base-2 JSD 0.175792 (published 0.176000); TV 0.292535 (published 0.292000); mean human entropy 0.239332 bits. These distribution metrics do not share the hard-label accuracy target. Upstream item predictions are unavailable; this is an aggregate comparison to rounded published values.

## Typed Decisions common test

This is the common comparison task, not a reproduction of each reference model’s native test. It contains 400 states and 2,000 equally weighted questions. Accuracy compares first argmax(p) with first argmax(q). Original rounded gold masses are not renormalized; prediction probabilities are normalized. KL(q‖p) uses floor 1e-9; Brier is summed squared error; ECE10 uses hard argmax correctness. Original arithmetic and strict checks remain in the underlying evidence; these metrics do not claim full native wire/HTTP reproduction.

| Model | Protocol | T | n | Accuracy | KL(q‖p) | Brier | ECE10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | serving | 2.3510958126 | 2000 | 45.950% | 0.349523 | 0.195493 | 0.045770 |
| Kev-0.8B | raw_T1 | 1 | 2000 | 45.950% | 0.498068 | 0.260309 | 0.155170 |
| Kev-4B | serving | 2.4060500722 | 2000 | 66.450% | 0.223109 | 0.124565 | 0.089534 |
| Kev-4B | raw_T1 | 1 | 2000 | 66.450% | 0.504515 | 0.201069 | 0.091401 |
| Kev-9B | serving | 2.1936499594 | 2000 | 68.050% | 0.213790 | 0.116321 | 0.064928 |
| Kev-9B | raw_T1 | 1 | 2000 | 68.050% | 0.519309 | 0.187225 | 0.091136 |
| Nimble-9B | serving | 1 | 2000 | 65.100% | 0.706028 | 0.254995 | 0.172864 |
| Open-Jev-2B | serving | 1.5187963429 | 2000 | 58.250% | 0.410911 | 0.193817 | 0.081003 |
| Open-Jev-2B | raw_T1 | 1 | 2000 | 58.250% | 0.659782 | 0.245028 | 0.159235 |
| Open-Jev-9B | serving | 1.8969118766 | 2000 | 67.800% | 0.369436 | 0.147618 | 0.058202 |
| Open-Jev-9B | raw_T1 | 1 | 2000 | 67.800% | 0.885942 | 0.224383 | 0.148582 |

Nimble serving is already T=1 and is not duplicated. There is no matched published upstream score for this common task in the frozen matrix.

## Open-Jev original release-v2 test

All-row n=10,532: 10,046 one-hot hard rows and 486 soft rows. Hard accuracy uses only hard rows; expected accuracy `mean(q[argmax(p)])`, NLL `−mean(sum(q log p))`, Brier, expected Brier and ECE15 use all rows. Expected Brier adds `mean(1−sum(q²))` to Brier. ECE15 compares top confidence with expected correctness.

| Model | Protocol | T | Hard accuracy | Expected accuracy | NLL | Brier | Expected Brier | ECE15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Open-Jev-2B | serving | 1.5187963429 | 94.635% | 91.877% | 0.195622 | 0.076288 | 0.104339 | 0.012282 |
| Open-Jev-2B | raw_T1 | 1 | 94.635% | 91.877% | 0.213531 | 0.080689 | 0.108740 | 0.024150 |
| Open-Jev-9B | serving | 1.8969118766 | 97.511% | 94.687% | 0.130801 | 0.039047 | 0.067098 | 0.007525 |
| Open-Jev-9B | raw_T1 | 1 | 97.511% | 94.687% | 0.138525 | 0.040875 | 0.068926 | 0.011593 |

Published original-test comparison from `Zefan-Cai/Open-Jev/reports/full-data-eval-n1-v1/{2b,9b}-audit.json`, with the same original-test population and native temperature:

| Model | Protocol | T | Hard accuracy | Expected accuracy | NLL | Brier | Expected Brier | ECE15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Open-Jev-2B | upstream serving | 1.5187963429 | 94.714% | 91.953% | 0.195380 | 0.076117 | 0.104168 | 0.011606 |
| Open-Jev-9B | upstream serving | 1.8969118766 | 97.541% | 94.715% | 0.130947 | 0.039113 | 0.067164 | 0.007707 |

These are aggregate comparisons. A net correct-count difference is not the number of prediction flips and does not establish a hardware cause. Selective coverage curves at thresholds 0.5, 0.7, 0.8, 0.9, 0.95 and 0.99 are retained under each JSON row’s `metrics.coverage`; selected hard and selected expected accuracy use different eligible populations.

## JEVal original test — native response formulas

Each model covers the same 11,257-row inventory: 10,938 classification rows and 319 score rows. Classification accuracy uses actual native choice or Noul ≥0.5 and divides correct answers by **all 10,938 rows**; unsupported/overlength rows count as incorrect. Brier uses unrenormalized wire probabilities, Noul `[1−p,p]`, and only valid classification rows. ECE10 uses native confidence and the local right-bin convention. Score MAE is valid-only in native scale (Kev expected rounded score; Nimble selected integer). This is a local response-formula evaluation, not an exact paper-scorer reproduction.

| Model | T | Correct / full classification | Accuracy | Valid classification n | Valid Brier | Valid ECE10 | Valid / full score n | Score MAE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | 2.3510958126 | 5089/10938 | 46.526% | 9911 | 0.598302 | 0.163216 | 319/319 | 1.121768 |
| Nimble v1 | 1 | 5394/10938 | 49.314% | 7694 | 0.433576 | 0.135361 | 312/319 | 0.842949 |
| Kev-4B | 2.4060500722 | 6741/10938 | 61.629% | 9911 | 0.436119 | 0.173661 | 319/319 | 0.914081 |
| Kev-9B | 2.1936499594 | 6931/10938 | 63.366% | 9911 | 0.406847 | 0.109838 | 319/319 | 0.923337 |

| Model | Valid rows (both types) | Overlength | Unsupported | Retained review flags |
| --- | --- | --- | --- | --- |
| Kev-0.8B | 10230 | 1027 | 0 | 6 |
| Nimble v1 | 8006 | 998 | 2253 | 30 |
| Kev-4B | 10230 | 1027 | 0 | 8 |
| Kev-9B | 10230 | 1027 | 0 | 7 |

Nimble’s 2,253 unsupported rows comprise 2,047 with more than 26 candidates and 206 requiring nonempty context (ARC Challenge 95; ARC Easy 111); overlength is a separate 998 rows. The additive erratum changes this explanation, not metrics. Kev-4B/9B length errata likewise change no metrics: limits can be exceeded by state plus branch, even when `state_tokens` is null. Valid-only metrics use different model-specific populations and are not a same-item controlled comparison. No raw-T1, NOTA or permutation protocol is added.

| Model × dataset | Current status | Metric |
| --- | --- | --- |
| Open-Jev-2B × JEVal original test | blocked_numerical_admission | null |
| Open-Jev-9B × JEVal original test | blocked_numerical_admission | null |

Both remaining Open-Jev×JEVal cells failed E36/E37 candidate-batch numerical admission; E38 is diagnostic only. An exit-zero probe does not admit full JEVal execution.

## Open-Jev original OOD release-v2

Both checkpoints cover the same 15,920 rows: 15,446 hard and 474 soft. Native/raw T=1 panels derive from the same saved logits, not separate model runs. Formula definitions match the OOD increment: `softmax(logits/T)`, natural-log NLL with floor 1e-15, summed Brier, expected Brier and ECE15. Hard accuracy uses the 15,446 hard rows; all other headline metrics use all 15,920.

| Model | Protocol | T | Hard accuracy | Expected accuracy | NLL | Brier | Expected Brier | ECE15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Open-Jev-2B | serving | 1.5187963429 | 86.029% | 84.617% | 0.802074 | 0.246289 | 0.263620 | 0.105578 |
| Open-Jev-2B | raw_T1 | 1 | 86.029% | 84.617% | 1.156734 | 0.254767 | 0.272097 | 0.119213 |
| Open-Jev-9B | serving | 1.8969118766 | 91.979% | 90.414% | 0.299677 | 0.126748 | 0.144078 | 0.037593 |
| Open-Jev-9B | raw_T1 | 1 | 91.979% | 90.414% | 0.451535 | 0.137555 | 0.154885 | 0.058513 |

No matched published OOD number is supplied in the increment, so none is inferred. The JSON retains per-source, per-kind and selective-coverage panels. Coverage divides selected rows by the full panel; selected hard accuracy uses selected hard rows, selected expected accuracy uses all selected rows, and undefined values remain null. Grouped synthetic controls are not independent business scenarios. Across-checkpoint differences are reference comparisons, not training treatment effects.

## Audit limits and current acceptance boundary

- The base exporter checked available report/terminal/audit hash bindings, primary metrics, coverage and denominators. It did not rerun inference or independently re-audit raw predictions. Its row-level audit scopes remain binding.
- **28 Kev panels retain an absent historical audit-SHA terminal binding**: the 0.8B native-test run and all extended/devtools inline audits have report-bound inference terminals and metric agreement, but no successful finisher binding the audit SHA. Restoring this page does not upgrade that evidence.
- **Completed dated E39 re-audit:** [current result index](REFERENCE-DATED-REAUDIT-LATEST.json) restores an omitted accepted conclusion. Seven runs / 8,462 saved records / 11,495 questions / all 28 legacy panels were re-audited, with original 1e-10 tolerances and unchanged formulas. The actual Astra review independently reconstructed all 28 panels (maximum matrix difference 1.11e-16) and verified its 8,930-file bundle; 77 excluded dependencies were not reread. On 2026-11-01, 47 result/review/terminal artifacts and saved 8,952-entry before/after scan equality were rechecked. This restores prior evidence, not a new experiment or historical finisher. The dated wording erratum, small/perfect subgroup limits, untested recovery scope and original binding labels remain.
- Original Open-Jev test retains exact-boundary and small-population flags (including trex_runner n=4). Coverage-cell perfect values are flags for inspection, not general capability claims.
- All six incremental units have completed actual Astra scoped review, with their original flags and errata retained. This is bounded reference-result review, not global execution admission, independent verification of all weights/dependencies, or proof against contamination.
- JEVal flag counts remain 6 for Kev-0.8B, 30 for Nimble, 8 for Kev-4B and 7 for Kev-9B; see the increment’s `review_flags` for exact pointers. OOD 9B retains three main-panel flags; 2B having zero main-panel flags does not imply zero coverage-cell boundary flags.
- No new candidate test gain is published here. Training/development comparisons and current readiness/recovery review are separate milestones maintained on the Wiki.

Future accepted reference milestones update this file and the Wiki together, preserving formulas and past measured values. Corrections are dated and identify whether metrics changed. The archived former page is historical material and is not the current authority.

**2026-11-01 restoration note:** the previous latest-page path was removed during process-document cleanup while later documents still linked to it. This page restores the requested stable GitHub entry using the unchanged machine-readable result records; it does not restore the obsolete run-status chronology.
