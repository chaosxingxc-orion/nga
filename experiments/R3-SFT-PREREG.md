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
  on Track T data. *The R0 side here is the re-score of §14.5 item 1, never the published report
  (§14.2); §14.11 items 3 and 4: that re-score does not yet exist, so this B-4 is not reported until
  it does.*

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

*Suspended in part by §14.11 item 4: (c)'s **gating cells** are defined by R0 §13.5 verdicts
recomputed on the §14.5 item 1 R0-configuration fp32 re-score, which does not yet exist, so until it
does (c) has no population and **no arm is adopted under this clause**. An arm may be reported as
clearing K-floor and as winning (a) and (b); it is not reported as adopted. The re-score's deadline
is before the first §8.2 adoption decision of round 1 and before `FINAL.json` is written for 0.8B.*

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
examples/s/chip), never an aggregate alone. *Extended by §14.11 item 12: a rate also carries the
**window** it was measured over and excludes warm-up, a figure from the first seconds of a unit is
**provisional** and may not be carried into a scheduling or sizing decision, and where a heartbeat
emits a windowed rate (`ex_s_chip_w20`) that is the figure of record. The clause's full text and the
occasion that prompted it are there.*

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

*Added by §14.10 item 15: a **counterfactual declaration** is a standing clause of this section. Any
amendment that changes a decision rule after a result the old rule bore on states what the new rule
would have decided about that result. The clause's full text, its two scope conditions and its one
caution are in §14.10 item 15.*

*Added by §14.11: four further standing clauses of this section, each carried in full in the item
named. (a) **A commissioned measurement is specified and priced before it is ratified** — instrument
and item set in already-defined terms, an order-of-magnitude chip-hour cost with the rate and window
it came from, and the decision it could change; if that decision is "none" the clause is
documentation, scheduled with a deadline and never placed in a step that gates another step
(§14.11 item 10). (b) **A guarantee cited in an acceptance is demonstrated in the path the accepted
artefact took** — the file and function, the path the artefact travelled, and whether sibling
consumers have an equivalent (§14.11 item 11). (c) **A guard that gates a number ships with a
demonstration that its test fails when the guard is removed** (§14.11 item 15), **and the mutation is
applied to the path that produces the number, a self-description being no test of behaviour**
(§14.11 item 21, which sharpens (c) after the reviewer applied it to a test it would have certified).
(d) **A guard is documented with what it does not stop** (§14.11 item 16). Clauses (b) and (d) are
one defect seen from its two ends, and are read together.*

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
- the relaunch command written into the run directory;
- *added by §14.10 item 11: a relaunch never deletes or overwrites a run directory that holds a
  terminal marker; it moves it aside to a sibling `<name>.crash-<utc>/` first. The clause's text,
  and the digest-retention clause it is committed and cited with (§14.10 item 14), are there.*

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

12.7 This round cannot claim that its `in_proj_a` LoRA adapters learned a well-conditioned signal
(added by §14.10 item 4). Under the reference kernel in bf16 the gate path carries the noisiest
gradient in the model: `e_ref` of 0.034 to 0.051 relative error against the fp32 gold on `in_proj_a`,
`A_log` and `dt_bias`. A 3–5% relative gradient error on the one gate-path adapter LoRA trains is a
plausible low-SNR channel. If a later round finds `in_proj_a` adapters contributing little, this
measurement is the first place to look, rather than a finding about gating's importance in the
architecture. §7.2's precision is unchanged and no experiment in this round is authorised by this.

12.8 While the R0 erratum and the R0-configuration fp32 re-score are outstanding, this round cannot
claim any comparison with R0's **published** numbers, in any direction and in any venue including a
wiki entry or a commit message, and cannot claim that **any arm is adopted** (added by §14.11
items 3 and 4). It also cannot state R0's own defect magnitude beyond the headline already published
in `R0-BASELINE-RESULTS.md`, cannot report §6.3's B-4 for K1-PT against R0, and cannot make any claim
about R0 §12.1's length effect, whose "do not retest it" stays suspended (§14.9 item 6). Unlike
§12.1–§12.7 this item is **conditional**: it lifts for each clause when the obligation that gates it
is discharged — the erratum before the first line of `TEST-READS.log`, the re-score before the first
§8.2 adoption decision — and until then every report of record of wave 1 states in one line that the
erratum is outstanding and which claims it therefore does not make. What wave 1 **may** claim
meanwhile is listed in §14.11 item 3.

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
an independent computation, right-padding invariance, resume) are recorded in each run
directory. *The word "exact" is struck from that test list by §14.10 item 6, which rewrites the
resume test as two assertions — bit-identity for a step-3-to-6 resume, the measured trajectory floor
for a step-40 resume — because as written the test passed for the wrong reason. §14.7 item 4's
numbers stand; their scope is withdrawn there.*

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
1. **§6.3, §6.5: the R0 side.** *Re-grounded by §14.9 item 6: the re-score requirement stands, on
   precision instead of padding; (i) below stays pinned as written but is no longer evidence about
   padding, and (ii)'s erratum headline gains a second sentence. Corrected further by §14.11, where
   the substance is: (ii)'s second difference is withdrawn and "unpadded bf16" is defined (item 1),
   (ii) leaves step 1 of item 4 below (item 2) and gains a deadline of its own (item 3), the R0 side
   defined here is named as the gate on the round's first §8.2 adoption decision and does not yet
   exist (item 4), and the (i) verdict is admissible only with `report_compared` true (item 7).*
   Reason: both clauses still name
   `r0_baseline_rederived/report.json` as the R0 comparison target, which §14.2 forbids as the R0
   side of any comparison. Resolution:
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
      degenerate arms, and the item 1 identity check and erratum measurement. *Replaced by §14.11
      item 2, which carries the new text: the item 1 (ii) **erratum measurement is not part of this
      step** and is owed under §14.11 item 3 instead; the item 1 (i) identity check keeps its place
      and its round-stopping power in full. This wording admitted no split by interpretation, which
      is why it is amended and not read.*
   2. Wave 1, concurrent, one chip per run (§14.3), eight runs: K1 seeds 2 and 3, K2 seeds 2 and 3,
      K1-PT seeds 2 and 3, K1-QO seed 2, K1-FLA seed 2 (§14.4). *The wave becomes **ten** runs under
      §14.10 items 8 and 13: the eight registered arms unchanged, plus the K1 seed 2 same-config
      replicates `w1_k1_s2_replicate_diffchip` (chip 3, the gating floor) and
      `w1_k1_s2_replicate_samechip` (chip 2, reported and non-gating). Neither is an arm and neither
      enters any arm's seed mean.* K-align, K-floor, K1 against K2
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
    leaves relative positions unchanged. §14.9 item 6 keeps the R0 §12.1 retest and corrects its
    stated reason: the length effect was measured in bf16, whose composition noise swamps it.*
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
4. **Duplicate candidates.** *Superseded in part by §14.9 item 1: the factual premise of the next
   sentence is false and is withdrawn in full — no duplicate candidate exists anywhere, and the
   bf16 tied maxima are between distinct options. The readout rule stands as a declared-vacuous
   safeguard and its reporting requirement is kept as a vacuity audit, extended by §14.9 item 5's
   near-tie census.* Every tied maximum in the `exact` layout on the fixed samples is between
   candidates of equal token length with bit-identical scores, i.e. identical token sequences. The
   readout definition is fixed: candidates of one question with identical token sequences receive
   one forward pass and share the score bit for bit in every layout. The count of such questions
   is reported per suite beside the tie count of §4.2. The engineer confirms identity at string
   level before this is relied on.
