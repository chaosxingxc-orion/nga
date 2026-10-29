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
A7  ECE: standard 10-bin top-label ECE on held-out floor items; the top label is the argmax of the
    distribution, used as a calibration convention only.
"""
import math
from collections import defaultdict
from itertools import combinations

from common import FLOOR_VARIANT, INVARIANCE_VARIANTS, swap_positions
from decision import argmax_index, cumulative_decision

C = "C"  # the residual branch
ECE_BINS = 10
SWAP_ELIGIBLE_SIDES = ("i",)  # literal reading of pre-reg 3 item 3; ("i", "j") is the symmetric reading
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
        "failures_original": fail_orig, "failures_cumulative": fail_cum,
        "growth": None if fail_orig == 0 else (fail_cum - fail_orig) / fail_orig,
        "argmax_reference": {
            "failures_original": fail_orig_arg, "failures_cumulative": fail_cum_arg,
            "growth": None if fail_orig_arg == 0 else (fail_cum_arg - fail_orig_arg) / fail_orig_arg},
    }


# 2. T1 flip rate -----------------------------------------------------------------------------

def flip_rate(decided, task="T1"):
    """Fraction of the 6 unordered variant pairs of a unit whose decisions differ (C is a decision)."""
    variant_set = INVARIANCE_VARIANTS[task]
    pairs = list(combinations(variant_set, 2))
    flips = {p: 0 for p in pairs}
    n = 0
    for variants in _units(decided, task).values():
        if set(variants) != set(variant_set):
            continue
        n += 1
        for a, b in pairs:
            flips[(a, b)] += variants[a].cum_id != variants[b].cum_id
    return {
        "n_units": n,
        "overall": _rate(sum(flips.values()), n * len(pairs)),
        "per_pair": {f"{a}|{b}": _rate(c, n) for (a, b), c in flips.items()},
    }


# 3. T2 move rate -----------------------------------------------------------------------------

def move_rate(decided):
    out = {}
    for kind in ("swap", "reversed"):
        out[kind] = {"n_eligible": 0, "followed": 0, "unmoved": 0, "moved_elsewhere": 0, "n_ineligible": 0}
    for variants in _units(decided, "T2").values():
        base = variants.get("base")
        if base is None:
            continue
        for name, d in variants.items():
            if name == "base":
                continue
            ij = swap_positions(name)
            if ij is not None:
                bucket, i_pos, j_pos = out["swap"], ij[0], ij[1]
                eligible = base.cum_pos is not None and (
                    (base.cum_pos == i_pos and "i" in SWAP_ELIGIBLE_SIDES)
                    or (base.cum_pos == j_pos and "j" in SWAP_ELIGIBLE_SIDES))
                target = None if not eligible else (j_pos if base.cum_pos == i_pos else i_pos)
            elif name == "reversed":
                bucket = out["reversed"]
                eligible = base.cum_pos is not None
                target = base.cum_pos  # same definition, same list position
            else:
                continue
            if not eligible:
                bucket["n_ineligible"] += 1
                continue
            bucket["n_eligible"] += 1
            if d.cum_pos == target:
                bucket["followed"] += 1
            elif d.cum_id == base.cum_id:
                bucket["unmoved"] += 1
            else:
                bucket["moved_elsewhere"] += 1
    for bucket in out.values():
        n = bucket["n_eligible"]
        for k in ("followed", "unmoved", "moved_elsewhere"):
            bucket[k + "_rate"] = _rate(bucket[k], n)
    return out


# 4. Margin distribution ------------------------------------------------------------------------

def _quantiles(values):
    if not values:
        return None
    s = sorted(values)
    return {f"q{int(q * 100):02d}": s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))] for q in QUANTILES}


def margin_distribution(decided, task="T1"):
    """Share of T1 decisions whose distance to tau exceeds the within-unit score variance (A6)."""
    dists, above, n = [], 0, 0
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
            n += 1
            dists.append(v.dist)
            above += v.dist > variance
    return {"n_decisions": n, "share_distance_above_variance": _rate(above, n),
            "distance_quantiles": _quantiles(dists)}


# 5. C-branch rate ------------------------------------------------------------------------------

def c_branch_rate(decided, task):
    rows = [d for d in decided if d.row["task"] == task]
    return {"n": len(rows), "rate": _rate(sum(d.cum_pos is None for d in rows), len(rows))}


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


def cell_metrics(decided, side):
    """All pre-registered metrics for one cell. ECE only on the held-out side."""
    out = {
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
