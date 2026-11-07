# RC1 H2 candidate-loss DEV prospective protocol

Status: prospective exploratory attachment, prepared before any H2 NPU run; independent Astra scientific and runtime review required before activation. No current TEST results informed the proposal. The DEV population is reused, not a pristine holdout. This is independent of H1 and does not amend any earlier pre-registration or grant a stage gate.

Hypothesis: Replacing gold-response token CE with existing candidate-restricted question CE may improve discrimination between a true candidate and NOTA in the unchanged training pairs. Weak DEV NOTA supports testing this objective, not a claim that the objective caused the failures.

Fresh Qwen3.5-4B-Base seeds 2 and 3, each 3116 updates; K1 gold-token CE changes to K2 candidate-restricted question CE. All other K1 settings remain fixed as in the accepted proposal common.training, including LR .0001, two epochs, decision-v7 TRAIN, existing augmentation, LoRA r16/alpha32/dropout .05, AdamW weight decay .01, clipping 1, OneCycle pct_start .1, reference kernel, nonreentrant checkpointing, max_len 4096, micro_tokens 12000 and batch 10. Never resume the K1 baseline. Terminal 3116 only, no alternative seeds or checkpoint selection. K2 changes both competition and weighting; effects cannot isolate them.

Reuse the accepted q4b-s2 and q4b-s3 K1 baselines by same seed, with accepted saved vectors and publications referenced in the task SOURCEPINS; no baseline rerun. Full retained nine-group DEV/calibration panel; decision DEV1264 and transfer DEV656, calibration1148 only for existing operator fit. Full Track K FP32 rightpad HF32 off token budget 16384, raw first argmax and separate R0 tie-as-incorrect. Stable T=1 binary64 NLL, candidate-sum Brier, fixed-bin ECE10; unchanged calibration grid .50:.05:.95, utility +1/-1/0, higher-tau tie, minimum20 and fallback tiers, transfer default .5. No DEV threshold fitting. Pair exact ordered question/parent keys, report wins/losses/both-right/both-wrong and fixed two-seed mean without probability ensemble, pooled ECE or doubled n; no new bootstrap/significance. Retain all source/type strata, near/exact ties, constant/uniform/drop/blank controls, permutation flips plus both-correct/exclusions, and absent/present NOTA under both tie rules.

## Conjunctive proposed criteria (verbatim)

- Each fixed seed improves transfer NOTA both-right by >=3 parents out of36 relative to matched K1 under BOTH raw and R0: seed2 >=19/36, seed3 >=20/36. Report per-parent gains/losses and fixed two-seed mean, never n72 independent parents.
- Each seed transfer false-NOTA count <=10 and <=7 respectively, absent NOTA-correct >=27 and >=26, present correct >=23 and >=24; decision NOTA both-right >=54/60 and >=53/60 respectively under both tie rules.
- Each seed on each clean suite raw/R0 accuracy delta >= -0.01 against K1; PAWS correct >=62/80 for both seeds. All source/type changes reported, not only PAWS.
- Fixed two-seed mean transfer NLL delta <= +0.02 nats, Brier delta <= +0.01 absolute, ECE10 delta <= +0.01 absolute. Each seed clean raw/R0 accuracy exceeds each retained constant/uniform/drop/blank control on each suite.
- Both seeds finish terminal3116 with exact panels; no alternate seeds/checkpoints. All criteria conjunctive, descriptive and proposed prospectively; small36-parent panel supports no general robustness or stage-gate inference.

A missing seed or panel prevents support; any failed conjunct is not supported by this bounded DEV experiment, with no automatic tuning ladder. Report every parent transition, source/type adverse cell and permutation counterpart even on failure.

Defect registry 5: NOTA fallback and paired discrimination; 16: relative candidate scores, no calibrated IIA claim; 12: decision-level pairing and controls, no G1 claim. Unconstrained lookup memorizes question/gold, always-NOTA fails present, never-NOTA fails absent, constant predictions can give zero flips while wrong. Paired both-right, both sides of NOTA and clean/control/source retention are their discrimination counterparts. These are proposed operational mappings, not proven repairs.

Exact release, image, model, data and accepted evidence receipts and candidate bytes are pinned in `.local/releases/engineering-base-rc1/tasks/execution/h2-candidate-loss-preparation/SOURCEPINS.json`. Nine-group wiring, baseline reader, candidate publication bindings and independent scientific/runtime review remain prerequisites. K2 hardware capability, throughput, memory and duration are unknown. No H2 TEST authorization is implied.
