# Current Jev experiment conclusions

Updated: 2026-11-02
Authority: this file is the current remote collaboration entry. Detailed run procedures, receipts, container logs and intermediate reviews remain in the local dated archive and CephFS. The remote wiki keeps only conclusions and the information needed for coordination.

## Current position

D1 reference reporting is closed for the registered test matrix: 36 of 38 model-by-dataset combinations have results; Open-Jev-2B×JEVal and Open-Jev-9B×JEVal remain `blocked/null`. Test metrics are preserved by task formula, temperature, hard/soft target and effective denominator. Formal Jev training has not started. The three-step Qwen3.5-0.8B NPU preflight proves only the training path and guarded resource handoff; it is not a training result or a test-set result.

The engineering constraints are fixed: NPU work consumes a per-chip FIFO queue; CPU scoring, independent checks, baseline locking, Astra review and report refresh run asynchronously in an ordered lane. The controller has regression tests, but a production queue and ready manifest are not deployed, so current continuous NPU saturation must not be claimed.

## Coverage correction — 2026-11-02

The current D1 matrix was too narrow for a broad Jev capability claim. Its 38 model-by-dataset units (36 scored and 2 blocked) remain frozen, but they are concentrated in a few source families. The repository inventory contains 24 directories, yet that count includes version projections, result packages, overlapping sources and different modalities.

The expansion register now distinguishes approximately 16–17 independent source/task families and more than 50 native test/eval panels. The first priority is text-compatible reference evaluation: `Praveenrajus/jev-bench` (22 source panels), canonical `Hanno-Labs/decision-bench` (43 task IDs, 27 families, 28 domains), the independent `akhilaaa3/decision-bench` medium/hard panels, Eikos, Korean JEV, Respan Behavior, DecisionPivot and DecisionRobust text. Complex/spatial decisions and guardrail/safety follow as separate diagnostic families.

This expansion does not authorize inference yet. The latest metadata audit has four new entries, all `needs_review`, with zero `ready_for_inference`; no candidate TEST rows were read. Jev-bench has confirmed source-name and release-hash correspondence with frozen Nimble panels for MASSIVE, PAWS and Civil Comments, so item identity must be audited before those panels can support independent generalization claims. Canonical versus legacy DecisionBench remain separate sources, and state-macro, question-weighted, hard/soft-label, calibration and paired robustness statistics remain separate tables.

DecisionRobust image and other multimodal collections will use a separate matrix. WebJev and OneJev currently have no public TEST, Imajev remains blocked by its release gates, and `btzsc` remains a boundary classification comparison until its typed-decision schema is proven. Public collections still do not cover business-authored rules, Chinese business rules, unknown/fallback, evidence and audit state, equivalence classes or end-to-end cost per correct result; those require frozen internal datasets later.

The detailed scope and execution order are in [`proposal/16-dataset-coverage-expansion-v4-status-2026-11-02.md`](../proposal/16-dataset-coverage-expansion-v4-status-2026-11-02.md). The frozen D1 values in this page and `experiments/REFERENCE-BASELINE-LATEST.md` are unchanged.

Resource correction — 2026-11-02: a local Docker inspection briefly reported the six allocated receipt IDs as missing. That observation was against the wrong Docker daemon. A direct inspection on host 175 resolves all six immutable receipt IDs to running containers; chips 0, 1, 4, 5, 6 and 7 remain allocated, and chips 2 and 3 are the only free chips. No release or allocation edit was made. Formal preparation must use a fresh allocation snapshot and the resource adapter claim transaction.

Engineering correction — 2026-11-02: the formal prepare/launcher pair now accepts an explicit two-chip seed binding, validates chip IDs against the eight-device range, and rejects a seed/chip mismatch. The launcher also disables Torch backend autoload before importing the CPU-only checker. The change is committed as `4f57092`; focused regression tests pass. A v11 CPU preparation attempt was stopped by the existing evidence consumer because the selected legacy training-evidence pack is not compatible with the newer Instruct/Base evidence closure; no NPU activation or TEST read occurred. A subsequent container attempt exposed that the 175 workspace snapshot was stale and incomplete, so the preparation has not yet received an exact-plan Astra review. The next action is to rerun the CPU-only preparation from a complete, hash-pinned source snapshot, then obtain a fresh independent review.

