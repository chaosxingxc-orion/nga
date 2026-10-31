# Current Jev experiment conclusions

Updated: 2026-10-31  
Authority: this file is the current remote collaboration entry. Detailed run procedures, receipts, container logs and intermediate reviews remain local under `experiments/` and CephFS. The remote wiki keeps only conclusions and the information needed for coordination.

## Current position

D1 reference reporting is closed for the registered test matrix: 36 of 38 model-by-dataset combinations have results; Open-Jev-2B×JEVal and Open-Jev-9B×JEVal remain `blocked/null`. Test metrics are preserved by task formula, temperature, hard/soft target and effective denominator. Formal Jev training has not started. The three-step Qwen3.5-0.8B NPU preflight proves only the training path and guarded resource handoff; it is not a training result or a test-set result.

The engineering constraints are fixed: NPU work consumes a per-chip FIFO queue; CPU scoring, independent checks, baseline locking, Astra review and report refresh run asynchronously in an ordered lane. The controller has regression tests, but a production queue and ready manifest are not deployed, so current continuous NPU saturation must not be claimed.

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

The numbers below come from the frozen test matrix [`REFERENCE-BASELINE-MATRIX-2026-10-31.json`](../experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json), SHA256 `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`. Percentages are accuracy; other values retain their native scale.

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

### NxM direct-readout baseline

D1 remains the current 38-cell reference scope; it is not expanded. Internal experiments will build a separate NxM product: N model sizes (first Qwen3.5-0.8B, then 2B, 4B and 9B) × M frozen tasks (Kev decision/transfer, Typed, JEVal and later gap datasets). Every cell uses the same harness, test lock, paired decision-level metrics and resource evidence; missing cells are `blocked`, never zero.

Start with Qwen3.5-0.8B K0 untuned readout, then K1 LoRA. Seeds 2 and 3 are registered before any result is read. K1 dev gates and test lock are in [`R3-TRAINING-WAVE-PREREG-2026-10-31.md`](../experiments/R3-TRAINING-WAVE-PREREG-2026-10-31.md). K2 option-restricted loss is the fixed challenger. K4/RL and real-business integration are not started early.

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

Remote collaboration should use this file and the current pointer in `experiments/REFERENCE-BASELINE-LATEST.md`. Historical experiment entries and raw review material are archival lookup only.
