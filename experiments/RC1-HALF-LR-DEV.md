# RC1 0.8B half-learning-rate DEV experiment

Prospective protocol frozen 2026-11-06 before any successor model run. Implementation and exact launch bindings remain pending independent review; this document does not claim execution readiness. Release remains engineering-base-rc1, image4726. No change to the ongoing twelve-role TEST campaign or its claims.

## Question and scientific scope

Does halving the fixed K1 training learning-rate schedule improve 0.8B transfer probability reliability while retaining discrimination? Accepted DEV identifies the symptoms (mean transfer NLL 1.017976917 versus own Base 1.016289396; ECE10 0.190486673 versus 0.139335074), not an overtraining mechanism. This is an exploratory follow-up on known DEV, not an unseen holdout or causal mechanism test.

Maps to defect5 reliability, defect16 candidate probabilities and defect12 measurement prerequisite. Gold lookup can optimize accuracy/NLL/Brier; constant confidence can improve ECE while ignoring input; zero adaptation can erase learning. Discrimination counterparts are clean correctness, source retention, paired changes, input controls and NOTA both-sides-right. Permutation consistency always includes both-correct and exclusions.

## Fixed training and comparison

Two fresh runs from accepted Qwen3.5-0.8B Base, seeds2/3, one chip each. Existing decision-v7 TRAIN15,576, two epochs, terminal3116, same K1 choice-only/NOTA augmentation. LoRA r16/alpha32/dropout0.05, AdamW weight_decay0.01, clipping1, OneCycleLR pct_start0.1, ref kernel/nonreentrant gradient checkpointing, max_len4096, micro_tokens12000, batch10 base questions.

Only scientific change: peak lr1e-4 → 5e-5, including the corresponding OneCycle initial/final rates. No early stopping, checkpoint sweep, baseline-terminal warm start, seed replacement or automatic tuning ladder. Interrupted runs may resume only their exact owned successor configuration/checkpoint; recipe and identity must distinguish learning rate. The existing baseline default path stays unchanged.

Each successor seed compares against its own accepted K1 terminal3116 seed, reusing saved baseline DEV vectors and publication receipts. Own Base remains context. Do not reacquire completed baselines. Candidate identity: adapter `k1-family-h1-lr5e-5-v2`, recipe `k1-base-0.8b-3116-lr5e-5-v2`; exact reviewed source/config/runtime bindings will be attached before launch.

## Fixed populations and measurements

Use existing decision DEV1264, transfer DEV656 and calibration1148, including their frozen variants and drop/blank controls. TRAIN SHA256 `5ddc8e94f3e0af1c8abdb887ed77c1e8813879efcc428edc6d4ea0bed537daf6`; accepted split/variant and baseline bindings are reused from the recorded small matched DEV evidence. No newly generated split or variant. No successor TEST access; neither pending TEST nor later TEST outcomes may choose this experiment's configuration, seeds, checkpoint or thresholds.

Unchanged full Track K continuation instrument: FP32/rightpad/HF32off, padded-token budget16384, all candidates and original ordering, no truncation or length normalization change. Raw-score first argmax and R0 tie-as-incorrect separately. T=1 stable binary64 probabilities, unclipped NLL, candidate-sum Brier, fixed-bin ECE10 with raw-score correctness. Operator tau fit only on calibration1148 with existing grid/tie/fallback rules; transfer default0.5. Report all source/type strata, exact/near ties, constant/uniform/drop/blank, permutation flips plus discrimination and exclusions, NOTA present/absent and both-right. Accuracy is not consistency.

Pair by identical ordered questions/parents and seed; report wins/losses/both-right/both-wrong and fixed two-seed same-question means. No probability ensemble, doubled denominator, DEV confidence interval or significance claim.

## Prospective decision criteria

All following criteria are conjunctive. They define this bounded exploratory decision only, not retrospective acceptance of the original DEV experiment or a stage gate.

1. Against the corresponding terminal3116 K1 seed, fixed two-seed mean transfer NLL delta <= -0.02 nats/question AND mean ECE10 delta <= -0.01 absolute; each seed NLL/ECE delta <= 0.

2. Mean transfer candidate-sum Brier delta <= 0; each seed on each clean suite raw and R0 accuracy delta >= -0.01 (one percentage point), checked by exact rational counts.

3. For each seed, PAWS/emotion/SciQ correct count >= its corresponding K1 count (48/39/72 for seed2, 42/42/72 for seed3), each n80. Report Base counts separately without treating restoration as observed.

4. For each seed and both suites, clean raw/R0 accuracy exceeds each retained constant/uniform/drop/blank control and NOTA both-right counts do not decrease versus matched K1. Preserve permutation discrimination/exclusions; zero flips is no success criterion.

5. Both seeds complete exact terminal3116 and all registered DEV panels; any incomplete lane is unavailable, no replacement. Failure of any conjunct is not supported by this bounded DEV experiment; no tuning ladder follows automatically.

Any failed conjunct means the stated bounded improvement is unsupported. Missing output remains unavailable. Publish adverse results; do not use outcomes to relax criteria. Positive evidence does not prove generalization beyond these DEV populations or an overtraining mechanism.

## Execution and efficiency

Finish CPU configuration/source/entrypoint preparation before resource claim. Reuse accepted image/model/data receipts; check only changed bindings and live ownership. Detached retained containers, persistent Ceph logs/heartbeat/terminal and exact relaunch, checkpoint-level resume. NPU execution releases before CPU comparison/review/publication; unrelated ready work does not wait for these reports. Measure training and inference separately, per-chip throughput with chip count and reserved memory. Candidate runtime costs remain unmeasured.

Independent review must accept the concrete LR/config/checkpoint/publication route and launch bindings before dispatch. Actual successor numerical results require separate independent review afterward. Fixed release does not imply this changed training recipe is numerically equivalent to baseline; its purpose is a scientific comparison.