5. **Status of §14.2 and §14.5 item 10.** *Re-grounded by §14.9 item 6: the consequences below
   stand on precision rather than on padding, and the erratum headline this item fixes becomes two
   sentences. The second difference this item commissions is **withdrawn** by §14.11 item 1, which
   also fixes what "unpadded bf16" means wherever the phrase survives; the substance is there.* The
   padding diagnosis is withdrawn: in fp32 with HF32 off, left-padded `r0` vs
   `exact` is ≤ 8e-5 nats with zero argmax changes on five suites; in bf16 its
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
     verdict are fixed there. Decided by §14.10 item 1: (G2) **failed** on the declared verdict batch
     at 368 of 372 against the 369 required, the 320 population failed it too, and §14.8 item 1's
     pre-registered "both fail" branch is the one taken — wave 1 and the ladder train on the
     reference kernel. The pooled three-batch reading, which would have passed, is recorded and
     refused there, and §14.10 item 3 fixes a five-batch median rule for the next gate without
     applying it to this one.* The stacked figures already recorded (e(F,G) 4.02e-02 against
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
     under schedule pressure after a result is seen. *This clause has fired: §14.10 item 1 records
     (G2)'s failure and sends wave 1 and the ladder to the reference kernel. (G4) was not run and is
     not required. The realized cost is the one-chip-per-run figure of §14.10 item 8 — about 1.84 h
     per K1 run and 6.76 h for the wave, set by the two K2-shared runs — not the
     three-processes-per-chip estimate above.*
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
     "bit-identical in the adapter; the logged loss agrees to 6e-08". *Scope withdrawn by §14.10
     item 6: these numbers stand, but they were measured inside the five-to-ten-step window in which
     this trainer is bitwise reproducible, and the "6e-08" is itself that window's step-5 half-ULP
     event. The four claims this round may make, and the rewritten resume test, are there.*
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
arm. *Extended by §14.10 with items 8 and 9; the item-by-item status as of the gate verdict, which
leaves items 1, 7, 8 and 9 **open** and wave 1 **not cleared to launch**, is the table at the end of
§14.10. Extended again by §14.11 with item 10; the status as of amendment 11, which leaves items 1,
7, 8, 9 and 10 **open** and wave 1 **still not cleared to launch**, is the table at the end of
§14.11.*
1. This amendment (§14.7), §14.8, which corrects (G2) and adds the (G3) obligation to both
   branches, §14.10, which records the gate verdict and adds items 8 and 9 below, and §14.11, which
   releases the erratum from §14.5 item 4 step 1 and adds item 10 below.
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
7. The §14.5 item 4 step 2 chip-assignment file, written with its sha256 recorded. *It must now
   carry **ten** runs (§14.10 items 8 and 13) and lose its `DRAFT` status; items 7 and 9 are
   discharged together.*
8. *Added by §14.10 item 6:* §14.3's resume test rewritten as two assertions — bit-identity for a
   step-3-to-6 resume, and the §14.10 item 6 (iii) trajectory floor for a step-40 resume — and the
   trainer's full test suite re-run on a chip with its output recorded in the run directory.
9. *Added by §14.10 items 8 and 13:* the ninth and tenth runs, `w1_k1_s2_replicate_diffchip` on
   chip 3 and `w1_k1_s2_replicate_samechip` on chip 2, named in the item 7 assignment file before
   the wave launches, with the gating rule (only the different-chip floor gates) and the dev-readout
   sequence written there.
10. *Added by §14.11 items 17, 19 and 7:* the three checks that gate K0's numbers being read, as
    **one job with one marker file**, in this order — (a) §14.11 item 19's `rp_c32` and
    resume-offset composition cells, the control; (b) §14.11 item 17's sampled re-score with its
    **mandatory cross-model counterpart** that must fail the §14.6 item 3 bar, the sample and its
    sha1 written before the re-score; (c) §14.11 item 7's `report_compared` check on the (i)
    identity verdict. Run on a chip freed by K0 before wave 1 launches; minutes on one chip. K0's
    post-hoc `manifests/` is written with (b), carrying in the file the sentence that it attests the
    files as they stood when it was written and not their origin.

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
     wave 1 and the ladder train on the reference kernel, per §14.7 item 2's existing clause. *The
     branch taken, recorded by §14.10 item 1: **both populations failed the declared verdict batch**
     — 368 of 372 against 369, and 315 of 320 against 317 — so this is the "both fail" branch and not
     the contestable split verdict. Wave 1 and the ladder train on the reference kernel.*

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
     with the measurement silently never taken. *The sentence beginning "The live instance:" is
     replaced by §14.10 item 10, which settles the error string's provenance from six surviving logs
     of this round plus `CHIP-ALLOCATION.json` rather than from anyone's testimony, records that
     `aclInit` 507899 and `Resource_Busy(EL0005)` are two lines of one CANN error block and not two
     accounts, and corrects two attributions (the 370 MB figure is the reviewer's and is
     uncorroborated; `_watchdog/digest.json` is rolling and cannot be cited after the fact). The
     clause's function is unaffected. The superseded sentence is kept below.* The live instance:
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

14.9 **Amendment 9, the withdrawal of amendment 6 item 4, the verified tie mechanism, the scorer
of record, what the fp32 verdict table establishes, and the re-grounding of the R0 re-score,
2026-10-30.** Made after the fp32 verdict table (`r3_runs/scorer_r3/fp32/fp32_verdict.md`, 05:03Z)
and the string- and token-level tie audits (`tie_audit_bf16.md`, `tie_audit_fp32.md`, 05:04Z) were
read and verified independently by the reviewer, and before any readout of record exists. Source:
the review ruling `reviews/R3-SCORER-VERDICT-RULING-fable-20261030.md` (Fable 5.1, CLAUDE.md §2),
whose §6 carries this text; §14.8 is a different amendment, from a different ruling.
1. **§14.6 item 4 is withdrawn as to fact and kept as to rule.** Item 4's first sentence — "every
   tied maximum in the `exact` layout on the fixed samples is between candidates of equal token
   length with bit-identical scores, i.e. identical token sequences" — is **false and is withdrawn
   in full**. It was written from the orchestrator's instruction to the engineer, not from a
   measurement, and the inference "equal score, therefore identical token sequence" was never
   valid. The measured facts replacing it:
   - **No duplicate candidate exists anywhere.** Questions with a repeated option string: 0 of
     1,264 decision-v7, 0 of 656 transfer-v4, 0 of 24,000 T1 typed-decisions, 0 of 30,720 T1
     openjev-synth, 0 of 2,216 T1 akhilaaa3 — in the fixed samples and in the whole source
     partitions (`tie_audit_bf16.md`, `tie_audit_fp32.md`; re-run independently by the reviewer).
     At token level, `n_dup_questions` = 0 in all 10 fp32 sidecars.
   - **The bf16 tied maxima are between distinct options with exactly equal scores**:
     ` no`/` yes`, ` reject`/` accept`, ` true`/` false`, ` c`/` d`, ` 3`/` 4`; 1 to 12 ties per
     cell over 11 audited cells, 0 of them duplicates. **fp32 has 0 ties in all 10 cells** over
     1,344 items.
   - The duplicate-candidate **readout rule** of item 4 — candidates of one question with
     identical token sequences receive one forward pass and share the score bit for bit in every
     layout, never applied to mode `r0` — **stands as written**, relabelled a **declared-vacuous
     safeguard**. It is measured to act on 0 questions in every suite, so it changes no number of
     this round; it is kept because its behaviour on any future duplicate is the correct one (the
     duplicate becomes an exact tie, resolved by §4.2's stored order, rather than by batch
     composition), because keeping it costs nothing, and because deleting implemented and tested
     harness code after a result has been seen, for no measured reason, is not something this
     round does (§14.4's precedent). Its unit test (`dedup_test_run2`, PASS) constructs the
     duplicate synthetically, since no real one exists; that is recorded as the reason the test is
     synthetic.
   - Item 4's reporting requirement is **kept and extended by item 5 below**: the per-suite count
     of questions with duplicate candidate token sequences stays as the audit that the safeguard
     remains vacuous. It must read 0; a non-zero value is a flag to be investigated before the
     readout is reported, not a routine number.
   - Item 4's last sentence, "the engineer confirms identity at string level before this is relied
     on", is **discharged**: the confirmation was performed and returned negative. The clause did
     its work and is replaced by these facts rather than deleted.
2. **The tie mechanism, verified, and the limit of the verification.** The explanation recorded
   for the bf16 ties is **bf16 logit quantisation**, not bf16 score quantisation: scores are fp32
   (`scorer_r3._token_logprobs` casts logits to float32 before `log_softmax`) and the bf16 `exact`
   files contain top-2 gaps as fine as 1.675e-4, far below bf16 resolution, so the scores are not
   on a bf16 grid. For a question whose candidates are single-token, all candidates are read off
   one prefix forward, the `logsumexp` term is common, and the top-2 score gap is exactly the
   difference of two bf16 logits, which does lie on the bf16 grid. Two checks, both run on data
   already on disk at no NPU cost, before this explanation was written down:
   - **Grid test**: of the single-token-candidate items with a nonzero top-2 gap, **888 of 926**
     have a gap that is an exact multiple of a power of two in bf16, against **0 of 719** in fp32.
   - **Composition fragility**: the bf16 `exact` ties are mostly not ties under the unpadded
     equal-length controls (`eq_a` 0 of 5, 0 of 6, 4 of 12, 0 of 2 in the cells with ties), which
     excludes a structural cause — an indexing or position defect that read one logit for two
     candidates would tie in every layout.
   **Limit, stated rather than smoothed over**: for multi-token candidates (31 bf16 ties of 674
   multi-token items) only the first-token term shares a `logsumexp`, and 269 of 643 nonzero gaps
   are on-grid. The mechanism is therefore recorded as **verified for single-token candidates and
   consistent with, but not individually verified for, multi-token candidates**; the
   composition-fragility evidence covers both. No further measurement is required, because the
   scorer of record is fp32, where the phenomenon does not occur. **fp32's 0 ties is not a
   by-construction zero**: the same tie code reports 137 ties over 2,048 bf16 items, and fp32's
   smallest top-2 gaps are 9.82e-5 and 6.50e-4, so the measurement resolves and lists near-ties it
   could have called ties.
3. **Scorer of record.** *Annotated by §14.11 item 9: the loader refusal cited when this table was
   accepted — a score file whose `sample_sha1` or per-item `keys` do not match its sidecar is refused
   — is a property of the **fixed-sample path only**, not of this round's harness. The verdict table
   is unaffected and no number is withdrawn; the sibling readers that have no equivalent are named
   there. Corrected further by §14.11 item 20: the `measure_floor.py` hash below is the `fp32/code2/`
   copy, and the fp32 runs used two frozen copies; both hashes and the confinement of their
   difference are there. And by §14.11 item 13: until 2026-10-30 this mode could not be selected
   through the `--full` readout entry point at all — blast radius zero, nothing withdrawn.* Both
   `rp` and `fast` passed §14.6 item 3 on all five suites. Under that
   clause's own order the first is the scorer of record, and it is also the conservative layout,
   so **the scorer of record of R3 is `r3_code/scorer_r3.py` `R3Scorer` mode `rightpad`**: one row
   per candidate, **right**-padded with an explicit attention mask, the LM head applied only at
   the scored positions, `token_budget = 16384`; the model and activations in **float32**; the NPU
   **HF32 matmul and conv flags off**; the duplicate-candidate safeguard of item 1 on; and the
   model of record the **unmerged** adapter applied at scoring time (§14.5 item 5). Code identity:
   `scorer_r3.py` sha1 `d4ad266162660d3f269ddc14703089e3b4118eb7`, `measure_floor.py`
   `44d80526d4a9238d6c55567a0ab3dfe1584e7375`, `sample_r3.py`
   `6f1277f954ff6b3c352258e27de8ed74a506bdd6` (frozen copy `fp32/code2/SHA1SUMS`, verified equal
   to the live files). Mode `fast` is the **retained check** of §14.6 item 3 and is not a scorer
   of record; a reported number produced by `fast` requires a new amendment. Mode `r0` remains
   inadmissible for any readout (§14.2), whatever item 6 below measures about it. Every readout's
   header records mode, `token_budget`, `dtype`, `hf32` and batch composition (§14.6 item 2).
4. **What the fp32 verdict table establishes, and what it does not.** The table is accepted: the
   null gate passes 10 of 10 cells (worst 1.26e-4 against τ_s = 1e-3), (i′)/(ii′)/(iii′) pass in
   all 20 cell-by-candidate rows (worst 1.13e-4; 0 argmax disagreements under either tie rule),
   `exact` vs `exact2` is bit-identical in 10 of 10 cells, and the discrimination counterpart
   fails as required (synthetic +0.01-per-candidate 0.04 to 0.77; bf16 matched by key 0.0989 to
   0.657 nats with 0 to 10 argmax disagreements per cell). Four qualifications are recorded with
   it, so that later readers do not credit the table with more than it measured:
   - **(iii′) is implied by (ii′)** — equal argmaxes force equal correct counts — and is not
     independent corroboration. Its content is that gold is re-derived from the source partition
     by key, independently of the scores.
   - **`exact` vs `exact2` bit-identity is near-tautological**: in the `exact` layout every
     forward is a single unpadded row. It bears only on run-to-run nondeterminism (its use in
     §14.6 item 1) and is not evidence about any batched layout.
   - **The null gate measures batch-size arithmetic, not padding**: the `eq_*` layouts contain no
     padding anywhere.
   - **Vacuity, labelled.** `T1__akhilaaa3/adapter` `rp_b` is batch size 1 for 100% of rows and is
     therefore the `exact` layout, so (i′) is vacuous for it (self-flagged, max |Δ| 0).
     `T1__akhilaaa3/r0model` `rp_b` is batch size 1 for 91% of rows (maximum 3) and is
     **near-vacuous** as a second composition. On those two cells the second composition of record
     for `rp` is `rp_chunk`/`rp_rev` (1.74e-5 to 3.08e-5, 0 argmax disagreements). More generally,
     because `_rightpad` sorts rows by descending length, `rp` exercises only 0.4% to 2.6% padded
     tokens in 8 of 10 cells (13.7% on transfer-v4): **(i′) for `rp` is a strong test of batch
     composition and a weak test of padding.** The strong padding evidence in this table is `fast`
     (3.7% to 41.8% padded prompt tokens, ≤1.13e-4) and `r0` (left padding without position ids,
     ≤9.61e-5). No suite's verdict rests on a vacuous cell: every cell has a genuinely batched
     composition of each candidate mode (`rp_a` 9 to 218 rows per batch, `fast_a` groups of 13 to
     128).
5. **§4.2 reporting, extended: the near-tie census travels with every readout of record.** Beside
   the tie count and the two tie-rule accuracies, every readout of record reports the **count and
   the list of questions whose `exact` top-2 gap is ≤ τ_s = 1e-3**, with each listed question's
   top-2 candidates, and the duplicate-candidate count of item 1. Reason: an item whose top-2 gap
   is below the measured layout difference is decided by arithmetic rather than by the model — on
   the fixed samples one item sits at 9.82e-5 against a worst measured layout difference of
   1.26e-4 — and "0 argmax disagreements" is interpretable only beside that count. A tie or
   near-tie is now known to be between **distinct** levels, so it is a statement about the harness
   and the precision (R0 §11.8 item 1), never about the model's indifference between two copies
   of one option. On the fp32 fixed samples Kev's first-maximal-index rule and the R0 "a tie is not
   correct" convention **coincide** (0 ties over 1,344 items); §4.2 keeps both numbers, and that
   coincidence is reported.
6. **§14.5 item 1 and item 10, re-grounded on precision.** *Corrected in part by §14.11 item 1: the
   "(unpadded bf16 − fp32)" half of the metric-by-metric structure restated below is **withdrawn**,
   so §14.5 item 1 (ii) reports one difference; the two headline sentences below are unchanged, and
   the withdrawn half's content is carried in the erratum's text from the figures this item and
   §14.6 item 5 already measured.* Left padding without position ids is
   now measured **harmless in fp32**: max |Δ| 1.88e-5 to 9.61e-5 against `exact` with **0 argmax
   disagreements in all 10 cells** under either tie rule. The §14.2 consequences nevertheless
   stand, on this ground instead:
   - The published R0 readouts are **bf16**, and bf16 is not an admissible precision for a readout
     of record (§14.6 item 2); bf16 `exact` against fp32 `exact`, matched by key, differs by
     **0.0989 to 0.657 nats with 0 to 10 Kev-rule argmax disagreements per cell**, against
     decision lines with 1.0- and 2.0-point bars. The R0 side of every R3 comparison is therefore
     still a re-score by the scorer of record (item 3), and the published `r0_baseline` and
     `r0_baseline_rederived` readouts are still not the R0 side of any comparison.
   - **§14.5 item 1 (i) stands, pinned as written**, and its purpose is narrowed: it is the
     control separating bf16 composition noise and environment drift from a code defect, and it is
     **not** evidence about padding.
   - **The erratum's headline becomes two sentences**: "the padding claim does not survive a noise
     floor" and "what survives is precision: the published bf16 readout differs from the fp32
     scorer of record by 0.10 to 0.66 nats with up to 10 argmax disagreements per 128-item cell,
     while the left padding it was blamed on contributes ≤1e-4 with none." §14.5 item 1 (ii)'s
     metric-by-metric structure — (padded bf16 rerun − fp32) and (unpadded bf16 − fp32) — is
     unchanged, and the erratum still has no pass bar and no stopping power.
   - **§14.5 item 10's R0 §12.1 retest is kept, with its stated reason corrected.** The suspension
     of R0 §12.1's "do not retest it" no longer rests on the padding shift (0.157 nats, one bf16
     composition draw) matching the length effect (+0.154 nats per token); it rests on the length
     effect having been measured in bf16, whose composition noise on these samples is 0.10 to 0.66
     nats and therefore swamps an effect of that size. The retest happens in fp32, on the scorer
     of record.
7. **R0 erratum text for the tie rate.** The §14.5 item 1 (ii) erratum carries this sentence,
   which corrects the cause but not the number recorded in `R0-BASELINE-RESULTS.md` §9 item 3:
   "R0's 5.21% of T1 rows with exact top ties are ties between **distinct** level names whose bf16
   *logits* collided, not rows whose within-item difference was lost in storage, and they are
   composition-fragile: a different batch composition produces a different set of tied rows. The
   tie rate is therefore a property of R0's precision and batching, not of its data and not of the
   model's indifference between levels. In fp32 on the fixed samples the same measurement yields 0
   ties over 1,344 items." Nothing in R0 §6's identifier-prior mechanism depends on ties, and it
   is unaffected.
8. **The scorer of record's own test suite must be green before the first readout of record.**
   `test_scorer_r3.py::test_bf16_fast_within_measured_two_order_floor` was failing when the ruling
   was written (recorded floor 0.4203, `fast` vs `exact` 0.3587 on 25 items). It asserts a bf16
   property that §14.6
   items 1 and 2 retired, so it voids nothing — the fp32 verdict was reproduced from the raw score
   files without it, and wave-1 training does not call the scorer. It does block the first readout
   of record: a red suite in the scorer of record's own test file leaves the suite unable to
   signal a new break. Before the first readout of record is written, the assertion is either
   rewritten as the §14.6 item 3 fp32 bar (max |Δ| vs `exact` ≤ 1e-3 and 0 argmax disagreements;
   it currently measures 5.2e-5) or removed with a comment naming §14.6 item 1 as the clause that
   retired it, and the full suite is re-run on a chip with its output recorded in the run
   directory. A skip marker or an expected-failure annotation is not an acceptable fix, because it
   would leave the suite's green state meaning less than it says.
   - *State of the tree when this amendment was committed:* the assertion has already been replaced
     in `r3_code/test_scorer_r3.py` by `test_fp32_candidates_meet_the_amendment6_bar`, which asserts
     the §14.6 item 3 fp32 bar with a discrimination counterpart — the first of the two remedies
     above. The old assertion survives in `r3_code_dev/test_scorer_r3.py`. The **obligation is not
     discharged by the rewrite**: the full suite must still be re-run on a chip with its output
     recorded in the run directory before the first readout of record. This note exists so the
     paragraph above is not read later as a false statement about the tree; it was true of the tree
     the ruling examined.
   - *Discharged, 2026-10-30 05:46:41Z.* The full suite was re-run on chip 2 into
     `r3_runs/scorer_r3/test_rerun/`, marker `DONE` with `rc=0`: **8 tests, 8 passed, 0 failed**, no
     traceback. The replacement test measures max |Δ| from `exact` of 3.9e-5 to 7.7e-5 over `eq_a`,
     `eq_c`, `rp_a`, `rp_b`, `fast_a` and `fast_b` against the 1e-3 bar, with 25 of 25 rows
     evaluated; its discrimination counterpart fails as required, bf16 `eq_c` against bf16 `exact`
     being 0.356 nats. A second test asserts HF32 is off for the precision of record and that
     `fp32_verdict` refuses an fp32 cell whose `hf32` flag is not false. This clause is therefore
     no longer outstanding against the first readout of record. This is not a relaxation of any
   bar: the bf16 bar is not lowered, the precision it governed is no longer admissible.

14.10 **Amendment 10, the `gdn_fast_ref` gate verdict, the reproducibility limit and what resume may
claim, two replicates inside wave 1, `TASK_QUEUE_ENABLE`, a future kernel gate's batch rule, two
corrections to the orchestrator's record, and three standing clauses, 2026-10-30.** Made after the
gate reported and before any arm of wave 1 was trained and before any readout of record exists.
Source: the review ruling `reviews/R3-GATE-VERDICT-RULING-fable-20261030.md` (Fable 5.1, CLAUDE.md
§2), whose §10 carries the text of items 1 to 12 and whose dated addendum (§§14–17, 06:35Z–06:48Z)
carries items 13 to 15; each item names the ruling section it comes from. **Stated precisely,
because the engineer's conduct is part of the record:** the gate failed narrowly on its declared
verdict batch, three of the four natural readings of the same data pass, and the engineer used the
declared one, reported the passing alternative as an undeclared alternative rather than as a result,
and asked for a ruling. Items 1 and 3 exist because it did.
1. **(G2) failed; wave 1 and the ladder train on the reference kernel (ruling §2).** Applying §14.7
   item 2 as amended by §14.8 item 1: (G1) **passed** on all three batches (whole-model fp32 logits
   relative L2 1.63e-06 / 1.52e-06 / 1.50e-06 against 1e-4; minimum gradient cosine 0.9999997 over
   the 372 against 0.9999, none below). **(G2) failed** on the declared verdict batch: 368 of 372
   LoRA tensors within `e_fast ≤ 1.5 · e_ref + 1e-3` where ⌈0.99 × 372⌉ = 369 are required, with 0
   beyond 3×. Batch 1 gives 371 (a pass) and batch 2 gives 367 (a fail). The non-gating 320
   full-trainable population also fails the verdict batch (315 of 320 against 317 required) and
   carries one tensor beyond 3× on batch 2 (`layers.21.linear_attn.dt_bias`, e_fast 3.29e-02 against
   e_ref 9.74e-03). This is §14.8 item 1's pre-registered **"both fail"** branch, not its split
   verdict. (G4) was not run and is not required: §14.7 item 2's consequence clause fires on any one
   of (G1)–(G4) failing, and a number produced after the branch is decided could serve only to argue
   against it. **Every arm of wave 1 and every size of the ladder trains on the in-tree reference
   kernel.** Numbers, the four sha256s and the full per-tensor out-of-bound lists are in
   `r3_runs/eff/gate_fast_ref/` (`GATE_RESULT.json`, `GATE_RECORD.txt`, `SHA256SUMS.txt`).
   - **The verdict batch was pre-declared in this pre-registration's own terms**, not only in the
     gate script's docstring: §14.7 item 2 (G4) records `|loss_R − loss_G| = 2.28e-02` before the
     gate ran, and of the three batches only step 0 matches it (0.0228285, against 0.016142 and
     0.028856). The docstring sentence "Verdict of record = step 0" is also present in the preserved
     `gate_fast_ref/gate_model_level.run1.py`, whose sha256 `615d5afb06c6…` is the script of the
     first run that produced a number.
   - **The pooled reading is recorded and refused (ruling §3.1).** Pooling the three batches gives
     1106 of 1116 = 99.104% and **would pass**; so would the mean of the three per-batch fractions
     (99.105%). Neither was declared beforehand, neither is used, and both are written here rather
     than omitted, so that a later reader can see the gate was decided against the reading that
     would have let the work proceed faster. Rule 3 bars choosing among readings after the data, and
     §14.7 item 2's consequence clause ("so the gate is not reopened under schedule pressure after a
     result is seen") and §14.8 item 1's "only one population may gate" each refuse the same move.
     A further objection stands independently of the timing: the out-of-bound tensors are clustered
     by tensor identity and by batch, so 1,116 is not a sample of 1,116 and a bar calibrated on 372
     correlated tensors does not transfer to a pool of three correlated batches.
   - **§14.7 checklist item 2's recorded decision is satisfied by this item together with
     `gate_fast_ref/`**, which carries the failing numbers, the same four sha256s a passing gate
     would have recorded, the statement that (G1)–(G3) ran and (G4) did not, and the statement that
     the branch follows from **a gate verdict and not from a gate crash** (§14.8 item 3).
   - **`fast_ref` is not retired.** It passed (G1) with two orders of margin and is a correct
     implementation that failed a bf16-rounding bar. Item 3 below fixes the terms on which a revised
     version may be re-gated.
2. **The failure's structure, recorded as a finding of this round (ruling §4).** All ten
   out-of-bound LoRA tensors across the three batches are `linear_attn.in_proj_a` (layers 0, 1, 16;
   9; 9, 20, 21) and nothing else out of 372, and the non-gating population's out-of-bound tensors
   are `A_log`, `dt_bias`, `linear_attn.norm`, `in_proj_a` and two attention norms — the same
   gate-and-normalisation family on which the FLA kernel failed §14.1 (b′) (`speedup/README.md:51`),
   and whose only LoRA-trainable member is `in_proj_a` (§7.2's target list; `A_log`, `dt_bias` and
   the norms are frozen).
   - **This is not an artefact of small-norm tensors carrying large relative error.** On the verdict
     batch the median e_ref over the 372 is 0.035145 and the median e_fast is 0.035052 — the two
     kernels are indistinguishable in bulk — and the four failing tensors have e_ref of 0.03398,
     0.03710, 0.04826 and 0.03563, i.e. **at or barely above the median**, against e_fast of
     0.05348, 0.06336, 0.07676 and 0.05469. The reference kernel finds nothing unusual about these
     tensors; only `fast_ref` does.
   - **The mechanism, labelled as this report's own construct and not a literature result (CLAUDE.md
     §4 rule 4).** `g`, the cumulative gate, enters the kernel **only** through the matrix that is
     inverted (`A = −((k_beta @ kᵀ) · exp(g_i − g_j))`), while `q`, `k` and `v` also enter through
     paths outside it. `gdn_fast_ref` replaces the reference's replayed forward-substitution backward
     with the analytic `dL/dA = Xᵀ (dL/dX) Xᵀ`, `X = (I − A)⁻¹`, so the entire rounding difference of
     the change is deposited in `dL/dA`, which is the sole route to the gate parameters, and it is
     applied through `X` twice, so it scales with cond(X)² where the forward scales with cond(X)
     once. That predicts a kernel that passes (G1) in fp32 with two orders of margin while failing
     (G2) in bf16, a per-batch count that varies with the batch's decay profile (the observed
     367–371), and the worst batch being the one with the longest chunks and most padding (step 2).
     **Two independent re-expressions of this inverse, by different authors with different
     algorithms, degrade the same path**, which makes it a property of the operator rather than of
     either implementation.
   - **Nothing about the reference kernel's admissibility changes.** It is the baseline against which
     e_ref is defined and its fp32 form is the gold; no measurement here is evidence about it.
