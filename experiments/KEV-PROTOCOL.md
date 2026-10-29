# Kev 1.0 evaluation protocol, as implemented in the downloaded repository

Strictly factual. Every claim cites a path and line number in the local copies:

- GitHub repo `jaredpalmer/kev`, commit `2074cc44256200bb37540103fa4572901faa10f3`, at `/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev` (paths below are relative to it unless prefixed `SUITES/`).
- HF dataset `jaredpalmer/kev-suites`, revision `cc4bac803e73112689ec327ffa481c519cbc7a05`, at `/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites` (written `SUITES/`). 125 files, 295,268,087 bytes, all verified against the HF API size, LFS sha256 and git blob ids; see `SUITES/.complete`.

"Not determinable from the repo" marks what the files do not say.

## 0. Correction to the task brief: "new sources" is transfer-v4, not breadth-v1

The brief equates "new sources" with `breadth-v1`. The repo says otherwise.

- README.md:38 defines the column "Held-out datasets: index" as the chance-corrected index "scored on the test split of `breadth-v1`". That column is separate from the accuracy table.
- README.md:48: "'New sources' means datasets and policy rules Kev never saw during training." The numbers in the "Accuracy: New Sources" column are transfer-v4 numbers: `docs/releases/kev-1.0.md:19-20` ("Out-of-domain: transfer-v4 development accuracy 0.648 / 0.817 / 0.820 / 0.851 / 0.857", "transfer-v4 locked test accuracy / Brier 0.697 / 0.397 ..."), `docs/model-cards/kev-0.8b.md:181-182`, and `docs/claims.json` (entries with printed 0.648 and 0.697: paths `candidate.transfer_dev.acc` and `candidate.locked_transfer.acc` of `runs/release/kev-08b-r15.json`; the README entries cite `transfer.clean.acc` of `runs/r15-08b/00-trial-0/result.json` and `suites.transfer.clean.acc` of `runs/locked/kev-08b-r15-ungated/summary.json`).
- `runs/locked/kev-08b-r15-ungated/summary.json` gives `suites.transfer.suite = evals/v4/transfer-v4`, `clean.n = 656`, `clean.acc = 0.6966463...` (= 457/656); `suites.decision.suite = evals/v7/decision-v7`, `clean.n = 1200`, `clean.acc = 0.8375`.
- breadth-v1 accuracy for Kev-0.8B is reported separately: `docs/model-cards/kev-0.8b.md:176-178` (development, all 14 datasets, 3,075 questions: 0.597; test, 3,089 questions: 0.586; test index 23.3).
- Consequence: "Accuracy: New Sources" = transfer-v4 development / locked test (656 / 656 questions); "Accuracy: Trained Sources" = decision-v7 development / locked test (1,264 / 1,200 questions). breadth-v1 is a third panel.
- breadth-v1 partitions are NOT public. `evals/breadth-v1/manifest.json` (key `mirror_note`): the partitions "live only in this private mirror" `jaredpalmer/kev-private-evals` (HTTP 401 without credentials); the repo has only `manifest.json` and `overlap.json` for it (`ls evals/breadth-v1`). `kev-suites` contains no breadth-v1 file (125 siblings listed). The only way to obtain the items is to rebuild them from the 14 upstream datasets with `scripts/build_breadth_v1.py`; the docstring (lines 1-27) says it is deterministic and rebuilds "byte for byte" (sha256 per partition in the manifest `files`). That requires `datasets`/`transformers`/`scikit-learn`/`pandas`/`pyarrow`/`scipy`, the Qwen3.5-4B-Base tokenizer and downloads of about 0.9 GB (BRIGHT 604 MB, ChessBench 148 MB, RouterBench 100 MB, ContractNLI 65 MB, cfcolor 54 MB, others small); none of these Python packages is installed on this host (system Python 3.11, no torch/numpy/pandas), and the script requires Python 3.12+ (`pyproject.toml:13`). It was not run.

## 1. README table of results (copied verbatim, README.md:40-46)

