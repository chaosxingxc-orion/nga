# 8 · Review and adversarial check: working hypotheses, the report's own constructs, methodological defects and attacks

> This chapter adds no evidence; it only reviews and attacks. Its reason for existing: the production process of this report is "the questioner gives a proposition → I look for evidence → I write the conclusion", which **satisfies the standard conditions for confirmation bias**; and the framework in §2.2 is a joint product of the discussion, of which I am a co-author, so I am no longer an external reviewer. "Basically reaching agreement" is exactly the moment when adversarial analysis is most needed.
>
> §8.1 rules on the four working hypotheses one by one (three are "conclusion right, mechanism wrong"), marks the eight frameworks in this report that **belong to me rather than to the literature** together with their overfitting risk, lists my own nine methodological defects (including one recorded instance of confirmation bias), and gives a robustness grading of the conclusions plus four blind spots in the questioner's field of view. §8.2 tests the §2.2 framework with seven attacks: **two overturn its wording, three force it to add qualifications, one is undecided and the most important, one is a permanent discount**; it then gives the revised framework and "what evidence would overturn it". §8.3 is the work-question matrix and the blind-spot summary sorted by impact; §8.4 is the list of open questions.
>
> How to read: the P0′–P5′ in §8.2.3 are an **intermediate version**; the final framework wording for the whole report is the P0″–P5″ of §2.2.5, and the ruling on A4 is in the second postscript of §8.2.1.

## 8.1 The four working hypotheses, the report's own constructs and my methodological defects

> Protocol: this section adds no evidence; it only reviews. Sections 14–§5.2 each answer a working hypothesis raised by the questioner, and **the person who raised the hypothesis and the person who tested it are the two ends of the same conversation, which is the standard condition for confirmation bias**. While reviewing §2.1 on 2026-10-28 I found an instance: the first draft treated the proposition "the migration of idempotence" as a foundation, while the evidence overturning its premise **had already been cited by this report itself**, scattered across 04, 05, 06, 09, 10 and §1.4; it simply was not retrieved when §2.1 was written. This section handles this kind of failure systematically: §8.1.1 rules on the four hypotheses one by one, §8.1.2 marks which frameworks in the report are my own constructs rather than literature conclusions, §8.1.3 lists my own methodological defects, §8.1.4 gives a grading of "which conclusions are most robust and which are most likely to be overturned", and §8.1.5 answers "what blind spots lie in the questioner's field of view".

### 8.1.1 Rulings on the four working hypotheses

| # | Hypothesis (raised by the questioner) | Ruling | Direction of conclusion | Mechanism given |
| --- | --- | --- | --- | --- |
| H1 | SFT cannot give a model generalization ability in the general sense (§6.2) | **Strong form does not hold, weak form holds** | **Right** | **Incomplete**: the hypothesis attributes the cause to the "supervised objective", while the evidence shows that what moves results across levels is base-model scale, the instruction-tuned starting point, the supervision distribution and structural constraints |
| H2 | Our business expectations of Jev cannot be directly turned into a differentiable learning function (§6.4) | **Conclusion holds, reasoning does not** | **Right** | **Wrong**: resistance to gradients has four distinct causes; the classes that are genuinely non-differentiable are exactly the classes where measured RL gain is zero, so "non-differentiable → use RL" does not hold |
| H3 | RL should be considered to preserve ICL and skill-like semantic injection at the same time (§6.3) | **Does not hold** | **Wrong** | **Wrong**: what decides whether ICL survives is "whether the task definition changes between training samples"; the only two methods that improve "defining the task from context" (MetaICL, symbol tuning) are both SFT |
| H4 | Jev-class model = converting generative business judgment that does not guarantee idempotence into "indicator output + deterministic idempotent execution in the harness" (§2.1 §2.1) | **Premise does not hold, conclusion needs major revision** | **Partly right** | **Partly wrong**: see the six pieces of counter-evidence in §2.1.3 |

#### 8.1.1.1 A pattern worth noting

Three of the four (H1, H2, H4) have **the right direction of conclusion but a mechanism that is wrong or incomplete**. This is not a coincidence; it is the difference between two sources of knowledge:

- The questioner's judgments come from **deployment and engineering observation**: change the schema and the model stops working, business goals cannot be written as a loss, generative output is unstable. This kind of observation is very reliable about **phenomena**.
- Attributing mechanisms requires **controlled experiments**, and the literature happens to lack controlled experiments at exactly these points: nobody has measured k-shot curves before and after decision fine-tuning (§3.1), nobody has measured Jev's repeat jitter side by side with a temperature-0 generative baseline (§2.1.3 counter-evidence 1), nobody has compared the three numeric routes on the same batch of numeric decisions (§6.5 blind spot 3).

**Corollary**: on this topic, "phenomenon judgments" are far more trustworthy than "mechanism judgments". When there is disagreement, one should keep the questioner's phenomenon and redo the mechanism, rather than accept or reject the whole. H4 was handled exactly this way: its **diagnostic value is high** (it correctly predicted why the fifth cell "closed-loop executor" in §5.1.4 generally fails: the decision was moved back into the model), while its **descriptive claim about idempotence is wrong**.

#### 8.1.1.2 The diagnostic value of H4 should be recorded explicitly

In §1.1.6 I wrote "Jev's value lies in the interface contract, not in the weights". The questioner's version is sharper than mine because it states **what the contract is for**: the point of the contract is not "the output parses well" but "handing the **bookkeeping** of the decision to code". (I first wrote this as "moving decision authority from the model to the code"; the questioner pointed out on 2026-10-28 that this is wrong: **what we build is an AI system, and the core logic is the generalization of semantic understanding**. This objection uses exactly this report's own reductio, since the unconstrained optimum of "move it to code" is likewise a lookup table, so it holds, and the wording has been corrected in §2.1.7.) This version can make a prediction that my version cannot: which kind of deployment will succeed (decision authority in the code) and which will fail (decision authority back in the model). The five-cell table in §5.1.4 agrees with it completely, and that table was written before I heard this proposition. **So the correct attitude here is not "the proposition is wrong" but "the diagnostic part of the proposition should be adopted and the descriptive part replaced".**

### 8.1.2 Which frameworks in the report are my own constructs

Each item below is used as an organizing tool in the main text, but **no paper has ever proposed any of them**. This is where the report is most easily misread as "literature conclusions", so each one is annotated with its basis and its overfitting risk.

