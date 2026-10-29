"""Metrics, exactly as defined in R0-BASELINE-PREREG.md section 3.

Every function takes ``Decided`` rows (a readout row plus its decisions) and returns plain dicts.
Nothing here pools across sources or level types: callers pass the rows of one cell, where a cell
is (split, side, source, level_type).  Decisions are made by the cumulative-mass operator;
``argmax`` appears only as the reference column of the accuracy floor and in the ECE convention.
There is no expectation operator anywhere.

Ambiguities in the pre-registration, and the reading implemented (the decision operator's reading, A1, is in decision.py; threshold fitting, A2, in thresholds.py; rendering, A3, in prompt.py):
A4  cumulative failure set: union over the four T1 name variants of the items that fail (C is a
    failure); reported for T1 only, because T2 variants carry different gold by design.
A5  swap eligibility: only items whose base decision is list position i of ``swap_i_j`` (literal
    reading).  Positions, not ids: ids never move in a swap.  ``reversed`` items: followed means
    the decision stays on the same definition, which sits at the same list position (ids are
    reversed, definitions are not); a decision on the same id that is not followed is unmoved.
A6  margin: distance (decision.cumulative_decision) compared with the within-group variance of
    level probabilities across the four T1 variants of the unit, averaged over levels.  The
    pre-registration says "variance"; a distance (probability units) is compared with a variance
    (squared units) exactly as written.  T1 only: T2 has no equivalence class.
A8  amendment 4 + 11.8 (both columns under explicit parents ``argmax_reference`` / ``thresholded``, no bare keys) (pre-reg section 11): flip rates are primary on argmax (a statement about the model)
    with the thresholded rate beside them (a statement about the operator);
    a thresholded rate over rows with no decision is null, never 0.0; every flip rate carries the C-branch
    rate of the rows it was computed over; margin counts decisions, not rows; a C-branch rate of exactly
    0.0 or 1.0 is flagged as forced by the fitted tau.  The move rate is likewise carried on argmax
    (``argmax_reference`` / ``thresholded`` inside each kind), which is what section 8.2 asked for and B-3 now reads.
A7  ECE: standard 10-bin top-label ECE on held-out floor items; the top label is the argmax of the
    distribution, used as a calibration convention only.
"""
import math
from collections import defaultdict
from itertools import combinations

from common import FLOOR_VARIANT, INVARIANCE_VARIANTS, swap_positions
from decision import argmax_index, cumulative_decision
from thresholds import DECISIVE_MAX_ABSTAIN

C = "C"  # the residual branch
ECE_BINS = 10
SWAP_ELIGIBLE_SIDES = ("i",)  # literal reading of pre-reg 3 item 3; ("i", "j") is the symmetric reading
SCORED_ON_ARGMAX = "argmax (statement about the model; primary, pre-reg 11.2)"
SCORED_ON_THRESHOLDED = "cumulative-mass operator (statement about the operator)"
QUANTILES = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)


class Decided:
    """A readout row with the decisions made on it."""

    __slots__ = ("row", "tau", "tier", "cum_pos", "dist", "arg_pos")

    def __init__(self, row, tau, tier):
        self.row = row
        self.tau = tau
        self.tier = tier
        self.cum_pos, self.dist = cumulative_decision(row["p"], row["level_type"], tau)
        self.arg_pos = argmax_index(row["p"])

    @property
    def cum_id(self):
        return C if self.cum_pos is None else self.row["ids"][self.cum_pos]

    @property
    def arg_id(self):
        return self.row["ids"][self.arg_pos]


def decide_rows(rows, thresholds):
    out = []
    for r in rows:
        tau, tier = thresholds.tau_for(r)
        out.append(Decided(r, tau, tier))
    return out


def _rate(num, den):
    return None if den == 0 else num / den


def _units(decided, task):
    """{unit: {variant: Decided}} for one task."""
    units = defaultdict(dict)
    for d in decided:
        if d.row["task"] == task:
            units[d.row["unit"]][d.row["variant"]] = d
    return units


# 1. Accuracy floor ---------------------------------------------------------------------------

def accuracy_floor(decided, task):
    """Accuracy on the floor variant (T1 original / T2 base) against gold, cumulative-mass operator
    with the argmax reference column. A C decision is counted as wrong."""
    rows = [d for d in decided if d.row["task"] == task and d.row["variant"] == FLOOR_VARIANT[task]
            and d.row["gold"] is not None]
    n = len(rows)
    cum_ok = sum(d.cum_id == d.row["gold"] for d in rows)
    arg_ok = sum(d.arg_id == d.row["gold"] for d in rows)
    return {"n": n, "acc_cumulative": _rate(cum_ok, n), "acc_argmax_reference": _rate(arg_ok, n)}