```
| Model | Accuracy: New Sources | Accuracy: Trained Sources | Brier: New Sources |
|---|---|---|---|
| Kev-0.8B | 0.648 / 0.697 | 0.827 / 0.838 | 0.481 / 0.416 |
| Kev-4B | 0.817 / 0.838 | 0.873 / 0.865 | 0.269 / 0.242 |
| Kev-9B | 0.820 / 0.852 | 0.874 / 0.873 | 0.289 / 0.217 |
| Kev-27B | **0.851 / 0.889** | 0.865 / 0.866 | **0.225 / 0.156** |
| Jev | 0.857 / – | 0.845 / – | 0.211 / – |
```

Meaning of dev and test (README.md:48): "Each cell is **development / test**. ... We pick checkpoints using the development sets and read each test set only once per released model. Jev has only been run on the development sets of these two suites."

- development = `development.jsonl` partition of the suite, used for checkpoint selection (and, for the shipped temperature, see section 5).
- test = `test.jsonl` partition, "locked": `kev/suite.py:208-209` raises unless `--allow-test` is given; `kev/benchmark.py:182` and `:200` select it.
- Both are the `clean` variant only (section 4).
- Which checkpoint: the table scores the final released Kev 1.0 checkpoints, which went through further training stages after `decision-v7` (section 5). Kev-0.8B "Trained Sources" 0.827 / 0.838 is stated at `docs/model-cards/kev-0.8b.md:196` ("decision-v7 development (1,264) / locked test (1,200) | 0.827 / 0.838").
- Kev-0.8B/4B/9B/27B rows use the shipped temperature on the fp32 path (`docs/releases/kev-1.0.md:14`). Temperature does not change argmax (`kev/model.py:214-217`), so accuracy is temperature independent.
- The README does not state the number of seeds; one checkpoint per model.

## 2. Panels and item counts

All counts below were recomputed from the raw jsonl files and equal the counts in the suite manifests (sha256 of each file also equal).

### 2.1 "Trained sources": decision-v7 (`SUITES/v7/decision-v7/`, byte-identical to `evals/v7/decision-v7/` for dev/test/calibration)

Manifest `files` (`evals/v7/decision-v7/manifest.json`): train 12,576 records / 15,576 questions; calibration 968 / 1,148; development 1,204 / 1,468; test 1,176 / 1,440. `train.jsonl` is not in git; it is in `SUITES/v7/decision-v7/train.jsonl` (18,679,889 bytes, sha256 7ed5254b5cb5291baefaceb09edf7e13110258211518c8038f4a12c11bd628ad = manifest).

Headline (clean) questions per source:

| source | development | test |
|---|---|---|
| agnews (topic + 2 yes/no) | 240 | 240 |
| yelp (rating + yes/no) | 160 | 160 |
| amazon | 80 | 80 |
| banking77 | 80 | 80 |
| boolq | 80 | 80 |
| dbpedia14 | 80 | 80 |
| imdb | 80 | 80 |
| mnli | 80 | 80 |
| sst5 | 80 | 80 |
| trec | 80 | 80 |
| compositional (generated rule structures) | 128 | 0 |
| legacy_policy (generated policy pairs) | 96 | 0 |
| contrastive (generated, locked shapes) | 0 | 160 |
| total clean | 1,264 | 1,200 |

The remaining questions of each file (development 204, test 240) are non-clean variants (`permuted`, `none_present`, `none_absent`) that `summarize` excludes from the headline (`kev/benchmark.py:76,87-90`). Training: 10,000 public records (1,000 per source) + 896 legacy_policy + 1,680 compositional = 12,576 (`evals/v7/decision-v7/manifest.json` `protocol.public_train_records`, `synthetic_records_per_arm`; `docs/model-cards/kev-0.8b.md:144`).

### 2.2 "New sources": transfer-v4 (`SUITES/v4/transfer-v4/`)

Manifest: development 764 records / 764 questions, test 764 / 764, train and calibration empty (`evals/v4/transfer-v4/manifest.json` `files`). Clean questions: 656 per split.

| source | development | test |
|---|---|---|
| mmlu (4 options) | 80 | 80 |
| emotion | 80 | 80 |
| sciq | 80 | 80 |
| paws | 80 | 80 |
| qnli | 80 | 80 |
| tweet_offensive | 80 | 80 |
| composition_holdout (generated, held-out rule shapes) | 96 | 96 |
| legacy_holdout (generated, `authorization`/`deadline` policy) | 80 | 0 |
| contrastive (locked policy shapes) | 0 | 80 |
| total clean | 656 | 656 |

