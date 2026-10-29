# R3 first SFT round (round 1): pre-registration

> 2026-10-30 · Draft. The orchestrator's rulings of 2026-10-30 are written in (§13). It becomes frozen
> when committed, and it must be committed **before** any scored run it covers, including the untuned
> K0 scoring. After that only results are filled in; changes go in numbered amendments that cite
> clauses (`§n.m`) by number (proposal `00-research-proposal.md` §0 rule 3).
>
> Sources: `KEV-PROTOCOL.md` (Kev's protocol, with file:line citations into
> `/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev`, here written `kev/`; where a citation is marked
> `@5f78968` it is the commit the Kev stage-1 trials ran, `runs/q35-08b/*/provenance.json`),
> `R3-REFERENCE-TARGETS.md`, `R0-BASELINE-PREREG.md` (here written `R0 §n`), `R0-BASELINE-RESULTS.md`
> (`R0-RES §n`), proposal R3. Constructs that are the report's own and not literature conclusions
> (CLAUDE.md rule 4.4): P0″, P2″, P3″, the defect-registry framing, the generalization levels.

---

## 1. What this round is, and what it is not

1.1 The first weight update in the program: supervised fine-tuning of Qwen3.5 checkpoints on Kev's
public `decision-v7` training set, read out with **our** label log-probability readout. It is measured
on two pre-registered tracks: Track K (Kev's own suites and metric, §4) and Track T (our task set and
the R0 decision lines, §6).

1.2 It is a subset of proposal R3. It does **not** measure R3-1 (swap AUC), R3-2 (definition
deletion) or R3-3 (k-shot curves), and its arms are not the R3-4 fixed-level-set control. **Gate G2 is
not decided by this round** (§12).

1.3 The defect-registry row (survey §2.2.4) that each measure points at:
- Track K accuracy is the P2″ floor on Kev's level sets. It reads rows 1 and 17 (levels must be read;
  definitions are shown) and row 8 (Kev `score` questions are ordinal).
- The permutation flip rate reads row 6, as an invariance measurement on untrained (K0) models only
  (§4.8).
- The none-of-the-above pair reads rows 5 and 16.
- The K3 symbol arm reads rows 1 and 17.
- B-2, B-3 and B-4 read rows 1 and 17, as in R0 §3.1.

---

## 2. Models and data, frozen

2.1 **Checkpoints** (local, `/mnt/cephfs/xingchao/models/jev/`): `Qwen__Qwen3.5-0.8B-Base` (revision
`dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`, the revision Kev trained from, `experiments/q35-08b.json`),
`Qwen__Qwen3.5-0.8B` (the R0 model), `Qwen__Qwen3.5-{2B,4B,9B}-Base`. The revision of every
checkpoint is written into every report header. No size ≥ 10B is used.

2.2 **Kev data**, converted by `r1_code/convert_kev.py` (converter sha256 `b89269f9…`), at
`/mnt/cephfs/xingchao/experiments/jev/KEV/`, verified against `KEV/manifest.json` on 2026-10-30. Each row
is one question, and every row has `candidate_set = exclusive`. Training (§3.4) re-converts augmented
Kev records from the original `SUITES/v7/decision-v7/train.jsonl` with the same converter.

| suite / partition | clean questions | variant questions (`permuted` / `none_present` / `none_absent`) | role |
| --- | --- | --- | --- |
| decision-v7 train | 15,576 (12,576 records) | 0 | training; constant fit (§5.1) |
| decision-v7 calibration | 1,148 | 0 | τ fit for the Track K operator column (§4.4) only |
| decision-v7 dev | 1,264 | 84 / 60 / 60 | selection |
| decision-v7 test | 1,200 | 96 / 72 / 72 | locked (§8.4) |
| transfer-v4 dev | 656 | 36 / 36 / 36 | selection |
| transfer-v4 test | 656 | 36 / 36 / 36 | locked (§8.4) |

Clean rows are in `<suite>/<partition>.jsonl` and variant rows in `<suite>/<partition>.variants.jsonl`.
A variant links to its clean parent by `kev.parent_id` + `kev.qindex`, and variants never enter a
headline number. transfer-v4 sources are never trained on (KEV-PROTOCOL §5, `kev/train.py:114-116`).
The `contrastive` source appears in decision-v7 test (160 questions) but not in its dev or train.

2.3 **Track T data**: the R0 task files T1/T2/T3 exactly as frozen in R0 §2 and §9.1, split by
`group70` (and by `question70` for `akhilaaa3`, reported additionally) using the R0 `split.py`.

