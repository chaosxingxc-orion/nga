"""Track T of the R3 SFT round (R3-SFT-PREREG sec 2.3, 2.5, 2.6, 5, 6): scoring plan, tau fit on the r3tau carve-out, cells on the
selection and report halves, decision lines B-1, B-2, B-2 (T3), B-3 and B-4 with the pass / void / fail rules.

The R0 metric code is reused, not reimplemented: common.load_records / make_row, split.TrainView, thresholds.fit_thresholds,
decision.cumulative_decision (through metrics.Decided), metrics.cell_metrics (floor, flip, move, margin, failure set, ECE,
threshold-fit summary), scorer.ConstantClassifierScorer / UniformScorer. What this module adds is only what R0's metrics.py does
not do and the R3 prereg requires:

  * the tie rule of R0 sec 12.5 / 13.1 on the argmax columns and on the accuracy floor (R0's metrics.py predates amendments 5-6):
      - accuracy floor: a tie at the top is NOT correct (13.1 item 3);
      - flip rate: a variant pair with a tied side is DROPPED from the denominator and counted (13.1 item 1);
      - move rate: an item with a tied base or variant decision is INELIGIBLE and counted (13.1 item 2);
    ties are read from the raw summed scores s_i (R0 sec 13.3), and a cell whose tie rate exceeds 10% carries that rate in every
    metric it reports (13.1, last paragraph);
  * the r3tau tau carve-out and the r3sel halves (sec 2.5, 2.6);
  * the pass / void / fail rule of R0 sec 13.5 (gap = empty-input flip - real flip, both argmax-scored).
"""
import hashlib
import json
from collections import defaultdict
from itertools import combinations

import core_r3 as C
import common as RC            # R0 common.py
import metrics as M            # R0 metrics.py
import scorer as RS            # R0 scorer.py: ConstantClassifierScorer, UniformScorer
import split as S              # R0 split.py
import thresholds as TH        # R0 thresholds.py
from common import FLOOR_VARIANT, INVARIANCE_VARIANTS, LEVEL_TYPES, swap_positions

# ---- frozen constants of the prereg (sec 2.5, 2.6, 6.2, 6.3; R0 sec 3.1, 8.5, 13.1, 13.5) ---------------------------------
R3SEL_PREFIX = "r3sel:"
R3SEL_SELECTION_BELOW = 5000       # bucket < 5000 -> selection half, else report half (sec 2.5)
R3TAU_PREFIX = "r3tau:"
R3TAU_BELOW = 1500                 # group70 train-side groups with bucket < 1500 -> tau-fitting carve-out (sec 2.6)
B1_MARGIN = 0.10                   # operator accuracy >= constant + 10 points (R0 sec 3.1)
B2_PASS_GAP = 0.10                 # gap >= +0.10 passes (R0 sec 13.5)
B2_VOID_BELOW = 0.05               # |gap| < 0.05 voids the cell's T1 numbers (R0 sec 13.5)
B3_FOLLOWED_ABOVE = 0.30           # followed rate > 30% (R0 sec 8.5)
B3_MARGIN_OVER_FLIP = 0.10         # and >= 10 points above the same cell's T1 flip (R0 sec 8.5)
B4_MAX_FLIP_RISE = 0.02            # not raising the T1 argmax flip rate by more than 2 points (sec 6.3)
TIE_RATE_FLAG = 0.10               # R0 sec 13.1: a cell above 10% tie rate carries it in every metric
MIN_N = 30                         # minimum sample count flagged by tools/watchdog.py (default --min-n)
EPS = 1e-9

# ---- named readings of ambiguous clauses (each one is listed in the report) -----------------------------------------------
TIE_NOT_CORRECT_IN_CUM_COLUMN = True       # sec 6.1 "ties per R0 sec 12.5/13.1": 13.1 item 3 is stated for the accuracy floor; applied to both columns
HALF_HASH_FIELD = "group_id"               # sec 2.5: the r3sel hash is of group_id, also for the question70 side of akhilaaa3
QUESTION70_TAU_FROM_GROUP70_CARVEOUT = True    # the additional question70 report of akhilaaa3 uses the same carve-out tau (sec 2.6 names no other)
B1_ROLLUP_INCLUDES_BELOW_MIN_N = True      # "B-1 on that source" (sec 6.3 ruling 3) = every (level type, floor) cell of the source, whatever its n
B1_FLOORS = ("T1", "T2")                   # R0's B-1 lines were evaluated on both floors
B4_ACCURACY_FLOOR = "T1"                   # "improves held-out accuracy": the T1 floor (original variant); T2 base floor reported beside
GATING_VOID_RULE = "any_seed_void_excludes"    # sec 8.2(c): a cell is gating only if not void for either arm at every one of its seeds
THRESHOLDED_COLUMNS_KEEP_R0_TIE_HANDLING = True    # thresholded flip / move columns are R0's, unchanged; only argmax columns and the floor follow 13.1

EXPECTED_TOTALS = {   # sec 2.5, group70 held-out side, distinct (group_id, qname) units: (task, source) -> (selection, report)
    ("T1", "typed-decisions"): (870, 995), ("T2", "typed-decisions"): (870, 995), ("T3", "typed-decisions"): (870, 995),
    ("T1", "openjev-synth"): (540, 608), ("T2", "openjev-synth"): (540, 608),
    ("T1", "akhilaaa3-hard"): (68, 52), ("T2", "akhilaaa3-hard"): (72, 55),
    ("T1", "akhilaaa3-medium"): (19, 53), ("T2", "akhilaaa3-medium"): (19, 54),
}


