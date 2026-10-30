# E30 — Deterministic typed experiment recovery

## Purpose and hypothesis

Defects 12/16: verify actual continued execution and independent acceptance after
explicitly injected signal interruption. Degenerate success-marker-only behavior must fail
missing-item, foreign-container, wrong-device and failed-audit counterparts.

## Setup

See [pre-registration](../experiments/TYPED-RECOVERY-CONTROLLER-2026-10-30.md).
175 CPU-only, existing immutable image, new isolated fixture and controller.
24 deterministic items, actual worker SIGKILL and audit SIGKILL, two retry limit.
No live reference run or NPU allocation is changed.

## Execution

Implementation preparation. Twenty-eight state-machine tests passed with mocked Docker
and real filesystem artifacts. Real retained Docker fault injection awaits parent
implementation review; these tests do not establish real recovery completion.

## Results and verdict

Pending. No global automatic-recovery, model-quality or Astra approval claim.

## Actual execution — 2026-10-30 18:20 UTC

The parent reviewed code, reran all 28 tests, verified all ten frozen files and
approved plan `6d72d8f13a3dac950ebd2cad6c31b5a1f829cb56ae1e76d9191a209ced768edb`.
It then launched retained detached controller and fault injector on 175.
Root: `reference_inference/e30-recovery-fixture-20261030/`.

The worker was actually SIGKILLed after three receipts, restarted once, and
completed all 24 items. Audit generation 0 was actually SIGKILLed and remains
retained with exit 137; generation 1 independently verified all items and sum
of squares 4,324. Controller, worker, successful audit and injector all exited 0;
controller and injector terminal/wrapper timestamps are 18:20:27 UTC.
The parent separately verified all three prefix receipt hashes, full 24-item
coverage and audit output/terminal hashes. No review flags.

- Worker: `de9e10834ed3de250f23a5f4dce317e22053d1885f62440f9d7296bf2bfa29f6`
- Failed audit: `67e5eb6e4c502846fed2db73b24d4d550daf8d312379c829b0fb63e26d1e9b74`
- Successful audit: `5882376e61f1e3e8cb4b0c550dc9a0159dc004b7039efc032d48c9d2a881204f`
- Audit SHA256: `a1c8163a5e7c82ae0d710c0878064118062e676f675105426d9b3948904e2e69`

Verdict: the preregistered isolated CPU double-interruption admission passes.
This does not certify recovery of arbitrary old NPU runs or host/daemon loss.
No existing reference run was interrupted or migrated. A further Astra attempt
returned only guideline acknowledgement, so substantive Astra review is still pending.
