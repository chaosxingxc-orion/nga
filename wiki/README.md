# Current experiment conclusions

The remote wiki is the collaboration surface for current conclusions. Start with
[`CURRENT-CONCLUSIONS.md`](CURRENT-CONCLUSIONS.md), which contains the four required dimensions:
Jev gain categories, task and test-set metrics with separate statistical protocols, business
requirement coverage, and the NxM/training/data/RL route.

The remote surface intentionally excludes process logs, dated experiment pages, intermediate
Astra reviews, old pre-registrations and milestone drafts. Those materials remain in the local
three-day archive under `.local/archive/` and are available only for bounded historical lookup.
They are not current-fact authority.

The current tracked machine indexes are in `experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json`
and `experiments/REFERENCE-BASELINE-INCREMENT-2026-10-31.json`. Test-split values are the external
comparison metrics; dev and calibration values are diagnostic only. A missing or blocked cell is
reported as `blocked/null`, never as zero.

Archive policy: at each milestone refresh, process documents older than three days are moved to
`.local/archive/YYYY-MM-DD/`. The latest conclusion page and current machine indexes stay in the
tracked surface. Astra-facing briefs read those current files first and consult the archive only
when a bounded historical question requires it.
