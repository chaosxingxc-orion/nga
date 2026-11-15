"""Track K secondary measures (R3-SFT-PREREG sec 4.4-4.8): order-permutation flip rate, none-of-the-above pair, and the
operator column. All functions take RAW per-option scores (sec 3.2), keyed by core_r3.kev_key, so any scorer can feed them.

Secondary metrics gate nothing in this round (sec 4.7): nothing in this module returns a pass/fail verdict.

Construction of the variants (sec 2.2, 4.5, 4.6): Kev's frozen suites already contain the `permuted`, `none_present` and
`none_absent` questions (convert_kev.py writes them to <split>.variants.jsonl); they are deterministic by construction
(fixed files, sha256 in KEV/manifest.json). A variant links to its clean parent by kev.parent_id + kev.qindex. This module
never generates a variant; it only pairs them with their parents and refuses a pair whose parent is missing.
"""
import core_r3 as C
import metrics as M            # R0 metric code (Decided)
import split as S
import thresholds as TH
from common import levelset_version

# ---- named constants for the readings of ambiguous clauses (every one is listed in the report) ------------------------
# sec 4.5 says tied pairs are dropped "(R0 sec 13.1 item 1)". sec 4.6 is silent on ties in the NOTA pair: the literal
# reading is the Track K headline rule (sec 4.2: first maximal index wins) with the R0-convention number beside it.
NOTA_TIE_RULE_PRIMARY = "kev"          # "kev" (first maximal index) or "r0" (a tie is not a choice)
# sec 4.5: "accuracy on the permuted rows and the share of pairs correct on both sides, reported beside the flip rate".
# Literal reading: accuracy over ALL permuted rows of the partition (same-order ones included); both-correct share over
# the pairs that enter the flip denominator (not excluded, not dropped).
BOTH_CORRECT_DENOMINATOR = "flip_denominator_pairs"
# sec 4.4: transfer-v4 has no calibration partition "so its sources fall to the (type, size) tier". R0's tier 3 is keyed
# (source, level_type, n_levels); a transfer-v4 source never occurs in decision-v7 calibration, so with R0's code unchanged
# (the clause says "unchanged") the sources fall through to tier 4, tau = 0.5. This constant records the reading.
OPERATOR_FALLBACK_READING = "r0_unchanged: transfer-v4 sources reach tier 4 (default tau 0.5)"

PERMUTED_SANITY_LABEL = ("SANITY METRIC, IN-DISTRIBUTION: this arm was trained with sec 3.4 option shuffling, so the "
                         "flip rate is not an invariance finding (sec 4.8)")
PERMUTED_INVARIANCE_LABEL = "invariance measurement, untrained model (K0): the only arm whose permutation numbers may be read as invariance (sec 4.8)"


def index_rows(rows):
    return {C.kev_key(r): r for r in rows}


# ---- sec 4.5 permutation pairs ----------------------------------------------------------------------------------------

def build_permutation_pairs(clean_rows, variant_rows):
    """sec 4.5: the unit is a (clean parent, permuted) pair. Returns a list of dicts
    {parent, permuted, same_order}; `same_order` pairs are EXCLUDED from the flip rate and counted (they would contribute 0
    by construction). A parent that is missing, or whose option set / gold differs from the permuted row, is an error."""
    parents = index_rows(clean_rows)
    pairs = []
    for v in variant_rows:
        if v["variant"] != "permuted":
            continue
        p = parents.get(C.parent_key(v))
        if p is None:
            raise ValueError(f"permuted row {C.kev_key(v)} has no clean parent {C.parent_key(v)}")
        if sorted(C.level_ids(p)) != sorted(C.level_ids(v)) or p["gold"] != v["gold"]:
            raise ValueError(f"permuted row {C.kev_key(v)}: option set or gold differs from its parent")
        pairs.append({"parent": p, "permuted": v, "same_order": C.level_ids(p) == C.level_ids(v)})
    return pairs


