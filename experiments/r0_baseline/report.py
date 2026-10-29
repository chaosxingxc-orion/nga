"""Assemble the pre-registered baseline report from raw readouts.

Input: readout rows per scorer.  For every split, every scorer fits tau on its own train rows
(thresholds.fit_thresholds, TrainView only), decides every row with the fitted thresholds, and the
metrics are computed per cell = (split, side, source, level_type).  There is no pooled row.

Scorer roles shown side by side (pre-reg section 4: degenerate baselines are never omitted):
primary, primary+empty_input, primary+question_only, constant@<split>, uniform.

Decision lines B-1, B-2 and B-3 are evaluated mechanically from the numbers with the constants of
pre-registration section 3.1.  B-3's "clearly above the T1 flip rate" has no number in the
pre-registration, so only the 30% part is a verdict and the flip rate is printed beside it.
B-4 needs a second, post-training report and is not evaluated here.
"""
from collections import defaultdict

import metrics as M
import split as S
import thresholds as TH
from common import LEVEL_TYPES

B1_MARGIN = 0.10          # untuned readout beats the constant classifier by >= 10 points
B2_MARGIN = 0.10          # real-model flip rate >= 10 points below the empty-input baseline
B2_VOID_WITHIN = 0.05     # within 5 points of the empty-input baseline: T1 numbers void
B3_FOLLOWED_ABOVE = 0.30  # T2 followed rate above 30%

ROLE_ORDER = ("primary", "empty_input", "question_only", "constant", "uniform")


def role_names(primary, split_name):
    return {
        "primary": primary,
        "empty_input": f"{primary}+empty_input",
        "question_only": f"{primary}+question_only",
        "constant": f"constant@{split_name}",
        "uniform": "uniform",
    }


def build_report(rows_by_scorer, primary):
    """Return the report dict. ``rows_by_scorer`` maps physical scorer name -> list of readout rows."""
    report = {"primary": primary, "splits": {}, "thresholds": {}, "missing": []}
    for splitter in (S.GROUP70, S.QUESTION70):
        split_cells, split_tau = {}, {}
        primary_rows = [r for r in rows_by_scorer.get(primary, []) if splitter in S.splitters_for_source(r["source"])]
        for role, phys in role_names(primary, splitter.name).items():
            rows = [r for r in rows_by_scorer.get(phys, []) if splitter in S.splitters_for_source(r["source"])]
            if not rows:
                if primary_rows:  # this split applies to the run, but the role has no readouts
                    report["missing"].append(f"{splitter.name}:{role} ({phys})")
                continue
            fitted = TH.fit_thresholds(S.TrainView.of(rows, splitter))
            decided = M.decide_rows(rows, fitted)
            by_cell, tiers = defaultdict(list), defaultdict(lambda: defaultdict(int))
            for d in decided:
                side = splitter.assign(d.row)
                by_cell[(side, d.row["source"], d.row["level_type"])].append(d)
                tiers[side][d.tier] += 1
            for (side, source, ltype), ds in by_cell.items():
                split_cells.setdefault(side, {}).setdefault(source, {}).setdefault(ltype, {})[role] = M.cell_metrics(ds, side)
            split_tau[role] = {"scorer": phys, **fitted.summary(), "rows_by_tier": {s: dict(t) for s, t in tiers.items()}}
        if split_cells:
            report["splits"][splitter.name] = split_cells
            report["thresholds"][splitter.name] = split_tau
    report["decision_lines"] = decision_lines(report)
    return report