# ---- splits (sec 2.5, 2.6) ---------------------------------------------------------------------------------------------------

def half_of(group_id):
    """'selection' if bucket(sha256('r3sel:' + group_id)) < 5000 else 'report' (sec 2.5; same bucket convention as split.py)."""
    return "selection" if S.bucket(R3SEL_PREFIX + group_id) < R3SEL_SELECTION_BELOW else "report"


def in_carveout(group_id):
    return S.bucket(R3TAU_PREFIX + group_id) < R3TAU_BELOW


class R3TauSplitter:
    """TrainView adapter for sec 2.6: TRAIN = group70 train-side groups with bucket('r3tau:' + group_id) < 1500; everything else
    HELDOUT. thresholds.fit_thresholds fits on a TrainView built with this splitter, i.e. only on the carve-out."""
    name = "r3tau-carveout"

    def assign(self, row):
        return S.TRAIN if (S.GROUP70.assign(row) == S.TRAIN and in_carveout(row["group_id"])) else S.HELDOUT


CONFIG_R3 = {"name": "r3", "tau_splitter": R3TauSplitter(), "halves": True, "tie_rule": "r13_1"}
# sec 6.3 / 14.5 item 1: the R0 configuration = tau on the full group70 train side, the whole held-out side, and the tie rule the
# PUBLISHED R0 report used (pre-13.1: a top tie resolves to the first maximal index, nothing is dropped or made ineligible).
CONFIG_R0 = {"name": "r0", "tau_splitter": S.GROUP70, "halves": False, "tie_rule": "r0_published"}
CONFIGS = {"r3": CONFIG_R3, "r0": CONFIG_R0}


def is_fitting_record(rec):
    """Record-level mirror of thresholds.fitting_row (which reads readout rows)."""
    return rec.get("gold_id") is not None and (rec["task"] in ("T1", "T3") or rec["variant"] == "base")


def records_needed(records, config):
    """The records a model must score for `config` (everything else is never read by any metric):
    r3: the tau carve-out (fitting rows only), the whole group70 held-out side, and akhilaaa3's question70 held-out side;
    r0: the whole group70 train side (fitting rows only) and the whole group70 held-out side."""
    out = []
    for r in records:
        g70 = S.GROUP70.assign(r)
        if g70 == S.HELDOUT:
            out.append(r)
        elif config["name"] == "r3":
            if (in_carveout(r["group_id"]) and is_fitting_record(r)) or (
                    r["source"].startswith("akhilaaa3") and S.QUESTION70.assign(r) == S.HELDOUT):
                out.append(r)
        elif is_fitting_record(r):
            out.append(r)
    return out


def limit_groups(records, n_per_category):
    """Dry-run helper: keep the first n groups (by split hash) in each category carve-out / selection half / report half /
    group70 train rest, so that every part of the report has rows. n=0 keeps everything. tau versions are recomputed."""
    if not n_per_category:
        return records
    cats = defaultdict(set)
    for r in records:
        g = r["group_id"]
        if S.GROUP70.assign(r) == S.TRAIN:
            cats["carve" if in_carveout(g) else "train_rest"].add(g)
        else:
            cats[half_of(g)].add(g)
    keep = set()
    for c, gs in cats.items():
        keep |= set(sorted(gs, key=lambda g: (S.bucket(g), g))[:n_per_category])
    kept = [r for r in records if r["group_id"] in keep]
    RC._assign_tau_versions(kept)
    return kept


def shard_of(group_id, num_shards):
    """Shard of a group (run_baseline.py convention: digest bytes 8..16, independent of the split bucket in bytes 0..8)."""
    if num_shards <= 1:
        return 0
    return int.from_bytes(hashlib.sha256(group_id.encode("utf-8")).digest()[8:16], "big") % num_shards


# ---- cell sizes and the sec 2.5 counts -----------------------------------------------------------------------------------------

def cell_sizes(records):
    """Distinct (group_id, qname) units per (task, source, level type, half) on the group70 held-out side (sec 2.5: printed in
    every Track T report)."""
    units = defaultdict(set)
    for r in records:
        if S.GROUP70.assign(r) == S.HELDOUT:
            units[(r["task"], r["source"], r["level_type"], half_of(r["group_id"]))].add((r["group_id"], r["qname"]))
    out = {}
    for (task, src, lt, half), u in units.items():
        out.setdefault(task, {}).setdefault(src, {}).setdefault(lt, {})[half] = len(u)
    return out


def check_totals(records):
    """sec 2.5 cross-check: distinct (group_id, qname) units per (task, source, half) against the prereg's totals. Returns
    {"ok", "mismatches", "totals"}. Only meaningful for the unlimited record set."""
    units = defaultdict(set)
    for r in records:
        if S.GROUP70.assign(r) == S.HELDOUT:
            units[(r["task"], r["source"], half_of(r["group_id"]))].add((r["group_id"], r["qname"]))
    totals = {f"{t}/{s}": [len(units.get((t, s, "selection"), ())), len(units.get((t, s, "report"), ()))]
              for (t, s) in sorted({(t, s) for (t, s, _) in units})}
    bad = [{"cell": f"{t}/{s}", "expected": list(exp), "got": totals.get(f"{t}/{s}")} for (t, s), exp in sorted(EXPECTED_TOTALS.items())
           if totals.get(f"{t}/{s}") != list(exp)]
    return {"clause": "sec 2.5", "ok": not bad, "mismatches": bad, "totals": totals}


