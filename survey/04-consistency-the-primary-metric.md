# 4 · Consistency: the primary metric, its denominator, and failure under symbolic interventions

> Per P1 in §2.2, **the consistency rate is the primary metric and accuracy is the declared floor**. This chapter is the full body of evidence for that primary metric, in two halves.
>
> §4.1 (the former D2 dimension) is consistency under **symbolic interventions**: rules, negation, arithmetic/time, fallback options, instruction hierarchy, adversarial context. Its core finding is that the bottleneck is not in "reading" but in "doing": policy modifications are read out correctly but executed in only 22%–72% of cases. §4.2 (the former D4 dimension) splits "numerical consistency" into **30 sub-dimensions** (A same-input stability / B option-representation dependence / C logical coherence / D uncertainty semantics / E input-content sensitivity / F interface and actions), each with a quantifiable definition and the existing evidence.
>
> This must be read together with §2.1.8: **the "consistency rate" of the same model is 99.83% under the byte-level rerun protocol and 53.7% under the answer-preserving adversarial variant protocol, a gap of 46 percentage points**. So before the denominator is fixed, "consistency rate" is not a metric; and the only denominator with business meaning (the equivalence classes the business declares) has never been defined by anyone.

## 4.1 D2 symbolic instruction following: rules, negation, arithmetic/time, fallback, hierarchy and adversarial context

> Protocol: the model receives a **symbolic** instruction (rule, threshold, condition, hierarchy, fallback rule); can it execute it faithfully in a single forward pass? Difference from D1: D1 cares about "whether the examples / definitions are used"; D2 cares about "given a rule that has been understood, is the decision produced according to the rule". Difference from D3: D3 cares about "how to write rules so that they get executed".

### 4.1.1 Upstream baseline: rule following in generative LLMs

