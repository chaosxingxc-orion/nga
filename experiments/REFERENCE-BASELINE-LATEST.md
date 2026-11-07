# Reference baseline — latest results

Restored: **2026-11-01 UTC**; latest additive result update: **2026-11-07 UTC**. This is the current repository entry point for reference test/OOD metrics. It consolidates the frozen matrix and its accepted additive results without changing historical readings. The [GitHub Wiki](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions) maintains the wider four-dimensional conclusions, current engineering status and next steps. Process records remain local and are archived every three days.

**Coverage: 36 of the fixed 38 model × dataset units have results; 2 remain blocked with null metrics.** The base matrix has 58 protocol panels over 30 units (Kev 15, Nimble 7, Typed Decisions 6, Open-Jev original test 2). The increment adds four JEVal units and two Open-Jev OOD units. Temperature variants and full/release masks are separate panels, not additional model × dataset units. This is the agreed reference scope, not a complete cross-product of every model and every dataset.

These are reference inference results. They do not establish an NGA training gain, decision consistency, a research gate pass or production business benefit. Development/calibration results from current training are reported separately in the Wiki; they are not inserted into these test tables. No new inference or training was run to restore this page.

Coverage correction — 2026-11-02: the 38 units above are model × dataset units, not 38 independent datasets or a complete NxM. The latest v9 metadata audit covers 12 expansion sources, all `needs_review`, with zero newly admitted panels in that audit. Previous approximate source/panel targets are superseded as current coverage counts; source identity, native TEST, metric denominator and overlap must be established per panel. See the [current coverage plan](../proposal/24-dataset-coverage-expansion-v10-20261102.md) and [GitHub Wiki coverage conclusions](https://github.com/chaosxingxc-orion/nga/wiki/Dataset-Coverage). No new result is introduced by this correction.

Current coverage snapshot (2026-11-04): **112 inferred/scored and parent-accepted cells** in the recent four-size Qwen extension (28 complete panels). The inventoried28-panel ×4-size subset contains112 cells:112 accepted and0 not yet accepted, including running and reconstructed results. Within its Jev-bench22-panel subset,88/88 are accepted. These are partial inventories, not the global Cartesian denominator; historical36/38 remains a separate registry. Published counts preserve previous readings; newly accepted local-codebook cells are separated below from publisher-native protocols.

Execution status and dataset-admission progress are maintained in the Wiki. Fixed reference-model TEST evaluation can proceed per admitted panel; final evaluation of newly trained candidates follows DEV selection and a frozen TEST plan. Training progress is not a reference TEST metric.


The fixed 2B/4B/9B retained-training **DEV** reconstruction and paired arithmetic now have scoped independent acceptance: [machine-readable conclusions](SCALE-DEV-SCOPED-RESULTS-2026-11-05.json) and [Wiki](https://github.com/chaosxingxc-orion/nga/wiki/Scale-DEV-Scoped-Conclusions). Complete eligibility remains open, including a disclosed overbroad report-half decoding boundary. These DEV diagnostics are separate from the TEST tables and grant no new TEST or historical formal-training claim.

## Accepted training comparison — 2026-11-05

The fixed Qwen3.5-0.8B seven-member same-TEST report passed independent scientific review. Primary seed-mean accuracy is **83.333333%** on decision-v7 (1200 questions) and **67.530488%** on transfer-v4 (656), improving over its own Base by **28.500000 pp** and **4.725610 pp**. Frozen paired 90% intervals are [25.958333, 31.041667] and [1.448171, 7.926829] pp. Transfer ECE worsens; no uniform metric improvement or superiority over PT is claimed.

[Accepted result artifact](FINAL-SAME-TEST-RESULTS-2026-11-05.json) · [Full tables and qualified local Kev comparison](https://github.com/chaosxingxc-orion/nga/wiki/Qwen35-Final-Same-TEST). Local Kev saved-item comparisons preserve native versus T=1 protocols and the missing historical audit-SHA binding; the exact source-question mask and data mapping for all1,856 questions are now independently accepted. This is a field-mapping comparison across different interfaces: prompt-byte, tokenizer and numerical equivalence are not established; outer whitespace differs on36 decision input rows,1 transfer input row and8 transfer definitions. Historical reference tables below are unchanged.

### Current twelve-member same-TEST comparison — 2026-11-06

The current fixed roster contains Qwen3.5 0.8B, 2B, 4B and 9B, each with its own Base and fixed seed-2/seed-3 adapters. All eight model-size/task own-Base cells were independently accepted under the frozen decision-v7 and transfer-v4 TEST protocols. The authoritative tables, paired effects, controls and limitations are maintained in the [full-family Wiki report](https://github.com/chaosxingxc-orion/nga/wiki/RC1-Full-Family-Same-TEST) and its [comparison JSON](https://raw.githubusercontent.com/wiki/chaosxingxc-orion/nga/RC1-Full-Family-Same-TEST-comparison.json).

This is a descriptive conditional comparison, not a universal training claim, gate decision or business result. The two reports are separate milestones: the seven-member result above preserves its original scope, while the twelve-member report adds the 2B/4B/9B roles and does not rewrite historical values. The latest accepted two-seed own-Base decision/transfer effects are, respectively, **+28.583333/+4.801829 pp** (0.8B), **+21.375000/+10.518293 pp** (2B), **+10.541667/+4.573171 pp** (4B), and **+7.708333/+6.097561 pp** (9B). Transfer calibration and other adverse panels remain disclosed in the full report.

### Scoped 4B/9B reference attachment — 2026-11-07

[Accepted reference alignment](https://github.com/chaosxingxc-orion/nga/wiki/RC1-Family-Reference-Alignment) adds model-specific, receipt-based same-source TEST context for Kev-4B/9B. Current continuation, historical pointer native/T1 and publisher aggregates remain separate. Across eight current seed/task cells versus local native Kev, accuracy is higher in two, equal in one and lower in five; NLL/Brier/ECE are worse in all eight. Existing own-Base acceptance and regressions remain unchanged. No paired reference inference or training superiority is claimed; reference TEST exposure to training design remains disclosed. Kev-2B and publisher NLL remain absent. Historical source metrics below are unchanged.

## Kev documents/devtools — completed Base matrix, 2026-11-07

Six further saved TEST cells (2B/4B/9B × two datasets) pass independent numerical and adversarial review for scoped descriptive publication; together with the prior0.8B cells this completes this particular 4×2 Base matrix. This is not the global Cartesian inventory and does not complete the separate Instruct queue. [Exact metrics, controls, provenance and all17 limitations](KEV-FIXED-BASE-TEST-2026-11-07.json) · [Wiki matrix and review](https://github.com/chaosxingxc-orion/nga/wiki/Kev-Documents-Devtools-Public-TEST).

| Public TEST | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| documents correct/936 | 606 | 694 | 751 | 775 |
| documents accuracy | 64.743590% | 74.145299% | 80.235043% | 82.799145% |
| documents both-correct/395 pairs | 152 | 230 | 271 | 288 |
| devtools correct/1073 | 467 | 539 | 555 | 606 |
| devtools accuracy | 43.522833% | 50.232992% | 51.724138% | 56.477167% |
| devtools both-correct/454 pairs | 1 | 112 | 51 | 68 |

These are fixed Base adapted-label T=1 results, not training gains. The native trained Kev-0.8B pointer endpoint and shipped T=2.3510958125672174 remain separate context; native exact NLL is unavailable. The devtools1071 release-ID mask is reported separately and has no454-pair result. All devtools Base sizes shown have Brier and exact NLL worse than uniform; 4B/9B collapse to false on both code-review and flaky-test despite distinct logits, and their both-correct counts decline versus2B. Documents bank-account correctness is15/48,12/48,16/48 for2B/4B/9B. Keep the complete adverse rows and limitations with the headline metrics; no TEST selection, native matched significance or causal consistency claim follows. Prior0.8B artifact and historical coverage counts remain unchanged.

## Large-candidate released TEST — local codebook protocol, 2026-11-04

Twenty cells independently reconstructed and diagnosed from all20,000 saved records. [Full metrics and evidence](REFERENCE-LARGE-CANDIDATE-INCREMENT-2026-11-04.json). Each cell uses1,000 released TEST rows, float32, HF32off, batch1, all77/151/60/100 candidates for Banking77/CLINC150/MASSIVE/LEDGAR respectively, one forward; this local interface is not the original publisher endpoint. Other cells remain pending acceptance.

| Task | Qwen3.5 Base | Correct/n | Accuracy | Macro-F1 | Balanced accuracy | Vector Brier | NLL (nats) | ECE15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| banking77 | 08b | 22/1000 | 2.2% | 0.009851 | 0.023704 | 1.045725 | 5.954751 | 0.161240 |
| banking77 | 2b | 12/1000 | 1.2% | 0.000310 | 0.012987 | 1.068676 | 5.918805 | 0.220709 |
| banking77 | 4b | 440/1000 | 44.0% | 0.418439 | 0.439718 | 0.778950 | 3.274129 | 0.131077 |
| clinc150 | 08b | 7/1000 | 0.7% | 0.000350 | 0.009461 | 1.084700 | 7.528431 | 0.187764 |
| clinc150 | 2b | 8/1000 | 0.8% | 0.001112 | 0.007285 | 1.067507 | 7.023363 | 0.173660 |
| banking77 | 9b | 424/1000 | 42.4% | 0.420573 | 0.417690 | 0.789818 | 2.931394 | 0.134384 |
| clinc150 | 4b | 423/1000 | 42.3% | 0.506465 | 0.523983 | 0.753368 | 3.802889 | 0.100242 |
| clinc150 | 9b | 387/1000 | 38.7% | 0.472384 | 0.479867 | 0.763236 | 3.674391 | 0.086193 |
| massive | 08b | 3/1000 | 0.3% | 0.000100 | 0.017241 | 1.206643 | 5.983877 | 0.456181 |
| massive | 2b | 3/1000 | 0.3% | 0.000100 | 0.017241 | 1.121948 | 5.988863 | 0.308167 |
| massive | 4b | 459/1000 | 45.9% | 0.410654 | 0.450384 | 0.703730 | 2.630925 | 0.105414 |
| massive | 9b | 405/1000 | 40.5% | 0.355926 | 0.367785 | 0.754670 | 2.992010 | 0.060142 |
| ledgar | 08b | 46/1000 | 4.6% | 0.013509 | 0.028622 | 1.031944 | 6.005193 | 0.110802 |
| ledgar | 2b | 68/1000 | 6.8% | 0.012560 | 0.024561 | 1.013298 | 5.388265 | 0.214949 |
| ledgar | 4b | 600/1000 | 60.0% | 0.450902 | 0.526925 | 0.603394 | 2.026824 | 0.113005 |
| ledgar | 9b | 587/1000 | 58.7% | 0.410449 | 0.484318 | 0.577620 | 1.897855 | 0.071712 |

LEDGAR9B completes this four-size panel: 587/1000, accuracy58.7%, macro-F1 0.410449, balanced accuracy0.484318, vector Brier0.577620, NLL1.897855, ECE15 0.071712. Complete source/tokenizer/saved-arithmetic diagnosis and parent verification of2045 evidence pins passed. Its accuracy is1.3pp below4B while Brier/NLL/ECE are lower; no uniform size advantage.

GoEmotions completes the four-model panel: accuracy is 2.1%/3.5%/16.1%/19.1% for 0.8B/2B/4B/9B. Hard macro-F1 is 0.018145/0.010085/0.182929/0.093968; balanced accuracy is 0.054214/0.061422/0.249350/0.171974. Soft target metrics remain separate. The human_agreement field is normalized label-vote mass, not per-person agreement; 28 registered classes include one class without TEST support. These are local exclusive-classification derivatives, not native GoEmotions multilabel results.

Macro-F1 averages all registered classes; balanced accuracy averages classes with TEST support. All Banking/CLINC classes have support; MASSIVE has58/60 supported classes, LEDGAR95/100. Banking support is6–20 per class; CLINC1–187. Small class estimates require caution. No threshold or temperature was fitted onTEST.

Banking0.8B/2B predict only5/2 of77 classes; codeAA (position27) receives941/992 predictions. CLINC0.8B/2B predict4/3 of151 classes; O/AA receive853/991 predictions. Both CLINC models never predict OOS (187 gold examples, recall0); the descriptive constant-OOS control is18.7%, compared with0.7%/0.8%. Each cell has1,000 distinct probability and logit vectors. Complete source, prompt, tokenizer, candidate mapping and saved softmax checks found no index or scoring defect explaining these results. Code/position/semantic effects are confounded; no causal bias claim is made. These are fixed-interface baselines, not trained gains.

MASSIVE0.8B/2B accuracy is0.3% each; 2B selects AA/iot_hue_lighton for all1000 inputs despite distinct vectors. MASSIVE4B/9B accuracy45.9%/40.5%; cooking_query receives134/285 predictions with zero TEST gold support. Registered zero-support classes remain included in macro-F1. LEDGAR0.8B/2B/4B accuracy4.6%/6.8%/60.0%; null source definitions remain null. Complete7000-row diagnosis found no source/token/saved-arithmetic defect. MASSIVE released-source overlaps3train/1validation are retained and reported.

## BEV public TEST increment — local protocol, updated 2026-11-03

These four additional fixed-base panels are separate from the historical 38-unit reference matrix. Dataset `avbiswas/bev-decision`, configuration `numeric_temporal`, public `test`: 3,329 rows, 6,518 questions, 24 duplicate requests retained. This is `bev-local-typed-exact-release-test-v1`, not native AnyJev's default 46,320-question task or Tacit readout. Exact counts and report pins for all four sizes are in [REFERENCE-BEV-PUBLIC-INCREMENT-2026-11-03.json](REFERENCE-BEV-PUBLIC-INCREMENT-2026-11-03.json). The preceding [0.8B/2B snapshot](REFERENCE-BEV-PUBLIC-INCREMENT-2026-11-02.json) remains unchanged. Four model sizes do not mean four independent datasets.

| Model | All correct/n | Accuracy | Choice | Noul | Score | Score index MAE | Normalized error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B-Base | 2847/6518 | 43.679% | 1307/3002, 43.538% | 1353/2835, 47.725% | 187/681, 27.460% | 1.157122 | 0.362580 |
| Qwen3.5-2B-Base | 3311/6518 | 50.798% | 1514/3002, 50.433% | 1618/2835, 57.072% | 179/681, 26.285% | 1.352423 | 0.426456 |
| Qwen3.5-4B-Base | 3734/6518 | 57.288% | 1676/3002, 55.829% | 1838/2835, 64.832% | 220/681, 32.305% | 1.217327 | 0.389868 |
| Qwen3.5-9B-Base | 3980/6518 | 61.062% | 1838/3002, 61.226% | 1888/2835, 66.596% | 254/681, 37.298% | 0.963289 | 0.309227 |

All four have 6,518 valid predictions, with score errors over all 681 score questions. The 2B overall accuracy increases by 7.118748 percentage points versus 0.8B, while score accuracy and both ordinal errors worsen. The 4B overall accuracy increases by 6.489721 percentage points versus 2B and 13.608469 versus 0.8B. All three type accuracies improve versus 2B; both ordinal errors improve versus 2B but remain worse than 0.8B. No training gain, decision consistency, significance or candidate eligibility follows.

The 2B report was independently reconstructed by an inherited-model child and again by the parent (6,568 evidence pins verified). The 4B independent inherited-model review reconstructed the complete report, verified 6,561 provenance pins and rebuilt all requests/gold from the original parquet; request/gold bytes match both smaller baselines. Explicit additional Astra confirmation has not produced a review artifact; the earlier 0.8B independent review remains unchanged. Runtime, runner, host and CPU terminal receipts all report exit 0. The retained 4B Docker exited at 2026-11-02 15:57:46 UTC.

4B exact report: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/bev_public_test_4b_20261102_v1/cpu/report.json`, SHA256 `2a399cf5e72c01ef97e007bff711cda776dc11c205c308d98c09fc16cf1c61c0`. Score index MAE is `1.2173274596182084`; normalized error is `0.3898678414096919`, including the full-denominator failure-penalty formulation because failure count is zero. This dated addition preserves the earlier readings and historical 38-unit coverage count.

2026-11-03 additive result: 9B improves overall accuracy by **3.774164 percentage points versus 4B**, 10.263885 versus 2B and 17.382633 versus 0.8B. All three type accuracies improve versus each smaller baseline; its score MAE and normalized error are also lower than each. This does not make the smaller-size ordinal-error series monotonic or establish statistical significance.

The 9B independent inherited-model review exactly reconstructed the complete CPU report, verified 6,563 provenance/lifecycle pins and rebuilt all 3,329 source rows / 6,518 questions from the original parquet. Requests and gold are byte-identical across all four models; all predictions are valid, with zero failures and the same 24 retained duplicate requests. This is an independent result review of the stated scope; the subagent inherits its parent model configuration, and its deployed model identity is not independently verified here. Runner, host and CPU completion evidence agree; the retained Docker exited successfully at 2026-11-02 19:09:53 UTC and resource release was verified. No scientific acceptance or trained-candidate qualification is granted.

9B report: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/bev_public_test_9b_20261102_v1/cpu/report.json`, SHA256 `a8b0e3adc00714e58364c747f21c3a9c59405c1510a224014e1b635ffeb7f8a2`. Exact score MAE: `0.9632892804698973`; normalized error: `0.30922662750856583`, denominator 681. Historical readings and the separate 38-unit coverage count are unchanged.

## BEV default full TEST increment — native full-label, updated 2026-11-04

This is a separate protocol and population from numeric_temporal above: avbiswas/bev-decision default public TEST, 24,386 source rows and 46,320 questions. All four reported model sizes use Transformers full-label fp32, batch1, HF32 off, maximum8192; all44 inputs above4096 and nine semantic duplicate requests are retained. The exact result record is [REFERENCE-BEV-NATIVE-INCREMENT-2026-11-03.json](REFERENCE-BEV-NATIVE-INCREMENT-2026-11-03.json). The 9B row was added after independent recovery review on 2026-11-04.

| Model | Correct/questions | Accuracy | Choice correct/n | Yes/no correct/n | Score exact correct/n | Adaptive |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen3.5-0.8B-Base | 24329/46320 | 52.524% | 9404/18808, 50.000% | 12100/17572, 68.860% | 2825/9940, 28.421% | NOT_EVALUATED |
| Qwen3.5-2B-Base | 26782/46320 | 57.820% | 11139/18808, 59.225% | 12668/17572, 72.092% | 2975/9940, 29.930% | NOT_EVALUATED |
| Qwen3.5-4B-Base | 30552/46320 | 65.959% | 12391/18808, 65.882% | 13992/17572, 79.627% | 4169/9940, 41.942% | NOT_EVALUATED |
| Qwen3.5-9B-Base | 30465/46320 | 65.771% | 12404/18808, 65.951% | 13756/17572, 78.284% | 4305/9940, 43.310% | NOT_EVALUATED |

Every committed record, identity/order, selected fp32 label-logit arithmetic, typed choice and automatic CPU summary was independently reconstructed; maximum arithmetic discrepancy0. Production stores selected label logits, so full-vocabulary finiteness is inference-attested rather than independently replayable from saved full vectors. This is a descriptive fixed-base TEST result, not training benefit, candidate selection or matched reproduction of vLLM top20/H100/Tacit trained weights. Upstream released-run exact revision lineage remains unknown.

Choice accuracy exactly50% was investigated:3,582 predictions are nonzero, and18,799 distinct selected-logit vectors remain across18,808 questions; this is not a constant-zero fallback. Three perfect qid groups (779/779,61/61,60/60) have constant gold and predictions and do not establish discrimination.622 of699 qid groups have fewer than30 observations; these are descriptive flags, not new performance gates. Type, domain and qid strata are NGA additive diagnostics;18 domains do not mean18 independent datasets.

The 2B complete-panel result is independently reconstructed: all46,320records, selected-label operands, identities, ordering and CPU report agree exactly. Its2,453additional correct decisions versus0.8B correspond to5.295769percentage points on this same panel; this is a fixed-base model comparison, not training gain or a significance claim. The 4B result was independently reconstructed with 185,391 checks and zero arithmetic discrepancy; 43 dependency fingerprints were also rechecked by the orchestrator. It adds 3,770 correct decisions / 8.139033 percentage points versus 2B. The 9B complete-panel result is independently reconstructed and accepted for fixed-base TEST reporting. It has 87 fewer correct decisions than 4B (-0.187824 percentage points), a descriptive model-size comparison rather than training gain or significance. Do not derive a gain by subtracting this52.524% from the different6518-question protocol. Existing reference metrics and denominators are unchanged.

Identity correction — 2026-11-04: earlier descriptions equating independent subagents with non-Astra reviewers are withdrawn. Frozen receipts retain their original wording; review scope and evidence, rather than an unverified model label, determine what was accepted.

## BEV counterfactual TEST increment — native full-label, 2026-11-04

Four fixed Qwen3.5 Base models completed the same public `counterfactual_15k/test` population: 2,386 rows and questions, no exclusion or truncation. Protocol: Transformers full-label fp32, batch1, HF32 off, one forward. This is an additional BEV panel, not a new independent source family or an amendment to the historical 36/38 matrix. Exact metrics and artifact pins: [REFERENCE-BEV-COUNTERFACTUAL-INCREMENT-2026-11-04.json](REFERENCE-BEV-COUNTERFACTUAL-INCREMENT-2026-11-04.json).

| Model | Correct / n | Accuracy | Choice | Yes/no | Score |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B-Base | 1229/2386 | 51.508801% | 563/1180 | 499/804 | 167/402 |
| Qwen3.5-2B-Base | 1538/2386 | 64.459346% | 721/1180 | 590/804 | 227/402 |
| Qwen3.5-4B-Base | 2123/2386 | 88.977368% | 997/1180 | 752/804 | 374/402 |
| Qwen3.5-9B-Base | 2173/2386 | 91.072925% | 1039/1180 | 764/804 | 370/402 |

Independent reconstruction verified all 9,544 saved predictions, source/gold joins, selected-logit arithmetic, receipts and retained-container lifecycle; parent rehashed 19,201 unique evidence files. Published summary metrics match exactly. This accepts fixed-baseline result correctness, not named Astra review, candidate selection or training gains. The public data lacks usable pair IDs, so no paired consistency claim follows. Saved records retain selected label logits rather than the whole vocabulary; model forward values are supported by the previously admitted numerical runtime and provenance, not a new model rerun. Different BEV populations/protocols cannot be subtracted to claim improvement.

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

## BEV skills TEST increment — native full-label, 2026-11-04

Two fixed Qwen3.5 Base models completed the same public `skills/test` population: 6,755 source rows, 10,316 questions, 74 duplicate excess requests retained. Independent CPU reconstruction covered every saved selected-logit record and ordered receipt; parent verification covered 41,348 unique evidence pins. These are two additional BEV cells, not new independent datasets or training gains. [Metrics and artifact pins](REFERENCE-BEV-SKILLS-INCREMENT-2026-11-04.json).

| Model | Correct / questions | Hard-label accuracy | Status |
| --- | ---: | ---: | --- |
| Qwen3.5-0.8B-Base | 4960 / 10316 | 48.080651% | Independently reconstructed |
| Qwen3.5-2B-Base | 6224 / 10316 | 60.333463% | Independently reconstructed |

The population includes 1,280 questions with soft target distributions; the registered scorer uses their accompanying hard labels. Soft-target probability metrics remain unevaluated. Score-type accuracy is discrete ordinal-label accuracy, not a regression metric. Compact records retain selected label logits, not full-vocabulary tensors. Named Astra adversarial review is pending; no training-benefit or candidate-TEST acceptance is implied. Prior results and the historical 36/38 reference matrix are unchanged.

## Typed Decisions Qwen TEST increment — single-question v2, 2026-11-04

Two fixed Qwen3.5 Base models completed the same 400 states / 2,000 public TEST decisions. Every saved selected-logit record and source/gold/receipt identity was independently reconstructed; the parent verified 8,075 unique evidence pins. [Exact metrics and source artifacts](REFERENCE-TYPED-QWEN-INCREMENT-2026-11-04.json).

| Model | Correct / decisions | Accuracy | KL(q‖p) | Brier | ECE10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-0.8B-Base | 768/2000 | 38.4% | 0.639049439 | 0.319158819 | 0.208538028 |
| Qwen3.5-2B-Base | 920/2000 | 46.0% | 0.489223254 | 0.247655881 | 0.123971923 |

Accuracy, KL, Brier and ECE10 reproduce publisher formulas, including original gold mass and native predicted normalization and ECE accumulation order. Inference uses one full-label forward per question; it is **not** the publisher five-question endpoint. Formula agreement does not establish inference-protocol equivalence. Overall 2B improves all four descriptive metrics over 0.8B, but ordinal hard accuracy declines from 34.0% to 32.5%; scale effects are not uniform across types. These are fixed-base results, not training gains. No named Astra acceptance or candidate-TEST authority is claimed.

## BEV hard and skills additional TEST cells — 2026-11-04

Full saved-result reconstruction and parent evidence verification accepted three additional fixed-base cells. [Exact counts, type strata and artifact pins](REFERENCE-BEV-HARD-SKILLS-ADDITIONAL-2026-11-04.json). Prior cells are unchanged.

| Panel | Model | Correct / questions | Hard-label accuracy |
| --- | --- | ---: | ---: |
| hard_50k | Qwen3.5-0.8B-Base | 5677 / 14479 | 39.208509% |
| hard_50k | Qwen3.5-2B-Base | 7688 / 14479 | 53.097590% |
| skills | Qwen3.5-4B-Base | 7221 / 10316 | 69.998061% |

The combined five-job review, including previously accepted Typed cells, reconstructed 43,274 saved records; parent verification checked 86,731 unique artifact pins. This does not represent new NPU computation. Skills retains 74 duplicate excess requests and 1,280 soft-label questions evaluated using their hard labels; soft-distribution metrics are now reported in the separately labelled post-inference supplement below. Hard score-type population is only 74 questions, so its strata are descriptive. These are fixed-base scale comparisons, not training gains or paired consistency.

## Typed Decisions four-size matrix completed — 2026-11-04

The additional 4B and 9B cells passed independent full saved-result reconstruction; parent verification checked 8,075 unique pins. [Additional metrics and evidence](REFERENCE-TYPED-QWEN-ADDITIONAL-2026-11-04.json). Each model uses the same 400 states / 2,000 questions, single-question v2 protocol and frozen publisher metric formulas.

| Model | Correct / decisions | Accuracy | KL(q‖p) | Brier | ECE10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-4B-Base | 1114/2000 | 55.7% | 0.404785680 | 0.194924770 | 0.070808215 |
| Qwen3.5-9B-Base | 1170/2000 | 58.5% | 0.308770753 | 0.157799407 | 0.037623090 |

All four Qwen sizes now have accepted results on this panel. Overall accuracy rises and KL/Brier/ECE10 decrease with scale in this fixed comparison; subtype metrics need separate interpretation. This does not establish training gains, paired consistency, native five-question inference-endpoint equivalence, or complete cross-dataset coverage.

## Hard 4B and HelpSteer2 verbosity TEST increment — 2026-11-04

Independent complete saved-result reconstruction accepted hard4B at **8748/14479 = 60.418537%**. HelpSteer2 verbosity uses the separate preregistered local ordinal protocol on 1,000 released TEST rows; it is not Jevify endpoint/scorer equivalence. [Exact metrics and evidence](REFERENCE-HARD4B-HELPSTEER-INCREMENT-2026-11-04.json).

| HelpSteer2 model | Accuracy | Argmax MAE | Expected-index MAE | Normalized RPS |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-0.8B-Base | 16.7% | 1.091 | 0.552943309 | 0.149852795 |
| Qwen3.5-2B-Base | 15.5% | 1.119 | 0.710356389 | 0.150557378 |
| Constant grade2 diagnostic | 61.9% | 0.463 | — | — |

Both models perform worse than the constant-grade diagnostic on accuracy and argmax MAE; predictions concentrate on grade3. The constant is a TEST-population descriptive diagnostic, not a learned held-out result. Full mapping and persisted arithmetic checks found no discrepancy, which does not prove model capability is the sole cause. Dedicated CPU bad-case diagnosis is pending; any subsequent optimization requires separate DEV design and preregistration. No test-driven prompt/threshold change has been applied.

## Hard four-size completion and ordinal TEST increments — 2026-11-04

Hard 9B is accepted at **9701/14479 = 67.000483%**, completing the four-size hard matrix. Four more ordinal cells passed full saved-result reconstruction. [Counts, formulas and artifact pins](REFERENCE-HARD9B-ORDINAL-INCREMENT-2026-11-04.json).

| Panel / model | Accuracy | Argmax MAE | Expected-index MAE | Normalized RPS |
| --- | ---: | ---: | ---: | ---: |
| HelpSteer2 4B | 31.6% | 1.212 | 0.657099273 | 0.134284801 |
| HelpSteer2 9B | 35.0% | 0.966 | 0.597090074 | 0.117272213 |
| STS-B 0.8B | 23.6% | 1.616 | 1.378102318 | 0.210381312 |
| STS-B 2B | 21.6% | 1.620 | 1.049575596 | 0.170985528 |

HelpSteer2 four-size evaluation is complete; every model remains below the descriptive constant-grade2 accuracy61.9% and above its MAE0.463. STS-B constant-grade3 accuracy20.3% / MAE1.322 shows why accuracy alone is insufficient: the small models exceed that accuracy but have worse argmax MAE. STS-B retains its four train/two validation exact-state overlaps. These are local ordinal formulas, not publisher inference/scorer equivalence or learned gains.

## STS-B four-size TEST matrix completed — 2026-11-04

The final 4B and 9B cells passed complete independent saved-result reconstruction (1,000 records each). Publication verification checked 4,082 remote and one local unique evidence-file hash. [Exact metrics and artifact pins](REFERENCE-STSB-COMPLETION-2026-11-04.json). Prior measured values and frozen formulas are unchanged.

| Model | Correct / TEST rows | Accuracy | Argmax MAE | Expected-index MAE | Normalized RPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-4B-Base | 424/1000 | 42.4% | 0.782 | 0.667237347 | 0.094263911 |
| Qwen3.5-9B-Base | 438/1000 | 43.8% | 0.678 | 0.715295479 | 0.093595116 |

Both exceed the descriptive constant-grade3 accuracy20.3% and improve on its MAE1.322. The 9B expected-index MAE is worse than 4B despite better accuracy, argmax MAE and RPS; scale does not improve every metric. All four sizes now have accepted local ordinal TEST results. Four train/two validation exact-state overlaps and one within-TEST repeated state remain in the original population. This is saved selected-logit arithmetic/provenance verification, not independent model-forward reproduction, Jevify endpoint/scorer equivalence, named Astra review or training benefit.

## PAWS released TEST increment — 2026-11-04

Two fixed Qwen3.5 Base cells passed independent full reconstruction of all1,000 saved readouts each;4,075 evidence files were rehashed. [Exact results and evidence](REFERENCE-PAWS-INCREMENT-2026-11-04.json). This is the Praveenrajus/jev-bench released TEST subset with local full-label inference, not verified original upstream TEST lineage or Jevify endpoint equivalence.

| Model | Correct / n | Accuracy | Yes recall (n432) | No recall (n568) |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-0.8B-Base | 684/1000 | 68.4% | 368/432 =85.185185% | 316/568 =55.633803% |
| Qwen3.5-2B-Base | 744/1000 | 74.4% | 201/432 =46.527778% | 543/568 =95.598592% |

Both exceed descriptive always-No accuracy56.8%, but2B's higher total accuracy coexists with substantially lower Yes recall. This is not uniform class-wise improvement, paired consistency, training gain or named Astra acceptance. Per-class counts and output histograms remain in the exact JSON; no cross-task aggregate is introduced.

## PAWS completion and BoolQ small-model TEST — 2026-11-04

Independent full saved-result reconstruction and8,142-file hash verification accepted four more1,000-row cells. [Exact results](REFERENCE-PAWS-BOOLQ-ADDITIONAL-2026-11-04.json). These retain the Jev-bench released-subset/local full-label limits above.

| Panel / model | Accuracy | Yes recall | No recall |
| --- | ---: | ---: | ---: |
| PAWS4B | 826/1000 =82.6% | 339/432 =78.472222% | 487/568 =85.739437% |
| PAWS9B | 825/1000 =82.5% | 358/432 =82.870370% | 467/568 =82.218310% |
| BoolQ0.8B | 676/1000 =67.6% | 599/628 =95.382166% | 77/372 =20.698925% |
| BoolQ2B | 796/1000 =79.6% | 504/628 =80.254777% | 292/372 =78.494624% |

PAWS four sizes are complete;4B/9B differ by one correct answer, which does not establish statistical equivalence. BoolQ0.8B exceeds descriptive always-Yes62.8% by4.8 percentage points but has weak No recall;2B improves total and No recall while reducing Yes recall. Constants are descriptive TEST-population comparators. No training improvement, paired consistency, original hidden BoolQ TEST result or named Astra acceptance is claimed.

## BoolQ four-size completion — 2026-11-04

The final two1,000-row released TEST cells passed full independent saved-result reconstruction;4,076 evidence hashes were rechecked. [Exact results](REFERENCE-BOOLQ-COMPLETION-2026-11-04.json).

| Model | Accuracy | Yes recall (n628) | No recall (n372) |
| --- | ---: | ---: | ---: |
| Qwen3.5-4B-Base | 827/1000 =82.7% | 470/628 =74.840764% | 357/372 =95.967742% |
| Qwen3.5-9B-Base | 862/1000 =86.2% | 503/628 =80.095541% | 359/372 =96.505376% |

All four sizes now have accepted BoolQ local full-label results.9B improves both class recalls versus4B in this fixed comparison; statistical significance and training treatment effects are not established. Released-subset provenance, original hidden-TEST and Jevify endpoint limitations remain unchanged.

## SMS Spam / MNLI released TEST increment — 2026-11-04

Four Qwen3.5 Base sizes, existing local full-label fp32 protocol. All 7,200 predictions were independently reconstructed from source/request/gold, saved selected logits and lifecycle receipts; parent rehashed all 14,662 evidence files. [Exact results and limits](REFERENCE-SMS-MNLI-INCREMENT-2026-11-04.json).

| Panel / metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| SMS accuracy (n=800) | 85.5% | 74.75% | 94.375% | 96.375% |
| SMS spam recall (n=115) | 2/115 | 99/115 | 80/115 | 91/115 |
| MNLI accuracy (n=1000) | 35.9% | 64.2% | 78.5% | 81.2% |

SMS always-ham is 85.625%; MNLI always-entailment is 36.0%, both descriptive TEST-population constants. MNLI0.8B predicts entailment999/1000 with zero neutral/contradiction recall. All1000 selected-logit vectors differ; full mapping and arithmetic reconstruction rules out an aggregate scoring error or duplicated identical output, but does not identify whether checkpoint or prompt causes the collapse. SMS0.8B spam recall is only2/115; aggregate accuracy alone is misleading.

These are Jev-bench derived-release TEST subsets, not established upstream hidden TEST or Jevify endpoint reproduction. SMS retains13 excess duplicates and79/14 exact train/validation matches; MNLI has no exact release overlap. No independent model-forward/full-vocabulary replay, clean training generalization, significance or training gain is claimed. Historical36/38 coverage is unchanged.

## ARC released TEST and BEV skills9B completion — 2026-11-04

Independent source/readout/report/lifecycle reconstruction completed; parent rehashed28,812 evidence files. [Exact results and diagnostics](REFERENCE-ARC-SKILLS-COMPLETION-2026-11-04.json).

| ARC Challenge derived-release TEST | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| Correct /1000 | 571 | 775 | 911 | 935 |
| Accuracy | 57.1% | 77.5% | 91.1% | 93.5% |

ARC has4 three-option,993 four-option and3 five-option questions. Option-position diagnostics are not shared semantic classes. Small perfect strata were independently inspected and remain descriptive. Seven TEST states match release train and two validation, but no full-request overlaps or internal duplicate requests. This is not established original upstream hidden TEST, Jevify endpoint equivalence or a training gain.

BEV skills9B completed **7358/10316 =71.326095%**: choice3167/4463, yes/no3847/5100, score344/753. It adds137 correct answers over4B (+1.328034 percentage points), a descriptive fixed-model comparison. All6755source rows and74semantic duplicate requests retained. The1280soft-target questions are evaluated by attached hard labels only; soft distribution quality remains unmeasured. All62qid slices flagged for small n or exact0/1 were regrouped and checked; one perfect n30 slice has constant gold. These observations do not establish invariance or generalization.

The recent13-panel×4-size subset now has52 accepted results; this does not complete the global model×dataset×protocol Cartesian product. The historical38-unit coverage count remains unchanged.

## StrategyQA and SST5 released TEST increment — 2026-11-04

Twelve additional fixed-base cells independently reconstructed. Parent rehashed11,261 StrategyQA and8,140 SST5 evidence files. [Exact results, class counts and limitations](REFERENCE-STRATEGYQA-SST5-INCREMENT-2026-11-04.json).

| Panel / metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| StrategyQA closed correct/687 | 344 | 407 | 402 | 384 |
| StrategyQA grounded correct/687 | 414 | 557 | 555 | 547 |
| SST5 accuracy (n1000) | 18.2% | 31.5% | 52.3% | 53.0% |
| SST5 argmax index MAE | 1.923 | 1.074 | 0.565 | 0.540 |
| SST5 expected-index MAE | 1.311213 | 0.911756 | 0.612405 | 0.593319 |
| SST5 normalized RPS | 0.261063 | 0.157625 | 0.102780 | 0.099456 |

Grounded inputs yield higher observed StrategyQA accuracy for all four sizes, but this is input conditioning, not training gain, a significance result or paired invariance. Closed performance is not monotonic with size. Both views have333Yes/354No; constant-No354/687 is descriptive. Each has one exact released-train overlap, no validation overlap or internal duplicates.

SST5 0.8B predicts highest level974/1000 times and next-highest26, giving zero recall for the firstthree levels. All1000savedlogitvectors differ; source mapping and independent formulas matched, so this is a real saved-output failure, not an aggregate formula error. Cause requires non-TEST controlled diagnosis. SST5 retains one train-overlapping request. Ordinal metrics use frozen local formulas; no native endpoint or original hidden-TEST equivalence is asserted.

## Yelp5 / HelpSteer helpfulness — accepted fixed-base TEST, 2026-11-04

Parent accepted after independent full reconstruction and additional 8,000-row arithmetic checks; 24,403 evidence/artifact fingerprints rechecked. Each cell uses 1,000 derived-release TEST rows. Models are fixed Qwen3.5 Base; this is not training gain.

| Task / metric | 0.8B | 2B | 4B | 9B |
| --- | ---: | ---: | ---: | ---: |
| yelp5 accuracy | 25.1% | 52.5% | 62.7% | 60.8% |
| yelp5 argmax index MAE | 1.658000 | 0.594000 | 0.410000 | 0.438000 |
| yelp5 expected-index MAE | 1.251373 | 0.529634 | 0.441932 | 0.514208 |
| yelp5 normalized RPS | 0.234082 | 0.085530 | 0.075226 | 0.084412 |
| helpsteer2_helpfulness accuracy | 38.9% | 38.9% | 37.7% | 37.7% |
| helpsteer2_helpfulness argmax index MAE | 1.064000 | 1.074000 | 0.940000 | 0.956000 |
| helpsteer2_helpfulness expected-index MAE | 0.969857 | 0.998699 | 0.960818 | 0.922211 |
| helpsteer2_helpfulness normalized RPS | 0.171084 | 0.175266 | 0.159068 | 0.156607 |

Yelp5 4B exceeds 9B descriptively: accuracy 62.7% versus 60.8%, and lower values for all three ordinal errors. Yelp5 0.8B never predicts the two-star level; its two-star recall is 0/196. All 1,000 saved vectors are distinct; mapping and arithmetic checks passed.

Helpfulness accuracy is 38.9% / 38.9% / 37.7% / 37.7%, below the descriptive constant-highest-level accuracy of 41.8%. The constant middle-high level (index 3) has MAE 0.944; 4B MAE 0.940 is slightly lower, while 9B/0.8B/2B are higher. These constants use this TEST population and are not learned held-out baselines.

Helpfulness 0.8B predicts only levels 3/4 (246/754); the lowest three recalls are zero. 2B has zero recall at levels 1/2; 4B at level 1. Independently verified confusion matrices and 1,000 distinct vectors per flagged cell support observed behavior, without causal attribution to checkpoint versus prompt/readout.

Both panels have zero exact TEST request overlap with this release train/validation and zero internal duplicate excess; original upstream split lineage remains unverified. Ordered levels, denominators and formulas are unchanged. Full-vocabulary vectors were not persisted; this review reconstructs saved selected logits, not fresh model forwards.

Exact counts, formulas, diagnostics and evidence: [REFERENCE-YELP-HELPFULNESS-INCREMENT-2026-11-04.json](REFERENCE-YELP-HELPFULNESS-INCREMENT-2026-11-04.json).

## FEVER supplied-evidence binary TEST — accepted fixed-base results, 2026-11-04

All 4,000 rows were independently reconstructed; the parent rechecked 8,504 evidence fingerprints without mismatch. [Exact results and limitations](REFERENCE-FEVER-INCREMENT-2026-11-04.json).

| Metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| Correct / 1000 | 528 | 859 | 932 | 945 |
| Accuracy | 52.8% | 85.9% | 93.2% | 94.5% |
| Support correct / 502 | 500 | 490 | 456 | 468 |
| Refute correct / 498 | 28 | 369 | 476 | 477 |

0.8B predicts support 970/1000 times; its refute recall is only 28/498 = 5.622490%. Source mapping and saved-logit arithmetic were checked, so the low minority-class recall remains an adverse behavioral finding. Descriptive constant-support accuracy is 50.2%; it is not a trained held-out baseline.

This task supplies gold evidence and excludes NOT ENOUGH INFO. It is **not official FEVER score, retrieval evaluation or three-class accuracy**, nor a publisher-native endpoint reproduction. There are no exact release train/validation request overlaps or internal duplicates; upstream lineage and pretraining disjointness are unestablished. No training gain or significance claim is made.

At this increment, the recent four-size subset reached **76 accepted cells across 19 panels/protocols** (historical milestone; current count above). This does not complete the global model×dataset×protocol Cartesian product; historical 36/38 is a separate irregular registry.

## MMLU positioned released TEST — accepted fixed-base results, 2026-11-04

All 4,000 rows independently reconstructed; parent rechecked 8,385 evidence fingerprints without mismatch. This is a 1,000-row released subset under local positional full-label readout, not original full-MMLU or publisher-native endpoint equivalence.

| Metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| Correct / 1000 | 374 | 527 | 707 | 749 |
| Accuracy | 37.4% | 52.7% | 70.7% | 74.9% |
| Predictions A/B/C/D | 682/105/80/133 | 512/193/156/139 | 224/287/250/239 | 190/283/284/243 |

Physical row 396 (`mmlu/test/4021`) has identical A/D descriptions and published gold D. All four choose A and are counted incorrect under the frozen metric; the row remains in the denominator. Positional diagnostics are not semantic class recalls. Of 57 subject groups, 52 have fewer than 30 samples; all 0%/100% subject results occur in those small groups and are not mastery/generalization evidence.

There are zero full-request overlaps with release train/validation and zero internal duplicate full requests, but one TEST state matches validation with a different question. Upstream split lineage and pretraining disjointness remain unestablished. The earlier synthetic behavioral failures are preserved. No training gain or paired significance claim.

At this increment, the recent four-size subset reached **80 accepted cells across 20 panels/protocols** (historical milestone; current count above); this remains a partial matrix. [Exact results and diagnostics](REFERENCE-MMLU-INCREMENT-2026-11-04.json).

## ChaosNLI / Civil Comments hard and soft TEST — accepted, 2026-11-04

All 14,396 saved readouts were independently reconstructed; parent rehashed 29,536 evidence files without mismatch. Metrics are NGA prospectively specified formulas, not original publisher endpoint/scorer equivalence.

| Panel / metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| chaosnli Accuracy | 46.278924% | 55.597248% | 50.343965% | 59.787367% |
| chaosnli TVD human | 0.374126194 | 0.303080188 | 0.343244182 | 0.289369624 |
| chaosnli Soft Brier vector | 0.331774344 | 0.206601265 | 0.278169589 | 0.192805710 |
| chaosnli Soft CE nats | 1.292310694 | 1.098808273 | 1.272348657 | 1.123949422 |
| chaosnli ECE15 | 0.266674887 | 0.089062904 | 0.261470631 | 0.095945442 |
| civil_comments Accuracy | 92.300000% | 87.300000% | 76.950000% | 82.750000% |
| civil_comments TVD human | 0.279914412 | 0.295926175 | 0.248135100 | 0.192701535 |
| civil_comments Soft Brier vector | 0.176807675 | 0.204694789 | 0.205619339 | 0.142711265 |
| civil_comments Soft CE nats | 0.464435554 | 0.490515605 | 0.464949310 | 0.385201015 |
| civil_comments ECE15 | 0.251565683 | 0.224792749 | 0.027242978 | 0.032746543 |

ChaosNLI n=1599/model; Civil Comments n=2000/model. ChaosNLI 0.8B predicts entailment 1597/1599; neutral/contradiction recalls are zero. Civil 0.8B predicts non-toxic for all 2000, so 92.3% equals the majority constant and toxic recall is 0/154. Toxic recalls for 2B/4B/9B are 33/154, 100/154, 70/154. High total accuracy is not toxic-detection success.

TEST mean-human distributions are descriptive oracle baselines. ChaosNLI TVD baseline=0.316499958; only 2B/9B beat it. Civil TVD baseline=0.140898570; all models are worse. Civil scalar Brier is half the vector value; do not mix the two conventions.

Civil has 3 exact TEST requests overlapping release train, none with validation. ChaosNLI train/validation are not published; overlap is unassessed, not zero. No internal duplicate full requests. Upstream lineage/pretraining disjointness unestablished. No training gain, original ChaosNLI JS, Civil AUROC, AURC, consistency or unknown-handling claim.

At this increment, four-size coverage reached **88 accepted cells across 22 panels/protocols** (historical milestone; current count above), still not global NxM. [Exact metrics, bins and diagnostics](REFERENCE-SOFTLABEL-INCREMENT-2026-11-04.json).

## Measuring Hate Speech released TEST — accepted, 2026-11-04

Four 1,000-item cells were independently reconstructed with hard, soft-label and ordinal metrics; parent checked 8,620 evidence and delivery pins without mismatch. This is the Jev-bench three-level derivative, not the original continuous-scale publisher endpoint.

| Metric | Qwen3.5-0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| Accuracy | 26.5% | 27.9% | 44.9% | 29.7% |
| Argmax MAE | 1.421000000 | 1.393000000 | 0.898000000 | 0.812000000 |
| Expected MAE | 1.274756431 | 1.175263448 | 0.883842974 | 0.856993902 |
| TVD human | 0.608189135 | 0.569669295 | 0.477129528 | 0.549525650 |
| Soft Brier vector | 0.848328821 | 0.718086091 | 0.514462330 | 0.578949954 |
| Soft CE nats | 1.580016790 | 1.466452244 | 1.310475258 | 1.338569811 |
| Hard RPS normalized | 0.517458684 | 0.451768063 | 0.318639757 | 0.281880351 |
| Soft RPS normalized | 0.413067450 | 0.347626743 | 0.223327055 | 0.192792267 |
| ECE15 | 0.575925317 | 0.500561566 | 0.255161377 | 0.303460712 |

All four hard accuracies are below the descriptive constant no_hate 68.6%, and argmax MAE is worse than its 0.579. The 0.8B model predicts hate for all 1,000 items; 2B never predicts borderline. All saved score vectors, class ordering and zero/one recalls were checked. 4B leads accuracy/TVD; 9B leads MAE/RPS, so model-size benefit depends on the target metric. TEST mean-human controls are oracle diagnostics, not deployable baselines. Release train/validation exact request overlaps are zero; upstream and pretraining disjointness remain unknown. No training gain is claimed.

[Exact results, confusion matrices and limitations](REFERENCE-MEASURING-INCREMENT-2026-11-04.json).

## BEV skills soft targets — descriptive supplement, 2026-11-04

This is a post-inference descriptive supplement, not retrospective preregistration or a selection signal. All41,264 existing saved records were independently audited; each model has exactly1,280 source soft targets (choice280, Noul659, score341). Parent rehashed82,579 evidence files. No NPU inference was repeated, hard-label metrics changed or inference cells added.

| Type / metric | 0.8B Base | 2B Base | 4B Base | 9B Base |
| --- | ---: | ---: | ---: | ---: |
| choice TVD | 0.588671451 | 0.374661008 | 0.354847645 | 0.381284810 |
| choice Soft Brier vector | 0.513868496 | 0.276242487 | 0.280899689 | 0.304140470 |
| choice Soft CE nats | 1.901516824 | 1.397824523 | 1.480636981 | 1.486961149 |
| noul TVD | 0.262084125 | 0.243557489 | 0.184752505 | 0.174146939 |
| noul Soft Brier vector | 0.174980548 | 0.163492967 | 0.135013715 | 0.124743900 |
| noul Soft CE nats | 0.619612490 | 0.604589577 | 0.592360390 | 0.564888551 |
| noul Soft Brier scalar | 0.087490274 | 0.081746483 | 0.067506858 | 0.062371950 |
| score TVD | 0.592788632 | 0.571100856 | 0.462679719 | 0.469017145 |
| score Soft Brier vector | 0.551540409 | 0.582594084 | 0.414799388 | 0.391320995 |
| score Soft CE nats | 1.618246304 | 1.584629303 | 1.354282549 | 1.288605623 |
| score Soft RPS normalized | 0.231233146 | 0.229331544 | 0.132425493 | 0.117335822 |

Means are question-weighted within type; no pooled cross-type headline. Source targets are not renormalized (maximum sum deviation about1e-6). Noul scalar and vector Brier are separately named; score RPS divides cumulative squared errors by K−1. Choice4B→9B hard accuracy improves while TVD/Brier/CE worsen; score9B improves Brier/CE/RPS but worsens TVD. Larger models do not improve every metric monotonically.

0.8B predicts No on650/659 soft Noul questions and index0 on226/280 soft choice questions. All reconstructed probability vectors are distinct within each type/model; constant-index strata are retained and diagnosed, without assigning a semantic cause. Original74 duplicate full-panel requests remain. No training gain, significance, decision consistency or publisher-native probability endpoint claim follows.

[Exact results, formulas, strata and diagnostics](REFERENCE-SKILLS-SOFT-SUPPLEMENT-2026-11-04.json).

## Qwen3.5-0.8B adapted Kev public TEST (2026-11-05)

Independent scoped scientific review and parent input verification accepted these fixed-base results. [Exact metrics, controls, native context and limitations](KEV-FIXED-BASE-TEST-2026-11-05.json).

| Task / population | Correct / n | Accuracy | Brier | Exact logit NLL | ECE10 | Observational changed / pairs | Both correct / pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| documents-v1 full | 606/936 | 64.743590% | 0.552300412 | 1.202589362 | 0.162389881 | 301/395 | 152/395 |
| devtools-v1 full | 467/1073 | 43.522833% | 0.676046829 | 1.178862904 | 0.200511448 | 12/454 | 1/454 |

All 748 devtools boolean predictions are false. Full1073 preserves duplicate source occurrences682/744; the separately frozen release1071 mask yields465/1071 and does not replace the454pairs. Native Kev reports documents936 at85.149573% and devtools1071 at63.678805%; its trained weights, pointer head, rendering, label order and T=2.3510958125672174 differ. These contextual numbers do not establish endpoint equivalence or a training effect. Native TEST vectors and NLL are unavailable in the reviewed evidence.

Pairs are observational changed-input/changed-label pairs, not invariance tests or minimal causal interventions. Supplemental controls and support strata are descriptive; TEST-majority is a label-informed oracle. One-hot controls have infinite mathematical NLL; probability-only clipped NLL floors p at1e-9 and is reported separately in the artifact. Uniform hard ties use the first index. Zero-support recalls are undefined. Saved candidate logits cannot independently replay original full-vocabulary arithmetic. All mandatory scope limits accompany the machine-readable artifact.