def decision_lines(report):
    """B-1, B-2, B-3 per (source, level_type) cell on the held-out side of the group70 split."""
    out = {"B-1": [], "B-2": [], "B-3": [], "B-4": "needs a second report after training; not evaluated here"}
    cells = report["splits"].get("group70", {}).get("heldout", {})
    for source in sorted(cells):
        for ltype in LEVEL_TYPES:
            roles = cells[source].get(ltype)
            if not roles or "primary" not in roles:
                continue
            p = roles["primary"]
            if "constant" in roles:
                for task in ("T1", "T2"):
                    a, b = p[f"floor_{task}"]["acc_cumulative"], roles["constant"][f"floor_{task}"]["acc_cumulative"]
                    if a is not None and b is not None:
                        out["B-1"].append({"source": source, "level_type": ltype, "floor": task,
                                           "readout": a, "constant": b, "difference": a - b,
                                           "pass": a - b >= B1_MARGIN})
            real_flip = p["flip_T1"]["overall"]
            if "empty_input" in roles and real_flip is not None and roles["empty_input"]["flip_T1"]["overall"] is not None:
                empty_flip = roles["empty_input"]["flip_T1"]["overall"]
                gap = empty_flip - real_flip
                out["B-2"].append({"source": source, "level_type": ltype, "real_flip": real_flip,
                                   "empty_input_flip": empty_flip, "gap": gap, "pass": gap >= B2_MARGIN,
                                   "t1_void": abs(gap) <= B2_VOID_WITHIN})
            fr = p["move_T2"]["swap"]["followed_rate"]
            if fr is not None:
                out["B-3"].append({"source": source, "level_type": ltype, "followed_rate": fr,
                                   "above_30_percent": fr > B3_FOLLOWED_ABOVE, "t1_flip_same_cell": real_flip,
                                   "followed_minus_flip": None if real_flip is None else fr - real_flip,
                                   "clearly_above_flip": "reader judgement (no number in the pre-registration)"})
    return out


# ---------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------

def _f(x, pct=True):
    if x is None:
        return "-"
    return f"{100 * x:.1f}" if pct else f"{x:.4g}"


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _iter_cells(side_cells):
    for source in sorted(side_cells):
        for ltype in LEVEL_TYPES:
            roles = side_cells[source].get(ltype)
            if roles:
                for role in ROLE_ORDER:
                    if role in roles:
                        yield source, ltype, role, roles[role]