# ---- readout rows and tie-aware decisions -------------------------------------------------------------------------------------

def make_readout(rec, s, probs=None):
    """R0 readout row (common.make_row) plus the raw scores and the tie flag (R0 sec 12.6, 13.3). `probs` overrides softmax(s)
    for the constant classifier, whose distribution is one-hot by definition (R0 sec 4 item 3)."""
    row = RC.make_row(rec, C.softmax(s) if probs is None else probs)
    row["s"] = list(s)
    row["tie"] = C.is_tie(s)
    return row


class TDecided(M.Decided):
    """metrics.Decided plus `tie`: exact tie at the top of the raw scores (of the probabilities, for rows without s)."""
    __slots__ = ("tie",)

    def __init__(self, row, tau, tier):
        super().__init__(row, tau, tier)
        s = row.get("s")
        if s:
            self.tie = C.is_tie(s)
        else:
            top = max(row["p"])
            self.tie = sum(1 for p in row["p"] if p == top) >= 2


def decide_rows(rows, fitted):
    out = []
    for r in rows:
        tau, tier = fitted.tau_for(r)
        out.append(TDecided(r, tau, tier))
    return out


def _rate(num, den):
    return None if den == 0 else num / den


def tie_summary(decided):
    n = len(decided)
    t = sum(d.tie for d in decided)
    rate = _rate(t, n)
    return {"n": n, "tie_count": t, "tie_rate": rate, "tie_rate_over_10pct": bool(rate is not None and rate > TIE_RATE_FLAG)}


def accuracy_floor_r3(decided, task):
    """R0 accuracy floor with the 13.1 item 3 rule: a tie at the top is not correct. Cumulative-mass operator (primary,
    C = wrong) and the argmax reference column; the tie rate is reported beside."""
    rows = [d for d in decided if d.row["task"] == task and d.row["variant"] == FLOOR_VARIANT[task] and d.row["gold"] is not None]
    n = len(rows)
    cum_ok = sum(d.cum_id == d.row["gold"] and not (d.tie and TIE_NOT_CORRECT_IN_CUM_COLUMN) for d in rows)
    arg_ok = sum(d.arg_id == d.row["gold"] and not d.tie for d in rows)
    return {"n": n, "acc_cumulative": _rate(cum_ok, n), "acc_argmax_reference": _rate(arg_ok, n), **tie_summary(rows),
            "tie_rule": "a tie at the top is not correct (R0 sec 13.1 item 3)"}


def flip_rate_r3(decided, task="T1"):
    """R0 flip_rate (thresholded column, C-branch rate, unit count: unchanged) with the argmax column recomputed under 13.1
    item 1: a pair with a tied side is dropped from the denominator and the dropped count is reported."""
    base = M.flip_rate(decided, task)
    variant_set = INVARIANCE_VARIANTS[task]
    pairs = list(combinations(variant_set, 2))
    flips = {p: 0 for p in pairs}
    used = {p: 0 for p in pairs}
    dropped = {p: 0 for p in pairs}
    for variants in M._units(decided, task).values():
        if set(variants) != set(variant_set):
            continue
        for a, b in pairs:
            if variants[a].tie or variants[b].tie:
                dropped[(a, b)] += 1
                continue
            used[(a, b)] += 1
            flips[(a, b)] += variants[a].arg_pos != variants[b].arg_pos
    den = sum(used.values())
    base["argmax_reference"] = {
        "overall": _rate(sum(flips.values()), den),
        "per_pair": {f"{a}|{b}": _rate(flips[(a, b)], used[(a, b)]) for a, b in pairs},
        "n_pairs_used": den, "n_pairs_dropped_tie": sum(dropped.values()),
        "n_pairs_total": den + sum(dropped.values()),
        "per_pair_dropped": {f"{a}|{b}": dropped[(a, b)] for a, b in pairs},
        "scored_on": M.SCORED_ON_ARGMAX, "tie_rule": "pair dropped when either side is tied (R0 sec 13.1 item 1)"}
    covered = [v for variants in M._units(decided, task).values() if set(variants) == set(variant_set) for v in variants.values()]
    base["tie"] = tie_summary(covered)
    return base


