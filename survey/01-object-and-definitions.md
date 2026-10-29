# 1 · Object and definitions: what Jev-class models are, what the backbone constraints are, and what each paper is saying

> This chapter establishes the factual basis for the whole report and contains no judgments. §1.1 is the object itself (interface primitives, the vendor's acknowledged zigzag, black-box architecture reconstruction, independent evaluations and audits); §1.2 is the recipe matrix given by more than fifteen open-source reproductions, together with the small-model evidence; §1.3 is where hybrid backbones (Gated DeltaNet class) break the structural assumptions that the Jev-style interface depends on, **survey only, no selection**; §1.4 is the cross-paper definitional disagreement, which explains why the numbers in later chapters cannot be compared with each other directly.
>
> How to read: §1.1–§1.2 answer "what it is and who has reproduced it", §1.3 answers "whether our backbone can carry it", §1.4 answers "whether two numbers should be placed side by side when you read them".

## 1.1 Jev / System One: definition, interface primitives, architecture reconstruction and independent evaluation

> This section answers: what exactly a "Jev-class fast-thinking model" is, what interface it exposes, what architecture black-box probes infer, and what conclusions independent evaluations reach. All numbers were checked against the cached original texts.

### 1.1.1 Basic facts

| Item | Content | Source |
| --- | --- | --- |
| Vendor / release | TypeSafe AI (San Francisco, founded 2024); Jev released 2026-09-15; Jev 1.14 released 2026-10-14 | [Wikipedia](https://en.wikipedia.org/wiki/Jev_(AI_model)), [docs/models](https://docs.typesafe.ai/models) |
| Pricing | Input $0.042 / Mtok, output not billed (the output is not text) | [docs/models](https://docs.typesafe.ai/models) |
| Context | 64k per request, 32k per question; can be relaxed with the `TypeSafe-Danger-Zone-Long-Context: true` header; the number of questions per request is unlimited, constrained only by the two caps | [docs/models](https://docs.typesafe.ai/models) |
| Training | "RLCD" (Reinforcement Learning for Calibrated Decisions), synthetic data only, details not disclosed; no fine-tuning on customer data, one set of weights serves all accounts | [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer), [docs/models](https://docs.typesafe.ai/models), Wikipedia |
| Positioning | "For building AI-driven software rather than agents": code owns the control flow, deterministic rules and side effects, the model only answers narrow, structured judgments; "ask independent questions together, then combine the answers in code" | [How to build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) |

### 1.1.2 Interface primitives (the starting point of our later "logic primitives" discussion)

TypeSafe's System One API has only three question types, plus `state`:

| Primitive | Returns | Constraints | Notes |
| --- | --- | --- | --- |
| **Noul** | Probability P(true) that a proposition is true | Optional `criteria`: when the yes/no boundary is subtle, use structured `true` / `false` descriptions, each with definitions and examples | [primitives/advanced](https://docs.typesafe.ai/primitives/advanced) |
| **Choice** | A probability distribution over the options + a confidence | Options carry `criteria` (descriptions) and `examples`; JSON structure may be used | Same as above |
| **Score** | A probability distribution over ordered levels + a score + a confidence | `criteria` is an ordered description of levels from low to high, ≥2 levels, API maximum 10 levels | [primitives/score](https://docs.typesafe.ai/primitives/score) |
| **State** | The material the questions are about: text, a JSON object or an array, "may contain relevant context, examples and other information that helps answer"; the metaphor is "material handed to a panel of experts" | The documentation explicitly allows examples inside state | [concepts/state](https://docs.typesafe.ai/concepts/state) |

**Confidence** is defined as `confidence = (p_max − 1/n) / (1 − 1/n)`: it looks only at the highest probability, is 0 for the uniform distribution and 1 for certainty ([docs/confidence](https://docs.typesafe.ai/confidence)). This means "confidence" is not entropy and not the top-2 gap, but only the height of the top-1 relative to the uniform distribution. Several papers point out that this definition is not the same thing as "the ability to detect errors" (see D§4.1).

**The official patterns** form the primitive library for "composing small judgments in code":

- **Speculative fan-out**: ask several independent questions in parallel within one request ([patterns/fan-out](https://docs.typesafe.ai/patterns/fan-out)).
- **Composite scoring**: the results of several Noul / Score calls are combined in code as a weighted sum ([patterns/composite-scoring](https://docs.typesafe.ai/patterns/composite-scoring)).
- **Confidence routing**: one global lower bound (0.6 in the example) + a separate threshold for each action class; below the threshold, hand over to a human ([patterns/confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing)).
- **Walking a taxonomy**: one Choice per layer, walking down the tree layer by layer in code ([primitives/advanced](https://docs.typesafe.ai/primitives/advanced)).
- Engineering advice from the **Agent skill document**: "put the questions and the threshold constants in one file for easy review; agents are not good at writing questions, edit them collaboratively"; "if you only need the best option, take the highest confidence and do not set thresholds everywhere" ([agent-skill](https://docs.typesafe.ai/agent-skill)).

**The use-case map** ([use-case map](https://docs.typesafe.ai/concepts/use-case-map)) divides decision shapes into ten classes: classification, detection, scoring, routing, search, retrieval, ranking, verification, ML feature extraction, structured extraction. These ten classes are the reference taxonomy when we define the D3 primitive set.

### 1.1.3 The vendor's acknowledged "zigzag" (jev-1.13 model jaggedness)

The official documentation lists 9 failure classes and gives "use this instead" advice ([model-jaggedness/jev-1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13)):

| # | Failure mode | Official advice |
| --- | --- | --- |
| 1 | Literal reading | Write out precise conditions and criteria for each option |
| 2 | Math and numbers: cannot count reliably (character counts, word frequencies, list items), "recognizes the shape of the answer rather than tallying one by one" | Put arithmetic in code |
| 3 | Date and time comparison: reads dates as text; before/after, interval and window judgments are unreliable | Extract the components and compare them in code |
| 4 | Indirection: double negation, attributes of attributes, multi-hop | Reduce the number of hops; point directly at the relevant state |
| 5 | State with a large amount of irrelevant detail | Filter first; send only what the question needs |
| 6 | Adversarial content | Write precise prompts; test the boundaries before going live |
| 7 | Instructions contradicting the criteria | Align the criteria with the instructions |
| 8 | Choice option order: biased toward options placed earlier | Reorder the options and check that the answers agree |
| 9 | Generation | Use a generative model |

This table is almost the "official problem list" for D2 / D4; third-party papers (below and in the per-dimension chapters) have quantified every one of these items and found more failures that the vendor does not list.

### 1.1.4 Architecture reconstruction (black-box probes)

Archer Hume's "Jev's Architecture Unmasked" (2026-09-17, [link](https://archerhume.com/posts/jevs-architecture-unmasked)) concludes from API probes:

- **A causal Transformer** (the author guesses it contains sparse MoE but explicitly says "this is speculation"), with **a shared state prefix + mutually isolated question branches + direct probability readout**.
- **Evidence for branch isolation**: placing a secret code in a sibling question, the queried question gives probability 0.00; deleting that sibling question leaves the result unchanged; placing the same statement in state raises the probability.
- **Evidence for list-style readout**: with the target option placed first, 12/16 correct; placed last, 16/16 correct, which shows the options are not scored independently.
- **An irrelevant option changes the odds ratio between existing options**: after adding an irrelevant option, the mean log-odds between the two original options drops from +0.38 to +0.11, and all ten random blocks drop (mean −0.28, 95% interval −0.36 to −0.19). This rules out the mechanism "fixed independent logits + an unchanged softmax".
- **Serving characteristics**: server time is almost flat up to about 100 questions and rises linearly after that; measured in tokens, question text costs about twice as much as state.
- **The tokenizer** matched none of 192 public tokenizers across 415 probes; each digit is tokenized separately.

This reconstruction directly determines the structure of the open-source reproductions (see [§1.2](01-object-and-definitions.md)) and the branch-isolation difficulty under hybrid architectures (see [§1.3](01-object-and-definitions.md)).

### 1.1.5 Independent evaluations and audits: what Jev is good at and what it is not

#### 1.1.5.1 Broad capability

| Source | Setup | Main conclusions |
| --- | --- | --- |
| [2609.37647](https://arxiv.org/abs/2609.37647) | 37 datasets zero-shot, 346,009 requests costing under 10 dollars; compared against the exact next-token probabilities of Qwen3.8-27B and Gemma-4-E4B | IMDB / SST-2 / HellaSwag / ARC 95–99%, Belebele 86.7% across 122 languages; beats Qwen on 27 of 37 datasets and Gemma on all; all three degrade on low-resource languages, fine-grained/noisy labels, and rubric-based quality judgments. Choice probabilities are well calibrated; **binary probabilities rank well but are placed inaccurately relative to a fixed 0.5 threshold**; on UNFAIR-ToS, tuning the threshold on the training set raises micro-F1 from 0.50 to 0.75 |
| [2610.11978](https://arxiv.org/abs/2610.11978) | 13 multiple-choice benchmarks, compared against 19 LLMs | On knowledge and common sense, on par with frontier models; best on MMLU-Redux and ARC-Challenge; **MathQA 17.7 points below the frontier median, below all 19 LLMs** |
| [2609.24574](https://arxiv.org/abs/2609.24574) | Computational social science, 18 tasks, 7,977 items, compared against 19 LLMs | Behind the best LLM for the task on 14 of 15 tasks, median gap 11.6 macro-F1, but median cost 44 times lower; confidence better calibrated than the verbalized confidence of 16 of the 19 LLMs; on the "empathy in peer-support conversations" task, **highly confident but close to random** |
| [2610.18529](https://arxiv.org/abs/2610.18529) | Medicine, 15 datasets, 8,742 items | On text-driven tasks on par with leading models, **clearly weaker on number-driven tasks**; strong consistency under changes of question format; most models cannot recognize "the correct answer is missing" and do not use the optional abstain; **normalizing per-option binary scores retains higher accuracy than Choice scoring** |
| [2610.33258](https://arxiv.org/abs/2610.33258) | Content moderation on 142,658 human-annotated comments, compared against 14 frontier reasoning models | Zero-shot AUROC 0.83, statistically indistinguishable from 13 of the 14 frontier systems, at a cost 1–3 orders of magnitude lower; "confidence" mixes two different kinds of uncertainty, **human disagreement** and **decision risk** |
| [2609.26550](https://arxiv.org/abs/2609.26550) | JEV-as-a-Judge, compared against 16 generative and reward-model judges | On every task where the verdict can be read directly from the text, within 3 points of GPT-6 at 0.36% of its cost, median latency 0.15 s; **behind on math / code / logic tasks where the verdict must be derived**; a confidence-gated cascade beats GPT-6 by 0.9 points on 1,610 pairs at 41% of the cost |
| [2610.35721](https://arxiv.org/abs/2610.35721) | Clinical trial eligibility, 2,048 pairs | In batch mode, on par with Qwen Flash on TrialGPT / MIMIC-IV, significantly better on MIMIC-III (0.768 vs 0.534), with the advantage coming mainly from recall on the "insufficient information" class (56.3% vs 9.9%); latency 1.18–1.40 s vs 2.80–8.90 s, cost 53%–74% lower |
| [2609.24052](https://arxiv.org/abs/2609.24052) | Screening 499,500 Texas crash narratives, 195,857 coded with a 27-question schema | F1 0.908 against human labels; cost is determined by schema size, not narrative length; **calibration varies by model, not by paradigm, so every model must be audited**; recalibration reduces calibration error by 3.3 times |
| [2609.23136](https://arxiv.org/abs/2609.23136) | 6G Open RAN intent interpretation | Jev meets the 1 s near-real-time budget on 99.8% of calls; two hosted LLMs reach 17.9% and 0% |

#### 1.1.5.2 Meta-audits and ecosystem

- **Early evidence audit** ([2609.32160](https://arxiv.org/abs/2609.32160)): reviews the 28 papers published within 9 days of release and concludes that "**typed readout itself has not yet shown an accuracy advantage independent of comparable label-probability readout**; Jev's clearest gains are in latency and cost, and an accuracy gap remains on hard tasks; in practice confidence is mostly used to decide when to hand off to a stronger model or a human". It gives a 14-item evaluation checklist.
- **Ecosystem** ([2609.30216](https://arxiv.org/abs/2609.30216)): 2,170 public GitHub projects as of 2026-09-22; attribute judgment and scoring are the most common uses; action selection, content filtering and model/tool selection vary widely across domains.
- **The practitioner guide** ([2610.33775](https://arxiv.org/abs/2610.33775)) proposes a five-family taxonomy: encoder classifiers, reward models, non-autoregressive decision engines, contrastive decision models, extraction models. Our direction falls in the **decoder-backbone** subclass of "non-autoregressive decision engines".
- **Leaderboards**: Decision Index 0.4 changed its main ranking to "Full score = 60% private tests on the same skills + 40% private decision tasks in new domains", with skill scores corrected for chance level ([apolinario/decision-index](https://github.com/apolinario/decision-index)); Jev leads version 0.2 ([systemonemodels.org](https://systemonemodels.org/examples/articles/jev-decision-index/)).

#### 1.1.5.3 Stability and bias (overview; details in D§4.1)

- Extremely high repeatability: on a 24-question cultural values survey with 288,000 responses, ICC 0.997 ([2609.36399](https://arxiv.org/abs/2609.36399)).
- But "same score, different verdicts": on ContractNLI, after changing the visible hypothesis, the requested answer and the output order, corrections and regressions cancel out, accuracy is unchanged while the decisions have changed ([2609.27678](https://arxiv.org/abs/2609.27678)).
- Broadly good on cognitive biases, but sensitive to irrelevant numerical information and option order ([2610.19619](https://arxiv.org/abs/2610.19619)).

### 1.1.6 Section summary: what Jev is and what it is not

1. **What it is**: a causal Transformer whose only interface is "state + typed question → probability", with a shared prefix, branch isolation and list-style readout, winning on calibration training and very low cost.
2. **What it is not**: not a more accurate classifier, not a model that can do arithmetic / compare dates / count, not a scorer immune to option order and irrelevant options, and not a model for which "confidence = knowing what it does not know".
3. **What it means for us**: Jev's value lies in the **interface contract** (probabilities that can be thresholded, composed and audited), not in the weights. As long as this contract is reproduced, a small model + domain data can beat it on specific tasks (see §1.2). The truly hard part is making this contract **stay consistent** across the dimensions D1–D5 (see §4.2).
4. **This item was revised in 17 and §8.1**: saying "the value lies in the interface contract" is not enough, because it does not say what the contract is for. The sharper version is "the contract hands the **bookkeeping of the decision** to code and leaves the **semantics** in the model". Note that this is not "turning the decision into code": the step that maps an open-world unstructured situation onto a scaled observation record has no code form at all; it is semantic generalization, and it is the only irreplaceable part of the whole construct (§2.1.7). This version predicts which kinds of deployment succeed (the decision authority is in code) and which fail (the decision authority goes back to the model), and it agrees with the five-cell table of §5.1.4. But it **cannot** be read further as "so the system is idempotent": the host Jev's own repeat jitter, the effect of menu composition on the metrics, the effect of harness planning and queuing, and "judgments that cannot be made without writing out intermediate steps" are four items that together restrict it to "shrinking the non-idempotent surface into a few boundable, priceable fields" (§2.1 §2.1, §8.1.1.2).
## 1.2 Open-source decoder reproductions and the recipe matrix (with small-model evidence)

> This section answers: which works reproduce the Jev interface with open-source causal language models (Qwen / Gemma, etc.), what backbone, readout head, loss, data, calibration and "branch isolation" method each uses, and how far small models (0.6B–9B) actually get. The encoder family (Laya, Verdict, Jeva, NDM, RubriX, Bongard, etc.) is outside our technical direction and is cited only for comparison.

### 1.2.1 A shared skeleton

All decoder reproductions follow the three-part structure reconstructed by Archer Hume:

1. **Shared state prefix**: state is encoded only once (KV cache / prefix forking / separate rows).
2. **Mutually isolated question branches**: a tree-shaped attention mask (attention-only backbones), or one row per question, or prefix forking (hybrid backbones, see §1.3).
3. **Readout**: read the candidate-letter logits of the LM head at the last position (letter readout), or place a "pointer head" at the end position of each option / mean-span pooling, then softmax over the legal options, and finally multiply by a fitted temperature.

One important piece of prior evidence: **readout works without training**. The LDM paper finds that the readout of an untuned 27B model already reaches 97% of its post-tuning accuracy ([2610.15501](https://arxiv.org/abs/2610.15501)); FunDM uses 24 of the 36 layers of Qwen3-8B and a small head trained without labels to recover about 99% of multiple-choice accuracy, with 1.56–1.57 times throughput and about one third less peak memory ([2610.17175](https://arxiv.org/abs/2610.17175)); the conclusion of LLM-as-Jev is written straight into its title: "LLMs are already Jev-style decision models" ([2610.02076](https://arxiv.org/abs/2610.02076)).

### 1.2.2 Recipe matrix

| Name | Backbone | Readout / head | Training objective | Data | Calibration | Branch isolation | Key numbers | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Kev** 1.0 | Qwen3.5-0.8B/4B/9B, Qwen3.8-27B | rank-16 LoRA + pointer head | Cross-entropy (details in the README) | `decision-v7`: 10,000 public-dataset samples + 896 generated policy samples + 1,680 samples over 60 rule structures | One temperature stored per checkpoint (0.8B 2.35, 4B 2.41, 9B 2.19, 27B 1.32; 27B/9B fitted on a never-trained held-out set) | Attention-only backbones use a tree mask + position reset; **Qwen3.5/3.8 ignore the mask because of DeltaNet, so each question gets its own row** | Kev-9B puts ≥0.9 probability on a wrong answer in 2.4% of questions from new sources; date-fact supplementation (`KEV_DATE_FACTS`) raises deadline-policy questions from 0.80 to 0.90 (Jev 0.93); provides `/v1/systemone/permute` for multi-order testing | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| **Tev1** | Qwen3.5-4B | Outputs a single answer letter (letter) | SFT | 37,840 unique training samples, about 17 dollars, 25 minutes | Not stated | One question per request | 880/1,000 on main decisions, 300/300 on policy transfer | [togethercomputer/tev1](https://github.com/togethercomputer/tev1), [Together blog](https://www.together.ai/blog/how-to-train-your-own-jev) |
| **Bespoke Nimble** 9B | Qwen3.5-9B + LoRA | Enum field (1–255 choices) | SFT | **Contrastive data curation**: "change one fact so the answer flips"; 2,676 public training samples + 324 evaluation | Not stated | 8,192-token context | Macro-F1 −12.0 under popularity shift in the finance domain (see D4) | [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble), [model card](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B-v3) |
| **pplx-decider** v1.2 | 27B (inherits v1.1-27B) | Multiple readouts per request | Details not disclosed | Not disclosed | — | Joint within a request, independent across requests | Decision Index 68.09 (joint request) vs 67.75 (separate) vs 62.30 for v1.1; **asking several facets of the same message jointly helps (PhishNChips +5.1), asking independent candidates jointly hurts (−0.2 to −0.4) → "separate requests for independent candidates"** | [model card](https://huggingface.co/perplexity-ai/pplx-decider-v1.2) |
| **OneJev** 1.6 | Qwen3.5-0.8B/4B/9B, Qwen3.8-27B (multimodal, vision tower frozen) | Answer position | Cross-entropy + Brier | 99,193 questions (94,707 public), lr 5e-6, 16,384 tokens, 1 epoch | Brier term | — | One 720p screenshot on an H200: 0.8B 1 question 31 ms / 10 questions 51 ms; 4B 64 / 104 ms; 9B 81 / 131 ms | [OmniJev/OneJev](https://github.com/OmniJev/OneJev) |
| **Open-Jev** (Zefan-Cai) | Qwen 2B/9B/27B | LoRA (27B rank 8) + scalar decision head | — | Frozen 148,639-row training mixture | Saved temperature | — | The 127,787-row internal evaluation of 27B v1.1 passed an independent audit | [Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev) |
| **open-jev / TOD** (daseinlabs) | Gemma 4 12B + LoRA; or a small head on frozen Gemma 3 4B | Head | — | User-supplied data | — | — | cookbook 01: 84.2% / 66.3% zero-shot → 97.0% / 100% (team / priority) | [daseinlabs/open-jev](https://github.com/daseinlabs/open-jev) |
| **qwen-rlcd** | Qwen3.5-0.8B-Base (18 DeltaNet + 6 attention) | letter / likelihood / PMI / `<|read|>` head | Inference only (training shelved) | — | — | **Prefix forking** replaces the tree mask; forking gives 8–19 times speedup over the full forward; on 0.8B, forking vs sequential error 4.8e-5; the gradient check through the cache has not been done | [shamazharikh/qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| **Mapika decider** | Stock Gemma-4-31B-it / Qwen3.6-27B (weights unchanged) | Readout | No training | — | **Temperature fitted by option count** T(n)=max(0.05, 10.124 − 1.633·ln n) | — | Gemma-4-31B-it Decision Index 57.33, 2nd of 70; Qwen3.6-27B 51.35, 8th; decider-31b v2 (merged fine-tune) 63.90 | [Mapika/decider](https://github.com/Mapika/decider) |
| **StartLux-Decision** v1.1 | 4B / 9B / 27B (two variants, Instant and AutoThink) | Single-pass (Instant uses bidirectional attention in the full-attention layers); AutoThink generates reasoning when the top probability is < 0.9 | Three stages: shared decision ability → differentiation → reasoning supervision + RL for AutoThink | After adding the scoring / safety / preference / logic families in stage 2, +8.6 points on the 18 corresponding DecisionPivot tasks, only +0.3 on out-of-family tasks | **Policy-aware calibration**: confidence-accuracy gap ≤2.7 pp across 184 settings | — | AutoThink over Instant: +18.4/+12.4/+11.5 points of paired accuracy at 4B/9B/27B; 27B AutoThink 86.9%, Instant 75.4%; 27B Instant ranks 1st among 174 Decision Index entries (2026-10-16) | [2610.17309](https://arxiv.org/abs/2610.17309), [StartLuxLabs](https://github.com/StartLuxLabs/StartLux-Decision) |
| **Releasing the Inner Jev** | Gemma 4 31B / 12B, Qwen3.6-27B, Qwen3.5-4B | LoRA + a decision head initialized from a slice of the LM head + a learned correction term | Teacher labels (Qwen3.5-122B-A10B, Qwen3.6-27B); **soft labels "may" not help** | OpenDecisions | — | — | Gemma 4 31B without fine-tuning 79.6 vs Jev 80.1, 84.4 after fine-tuning; **LoRA is the source of the improvement, insensitive to rank** | [2610.17205](https://arxiv.org/abs/2610.17205) |
| **LLM-as-Jev** | 4B frozen (with 0.6B experiments) | Reads logits directly; list-wise loss + KL regularization | — | — | — | — | JevBench 94.8% with native thinking under a token budget enabled; 0.6B on Banking77 (77 classes) from 22.2% → 60.5%; letter readout cannot handle 77 classes | [2610.02076](https://arxiv.org/abs/2610.02076) |
| **LDM** | Three base models (including Gemma-4-31B) | One prefill; at the last position the LM head normalizes only the legal-option logits | DDS (diverse decision supervision) + SPRD (self-questioning reasoning distillation) | DecisionVista-Synth / Human | — | — | +1.8 / +1.5 points over step-matched baselines; 182 times median latency speedup over reasoning rollouts; routing recovers 92% of the reasoning advantage with 27–58% of the reasoning tokens | [2610.15501](https://arxiv.org/abs/2610.15501) |
| **SII-Decision** | 4B / 27B (one full-rank, one LoRA) | — | **Reasoning-to-Readout self-distillation** | — | — | — | 27B ties Jev on JEVal; a typical query takes about 0.1 s | [2610.03935](https://arxiv.org/abs/2610.03935) |
| **Chinese Decision** | Qwen3.5-0.8B/2B/4B | Candidate-letter logits at the last position, normalized only over legal options | 1 epoch, 13.048M decisions | Same as left | Temperature fitted on the validation set; Q8_0 quantization | Each question is compiled into a shared instruction + candidate prompt | CJ-Bench 307,900 decisions: 4B overall 85.97%, general 75.69%, medical/legal/finance average 84.00% | [2610.23170](https://arxiv.org/abs/2610.23170) |
| **Intern-Decision** | 0.8B / 2B / 4B multimodal | One decision placeholder per field inside a complete JSON skeleton, read out with the native LM head | Autoregressive masked LM | — | Temperature scaling: Brier 0.628→0.550, ECE 0.213→0.089 | All fields evaluated in a single causal forward | 4B seven-suite average 90.02% vs 88.74% for Jev 1.13; a three-field 289-token request takes 44.16 ms on an RTX 4090; confidence handoff takes JevBench-Hard from 73.87%→87.39% | [2610.22131](https://arxiv.org/abs/2610.22131) |
| **AnyJev** | Frozen backbone | **Question-agnostic head**: affine map into the final-layer space, reusing the original output head | — | — | — | — | Across 11 models, reversing the option list changes 33% of answers on average; rotation lowers the order flip rate from 0.33 to 0.14 / 0.18 | [2610.00831](https://arxiv.org/abs/2610.00831), [nokia-applied-research/AnyJev](https://github.com/nokia-applied-research/AnyJev) |
| **OpenJev-RLCD** | Qwen3-1.7B | Explicit probabilities | "Calibrate first, then reinforce": the same proper scoring rule as the reward | Two real reasoning tasks | Intrinsic | — | Compared with SFT / RFT / GRPO (each with temperature scaling), accuracy equal or better, selective prediction better in all cases; on GSM8K answer verification a single query can decide 81% of items at ≤5% error, GRPO 19% | [2609.38850](https://arxiv.org/abs/2609.38850) |
| **PACT** | — | Single-token typed decision | Pairwise anchored calibration fine-tuning | — | — | — | Accuracy 84.6 vs 85.2 for the published recipe (no significant difference); lowest position bias, relabeling 9.8 vs 13.8%; variance across seeds halved, NLL −26%; "the value is in robustness, not accuracy" | [2609.35865](https://arxiv.org/abs/2609.35865) |
| **this-that-model** 1.0 | 2B | Reads directly from the hidden state at a designated position, restricted to the declared option set | — | Internal suite of 42 families | Brier 0.042 | All questions in a request answered in the same forward | 30.9 ms on a notebook GPU; third-party 68-question queue 0.941 vs Jev 0.765 | [2609.23886](https://arxiv.org/abs/2609.23886), [FLock-io](https://github.com/FLock-io/this-that-model) |
| **System X** | Qwen3-0.6B → v4 Qwen3-1.7B LoRA | LLM-as-Jev readout + a "text reply" option; when it wins, generation continues from the KV cache | — | Reason-9k + Bitext | ECE 0.292→0.169 | Scores on a prompt-cache copy; differs from full-sequence scoring by 1.4e-6 | v4 JevBench 55.0%→61.0%; cache reuse saves 15–39% latency | [2610.25456](https://arxiv.org/abs/2610.25456) |
| **Our Own Jev** | Frozen backbone + rank-16 LoRA + pointer head | Answers three questions in one forward | — | 148K agent coding sessions | — | — | Replaces a frontier judge costing about 1,000 dollars per pass; 1,000 sessions in about 3 minutes on one GPU for about 0.06 dollars | [2610.29052](https://arxiv.org/abs/2610.29052) |
| **Decision Model Factory** | Selectable backbone | Computes probabilities only for the allowed answers, reusing the shared context | Short recipe: train→calibrate→validate→evaluate | — | — | A dedicated runner gives more than 2 times speedup on multi-question loads | On Japanese tasks all five models beat their backbones, three beat the public best | [2610.34956](https://arxiv.org/abs/2610.34956) |
| **SecJev** | Kev-based 0.8B–9B | Kev single-pass candidate scoring | Scenario-weighted training | SecJev-Corpus: 14 tasks, 8 sources | — | — | **SecJev-0.8B beats the general-purpose Kev-9B by 20.51 pp of task macro-accuracy**; 0.8B/4B are close in accuracy and latency to answer-only generative fine-tuning, with lower peak memory | [2610.03073](https://arxiv.org/abs/2610.03073) |
| **AgentDecision-4B** | 4B | — | Trained on the states the agent reaches after its own mistakes, with Jev's answers as labels | DecisionGym | Thresholds fitted per choice | — | Out-of-distribution tasks 91.5% vs Jev 82.0%; in-distribution makes the agent 81.1–89.0% cheaper and up to 2.5 times faster | [2610.21412](https://arxiv.org/abs/2610.21412) |
| **SanSi / LEV** (recurrent) | LMs pretrained to be recurrent (LEV 2.6B, etc.) | Reads the options after each recurrent step; all steps trained jointly | Proper scoring rule | — | A small stopper fits thresholds on unlabeled requests | — | SanSi 72.0% on 10,027 decisions from 59 sources, +13.5 over a same-shape non-recurrent model; LEV 2.6B JevBench from 63.2%→76.2% going from depth 1→4; on-demand depth saves 15% compute | [2610.07730](https://arxiv.org/abs/2610.07730), [2610.20951](https://arxiv.org/abs/2610.20951) |
| **Block-causal** | — | Candidate-agnostic block-causal attention + position reset | — | — | — | Isolation + position reset | Isolation alone takes the test flip rate from 8.30%→3.82%, OOD 7.54%→3.71%; resetting positions alone is worse | [2610.01601](https://arxiv.org/abs/2610.01601) |
| **Prism-1** | Qwen3-8B / Gemma 4 12B | Position- and opponent-agnostic scoring | — | — | — | — | One shuffle under letter readout changes 20.0% / 11.9% of answers; Prism-1 has zero flips | [2610.22066](https://arxiv.org/abs/2610.22066) |
| **Runoff** | Any (training-free) | First scores each option alone to keep a few candidates, then lets each candidate occupy each position for a list-wise comparison | None | — | — | Two forwards | Order-independent by construction; zero flips for two open-source models on five datasets, versus 9.3% average for cyclic shifts; 3–4 times faster at 20 options | [2610.18233](https://arxiv.org/abs/2610.18233) |
| **ufakzeka-karar** | Turkish | Option-blind head (order-invariant) | — | — | — | — | — | [2610.06744](https://arxiv.org/abs/2610.06744) |
| **JEV entailment reranking** | NeoHorse-1-4B | **mean-span pooling** replaces the option-end pointer | **Selective adaptation**: LoRA kept on the attention and Gated DeltaNet projections, FFN adapters removed | MC11 | — | — | Trainable parameters more than halved with an accuracy gain | [2610.35654](https://arxiv.org/abs/2610.35654) |

Supplementary training theory: an exact risk calculation under a Gaussian surrogate shows that **the student inherits the teacher's bias; more student data cannot remove it, and agreement with the teacher cannot expose it**; a fixed representation lowers risk only when the sample size is below some threshold; temperature scaling removes all excess risk only when the direction of the teacher's coefficients is correct ([2610.26797](https://arxiv.org/abs/2610.26797)). This agrees with the empirical finding in "Releasing the Inner Jev" that "teacher labels help, soft labels may not", and it is the origin of the "teacher bias inheritance" sub-dimension in D4.

### 1.2.3 Can small models actually do it: evidence summary

| Evidence | Conclusion |
| --- | --- |
| SecJev-0.8B > Kev-9B (+20.51 pp) ([2610.03073](https://arxiv.org/abs/2610.03073)) | **Domain data > parameter count** |
| AgentDecision-4B out-of-distribution 91.5% > Jev 82.0% ([2610.21412](https://arxiv.org/abs/2610.21412)) | **Training on the states of one's own trajectories > a general-purpose model** |
| 0.6B Banking77 22.2% → 60.5% ([2610.02076](https://arxiv.org/abs/2610.02076)) | Small models can learn multi-class list-style readout |
| Chinese Decision 4B medical/legal/finance 84.00% ([2610.23170](https://arxiv.org/abs/2610.23170)) | 1 epoch and 13M decisions suffice for a usable small Chinese decision model |
| this-that 2B third-party 68 questions 0.941 > Jev 0.765 ([2609.23886](https://arxiv.org/abs/2609.23886)) | Single source, small sample, but the direction agrees |
| JevCascade: 150-class full menu 69.0% → curated 5-candidate menu 95.4%, **a span of 26 points, larger than the gap between 0.8B and 4B**; menu interventions are predictable to within 4.2 points ([2610.07716](https://arxiv.org/abs/2610.07716)) | **Candidate-set design is more first-order than model size** |
| Microtask eligibility gap: off-the-shelf Qwen3 0.6/1.7/4/8B pass the practitioner threshold on 0/16 of 4 agent microtasks, 4-bit quantization changes nothing, Llama-3.x fails 12/12; recommends "put the SLM behind a cheap baseline that already meets the bar, and use it only where the baseline fails" ([2610.00025](https://arxiv.org/abs/2610.00025)) | **Untrained small models are not enough**: either train them or place them behind a baseline |
| Measure Before You Train: on 739 real emails, logistic regression with about 200 labels is the most accurate on every field, and few-shot prompting cannot close the gap; but when "the most accurate system" is composed into actions it most often ignores emails that need handling (18% vs 4% for the best LLM); a cost-chosen threshold on the noisy probabilities halves this and makes it the cheapest system ([2610.32955](https://arxiv.org/abs/2610.32955)) | **Measure before training; accuracy is not the product metric; the threshold is part of the product** |
| Jev-like (Qwen3-1.7B + LoRA + 37 open-source datasets): in-domain confidence tracks accuracy almost exactly; out of domain, a 0.99 gate validated in-domain at 99.85% fails ([mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike)) | Small-model calibration **does not transfer** to new distributions |
| Continued post-training of small models: SDFT depends on strong ICL and instruction-following ability and fails on small models; forgetting and insufficient acquisition correlate linearly with distribution shift ([2610.13113](https://arxiv.org/abs/2610.13113)) | Continued training of small decision models must control distribution shift, which relates directly to D1 |

### 1.2.4 Consensus and disagreement read from the recipe matrix

**Consensus**

1. LoRA + a small readout head + a temperature suffice to reproduce the interface; full rank is not required.
2. Hard labels from a teacher (a larger model) work; contrastive / counterfactual data (Nimble, Certo, the DecisionPivot training set) works for rule sensitivity.
3. Calibration must be fitted on a **held-out distribution** (as Kev-27B/9B do), and fitting by **option count** (Mapika) or **deployment policy** (StartLux) is more stable.
4. Order bias must be solved **structurally** (block-causal, Prism-1, Runoff, AnyJev rotation), not by shuffling the training data (Prism-1 shows that published decision fine-tunes still flip).

**Disagreement / undecided**

1. Whether soft labels help (Releasing the Inner Jev says "may not help", OneJev uses Brier, OpenJev-RLCD uses a proper scoring rule as the reward).
2. Single-pass vs recurrent (SanSi / LEV) vs on-demand reasoning (StartLux AutoThink, Selective Reasoning, LDM routing): all three paths claim large gains on "hard problems", but there is no controlled comparison on the same benchmark and the same backbone.
3. Branch isolation **at training time** under hybrid backbones (Gated DeltaNet): Kev sidesteps it with separate rows, qwen-rlcd's prefix forking is inference only, and no work reports results for "training with a tree mask on a hybrid backbone" (see §1.3).

### 1.2.5 What it means for us (analysis only)

- Reproducing the interface itself is not the hard part; **domain data, candidate-set design, per-choice fitted thresholds and held-out calibration** are where the scores come from.
- Small models (0.6B–4B) can beat general-purpose 9B–27B models and Jev in narrow domains, but **not without training**, and calibration does not transfer.
- Almost every work in the recipe matrix treats "examples / definitions / rules" as **training data** rather than **inference-time input**; this is exactly where the gap for D1 and D3 lies.
## 1.3 Backbone models and hybrid-architecture constraints (survey only, no selection)

> Protocol: **survey only, no selection**. The user asked that "anything with mamba has this class of problem; survey first, select later". This section organizes: the three structural assumptions the Jev-style interface depends on; at which step hybrid backbones break them; how each open-source reproduction works around this; what can be borrowed from the inference-systems literature; and which questions nobody has studied.

### 1.3.1 The Three Structural Assumptions the Jev-Style Interface Depends On

Archer Hume's probes of the hosted Jev ([architecture](https://archerhume.com/posts/jevs-architecture-unmasked)) and all open-source reproductions (§1.2) share the same skeleton:

1. **Shared state prefix**: the state is encoded once and all questions reuse its cache. "Causal attention describes which positions may use which information, not the order in which input tokens must be executed", so the prefill phase can be parallel.
2. **Question branch isolation**: each question (with its options) can see only the state and itself, never its sibling branches. Isolation gives the interface its semantics: "asking whether the customer is angry should not change which queue the ticket goes into". Probe evidence: a secret placed in a sibling branch → 0.00; placed in the state → the probability rises.
3. **Position reset / readout**: each branch's position IDs restart from the end of the state; the readout is taken at the branch's last token.

On an **attention-only** model, 1–3 can be implemented in one forward pass with a tree-shaped attention mask + position-ID reset (Kev README: "on attention-only models, rows and the mask give identical probabilities"; [Kev](https://github.com/jaredpalmer/kev)). The block-causal paper shows that isolation alone has value: isolation by itself takes the test flip rate from 8.30%→3.82% and OOD from 7.54%→3.71%, while resetting positions alone is worse ([2610.01601](https://arxiv.org/abs/2610.01601)).

### 1.3.2 At Which Step Hybrid Backbones Break the Assumptions

| Fact | Source |
| --- | --- |
| Qwen3.5-9B-Base: 32 layers = **24 Gated DeltaNet (linear attention) + 8 full attention**, hidden 4,096 | [Kev-9B model card](https://huggingface.co/jaredpalmer/kev-9b) |
| Qwen3.5-0.8B-Base: 24 layers = **18 Gated DeltaNet + 6 gated full attention** | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| "Qwen3.5 and Qwen3.8 interleave attention layers with Gated DeltaNet layers; the latter are recurrent and **ignore the attention mask**" | [Kev README](https://github.com/jaredpalmer/kev) |
| "A tree-shaped attention mask cannot isolate sibling branches inside the recurrent layers" | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| The recurrent layers of hybrid models **update state in place**; cache entries with partial prefix overlap cannot be rolled back and can only be hit by exact match | [Marconi 2411.19379](https://arxiv.org/abs/2411.19379) |
| Cache state is **history-dependent**: the same token sequence yields different cache states under different sequences of cache operations, so prefix matching is not sufficient to guarantee correct reuse | [Cache Engineering 2610.28577](https://arxiv.org/abs/2610.28577) |

Verified layer configurations (read directly from each repository's `config.json` on Hugging Face on 2026-10-28; all are `Qwen3_5ForConditionalGeneration`, `full_attention_interval = 4`, i.e. 1 full-attention layer and 3 Gated DeltaNet layers in every 4 layers; vocabulary 248,320, context 262,144):

| Model | Layers | Full attention / linear attention | hidden | Attention heads / KV heads | FFN |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B (Base / Instruct identical) | 24 | 6 / 18 | 1,024 | 8 / 2 | 3,584 |
| Qwen3.5-2B (same) | 24 | 6 / 18 | 2,048 | 8 / 2 | 6,144 |
| Qwen3.5-4B (same) | 32 | 8 / 24 | 2,560 | 16 / 4 | 9,216 |
| Qwen3.5-9B (same) | 32 | 8 / 24 | 4,096 | 16 / 4 | 12,288 |
| Qwen3.5-27B, Qwen3.6-27B, **Qwen3.8-27B** | 64 | 16 / 48 | 5,120 | 24 / 4 | 17,408 |

The three generations of 27B have exactly the same shape; they differ only in weights. The Qwen3.8 series **has no size below 27B** (Hugging Face only has `Qwen3.8-27B`, `Qwen3.8-2.4T-A95B` and `Qwen3.8-Flash-Next`, the latter two being MoE), and Qwen3.6 only has 27B and 35B-A3B. So the "small to large" same-architecture ladder can only be Qwen3.5-0.8B / 2B / 4B / 9B → 27B (any of 3.5 / 3.6 / 3.8), which matches the four levels actually used by reproductions such as Kev and OneJev (§6.1.5). **The endgame size is fixed at the 27B / 35B level** (2026-10-28 terms), and there is a fact that must be separated first: **27B is dense, and Qwen has no dense 35B: every 35B is the `35B-A3B` MoE (about 3B active)**. If the endgame lands on 35B-A3B, then beyond the three structural assumptions below there is one more item, "whether per-token expert routing introduces new coupling between isolated branches", on which this report has **zero hits** (§6.1.5). The local `/mnt/cephfs/models/` already holds complete, unquantized checkpoints of all three 27B models, Qwen3.5-27B, Qwen3.6-27B and Qwen3.8-27B, so a "same shape, cross-generation weights" comparison can be run directly. This turns the variable "small end and large end differ in generation" into a measurable quantity: the difference of the same decision evaluation between 3.5-27B and 3.8-27B is the difference brought by cross-generation pretraining, independent of size.

**Implication**: the recurrent layers mean assumption 2 (isolation) cannot be achieved by a mask: tokens of branch A "flow into" branch B through the recurrent state. Assumption 1 (shared prefix) still holds, but what is reused is a **recurrent-state snapshot**, not KV.

### 1.3.3 The Three Workarounds Used by Open-Source Reproductions

| Method | What it does | Cost / evidence | Source |
| --- | --- | --- | --- |
| **Row-by-row execution (Kev)** | One row per question: "state + that question", with the same positions as the tree-mask scheme; the state cache is computed once and reused by every row; the server batches by a token budget (one row of at most 16,384 tokens per forward pass), "memory does not grow with the number of questions, and answers do not depend on batching" | Isolation is exact; every row has to re-read the state's recurrent state; `forward()` (the source of all published numbers) and the server agree within fp32 rounding | [Kev](https://github.com/jaredpalmer/kev) |
| **Prefix forking (qwen-rlcd)** | Prefill the state and keep the cache (KV for attention layers + conv and recurrent state for DeltaNet layers); copy along the batch dimension, one row per branch; right-pad all "question + answer" branches and run them as one batch at the same position offset; read the hidden state at each branch's last real token | 8–19× faster than one forward pass per branch; chunking branches bounds memory; on real 0.8B weights the fork vs sequential error is 4.8e-5 (tolerance 1e-3), and the negative control with the recurrent state zeroed gives 6.3; **"the gradient check through the cache is deferred to training time"**: training is on hold | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| **Shared-context anchoring + candidate prefix sharing + decision-guided pruning (FastJEV)** | Reuse the recurrent initial state and skip the unused final recurrent cache; keep the intermediate states that later branches need; prune depth by relative score change on a small unlabeled set | Candidate depth −43.75–45.83%, retaining 93.66–97.52% of task score; **"candidate prefix sharing reduces repeated computation but increases latency"**; "sharing granularity and execution scheduling must be designed together" | [2610.11379](https://arxiv.org/abs/2610.11379) |

Two further architecture-related choices on the training side:

- **Selective adaptation**: keep LoRA on the attention and Gated DeltaNet projections and drop the FFN adapters; on MC11 this beats the all-module baseline with trainable parameters cut by more than half ([2610.35654](https://arxiv.org/abs/2610.35654)); Kev-9B's LoRA is also placed on the attention, MLP and DeltaNet projections (45.4M parameters).
- **StartLux Instant**: bidirectional attention over the prompt inside the **full-attention layers** (llama.cpp non-causal flag, vLLM plugin); only the attention layers are changed, the recurrent layers are untouched ([StartLux](https://github.com/StartLuxLabs/StartLux-Decision)). This shows that on a hybrid backbone the freedom to "change how the model reads" is concentrated in the few attention layers.

### 1.3.4 What Can Be Borrowed from the Inference-Systems Literature

| Work | Applicable layer | Key point | Source |
| --- | --- | --- | --- |
| Hydragen | Attention | Compute attention separately for the shared prefix and the unique suffixes | [2402.05099](https://arxiv.org/abs/2402.05099) |
| DeFT | Attention | IO reuse and load balancing for tree-shaped KV | [2404.00242](https://arxiv.org/abs/2404.00242) |
| Block-Attention | Attention | Documents are chunked and their KV computed independently; the last chunk sees everything | [2409.15355](https://arxiv.org/abs/2409.15355) |
| IPPD | Attention | Virtual position IDs + mask manipulation to answer multiple same-context questions in parallel within one prompt, without changing the architecture | [2609.05707](https://arxiv.org/abs/2609.05707) |
| Visual Jev | Both (implemented by batching isolated suffixes) | Image and shared context encoded once, isolated question suffixes batched: at N=32, warm state is 8.9× faster than serial and 3.4× faster than batching with prefix recomputation, with higher peak memory; typed heads show no consistent advantage | [2609.25845](https://arxiv.org/abs/2609.25845) |
| Marconi | Recurrent | Admission / eviction policies for prefix caching in hybrid models: token hit rate up to 34.4×, TTFT −71.1% | [2411.19379](https://arxiv.org/abs/2411.19379) |
| Cache Engineering | Both | The agent directly drops / repositions the cache; serving challenges from history dependence | [2610.28577](https://arxiv.org/abs/2610.28577) |
| FastJEV | Both | See 8.3 | [2610.11379](https://arxiv.org/abs/2610.11379) |

The attention-layer works (the first four) solve different faces of **the same problem**: IO for the shared prefix on a tree. They all assume the mask is effective, so they only cover the attention layers of a hybrid backbone; for the recurrent layers there are only two papers, Marconi and FastJEV.

### 1.3.5 Attention-Only Backbones as the Control

Attention-only backbones used in reproduction work: the Qwen3 series (Qwen3-1.7B in OpenJev-RLCD; Qwen3-8B in FunDM; Qwen3-0.6B–8B in System X / SHIFT-JEV / Microtask), Gemma 3 (daseinlabs' decision head on a frozen Gemma 3 4B), Qwen3-8B / Gemma 4 12B (Prism-1), Gemma 4 31B (Releasing Inner Jev). On these backbones the "rows and mask are equivalent" statement in the Kev README holds, and the tree-mask scheme can be trained directly (gradients through the shared prefix have no recurrent-state problem).

**The gap in cost comparison**: no work compares "hybrid backbone + row-by-row / forking" against "attention-only + tree mask" at equal parameter count on decision accuracy, calibration and latency. The existing numbers are scattered: OneJev (Qwen3.5 hybrid) 0.8B 31/51 ms, 4B 64/104, 9B 81/131 ([OneJev](https://github.com/OmniJev/OneJev)); Intern-Decision 4B 44.16 ms ([2610.22131](https://arxiv.org/abs/2610.22131)); this-that 2B 30.9 ms ([2609.23886](https://arxiv.org/abs/2609.23886)); the measurement conditions all differ.

### 1.3.6 Matrix for This Section

| Question | Attention-only | Hybrid (DeltaNet) | Evidence status |
| --- | --- | --- | --- |
| Shared state prefix (inference) | KV reuse, mature | Recurrent-state snapshot reuse (Kev, qwen-rlcd, FastJEV) | Both feasible |
| Branch isolation (inference) | Tree mask, one forward pass | Row-by-row / prefix forking (multi-row batch) | Feasible on hybrid; memory and scheduling costs have numbers (8–19×, FastJEV's latency warning) |
| Branch isolation (**training**) | Tree mask, gradients flow naturally | Forked cache needs gradients through the copied recurrent state | **qwen-rlcd explicitly defers; no literature at all** |
| Prefix-cache serving | vLLM etc., mature | Marconi-style admission / eviction | One paper for hybrid |
| Changes to the reading mode (bidirectional etc.) | All layers changeable | Only attention layers changeable (StartLux) | Existing practice |
| Adapter placement | Anywhere | Attention + DeltaNet projections, drop FFN (2610.35654) | One paper |
| Decision quality of hybrid vs attention-only at equal parameter count | — | — | **None** |

### 1.3.7 Blind Spots (To Be Filled Before Selection)

1. **Branch isolation at training time** has no literature on hybrid backbones: Kev trains "row-by-row" (one row per question), which is equivalent but costs repeated encoding of the state; qwen-rlcd's forking scheme is "deferred" for training. Either accept the row-by-row training cost or prove that gradients through the copied recurrent state are correct; neither has public numbers.
2. **Whether recurrent layers are more sensitive than attention to "irrelevant detail in a large state"**: the D2/D4 evidence (Jev retrieves without error within 20k tokens, but multiple updates interfere with each other) all comes from the hosted Jev, whose architecture is unknown; there is no open-source hybrid vs attention-only comparison.
3. **Structural mitigation of order bias** (block-causal, Prism-1, Runoff) and how to implement it on hybrid backbones: block-causal depends on the mask; Runoff is two forward passes (architecture-independent); Prism-1's implementation details are unverified.
4. **Quantization and fused kernels**: Kev uses fused DeltaNet kernels + CUDA graphs on CUDA, with bf16 deviating from fp32 by at most 0.03/0.05; Chinese Decision's Q8_0 changes top-1 by 0.4–1.1%. These are all single-point numbers, with no breakdown by layer type.
5. ~~Qwen3.6 / 3.8 layer configurations have no verifiable numbers~~: verified from `config.json` on 2026-10-28 and listed in 8.2; the remaining gap is that Qwen3.8 has no small size, so the small→large ladder must cross generations (Qwen3.5 small models → 3.8-27B), and the cross-generation pretraining / post-training difference is itself a variable that no literature controls for.

## 1.4 Cross-paper comparison of problem definitions: the same word, different definitions

> Protocol: the user asked to "summarize the problem definitions in detail; the academic definitions in different papers are very likely to differ". This section only organizes and compares at the level of definitions and does not propose our own definition (that is the next stage's work), but §1.4.10 lists "the points of disagreement we must answer before defining the problem". All quotations were checked against the cached full text / abstract / documentation; definitions that could not be checked are marked "unverified".

### 1.4.1 Why Definitions Diverge

Jev was released only six weeks ago, TypeSafe has published no training details or formal definition, and the community is doing three things at once: reproduction (which needs operational definitions), auditing (which needs testable definitions) and theorizing (which needs axiomatic definitions). The three motivations give mutually incompatible definitions of "decision model", and **the same metric name (ECE, flip rate, confidence, RLCD) refers to different quantities in different papers**. Definitions must be aligned before numbers can be compared across papers; this is also the root of README §4 "numbers across papers are not directly comparable".
### 1.4.2 What the "Decision Model" Is Called and What It Refers To

| Name | Key points of the definition | Source |
| --- | --- | --- |
| **System One model** (TypeSafe) | "trained for calibrated decisions: their probabilities are optimized against outcomes to reflect uncertainty. Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct"; "designed to return stable answers across repeated evaluations" (Self-consistent); writes no replies, produces no code, generates no explanations; classified under "Machine Native Intelligence"; the training path is RLCD (the "third post-training path" alongside RLHF and RLVR) | [system-one](https://docs.typesafe.ai/concepts/system-one), [how-to-build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one), [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer) |
| **Typed decision model (TDM)** | The generic name in the audit papers; emphasizes the "typed" interface rather than the training method: "Type-Safe Is Not Error-Free", "Labels Override Definitions", "TDMs under Prevalence Shift", "How Reliably Do TDMs Use Fallback", "open TDMs" | [2609.32160](https://arxiv.org/abs/2609.32160), [2609.26758](https://arxiv.org/abs/2609.26758), [2610.02586](https://arxiv.org/abs/2610.02586), [2610.26325](https://arxiv.org/abs/2610.26325), [2610.19856](https://arxiv.org/abs/2610.19856), [2609.31142](https://arxiv.org/abs/2609.31142) |
| **Typed decision models, also called System One models** | "return such probabilities without generating text"; the object of interest is "decision gates": "Software that hands branching decisions to a model needs a declared option and a probability it can threshold" | [2610.00346](https://arxiv.org/abs/2610.00346) |
| **Large Decision Model (LDM)** | "processes the task in one prefill, projects the last input hidden state through the LM head, and normalises only the allowed option logits"; the Choice 2–8 and Score 3–6 limits "are implementation choices, not part of the LDM definition"; calls the training **decision tuning** and the output **readout** | [2610.15501](https://arxiv.org/abs/2610.15501) |
| **General decision model** | A decision instance is a quadruple (state, instruction, criteria, gold): "state provides the information needed for the decision, instruction specifies the decision goal, criteria defines the legal decision space"; the readout is called **First-Token Decision Readout** (the distribution at the answer position restricted to the legal option labels; choice / noul / score obtained in one forward pass) | [2610.03935](https://arxiv.org/abs/2610.03935) |
| **Narrow Decision Model (NDM)** | Eight desiderata: D1 typed output (a distribution over a closed set, never free text); D2 calibration ("among answers given probability p, about p are right", measured, adjusted and reported separately per question type); D3 single-pass (all questions and options of one request answered in one forward pass, the state encoded only once); D4 option-permutation invariance (reordering options only permutes the output distribution, nothing else changes); D5 question isolation (an answer does not depend on other questions in the same request or their options); D6 abstention (each Choice may include an explicit "none of these", whose probability is calibrated separately); D7 read, not memorize (options are recognized by their descriptions; unseen options and unseen organizational structures can be handled); D8 (a structural item, not excerpted). Claims to give "a formal statement of the System One decision contract", including **declared / undeclared abstention mechanisms** and a **set-valued training objective**, and requires that "the evaluation protocol for the accept-or-reject mechanism be completed before the held-out data is opened" (contract tests) | [2610.25553](https://arxiv.org/abs/2610.25553) |
| **Prefill-only decision model** | "score every candidate in a menu in a single forward pass and never decode"; the core property is **readout stability** (Definition 1: the distribution after restricting the menu to a subset equals the original distribution renormalized on that subset) | [2610.07716](https://arxiv.org/abs/2610.07716) |
| **System 1 decision models** | "architectures that map an input directly to a typed, structured decision in a single forward pass"; five-family taxonomy: encoder classifiers, reward models, non-autoregressive decision engines, contrastive decision models, extraction models | [2610.33775](https://arxiv.org/abs/2610.33775) |
| **System 1 / can it be left to System 1** | The question is "can it be left to a fast model that answers with calibrated probabilities in a single forward pass, or does it still need a generative LLM" | [2610.21244](https://arxiv.org/abs/2610.21244) |
| **Probability-only model** | "return calibrated probabilities for fixed choices in milliseconds and generate no text" | [2610.09188](https://arxiv.org/abs/2610.09188) |
| **Candidate-scoring decision model** | "return a probability distribution over a presented set of answers"; three training ingredients (soft targets, frozen backbone, temperature) determine "what these probabilities estimate" | [2610.26797](https://arxiv.org/abs/2610.26797) |
| **Decision models (FunDM)** | "score candidate answers or actions": action selection and answer selection are treated as the same class | [2610.17175](https://arxiv.org/abs/2610.17175) |
| **Direct-decision model** | "JEV-like direct-decision models", emphasizing skipping reasoning and emitting the distribution directly; used in the ordinal-bias study | [2609.38827](https://arxiv.org/abs/2609.38827) |
| **One-pass decision model** | A conclusion-style definition: "best used as fast selectors over a state that a reasoning model has computed and checked", i.e. the decision model is a **selector**, not a **calculator** | [2610.24929](https://arxiv.org/abs/2610.24929) |
| **System 1.5** | A looped model: each loop step reads the options once; "one model serves every budget from 1 to 8 loops" | [2610.07730](https://arxiv.org/abs/2610.07730) |
| **Atomic action** | "fast, single-step decisions such as classification, semantic endpointing, Boolean checks, and scoring, formulated as constrained generation with single-token outputs" (still generative decoding, just a single token) | [2609.36115](https://arxiv.org/abs/2609.36115) |
| **Native typed decision-making** | An action encoder embeds each candidate action description in parallel and scores it against the LLM's internal state to obtain a typed action distribution | [2609.36116](https://arxiv.org/abs/2609.36116) |
| **Machine intuition** | "recognising patterns and judging situations without explicitly unfolding every intermediate step", as an independently trainable capability | [2609.39111](https://arxiv.org/abs/2609.39111) |
| **Typed probabilistic assessor** | Laya's self-description: answers choice / noul / score questions over workflow state | [2609.33843](https://arxiv.org/abs/2609.33843) |
| **System One with a natural-language interface** | Opposes "structured schema objects encoding state, intent and candidates"; argues that both the request and the candidates should be expressed in natural language, with a candidate space that can be an open set in the millions | [2610.11316](https://arxiv.org/abs/2610.11316) |
| **"LLMs are already Jev-style decision models"** | A frozen chat model with logits read directly already satisfies the definition; "decision model" is a readout mode, not a model category | [2610.02076](https://arxiv.org/abs/2610.02076) |

**Points of disagreement**: (1) whether the subject of the definition is the **interface** (TDM, LDM, JEVal), the **properties** (the eight NDM items, readout stability), the **training method** (TypeSafe's RLCD, "optimized against outcomes") or the **use** (decision gate, fast selector, can it be left to System 1); (2) whether "generates no text" is part of the definition: Koa-decision and SALSA generate a single token, System X continues from the KV cache, StartLux AutoThink reasons first and then reads out, and all call themselves decision models; (3) whether the option limit (255 / 2–8 / millions) belongs to the definition; (4) "calibration" is a description of the training objective in TypeSafe, a contract clause in NDM, and a hypothesis to be tested in the audit papers.

### 1.4.3 Formalization of the Request / Contract

| Formalization | Content | Source |
| --- | --- | --- |
| TypeSafe's three primitives | Noul (a single probability), Choice (a distribution over ≤255 options), Score (a distribution over 2–10 ordered levels); one request = one state + multiple questions; state and questions are separated, and examples may go in the state or in the question's examples field | §1.1, [state docs](https://docs.typesafe.ai/concepts/state) |
| Kev's question schema | `{"type": "choice", "instructions": …, "criteria": {name: definition, …}}`; options are given as "name + definition" pairs | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| JEVal quadruple | (state, instruction, criteria, gold); criteria defines the legal decision space | [2610.03935](https://arxiv.org/abs/2610.03935) |
| LDM | Choice with 2–8 named options, yes/no, Score with 3–6 levels; the limits are implementation choices | [2610.15501](https://arxiv.org/abs/2610.15501) |
| NDM contract | Closed-set distribution + calibration per question type + single-pass + permutation invariance + question isolation + explicit abstention + reading option descriptions; declared / undeclared abstention; set-valued objective; a synthetic-data engine with "validity guards"; "specification first" | [2610.25553](https://arxiv.org/abs/2610.25553) |
| Probability Contracts | Treats the Event (Noul) and Choice interfaces as two possibly inconsistent "probability contracts": ask the same fact through both interfaces, then compare "canonical posterior error", "complement residual" and "coarsening residual"; Jev's Event and Choice interfaces **change the binary action in 32.8% of valid pairs** at a 10% latency cost | [2609.37470](https://arxiv.org/abs/2609.37470) |
| Multiple questions over shared state | Verdict: "answering many small typed questions about one piece of state"; a structured mask makes the state encoding independent of the questions, the questions independent of each other, and the option order irrelevant "by construction"; Intern-Decision places one decision placeholder per field inside a complete JSON skeleton | [2610.20778](https://arxiv.org/abs/2610.20778), [2610.22131](https://arxiv.org/abs/2610.22131) |
| Single-token constrained generation | Koa-decision's atomic label tokens; SALSA's class→token mapping | [2609.36115](https://arxiv.org/abs/2609.36115), [2510.22691](https://arxiv.org/abs/2510.22691) |
| Natural-language request + natural-language candidates | MetaEncoder: no schema, candidates can number in the millions | [2610.11316](https://arxiv.org/abs/2610.11316) |
| Action space | FunDM / Dyad / AgentDecision: candidates are action descriptions; DecisionGym's three levels (L1 isolated questions, L2 step-level over recorded trajectories, L3 controlling a running agent) | [2610.17175](https://arxiv.org/abs/2610.17175), [2609.36116](https://arxiv.org/abs/2609.36116), [2610.21412](https://arxiv.org/abs/2610.21412) |

**Points of disagreement**: whether Event and Choice are the same contract (2609.37470 shows they are not on Jev); when "option = name + definition", which one the model follows (2609.26758: the name; 2610.02586: labels override definitions); whether multiple questions should be "isolated" (NDM D5, Verdict) or "jointly beneficial" (pplx-decider: asking multiple facets of the same message jointly +5.1, asking independent candidates jointly −0.2 to −0.4, see §1.2).

### 1.4.4 What "Confidence" Means

| Definition | Content | Source |
| --- | --- | --- |
| TypeSafe `confidence` | Compresses the distribution shape into one number in 0–1: "1 when all the probability is on one outcome and 0 when the probability is spread evenly"; Noul has no such field; §1.1 gives its formula, which depends only on the top probability ((p_max − 1/n)/(1 − 1/n)) | [confidence docs](https://docs.typesafe.ai/confidence), §1.1 |
| Top probability | "confidence to be the probability of its verdict"; also notes that Jev's native field "is a statistic of the whole label distribution whose formula is not published", with Spearman 0.976 between the two; SanSi likewise "Confidence is the top probability" | [2609.26550](https://arxiv.org/abs/2609.26550), [2610.07730](https://arxiv.org/abs/2610.07730) |
| Expected error | ufakzeka-karar returns temperature-scaled probabilities + "an expected error that serves as a 'not sure' signal" | [2610.06744](https://arxiv.org/abs/2610.06744) |
| Learned uncertainty score | SHIFT-JEV learns one risk score from three signal classes (uncertainty, format, option consistency) and compares it with the top-probability score (at a 10% target risk, 3–5 vs 5–15 / 27 exceedances) | [2610.34329](https://arxiv.org/abs/2610.34329) |
| Two kinds of uncertainty (training view) | OpenJev-RLCD: the outcome is "one-hot when there is a right answer (epistemic uncertainty) and spread when humans disagree (aleatoric uncertainty)"; "Aleatoric uncertainty: when RL cannot help" | [2609.38850](https://arxiv.org/abs/2609.38850) |
| Two kinds of uncertainty (deployment view) | Human disagreement vs decision risk; under asymmetric loss the two require opposite escalation signals, "no single confidence number serves both"; splitting a judgment into parallel sub-questions and reading the dispersion recovers the disagreement signal | [2610.33258](https://arxiv.org/abs/2610.33258) |
| Calibration vs sensitivity | "calibration and sensitivity (how well confidence separates right from wrong answers) are distinct"; the most sensitive model's confidence tracks "which kind of situation will fail" rather than "which answer is wrong" | [2610.09683](https://arxiv.org/abs/2610.09683) |
| Answer confidence vs self-knowledge | "Do you know the answer" style Nouls are separated from answer confidence; surface cues can masquerade as self-knowledge | [2610.01006](https://arxiv.org/abs/2610.01006) |
| The decision model "does not know its own limits" | "its confidence flags the errors it makes itself but not" errors inherited from input errors | [2610.24929](https://arxiv.org/abs/2610.24929) |
| Answer quality (answer mass) | AnyJev uses "total probability mass on the legal options" as the readout's normalizer and as a validity metric | [2610.00831](https://arxiv.org/abs/2610.00831) |

**Points of disagreement**: confidence is (a) a statistic of the distribution shape (TypeSafe), (b) the top-1 probability (most audits), (c) a learned risk score (SHIFT-JEV), or (d) two quantities that cannot be merged (2610.33258). (a) and (b) are highly correlated in ranking but **not equivalent at the threshold level** (the same 0.6 threshold means different things with 2 options and with 10 options), and neither is an "error detector" (§4.2 D1).

### 1.4.5 How "Calibration" Is Defined and Measured

| Definition / metric | Content | Source |
| --- | --- | --- |
| TypeSafe | "measured across groups of predictions; it does not guarantee that an individual answer is correct" | [system-one](https://docs.typesafe.ai/concepts/system-one) |
| NDM D2 | "among answers given probability p, about p are right", measured, adjusted and reported separately **per question type** | [2610.25553](https://arxiv.org/abs/2610.25553) |
| ECE, 15 equal-width bins | Choice uses the top option's probability, Noul uses its probability; "top-label ECE, 15 equal-width bins, the last bin closed" | [2609.37647](https://arxiv.org/abs/2609.37647), [2610.26325](https://arxiv.org/abs/2610.26325) |
| ECE, 10 equal-width bins | JEVal: "ten equal-width confidence bins"; SanSi: ten equal-width bins, only on answerable items | [2610.03935](https://arxiv.org/abs/2610.03935), [2610.07730](https://arxiv.org/abs/2610.07730) |
| ECE, 15 equal-mass bins | AnyJev | [2610.00831](https://arxiv.org/abs/2610.00831) |
| Equal-mass bins + bias-aware estimation | Adopted by the benchmark paper on the grounds that "the estimate depends on the binning scheme" | [2610.00346](https://arxiv.org/abs/2610.00346) |
| ECE relative to a finite-sample null | TypedBench: "calibration relative to a matched finite-sample null ECE", also reporting smooth ECE, Brier, NLL, coverage at 5% risk, flip rate, JSD, RPS, QWK and decision value under asymmetric costs; evaluated across "friendly / adversarial" phrasings | [2610.11392](https://arxiv.org/abs/2610.11392) |
| smooth ECE | ufakzeka-karar (temperature scaling lowers it on the dev set and raises it on held-out support questions, 0.027→0.045) | [2610.06744](https://arxiv.org/abs/2610.06744) |
| Signed confidence-accuracy gap | Laya audit: −0.214, accuracy above confidence in every occupied bin, "sign agreement collapses every binned ECE variant to the same value"; the direction determines which way the cascade fails | [2609.33843](https://arxiv.org/abs/2609.33843) |
| Proper scoring rules | Brier, log-loss, RPS as training objectives and evaluation (jevlike, Open-Jev, NDM, SanSi, OpenJev-RLCD, UniJev CORA) | §6.1 family C |
| Selective prediction / AURC | Risk-coverage curve after sorting by confidence (OpenJev-RLCD, PACT, 2609.37647) | [2609.38850](https://arxiv.org/abs/2609.38850), [2609.35865](https://arxiv.org/abs/2609.35865) |
| Policy-aware calibration | Measures the confidence-accuracy gap under the deployment policy (selection, routing), ≤2.7 pp across 184 settings; "downstream selection distorts the confidence-accuracy relation even when the model is unchanged" | [2610.17309](https://arxiv.org/abs/2610.17309) |
| Risk budget / false-omission risk | Default to a conservative fallback when uncertain, and control the false-omission risk within the subset "assigned the utility-maximizing action"; naive thresholds exceed the budget in about half the settings, Learn Then Test 7.8% | [2610.19811](https://arxiv.org/abs/2610.19811) |
| Calibration under prior shift | Candidate restriction, EM prior correction, 35 pre-registered paired tests | [2610.26325](https://arxiv.org/abs/2610.26325) |
| Probability axioms / coherence | Deviation of negation-pair sums from 1: Jev 0.064, Qwen3.8-27B first token 0.293, verbalized probability 0.122; total variation between hierarchical marginalization and direct asking: Jev 0.219–0.349, Laya 0.424–0.689 | [2609.33209](https://arxiv.org/abs/2609.33209), [2609.33971](https://arxiv.org/abs/2609.33971) |
| Cross-interface consistency | Canonical posterior error, complement residual, coarsening residual | [2609.37470](https://arxiv.org/abs/2609.37470) |

**Points of disagreement**: (1) the binning scheme (10/15, equal-width/equal-mass, closed last bin) directly changes the ECE value, so it is not comparable across papers; (2) whether "calibration" includes coherence (2609.33209 / 2609.33971 say it does not and must be listed separately); (3) whether calibration is measured on "isolated questions" or under the "deployment policy" (StartLux, 2610.19811 and 2609.37470 hold that only the latter is the product metric); (4) whether Noul calibration is measured separately for the positive and negative classes (2609.37647 uses the Noul probability itself, TypedBench uses friendly / adversarial phrasings).

### 1.4.6 How "Consistency / Flip" Is Defined

| Definition | Content | Source |
| --- | --- | --- |
| Repeatability | ICC of repeated calls on the same request (0.997); the test-retest floor ("Jev is not deterministic, so … the flip rate between two identical runs"); repeats in a fixed order as a control; same-text rerun flips 0.17% | [2609.36399](https://arxiv.org/abs/2609.36399), [2609.26758](https://arxiv.org/abs/2609.26758), [2610.35826](https://arxiv.org/abs/2610.35826), [2609.31142](https://arxiv.org/abs/2609.31142) |
| Single-shuffle flip | One shuffle under letter readout changes 12–20% (Qwen3-8B 20.0% / Gemma 4 12B 11.9%, the published fine-tune 9.1%) | [2610.22066](https://arxiv.org/abs/2610.22066) |
| Cumulative failure set | Tracks individual items across eight presentations: "accuracy varies by less than two percentage points, yet its cumulative failure set expands by 27–29% relative to the original order"; i.e. **stable accuracy ≠ stable items** | [2610.35826](https://arxiv.org/abs/2610.35826) |
| List reversal | Averaged over 11 models, reversing the option list changes 33% of answers | [2610.00831](https://arxiv.org/abs/2610.00831) |
| Order invariance (definition) | Runoff Definition 1: the decision rule gives the same distribution for any option order; NDM D4: reordering only permutes the distribution | [2610.18233](https://arxiv.org/abs/2610.18233), [2610.25553](https://arxiv.org/abs/2610.25553) |
| Luce's two axioms | Order independence + adding an option does not change the relative odds of the other options; theorem: only a softmax in which "each option's score depends on itself alone" satisfies both; "a well-chosen added option steers 4–34% of decisions" | [2610.22066](https://arxiv.org/abs/2610.22066) |
| IIA / clones / decoys | Pre-registered tests of Jev's option-set dependence (decoys, fillers) | [2610.16655](https://arxiv.org/abs/2610.16655) |
| Readout stability | Distribution after menu restriction = original distribution renormalized (Definition 1); when it holds, the restricted predictor is exact | [2610.07716](https://arxiv.org/abs/2610.07716) |
| Definition-level flip | "track changes in the selected definition rather than in the returned name": after swapping the name-definition binding, a model that follows definitions should return a different name; AUC 93.8% → 23.2% | [2609.26758](https://arxiv.org/abs/2609.26758) |
| Labels override definitions | Three interventions: deleted / contradictory / reversed definitions | [2610.02586](https://arxiv.org/abs/2610.02586) |
| Answer-preserving variants | Keeps only the 5,586 variants that "should not change the answer" and attacks only correct decisions: 46.3% flips vs 0.17% for same-text reruns | [2609.31142](https://arxiv.org/abs/2609.31142) |
| Equivalent wording vs identical-text repeats | "changes answers more across equivalent wordings than across identical-text repeats" | [2610.30045](https://arxiv.org/abs/2610.30045) |
| Ordinal compression | "candidate-space compression": correlated with the number of options, direction not unique, large models still biased | [2609.38827](https://arxiv.org/abs/2609.38827) |
| Position bias (training metric) | PACT: "answer flips under relabelling" 9.8 vs 13.8% | [2609.35865](https://arxiv.org/abs/2609.35865) |
| Question isolation | NDM D5; Verdict's structural mask; pplx-decider's "joint / separate request" experiment | [2610.25553](https://arxiv.org/abs/2610.25553), [2610.20778](https://arxiv.org/abs/2610.20778) |

**Points of disagreement**: (1) "flip rate" has at least five denominators (single shuffle, cumulative over eight presentations, list reversal, relabelling, answer-preserving variants); (2) whether order invariance is a **guarantee by construction** (Prism-1, block-causal, Verdict, NDM) or an **empirical measurement** (AnyJev, 2610.35826); (3) whether the object of "consistency" is the name, the definition or the distribution (the core distinction of 2609.26758); the 30 sub-dimensions of §4.2 are an enumeration on top of these definitions.
### 1.4.7 "RLCD" Has at Least Four Meanings

| Usage | Meaning | Source |
| --- | --- | --- |
| TypeSafe | The "third post-training path" alongside RLHF and RLVR, "probabilities are optimized against outcomes"; **algorithm, reward and data are all unpublished** | [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer) |
| Proper-scoring reward with reasoning chains | OpenJev-RLCD: after each reasoning chain, read out the committed distribution and score it with a strictly proper scoring rule; a variance identity distinguishes "per-chain scoring" from "mixture scoring" (the latter = RLVR + a diversity reward); "calibrate first, then reinforce" | [2609.38850](https://arxiv.org/abs/2609.38850) |
| RLCD² (differential reward for reasoning quality) | StartLux AutoThink: the difference in proper score between the readouts before and after reasoning + a soft length penalty; only for models that generate reasoning | [2610.17309](https://arxiv.org/abs/2610.17309) |
| Umbrella term for five "RLCD algorithms" | UniJev compares Shaped RLCD, GRPO, CtR, RLCD-lite and Rewarding Doubt; its Table 1 lists the CE + Brier of Von / OneJev / Open-Jev and the CE of Kev / NanoJev as "direct gradient" controls | [2610.25784](https://arxiv.org/abs/2610.25784) |
| "The RLCD recipe released by open-source System One models" | SBERT2S1 refers to a score-function estimator with reward normalization (REINFORCE-style), 2.5–3.0 points below cross-entropy | [2610.02486](https://arxiv.org/abs/2610.02486) |
| "Reinforcement learning against proper scoring rules" | The benchmark paper's description of Laya: "trained with reinforcement learning against proper scoring rules, a recipe its developers call RLCD" | [2610.00346](https://arxiv.org/abs/2610.00346) |
| Stand-in | jevlike: "our open-source stand-in for TypeSafe's unpublished RLCD. We claim no equivalence"; in practice CE + 0.5·Brier | [mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike) |
| Equivalence theorem | NDM: "proper scoring rules applied directly when labels are known … reach the same optimum as the policy gradient of an RLCD-style reward without its variance" | [2610.25553](https://arxiv.org/abs/2610.25553) |
| Community naming | Model names such as `SFT + RLCD` (S²-MAS), `qwen3-0.6b-rlcd-decision`, `rlcd-modernbert-151m`, `Qwen-2.5-1B-RLCD`, with varying training details | [2610.27746](https://arxiv.org/abs/2610.27746), HF probe records |

**Points of disagreement**: when reading "RLCD" one must first ask three things: is there a reasoning chain, is the reward correctness or a proper score, and is it a policy gradient or a direct gradient. The conclusion of §6.1.3, "no positive evidence for RL on single-pass models", holds only for the one meaning "no reasoning chain + policy gradient".

### 1.4.8 How "Abstention / Fallback / Don't Know" Is Defined

| Definition | Content | Source |
| --- | --- | --- |
| Explicit option + separate calibration | NDM D6: the probability of "none of these" is calibrated separately; two mechanisms, declared (present among the options) and undeclared (absent from the options, relying on probability) | [2610.25553](https://arxiv.org/abs/2610.25553) |
| Probability band | TypeSafe cookbook: 0.30–0.70 maps to `uncertain` and goes to a human, with the explicit statement "The band is illustrative; it is neither a calibrated guarantee nor an optimized threshold"; confidence routing uses a global floor (0.6 in the example) + per-action-class thresholds | [consistency cookbook](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook), [confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing) |
| Abstention in the evaluation protocol | JevBench counts yes/no answers whose probability falls inside the band as "abstention = error", so Releasing the Inner Jev moves such answers to 0.801 / 0.199 | [2610.17205](https://arxiv.org/abs/2610.17205) |
| Execution of fallback rules | PFR test: whether the switch between the regular assignment and the fallback assignment is correct; Intern drops from 97.9% to 23.1% on TREC50, "even when the correct class is given explicitly" | [2610.19856](https://arxiv.org/abs/2610.19856) |
| Correct answer absent | Wrong substitutes are still accepted even when an explicit reject option exists (the arithmetic-dependent rejection bottleneck, 7% → 79% after thresholding, see §4.1); legal domain: after the correct verdict is replaced, generative LLMs still pick one in 38–86% of items, the most cautious decision model 30% | [2609.39496](https://arxiv.org/abs/2609.39496), [2610.29961](https://arxiv.org/abs/2610.29961) |
| Out-of-scope items | TypedBench: "out-of-scope items, whose true option is withheld"; abstention rate measured separately with / without "none of the above" | [2610.11392](https://arxiv.org/abs/2610.11392) |
| Answerable / unanswerable | SanSi computes ECE only on "answerable items", plus a stopper whose threshold is fitted on unlabeled requests | [2610.07730](https://arxiv.org/abs/2610.07730) |
| Silent hallucination | RSAJEV: "assigning higher confidence to unseen than to seen classes (AUROC 0.38)"; prototype retrieval restores "a calibratable abstention channel" | [2610.15742](https://arxiv.org/abs/2610.15742) |
| Certified abstention | SHIFT-JEV certifies the abstention threshold with Learn-then-Test; 2610.19811 replaces abstention with a conservative fallback action when there is no human hand-off and controls the false-omission risk | [2610.34329](https://arxiv.org/abs/2610.34329), [2610.19811](https://arxiv.org/abs/2610.19811) |
| Hand-off option ineffective | "neither an explicit nor a trained hand-off option closes this gap" (inherited input errors) | [2610.24929](https://arxiv.org/abs/2610.24929) |
| Ternary contract | true / false / unknown admission (§3.2) | [2610.10978](https://arxiv.org/abs/2610.10978) |

**Points of disagreement**: abstention is an **option** (NDM, TypedBench's NOTA condition), a **probability band** (TypeSafe, JevBench), a **separate risk score** (SHIFT-JEV, ufakzeka), or a **fallback action** (2610.19811, PFR). The four definitions correspond to four failures: the option is not chosen (legal 30%), the band is not calibrated (TypeSafe's own statement), the score does not transfer (jevlike out of domain), the fallback is not executed (Intern 23.1%).

### 1.4.9 Definitions at the Agent Layer

| Definition | Content | Source |
| --- | --- | --- |
| Record-state mismatch / claim laundering | The decision layer "follows the record instead [and] turns the agent's claim into the decision"; the record dominates in all 12 model-domain configurations | [2610.25947](https://arxiv.org/abs/2610.25947) |
| Three-level delegation | L1 isolated questions, L2 step-level over recorded trajectories, L3 controlling a running agent; "confidence thresholds fitted on trajectories"; a non-inferiority test as the acceptance criterion | [2610.21412](https://arxiv.org/abs/2610.21412) |
| Controller | The decision model as agent controller shows "good judgment, bad advice" (ranking AUROC 0.78, but mean "done" probability 0.50 while 87% actually pass, see §4.2) | [2610.24649](https://arxiv.org/abs/2610.24649) |
| System Switch | When the fast model should stop and hand off to the reasoning model: defer the most uncertain 30% by confidence | [2610.09683](https://arxiv.org/abs/2610.09683) |
| Fast selector | The decision model "over a state that a reasoning model has computed and checked" | [2610.24929](https://arxiv.org/abs/2610.24929) |
| Can it be left to System 1 | The same typed request sent to 30 models, four task groups + 138 closed-loop environments | [2610.21244](https://arxiv.org/abs/2610.21244) |
| Quadruple / joint reliability | Controlled tests of rule transfer, joint reliability and information use; "equivalent rewrites have opposite task-level effects" | [2610.30045](https://arxiv.org/abs/2610.30045) |
| Two time scales | A slow teacher writes instructions in a paused environment, a fast student executes while running; under a "live clock" the faster model overtakes | [2610.20665](https://arxiv.org/abs/2610.20665) |
| Decision-level continual learning | Typed feedback (accept / revoke) becomes bounded causal state | [2610.31521](https://arxiv.org/abs/2610.31521) |

**Points of disagreement**: whether "correct" at the agent layer means **isolated accuracy** (L1), **step-level agreement** (L2) or **task success / cost / clock** (L3, live clock); the conclusion of §5.2, "faster decisions ≠ a better agent", is exactly the manifestation of these three definitions not agreeing.

### 1.4.10 Summary Table of Disagreements and "What We Must Answer Before Defining the Problem"

| Dimension | Definition A | Definition B | Definition C | Consequence |
| --- | --- | --- | --- | --- |
| Decision model | Interface (TDM / LDM) | Property contract (eight NDM items, readout stability) | Use (gate / selector / can it be left to System 1) | Decides whether the evaluated object is "the model" or "model + threshold + code" |
| Request | Three primitives + limits | Quadruple (state, instruction, criteria, gold) | Natural-language candidates / action space | Decides the input form of the D3 rule language |
| Confidence | Distribution-shape statistic | top-1 probability | Learned risk score / two quantities | Thresholds do not transfer across different option counts |
| Calibration | Population frequency matching (10/15 equal-width/equal-mass) | Coherence + axioms | Error under deployment policy / risk budget | ECE numbers not comparable across papers |
| Consistency | Single-shuffle flip | Cumulative failure set / answer-preserving variants | Definition-level flip | "Unchanged accuracy" hides per-item instability |
| Order / IIA | Empirical flip rate | Guarantee by construction (Luce) | Readout stability | Whether hybrid backbones can satisfy the constructive guarantee (§1.3) |
| RLCD | Unpublished | Proper-scoring reward with reasoning chains | Direct-gradient stand-in | The conclusion on "whether RL helps" depends on the meaning |
| Abstention | Explicit option (calibrated separately) | Probability band | Risk score / fallback action | Four different failure modes |
| Multiple questions | Isolation (NDM D5) | Jointly beneficial (pplx) | Read dispersion after decomposition (2610.33258) | Semantics of fan-out and decomposition |
| Agent correctness | Isolated accuracy | Step-level agreement | Task success / cost / clock | "Faster ≠ better" |

Before we write our own problem definition, at least six of these disagreements must be fixed first: (1) whether "decision model" is defined by interface or by contract; (2) whether confidence uses top-1 or a distribution statistic, and whether it should be separated from "self-knowledge"; (3) which binning calibration uses, whether it includes coherence, and whether it is measured in isolation or under the deployment policy; (4) which denominator the flip rate uses, and whether order invariance should be a guarantee by construction or an empirical measurement; (5) whether abstention is an option, a band, a score or an action; (6) which meaning the word "RLCD" has in our documents. This section does not fix any of these; it only points out the evidence and failure cases already in the literature for each choice.
