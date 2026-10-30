# R3 first SFT round (round 1): pre-registration

> 2026-10-30 · Frozen as of 387521b (2026-10-30 00:44 +0800). The orchestrator's rulings of
> 2026-10-30 are written in (§13). It became frozen when committed, and it had to be committed
> **before** any scored run it covers, including the untuned K0 scoring. After that only results are
> filled in; changes go in numbered amendments that cite clauses (`§n.m`) by number (proposal
> `00-research-proposal.md` §0 rule 3).
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
- resumable at step (training) or item (scoring) granularity — *corrected for the §14.5 item 1 (i)
  identity run by §14.8 item 5: that run is resumable at readout-file granularity, and resuming a
  partial readout file in place is barred*;
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

14.2 **Amendment 2, scorer padding, 2026-10-30.** *Superseded in part by §14.6 item 5: the padding
diagnosis is withdrawn; the consequences stand on the corrected ground.* A second, independent
implementation of the
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

14.4 **Amendment 4, kernel verdict and a downstream kernel test, 2026-10-30.** Applying §14.1 as
written: (a′) passed (fp32 logits relative L2 5.85e-5, minimum gradient cosine 0.9999984), (b′)
failed (96.6% of tensors within the bound against 99% required; no tensor beyond 3×; logits ratio
1.016) (`speedup/runs/modelcheck2/model_check.json` via `speedup/code/gate_bprime.py`, 309 of 320
trainable tensors within the bound; the `NGA_GDN_FP32=1` variant `runs/modelcheck3-fp32in` gives
311 of 320, 97.2% — citation added by §14.8 item 2, which leaves this verdict unchanged), and (c)
failed (mean |Δloss| 0.0281, last-50-step mean −6.65%). This amendment's verdict and its kernel
references are to the fused gated-delta-rule / FLA kernel under `speedup/` only; a third
implementation is governed by §14.7 item 1. Every round-1 arm at 0.8B therefore trains on the
**reference** kernel. The (c) tolerance was found to sit below run-to-run noise: the reference against
its own same-seed rerun gives 0.0272 and −3.03%. It is not relaxed retroactively.
For the ladder only (2B, 4B, 9B), the fast kernel becomes admissible through one downstream test,
fixed now, before it is run: K1 seed 2 at 0.8B is trained a second time with the fast kernel (arm
K1-FLA, engineering only, never a candidate for adoption and never read on test). The fast kernel is
admissible for the ladder if, on **both** decision-v7 dev and transfer-v4 dev, K1-FLA's accuracy lies
within [min − 1.0, max + 1.0] points of the two reference-kernel K1 seeds, **and** the paired
per-question disagreement between K1-FLA and reference K1 seed 2 is no larger than the disagreement
between reference K1 seeds 2 and 3. Otherwise the ladder trains on the reference kernel.

14.5 **Amendment 5, R0 comparison target, open choices, run order, model of record, the ladder's
training mode, sequencing, the widened padding diagnosis and status, 2026-10-30.** Made before any
arm was trained and before any admissible readout exists (the pre-§14.2 K0 numbers are void). The user
set the goal of this round on 2026-10-30: train Qwen3.5 models below 10B on host 175 on local data
and report on Kev's own test sets (§9.4 wording). Each item names the clauses it changes, the reason,
and the resolution.
1. **§6.3, §6.5: the R0 side.** Reason: both clauses still name `r0_baseline_rederived/report.json`
   as the R0 comparison target, which §14.2 forbids as the R0 side of any comparison. Resolution:
   - The R0 side is `Qwen3.5-0.8B` (§2.1) re-scored by an admissible scorer (item 7) under the R0
     configuration of §6.3 (prompt `r0-prompt-v2`, τ fitted on the full `group70` train side, the whole
     held-out side, and the tie rule the published report used, pre-§13.1). K1-PT's B-4 against R0 is
     computed against this re-score only. R0 §13.5's B-2 pass/void verdicts and §8.2 (c)'s gating cells
     are recomputed on this re-score. The
     published R0 report's verdicts are not carried over to it.
   - §6.5 is split in two. **(i) Harness identity**: K0 on `Qwen3.5-0.8B` is derived under the R0
     configuration using the *same padded scorer the R0 run used* — `r0_code/scorer.py` at R0's commit,
     R0's `token_budget`, R0's shard count and shard assignment, and R0's image id, as recorded in
     R0-RES §2 — and must reproduce `r0_baseline_rederived/report.json` exactly for every metric the
     tie rule does not affect. Pad counts depend on batch composition, which depends on the sharding,
     so the shard assignment is load-bearing and is pinned, not inferred. **A difference under the fully
     pinned configuration is a code defect and stops the round.** A difference traceable to a
     configuration element that **cannot** be pinned is not a defect verdict and does not stop the
     round: it is pinned where possible, recorded where not, and carried into (ii) as a stated gap. Two
     such elements are known now: R0 recorded **no harness commit** (`git_commit: unknown`, R0-RES §2),
     so the source pin is the committed snapshot `experiments/r0_baseline/scorer.py`, verified
     byte-identical to the live `r0_code/scorer.py`; and R0 ran under image
     `sha256:4d683043…` while §11.1 names `nga-verl-qwen35-v030:20261029`, so if the R0 image is
     unavailable the image difference is recorded and (ii) is read with it stated.
     **(ii) Erratum measurement**: the scorer of record is run on the same items, and the two are
     differenced metric by metric. Per §14.6 item 5, (ii) reports (padded bf16 rerun − fp32) and
     (unpadded bf16 − fp32), and the scorer of record is fp32 with HF32 off (§14.6 items 2 and 3);
     the (i) rerun keeps R0's bf16, since reproducing R0 requires R0's precision. This has **no**
     pass bar and no stopping power; it is the content of the R0 erratum. Without the (i) padded rerun
     the (ii) difference could not separate the bf16 batch-composition noise these numbers carry
     (§14.6 item 5) from environment drift, which is why (i) is the control and why it is pinned.
     The (i) derivation is the only use of the padded scorer admitted in R3: it is a code-identity
     check against a published report, never a readout of record, so §14.2's unpadded/right-padded
     requirement is not weakened by it. Every number this round reports comes from the admissible
     scorer. The (i) derivation writes its readouts to `r3_runs/harness_identity/`. Its only consumer
     is the (ii) erratum difference, which is an R0 artifact (`R0-BASELINE-RESULTS.md`), not a report of
     record of this round. No number of this round cites a file in that directory; a test naming this
     clause asserts that no report of record of this round names a source path containing
     `harness_identity/`.
