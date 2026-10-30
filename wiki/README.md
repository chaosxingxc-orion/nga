# Experiment wiki

Every experiment in this program is recorded here, one file per experiment, and pushed to
`origin/main`. A run that is not recorded here did not happen as far as the program is concerned.

## The rule

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `wiki/<id>.md` and fill sections 1-3 (**purpose,
   hypothesis, setup**) *before* launching the run. The hypothesis is worthless written afterwards.
2. Fill section 4 (**results**) from the run's own report files, and section 5 (**verdict**) against
   the pre-registered decision lines only.
3. Add the file to the index below, and commit and push. Results are appended; a wrong number is
   corrected by a dated note, not by a silent edit.
4. The pre-registration files under `experiments/` stay the normative source for metrics, thresholds
   and splits. The wiki records what was run and what came out; where the two disagree, the
   pre-registration governs and the wiki entry says so.

English only, as everywhere in this repository (CLAUDE.md §1).

## Index

| id | title | round | status |
| --- | --- | --- | --- |
| [F1](F1-fetch-qwen3-0.6b.md) | fetch `Qwen3-0.6B`, the attention-only control | R0 | done |
| [K0](K0-untuned-readout.md) | untuned readout of the Qwen3.5 checkpoints on Kev's suites and our task set | R3 round 1 | planned |
| [E1](E1-gdn-fast-ref-gate.md) | admissibility gate for `gdn_fast_ref`, a third gated-delta-rule kernel | R3 round 1 | done — (G2) failed, not admitted |
| [W1](W1-wave1-first-weight-updates.md) | wave 1: the first weight updates (K1, K2, K1-PT, K1-QO, K1-FLA) | R3 round 1 | planned |
| [E2](E2-scorer-admissibility-fp32.md) | scorer admissibility: the bf16 table that failed and the fp32 verdict that replaced it | R3 round 1 | done |
| [R0S](R0S-r0-side-fp32-rescore.md) | the R0 side of record: fp32 re-score of `Qwen3.5-0.8B` under the R0 configuration (adoption gate) | R3 round 1 | planned |
| [E3](E3-k0-readout-precondition.md) | the precondition for reading K0: c32 composition control, realized-call replay, provenance re-score with counterpart | R3 round 1 | completed CLEAN; independent Astra review not claimed |
| [E6](E6-reference-inference-20261030.md) | native Kev-0.8B inference compatibility on Ascend | reference evaluation | two development records completed; full test evaluation pending |
| [E7](E7-reference-kev-test-20261030.md) | automatic native Kev-0.8B inference on decision-v7 and transfer-v4 test | reference evaluation | complete; main metrics independently recomputed; Astra review pending |
| [E8](E8-reference-kev-scale-probe-20261030.md) | native Kev-4B development compatibility and efficiency probe | reference evaluation | four development records completed; 9B not run |

## Where the artifacts live

- Pre-registrations, protocol notes and results documents: `experiments/`
- Code snapshot behind committed results: `experiments/r3_sft/` (working copy on cephfs)
- Run directories, logs, readouts and reports: `/mnt/cephfs/xingchao/experiments/jev/` (not committed)
- Watchdog digest, the only status source the orchestrator reads: `/mnt/cephfs/xingchao/experiments/jev/_watchdog/digest.md`