(`docs/model-cards/kev-0.8b.md:163`: "six never-trained public sources (QNLI, SciQ, TweetEval-offensive, PAWS, MMLU, Emotion) plus held-out policy and rule structures".) 108 non-clean variant questions per split are excluded from the headline.

### 2.3 breadth-v1 (14 datasets; separate panel, not in the README accuracy table)

`evals/breadth-v1/manifest.json` keys `counts` and `questions`. Records per dataset are 150 in each of development and test, except ContractNLI 40 documents. Total 1990 / 1990 records, 3075 / 3089 questions (development / test). The metric column is the manifest's `datasets.<name>.metric`; the licence column is its `licence` field (also `scripts/build_breadth_v1.py` lines in the last column).

| dataset | area | metric | records dev / test | questions dev / test | licence | defined at |
|---|---|---|---|---|---|---|
| musr | knowledge | accuracy | 150 / 150 | 150 / 150 | CC-BY-4.0 (dataset card); code MIT | scripts/build_breadth_v1.py:84 |
| sata_bench | knowledge | case_exact | 150 / 150 | 959 / 974 | CC-BY-NC-4.0 (dataset card; the GitHub repo is MIT): the derived records inherit the non-commercial term | scripts/build_breadth_v1.py:88 |
| chessbench | knowledge | accuracy | 150 / 150 | 150 / 150 | Apache-2.0 (code and data release); positions from lichess.org (CC0) | scripts/build_breadth_v1.py:92 |
| contractnli | language | accuracy | 40 / 40 | 160 / 160 | CC-BY-4.0 (Hitachi America terms of use grant CC BY 4.0) | scripts/build_breadth_v1.py:96 |
| hellaswag | language | accuracy | 150 / 150 | 150 / 150 | MIT (code/data release); ActivityNet Captions contexts only | scripts/build_breadth_v1.py:100 |
| clinc150 | retrieval | accuracy | 150 / 150 | 150 / 150 | CC-BY-3.0 | scripts/build_breadth_v1.py:104 |
| sgd | retrieval | accuracy | 150 / 150 | 150 / 150 | CC-BY-SA-4.0: the derived records inherit the share-alike term | scripts/build_breadth_v1.py:108 |
| bright | retrieval | accuracy | 150 / 150 | 150 / 150 | CC-BY-4.0 | scripts/build_breadth_v1.py:112 |
| bfcl | tools | case_exact | 150 / 150 | 306 / 305 | Apache-2.0 | scripts/build_breadth_v1.py:116 |
| toolret | tools | accuracy | 150 / 150 | 150 / 150 | Apache-2.0 (ToolRet release); queries and tools re-published from its source benchmarks | scripts/build_breadth_v1.py:120 |
| apibank | tools | accuracy | 150 / 150 | 150 / 150 | MIT | scripts/build_breadth_v1.py:124 |
| routerbench | tools | accuracy | 150 / 150 | 150 / 150 | MIT | scripts/build_breadth_v1.py:128 |
| humicroedit | arts | accuracy | 150 / 150 | 150 / 150 | none stated (SemEval-2020 Task 7 research release; the README asks users to cite the task paper) | scripts/build_breadth_v1.py:132 |
| cfcolor | arts | accuracy | 150 / 150 | 150 / 150 | release notice: 'Permission is granted for anyone to copy, use, modify, or distribute this program and accompanying programs and documents for any purpose' (runPrediction.m), no separate data licence | scripts/build_breadth_v1.py:136 |

The per-dataset question-to-option mapping (candidate subsets, number of options 2..10, `MAX_OPTIONS = 10`, `scripts/build_breadth_v1.py:55`) is the `mapping` field in the same lines. Kev supports `choice` and `noul` for breadth-v1; sata_bench and bfcl use one `noul` per candidate and `case_exact` scoring (all questions of a record correct). Excluded: GPQA Diamond (gated; `manifest.json` `skipped`).

Other panels in the repo, not in the README accuracy table: tasksource-heldout-v1, hard-v1, devtools-v1, documents-v1/v2, longdoc-v1 (`docs/model-cards/kev-0.8b.md:159-167`).