def failure_sets(decided, task="T1"):
    """Cumulative failure set across the variants of an invariance task (A4)."""
    variant_set = INVARIANCE_VARIANTS[task]
    ref = FLOOR_VARIANT[task]
    fail_orig = fail_cum = fail_orig_arg = fail_cum_arg = n = 0
    for variants in _units(decided, task).values():
        if set(variants) != set(variant_set) or variants[ref].row["gold"] is None:
            continue
        n += 1
        gold = variants[ref].row["gold"]
        wrong = [v.cum_id != gold for v in variants.values()]
        wrong_arg = [v.arg_id != gold for v in variants.values()]
        fail_orig += variants[ref].cum_id != gold
        fail_orig_arg += variants[ref].arg_id != gold
        fail_cum += any(wrong)
        fail_cum_arg += any(wrong_arg)
    return {
        "n_units": n,
        "thresholded": {
            "scored_on": SCORED_ON_THRESHOLDED,
            "failures_original": fail_orig, "failures_cumulative": fail_cum,
            "growth": None if fail_orig == 0 else (fail_cum - fail_orig) / fail_orig},
        "argmax_reference": {
            "scored_on": SCORED_ON_ARGMAX,
            "failures_original": fail_orig_arg, "failures_cumulative": fail_cum_arg,
            "growth": None if fail_orig_arg == 0 else (fail_cum_arg - fail_orig_arg) / fail_orig_arg},
    }


# 2. T1 flip rate -----------------------------------------------------------------------------

def _forced_flag(rate, ds):
    """Pre-reg 11.5: a C-branch rate of exactly 0.0 or 1.0 says something about the fitted tau, not the model."""
    taus = sorted({d.tau for d in ds})
    out = {"fitted_taus": taus, "forced_by_tau": rate is not None and rate in (0.0, 1.0), "forced_reason": None}
    if out["forced_by_tau"]:
        if rate == 1.0:
            out["forced_reason"] = "every row abstained under the fitted tau"
        elif taus == [0.5] and all(len(d.row["ids"]) == 2 for d in ds):
            out["forced_reason"] = "tau 0.50 with two levels: abstention is arithmetically impossible"
        else:
            out["forced_reason"] = "no row abstained under the fitted tau"
    return out


def _c_summary(ds):
    n = len(ds)
    rate = _rate(sum(d.cum_pos is None for d in ds), n)
    return {"n": n, "rate": rate, **_forced_flag(rate, ds)}


def flip_rate(decided, task="T1"):
    """Fraction of the 6 unordered variant pairs of a unit whose decisions differ (C is a decision).

    ``argmax_reference`` is the primary column (statement about the model, pre-reg 11.2): the same
    computation over argmax positions.  ``overall`` / ``per_pair`` are the thresholded column
    (statement about the operator).  The thresholded rate is null when the rows it covers contain no
    decision at all (pre-reg 11.1); ``c_branch`` is the C-branch rate of those same rows."""
    variant_set = INVARIANCE_VARIANTS[task]
    pairs = list(combinations(variant_set, 2))
    flips = {p: 0 for p in pairs}
    flips_arg = {p: 0 for p in pairs}
    decided_pair = {p: 0 for p in pairs}  # units where at least one of the pair's two variants has a decision
    n = 0
    covered = []
    for variants in _units(decided, task).values():
        if set(variants) != set(variant_set):
            continue
        n += 1
        covered.extend(variants.values())
        for a, b in pairs:
            flips[(a, b)] += variants[a].cum_id != variants[b].cum_id
            flips_arg[(a, b)] += variants[a].arg_pos != variants[b].arg_pos
            decided_pair[(a, b)] += variants[a].cum_pos is not None or variants[b].cum_pos is not None
    c = _c_summary(covered)  # C-branch rate of the rows both columns were computed over
    n_decisions = sum(d.cum_pos is not None for d in covered)
    overall = _rate(sum(flips.values()), n * len(pairs)) if n_decisions else None
    # pre-reg 11.8 clause 1: no bare overall / per_pair; both columns sit under an explicit parent.
    return {
        "n_units": n,
        "n_decisions": n_decisions,
        "c_branch": c,
        "argmax_reference": {
            "overall": _rate(sum(flips_arg.values()), n * len(pairs)),
            "per_pair": {f"{a}|{b}": _rate(c_, n) for (a, b), c_ in flips_arg.items()},
            "scored_on": SCORED_ON_ARGMAX},
        "thresholded": {
            "overall": overall,
            "per_pair": {f"{a}|{b}": (_rate(flips[(a, b)], n) if decided_pair[(a, b)] else None) for a, b in pairs},
            "scored_on": SCORED_ON_THRESHOLDED},
    }


