# HelpSteer2 DEV template × numeric-code diagnostic, v1

Status: prospective protocol draft awaiting independent review; no NPU launch or execution acceptance. Historical public TEST results stay unchanged. This changes input/readout protocol and is **not** a speed-only optimization. These constructs and thresholds are local diagnostic choices, not literature claims.

## Question and registry mapping

Defects 1 (names overriding definitions), 8 (ordinal compression), 12 (paired decision consistency), and 17 (expert-defined levels must be read): does changing template or displayed code alter the same semantic grade prediction, and can the model distinguish request-relative verbosity? Unconstrained perfect consistency is achieved by a constant classifier, which is therefore insufficient. Perfect accuracy on a known finite population is achieved by lookup, so this diagnosis neither proves generalization nor authorizes training gains. We retain all five published grade definitions, in their original order, including succinct rather than inadequate as grade 0.

## Population and locked factors

Source: publisher `helpsteer2_verbosity/validation.jsonl`, exactly 500 IDs. Sort by SHA256(`nga-helpsteer2-ordinal-dev-20261104-v1` + NUL + source ID), take first 128; remaining 372 are confirmation only. Source bytes, tokenizer files and CPU code are hashed in CONFIG.json. Selection depends only on IDs. No TEST read or choice is permitted in this preparation. Existing TEST exposure is acknowledged; this DEV experiment cannot make it unseen again.

Two fixed Base models: Qwen3.5 0.8B and 2B. Each receives the identical 128 IDs in four conditions:

| ID | Rendering | Display codes | Semantic decode |
|---|---|---|---|
| chat_1_5 | Existing AnyJev tokenizer chat template | 1…5 | digit − 1 |
| chat_0_4 | Same template | 0…4 | digit |
| plain_1_5 | Exact AnyJev no-template fallback, explicitly forced for this diagnostic | 1…5 | digit − 1 |
| plain_0_4 | Same fallback | 0…4 | digit |

The fallback is `system + "\n\n" + user + "\nAnswer:"`. Both model READMEs lines 15–20 say pre-trained only, intended for fine-tuning/in-context research rather than direct interaction, and mention trained chat control tokens. **They do not document a canonical Base plain prompt.** Thus this factor tests a local upstream-fallback rendering; it is not called the official/native Base format. Actual tokenizer rendering and single-token IDs are recorded in TOKENIZATION.json. No definitions, instructions, state content or grade ordering change between conditions; no truncation.

128 × 4 × 2 = 1,024 main forward passes. Use one full next-token read per request, fp32 model, HF32 disabled, eval mode, batch size 1, vocabulary 248320, max length 8192. Gold stays CPU-only. Actual image/model weight manifest and resource admission must be bound before launch; CONFIG currently binds preparation inputs, **not all execution dependencies**.

## Discrimination counterpart

Four words Amber/Birch/Coral/Dune each produce three inputs:

1. Request exactly one occurrence, response one occurrence.
2. Same one-occurrence request, response eight repetitions.
3. Request exactly eight occurrences, response eight occurrences.

For each word, predicted verbosity of (2) must exceed (1) and (3). The second comparison holds the **response itself identical**, while requested information changes. This directly follows the rubric's “relative to what the prompt asked” and “extra details … repetition”; it does not assign a grade mechanically from length. Only relative ordering is asserted; no five-class absolute gold is invented. Four lexical instances are construction repeats, not eight independent human judgments or a population estimate. This counterpart needs independent semantic review before execution acceptance; its coverage is deliberately limited.

12 control inputs × 4 × 2 = 96 additional forwards, total **1,120**. Report strict argmax ordering, expected-grade ordering and ties separately. Constant-middle predictions yield 0/8 strict orderings. Length-only predictions necessarily tie on the four identical-response pairs and cannot meet the joint threshold.

## Saving and arithmetic

Save full final-position **fp32 vocabulary logits**, actual unpadded int64 input_ids and attention_mask, a result JSON with request and condition identities, and a hash receipt written last per item. Never discard logits after scoring. Approximate logits payload is 1.11 GB decimal for all 1,120 forwards, before compression and input metadata. Reject nonfinite logits, wrong vocabulary shape, wrong model/input/config pins, missing or duplicate items, and any implicit truncation. Resume only after verifying the complete committed item receipt. An OOM is a failure requiring an explicitly versioned operational amendment, not silent truncation or dropped records.

Restricted probabilities: fp32 saved logits converted to fp64, stable softmax on the five display-token logits in original semantic grade order. Argmax ties take smallest semantic index, with tie counts reported (if alignment with historical tie implementation differs, declare it). Expected grade is sum(g × p_g). Main metrics, separately for every cell:

- Exact accuracy: correct argmax / 128.
- Argmax MAE: mean |argmax − gold|.
- Expected-grade MAE: mean |sum(g × p_g) − gold|.
- Normalized RPS: mean over items of sum from k=0…3 of (sum from g=0…k p_g − 1[gold≤k])² / 4.
- Gold/prediction histogram, grade-2 recall with gold-grade-2 denominator, missing/zero denominator explicitly null.
- Descriptive constant-grade-2 baseline on the same DEV128 only; not a learned competitor.

For each model, all six pairs of conditions use identical IDs: semantic argmax flip count /128, mean absolute expected-grade shift, mean total variation distance. Factor effects compare templates within each coding and codes within each template; report interactions descriptively. Accuracy is **not** a consistency metric. An operational low-flip diagnostic requires ≤6/128 flips and both compared conditions satisfying ≥7/8 strict argmax and ≥7/8 expected-grade control orderings. No statistical generalization or business acceptance claim follows this threshold.

Full-vocabulary secondary diagnostics: total mass on five labels, all-token top20 IDs/logits decoded by pinned tokenizer, label rank and top20 presence, mass on token IDs for all bare digits 0…5, and recorded tokenizations of whitespace-prefixed labels. Multi-token representations must not be treated as equivalent next-token labels or added to restricted scores. Full logits permit additional clearly labeled post-hoc diagnostics without changing primary metrics.

## Ranking and confirmation

Rank each model's conditions by (argmax MAE ascending, normalized RPS ascending, accuracy descending, fixed priority chat_1_5 → chat_0_4 → plain_1_5 → plain_0_4). A condition is eligible for confirmation only if it satisfies both ≥7/8 discrimination thresholds and beats constant-grade-2 argmax MAE on DEV128. If none qualifies, report no eligible driver and move to TRAIN-based learning design; do not relax thresholds after inspecting results. The selected condition and all confirmation metrics must be frozen before opening the 372 confirmation items. On confirmation compare the selected driver against chat_1_5 and the constant baseline with paired errors; a separate confirmation amendment/launch package is required. DEV gains alone cannot establish TEST gains. No condition selection or confirmation has occurred.

## Execution boundaries

This directory supplies CPU-rendered preparation, not an admitted runner. Still required: independently review semantic controls/new protocol; bind model weight manifests and immutable runtime/image; implement full-vector resumable DEV runner and multiworker CPU scorer with fixtures; bind released resources through the existing allocation contract; establish detached retained Docker, Ceph logs/heartbeat/terminal marker and exact relaunch; prepare wiki experiment entry. Poll through watchdog digest at 600 seconds. CPU scoring and reports proceed asynchronously to unrelated NPU queues. Do not edit existing TEST run sources or outputs.