2.4 **Symbol data** (K3 only): `r1_sft_data/symbol/` **rebuilt** with `r1_code/build_sft.py --arm
symbol`, using k = 2, p_swap = 0.25, the τ carve-out of §2.6 excluded, the `openjev-synth` T1 `digits`
variant excluded (R0 §12.3), the `digits` identifier family excluded from every `openjev-synth`
augmentation (a random digit over a count definition recreates the same conflict), and
`openjev-synth` capped at 40% of rows (`--openjev-max-share 0.4`).
Eligible rows come from the `group70` train side and, for `akhilaaa3`, also the `question70` train
side. T2 swap and reversed rows are used only with recomputed gold, and T3 is never used. The
frozen build (copied from the rebuilt `manifest.json`, 2026-10-30): 103,238 rows; `typed-decisions`
58,198 (56.37%), `openjev-synth` 41,280 (39.99%), `akhilaaa3` 3,760 (3.64%); 58,028,195 prompt and
260,713 response tokens; `train.jsonl` sha256
`7b1edec5f6e0d3a7e7fd1e8778f0afdb11f756c956f2de02102d6a212c961540`. An independent orchestrator
check over this file found no `group70` held-out group, no `question70` held-out question and no
r3tau-carved group. The 168,094-row build of 2026-10-30 00:13 UTC and the 103,238-row build that
still drew `digits` identifiers for `openjev-synth` (sha256 `1ec55dba…`) are superseded.
The `fixed` build (not used by any round-1 arm) is 8,427 rows, sha256 `ed24c17a…`.

2.5 **Track T selection and report halves.** Each held-out side (`group70`, and `question70` for
`akhilaaa3`) is split by `bucket(sha256("r3sel:" + group_id))`. The bucket is the first 8 bytes of the
digest, read as a big-endian integer, modulo 10,000, the same convention as `split.py`. Bucket < 5000
is the **selection half** and the rest is the **report half**. Cell sizes per (source, level type)
and half are deterministic from this rule and are printed in every Track T report. Totals on the
`group70` held-out side, counted by the orchestrator on 2026-10-30 as distinct (`group_id`, `qname`)
units, selection / report: T1 and T2 `typed-decisions` 870 / 995, `openjev-synth` 540 / 608,
`akhilaaa3-hard` 68 / 52 (T2 72 / 55), `akhilaaa3-medium` 19 / 53 (T2 19 / 54); T3 `typed-decisions`
870 / 995. The `akhilaaa3-medium` selection half is small enough that its cells will mostly fall below
the minimum sample count; this is why `akhilaaa3` cells never gate (§8.2 c).

2.6 **Track T threshold-fitting carve-out.** Groups on the `group70` train side with
`bucket(sha256("r3tau:" + group_id)) < 1500` (about 15% of train groups) form the τ-fitting set. They
are excluded from all training data in every arm (in this round only K3 draws on Track T data), and in
R3 they are the only Track T rows τ is fitted on. The size and the fallback-tier usage (R0 §8.3) are
reported. The carve-out covers Track T only; Track K τ is fitted on decision-v7 calibration (§4.4).

---

## 3. Readout, prompt and training-time augmentation

3.1 **Prompt**: `r0-prompt-v2`, raw completion, no chat template, render mode `record_name`, built by
the single locked `prompt.py` (R0 §8.7). Training rows and evaluation prompts are byte-identical up to
the answer cue. A prompt change voids B-4 (R0 §8.7) and voids every Track K comparison across arms.

3.2 **Readout**: for each question, candidate `i` is the string `" " + name_i`. Its score `s_i` is the
**unnormalized sum** of the log-probabilities of its tokens after the prompt, computed in fp32 from the
logits, with the tokenization the R0 scorer uses. The readout distribution is `softmax(s)` over that
question's options. Every readout row stores the raw `s_i` for each candidate alongside the
probabilities (R0 §12.6, §13.3).

3.3 **Declared differences from Kev**, stated in every Track K table header:
- (a) The readout is the label log-probability continuation, not Kev's pointer head over `</opt>`
  states (`kev/model.py:205-217`).
- (b) The prompt has a task definition, `- name: definition` options and `Answer:`, not Kev's
  special-token format (`kev/model.py:87-119`). Where Kev gives no description, our definition equals
  the name.
- (c) The training unit is one question, not one record (§7.2).
- (d) K1's loss is over the full vocabulary (§7.2).
- (e) There is no new head: the existing LM head is used and kept frozen.
- (f) Record order is shuffled per question, not per record. Kev's loss weights each record's mean
  question loss, while ours weights questions equally (`kev/train.py@5f78968:200-219`).

3.4 **Training-time augmentation: Kev's stage-1 augmentation, replicated exactly as implemented.**
It is applied to the Kev training **records** before conversion, in every arm that uses Kev training
data (K1, K1-PT, K1-QO, K2, and K3/K4 through inheritance). It is implemented by calling Kev's own
functions from the pinned repository.
- Per seed `s` and 0-based epoch `e`, every record gets
  `item_rng = random.Random(source_seed(s, f"{e}:{record _meta.id}"))`
  (`kev/train.py@5f78968:184`; `source_seed` at `kev/data.py:20-21`, which is identical at both
  commits).
