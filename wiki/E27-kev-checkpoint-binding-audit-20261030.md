# E27 — supplementary Kev checkpoint metadata binding audit

Preregistered 2026-10-30 before execution. No inference, training or fitted metric changes.

## Purpose and counterpart

Defects 12/16: supplement the existing independently recomputed reference metrics with
an explicit frozen checkpoint temperature/base/publication check. Merely trusting the
saved environment can accept an internally consistent wrong temperature; a valid binding
passes, while altered head bytes, wrong temperature/base/release and a driver temperature
override must fail. This is provenance verification, not a decision-consistency metric.

## Setup

Nine completed 175 runs: Kev 0.8B/4B/9B main, extended and devtools tests (E7/E9/E12/E20/E22).
Read `head.pt` with CPU `torch.load(weights_only=True)`; never import the native loader.
Check frozen head/adapter/base marker/config and the frozen driver LoadOptions AST,
recorded environment and per-suite serving temperature, terminal/report/rows bindings.
Map release specifications to the checkpoint README release identifier and published
weight hashes (prefixes where the README provides only prefixes); never infer the mapping
from matching accuracy. Older runs lacking a release spec or launch receipt retain that
explicit limitation. No run artifact is modified. Arithmetic remains the earlier independent
scorer's scope; this audit does not authenticate historical logits or replace Astra review.

## Execution

Output `reference_inference/kev_checkpoint_binding_audit_20261030/`, existing immutable
image, CPU only. Frozen script/tests/prereg, fixed retained detached container, CephFS
log/status/terminal/wrapper and exact relaunch command. New output required after terminal.

## Results and verdict

Pending actual execution. Seven focused valid/corrupt/override tests pass.

2026-10-30 16:59 UTC amendment: first CPU audit exited 1 because the checkpoint
README is not in the inference frozen manifests. README is publication evidence,
not a model loader dependency; the failure is preserved. The revised audit will
freeze its own explicit publication manifest before a new CPU run, label the README
as supplementary rather than original-run-frozen, and still require head/adapter/base
hashes in the original manifest. This does not retroactively add an inference input.

2026-10-30 17:00 UTC result: the fresh v2 audit completed rc 0, wrapper rc 0 and
retained CPU container `nga-kev-checkpoint-binding-audit-v2` exited/0, ID
`39575bc9ea3244b8d3218b11c29522e9b3152dc559abd7ca94f5b06203193615`.
All nine runs passed checkpoint metadata and saved output bindings. All 18 frozen
supplementary audit inputs were rechecked after completion. Report SHA256:
`9f5f7da56a2d3ad8753877815d60c704e1d3bc0c48878e9a0c74394d2670948e`.

| Model | Head temperature | Publication | Completed runs checked |
| --- | ---: | --- | ---: |
| 0.8B | 2.3510958125672174 | kev-08b-r15 | 3 |
| 4B | 2.406050072164233 | kev-4b-r10 | 3 |
| 9B | 2.193649959389252 | kev-9b-r27 | 3 |

E7 has no original saved launch receipt and is explicitly reported as such; the
other eight receipt bindings pass. All nine READMEs are supplementary publication
inputs rather than original frozen inference inputs. Original execution manifests
and output files remain unchanged. Scoped verdict: saved serving temperatures,
base identity, frozen loader options and publication mapping match these checkpoints.
This does not prove historical tensor provenance or replace arithmetic/Astra review.