| Construct | Where | Basis | Overfitting risk |
| --- | --- | --- | --- |
| **Seven generalization levels L0–L6** | §6.2.1 | Results of about 20 papers sorted by "what changed" and then merged | **Medium-high**. The levels are not orthogonal (L2 new schema and L3 new symbol operations are mixed together in real data), and L5 calibration transfer and L6 reasoning depth each have only two or three pieces of evidence. A different layering might yield a different answer to "which level has positive evidence" |
| **Five classes of differentiability A–E** | §6.4.2 | Classified by "why it resists gradients" rather than by business domain | **Medium**. The boundary between class C (quantile/rank) and class D (downstream long-range) depends on whether you count the certification means as part of the objective or part of the process |
| **Three layers of idempotence L1–L3** | §2.1.4 | Built by me while testing H4, to make the proposition falsifiable | **High**. The three-layer division itself has no literature support; §2.1.3 has already shown that L3 is not a clean layer (it holds only under a fixed plan and fixed load), so this table is missing at least one "load/plan" dimension |
| **Five System1+System2 positions A–E** | §5.1.4 | About 15 systems classified by "who consumes S1's output" | **Medium**. It fits the "guard/routing/classification" family well and is strained on the "memory/monitoring/review" family: SOMA is a control loop of cumulative judgments, Mnemon's S1 output is never executed at all, and this family has exactly the best measured results (LoCoMo 91.7%, highest among 14 systems) |
| **The "decision repetition" axis** | §5.1.1.3 | The common structure extracted from the motivation sentences of three papers (JEVDB, Bellman LM, NIOCIS) | **High**. No paper has quantified "repetition", and no paper has regressed it against gain. It is a **hypothesis** that I am using as a criterion |
| **"Question graph vs token stream"** | §6.5.5.1 | Derived from the cost structure (asking more is nearly free, generating more is metered), then filled in with five existing forms | **Medium-high**. The compositional calibration of "splitting one judgment into n judgments" **has not been answered by any paper** (§6.5 blind spot 5), so the feasibility of this form is inferred, not measured |
| **Twelve business properties P1–P12** | §5.1.2 | Enumerated from the angle of "what the business side would order on" | **Known to be incomplete**. §7.3.1 itself proves this: TUPLE-Bench's "the interface fields themselves are an information leak" is not on the list |
| **The 30 sub-dimensions of D4** | §4.2 | Enumerative exploration; the user explicitly asked to "define and understand the question ourselves" | **Low** (declared as exploration from the start), but **the sub-dimensions are highly correlated** and cannot be treated as 30 independent measurement axes |

**How to read**: for every framework in the table above, sentences in the main text of the form "under this classification, cell X is empty" **should be read as "under this report's classification"**, not as "the literature has proved that X does not exist".

### 8.1.3 My own methodological defects