# 3. T2 move rate -----------------------------------------------------------------------------

def _move_buckets(decided, pos_of, id_of):
    """Move-rate buckets with decisions read through ``pos_of`` / ``id_of`` (Decided -> list position or None / id)."""
    out = {}
    for kind in ("swap", "reversed"):
        out[kind] = {"n_eligible": 0, "followed": 0, "unmoved": 0, "moved_elsewhere": 0, "n_ineligible": 0}
    for variants in _units(decided, "T2").values():
        base = variants.get("base")
        if base is None:
            continue
        base_pos = pos_of(base)
        for name, d in variants.items():
            if name == "base":
                continue
            ij = swap_positions(name)
            if ij is not None:
                bucket, i_pos, j_pos = out["swap"], ij[0], ij[1]
                eligible = base_pos is not None and (
                    (base_pos == i_pos and "i" in SWAP_ELIGIBLE_SIDES)
                    or (base_pos == j_pos and "j" in SWAP_ELIGIBLE_SIDES))
                target = None if not eligible else (j_pos if base_pos == i_pos else i_pos)
            elif name == "reversed":
                bucket = out["reversed"]
                eligible = base_pos is not None
                target = base_pos  # same definition, same list position
            else:
                continue
            if not eligible:
                bucket["n_ineligible"] += 1
                continue
            bucket["n_eligible"] += 1
            if pos_of(d) == target:
                bucket["followed"] += 1
            elif id_of(d) == id_of(base):
                bucket["unmoved"] += 1
            else:
                bucket["moved_elsewhere"] += 1
    for bucket in out.values():
        n = bucket["n_eligible"]
        for k in ("followed", "unmoved", "moved_elsewhere"):
            bucket[k + "_rate"] = _rate(bucket[k], n)
    return out


def move_rate(decided):
    """Per kind (swap / reversed): ``argmax_reference`` (primary per pre-reg 8.2 and 11.2, the column B-3
    reads) and ``thresholded``; no bare counts or rates (pre-reg 11.8 clause 1)."""
    thr = _move_buckets(decided, lambda d: d.cum_pos, lambda d: d.cum_id)
    arg = _move_buckets(decided, lambda d: d.arg_pos, lambda d: d.arg_id)
    return {kind: {"argmax_reference": {**arg[kind], "scored_on": SCORED_ON_ARGMAX},
                   "thresholded": {**thr[kind], "scored_on": SCORED_ON_THRESHOLDED}} for kind in thr}


# 4. Margin distribution ------------------------------------------------------------------------

def _quantiles(values):
    if not values:
        return None
    s = sorted(values)
    return {f"q{int(q * 100):02d}": s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))] for q in QUANTILES}


def margin_distribution(decided, task="T1"):
    """Share of T1 decisions whose distance to tau exceeds the within-unit score variance (A6).

    Only rows that produced a decision count (pre-reg 11.4): the ordinal operator returns a distance
    even when it abstains, and that distance is not a margin of any decision.  The statistic is null
    when there is no decision."""
    dists, above, n, n_rows = [], 0, 0, 0
    for variants in _units(decided, task).values():
        if set(variants) != set(INVARIANCE_VARIANTS[task]):
            continue
        ids = variants[FLOOR_VARIANT[task]].row["ids"]
        per_level = []
        for j, level_id in enumerate(ids):
            ps = [v.row["p"][v.row["ids"].index(level_id)] for v in variants.values()]
            mean = math.fsum(ps) / len(ps)
            per_level.append(math.fsum((p - mean) ** 2 for p in ps) / len(ps))
        variance = math.fsum(per_level) / len(per_level)
        for v in variants.values():
            n_rows += 1
            if v.cum_pos is None:
                continue
            n += 1
            dists.append(v.dist)
            above += v.dist > variance
    return {"n_decisions": n, "n_rows": n_rows, "share_distance_above_variance": _rate(above, n),
            "distance_quantiles": _quantiles(dists)}


# 5. C-branch rate ------------------------------------------------------------------------------

def c_branch_rate(decided, task):
    return _c_summary([d for d in decided if d.row["task"] == task])