## Dimension 1 — how Jev-class gains are obtained

This is our literature grouping, not a claim that each paper established a causal mechanism. A work can belong to more than one group.

| Group | Examples | Change | What we can conclude |
| --- | --- | --- | --- |
| Frozen parameters, changed driving/readout | LLM-as-Jev, Mapika decider, AnyJev, Runoff, JevCascade, RSAJEV, parts of Releasing the Inner Jev | Candidate presentation, logit/probability normalization, temperature, rotation debiasing, menu restriction, multiple readouts or prototype memory | Readout and harness changes can produce gains; they are not model-training gains |
| Structural model changes | Block-causal readout, Prism-1, SanSi, LEV, NumericJev, NIOCIS, and proposed branch/recurrence variants | Branch isolation, position independence, recurrence depth, candidate trees or node conditioning | A structural gain needs a same-task, same-parameter direct-readout control; branch isolation on the Qwen3.5 hybrid backbone is still an engineering blocker |
| Task and training-data design | Kev, Tev1, Nimble, SecJev, Chinese Decision, DKnown-Jev, Open-Jev | Decision format, candidate sets, domain tasks, contrast pairs or scenario weighting, followed by SFT/LoRA | Data distribution can improve in-task performance; it does not establish general reasoning or business benefit |
| Learning-method design | Nimble one-fact contrast, PACT paired calibration, ordinal/proper-scoring terms, reasoning-to-readout distillation, RLCD, SHIFT-JEV KL plus temperature, scheduling RL | Supervision, loss, distillation or policy optimization | Compare each method with a same-data, same-backbone CE/LoRA baseline; isolated paper numbers do not establish the mechanism |

The most stable evidence is that frozen readout and post-processing can yield engineering gains, task data can improve in-domain accuracy, and evidence for changing the learning objective is less consistent. The survey also finds that untuned readout reaches roughly 76%–97% of tuned accuracy across the cited scale range. Our first training question is therefore whether task training improves and stabilizes readout on held-out task families.

## Dimension 2 — tasks, published metrics and reference results

The numbers below come from the frozen test matrix `experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json`, SHA256 `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`. Percentages are accuracy; other values retain their native scale.

### Kev native test sets

| Dataset (n) | Kev-0.8B | Kev-4B | Kev-9B |
| --- | ---: | ---: | ---: |
| decision-v7 clean (1200) | 83.750% | 86.500% | 87.250% |
| transfer-v4 clean (656) | 69.665% | 83.841% | 85.213% |
| hard-v1 clean (1088) | 66.636% | 80.331% | 83.456% |
| documents-v1 clean (936) | 85.150% | 90.278% | 89.957% |
| devtools-v1 full (1073) | 63.653% | 75.582% | 79.124% |
| devtools-v1 release (1071) | 63.679% | 75.630% | 79.178% |

Published/alignment metrics are question-weighted hard accuracy, summed one-hot multiclass Brier, top-confidence ECE10 and NLL. Native temperatures are 2.3510958126, 2.4060500722 and 2.1936499594 for 0.8B, 4B and 9B. Raw T=1 is a separate protocol; its probability metrics are not pooled with native-temperature values.

### Nimble native test sets

Nimble has 1,884 test items across seven original subsets and uses native T=1. It has no single Kev-equivalent task definition, so no cross-subset total is reported.

| Subset (n) | Accuracy | Native additional metrics |
| --- | ---: | --- |
| MASSIVE en-US (350) | 86.857% | Brier 0.215612; ECE10 0.069903; NLL 0.566445 |
| MASSIVE de-DE (350) | 84.000% | Brier 0.256619; ECE10 0.081899; NLL 0.664881 |
| PAWS (250) | 82.800% | Brier 0.279648; binary Brier 0.139824; ECE10 0.100160 |
| Civil Comments (300) | 70.000% | Brier 0.413404; binary Brier 0.206702; ECE10 0.135851 |
| Aegis2 (250) | 81.600% | Brier 0.289384; binary Brier 0.144692; ECE10 0.098642 |
| SummEval relevance (240) | 48.750% | Brier 0.676895; score MAE 0.695520; ECE10 0.090175 |
| SummEval consistency (144) | 75.000% | Brier 0.419423; score MAE 0.567382; ECE10 0.171725 |