3. **A future kernel gate's batch rule, fixed now and not applied to the gate just decided (ruling
   §3.2 and §3.3).** The instrument that decided item 1 above has a batch-to-batch spread of four
   tensors (367–371) and decided by a margin of one, which is a badly calibrated gate whether or not
   it reached the right verdict. For **any kernel gate whose data does not yet exist** — a revised
   `fast_ref`, any fourth implementation, and (G1) at each ladder size — (G2) is measured as follows,
   and this rule is **not retroactive** (§14.4's precedent: "it is not relaxed retroactively"):
   - **Five batches, not three**, named in advance by their index in the trainer's own data order,
     in both the gate script's docstring and the amendment that authorises the gate, before it runs.
   - **Each batch is judged separately against the unchanged bound** (`e_fast ≤ 1.5 · e_ref + 1e-3`
     for ≥ 99% of the gating population) **and the verdict is the median of the five per-batch
     counts.** The median keeps the batch as the unit of analysis, which is the unit the noise lives
     in; it cannot be gamed after the data; and it does not pool correlated tensors. *On the data of
     item 1 above the median of {368, 371, 367} is 368 and the verdict would be unchanged, which is
     the only honest condition under which to pre-register a replacement rule.*
   - **All five per-batch counts are reported.** A spread greater than 2 across the five is reported
     as a flag that the gate is under-powered for its own bar, not averaged away.
   - **The 3× clause binds on every batch**: no tensor may exceed `3 · e_ref + 1e-3` on **any** of
     the five. Catastrophic error is not a quantity to take a median of.
   - Pooling tensors across batches is **not** admitted, in this or any other form.
4. **§12, added: what this round cannot claim about the gate path (ruling §4.4).** Under the
   reference kernel in bf16, the gate path is the noisiest gradient in the model: e_ref of 0.034 to
   0.051 relative error against the fp32 gold on `in_proj_a`, `A_log` and `dt_bias`. bf16 compute
   over fp32 master weights is this round's pre-registered precision (§7.2) and nothing changes. The
   claim that is **not** available: *this round cannot claim that its `in_proj_a` LoRA adapters
   learned a well-conditioned signal.* A 3–5% relative gradient error on the one gate-path adapter
   is a plausible low-SNR channel, and if a later round finds `in_proj_a` adapters contributing
   little, this measurement is the first place to look rather than a finding about gating's
   importance in the architecture. No experiment in this round is authorised by this item.
5. **(G3) is measured on both branches as §14.8 item 4 required, and the model-level floor is
   exactly zero (ruling §5.1).** Recorded: two invocations of the reference kernel with identical
   micro-batch, seed, rows and chunk plan — one in-process, one in a **separate process** — give
   d(R,R′) = **0.0** over the stacked 372-tensor LoRA gradient, **372 of 372 tensors bitwise equal**,
   and |loss_R − loss_R′| = 0, on six batches across `model_level_final` and `diag_steps9_11`; an
   independently written second script (`r3_code/tq_check.py`) reports `max_rel_l2` **exactly 0.0**
   and 372 of 372 bitwise equal on five further batches in every one of six pairings. **This zero is
   not a by-construction zero** (CLAUDE.md §7.1): the same code reports 3.3062e-02 for the
   fast-against-reference comparison on the same step and 318 and 319 of 320 rather than 320 for
   base tensors on steps 1 and 2, and the reviewer verified the cross-process bit-identity
   independently by hashing the 372 serialized storages of `grads_R_step0.pt` and
   `grads_Rprime_step0.pt` (43,290,624 bytes, all equal, `data.pkl` streams equal). **Scope, stated
   rather than implied:** one chip, one container, one host, one CANN version, sequential in time. It
   is **not** evidence of reproducibility across chips, hosts or images and no claim of that kind is
   licensed.
   - **The model-level replicate is the floor of record for every model-level bf16 statement about a
     kernel**, as §14.7 item 2 (G3) intended, and it is zero, which is why item 9 below has an
     instrument of unlimited resolution.
   - **The trajectory replicate is the floor of record for (G4) and for every trajectory statement,
     and it is not zero**: mean |loss_R − loss_R2| over 100 steps = **6.046e-03** (max 3.587e-02,
     8 of 100 steps bitwise equal, first-20 mean 4.342e-03, last-20 mean 7.181e-03); the first
     replicate gave 5.430e-03. §14.7 checklist item 5's K2 cell was re-measured against it:
     reference + shared K2 0.0585 against the row form's 0.0586 — clean — and `fast_ref` + shared
     0.0746 against 0.0642, not covered by the floor, which is consistent with item 1 above's verdict
     and is now moot since `fast_ref` does not train.
6. **The reproducibility limit, and §14.3's "exact resume" restated for the second and last time
   (ruling §5.2, §5.3, §5.4 and §6).** §14.7 item 4 restated §14.3's claim as "bit-identical in the
   adapter; the logged loss agrees to 6e-08". **Those numbers stand; their scope is withdrawn.** They
   were measured over a handful of steps, and a handful of steps is precisely the window in which
   this trainer is bitwise reproducible. The "6e-08" is itself the step-5 half-ULP event described
   below, caught in two of five repeats before anyone was looking for it.
   - **The mechanism first proposed — that Adam amplifies a last-bit gradient difference — is
     withdrawn, refuted by the engineer's own test.** Under SGD with momentum 0.9 and the same
     schedule the same replicate pair diverges **earlier** (first differing step 3 against AdamW's
     5) and ends **twice as far apart** (final-weight relative L2 2.69e-04 against 1.31e-04), with
     0 of 372 tensors bitwise equal at step 40 under both
     (`gate_fast_ref/sgd_replicate/out/diag_sgd_replicate.json`). Adam's second moment is not
     necessary for the phenomenon. *Limits, recorded rather than waived: one replicate pair per
     optimizer, and the two optimizers are not on the same trajectory (mean loss over the last ten
     steps 0.521 against 0.451, mean gradient norm 35.8 against 26.3), so only the qualitative
     reading — SGD is not closer, and is earlier — is supported. That is all it is used for.*
   - **The admissible mechanism statement.** *A rare last-bit nondeterminism on the forward /
     loss-reduction path, not present in the gradients at any measured cell, amplified to the 1e-2
     scale within about ten optimizer steps by a mechanism that is optimizer-independent and has not
     been identified.* The evidence that the seed is in the forward and not in the gradients: across
     six pairings of five batches (1,860 tensor cells) **no gradient tensor ever differs**
     (`max_rel_l2` exactly 0.0) while the loss scalar differs by one half-ULP (1.1920929e-07) on two
     batches **between two runs of the same configuration**; and at the first differing step of
     every trajectory pair — AdamW 5, dropout-0.0 8, SGD 3 — the `grad_norm` difference is **exactly
     0.0**.
   - **The amplification is a jump, not a growth, and is this round's hypothesis rather than its
     finding (CLAUDE.md §4 rule 4).** 1.19e-07 at step 10 becomes 3.59e-02 at step 11 — five orders
     in one optimizer step at lr ≈ 1e-5 — and then stops growing (first-20 4.34e-03, last-20
     7.18e-03). Smooth amplification by any optimizer cannot produce the first and would not produce
     the second. The hypothesis on record: this trainer holds **bf16 compute weights over fp32
     master weights** (§7.2), so a sub-ULP fp32 master-weight difference is invisible until it
     crosses a **bf16 rounding boundary**, whereupon the compute weight moves by a full bf16 ULP — a
     finite jump of about 0.4% — after which the two runs are two valid trajectories a bounded
     distance apart. The global grad-norm clip at 1.0 against measured gradient norms of 20 to 150
     is a second candidate threshold. **No ruling in this amendment depends on which it is.**
   - **The claims this round may make, and no others.** (i) The backward is bitwise reproducible
     from identical state, same chip and image (item 5 above). (ii) **A same-seed training run is
     bitwise reproducible for about 5 to 10 optimizer steps and not beyond**; no claim of bitwise
     equality past **step 3** is admissible for any configuration. (iii) Beyond that window two
     same-config runs are two samples from one distribution, separated by a mean |Δloss| of
     **6.05e-03** over 100 steps and a final-adapter relative L2 of **1.31e-04** with **0 of 372
     tensors bitwise equal**; that number, not zero, is the floor for any trajectory-level
     comparison. (iv) **Resume is not bit-exact and is not described as "exact" anywhere in this
     round.** A resumed run is a different sample from the same distribution, which is what §11.2's
     resumability requires of it, and is **not** evidence that two runs are the same run. The word
     "exact" is struck from §14.3's test list and replaced by "resume", with these four claims as
     its content.
   - **§14.3's resume test is rewritten before wave 1 launches, because as written it passes for the
     wrong reason.** It resumes after a handful of steps, inside the reproducible window, so it
     would stay green if resume were badly broken past step 10 — the defect §14.9 item 8 named in
     the scorer's own suite, with the same remedy. The replacement asserts **two** things: that a
     checkpoint at step 3 resumed to step 6 gives a **bit-identical** adapter, which is a real and
     sharp property inside the measured window; and that a resume at step 40 reproduces the
     remaining trajectory **to within the (iii) floor above**, with the test naming that floor and
     its source file. Neither assertion overclaims. The suite is re-run on a chip with its output
     recorded in the run directory, as §14.3 requires. A skip marker or an expected-failure
     annotation is not an acceptable alternative (§14.9 item 8's convention).
   - **No readout of record is affected, and this is not reopened.** §14.7 item 4 fixed the scope —
     scoring performs no backward — and §14.9 item 3 made the scorer of record fp32. The limit is a
     property of **training** trajectories. The `harness_identity` pin, whose completed files were
     byte-identical to R0's eighteen hours later on different chips (§14.8 item 6), is scoring and
     is unaffected. Nothing about the scorer, the readouts or the erratum is reopened.
7. **One cheap localisation experiment, pre-registered and explicitly not a blocker (ruling §5.3 and
   §5.4).** Two same-config runs of 15 steps dump, after each step, the fp32 master weights and
   their bf16 cast, and the report names **the first step at which each first differs**. If the bf16
   cast diverges a step or more after the fp32 master weights, the bf16 rounding boundary of item 6
   above is the amplifier; if they diverge together, it is not. It costs minutes on one chip, it is
   recorded in `r3_runs/eff/` with a wiki entry (CLAUDE.md §8), and **wave 1 does not wait for it**:
   items 6 above and 8 below are written so as to hold whatever it returns. It is not permitted to
   change any floor, threshold or claim of this round; a result that suggests one needs a further
   amendment.
8. **A same-config replicate inside wave 1: K1 seed 2, a ninth run, named in the chip-assignment
   file before launch (ruling §7).** §14.5 item 4 step 2's wave becomes **nine runs**: the eight
   registered arms unchanged, plus **K1 seed 2 trained a second time with an identical
   configuration** on the reference kernel and **scored on both dev partitions with the scorer of
   record**, exactly as the arm is. Reason: every decision line in this round is in **accuracy
   points** (§8.2 (b) 1.0, §8.2 (c) 2.0, §9.1 0.80 / 0.60, §14.4's ±1.0 band) while the measured
   floor is **6.05e-03 nats of training loss**, and a loss floor cannot be converted into an
   accuracy floor. The standing project rule — measure the same-config replicate floor before
   ratifying any equivalence threshold — therefore has never been satisfied for §8.2 (b) or (c), and
   item 6 above removes the only reason it might have been thought vacuous. *Item 13 below, from the
   ruling's dated addendum, fixes this run on chip 3 as `w1_k1_s2_replicate_diffchip`, adds a tenth
   run as its same-chip companion, and names which of the two floors gates; read the two items
   together.*
   - **Arm and seed**: K1 seed 2, because it is the arm §9.1 K-align is judged on, the arm §8.2's
     first adoption decision uses, the seed §9.3 K-ladder uses for like-for-like, the base of
     §14.4's K1-FLA band, and the cheapest run in the wave.
   - **Cost: no additional wave wall clock.** The wave is 6.76 h, set entirely by the two K2-shared
     runs at 1.280 q/s/chip (`bench_record.json` `v4_ref_k2sh_mt3000_r48`, measured with
     `TASK_QUEUE_ENABLE=2` already in effect, so the figure does not shrink under item 9 below); a
     K1 run on the reference kernel is 1.84 h at 4.715 q/s/chip (`ref_tq2_nockpt`, 30.5 GiB). From
     about t = 1.9 h six of eight chips are idle for roughly five hours. The ninth run takes the
     first chip a K1 run frees, finishes about t = 3.7 h, and is scored well inside the envelope.
   - **It is named in the §14.5 item 4 step 2 (b) chip-assignment file before the wave launches**,
     as the sequential successor on a specific chip, with that file's sha256 recorded per §14.7
     checklist item 7. It is a **run of record** and therefore does not share a chip with another
     (step 2 (a)). Adding it after any dev number is read would be barred by step 2 (b), which is
     why it is fixed here.
   - **It is a floor measurement, not a third seed.** It must **not** enter K1's two-seed mean, be
     averaged into any arm's accuracy, or be used to break a tie; each would change a pre-registered
     estimator after the data. Its single use is to report, in accuracy points on each dev suite,
     how far apart two identical configurations land.
   - **What happens if the floor is large, fixed before the number exists.** If the replicate's
     dev-accuracy difference on a suite is **below** 1.0 point, §8.2 (b)'s bar stands and the floor
     is reported beside every comparison. If it **meets or exceeds** 1.0 point on either dev suite,
     the bar **is not relaxed** (§14.1 and §14.4's precedent); instead any §8.2 (b) comparison whose
     margin falls inside the floor is reported as **indeterminate**, the arm is **not adopted on
     that basis**, and adoption must be carried by §8.2 (a) and (c) with the floor reported. **No
     arm is adopted on a margin smaller than the measured floor.** The same test applies to §8.2
     (c)'s 2-point flip-rate bar on the gating cells. §9.1 K-align is an absolute line, not a
     difference tolerance, so the floor does not move it; the floor is reported beside the gap and
     §9.1's "the gap is reported as a gap" stands.
   - **§8.2 (a)'s estimator is unchanged and is labelled.** The bootstrap resamples **questions** and
     therefore estimates question-sampling variance only; run-to-run variance (seed, and same-seed
     run noise) is averaged by the two-seed mean and never estimated, so it does not enter the
     interval. Changing the statistic now is barred by rule 3. Every §8.2 report therefore states
     that **the interval is conditional on the realized runs and does not include run-to-run
     variance**, and reports this item's replicate floor beside it. Additive and restrictive.
   - **Not ordered**: no K2 replicate (6.8 h, would double the wave), no third seed of any arm, no
     change to the eight registered arms, no re-run of anything measured. If K1's floor turns out
     large enough to matter for the K1-against-K2 comparison specifically, a K2 replicate is
     requested then, with a number in hand.
9. **`TASK_QUEUE_ENABLE`: an efficiency defect fixed, and the §9 obligation discharged by the right
   instrument (ruling §8).** The container image exports `TASK_QUEUE_ENABLE=1`, so `train_r3.py`'s
   `os.environ.setdefault("TASK_QUEUE_ENABLE", "2")` **never took effect inside a container** and a
   performance fix believed to be in force had never once run. The trainer now **assigns**
   (`os.environ["TASK_QUEUE_ENABLE"] = os.environ.get("NGA_TASK_QUEUE_ENABLE", "2")`), overridable
   by `NGA_TASK_QUEUE_ENABLE`, with the realized value in every manifest.
   - **Measured effect, in the form CLAUDE.md §9 requires**: the same 100 reference-kernel steps run
     at **1.94 q/s/chip** with 1 and **4.4 q/s/chip** with 2 over all 100 steps (1.93 → 4.84 over
     steps 11–100), **one chip**, **30.5 GiB reserved**, K1, micro-tokens 4096, ±15% host noise — a
     **2.3 to 2.5× speedup**. The quoted headline is this pair, not the end-of-run windowed
     "2.00 → 4.96".
   - **It changes speed only, and the usual check could not have shown that.** A loss-curve
     comparison cannot resolve anything below item 6 above's (iii) floor of 6.05e-03 nats and is
     blind past about step 10, so it would pass a change that perturbed the arithmetic by 1e-3 nats.
     The admissible instrument is the opposite of a trajectory: a **single-step, identical-state,
     cross-process** comparison, whose floor is **exactly 0.0** (item 5 above) and which therefore
     has unlimited resolution. Evidence of record, all three independent: (i)
     `gate_fast_ref/tq_check/out/tq_check.json` (`DONE rc=0` 06:04:19Z) — TQ = 1, 2, 1, 2 in four
     separate processes, five fixed batches from identical weights, **`max_rel_l2` exactly 0.0 and
     372 of 372 LoRA gradients bitwise equal in all six pairings**, the only non-zero quantity being
     a half-ULP loss difference on two batches **which occurs in the TQ2-against-TQ2′ same-config
     pair**, so it is inside the replicate floor and not attributable to the flag; (ii) the three
     model-level gate runs, TQ=1 and TQ=2 with two different trainer hashes, giving bf16 losses
     equal **to all 17 significant digits** on all three batches and identical (G2) counts of
     368 / 371 / 367; (iii) the 100-step TQ=1-against-TQ=2 trajectory being **step-for-step
     indistinguishable from a same-config replicate**. The flag is **admitted for wave 1 with no
     further measurement**.
   - **Standing rule, which is the generalisable part.** Any future change to this trainer claimed
     to affect **speed only** discharges CLAUDE.md §9 by the instrument in (i) — identical weights,
     fixed batches, separate processes, bitwise on all 372 gradients — and **not** by a loss-curve
     comparison. A loss-curve check is admissible only as a secondary report, never as the evidence.
   - **And the defect's own lesson.** Every environment variable this trainer sets for performance
     is **read back from `os.environ` after import and written to the manifest**, so that an image's
     inherited value cannot silently defeat it again; `task_queue_enable` already is. A defect that
     hid behind a `setdefault` for this long is one the manifest must make visible. Two chips of
     wave 1 were about to spend 6.8 h each at 2.4× less than necessary.
10. **§14.8 item 3 is corrected: the crash's error string, and who observed what (ruling §9.1, §9.2
    and §11).** §14.8 item 3's live instance describes the gate's first launch as having an "`EL0005
    Resource_Busy … rtGetDeviceCount execution failed` log tail". The engineer reports that the log
    showed `aclInit` error 507899 and `rtGetDeviceCount execution failed` and that it did not see
    `EL0005`; it also **deleted the original `run.log` before relaunching**, so the file cannot be
    re-read. The record is corrected, and the correction is **not** that one account was wrong:
    **`aclInit` error 507899 and `Resource_Busy(EL0005)` are two lines of one CANN error block**, not
    two competing accounts. The identical three-line cluster — `NPU function error: aclInit, error
    code is 507899`, then `Resource_Busy(EL0005): The resources are busy.`, then `rtGetDeviceCount
    execution failed, reason=driver error:internal error` — is present in six logs of this round
    that are still on disk: `scorer_r3/fp32/run_w{1,2,3}_failed_startup_npu_busy/run.log`,
    `scorer_r3/smoke_mf/run.log`, and `harness_identity/logs/shard{0,1,2}.log`. The engineer
    reported the first and third lines and not the second, four lines below a line it had already
    matched, which is what its partial read predicts. **The clause's function is unaffected**: this
    was an infrastructure fault at process start, **not a (G1) result**, and a `FAILED` marker is
    not admissible as a gate verdict.

    §14.8 item 3's sentence beginning "The live instance:" is replaced by:

    > The live instance: `r3_runs/eff/gate_fast_ref/model_level/FAILED` recorded `rc=1
    > utc=2026-10-30T04:41:39Z` — attested by two independent contemporaneous reads, the
    > orchestrator's of the watchdog `digest.json` and the reviewer's in
    > `reviews/R3-CHIP-PRIORITY-RULING-fable-20261030.md`, and by neither now, since the marker went
    > with the deleted directory and `_watchdog/digest.json` is **a rolling file, rewritten every
    > poll, which cannot be cited as evidence after the fact**. The failure was the CANN startup
    > fault whose block reads `NPU function error: aclInit, error code is 507899` /
    > `Resource_Busy(EL0005): The resources are busy.` / `rtGetDeviceCount execution failed,
    > reason=driver error:internal error`; the engineer observed the first and third lines in the
    > original log, the second line is the same block's symbolic condition and is attested in six
    > other logs of this round (`scorer_r3/fp32/run_w{1,2,3}_failed_startup_npu_busy/run.log`,
    > `scorer_r3/smoke_mf/run.log`, `harness_identity/logs/shard{0,1,2}.log`), and the original
    > `run.log` was deleted before the relaunch so it cannot be re-read. A third surviving artefact,
    > independent of both the digest and either ruling, is `CHIP-ALLOCATION.json`'s
    > `why_this_file_exists`, which records that "chip 1 was sampled unclaimed at 04:37Z between
    > shards of the fp32 scorer wave, was handed to the gate measurement, and
    > `r3_runs/eff/gate_fast_ref/model_level` failed at 04:41Z with 'Get device cnt failed /
    > CheckDeviceIdIsValid' because the device was not actually free" — fixing the time, the cause
    > and the signature in the form the orchestrator's digest carried.
    > `gate_fast_ref/CRASH_NOTE.txt` is the reconstruction of record and marks itself as one. The
    > fault was an **infrastructure fault at process start on a chip that was not free** (the scorer
    > wave still held chip 1), **not a (G1) result**, and not admissible as one. The earlier
    > ruling's further detail that chip 1 "still carried pid 1527259 with 370 MB" was a live
    > device-state read with **no surviving artefact**; it is uncorroborated, carries no weight, and
    > the conclusion does not rest on it — the chip-not-free finding is carried by the three
    > artefacts above. The recorded decision states which of the four gates ran, their numbers, and
    > that it follows from a verdict rather than from a crash.
11. **§11.2, added: a relaunch never destroys a terminal marker or its log (ruling §9.3).**
    CLAUDE.md §7 makes the marker file the source of truth for whether a run finished; a source of
    truth a relaunch can delete is not one. Twice on 2026-10-30 evidence was overwritten by a
    relaunch, and in the case of §14.8 item 3 the destroyed artefact was evidence in a dispute about
    whether a gate had failed — exactly the distinction between "the gate ran and returned a
    verdict" and "the gate did not complete" that §14.8 item 3 exists to draw. Added to §11.2:

    > **A relaunch never deletes or overwrites a run directory that holds a terminal marker.** It
    > moves it aside first, to a sibling `<name>.crash-<utc>/`, keeping the log, the marker and the
    > launch record together. This costs one command and applies only to directories that already
    > carry a marker; a directory with no marker may be reused freely. Where a crash log has already
    > been lost, the reconstruction is written as a dated note that marks itself a reconstruction and
    > attributes each fact to whoever observed it (`gate_fast_ref/CRASH_NOTE.txt` is the model).

    This clause does **not** stand alone: it preserves the run directory, and item 14 below
    preserves the digest's pointer and error signature. Neither alone would have prevented the loss
    behind item 10 above, and the two are committed and cited as a pair.
12. **Wiki (CLAUDE.md §8).** `wiki/E1-gdn-fast-ref-gate.md` records this verdict as a dated
    results-and-verdict section written from `gate_fast_ref/`'s own report files, including the
    refused pooled reading of item 1 and the item 2 mechanism. §14.8 item 1's existing obligation to
    correct that entry's lines 36, 60-64 and 180 as a dated note is unchanged — and the correction
    is now more interesting than it was, since the entry's pre-run prediction that the kernel "fails
    exactly as the FLA kernel failed" is, on the evidence of item 2, **substantially right for a
    reason the entry did not give**: not the same tensors, but the same gate-and-normalisation path,
    seen through the one member of it that LoRA trains. That is recorded as a dated note, not a
    silent edit, and the hypothesis section is not rewritten. The item 7 localisation run and the
    item 8 replicates each get their own entry, written before they launch.
13. **The replicate's chip, and a second replicate (ruling addendum §14).** Item 8 above's ninth run
    is placed on a **different chip** from `w1_k1_s2`, deliberately: the floor bounds §8.2 (b) and
    (c), whose comparisons are between arms on different chips, so the floor must carry any
    chip-to-chip term or it bounds the wrong quantity. The two errors are also **not symmetric**. A
    floor too small calls a margin that is really inside the noise **real**, which yields a **wrong
    adoption**, carried into the ladder and into every downstream claim. A floor too large calls a
    real margin **indeterminate**, which is costly but visible, recoverable and already this
    pre-registration's culture (§9.1: "the gap is reported as a gap; it is not explained away"). A
    research round absorbs a Type II error far better than a false adoption, so different-chip
    dominates for the floor's stated purpose. A **tenth** run is added,
    `w1_k1_s2_replicate_samechip` on **chip 2**, sequentially after `w1_k1_s2`, so the composite
    floor can be decomposed; the chip-3 run is named `w1_k1_s2_replicate_diffchip`. Both are named
    in `r3_runs/w1/CHIP-ASSIGNMENT.json` before launch with its sha256 recorded (§14.5 item 4 step 2
    (b)) — revision 2, ten runs on eight chips, sha256
    `0e680df32d9217f6f465818c0f8ab9ebb86bc17c9812ed442b15706ae188f962` in `CHIP-ASSIGNMENT.sha256`,
    `DRAFT` until this amendment is committed — both complete by about t = 3.7 h inside the 6.76 h
    envelope, and that file **sequences the dev readouts of record explicitly** rather than leaving
    them to be discovered at runtime, since from t ≈ 1.9 h only chips 4–7 are free for scoring until
    the replicates finish.
    - **Why a same-chip companion exists at all.** Item 5 above's bitwise-reproducibility finding is
      scoped to one chip, one container and one host and is explicitly **not** evidence of
      reproducibility across chips. §14.8 item 6's existing cross-chip evidence does not reach it:
      that evidence is **scoring** — forward only, no backward, no optimizer — while this is a claim
      about **training**. The pair measures precisely the gap item 5 above left open.
    - **Only the different-chip floor gates.** It is the floor of record for §8.2 (b) and (c) and for
      item 8 above's "no arm is adopted on a margin smaller than the measured floor". The same-chip
      floor is measured, reported beside it and **does not gate**, **even if it is the larger of the
      two** — the gating floor is named by its role, not by its size, and it is named here before
      either number exists. Two floors with no pre-named decider would be two chances to call a
      margin inside the floor, chosen after the numbers, which is what §14.8 item 1 refused for the
      two tensor populations and what item 1 above refused for batch pooling; the reviewer applied
      that rule to itself here rather than inventing a new one for this case.
    - **The contrast is chip identity only.** Both replicates run at a different time and under
      different co-tenancy than the original, so the difference between the two floors isolates the
      **chip-identity** term with time and co-tenancy varying in both; it is not a general chip
      effect. If the composite is indistinguishable from the same-chip floor, the chip term is
      negligible and the floor is run-to-run noise. If the composite is materially larger, a
      chip-identity term exists **in training**: the composite still gates, the split is named in
      every §8.2 report, item 5 above's single-chip scope limit is restated as a measured finding
      rather than an untested gap, and **every future wave states whether an arm's two seeds shared
      a chip**, since a chip term would make that a confound inside the seed-mean itself.
    - Neither replicate enters any arm's two-seed mean, is averaged into any accuracy, or breaks any
      tie. No third chip, no replicate of any other arm, no K2 replicate.
14. **Watchdog digest retention (ruling addendum §15).** `_watchdog/digest.json` and `digest.md` are
    rewritten every pass, so evidence existing only there has the lifetime of one poll — the defect
    that made item 10 above's error string unverifiable. The watchdog retains a **dated copy of every
    pass that carries a flag**, and the trigger is **any** flag — failure, stall **or suspicious
    success** per CLAUDE.md §7.1 — not failures alone: this round's most load-bearing number is a
    rate of exactly 0.0 (item 5 above), which §7.1 classes as suspicious and which a failure-only
    rule would have discarded. "Unexplained" is **not** a criterion, because tier 0 is a script and
    may not judge what is explained; the watchdog retains on the flag and tier 1 decides what it
    meant. Retention is capped by count or age, and **the retained copies, not the live file, are
    the citable artefact.**
    - Recorded with it: retention preserves **pointers and clustered error signatures, never the
      evidence** (§7.1 — "full tracebacks never enter the digest"), so it reproduces a marker, a
      timestamp and an error exemplar but **not the log the pointer names**. It therefore **does not
      stand alone**: item 11 above preserves the run directory and this item preserves the
      signature, neither alone would have prevented the loss behind item 10 above, and they are
      committed and cited as a pair.
15. **Counterfactual declaration, a standing clause on rule changes (ruling addendum §16).** Added
    to §10 ("Reporting and measurement-trap checks") as a standing clause, carried here in full:

    > **Counterfactual declaration.** Any amendment that changes a **decision rule** of this
    > pre-registration — a metric, a threshold, a population, an estimator or an aggregation — and
    > that is written **after** a result the old rule bore on, states in the amendment itself **what
    > the new rule would have decided about that result**, computed from the data already in hand.
    > - If the new rule reaches the **same** verdict, the amendment says so. This is the cheap and
    >   ordinary case and it discharges the clause.
    > - If the new rule reaches a **different** verdict, the amendment says so **prominently**, is
    >   **not applied retroactively** to that result, and must carry a justification that does not
    >   reference it. A rule that reverses the case that prompted it needs an argument that would
    >   have been made before the case arose.
    > - The clause does **not** apply to a correction of fact, which has no counterfactual verdict
    >   (§14.9 item 1 is the model), nor to a new obligation that no prior rule could have decided
    >   (§14.10 item 8 is the model). An amendment in either class says which, in one sentence,
    >   rather than omitting the declaration silently.
    >
    > Reason: a rule written after a result is suspect in exactly one way, that it was shaped to
    > change that result. The counterfactual is determinate, costs nothing to compute from data
    > already held, and cannot be gamed, so stating it converts an unfalsifiable question about
    > motive into a checkable claim. It is the rule-level counterpart of rule 3's pre-registration
    > requirement, for the cases where pre-registration has already been overtaken by events.

    - **Scope, tested against this round's own amendments.** §14.1 replaced §11.3's (a)/(b)
      thresholds after finding they sat below the noise floor, and the replacement (b′) also fails
      the FLA kernel (96.6% against 99%), so the counterfactual **agrees**. Item 3 above's
      five-batch median gives median {368, 371, 367} = 368 and leaves item 1's verdict unchanged, so
      it **agrees** and its own text discharges the clause. §14.9 item 1 withdrew a factual premise,
      where there is no decision rule and no counterfactual verdict, so the clause **does not
      apply**. Item 8 above creates a new obligation, which no prior rule could have decided, so the
      clause **does not apply** to it either — stated here rather than omitted silently, as the
      clause requires. The reviewer tested §14.1, item 3, §14.9 item 1 and item 8; the extension of
      the same class to **item 13** (the placement of the two replicates) is the applying writer's
      classification, not the reviewer's, and is flagged as such so that a later reader can
      disagree with it without having to reconstruct who decided what.
    - **One caution, which is part of the clause and not a gloss on it.** The clause must not become
      a reason to *avoid* fixing a broken rule. A badly calibrated instrument is fixed when it is
      discovered, and the fact that fixing it would have changed a verdict is a reason to declare
      loudly and not apply retroactively — **not** a reason to leave the instrument broken. §14.1 is
      the precedent in the right direction: thresholds below their own noise floor were replaced the
      moment that was known, with the old verdict left standing.

**Launch-checklist status (§14.7's checklist as extended by §14.8 and by this amendment, ruling §12
and the addendum's closing status).** This is a status, not an authorisation: **wave 1 is not
cleared to launch**, because items 1, 7, 8 and 9 are open and three of them are open *because of*
this amendment.

| # | Checklist item | Status |
| --- | --- | --- |
| 1 | §14.7 and §14.8 committed | **Open** — this amendment (§14.10), now with items 13–15, must be committed too |
| 2 | `gate_fast_ref/` with (G1)–(G4) **or** the recorded reference-kernel decision, with the four sha256s, naming which gates ran and that it follows from a verdict not a crash | **Met** — `GATE_RECORD.txt`, `GATE_RESULT.json`, `SHA256SUMS.txt`, `CRASH_NOTE.txt`; item 1 above is the pre-registration half |
| 2b | (G3) on this branch, model-level **and** trajectory (§14.8 item 4) | **Met** — `model_level_final`, `trajectory_final`; verified independently by the reviewer |
| 3 | Corrected equal-length determinism probe, green | **Met** — `tests_chip1/run.log`: all four corrected-path probes including "2 identical-length rows, explicit 4D mask" at 0.000e+00, `DONE rc=0` |
| 4 | K2 dropout-mask-semantics test, green | **Met** — "ALL 8 K2-SHARED TESTS PASSED (ref, fast_ref)", with the per-question prompt mask asserted (batch 3 for 43 options) |
| 5 | Production bf16 K2 cell re-measured against the (G3) floor | **Met for the branch that now trains** — reference + shared 0.0585 against the row form's 0.0586; the `fast_ref` cell (0.0746 against 0.0642, not covered) is moot under item 1 above |
| 6 | `bench_record.json` carrying `gdn_impl`, `k2_impl`, trainer sha256 | **Met** — verified present on every row |
| 7 | §14.5 item 4 step 2 chip-assignment file, sha256 recorded | **Open** — `r3_runs/w1/CHIP-ASSIGNMENT.json` now exists at revision 2, ten runs on eight chips, sha256 `0e680df32d9217f6f465818c0f8ab9ebb86bc17c9812ed442b15706ae188f962` recorded in `CHIP-ASSIGNMENT.sha256`, but it is marked `DRAFT` and is not authoritative until this amendment is committed; it discharges items 7 and 9 together |
| 8 | §14.3 resume test rewritten and the suite re-run on a chip (item 6 above) | **Open** — new obligation from this amendment; minutes on one chip |
| 9 | The ninth and tenth runs named in the assignment file before launch (items 8 and 13 above) | **Open** — new obligation from this amendment; the file must carry **ten** runs and lose its `DRAFT` status, and this must be fixed before launch, not after |

Not on the critical path and explicitly not blocking: item 7 above's master-weight localisation run,
and item 12 above's wiki entries for the new runs (written *before* those runs launch, per CLAUDE.md
§8, but neither run blocks the wave). One item outside this checklist is still the actual gate on
launching: §14.5 item 4 **step 1 must be complete and read on dev** before step 2 begins, and §14.8
item 6 left `harness_identity` holding chips 5–7 to its own `DONE`, expected about 09:00Z. That
ruling stands as written — option (a), let it finish; nothing is stopped — and nothing in this
amendment changes the step order. *§14.11 item 2 changes step 1's **contents**, not the step order:
the (ii) erratum measurement leaves the step, the (i) identity check keeps its place and its
round-stopping power, and §14.11 item 7 adds one condition on reading that verdict.*

14.11 **Amendment 11, the withdrawal of the second erratum difference, the erratum's release from
the gating step and its two deadlines, the R0 re-score named as the adoption gate it is, four
instrument defects and their accepted fixes, K0's readout provenance and realised composition
verified by reproduction rather than re-run, the single-partition scorer path closed, and five
standing clauses one of which is sharpened by the reviewer's own application of it, 2026-10-30.**
Made before any arm of wave 1 was trained, before any readout of record exists, and before any
erratum or identity-verdict number exists (verified by search: no `ERRATUM-DIFF.json` and no
`IDENTITY_VERDICT.json` anywhere in the experiment tree at 07:05Z). Source: the review ruling
`reviews/R3-ERRATUM-SCOPE-RULING-fable-20261030.md` (Fable 5.1, CLAUDE.md §2), closed at 07:58Z:
its §9 carries items 1 to 12, its §13 carries items 14 to 18 after the 07:17Z addendum, its §16
carries item 13 and items 19 to 22 after the 07:40Z addendum, and its §18 corrects two of the
ruling's own sentences at 07:55Z — a struck bullet in item 4 and K0's roles in item 17, both applied
here; each item names the ruling section it comes from. Where the ruling wrote an item twice the
**later text is the one applied**: items 6 and 8 are §13's restatements, not §9's originals, because
the code moved under them between the two, and item 13 is §16's filled item, not §9's reserved slot.
There are no reserved slots; this amendment is items 1 to 22 and is committed whole.

**Counterfactual declaration (§10, added by §14.10 item 15), for this amendment as a whole.** Items 1
to 4 change a sequencing rule and the scope of a commissioned measurement. No result existed that the
old rules bore on: the erratum, the (i) identity verdict and every readout of record are unwritten,
and wave 1 has not launched. So there is **no counterfactual verdict to compute**, and the clause's
second scope condition applies — these are new or withdrawn obligations, not rules rewritten after a
result. Items 5 to 8 are instrument fixes and a freeze; item 9 is a correction of the stated scope of
an acceptance, which §14.9 item 1 is the model for; items 10 to 12 are new standing clauses that no
prior rule could have decided; items 14, 18, 13 and 20 are corrections of fact and items 15, 16, 17,
19, 21 and 22 are new obligations, so the clause does not apply to any of them either. This paragraph
exists so the declaration is not omitted silently, as the clause requires. Items 10, 11 and 12 each
state, in their own text, what they would have decided about the case that prompted them, and item 15
does the same although as a new obligation it need not.

1. **§14.6 item 5 and §14.5 item 1 (ii): the second difference is withdrawn (ruling §2).** The
   requirement that the erratum report "(unpadded bf16 − fp32)" as a full-set, metric-by-metric
   difference is **withdrawn**. Reasons, in the order they decide it: (a) the clause is not
   executable as written — "unpadded bf16" is defined twice and incompatibly in this file (§14.2's
   `token_budget=1`, one row per candidate, i.e. mode `exact`; §14.6 item 1's and §14.5 item 7's
   `eq`, "mathematically the unpadded layout"), and no clause states its item set; (b) the
   decomposition it was commissioned to perform — how much of R0's defect is padding — **has been
   performed** at the candidate-score level, in the guarded fixed-sample path, and is accepted: the
   fp32 padding term is ≤9.61e-5 nats with 0 argmax disagreements in all 10 cells (§14.9 item 6), the
   bf16 padded and unpadded layouts are the same distance from `exact` (0.74 against 0.74 and 0.81,
   §14.6 item 5), and the precision term is the whole of it (0.0989 to 0.657 nats, 0 to 10 Kev-rule
   argmax disagreements per cell); (c) the full-set version costs 2x to 12x the first half of the
   erratum on the suites it would run on (measured per-mode fp32 rates,
   `r3_runs/scorer_r3/an_fp32.json`: `exact`/`rp` 3.3x to 20.8x, `eq_a`/`rp` 1.8x to 6.5x over five
   cells), which is one to two orders of magnitude more than the measurement it qualifies, for a
   document that has no pass bar and no stopping power.
   - **Where the phrase survives anywhere in this file, "unpadded bf16" means mode `exact` on the
     §14.6 item 3 fixed samples** — §14.2's definition, the earlier and more literal one — and not
     `eq`. No clause of this file commissions a full-set bf16 pass in any layout.
   - **What is withdrawn is a measurement, not a statement.** The erratum **carries in its text** the
     decomposition the second difference would have computed, each figure with the file it comes
     from: the fp32 padding bound, the bf16 padded-versus-unpadded equivalence, and the bf16-to-fp32
     precision gap, as listed in (b). Every figure in that list comes from the fixed-sample path
     whose loader refuses files that do not match their sidecar (item 9 below), and none from the
     path with the defects of items 5 and 6 below.
   - §14.5 item 1 (ii) accordingly reports **one** difference, (padded bf16 rerun − fp32), metric by
     metric, with the (i) verdict stated beside it, which is what `r3_code/harness_identity_r3.py`
     `erratum()` implements. The erratum's two headline sentences (§14.9 item 6) are unchanged.

2. **§14.5 item 4 step 1: the erratum leaves the gating step (ruling §3, §6).** Step 1 is replaced by:

   > 1. K0 on `Qwen3.5-0.8B-Base` and `Qwen3.5-0.8B` with the admissible scorer, both tracks, all
   >    degenerate arms, and the item 1 (i) pinned identity check. **The item 1 (ii) erratum
   >    measurement is not part of this step**: it has no pass bar and no stopping power by its own
   >    terms, no comparison of this round reads it (the R0 side of every R3 comparison is a
   >    re-score, §14.2, §14.9 item 6), and its output is an artifact of `R0-BASELINE-RESULTS.md`. It
   >    is owed under §14.11 item 3 and is not a condition of wave 1. The (i) identity check keeps
   >    its place and its round-stopping power in full.

   This is an amendment and not a reading: step 1's wording as it stood admitted no split, and nobody
   is to reach this conclusion by interpreting it. Committed before wave 1 launches.

3. **The erratum's deadlines, and what wave 1 may not claim while it is outstanding (ruling §6.3,
   §6.4).** An obligation with no deadline is how a pending erratum becomes a permanent one, so both
   deadlines below are tied to events that must occur, not to dates.
   - **The erratum is published to `R0-BASELINE-RESULTS.md` before the first test read of the round**
     (§8.4, the first line appended to `TEST-READS.log`), and in any case before any report of record
     of round 1 is committed. The test lock is the round's point of no return.
   - Both this deadline and item 4 below's are listed **in `R0-BASELINE-RESULTS.md`'s erratum-pending
     note**, with their deadlines named, so the owed work is visible in the document that is owed it;
     and `tools/watchdog.py` flags each as outstanding in every digest until its product exists.
   - **While the erratum is outstanding, no number of this round is compared with R0's published
     numbers in any direction**, including in a wiki entry or a commit message (§14.2 is not
     suspended by the erratum being late; it is the reason the erratum exists), no sentence states
     R0's own defect magnitude beyond the headline already published in that file, no claim is made
     about R0 §12.1's length effect, whose "do not retest it" stays suspended (§14.9 item 6), and
     §6.3's B-4 for K1-PT against R0 is not reported (item 4 below).
   - **Every report of record of wave 1 states in one line that the R0 erratum is outstanding and
     which claims it therefore does not make.** Admissible with it outstanding: all Track K dev
     numbers of every wave-1 arm from the scorer of record, with the §14.9 item 5 near-tie census and
     §10.1's counts; §9.1 K-align and §9.2 K-floor in their absolute forms, which compare an arm
     against a fixed line or against the arm's own question-only comparator rather than against R0;
     §8.2 (a) and (b); the §14.10 items 8 and 13 replicate floors; §14.4's K1-FLA ladder-kernel band,
     which is arm-against-arm; and every training-performance and throughput figure (§10.2 as
     extended by item 12 below).

4. **The R0-configuration fp32 re-score is named as the gate it already is: on adoption, not on
   launch (ruling §6.2).** §14.5 item 1's R0 side — `Qwen3.5-0.8B` re-scored by the scorer of record
   under the R0 configuration of §6.3 — is the fp32 side `erratum()` requires
   (`track_t_config == "r0"`, arm K0, R0's model path), and it **does not exist**: the running
   `r3_runs/k0_fp32` is `track_t_config = "r3"` (`instruct/RUN_IDENTITY.json`). It needs 102,654
   records per role (`track_t_r3.records_needed`, `CONFIG_R0`; recounted 2026-10-30). Four clauses
   read it, all of them at selection and adoption time and none of them to launch a training run:
   - **§8.2 (c)**, whose **gating cells** are "the `typed-decisions` T1 cells that are not void under
     R0 §13.5 for either model", and whose R0 §13.5 verdicts §14.5 item 1 requires to be recomputed
     on this re-score. **Until the re-score exists, §8.2 (c) has no population, and no arm is adopted
     under §8.2.** An arm may be reported as clearing K-floor and as winning (a) and (b); it is not
     reported as adopted.
   - §6.3's B-4 for K1-PT against R0, computed against this re-score only; and R0 §13.5's recomputed
     B-2 pass/void verdicts, which are also what defines §8.2 (c)'s population above.
   - §14.5 item 10's R0 §12.1 length-effect retest in fp32 (§14.9 item 6).

   **§9.2 K-floor is not a reader of this re-score** (ruling §18, correcting the ruling's own §9
   item 4): §9.2 compares every seed of every trained arm against the constant arm (§5.1) and against
   the test-time question-only arm (§5.2), both of which are wave-1 Track K dev arms from the scorer
   of record. Neither is R0, the re-score, or anything under the R0 configuration, which is why item 3
   above lists K-floor in its absolute form as admissible while the erratum is outstanding. The
   struck reading was a conflation with R0 §13.5's B-2 verdicts, which sit beside it in the same list
   and do depend on the re-score. It is recorded rather than quietly dropped because a clause that
   names a dependency which does not exist teaches a later reader to distrust the ones that do.

   **Deadline: produced and read before the first §8.2 adoption decision of round 1, and before
   `FINAL.json` is written for 0.8B.** It is **not** a launch gate for wave 1, and it does not
   contend for wave-1 chips: §14.10 item 8's arithmetic leaves six of eight chips idle from about
   t = 1.9 h of the wave and this pass needs about three. That chip count is **provisional** in
   item 12 below's sense: it is an availability argument extrapolated from the fp32 `rp` rates,
   not a sizing decision. The run plan sets the count and may set it higher or lower; this clause
   establishes only that the pass need not wait for wave 1. It is a run of record and obeys
   §14.5 item 4 step 2 (a): it does not share a chip with a training run of record. **It has no
   run plan.** Nobody has sized or scheduled it, it was invisible until it was traced through
   §8.2 (c), and it comes due
   weeks of wall-clock sooner than it feels, which makes it the single obligation of this amendment
   most likely to be forgotten. That sentence is in the pre-registration because a clause that
   records its own forgettability is the only defence against it.

5. **`erratum()` asserts completeness; a reported difference on a partial item set is barred (ruling
   §1.8, §7.2).** `harness_identity_r3.py` `erratum()` intersected the keys of the two sides and
   derived its record set from whatever intersection it found, with no comparison against an expected
   count; a probe produced `n_shared_items = 330` against 102,654 needed per role and the function
   did not complain. A partial fp32 side therefore reduces **both** blocks consistently, so the
   difference stays internally coherent and reads as reassuring. Required before the erratum is
   produced: the shared key set **equals** `records_needed(records, CONFIG_R0)` for every role,
   asserted, with the function **refusing loudly** and writing no document otherwise; the expected
   and actual counts are recorded in `ERRATUM-DIFF.json` beside `n_shared_items`. **"The difference
   is small" is admissible only with this assertion green**, since without it small is
   indistinguishable from absent. A test naming this clause asserts the refusal on a deliberately
   truncated side.
   - *Built and accepted (ruling §11.1), before this ruling arrived:* `_completeness` requires the
     fp32 side of every role to hold exactly `records_needed(records, CONFIG_R0)` and the padded side
     to hold all of them, raising `ErratumRefused` naming the role, the count held, the count needed,
     the number missing and three example keys; the intersection logic is gone. The asymmetry is
     deliberate and is explained in the code: the padded side legitimately holds more rows than
     `records_needed(CONFIG_R0)`, and the extras are inert (item 18 below).

6. **Readout provenance lives inside the readouts, the consumer recomputes what it checks against,
   and no readout file is hand-seeded (ruling §1.9, §7.3, §7.4, §11.1; §13's restatement,
   applied in place of the ruling's §9 item 6).** The defect: `read_admissible_rows` globbed
   `trackt/readouts`, took the role from the filename and read rows with no validation, while
   `erratum()` validated only three fields of a sibling `RUN_IDENTITY.json` (`track_t_config`, `arm`,
   `model_path`). R3 Track T readout files **carried no header at all** — provenance existed at run
   granularity (`RUN_IDENTITY.json`'s `model_sha256`, `report.json`'s header) and at no finer
   granularity, so the enforcement unit was the directory and any file placed in it inherited the
   directory's claimed identity. A directory holding the **Base** model's `track_t_config = r3` smoke
   readouts beside a `RUN_IDENTITY.json` claiming the R0 model and `r0` was **accepted** by the real
   `erratum()`, which produced `argmax_changed` of 142, 210 and 203 and a maximum probability gap of
   0.79 — a confident, plausible, positive result of exactly the shape the withdrawn padding defect
   would have had. The remedy, built before this ruling and accepted by it, is
   `r3_code/provenance_r3.py`, and the pre-registration requires what that module implements:
   - every readout row produced by `full_eval_r3` carries `m`, the first 16 hex of the sha256 of the
     model that produced it;
   - every producing process writes `manifests/<tag>.json` with each readout file's sha256 and row
     count, the full model sha256, and the scorer descriptor (mode, dtype, hf32, token_budget,
     record_grade);
   - the consumer **recomputes the expected model sha256 from the weights on disk**
     (`testlock_r3.model_identity`) and never takes it from `RUN_IDENTITY.json`, and `verify()`
     requires: `RUN_IDENTITY`'s model sha equal to the recomputed one, every readout file listed in a
     manifest with matching sha256 and row count, the manifest's model sha equal to the recomputed
     one, the manifest's scorer being the scorer of record, every row stamped with the expected
     model, and no key twice in a role.

   **Principle, carried in the pre-registration's own voice because it generalises past this
   instrument:** *a gate whose only evidence is written by the thing being gated is no gate.*
   **No readout file of record is written by hand, copied or seeded from another run**, whatever its
   numerics permit. This is why the erratum does not reuse K0's instruct readouts as its fp32 side:
   46,215 of the 102,654 records `CONFIG_R0` needs are already in `CONFIG_R3`'s 46,342 (recounted
   2026-10-30 over 119,690 T1/T2/T3 records), and the layout difference on the `T1__*/r0model` cells
   is 2.15e-5 to 4.63e-5 against 0.10 to 0.66 nats being measured, so the numerics did permit it —
   but reuse means placing files in `trackt/readouts/` that the run did not produce, which is
   operationally indistinguishable from the spoof above, and an instrument that cannot tell them
   apart must be fed neither. Once this item's provenance is implemented and asserted, reuse of
   identically-configured rows **by key** becomes admissible again, because the seeded file must then
   carry and prove the identity it claims; recorded now, before a later re-score's cost makes the
   point tempting to argue. Tests naming this clause assert the refusal of a mislabelled directory
   and of a partial side, and item 15 below applies to both.

7. **The (i) identity verdict is admissible only if it compared the report (ruling §8.2).**
   `identity_check()` compares the derived report only `if os.path.exists(rp)`; otherwise it can
   return **IDENTICAL** on the readout comparison alone with `report_compared: false` in the document,
   while §14.5 item 1 (i) requires the derivation to reproduce `r0_baseline_rederived/report.json`
   for every metric the tie rule does not affect. An (i) verdict with `report_compared` false is read
   as **INCOMPLETE** regardless of its readout comparison, and the run is not complete. This is a
   check on a field of a file after the run and requires no edit to live code.

8. **The (i) code path was frozen in fact; the freeze clause is narrowed to that, with the evidence
   named (ruling §8.1, §10; §13's restatement, applied in place of the ruling's §9 item 8).**
   `harness_identity_r3.py` was edited while the pinned control ran — sha1
   `51070298f8ab89d1ca8aaeb02f18d49dbb738919` at launch (frozen snapshot
   `r3_runs/k0_fp32/code/harness_identity_r3.py`), sha1 `e01d57460958ad6ac45b5f691b3816b0f35c19a6`
   at 07:17Z. The (i) verdict remains attributable, by diff rather than by assurance: **every hunk is
   at line 407 or later**, so `r0_pins`, `compare_headers`, `compare_readouts`, `compare_reports`,
   `classify`, `identity_check`, `read_padded_rows` and `read_admissible_rows` are byte-identical
   between the two files, the argument parser and `main` are unchanged, and the two new imports are
   inside `erratum()` rather than at module scope. Both hashes and that diff are recorded in the (i)
   run's record.
   - **Standing, forward**: an edit to an instrument between a control's launch and its verdict is
     made only in a region the verdict's code path does not reach, and the **diff against the frozen
     snapshot is produced before the edit, not after it**. If no frozen snapshot of the instrument
     exists, the edit waits for the verdict. Had a hunk landed at line 300 here, nobody would have
     known until a DEFECT verdict had to be explained.
   - The ruling's §8.1 instruction that **no** edit be made at all is superseded by this item, on the
     ground that the edit was confined and the confinement is checkable. Its other three provisions
     stand: items 5, 6 and 7 above apply to `erratum()`, nothing inside the pinned run's directory is
     touched, and the run is not restarted.

9. **§14.9 item 3, annotated: the loader's refusal is path-local (ruling §8.3).** The §14.9 verdict
   table was accepted partly on the strength of a loader that refuses a score file whose `sample_sha1`
   or per-item `keys` do not match its sidecar, and that refusal was verified by the reviewer over all
   140 fp32 score files in 10 cells. **The verdict table is unaffected** and no number is withdrawn:
   it was produced and read through `sample_r3` / `measure_floor` / `fp32_verdict`, which do implement
   that refusal (`measure_floor.py:134-136` and `:160`; `fp32_verdict.py`'s strict loading, which also
   refuses non-harness-written sidecars and cross-checks gold by key). What is corrected is the
   **scope of the stated reason**: that refusal is a property of the **fixed-sample path only**.
   `harness_identity_r3.py`'s `read_admissible_rows` has no equivalent of its own — the erratum
   path's provenance comes from `erratum()`'s own `provenance_r3.verify` call (item 6 above), not
   from the reader — and `read_padded_rows` validates nothing either; its guarantee is comparison
   against R0's own published files, which is adequate and different. A later reader must not inherit
   "the loader refuses mismatched files" as a property of this round's harness.

10. **Standing clause, commissioned measurements, added to §10 (ruling §4.3).** Carried in full:

    > **A commissioned measurement is specified and priced before it is ratified.** Any clause of this
    > pre-registration that **commissions a measurement** — as distinct from one that sets a bound —
    > states, in the amendment that creates it: (a) the **instrument**, in terms this file has already
    > defined, and the **item set**; (b) an **order-of-magnitude cost** in chip-hours, with the rate
    > and the window it was extrapolated from (§10.2 as extended by §14.11 item 12); and (c) the
    > **decision the number could change**. If (c) is "none", the clause is **documentation**: it is
    > scheduled with a deadline tied to an event that must occur, and it is **not placed in a step
    > that gates another step**. A clause that cannot answer (a) is not executable and must not be
    > ratified; a clause whose (b) exceeds the measurement or decision it qualifies is re-scoped
    > before it is ratified, not after it is attempted.
    >
    > Reason: a clause that sets a bound is checked against the noise floor (§14.1's precedent, and
    > the standing project rule that an equivalence threshold needs a measured same-config replicate
    > floor first). A clause that commissions a measurement has no such check, and fails in its own
    > ways — naming an instrument the file defines two ways, leaving the item set open, costing more
    > than the decision it informs, or informing no decision at all. All four occurred in one sentence
    > of §14.6 item 5.

    Counterfactual, as §10's declaration clause requires: applied to §14.6 item 5's second difference
    this clause **fires on all three questions** and the clause would not have been ratified in the
    form it was. Applied to §14.5 item 7's admissibility bar it is **silent**, because that was a
    tolerance and is covered by the replicate-floor rule instead. One hit, one miss, and the miss is
    covered elsewhere. The two defects are the same family and different members: §14.6 item 1's bar
    was unsatisfiable **by construction**, while §14.6 item 5's second difference was
    **underspecified and unpriced**. What they share is that both were ratified without anyone asking
    whether they could be carried out as written.

11. **Standing clause, acceptances and path-local guarantees, added to §10 (ruling §8.4).** Carried in
    full:

    > **A guarantee cited in an acceptance is demonstrated in the path the accepted artefact took.**
    > Any acceptance of a result that cites a mechanism as a reason to trust it — a refusing loader, a
    > green test suite, a validating header, an assertion — names the **file and function** that
    > implements the mechanism and the **code path the accepted artefact actually travelled**, and
    > states whether sibling consumers of the same data have an equivalent. Where they do not, the
    > acceptance says so, and the gap becomes a **named obligation** rather than an assumption. An
    > acceptance may not cite a mechanism as a property of "the harness".
    >
    > Reason: three of this round's instrument defects have the same form — a check present in one
    > code path, absent in a sibling, and cited as general: the fixed-sample loader's sidecar refusal
    > against `read_admissible_rows` (§14.11 items 6 and 9), the scorer-of-record selection remapped
    > in a second entry point (§14.11 item 13, the clearest of the three), and §14.9 item 8's
    > green-suite claim, which was true of the artefact and false of the suite. In each case the
    > artefact survives scrutiny and the sentence justifying it does not, and the next artefact
    > through the sibling path inherits a guarantee it never had.

    Counterfactual: applied to the §14.9 verdict table's acceptance this clause reaches the **same
    verdict** — accept — and adds one sentence naming `fp32_verdict.py`'s strict loading and the
    absence of an equivalent in `read_admissible_rows`. It changes no verdict in this round's history.

12. **§10.2 extended: a rate carries the window it was measured over (ruling §5).** §10.2's
    requirement that every throughput figure be per chip with the chip count stated is extended:

    > Every throughput figure and every ETA derived from one also states the **window** it was
    > measured over — wall-clock span and item count — and **excludes warm-up**. On the Ascend hosts
    > the first steps of any job are dominated by TBE operator compilation and are not the rate: a
    > figure taken from the first seconds of a unit, or from fewer items than a warmed-up batch, is
    > labelled **provisional** and may not be carried into a scheduling or sizing decision. Where a
    > heartbeat already emits a windowed rate (`ex_s_chip_w20`), that is the figure of record.

    Occasion, recorded because the correction is part of the record: K0 was first estimated at 15 h
    from throughput lines read in the first 30 seconds of each file; the measured rate was about 13x
    higher (`K_base_decision_dev_clean`: 1,264 rows in 529 s, 2.4 rows/s/chip). The engineer traced
    the error to its cause and corrected it **before the number was used irreversibly**, and the
    joiner sized against the stale estimate was disarmed with `r3_runs/k0_fp32/JOIN_DISARMED.json`
    recording the cause, the state left behind, the preserved re-arm mechanism and a checkpoint time.
    Counterfactual: this clause creates a new obligation and decides nothing retroactively; the stale
    estimate was corrected by the engineer, not by this rule. Two prior measurements of this round
    (§14.10 items 3 and 6) were also taken over a handful of steps, and §14.10 item 6 already says
    that is the window in which the quantity is not yet stable; this clause generalises both.

13. **The `eval_r3.make_score_fn` silent downgrade: fixed, blast radius zero, verified (ruling
    §15.1).** Until 2026-10-30 `make_score_fn` mapped every `--scorer` other than `exact` and `fast`
    to `exact`, so the scorer of record named by §14.9 item 3 **could not be selected through the
    `--full` readout entry point**: `--scorer rightpad` ran the exact layout. The line now reads
    `mode = "exact" if a.scorer == "hf" else a.scorer`, the defect is recorded in the function's
    docstring, and `--require-record-grade` refuses any configuration that is not the scorer of
    record, on the flags **read back** from torch rather than as requested.
    - **Nothing of record is affected and no number is withdrawn.** The 140 fp32 score files behind
      the §14.9 verdict table were written by `measure_floor.save`, which imports `scorer_r3` and
      `sample_r3` directly and calls `R3Scorer(...).score_enc(enc, "rightpad", token_budget=16384)`;
      the frozen `fp32/code/SHA1SUMS` and `fp32/code2/SHA1SUMS` carry bit-identical `scorer_r3.py`
      (`d4ad2661…`) and `sample_r3.py` (`6f1277f9…`), so the defect lived in a function neither wave
      imported. The only pre-fix `--full` runs are two CPU dry runs with `--scorer fast`, which the
      old mapping handled correctly. **K0 of record runs the fixed code**: `r3_code/eval_r3.py` and
      `r3_runs/k0_fp32/code/eval_r3.py` are both sha1 `b33a8be84a10f3823fa20f3bfdf95c5c346ccf72`
      (verified by the reviewer). §14.5 item 5's `eval200_rp_*` citations ran the single-partition
      `score_rightpad`, which the defect does not touch.
    - *Dated note, 2026-10-30 08:20Z, while K0 was still scoring.* **The live copy's hash above is
      now stale and the claim it supports is not.** `r3_code/eval_r3.py` moved to sha1
      `ee363143eb37be4df24c1f1304d7b5eb9c1fc5ab` when item 22 below was implemented; the frozen
      `r3_runs/k0_fp32/code/eval_r3.py` is **untouched at `b33a8be8…`**, and K0's worker invokes
      `os.path.join(run, "code", "eval_r3.py")` with `python3 -P`, so the run of record cannot reach
      the live file at all. That is stronger than §14.11 item 8's standing rule requires — the rule
      asks that a mid-flight edit be confined to a region the verdict's code path does not reach,
      and here the edited file is not on the path. `make_score_fn` and `score_model` were
      additionally verified byte-identical between the two copies after the edit. What item 8 was
      **not** given is its diff before the edit rather than after; the edit is admissible on the
      frozen-snapshot ground above, and the sequencing lapse is recorded rather than waived. This
      note exists because a later reader re-checking the two hashes would find one of them failing
      on the round's most sensitive claim, and would have to reconstruct why.
    - **It is the third member of item 11 above's class**, and the clearest: the guarantee "the
      scorer of record is selected by `--scorer rightpad`" was true in `measure_floor`'s path and
      false in the readout entry point, and the suite whose greenness §14.9 item 8 cited never
      imported the file the defect was in (item 21 below).

14. **A withdrawn false alarm, recorded rather than deleted (ruling §10).** It was escalated to the
    reviewer that `harness_identity_run.sh`'s trailing call could write an erratum difference on an
    incomplete item set at about 09:00Z. **That is false and is withdrawn.** The trailing call is
    `compare`, i.e. `identity_check()`, which never calls `erratum()`; `erratum()` is reachable only
    through its own subcommand, requires `--admissible-run`, and refuses without an
    `IDENTITY_VERDICT.json` — verified by the engineer running it against the live directory, where it
    refused and wrote nothing, and independently by the reviewer from the source. `identity_check()`
    already enforces completeness against R0's **published** readout set rather than against an
    intersection (`missing_files`, `rows_missing`, `rows_extra`, and `classify()` returning INCOMPLETE
    with exit 5), which is a stronger check than the one the alarm asked for. The alarm is recorded
    because it caused a code change to be ordered on a live pinned control, and the engineer's earlier
    wording, which invited the erratum reading, is recorded as its cause. **Nothing about the
    completeness defect of item 5 above is withdrawn**; only its reachability through that path was
    wrong.

15. **Standing clause, guards and mutation, added to §10 (ruling §11.2).** *Sharpened by item 21
    below, which adds a paragraph to this clause's text: the mutation must be applied to the path
    that produces the number, and a test that asserts only on a self-description is not a test of
    behaviour. Read the two together; the sharpening is part of the clause, not a gloss on it.*
    Carried in full:

    > **A guard that gates a number ships with a demonstration that its test fails when the guard is
    > removed.** For every check whose failure is supposed to stop a number being reported — a
    > completeness assertion, a provenance verification, an admissibility bar, a refusal — the run
    > directory holds a short mutation script that disables the guard and shows the test that covers
    > it then **fails**, with the output recorded. A test that still passes with its guard disabled is
    > **too weak and is rewritten**, not annotated.
    >
    > Reason: this round has produced a resume test that passed for the wrong reason (§14.10 item 6)
    > and a green suite asserting a property that had been retired (§14.9 item 8). Both would have
    > been caught by the one question a mutation asks — does the test fail when the thing it tests is
    > removed? It is the guard-level analogue of §10's counterfactual declaration: determinate,
    > computable from what is in hand, impossible to game, and it converts "the test passes" into
    > "the test passes **because** the guard is there".
    >
    > Scope: guards that gate a number, not every unit test. `r3_runs/k0_fp32/analysis/k0_mutation.py`
    > is the model — two guards disabled, two tests shown to fail, `MUTANT CAUGHT` printed for each.

    Counterfactual: a new obligation, so §10's declaration clause does not apply. Applied backwards it
    would have caught §14.10 item 6's resume test and §14.9 item 8's retired assertion; neither
    verdict of this round changes, because both were already corrected by other means.

16. **Standing clause, guards declare their threat model; an extension of item 11 above, added to §10
    (ruling §11.3).** Carried in full:

    > **A guard is documented with what it does not stop.** Every check introduced to make a number
    > trustworthy states, where it is implemented and wherever it is cited, the class of failure it
    > defends against and the class it does not. A provenance check that defends against accident — a
    > wrong directory, a copy, a stale shard layout, a partial run, a different scorer — says so, and
    > says that it does not defend against deliberate, consistent rewriting of rows, manifests and
    > identity files together, which nothing on a shared filesystem can.
    >
    > Reason: §14.11 item 11's defect seen from the other end. That item governs what an acceptance
    > may cite; a guard whose limits are unwritten supplies the overclaim that an acceptance then
    > cites, and the citation is load-bearing before anyone rechecks it. §14.9's acceptance resting on
    > a refusal that existed in one path is the instance that cost this round the most; a guard
    > described without its threat model reaches the same place by the same route.
    >
    > `r3_code/provenance_r3.py`'s docstring is the model: it states the defect that prompted it, the
    > three places provenance now lives, and the limit, in the file a reader will open.

17. **K0's readout provenance: verified by reproduction, not re-run, and the verification is
    pre-registered here (ruling §12).** `r3_runs/k0_fp32` is the round's first readout of record and
    was launched from the pre-stamping snapshot: its rows carry no `m` stamp and it has no
    `manifests/`. Its scorer configuration **is** guarded in flight (`--require-record-grade`, mode,
    dtype, HF32 and token budget read back from torch, `record_grade` in the header); its readout
    provenance is not. **K0 is not re-run** — a re-run would buy a producer-written stamp, while a
    re-score demonstrates the binding a stamp only asserts, and K0 admits the stronger instrument for
    minutes of one chip against about four hours of five on the critical path. **K0 is not
    grandfathered either**, and the shape of that decision is stated plainly rather than left for a
    reader to discover: this verification was devised after K0 launched and while it was still
    scoring, so it is a bar set on a run already in flight. What keeps it from being a bar shaped to
    its own data is that the bar is **§14.6 item 3's existing one**, reused rather than invented, and
    that the sample rule, the counterpart and the consequence are all fixed here before any of the
    three numbers exists (rule 3).
    - **Item 19 below is this item's control, not an addition to it**, because the 64-item re-score is
      itself one or two calls of `full_eval_r3.SCORE_CHUNK = 32` against stored rows that came from
      32-question calls at unknown offsets, so this comparison **already crosses compositions**. The
      two items are **one job with one marker file**, run in this order: item 19's `rp_c32` and
      resume-offset cells, then this item's re-score with its cross-model counterpart, then item 7
      above's `report_compared` check on the (i) verdict. Those three are what gate K0's numbers
      being read, and all three are minutes on the one chip K0 itself frees.
    - **Before any decision reads K0**, and on a chip freed by K0 before wave 1 launches: 64 items per
      (checkpoint, suite) cell over decision-v7 dev, transfer-v4 dev and the three T1 sources, drawn
      from K0's **finished** readouts by `numpy.random.default_rng(20261030)` over sorted keys, for
      both checkpoints, the sample and its sha1 written before the re-score; re-scored by the stamped
      harness with the scorer of record on the weights K0's `RUN_IDENTITY.json` names, with the model
      sha256 recomputed from disk.
    - **Bar, unchanged from §14.6 item 3**: max |Δ| per candidate against the stored scores
      ≤ τ_s = 1e-3 nats and **0 argmax disagreements** under either tie rule on items whose stored
      top-2 gap exceeds τ_s, with items at or below τ_s counted and listed (§14.9 item 5).
      Bit-identity is **not** required and not claimed: the sample's batch composition differs from
      the production pass, and the measured same-precision layout differences on these suites are
      1.81e-5 to 1.26e-4.
    - **Discrimination counterpart, mandatory (rule 2)**: the same sample re-scored on the **other**
      checkpoint must **fail** the bar. A verification that passes for any model measures nothing,
      and this round has already produced three by-construction zeros. If the counterpart passes, the
      verification is void and the fault is in the verification, not a finding about K0.
    - **Consequence, fixed before the numbers**: a failing cell's K0 readouts are **void and
      re-scored**; the bar is not relaxed and the failure is not explained away (§14.1 and §14.4's
      precedent). More than one failing cell re-runs K0 in full from the stamped snapshot.
    - **Also produced**: a post-hoc `manifests/` for K0, carrying in the file the sentence that it
      attests the files as they stood when it was written and **not** their origin, the re-score being
      what attests origin (item 16 above). Writing the manifest without that sentence would create
      precisely the overclaim item 16 exists to prevent.
    - **Why this is an input to wave 1 and not a side quest, with K0's roles stated correctly**
      (ruling §18, correcting the ruling's own §12.3): K0 is **not** the comparator for §9.2's
      question-only line — §14.5 item 4 step 2 fixes that comparator as **the arm itself**, which is
      why every trained arm is also scored with `input_mode = drop` and `blank`. K0's actual roles in
      wave 1's claims are §6.3's B-4 against the **same base checkpoint** and the §5 degenerate
      baseline reported beside every trained number. The conclusion stands on those roles: K0's
      numbers enter wave-1 claims, so verifying their provenance is on the critical path.
    - **Forward, and this is the part that closes the class**: no run of record launches from a
      snapshot without stamping, and **every** reader of readouts of record verifies provenance, not
      only `erratum()`. The readers are named here so the next one is not forgotten silently:
      `erratum()`, `full_eval_r3`'s report stage, `select_r3`, `testlock_r3` at the §8.4 test read, and
      any analysis that produces a reported number. A reader added later is added to this list in the
      amendment that adds it. **The preferred implementation is for the reader to verify, not its
      caller**: `read_admissible_rows` itself calls `provenance_r3.verify`, so the guarantee travels
      with the reader. As things stand it is `erratum()` that calls `verify`, so the guarantee is
      demonstrated by the caller and will break the moment a second caller appears (item 9 above,
      item 11 above's class).

18. **A reading note for the erratum, ratified before the erratum exists (ruling §12, from
    `r3_runs/k0_fp32/analysis/k0_reconcile.py`).** `tau_fit.<role>.carveout_rows` counts every row the
    τ splitter puts on the TRAIN side, fitting or not. R0's published report counts **83,005** (every
    group70 train-side row R0 scored, including 17,036 T2 non-base variant rows that
    `thresholds.fitting_row` rejects); a measurement over `records_needed(CONFIG_R0)` counts
    **65,969**. The fitted τ, every cell and every decision line are identical either way (3 of 13,945
    leaves differ, all of them this row-count field). **A difference in this field against the
    published report is not a discrepancy**, and in the erratum difference specifically both sides use
    the same rows. This is ratified now, before any erratum or (i) verdict exists, precisely so that it
    cannot be produced as an explanation after a difference appears; it lives in the pre-registration
    and not only in a code constant and a README. The check it rests on is
    `r3_runs/k0_fp32/analysis/k0_reconcile.py`, a chip-free comparison against R0's published
    readouts, and it is **not** a readout of record.

19. **The composition of record is measured, and it is the control that makes item 17 readable
    (ruling §15.3).** Under `--full` the entry point scores in calls of
    `full_eval_r3.SCORE_CHUNK = 32` questions in stored order, and `core_r3.score_resumable` chunks
    the **remaining** rows, so a resume **shifts the call boundaries** (70 rows fresh: 32/32/6; after
    10 stored: 32/28; after 33: 32/5). The §14.6 item 3 fp32 table measured `rp_a` (whole sample),
    `rp_b` (2048 budget), `rp_chunk` (stored-order 64) and `rp_rev` (reversed 64): **no 32-question
    composition and no resume-shifted composition is in it**, while K0 of record is resumable at item
    granularity, so its realised boundaries are not recoverable from its own files.
    - **Required before K0's numbers are read**, merged into item 17 above's job: on the same §14.6
      item 3 fixed samples, one chip, add an **`rp_c32`** cell (stored-order 32-question calls) and
      **one resume-offset** cell (the same sample with a non-zero number of rows pre-stored, so the
      first call is short), measured against fp32 `exact` at the **unchanged** §14.6 item 3 bar:
      max |Δ| per candidate ≤ τ_s = 1e-3 and 0 argmax disagreements under either tie rule on items
      whose `exact` top-2 gap exceeds τ_s.
    - **Why it is a precondition and not an addition:** item 17's 64-item re-score is itself one or
      two calls of 32, while the stored rows came from 32-question calls at unknown offsets, so item
      17's comparison already crosses compositions. Without these two cells, a failure of item 17's
      bar could not be attributed between a provenance fault and ordinary composition noise — the
      same confound §14.5 item 1 (i) exists to prevent for the erratum.
    - Expected to pass with margin (worst measured composition spread 1.13e-4 against 1e-3). **An
      expected pass is not a reason to skip a measurement; it is the reason it is cheap.** If either
      cell fails, K0's readouts are void for the affected suites and the bar is not relaxed.
    - Devised, like item 17 above, after K0 had launched and while it was still scoring, and recorded
      as such: it is a control added to a run already in flight. What keeps it from being a bar
      shaped to its own data is that the bar is §14.6 item 3's, unchanged, and that both cells and
      the consequence of failure are fixed here before either number exists (rule 3).

20. **§14.9 item 3's code citation names both frozen copies and states what differs (ruling §15.2).**
    §14.9 item 3 quotes `measure_floor.py` `44d80526…`, the `fp32/code2/` copy, while the fp32 runs
    used two frozen copies: `fp32/code/measure_floor.py` `c39122c3929439449697f65856e23f5bac02cc24`
    and `fp32/code2/measure_floor.py` `44d80526d4a9238d6c55567a0ab3dfe1584e7375`. Both are cited,
    with this statement of the difference, verified by diff: **two hunks, confined to the `exact`
    mode's parallelisation** — the added `--exact-shard K/N` argument and the part-file merge with
    resume-key checking and timing. No candidate mode (`rp_*`, `fast_*`, `eq_*`, `r0`) is touched,
    and `scorer_r3.py` and `sample_r3.py` are **bit-identical** between the two copies, so **no score
    value in any cell can differ by wave**. `exact` vs `exact2` bit-identity in 10 of 10 cells (§14.9
    item 4) is the measurement that covers the one thing the difference could have touched. A
    file-to-wave mapping of the 140 score files is **not required and is a declined action, not an
    open one**, because it cannot change a number; it becomes required if any later document cites
    the **harness** identity rather than the **scorer** identity, and `exact.part.s*` naming
    distinguishes the waves on disk.

21. **Item 15 sharpened: a mutation must hit the path that produces the number, and a
    self-description is not behaviour (ruling §15.4).** Added to item 15 above's clause text, and
    read as part of it:

    > The mutation is applied to **the code path that produces the number**, not to a metadata or
    > self-description path. A test that asserts only on a handle's own description of itself — a
    > `describe()`, a header, a recorded configuration — is **not** a test of the behaviour it
    > describes, and a mutation that such a test catches certifies the description only. Where a
    > guard exists to ensure a computation is performed one way, its test calls the computation and
    > observes what was actually passed to it.

    Occasion, and it is recorded in full because how the limit was found is the most useful part of
    it: the reviewer applied item 15 to the test written for item 13's fix and found item 15
    insufficient. `test_scorer_r3.py` never imports `eval_r3`, so the suite whose greenness §14.9
    item 8 cited could not have caught item 13's defect at all. Its replacement,
    `test_full_eval_r3.py:317`, builds the scorer handle and asserts on `describe()` **without ever
    calling it**, so a regression in which `describe()` is right and `score()` is wrong would pass.
    Reverting item 13's fix makes `describe()` report `exact` and that test does fail — `MUTANT
    CAUGHT` — **so item 15 as first written would have certified an inadequate test**: a mutation
    probes only the mutation applied, and this one hits the metadata path. `describe()` is a claim;
    `score()` is the behaviour. A guard that checks the claim and not the behaviour is item 6 above's
    principle one level down — a gate whose evidence is written by the gated party. **Required**:
    `r3_runs/make_score_fn_readback/readback.py`, which patches `R3Scorer` with a recorder and
    asserts the constructor kwargs **and the mode actually passed to `score_raw`**, becomes a test in
    `test_full_eval_r3.py`, and item 15's mutation for item 13's guard is applied to that test.
    Recorded as a limit the reviewer found in its own clause within the hour of writing it, so a
    later reader does not inherit item 15 as stronger than it is (item 16 above): a clause that
    records how it was found to be insufficient is worth more than one that reads as if it arrived
    complete, which is why the limit is written into the clause rather than into a note about it.

22. **The single-partition path stops answering to the record-grade flag names (ruling §15.5).**
    Without `--full`, `eval_r3.score_model` dispatches `--scorer rightpad` to `score_rightpad`, which
    loads the model in **bfloat16** and calls `train_r3.row_logprob_sums` — not `R3Scorer` — with no
    dedup, no HF32 control, `--token-budget` reinterpreted as `micro_tokens`, and a report header
    that records **neither `dtype` nor `hf32`**; on the same path `exact` and `fast` construct
    `R3Scorer` without passing `dtype` or `token_budget`, so both flags are silently ignored and the
    defaults apply. No readout of record comes through this path, so **nothing of record is
    affected**.
    - **It is closed, not documented.** One flag name with two meanings in two entry points, one of
      them bf16 without a precision record, is item 11 above's class in its purest form, and a
      comment does not stop the next reach for `--scorer rightpad` under time pressure. The path
      refuses `rightpad`, `exact` and `fast` unless an explicit **`--not-of-record`** acknowledgement
      is passed; with it, the header records `dtype`, `hf32` and `record_grade: false`, and every
      ignored flag is reported as ignored rather than accepted silently.
    - The path is **not removed**: it has legitimate diagnostic uses, and deleting working code after
      a result has been seen is not something this round does (§14.4's precedent, §14.9 item 1's
      reasoning). A test naming this clause asserts the refusal without the acknowledgement flag.

**Launch-checklist status (§14.7's checklist as extended by §14.8, by §14.10 and by this amendment,
ruling §6.5 and §14.2).** This is a status, not an authorisation: **wave 1 is not cleared to launch**.
Items 1, 7, 8, 9 and 10 are open, and item 10 is open because of this amendment.

| # | Checklist item | Status |
| --- | --- | --- |
| 1 | §14.7, §14.8 and §14.10 committed | **Open** — this amendment (§14.11) must be committed too |
| 2 | `gate_fast_ref/` with (G1)–(G4) **or** the recorded reference-kernel decision | **Met** — §14.10's table, unchanged by this amendment |
| 2b | (G3) on this branch, model-level **and** trajectory (§14.8 item 4) | **Met** — §14.10's table, unchanged by this amendment |
| 3 | Corrected equal-length determinism probe, green | **Met** — §14.10's table, unchanged by this amendment |
| 4 | K2 dropout-mask-semantics test, green | **Met** — §14.10's table, unchanged by this amendment |
| 5 | Production bf16 K2 cell re-measured against the (G3) floor | **Met for the branch that now trains** — §14.10's table, unchanged by this amendment |
| 6 | `bench_record.json` carrying `gdn_impl`, `k2_impl`, trainer sha256 | **Met** — §14.10's table, unchanged by this amendment |
| 7 | §14.5 item 4 step 2 chip-assignment file, sha256 recorded | **Open** — `r3_runs/w1/CHIP-ASSIGNMENT.json` is at revision 2 with its sha256 recorded but marked `DRAFT`; it is not authoritative until §14.10 and this amendment are committed, and it discharges items 7 and 9 together |
| 8 | §14.3 resume test rewritten and the suite re-run on a chip (§14.10 item 6) | **Open** — unchanged by this amendment; minutes on one chip |
| 9 | The ninth and tenth runs named in the assignment file before launch (§14.10 items 8 and 13) | **Open** — unchanged by this amendment |
| 10 | *Added by items 7, 17 and 19 above:* the three checks that gate K0's numbers being read, as **one job with one marker**, in order — item 19's `rp_c32` and resume-offset cells, then item 17's re-score with its mandatory cross-model counterpart, then item 7's `report_compared` check; plus K0's post-hoc `manifests/` with its limitation stated in the file | **Open** — new obligation from this amendment; minutes on the one chip K0 itself frees |

Outside this checklist, and still the actual gate on launching: §14.5 item 4 **step 1 must be complete
and read on dev** before step 2 begins. Item 2 above removes the (ii) erratum measurement from that
step and leaves the (i) identity check in it with its round-stopping power; the (i) verdict is
unwritten, is expected about 09:00Z, and is now additionally subject to item 7 above
(`report_compared` must be true) and to item 8 above's recorded hashes.

**Not on this checklist by design, and the obligation most likely to be forgotten: the
R0-configuration fp32 re-score of item 4 above has no run plan.** It gates the round's first §8.2
adoption decision — and therefore every adoption of round 1 — not the wave's launch, so it will not
stop anything launching and nothing downstream will notice its absence until an adoption has to be
decided. Nobody has sized or scheduled it: 102,654 records per role, at a chip count the run plan
still has to set (item 4's "about three" is provisional, per item 12). The reviewer said
twice that it is the likeliest obligation of this ruling to be forgotten, and it is repeated here
because this table is what gets read before a launch.