def permutation_metrics(pairs, scores, operator=None, arm_kind="K0"):
    """sec 4.5/4.8/10.1. `scores` maps core_r3.kev_key -> raw s for clean parents AND permuted rows.

    A flip means the chosen level id differs; a pair where either side is tied at the top is dropped and counted.
    `operator(row, s) -> position or None` (optional) supplies the C-branch rate (sec 10.1: a flip rate carries its
    C-branch rate) over the rows of the flip denominator. `arm_kind` "K0" labels the number an invariance measurement;
    every other arm labels it a sanity metric (sec 4.8)."""
    total = len(pairs)
    excluded = sum(1 for p in pairs if p["same_order"])
    used = [p for p in pairs if not p["same_order"]]
    dropped = flips = both_correct = den = c_n = c_rows = 0
    for p in used:
        sp, sv = scores[C.kev_key(p["parent"])], scores[C.kev_key(p["permuted"])]
        if C.is_tie(sp) or C.is_tie(sv):
            dropped += 1
            continue
        den += 1
        ip, iv = C.level_ids(p["parent"])[C.argmax_first(sp)], C.level_ids(p["permuted"])[C.argmax_first(sv)]
        flips += int(ip != iv)
        both_correct += int(ip == p["parent"]["gold"] and iv == p["permuted"]["gold"])
        if operator is not None:
            for row, s in ((p["parent"], sp), (p["permuted"], sv)):
                c_rows += 1
                c_n += int(operator(row, s) is None)
    perm_rows = [p["permuted"] for p in pairs]
    perm_acc = C.headline(perm_rows, [scores[C.kev_key(r)] for r in perm_rows]) if perm_rows else None
    return {
        "clause": "sec 4.5 / 4.8",
        "label": PERMUTED_INVARIANCE_LABEL if arm_kind == "K0" else PERMUTED_SANITY_LABEL,
        "n_pairs_total": total, "n_excluded_same_order": excluded, "n_pairs_eligible": len(used),
        "n_dropped_tied_pairs": dropped, "n": den, "n_flips": flips,
        "flip_rate": (flips / den) if den else None,
        "c_branch": {"n": c_rows, "rate": (c_n / c_rows) if c_rows else None,
                     "note": "operator column tau; None when no operator was supplied"},
        "discrimination_counterpart": {
            "permuted_rows_accuracy": perm_acc,
            "both_sides_correct": {"n": den, "share": (both_correct / den) if den else None,
                                   "denominator": BOTH_CORRECT_DENOMINATOR}},
    }


# ---- sec 4.6 none-of-the-above pair -----------------------------------------------------------------------------------

def build_nota_units(clean_rows, variant_rows):
    """sec 4.6: the unit is a parent that carries BOTH NOTA variants. Returns [{parent, present, absent, nota_id}]."""
    parents = index_rows(clean_rows)
    by_parent = {}
    for v in variant_rows:
        if v["variant"] in ("none_present", "none_absent"):
            by_parent.setdefault(C.parent_key(v), {})[v["variant"]] = v
    units = []
    for pk, d in by_parent.items():
        if "none_present" not in d or "none_absent" not in d:
            continue
        p = parents.get(pk)
        if p is None:
            raise ValueError(f"NOTA variants of {pk} have no clean parent")
        nota = d["none_present"]["kev"]["none_key"]
        if d["none_absent"]["kev"]["none_key"] != nota:
            raise ValueError(f"{pk}: the two NOTA variants use different none keys")
        if nota not in C.level_ids(d["none_present"]) or nota not in C.level_ids(d["none_absent"]):
            raise ValueError(f"{pk}: NOTA option missing from a variant")
        if d["none_absent"]["gold"] != nota:
            raise ValueError(f"{pk}: none_absent gold is not the NOTA option")
        if d["none_present"]["gold"] != p["gold"] or p["gold"] not in C.level_ids(d["none_present"]):
            raise ValueError(f"{pk}: none_present must keep the parent's gold")
        units.append({"parent": p, "present": d["none_present"], "absent": d["none_absent"], "nota_id": nota})
    return units