## 3. Item format and how options are presented

### 3.1 Stored format (a "labelled request", `kev/data.py:1-6`, `:362-369`)

Per jsonl line: `{"state": JSONContent, "questions": {qid: {"type": "choice"|"noul"|"score", "instructions": JSONContent, "criteria": ..., "label": ..., "src": str}}, "_meta": {...}}`.

- `choice`: `criteria` is an ordered dict `option_key -> description|null`; `label` is the option key (string). 
- `noul` (yes/no): optional `criteria` `{"true": ..., "false": ...}`; `label` is a bool.
- `score` (ordered levels): `criteria` is a list of level descriptions; `label` is the level index (int).
- `state` is a str, dict or list (in decision-v7 development: 664 str, 468 dict, 72 list records of 1,204). `_meta` carries `id`, `source`, `group_id`, `variant` (`clean|permuted|none_present|none_absent`), dataset revision, etc.
- Only `state`, and per question `type`, `instructions`, `criteria` are sent to the model (`kev/data.py:389-394`, `api_request`); labels are never shown.

### 3.2 What the model sees (`kev/api.py`, `kev/model.py`)

- `kev/data.py:397-403` `materialize` calls `kev/api.py:102-117` `to_record`: `state = render(state)`; per question `instr = render(instructions)`, `options` = a list of strings.
- `render` (`kev/api.py:49-55`): str/int/float/bool -> `str(v)`; None -> `""`; list -> lines `- item`; dict -> lines `key: value` (nested values on indented lines), "Field names are kept as labels".
- Option strings (`kev/api.py:58-59`, `:107-115`): choice: `key` if the description is None/empty, else `"key: " + render(description)`; noul: exactly two options in order `[no, yes]` (`"no"`/`"yes"`, with `": desc"` if criteria give a description); score: `render(level_description)` only, no identifier.
- There is no task-definition text, no letter/number identifier (A/B/C), and no chat template in the Kev model. `kev/model.py:87-119` `encode`: ids = `<state>` token + state tokens, then per question `<q> instruction <opt> option_1 </opt> <opt> option_2 </opt> ... <decide>`, where the delimiters are five existing Qwen special tokens (`kev/model.py:11`: `<|fim_prefix|>, <|fim_middle|>, <|box_start|>, <|box_end|>, <|fim_suffix|>`). Caller text containing `<|...|>` is rewritten so it cannot forge delimiters (`kev/model.py:78-84`). The option identity is its position in the list; the option key text is part of the option string only when it is a choice key.
- Each question is its own row continuing from the shared state; questions cannot read each other (`kev/model.py:188-200` `rows_of`; `docs/model-cards/kev-0.8b.md:98` states it).
- Readout: a pointer head. `kev/model.py:205-217` `PointerHead(d, dp=256)`: `q = Linear(d, 256)` on the `<decide>` hidden state, `k = Linear(d, 256)` on each option's closing `</opt>` hidden state; logits `z_i = (k(h_opt_i) . q(h_decide)) / sqrt(256)`; probabilities = softmax over the options of that question (`kev/predictors.py:140` `torch.softmax(z, -1)`). `docs/model-cards/kev-0.8b.md:80` ("Pointer head: two projections score each option's closing token against the question's final token; a softmax gives the probabilities").
- Option order at evaluation is the stored order (`kev/evaluate.py` legacy path augments, but the benchmark path used for the README does not; `kev/benchmark.py:106-168` calls `LocalPredictor.__call__` on the stored record, `kev/predictors.py:127-147`). The `permuted` variants are reported separately.
- The zero-shot letter-logit baseline in `kev/evaluate.py:138-161` (prompt `"{state}\n\nQuestion: {instr}\nA. ...\nAnswer:"`, optional chat template) is a diagnostic baseline of the base model, not the Kev readout.

## 4. How accuracy is computed

Eval entry point: `python -m kev.benchmark --run <ckpt> --suite evals/<v>/<name> [--split development] [--allow-test]` (`kev/benchmark.py:1-4,171-215`).