One-hot multiclass Brier, Noul binary Brier, expected-score MAE, JSD and TV remain separate because their targets and denominators differ.

### Typed Decisions common test

The common test contains 400 states and 2,000 questions. It compares readouts across models and is not a reproduction of each model's own test suite.

| Model | Serving accuracy | Serving KL | Serving Brier | Serving ECE10 | Raw T=1 accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | 45.950% | 0.349523 | 0.195493 | 0.045770 | 45.950% |
| Kev-4B | 66.450% | 0.223109 | 0.124565 | 0.089534 | 66.450% |
| Kev-9B | 68.050% | 0.213790 | 0.116321 | 0.064928 | 68.050% |
| Nimble-9B (T=1) | 65.100% | 0.706028 | 0.254995 | 0.172864 | 65.100% |
| Open-Jev-2B | 58.250% | 0.410911 | 0.193817 | 0.081003 | 58.250% |
| Open-Jev-9B | 67.800% | 0.369436 | 0.147618 | 0.058202 | 67.800% |

### Open-Jev original release-v2 test

The test has 10,532 rows: 10,046 one-hot hard rows and 486 soft rows. Hard accuracy uses only one-hot rows; expected accuracy, NLL, Brier, expected Brier and ECE15 use all rows.

| Model | Serving hard accuracy | Serving expected accuracy | Serving NLL | Serving Brier | Raw T=1 hard accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Open-Jev-2B | 94.635% | 91.877% | 0.195622 | 0.076288 | 94.635% |
| Open-Jev-9B | 97.511% | 94.687% | 0.130801 | 0.039047 | 97.511% |

### Why published statistics are listed separately

- Native temperature and raw T=1 are different readout protocols. Accuracy can match while probability metrics change.
- Hard accuracy uses one-hot targets; expected/soft accuracy uses a target distribution.
- Kev Brier, Nimble Noul binary Brier and score MAE, Typed `KL(q||p)`, and Open-Jev expected Brier are different formulas.
- JEVal keeps valid, overlength, unsupported, classification and score denominators separate. Open-Jev×JEVal remains `blocked/null` and is not zero-filled.
- A model's own test, Typed common test, JEVal and original Open-Jev test are different tasks. Comparisons require the same data and protocol.

## Dimension 3 — business requirements and coverage

These are capability requirements, not production claims. Existing public tasks carry only part of them.

| Requirement | Existing carrier | Gap |
| --- | --- | --- |
| Candidate membership and type correctness | Kev, Nimble, Typed, Open-Jev | Type-correct semantic errors need paired tests |
| Calibration and risk ranking | Typed, Kev, Nimble, Open-Jev, JEVal, Sys1Cal | Broad coverage, but ECE/KL/Brier formulas differ |
| Invariance under equivalent wording | Typed paraphrase/common tasks, ordering and adversarial tests | No unified business-equivalence class or primary metric |
| Fallback, abstain and unknown | JEVal, PFR, arithmetic refusal, Sys1Cal | Partial coverage; unknown is not a common structural output |
| Selective escalation and self-knowledge | JEVal and selective-prediction studies | No cross-domain test of error-source identification |
| Probability axioms and repeated judgments | Probability axiom battery and Probability Contracts | Small scale; no n-way decomposition protocol |
| Rules written by business staff | No qualifying public task; moderation rule/precedent studies are closest | Author identity, editable versions and definition quality are absent |
| Auditability | No public benchmark gives a model-level verdict | Needs task graph, evidence state, receipt and harness definitions |
| Cost/latency per correct result | Scattered latency, caching and cascade reports | No common cost-per-correct protocol |
| Chinese business rules and numeric/date decisions | Existing Chinese tasks and Kev date supplement only partially apply | No business-rule Chinese set or matched numeric-route comparison |

