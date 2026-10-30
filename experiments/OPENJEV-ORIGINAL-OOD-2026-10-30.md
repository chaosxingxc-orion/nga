# E32 — Original complete Open-Jev OOD reference inference

Pre-registration, 2026-10-30, before any E32 launch. Defects 12/16 concern
measurement provenance and generalization evidence. A degenerate optimum is to
report a plausible aggregate from a different split or incomplete population.
Counterparts reject renamed test rows, wrong data hash, duplicate/missing IDs,
changed model/prompt dependencies, incomplete lengths and forged receipt totals.
No invariant model-quality claim follows from checksum equality.

Population: exact restored `release-v2/ood.jsonl`, 15,920 ordered rows, 15,446
hard and 474 soft targets, SHA256
`9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee`.
All original `split=ood` fields, IDs, options, source/group identities and targets
remain unchanged. Direct full-population inference avoids splitting into the
15,701-row public projection and 219-row supplement. This is an OOD evaluation,
never a renamed test split or combination with the original test denominator.

Checkpoints and native interfaces are exactly the E14/E18 Open-Jev 2B/9B sources,
base revisions, adapter/readout weights, native BF16 unmerged backbone and FP32
head, native SDPA path and 4,096-candidate-prompt token limit. Temperatures remain
2B=1.518796342858676 and 9B=1.8969118766347646; no OOD fit. Full CPU token preflight
precedes NPU inference, with no truncation. Any overlength blocks that model's
full claim and is reported, not silently skipped. Existing successful native
probes/public execution establish the model path; this new population still
requires full length admission. Per-chip throughput and reserved memory remain
in the inference heartbeat; a newly observed efficiency defect is investigated.

Metrics retain E14/E18/native `jev.metrics.evaluate_probabilities` arithmetic:
hard accuracy on 15,446 hard rows; expected accuracy, NLL, soft-target summed
Brier, expected Brier (including target irreducible uncertainty), ECE15 using
expected correctness on all 15,920. Preserve serving-temperature and raw T=1
panels plus source/kind breakdowns. Missing/failed rows do not become zero-filled
probabilities; no completed aggregate is published before full coverage. Perfect
rates, tiny cells and suspicious identical metrics retain independent audit flags.
Metric differences from other benchmark definitions are explicitly labelled.

Execution uses authorized 175 only and the existing immutable image. New frozen
run directories and retained fixed-name Docker containers have CephFS logs,
timestamped progress, terminal markers, item-granularity resume and exact relaunch
scripts. A parent review binds each configuration hash before CPU preflight or
NPU launch. NPU allocation must already be explicitly released; launch checks
actual live device maps while holding the allocation lock. No live run is adopted,
stopped or mutated. A separate detached CPU finisher waits for inference's bound
terminal and actual Docker exit, independently recomputes coverage/probabilities/
metrics and rechecks completion. All failed evidence is retained.

Acceptance: exact original population and model binding, full eligible preflight,
15,920 valid inference receipts, terminal/wrapper and retained-container exit 0,
independent metric audit, explicit review flags and report hashes. No full OOD
metric, training gain, complete automatic recovery or Astra approval is claimed
by preparation, preflight, a successful shell command or this protocol.