- Unit = one question (a record may hold 1 to 3 questions). `prediction_rows` (`kev/benchmark.py:48-70`) emits one row per question with `label` = index of the gold option (`labels`, `:30-33`: choice -> `keys.index(label)`, noul -> `int(label)` with keys `[false, true]`, score -> `int(label)`).
- Prediction = per-question argmax over that question's options: `kev/metrics.py:73` `acc.append(int(p.argmax() == y))` with `p = row["p"]` (numpy argmax: the first maximal index wins; no tie rule is stated; ties are practically impossible for float softmax outputs). The probabilities are renormalised, `renormalize_returned_probabilities: True` (`kev/benchmark.py:101`, `validate_distribution` `:36-45`). No abstain option; "none of the above" options appear only in the non-clean variants.
- Aggregation = micro over questions: `kev/metrics.py:78` `"acc": float(np.mean(acc))`. `summarize` (`kev/benchmark.py:73-103`) reports `"clean": metrics(knowable)` where `knowable` = clean rows whose `source != "unknowable"`. The README accuracy is `clean.acc` (`docs/claims.json`: path `["clean","acc"]` / `["suites","transfer","clean","acc"]`). There is also a per-task breakdown `tasks` (`grouped_metrics(clean, "task")`, `kev/metrics.py:183-187`), but the headline is not a mean over tasks.
- Therefore the README numbers are micro accuracy over questions, so sources with more questions (agnews 240, yelp 160 in decision-v7) weigh more than others (80 each); there is no macro over datasets in the README accuracy. (The breadth-v1 index is different: per-dataset chance-corrected skill, area mean, mean of 5 areas, `scripts/breadth_report.py:112-136`, `evals/breadth-v1/manifest.json` `scoring`.)
- Split: `development.jsonl` or `test.jsonl` of the whole suite (`kev/suite.py:204-220` `load_split`: sha256 and record count checked against the manifest). Filtering: only `variant == "clean"` rows enter `clean` (`kev/benchmark.py:76`); the audit note at `docs/model-cards/kev-0.8b.md:169` says only "audited" headline panels exclude unsound items, and the README's decision-v7 and transfer-v4 rows are the unaudited full clean sets (counts 1,264 / 1,200 and 656 / 656 above equal `report.json` `clean.n`). Admitted suites do not skip records (`coverage.rejected_records = 0` in `runs/locked/kev-08b-r15-ungated/summary.json`); for eval-only suites such as breadth-v1 an un-encodable record is counted as rejected, and the breadth report counts it as wrong (`kev/benchmark.py:124-127`, `scripts/breadth_report.py:41-64`).
- breadth-v1 accuracy: `dataset_score` (`scripts/breadth_report.py:41-64`): metric `accuracy` = fraction of questions right; `case_exact` (sata_bench, bfcl) = fraction of records with every question right. `docs/model-cards/kev-0.8b.md:176-177` quotes question accuracy over all 3,075 / 3,089 questions.
- Context for scoring: prompts are encoded strictly within the suite's `context`; decision-v7 / transfer-v4 use max_state 384, max_branch 1024, max_packed 2048 with `truncate: false` (manifest `context`), so no item is truncated; breadth-v1 uses the serving context 8,192 / 8,192 / 16,384 (manifest `context`).

## 5. Training recipe as implemented

Source: `kev/train.py`, `kev/model.py`, `docs/model-cards/kev-0.8b.md:140-155`, `experiments/q35-08b.json`.

Base recipe (stage 1; the one the task brief describes), `docs/model-cards/kev-0.8b.md:152`: "Two epochs on `decision-v7` from the base: LoRA rank 16, alpha 32; learning rate 1e-4, one-cycle schedule; batch 8; bf16 autocast; seed 2. The loss is cross-entropy over each question's options. Option order is shuffled, 'none of the above' options and distractors are inserted at random, and a quarter of choice records also yield a minimal pair." The same card states 4B and 9B share the recipe (README.md:51, "share one training recipe").