- Then `augment(req, item_rng, p_none=0.1, p_none_distract=0.12, p_distract=0.15)`
  (`kev/data.py@5f78968:311-333`). For choice questions only (noul and score are untouched), one draw
  `r` decides the change:
  - `r < 0.10`, if the question has more than 2 options: a none-of-the-above (NOTA) option replaces the
    gold and becomes the label.
  - `0.10 ≤ r < 0.22`: a NOTA option is added as a wrong alternative.
  - `0.22 ≤ r < 0.37`: one of 4 fixed irrelevant distractors is added (`DISTRACTORS`,
    `kev/data.py:56`).
  - Whatever `r` is, the option order is **always** shuffled.

  NOTA options are drawn from the 13-entry `NONE_OPTIONS` list (`kev/data.py:51-55`; identical at both
  commits), excluding any key the question already has.
- Then, with probability `p_none_pair = 0.25`, drawn from the same `item_rng`, `none_pair(req,
  item_rng)` adds a minimal pair: one eligible choice question (≥ 3 options) rendered with and without
  its gold, plus the same NOTA option (`kev/train.py@5f78968:186-187`, `kev/data.py@5f78968:335-348`).
  5,224 of 12,576 train records have an eligible question, so about 1,306 pairs (2,612 extra questions)
  are expected per epoch.
- Rates: `kev/train.py:400-403` (defaults); `p_none_pair` from `experiments/q35-08b.json`. The trial
  provenance config records all four.
- The current `augment`/`none_pair` differ from `@5f78968` only for soft-target questions. decision-v7
  train has none (0 of 15,576 rows carry `has_target`), so the two commits behave identically on this
  data.
- Pair siblings ride in the optimizer step of the question that produced them and do not count toward
  the batch (as in `kev/train.py@5f78968:181-191`).
- The training NOTA keys (`other`, `none`, `not_listed`, `none_of_the_above`, `unknown`, `no_match`) do
  **not** include the evaluation variants' key `none_of_these`.

---

## 4. Track K metrics

4.1 **Headline accuracy**, exactly Kev's metric: for each question, the prediction is the argmax over
that question's options, and accuracy is the micro mean over the clean questions of the partition
(`kev/metrics.py:73` `acc.append(int(p.argmax() == y))`; `:78` `np.mean(acc)`; clean filter
`kev/benchmark.py:76`). Reported per suite and partition. Per-source and per-`level_type` breakdowns
are reported beside it, never as a headline.

4.2 **Tie rule (Track K headline).** KEV-PROTOCOL §4 documents numpy `argmax`: the **first** maximal
index in the stored option order wins. The headline uses that rule, computed on the raw fp32 scores
`s_i` of §3.2. Two numbers are always reported beside it: the tie count (questions with ≥ 2 options
exactly equal at the top) and the accuracy under the R0 convention, where a tie is not correct
(R0 §12.5, §13.1). Track T keeps R0's rule (§6.1).

4.3 Unconstrained optimum of the headline: a lookup of the majority option per (source, question), or
an answer from the question wording alone. It is sealed by §5 and decision line K-floor (§9.2).

4.4 **Operator column (secondary).** Labelled **a statement about the harness, not about the model**
(R0 §11.8 item 1, R3-REFERENCE-TARGETS §5.2). It is the R0 cumulative-mass operator, unchanged: the
R0 §8.3 grid, utility, tie rule and fallback tiers, and the §11.3 prohibition. τ is fitted per model on
decision-v7 **calibration** and applied unchanged to dev and test of both suites. transfer-v4 has no
calibration partition, so its sources fall to the (type, size) tier. Reported as accuracy, C-branch
rate and fitted τ, and never compared with a Kev number.

4.5 **Order-permutation flip rate (secondary; invariance; row 6).** The unit is a (clean parent,
`permuted`) pair.
- Pairs whose option order equals the parent's are **excluded** and counted, because they would
  contribute zero by construction: decision-v7 dev 29 of 84, test 30 of 96; transfer-v4 dev 2 of 36,
  test 1 of 36.
- A flip means the chosen level **id** differs. Pairs where either side is tied at the top are dropped
  and counted (R0 §13.1 item 1).
- Unconstrained optimum: any input-ignoring classifier keyed to a level id, which scores 0.
- Discrimination counterpart: accuracy on the permuted rows and the share of pairs correct on both
  sides, reported beside the flip rate.
- For every arm trained with §3.4's option shuffling, this flip rate is **in-distribution** and is
  governed by §4.8.

4.6 **None-of-the-above pair (secondary; rows 5 and 16).** The unit is a parent that carries both NOTA
variants: decision-v7 dev 60, test 72; transfer-v4 36 / 36.
- Reported:
  - the `none_absent` NOTA-selection rate (gold removed, so the NOTA option is correct);
  - the `none_present` accuracy and false-NOTA rate (gold present);
  - **both-sides-right**: `none_absent` picks NOTA **and** `none_present` picks gold.