2. **§7.4, ruling 6: K3's base when §8.2 does not separate K1 and K2.** Reason: §8.2 is a one-way
   replacement test, so applying it "to the two" can leave neither better. Resolution: K1 is the
   incumbent and K2 the candidate. K3 starts from K2 only if K2 replaces K1 under §8.2; otherwise it
   starts from K1, the arm K-align is judged on (§9.1). Sub-case: if K1 fails K-floor (§9.2) and K2
   clears it, the base is K2; if neither clears K-floor, no base is fixed: K3's base is re-registered in
   the post-G1 amendment, because no admissible arm exists. Likewise K4 (§7.5) does not run in round 1
   if no arm is adopted after wave 1. This choice is made in round 1 (item 6) even though K3 itself does
   not run in round 1, and it is **provisional**: it is re-registered in the post-G1 K3 amendment, since
   arms trained between now and G1 may supersede it.
3. **§9.1: consequence of missing K-align.** Reason: §9.1 says the gap is reported but not what
   happens to the round. Resolution: the round continues on the order of item 4. The gap is reported
   beside the declared differences of §3.3, which are candidate causes and are not measured as causes in
   this round, and is not explained away; no Kev comparison (§9.3, §9.4) may describe any result of this
   round as aligned with, matching or replicating Kev.
   - Clearing §9.1 licenses only the sentence "clears the pre-registered K-align line". The words
     **aligned with**, **matches** or **replicates** Kev are admissible only if the two-seed mean lies
     within [min − 1.0, max + 1.0] points of the three reference stage-1 seeds on **both** suites, the
     same bound §14.4 uses. Otherwise the result is reported as "below the reference stage-1 range by
     X points on decision-v7 dev and Y on transfer-v4 dev".
4. **§7.1, §7.5, §7.6, §8.4: run order and scope.** Reason: §7 gives dependencies but no order, and
   §7.1 and §7.6 leave the ladder conditional. Resolution, each step starting only after the previous
   one has finished and been read on dev:
   1. K0 on `Qwen3.5-0.8B-Base` and `Qwen3.5-0.8B` with the admissible scorer, both tracks, all
      degenerate arms, and the item 1 identity check and erratum measurement.
   2. Wave 1, concurrent, one chip per run (§14.3), eight runs: K1 seeds 2 and 3, K2 seeds 2 and 3,
      K1-PT seeds 2 and 3, K1-QO seed 2, K1-FLA seed 2 (§14.4). K-align, K-floor, K1 against K2
      (§8.2, item 2) and the ladder kernel test (§14.4) are decided from this wave. Every trained arm
      is also scored with `input_mode = drop` (§5.2) and `blank` (§5.3) on both dev partitions, since
      §9.2's question-only comparator is the arm itself. Wave 1 is 8 single-chip trainings on a host
      with 8 chips (§11.1). Contention is resolved by the step order, not by reserving a chip: step 1's
      scoring completes before step 2 launches, and an arm's own scoring starts only on a chip freed by
      a finished training run. Three constraints are fixed here. (a) **No two runs of record share a
      chip**, and no scoring of record shares a chip with a training run of record, so the per-chip
      throughput and reserved-memory figures of §10.2 measure one run each. (b) The chip assignment and
      the concurrency per chip are written into the wave's directory **before it launches** and are not
      changed after any arm's dev number has been read. Sharing a chip between two runs of record is
      not admitted in round 1; it requires a new amendment committed before any shared run launches.
      The file's sha256 is recorded in every run's §7.7 record, and the watchdog compares each run's
      recorded chip against it. (c) The chip assignment of every run is recorded (§7.7, §10.2).
   3. K4 (§7.5), from the arm adopted after wave 1, at **0.8B only**.
   4. Ladder 2B, 4B, 9B (§7.6), **in scope for round 1**, each size preceded by its K0 (§7.1).
      - **§7.6 is fixed now.** The ladder trains with the adopted **LoRA** arm (K1 or K2), at 2B, 4B and
        9B, regardless of whether K4 is adopted at 0.8B. Full fine-tuning is not inherited by the
        ladder: the §14.3 single-chip trainer cannot hold the full-FT state above ~2B (9B needs roughly
        144 GB of weights, gradients, fp32 master weights and two Adam moments against 64 GB of HBM),
        and §14.4's kernel admissibility test is a LoRA test. K4,
        if adopted, is reported at 0.8B only and §9.3 K-ladder reads on the LoRA ladder. A multi-chip or
        full-FT ladder requires a new amendment written and committed before any K4 number is read.
      - If a size does not fit the §14.3 trainer at any micro-batch permitted by §7.6, that size is
        reported as "not run, memory" with the measured requirement, and the ladder stops at the last
        size that fits. K-ladder (§9.3) is then read over the sizes that ran, with the omission stated.
      - Unconstrained optimum and its discrimination counterpart (rule 2): a larger model may raise
        decision-v7 by memorizing more of the trained sources. The counterpart is transfer-v4, whose
        sources are never trained on (§2.2); §9.3 requires the non-decrease on **both** suites, so a
        decision-v7-only rise is not a K-ladder pass.
   5. `FINAL.json` and the single test read per size (§8.4). `FINAL.json` for a size is written and
      committed when that size's selection ends, and is not re-opened by a later size's result.

   K3 is not in this order (item 6). The round-1 adoption chain is K1 → K2 → K4.
5. **§7.2 "Model of record", §8.4: LoRA arms.** Reason: folding the adapter into bf16 base weights
   perturbs scores. On the smoke run, decision-v7 dev, 200 items, the unmerged adapter gives 0.755
   under both tie rules with no ties, while the folded copy gives 0.760 under Kev's
   first-maximal-index rule and 0.750 under the R0 convention, with 2 exact top ties on `kev-boolq`.
   Folding's apparent +0.005 is entirely those two ties resolving to position 0; it is a tie artifact,
   not a gain (`r3_runs/eval200_rp_unmerged`, `eval200_rp_folded`). Resolution: the
   model of record of every LoRA run is the end-of-training adapter, **unmerged**, applied at scoring
   time to the §2.1 base checkpoint at its recorded revision. A folded copy may exist for inspection
   and never produces a reported number. For LoRA runs the §8.4 test lock and `TEST-READS.log` hash the
   adapter files (sha256 per file) together with the base checkpoint revision, and `FINAL.json` names
   both. Full fine-tuned models (K4) hash their weight files as §8.4 states. A test naming this clause
   asserts that every report of record for a LoRA arm has a non-null `model.adapter` in its header and
   no `model_path` under a `merged/` directory.