- LoRA targets (`kev/model.py:266-274`): `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`, plus on hybrid (Gated DeltaNet) backbones `in_proj_qkv, in_proj_z, in_proj_a, in_proj_b, out_proj`; `r = 16`, `lora_alpha = 2r = 32`, `lora_dropout = 0.05`, task type FEATURE_EXTRACTION. Backbone frozen; the pointer head (two `Linear(d, 256)`) is trained from scratch at the same lr (`--head_lr 0` -> `lr`, `kev/train.py:577-578`).
- Optimiser: AdamW, weight decay 0.01 default (`kev/train.py:376`, `:580`); `OneCycleLR(max_lr=lr, pct_start=0.1)` (`:588`); global gradient-norm clip 1.0 (`:503`).
- Batch: `experiments/q35-08b.json`: `batch: 8, accum: 1` (8 records per optimizer step), `epochs: 2`, `lr: 0.0001`, `dtype: bf16` (autocast over fp32 weights, `kev/train.py:534`), `p_none_pair: 0.25`, seeds 0, 1, 2; base `Qwen/Qwen3.5-0.8B-Base` revision `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`.
- Max length (stage 1): `kev/model.py:14` `MAX_STATE, MAX_BRANCH, MAX_PACKED = 384, 1024, 2048` tokens. Later stage 3: states up to 7,552 tokens (`docs/model-cards/kev-0.8b.md:154`).
- Loss: per-question cross-entropy over that question's option logits (`kev/train.py:41-60`, `F.cross_entropy(z[None], y, label_smoothing=0.0)` at line 51; soft-target cross-entropy for records carrying a `target`). Other terms (`--perm_kl`, `--ord_w`, `--brier_w`, `--focal_gamma`, `--anchor_w`) default to 0 (`:381-386,409`). No auxiliary loss is stated for the stage-1 recipe.
- Augmentation during training (`kev/data.py:320-343` `augment`, defaults `p_none=0.1`, `p_none_distract=0.12`, `p_distract=0.15`; `kev/train.py:400-403`, `p_none_pair` 0.25 from the config): option permutation always; "none of the above" or irrelevant distractor options sometimes.
- Training data and breadth-v1: `evals/breadth-v1/manifest.json` lists `trainable_sources: []` and `eval_only: true`; `kev/train.py:114-116` raises if training records contain an eval-only source; `kev/suite.py:181-189` `validate_training`. `docs/model-cards/kev-0.8b.md:148`: breadth-v1, tasksource-heldout-v1, transfer-v4, longdoc-v1 and the When2Call and prompt-injection sources of devtools-v1 "never enter training". `decision-v7` train sources are the ten public sets (banking77, boolq, agnews, mnli, sst5, yelp, trec, dbpedia14, amazon, imdb) plus the generated legacy_policy and compositional (manifest `trainable_sources`); mmlu, emotion, tweet_offensive, qnli, paws, sciq and the held-out structures are in `eval_only_sources`. Hence neither breadth-v1 nor transfer-v4 is trained on. Not determinable from the repo: upstream-dataset overlap beyond what `evals/breadth-v1/overlap.json` (screening output) records, and the Qwen pretraining data.
- Important for comparisons: the released Kev-0.8B/4B/9B checkpoints that produce the README table are NOT the stage-1 model. `docs/model-cards/kev-0.8b.md:140-155` lists three further stages: (2) dates and missing evidence, 1,425 records, one epoch at lr 4e-5; (3) documents-v1 + hard-v1 + devtools-v1, 16,539 records, one epoch at lr 2e-5, batch 4 x 2 accumulation, states up to 7,552 tokens; (4) a fitted temperature T = 2.35. Kev-27B is a different recipe (full-weight fine-tune of Qwen3.8-27B, `README.md:51`). The README "Trained Sources" and "New Sources" figures are therefore measured after all stages. Stage-1-only trials of the same recipe on Qwen3.5-0.8B-Base (3 seeds, `runs/q35-08b/00-trial-0`, `01-trial-1`, `02-trial-2`, each `result.json`, development partitions): decision-v7 `clean.acc` 0.8172 / 0.8196 / 0.8291 (n = 1,264) and transfer-v4 `transfer.clean.acc` 0.6220 / 0.6341 / 0.6433 (n = 656). These are the closest published numbers to a pure `decision-v7` stage-1 model.

## 6. Public availability of decision-v7 training data

