# Fixed RC1 trained DEV measurement contract

Frozen before successor inference, 2026-11-06. Scope: the eight new functional campaign adapters, Qwen3.5 Base0.8B/2B/4B/9B × seeds2/3, terminal3116. This is a new DEV measurement campaign; historical roster membership, selection and TEST authorization are not inherited. Training remains unchanged. No new TEST read, hyperparameter selection, threshold tuning on DEV, or automatic gate pass is authorized by this document.

## Purpose and declared interpretation

Measure the actual new adapters with the established R3 continuation-scoring protocol and usable controls, preserving comparable readouts for subsequent scientific review. This addresses the defect12 measurement prerequisite. High task accuracy can arise from constant predictions, question/source lookup or input neglect; constant/uniform and same-adapter input-drop/input-blank controls are retained. Permutation and NOTA diagnostics keep their existing discrimination and paired correctness definitions. Aggregate accuracy is not decision consistency, and test-time input-drop is not a trained-QO semantic-transfer control.

## Frozen population and scoring

Each adapter consumes decision-v7 calibration1148, decision-v7 DEV1264 and transfer-v4 DEV656 from the existing frozen combined-evaluation closure. All predefined Track K variants and controls remain in the existing instrument. Eight adapters cover15360 clean DEV,9184 calibration,30720 drop/blank and2496 variant question-condition evaluations:57760 in total. This count excludes pureCPU constant/uniform controls and is not a count of candidate forwards. Missing items are failures, never denominator changes.

Use the existing `combined_eval_closure_20261031_v1/r3_code/eval_r3.py` full Track K instrument: `--full --arm K1 --partitions dev,calibration --stages k --scorer rightpad --dtype float32 --token-budget 16384 --no-hf32 --require-record-grade`. Freeze exact source/data/config identities before dispatch. The wrapper may persist the returned Track K report, but must not enable the separate Track T report stage. Model-of-record is the matching Base plus unmerged published adapter; require successful training exit, terminal checkpoint3116 and matching publication. Failed/missing seeds remain explicit.

Each candidate score is the existing summed continuation-token log probability. Headline accuracy uses first raw-score argmax; the R0 tie-as-incorrect convention is separate. Preserve near-tie and duplicate-token-candidate diagnostics, source/type strata and existing population checks. Fit Track K operator tau only on decision-v7 calibration and apply unchanged; do not fit temperature or tau on DEV/TEST. This campaign does not read Track T data or fit Track T tau.

## Reporting and comparison

Report every fixed size and both seeds individually; the within-size two-seed mean is descriptive. No cross-size pooled mean, best-seed selection or historical adapter substitution. Numerical scores and named metrics are computed by CPU scripts. Reuse existing same-size K0 only after verifying exact base identity, prompt/tokenizer, candidate readout, population and statistical compatibility; otherwise disclose the mismatch and prepare a specific matched baseline, rather than subtract unlike metrics.

No historical W/K-floor threshold becomes an automatic new eligibility rule. Controls and existing diagnostic predicates may be reported with their definitions, but any new selection contract and final TEST roster must be fixed separately before its use. Reference comparisons keep native temperature versusT1, different masks and different interfaces separate. Preserve historical accepted numbers unchanged. No training improvement is claimed until the actual measurements and comparison are independently reviewed.

## Execution

One model load per lane for calibration and both suites where supported; consume trained adapters as each lane finishes. Reuse resumable item storage, log/heartbeat and actual exit markers. Separate pureCPU metric work from NPU ownership so next useful work can start after inference. Fixed image/entry and numerical mode must be recorded; actualFP32 memory headroom remains to be checked, particularly9B. A bounded functional smoke may use fixed deterministic DEV keys; no TEST access. An OOM requires resource/config diagnosis, not silent truncation, precision change or sample exclusion.

The old BF16/token-budget1 waiting successor was stopped before inference because it did not implement this protocol. Its prototype and receipts remain local. Eight current trainings are not interrupted. This contract is a measurement preregistration, not proof that the replacement queue is implemented or that scientific eligibility has passed.