def move_rate_r3(decided):
    """R0 move_rate with the argmax columns recomputed under 13.1 item 2: an item whose base or variant decision is tied is
    ineligible (counted in n_ineligible and n_ineligible_tie)."""
    out = M.move_rate(decided)
    arg = {k: {"n_eligible": 0, "followed": 0, "unmoved": 0, "moved_elsewhere": 0, "n_ineligible": 0, "n_ineligible_tie": 0}
           for k in ("swap", "reversed")}
    for variants in M._units(decided, "T2").values():
        base = variants.get("base")
        if base is None:
            continue
        for name, d in variants.items():
            if name == "base":
                continue
            ij = swap_positions(name)
            if ij is not None:
                bucket, i_pos, j_pos = arg["swap"], ij[0], ij[1]
                eligible = (base.arg_pos == i_pos and "i" in M.SWAP_ELIGIBLE_SIDES) or (base.arg_pos == j_pos and "j" in M.SWAP_ELIGIBLE_SIDES)
                target = j_pos if base.arg_pos == i_pos else i_pos
            elif name == "reversed":
                bucket, eligible, target = arg["reversed"], True, base.arg_pos
            else:
                continue
            if base.tie:                       # eligibility cannot be judged from a tied base decision
                bucket["n_ineligible"] += 1
                bucket["n_ineligible_tie"] += 1
                continue
            if not eligible:
                bucket["n_ineligible"] += 1
                continue
            if d.tie:
                bucket["n_ineligible"] += 1
                bucket["n_ineligible_tie"] += 1
                continue
            bucket["n_eligible"] += 1
            if d.arg_pos == target:
                bucket["followed"] += 1
            elif d.arg_id == base.arg_id:
                bucket["unmoved"] += 1
            else:
                bucket["moved_elsewhere"] += 1
    for kind, b in arg.items():
        n = b["n_eligible"]
        for k in ("followed", "unmoved", "moved_elsewhere"):
            b[k + "_rate"] = _rate(b[k], n)
        out[kind]["argmax_reference"] = {**b, "scored_on": M.SCORED_ON_ARGMAX, "tie_rule": "item ineligible when base or variant is tied (R0 sec 13.1 item 2)"}
    return out


def cell_metrics_r3(decided, fitted):
    """All R0 cell metrics for one cell with the 13.1 tie rules on the argmax columns and the floor. Every metric carries the
    cell's tie rate and whether it exceeds 10% (13.1, last paragraph)."""
    m = M.cell_metrics(decided, "heldout", fitted)
    m["floor_T1"] = accuracy_floor_r3(decided, "T1")
    m["floor_T2"] = accuracy_floor_r3(decided, "T2")
    m["flip_T1"] = flip_rate_r3(decided, "T1")
    m["move_T2"] = move_rate_r3(decided)
    if any(d.row["task"] == "T3" for d in decided):
        m["floor_T3"] = accuracy_floor_r3(decided, "T3")
        m["flip_T3"] = flip_rate_r3(decided, "T3")
    cell_tie = tie_summary(decided)
    m["tie"] = cell_tie
    # R3 sec 14.9 item 5: the near-tie census of the cell's raw scores (gold-free: the cell mixes tasks and variants)
    m["near_tie_census"] = C.near_tie_census([d.row["s"] for d in decided if d.row.get("s")], keys=[d.row.get("k") for d in decided if d.row.get("s")],
                                    option_ids=[d.row["ids"] for d in decided if d.row.get("s")])
    flag = {"cell_tie_rate": cell_tie["tie_rate"], "cell_tie_rate_over_10pct": cell_tie["tie_rate_over_10pct"]}
    for key in ("floor_T1", "floor_T2", "floor_T3", "flip_T1", "flip_T3", "failure_set_T1", "failure_set_T3", "margin_T1", "margin_T3"):
        if key in m:
            m[key].update(flag)
    for kind in ("swap", "reversed"):
        m["move_T2"][kind]["argmax_reference"].update(flag)
    m["below_min_n"] = {k: m[k]["n"] for k in ("floor_T1", "floor_T2") if m[k]["n"] < MIN_N}
    return m


def cell_metrics_r0_rule(decided, fitted):
    """The metrics of R0's own metrics.cell_metrics (the tie rule the PUBLISHED R0 report used, pre-13.1), with the keys the decision
    lines read added in a way that changes no number: the tie summary is reported beside, and the counts of pairs dropped / items made
    ineligible by a tie are 0 because this rule never drops or excludes. Used by CONFIG_R0 (sec 6.3, 14.5 item 1)."""
    m = M.cell_metrics(decided, "heldout", fitted)
    note = "R0 published rule (pre-13.1): a top tie resolves to the first maximal index; the tie count is reported beside, nothing is dropped"
    for task in ("T1", "T2", "T3"):
        key = f"floor_{task}"
        if key in m:
            rows = [d for d in decided if d.row["task"] == task and d.row["variant"] == FLOOR_VARIANT[task] and d.row["gold"] is not None]
            m[key].update(tie_summary(rows))
            m[key]["tie_rule"] = note
    for key in ("flip_T1", "flip_T3"):
        if key in m:
            n_pairs = m[key]["n_units"] * len(INVARIANCE_VARIANTS["T3" if key == "flip_T3" else "T1"]) * (len(INVARIANCE_VARIANTS["T3" if key == "flip_T3" else "T1"]) - 1) // 2
            m[key]["argmax_reference"].update({"n_pairs_used": n_pairs, "n_pairs_total": n_pairs, "n_pairs_dropped_tie": 0, "tie_rule": note})
            m[key]["tie"] = tie_summary(decided)
    for kind in ("swap", "reversed"):
        m["move_T2"][kind]["argmax_reference"].update({"n_ineligible_tie": 0, "tie_rule": note})
    cell_tie = tie_summary(decided)
    m["tie"] = cell_tie
    m["below_min_n"] = {k: m[k]["n"] for k in ("floor_T1", "floor_T2") if m[k]["n"] < MIN_N}
    return m


CELL_METRICS = {"r13_1": cell_metrics_r3, "r0_published": cell_metrics_r0_rule}