The main missing artifacts are business-authored rules, equivalence classes, unknown/fallback, auditable intermediate state, joint cost/correctness evaluation, and Chinese business/numeric tasks. These must become frozen datasets and metrics before training claims are made.

## Dimension 4 — our experiment route

### Dataset coverage expansion (2026-11-01)

The first public-evaluation contract covered six task families and 14 evaluation cells. That is too narrow for a broad Jev capability claim. The local inventory contains 24 directories, but this count includes version projections, result packages, overlapping sources and different modalities; it is not a count of independent datasets. The next coverage milestone expands the candidate task axis to 12 families in three batches: eight direct-test families (the existing six plus complex deterministic decisions and spatial decisions), three boundary/migration families (safety/guardrail, multilingual/behavior and web/action), and one separate multimodal family (vision/video typed decisions). The first metadata audit produced 16 new contract cells: 12 remain `needs_review` and 4 are `blocked`; none is authorized for inference. WebJev and OneJev have no native TEST, and Imajev has hidden labels plus failed release gates. No new candidate TEST samples have been read and no new inference or training has been authorized by this planning update. The detailed scope is in [`proposal/13-dataset-coverage-expansion-v2-2026-11-01.md`](../proposal/13-dataset-coverage-expansion-v2-2026-11-01.md).

Coverage feedback revision (2026-11-02): the 12-family candidate plan was still too compressed. The next admission matrix expands to approximately 16–17 source/task families and 50+ native test panels, adding Jev-bench (22 native test configs), canonical and legacy DecisionBench as separate sources, and DecisionRobust image; existing Eikos heldout, Korean JEV, Respan Behavior, and DecisionRobust text candidates are promoted to separately scored native panels. Each panel remains split by source, task, formula, denominator, target and pairing; this does not amend the frozen 38-cell D1 reference matrix. The v3 plan is in [`proposal/15-dataset-coverage-expansion-v3-2026-11-02.md`](../proposal/15-dataset-coverage-expansion-v3-2026-11-02.md). Metadata-only review has authorized no new inference.

The first v3 metadata audit is complete: four newly added entries are all `needs_review` (zero `ready_for_inference`, zero `blocked`). Jev-bench has confirmed source-name and release-hash correspondence with frozen Nimble panels (`massive`, `paws`, `civil_comments`), although its released TEST counts differ from the frozen subsamples; exact item identity still needs checking before independent generalization claims. Canonical DecisionBench, legacy DecisionBench and DecisionRobust image still require metric, source, input-interface and pairing reviews. No candidate TEST rows were read and no new inference was authorized.

The engineering queue also needs a separate admission note. A chip-3 Instruct-K0 DEV successor has `EXIT=0`, `RELEASE` and `SUPERVISOR_DONE`, but its precheck remains `PENDING_ROOT_REVIEW` and its scientific acceptance is false. It is retained as a possible successor input, not as a published result. The latest watchdog snapshot reported no queued admissible successor and marked the NPU as free; the retained release snapshot specifically lists chips 1 and 3 as free. Historical stalled entries do not count as active work. The next safe action is CPU provenance/precheck review, followed by FIFO activation only after an admissible successor is signed.

Resource snapshot revision (2026-11-02): the guarded resource adapter has since released chip 2 as well as chip 3. The authoritative allocation file now lists chips 2 and 3 as free; chips 0, 1, 4, 5, 6 and 7 remain owned by existing engineering runs. This is recorded in local `.local/reports/resource-and-admission-snapshot-20261102.json`. No manual allocation edit was made. Formal K1 v8 remains `NONAUTHORIZING_RESOURCE_BLOCKED`, and the four new dataset panels remain `ready_for_inference=0`, so neither free chip is used for unapproved TEST work.

The CPU precheck repair found a real version-binding error: the previous source-verified v2 bundle was for `Qwen3.5-0.8B-Base`, while the chip-3 report is Instruct. The current validator correctly rejected that bundle. A new, separately owned v2 bundle for the Instruct report now passes the same pinned validator with exit 0 and `test_read=false`; it is accepted only as scoped CPU precheck evidence. Formal preparation, exact-plan review and activation remain open.

