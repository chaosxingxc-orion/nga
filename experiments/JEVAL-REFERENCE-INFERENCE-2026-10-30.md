# E33 — JEVal actual reference inference, native budgets and explicit scoring

Pre-registration 2026-10-30, before E33 model runs. Defects 12/16: task identity,
measurement and external generalization. The degenerate optimum of dropping hard,
long or unsupported rows must fail complete-denominator and original-ID checks.
Gold/metadata invariance has candidate-content/order discrimination counterparts.
Aggregate accuracy is not a paired consistency measure.

## Population and model scope

Exact JEVal `test.parquet`, SHA256
`88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82`,
11,257 ordered rows: 9,582 choice, 1,356 noul, 319 score. Original state strings,
question definitions and candidate order remain intact. Original source train/dev
provenance remains recorded; the published JEVal test is not silently filtered.
Six fixed existing checkpoints: Kev 0.8B/4B/9B, Open-Jev 2B/9B, initial Nimble v1.
Each run binds the corresponding completed E31 eligibility configuration/report
and exactly the same native sources, base and adapter/head dependencies.

Native limits are unchanged: Kev 8,192 state/state-plus-branch and 16,384 packed;
Open-Jev 4,096 per candidate prompt; Nimble 2,048 and at most 26 candidates,
nonempty context. Unsupported and overlength rows get identity-bound receipts
without fabricated predictions. All 11,257 rows remain in coverage counts.
Unexpected runtime exceptions fail and retain the run; they do not become skips.
No extended context, window aggregation, prompt repair or placeholder context.

## Native execution and admission

Reuse the successful native model paths: Kev FP32/eager merged LocalPredictor;
Open-Jev BF16/unmerged/SDPA backbone and FP32 head; Nimble BF16 safe merge with
FP32 candidate projection. Preserve release temperatures. Inputs passed to forward
are checked against E31 token hashes, including a recorder on consumed Kev encoder
and Open-Jev tokenizer outputs. No labels enter model requests.

In a separate probe-only retained container, run two forwards of each fixed synthetic type, followed by
two forwards of the longest eligible input (largest recorded token length, lowest
original index breaks ties). This boundary input is selected using token metadata
before predictions, not accuracy. Repeat maximum probability difference <=1e-5;
all durations positive/finite; report per-chip throughput, one chip, reserved memory.
OOM, invalid output or numerical drift stops the run for engineering diagnosis.
The probe stops with its own terminal without entering the test loop. Parent
review must bind the exact probe configuration and report hashes in PROBE_REVIEW.json;
only then may a new inference configuration be prepared. It must use the same
native dependencies, runtime and executable sources. Throughput/memory are
reviewed before formal inference, not just checked for positive timings.
The boundary probe is disclosed test exposure for runtime admission, not a score
or a training-selection observation. It does not authorize changing precision,
attention, context or response semantics after seeing results.

## Metrics: paper formulas with disclosed local response conventions

The exact paper test scorer is unavailable; this is a new native-budget evaluation,
not an exact reproduction of every paper row. Model versions and temperatures also
differ from some paper entries. Paper-formula choices below are frozen now:

- Classification accuracy: actual returned choice, or `noul >= 0.5`, compared with
  scalar gold; denominator **10,938**, including unsupported/overlength as wrong.
- Raw summed one-hot Brier: valid classification only; use wire probabilities as
  returned without renormalization. For noul, reconstruct `[1−noul,noul]` from the
  returned scalar. No valid rows means undefined (`null`), not zero.
- ECE10: valid classification only. Choice uses the native returned confidence
  (Kev/Open-Jev chance-adjusted; Nimble selected probability). Noul uses returned
  selected binary probability. Bins `min(int(confidence*10),9)`; exact boundaries
  go to the upper bin except 1.0 in the final bin. These confidence/boundary choices
  are **local conventions**, not proven paper-scorer equivalence.
- Score MAE: valid score only, original level units, using actual returned score.
  Kev uses its four-decimal expected level; Open-Jev its native expected level;
  Nimble's enum-to-score adapter returns the selected integer level, not a newly
  invented expectation. Invalid/ineligible scores are excluded and counted against
  the full **319** score population. No division by K−1 or source-macro averaging.

Kev wire values retain native four-decimal serialization; Open-Jev's formatter
retains its native normalized floating values. Native logits and probabilities
are saved separately for audit. Nimble's typed enum/bool outputs are adapted with
explicit probabilities; this is not an upstream JEVal HTTP response reproduction.
Strict native response schemas reject missing/extra fields, nonfinite numbers,
wrong candidates or out-of-range values; raw probability mass need not sum to one.
The native emitter's normalized model distributions and the response metric's
non-normalizing validation are distinct checks.

## Execution and acceptance

New retained detached containers on 175, existing immutable image only. CephFS log,
10-second timestamped progress, item receipts, terminal/wrapper, exact guarded
relaunch; fixed-name containers retained for exit inspection. Source/dependency
closure frozen before execution. Parent review binds configuration hashes before
launch; allocation lock and current live-device checks prevent conflicting chips.
No automatic adoption of old live runs. An independent CPU finisher checks actual
Docker identity, complete terminal and independently reconstructs native responses
and metric arithmetic. It checks token hash provenance, not independent tokenization.

Completion requires 11,257 unique receipts, complete denominators, unchanged input
hashes, successful inference terminal/wrapper/retained container, independent audit
and flagged suspicious metrics retained. No training, fitting, real-business
integration, new training benefit or Astra approval follows from this experiment.