- Unconstrained optima: "always NOTA when offered" scores 1.0 on `none_absent` and 0 on `none_present`;
  "never NOTA" scores the reverse. Both score 0 on both-sides-right, which is the primary number of this
  pair.
- From K1 onward the arms train on NOTA options and minimal pairs (§3.4), but under keys other than the
  evaluation key `none_of_these`, as Kev's own training did.

4.7 The secondary metrics (§4.4–4.6) gate nothing in this round. They are reported for every scored
model.

4.8 **Permutation flip rate of trained arms is a sanity metric, and the row-6 spend is declared.**
- Every arm that trains on Kev data with §3.4 shuffles option order on every training example: K1,
  K1-PT, K1-QO, K2, K3, K4 and the ladder runs. For these arms the §4.5 flip rate is
  **in-distribution**. It is reported only as a sanity metric, labelled as such, and **never** as an
  invariance finding. Only K0 (untrained) permutation numbers may be read as invariance.
- **Declared.** Shuffling spends training budget on registry row 6, which survey §2.2.4 marks "solved
  and free; should get no further training budget". The spend is kept because K-align (§9.1) requires
  replicating Kev's stage-1 recipe, and that recipe shuffles.

---

## 5. Track K degenerate baselines (rule 4.2), reported beside every trained number

5.1 **Constant**: the majority gold level per (source, `qname`) on decision-v7 train. When that key is
absent (all of transfer-v4; `contrastive` in decision-v7 test), the fallback is the majority gold
**position** per (`level_type`, number of options) on decision-v7 train, and after that position 0.
Tier usage is reported.

5.2 **Question-only, test-time**: the scored model itself with `input_mode = drop` (R0 §4 item 2).

5.3 **Empty-state, test-time**: the scored model itself with `input_mode = blank` (R0 §4 item 1).

5.4 **Uniform**: equal mass on every option. Under §4.2 it always picks position 0, so its headline
equals the share of gold at position 0. Under the R0 convention it scores 0. Both numbers are reported.

5.5 **Trained question-only seal**: arm K1-QO (§7.9). A trained number on transfer-v4 that does not
beat K1-QO's accuracy on the same partition by ≥ 5 points is reported as **not a semantic-transfer
claim**.

---

## 6. Track T

6.1 Harness, prompt version and metric definitions are R0's as amended through R0 §13, unchanged:
- T1 flip (argmax primary, R0 §11.2), T2 move (argmax, §8.2), T3 flip;
- the accuracy floor (cumulative-mass operator), C-branch rate, margin (decisions only, §11.4), ECE;
- ties per §12.5/§13.1, and nulls per §11.1.

What R3 changes: τ is fitted **only** on the carve-out of §2.6, and results are computed separately
on the two halves of §2.5. The constant classifier is still fitted on the `group70` train side
(R0 §4 item 3).

6.2 **Decision lines of record**, reported on the **report half** only, for every scored model and
separately for each seed:
- **B-1**: operator accuracy ≥ constant + 10 points, per source.
- **B-2**: T1 argmax flip against empty-input, with pass, void or fail set by the R0 §13.5 gap rule,
  per cell.
- **B-2 (T3)**: the same test on T3, `typed-decisions` only.
- **B-3**: T2 followed-rate > 30% and ≥ 10 points above the same cell's T1 flip (R0 §8.5, §11.2).

A line is reported as passed for an arm only if it passes for every seed of that arm.

6.3 **B-4**: a trained model improves held-out accuracy over its untuned base without raising the T1
argmax flip rate by more than 2 points.
- Evaluated per (source, level type) cell on the report half, against the K0 Track T score of the
  **same base checkpoint** under the same R3 configuration.
- **Admissibility (ruling 3)**: a B-4 accuracy claim on a source is admissible only where the
  **trained** model clears B-1 on that source. Where it does not, B-4 for that source reads **"not
  admissible"**, not "fail".
- For K1-PT (§7.8) B-4 is also evaluated against **R0 itself**. K1-PT's readouts are re-derived under
  the R0 configuration (τ fitted on the full `group70` train side, the whole held-out side, R0's tie
  rule) and compared with `r0_baseline_rederived/report.json`. This is valid because K1-PT never trains
  on Track T data.

6.4 Reporting caveats carried from R0:
- `openjev-synth` T1 numbers are reported as a label/definition conflict, never as name invariance
  (R0 §12.3).
- The B-2 pass on `typed-decisions` boolean carries the constant-arm caveat (R0 §12.4) if it recurs.
- `akhilaaa3` cells carry their n, and only their direction is reportable.

6.5 **Harness identity check.** K0 on `Qwen3.5-0.8B`, derived under the R0 configuration, must
reproduce `r0_baseline_rederived/report.json` for every metric the tie rule does not affect. Any other
difference stops the round until it is explained.

---

## 7. Arms (round 1; every arm at 0.8B first)