# ---- building the Track T block -----------------------------------------------------------------------------------------------

ROLES = ("primary", "empty_input", "question_only", "constant", "uniform")
MODEL_ROLES = {"primary": "full", "empty_input": "blank", "question_only": "drop"}


def constant_and_uniform_rows(all_records, needed_records_list):
    """R0 degenerate rows without a model: the constant classifier fitted on the group70 train side (and, for akhilaaa3, the
    question70 train side), one-hot; uniform. Scores `s` are the one-hot / uniform values themselves."""
    out = {"constant": [], "uniform": []}
    consts = {}
    for splitter in (S.GROUP70, S.QUESTION70):
        rel = [r for r in all_records if splitter in S.splitters_for_source(r["source"])]
        if rel:
            c = RS.ConstantClassifierScorer(splitter.name)
            c.fit(S.TrainView.of(rel, splitter))
            consts[splitter.name] = c
    for r in needed_records_list:
        c = consts["group70"]
        onehot = c.score([r])[0]
        out["constant"].append(make_readout(r, onehot, probs=onehot))
        out["uniform"].append(make_readout(r, [1.0 / len(r["levels"])] * len(r["levels"])))
    return out


def build_track_t(rows_by_role, records_for_sizes, config=CONFIG_R3, meta=None):
    """Assemble the Track T block from readout rows per role. Pure function of its inputs (no model)."""
    block = {"config": config["name"], "tie_rule": config["tie_rule"], "tau_splitter": config["tau_splitter"].name, "clauses": ["sec 2.3", "sec 2.5", "sec 2.6", "sec 5", "sec 6.1", "sec 6.2"],
             "constants": {"R3SEL_SELECTION_BELOW": R3SEL_SELECTION_BELOW, "R3TAU_BELOW": R3TAU_BELOW, "MIN_N": MIN_N, "TIE_RATE_FLAG": TIE_RATE_FLAG,
                           "B1_MARGIN": B1_MARGIN, "B2_PASS_GAP": B2_PASS_GAP, "B2_VOID_BELOW": B2_VOID_BELOW,
                           "B3_FOLLOWED_ABOVE": B3_FOLLOWED_ABOVE, "B3_MARGIN_OVER_FLIP": B3_MARGIN_OVER_FLIP, "B4_MAX_FLIP_RISE": B4_MAX_FLIP_RISE},
             "readings": {"TIE_NOT_CORRECT_IN_CUM_COLUMN": TIE_NOT_CORRECT_IN_CUM_COLUMN, "HALF_HASH_FIELD": HALF_HASH_FIELD,
                          "QUESTION70_TAU_FROM_GROUP70_CARVEOUT": QUESTION70_TAU_FROM_GROUP70_CARVEOUT,
                          "B1_ROLLUP_INCLUDES_BELOW_MIN_N": B1_ROLLUP_INCLUDES_BELOW_MIN_N, "B1_FLOORS": list(B1_FLOORS),
                          "B4_ACCURACY_FLOOR": B4_ACCURACY_FLOOR, "GATING_VOID_RULE": GATING_VOID_RULE,
                          "THRESHOLDED_COLUMNS_KEEP_R0_TIE_HANDLING": THRESHOLDED_COLUMNS_KEEP_R0_TIE_HANDLING},
             "meta": meta or {}, "cell_sizes": cell_sizes(records_for_sizes), "tau_fit": {}, "cells": {}, "question70": {}}
    for role in ROLES:
        rows = rows_by_role.get(role)
        if not rows:
            block.setdefault("missing_roles", []).append(role)
            continue
        view = S.TrainView.of(rows, config["tau_splitter"])
        fitted = TH.fit_thresholds(view)
        decided = decide_rows(rows, fitted)
        block["tau_fit"][role] = {"carveout_rows": len(view), "fitted": fitted.summary(),
                                  "rows_decided_by_tier": dict(_count(d.tier for d in decided if S.GROUP70.assign(d.row) == S.HELDOUT))}
        by_cell, by_cell_q = defaultdict(list), defaultdict(list)
        for d in decided:
            r = d.row
            half = half_of(r["group_id"]) if config["halves"] else "all"
            if S.GROUP70.assign(r) == S.HELDOUT:
                by_cell[(half, r["source"], r["level_type"])].append(d)
            if config["name"] == "r3" and r["source"].startswith("akhilaaa3") and S.QUESTION70.assign(r) == S.HELDOUT:
                by_cell_q[(half, r["source"], r["level_type"])].append(d)
        for target, cells in ((block["cells"], by_cell), (block["question70"], by_cell_q)):
            for (half, source, lt), ds in cells.items():
                target.setdefault(half, {}).setdefault(source, {}).setdefault(lt, {})[role] = CELL_METRICS[config["tie_rule"]](ds, fitted)
    report_key = "report" if config["halves"] else "all"
    block["decision_lines"] = {report_key: decision_lines(block["cells"].get(report_key, {}))}
    if config["halves"]:
        block["selection"] = selection_summary(block["cells"].get("selection", {}))
    return block


def _count(it):
    c = defaultdict(int)
    for x in it:
        c[x] += 1
    return c


# ---- decision lines (sec 6.2) ----------------------------------------------------------------------------------------------------

def _ge(a, b):
    return a >= b - EPS