6. **Sequencing deviation; K3 deferred (§1.3, §2.6, §4.8, §7.4, §12.5).** Reason: this round trains
   before gate G1 and before the R2 harness exists, against `proposal/01-work-plan-four-directions.md`
   §6 items 4 and 5 (user ruling 2026-10-30, recorded in proposal R3). Resolution:
   - K1, K2, K4, the controls K1-PT, K1-QO and K1-FLA, and the ladder are **accuracy SFT** on Kev's
     data, not training aimed at consistency, and may run before G1. Declared: they inherit §3.4's
     option shuffling and NOTA pairs, which spend on registry rows 6, 5 and 16; that spend is kept only
     to replicate Kev's recipe (§4.8), and the trained flip rate stays a sanity metric.
     §4.8's treatment is extended to §4.6: for every arm trained under §3.4, the NOTA-selection rate,
     false-NOTA rate and both-sides-right are **sanity metrics**, labelled as such, never a row-5 or
     row-16 finding; only K0's NOTA numbers may be read as such. No trained-arm number of round 1 may be
     reported as an invariance, consistency, abstention or unknown-handling result, and no round-1
     number
     is evidence for or against G1 (WP-1.9, WP-2.6). The row-6/5/16 spend is a declared cost and is not
     progress on those rows.
   - K3 trains on renaming and definition-swap manipulations and **is** consistency-targeted. It is
     **deferred until G1 is decided**: it stays pre-registered as written in §7.4 and §2.4 and is not
     withdrawn, but it does not run in round 1 and produces no round-1 number.
   - Consequences: the §7.4 base choice (item 2) is still made in round 1, for later use; §12.5 is moot
     for round 1; no round-1 arm draws on Track T data, so §2.6's training exclusion is vacuous in round
     1 while τ is still fitted on the carve-out only; K3 re-enters after G1.
7. **§14.2: scorer admissibility numbers.** Reason: §14.2 admits a scorer only within "the measured
   bf16 batch-size floor", and that floor had not been measured when §14.2 was written. Resolution:

   `[FILLED BY ORCHESTRATOR: floor table]`

   **Resolved, 2026-10-30.** The table was generated and read
   (`r3_runs/scorer_r3/floor_table.md`, 03:26Z). Its verdict under the rule below is in §14.6 item 1:
   no bf16 batched scorer is admissible, including a null control that is mathematically the unpadded
   layout, so the rule below is **superseded by the fp32 bar of §14.6 item 3** and bf16 is no longer an
   admissible precision for a readout of record (§14.6 item 2). The rule below is kept as the record of
   what was required when the measurement was commissioned.

   The table gives, per suite, the fixed sample and its n, the admitted layout's replicate floor, the
   admitted scorer's difference from the unpadded layout, and the verdict under this rule,
   fixed before the table is filled: a scorer is admissible on a suite only if, on that suite's fixed
   sample, (i) the maximum absolute per-candidate score difference from the unpadded layout does not
   exceed the admitted layout's replicate floor — the maximum absolute per-candidate score difference
   between two runs of the admitted scorer on the same sample under two different batch compositions
   (the sample in two fixed orders), measured before the table is read — (ii) no question's argmax
   differs under either tie rule, and (iii) the sample headline accuracy of the admitted scorer equals
   the unpadded layout's under each tie rule. The sample and its n are fixed before the measurement is
   read. A scorer that fails is fixed; the bound is not relaxed, retroactively or otherwise (§14.4).
   No readout of record is produced before the table is filled.
8. **Header: status.** Reason: the header still said "Draft", but the file was committed at
   `387521b` (2026-10-30 00:44 +0800) before any scored run it covers. Resolution: the file is
   **frozen as of `387521b`**. Every later change is a numbered amendment in §14, §14.1 onward. This
   amendment's only edits outside §14 are in that header line and the sentence after it: the header's
   `2026-10-30 · Draft.` now reads `2026-10-30 · Frozen as of 387521b (2026-10-30 00:44 +0800).`, and
   "It becomes frozen when committed, and it must be committed" is put in the past tense, since it did.
   No other clause of §1–§13 is touched by this amendment.
9. **§13 ruling F2: "counts copied in later".** Checked against §2.4 and
   `r1_sft_data/symbol/manifest.json`: §2.4 carries the rebuilt counts (103,238 rows, per-source
   counts and shares, token counts, `train.jsonl` sha256 `7b1edec5…`), and the manifest's own
   verification records 0 `openjev-synth` rows with a `digits`-family augmentation and 0 `openjev-synth`
   T1 `digits` rows. F2 is **discharged**.
10. **§14.2 widened: the padding defect is not confined to candidates of unequal length.**
    *Superseded in part by §14.6 item 5: the padding diagnosis is withdrawn; the consequences stand on
    the corrected ground. The RoPE statement below is corrected there — a uniform position offset
    leaves relative positions unchanged.*
    `r0_code/scorer.py:342-383` flattens every candidate of every item into one list, sorts it globally
    by descending length, and cuts batches at `token_budget // longest`. A row's pad count is therefore
    set by the longest row in its batch, usually from another question, and one question's candidates
    can
    land in different batches of different widths — so **equal-length candidates are left-padded too, by
    differing amounts**. The forward pass supplies no `position_ids`, so left padding also shifts every
    real token's RoPE position by the pad count. §14.2's admissibility requirement is unchanged and
    already covers this; its diagnosis is widened to: *every* row scored by `HFScorer` at
    `token_budget > 1` is perturbed by an amount that depends on its batch's composition. The §14.2
    fixed-sample measurement covers both cases: unequal-length candidates within a question, and
    equal-length candidates split across batches.
    **Consequence for R0.** R0 §12.1 ground 1 — "on 73.97% of rows every candidate has the same token
    count, so the missing normalization adds an identical constant to every candidate" — does not hold
    under this scorer, and ground 3's measured length effect (+0.154 nats per token) is the same
    magnitude as the measured padding shift (0.157 nats). R0 §12.1's and R0-RES §7.3's "do not retest
    it"
    is **suspended** until the erratum reports; the length confound is retested on the admissible scorer
    as part of it.
11. **§11.1's trainer line.** Reason: §11.1 still reads "verl FSDP SFT", which §14.3 superseded.
    Resolution: §11.1's trainer clause is read as §14.3's single-chip PyTorch + peft trainer. The host,
    chip count, image and `python3 -P` requirement of §11.1 are unchanged.

14.6 **Amendment 6, precision of record, scorer admissibility bar, duplicate candidates, and the
status of §14.2, 2026-10-30.** Made after the §14.5 item 7 table (`r3_runs/scorer_r3/floor_table.md`,
generated 03:26Z) was read and before any readout of record exists.
1. **Verdict under §14.5 item 7 as written.** No bf16 batched scorer is admissible on any suite: `rp`
   and `fast` fail in every measured cell, and the null control `eq` (the unpadded layout batched only
   with equal-length rows, no padding anywhere) fails 10 of 10 cells (i: 8, ii: 10, iii: 10). `exact`
   vs `exact2` is bit-identical in 9 of 9 cells, so the variation is batch composition, not
   nondeterminism. Criterion (i) compares one draw of bf16 composition noise with another and is
   non-diagnostic in bf16. The bound is not relaxed; bf16 is removed from the admissible precisions for
   readouts of record.