7.1 **K0 untuned.** Each checkpoint of §2.1 is scored as is on both tracks, with all degenerate arms.
Order: `Qwen3.5-0.8B-Base`, `Qwen3.5-0.8B`, then 2B/4B/9B Base when the ladder reaches them.

7.2 **K1 Kev-recipe replication.** Base checkpoint `Qwen3.5-0.8B-Base`.
- **LoRA**: r = 16, alpha = 32, dropout 0.05. Targets: `q_proj, k_proj, v_proj, o_proj, gate_proj,
  up_proj, down_proj, in_proj_qkv, in_proj_z, in_proj_a, in_proj_b, out_proj` (`kev/model.py:266-274`,
  the hybrid list). Embeddings and LM head are frozen.
- **Optimizer**: AdamW, weight decay 0.01; `OneCycleLR(max_lr = 1e-4, pct_start = 0.1)` over all
  steps; global grad-norm clip 1.0; bf16 compute over fp32 master weights and optimizer state
  (`kev/train.py:376, 503, 534, 580, 588`). 2 epochs.
- **Data**: decision-v7 train only, augmented per §3.4, one example per question, rendered with §3.1.
  Example order is shuffled per epoch from the seed.
- **Batch: 10 base questions per optimizer step**, global, with their §3.4 pair siblings riding
  along. That is ⌈15,576 / 10⌉ = 1,558 steps per epoch and 3,116 in total. Kev runs 8 records per step
  (≈ 9.9 questions), 1,572 steps per epoch and 3,144 in total (`experiments/q35-08b.json`;
  `runs/q35-08b/00-trial-0/train.log`, "step …/3144"). Declared difference.
- **Seeds 2 and 3** (ruling 5).
- **Loss**: token cross-entropy on the response `" " + gold name` only, with prompt tokens masked,
  averaged over the response tokens in the step, and **no EOS token in the loss** (if the framework
  appends one, it is masked).
- **Model of record**: the end-of-training checkpoint, as in the Kev stage-1 trials.

7.3 **K2 option-restricted loss.** As K1, but the loss for each question is `−log softmax(s)_gold`,
where `s` holds the §3.2 summed identifier log-probabilities of **all** that question's options,
including any options §3.4 added. This is Kev's objective (`kev/train.py:51`) expressed in our readout.
It is averaged over the questions in the step. A test asserts that the `s` computed at training time
equals the evaluation scorer's `s` on fixed rows to within 1e-3 nats (fp32).

7.4 **K3 symbol mix.** Starts from the better of K1 and K2, chosen by applying §8.2 to the two. To
that arm's data it adds 6,675 rows of §2.4, so that symbol rows are 30% of the 22,251 base examples per
epoch. Symbol rows are not passed through §3.4.
- The 6,675 rows are drawn once, in ascending order of sha256(`"k3-mix-v1" ‖ row key`), and reused in
  both epochs. Their source composition is reported.
- Steps per epoch: ⌈22,251 / 10⌉ = 2,226.
- §3.4 pair siblings bring the realized symbol share to about 27%; the realized share is reported.

7.5 **K4 full fine-tuning.** Starts from the arm adopted at that point, with all parameters trained and
no LoRA. lr is 1e-5 or 2e-5, with two seeds each; everything else follows the adopted arm. The lr with
the higher seed-mean combined-dev accuracy (§8.2) is chosen, and K4 is then adopted or rejected by
§8.2.
- **Declared deviation** from proposal R3, whose protocol limits training means to "LoRA, data
  composition, structural isolation and temperature". The reason: K4 is an improvement arm outside the
  reference-alignment comparison (Kev uses LoRA), and K-align is judged on K1 only.
- **Proposal R3 must be amended before K4's result is cited as an R3 result.**

7.6 **Ladder.** The recipe adopted at 0.8B runs unchanged on 2B, 4B and 9B Base, with **one seed
(seed 2)**, declared. Nothing is re-tuned per size. The one permitted change is a smaller micro-batch
with the same global batch when memory forces it, and that is recorded.

7.7 Every run writes into its directory: the resolved config, the data file sha256s, the prompt
version, the checkpoint revision, the kernel record (§11.3), the loss curve and the relaunch command.

7.8 **K1-PT.** K1's recipe, seeds included, on `Qwen3.5-0.8B` (the post-trained checkpoint R0 scored).
It exists so that B-4 can also be evaluated against R0 itself (§6.3). It is a control, not a candidate
for adoption.

7.9 **K1-QO.** K1's recipe with the state removed from every training prompt (`input_mode = drop`),
at 0.8B with seed 2 only. It is scored with the state dropped, matching how it was trained. Its dev
accuracy is the trained question-only seal of §5.5. It is a control, not a candidate for adoption.

---

## 8. Selection, adoption and the test lock

8.1 Selection uses only decision-v7 dev, transfer-v4 dev and the Track T **selection half**. Test
partitions and the Track T report half never inform any choice.

