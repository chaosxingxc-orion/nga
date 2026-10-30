# R3 selection consumer repair — 2026-10-30

Selection previously accepted stored report summaries without checking their producing model,
question population or training seeds. A zero-cell condition (c) returned `ok=true`, a single
report could satisfy K-align, and `adopt_first({"passes": true})` ignored the R0 fp32 prerequisite
added by amendment 11. These are engineering validity defects, not model findings.

The working CephFS code now loads selection inputs through `selection_evidence_r3`:

- It hashes the actual adapter/checkpoint, checks the producing manifests and row stamps, and
  validates the exact development question keys, candidate order, gold and stored decisions.
- It recomputes clean, question-only and empty-input accuracies from scores, and the constant
  baseline from training data. Editing `report.json` accuracy fields cannot change the result.
- Training identity comes from the completed trainer manifest. Two-seed comparisons and K-align
  require distinct registered seeds 2 and 3; copying a report does not create another seed.
- Track T input files are checked against their manifest; rows are matched to the expected
  population and metadata reconstructed from tasks. Selection recomputation retains threshold
  fitting data and excludes report-half held-out rows from metric computation.
- Condition (c) cannot pass without a verified, full R0 fp32 run and a nonempty gating population.
  A smoke completion marker is refused. Candidate replacement also enforces K-floor.
- First adoption reloads the named seed runs and recomputes K-floor; a supplied pass flag is
  insufficient. Without the R0 prerequisite, adoption remains false.

The provenance verifier now supports the complete set of Track K and Track T directories together,
while retaining the original single-directory interface. Conflicting producer manifests are refused.

Validation: 25 synthetic consumer tests, 8 numerical/selection tests, 7 provenance boundary tests,
and 11 existing harness-identity/erratum compatibility tests passed. Synthetic consumer tests cover
valid complete input and missing/duplicate/wrong questions, changed weights, changed data, stale
manifests, invalid scores, wrong objective, unfinished training, partial reports, duplicate seeds,
CLI loading, and smoke-vs-record rejection. Numerical tests use explicit synthetic verified inputs;
they do not substitute for the separate real-loader tests.

The compatibility suite unexpectedly exceeded one minute (about 90 seconds) and was run attached;
that did not follow the repository's long-run rule. It completed, and subsequent checks of that
duration must be detached. This was a CPU compatibility test, not an NPU training run.

Evidence and file hashes: [R3-SELECTION-CONSUMER-REPAIR.json](R3-SELECTION-CONSUMER-REPAIR.json).
Pre-edit files are retained under
`/mnt/cephfs/xingchao/experiments/jev/r3_runs/_selection_consumer_fix_20261030/`.
Existing frozen experiment snapshots were not changed. Relevant working dependencies are now
included in the repository snapshot so the newly recorded selection entry point is reviewable.

## Limits and remaining work

This is not closure of the whole provenance obligation. The `full_eval_r3` report stage and
`testlock_r3` consumer wiring still need their own implementation and tests. Adapter identity
currently binds adapter content plus the base revision/path, not the base weight bytes; that
existing limitation remains. There has been no selection on actual completed W1 arms, no actual
full-size Track T selection recomputation in this repair, and no final-test read. E3, the full
resume suite, R0 fp32 re-score and the independently reviewed release remain outstanding.

All numeric decision thresholds are unchanged. An absent/empty gating population is reported
incomplete, never as empirical evidence that consistency held. No independent Astra acceptance
is claimed: the user requested all other project sessions be stopped.