2. **Precision of record.** Every readout of record, Track K and Track T, every arm including K0, the
   degenerate baselines, the R0 re-score of §14.5 item 1 and the erratum, is scored in float32 with
   HF32 matmul disabled. Each readout's header records `dtype`, `hf32` (must be false, asserted by a
   test naming this clause), layout, token budget and batch composition. bf16 may be used for smoke
   runs and never for a reported number. Training precision is unchanged. The change is not a cost
   concession: fp32 batched scoring costs 0.133 s per item against 6.12 s per item for the bf16 exact
   layout the §14.5 item 7 rule required, about 46x faster (`r3_runs/scorer_r3/an_fp32.json`), so the
   correct choice is also the cheaper one. This supersedes §11.1's dtype only; its host, chip count,
   image and `python3 -P` requirement are unchanged.
3. **Admissibility bar, fixed before the fp32 runs it needs exist.** τ_s = 1e-3 nats (the `NEAR`
   constant of `r3_code/floor_table.py:34`). On each suite's fixed sample (the §14.5 item 7 samples,
   with the three T1 `r0model` samples re-fixed at n = 128 with per-tag sidecars and their key sha1
   recorded before scoring):
   - (a) **null gate**: max |Δ| per candidate over all pairs among fp32 `exact`, `eq_a`, `eq_b`, `eq_c`
     ≤ τ_s; if this fails, the bar is wrong and the round stops; it is not raised.
   - (b) **(i′)** the candidate scorer's max |Δ| per candidate vs fp32 `exact`, under two compositions
     a and b, ≤ τ_s.
   - (c) **(ii′)** zero argmax disagreements under either tie rule on items whose `exact` top-2 gap
     exceeds τ_s; items at or below τ_s are counted and listed.
   - (d) **(iii′)** sample headline accuracy equal under both tie rules, or differing only on the
     listed items.

   Both `rp` and `fast` are candidates; the first that passes on every suite is the scorer of record
   for the round, the other is retained as a check. Declared as already seen: one fp32 composition per
   mode on n = 32 to 64 (`data_fp32/`), max |Δ| vs `exact` 2.4e-5 to 7.1e-5 for `eq_a`, `rp_a`,
   `fast_a` and `r0`, zero disagreements; HF32-on fp32 differs from HF32-off by 3.80e-3 to 5.26e-3
   per mode (`probe2_float32.json` against `probe2_nohf32_float32.json`, raw max |Δ| over 251
   candidates: `exact` 3.80e-3, `eqlen` 4.54e-3, `r0` 4.44e-3, `rightpad` 4.65e-3, `fast` 5.26e-3;
   the ruling quoted 3.1e-3 to 3.8e-3, corrected here after recomputation). The verdict is the same
   for any τ_s in [1e-4, 3e-3], and every mode's HF32 error exceeds the top of that interval, which
   is the only use this clause makes of the figure.
4. **Duplicate candidates.** Every tied maximum in the `exact` layout on the fixed samples is between
   candidates of equal token length with bit-identical scores, i.e. identical token sequences. The
   readout definition is fixed: candidates of one question with identical token sequences receive one
   forward pass and share the score bit for bit in every layout. The count of such questions is
   reported per suite beside the tie count of §4.2. The engineer confirms identity at string level
   before this is relied on.
5. **Status of §14.2 and §14.5 item 10.** The padding diagnosis is withdrawn: in fp32 with HF32 off,
   left-padded `r0` vs `exact` is ≤ 8e-5 nats with zero argmax changes on five suites; in bf16 its
   difference from `exact` (0.74 nats, decision-v7) equals that of the unpadded controls (0.74, 0.81).
   The 0.157-nats figure was one bf16 composition draw. Item 10's RoPE statement is corrected: a
   uniform position offset leaves relative positions unchanged. §14.2's three consequences stand on
   the corrected ground (bf16 composition noise of up to 2.6 sample-accuracy points against 1.0-point
   bars): pre-amendment K0 numbers are void; published R0 readouts are not the R0 side of any
   comparison; §14.5 item 1 (i) stands as the pinned identity check. Item 1 (ii) now reports (padded
   bf16 rerun − fp32) and (unpadded bf16 − fp32) metric by metric; the erratum's headline sentence is
   "the padding claim does not survive a noise floor". The R0 §12.1 retest of item 10 stays.
6. **Reference precision.** §14.5 item 3's band is unchanged. Every K-align sentence states that the
   reference stage-1 numbers' measurement precision is unknown and that this round's side is fp32.
7. **Harness fixes required before scoring**: `measure_floor.py` writes `rows.json`/`enc_info.json`
   per tag, and every score file carries per-item keys and the sample sha1.

14.7 **Amendment 7, a third gated-delta-rule kernel (`gdn_fast_ref`), K2 prompt sharing and its
dropout mask, and a backward-pass nondeterminism defect in the trainer, 2026-10-30.** Made before any
arm of wave 1 was trained and before any readout of record exists.
1. **§14.4's scope is narrowed, and the gap it leaves is closed.** §11.3, §14.1 and §14.4 are read as
   governing one specific implementation: the fused gated-delta-rule / FLA kernel under
   `/mnt/cephfs/xingchao/docker/verl_v030_20261029/speedup/`. §14.4's verdict ((b′) and (c) failed;
   the ladder route through K1-FLA) applies to that kernel and to no other. §14.4's sentence "every
   round-1 arm at 0.8B therefore trains on the reference kernel" is read as "…trains on a kernel
   admitted under §11.3 as amended", and the only kernels so admitted are the in-tree reference
   (`transformers.models.qwen3_5.modeling_qwen3_5.torch_chunk_gated_delta_rule`) and any kernel that
   passes item 2 below. A third implementation does not inherit the word "reference" by being
   mathematically the same function; it is admitted by measurement or not at all.