A new formal K1 preparation generation is now drafted at `formal_k1_preparation_20261102_v8`. It binds the corrected Instruct v2 precheck and records seed2/seed3, but remains `NONAUTHORIZING_RESOURCE_BLOCKED`: CHIP-ALLOCATION currently shows chip1 owned by the formal DEV run and chip4 owned by the 4B engineering DEV run. No resource claim, NPU activation, training launch or TEST read was made. The draft awaits an exact-plan Astra review and a later live release/claim transaction.

The bounded exact-plan review then returned `CHANGES_REQUIRED`: v8 has a stale allocation hash, names chips 1/4 although the live adapter now lists chips 2/3 free, omits the repaired C02 receipt binding, and lacks a complete exact training/recovery closure. A new preparation generation and a fresh independent review are required before any activation.

### NxM direct-readout baseline

D1 remains the current 38-cell reference scope; it is not expanded. Internal experiments will build a separate NxM product: N model sizes (first Qwen3.5-0.8B, then 2B, 4B and 9B) × M frozen tasks (Kev decision/transfer, Typed, JEVal and later gap datasets). Every cell uses the same harness, test lock, paired decision-level metrics and resource evidence; missing cells are `blocked`, never zero.

Start with Qwen3.5-0.8B K0 untuned readout, then K1 LoRA. Seeds 2 and 3 are registered before any result is read. K1 dev gates and test lock are in `R3 training preregistration (local archive)`. K2 option-restricted loss is the fixed challenger. K4/RL and real-business integration are not started early.

### Open learning/optimization methods and engineering base

Use same-backbone, same-data, same-test-lock CE/LoRA as the first baseline. Then add one factor at a time: one-fact contrast data, option-restricted loss, ordinal/proper-scoring terms, temperature/prior calibration, distillation and menu optimization. Record per-chip throughput, memory, recovery, paired test gain and calibration change. The preflight passed three steps; formal training still requires a frozen code snapshot, real claim/release adapter, detached resumable containers and a throughput window of at least ten warmup-excluded steps over at least 60 seconds.

### Business-gap datasets

Turn the gaps into frozen tasks: business-authored rules, equivalent rewrites, unknown/fallback, evidence state and audit receipts, Chinese business rules, numeric/date intervals, and cost/escalation decisions. Each set needs train/dev/test, rule-family holdout, paired equivalence, typed candidates and explicit denominators. First report direct-readout test performance, then decide whether training is warranted. Real business samples and production integration remain out of scope.

### Reinforcement learning and usable baselines

RL is conditional. First establish SFT/LoRA, proper scoring, calibration and gap-dataset baselines. Start RL only when the reward depends on an auditable intermediate object or a scheduling decision:

1. readout-side RL against CE/proper-scoring to test whether a single-pass readout gains anything;
2. scheduling RL against a model-free deterministic controller, reporting cost, coverage and correctness together;
3. decomposition RL only after intermediate-state tasks pass, with a KL anchor, a gold holdout and reward-gaming checks.

Every RL result uses the same test split, decision-level paired protocol and cost definition as its baseline. A higher reward is not a business benefit claim.

## Coordination status and next milestone

- **Done:** D1 reference matrix and latest cumulative report; E39 legacy Kev CPU re-audit; bounded E40/E41 Open-Jev engineering diagnostics and guarded release; Q-host CPU contract; R3 three-step training preflight; asynchronous queue CPU regression tests.
- **Open:** Open-Jev×JEVal numeric/memory admission; production FIFO adapter, ready manifest and watchdog deployment; formal K1 seed 2/3 training; post-training test-lock evaluation; business-gap datasets; RL baseline.
- **Next order:** freeze the training code snapshot → complete the efficiency-window validation while the NPU queue keeps consuming work → launch K1 seeds 2/3 → score dev asynchronously and select → write `FINAL.json` → read test once → refresh this file and a new cumulative report.

Remote collaboration should use this file. Historical experiment entries, raw reviews and milestone reports are local archival lookup only; they are intentionally absent from the remote wiki.