8.2 **Continuous-improvement rule** (0.8B; two seeds per arm). Candidate arm A replaces the current
best B only if all three conditions hold:
- (a) **Paired bootstrap.** The combined dev set is decision-v7 dev plus transfer-v4 dev, 1,920
  questions. For each question, correctness is averaged over the two seeds of each arm. The statistic
  is the micro-accuracy difference A − B. It is resampled 10,000 times over questions with
  `numpy.random.default_rng(20261030)`, and the 90% percentile CI must have a lower bound > 0.
- (b) Neither suite's seed-mean dev accuracy drops by more than 1.0 point.
- (c) The seed-mean T1 argmax flip rate on the Track T selection half does not rise by more than
  2 points in any **gating cell**. Gating cells are the `typed-decisions` T1 cells that are not void
  under R0 §13.5 for either model. `akhilaaa3` cells are reported but do not gate, and `openjev-synth`
  never gates (R0 §12.3).

K1 becomes the first adopted arm if it clears K-floor (§9.2).

8.3 Every §8.2 comparison is reported with each suite's n, the per-seed accuracies, the bootstrap CI,
and the per-question discordant counts.

8.4 **Test lock.** For each size, test partitions are read only after all selection at that size is
final:
1. The final model is named in `FINAL.json` in the round directory.
2. Only then is each test partition (clean and variants) read, **once**. The read covers the final
   model (every seed), that size's K0 checkpoint(s) and, at 0.8B, K1-QO and K1-PT.
3. Each read appends one line to `TEST-READS.log`: UTC time, model path and sha256, suite, partition,
   n and headline accuracy.

The scorer refuses a test partition unless the model is named in `FINAL.json` and has no earlier line
for that partition.

---

## 9. Track K decision lines, stated before any run

9.1 **K-align.** The two-seed mean of K1 at 0.8B reaches decision-v7 dev ≥ 0.80 **and** transfer-v4
dev ≥ 0.60, with both seeds reported. The like-for-like reference (a single stage, with the same
augmentation) is Kev's stage-1 trials on `Qwen3.5-0.8B-Base`, seeds 0/1/2: decision-v7 dev 0.8172 /
0.8196 / 0.8291 (n = 1,264) and transfer-v4 dev 0.6220 / 0.6341 / 0.6433 (n = 656)
(`runs/q35-08b/{00-trial-0,01-trial-1,02-trial-2}/result.json`, KEV-PROTOCOL §5). If the line is not
met, the gap is reported as a gap with its declared causes (§3.3); it is not explained away.

9.2 **K-floor.** Every seed of every trained arm beats both the constant (§5.1) and the test-time
question-only arm (§5.2) by ≥ 5 points on the dev partition of both suites. An arm that fails K-floor
cannot be adopted.

9.3 **K-ladder.** For the adopted recipe, dev accuracy on each suite does not decrease with size
(0.8B ≤ 2B ≤ 4B ≤ 9B; 0.8B uses the seed-2 run for like-for-like). Each size is reported beside the
Kev released numbers (dev / test). Those numbers are an **upper reference, not a target**: they come
after two further training stages and a fitted temperature, and the temperature cannot change argmax
accuracy (KEV-PROTOCOL §1, §5).

| Kev 1.0 release | decision-v7 (trained sources) | transfer-v4 (new sources) |
| --- | --- | --- |
| Kev-0.8B | 0.827 / 0.838 | 0.648 / 0.697 |
| Kev-4B | 0.873 / 0.865 | 0.817 / 0.838 |
| Kev-9B | 0.874 / 0.873 | 0.820 / 0.852 |

Kev released no 2B model, so the 2B row has no reference.

9.4 Every Kev comparison follows the wording of R3-REFERENCE-TARGETS §5.1: "Kev reports X on its suite
with a trained pointer head; our figure is a label log-probability readout of a model trained with the
declared differences of §3.3". Never "we reach X% of Kev".

---

## 10. Reporting and measurement-trap checks

10.1 Every rate carries its n. Every accuracy also carries its tie count, and every flip rate its
dropped-pair count and C-branch rate (R0 §11.1).

10.2 Every throughput figure is **per chip**, with the chip count stated (tokens/s/chip and
examples/s/chip), never an aggregate alone.

10.3 The watchdog flags any rate of exactly 0.0 or 1.0, any metric identical across cells, and any
cell below the minimum sample count. Each flag is explained **before** the number is reported
(CLAUDE.md §7.1).

10.4 Before the first Track K number of each model:
- (a) The constant and uniform arms are computed first, and the gold-position distribution per suite
  and partition is reported. In decision-v7 train the gold is at position 0 on 5,416 of 15,576
  questions.
- (b) For one record per source, the rendered prompts of the clean, permuted and both NOTA variants are
  hashed, and the hashes must all differ.
- (c) For 20 rows, the stored argmax is recomputed from the stored `s_i`.

