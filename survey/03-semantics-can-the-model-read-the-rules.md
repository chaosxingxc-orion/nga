# 3 · Semantics: did the model actually read what the business side wrote

> If the core logic is the generalization of semantic understanding (§2.2 P0), then the first question to ask is: **does the model actually read the definitions, criteria, examples and rules that the business side writes down in text**. This chapter is the whole body of evidence on that question.
>
> The protocol of §3.1 (formerly dimension D1) is not a cost level. It is: whether the decision-fine-tuned single-pass model still has, and can use, ICL; **whether business staff can use a Jev-class model directly through prompt engineering**; and the effect size and failure modes of each lever. §3.2 (formerly dimension D3) is the other half: define a set of logic primitives so that non-technical business experts can write business rules in text and have them executed faithfully.
>
> The two sharpest conclusions of this chapter: **label names override definitions** (a name-definition swap takes mean AUC from 93.8% → 23.2%, while the type-error rate stays at 0% throughout: correct type ≠ read the definition), and **deleting all definitions leaves accuracy unchanged**. They strike directly at the premise that "business staff can configure it".

## 3.1 D1 in-context learning: can it "learn in the prompt", and which levers can business staff use

> Protocol (per the latest discussion): not a cost level. Three questions to answer:
> 1. Does the decision-fine-tuned single-pass model **still have / can it use** ICL (examples, definitions, criteria, state structure)?
> 2. How to **make good use** of this ability?
> 3. Which levers can **business staff use through prompt engineering**, how large are the effects, and in which situations do they fail?

### 3.1.1 First, Back to the Basic Facts of ICL (Upstream Literature)

A decision model is obtained by fine-tuning a causal LM, so the ICL regularities of LMs are our starting point. The conclusions directly relevant to "business staff writing examples":