# 6. Calibration --------------------------------------------------------------------------------

def ece(decided):
    """Top-label ECE against gold on floor items, 10 equal-width bins (A7)."""
    bins = [[0, 0.0, 0] for _ in range(ECE_BINS)]  # count, confidence sum, correct
    n = 0
    for d in decided:
        r = d.row
        if r["variant"] != FLOOR_VARIANT[r["task"]] or r["gold"] is None:
            continue
        conf = r["p"][d.arg_pos]
        b = bins[min(ECE_BINS - 1, int(conf * ECE_BINS))]
        b[0] += 1
        b[1] += conf
        b[2] += d.arg_id == r["gold"]
        n += 1
    if n == 0:
        return {"n": 0, "ece": None}
    total = math.fsum(abs(b[1] / b[0] - b[2] / b[0]) * b[0] for b in bins if b[0])
    return {"n": n, "ece": total / n}


MAX_FIT_ENTRIES = 5  # fitted entries listed individually per cell (akhilaaa3 has hundreds of questions)


def threshold_fit_summary(decided, fitted):
    """Per-cell report of what threshold fitting did (pre-reg 11.3). Reporting only: nothing here
    feeds back into the fit.  ``fitted`` is a thresholds.FittedThresholds (or None to skip diagnostics)."""
    n = len(decided)
    tiers = defaultdict(int)
    taus = defaultdict(int)
    entries = {}
    for d in decided:
        tiers[d.tier] += 1
        taus[d.tau] += 1
        if fitted is not None:
            _, _, key = fitted.lookup(d.row)
            e = entries.setdefault(key, [0, fitted.diagnostics(key) if key else None, d.tau, d.tier])
            e[0] += 1
    out = {"n_rows": n, "rows_by_tier": dict(tiers), "rows_by_tau": {str(t): c for t, c in sorted(taus.items())}}
    if fitted is None:
        return out
    diag_rows = [e for e in entries.values() if e[1] is not None]
    # Collapsed = the fit chose a tau that is not decisive (abstain rate > 0.5, pre-reg 11.8 clause 2).
    collapsed = [e for e in diag_rows if e[1]["abstain_rate_at_chosen_tau"] > DECISIVE_MAX_ABSTAIN]
    out["n_fitted_entries"] = len(diag_rows)
    out["share_rows_in_collapsed_entries"] = _rate(sum(e[0] for e in collapsed), n)
    out["entries"] = [
        {"rows": rows, "tier": tier, "fitted_tau": tau, "n_fit": diag["n_fit"],
         "utility_at_fitted_tau": diag["utility_at_chosen_tau"],
         "abstain_rate_at_fitted_tau": diag["abstain_rate_at_chosen_tau"],
         "best_decisive_tau": diag["best_decisive_tau"], "best_decisive_utility": diag["best_decisive_utility"],
         "best_decisive_abstain_rate": diag["best_decisive_abstain_rate"],
         "utility_by_tau": diag["utility_by_tau"], "abstain_rate_by_tau": diag["abstain_rate_by_tau"],
         "collapsed": diag["abstain_rate_at_chosen_tau"] > DECISIVE_MAX_ABSTAIN}
        for rows, diag, tau, tier in sorted(diag_rows, key=lambda e: -e[0])[:MAX_FIT_ENTRIES]]
    return out


def cell_metrics(decided, side, fitted=None):
    """All pre-registered metrics for one cell. ECE only on the held-out side."""
    out = {
        "threshold_fit": threshold_fit_summary(decided, fitted),
        "floor_T1": accuracy_floor(decided, "T1"),
        "floor_T2": accuracy_floor(decided, "T2"),
        "failure_set_T1": failure_sets(decided),
        "flip_T1": flip_rate(decided),
        "move_T2": move_rate(decided),
        "margin_T1": margin_distribution(decided),
        "c_branch": {"T1": c_branch_rate(decided, "T1"), "T2": c_branch_rate(decided, "T2")},
    }
    if side == "heldout":
        out["ece"] = ece(decided)
    # T3 (question-set invariance): same definitions as T1, along the prefix-question axis.
    if any(d.row["task"] == "T3" for d in decided):
        out["floor_T3"] = accuracy_floor(decided, "T3")
        out["failure_set_T3"] = failure_sets(decided, "T3")
        out["flip_T3"] = flip_rate(decided, "T3")
        out["margin_T3"] = margin_distribution(decided, "T3")
        out["c_branch"]["T3"] = c_branch_rate(decided, "T3")
    return out
