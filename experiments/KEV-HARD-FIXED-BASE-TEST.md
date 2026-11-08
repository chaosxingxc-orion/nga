# Kev hard-v1 fixed Base TEST protocol

**Status: CPU prepared; scientific protocol accepted within scope; execution packages and runtime admission pending.** Protocol `nga-qwen-kev-name-preserving-mixed-v1` is prospective, before model TEST inference. This publication does not grant a launch. The exact accepted scientific protocol and machine specification are identified by SHA-256 in the [accepted summary](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/KEV-HARD-FIXED-BASE-TEST-ACCEPTED.json). That summary preserves the original acceptance identity; it does not change the original protocol's pending-review gate. Execution binding requires a future prospective amendment and separate admission.

## Population and interface

Four cells use Qwen3.5 Base 0.8B, 2B, 4B and 9B without adapters on the same [public hard-v1 TEST](https://github.com/jaredpalmer/kev/tree/main/evals/hard-v1). The source has 700 records and 1,088 questions: 826 choice, 226 Noul, 36 score. The derived panel source has 1,088 rows; retain the 700-record lineage. This is separate from BEV hard14479. Preserve physical source line and question insertion order, all questions, states and candidate order. No model outputs have been examined.

Render choice as exact name when its definition is null or empty, otherwise exact `name + ": " + description`. The 860 null entries occur in 213 questions; missing definitions remain missing. Score retains six ordered criteria, displayed 1–6 for indices 0–5. Noul has absent criteria and labels Yes/No, true at index 0; reject an unexpected criteria object. No facts, source gold or generated definitions enter prompts. The RC1 AnyJev single-question chat reads final-position LM answer-label logits. Name-preserving rendering is a prospective change from the description-only interface. The missing definitions limit interpretation under the report's defect 1/17 constructs.

The unrestricted optimum is a perfect record-to-label lookup. The discrimination counterpart comprises 134 frozen, different-input, different-gold, same-canonical-schema pairs with 268 distinct endpoints. In 43 pairs candidate order differs: compare source semantic names, truth values or zero-based score indices using the frozen position map, never raw positions. Report changed and both correct out of 134. Pairs reject semantic constants, but do not rule out lookup, menu-order heuristics or learned generator grammar; they are not invariance, causal sensitivity or generalization tests.

## Frozen identity and setup

The [accepted summary](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/KEV-HARD-FIXED-BASE-TEST-ACCEPTED.json) pins the reviewed protocol, machine specification, original source, full source join, pair artifacts, controls, request file and ordered request digest. All four request files have identical pinned bytes and each has 1,088 requests, lengths 110–4,758 and 894,976 total tokens. Choice A–F token IDs are 32–37, score 1–6 IDs 16–21 and Yes/No IDs 9175/2665. Full source join and CPU-only payloads retain their frozen identities but are not publication payloads.

The reference fixed RC1 image is `sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d`. Reference settings: FP32, HF32 off, batch 1, vocabulary 248320, maximum 8192, no truncation, all label logits, no chain of thought, top-20 censorship or shared-prefix switch. The reference plan is Instruct-specific: its guards, asset and numeric receipts do not admit Base. Exact Base model/loader, asset and numerical receipts, package, resource and per-cell config/contract/plan identities must be bound in a future amendment before execution. This scientific review does not establish numerical equivalence or runtime readiness.

## Frozen measures

At T=1, given final-position FP32 answer logits `z`, compute in float64 `l_j = z_j - logsumexp(z)` and `p_j = exp(l_j)` over candidate labels only. Hard accuracy is first maximum in original order against gold over 1,088. Also preserve the native `numpy.argsort(-l)[0]` index, all top ties and native/first-index disagreements; report both hard and pair variants if they differ. Do not assume the reference runtime field named first_index implements first maximum.

Categorical Brier is mean `sum_j (p_j - 1[j=y])²`; NLL is mean `-l_y` from saved restricted log probabilities, with no clipping. ECE10 bins confidence `max(p)` by `min(floor(10*confidence),9)` and weights absolute bin accuracy–confidence gaps by population; empty bins contribute zero. Noul additionally reports scalar Brier `mean((p_true-y_bool)²)` over 226. Score over 36 reports first-max index MAE, expected-index MAE and normalized RPS `mean(sum_{t=0}^{K-2}(sum_{j<=t}p_j - 1[y<=t])²/(K-1))`; expectation is descriptive, not a hard prediction. No physical equal-interval claim is implied. Report exact numerators and denominators, type, source, family, subtype, null, repeated-description and K strata, ties and identity failures. Reject missing, extra, duplicate, reordered, nonfinite or identity-mismatched predictions, and require all pairs. These defect and family associations are report constructs, not established mechanisms or stage gates.

The frozen controls are descriptive and set no pass threshold:

| Control | Correct / 1088 | Brier | NLL (nats) | ECE10 | Changed / 134 | Both correct / 134 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First-option one-hot | 299 | 1.4503676471 | infinity (789 zeros) | 0.7251838235 | 34 | 2 |
| Uniform, first maximum | 299 | 0.7165747549 | 1.3370926132 | 0.0100796569 | 34 | 2 |
| TEST schema-majority oracle | 931 | 0.2886029412 | infinity (157 zeros) | 0.1443014706 | 0 | 0 |

The oracle groups canonical schemas ignoring mapping key order, counts TEST semantic gold, breaks ties lexically and maps back to source order. It is label-derived and CPU-only, never a tuning or inference component. There are 805 schemas, 746 singleton schemas/questions. First-position predictions can change semantically when order changes. Flag suspicious zeros, ones, identical metrics and small strata for review, including intentional control results.

## Interpretation and admission

Exact and normalized state and source-ID overlap with the three available named hard development, documents TEST and devtools TEST sources is zero. The exact training split is absent, so training overlap is **unknown**; pretrained-weight contamination is also **unknown**. The external overlap screen is inherited, not independently rerun. No clean-training or held-out generalization claim follows.

Historical Kev 0.8B, 4B and 9B references use trained adapters and pointer heads, not Base LM label logits. Native temperatures are respectively 2.3510958125672174, 2.406050072164233 and 2.193649959389252; native-T and raw-T1 rows remain separate. There is no Kev 2B reference. Shared population and option text provide context only, not a training-gain estimate, native reproduction or calibration equivalence.

Before inference: bind Base-specific numerical and asset evidence to the actual image, loader, lengths and all labels; prepare and review all four exact execution packages and prospective amendment; independently implement and review the saved-vector scorer; keep source, derived source, gold, join, pairs, controls and CPU consumers outside every inference mount ancestor. Only gold-free requests and required dependencies belong in inference mounts. The prospective resource scope is physical chips 4/5 subject to a live eligible lease and predecessor release; protect 2/3 and 0/1/6/7. Separately admit the resource and retained detached supervisor, with resume, durable heartbeat/log, relaunch and terminal marker. No TEST-dependent selection, calibration or parameter changes are permitted.

## 2026-11-08 numerical scope clarification, before execution

Independent review accepts reuse of the existing implementation and long-DEV protocol, with a bounded same-Base/fixed-RC1 image gap. The [scope record](KEV-HARD-BASE-RC1-NUMERICAL-SCOPE.json) pins the four exact Base manifests and reviewed evidence. For each model, reuse the three frozen 4097/5296/8192-token DEV inputs across reference, reference-repeat and adapter: nine forwards per model, 36 total. Keep FP32, HF32 disabled, batch1, full vocabulary248320 and existing zero tolerances. Compare within the same actual RC1 image and checkpoint; historical old-image Base receipts and RC1 Instruct receipts are not substitutes. Project all required label sets from saved full vectors on CPU, without additional label-specific or4758-token NPU probes.

This closes the question of what numerical work is required, not the numerical work itself. No qualification result or launch is recorded. Exact execution packages, lifecycle and resource admission and their prospective bindings remain required before launch. Frozen TEST inputs, metrics, pairs and interpretation are unchanged.
