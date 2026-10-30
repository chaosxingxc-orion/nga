# E14 — Native Open-Jev-2B public test evaluation

Preregistered 2026-10-30 before preflight or test inference. Status: preparation; full
inference requires the whole-test length preflight and code review to pass.

## Purpose and hypothesis

Measure the released native Open-Jev-2B on every row of the redistributable release-v2
test projection. Defect registry row 12: measurement validity. The unconstrained optimum
is a lookup of exposed test labels; these measurements therefore describe the fixed
reference checkpoint only, not unseen generalization. Constant distributions can pass
structural checks; no consistency or invariance claim follows from accuracy. Native
source-specific results and hard/soft counts prevent a single aggregate hiding coverage.

## Frozen setup and methods

Use exactly 10,356 ordered rows from the raw redistributable test JSONL, uncompressed
SHA256 `0c4b953282a4292272110536ca543fe6e2736ab729b81d9b0464dd8ab4eec86a`.
There are 9,995 one-hot and 361 soft-target rows. This is not the old 10,532-row complete
test; 176 Wiki rows are absent. No sampling, target fitting, truncation or skipping.

Checkpoint: ZefanCai Open-Jev-2B package/checkpoint. Base: Qwen/Qwen3.5-2B revision
`15852e8c16360a2fea060d615a32b45270f8a8fc`. Preserve native independent-candidate prompts,
right padding, thinking disabled, generation prompt enabled, unmerged adapter, bf16
backbone, float32 scalar head and SDPA. Local-path resolution and torch_npu device/timing
are the only device adaptations. No prefix cache, quantization, temperature fit or model
selection. Native max_length=4096 is immutable. A CPU preflight renders and tokenizes
every candidate with the native code and exact tokenizer; any oversized row blocks the
full native run for explicit protocol resolution, never silently drops a row.

Use the saved serving temperature 1.518796342858676, plus separately labeled raw T=1
statistics from the same logits. Native `jev.metrics.evaluate_probabilities`: hard accuracy
counts only one-hot targets (9,995); expected accuracy uses target mass at first argmax;
NLL uses probability floor 1e-15; Brier is sum_k(p_k-q_k)^2; expected Brier adds
1-sum_k(q_k^2); these four statistics include all 10,356 rows. ECE uses 15 equal-width
top-label bins and expected correctness, weighted by row count. Native fixed coverage
thresholds are 0.5/0.7/0.8/0.9/0.95/0.99. Preserve source-specific serving metrics.
This does not make Kev and Open-Jev Brier denominators or ECE definitions interchangeable.

## Execution and acceptance

Directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030/`.
CPU tokenizer preflight runs detached in retained container `nga-reference-openjev2-lengths`.
After review and preflight pass, full inference uses 175 chip 2 only, after atomic allocation
and live Docker device checks; retained container `nga-reference-openjev2-test`.
Image SHA256 `8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
Freeze source, model, tokenizer, data, source manifest, driver and execution scripts by hash;
verify before and after each mode. Config identity binds ordered input and every receipt.
Each record keeps its ID/index/input hash, ordered options, targets, raw logits, serving
probabilities, tokens and latency. Resume only contiguous validated prefixes; corruption,
wrong order or changed source fails closed. No automatic retry of a recorded error.

CephFS log, 15-second heartbeat, atomic terminal, wrapper exit marker and exact relaunch
must survive SSH loss. Inference heartbeat reports questions/s/chip, chip count and reserved
memory. Completion requires all rows, zero failed rows, matching source identities and
independent metric/denominator review; a subset must not generate a full report.
A length preflight success only means that tokenization completed; its `status` must be
`ready`, not `blocked_overlength`, before inference. No test result claim yet.

## Results

2026-10-30 preregistration amendment before any test inference: previous CPU-only
preflights completed 10,356 rows / 28,622 prompts, maximum 724 tokens, zero overlength.
They remain in the original directory. Final reviewed driver uses a fresh directory
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030_v3/`
and containers `nga-reference-openjev2-lengths-v3` / `nga-reference-openjev2-test-v3`.
It binds preflight terminal and wrapper exit to complete length receipts, hashes final
reports in terminals, rejects direct re-execution over existing terminals, checks token
counts against preflight, and flags suspicious source metrics. Re-freeze and rerun the
whole CPU preflight before claiming chip 2. Native model/data/metric choices are unchanged.
Formal inference results pending.

2026-10-30 15:44 UTC execution update: v3 froze 90 files. Its complete CPU preflight
wrote ready/rc 0 at 15:44:25Z, wrapper rc 0 at 15:44:26Z; all 10,356 rows again passed.
The launcher rechecked all frozen files, every length receipt, preflight report hash,
terminal/wrapper and CPU-container exit. Under the allocation lock it checked live device
maps, claimed physical chip 2, and launched retained `nga-reference-openjev2-test-v3`:
`a821b5cbf77873ea02f2a7a52cfd904ec1bd5bc2ce216d213298e94c9891cdac`.
`LAUNCH_RECEIPT.json` binds actual image, container, entrypoint, command, config and wrapper.
This is a launch record; complete test metrics and independent verification remain pending.

## Verdict

Pending. No new training or locked NGA candidate tests are authorized by this entry.

2026-10-30 17:41 UTC completion update: v3 completed all 10,356 rows at 17:38:54,
wrapper rc=0 at 17:38:57; retained inference and independent CPU finisher containers
both exited 0. Independent audit verified 90 frozen / 89 required dependencies and
all row identities, and recomputed the serving and T1 metrics. Status remains
`COMPLETED_SCOPED_REVIEW_REQUIRED`: customer-control-v1 hard accuracy is exactly 1,
and trex_runner-v1 contains only four rows. Bounded diagnosis is pending; neither
flag is erased by the successful artifact checks.

Hard accuracy: 94.917459% over 9,995 hard rows; expected accuracy: 93.004745% over
all 10,356 rows. Serving / T1 NLL: .161449973 / .180290211; soft-target Brier:
.071997176 / .076675304; expected Brier: .091447598 / .096125726; ECE15 with
expected correctness: .011064231 / .024299533. These are the public projection,
not the full original test. E24 automatically launched the separate 176-row
supplement after dependency verification; its final joined result is still pending.

Report SHA256 `fb1083b51963c4e06621fae50f4ad9f2f3132a7d24a23cd84dcfef649c635b7a`;
audit SHA256 `051c99d8cad8c9fb40f62ab914d4324b401cb4611ae055af21eeba376ba27702`.