Yes, fully. `SUITES/v7/decision-v7/train.jsonl`: 18,679,889 bytes, 12,576 records, 15,576 questions, sha256 = manifest `files["train.jsonl"]`. Its calibration (968 records), development and test files are also in `kev-suites`. Related public training sets in `kev-suites`: `public-pool-v4/v5/v6/train.jsonl` (the pool the 10,000 public records are drawn from; manifest `protocol.public_pool: evals/public-pool-v4`), `documents-v1/train.jsonl` (23,268,481 B), `hard-v1/train.jsonl` (23,118,561 B). The public-source texts are the upstream datasets' (section 7).

## 7. Licences

Kev code and adapters: Apache-2.0 (`LICENSE`; README.md:501-503: "Training datasets have their own licenses; see the model cards"). The suite manifests of decision-v7 and transfer-v4 contain no licence field ("per-source licences and revisions are recorded in the suite manifests", `docs/model-cards/kev-0.8b.md:148`, holds for devtools-v1, breadth-v1 and longdoc-v1 only). Therefore for decision-v7 and transfer-v4 sources the repo does not state licences: not determinable from the repo. For information only (not from the repo, queried from the HF API `cardData.license` on 2026-10-30, may be incomplete): banking77 cc-by-4.0; boolq cc-by-sa-3.0; ag_news unknown; multi_nli cc-by-3.0/cc-by-sa-3.0/mit/other; sst5 not stated; yelp_review_full other; trec unknown; dbpedia_14 cc-by-sa-3.0; amazon_reviews_multi_en apache-2.0; imdb other; mmlu mit; sciq cc-by-nc-3.0; qnli (glue) other; tweet_eval unknown; paws other; emotion other. The generated sources (legacy_policy, compositional, contrastive, composition_holdout, legacy_holdout) are produced by Kev code under Apache-2.0 (`kev/contrastive.py`, `kev/composition.py`).

breadth-v1 licences (repo, `scripts/build_breadth_v1.py` DATASETS and `evals/breadth-v1/manifest.json` `datasets.<name>.licence`); the manifest `mirror_note` says the partitions are private because SATA-Bench is CC-BY-NC-4.0, SGD CC-BY-SA-4.0, Humicroedit has no licence and cfcolor has a code-only notice:

| dataset | licence as recorded |
|---|---|
| musr | CC-BY-4.0 (dataset card); code MIT |
| sata_bench | CC-BY-NC-4.0 (dataset card; the GitHub repo is MIT): the derived records inherit the non-commercial term |
| chessbench | Apache-2.0 (code and data release); positions from lichess.org (CC0) |
| contractnli | CC-BY-4.0 (Hitachi America terms of use grant CC BY 4.0) |
| hellaswag | MIT (code/data release); ActivityNet Captions contexts only |
| clinc150 | CC-BY-3.0 |
| sgd | CC-BY-SA-4.0: the derived records inherit the share-alike term |
| bright | CC-BY-4.0 |
| bfcl | Apache-2.0 |
| toolret | Apache-2.0 (ToolRet release); queries and tools re-published from its source benchmarks |
| apibank | MIT |
| routerbench | MIT |
| humicroedit | none stated (SemEval-2020 Task 7 research release; the README asks users to cite the task paper) |
| cfcolor | release notice: 'Permission is granted for anyone to copy, use, modify, or distribute this program and accompanying programs and documents for any purpose' (runPrediction.m), no separate data licence |

## 8. Facts that matter for running our checkpoints on the same items

- What can be reproduced locally today: decision-v7 development/test (1,264 / 1,200 clean questions) and transfer-v4 development/test (656 / 656), i.e. the four numbers per model in the README table. These are converted to our record format in `/mnt/cephfs/xingchao/experiments/jev/KEV/` by `/mnt/cephfs/xingchao/experiments/jev/r1_code/convert_kev.py` (non-clean variants are written to separate `*.variants.jsonl` files and must not enter the headline).
- The Kev prompt has no task definition and no option identifiers; our prompt builder adds a task definition and shows `- <name>: <definition>`. Option text for choice questions without descriptions equals the key, so name and definition coincide. Prompt-format differences are a confound when comparing with the Kev numbers; the Kev readout is a pointer head over option spans, ours is the continuation of the identifier after `Answer:`.
- Micro accuracy over questions is what Kev reports; reporting per-source accuracies alongside is possible from `tasks` but those are not the headline.