def render_markdown(report, header):
    out = ["# R0 baseline report", "",
           "Generated from raw readouts. Every row is one source and one level type. "
           "All rates are percentages unless stated. Definitions: `experiments/R0-BASELINE-PREREG.md` section 3.", "",
           "## Run header", "", "```"]
    out += [f"{k}: {v}" for k, v in header.items()]
    out += ["```", ""]
    if report["missing"]:
        out += ["**Missing scorer runs (their rows are absent below):** " + ", ".join(report["missing"]), ""]
    for split_name, sides in report["splits"].items():
        for side in ("heldout", "train"):
            if side not in sides:
                continue
            note = "tau fitted on train, applied unchanged" if side == "heldout" else "in-sample: tau was fitted on these rows"
            out += [f"## Split `{split_name}`, side `{side}` ({note})", ""]
            cells = sides[side]
            rows = [[s, lt, role, m["floor_T1"]["n"], _f(m["floor_T1"]["acc_cumulative"]),
                     _f(m["floor_T1"]["acc_argmax_reference"]), _f(m["c_branch"]["T1"]["rate"]),
                     m["floor_T2"]["n"], _f(m["floor_T2"]["acc_cumulative"]),
                     _f(m["floor_T2"]["acc_argmax_reference"]), _f(m["c_branch"]["T2"]["rate"]),
                     _f(m["ece"]["ece"], False) if "ece" in m else "-"]
                    for s, lt, role, m in _iter_cells(cells)]
            out += ["### Accuracy floor and C-branch rate", "",
                    _table(["source", "level_type", "scorer", "T1 n", "T1 acc (cum-mass)", "T1 acc (argmax ref)",
                            "T1 C-rate", "T2 n", "T2 acc (cum-mass)", "T2 acc (argmax ref)", "T2 C-rate", "ECE (0-1)"], rows), ""]
            rows = [[s, lt, role, m["failure_set_T1"]["n_units"], m["failure_set_T1"]["failures_original"],
                     m["failure_set_T1"]["failures_cumulative"], _f(m["failure_set_T1"]["growth"]),
                     _f(m["flip_T1"]["overall"])] + [_f(v) for v in m["flip_T1"]["per_pair"].values()]
                    for s, lt, role, m in _iter_cells(cells)]
            pair_names = next((list(m["flip_T1"]["per_pair"]) for _, _, _, m in _iter_cells(cells)), [])
            out += ["### T1 invariance: cumulative failure set and flip rate", "",
                    _table(["source", "level_type", "scorer", "units", "fail (original)", "fail (cumulative, 4 variants)",
                            "growth", "flip overall"] + [f"flip {p.replace('|', ' / ')}" for p in pair_names], rows), ""]
            t3 = [(s, lt, role, m) for s, lt, role, m in _iter_cells(cells) if "flip_T3" in m]
            if t3:
                pair_names3 = list(t3[0][3]["flip_T3"]["per_pair"])
                rows = [[s, lt, role, m["floor_T3"]["n"], _f(m["floor_T3"]["acc_cumulative"]),
                         _f(m["floor_T3"]["acc_argmax_reference"]), _f(m["c_branch"]["T3"]["rate"]),
                         m["failure_set_T3"]["failures_original"], m["failure_set_T3"]["failures_cumulative"],
                         _f(m["failure_set_T3"]["growth"]), m["flip_T3"]["n_units"], _f(m["flip_T3"]["overall"])]
                        + [_f(v) for v in m["flip_T3"]["per_pair"].values()] for s, lt, role, m in t3]
                out += ["### T3 question-set invariance (floor variant prefix_1q; flip rate defined as in T1; "
                        "prefix_5q / prefix_5q_shuffled is the pure ordering effect)", "",
                        _table(["source", "level_type", "scorer", "floor n", "acc (cum-mass)", "acc (argmax ref)", "C-rate",
                                "fail (prefix_1q)", "fail (cumulative, 4 variants)", "growth", "units", "flip overall"]
                               + [f"flip {p.replace('|', ' / ')}" for p in pair_names3], rows), ""]
            rows = []
            for s, lt, role, m in _iter_cells(cells):
                sw, rv = m["move_T2"]["swap"], m["move_T2"]["reversed"]
                rows.append([s, lt, role, sw["n_eligible"], _f(sw["followed_rate"]), _f(sw["unmoved_rate"]),
                             _f(sw["moved_elsewhere_rate"]), sw["n_ineligible"], rv["n_eligible"],
                             _f(rv["followed_rate"]), _f(rv["unmoved_rate"]), _f(rv["moved_elsewhere_rate"]), rv["n_ineligible"]])
            out += ["### T2 discrimination: move rate", "",
                    _table(["source", "level_type", "scorer", "swap eligible", "followed", "unmoved", "moved elsewhere",
                            "swap ineligible", "rev eligible", "followed", "unmoved", "moved elsewhere", "rev ineligible"], rows), ""]
            rows = []
            for s, lt, role, m in _iter_cells(cells):
                mg = m["margin_T1"]
                q = mg["distance_quantiles"] or {}
                rows.append([s, lt, role, mg["n_decisions"], _f(mg["share_distance_above_variance"])]
                            + [_f(q.get(k), False) for k in ("q00", "q10", "q25", "q50", "q75", "q90", "q100")])
            out += ["### Margin distribution (T1): share of decisions with distance above within-group variance, "
                    "and quantiles of the distance (probability units)", "",
                    _table(["source", "level_type", "scorer", "decisions", "share above variance",
                            "d q0", "q10", "q25", "q50", "q75", "q90", "q100"], rows), ""]
    out += ["## Threshold fitting", ""]
    for split_name, roles in report["thresholds"].items():
        rows = [[split_name, role, info["scorer"], info["fitted_keys_per_tier"], info["rows_by_tier"]] for role, info in roles.items()]
        out += [_table(["split", "role", "scorer", "keys fitted per tier", "rows decided per side and tier"], rows), ""]
    dl = report["decision_lines"]
    out += ["## Decision lines (held-out side, split `group70`)", ""]
    out += ["### B-1 readout vs constant classifier (pass: >= 10 points)", "",
            _table(["source", "level_type", "floor", "readout", "constant", "diff", "pass"],
                   [[r["source"], r["level_type"], r["floor"], _f(r["readout"]), _f(r["constant"]), _f(r["difference"]), r["pass"]] for r in dl["B-1"]]), ""]
    out += ["### B-2 real flip vs empty-input flip (pass: real >= 10 points below; void if within 5 points)", "",
            _table(["source", "level_type", "real flip", "empty-input flip", "gap", "pass", "T1 void"],
                   [[r["source"], r["level_type"], _f(r["real_flip"]), _f(r["empty_input_flip"]), _f(r["gap"]), r["pass"], r["t1_void"]] for r in dl["B-2"]]), ""]
    out += ["### B-3 T2 followed rate (pass: above 30%; 'clearly above T1 flip' is a reader judgement)", "",
            _table(["source", "level_type", "followed", "above 30%", "T1 flip same cell", "followed minus flip"],
                   [[r["source"], r["level_type"], _f(r["followed_rate"]), r["above_30_percent"], _f(r["t1_flip_same_cell"]), _f(r["followed_minus_flip"])] for r in dl["B-3"]]), ""]
    out += [f"### B-4\n\n{dl['B-4']}", ""]
    return "\n".join(out)
