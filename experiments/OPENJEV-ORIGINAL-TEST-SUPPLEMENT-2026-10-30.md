# Open-Jev original-test supplementary inference and exact join

Pre-registered 2026-10-30 before supplementary inference. Status: preparation; no run launched.

## Scope and hypothesis

Defect 12 (measurement validity) and defect 16 (evidence acceptance): the redistributable
10,356-row test omits 176 Wikispeedia records from the original 10,532-row test. Evaluate only
those missing records using the exact corresponding E14/E18 model interface, then recompute
full-test metrics from all original-order logits. This is reference inference, not training.
A degenerate join can manufacture a plausible aggregate from mismatched models or rows;
valid joins must pass while wrong model/configuration, duplicate, missing or altered rows fail.
No accuracy target is interpreted as consistency or evidence of unseen generalization.

## Fixed populations and protocol

Original full test SHA256:
`fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b`.
Full denominator 10,532 = 10,046 hard + 486 soft. Public projection SHA256:
`0c4b953282a4292272110536ca543fe6e2736ab729b81d9b0464dd8ab4eec86a`,
10,356 = 9,995 hard + 361 soft. Supplement SHA256:
`e1d5bbf9212fff1fba6b3e26df5afd34c55bbe9d83fdc3464446d6da23a0a83d`,
176 = 51 hard + 125 soft, original one-based positions 1465 through 1640.
Exact row content and order must match the original restored file; uniqueness alone is insufficient.
The OOD split is outside this experiment.

For each size, retain its public-run checkpoint, base revision, frozen native code, candidate
prompt construction, unmerged adapter, bf16 backbone / FP32 readout, SDPA and 4,096-token
limit. Serving temperature: 2B `1.518796342858676`; 9B `1.8969118766347646`.
No fitting, truncation, new exclusions or temperature selection. All supplement candidates
receive a length preflight before model loading. An overlength item blocks that size's run.

## Metric methods

Recompute original native hard accuracy, expected accuracy over hard and soft targets, NLL,
distribution Brier, expected one-hot Brier, ECE15 and fixed confidence coverage/risk tables.
Report serving-temperature and raw T=1 separately; source and kind panels retain their own
denominators. Preserve the public-only result as a distinct population. Never average its
aggregate score with the supplement: full statistics come from the exact joined ordered logits.
Source/kind sample counts below 30, exact 0/1 metrics and identical metrics across groups
remain review flags. No aggregate accuracy is labeled decision consistency.

## Execution, provenance and acceptance

175 only; existing immutable image. Each size waits for its public inference's successful
structured terminal, wrapper, exact retained Docker identity and exited/0, and successful
independent artifact audit. Chip transfer requires the allocation lock, matching old ownership
or confirmed free state and no actual running device conflict. Failure blocks that dependency.
New supplement run directories, fixed retained containers, CephFS heartbeat/logs/terminal,
item-level receipts and exact guarded relaunch commands are required. Existing frozen runs
are not edited or restarted.

Before full-test reporting, reverify both component configs/files/receipts and terminal/report
bindings. Equal model signatures cover image, base ID/revision, checkpoint file hashes,
native-code relative paths/hashes, length and temperature. Bind each original row to exactly
one unchanged component receipt, retaining its source config and index. Recompute all metrics
with the independent stdlib scorer and bind the join report to both component reports and
config hashes. Container completion and an aggregate score alone do not pass acceptance.

## Results

Pending implementation review, supplementary execution and exact join. No original-full
inference score, substantive Astra approval or Jev training benefit is claimed.
