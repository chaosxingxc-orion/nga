# R3 reference targets: what the literature reported, and what of it we can measure

> 2026-10-30. Built for the SFT rounds (proposal R3, gate G2) on Qwen3.5-0.8B / 2B / 4B / 9B.
> Purpose: fix, before any training run, **which published numbers we may put beside ours and in
> what words**. Every number below is traceable to a sentence in `survey/` or `proposal/`; the
> location column gives the file and section. Where the survey does not state something the cell
> reads **not stated in survey**. Nothing here is a new claim about the literature.
>
> Scope reminder: the survey is analysis-only and is not edited by this file. Citations are given
> exactly as the survey gives them (arXiv id, repository, or model card).
>
> **Constructs that are the report's own, not literature conclusions** (survey §8.1.2, CLAUDE.md
> rule 4.4): the seven generalization levels L0–L6 used in column "metric definition" below, the
> framework items P0″–P5″, the D4 sub-dimensions, the question graph, the decision-repetition axis,
> the twelve business properties. Where a row uses one of these, it is the report's classification
> of someone else's measurement, not the authors' own wording.

---

## 1. Our measuring instrument, stated first

Everything in the "measurable by us?" column is judged against this instrument, so it is written
down before the table (`experiments/R0-BASELINE-PREREG.md` §1, §8.1; `R0-BASELINE-RESULTS.md` §2):

- **Model**: plain Qwen3.5 decoder, no typed head. Readout is **same-backbone label
  log-probability** over the declared level set, normalized over that set — survey §7.1 checklist
  item B1, proposal task `E-0.3`.
- **Prompt**: `r0-prompt-v2`, format **raw completion, no chat template** (task definition, input,
  question, options as identifier + definition, `Answer:`).
- **Scoring**: unnormalized sum of the log-probabilities of a level's identifier tokens, then
  softmax over the item's levels (`R0-BASELINE-PREREG.md` §12.1).
- **Operator**: cumulative-mass threshold, residual to C; `argmax` recorded only as a reference
  column and never reported alone (`R0-BASELINE-RESULTS.md` §3, §5).
- **Data**: `typed-decisions` (6,000 inputs, 15 questions), `akhilaaa3` (586 inputs, medium/hard,
  545 distinct questions), `openjev-synth` (7,680 inputs, one `qname`, code labels).
- **Splits**: `group70` held-out, plus a question-disjoint split for `akhilaaa3` only.

---

## 2. The alignment target table

Priority order: results on the three sources we hold, then Qwen3.5 / Qwen3 backbones at or below
9B, then the specific numbers the proposal leans on. "measurable by us?" is one of
`yes, same data and metric` / `yes after re-downloading <repo>` / `only approximately, because …` /
`no, because …`.