def b2_status(gap):
    """R0 sec 13.5: gap >= +0.10 passes; |gap| < 0.05 voids the cell's T1 numbers; otherwise B-2 fails and nothing is void."""
    if gap is None:
        return "undefined"
    if _ge(gap, B2_PASS_GAP):
        return "pass"
    if abs(gap) < B2_VOID_BELOW - EPS:
        return "void"
    return "fail"


def _b2_line(source, lt, real_m, empty_m, key):
    real, empty = real_m[key]["argmax_reference"], empty_m[key]["argmax_reference"]
    gap = None if real["overall"] is None or empty["overall"] is None else empty["overall"] - real["overall"]
    return {"source": source, "level_type": lt, "scored_on": "argmax", "real_flip": real["overall"], "empty_input_flip": empty["overall"],
            "gap": gap, "status": b2_status(gap), "n_units": real_m[key]["n_units"], "n_units_empty_input": empty_m[key]["n_units"],
            "n_pairs_used": real["n_pairs_used"], "n_pairs_dropped_tie": real["n_pairs_dropped_tie"],
            "empty_input_n_pairs_used": empty["n_pairs_used"], "empty_input_n_pairs_dropped_tie": empty["n_pairs_dropped_tie"],
            "real_c_branch_rate": real_m[key]["c_branch"]["rate"], "empty_input_c_branch_rate": empty_m[key]["c_branch"]["rate"],
            "cell_tie_rate": real_m["tie"]["tie_rate"], "cell_tie_rate_over_10pct": real_m["tie"]["tie_rate_over_10pct"],
            "below_min_n": real_m[key]["n_units"] < MIN_N,
            "real_flip_thresholded": real_m[key]["thresholded"]["overall"], "empty_input_flip_thresholded": empty_m[key]["thresholded"]["overall"]}


def decision_lines(cells_half):
    """B-1, B-2, B-2 (T3), B-3 on one half ({source: {level_type: {role: cell metrics}}}); the report half for the lines of record."""
    out = {"B-1": [], "B-1_by_source": {}, "B-2": [], "B-2_T3": [], "B-3": []}
    for source in sorted(cells_half):
        for lt in LEVEL_TYPES:
            roles = cells_half[source].get(lt)
            if not roles or "primary" not in roles:
                continue
            p = roles["primary"]
            if "constant" in roles:
                for task in B1_FLOORS:
                    a, b = p[f"floor_{task}"]["acc_cumulative"], roles["constant"][f"floor_{task}"]["acc_cumulative"]
                    if a is not None and b is not None:
                        out["B-1"].append({"source": source, "level_type": lt, "floor": task, "operator_accuracy": a, "constant_accuracy": b,
                                           "difference": a - b, "pass": _ge(a - b, B1_MARGIN), "n": p[f"floor_{task}"]["n"],
                                           "below_min_n": p[f"floor_{task}"]["n"] < MIN_N, "tie_rate": p[f"floor_{task}"]["tie_rate"]})
            if "empty_input" in roles and p["flip_T1"]["n_units"]:
                out["B-2"].append(_b2_line(source, lt, p, roles["empty_input"], "flip_T1"))
            if "flip_T3" in p and "empty_input" in roles and "flip_T3" in roles["empty_input"]:
                out["B-2_T3"].append(_b2_line(source, lt, p, roles["empty_input"], "flip_T3"))
            sw = p["move_T2"]["swap"]["argmax_reference"]
            fr, flip = sw["followed_rate"], p["flip_T1"]["argmax_reference"]["overall"]
            if fr is not None:
                ok = None if flip is None else (fr > B3_FOLLOWED_ABOVE and _ge(fr - flip, B3_MARGIN_OVER_FLIP))
                out["B-3"].append({"source": source, "level_type": lt, "scored_on": "argmax", "followed_rate": fr, "n_eligible": sw["n_eligible"],
                                   "n_ineligible": sw["n_ineligible"], "n_ineligible_tie": sw["n_ineligible_tie"],
                                   "above_30_percent": fr > B3_FOLLOWED_ABOVE, "t1_flip_same_cell": flip,
                                   "followed_minus_flip": None if flip is None else fr - flip,
                                   "exceeds_flip_by_10_points": None if flip is None else _ge(fr - flip, B3_MARGIN_OVER_FLIP),
                                   "pass": ok, "below_min_n": sw["n_eligible"] < MIN_N,
                                   "cell_tie_rate": p["tie"]["tie_rate"], "cell_tie_rate_over_10pct": p["tie"]["tie_rate_over_10pct"]})
    by_src = defaultdict(list)
    for ln in out["B-1"]:
        if B1_ROLLUP_INCLUDES_BELOW_MIN_N or not ln["below_min_n"]:
            by_src[ln["source"]].append(ln)
    out["B-1_by_source"] = {s: {"pass": all(l["pass"] for l in ls), "n_cells": len(ls), "includes_below_min_n": any(l["below_min_n"] for l in ls)}
                            for s, ls in sorted(by_src.items())}
    return out