2. **`gdn_fast_ref` (`r3_code/gdn_fast_ref.py`, `--gdn-impl fast_ref`): its gate, fixed before the
   runs it needs exist.** The reference kernel's math re-implemented with a block-doubling matrix
   inverse and an analytic backward in place of the 63-iteration in-place inverse. Motivation is
   launch-bound execution, not precision: ~69,000 device tasks per step at 21% device-busy wall time,
   corroborated by 9–22% AICore on host 175 under three concurrent jobs. It is admitted for wave 1 and
   for the ladder only after all of (G1)–(G4) pass, on fixed batches of real decision-v7 train rows,
   with every number and the sha256 of `r3_code/train_r3.py`, `gdn_fast_ref.py`, `test_gdn_e2e.py` and
   `test_gdn_fast_ref.py` written into `r3_runs/eff/gate_fast_ref/` and committed before any arm of
   wave 1 launches. All four are measured on the trainer **after** the item 4 fix.
   - **(G1) Same function in fp32, layer and model level.** Layer level, already measured and recorded
     here as the declared prior: fast-vs-ref max relative L2 2.63e-07 to 3.51e-07 over shapes
     (B2,T64), (B3,T100), (B2,T700), (B1,T1024), (B4,T257), with and without an initial state; against
     an fp64 gold both kernels agree to ~1e-6; worst over the 18 real layers 3.1e-05 forward and
     8.3e-05 gradient (`r3_runs/eff/final_test_gdn/run.log`). Required in addition, at model level with
     the whole model in fp32 and no autocast: logits relative L2 between the two kernels ≤ 1e-4, and
     every trainable tensor's gradient cosine ≥ 0.9999. This is §14.1 (a′) applied unchanged.
   - **(G2) §14.1 (b′) per tensor, at model level.** With e_X(t) the relative L2 of LoRA tensor t's
     gradient from kernel X in bf16 against the whole-model fp32 gold on the same step:
     e_fast(t) ≤ 1.5 · e_ref(t) + 1e-3 for at least 99% of the 372 tensors, and no tensor has
     e_fast(t) > 3 · e_ref(t) + 1e-3. This is the identical bound the FLA kernel failed at 96.6%
     (§14.4), and it is the number that decides this kernel. *Superseded by §14.8 item 1: the bound
     is identical, the population is not — the FLA kernel's 96.6% is over 320 full-model trainable
     tensors, every one of the eleven tensors it failed on is frozen under LoRA and cannot appear in
     the 372, and the replacement sentence, the gating population and the consequence of a split
     verdict are fixed there.* The stacked figures already recorded (e(F,G) 4.02e-02 against
     e(R,G) 3.79e-02, ratio 1.06) do not discharge it.
   - **(G3) A same-config replicate floor, which did not exist when this kernel was proposed.** Two
     invocations of the reference kernel with identical micro-batch, seed, data and chunk plan: report
     d(R,R′) over the stacked LoRA gradient and |loss_R − loss_R′| per step. This replicate floor, and
     not re-batching, is the floor of record for every bf16 statement about this kernel. The floor used
     when the kernel was proposed — d(R2,R) = 3.77e-02 / 3.78e-02 with R2 at one row per chunk
     (`r3_runs/eff/gdn_e2e2`, `final_test_gdn`) — is **void as a floor** under item 4: one row per
     chunk is the habitat of the defect found there, measured at 1.8e-02 relative L2 against the
     corrected path, so that number mixes re-batching with the defect. d(R3,R) is also not a second
     composition: R3 has R's chunk count and padding and its median per-tensor difference is 0.0e+00.
   - **(G4) Trajectory, 100 steps, judged on the trend and not only the mean.** Both kernels run
     100 optimizer steps with the same seed, data and chunk plan. The (G3) **trajectory**
     replicate floor is measured and written into `gate_fast_ref/` before (G4) is run, so (G4)'s
     bar is fixed before its own data exists. Because this item uses "(G3)" for two measurements,
     (G4)'s floor is named here as the trajectory replicate — the mean over the same 100 steps of
     |loss_R − loss_R′| (`r3_code/gate_trajectory.py`) — and not the model-level per-step
     replicate (§14.8 item 3). The per-step |Δloss| series is reported in full. Pass requires
     **both**: mean |Δloss| ≤ max(the (G3) floor, 0.5 · |loss_R − loss_G| as measured on the same
     rows, i.e. 1.14e-02 against the recorded |loss_R − loss_G| = 2.28e-02); and the mean of the
     last 20 steps ≤ 3 × the mean of the first 20 steps. The second clause exists because the
     four-step evidence offered (1.5e-3, 1.4e-3, 4.4e-3, 1.2e-2, mean 4.7e-3) grows monotonically
     by 8× while its proposed floor series (7.5e-3, 2.5e-3, 8.8e-3, 9.7e-4) does not, so a
     four-step mean cannot distinguish bf16 noise from divergence. §14.1 (c) is **not** relaxed
     retroactively and remains as written for the FLA kernel (§14.4); (G4) is a different test,
     pre-registered for a different kernel before it runs, and its floor is same-config rather
     than a second draw of composition noise, which is why §14.6 item 1's objection to criterion
     (i) does not apply to it.
   - **If any of (G1)–(G4) fails, wave 1 and the ladder train on the reference kernel**, at the
     measured cost of about 2.8 h per K1 run at three processes per chip and about 6.8 h per K2-shared
     run, roughly a day for the wave. That consequence is recorded here so the gate is not reopened
     under schedule pressure after a result is seen.
   - **Ladder.** Every `fast_ref` number is at 0.8B over 18 layers. Before each of 2B, 4B and 9B trains
     with `fast_ref`, (G1) is repeated at that size on real rows of that size and recorded; a size that
     fails trains on the reference kernel. (G2)–(G4) are not repeated per size.
   - **No `K1-fast_ref` arm is created.** §14.4's downstream route existed because the FLA kernel had
     failed the numeric gate and a coarse accuracy check was the only remaining instrument. A ±1.0-point
     one-seed accuracy band cannot resolve what this gate resolves in fp32, and a ninth run is not
     spent on it.
   - **Discrimination counterpart (rule 2).** The unconstrained optimum of a speedup gate is a kernel
     that is bit-identical and therefore passes trivially; the counterpart is a wrong fast kernel that
     must fail. Recorded: the first attempt, a Neumann-product inverse, fails the 1e-3 forward check on
     3 of the first 8 real layers, and its NaN-loss benchmarks are excluded in
     `r3_runs/eff/INVALID_nan_square_inverse/` and cited in no number of this round.
   - **Speed figures carry the host's own noise.** `r3_runs/eff/bench_record.json`'s note records
     ~10–15% repeat-to-repeat variation from other tenants on the same chips and CPUs, so every
     throughput and wall-clock estimate in this item is ±15%. `mk_bench_record.py` adds `gdn_impl`,
     `k2_impl` and the trainer sha256 as fields, since §7.7 requires a kernel record per run and the
     implementation is currently recoverable only by parsing `train_command`.