1. **Confirmation bias, with one instance already.** The process is "the questioner gives a hypothesis → I look for evidence → I write the conclusion". The first draft of §2.1 is the failure case: of the papers behind five of the six pieces of counter-evidence (constraint tax, IIA pre-registration, plans changing answers, control-loop SoK, Koa-decision), **four had already been cited in other chapters of this report**; only [2610.06425](https://arxiv.org/abs/2610.06425) was newly added during review. In other words the failure was not in retrieval but in **not doing a reverse search of existing evidence when writing a new chapter**.
2. **I read only about 70 papers in full; the remaining 212 were read from abstracts.** Numbers in abstracts are often not the paper's main conclusion, and qualifying conditions are often not written into the abstract. In many places this report paraphrases abstract sentences.
3. **One-directional retrieval.** The keywords revolved around Jev / typed decision / System One, which will systematically miss systems that **do not use this terminology but expose the same kind of interface**; the early audit itself admitted this limitation.
4. **No evaluation was run.** All numbers are paraphrased from papers and documents, and §1.4 has already shown that protocols across papers are incomparable (at least five algorithms for ECE, five denominators for flip rate), so any cross-paper comparison can only be qualitative.
5. **All compliance rates come from the coding of a single audit** ([2609.32160](https://arxiv.org/abs/2609.32160), a corpus of 28 papers, a nine-day window); the large number of papers added in the following month has not been re-coded under the same checklist.
6. **The time window is extremely narrow.** The great majority of the evidence is preprints from the six weeks after the Jev release, not peer-reviewed, and several describe themselves as "early evidence".
7. **My "zero hits" statements are the most fragile class of claims.** "No paper has done X" can only be falsified, never confirmed, and it appears dozens of times in this report. Each one should be read as "not found within this report's retrieval scope".

8. **I organized the whole report along the single axis of "business cost" and did not re-walk it along "semantic generalization".** The questioner pointed this out on 2026-10-28, and it caused one identifiable omission: the engineering operation that makes Jev cheap and the operation that destroys rule sensitivity **are the same operation** (Certo's cacheable independent encoding is about 5× cheaper, and rule-sensitivity recall@1 goes 1.00 → 0.24, [2609.37832](https://arxiv.org/abs/2609.37832)), while this report recorded these two facts separately in §5.1.1 (cost structure) and §6.2.3 (generalization levels), **never placed them side by side, and never wrote them up as a trade-off**. When organized along the cost axis, "63× cheaper" is recorded as an advantage, while on the semantic axis the same evidence says "the model is irreplaceable" ([2609.29429](https://arxiv.org/abs/2609.29429)); the same number means something completely different on the two axes.
9. **Three times in a row I ruled the questioner's proposition to "have a degenerate optimum" without pointing out one step earlier that this was the same pattern.** Idempotence → lookup table (§2.1.6), move to code → lookup table (§2.1.7), consistency rate → constant classifier (§2.1.8). All three propositions named the "invariance" half and left the "discrimination" half empty. Writing the three reductios separately let the same structural gap be rediscovered three times, which is itself an organizational failure.

### 8.1.4 Robustness grading of the conclusions

| Robustness | Conclusion | Why |
| --- | --- | --- |
| **Most robust** | The orders of magnitude of cost and latency (1–2 orders of magnitude cheaper, review 16–357× more expensive, local 2B at 30.9 ms versus frontier API at 8,758 ms) | Multiple independent measurements, consistent direction, consistent magnitude, and matching the structural cause "no decoding" |
| **Most robust** | Typed readout itself has no accuracy advantage independent of same-class label-probability readout | Two independent paths: the 28-paper coding of the early audit + an off-the-shelf model reading logits is enough ([2610.02076](https://arxiv.org/abs/2610.02076)) |
| **Robust** | Structural constraints (masking / position reset / block isolation) beat writing consistency into the loss | Multiple papers, consistent direction, and a strong form that "holds by construction" |
| **Robust** | Ordinal scale compression | 40 datasets × 9 models × 3 families, with independent cross-paradigm confirmation (central tendency effect on clinical ordinal scales) |
| **Robust** | Fallback/abstention is the worst cell | Two mutually independent measurements (refusal rate 7%; a fallback option drops Intern from 97.9% to 23.1%) |
| **Medium** | "RL on single-pass models is negative or ineffective" | §6.1 and §6.3 both correctly restrict this to "single-pass / pure readout" and note that "all positive evidence is tied to reasoning chains", so **the wording is fine**; the problem is **the evidence base is too small**. Of the three negative data points, one is an encoder (which by the user's own definition is not our direction anyway), one is small-scale REINFORCE, and one is GRPO inside an Agent loop rather than RL on a readout. Supporting a general conclusion about architecture with three heterogeneous points is thin |
| **Medium** | Five System1+System2 positions | The classification is my own, and it is strained on the "memory/monitoring" family (§8.1.2) |
| **Most likely to be overturned** | "Nobody guarantees L2 semantic idempotence" | This is a zero-hit statement, and it is the most likely retrieval blind spot: relevant work may be published in the robustness/invariance literature without describing itself as related to decision models |
| **Most likely to be overturned** | "Nobody has measured end-to-end cost per correct result" | Same as above. Industrial practice very likely has this protocol but does not publish papers; this report's sources skew academic (the early audit also admitted "industrial experience is underestimated") |
| **Most likely to be overturned** | "Decision repetition" is the main variable of gain | Never quantified or regressed (§8.1.2) |

### 8.1.5 Four blind spots in the questioner's field of view

This is the part this section was asked to answer. For each: the blind spot, why it is a blind spot, and the supporting measurements.

**Blind spot 1: treating "idempotence" as the goal, when what the business actually needs is "boundable risk", and the two conflict under asymmetric costs.**
"Deterministic, idempotent execution" requires collapsing the distribution into one action. But after averaging over respondents, **the probability vector is closer to the human per-item marginal distribution than the rounded answer** ([2610.14912](https://arxiv.org/abs/2610.14912)); confidence conflates human disagreement with decision risk, and under asymmetric loss the two demand **opposite escalation signals**, so **no single confidence number can serve both** ([2610.33258](https://arxiv.org/abs/2610.33258)). The genuinely operational goal is something else: treating the output as an "observation record with scores" and letting unknown refuse directly yields a **calibration-free** upper bound on verdict flips, on which one can choose among multiple sufficient contracts ([2610.10978](https://arxiv.org/abs/2610.10978)). **Boundable > idempotent**, and the former can hold when the latter does not.

**Blind spot 2: the proposition treats the harness as a trustworthy deterministic layer, while the harness itself changes answers.**
In semantic query engines "**the choice of query plan affects not only cost but also results**"; accuracy is plan-independent **only under pointwise deterministic policies**, and when the escalation band is calibrated on the plan's own candidates, **selection pushdown is not quality-reliable** ([2610.08089](https://arxiv.org/abs/2610.08089)). A systematic survey of 139 paper families is more direct: 50 families claim to fit a control loop, **only 4 support it with matching measurements**; of the 139, **only 4 report deadline attainment**; and "a decision that meets a 10-second budget for every isolated request fails it for every request once the decision is queued before a replayed execution time" ([2610.06425](https://arxiv.org/abs/2610.06425)). **Moving the hard part into the harness is not the same as solving it**; once moved, it becomes a queueing-theory and query-optimization problem, and almost nobody in the existing Jev literature measures either.

**Blind spot 3: the proposition implicitly assumes "conservation of capability", so it underestimates the loss of multi-step / stateful business logic, and the harness receives no signal of this loss.**
This is the most dangerous item for deployment. Jev cannot make decisions that "an LLM can only make by writing out intermediate steps" (items solvable in one forward pass 97.5%, the rest **74%**); when the answer depends on two or more updates from the same user, accuracy drops, to 53%–80% at sixteen updates; given a stale state summary, it answers from the stale summary. And **it does not know its own limits**: confidence flags the errors it makes itself but cannot flag the errors it inherits from stale inputs, and **neither explicit nor trained handoff options catch the latter** ([2610.24929](https://arxiv.org/abs/2610.24929)). The "indicator + deterministic execution" architecture has **no usable signal** for this class of failure; what the harness sees is a high-confidence, type-valid, semantically wrong value. Combined with the "constraint tax" finding (a hard schema raises "valid but wrong" from 49.5% to 88.9%, [2605.26128](https://arxiv.org/abs/2605.26128)), this is the only place in the whole architecture where **the failure mode is more hidden than in the alternative**.

**Blind spot 4: the premise "driven by usable configuration (prompts)" has itself never been validated by any evaluation.**
The proposition starts from "generalized, flexible, configuration-based business processing ability of a generative model". But in all the evidence for D1, the prompts were written by **researchers**; no evaluation set treats "the author of the rules/criteria/examples is a non-technical business expert" as a variable (§7.5 item 3, §5.1.5 blind spot 6). And the known failure modes land exactly where business staff are most likely to step: **label names override definitions** (AUC 93.8% → 23.2%), deleting the definitions leaves accuracy unchanged, small models cannot flip label semantics in context, homogeneous examples collapse small models to below 12% (§3.1). **"Configurable" is an assumption in this literature, not a measured property.** If it does not hold, then of the two halves the proposition splits out, the "model + prompt configuration" half has a weaker source of capability than the proposition assumes.

### 8.1.6 Summary of this section

- Of the four working hypotheses, three have **the right direction of conclusion and the wrong mechanism** (H1, H2, H4), and one does not hold (H3). When there is disagreement, keep the phenomenon and redo the mechanism.
- H4's **diagnostic value should be adopted** (it correctly predicted which kind of deployment fails), and its **descriptive claim should be replaced** (idempotence is not what it does; what it does is shrink a non-idempotent surface down to a few boundable fields).
- Eight frameworks in the report are **my own constructs**, of which "three layers of idempotence", "decision repetition" and "question graph" carry the highest overfitting risk.
- Among my own methodological defects, the one most worth guarding against is **confirmation bias**, and there is already one instance: most of the counter-evidence material for the first draft of §2.1 was already in this report; a reverse search was simply not done when writing the new chapter.
- The dozens of "no paper has done X" statements should all be read as "not found within this report's retrieval scope"; of these, "nobody guarantees L2" and "nobody has measured end-to-end cost" are the most likely retrieval blind spots.

## 8.2 Seven adversarial attacks on the §2.2 framework

> **Reading note**: this section was written after the fourth round of the discussion, and its target is the six statements P0–P5 agreed at that time (their revised version P0′–P5′ is in §8.2.3). After the sixth round of the discussion (the "multiple questions on the same state" example in §2.2.1), **A1 was resolved and A4 was upgraded to a backbone-specific version**; the final framework is the P0″–P5″ of §2.2.5. This section keeps the original text and adds postscripts at A1 and A4, to preserve the trail of reasoning.

> Protocol: this section adds no evidence; it only restructures the logic. The four rounds of discussion on 2026-10-28 switched the organizing axis of this report from "**business cost**" to "**the generalization of semantic understanding**", and switched the main metric from accuracy to the consistency rate on equivalence classes. §2.2 first writes the agreed framework as six falsifiable statements; **the task of the remaining sections is to attack it**.
>
> Why the attacks take more space than the statements: §8.1.3 already recorded that this report's production process (the questioner gives a proposition → I look for evidence → I write the conclusion) satisfies the standard conditions for confirmation bias, and **the conditions now are worse than they were then**: this framework is a joint product of the discussion, I am its co-author, and I am no longer an external reviewer. "I feel we have basically reached agreement on the approach" is exactly the moment when adversarial analysis is most needed.
>
> Conclusions first: of the seven attacks, **two overturn the framework's wording** (A1: the equivalence class is itself a non-idempotent judgment; A3: "the model handles semantics, the code handles bookkeeping" has no boundary), **three force the framework to add qualifying conditions** (A2: pre-registration; A5: it is a system metric, not a model metric; A6: do not present ordinary multi-objective optimization as a discovery), **one is undecided but the most important** (A4: the semantic axis and the cost axis may be directly opposed at the architecture level), and **one is a permanent discount** (A7: each of the four load-bearing points rests on a single paper). The revised framework is in §8.2.3.

### 8.2.1 The seven adversarial attacks

#### A1 The equivalence class is itself a judgment, and exactly the kind of judgment we want to get rid of: **overturns the wording of P1**

P1 hands the "denominator" problem to "business-declared equivalence classes". But **who declares them?** When a business expert says "these two cases are equivalent", that statement is itself a generalized, semantics-based judgment that does not guarantee idempotence, isomorphic to the kind of judgment we want to replace. So P1 does not solve the problem; it only **moves it up one layer**, and the new location has fewer measurements than the old one.

Evidence supporting this attack:
- Artifacts written by the business side are **systematically defective**: of 138,133 public SKILL.md files, **91.8%** have at least one defect (CI 88.8–94.6%), mainly weak routing metadata and bloated, non-executable bodies ([2608.08453](https://arxiv.org/abs/2608.08453)). There is no reason to think "equivalence-class declarations" would be written any better.
- Rule artifacts **must be compiled for a specific model**: a SemTree tree compiled for judge A drops from 67.70% to **47.87%** when moved to judge B ([2610.13999](https://arxiv.org/abs/2610.13999)). Must equivalence-class declarations then also be recompiled per model? If so, they are not a business artifact but a model artifact, and the words "business-declared" in P1 do not hold.
- Worse, there is a **cycle**: if the equivalence classes cannot be enumerated (which is exactly why generalization is needed), then deciding "are these two situations of the same kind" requires a model, so **the consistency of the metric depends on the consistency of the metric's own model**.
- And the equivalence class is precisely **where business risk hides**: "are two loan applications that differ only in zip code equivalent?" is a fairness ruling, not a measurement. Writing it into the denominator hides the most contested judgment inside the metric definition.

**Ruling: the attack holds, P1 must be rewritten.** The defensible version is not "business-declared equivalence classes" but "**versioned, held-out, audited equivalence-class declarations**": that is, treat the equivalence class as **an artifact that needs governance**, a newly added non-idempotent source in the system, which must be listed as a risk item rather than taken as the reliable base of the metric. This has been written into P5′ in §8.2.3.

**Postscript (after the sixth round): A1 has been resolved, and not by patching but by dissolution.** The equivalence class does not need to be declared separately: it is **induced by the question**. "I eat rice" and "I eat milk" are of the same kind under "did you eat a meal" and of different kinds under "did you drink a liquid", and questions are already first-class objects of the interface (§2.2.1). But omission 2 in §2.3 points out that this holds only for **human-written, offline** questions; questions generated at runtime by S2 inside an Agent loop bring A1 back unchanged.

#### A2 The consistency rate is unfalsifiable when the equivalence classes are chosen after the fact: **P1 gains a pre-registration condition**

Any consistency rate can be engineered by picking the equivalence relation. Stack A1 on top of this: if we declare the equivalence classes and we also report the consistency rate on those classes on the same batch of data, that is **in-sample fitting**, and this report has already cited its price: one paper fitted its threshold in-sample, targeting 5% while the held-out set went as high as **17%** ([2610.02267](https://arxiv.org/abs/2610.02267)); the same paper corrected "saves 23.9%" to **4.3%** and reported gate accuracy as end-to-end quality, 58% versus 98%.

The literature already has templates that do this right: the IIA study **pre-registered** its hypotheses and then ran 299,463 calls ([2610.16655](https://arxiv.org/abs/2610.16655)); the union-bound study is **pre-registered** with 36,000 calls ([2610.10978](https://arxiv.org/abs/2610.10978)).

**Ruling: the attack holds and a remedy is available.** The usable form of P1 must be written as "decision consistency rate on **pre-registered, held-out** equivalence classes". A consistency rate that is not pre-registered is not evidence.

#### A3 "The model handles semantics, the code handles bookkeeping" has no boundary: **overturns the wording of P0**

This dichotomy sounds clean, but the report contains three pieces of evidence that **bookkeeping carries semantics**:

| What is treated as "bookkeeping" | How it carries semantics |
| --- | --- |
| Option table (configuration) | Every option added shifts the log-odds between the gold label and the strongest wrong label; the systematic shift is **1.2–3×** the model's own rerun fluctuation ([2610.16655](https://arxiv.org/abs/2610.16655)) |
| Query plan (execution) | "The choice of query plan affects not only cost but also results"; accuracy is plan-independent **only under pointwise deterministic policies** ([2610.08089](https://arxiv.org/abs/2610.08089)) |
| Decision-tree structure (compiled artifact) | A tree compiled for judge A drops **19.8 points** when moved to judge B ([2610.13999](https://arxiv.org/abs/2610.13999)) |

**Ruling: the attack holds, but it points to a precise repair.** The common factor: **whenever the parameters of the code are fitted on the model's own outputs or candidates, that code carries semantics and the dichotomy breaks**. This is exactly the boundary measured by [2610.08089](https://arxiv.org/abs/2610.08089): "when the escalation band is calibrated on the plan's own candidates, selection pushdown **is not quality-reliable**". So the defensible version of P0 needs a condition: **the parameters of the code may only be fitted on held-out ground truth, never on the model's own candidates**; when this condition is met the dichotomy holds, and when it is not, bookkeeping is part of the semantics and must be evaluated as semantics.

#### A4 The semantic axis and the cost axis may be directly opposed at the architecture level: **undecided, and the most important item**

This is the deepest attack on P0 + P5, because it hits not the wording but the **architecture**.

- If semantic sensitivity requires **joint encoding** (reading state + rules + candidates together), then the skeleton "shared state prefix + isolated question branches + list-style readout", copied by more than 15 open-source reproductions, **is structurally opposed to the core logic we just agreed on**. Measured: the joint scorer has rule-sensitivity recall@1 **1.00**; switching to cacheable independent encoding (about 5× cheaper at 77 candidates) drops it to **0.24** ([2609.37832](https://arxiv.org/abs/2609.37832)).
- The counter-evidence is just as strong: under the standard architecture, **one generic question** zero-shot across 44 benchmarks reaches a median AUROC of 0.886 and beats most supervised baselines ([2609.29429](https://arxiv.org/abs/2609.29429)). Semantic generalization has at least one strong example alive on the cheap architecture.

One paper on each side, with different backbones, tasks and readout methods; **this report cannot rule on it**. And the consequences are heavy: if A4 holds, then "continued training of Jev-style readout on a small Qwen" is optimizing the **wrong architecture** for the goal we just agreed on.

**Ruling: undecided.** This is the evidence gap this report most needs filled (see §8.2.2), and it is a row that should be added to the "most likely to be overturned" grade in §8.1.4.

**Postscript (after the sixth round): A4 now has a sharper, backbone-specific version.** "Multiple questions on the same state" requires the state to be encoded once and each question to project separately; this is exactly the shared-prefix + isolated-branch architecture. But the shared prefix is computed **while the question is unknown**: under an attention-only backbone the KV cache keeps token-level detail and the question branch can "re-read" the state; while in the 64 layers of Qwen3.5/3.8-27B, **48 are recurrent layers**, the shared prefix reuses a recurrent state snapshot (§1.3.2), and what the question branch gets is a **question-independent fixed-length summary**. Prediction: questions that need non-salient aspects of the state will fail, and fail silently. This is row 11 of the defect registry (§2.2.4), and the control (hybrid vs attention-only, same state, N questions, binned by aspect salience) can be run now.

**Second postscript (after the eighth round): A4 is ruled by a design choice and is no longer undecided.** The order fixed by the questioner is task definition → input → candidate branches, with the encoding of the input conditioned on the task definition (the expensive, rule-sensitive side in Certo; the direction of Bongard's third stage, [2609.39111](https://arxiv.org/abs/2609.39111)), and cross-sample caching along the axis "the same set of rules" rather than "the same input, multiple questions". So the attack "the cheap operation and the operation that destroys rule sensitivity are the same one" still holds; we simply chose the side that pays: what is lost is Jev's "additional questions nearly free", what is kept is the one to two orders of magnitude from "no decoding" (§2.2.5 P5″). The residual is backbone-specific: on the hybrid backbone the channel through which candidate branches see the input is 16 attention layers verbatim + 48 recurrent layers of compression; defect 11 is rewritten as "candidate branches see the input through recurrent layers", and the control experiment (local Qwen3-0.6B attention-only versus Qwen3.5-0.8B hybrid) remains the first structural experiment to run.

#### A5 "Decision consistency rate" is a system metric, not a model metric: **P1 and P2 gain qualifications**

Two independent reasons:

1. **Conflict with asymmetric costs.** After averaging over respondents, **the probability vector is closer to the human per-item marginal distribution than the rounded answer** ([2610.14912](https://arxiv.org/abs/2610.14912)); confidence conflates human disagreement with decision risk, and under asymmetric loss the two demand **opposite escalation signals**, so **no single confidence number can serve both** ([2610.33258](https://arxiv.org/abs/2610.33258)). If the main metric is the consistency rate of "decisions", optimizing it will collapse the distribution into one action, and that throws away exactly the information that decisions under asymmetric costs need.
2. **A "decision" exists only after the threshold.** So decision consistency is a property of (model + threshold + contract), and **no model-level version exists**. And the threshold is fitted after training, so "using decision consistency as a training objective" is circular in time.

**Ruling: the attack holds, the framework must be layered.** Usable form: the **system-level** main metric is the decision consistency rate on pre-registered equivalence classes; the trainable proxy at the **model level** can only be **the ordinal stability of the scores** (which happens to match "the readout is ordinal in the first place, not probabilistic": ordinal-layer error 4.2 points versus probability-layer 21.0 points, §6.5.2.2). Mixing the two layers mistakes a system metric for a model objective.

#### A6 The pair "invariance + discrimination" is nothing new in itself: **prevents packaging ordinary multi-objective optimization as a discovery**

Expanded, P4 is "constrained multi-objective optimization", which is textbook content. If the framework's contribution is stated as P4, it has no contribution.

**Ruling: the attack partly holds, and the credit must be limited.** The new part is only three items, and all are **concrete fixed choices** rather than general principles: (a) which invariance to use: not byte-level rerun (already at ICC 0.997 / flips 0.17%, no gain to be had), not order permutation (purchasable by construction, Prism-1 zero flips), but **pre-registered business equivalence classes**, which nobody has defined; (b) where idempotence should live: in the threshold and the deterministic contract, with a bound that **does not depend on calibration**; (c) where the trade-off should be priced: cost and semantics are the same knob (A4). Apart from these three, P4 should be treated as a restatement of common sense, not a discovery.

#### A7 Each of the four load-bearing points rests on a single paper: **permanent discount**

| Load-bearing conclusion | Sole source |
| --- | --- |
| Calibration-free union bound (the foundation of P2, P3) | [2610.10978](https://arxiv.org/abs/2610.10978) |
| Cost and semantics are the same knob (P5, A4) | [2609.37832](https://arxiv.org/abs/2609.37832) |
| The metric is a menu-relative quantity (the core counterexample for A3, L2) | [2610.16655](https://arxiv.org/abs/2610.16655) |
| Semantic generalization is alive on the cheap architecture (the strongest support for P0) | [2609.29429](https://arxiv.org/abs/2609.29429) |

All four are preprints from the six weeks after the Jev release, not peer-reviewed. **If any one fails to reproduce, the framework loses a pillar**; two of them (union bound, IIA) are pre-registered studies, the two most credible of the four, and the other two are not.

**Ruling: this is not a defect that can be patched; it is a discount that must stay attached to the framework permanently.**

### 8.2.2 The evidence missing to rule on these disagreements (gaps, not plans)

Following the protocol of §8.4, the undecided parts above are written as "which measurement is missing", not "what should be done":

| Gap | Which attack it rules on | Closest existing thing |
| --- | --- | --- |
| **Side-by-side measurement of "joint encoding vs cacheable independent encoding" on the same backbone, same data, same task, reporting rule sensitivity and unit price together** | **A4** (most important) | Certo reports both ends only in its own setting ([2609.37832](https://arxiv.org/abs/2609.37832)); nobody has done a cross-setting control |
| **Consistency rates reported side by side on the four denominators**: byte-level rerun / order permutation / answer-preserving adversarial variants / **pre-registered business equivalence classes** | **A1, A2** | The first three denominators each have a paper (0.17%, 0.11%–8.30%, 46.3%); **the fourth has never been defined** (§7.5 row 13) |
| **k-shot curves before and after decision fine-tuning**, plus controls with the name-definition swap protocol, rendering fixes and symbol tuning | Whether P0 can be repaired (whether semantics can be read back) | Rendering fix **+0.1511** ([2610.02586](https://arxiv.org/abs/2610.02586)), symbol tuning improves flipped in-context label semantics ([2305.08298](https://arxiv.org/abs/2305.08298)), **neither has been tried on a decision model**; nobody has measured k-shot curves (§3.1 blind spot 1) |

### 8.2.3 The framework that remains after the attacks

> This subsection is the **intermediate version** (P0′–P5′). The final version P0″–P5″ is in §2.2.5; the differences are: equivalence classes are induced by questions (P0″), the main metric becomes the pair "within-question invariance / cross-question re-partition" (P1″), accuracy is a third leg rather than a supplement to the floor (P2″), and the cost trade-off is bounded as "losing 'additional questions nearly free', not losing one to two orders of magnitude" (P5″).

Folding in the five attacks that hold, the defensible version is:

> **P0′** The model maps open-world situations into typed observations with a scale; the code does arithmetic on top of the observations, **and the parameters of the code may only be fitted on held-out ground truth, never on the model's own candidates**. When this condition is not met, "bookkeeping" carries semantics and must be evaluated as semantics.
>
> **P1′** The system-level main metric is the decision consistency rate on **pre-registered, held-out** business equivalence classes. The trainable proxy at the model level can only be **the ordinal stability of the scores**; the two layers must not be mixed.
>
> **P2′** Accuracy is a **declared floor**, and it must be measured with the decision-level paired protocol (cumulative failure set, equivalence-class flip rate), not with aggregate accuracy: across 8 orderings accuracy changes by **<2 pp** while the cumulative failure set grows by **27–29%** ([2610.35826](https://arxiv.org/abs/2610.35826)).
>
> **P3′** Idempotence lives in the threshold and the deterministic contract; the three requirements on the model side are a monotonic thresholdable score, native unknown (currently the worst cell: correct refusal rate **7%** when the answer is absent, up to **79%** with a fitted threshold), and invariance within equivalence classes.
>
> **P4′** Every invariance is paired with a discrimination. This item is a restatement of common sense; the credit lies only in the fixed choice of "which invariance to use" (A6).
>
> **P5′** Unit price is the enabling condition. **The equivalence-class declaration is a newly added non-idempotent source in the system** and must be versioned, held out, audited and listed as a risk item. Any means of trading cost for semantics must be priced explicitly, and this trade-off is currently **undecided** (A4).

### 8.2.4 What evidence would overturn this framework

| If observed | What is overturned |
| --- | --- |
| On pre-registered business equivalence classes, the consistency rate of typed single-pass readout is **not better than** same-backbone label log-probability readout | The entire motivation for P0 and P1: the Jev-class interface would then have no consistency advantage either, only cost |
| Joint encoding and cacheable independent encoding show **no significant difference** in rule sensitivity | A4 dissolves, and the "explicit pricing" in P5 is downgraded to a secondary clause; this is **good news** for the framework |
| The union bound is overturned in some cell by a third-party reproduction | The foundation of P2 and P3 (sole source, A7) |
| Rendering fixes + symbol tuning **cannot** repair "names override definitions" | The repairability of P0: semantic generalization may be unreachable on this interface, in which case "the core logic is semantic generalization" is only a wish |
| The k-shot curve flattens after decision fine-tuning | The premise that business staff can configure it (§5.1.5 blind spot 6, §8.1.5 blind spot 4) |

### 8.2.5 Summary of this section

1. **Reaching agreement is not passing a test.** This framework is a joint product of the discussion, I am a co-author, and the conditions for confirmation bias are worse than those recorded in §8.1. That is why the attacks in this section take more space than the statements.
2. **Of the seven attacks, two of the framework's wordings are overturned** (the equivalence class is not a reliable base but a newly added non-idempotent source; "the model handles semantics, the code handles bookkeeping" holds only when "the code's parameters are not fitted on the model's candidates"), **three must gain qualifications** (pre-registration, separating the system level from the model level, credit only for the fixed choices), **one is undecided and the most important** (whether cost and semantics are opposed at the architecture level), **one is a permanent discount** (each of the four load-bearing points rests on one paper, two of which are not pre-registered).
3. **The framework is not weakened by this; it becomes falsifiable.** §8.2.4 lists five observations that would overturn it, and the measurements for three of them **can be made now** (consistency rates side by side on the four denominators, the joint vs independent encoding control, k-shot curves before and after decision fine-tuning).
4. **The one thing most worth remembering**: all three propositions (idempotence, move to code, consistency rate) named only "invariance" and left "discrimination" empty, and their unconstrained optima were lookup table, lookup table and constant classifier respectively. This is a **pattern**, not three coincidences: when the next proposition is raised, first check whether its unconstrained optimum is a degenerate model.
## 8.3 Work-problem matrix and blind-spot summary

> This section compresses the conclusions of 01–08 into two tables: (1) for each dimension, "which class of problem is solved by which works, and to what degree"; (2) a cross-dimension list of blind spots, ordered by how directly "we would run into them when training our own Jev-class model". Details and numbers are in the respective chapters; this section only gives the index.

### 8.3.1 Overview of the Five Dimensions

| Dimension | Problem restated (in the user's terms) | Solved | Partially solved | Unsolved |
| --- | --- | --- | --- | --- |
| **D1 ICL** | Whether a single-pass model retains ICL after decision fine-tuning; how to exploit it; which prompt levers business staff can use | Option names and definitions are the strongest levers (03 §3.1.2.2); in-state examples/precedents work (JevKT, review precedents) | The effect of example count and format has only indirect evidence; upstream ICL mechanisms (label space, format, symbolic circuits) have not been verified on decision models | **No direct measurement of whether decision fine-tuning preserves or destroys ICL**; the effect of prompts written by non-technical staff has not been measured |
| **D2 Symbolic instructions** | Whether the model faithfully executes explicit symbolic rules (thresholds, dates, negation, fallback) | "Read"-type factual probes are stable (Reading Right 0.96–1.00 with code composition) | Negation/hierarchy have label-free metrics; arithmetic/date boundaries are clear (the vendor recommends putting them in code) | **Refusal/fallback is the weakest link** (99%/7%, 97.9→23.1); no mitigation for equivalent-wording invariance |
| **D3 Rule language** | Give non-technical experts a set of logic primitives to write business rules in text, which the model executes faithfully | The Skill paradigm works for generative Agents (+16.6); NL→IR compilers have multiple intermediate representations | SemTree (Yes/No/Unknown trees, compile-per-judge) and probability-aware deterministic adjudication (union bound) are prototypes on single-pass models | **No rule language targets single-pass models**; primitive executability is not graded; the Unknown primitive conflicts with "the model cannot say it does not know"; L1/L2 rules (dependency / new framework) reach only 35%/13% even on reasoning models |
| **D4 Consistency** | Define and measure all factors that change the probability of "the same judgment" | Order (structural mitigation), prior shift (EM/KL anchors), repeatability | 26 of the 30 sub-dimensions have definitions and metrics | **Mitigation covers only 2 items**; version drift and teacher bias have no empirical evidence; no unified consistency benchmark; zero evidence in Chinese |
| **D5 Agent/knowledge** | Whether fast/slow cooperation can replace "slow thinking + execution feedback" | Memory selection/judgment (pre-registered non-inferiority); domain Agents whose action space is enumerated by code | Four classes of switching signal, but confidence ≠ "needs thinking"; S1 monitoring S2 has only SOMA | **Cheaper does not mean better** (three opposing papers); no standard for benefit accounting; no work on knowledge-structure maintenance; rule/LR baselines are often sufficient |
| **08 Backbone** | Constraints a hybrid backbone places on the Jev-style interface | Inference-time isolation (row-by-row / forking) is feasible | Selective adaptation, bidirectional reading of attention layers | **No literature on training-time branch isolation**; no controlled comparison of hybrid vs attention-only at equal parameter count |

### 8.3.2 Work → Problem Matrix (Main Works)

Columns = dimensions; cell = the type of contribution the work makes to that dimension: **E** evidence (measured the problem), **M** mitigation (gives a usable method), **T** tool/benchmark, **N** opposing evidence.

| Work | D1 | D2 | D3 | D4 | D5 | 08 |
| --- | --- | --- | --- | --- | --- | --- |
| TypeSafe documentation (primitives / patterns / jaggedness / cookbooks / agent-skill) | M | E | M | E | M | — |
| Archer Hume architecture probe | — | — | — | E | — | E |
| Kev | — | — | — | T(permute) | — | M(row-by-row) |
| qwen-rlcd | — | — | — | — | — | M(forking) |
| StartLux-Decision | — | — | — | M(calibration) | M(AutoThink) | M(bidirectional) |
| Releasing Inner Jev / LLM-as-Jev / LDM / FunDM / AnyJev | — | — | — | E(readout) | — | — |
| OneJev / Open-Jev / Tev1 / Nimble / Intern-Decision / Chinese Decision | — | — | — | E | — | E(latency) |
| PACT / Prism-1 / Runoff / Block-causal | — | — | — | M(order) | — | — |
| SanSi / LEV | — | — | — | — | M(depth) | — |
| 2609.26758 option names / 2610.02586 definitions | E, M | — | E | E | — | — |
| JevKT / review precedents / MemCom / cheat-sheet / Jev-LDE | E | — | — | — | — | — |
| CALICO / Goldsmith | M | — | M | — | — | — |
| In-context fixation / semantic anchors / schema | E(upstream) | — | — | — | — | — |
| Reading Right | — | E, M | M | — | — | — |
| Negation axioms 2609.33209 / hierarchy 2609.33971 / conjunction 2610.19619 | — | E | — | E | — | — |
| Refusal bottleneck / Lost in the Fallback / legal abstention / refusal transfer / retirement gate | — | E | E | E | — | — |
| JevOut / JevAdvBench / option channel / Same Attack / TrustJev / DICE | — | E | — | E | N | — |
| 2610.30045 wording / tables 2610.19536 | — | E | — | E | — | — |
| IIA 2610.16655 / selection bias 2610.35826 / request independence 2610.14631 | — | — | — | E | — | — |
| Multiple-correct 2610.29217 / ordinal compression 2609.38827 | — | — | E | E | — | — |
| Self-knowledge 2610.01006 / two kinds of uncertainty 2610.33258 / literal lock-in 2610.22526 | — | — | — | E | — | — |
| Prevalence shift 2610.26325 / SHIFT-JEV | — | — | — | E, M | M | — |
| Teacher bias 2610.26797 | — | — | — | E(theory) | — | — |
| SemTree | — | — | M | E(version) | — | — |
| Probability-aware deterministic adjudication 2610.10978 / semantic query optimization 2610.08089 / JEVDB | — | — | M | M(composition) | — | — |
| Jev-Guard / SafePyramid / LPG / gpt-oss-safeguard / PolicyGuard | — | — | E, M | — | M | — |
| Artic / FlashScript / TraceCompiler / Formal Skill / P2T / SIRNA / Cedar / ARc / LSP | — | — | M(IR) | — | — | — |
| SkillsBench / 138K SKILL.md / Skill coverage / SkillSentry / Auto-Policy | — | — | E | — | — | — |
| Code Owns the Simulation / What Can't Jev Decide | — | E | M(boundary) | E | N | — |
| When Faster Decisions… / Good Judgment Bad Advice / JevAgentHarness / Microtask / Measure Before You Train / JEVal | — | — | — | — | N, M | — |
| System1-Arena / Fast Models Slow Evidence / DecisionPivot / TypedBench | — | E | — | E | T | — |
| Selective Reasoning / SOMA / System Switch / VoI / Truncated Reasoning / TORSI | — | — | — | — | M | — |
| Selection vs extraction / Mnemon / Jev-Mem / SJC / compression for follow-up questions | — | — | — | — | E, M | — |
| REFLEX / Jev-LiteMAS / S1-MAS / BLADE / Jarvis | — | — | — | — | M | — |
| Jev-Mobile / JEV-Star / SearchJev / JevCoder / Decision4Rec / NIOCIS | — | — | M(action space) | — | M | — |
| Claim Laundering / Jev-DLC | — | — | — | E | E, M | — |
| Marconi / FastJEV / Hydragen / DeFT / Block-Attention / IPPD / Visual Jev / selective adaptation | — | — | — | — | — | M |

### 8.3.3 Blind-Spot Summary (Ordered by Impact on Our Own Training Work)

#### Tier 1: Directly Decides Whether a Training Recipe Can Stand

1. **Whether decision fine-tuning preserves ICL (D1)**. All reproductions report only accuracy/ECE; nobody has measured "how much in-state examples change the decision" before and after fine-tuning. If RLCD / soft-label distillation wipes out ICL, the premises of both D1 and D3 fail.
2. **No literature on training-time branch isolation on hybrid backbones (08)**. The whole Qwen3.5 series is a DeltaNet hybrid; Kev trains row-by-row, qwen-rlcd defers the question. Either prove that gradients pass correctly through the copied recurrent state, or accept the row-by-row cost, or switch to an attention-only backbone: none of the three paths has public numbers.
3. **No empirical evidence on teacher-bias inheritance (D4-D5)**. Small model + Jev labels (AgentDecision-4B) or + large-LLM labels (Releasing Inner Jev) is the mainstream recipe; theory says the student inherits the teacher's IIA/ordinal/negation defects and more data does not remove them; nobody has measured it.
4. **Refusal/fallback/Unknown (D2-F6, D3 blind spot 3)**. A rule language needs a "don't know" primitive; single-pass models are weakest on exactly this item; the only mitigation is one instance of a ternary contract (retirement gate).

#### Tier 2: Decides the Shape of the Rule Language

5. **No rule language targets single-pass models**; primitive executability is not graded by "read / compose / needs intermediate steps" (D3).
6. **Contradictory evidence on question-form equivalence** (Noul normalization vs Choice, medical +, intent −8.7): every primitive must be tested individually on the target model (D4-B6).
7. **No mitigation for equivalent-wording invariance** (D2/D4-C3): a rule language must either template the wording or train for invariance; neither has been done.
8. **Decomposed probabilities are not self-consistent** (TV 0.219–0.349, reconstruction −22.9): node probabilities in a rule tree cannot simply be multiplied (D4-C1).
9. **Compile-per-judge** (SemTree 67.70→47.87): a compilation step is needed between the business rules and the tree the model actually executes, and it changes with the model version (D3-6, D4-A3).

#### Tier 3: Decides Deployment and Evaluation

10. **No unified consistency benchmark**; decision-level paired evaluation is not the norm (D4).
11. **No standard for benefit accounting of fast/slow cooperation** (D5-1); confidence is not a "needs thinking" signal (D5-2).
12. **Rule / logistic-regression baselines are often sufficient**, but no work compares them systematically (D5-4).
13. **S1 training data must include post-error states, and S1 trusts the record over the observation**: neither has entered any recipe (D5-5).
14. **Evidence for Chinese / enterprise scenarios is close to zero**: consistency, Agents and rule languages are all on English public data; in Chinese there is only CJ-Bench's accuracy and ECE (D4-E5, D5-7).
15. **Knowledge-structure maintenance** (ontologies, rule-base versioning) has no work (D5-6).
16. **No controlled comparison of decision quality for hybrid vs attention-only at equal parameter count** (08).
## 8.4 List of open questions (without solutions)

> Terms: "this stage keeps only analysis and survey work... understand the problem first". This section **gives no training plan**; it only rewrites the blind spots of §8.3 as answerable questions and, for each question, names the measurement method already available in the literature (or points out that the measurement itself is also missing). The purpose is to give the next stage's experiments a clear statement of "what was answered".

### 8.4.1 D1: Retention and Use of ICL

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q1.1 | Before and after decision fine-tuning (LoRA / full-parameter / RLCD / soft-label distillation), how much does the marginal effect of k in-state examples on the decision change? | Upstream: example-count vs accuracy curves; the label-slot test of In-context fixation ([2605.08295](https://arxiv.org/abs/2605.08295)); JevKT's zero-data AUC ([2610.11135](https://arxiv.org/abs/2610.11135)) | No standard definition of "example effect" on decision models; needs a paired design (same state ± examples) |
| Q1.2 | Is the effect the same when examples are placed in the state (JSON array) versus in the question's `examples` field? | The two placements in the vendor API ([state documentation](https://docs.typesafe.ai/concepts/state)) | No controlled comparison |
| Q1.3 | When example labels conflict with option names, which wins? (The decision-model counterpart of In-context fixation's "label slot") | [2605.08295](https://arxiv.org/abs/2605.08295), [2609.26758](https://arxiv.org/abs/2609.26758) | None |
| Q1.4 | How much worse is decision quality with option names / definitions / examples written by non-technical staff than with those written by experts? | The expert editing workflows of CALICO / Goldsmith ([2609.14726](https://arxiv.org/abs/2609.14726), [2610.09489](https://arxiv.org/abs/2610.09489)) | **No measurement of "author expertise → decision quality"** |
| Q1.5 | Does the finding that definitions can be removed (0.8487→0.7971) hold for Chinese business rules? | The removal / contradiction / inversion design of [2610.02586](https://arxiv.org/abs/2610.02586) | No Chinese data |

### 8.4.2 D2: Symbolic Instructions

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q2.1 | Which symbolic operations are reliable within a single pass (comparison, containment, date ordering) and which are not (arithmetic, counting, multi-hop)? | Reading Right's factual probes + code composition ([2610.18579](https://arxiv.org/abs/2610.18579)); the "thinking-token grading" of What Can't Jev Decide ([2610.24929](https://arxiv.org/abs/2610.24929)); the 126 counting-failure variants | The two gradings have not been merged |
| Q2.2 | The relation between fallback/refusal execution rate and rule wording | The PFR test ([2610.19856](https://arxiv.org/abs/2610.19856)); refusal-bottleneck pairing ([2609.39496](https://arxiv.org/abs/2609.39496)) | No mitigation available to measure |
| Q2.3 | Do axiom violations for negation, exclusivity and conjunction increase or decrease after fine-tuning? | The label-free axiom battery ([2609.33209](https://arxiv.org/abs/2609.33209)) | No before/after fine-tuning comparison |
| Q2.4 | Can the separation of policy authority vs evidence be reproduced on small models? | TrustJev's paired supervision ([2610.34826](https://arxiv.org/abs/2610.34826)) | Only one paper |

### 8.4.3 D3: Rule Language

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q3.1 | Where is the boundary of the rule subset a single-pass model can execute faithfully (L0 single rule / with one exception / L1 dependency / L2 new framework)? | The SafePyramid three-level numbers ([2606.29887](https://arxiv.org/abs/2606.29887)) on reasoning models | None on single-pass models |
| Q3.2 | What is the minimal sufficient set of primitives? Candidates: read / compare / contain / exception / Unknown / evidence requirement / typed variables | IR elements of the compiler-type works (05 §3.2.2); SemTree node types; probability-aware true/false/unknown | None |
| Q3.3 | How does error propagate when rules are composed in code? | Union bound ([2610.10978](https://arxiv.org/abs/2610.10978)); fan-out-weighted expected error ([2610.08089](https://arxiv.org/abs/2610.08089)); hierarchy TV ([2609.33971](https://arxiv.org/abs/2609.33971)) | The three have not been verified on the same rule tree |
| Q3.4 | What does a "compile-per-judge" compiler look like for small models? How much does the rule base degrade after a model version change? | SemTree's judge-swap experiment ([2610.13999](https://arxiv.org/abs/2610.13999)) | None |
| Q3.5 | Can the Skill part of a rule (how to do it) and the Policy part (what is allowed) be expressed separately and their interaction measured? | Auto-Policy's distinction ([2608.25091](https://arxiv.org/abs/2608.25091)); Jev-Guard's policy tree ([2610.18326](https://arxiv.org/abs/2610.18326)) | None |
| Q3.6 | The "executability rate" of rules written by non-technical experts, and the "executability rate after one round of repair" | SemTree node repair (82.04→86.16); AFTER one round of refinement +3.7–6.7 | No setting where the authors are non-experts |

### 8.4.4 D4: Consistency

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q4.1 | A joint profile of the 30 sub-dimensions (06 §4.2.2) on the same model and the same data | Each sub-dimension has its own metric | **No unified benchmark**; DecisionPivot / TypedBench / System1-Arena each cover a part |
| Q4.2 | The correlation between the distilled student and its teacher on order, IIA, ordinal compression and negation violations (teacher-bias inheritance) | The individual metrics + Gaussian proxy theory ([2610.26797](https://arxiv.org/abs/2610.26797)) | No empirical evidence |
| Q4.3 | Version drift: the decision-level flip rate of the same rule base between adjacent versions | The cumulative-failure-set method over 8 presentations in 2610.35826 can be borrowed | None |
| Q4.4 | Consistency of the same judgment expressed as Noul / Choice / Score, broken down by task type | 2609.33209 (sum of 1.14), 2610.18529, 2610.16655 (−8.7) | Needs systematization by task type |
| Q4.5 | The E5 (language), E6 (style) and B3 (option name) effects in Chinese | English methods are portable | None in Chinese |
| Q4.6 | Decision-level paired evaluation should become the reporting norm for reproduction work: report at least flip rate, cumulative failure set, axiom violations, readout type | 2610.35826, 2609.27678, 2609.33209, 2610.00054 | Needs a norm rather than a new method |

### 8.4.5 D5: Agent and Knowledge

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q5.1 | "Resources per successful delivery" as the unified accounting (including pre-screening cost and held-out-set thresholds) | The three metrics of [2610.13092](https://arxiv.org/abs/2610.13092); the self-audit checklist of [2610.02267](https://arxiv.org/abs/2610.02267) | Needs a norm |
| Q5.2 | Which signal can predict "needs slow thinking" rather than merely "the answer is uncertain"? | System Switch's AUROC-benefit correlation ([2610.09683](https://arxiv.org/abs/2610.09683)); VoI ([2610.21160](https://arxiv.org/abs/2610.21160)); SOMA's behavioral judgment ([2610.26793](https://arxiv.org/abs/2610.26793)) | No theory for language Agents |
| Q5.3 | Head-to-head: S1 decisions vs deterministic rules vs logistic regression as a microtask controller | The rule arm and placebo arm design of Good Judgment ([2610.24649](https://arxiv.org/abs/2610.24649)); Measure Before You Train ([2610.32955](https://arxiv.org/abs/2610.32955)) | No systematic comparison |
| Q5.4 | After the S1 training set includes "post-error states" and "record-observation conflicts", how far does Claim Laundering's 53–100% drop? | Paired state construction ([2610.25947](https://arxiv.org/abs/2610.25947)); AgentDecision-4B's trajectory collection ([2610.21412](https://arxiv.org/abs/2610.21412)) | The two have not been combined |
| Q5.5 | A task definition for S1 maintaining structured knowledge (ontology nodes, rule versions, fact validity periods) | Jarvis's versioned task records ([2610.23804](https://arxiv.org/abs/2610.23804)); Jev-DLC's bounded channel ([2610.31521](https://arxiv.org/abs/2610.31521)); the retirement gate's ternary contract ([2610.15710](https://arxiv.org/abs/2610.15710)) | The task itself is undefined |
| Q5.6 | How the trade-off between compressing for the current question vs for follow-up questions behaves under S1 judgment | The follow-up-question protocol of [2610.27301](https://arxiv.org/abs/2610.27301) | None on the S1 side |

### 8.4.6 Backbone

| # | Question | Existing measurement | Measurement gap |
| --- | --- | --- | --- |
| Q6.1 | On a hybrid backbone, are the gradients through a forked cache equivalent to row-by-row training? | qwen-rlcd's inference equivalence test (4.8e-5) | None on the training side |
| Q6.2 | Hybrid vs attention-only at equal parameter count: accuracy, calibration, order flip rate, latency | Single-point numbers from the individual reproductions (08 §1.3.5) | No controlled comparison |
| Q6.3 | Are recurrent layers more sensitive than attention layers to irrelevant details / interference from repeated updates? | The single-factor design of What Can't Jev Decide | No architecture comparison |
| Q6.4 | The implementation path for structural mitigation of order bias on hybrid backbones | Block-causal (masking), Runoff (two forward passes), Prism-1 | None on hybrid backbones |

### 8.4.7 Three Cross-Dimension Meta-Questions

1. **Can the three-way split "read / compose / needs intermediate steps" become the shared coordinate for primitive grading, consistency sub-dimensions and fast/slow switching?** Each of the three dimensions gives one boundary (Reading Right, Code Owns the Simulation, What Can't Jev Decide); they have not been unified.
2. **Into how many numbers should confidence be split?** Calibration, discrimination, sensitivity, human disagreement vs decision risk, self-knowledge: at least five meanings, while the interface returns a single probability.
3. **The rule language, the consistency benchmark and Agent benefit accounting all need "decision-level paired" evaluation**: this is a methodological gap shared by the three dimensions, not three independent problems.