| Fact | Source |
| --- | --- |
| The **true labels of examples are not required**: randomly replacing example labels barely hurts the classification / multiple-choice performance of 12 models; what matters is the label space, the input distribution and the format | [2202.12837](https://arxiv.org/abs/2202.12837) |
| **Only large models can learn flipped labels**: small models ignore flipped labels and rely on pretrained semantic priors; overriding priors is an ability that emerges with scale | [2303.03846](https://arxiv.org/abs/2303.03846) |
| **1–12B open models have exactly zero semantic override rate under few-shot**: inverted examples can only raise "prompt alignment" at the cost of accuracy; ICL is "adjusting how inputs project onto stable semantic directions", not remapping label meanings | [2511.21038](https://arxiv.org/abs/2511.21038) |
| **Homogeneous labels collapse 0.8B–8B models to ≤12%**: the model treats the tokens in the label slot as an exhaustive answer vocabulary; if examples carry meaningless tokens like {foo,bar,vex,nit,orb}, 42–67% of the probability falls on the example set, P(dog) < 0.2%; under 4-way classification three models score 0% | [2605.08295](https://arxiv.org/abs/2605.08295) |
| ICL decomposes into two separable mechanisms, **task Schema and Binding**: Schema transfers 100% through late MLPs, Binding transfers 62% through the residual stream; prior knowledge interferes through attention misrouting (72.7% recency bias); 38% binding failure in high-prior scenarios; the same holds on Mamba | [2512.17325](https://arxiv.org/abs/2512.17325) |
| **Label words are anchors**: shallow layers aggregate semantics into the label-word representation, deep layers use it as the reference for prediction | [2305.14160](https://arxiv.org/abs/2305.14160) |
| **Symbol tuning**: fine-tuning with arbitrary symbols replacing natural-language labels forces the model to learn the input-label mapping; more robust on unseen ICL tasks and underspecified prompts | [2305.08298](https://arxiv.org/abs/2305.08298) |
| **Calibrate before use / batch calibration**: few-shot instability comes from bias toward specific answers (last position, pretraining frequency); estimating the bias with content-free inputs corrects it | [2102.09690](https://arxiv.org/abs/2102.09690), [2309.17249](https://arxiv.org/abs/2309.17249) |
| **Task vectors / function vectors**: ICL compresses the example set into one vector; a few attention heads carry the task representation | [2310.15916](https://arxiv.org/abs/2310.15916), [2310.15213](https://arxiv.org/abs/2310.15213) |
| **Rules can be amortized, pairings cannot**: a static vector is equivalent to one synthetic example and necessarily fails on high-rank mappings (word-level bijections) | [2610.00526](https://arxiv.org/abs/2610.00526) |
| **ICL amplifies latent symbolic circuits**: the abstraction-induction-retrieval three-stage circuit already exists before accuracy rises; examples merely feed inputs to the same circuit | [2609.36265](https://arxiv.org/abs/2609.36265) |
| **Many-shot**: hundreds to thousands of examples keep improving results, especially for large label spaces; but highly sensitive to the selection strategy, and limited gains on open generation tasks | [2404.11018](https://arxiv.org/abs/2404.11018), [2405.00200](https://arxiv.org/abs/2405.00200), [2603.05829](https://arxiv.org/abs/2603.05829) |
| Example **ordering can be attacked**: merely reordering examples gives nearly 80% attack success on LLaMA-3 | [2502.14628](https://arxiv.org/abs/2502.14628) |
| **ICL and instruction following are not the same thing**: 3-shot ICL alignment is still worse than instruction tuning | [2405.19874](https://arxiv.org/abs/2405.19874) |
| **ICL hurts calibration**, the source being example-selection bias; a cross-model cross-task universal calibrator can cut the calibration error of frontier models by more than 50% | [2610.17096](https://arxiv.org/abs/2610.17096), [2506.12796](https://arxiv.org/abs/2506.12796) |
| Post-training **reduces distribution coverage and in-context steerability** | [2510.06084](https://arxiv.org/abs/2510.06084) |

**Hard constraints that follow from these facts**: at our target scale of 0.6B–9B, **what ICL can do is "recognize the task pattern + adjust the boundary along existing semantic directions"; what it cannot do is "flip label meanings with examples" or "make the model learn a mapping that conflicts with its prior"**. When business staff write examples, the examples mainly demonstrate the format, expose the label space and pull the input distribution closer; they do not "teach" the model new rules.

### 3.1.2 ICL Evidence on Decision Models (Jev and Reproductions)

#### 3.1.2.1 Where the Official Interface Puts ICL

- The `state` documentation explicitly allows "relevant context, examples and other information helpful for answering" ([concepts/state](https://docs.typesafe.ai/concepts/state)).
- Choice options carry `criteria` (a description) and `examples`; Noul's `criteria.true` / `criteria.false` can each carry a definition and examples; each Score level is a description ([primitives/advanced](https://docs.typesafe.ai/primitives/advanced)).
- The fix for item 1 of the vendor's zigzag table, "literal reading", is exactly "write precise conditions and criteria for each option" ([jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)).

In other words, the vendor designed all three carriers of ICL, **definitions, examples and criteria**, into the interface; the question is whether the model actually uses them.

#### 3.1.2.2 Are Definitions Used? "Label Names Override Definitions"

This is the most important and most counter-intuitive chain of evidence in D1:

| Evidence | Number | Source |
| --- | --- | --- |
| Change only the "name-definition" pairing, not the question, the state, or the name and definition texts themselves: on 1,200 decision tasks with task-specific definitions, the decision flip rate under yes/no names is up to 70.4 pp higher than the 0/1 control; **reassignment under yes/no names takes mean AUC from 93.8% to a below-chance 23.2%**; with random strings as names the flip rate is close to the neutral control; type-error rate 0% throughout | Correct type ≠ following the definition | [2609.26758](https://arxiv.org/abs/2609.26758) |
| When the rule is written only in the definition, the model mostly answers by label: **deleting all definitions leaves accuracy unchanged** (0.8487), although definitions alone can sustain 0.7971; when label and definition contradict, accuracy drops from 0.8511 to 0.2281; **the cause is localized to the prompt rendering `"{label}: {definition}"`**; switching to definition-only (labels replaced by A/B identifiers) gives +0.1511 accuracy; a "two-call test" is given to decide whether a model reads definitions | The definition is the only place a developer can write rules, but the model reads the label | [2610.02586](https://arxiv.org/abs/2610.02586) |
| HateDecide: supplying the dataset's hate-speech definition **changes up to 28% of predictions without consistently improving classification**; decomposing the definition into multiple questions is significantly effective in only 20% of comparisons | Definitions change answers but do not improve them | [2610.03324](https://arxiv.org/abs/2610.03324) |
| Online moderation: Jev generally benefits from **retrieved precedents** (improves exact policy selection and harmful-content discrimination under a fixed answer space); Laya instead "retrieval often changes its positive rate or no-violation rate without improving discrimination" | Precedents (examples) work for the decoder family, unstable for the encoder family | [2610.07953](https://arxiv.org/abs/2610.07953) |
| Structured-output schema descriptions: label definitions in the system prompt beat those in the schema description (GPT-4.1 / 5.4 lower by 11–13 points); but when schema and prompt conflict, wrong schema instructions drop accuracy by 5–45 points; adding an intermediate reasoning field before the label gives schema-only accuracy +15–24 | The **position** and **rendering** of definitions are first-order variables | [2608.08254](https://arxiv.org/abs/2608.08254) |

**Reading**: the decision-fine-tuned model keeps the LM's "label-word anchor" mechanism. It answers from the semantic prior of the option **name**; the definition is read only when the name carries no information (random strings, A/B). This is fully consistent with the §3.1 finding that "small models cannot flip label semantics": a definition is an attempt to rewrite the label meaning, and small models cannot do that.

#### 3.1.2.3 Are Examples Used? Indirect Evidence

No paper runs a "k-shot example curve" experiment **directly** on a decision model. The indirect evidence that can be found:

- **JevKT** (knowledge tracing): zero-data Jev AUC .706, **.722 after adding examples and similar-learner statistics**, ahead of deep KT models up to 16 learners and on average up to 64; this gain is Jev-specific, three other LLMs with byte-identical requests all score below it ([2610.11135](https://arxiv.org/abs/2610.11135)). This is the closest thing to evidence that "examples in state work".
- **Retrieved precedents** help Jev (table above, [2610.07953](https://arxiv.org/abs/2610.07953)).
- **Nimble's contrastive data curation** ("change one fact so the answer flips") uses example pairs at training time, not at inference time ([bespokelabsai/nimble](https://github.com/bespokelabsai/nimble)).
- **Jev-LDE**: train a small model (System 1) to perform one Keep / Delete / Replace edit on the retrieved example set, then feed it to the target LLM; consistent gains on classification benchmarks and transferable ([2609.33609](https://arxiv.org/abs/2609.33609)). It shows that "which examples to pick" can itself be a decision task.
- **Many-shot compression**: MemCom compresses many-shot representations layer by layer and beats the surprisingly strong baseline of "just use fewer examples" at 3–8× compression ([2510.16092](https://arxiv.org/abs/2510.16092)); cheat-sheet ICL distills many examples into one text summary ([2509.20820](https://arxiv.org/abs/2509.20820)).
- **State length**: in TypedBench the host model's accuracy stays flat up to 30k tokens, decoders slow down, encoders truncate silently ([2610.11392](https://arxiv.org/abs/2610.11392)); item 5 of the vendor's zigzag table warns that "state with lots of irrelevant detail should be filtered first". Putting examples into state runs straight into this.

**Gap**: no work answers "how does the k-shot curve of the same backbone change before and after decision fine-tuning". This is the first blind spot of D1.

#### 3.1.2.4 Are Wording and Criteria Used? "Read, but Not Necessarily Acted On"

- Across the nine suites of TypedBench, **the host model is wording-sensitive and systematically under-confident**, and decoders degrade with structural complexity; the "share of variance attributable to wording" is used as a reported metric ([2610.11392](https://arxiv.org/abs/2610.11392)).
- Rule transfer: **equivalent rewrites have opposite task-level effects**, "gains on unfamiliar rules may still depend on familiar wording"; "a decision service changes its answer more between equivalent wordings than between genuinely different rules" ([2610.30045](https://arxiv.org/abs/2610.30045)).
- Reading Right, Acting Wrong: policy modifications are **read out correctly** but **acted on** in only 22%–72% of cases ([2610.18579](https://arxiv.org/abs/2610.18579), details in D2).
- Definition optimization can be a training target: Goldsmith treats "structured annotation definitions" as trainable text objects and revises them by textual gradients with an executable structural loss on a small gold set, beating OPRO / APE / PromptBreeder ([2610.09489](https://arxiv.org/abs/2610.09489)); CALICO lets non-technical domain experts turn a codebook into an editable, versionable, optimizable prompt, two coders gaining +13.0 / +7.4 points respectively, and the optimized prompt captured coder-specific interpretations ([2609.14726](https://arxiv.org/abs/2609.14726)).
### 3.1.3 Prompt Levers Available to Business Staff: Effect Sizes and Failure Modes

Organizing the evidence above by "knobs business staff can turn":

| Lever | Expected effect | Known effect size | Failure mode | Evidence |
| --- | --- | --- | --- | --- |
| **Option names** | The strongest lever | Name-definition reassignment takes AUC 93.8%→23.2%; misleading names push guard fail-open rates to 93–100% | When names have polarity (yes/no, allow/deny, safe/unsafe) they override everything; when name and definition disagree the model follows the name | [2609.26758](https://arxiv.org/abs/2609.26758), [2610.12292](https://arxiv.org/abs/2610.12292) |
| **Definitions / criteria** | Supposed to be the place to write rules | Deletion leaves accuracy unchanged, contradiction 0.85→0.23; definition-only +0.15 | Masked by names; changes 28% of predictions without improvement; rendering decides whether it is read | [2610.02586](https://arxiv.org/abs/2610.02586), [2610.03324](https://arxiv.org/abs/2610.03324) |
| **Examples (in state or in options)** | Demonstrate format, expose label space, pull distribution closer | JevKT +0.016 AUC; precedents help Jev | Homogeneous examples collapse; small models cannot flip semantics; longer examples run into "irrelevant state" degradation; example order can be attacked | [2610.11135](https://arxiv.org/abs/2610.11135), [2605.08295](https://arxiv.org/abs/2605.08295), [2511.21038](https://arxiv.org/abs/2511.21038) |
| **Wording / rewrites** | Should have no effect | Equivalent rewrites have opposite effects; the host model is wording-sensitive | This is a variance source, not a lever; take the median over multiple wordings | [2610.30045](https://arxiv.org/abs/2610.30045), [2610.11392](https://arxiv.org/abs/2610.11392) |
| **Candidate set (menu) design** | First-order variable | 150 classes→5 curated candidates: 69.0%→95.4%, a span larger than the gap between 0.8B and 4B | Similar candidates, many candidates (Laya 31% with 50 nearest-neighbor tools), missing "other" option makes refusal fail | [2610.07716](https://arxiv.org/abs/2610.07716), [2610.02267](https://arxiv.org/abs/2610.02267) |
| **Question decomposition (one big question split into several Nouls)** | Auditable, composable | Decomposition is significantly effective in only 20% of comparisons; but normalized per-option binary scores after decomposition are more accurate than Choice scoring in medicine | Decomposition introduces probabilistic inconsistency (see D4 hierarchical consistency) | [2610.03324](https://arxiv.org/abs/2610.03324), [2610.18529](https://arxiv.org/abs/2610.18529) |
| **State structure (JSON vs text, filtering)** | Reduce irrelevant information | Vendor recommends filtering; host model flat up to 30k | Decoders slow down with length; irrelevant detail degrades | [docs/state](https://docs.typesafe.ai/concepts/state), [2610.11392](https://arxiv.org/abs/2610.11392) |
| **Language** | Should have no effect | Indonesian regional languages with human Indonesian translation +37.2 points; Bengali literal lock-in 1.9–6.4× higher than English | Under low-resource languages all ICL levers weaken | [2610.14112](https://arxiv.org/abs/2610.14112), [2610.22526](https://arxiv.org/abs/2610.22526) |
| **Writing rules into state rather than into definitions** | Bypass name masking | Archer's probe: a statement placed in state raises probability more than one placed in a sibling question | No direct controlled experiment | [Archer Hume](https://archerhume.com/posts/jevs-architecture-unmasked) |

### 3.1.4 Alternatives and Complements to ICL (Not Our Main Line, but Worth Knowing)

- **Turning context into weights**: Text-to-LoRA, Doc-to-LoRA, Internalizer, Cartridges and LatentSkill are all "hypernetwork / self-learning compresses a document or skill into LoRA / KV"; LatentSkill beats in-context skills by +21.4 success rate on ALFWorld ([2606.06087](https://arxiv.org/abs/2606.06087), [2602.15902](https://arxiv.org/abs/2602.15902), [2610.11715](https://arxiv.org/abs/2610.11715), [2506.06266](https://arxiv.org/abs/2506.06266)). These methods keep "business staff write text" at the front end, but the model side is no longer ICL.
- **Task operators**: the output of each attention head is an affine transform of its context-masked version, so an input-dependent operator can replace the examples ([2610.01054](https://arxiv.org/abs/2610.01054)).
- **Meta-learned logic**: 1.5B–7B small models learn syllogisms by few-shot meta-learning and beat GPT-4o / o3-mini in low-data regimes ([2505.14313](https://arxiv.org/abs/2505.14313)); MetaICL ([2110.15943](https://arxiv.org/abs/2110.15943)). This is the route of "training the model to learn from examples"; its relation to decision fine-tuning has not been studied.
- **Hierarchical demonstrations beat flat logs**: on vaguely described tasks, grouped demonstrations raise pass rate 76.7%→90.7%, with no gain under precise descriptions; only sub-goal grouping works ([2606.20978](https://arxiv.org/abs/2606.20978)). Directly relevant to "business staff supplying process examples".

### 3.1.5 Which Works Solve Which Kind of Problem (D1 Mini-Matrix)

| Problem | Existing work | Status |
| --- | --- | --- |
| Are definitions read | 2609.26758, 2610.02586 (incl. diagnostic test) | **Quantified**, cause localized to rendering and name polarity |
| Do examples work | JevKT, precedent retrieval, Nimble training-time contrast | Indirect evidence, **no k-shot curve** |
| Wording sensitivity | TypedBench, Rule transfer | Quantified, no mitigation |
| Optimization of definitions / prompts | Goldsmith, CALICO, Jev-LDE | Tools exist, aimed at generative LLMs or external editors |
| ICL ceiling of small models | Semantic anchors, In-context fixation, Schema/Binding | Upstream LM conclusions clear, **not re-verified on decision-fine-tuned models** |
| Effect of ICL on calibration | CALIBFORMER, Surprise calibration | Upstream LM, not measured on decision models |
| Menu / candidate-set design | JevCascade, Fast Models Slow Evidence | Quantified, the strongest lever |

### 3.1.6 D1 Blind Spots (Identified by Us, Not Covered by Existing Work)

1. **Does decision fine-tuning preserve ICL**: no paper compares the k-shot curve, label-flipping ability or definition-following rate of the same backbone before and after fine-tuning. Spectrum Tuning hints that post-training reduces in-context steerability, but it was not measured on decision models.
2. **A training-side fix for "definitions masked by names"**: the Symbol tuning idea (meaningless symbols as labels to force reading of definitions) has not been tried on decision models; 2610.02586 only gives a rendering-level fix.
3. **Where to put examples**: in state, in the option's `examples`, or in Noul's true/false criteria; the effects of the three positions have no controlled comparison. Archer's probe only shows "state is visible, sibling questions are not".
4. **Interaction of examples × branch isolation**: examples placed in state are shared by all questions and add to the cost of every branch; placed in the question branch, each question carries its own copy. Nobody has measured the accuracy/cost trade-off of these two layouts.
5. **ICL and calibration**: the example-selection bias introduced by ICL breaks calibration (upstream evidence), while calibration is the core selling point of decision models; the interaction of the two is unmeasured.
6. **"Prompt usability" from the business staff's perspective**: CALICO targets generative LLMs; there is no usability study for decision models of "non-technical staff write criteria → model following rate".
7. Whether **median over multiple wordings / batch calibration** can be ported to the single-pass decision interface (which natively supports fan-out at low cost) has not been done.

These blind spots are turned into measurable problem definitions in [§8.4](08-critical-and-adversarial-review.md).

## 3.2 D3 logic primitives and rule language: letting business experts write rules in text

> Protocol (per the latest discussion): define a set of **logic primitives** so that non-technical business experts can make the model understand business rules by **writing text**, just as a Skill uses text to make the model understand a work capability. This section covers: (1) the evidence on the Skill paradigm itself; (2) compiler-style work on "natural-language rules → executable structure"; (3) primitives and composition patterns already present on decision models; (4) the experience of "policy-as-prompt" guards; (5) blind spots.

### 3.2.1 The Skill Paradigm: How Far Can Text Teach a Model a "Work Capability"

| Fact | Source |
| --- | --- |
| Agent Skills specification: `SKILL.md` = YAML front matter (`name` ≤64 characters, `description` ≤1024 characters) + arbitrary Markdown body; optional `scripts/`, `references/`, `assets/`; **progressive disclosure**: only about 100 tokens of metadata are loaded at startup, the <5000-token body is loaded on activation | [agentskills.io/specification](https://agentskills.io/specification) |
| SkillsBench: 87 tasks, 8 domains, 18 model-harness configurations; curated Skills raise mean pass rate 33.9%→50.5% (+16.6 pp), +4.1 to +25.7 per configuration; **focused Skills of ≤3 modules beat large all-in-one ones**; a small model with Skills can match a large model without | [2602.12670](https://arxiv.org/abs/2602.12670) |
| 138,133 public SKILL.md files: **91.8% have at least one defect** (88.8–94.6%); mainly weak routing metadata, bloated or non-executable bodies, poor resource organization; Skills with effective routing metadata are retrieved more reliably | [2608.08453](https://arxiv.org/abs/2608.08453) |
| SkillJuror: progressive disclosure changes runtime behavior before it changes overall outcomes | [2606.11543](https://arxiv.org/abs/2606.11543) |
| Skill coverage: task outcomes do not show which parts of a Skill were executed or whether they were executed as instructed; trajectory-level coverage metrics are needed | [2606.20659](https://arxiv.org/abs/2606.20659) |
| SkillSentry: even when an Agent has completed a task under Skill guidance, it may be unstable due to deviating from the procedure or executing steps wrongly; a DSL expresses runtime assertions as guarantees | [2608.09253](https://arxiv.org/abs/2608.09253) |
| AFTER: 382 enterprise tasks, 6 roles, 22 procedural skills; one round of refinement +3.7–6.7 points; controlled evaluation of transfer across tasks / roles / models | [2606.23127](https://arxiv.org/abs/2606.23127) |
| **Auto-Policy, not Auto-Skill**: "a Skill describes how an Agent should behave; a Policy decides which behavior is **allowed** to become an action"; existing formats cover only the former and leave the latter to the model; auto-generating more Skills amplifies the gap, not safety | [2608.25091](https://arxiv.org/abs/2608.25091) |
| LatentSkill: compresses text skills into LoRA via a hypernetwork, ALFWorld +21.4 success rate, prefill tokens greatly reduced | [2606.06087](https://arxiv.org/abs/2606.06087) |
| Decision models screening malicious Skills: SkillScreen scores from SKILL.md in a single pass, flagging only 20–25% of benign Skills at 99% recall | [2610.17727](https://arxiv.org/abs/2610.17727) |

**Implications for D3**: Skills prove that "text can teach a generative Agent to do things", but their reliability comes from **the model's ability to reason at execution time**; and they only cover "how to do it", not "what is allowed". The "business rule language" we want is closer to Policy than to Skill, and the executor is a **single-pass, non-reasoning** decision model. These two differences mean the Skill approach cannot be copied directly.

### 3.2.2 Natural-Language Rules → Executable Structure: Compiler-Style Work

All of these works answer "how does text written by a business expert become something a machine executes faithfully". They target generative LLMs, but their **intermediate representations** are exactly the candidates for our logic primitives.

| Work | Input → intermediate representation | Key result | Source |
| --- | --- | --- | --- |
| **Artic** | Natural-language workflow → artifact-driven workflow (each step declares the artifacts it reads/writes, constraints gate artifacts, explicit control transfer); the compiler identifies steps that depend on too much state or have hard control logic and optimizes them | 488 instances in 11 real domains, task resolution rate +28 pp; cross-model and repeated-execution consistency +32 / +56 pp | [2608.21341](https://arxiv.org/abs/2608.21341) |
| **FlashScript** | Successful Agent runs → neuro-symbolic program (actions and data transforms become code, instance values become parameters, **decisions that need model judgment become LLM calls**); three-tier placement + three techniques for replacing most calls with code | 120 WorkBench tasks: the NSP's tool calls are fully identical on every run, about 70× fewer input tokens, 1/3 runtime; on composite tasks the Skill-guided Agent drops to 23% while the NSP stays correct; all 108 unseen instances generalize | [2610.33876](https://arxiv.org/abs/2610.33876) |
| **TraceCompiler** | Clusters of noisy Agent trajectories → mostly deterministic workflow; a dependency is admitted only when a consumer's parameters contain a value uniquely attributable to an earlier producer, each hard edge carrying auditable evidence | — | [2608.02680](https://arxiv.org/abs/2608.02680) |
| **Formal Skill** | Markdown skill → JSON metadata + action schema + Python executor + hook control logic + skill-local state; "executable state machine + hook policies" | Competitive scores on Harness-Bench with far fewer tokens | [2605.19604](https://arxiv.org/abs/2605.19604) |
| **P2T (Executable Governance)** | Policy documents → normalized machine-readable rules; a compact DSL encodes **harm, scope, conditions, exceptions, required evidence** | — | [2512.04408](https://arxiv.org/abs/2512.04408) |
| **SIRNA** | Business rule documents → SMT formulas (LLM translation + verification), consistency-checked against the SMT representation of the implementation; tax cost calculation case | — | [2608.00396](https://arxiv.org/abs/2608.00396) |
| **Cedar autoformalization** | Agent prompts / MCP tool descriptions / policy documents → Cedar policy language (generate-critique loop) | MedAgentBench | [2606.26649](https://arxiv.org/abs/2606.26649) |
| **ARc (Automated Reasoning checks)** | Natural-language policy → formalization (optionally human-guided), statements verified by automated formal reasoning at inference time | A public service aimed at regulated industries such as finance / healthcare | [2511.09008](https://arxiv.org/abs/2511.09008) |
| **Logic Sketch Prompting** | Introduces typed variables, a deterministic condition evaluator and a rule-based validator into the prompt | Highest and reproducible for all three open models on two pharmacological compliance tasks | [2512.22258](https://arxiv.org/abs/2512.22258) |
| **NormBench / Deontic trees** | Statutes → span-anchored deontic trees (general rules, nested exceptions, counter-exceptions) | Diagnoses "silent scope omission" | [2606.08932](https://arxiv.org/abs/2606.08932) |
| **Business rules recovered as cascaded lookups** | Historical transactions → knowledge-graph-guided candidate business keys (column combinations) → cascaded lookup tables, rather than opaque statistical patterns | Sales-order fields (payment terms, shipping point, sales attribution) | [2610.34258](https://arxiv.org/abs/2610.34258) |
| **AgenTest** | System prompt / tool definitions / domain knowledge → mined business rules → tests for the Agent's business-logic defects | Rules are "scattered across the system prompt and tool definitions, or implicit in domain knowledge" | [2610.28116](https://arxiv.org/abs/2610.28116) |
| **Typed action contracts** | The model only interprets intent and proposes actions; typed action contracts, permission-aware capability exposure, scoped context, pre-side-effect validation, consumer-side execution boundaries | "Bounded autonomy" for enterprise AI | [2604.14723](https://arxiv.org/abs/2604.14723) |
| **Bellman LMs** | The decision space in bounded Agent workflows tends to saturate → "discretize, then decide": solve the decision once as an optimization problem and reuse it | Faster, cheaper, more reliable | [2610.24871](https://arxiv.org/abs/2610.24871) |
| **LLM as interface, not oracle** | The LLM only does schema-constrained feature extraction + deterministic plausibility checks; the final decision goes to structured ML | Pediatric appendicitis | [2606.19183](https://arxiv.org/abs/2606.19183) |

**Shared intermediate-representation elements** (appearing two or more times): the **read/write artifacts** of a step; the hierarchy of **conditions / exceptions / counter-exceptions**; statements that **require evidence**; **points requiring model judgment** explicitly isolated as "calls"; a **deterministic evaluator** responsible for arithmetic / comparison; **typed variables**. This is the minimal candidate set for defining our logic primitives.
### 3.2.3 Primitives and Composition Patterns Already Present on Decision Models

#### 3.2.3.1 Official Primitives and Patterns (Details in §1.1)

- Three question primitives: Noul (P(true)), Choice (distribution over ≤255 options), Score (ordered distribution over ≤10 levels); all accept JSON-structured `instructions` / `criteria` / `examples`.
- Five composition patterns: fan-out, composite scoring, confidence routing (global floor + per-action threshold), walking a classification tree level by level, "put the constants in one file for easy review".
- Two cookbooks directly demonstrate "business rules → list of Nouls": the **self-consistency cookbook** runs a car-insurance claim through a 14-Noul scoring rubric 15 times to check whether each answer is stable ([consistency_noul_cookbook](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook)); the **autoresearch cookbook** uses 29 Scores + 9 Nouls to turn free text into 67 columns of numeric features fed to CatBoost ([autoresearch_feature_discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery)).
- The example rules on the official evaluation page look exactly like business rules: "every reimbursement must have a receipt; if it cannot be read, have the employee resubmit", "meals over 75 dollars need a manager's signature when the description and the receipt disagree" ([evals.typesafe.ai](https://evals.typesafe.ai/)).

#### 3.2.3.2 Third-Party Primitives / Composition Structures

| Work | Primitive / structure | Key result | Source |
| --- | --- | --- | --- |
| **SemTree** | Rule decision = semantic decision tree: each node is a natural-language question with explicit **Yes/No/Unknown criteria**, answered by a pluggable semantic judge; the branch structure is **compiled against the answers that judge actually gives**; the execution path is the reasoning, errors are fixed at the node where they occur; corrected nodes become training labels for the judge; a tool-using LLM editor revises questions and subtrees while observing execution results | ShARC 8,276 cases: a tree executed by the host judge 67.70% (2.99 questions/case), on par with asking the final label directly 68.23%; a tree compiled for another judge gets only 47.87% when the judge is swapped, a tree recompiled on the new judge's answers 64.39%; node repair takes BANKING77 82.04%→86.16%; one explicit exemption node cuts false positives on a Chinese e-commerce moderation clause 24→5; the trained editor takes dev accuracy 64.47%→73.35% | [2610.13999](https://arxiv.org/abs/2610.13999) |
| **Probabilistic perception, deterministic adjudication** | Model outputs serve only as **scored observation records**; an admission policy maps scores to true / false / **unknown** under a declared false-positive ceiling; unknown means reject; a deterministic, sufficiency-checked contract adjudicates; the probability that perception changes the adjudication has a **union bound** (sum of each perception field's false-admission rate + unknown rate); minimizing the estimated bound is an effective cost model for choosing contracts | 36,000 calls over 2 domains and 2 sensor families, not one unit refutes the bound; all 13 "reject→allow" flips among 21,000 test adjudications come from 3 contradictory records | [2610.10978](https://arxiv.org/abs/2610.10978) |
| **Clinician-led inspectable rules** | Two clinicians define, finalize and adjudicate a rule base of 4 safety checks, formally verified for internal consistency, used as a guard on LLM output; **every adjudication can be recomputed from one named rule and 16 facts** | The largest disagreement class against a matched Llama-3.3-70B judge is structural | [2610.30690](https://arxiv.org/abs/2610.30690) |
| **Jev-Guard** | An editable **policy tree**: first route on the tree to the applicable policy by the caller's audit context, then classify safety conditioned on the retrieved policy | 93.72% safety accuracy on 7,033 cases at 58 ms; hierarchical routing 93.10%; full pipeline 240 ms | [2610.18326](https://arxiv.org/abs/2610.18326) |
| **JEVDB** | SQL extension: semantic filter, join, classify and sort go to the decision model, uncertain ones escalate to a generative LLM; **a semantic Bloom filter screens candidates with "registered necessary conditions"**; Yannakakis semi-join reduction | Lowest latency on all 21 SemBench queries, lowest cost on 19; Shelob 540K candidate pairs | [2610.02046](https://arxiv.org/abs/2610.02046) |
| **Cost-accuracy optimization of semantic queries** | Expected error from each decision's calibrated confidence, weighted by its contribution to the output (fan-out) to obtain expected output error; the query plan affects both cost and result | Formal problem definition | [2610.08089](https://arxiv.org/abs/2610.08089) |
| **Code Owns the Simulation, Jev Owns the Evaluation** | A clean boundary: what **can be judged from the input description** (evaluation) Jev can do (CRT 99%); what **depends on things beyond the predicted input** (simulation) Jev cannot | Reflection tests, one-shot matrix games, ALFWorld, robot control | [2610.01834](https://arxiv.org/abs/2610.01834) |
| **NIOCIS** | Execution logs → loop-collapsed action graph (forward transitions + recovery back-edges); at each state ask one typed question "which declared option is the next hop + stop"; **node-conditioned option space** | 1,615 production security-operations episodes | [2610.25985](https://arxiv.org/abs/2610.25985) |
| **SharedKV-BT** | Each active node of a behavior tree exposes stage-local fields and candidates, scored in parallel over a shared KV; the selected decision goes to a separate execution system | Robot manipulation | [2610.07327](https://arxiv.org/abs/2610.07327) |
| **NumericJev** | A "range selection" primitive: a multi-way decision tree recursively refines a numeric value | See D2 | [2609.28587](https://arxiv.org/abs/2609.28587) |
| **JevForest** | Feature acquisition within a budget: path votes of bootstrapped trees decide the next question to ask Jev | AG News four questions 0.729 vs static ordering 0.667, random 0.583 | [2610.10615](https://arxiv.org/abs/2610.10615) |
| **LAVOIR** | Places "missing information slots" next to the options; one forward pass returns both the decision distribution and the **value of information** of each slot | Statistically indistinguishable from the Bayes ceiling on seen schemas (encoder family, cited as control) | [2609.30706](https://arxiv.org/abs/2609.30706) |
| **Reading Right** | Fact probes + code composition | Code composition 0.96–1.00 (see D2) | [2610.18579](https://arxiv.org/abs/2610.18579) |

#### 3.2.3.3 Rubric / Checklist Primitives (Upstream)

- TICK: LLM-generated instruction-specific checklists make evaluation interpretable ([2410.03608](https://arxiv.org/abs/2410.03608)); Rubrics as Rewards uses instance-specific rubrics as RL rewards ([2507.17746](https://arxiv.org/abs/2507.17746)); ReVeR derives **hard rules and grading principles** from the instruction itself and judges point by point with tool augmentation ([2610.18766](https://arxiv.org/abs/2610.18766)); rubric adjudication lacks uncertainty and needs criterion-weighted aggregation ([2610.21214](https://arxiv.org/abs/2610.21214)); decision models as rubric judges are "cheap, fast, and wrong in the same places" ([2609.29769](https://arxiv.org/abs/2609.29769)).

### 3.2.4 "Policy-as-Prompt" Guards: Experience of Feeding Business Rule Text Directly to the Model

| Work | Conclusion | Source |
| --- | --- | --- |
| gpt-oss-safeguard (120b / 20b) | Open-weight **reasoning** models that read the developer's policy and the content together and output a conclusion plus reasoning; "reasoning helps the model generalize to newly written policies"; traditional classifiers are fast but need retraining when the policy changes | [OpenAI](https://openai.com/index/introducing-gpt-oss-safeguard/) |
| DynaGuard | Dynamic guard for user-defined policies, with optional CoT | [2509.02563](https://arxiv.org/abs/2509.02563) |
| **SafePyramid** | 1,000 dialogues, 3,000 policies, 61,699 natural-language rules, three levels: L0 single rule, L1 rule dependency, L2 entirely new policy framework defined in context; **the best model, GPT-5.5, exactly identifies all violated rules in only 54.0% / 35.3% / 12.9%** | [2606.29887](https://arxiv.org/abs/2606.29887) |
| **LPG** | Compresses the internal deliberation of policy grounding into 10 latent tokens; a 4B model reaches 84.5% safety accuracy, about 11× faster than Qwen3-4B-Thinking | [2605.17329](https://arxiv.org/abs/2605.17329) |
| Policy-as-Prompt (community governance) | Handing moderation rules to ChatGPT is not enough; the impact on community governance must be considered | [2607.12149](https://arxiv.org/abs/2607.12149), [2502.18695](https://arxiv.org/abs/2502.18695) |
| PolicyGuard | DLP classification criteria defined entirely by a **plain-text policy file editable by non-engineers** | [2608.02687](https://arxiv.org/abs/2608.02687) |
| BARRED / PAM | Train custom policy classifiers from synthesized training data using only a task description + a few unlabeled samples | [2604.25203](https://arxiv.org/abs/2604.25203), [2505.19766](https://arxiv.org/abs/2505.19766) |
| Text de-identification | Natural-language de-identification rules + instruction tuning, outputting auditable rationales | [2608.14693](https://arxiv.org/abs/2608.14693) |
| Multi-turn constraint tracking | StateWise: the model maintains its own revisable constraint state (with tombstones); persistent failures and recurrences measured with executable checkers | [2610.33766](https://arxiv.org/abs/2610.33766) |
| Jev in moderation | Benefits from retrieved precedents; definitions change predictions without stable improvement (see D1) | [2610.07953](https://arxiv.org/abs/2610.07953), [2610.03324](https://arxiv.org/abs/2610.03324) |

**Implication**: even the strongest reasoning models reach exact execution rates of only 35% / 13% on "rule dependency" (L1) and "new policy framework" (L2). For a single-pass model to be reliable, rules must be **decomposed** to single-rule (L0) granularity, with dependencies and composition left to code. This is exactly the structure of SemTree and of "probabilistic perception, deterministic adjudication".

### 3.2.5 Which Works Solve Which Kind of Problem (D3 Mini-Matrix)

| Problem | Existing work | Status |
| --- | --- | --- |
| Can text teach a model to do things | SkillsBench, AFTER | Proven for generative Agents; **none** for single-pass models |
| Rule text → intermediate representation | Artic, P2T, SIRNA, Cedar, ARc, LSP, Deontic trees | Several IRs exist, aimed at generative LLMs / formal verification |
| Separation of judgment points from deterministic logic | FlashScript, TraceCompiler, Formal Skill, LLM-as-interface, Reading Right | **Consensus**: "decisions become calls, the rest becomes code" |
| Trees / contracts on single-pass models | SemTree, probabilistic perception deterministic adjudication, Jev-Guard, JEVDB, NIOCIS, SharedKV-BT | Prototypes exist; SemTree's "compile against the judge's answers" and Unknown nodes are closest to our needs |
| Editing interface for non-technical staff | CALICO, Goldsmith, PolicyGuard, SemTree's node repair | Exist, but only SemTree targets a decision judge |
| Ceiling of direct execution of policy text | SafePyramid | Clear: L1/L2 unreliable |
| Test sufficiency of rules | Skill coverage, SkillSentry, AgenTest | Aimed at generative Agents |

### 3.2.6 D3 Blind Spots

1. **No "rule language" for single-pass decision models**: all IRs (Artic, P2T, Cedar, LSP) assume the executor can reason or can call an evaluator. The subset of rules a single-pass model can execute faithfully (L0 single condition? with one exception?) has not been defined.
2. **The "executability" of primitives has not been graded**: Code Owns the Simulation gives one boundary ("evaluation vs simulation"), Reading Right gives another ("read vs compose"), 2610.24929 gives a third ("solvable in one pass vs needs intermediate steps"). The three boundaries have not been unified into one primitive-level classification.
3. **Unknown / abstain as a first-class primitive**: both SemTree and "probabilistic perception" treat Unknown as a node output, but D2 shows that fallback and refusal are the weakest point of single-pass models. The contradiction between "every primitive must be able to say I don't know" and "the model cannot say I don't know" has not been studied head-on.
4. **Wording invariance of rules**: Lost in the Fallback and 2610.30045 show that equivalent wordings lead to different decisions. A rule language must either prescribe the wording (templates) or train the model to be wording-invariant; no work has taken either path on decision models.
5. **Composition reliability of rules**: SemTree averages 2.99 questions per case; the hierarchical-consistency evidence in D4 (TV 0.219–0.349) shows that probabilities after decomposition are not self-consistent. For "how errors propagate" when several primitives are composed in code, the only formal starting points are semantic query optimization (2610.08089) and the union bound (2610.10978).
6. **Compiling per judge**: SemTree shows that a tree must be compiled for a specific judge (swapping the judge drops 67.70% to 47.87%). This means a compilation step is needed between "the rules the business expert writes" and "the tree the model actually executes", and what that compiler should look like for a small single-pass model has not been studied by anyone.
7. **The separation of Skill and Policy** has not yet appeared on decision models: Auto-Policy points out that the two differ, Jev-Guard's policy tree is a Policy, TypeSafe's agent-skill is a Skill; no work defines both at once and measures their interaction.
