# Open-Jev-2B public-test suspicious-success review

2026-10-30. Bounded post-run diagnosis of the two flags in
`reference_inference/openjev2_test_20261030_v3_finish_v2/INDEPENDENT_AUDIT.json`.
This does not change the preregistration, predictions or original review flags,
and is not Astra approval or a production reliability claim.

## Evidence and findings

The independently audited population contains 10,356 public-test rows, including
9,995 hard and 361 soft labels. The report SHA256 is
`fb1083b51963c4e06621fae50f4ad9f2f3132a7d24a23cd84dcfef649c635b7a`.
The diagnosis read the exact flagged cohort receipts and their source rows;
receipt index, target and candidate order were checked against the input export.

| Flag | Independently reconstructed observation | Interpretation |
| --- | --- | --- |
| `customer-control-v1/accuracy == 1.0` | 606 rows: 574 hard, all 574 correct; 32 soft. Expected accuracy over all 606 is 0.9722222222222222 | The perfect value uses the hard-label denominator, not all 606 rows. It is not a soft-target-perfect claim |
| `trex_runner-v1/count < 30` | Four hard rows, one correct, accuracy 0.25. All four predictions are `jump_full`; gold is `jump_short` twice, `jump_full` once, `duck` once | The small denominator and prediction collapse are real in this cohort. The flag remains substantively relevant; no stable ability estimate follows |

Customer-control contains 101 groups, six questions per group: 101 choice,
303 score and 202 noul rows. All 606 provenance records identify synthetic data.
There are 606 distinct rendered prompt sets and 15 distinct selected option texts;
the hard-label perfection is therefore not explained by one identical prompt or
one constant answer. Group dependence and synthetic construction limit inference
to other populations. This review does not establish absence of training/test
overlap or rule out learned generator structure.

The four trex receipts are indices 9469–9472. Serving confidences are respectively
0.5388810778341305, 0.9342832251114138, 0.8003626953492728 and
0.5058644596363814. Their targets select option indices 0, 1, 2, 0; predictions
select index 1 throughout. This independently reproduces 1/4 and shows why an
aggregate score alone would conceal this local failure.

## Input and scoring checks

The frozen native `jev/api.py:78–85` builds prompts from state, question, kind and
the current option. `jev/model.py:226–269` calls that builder and produces logits
in the same candidate order; noul uses the declared no/yes order with logits
`[0, score]`. The evaluation driver feeds the complete record to the native model,
so the native implementation, rather than the driver call signature alone, is
the relevant leakage boundary.

A bounded Python check extracted the two native rendering functions from that
frozen source. For every one of the 610 flagged-cohort records, reversing target
values and replacing ID, source, group ID and metadata left the prompts exactly
unchanged. This tests explicit label/metadata isolation; it does not prove that
the input text itself lacks target-revealing clues.

The independent scorer's hard accuracy uses only rows whose target maximum is
1; expected accuracy averages target mass assigned to the selected option over
all rows. These distinct denominators explain the customer-control values. No
denominator, candidate-index or explicit target-to-prompt error was found within
this bounded review.

As a secondary check, the serving-confidence ≥0.99 diagnostic selects 6,747 rows,
all hard and all correct in these saved predictions. They span ten sources:
customer-control 504, vizdoom-basic 480, workflow customer_service 382,
security_incidents 1,228, agent_trace_observability 301, invoice_processing 735,
painting-geometry 2,764, snake 163, tile_platformer 8 and reasoning-control 182.
This reproduces the observed zero error; it does not validate a deployment
threshold or remove finite-sample, group-dependence and distribution limitations.

Frozen source identities inspected:

- `code/jev/api.py`: `f22aa50c00d64aa91c2d415c1973f59bdaad11d1de51308ae5454326b8cbf350`.
- `code/jev/model.py`: `333bed84cf2801ba33b053891e9ff9563d082f3da87ad6ad1681a2b1bcb4c6aa`.

## Disposition

Retain both original review flags and this diagnosis alongside the scoped audit.
The counts and arithmetic are reproduced; the perfect hard subset has a specific
denominator and diverse predictions. The four-row trex limitation remains and
should be visible in reporting. Neither finding justifies changing the original
population, selecting a new threshold from test results, or claiming continued
training benefit. The 176-row supplement and exact original-test join remain
separate executions and must retain component review flags.

## Reproducible diagnosis artifacts

The checked script is [review_openjev_public_flags.py](../tools/review_openjev_public_flags.py).
It was executed on 175 with host `python3 -I` in under one minute. It bound all
10,356 receipt identities and probability/temperature pairs, then independently
reproduced both flagged cohorts and the confidence diagnostic. No original
artifact was written. Machine evidence, the exact script snapshot and a rerun
command are retained in
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_public_flag_review_20261030/`.

- `report.json` SHA256:
  `5ef5bf1b75ee265dd4120d0d83151c6ceaaa943f7ae7b8e78fe2f768f3063e8b`.
- `cohort_items` records all 610 IDs, input/receipt/prompt hashes, predicted and gold
  candidates, confidences and explicit label/metadata-invariance outcomes.
- `source_hashes` binds input data, source functions, original config/report/audit
  and the diagnostic script; `original_review_flags` preserves both flags.
- `REPRODUCE.sh` writes a separate `report-recomputed.json`, refusing overwrite.

The rerun includes a new observation timestamp, so its complete report hash may
differ; compare source hashes, cohort items, counts and the confidence diagnostic.
