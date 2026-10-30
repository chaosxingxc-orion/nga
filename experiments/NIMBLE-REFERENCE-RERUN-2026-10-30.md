# Original Nimble reference rerun with complete dependency freeze

Preregistered 2026-10-30 before E25 launch. This is reference inference, not training.
Normative metrics, populations and numerical interface remain those in E19.

Defects 12 and 16: E19 completed 1,884 predictions but its independent audit rejected
one omitted dependency, the base model `config.json`. Preserve E19 and failed E21
unchanged. E25 reruns all 1,884 records with a complete pre-launch dependency freeze;
no prior prediction is reused. No metric, threshold, checkpoint, seed, temperature,
subset or target is selected from E19 scores.

Seven fixed subsets: MASSIVE en-US/de-DE 350 each, PAWS 250, Civil Comments 300,
Aegis2 250, SummEval relevance 240 and consistency 144. Exact original manifest
hashes and ordered IDs; initial adapter revision
`594dfdcfb6f94e3d0c0db7535180d3c71689169a`, base revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`. Same native v1 prompt, BF16 safe merge,
SDPA backbone, FP32 candidate-token projection, T=1, limit 2048 without truncation.
Original accuracy, Brier variants, NLL, ECE10, score MAE and human distribution
metrics remain separate, as specified in E19. Accuracy is not consistency.

A verifier that accepts every artifact is degenerate; valid full artifacts must
pass, while omitted dependencies, forged reports, changed candidate order and
wrong actual device fail. Before launch, the independent verifier's required-file
set must be a subset of the frozen manifest, including every base file and model
config. Twenty-one verifier tests and three actual finisher subprocess tests
cover positive and negative artifacts. Suspicious numeric extremes, identical
metrics across suites and small groups are review flags, not automatic acceptance.

175 only, same immutable image, chip 3 after old container exit and locked ownership
transfer. New retained detached inference container and CPU observer, CephFS logs,
heartbeat, wrapper EXIT, hash-bound structured terminals, item receipts, and exact
launch/relaunch commands. Existing-terminal retry is rejected; interrupted prefixes
are reused only after the corrected driver's identity checks and a guarded restart.
Full score acceptance requires independent recomputation and source binding,
successful terminal/wrapper, actual exited/0 and flagged-cell review. No Astra
approval or training benefit is implied.