Before the first training step: for 20 train records, the §3.4 output is compared against Kev's
functions called directly, and must be byte-identical.

10.5 A clause of this file that changes a number is **in force** only when a test naming the clause
asserts it. The report header lists the clauses in force and those not in force (R0 §11.8 item 3).

---

## 11. Compute and run hygiene

11.1 Host 175 (`npu`), 8 × Ascend 910B3; image `nga-verl-qwen35-v030:20261029`; verl FSDP SFT. The
chip count of every run is recorded. Scoring and training use `python3 -P` inside the container, never
`-I` (CLAUDE.md §6).

11.2 Every run longer than a minute follows CLAUDE.md §7:
- launched with `docker run -d`, a fixed container name and no `--rm`;
- log and heartbeat on cephfs;
- a terminal marker holding the exit code, which is the source of truth for whether the run finished;
- resumable at step (training) or item (scoring) granularity;
- the relaunch command written into the run directory.

11.3 **Kernel choice.** The fast gated-delta-rule kernel under validation
(`/mnt/cephfs/xingchao/docker/verl_v030_20261029/speedup/`) may change speed and nothing else. A run
may use it only after all three checks below pass against the reference kernel, on fixed batches of
real training rows, with the results recorded in that run's directory:
- (a) **Forward**: the relative L2 error of the logits is ≤ 1e-2.
- (b) **Gradient**: for every trainable parameter tensor, cosine ≥ 0.999 and relative L2 error
  ≤ 1e-2.
- (c) **Tracking loss curve**: both kernels run the first 300 steps with the same seed and data. The
  mean per-step |Δloss| must be ≤ 0.02 nats, and the mean loss over the last 50 steps must agree
  within 1%.

If any check fails, the run uses the reference kernel.

---

## 12. What this round cannot claim

12.1 It does not decide G2 and does not measure R3-1, R3-2 or R3-3 (§1.2).

12.2 A Track K number cannot be compared with a Kev number as "the same model with a different head":
readout, prompt, training unit and loss weighting all differ (§3.3, §7.2).

12.3 Permutation and NOTA numbers rest on 34–96 units per partition and are directional only.

12.4 The Track T report half is untouched by selection, but it is about half the size of R0's held-out
cells. `akhilaaa3` cells on it are smaller still, and only their direction is reportable.

12.5 K3's T1/T2 numbers measure a model trained on the same kind of manipulation (renaming, definition
swap) on other groups of the same sources. They are not evidence of transfer to new sources.

12.6 K4's result is not an R3 result until proposal R3 is amended (§7.5). The ladder sizes have one
seed each, so differences between sizes that fall inside the 0.8B seed spread are not reportable as
size effects.

---

## 13. Rulings (orchestrator, 2026-10-30)