3. **§7.3: K2 trains with the prompt forwarded once, and with the prompt-side LoRA-dropout mask shared
   across a question's options.** `--k2-impl shared` (`r3_code/k2_shared.py`) forwards each question's
   prompt once and continues every option from the cached attention keys and values, convolution state
   and recurrent state, with gradients through both passes. Admitted, for `--arm k2`, as the K2
   configuration of record.
   - **Equality, measured, dropout off, fp32, real decision-v7 rows of 2 to 78 options**: per-option s
     worst |s_rows − s_shared| 4.2e-05 nats against §7.3's 1e-3; step loss |Δ| ≤ 2.0e-06; LoRA
     gradients over 372 tensors worst relative L2 1.7e-05, worst cosine 0.9999998; a left-padded batch
     of 8 ragged prompts equals each question scored alone to 2.7e-05; discrimination counterpart
     (options continued from another question's state) differs by 35.57 nats
     (`r3_runs/eff/final_test_k2_shared/run.log`). §7.3's independent-scorer equality holds at 4.58e-05
     nats on 2 to 77 options (`final_test_train_r3d`). §7.3's 1e-3 bar is unchanged and is met.
   - **Declared deviation from §7.2's regularizer, which equality does not cover.** The two forms are
     equal with dropout off. With dropout 0.05 they are different regularizers: the shared form draws
     one prompt-side LoRA-dropout mask per question, the row form draws one per option. The shared form
     is chosen, and not for speed: K1 contributes one row per question (§3.4 siblings being their own
     rows) and therefore already draws one prompt mask per question, so the shared form is the one
     whose dropout granularity matches K1's, and §8.2's K1-against-K2 decision then compares objectives
     rather than regularizers. The row form would introduce that confound. Because the K2 loss is a
     softmax across a question's options, a shared mask partly cancels inside the softmax, so the row
     form is also the higher-variance one. Dropout 0.05 is unchanged; dropout is **not** turned off for
     K2, which would confound objective with regularization in the one comparison this wave exists to
     make.
   - **The row form is not a fallback.** It is 91 s per step, about 79 h per run, and is not runnable in
     round 1 on any kernel. If K2 runs in wave 1, the prompt is forwarded once.
   - **Semantics pinned by test, not by implication.** A test naming this clause asserts that the
     prompt-side dropout mask is identical across a question's options within a step and differs
     between steps (`train_r3.py` seeds dropout per step as seed·1000003 + step), and is recorded in
     every K2 run directory under §7.7. Every K2 report of record states `k2_impl` and the realized
     dropout.
   - **The weakest measured cell is the production one and is re-measured before launch.** In bf16 with
     `fast_ref`, the shared form's RMS per-question loss error against the fp32 gold is 0.0746 against
     the row form's 0.0642 with a re-batching floor of 0.0640 — the floor does not cover the difference,
     and the cell passes only on the test's `1.5 · e_rows + 0.005` slack; under the reference kernel the
     same cell is clean (0.0585 against 0.0586, floor 0.0887) (`final_test_k2_shared/run.log`). That
     cell is repeated with the item 2 (G3) same-config replicate floor in place of the re-batching
     floor, and recorded, before K2 launches.
4. **A backward-pass nondeterminism defect in `r3_code/train_r3.py`, found before any run of record.**
   With a plain 2D attention mask, transformers drops the mask when a chunk has no padding — a single
   row, or rows of equal length — and sdpa takes the causal flash path, whose backward is not bitwise
   reproducible on this stack: repeat-to-repeat LoRA-gradient differences of about 2% relative L2, and
   1.8e-02 relative L2 against the corrected path (`r3_runs/eff/diag_det`, `diag_det2`, `diag_det3`).
   `row_logprob_sums` now always builds an explicit 4D mask, at no measured speed cost.
   - **Scope, stated precisely: the defect is in the backward pass.** Scoring performs no backward, so
     no readout of record is affected, and §14.2, §14.5 item 7 and §14.6 stand unchanged. §14.6 item 1's
     finding that `exact` and `exact2` are bit-identical in 9 of 9 cells is direct evidence on the
     point: `exact` (one row per candidate) and `eq` (equal-length rows, no padding) are exactly this
     defect's habitat on the forward path and are reproducible there, which is why §14.6's "the
     variation is batch composition, not nondeterminism" survives. That reason is recorded here because
     it is now load-bearing.
   - **No determinism claim about a run of record is corrected, because no run of record exists yet.**
     This is not a precedent that nondeterministic gradients are tolerable; it is the reason the finding
     is cheap.
   - **§14.3's "exact resume" is restated as measured, post-fix, and not as "bitwise".** Across five
     post-fix repeats the final adapter is identical at 0.00e+00 in all five; the logged per-step loss
     is 0.00e+00 in three and 5.96e-08 / 2.98e-08 on steps 5 and 6 in two, reproducibly the same values
     (`r3_runs/eff/res_fixed_a`, `res_fixed_b`, `final_test_train_r3d`). The admissible claim is
     "bit-identical in the adapter; the logged loss agrees to 6e-08".
   - **The fix is verified for only half of its stated scope, and that is closed before launch.**
     `diag_determinism.py` probes the corrected path for one long row and one short row (both bitwise
     reproducible) but its only "2 identical-length rows" probe calls the uncorrected path, where it is
     nondeterministic at 2.0e+00. A probe of two identical-length rows **through the corrected path** is
     added and must come out bitwise reproducible before wave 1 launches. Equal-length chunks are the
     common case for a question's options, so this is the half that matters for K2.
   - **Every pre-fix number used as a floor is void as a floor**, by name: the d(R2,R) = 3.77e-02 and
     3.78e-02 figures of `gdn_e2e2` and `final_test_gdn` (item 2 (G3)). Pre-fix numbers used as speed
     measurements stand.
   - **Smoke-run note, no correction.** §14.5 item 5's adapter was trained before this fix and is not a
     run of record. Its conclusion is unaffected: 0.755 / 0.760 / 0.750 compares one adapter under two
     folding treatments, so it does not depend on how that adapter was trained.

**Launch checklist (§14.7).** All of the following are committed before `docker run -d` on any wave-1
arm:
1. This amendment (§14.7) and §14.8, which corrects (G2) and adds the (G3) obligation to both
   branches.
2. `r3_runs/eff/gate_fast_ref/` holding (G1)–(G4) with the four sha256s of item 2, or the recorded
   decision to train on the reference kernel. That recorded decision carries the failing numbers and
   the same four sha256s, names which of the four gates ran, and states that it follows from a gate
   verdict and not from a gate crash (§14.8 item 3). On either branch `gate_fast_ref/` holds (G3),
   both the model-level and the trajectory replicate (§14.8 item 4).
3. The corrected equal-length determinism probe (item 4), green.
4. The K2 dropout-mask-semantics test (item 3), green.
5. The production bf16 K2 cell — shared K2 on whichever kernel item 2 leaves of record — re-measured
   against the (G3) floor (item 3), recorded. The reference + shared cell is not already discharged:
   its 0.0585 against 0.0586 figures rest on the re-batching floor of 0.0887 that item 2 (G3)
   declares void as a floor (§14.8 item 3).
6. `r3_runs/eff/bench_record.json` carrying `gdn_impl`, `k2_impl` and the trainer sha256.
7. The §14.5 item 4 step 2 chip-assignment file, written with its sha256 recorded.

14.8 **Amendment 8, (G2)'s gating population, the three §14.7 edits ratified with their
conditions, (G3) on every branch, and two corrections to the orchestrator's own record,
2026-10-30.** Made before any arm of wave 1 was trained and before any readout of record exists.
**Stated precisely, because the ordering is the point of this item:** (G2)'s correction is derived
from the FLA kernel's own failure evidence (the eleven frozen tensors at `speedup/README.md:51`)
and from no `fast_ref` number. It is *not* made before every gate number existed:
`gate_fast_ref/model_level/` already carried `DONE` at 2026-10-30T04:53:50Z, and the engineer that
produced those numbers has necessarily seen them. What is claimed is narrower and checkable — the
bar was moved for a reason that does not mention them, and the orchestrator had read none of them
when the ruling was requested or when this amendment was written. A reader who wants to test that
should compare the ruling's argument against the gate output and say so if the two coincide
suspiciously. Source: the review ruling `reviews/R3-CHIP-PRIORITY-RULING-fable-20261030.md` (Fable
5.1, CLAUDE.md §2); each item names the ruling section it comes from. The §14.7 and §14.4 clauses
this amendment corrects stay where they are and carry a pointer here (§14.2 and §14.4's own
convention).
1. **(G2)'s population: the 372 LoRA tensors gate; the 320 full-trainable tensors are measured and
   reported but do not gate (ruling §§4.1–4.3).** §14.7 item 2 (G2) applies the §14.1 (b′) bound to
   "at least 99% of the 372 tensors" and calls it "the identical bound the FLA kernel failed at
   96.6%". The bound is identical; the population is not. 372 is the LoRA tensor count, asserted by
   `r3_code/gate_model_level.py` on the LoRA-wrapped model's trainable list, while §14.4's 96.6% is
   309 of 320 **full-model trainable** parameters, built from `named_parameters()` on a plain,
   non-LoRA model (`speedup/code/model_check.py`, `speedup/runs/modelcheck2/model_check.json`, whose
   `per_tensor` entries contain no `lora` key). The decisive finding is stronger than the mismatch:
   the eleven tensors the FLA kernel actually failed (b′) on are named at `speedup/README.md:51` —
   L0/L1/L9/L20/L21 `dt_bias`, `A_log`, `linear_attn.norm`, `post_attention_layernorm`, `in_proj_a` —
   and **every one of them is frozen under LoRA, so none can appear in the 372**. (G2) on the 372
   alone is therefore not a better-targeted version of the same instrument; it is blind to its
   predecessor's only failure mode, and the FLA kernel would have passed it. The ruled remedy,
   pre-registered here before the numbers are read:
   - The **372 LoRA tensors gate the decision**, because they are the only tensors any arm of this
     round updates: §14.5 item 4 step 4 fixes the ladder on LoRA, and embeddings and the LM head are
     frozen (§7.2). A full-model comparison would gate partly on tensors no arm updates.
   - The **320 full-model trainable tensors are measured and reported beside them, and do not gate.**
     They need no second run and no non-LoRA model build: `gate_model_level.py` already performs the
     bf16 and fp32-gold backwards it needs, so setting `requires_grad = True` on the base parameters
     in its `build()` and collecting their `.grad` alongside the LoRA ones yields both populations
     from the same backward. No optimizer touches them and no training behaviour changes. If that
     turns out not to be cheap, the 320 population is reported from a separate invocation before the
     verdict is written; it is not dropped.
   - **Only one population may gate.** Two populations under one bound with no pre-named decider is
     two chances to pass, chosen after the numbers are visible. That is the pattern §14.1, §14.4 and
     §14.6 were each written to prevent, and rule 3 bars it.
   - **The split verdict is pre-registered, before the data.** 372 pass with 320 fail **admits** the
     kernel — the gate is on what trains — and obliges §14.7, `gate_fast_ref/` and every E1 and
     wave-1 statement that rests on the kernel to name the split, as "admitted on the LoRA
     population; the full-trainable population fails at X%, as the FLA kernel did at 96.6%, on the
     same class of small-norm gate and normalization tensors". It is not a silent pass. If both fail,
     wave 1 and the ladder train on the reference kernel, per §14.7 item 2's existing clause.

   §14.7 item 2 (G2)'s sentence "This is the identical bound the FLA kernel failed at 96.6% (§14.4),
   and it is the number that decides this kernel" is replaced by:

   > This is the **identical bound** applied to a **different and deliberately narrower population**:
   > §14.4's (b′) ran over the 320 trainable tensors of the unadapted model
   > (`speedup/runs/modelcheck2/model_check.json`, `code/gate_bprime.py`), while (G2) runs over the
   > 372 LoRA tensors, which are the only tensors any arm of this round updates. The two are **not
   > interchangeable, and the difference is not in this kernel's favour to claim**: all eleven tensors
   > on which the FLA kernel failed (b′) — L0/L1/L9/L20/L21 `dt_bias`, `A_log`, `linear_attn.norm`,
   > `post_attention_layernorm`, `in_proj_a`, per `speedup/README.md` — are frozen under LoRA and do
   > not appear in the 372. A 372-tensor gate could not have failed the FLA kernel as (b′) failed it.
   > The LoRA population gates because it is what training updates; the 320-tensor full-trainable
   > population is measured in the same backward, recorded in `gate_fast_ref/`, and reported beside it
   > as a non-gating cross-check, with the consequence of a split verdict fixed here: 372 pass with
   > 320 fail admits the kernel and obliges every statement resting on it to name the split; both fail
   > sends wave 1 to the reference kernel.

   The correction is additive and restrictive: it keeps the bar, names the population, and removes a
   claim the evidence does not support. The same wording in `wiki/E1-gdn-fast-ref-gate.md` — lines
   36, 60-64 and 180, which carry the "identical … 96.6%" claim and the prediction that the kernel
   "fails exactly as the FLA kernel failed" — is corrected there as a dated note, not a silent edit,
   since that entry's hypothesis section was written before the run (CLAUDE.md §8).
2. **The 96.6% is verified, not unverifiable; §14.4 stands, with a citation added (ruling §4.4).**
   This item records an objection of the orchestrator's that was checked and withdrawn; it is not a
   change to the pre-registration. The figure is **stated** at `speedup/README.md:51` from
   `runs/modelcheck2` and **computed** by `speedup/code/gate_bprime.py`, which derives
   `frac_within_1.5x_plus_1e-3` from the per-tensor errors rather than storing it, which is why
   grepping the JSON for the figure finds nothing; it recomputes as 309/320 = 0.9656 from
   `modelcheck2/model_check.json`. The orchestrator's search found nothing because it looked in
   `modelcheck3-fp32in/`, which is the `NGA_GDN_FP32=1` variant and gives 311/320 = 97.2% on a
   different failing set. **§14.4's verdict is not reopened**: the FLA kernel fails (b′) at both
   figures, both below the 99% bar, and its (c) failure (mean |Δloss| 0.0281, last-50 −6.65%) is
   independent of either. What §14.4 lacked was the citation, which is inserted there additively
   without touching the verdict.
3. **The three edits made to §14.7 after it was first drafted are ratified, with the conditions the
   ruling attaches (ruling §5).** None changes the amendment's substance; each repairs an
   unsatisfiable or under-specified clause, and each restricts rather than relaxes.
   - **Checklist item 2's "or the recorded decision to train on the reference kernel" — stands.** It
     names the fallback §14.7 item 2 had already chosen; a checklist satisfiable only by a passing
     gate would contradict that branch and, on a failure, leave wave 1 permanently unlaunchable or
     create pressure to reopen the gate, which is the outcome item 2 was written to prevent. Two
     conditions on how that record is written, normative here. (a) It records the failing numbers and
     the same four sha256s a passing gate would record, so the cheap path out of the gate is not to
     fail it quietly. (b) **It distinguishes "the gate ran and returned a verdict" from "the gate did
     not complete".** A `FAILED` marker under `gate_fast_ref/` is not by itself a gate result, and a
     reader may not treat one as triggering the reference-kernel fallback: that would launch wave 1
     with the measurement silently never taken. The live instance:
     `r3_runs/eff/gate_fast_ref/model_level/FAILED` recorded `rc=1 utc=2026-10-30T04:41:39Z` with an
     `EL0005 Resource_Busy … rtGetDeviceCount execution failed` log tail — an infrastructure fault at
     process start on a chip that was not free, **not a (G1) result**, and not admissible as one. The
     recorded decision states which of the four gates ran, their numbers, and that it follows from a
     verdict rather than from a crash.
   - **Checklist item 5's broadening to "whichever kernel item 2 leaves of record" — stands.** §14.7
     item 3's last bullet states the purpose it now tracks: the weakest measured cell is the
     production one. The original wording hardcoded `fast_ref`, which is the production kernel only
     on the branch where the gate passes; on the failure branch the production cell is reference +
     shared K2, and the original text would have left the cell that actually trains unmeasured while
     requiring a measurement of a cell nothing uses. The edit is not an exemption: the reference +
     shared K2 cell is **not** already discharged, because its 0.0585 against 0.0586 figures used the
     re-batching floor of 0.0887 (`final_test_k2_shared/run.log`) that §14.7 item 2 (G3) declares void
     as a floor. On either branch item 5 demands a measurement that does not yet exist, against the
     same-config replicate floor.
   - **The (G4) sequencing clause — stands, with the replicate named.** The bar `max(the (G3) floor,
     1.14e-02)` was already fixed in value by §14.7; the edit fixes **when** the (G3) term is
     measured, closing a reading in which the floor is computed after the fast kernel's trajectory is
     in hand, and `r3_code/gate_trajectory.py` already implements exactly that. Because §14.7 uses
     "(G3)" for two measurements — the model-level per-step replicate in `gate_model_level.py` and the
     100-step trajectory replicate in `gate_trajectory.py` — the naming fix is applied in §14.7 in
     place: (G4)'s floor is the **trajectory** replicate. A naming fix, not a change of bar.
4. **(G3) is measured on every branch, including the reference-kernel branch (ruling §5.4).**
   Checklist items 2 and 5 are each right and their conjunction leaves one unsatisfiable combination:
   item 5 requires the production K2 cell re-measured against the (G3) floor, and (G3) is a property
   of the reference kernel alone, so it exists on both branches only provided the gate ran. On the
   branch item 2 now admits — where the gate did **not** complete — there is no (G3) floor at all and
   item 5 cannot be satisfied on any kernel. Closed by pre-registering, before launch: **(G3), both
   the model-level and the trajectory replicate, is measured and recorded in
   `r3_runs/eff/gate_fast_ref/` on every branch, including the branch where wave 1 trains on the
   reference kernel.** It costs two reference-kernel invocations plus a 100-step reference pair, it
   needs no fast kernel, and checklist item 5 and §14.7 item 3's last bullet both depend on it. It is
   committed before `docker run -d` on any wave-1 arm.
5. **Resume granularity of the §14.5 item 1 (i) identity run: readout-file, not item (ruling §1 and
   §6 item 7).** §11.2's "resumable at step (training) or item (scoring) granularity" does not
   describe `r3_runs/harness_identity/`; §14.5 item 1 states no granularity for it, so §11.2 is the
   only clause that implies one, and it carries a pointer here. That run is resumable at
   **readout-file** granularity, deliberately: `PINS.json`'s `resume_hazard` records that
   `run_baseline.score_file` batches the items not yet written in chunks of `--chunk`, so resuming a
   half-written file changes the batch composition — and therefore the pad counts — of its remaining
   items; `r3_code/harness_identity_run.sh` therefore runs `drop-partial` first on every shard
   attempt, deleting incomplete readout files and redoing them from their first item, while complete
   files are skipped by key. Item-level resume is precisely the hazard the run was built to avoid, and
   acting on the orchestrator's "resumable at item granularity" description by resuming a file in
   place would have damaged the pin in the one way an interruption can. For that run, resuming a
   partial readout file in place is barred, and a relaunch uses `drop-partial` as written with the
   same image, code directory, shard count and `run_baseline.py` arguments.
6. **Chip priority between the pinned identity run and wave 1 (ruling §§2, 3 and 6 items 5–6).**
   Option (a), let `r3_runs/harness_identity` finish, is adopted, and nothing is stopped: §14.5
   item 4 puts the item 1 identity check in step 1 and wave 1 in step 2 and resolves contention "by
   the step order, not by reserving a chip", so the step order already decides it. The run's expected
   `DONE` is about 09:00Z, ±15%, about 4.3 h, not the 13 h the orchestrator extrapolated: the run
   declares `uniform_cost: false` so the watchdog computes no ETA for it, the heavy `hf` rows are
   scored first, and 359,070 of its 601,980 rows are degenerate-scorer rows. Interruption does **not**
   damage the pin, because the pin is on the computation and not on the occasion: `PINS.json` declares
   physical chip identity and wall clock not-pinned, `drop-partial` restarts incomplete files from
   their first item so no file is ever scored across an interruption, and the three completed
   `T1 typed-decisions` files were byte-compared against R0's with every row identical, 18 hours
   later, on different chips, with four co-tenant containers on the host. Option (b), stop and resume,
   is therefore available on its merits under item 5's conditions, but not as a way to launch wave 1
   early, which would need an amendment to §14.5 item 4 step 1 that the reviewer would not ratify.
   **Option (c)** — one chip for the identity run, seven for wave 1 — is **rejected**: the shards
   would run in six waves of one, about 12 h, and seven chips cannot hold the registered eight-run
   wave without queuing an arm or sharing a chip, which §14.5 item 4 step 2 (a) bars. **Option (d)** —
   reduce the sample — is **rejected**: the (i) check is defined as reproducing
   `r0_baseline_rederived/report.json` over R0's exact shards, a subset cannot produce the report, and
   the item set is a pre-registered element that rule 3 bars changing after the run started.
