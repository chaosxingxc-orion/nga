# E36 — Open-Jev candidate batch memory probe

## Purpose and hypothesis

Defects 12/16. The longest-single-input E33 probe does not cover the maximum
candidate batch. Test whether batch-axis chunking preserves native numerical
outputs within measured repeat noise while executing the metadata-selected
candidate width/padded workload envelope.

## Setup

[Pre-registration](../experiments/OPENJEV-CANDIDATE-BATCH-2026-10-30.md).
Same 2B/9B checkpoints, prompt/global-padding/head/temperature/response, fixed
8-row backbone chunks, chip 1 on 175, existing immutable image. Existing runs and
frozen sources remain intact. No full-test scores or new training.

## Execution

Preparing external wrapper and repeated original/chunked probe. Formal inference
requires later engineering acceptance; no candidate-batch admission yet.

## Results and verdict

Pending actual probes and terminal/output/actual-exit checks. A difference beyond
measured original-repeat noise blocks admission, even below 1e-5.

## Actual preparation and first launch

Three CPU wrapper tests passed in retained `nga-e36-chunk-unit`, existing immutable
image with backend autoload disabled. They cover preserved global padding/masks,
ordered tail batches, unknown argument rejection and cache refusal.
Two plans froze 110/113 files including the accepted E33 source closure and new
external scripts, preregistration, wrappers and Docker spec. Plans:

- 2B: `4a4526b9188619e5c5b73cdae9a32d81535bcd6f812fb8437ec161b07e418348`
- 9B: `2ed129d38ebe26252c4b8a0d2922d6ebe932f718538c748d02eb4e06947da391`

2B actually launched on chip 1 after locked ownership/live checks and all frozen
hashes: retained `812a70d4c68ea9e12f02090ea8b74c4afbe55822fb7e7ebd702534ae2c6bc6c2`.
Directories `reference_inference/openjev_candidate_batch_openjev{2,9}_20261030`.
9B remains prepared until 2B actually exits and the chip is explicitly released.

## 19:32 UTC — 2B completed, numerical admission failed

All 20 forwards completed, terminal 19:32:15 UTC and actual retained container
exit 0. Plan and terminal output hashes checked; report SHA256
`f9924b954ec46a690a38f4c4f264247d2f2fdaccf78aaebfb79a0c82d46986b6`.
This is a completed engineering measurement, **not accepted numerical equivalence**.
For index 9027, original/chunked maximum deltas: logits 0.2363473177,
probabilities 0.01414141465, numeric wire 0.01462904964; each path's repeat delta
was 0. Selected choice and token hashes match. `candidate_batch_admission=false`.
Synthetic controls match, but their candidate counts are below chunk size and do
not exercise actual partitioning. No tolerance was relaxed and no formal run starts.

The observed chunk calls preserve 4096 padded positions and ordered ranges
[0,8), [8,16), [16,24), [24,30). There are 30 logits and 30 matching consumed-token
hashes. Long-case reserved memory fell from 24.048828 to 7.539062 GiB; worst-padded
index 633 succeeded twice at 40.383299/39.780845 seconds, reserved 9.632812 GiB,
peak allocated 7.717834 GiB, one chip. These memory results do not compensate for
the failed numerical criterion. Exact kernel cause remains unproven; the current
receipts do not contain intermediate hidden states/dtypes for localization.

After actual exit and locked owner/live-device checks, chip 1 was explicitly
released. The already frozen 9B diagnostic probe actually started, retained
`65833641d6d3ba3fe1f218c318aeb7be35b1e29ef857f20e5dbaf817f6b0f0c7`.
It remains a diagnostic measurement, not permission to use changed test predictions.

## 19:50 UTC — 9B completed, numerical admission also failed

All 20 forwards completed; terminal 19:50:03 UTC, wrapper and actual retained
container exit 0. Plan, report and envelope hashes were checked. Report SHA256
`54e31f8ea0b2893cb3f71e6b291bbc903b3a3633447469fb36119890cf2f77b6`.
The original and chunked repeats are individually identical. For longest input
9027, cross-mode logits delta is 0.1410264969, probability delta 9.391012487e-6
and numeric-wire delta 9.714840504e-6; the latter two being below 1e-5 does not
satisfy the zero observed original-repeat noise floor. Choice and consumed-token
identity agree. `candidate_batch_admission=false`; no formal Open-Jev JEVal run
is authorized by E36.

Long-input reserved memory: 56.710938 GiB original versus 24.394531 GiB chunked;
first-pass time: 27.376623 versus 25.370842 seconds. Worst-padded input 633 runs
all 255 candidates in 32 ordered chunks (first [0,8,2156], last [248,255,2156]),
111.770099/111.420966 seconds, peak allocated 23.209832 GiB and reserved
27.187500 GiB on one chip. Every candidate remains present. This demonstrates
memory feasibility of that measured path, not numeric equivalence or full-test
performance. The exact numerical cause needs separate internal-state diagnostics;
batch-dependent kernels remain a hypothesis, not an established attribution.

Chip 1 was explicitly released under lock after retained exit, terminal/output
hashes, exact ownership and absence of a live device mapping were checked.
Four additional CPU comparison tests pass, covering real logit drift, legend-text
changes, probability-order changes and token-order differences. Together with the
three actual-image chunk tests this is seven tests, not evidence of model parity.