| # | Reference (as the survey cites it) | Location in our files | Backbone / size | Training method (data size) | Dataset / split | Metric definition | Reported number | Measurable by us? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Group A — results and properties on the three sources we hold** |
| A1 | `akhilaaa3/decision-bench` own results | survey §6.1.4.3 | hosted Jev 1.13 (size undisclosed) | none (hosted) | akhilaaa3, medium 80 states + hard; 586 questions; no official split stated | state macro-average accuracy | **90.48%**; generative frontier 98.8–99.1% | only approximately, because our split is `group70` / question-disjoint, not a state macro-average over the whole bench, and our readout is log-probability with no chat template; the whole bench must be re-downloaded first |
| A2 | akhilaaa3 by primitive | survey §2.2.3 (quoted again at §2.3 omission 7) | hosted Jev 1.13 | none | akhilaaa3 | accuracy, split by which primitive the question is asked through | **score 80.3% vs choice 95.7%** | only approximately, because our harness renders every level set the same way and does not switch primitive; the comparison would need a second rendering arm we have not pre-registered |
| A3 | `LocalLLaMA/typed-decisions` label property | survey §6.1.4.3 | — (dataset) | — | typed-decisions, 1,200 states × 5 questions, 6,000 question labels | share of question labels whose annotator argmax disagrees; median total variation | **35% disagreement, median TV 0.14** | yes after re-downloading `LocalLLaMA/typed-decisions` — our derived task files carry gold, not the annotator distribution |
| A4 | Laya audit on typed-decisions ([2609.33843](https://arxiv.org/abs/2609.33843)) | survey §1.4.5, §6.1.4.1 | Laya, ModernBERT-large 421M / mmBERT-base 322M (encoder) | RL against proper scoring rules, "a recipe its developers call RLCD" (data size not stated in survey) | `LocalLLaMA/typed-decisions`; `Luni/laya-jev-benchmark` | **signed** confidence-accuracy gap; the sign collapses every binned ECE variant to one value | **−0.214**, accuracy above confidence in every occupied bin | only approximately, because it is an encoder outside our technical direction (survey README §6) and the signed gap is not in our pre-registered metric set; our ECE is 10 equal-width bins |
| A5 | Laya out-of-domain probes ([2609.33843](https://arxiv.org/abs/2609.33843)) | survey §6.2.2 L2 | same as A4 | same as A4 | out-of-domain probes (not named in survey) | zero-shot transfer at L2 (new schema; L0–L6 is the report's own construct) | **"no zero-shot transfer"**, no number stated in survey | no, because the survey states no number and the probe set is not named |
| A6 | Open-Jev v1.1 synthetic `community-diversity-v2` ([Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev)) | survey §6.1.4.3 | — (dataset) | — | 48 templates × 80 groups, 30,720 training rows; split `family_disjoint … 1 ood` | share of counterfactual variants where flipping one field changes the code label | **10,201 / 11,858 = 86%** | yes, same data and metric — this is the discrimination half of R0's pre-registered equivalence classes (proposal R0 protocol) |
| A7 | Open-Jev training mixture ([Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev)) | survey §6.1.4.3 | — (dataset) | — | full mixture, 147,139 rows, 73 sources | number of distinct question strings | **4,101** distinct strings; one source (`wanli`) uses one question for 82,045 rows | yes after re-downloading `ZefanCai/Open-Jev-v1.1` — our local slice carries one `qname` over 30,720 records (`R0-BASELINE-RESULTS.md` §8 item 4) |
| A8 | Open-Jev models ([Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev)) | survey §1.2.2 | Qwen 2B / 9B / 27B | LoRA (27B rank 8) + scalar decision head; soft cross-entropy + 0.1·Brier; frozen 148,639-row mixture | internal evaluation, 127,787 rows (27B v1.1) | **not stated in survey** (only "passed an independent audit") | no accuracy number stated in survey | no, because the survey states no metric and no number for this checkpoint |
| **Group B — Qwen3.5 / Qwen3 decision checkpoints at or below 9B** |
| B1 | Kev 1.0 ([jaredpalmer/kev](https://github.com/jaredpalmer/kev)) | survey §6.2.2 L0/L1 | Qwen3.5-0.8B-Base | LoRA rank 16 + pointer head, cross-entropy, 2 epochs; `decision-v7` = 10,000 public + 896 policy + 1,680 rule-structure samples | `decision-v7` held-out (trained sources) vs `transfer-v4` (new sources: six never-trained public datasets plus held-out policy and rule structures; KEV-PROTOCOL §0, §2.2); dev / test. Not `breadth-v1`, which is private (`jaredpalmer/kev-private-evals`, HTTP 401) and which Kev reports only as a chance-corrected index | accuracy per the Kev README's three-column table | new sources **0.648 / 0.697**, trained sources **0.827 / 0.838** | yes after re-downloading `jaredpalmer/kev-suites` (0.3 GB) — same backbone size and a source-level split; but their readout is a trained pointer head, ours is an untuned log-probability readout, so the pair is "untuned vs tuned", not "same metric" |
| B2 | Kev 1.0 | survey §6.2.2 L0/L1 | Qwen3.5-4B-Base | as B1 | as B1: `decision-v7` (trained sources) vs `transfer-v4` (new sources) | as B1 | new sources **0.817 / 0.838**, trained **0.873 / 0.865** | as B1 |
| B3 | Kev 1.0 | survey §6.2.2 L0/L1 | Qwen3.5-9B-Base | as B1 | as B1: `decision-v7` (trained sources) vs `transfer-v4` (new sources) | as B1 | new sources **0.820 / 0.852**, trained **0.874 / 0.873** | as B1 |
| B4 | Kev 1.0 | survey §6.2.2 L0/L1 | Qwen3.8-27B | as B1 | as B1: `decision-v7` (trained sources) vs `transfer-v4` (new sources) | as B1; plus the new-source gap across the ladder | new sources **0.851 / 0.889**; new-source gap shrinks **17.9 pp at 0.8B → 1.4 pp at 27B**; 27B within one point of Jev (0.851 vs 0.857) | no, because 27B is above our 10B ceiling; kept as the scale anchor the ladder argument rests on |
| B5 | Kev-9B ([jaredpalmer/kev](https://github.com/jaredpalmer/kev)) | survey §1.2.2 | Qwen3.5-9B | as B1 | new sources | share of questions where ≥0.9 probability sits on a wrong answer | **2.4%** | only approximately, because it needs the same new-source suite and a confident-error definition we have not pre-registered; the shape is reportable from our stored `p` vectors |
| B6 | Kev date facts ([jaredpalmer/kev](https://github.com/jaredpalmer/kev)) | survey §1.2.2, §4.1.2.2 | Qwen3.5 Kev series | `KEV_DATE_FACTS` state supplement, no weight change | deadline-policy questions (set not named) | accuracy | **0.80 → 0.90** (Jev 0.93) | no, because none of our three sources is a deadline-policy set and the question set is not named in the survey |
| B7 | Tev1 ([togethercomputer/tev1](https://github.com/togethercomputer/tev1)) | survey §1.2.2 | Qwen3.5-4B (Instruct) | LoRA SFT, single answer letter; 37,840 unique training samples + 4,568 validation; about 17 USD, 25 minutes | own main-decision and policy-transfer sets | items correct / items | **880/1,000** main decisions, **300/300** policy transfer | only approximately, because the evaluation sets are internal to the repo and the readout is a generated answer letter, not a scored level set |
| B8 | TDMs under prevalence shift ([2610.26325](https://arxiv.org/abs/2610.26325)) | survey §6.2.2 L4 | Tev1-4B vs its own base Qwen3.5-4B | decision SFT (as B7) | FPB financial sentiment, prevalence-shift protocol, 5 public datasets + 35 pre-registered paired tests | Macro-F1 difference against the same base model | **+10.0** Macro-F1 over Qwen3.5-4B | no, because FPB is not one of our three sources and prior shift is not in our data; it is rebuildable per the paper (survey §6.2.5 L4) but is not an R3 target |
| B9 | Bespoke Nimble ([bespokelabsai/nimble](https://github.com/bespokelabsai/nimble)) | survey §6.1.1 family B, §1.2.2 | Qwen3.5-9B + LoRA (answer tokens only) | SFT on 2,676 contrastive samples ("change one fact so the answer flips") + 324 held out | own held-out set | accuracy | **90.1%** vs base 66.4%, Jev 93.2% | only approximately, because the held-out set is Nimble's own and the readout is an enum field (1–255 choices); same backbone size, different interface |
| B10 | TDMs under prevalence shift ([2610.26325](https://arxiv.org/abs/2610.26325)) | survey §6.2.2 L4 | Nimble-9B vs base Qwen3.5-9B | as B9 | FPB financial sentiment | Macro-F1 and ECE difference against the same base | **−12.0** Macro-F1, ECE **+9.6**, loss concentrated in the neutral class | no, same reason as B8. Retained because it is the sharpest statement that "the same decision SFT can be +10 or −12 depending on data composition" |
| B11 | Chinese Decision ([2610.23170](https://arxiv.org/abs/2610.23170)) | survey §1.2.2 | Qwen3.5-0.8B / 2B / 4B | 1 epoch, 13.048M decisions; candidate-letter logits at the last position, normalized over legal options; temperature on validation; Q8_0 | CJ-Bench, 307,900 decisions | accuracy overall and by domain | 4B overall **85.97%**, general 75.69%, medical/legal/finance **84.00%** | no, because the benchmark is Chinese and our pre-experiments are English by the user's decision (survey §6.2.5); backbone and readout are otherwise the closest match in the whole table |
| B12 | SecJev ([2610.03073](https://arxiv.org/abs/2610.03073)) | survey §1.2.3, §6.1.5 item 5 | Kev-based 0.8B–9B | scenario-weighted training on SecJev-Corpus (14 tasks, 8 sources; row count not stated in survey) | in-domain security tasks | task macro-accuracy | **SecJev-0.8B is +20.51 pp above the general-purpose Kev-9B** | no, because the corpus is a security domain we do not hold; it is the load-bearing counter-evidence for "the endgame must be large" and enters our wording, not our measurement |
| B13 | AgentDecision-4B ([2610.21412](https://arxiv.org/abs/2610.21412)) | survey §1.2.3 | 4B | trained on the states the agent reaches after its own mistakes, Jev's answers as labels (DecisionGym) | out-of-distribution agent tasks | accuracy | **91.5% vs Jev 82.0%** | no, because it is an agent-trajectory setting; the dataset is "to be released" per the paper (survey §6.1.4.1) |
| B14 | OneJev 1.6 ([OmniJev/OneJev](https://github.com/OmniJev/OneJev)) | survey §1.2.2, §1.3.5 | Qwen3.5-0.8B / 4B / 9B | cross-entropy + Brier, 99,193 questions (94,707 public), lr 5e-6, 1 epoch | one 720p screenshot on an H200 | wall-clock latency, 1 question / 10 questions | 0.8B **31 / 51 ms**, 4B 64 / 104, 9B 81 / 131 | only approximately, because the measurement conditions differ (survey §1.3.5 says so explicitly) and we run on Ascend 910B, not H200 |
| B15 | Intern-Decision ([2610.22131](https://arxiv.org/abs/2610.22131)) | survey §1.2.2 | 0.8B / 2B / 4B multimodal | autoregressive masked LM, one decision placeholder per JSON field | seven-suite average | accuracy; Brier; ECE | 4B **90.02%** vs Jev 1.13 88.74%; Brier 0.628→0.550, ECE 0.213→0.089 after temperature | no, because it is multimodal with a JSON-skeleton readout and the suites are not ours |
| B16 | StartLux-Decision v1.1 ([2610.17309](https://arxiv.org/abs/2610.17309)) | survey §1.2.2 | 4B / 9B / 27B | three stages: shared decision ability → differentiation → reasoning supervision + RL (AutoThink); about 2.7M samples at 0.8–9B | DecisionPivot and Decision Index entries | paired accuracy, AutoThink over Instant | **+18.4 / +12.4 / +11.5** points at 4B / 9B / 27B | no, because AutoThink generates reasoning when the top probability is below 0.9, which is outside the single-pass interface R3 trains; relevant only as the ceiling that reasoning buys |
| B17 | LLM-as-Jev ([2610.02076](https://arxiv.org/abs/2610.02076)) | survey §1.2.3 | Qwen3-0.6B (attention-only) | list-wise loss + KL regularization on read logits | Banking77 (77 classes) | accuracy | **22.2% → 60.5%**; letter readout cannot handle 77 classes | only approximately, because none of our three sources has a 77-level question; it is the evidence that small models can learn multi-class list readout at all |
| B18 | LLM-as-Jev ([2610.02076](https://arxiv.org/abs/2610.02076)) | survey §1.2.2 | 4B frozen | none (reads logits directly) | JevBench, native thinking under a token budget | accuracy | **94.8%** | no, because HF `fstandhartinger/jevbench` does not exist (survey §6.1.4.1) and the GitHub set is 231 public questions, not our data |
| B19 | FunDM ([2610.17175](https://arxiv.org/abs/2610.17175)) | survey §1.2.1, §6.1.1 family D | Qwen3-8B, 24 of 36 layers | **no labels**: KL to the frozen model's own answer distribution | eight benchmarks | multiple-choice accuracy; fraction of full-model accuracy recovered | **75.0 vs full model 75.7**, about **99%** recovered; 1.56–1.57× throughput, about one third less peak memory | only approximately, because it is an early-exit head on an attention-only backbone; the "label-free KL recovers nearly all of it" claim is directly relevant to R0-6 and is testable on our sources with a new arm |
| B20 | this-that-model 1.0 ([2609.23886](https://arxiv.org/abs/2609.23886)) | survey §1.2.2, §1.2.3 | 2B | reads the hidden state at a designated position, restricted to the declared option set | third-party 68-question queue | score (metric name not stated in survey); Brier; latency | **0.941 vs Jev 0.765**; Brier 0.042; 30.9 ms on a notebook GPU | no, because the metric is not defined in the survey and the queue is a single third-party source |
| B21 | jevlike ([mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike)) | survey §6.2.2 L5 | Qwen3-1.7B + LoRA | SFT on 37 open-source datasets, `CE + 0.5·Brier` | in-domain vs out-of-domain | ECE before and after a fitted temperature; precision of a 0.99 confidence gate | in-domain ECE **0.0212 → 0.0083** at T=1.19; OOD only **0.1311 → 0.1011**; the 0.99 gate validated in-domain at 99.85% **fails** out of domain | only approximately, because the binning algorithm is not stated and ECE has at least five variants (survey §1.4.5); the shape — temperature repairs in-domain and not out of domain — is reproducible on our held-out rule families |
| B22 | OpenJev-RLCD ([2609.38850](https://arxiv.org/abs/2609.38850)) | survey §6.1.1 family F | Qwen3-1.7B | "calibrate first, then reinforce": proper scoring rule as the RL reward after each reasoning chain | GSM8K answer verification | share of items a single query decides at ≤5% error | **81%** vs GRPO 19% | no, because it requires a reasoning chain; R3 forbids RL (proposal R3 protocol) |
| B23 | SBERT2S1 ([2610.02486](https://arxiv.org/abs/2610.02486)) | survey §6.1.3 | encoder (Sentence-Transformers family) | the RLCD recipe released with the open-source System One model, vs cross-entropy | MEDLINE-S1 / BIODECIDE, 243k | accuracy points relative to cross-entropy | RLCD **2.5–3.0 points below** cross-entropy; after temperature scaling no objective is clearly better calibrated than CE | no, because it is an encoder; cited by proposal R8-1 as the expectation for the readout-side RL falsification |
| B24 | ufakzeka-karar ([2610.06744](https://arxiv.org/abs/2610.06744)) | survey §6.1.3 | Turkish, proprietary 182M base | REINFORCE vs cross-entropy | not stated in survey | macro-F1 difference | REINFORCE **−10.2** macro-F1 | no, same reason as B23 |
| B25 | Block-causal ([2610.01601](https://arxiv.org/abs/2610.01601)) | survey §6.1.3, §1.3.1 | Gemma 3 1B; Qwen3-1.7B; Qwen3-4B | candidate-agnostic block-causal attention + position reset (structural, not a loss) | own test and OOD splits | option-order flip rate | **8.30% → 0.11%** (Gemma 3 1B), **18.16% → 1.20%** (Qwen3-1.7B); isolation alone 8.30→3.82 test, 7.54→3.71 OOD | no, because it depends on the attention mask and Qwen3.5's 18 of 24 layers are Gated DeltaNet, which ignore the mask (survey §1.3.2); this is defect 11's whole reason for existing |
| B26 | Prism-1 ([2610.22066](https://arxiv.org/abs/2610.22066)) | survey §1.2.2 | Qwen3-8B / Gemma 4 12B | one independent block per option, shared positions, LoRA, softmax over blocks | not stated in survey | share of answers changed by one shuffle | baseline **20.0% / 11.9%** (published fine-tune 9.1%); Prism-1 **zero flips** | no, same mask dependence as B25 |
| B27 | Our Own Jev ([2610.29052](https://arxiv.org/abs/2610.29052)) | survey §6.1.3 | 2B (and 1B) | frozen backbone + rank-16 LoRA + pointer head; 148K agent coding sessions | own hard tier and battery set | accuracy | 2B hard tier **63.1 after training, below frozen 67.6** (1B 48.6 vs 54.1); swapping one corpus version moves the hard tier **11 points** | only approximately, because the evaluation set is internal; it is the clearest published case of decision SFT being **negative** at 2B, which is the risk R3-5 tests |
| B28 | DKnown-Jev ([2610.24358](https://arxiv.org/abs/2610.24358)) | survey §6.1.1 family B | Qwen3.5-2B / Qwen3.8-27B base | fine-tuned directly from base, 1 epoch | not stated in survey | accuracy vs Jev | **27B 98.75%, 6.07 pp above Jev**; the 2B number is **not stated in survey** | no, because the 2B figure and the evaluation set are both absent from the survey |
| **Group C — the specific numbers the proposal leans on** |
| C1 | Labels Override Definitions ([2610.02586](https://arxiv.org/abs/2610.02586)) | survey §3.1.2.2; proposal R2-1, R3-2 | hosted Jev and open-source decision models (survey §6.2.2 L3) | none (prompt-rendering intervention) | **not stated in survey** | accuracy delta from switching the rendering `"{label}: {definition}"` to definition-only with A/B identifiers | **+0.1511** | yes, same metric, different data — the rendering fix is already our baseline's render mode (`R0-BASELINE-PREREG.md` §1) with `record_name` as the unmitigated arm; the **dataset** cannot be matched because the survey does not name it, so the comparison is "same intervention, our three sources" |
| C2 | Labels Override Definitions ([2610.02586](https://arxiv.org/abs/2610.02586)) | survey §3.1.2.2; proposal R3-2 | as C1 | none | as C1 | accuracy with all definitions deleted; with definitions only; with label and definition in conflict | deletion leaves accuracy **unchanged at 0.8487**; definitions alone sustain **0.7971**; conflict drops **0.8511 → 0.2281** | yes, same metric, different data; and our T2 is the local form of the conflict arm. Note our `openjev-synth` T1 already contains an unintended label/definition conflict on 54% of units (`R0-BASELINE-RESULTS.md` §7.1), so that source cannot carry this row |
| C3 | Labels override definitions, swap protocol ([2609.26758](https://arxiv.org/abs/2609.26758)) | survey §3.1.2.2, §1.4.6; proposal R3-1 (decision line > 60%) | hosted Jev and open-source decision models | none (name↔definition reassignment) | **1,200 decision tasks with task-specific definitions**; dataset name not stated in survey | **definition-level** AUC: track the change in the selected *definition*, not the returned *name* | mean AUC **93.8% → 23.2%** (below chance); flip rate under yes/no names up to **70.4 pp** above the 0/1 control; type-error rate **0% throughout** | only approximately, because our T2 scores a **followed rate** on swap-eligible units (9 of 10 cells fail; `R0-BASELINE-RESULTS.md` §3.4), not an AUC over 1,200 tasks. R3-1's "> 60%" line is an AUC, so the harness needs an AUC arm before G2 can be judged against 23.2% |
| C4 | LDM ([2610.15501](https://arxiv.org/abs/2610.15501)) | survey §1.2.1, §6.1.5 item 1, §6.2.2 L0/L1; proposal R0-6 | Qwen3.5 0.8B → 27B (three base models incl. Gemma-4-31B) | decision tuning vs untuned readout; DDS + SPRD | own validation set and DV-Dev-A/B | untuned readout accuracy as a fraction of post-tuning accuracy; absolute tuning gain | untuned readout reaches **76–97%** of tuned; gain shrinks **15.8 → 2.3 points**; 1/16 of the data recovers 88% of the gain at 9B | only approximately, because we have no tuned endpoint yet — the R0 run fixes only the untuned end and R0-6 is recorded as "borne on, not decided" (`R0-BASELINE-RESULTS.md` §1). After R3 the ratio becomes computable **on our data**, never against their numerator |
| C5 | LDM ([2610.15501](https://arxiv.org/abs/2610.15501)) | survey §6.1.5 item 2, §6.2.2 L2; proposal R6-2 | 27B | public recipe vs source-augmented recipe vs untuned | DV-Dev-A / DV-Dev-B (new schema, L2 in the report's own level scheme) | accuracy | public **88.1 / 87.5**, augmented **87.8 / 88.0**, **untuned 89.1 / 87.5** | no, because 27B is above our ceiling and DecisionVista's data status is unverified (survey §6.1.4.1); it is the reason R3-5 is written as "no regression", not "a gain" |
| C6 | LDM ([2610.15501](https://arxiv.org/abs/2610.15501)) | survey §6.1.5 item 3, §6.2.2 L6 | 27B untuned, allowed to reason (four-sample majority) | none | DV-Dev-A/B; three date-arithmetic and numeric-comparison schemas | accuracy, reasoning vs readout | **96.9 vs 89.1** and 96.8 vs 87.5; on numeric schemas readout **56–66% at every scale**, reasoning 98–100% | no, because it needs a reasoning rollout, which the single-pass interface excludes |
| C7 | Menu relativity / IIA ([2610.16655](https://arxiv.org/abs/2610.16655)) | survey §2.1.3 counter-evidence 3, §2.1.8 price list, §2.2.1 (exclusive / stackable row); proposal R2-4 | hosted Jev (pre-registered, 299,463 calls) | none | not stated in survey | accuracy cost of replacing joint scoring with one independent Noul per candidate; log-odds shift per added option | independent Noul **−8.7 points**; each added option shifts gold-vs-strongest-wrong log-odds by **0.20–0.52 nats = 1.2–3× rerun jitter**, about **1 nat** at 255 options | only approximately, because our level sets are 2–26 levels, not 255, and our cells are small (19–63 held-out units on `akhilaaa3`); the **sign and order of magnitude** are testable, the point estimate is not |
| C8 | DecisionPivot ([2610.28522](https://arxiv.org/abs/2610.28522)) | survey §4.1.2.2, §7.2; proposal R2-5 | Perplexity Decider (27B class); StartLux Instant | none (evaluation) | DecisionPivot core track, 2,400 binary contrast pairs, difficulty 1–3 | **pairwise** accuracy on contrast pairs, by difficulty | **87.7% → 57.4%** from difficulty 1 to 3 (Instant 90.7% → 65.3%); ranks positive above negative in 92.3% of pairs but gets **both sides right in only 74.1%** | yes after re-downloading `startlux-models/DecisionPivot` — but on their items, not ours: none of our three sources is binned by arithmetic/temporal difficulty. Proposal R2-5 says "returns to around 87.7%", which is their number on their data and must be worded as a reference level, not a target we can hit |
| C9 | Arithmetic refusal bottleneck ([2609.39496](https://arxiv.org/abs/2609.39496)) | survey §4.1.2.3, §6.5.2.4; proposal R2-2 | hosted Jev | none; a threshold chosen on a separate dev set, no retraining | own answer-present / answer-absent arithmetic items | correct-refusal rate when the correct answer is absent, at fixed answer-present accuracy | **7% → 79%** while retaining **97%** answer-present accuracy; native boolean verification reaches 99% exact match on the same answer-absent items | only approximately, because "the correct answer is absent" is a construction we do not hold: our only unknown is Open-Jev's **missing-evidence** unknown, and **rule-silent** unknown is zero locally with no code-label source (survey §6.1.4.3 item 4, proposal R1-3) |
| C10 | Union bound, probabilistic perception / deterministic adjudication ([2610.10978](https://arxiv.org/abs/2610.10978)) | survey §3.2.3.2; proposal R0-5 | not a decision-model result (2 sensor families) | none | 36,000 calls, 2 domains | whether the probability that perception changes the adjudication exceeds the sum of per-field false-admission and unknown rates | **not one unit refutes the bound**; all 13 reject→allow flips among 21,000 adjudications come from 3 contradictory records | only approximately, because our harness is built on this bound, so measuring it with the harness is circular; proposal §6 item 5 requires measuring it first with the plainest threshold protocol. Not computed in the R0 run (`R0-BASELINE-RESULTS.md` §1) |
| C11 | Certo ([2609.37832](https://arxiv.org/abs/2609.37832)) | survey §2.1.8 price list, §4.1.2.5 | Qwen3-4B joint scorer | targeted counterfactual supervision | held-out **synthetic** rule tasks; 77 candidates | rule-sensitivity recall@1 | joint 1.00 → cacheable independent encoding **0.24** (about 5× cheaper); counterfactual supervision recovers it on held-out synthetic rules, but the authors "did not isolate whether predictions depend on the given rule"; benefit on real rules "not established" | only approximately, because our fixed order (task definition → input → candidate branches) already chose the expensive, rule-sensitive side (survey README §1, P5″), so the cheap arm would have to be built on purpose |
| C12 | JevAdvBench ([2609.31142](https://arxiv.org/abs/2609.31142)) | survey §2.1.8, §4.1.2.4, §7.2; proposal R0-1 | hosted Jev; eight open-source TDMs | none | 862 questions + 5,586 answer-preserving variants, 12 black-box attacks | share of **correct** decisions flipped by an answer-preserving variant | **46.3%** (identical rerun flips 0.17%); open-source TDMs 34.0–51.7%; of decisions still executed at a 0.8 threshold, **23.5% are wrong** | no, because the adversarial variants need data that no longer exists locally (`R0-BASELINE-RESULTS.md` §8 item 3); this is why R0-1's four-denominator spread is untouched |
| C13 | Cumulative failure set ([2610.35826](https://arxiv.org/abs/2610.35826)) | survey §1.4.6, §4.2.1; proposal R0 protocol | hosted Jev | none | eight option presentations of the same items | growth of the cumulative failure set, against change in aggregate accuracy | accuracy moves **< 2 pp** while the cumulative failure set grows **27–29%** | yes, same metric, different perturbation axis — our T1 (level names) and T3 (question set) carry the cumulative failure set; order permutation itself needs re-downloaded data |
| C14 | Repeatability ([2609.36399](https://arxiv.org/abs/2609.36399)) and same-text rerun ([2609.31142](https://arxiv.org/abs/2609.31142)) | survey §1.1.5.3, §2.1.8 | hosted Jev | none | 24-question cultural values survey, 288,000 responses | ICC; same-text flip rate | **ICC 0.997**; same-text rerun flips **0.17%** | yes, same metric, trivially — under greedy decoding the byte-level rerun is exact for us (`R0-BASELINE-RESULTS.md` §8 item 3), which is itself why that denominator carries no information |
| C15 | SemTree ([2610.13999](https://arxiv.org/abs/2610.13999)) | survey §3.2.3.2, §4.2 (judge-swap row); proposal R7-2 | pluggable semantic judge | tree compiled against one judge's answers | ShARC, 8,276 cases | task accuracy of the compiled tree | host judge **67.70%** (2.99 questions/case) vs asking directly 68.23%; **47.87%** when the judge is swapped; 64.39% after recompiling | no, because ShARC is not local and tree compilation is R5/R7 work, not R3 |
| C16 | Reading Right, Acting Wrong ([2610.18579](https://arxiv.org/abs/2610.18579)) | survey §4.1.2.1; proposal R5-1 | six most accurate fast systems; 14 "capable" fast systems | none | generated and real states | share of policy modifications read out correctly but **executed** | execution **22%–72%**; 73%–85% of decision errors occur on states where every probed fact is answered correctly; composing the action in code reaches **0.96–1.00** | no, because it needs fact probes plus an action composition our sources do not define; it is R5's target, not R3's |
| C17 | Restoring the third truth value, Sys1Cal-v1 ([2609.35342](https://arxiv.org/abs/2609.35342)) | survey §6.5.2.1, §6.5.2.5; proposal R4-3 | hosted Jev | none | true/false propositions with P(A) known by construction | median **soft** accuracy, scored by total variation to the true distribution | Choice **0.771 → 0.978** after restoring P(U) | no, because it needs propositions whose P(A) is known by construction; our boolean questions have business gold, not a constructed probability |
| C18 | JevCascade ([2610.07716](https://arxiv.org/abs/2610.07716)) | survey §6.5.2.2, §1.2.3, §3.1.3 | six model families, ten core datasets | none (training-free menu restriction) | menu-only interventions | prediction error of post-intervention accuracy, at the **ordinal** layer vs the **probability** layer | ordinal **4.2 points**, probability **21.0 points**; 150-class menu 69.0% → curated 5-candidate 95.4%, a span larger than the 0.8B-to-4B gap | only approximately, because our level sets are fixed per question by the business; a menu-restriction arm would have to be constructed. The 4.2-vs-21.0 split is the reason our harness thresholds cumulative mass and never treats the readout as a world probability |
| C19 | NumericJev ([2609.28587](https://arxiv.org/abs/2609.28587)) | survey §4.1.2.2, §6.5.2.4; proposal R2 registry row 4 | not stated in survey | none (training-free interval tree) | 100-value grid; three-date historical index | range-normalized MAE | **5.18% → 1.84%**; 2.93 pp above direct selection even when the correct answer is in the candidate table | no, because none of our three sources asks for a number; `openjev-synth` counts requirements, which is an ordinal level set, not a numeric range |
| C20 | PACT ([2609.35865](https://arxiv.org/abs/2609.35865)) | survey §6.1.3, §6.5.2.3, §6.5.3 | not stated in survey | pairwise anchored calibration fine-tuning (four loss terms) | 324 held out, three seeds | accuracy; share of verdicts changed under relabelling; NLL; rubric-field MAE | accuracy **84.6 vs 85.2** (no significant difference); relabel flips **9.8 vs 13.8%**; NLL **−26%**; rubric MAE 0.232 vs 0.311; "no single term raises raw accuracy" | only approximately, because the held-out set is 324 items with three seeds; the usable import is the **expectation** that an added scoring term buys robustness and not accuracy, which bounds what R3's ablations may claim |
| C21 | Ordinal scale-utilization bias ([2609.38827](https://arxiv.org/abs/2609.38827)) | survey §6.5.2.3; proposal R4-1, R4-4 | nine models from the JEV / KEV / StartLux families | none | 40 datasets | number of effective labels used, against the gold distribution | decisions concentrate on **fewer effective labels**; a finer scale worsens it; randomizing candidate order reduces but does not remove it; scale does not restore utilization | yes, same metric, our data — `typed-decisions` and `openjev-synth` both carry ordinal levels and our frozen readouts store full probability vectors; the concentration figures in `R0-BASELINE-RESULTS.md` §6.1 are the local form, labelled there as our own analysis |
| C22 | Symbol tuning ([2305.08298](https://arxiv.org/abs/2305.08298)) | survey §3.1.1, §6.3.1; proposal R3 (`M-3.1`) | upstream LM result, model not stated in survey | SFT with natural-language labels replaced by arbitrary symbols | not stated in survey | "stronger on unseen ICL tasks, more robust to underspecified prompts, greatly improved ability to follow flipped labels" | **no number stated in survey** | the method is applicable to us; the **number is not**, because the survey states none. Survey §6.3.6 blind spot 2 records that symbol tuning has never been tried on a typed readout, so R3 has no reference value to align to |
| C23 | Semantic override in small models ([2511.21038](https://arxiv.org/abs/2511.21038)) | survey §3.1.1, §3.1.2.2, §6.2.2 L3 | 1–12B open models | none (few-shot) | not stated in survey | semantic override rate under inverted examples | **exactly zero**; inverted examples raise "prompt alignment" only at the cost of accuracy | only approximately, because it is a few-shot ICL measurement and our k-shot curves (R3-3) are the first of their kind on a decision model (survey §3.1.6 blind spot 1); zero is the floor we are trying to lift |
| C24 | RLCDAlignBench ([2609.29429](https://arxiv.org/abs/2609.29429)) | survey §6.4.1.1; proposal §0 pillar 4 | hosted Jev | RLCD (unpublished) | 10 failure classes, 44 benchmarks, 5 target models | zero-shot median AUROC of one generic question | **0.886**, beating supervised baselines on most benchmarks, at 1/63 the cost of an LLM judge | no, because the benchmark is HF-gated (CC BY-NC 4.0) and was excluded from our mirror (survey §6.1.4.2); proposal R0 `E-0.4` still lists it as a pillar to reproduce, which this row flags as blocked |
| C25 | Evidence audit checklist ([2609.32160](https://arxiv.org/abs/2609.32160)) | survey §7.1 | 26–27 applicable papers | — | — | compliance with the 14-item checklist | same-backbone label log-probability baseline **5/26**; option-name invariance **1/27**; latency with and without cache **3/20** | yes, same metric, as a property of our own report — our baseline **is** item B1, and T1 **is** item T3. This row is the reason most other rows read "only approximately": the published numbers never separated the interface's credit from the model's |

**Row count: 61 reference rows** (A1–A8, B1–B28, C1–C25).

---

## 3. Best reference metric at ≤ 9B, per source we hold

| Source we hold | Best reference headline the survey states | Size / backbone | Where | Reference checkpoint HF id, as the survey gives it |
| --- | --- | --- | --- | --- |
| `typed-decisions` (`LocalLLaMA/typed-decisions`) | **No model accuracy at any size is stated in the survey.** The only model result on this benchmark is the Laya audit's signed confidence-accuracy gap **−0.214** and "no zero-shot transfer" on out-of-domain probes | Laya: ModernBERT-large 421M / mmBERT-base 322M — encoder, outside our direction (survey README §6) | survey §1.4.5, §6.1.4.1, §6.2.2 L2 | `convaiinnovations/laya` (model page); benchmark also mirrored as `Luni/laya-jev-benchmark`. Size not stated in survey |
| `akhilaaa3` (`akhilaaa3/decision-bench`) | **Jev 1.13 state macro-average 90.48%**; generative frontier 98.8–99.1%; by primitive, score 80.3% vs choice 95.7% | hosted Jev, size undisclosed. **No ≤9B open checkpoint number on this set is stated in the survey** | survey §6.1.4.3; §2.2.3 / §2.3 omission 7 for the primitive split | none — the survey names no open checkpoint evaluated on this bench |
| `openjev-synth` (`ZefanCai/Open-Jev-v1.1` synthetic part) | **No accuracy number at any size is stated in the survey.** The 27B v1.1 internal evaluation (127,787 rows) is only described as having "passed an independent audit". The usable reference quantity is the dataset's own **86%** counterfactual flip rate | Open-Jev models are Qwen 2B / 9B / 27B with LoRA + a scalar decision head | survey §1.2.2, §6.1.4.3 | repository `Zefan-Cai/Open-Jev`; dataset `ZefanCai/Open-Jev` (CC0) and v1.1. Model-weight repo id **not stated in survey** |

**Reference decision checkpoints at ≤ 9B whose HF id the survey states** (these are the only ones we
may name; the other mirrored checkpoints appear in survey §6.1.4.2 as short names only):

| Checkpoint | HF id as the survey gives it | Size | Size on disk if the survey states it |
| --- | --- | --- | --- |
| Kev-9B | `jaredpalmer/kev-9b` | Qwen3.5-9B | not stated in survey (the 40-model mirror is about 79 GB in total) |
| Bespoke-Nimble-9B-v3 | `bespokelabs/Bespoke-Nimble-9B-v3` | Qwen3.5-9B + LoRA | not stated in survey |
| Tev1-4B-experimental | `togethercomputer/Tev1-4B-experimental` | Qwen3.5-4B | not stated in survey |
| OneJev-9B | `OmniJev/OneJev-9B` | Qwen3.5-9B | not stated in survey |
| Laya | `convaiinnovations/laya` | 421M / 322M encoder | not stated in survey |

Short names only, **full repo id not stated in survey**: `decider-0.8b`, `Decision-2.0-Kai-0.6B`,
`SanSi-2.6B`, `Lev-2.6B`, `AgentDecision-4B`, `kev 0.5/0.8/4B`, `Nimble-9B` v1 and v2,
`JevAny-Qwen3.8-27B-LoRA`, `ufakzeka-karar`, `rlcd-modernbert-151m` (survey §6.1.4.2). Above 9B and
therefore out of scope: `perplexity-ai/pplx-decider-v1.2`,
`startlux-models/StartLux-Decision-v1.1-27B-Instant-GGUF`.

---

## 4. HF dataset repo ids to re-download, with the split each row needs

| HF repo id | Split / subset needed | Which rows it unblocks | Size if the survey states it |
| --- | --- | --- | --- |
| `LocalLLaMA/typed-decisions` (Apache-2.0) | whole set, 1,200 states × 5 questions, **with the annotator distribution field** | A3 (35% disagreement, median TV 0.14), and R1-2's comparison target | not stated in survey |
| `akhilaaa3/decision-bench` (Apache-2.0) | `medium` (80 states) and `hard` | A1 (90.48% state macro-average), A2 (score vs choice) | not stated in survey |
| `ZefanCai/Open-Jev-v1.1` (CC0) | synthetic `community-diversity-v2`; split **`family_disjoint … 1 ood`** (5,120 `ood` rows); plus the full 147,139-row mixture for A7 | A6, A7; proposal R1 rule-family hold-out and R3-5's no-regression test | not stated in survey |
| `jaredpalmer/kev-suites` | **`transfer-v4`** (the "new sources" column; KEV-PROTOCOL §0) and `decision-v7` (trained sources), plus `diagnostics/binding-v1` (560 items, six tiers). `breadth-v1` is not in `kev-suites`: its partitions are private (`jaredpalmer/kev-private-evals`, HTTP 401), and Kev reports it only as a chance-corrected index | B1–B4, and the L1 row of survey §6.2.5 | **0.3 GB** |
| `startlux-models/DecisionPivot` | core track contrast pairs, difficulty 1–3 (7,800 items); reference track 32,233 | C8 (87.7% → 57.4%) | not stated in survey |
| `Praveenrajus/jev-bench` | 22,773 test questions with two key permutations and the label priors | infrastructure for the same-backbone log-probability baseline (C25 / checklist B1) | **2.95 GB** |
| `Hanno-Labs/decision-bench` | the three `compact_*` paraphrase columns | question-side paraphrase invariance (survey §2.3 omission 4) | **0.98 GB** |
| `SabaPivot/jev-safety-bench` | `original` / `reversed` / `serialization_control` pairs | the order-permutation denominator of R0-1, which is currently unmeasurable locally | not stated in survey |
| `carlosxiang/JEVal` | 11,257 items, 36 datasets | any row quoted against JEVal | not stated in survey |
| `limberc/this-that` | spatial (15 families, 7,305 items, three renderings) and complex-decisions (1,710 items) | the L2 new-schema row of survey §6.2.5 | not stated in survey |

Not re-downloadable: `fstandhartinger/jevbench` **does not exist** on HF (survey §6.1.4.1), so B18
has no path; `RLCDAlignBench` is HF-gated and was excluded from the mirror (survey §6.1.4.2), so C24
stays blocked.

---

## 5. Where alignment is impossible or misleading

This section decides the wording of every comparison. Each item is a concrete mismatch, not a
caution.

**5.1 Their accuracy and our accuracy are different functions of the same model.** Kev reads a
trained pointer head, Tev1 generates an answer letter, Nimble emits an enum field, Intern-Decision
fills a JSON placeholder (survey §1.2.2). Ours is a raw-completion **label log-probability**
normalized over the level set, with no chat template (`R0-BASELINE-PREREG.md` §1, §8.7). Survey §7.1
records that the same-backbone log-probability baseline is met by only **5 of 26** applicable
papers, so in almost every published number the interface's credit and the model's credit are not
separated. Correct wording: "Kev-9B reports 0.852 on its own new-source suite with a trained pointer
head; our figure is an untuned log-probability readout on different data" — never "we reach X% of
Kev".

**5.2 Our headline operator abstains; theirs does not exist.** Our pre-registered accuracy is the
**cumulative-mass** decision with the residual going to C. In the R0 run, 33 of 41 fitted threshold
entries were flagged `collapsed`, 20 of them fitted at τ = 0.95, and held-out C-branch rates run up
to 0.9997 (`R0-BASELINE-RESULTS.md` §5). An accuracy produced by an operator that declines on most
rows is not the same quantity as a reference accuracy that always commits. The argmax reference
column is the only one shaped like theirs, and `R0-BASELINE-PREREG.md` §11.8 item 1 forbids
reporting it alone. Any row of this table placed beside one of ours must carry both columns.

**5.3 The splits do not correspond.** Kev's axis is **source-level** (`decision-v7` trained sources
vs `transfer-v4` new sources; `breadth-v1` is a separate, private panel reported by Kev only as a chance-corrected index); Open-Jev's is **rule-family** (`family_disjoint … 1 ood`);
`typed-decisions` and `akhilaaa3` have **no official split at all**, so ours (`group70`, plus a
question-disjoint split for `akhilaaa3` only) is one we invented. "New sources" in their table and
"held out" in ours are not the same level of the report's own L0–L6 scheme: theirs is L1, ours is
closer to L0 (survey §6.2.1, and the levels are the report's own construct).

**5.4 The label sets are not the same objects.** Our T1 re-renders each level set into four name
variants, which no public set does (survey §6.1.4.3 item 3: "no set has transformed the name set").
Worse, on `openjev-synth` the `original` names **are the answer** (counts 0–4) and the `digits`
variant contradicts its own definitions on **7,680 of 14,234 T1 units, 54%**
(`R0-BASELINE-RESULTS.md` §7.1). No name-invariance number from that source is comparable with any
published name-invariance number, and `R0-BASELINE-PREREG.md` §12.3 forbids reporting it as one.

**5.5 "Flip rate", "consistency" and "ECE" are not single quantities.** Flip rate has at least five
denominators (single shuffle, cumulative over eight presentations, list reversal, relabelling,
answer-preserving variants; survey §1.4.6). ECE has at least five algorithms (10 or 15 bins,
equal-width or equal-mass, relative to a finite-sample null; survey §1.4.5) and we use 10
equal-width bins. The same model's "consistency rate" is **99.83%** under byte-level rerun and
**53.7%** under answer-preserving variants, a 46-point spread (survey §2.1.8). Any sentence of the
form "our consistency is X, the literature reports Y" is meaningless unless both denominators are
named in the same sentence.

**5.6 Three of our four consistency denominators are not measurable at all right now.** Byte-level
rerun is trivial under greedy decoding; order permutation and answer-preserving adversarial variants
need data that no longer exists locally (`R0-BASELINE-RESULTS.md` §8 item 3). So C12 and C13's
order axis cannot be aligned until §4's re-downloads happen, and R0-1 has no number.

**5.7 Hosted-Jev numbers are moving targets, not baselines.** A1 (90.48%), B9's 93.2%, B13's 82.0%
and every Group C hosted figure come from a closed model that can change under the same name;
checklist item R1 asks for the exact model version and run date for exactly this reason (survey
§7.1). They may be quoted as **reference levels on their data**, never as a baseline we beat or miss.

**5.8 Our cells are too small for a point comparison on `akhilaaa3`.** Held-out `group70` cells hold
**19 to 63 units**, the question-disjoint cells 17 to 43, and the watchdog flagged **26 primary
values below the minimum sample count** (`R0-BASELINE-RESULTS.md` §7.4). Against reference numbers
computed on thousands of items, only the **direction** of an effect on this source is reportable.

**5.9 Degenerate arms must travel with every number.** In the R0 run the constant classifier beats
the primary readout on all ten cells of the operator column, the question-only arm equals or beats
it on 6 of 10, and the one cell that passed name invariance has a constant arm (`true` on 1,800 of
1,800 rows) (`R0-BASELINE-RESULTS.md` §3.1, §4, §7.2). Comparing any of our accuracies to a
reference accuracy without its empty-input, question-only and majority-class twins reproduces
exactly the measurement failure CLAUDE.md §7.1 exists to catch.

**5.10 A prompt change voids the comparison we actually care about.** Decision line B-4 (training
improves held-out accuracy without raising the T1 flip rate by more than 2 points) requires the
post-training report to use the **same prompt version** as the baseline (`R0-BASELINE-PREREG.md`
§8.7). The rendering fix of C1 changes the rendering. If R3 adopts it, the before/after pair must be
rebuilt under one version, or the only internally valid comparison we own is lost — which would
leave us with nothing but the incomparable external rows above.

**5.11 Two load-bearing rows have no number to align to at all.** Symbol tuning (C22) is the method
R3 is built on and the survey states no effect size for it; survey §6.3.6 blind spot 2 records that
it has never been tried on a typed readout. The k-shot curve before and after decision tuning (R3-3)
is listed in survey §7.5 row 2 as something no paper has measured. For both, R3 produces the first
number rather than matching one, and the write-up must say so instead of implying a target was hit.
