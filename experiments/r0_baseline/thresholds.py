"""Fit the cumulative-mass threshold tau on the train split only (pre-reg 2.1 and 3.1).

Held-out rows cannot be passed to ``fit_thresholds``: it accepts a ``split.TrainView`` and nothing
else, and a TrainView can only be built by filtering rows through a splitter.  The returned
``FittedThresholds`` is immutable and is applied unchanged to every row, whichever side it is on.

What the pre-registration fixes: tau is fitted on train, per (question, level-set version), and
applied unchanged to held-out.  What it leaves open, and what is set here as harness constants
(AMBIGUITY A2, to be frozen with the first scored run):

* TAU_GRID: 0.50, 0.55, ..., 0.95.
* Objective: utility = +1 per correct decision, -1 per wrong decision, 0 per C, summed over the
  fitting rows; the best grid value wins, ties go to the larger tau.
* Fitting rows: gold-trusted rows only, i.e. every T1 and T3 variant (T3 gold is the unchanged target gold) and the T2 ``base`` variant.  T2
  swap / reversed rows carry gold that is partly wrong in the task files (see the run report) and
  are never used for fitting; they are decided under the tau of their unit's base level set.
* "Question" = (source, qname), the unit the pre-registration counts (545 for akhilaaa3, 1 for
  openjev-synth, 15 for typed-decisions).
* Fallback when a (question, level-set version) has fewer than MIN_FIT_ITEMS fitting rows, which is
  certain for held-out questions and for the per-item random names:
  tier 1 (source, qname, version) -> tier 2 (source, qname) -> tier 3 (source, level_type, number
  of levels) -> tier 4 DEFAULT_TAU.  Tier usage is counted and reported.
"""
from collections import defaultdict

import split as split_mod
from decision import cumulative_decision

TAU_GRID = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))
MIN_FIT_ITEMS = 20
DEFAULT_TAU = 0.5
TIERS = ("version", "question", "type_size", "default")


def fitting_row(row):
    """True for rows whose gold is trusted enough to fit tau on."""
    if row["gold"] is None:
        return False
    return row["task"] in ("T1", "T3") or row["variant"] == "base"


def tier_keys(row):
    src, q = row["source"], row["qname"]
    return (
        ("version", (src, q, row["tau_lsv"])),
        ("question", (src, q)),
        ("type_size", (src, row["level_type"], len(row["ids"]))),
    )


def _utilities(row):
    """Utility of this row at every grid value."""
    gold_pos = row["ids"].index(row["gold"])
    out = []
    for tau in TAU_GRID:
        pos, _ = cumulative_decision(row["p"], row["level_type"], tau)
        out.append(0 if pos is None else (1 if pos == gold_pos else -1))
    return out


def _utilities_and_decisions(row):
    """Utility and decided flag of this row at every grid value (reporting only, section 11.3)."""
    gold_pos = row["ids"].index(row["gold"])
    util, decided = [], []
    for tau in TAU_GRID:
        pos, _ = cumulative_decision(row["p"], row["level_type"], tau)
        util.append(0 if pos is None else (1 if pos == gold_pos else -1))
        decided.append(pos is not None)
    return util, decided


def _fit_diagnostics(chosen_i, utilities, decisions, n):
    """What the fit saw, for reporting (pre-reg 11.3). Never feeds back into the choice of tau.

    A grid value is *decisive* when the operator commits on at least one fitting row there; the best
    decisive tau is picked with the same tie rule as the fit (larger tau)."""
    decisive = [i for i in range(len(TAU_GRID)) if decisions[i] > 0]
    out = {"n_fit": n, "utility_at_chosen_tau": utilities[chosen_i],
           "abstain_rate_at_chosen_tau": 1 - decisions[chosen_i] / n,
           "utility_by_tau": {str(t): u for t, u in zip(TAU_GRID, utilities)},
           "best_decisive_tau": None, "best_decisive_utility": None, "best_decisive_abstain_rate": None}
    if decisive:
        b = max(decisive, key=lambda i: (utilities[i], i))
        out.update(best_decisive_tau=TAU_GRID[b], best_decisive_utility=utilities[b],
                   best_decisive_abstain_rate=1 - decisions[b] / n)
    return out


class FittedThresholds:
    """Immutable mapping from a row to (tau, tier)."""

    def __init__(self, splitter_name, table, diagnostics=None):
        self._splitter_name = splitter_name
        self._table = dict(table)  # {(tier, key): (tau, n_fit)}
        self._diag = dict(diagnostics or {})  # {(tier, key): fit diagnostics}, reporting only

    @property
    def splitter_name(self):
        return self._splitter_name

    def tau_for(self, row):
        tau, tier, _ = self.lookup(row)
        return tau, tier

    def lookup(self, row):
        """(tau, tier, key) where key identifies the fitted entry (None for the default tier)."""
        for tier, key in tier_keys(row):
            hit = self._table.get((tier, key))
            if hit is not None:
                return hit[0], tier, (tier, key)
        return DEFAULT_TAU, "default", None

    def diagnostics(self, key):
        """Fit diagnostics of an entry returned by ``lookup`` (None for the default tier)."""
        return self._diag.get(key)

    def summary(self):
        counts = defaultdict(int)
        for (tier, _), _ in self._table.items():
            counts[tier] += 1
        return {"splitter": self._splitter_name, "fitted_keys_per_tier": dict(counts)}


def fit_thresholds(train):
    """Fit tau on a TrainView (the only accepted input)."""
    if not isinstance(train, split_mod.TrainView):
        raise TypeError("fit_thresholds needs a split.TrainView; build one with TrainView.of(rows, splitter)")
    for row in train.rows:  # defence in depth: re-check the side of every row
        if train.splitter.assign(row) != split_mod.TRAIN:
            raise ValueError("held-out row found in a TrainView")
    sums = defaultdict(lambda: [0] * len(TAU_GRID))
    decs = defaultdict(lambda: [0] * len(TAU_GRID))
    counts = defaultdict(int)
    for row in train.rows:
        if not fitting_row(row):
            continue
        util, dec = _utilities_and_decisions(row)
        for tier, key in tier_keys(row):
            counts[(tier, key)] += 1
            acc, dacc = sums[(tier, key)], decs[(tier, key)]
            for i, u in enumerate(util):
                acc[i] += u
                dacc[i] += dec[i]
    table, diag = {}, {}
    for tk, n in counts.items():
        if n < MIN_FIT_ITEMS:
            continue
        best = max(range(len(TAU_GRID)), key=lambda i: (sums[tk][i], i))  # ties -> larger tau
        table[tk] = (TAU_GRID[best], n)
        diag[tk] = _fit_diagnostics(best, sums[tk], decs[tk], n)
    return FittedThresholds(train.splitter.name, table, diag)