| Fact | Source |
| --- | --- |
| RuLES: across 14 simple text scenarios, LLMs' ability to follow "do not do X" rules can be bypassed by jailbreaks; programmatic evaluation is needed | [2311.04235](https://arxiv.org/abs/2311.04235) |
| RuleArena: real rules in three domains (airline baggage fees, NBA trades, tax law) require long context, logical reasoning and exact arithmetic, beyond first-order logic | [2412.08972](https://arxiv.org/abs/2412.08972) |
| **Scaled rule-following failure**: none of 126 leading model variants can count accurately above a model-dependent, grammar-sensitive counting capacity threshold; the failure is abrupt and persists as scale and inference time increase | [2605.02028](https://arxiv.org/abs/2605.02028) |
| Verifiable instruction following overfits to a small set of constraints and generalizes poorly to unseen constraints (IFBench); RLVR reward-hacks (constraint satisfaction rises, answer quality falls; CALIF corrects this) | [2507.02833](https://arxiv.org/abs/2507.02833), [2610.19525](https://arxiv.org/abs/2610.19525) |
| WISE: rephrasing the same operational requirement changes the compliance rate substantially; five "avoid/exclude" phrasings fall below the positive baseline | [2610.05278](https://arxiv.org/abs/2610.05278) |
| Instruction hierarchy: non-adversarial benign conflicts are also common; failures decompose into three classes: "identifying the relevant instruction / resolving the conflict / reasoning correctly but outputting a violation" | [2604.09075](https://arxiv.org/abs/2604.09075), [2606.07808](https://arxiv.org/abs/2606.07808) |
| **Silent scope omission (SSO)**: models apply the general rule but quietly drop nested exceptions and counter-exceptions; NormBench, 2,290 Chinese and English statutory clauses | [2606.08932](https://arxiv.org/abs/2606.08932) |
| The **constraint tax** on small models: <3B models lose answer accuracy and executable accuracy under structured-output constraints; constrained decoding removes structural errors but exposes scale-dependent semantic gaps | [2605.26128](https://arxiv.org/abs/2605.26128), [2609.23742](https://arxiv.org/abs/2609.23742) |
| State tracking needs "reasoning written out in the moment": on a lock-state task, most of the violation reduction comes from reasoning at the moment of action; retained earlier reasoning contributes little, and neither filler text nor an accurate state table can substitute for it | [2610.25760](https://arxiv.org/abs/2610.25760) |

**Implication**: generative LLMs can compensate for part of rule execution by writing out intermediate steps; a single-pass decision model has no such route, so D2 failures will be "harder".

### 4.1.2 Evidence on decision models: grouped by failure type

#### 4.1.2.1 Reading right, acting wrong (composition failure)

**Reading Right, Acting Wrong** ([2610.18579](https://arxiv.org/abs/2610.18579)) is the core diagnosis for D2:

- On the six most accurate systems, **73%–85% of decision errors occur on states where "every probed fact is answered correctly"**, and this share grows as accuracy rises.
- 14 "capable" fast systems all err on **the same 141 states** (random expectation: 0).
- On generated states where "the probes suffice to determine the action", models that can read every fact correctly and can decide perfectly from the facts **drop 20–45 points as soon as they have to do both things from the trajectory at once**; using their own fact answers recovers 15–28 points; **composing the action from the facts in code reaches 0.96–1.00**.
- On real states "the decision itself is often missing": on ALFWorld, "state the next sub-goal" gives JEV +16 points, while any block of facts gives at most +5.
- Deleting history collapses accuracy where "early observations matter"; **policy modifications are read out correctly but executed in only 22%–72% of cases**; calibration error 2.6%–26.6%.
- Decoder fast systems have latency 27–225 ms, likelihood readout from open-source LMs 317–947 ms, reasoning models 2.3 s.

**Conclusion**: the bottleneck of single-pass models is the **composition** "facts → action", not "reading". This directly supports TypeSafe's own design principle ("ask independent questions together, compose in code") and the direction of D3 (primitives + composition in code).

#### 4.1.2.2 Arithmetic, time and negation

| Evidence | Numbers | Source |
| --- | --- | --- |
| The vendor's zigzag: unreliable counting, dates read as text | — | [jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13) |
| MathQA 17.7 points below the frontier median, below all 19 LLMs | — | [2610.11978](https://arxiv.org/abs/2610.11978) |
| In medicine, numerically driven tasks are clearly weaker than text-driven tasks | — | [2610.18529](https://arxiv.org/abs/2610.18529) |
| DecisionPivot: on 2,400 binary contrast pairs, Perplexity Decider **gives the higher yes probability to the positive item in 92.3% of pairs, yet classifies both sides correctly in only 74.1% of pairs**; pairwise accuracy from difficulty 1→3 goes 87.7%→57.4% (Instant 90.7%→65.3%); "arithmetic and temporal contrasts expose large performance gaps"; API chat models put top probability ≥0.99 in 63–93% of cases | **Ranked right, classified wrong** is the typical shape of the arithmetic/time class | [2610.28522](https://arxiv.org/abs/2610.28522) |
| Kev's date-fact supplement (code computes the day count and writes it into the state) lifts the deadline-policy questions 0.80→0.90 | Direct empirical support for "hand arithmetic to code" | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| Negation complementarity: Jev's mean absolute violation of P(A)+P(¬A)=1 is 0.064; Qwen3.8-27B first-token readout 0.293, verbalized readout 0.122; 19.0% of Jev's pairs deviate by >0.1, and the violation is ~5× its repeat-noise floor; **the mean probability of a single-label statement is 0.380, whereas consistency requires 1/3** | Negation is not free | [2609.33209](https://arxiv.org/abs/2609.33209) |
| TypedBench has a dedicated negation suite (Suite G) and a severity-ladder suite (F) | — | [2610.11392](https://arxiv.org/abs/2610.11392) |
| NumericJev: refines numerical ranges recursively with a multi-way decision tree; a 10-way tree needs only two rounds for a 100-value grid; 2.93 pp higher than "choosing directly from a candidate list that contains the correct answer"; range-normalized MAE 1.84% vs 5.18% for direct selection | Numerical output can be built in code from a "range selection" primitive | [2609.28587](https://arxiv.org/abs/2609.28587) |
| Choice2Seq: Jev's selection accuracy on arithmetic / lexical retrieval is 97.1% / 99.5%, but **serial construction retains only 33.0% / 2.1%**; restricting local options to the characters supported by the candidates, and explicit position indices, improve this | "Picking the right answer" and "constructing the answer step by step" are two different capabilities | [2610.16191](https://arxiv.org/abs/2610.16191) |
| Same-number reference swaps: cells in financial statements with the same value but different roles; Jev as an evidence verifier lets wrong-role references through and also rejects valid alternative references; explicit column labels help | Numerical matching ≠ role identification | [2610.08675](https://arxiv.org/abs/2610.08675) |
| Sensitive to irrelevant numerical information | — | [2610.19619](https://arxiv.org/abs/2610.19619) |

#### 4.1.2.3 Refusal, fallback and "the correct answer is absent"

| Evidence | Numbers | Source |
| --- | --- | --- |
| **The arithmetic-related refusal bottleneck**: answer-present accuracy 99%, correct refusal only 7%; this holds across number magnitude, operation depth, context and refusal label; **native Boolean verification reaches 99% exact match on the same answer-absent arithmetic items**, showing "can verify but cannot refuse"; choosing one threshold on a separate dev set takes the refusal rate 7%→79% while retaining 97% answer-present accuracy, with no retraining | Refusal is a readout-layer/threshold problem, not a capability problem | [2609.39496](https://arxiv.org/abs/2609.39496) |
| **Lost in the Fallback**: under non-adversarial conditions, the fallback rule itself makes models fail: on TREC50, Intern drops from 97.9% on regular assignment to 23.1% on fallback assignment, and this persists even when the correct class is given explicitly; **logically equivalent phrasings of the fallback rule cause large divergence in individual decisions while overall accuracy barely changes** | A fallback rule is a kind of "symbolic instruction" that is understood but not executed | [2610.19856](https://arxiv.org/abs/2610.19856) |
| Refusal policy transfer: a Jev policy calibrated on DBpedia rejects 69.3% of covered inputs on Emotion, and the reverse policy loses detection entirely; with 10 intent candidates Laya detects 99.0% of out-of-domain queries but rejects 48.8% of covered queries | Refusal thresholds do not transfer across tasks | [2610.03387](https://arxiv.org/abs/2610.03387) |
| Law: when the correct precedent is absent, generative LLMs still pick one on 38–86% of items, the most cautious decision model on 30%; on CaseHOLD, decision model 88.1% vs best LLM 88.2%, at 1/55 the cost | Decision models' abstention is **relatively** better but far from reliable | [2610.29961](https://arxiv.org/abs/2610.29961) |
| Medicine: most models can neither recognize that the correct answer is missing nor use the optional abstention | — | [2610.18529](https://arxiv.org/abs/2610.18529) |
| Memory retirement gate: Jev never retires wrongly on 141 same-session non-changes, but **retires too early**: the binary gate retires on 39.2% of "merely hinted" changes; a three-way decision brings this down to 15.5% but at a 15.3-point detection cost; cascading and simply raising the threshold cannot make the distinction | Distinguishing "established vs merely hinted" with a binary gate needs a third option | [2610.15710](https://arxiv.org/abs/2610.15710) |
| Self-knowledge: with no answer-relevant information, Jev still gives a salient option up to 0.80; on news outside its knowledge boundary, confidence exceeds accuracy by 0.21–0.33 and recalibration cannot fix it; but **targeted yes/no questions** reach AUROC 1.00 for "is the outcome already settled" and 0.95 for "is the evidence sufficient" (confidence itself 0.85) | "Asking a question about the evidence" is more reliable than "looking at confidence" | [2610.01006](https://arxiv.org/abs/2610.01006) |

#### 4.1.2.4 Instruction hierarchy and adversarial context

| Evidence | Numbers | Source |
| --- | --- | --- |
| Decision hijacking (InjecAgent, 510 cases): malicious content moves action probabilities but rarely makes Jev pick the attacker's target; override markers reduce the effect; an adaptive attack raises the success rate of new verification calls from 1.8% to 3.5%, correlated with small initial decision margins | Direct injection has limited effect on Jev | [2609.28613](https://arxiv.org/abs/2609.28613) |
| **JevOut**: within 64 target evaluations, short "background/procedural" context additions steer 61.4%–73.2% of initially correct decisions to a predetermined wrong option; 91.6% are judged by humans as natural and containing no decisive evidence; affects high-confidence decisions and transfers across models | **Natural context** is far more dangerous than direct injection | [2609.30243](https://arxiv.org/abs/2609.30243) |
| **JevAdvBench**: 862 items, 12 black-box attacks, flipping 46.3% of Jev's correct decisions (reruns flip only 0.17%); **flawed arguments containing no commands flip 77.2%**, close to direct injection at 92.0%; eight open-source TDMs 34.0%–51.7%; among decisions still executed under a 0.8 threshold, 23.5% are wrong | Thresholds cannot block attacks | [2609.31142](https://arxiv.org/abs/2609.31142) |
| **Option-channel attack**: seven open-source models as guards, allow/block accuracy 36%–72% (random 50%); six policy-irrelevant lines of server log raise the fail-open rate from 0% to 63%; **giving the permissive option a misleading name (definition and judged text unchanged) makes the four models that place labels in the input fail open 93%–100%**; all defenses are defeated; decisions flipped by the attack are no less confident than the original decisions | Option names are an attack surface (same root as D1 "names override definitions") | [2610.12292](https://arxiv.org/abs/2610.12292) |
| JevProbe: 2,273 tests over 228 real Jev applications, **81.5% show decision flips**, 98.6% of which lead to potential downstream safety impact | Reachability at the application layer | [2610.18612](https://arxiv.org/abs/2610.18612) |
| DICE: bounded substitutions in each of three adapter outputs (state extraction, question generation, output interpretation) can change the final decision, while Jev and the API response itself are not under the attacker's control | Interface boundaries are an attack surface | [2610.14404](https://arxiv.org/abs/2610.14404) |
| Poisoned into Action: an execution-aware protocol, 1,659 Jev-1.13 calls; under natural retrieval the standalone payload arrives in all 60 trials | Poisoned evidence reaches the action through retrieval | [2610.15537](https://arxiv.org/abs/2610.15537) |
| Same attack, different judges: 50 attack variants in 13 families, the first controlled comparison across Jev, 5 GPT/GLM judges, Llama Guard 3 and Prompt Guard 2 | — | [2610.17820](https://arxiv.org/abs/2610.17820) |
| **TrustJev**: protected policy scoring + bounded evidence correction (the correction budget computed from the trusted policy and the candidates); a 0.6B implementation achieves the highest Balance against 14 baselines on three datasets (authentication, instruction hierarchy, executable authorization rules); on the authorization benchmark 95.77% of sources answer all 32 attacks correctly (strongest comparison 80.98%) | **Architecturally separating "policy authority" from "untrusted evidence"** is currently the only structural defense | [2610.34826](https://arxiv.org/abs/2610.34826) |
| Calibration and deferral for prompt-injection detection: LLM judge AUROC 0.897, Jev 0.871, Prompt Guard 2 86M 0.757; under distribution shift the allow/block/defer policy needs separate calibration | — | [2610.20907](https://arxiv.org/abs/2610.20907) |
| Safety decisions: high overall accuracy and low mean calibration error can mask "high-confidence misjudgment as safe within specific attack groups"; under a strict miss limit, automatic allow is rare, and choosing allow/block thresholds separately increases automation mainly through more blocks | Report per attack group | [2609.33401](https://arxiv.org/abs/2609.33401) |

#### 4.1.2.5 Rule transfer and wording

- "Which Differences Matter" ([2610.30045](https://arxiv.org/abs/2610.30045)) uses **executable arithmetic rules** to test "rule transfer, joint reliability, information use" separately: adaptation gain increases with the answer consistency of the nearest sources; fully conflicting quadruples give small gains whose sign flips across source splits; **equivalent rewrites have opposite task-level effects**; an improvement from an external table does not prove that the model used the table's values and mapping.
- Certo ([2609.37832](https://arxiv.org/abs/2609.37832)): a Qwen3-4B joint scorer (state + rule + candidates read together) has rule-sensitivity recall@1 of 1.00; switching to cacheable independent encoding (candidates encoded once and reused, about 5× cheaper with 77 candidates) **loses rule sensitivity significantly** (the abstract says 1.00 → 0.24; the number at that point in the full text is masked, so the abstract is taken as authoritative), and shortlist+rerank cannot recover it; targeted counterfactual supervision recovers it on a held-out synthetic rule task, but the authors **did not isolate "whether the prediction depends on the given rule"**.
- Tables: decision models match LLMs on row classification / fact verification / anomaly detection and are cheaper, and three are more robust to question phrasing, **but no model is robust to how the table is organized**; for every model at least one third of row decisions change with the format ([2610.19536](https://arxiv.org/abs/2610.19536)).
- Graph tasks: accurate adjacency identification does not guarantee broader structural correctness ([2610.06354](https://arxiv.org/abs/2610.06354)).

#### 4.1.2.6 Decision models as rule judges

- Across nine panels and seven benchmarks, Jev and Decider lag significantly behind flash-tier LLM judges in at most 6 of 27 comparisons, while the latter are 16–357× more expensive and 5–350× slower; **they err in the same places** ([2609.29769](https://arxiv.org/abs/2609.29769)).
- Agent trajectory safety: on the JEV benchmark, mean positive-class F1 of 77.8 vs 74.1 for the strongest generative model ([2609.34862](https://arxiv.org/abs/2609.34862)).
- CALM bias tests: all eight TDMs show bias on 3–8 of 12 items; **an emotional tone pulls the typical TDM's accuracy from 99% to 42%**; all eight change their verdict when the answer positions are swapped (2026 LLM judges barely change); good calibration does not prevent bias ([2610.18122](https://arxiv.org/abs/2610.18122)).
- First-token readout **overestimates** position bias: three Qwen3 judges do not begin with the verdict token on 12%–49% of pairs, and forced readout returns "whichever appears first" ([2610.00054](https://arxiv.org/abs/2610.00054)). This is a caution for reproductions that "read out from logits".
### 4.1.3 Which work solves which class of problem (the D2 mini-matrix)

| Problem class | Diagnostic work | Mitigation work | Status |
| --- | --- | --- | --- |
| Facts→action composition | Reading Right | Composition in code (same paper) | **Diagnosed clearly; the solution is in the interface, not the model** |
| Arithmetic / time | The vendor's zigzag, DecisionPivot, MathQA, Choice2Seq | Kev date facts, NumericJev range tree, "arithmetic in code" | The solution is an engineering convention; no model-side breakthrough |
| Negation / complementarity | 2609.33209, TypedBench G | none | No mitigation |
| Refusal / fallback | 2609.39496, Lost in the Fallback, 2610.03387, law/medicine/memory gate | Dev-set threshold (7%→79%), three-way decision, yes/no questions about the evidence | Threshold-level mitigation; **fallback semantics not being executed** has no solution |
| Natural-context attacks | JevOut, JevAdvBench, option channel, JevProbe, DICE, Poisoned | TrustJev (structural), override markers (weak), reporting per attack group | Only TrustJev is a model-side structural solution |
| Rule transfer / wording | 2610.30045, Certo, tables, WISE | Counterfactual supervision (Certo, not isolated) | No general solution |
| Judge bias | 2610.18122, 2610.00054 | Test before use | No mitigation |
| Hierarchy / exceptions | NSHA, white-box diagnosis, NormBench (generative) | none | **Zero research on decision models** |

### 4.1.4 D2 blind spots

1. **The execution rate of the three "meta-rules" (fallback / exception / hierarchy) on single-pass models**: Lost in the Fallback tested only fallback; "nested exceptions silently dropped" (SSO) and "conflicting instructions from multiple sources" have no benchmark on decision models.
2. **A training-side solution to "reading right, acting wrong"**: Reading Right's solution is composition in code; nobody has tried to train a model to compose within a single pass (perhaps it should not be done at all), and nobody has quantified the boundary of "which compositions can be learned and which must be handed to code".
3. **A training objective for negation and complementarity**: 2609.33209 gives the measure; no work has used P(A)+P(¬A)=1 as a training constraint.
4. **A general threshold for refusal**: the threshold in 2609.39496 is task-specific; 2610.03387 proves it does not transfer. "Estimating candidate-set coverage" has not been defined as a problem in its own right.
5. **An evaluation protocol for defenses against natural-context attacks**: JevAdvBench and the option-channel attack prove that "confidence does not change"; TrustJev is only on three datasets; there is no result evaluating TrustJev on JevOut / JevAdvBench.
6. **An "executability grading" of rules**: which rules are doable in a single pass (lookup, matching, single-hop comparison) and which are not (counting, two or more state updates, arithmetic); only 2610.24929 gives a proxy measure, "how many thinking tokens a reference LLM needs" (Jev answers 97.5% of single-pass-solvable items correctly, the rest only 74%).
## 4.2 D4 consistency: split into 30 definable, measurable sub-questions

> Protocol (per the latest discussion): D4 is not just the four items "repetition, order, wording, calibration"; it has to **define and understand the question itself**. This section lists, one by one, the factors that appeared in the literature of the past two months and that make "the same business judgment" return different probabilities; for each item it gives the definition, the way to measure it, the existing evidence and the existing mitigations, and finally gives the matrix and the blind spots. This section is an exploration of the problem definition, not a solution.

### 4.2.1 Why Split It

Jev's selling point is "probabilities that can be thresholded, composed and audited". But the evidence below shows: **for the same fact and the same rule, the probability changes with 25 factors unrelated to the business**. These changes are often invisible in accuracy: 2610.35826 found that after Jev was given 8 option orders the accuracy changed by less than 2 percentage points, but the cumulative failure set grew by 27–29%; 2609.27678 found that "corrections and regressions cancel each other out, accuracy is unchanged but the decisions changed". So the D4 measurement must be **decision-level, paired, item by item**, not aggregate accuracy.

### 4.2.2 Sub-Dimension Checklist

Format for each item: **Definition** → **Measurement** → **Evidence** → **Existing mitigation** → **Status**.

#### A. Stability on the Same Input

**A1 Repeatability (same input, same configuration, multiple calls)**
- Definition: the variance of the output probability for completely identical requests.
- Measurement: intraclass correlation coefficient ICC; top-1 flip rate; absolute probability difference.
- Evidence: 24 cultural-values questions, 288,000 answers, ICC 0.997 ([2609.36399](https://arxiv.org/abs/2609.36399)); Jev's negation inconsistency is about 5 times its repetition noise, which shows that the repetition noise itself is small ([2609.33209](https://arxiv.org/abs/2609.33209)); "consistent answers also preserve errors": repeated wrong answers account for most of the observed errors ([2609.27678](https://arxiv.org/abs/2609.27678)).
- Mitigation: none needed; but high repeatability does not equal correctness, see A2–A4.
- Status: **solved and misleading**: high repeatability makes people mistake it for robustness.

**A2 Numerical Precision / Quantization / Merge Drift**
- Definition: the change of top-1 for the same weights under different precision, quantization or after merging.
- Measurement: proportion of top-1 changes; maximum probability deviation.
- Evidence: Kev's server-side bf16 differs from fp32 probabilities by at most ~0.03 (GPU) / 0.05 (Mac), about 1 top-1 change per 300 questions ([Kev README](https://github.com/jaredpalmer/kev)); Chinese Decision's merge and Q8_0 quantization each change 0.4–1.1% of top-1, the aggregate metrics are almost unchanged ([2610.23170](https://arxiv.org/abs/2610.23170)); Laya-typed's default CUDA path produced 5 paragraph swaps, and the probability shifts disappeared after an FP32 rerun ([2610.14631](https://arxiv.org/abs/2610.14631)); the damage from 4-bit quantization (RTN/GPTQ/AWQ) varies with model size and did not push any configuration into the passing range ([2610.00025](https://arxiv.org/abs/2610.00025)).
- Status: **measurable, small in magnitude, but flips at the threshold boundary**.

**A3 Version / Model Drift**
- Definition: the change of decisions for the same business rule across model versions or across models.
- Evidence: 2610.35826 covers two Jev versions, 12 reproductions, 6 LLMs; the tree SemTree compiled for judge A drops from 67.70% to 47.87% when moved to judge B ([2610.13999](https://arxiv.org/abs/2610.13999)); the rankings in Decision Index 0.4 fluctuate across versions ([Decision Index](https://systemonemodels.org/examples/articles/jev-decision-index/)).
- Status: **almost no systematic research**; critical for our "self-trained model + business rule library" (whether rules must be recompiled with the model).

#### B. Dependence on Option Representation

**B1 Option Order / Position**
- Definition: whether the decision changes after the option order is shuffled.
- Measurement: flip rate of one shuffle; expansion of the cumulative failure set across 8 presentations; residual after cyclic-shift averaging.
- Evidence: row 8 of the official jaggedness page admits it ([jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)); Archer Hume's probe: card placed first 12/16, placed last 16/16 ([architecture](https://archerhume.com/posts/jevs-architecture-unmasked)); after reordering, Jev's accuracy changes <2 pp but the cumulative failure set grows +27–29%, the gain from voting is limited, "unanimously agreed answers are also often wrong" ([2610.35826](https://arxiv.org/abs/2610.35826)); for Qwen3-8B / Gemma 4 12B letter readout, one shuffle changes 20.0% / 11.9%, the published decision fine-tuning still changes 9.1%; changing only the letters without moving positions changes 9.1% / 14.0%, moving only positions without changing letters changes 12.0% / 22.7%; training on shuffled data plateaus ([2610.22066](https://arxiv.org/abs/2610.22066)); reversing the order changes 30% of Laya's answers ([2610.02267](https://arxiv.org/abs/2610.02267)); order mainly changes the answer when the model is uncertain about the top few, yet list-style answers look confident ([2610.18233](https://arxiv.org/abs/2610.18233)).
- Mitigation: block-causal attention ([2610.01601](https://arxiv.org/abs/2610.01601)); Prism-1's position- and opponent-independent scoring (zero flips); Runoff's two stages (zero flips, cyclic-average residual 9.3%); AnyJev rotation + label-prior correction; PACT has the lowest position bias ([2609.35865](https://arxiv.org/abs/2609.35865)); Kev's `/permute` endpoint.
- Status: **clearly defined, mature measurement, structural mitigations exist**; but the mitigations all target Choice, and the position problem of Score (B5) is counted separately.

**B2 Option-Set Dependence / Independence of Irrelevant Alternatives (IIA)**
- Definition: whether the log-odds between the correct option and the strongest wrong option change after adding an option that is neither correct nor the strongest competitor.
- Measurement: ratio of the root-mean-square systematic shift of the log-odds (nats) to the between-run variation.
- Evidence: Jev 1.13, pre-registered, 299,463 calls: every added option moves the log-odds, 0.20–0.52 nats, 1.2–3 times the between-run variation, even when the new option takes only 0.1% probability; the shift is directional (options that resemble the wrong answer draw probability from it, +0.10 nats; paraphrases of the wrong answer get less than half of its 1/3); it grows with log(number of options), about 1 nat at 255 items; out-of-domain padding pushes the odds away from the correct answer; **multiple questions packed into one call do not affect each other (deviation <0.001)**; independent per-option Noul removes the dependence but accuracy is 8.7 points lower ([2610.16655](https://arxiv.org/abs/2610.16655)); Archer Hume: an irrelevant option moves the log-odds +0.38→+0.11, in all 10 blocks ([architecture](https://archerhume.com/posts/jevs-architecture-unmasked)).
- Mitigation: Prism-1's opponent independence; JevCascade's menu curation (0.8B on a curated 5-candidate menu 95.4% vs 4B on all 150 labels 80.0%, [2610.07716](https://arxiv.org/abs/2610.07716)).
- Status: **pre-registered evidence and a formal definition exist**; "the probability is only valid relative to its option list" should become part of the interface documentation.

**B3 Dependence on Option Names / Definitions**
- Definition: how much the decision changes when option names are changed or definitions are removed or altered.
- Evidence: see D1 §3.1.2.2 for details: replacing option names with meaningless codes takes AUC 93.8→23.2 ([2609.26758](https://arxiv.org/abs/2609.26758)); definitions can be removed (0.8487→0.7971), contradictory definitions 0.8511→0.2281 ([2610.02586](https://arxiv.org/abs/2610.02586)); giving the permissive option a misleading name raises the guard's false-allow rate to 93–100% ([2610.12292](https://arxiv.org/abs/2610.12292)); putting the literal meaning of an idiom into the option list draws away 65–96% of the remaining errors ([2610.22526](https://arxiv.org/abs/2610.22526)).
- Status: **consistent conclusion: option names are the strongest lever and the largest attack surface**.

**B4 Probability Allocation under Multiple Correct Options**
- Definition: whether probability is distributed fairly among several options when they are all correct.
- Evidence: three decision models, even when they rank all correct items above all distractors, still put at least one correct item below 1/n in 28–50% of the lists; five identical correct items differ in probability by 17–79 pp; **a threshold cannot identify the correct set** ([2610.29217](https://arxiv.org/abs/2610.29217)).
- Status: **defined, measured, no mitigation**. Multi-label business rules ("which of the following clauses are triggered") must be split into multiple Nouls.

**B5 Ordinal Scale Compression / Tendency toward the Middle**
- Definition: in Score-type questions, decisions concentrate on fewer effective levels than the gold standard.
- Measurement: effective label utilization (the proportion of the gold standard's effective support covered by the decisions); TVD.
- Evidence: JEV 1.13 on 6,400 ANLI questions reaches 74.95% accuracy, yet gives 38.8% of predictions and 51.3% of errors to Neutral, while the gold standard is nearly balanced; on 36 ordinal datasets it uses only 60–76% of the effective gold support, versus 87–102% on 4 nominal tasks; finer scales worsen the compression; random order weakens but does not remove it; widening the level spacing raises accuracy but does not restore utilization; larger models recover inconsistently; targeted training can mitigate it ([2609.38827](https://arxiv.org/abs/2609.38827)).
- Status: **defined, measured, a training mitigation direction is given**. Business scoring rules on a "1–10 scale" must take this into account.

**B6 Question-Form Equivalence (Noul / Choice / Score / Packed / Separate)**
- Definition: whether the probabilities agree when the same judgment is expressed as Noul, Choice, Score, or as several questions packed together / asked separately.
- Evidence: for Jev the single-label probabilities of "the label is X" over the three options sum to 1.14 on average ([2609.33209](https://arxiv.org/abs/2609.33209)); normalized per-option Noul preserves higher accuracy than Choice scoring (medicine, [2610.18529](https://arxiv.org/abs/2610.18529)) but is 8.7 points lower on intent classification ([2610.16655](https://arxiv.org/abs/2610.16655)): the direction is **inconsistent**; pplx-decider asking several facets of the same message jointly gets 68.09 vs 67.75 separately, and joint asking over independent passages drops slightly by 0.2–0.4 ([pplx-decider](https://huggingface.co/perplexity-ai/pplx-decider-v1.2)); Kev provides a "packed vs separate" comparison tool.
- Status: **the evidence contradicts itself and depends on the task**; "which primitive a business rule should be expressed in" has no general answer and is a quantity that D3 primitive design must measure.

#### C. Consistency of Logic and Decomposition

**C1 Hierarchical / Decompositional Coherence**
- Definition: whether asking the fine label directly agrees with the distribution reconstructed from "ask the coarse class first, then the fine label".
- Measurement: total variation TV at the coarse-class level; change in accuracy and ECE after reconstruction.
- Evidence: 72,000 questions: Jev's TV 0.219–0.349, Laya 0.424–0.689; on CLINC150 reconstruction changes Jev's accuracy by −22.9 pp [−24.9, −20.9] and Laya's by +21.3; on MASSIVE Laya's accuracy +9.2 but ECE 0.046→0.124 ([2609.33971](https://arxiv.org/abs/2609.33971)); SemTree's multi-step tree is on par with asking directly (67.70 vs 68.23, [2610.13999](https://arxiv.org/abs/2610.13999)).
- Status: **defined, clearly measured, the direction differs by model**; the "rule decomposition" of D3 must answer "are the probabilities still usable after decomposition".

**C2 Probability Axioms such as Negation / Complement / Conjunction**
- Definition: P(X)+P(¬X)=1, exclusive labels sum to 1, a conjunction is not larger than its single terms.
- Evidence: Jev's negation pairs deviate by 0.064 on average (CI 0.055–0.072), Qwen3.8-27B first token 0.293, verbalized 0.122; Jev's violation is about 5 times the repetition noise and concentrates where it is uncertain; Qwen rejects both the statement and its negation in 196/480 pairs ([2609.33209](https://arxiv.org/abs/2609.33209)); Jev gets famous probability puzzles right every time but violates the same rule every time on adapted versions; 54% of 15,000 answers on 30 conjunction tasks violate it ([2610.19619](https://arxiv.org/abs/2610.19619)).
- Mitigation: detectable without labels (axiom tests).
- Status: **defined, label-free measurement exists, no training-side mitigation**.

**C3 Invariance under Equivalent Wording**
- Definition: whether a logically equivalent rewording of the rule or question changes the decision.
- Evidence: "decision services change their answer across equivalent wordings more often than across repetitions of the identical text" ([2610.30045](https://arxiv.org/abs/2610.30045)); logically equivalent formulations of fallback rules produce substantive disagreement ([2610.19856](https://arxiv.org/abs/2610.19856)); 21 rewrites of table tasks: three decision models are robust to the question wording, **none is robust to the table organization**, and for every model at least 1/3 of the row decisions change with the format ([2610.19536](https://arxiv.org/abs/2610.19536)); on medical tasks Jev keeps strong consistency under changes of question format ([2610.18529](https://arxiv.org/abs/2610.18529)).
- Status: **clearly defined; the evidence shows "question wording" is more stable than "data format"**.

**C4 Framing Effects and Cognitive-Bias Manipulation**
- Definition: whether the probability changes when only the presentation (gain/loss framing, anchoring, irrelevant numbers) changes and the facts do not.
- Evidence: at the level of the selected answer Jev avoids most human biases, but it is sensitive to irrelevant numerical information and option order, and several bias manipulations significantly change the returned probability even when the selected answer is unchanged ([2610.19619](https://arxiv.org/abs/2610.19619)); the effect of gain/loss framing on high-stakes LLM advice (upstream control, [2610.29294](https://arxiv.org/abs/2610.29294)).
- Status: **selected answer stable, probability unstable**: thresholded systems are affected.

#### D. The Meaning of Confidence

**D1 Calibration vs Discrimination vs Sensitivity (three things, not one)**
- Definition: calibration = probability matches frequency; discrimination = AUROC of ranking right against wrong; sensitivity = whether confidence can separate right from wrong.
- Evidence: models with similar accuracy differ greatly in AUROC, and the confidence of the most sensitive model tracks "which kind of situation will fail" rather than "which answer is wrong"; the gain from deferring the 30% least certain decisions has rank correlation 0.87 with AUROC ([2610.09683](https://arxiv.org/abs/2610.09683)); Jev ranks completion requests best (AUROC 0.78 vs rules 0.62, small LLM 0.60) yet is poorly calibrated: mean "completed" probability 0.50 while 87% actually pass ([2610.24649](https://arxiv.org/abs/2610.24649)); in Indonesian the ECE does not increase but the ability to rank its own errors degrades on all three datasets ([2610.14112](https://arxiv.org/abs/2610.14112)); Intern-Decision's Brier 0.628→0.550 and ECE 0.213→0.089 come from the training objective ([2610.22131](https://arxiv.org/abs/2610.22131)).
- Status: **the concepts are separated; the three must be reported separately**.

**D2 Two Kinds of Uncertainty (human disagreement vs decision risk)**
- Evidence: 142,658 moderation comments: the model's AUROC 0.83 is indistinguishable from 13/14 frontier models; "confidence" mixes annotator disagreement with decision risk, and under asymmetric loss the two demand opposite escalation signals; splitting the judgment into parallel sub-questions and reading their dispersion recovers the disagreement signal, but only for the weakest model and only when the decomposition aligns with the source of disagreement ([2610.33258](https://arxiv.org/abs/2610.33258)).
- Status: **defined; mitigation is conditional**.

**D3 Self-Knowledge (is low confidence "random" or "don't know")**
- Evidence: with no relevant information at all Jev still gives the salient option up to 0.80; on news beyond its knowledge boundary confidence exceeds accuracy by 0.21–0.33 and recalibration on early months cannot fix it; targeted Nouls are sharper: whether the outcome is already settled AUROC 1.00, whether the evidence is sufficient 0.95 (vs answer confidence 0.85); "do you know the answer" seems to flag fictitious entities and post-boundary news (0.91), but after removing dates or using real names it is no better than answer uncertainty ([2610.01006](https://arxiv.org/abs/2610.01006)); on option lists without semantics the accuracy is random, yet the best-calibrated model still reports mean confidence 0.82; open-source models' confidence is inverted, and gating by confidence is worse than random ([2610.22526](https://arxiv.org/abs/2610.22526)).
- Status: **defined; surface cues disguise themselves as self-knowledge**.

**D4 Calibration and Thresholds under Prevalence (Prior) Shift**
- Evidence: Nimble-9B has only one more LoRA than Qwen3.5-9B, is better calibrated on intent tasks but Macro-F1 −12.0 on financial sentiment; under moderate shift, Jev's ECE and threshold risk are significantly higher than fine-tuned DeBERTa only on financial sentiment (+1.7/+2.5 pp), with an average gap ≤1 point over 2,000 scenarios; EM prior correction (label-free) lowers ECE by 2.7/1.8 points ([2610.26325](https://arxiv.org/abs/2610.26325)); SHIFT-JEV: KL anchor + temperature takes the calibration error under shift 0.289→0.087, and a chi-square test detects 95–99% of the class-prior shifts missed by confidence/embedding detectors ([2610.34329](https://arxiv.org/abs/2610.34329)).
- Status: **measurement and cheap mitigation exist**.

**D5 Inherited Teacher Bias**
- Evidence: exact risk computation on a Gaussian proxy: the student inherits the teacher's bias, more student data does not remove it, and agreement with the teacher cannot prove correctness ([2610.26797](https://arxiv.org/abs/2610.26797)); in the memory-retirement task, LLM majority-vote gold labels share most errors with the upgraded model of the same family ([2610.15710](https://arxiv.org/abs/2610.15710)); AgentDecision-4B uses Jev answers as labels ([2610.21412](https://arxiv.org/abs/2610.21412)); Releasing Inner Jev uses Qwen3.5-122B / Qwen3.6-27B as teachers ([2610.17205](https://arxiv.org/abs/2610.17205)).
- Status: **clear in theory, almost never measured empirically on decision models**. A direct risk for our "small model + distillation" route.

#### E. Dependence on Input Content

**E1 Numbers / Dates / Arithmetic** (see D2 for details)
- Evidence: MathQA is 17.7 points below the best LLM ([2610.11978](https://arxiv.org/abs/2610.11978)); numerically driven medical tasks are an explicit capability boundary ([2610.18529](https://arxiv.org/abs/2610.18529)); refusal bottleneck 99%/7% ([2609.39496](https://arxiv.org/abs/2609.39496)).
- Status: **boundary is clear, the vendor recommends "put arithmetic in code"**.

**E2 State Length / Irrelevant Detail / Indirection**
- Evidence: rows 4 and 5 of the official jaggedness page; Jev has no mis-retrieval record within 20k tokens and 64 options, but drops to 53–80% when the answer depends on two or more updates from the same user (16 updates), because similar records interfere with each other ([2610.24929](https://arxiv.org/abs/2610.24929)); Laya 31% on 50 nearest-neighbor tools, Jev 98% ([2610.02267](https://arxiv.org/abs/2610.02267)); Archer Hume: serving time is essentially flat up to ~100 questions, question text costs about 2 times the state ([architecture](https://archerhume.com/posts/jevs-architecture-unmasked)).
- Status: **"reading" is stable, "aggregating" is not**; boundary = intermediate steps required.

**E3 Flips from Natural Background Information (non-instructional adversarial)**
- Evidence: JevOut: within 64 target evaluations, short background / procedural additions steer 61.4–73.2% of initially correct decisions to the predetermined wrong option, without any explicit answer instruction ([2609.30243](https://arxiv.org/abs/2609.30243)); six lines of policy-irrelevant server logs raise the guard's false-allow rate 0%→63% ([2610.12292](https://arxiv.org/abs/2610.12292)).
- Status: **defined, high risk, no effective mitigation** ("escalate the least certain" does not work: decisions reversed by the attack are not less confident).

**E4 Record vs Observation (claim vs reality)**
- Evidence: Claim Laundering: in all 12 configurations the record influences the commitment decision more than the observation; after a claimed success that actually failed, 53–100% still stop / proceed / purchase; a linear probe can tell them apart (AUROC 0.77–1.00); EVIGATE's middle-layer veto +18.7 (ALFWorld) / +5.0 / +5.1, but offline calibration does not transfer to live trajectories ([2610.25947](https://arxiv.org/abs/2610.25947)); given a stale summary, Jev follows it ([2610.24929](https://arxiv.org/abs/2610.24929)); in compressed summaries 83% of failures trace back to summary entries with no environment support ([2610.20927](https://arxiv.org/abs/2610.20927)).
- Status: **defined; the most dangerous consistency problem in agent scenarios**.

**E5 Language / Culture / Persona**
- Evidence: Saudi vs US personas reproduce 87% of the human differences in English and 62% in Arabic; the difference comes from the question language, not the persona language, and confidence is lower in Arabic ([2609.36399](https://arxiv.org/abs/2609.36399)); Indonesian regional languages: human translation into Indonesian gains up to +37.2 points, ECE does not increase but the ability to rank errors degrades ([2610.14112](https://arxiv.org/abs/2610.14112)); the same medical question from English to Yoruba loses up to −39 pp accuracy ([2610.31315](https://arxiv.org/abs/2610.31315)); Bengali is captured by the literal meaning 1.9–6.4 times more often than English, "the resistance of commercial models is a property of the test language" ([2610.22526](https://arxiv.org/abs/2610.22526)).
- Status: **defined; the only Chinese evidence is Chinese Decision's CJ-Bench** ([2610.23170](https://arxiv.org/abs/2610.23170)).

**E6 Style / Emotion / Judge Bias**
- Evidence: CALM's 12 bias tests: all 8 TDMs are biased on 3–8 items, emotional tone has the largest effect, rewriting the better answer in an emotional tone takes a typical TDM's accuracy 99%→42%, and TDMs are more biased than the LLM judges of 2026 ([2610.18122](https://arxiv.org/abs/2610.18122)); JEV-as-Judge confidence routing fails under style adversaries and on reference-free prose ([2609.26550](https://arxiv.org/abs/2609.26550)).
- Status: **defined, measured, no mitigation**.

#### F. Interface and Composition

**F1 Readout Method (first token / verbalized / typed head / pointer)**
- Evidence: first-token readout overestimates position bias: for a Qwen3 judge, 12–49% of the pairs do not begin with the verdict token, a forced read returns "who is listed first", and after swapping 89.7% flip vs 47.5% when reading after generation ([2610.00054](https://arxiv.org/abs/2610.00054)); first-token negation bias 0.293 vs verbalized 0.122 ([2609.33209](https://arxiv.org/abs/2609.33209)); a typed head has no consistent advantage over LM-head readout ([2609.25845](https://arxiv.org/abs/2609.25845), [2609.32160](https://arxiv.org/abs/2609.32160)); JevCascade's readout stability is an ordinal property, not a probabilistic one (menu interventions predict with 4.2 points of error, probability-level variants 21.0 points) ([2610.07716](https://arxiv.org/abs/2610.07716)).
- Status: **the readout choice affects bias measurement results**; reproduction work should report the readout type.

**F2 Selection vs Sequential Construction (Choice2Seq)**
- Evidence: on arithmetic / lexical retrieval Jev's whole-selection accuracy is 97.1% / 99.5%, but only 33.0% / 2.1% is retained through local sequential construction ([2610.16191](https://arxiv.org/abs/2610.16191)).
- Status: **defined**; a business rule "judged step by step" and "judged as a whole" can give completely different results.

**F3 Request Independence / Packing Side Effects**
- Evidence: Nimble's request expansion on TREC DL2019/2020 causes 9.1%/8.0% strict binary flips and changes 21.4%/18.9% of the select-or-abstain actions; all 70 flips trace back to schema fields serialized into the scoring prompt; Von's fixed shared separator positions remove the flips ([2610.14631](https://arxiv.org/abs/2610.14631)); Jev's packed questions do not affect each other, <0.001 ([2610.16655](https://arxiv.org/abs/2610.16655)).
- Status: **the hosted model passes, open-source reproductions not necessarily**; an acceptance metric for reproductions.

**F4 Consistency after Decision→Action Composition**
- Evidence: the most accurate system, once composed into actions, most often ignores emails that need handling (18% vs 4% for the best LLM); a cost threshold on the noisy probability halves this ([2610.32955](https://arxiv.org/abs/2610.32955)); DICE: the three adapters for state extraction / question generation / output interpretation can each change the final decision while Jev's response is unchanged ([2610.14404](https://arxiv.org/abs/2610.14404)); union bound and cost-accuracy formalization ([2610.10978](https://arxiv.org/abs/2610.10978), [2610.08089](https://arxiv.org/abs/2610.08089)).
- Status: **defined; product metric ≠ decision accuracy**.

**F5 Adversarial Injection (explicit)**
- Evidence: JevAdvBench 862 questions; option-channel attacks give 36–72% accuracy (random 50%); JPDH program decision hijacking in real applications ([2610.18612](https://arxiv.org/abs/2610.18612)); injection detection AUROC 0.897 ([2610.20907](https://arxiv.org/abs/2610.20907)); Jev is most robust on tasks with "an explicit rule to look up" (0 bypasses for 8 forgeries, "why would anyone make such a request" bypasses 9% vs 56% for GPT-6 Astra), while on phishing detection, which needs holistic judgment, the same forgeries bypass 19–29%, and without attack it detects only 62% and mislabels 27% of benign requests ([2610.17820](https://arxiv.org/abs/2610.17820)); TrustJev separates policy authority from evidence ([2610.34826](https://arxiv.org/abs/2610.34826)).
- Status: **many definitions, few mitigations**; see D2 §4.1.2.4 for details.

**F6 Consistency of Refusal / Fallback / Abstention** (see D2 §4.1.2.3 for details)
- Evidence: arithmetic 99%/7%; with missing legal authority LLMs still choose 38–86%, the most cautious decision model 30% ([2610.29961](https://arxiv.org/abs/2610.29961)); refusal policy transfer 69.3%/48.8% ([2610.03387](https://arxiv.org/abs/2610.03387)); in memory retirement the binary gate retires prematurely 39.2%, the ternary gate drops this to 15.5% but detection −15.3 ([2610.15710](https://arxiv.org/abs/2610.15710)); in medicine most models are weak at both "recognizing a missing correct answer and using the optional abstention" ([2610.18529](https://arxiv.org/abs/2610.18529)).
- Status: **the weakest link**.

### 4.2.3 D4 Matrix: Which Work Solves Which Kind of Problem

| Sub-dimension | Defined | Measured | Mitigated | Representative work |
| --- | --- | --- | --- | --- |
| A1 Repeatability | ✓ | ✓ | Not needed | 2609.36399, 2609.27678 |
| A2 Precision/quantization | ✓ | ✓ | — | Kev, 2610.23170, 2610.14631 |
| A3 Version drift | Weak | Weak | — | 2610.35826, SemTree |
| B1 Order | ✓ | ✓ | ✓ (structural) | 2610.22066, 2610.18233, 2610.00831, 2610.01601, 2609.35865 |
| B2 IIA | ✓ | ✓ | Partial | 2610.16655, Prism-1, 2610.07716 |
| B3 Option names/definitions | ✓ | ✓ | — | 2609.26758, 2610.02586, 2610.12292, 2610.22526 |
| B4 Multiple correct | ✓ | ✓ | — | 2610.29217 |
| B5 Ordinal compression | ✓ | ✓ | Training direction | 2609.38827 |
| B6 Question form | ✓ | Contradictory | — | 2609.33209, 2610.18529, 2610.16655, pplx |
| C1 Hierarchical coherence | ✓ | ✓ | — | 2609.33971 |
| C2 Probability axioms | ✓ | ✓ (label-free) | — | 2609.33209, 2610.19619 |
| C3 Wording | ✓ | ✓ | — | 2610.30045, 2610.19856, 2610.19536 |
| C4 Framing | ✓ | Partial | — | 2610.19619 |
| D1 Calibration/discrimination/sensitivity | ✓ | ✓ | Training objective | 2610.09683, 2610.24649, 2610.22131 |
| D2 Two kinds of uncertainty | ✓ | ✓ | Conditional | 2610.33258 |
| D3 Self-knowledge | ✓ | ✓ | — | 2610.01006, 2610.22526 |
| D4 Prevalence shift | ✓ | ✓ | ✓ (EM/KL anchor) | 2610.26325, 2610.34329 |
| D5 Teacher bias | Theory | — | — | 2610.26797 |
| E1 Numbers | ✓ | ✓ | Code | 2610.11978, 2609.39496 |
| E2 Length/irrelevant | ✓ | ✓ | Filtering | 2610.24929, 2610.02267 |
| E3 Natural background flips | ✓ | ✓ | — | 2609.30243, 2610.12292 |
| E4 Record vs observation | ✓ | ✓ | Partial (probe veto) | 2610.25947, 2610.20927 |
| E5 Language/culture | ✓ | ✓ | Translation/cascade | 2609.36399, 2610.14112, 2610.31315, 2610.22526 |
| E6 Style/emotion | ✓ | ✓ | — | 2610.18122 |
| F1 Readout | ✓ | ✓ | Report readout type | 2610.00054, 2610.07716 |
| F2 Selection vs construction | ✓ | ✓ | — | 2610.16191 |
| F3 Request independence | ✓ | ✓ | Format fix | 2610.14631 |
| F4 Decision→action | ✓ | Partial | Starting point for formalization | 2610.32955, 2610.14404, 2610.08089 |
| F5 Explicit injection | ✓ | ✓ | Weak | 2609.31142, 2610.12292, 2610.17820 |
| F6 Refusal/fallback | ✓ | ✓ | — | 2609.39496, 2610.29961, 2610.03387 |

### 4.2.4 D4 Blind Spots

1. **There is no "consistency benchmark" that puts these sub-dimensions together**: DecisionPivot ([2610.28522](https://arxiv.org/abs/2610.28522)) is the closest (a control group of 48 tasks and 7 roles), but it covers only part of B1/C3/F6; TypedBench ([2610.18488](https://arxiv.org/abs/2610.18488)) and System1-Arena each cover another part. No work reports A–F at the same time.
2. **There is no consistency data for "Chinese + business rules"**: the E5 evidence is all English / Indonesian / Arabic / Bengali / Yoruba; for Chinese there is only CJ-Bench's accuracy and ECE.
3. **A3 version drift and D5 teacher bias have no empirical evidence**, yet these two items decide "whether the rule library must be recompiled with the model" and "whether a distilled small model inherits Jev's B2/B5/C2 defects".
4. **The evidence on B6 question-form equivalence contradicts itself**, which means every primitive of D3 must be tested separately on the target model for "Noul or Choice".
5. **Mitigations cover only the two items B1 and D4** (structural order independence, prior correction). The mitigations for B2–B5, C1–C3, E3 and E6 all stop at "report it" or "a training direction".
6. **Decision-level paired evaluation has not become the norm**: most reproduction work still reports only accuracy and ECE; 2610.35826 and 2609.27678 show that this systematically overestimates robustness.
