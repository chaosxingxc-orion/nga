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
| [E1](E1-gdn-fast-ref-gate.md) | admissibility gate for `gdn_fast_ref`, a third gated-delta-rule kernel | R3 round 1 | planned |
| [W1](W1-wave1-first-weight-updates.md) | wave 1: the first weight updates (K1, K2, K1-PT, K1-QO, K1-FLA) | R3 round 1 | planned |

## Where the artifacts live

- Pre-registrations, protocol notes and results documents: `experiments/`
- Code snapshot behind committed results: `experiments/r3_sft/` (working copy on cephfs)
- Run directories, logs, readouts and reports: `/mnt/cephfs/xingchao/experiments/jev/` (not committed)
- Watchdog digest, the only status source the orchestrator reads: `/mnt/cephfs/xingchao/experiments/jev/_watchdog/digest.md`