def selection_summary(cells_selection):
    """Per (source, level type) on the selection half: primary T1 argmax flip rate (with n and dropped pairs) and the B-2 status of
    the cell (needed by the sec 8.2(c) gating rule)."""
    out = {}
    for source in sorted(cells_selection):
        for lt in LEVEL_TYPES:
            roles = cells_selection[source].get(lt)
            if not roles or "primary" not in roles:
                continue
            p = roles["primary"]
            e = roles.get("empty_input")
            line = _b2_line(source, lt, p, e, "flip_T1") if e is not None and p["flip_T1"]["n_units"] else None
            out.setdefault(source, {})[lt] = {
                "flip_T1_argmax": p["flip_T1"]["argmax_reference"]["overall"], "n_units": p["flip_T1"]["n_units"],
                "n_pairs_used": p["flip_T1"]["argmax_reference"]["n_pairs_used"], "n_pairs_dropped_tie": p["flip_T1"]["argmax_reference"]["n_pairs_dropped_tie"],
                "b2_status": None if line is None else line["status"], "b2_gap": None if line is None else line["gap"],
                "floor_T1_acc_cumulative": p["floor_T1"]["acc_cumulative"], "floor_T1_n": p["floor_T1"]["n"]}
    return out


# ---- B-4 (sec 6.3, ruling 3) ----------------------------------------------------------------------------------------------------

def b4_lines(trained, base, half="report"):
    """B-4 per (source, level type) cell of `half`: the trained model improves held-out accuracy (T1 floor, cumulative-mass
    operator) over its untuned base without raising the T1 argmax flip rate by more than 2 points. Admissible only where the
    TRAINED model clears B-1 on the source (ruling 3), else the verdict is 'not admissible', not 'fail'. A prompt-version or
    configuration mismatch voids the comparison (R0 sec 8.7)."""
    tm, bm = trained.get("meta", {}), base.get("meta", {})
    mismatch = []
    if trained.get("config") != base.get("config"):
        mismatch.append(f"configuration differs: {trained.get('config')} vs {base.get('config')}")
    if tm.get("prompt_version") != bm.get("prompt_version"):
        mismatch.append(f"prompt version differs: {tm.get('prompt_version')} vs {bm.get('prompt_version')}")
    b1 = trained["decision_lines"][half]["B-1_by_source"]
    lines = []
    tc, bc = trained["cells"].get(half, {}), base["cells"].get(half, {})
    for source in sorted(tc):
        for lt in LEVEL_TYPES:
            t = tc.get(source, {}).get(lt, {}).get("primary")
            b = bc.get(source, {}).get(lt, {}).get("primary")
            if t is None or b is None:
                continue
            fl = f"floor_{B4_ACCURACY_FLOOR}"
            acc_t, acc_b = t[fl]["acc_cumulative"], b[fl]["acc_cumulative"]
            f_t, f_b = t["flip_T1"]["argmax_reference"]["overall"], b["flip_T1"]["argmax_reference"]["overall"]
            admissible = b1.get(source, {}).get("pass", False)
            if mismatch:
                verdict = "void"
            elif not admissible:
                verdict = "not admissible"
            elif None in (acc_t, acc_b, f_t, f_b):
                verdict = "undefined"
            else:
                verdict = "pass" if (acc_t > acc_b and (f_t - f_b) <= B4_MAX_FLIP_RISE + EPS) else "fail"
            lines.append({"source": source, "level_type": lt, "verdict": verdict, "admissible": admissible,
                          "trained_accuracy": acc_t, "base_accuracy": acc_b, "accuracy_gain": None if None in (acc_t, acc_b) else acc_t - acc_b,
                          "trained_t1_flip": f_t, "base_t1_flip": f_b, "flip_rise": None if None in (f_t, f_b) else f_t - f_b,
                          "n_trained": t[fl]["n"], "n_base": b[fl]["n"], "flip_n_pairs_trained": t["flip_T1"]["argmax_reference"]["n_pairs_used"],
                          "flip_n_pairs_base": b["flip_T1"]["argmax_reference"]["n_pairs_used"],
                          "t2_floor_accuracy_trained": t["floor_T2"]["acc_cumulative"], "t2_floor_accuracy_base": b["floor_T2"]["acc_cumulative"],
                          "below_min_n": min(t[fl]["n"], b[fl]["n"]) < MIN_N, "mismatch": mismatch})
    return lines


def roll_up_seeds(per_seed_lines, key=("source", "level_type"), status=lambda l: l.get("pass", l.get("status", l.get("verdict")))):
    """sec 6.2: 'a line is reported as passed for an arm only if it passes for every seed'. `per_seed_lines` is a list (one per
    seed) of line lists; returns {key tuple: {"passed": bool, "per_seed": [...]}}. A line missing for a seed does not pass."""
    keys = []
    for ls in per_seed_lines:
        for l in ls:
            k = tuple(l.get(f) for f in key + (("floor",) if "floor" in l else ()))
            if k not in keys:
                keys.append(k)
    out = {}
    for k in keys:
        per = []
        for ls in per_seed_lines:
            hit = [l for l in ls if tuple(l.get(f) for f in key + (("floor",) if "floor" in l else ())) == k]
            per.append(status(hit[0]) if hit else None)
        out[k] = {"passed": all(v is True or v == "pass" for v in per), "per_seed": per}
    return out


# ---- markdown -----------------------------------------------------------------------------------------------------------------------