| # | Point | Ruling | Clauses changed |
| --- | --- | --- | --- |
| 1 | Tie rule | Track K: Kev's first-maximal-index rule, with the R0-convention accuracy and tie count beside it; Track T keeps R0's rule | §4.2 |
| 2 | Operator column | Kept as a secondary column, labelled a statement about the harness | §4.4 |
| 3 | B-1 before B-4 | A B-4 accuracy claim is admissible only where the trained model clears B-1 on that source; otherwise "not admissible" | §6.3 |
| 4 | B-4 vs R0 | New arm K1-PT on `Qwen3.5-0.8B`; B-4 also evaluated against R0 under the R0 configuration | §6.3, §7.8, §8.4 |
| 5 | Adoption and seeds | Seeds 2 and 3 at 0.8B; paired bootstrap on combined dev, 90% CI lower bound > 0; ≤ 1.0-point drop per suite; ≤ 2-point T1 flip rise on the selection half; ladder uses one seed | §6.2, §7.2, §7.5, §7.6, §8.2, §8.3, §9.1, §9.2, §9.3, §12.6 |
| 6 | K3 base | §8.2 applied to K1 vs K2 | §7.4 (ratified) |
| 7 | Track T selection | Held-out side split by `r3sel:` hash; selection half for choices, report half for decision lines | §2.5, §6.1, §6.2, §8.1, §8.2, §12.4 |
| 8 | τ for Track T | `r3tau:` carve-out (bucket < 1500) of the `group70` train side, excluded from all training, the only Track T τ-fitting rows | §2.4, §2.6, §6.1 |
| 9 | K4 | Kept, as a declared deviation from proposal R3; K-align judged on K1 only; R3 must be amended before citing K4 | §7.5, §12.6 |
| 10 | Batch and unbriefed choices | 10 questions per step (3,116 steps vs Kev's 3,144); end-of-training checkpoint, no EOS, mixing rule, constant fallback tiers and gating cells ratified | §7.2, §7.4 |
| 11 | Kernel gate | Proposed tolerances ratified | §11.3 |
| 12 | Kev augmentation | Replicated exactly as implemented, by calling Kev's own functions | §2.2, §3.3, §3.4, §4.6, §7.2, §7.3, §10.4 |
| 13 | Trained question-only seal | New arm K1-QO; §5.5 judged against it | §5.5, §7.9, §8.4 |
| 14 | Symbol data | Drop the `openjev-synth` T1 `digits` variant; cap `openjev-synth` at 40%; rebuild | §2.4 |
| 15 | breadth-v1 vs transfer-v4 | `R3-REFERENCE-TARGETS.md` rows B1–B4, §4 and §5.3 corrected | (other file) |
| F1 | Scope of the τ carve-out | Track T only; Track K τ is fitted on decision-v7 calibration | §2.6 |
| F2 | `digits` identifiers on `openjev-synth` | `digits` identifier family excluded from all `openjev-synth` augmentations; counts copied in later | §2.4 |
| F3 | Pair siblings and steps | Accepted: 3,116 steps, siblings ride in the parent's step, realized K3 share reported | §7.2, §7.4 (as written) |
| F4 | Shuffling vs row 6 | Shuffling kept for K-align; the flip rate of shuffled arms is in-distribution, a sanity metric only; the row-6 spend is declared | §1.3, §4.5, new §4.8 |
| F5–F9 | Seed-handling choices, extra test reads, R0-configuration comparison, smaller cells | Accepted as written | §6.2, §6.3, §6.5, §8.4, §9.1–§9.3, §2.5, §2.6 (as written) |

---

## 14. Amendments (made before any arm was trained or scored on test)

14.1 **Amendment 1, the kernel gate (§11.3 a and b), 2026-10-30.** The §11.3 (a) and (b) thresholds
were ratified without a measured noise floor, and they sit below it. On 8 real training rows the
*reference* kernel in bf16, compared with an fp32 gold run of itself, already has logits relative L2
1.07e-2 and fails the per-tensor relative L2 ≤ 1e-2 on 311 of 320 tensors
(`speedup/runs/modelcheck/model_check.json`). No bf16 run of this model can pass (a) and (b) as
written, so they test rounding, not the kernel. They are replaced, before the fp32-only check
(`speedup/runs/modelcheck32/`) has reported, by:
- (a′) **Same function, fp32.** With the model in fp32 and both kernels in fp32 on the same rows, the
  logits relative L2 between the fast and the reference kernel is ≤ 1e-4, and every trainable
  parameter tensor's gradient has cosine ≥ 0.9999.
- (b′) **No worse than the reference in bf16.** With e_X(t) the relative L2 of tensor t's gradient
  from kernel X in bf16 against the fp32 gold: e_fast(t) ≤ 1.5 · e_ref(t) + 1e-3 for at least 99% of
  tensors, and no tensor has e_fast(t) > 3 · e_ref(t) + 1e-3. The logits relative L2 against gold
  satisfies e_fast ≤ 1.2 · e_ref.
- (c) is unchanged. If any of (a′), (b′) and (c) fails, the run uses the reference kernel.

14.2 **Amendment 2, scorer padding, 2026-10-30.** A second, independent implementation of the
option log-probability (the K2 loss test) found that `r0_code/scorer.py`'s `HFScorer`, at its default
`token_budget`, LEFT-pads a question's candidates of different token lengths in one batch, and that
the padding changes the score (0.157 nats on one decision-v7 train row; repro
`r3_code/diag_padding.py`). Therefore:
- Every R3 readout, Track K and Track T, every arm including K0 and the degenerate baselines, is
  produced by a scorer whose rows are unpadded or RIGHT-padded. Both layer types are causal, so tokens
  after a position cannot affect it, and right padding is exact up to bf16 batch-size effects. A
  scorer is admissible only after it matches the unpadded layout (`token_budget=1`, one row per
  candidate) within the measured bf16 batch-size floor on a fixed sample of every suite.
- §6.3 and §6.5 (K1-PT against R0): the R0 side is re-scored with the admissible scorer on the same
  base checkpoint and prompt version. The published `r0_baseline` and `r0_baseline_rederived`
  readouts are not used as the R0 side of any comparison. The size of the defect in the published R0
  numbers is measured on a fixed sample and reported as an erratum to R0-BASELINE-RESULTS.md.
- K0 numbers produced before this amendment with the padded scorer are void and are re-scored.

14.3 **Amendment 3, trainer, 2026-10-30.** Round 1 trains with a single-chip PyTorch + peft trainer
(`r3_code/train_r3.py`) on the same image, not verl's FSDP SFT trainer. verl's trainer was measured at
7.3 s per step for 8 short questions on 2 chips, and it lacks four things this pre-registration
requires: LoRA dropout, the one-cycle schedule, per-epoch augmentation, and the K2 loss. Its LoRA
merge was also found to be a silent no-op for this checkpoint class. Recipe clauses (§3, §7) are
unchanged. The trainer's own tests (LoRA-only trainable, response-only loss mask, K2 equality with
an independent computation, right-padding invariance, exact resume) are recorded in each run
directory.
