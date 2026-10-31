# Experiment wiki

The remote wiki is a collaboration surface for current conclusions. The latest four-dimension report is [`CURRENT-CONCLUSIONS.md`](CURRENT-CONCLUSIONS.md).

Detailed experiment procedures, receipts, raw logs, container records, intermediate reviews and dated process notes are maintained locally under `experiments/` and on CephFS. They are not the remote source of current facts. A milestone refresh updates `CURRENT-CONCLUSIONS.md` and the current pointer in [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md); older snapshots remain local/archive material for traceability.

The normative sources are:

- frozen metrics, splits, thresholds and formulas: `experiments/` preregistrations and the referenced machine-readable matrix;
- current conclusions for collaborators: [`CURRENT-CONCLUSIONS.md`](CURRENT-CONCLUSIONS.md);
- current reference-baseline pointer: [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md).

A result is not accepted merely because a container exited zero. It needs the registered test split, the registered formula and denominator, independent scoring, terminal/recovery evidence and guarded resource release. Dev and calibration values are diagnostic; test split values are the external comparison metrics.