def _f(x, pct=True):
    if x is None:
        return "-"
    return f"{100 * x:.1f}" if pct else f"{x:.4g}"


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def render_markdown(block):
    out = [f"## Track T (config `{block['config']}`, tau fitted on `{block['tau_splitter']}`)", ""]
    out += ["All rates are percentages. Every cell is (source, level type); n is the unit or row count the rate rests on. "
            "Ties follow R0 sec 13.1 (floor: not correct; flip: pair dropped; move: item ineligible). `<30` marks n below the minimum sample count.", ""]
    rows = []
    for task, srcs in sorted(block["cell_sizes"].items()):
        for src, lts in sorted(srcs.items()):
            for lt, halves in sorted(lts.items()):
                rows.append([task, src, lt, halves.get("selection", 0), halves.get("report", 0)])
    out += ["### Cell sizes (distinct group_id x qname units on the group70 held-out side; sec 2.5)", "",
            _table(["task", "source", "level type", "selection half", "report half"], rows), ""]
    rows = [[role, v["carveout_rows"], v["fitted"]["fitted_keys_per_tier"], v["rows_decided_by_tier"]] for role, v in block["tau_fit"].items()]
    out += ["### Tau fit (carve-out rows and fallback-tier usage; sec 2.6)", "",
            _table(["role", "carve-out rows", "fitted keys per tier", "held-out rows decided per tier"], rows), ""]
    for half, cells in sorted(block["cells"].items()):
        rows = []
        for source in sorted(cells):
            for lt in LEVEL_TYPES:
                for role in ROLES:
                    m = cells[source].get(lt, {}).get(role)
                    if not m:
                        continue
                    f1, f2, fl = m["floor_T1"], m["floor_T2"], m["flip_T1"]
                    sw = m["move_T2"]["swap"]["argmax_reference"]
                    rows.append([source, lt, role, f1["n"], _f(f1["acc_cumulative"]), _f(f1["acc_argmax_reference"]), f2["n"], _f(f2["acc_cumulative"]),
                                 fl["n_units"], _f(fl["argmax_reference"]["overall"]), fl["argmax_reference"]["n_pairs_dropped_tie"], _f(fl["thresholded"]["overall"]),
                                 _f(fl["c_branch"]["rate"]), sw["n_eligible"], _f(sw["followed_rate"]), _f(m["tie"]["tie_rate"]) + ("*" if m["tie"]["tie_rate_over_10pct"] else ""),
                                 "<30" if m["below_min_n"] else ""])
        out += [f"### Cells, half `{half}`", "",
                _table(["source", "level type", "role", "T1 n", "T1 acc (operator)", "T1 acc (argmax)", "T2 n", "T2 acc (operator)", "T1 units",
                        "T1 flip (argmax)", "dropped pairs", "T1 flip (thresholded)", "C-rate", "swap eligible", "followed (argmax)", "tie rate (*>10%)", "n"], rows), ""]
    for half, dl in block["decision_lines"].items():
        out += [f"### Decision lines of record, half `{half}`", ""]
        out += ["B-1 (operator accuracy >= constant + 10 points):", "",
                _table(["source", "level type", "floor", "n", "operator", "constant", "diff", "pass"],
                       [[l["source"], l["level_type"], l["floor"], l["n"], _f(l["operator_accuracy"]), _f(l["constant_accuracy"]), _f(l["difference"]), l["pass"]]
                        for l in dl["B-1"]]), "",
                "B-1 by source (every cell must pass): " + ", ".join(f"{s}: {v['pass']}" for s, v in dl["B-1_by_source"].items()), ""]
        for name in ("B-2", "B-2_T3"):
            out += [f"{name} (gap = empty-input flip - real flip, argmax; pass >= +10, void |gap| < 5, else fail):", "",
                    _table(["source", "level type", "units", "real flip", "empty flip", "gap", "status", "dropped pairs (real/empty)", "C-rate (real/empty)", "tie rate"],
                           [[l["source"], l["level_type"], l["n_units"], _f(l["real_flip"]), _f(l["empty_input_flip"]), _f(l["gap"]), l["status"],
                             f"{l['n_pairs_dropped_tie']}/{l['empty_input_n_pairs_dropped_tie']}", f"{_f(l['real_c_branch_rate'])}/{_f(l['empty_input_c_branch_rate'])}",
                             _f(l["cell_tie_rate"])] for l in dl[name]]), ""]
        out += ["B-3 (followed > 30% and >= 10 points above the same cell's T1 flip):", "",
                _table(["source", "level type", "eligible", "ineligible (tie)", "followed", "T1 flip", "diff", "pass"],
                       [[l["source"], l["level_type"], l["n_eligible"], f"{l['n_ineligible']} ({l['n_ineligible_tie']})", _f(l["followed_rate"]),
                         _f(l["t1_flip_same_cell"]), _f(l["followed_minus_flip"]), l["pass"]] for l in dl["B-3"]]), ""]
    if "selection" in block:
        rows = [[s, lt, v["n_units"], _f(v["flip_T1_argmax"]), v["n_pairs_dropped_tie"], v["b2_status"], _f(v["floor_T1_acc_cumulative"])]
                for s, lts in block["selection"].items() for lt, v in lts.items()]
        out += ["### Selection-half T1 flip and B-2 status (feeds sec 8.2 c; not a decision line)", "",
                _table(["source", "level type", "units", "T1 flip (argmax)", "dropped pairs", "B-2 status", "T1 acc (operator)"], rows), ""]
    return "\n".join(out)