def nota_metrics(units, scores):
    """sec 4.6: none_absent NOTA-selection rate; none_present accuracy and false-NOTA rate; both-sides-right.
    Reported under both tie rules (Kev first-max, R0 tie-is-not-a-choice); `NOTA_TIE_RULE_PRIMARY` marks the headline."""
    out = {}
    for rule in ("kev", "r0"):
        sel = acc = false_nota = both = 0
        for u in units:
            sa, sp = scores[C.kev_key(u["absent"])], scores[C.kev_key(u["present"])]
            ta, tp = C.is_tie(sa), C.is_tie(sp)
            pa = C.level_ids(u["absent"])[C.argmax_first(sa)]
            pp = C.level_ids(u["present"])[C.argmax_first(sp)]
            if rule == "r0":
                pa = None if ta else pa
                pp = None if tp else pp
            a_sel = pa == u["nota_id"]
            p_ok = pp == u["present"]["gold"]
            sel += a_sel
            acc += p_ok
            false_nota += pp == u["nota_id"]
            both += a_sel and p_ok
        n = len(units)
        out[rule] = {"n": n, "none_absent_nota_selection_rate": sel / n if n else None,
                     "none_present_accuracy": acc / n if n else None,
                     "none_present_false_nota_rate": false_nota / n if n else None,
                     "both_sides_right": both / n if n else None}
    return {"clause": "sec 4.6", "primary_tie_rule": NOTA_TIE_RULE_PRIMARY, "n_parents_with_both": len(units),
            "tie_count_none_absent": sum(C.is_tie(scores[C.kev_key(u["absent"])]) for u in units),
            "tie_count_none_present": sum(C.is_tie(scores[C.kev_key(u["present"])]) for u in units),
            **out[NOTA_TIE_RULE_PRIMARY], "kev_rule": out["kev"], "r0_rule": out["r0"],
            "optima_note": "always-NOTA = 1.0 on none_absent / 0 on none_present; never-NOTA the reverse; both score 0 on both-sides-right (sec 4.6)"}


# ---- sec 4.4 operator column --------------------------------------------------------------------------------------------

class CalibrationSplitter:
    """TrainView adapter: the R0 threshold fit accepts only a split.TrainView. For Track K the fitting rows are exactly the
    decision-v7 calibration partition (sec 4.4), so `assign` is TRAIN for calibration rows and HELDOUT for all others."""
    name = "decision-v7-calibration"

    def assign(self, row):
        return S.TRAIN if row.get("partition") == "calibration" else S.HELDOUT


def to_r0_row(row, s, partition):
    """Map a converted-Kev row and its raw scores to the readout-row shape the R0 operator/threshold code reads.
    task='T1', variant='original' are fixed dummies: they make thresholds.fitting_row accept every clean Kev row
    (all Kev gold is trusted); no Track T meaning is attached."""
    return {"task": "T1", "variant": "original", "source": row["source"], "qname": row["qname"], "level_type": row["level_type"],
            "ids": C.level_ids(row), "gold": row["gold"], "p": C.softmax(s), "tau_lsv": levelset_version(row["levels"]),
            "partition": partition, "k": C.kev_key(row)}


def fit_operator(cal_rows, cal_scores):
    """sec 4.4: tau fitted per model on decision-v7 calibration with R0's grid, utility, tie rule and fallback tiers."""
    rows = [to_r0_row(r, s, "calibration") for r, s in zip(cal_rows, cal_scores)]
    return TH.fit_thresholds(S.TrainView.of(rows, CalibrationSplitter()))


def operator_decision(fitted, row, s):
    """(position or None for C, tau, tier) of the R0 cumulative-mass operator on one converted-Kev row."""
    r0 = to_r0_row(row, s, "apply")
    tau, tier = fitted.tau_for(r0)
    return M.Decided(r0, tau, tier).cum_pos, tau, tier


def operator_column(rows, scores, fitted, partition):
    """sec 4.4: accuracy (C counts as wrong), C-branch rate and fitted tau, never compared with a Kev number."""
    n = correct = c_n = ties = 0
    taus, tiers = {}, {}
    for row, s in zip(rows, scores):
        pos, tau, tier = operator_decision(fitted, row, s)
        n += 1
        correct += pos is not None and pos == C.gold_index(row)
        c_n += pos is None
        ties += C.is_tie(s)
        taus[tau] = taus.get(tau, 0) + 1
        tiers[tier] = tiers.get(tier, 0) + 1
    return {"clause": "sec 4.4", "label": "a statement about the harness, not about the model", "partition": partition,
            "n": n, "accuracy": correct / n if n else None, "tie_count": ties,
            "c_branch": {"n": n, "rate": c_n / n if n else None},
            "rows_by_tau": {str(t): v for t, v in sorted(taus.items())}, "rows_by_tier": tiers,
            "fitted": fitted.summary(), "fallback_reading": OPERATOR_FALLBACK_READING}
