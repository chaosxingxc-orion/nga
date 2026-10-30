"""Selection, adoption and the Track K decision lines (R3-SFT-PREREG sec 8.2, 8.3, 9.1, 9.2, 9.3).

Inputs are STORED per-question readouts (core_r3.k_readout_path) and the Track T selection summary of each seed's report.json;
nothing here scores a model, and nothing here opens a test partition or the Track T report half (sec 8.1: selection uses only
decision-v7 dev, transfer-v4 dev and the Track T selection half).

    python3 -P select_r3.py compare --a <run_dir> <run_dir> --b <run_dir> <run_dir> --out <json>
    python3 -P select_r3.py kfloor --runs <run_dir> ...        (each run is one seed of one trained arm)
    python3 -P select_r3.py kalign --runs <seed run dirs of K1>
    python3 -P select_r3.py armlines --runs <seed run dirs of one arm>    (sec 6.2: a line passes for the arm only if it passes for every seed)
    python3 -P select_r3.py kladder --size 0.8B <run_dir> --size 2B <run_dir> ...
"""
import argparse
import json
import math
import os
import sys

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:   # python3 -P does not put the script directory on sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core_r3 as C
import selection_evidence_r3 as E

BOOTSTRAP_SEED = 20261030            # sec 8.2(a): numpy.random.default_rng(20261030)
BOOTSTRAP_RESAMPLES = 10000          # sec 8.2(a)
CI_LEVEL = 0.90                      # sec 8.2(a): 90% percentile CI, lower bound must be > 0
MAX_SUITE_DROP = 0.010               # sec 8.2(b): neither suite's seed-mean dev accuracy drops by more than 1.0 point
MAX_FLIP_RISE = 0.020                # sec 8.2(c): seed-mean T1 argmax flip rate rises by no more than 2 points in any gating cell
FLOOR_MARGIN = 0.05                  # sec 9.2: beats constant and question-only by >= 5 points
ALIGN_DEC, ALIGN_TRA = 0.80, 0.60    # sec 9.1
EPS = 1e-9
COMBINED_DEV = (("decision-v7", "dev"), ("transfer-v4", "dev"))
COMBINED_N = 1920                    # 1,264 + 656
KEV_STAGE1 = {"decision-v7": [0.8172, 0.8196, 0.8291], "transfer-v4": [0.6220, 0.6341, 0.6433]}    # sec 9.1, seeds 0/1/2
KEV_RELEASE = {"0.8B": {"decision-v7": (0.827, 0.838), "transfer-v4": (0.648, 0.697)},             # sec 9.3 (dev, test)
               "4B": {"decision-v7": (0.873, 0.865), "transfer-v4": (0.817, 0.838)},
               "9B": {"decision-v7": (0.874, 0.873), "transfer-v4": (0.820, 0.852)}}
GATING_VOID_RULE = "any_seed_void_excludes"    # a cell gates only if its B-2 status is neither void nor undefined for BOTH arms at EVERY seed
SELECTION_ONLY_HALF = "selection"
# sec 8.2(a) says "resampled 10,000 times over questions": the literal draw is one rng.integers(0, n, size=n) per resample, in
# sequence from the single generator; the percentile uses numpy's default (linear) interpolation.
BOOTSTRAP_DRAW = "per-resample rng.integers(0, n, size=n), 10,000 sequential draws; np.percentile linear"


# ---- loading --------------------------------------------------------------------------------------------------------------------

def correctness_vector(run_dir, suite, split="dev"):
    """[(key, 0/1 under the Kev rule)] in file order, from the stored clean readouts of a run."""
    rows = C.read_jsonl(C.k_readout_path(run_dir, suite, split, "clean"))
    return [(r["k"], int(r["argmax"] == r["gold_index"])) for r in rows]


def combined_dev(run_dir):
    """Per-question correctness over decision-v7 dev then transfer-v4 dev. Returns (keys, correct list, n per suite)."""
    keys, corr, n = [], [], {}
    for suite, split in COMBINED_DEV:
        v = correctness_vector(run_dir, suite, split)
        n[suite] = len(v)
        keys += [(suite, k) for k, _ in v]
        corr += [c for _, c in v]
    return keys, corr, n


def arm_matrix(run_dirs):
    """seeds x questions correctness matrix (list of lists) and the common key list; every seed must hold the same questions."""
    keys0, mats, n0 = None, [], None
    for d in run_dirs:
        keys, corr, n = combined_dev(d)
        if keys0 is None:
            keys0, n0 = keys, n
        elif keys != keys0:
            raise ValueError(f"{d}: readouts cover different questions than the first seed")
        mats.append(corr)
    return keys0, mats, n0


# ---- sec 8.2(a) ---------------------------------------------------------------------------------------------------------------

def paired_bootstrap(a_corr, b_corr, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES, ci=CI_LEVEL):
    """a_corr, b_corr: per-question correctness already averaged over the seeds of each arm. The statistic is the micro-accuracy
    difference A - B, resampled over questions with numpy.random.default_rng(seed); percentile CI at level `ci`."""
    import numpy as np
    d = np.asarray(a_corr, dtype=float) - np.asarray(b_corr, dtype=float)
    n = len(d)
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    for i in range(resamples):
        means[i] = d[rng.integers(0, n, size=n)].mean()
    lo, hi = np.percentile(means, [100 * (1 - ci) / 2, 100 * (1 + ci) / 2])
    return {"n": n, "mean_difference": float(d.mean()), "ci_level": ci, "ci_lower": float(lo), "ci_upper": float(hi),
            "resamples": resamples, "rng_seed": seed, "draw": BOOTSTRAP_DRAW, "lower_bound_above_zero": bool(lo > 0)}


def _seed_mean(mats):
    n_seeds = len(mats)
    return [sum(m[i] for m in mats) / n_seeds for i in range(len(mats[0]))]


def drop_ok(a_acc, b_acc):
    """sec 8.2(b): True unless A's seed-mean accuracy is below B's by MORE than 1.0 point (exactly 1.0 point is allowed)."""
    return (b_acc - a_acc) <= MAX_SUITE_DROP + EPS


def discordant(a_mean, b_mean):
    """Per-question discordant counts on the seed-mean correctness: A better, B better, equal (sec 8.3)."""
    a_better = sum(1 for a, b in zip(a_mean, b_mean) if a > b + EPS)
    b_better = sum(1 for a, b in zip(a_mean, b_mean) if b > a + EPS)
    return {"a_better": a_better, "b_better": b_better, "equal": len(a_mean) - a_better - b_better}


def discordant_per_seed_pair(a_mats, b_mats):
    out = []
    for i, a in enumerate(a_mats):
        for j, b in enumerate(b_mats):
            out.append({"a_seed_index": i, "b_seed_index": j, "a_right_b_wrong": sum(1 for x, y in zip(a, b) if x == 1 and y == 0),
                        "b_right_a_wrong": sum(1 for x, y in zip(a, b) if x == 0 and y == 1)})
    return out


# ---- sec 8.2(c) ---------------------------------------------------------------------------------------------------------------

def gating_cells(a_selections, b_selections):
    """sec 8.2(c): the gating cells are the `typed-decisions` T1 cells that are not void under R0 sec 13.5 for either model.
    `*_selections`: one selection summary per seed ({source: {level type: {b2_status, flip_T1_argmax, ...}}}). Returns
    ({level type: reason or None}); None means gating."""
    cells = {}
    for sel in a_selections + b_selections:
        for lt in sel.get("typed-decisions", {}):
            cells.setdefault(lt, None)
    out = {}
    for lt in sorted(cells):
        reason = None
        for tag, sels in (("A", a_selections), ("B", b_selections)):
            for i, sel in enumerate(sels):
                v = sel.get("typed-decisions", {}).get(lt)
                st = None if v is None else v.get("b2_status")
                if st in (None, "undefined"):
                    reason = f"B-2 status undefined for arm {tag} seed {i}"
                elif st == "void":
                    reason = f"B-2 void for arm {tag} seed {i}"
                if reason:
                    break
            if reason:
                break
        out[lt] = reason
    return out


def condition_c(a_selections, b_selections, r0_gating=None):
    if r0_gating is None:
        return {"clause": "sec 8.2(c), 14.11 item 4", "status": "INCOMPLETE", "ok": False,
                "n_gating_cells": 0, "cells": {}, "reason": "verified R0 fp32 gating population is required"}
    E.require(len(a_selections) == 2 and len(b_selections) == 2, "condition c requires two seeds per arm")
    statuses = r0_gating["statuses"]
    E.require(set(statuses) == {"boolean", "nominal", "ordinal"}, "incomplete R0 level-type population")
    E.require(all(v in {"pass", "fail", "void", "undefined"} for v in statuses.values()), "invalid R0 B-2 status")
    E.require(all(set(x.get("typed-decisions", {})) <= set(statuses) for x in a_selections + b_selections),
              "unexpected typed-decisions level type")
    gates = gating_cells(a_selections, b_selections)
    for lt, status in statuses.items():
        if status in {"void", "undefined"}:
            gates[lt] = "R0 fp32 B-2 " + status
        else:
            E.require(all(lt in x.get("typed-decisions", {}) for x in a_selections + b_selections),
                      "R0 gating cell is missing from an arm")
            E.require(all(x["typed-decisions"][lt].get("b2_status") in {"pass", "fail", "void", "undefined"}
                          for x in a_selections + b_selections), "invalid arm B-2 status")
    cells = {}
    ok = True
    for lt, reason in gates.items():
        entry = {"gating": reason is None, "excluded_reason": reason}
        if reason is None:
            fa = [s["typed-decisions"][lt]["flip_T1_argmax"] for s in a_selections]
            fb = [s["typed-decisions"][lt]["flip_T1_argmax"] for s in b_selections]
            if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in fa + fb):
                entry.update(gating=False, excluded_reason="a seed has no valid T1 argmax flip rate in this cell")
                ok = False
            else:
                E.require(all(type(x["typed-decisions"][lt].get("n_units")) is int
                              and x["typed-decisions"][lt]["n_units"] > 0
                              for x in a_selections + b_selections), "empty gating cell denominator")
                ma, mb = sum(fa) / len(fa), sum(fb) / len(fb)
                entry.update(a_seed_flips=fa, b_seed_flips=fb, a_mean_flip=ma, b_mean_flip=mb, rise=ma - mb,
                             n_units=[s["typed-decisions"][lt]["n_units"] for s in a_selections],
                             dropped_pairs=[s["typed-decisions"][lt]["n_pairs_dropped_tie"] for s in a_selections],
                             ok=(ma - mb) <= MAX_FLIP_RISE + EPS)
                ok = ok and entry["ok"]
        cells[lt] = entry
    return {"clause": "sec 8.2(c)", "gating_rule": GATING_VOID_RULE, "max_rise": MAX_FLIP_RISE, "cells": cells,
            "n_gating_cells": sum(1 for c in cells.values() if c["gating"]),
            "r0_gating_source": r0_gating.get("run"),
            "status": "COMPLETE" if any(c["gating"] for c in cells.values()) and all(c.get("excluded_reason") != "a seed has no valid T1 argmax flip rate in this cell" for c in cells.values()) else "INCOMPLETE",
            "ok": bool(ok and any(c["gating"] for c in cells.values()))}


# ---- sec 8.2 / 8.3 -------------------------------------------------------------------------------------------------------------

def compare(a_runs, b_runs, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES, r0_run=None):
    """Candidate arm A against B, recomputed from provenance-verified readouts and frozen dev tasks.
    No adoption without the verified R0 fp32 population (section 14.11 item 4)."""
    ar = [E.load_selection_report(d, require_track_t=True) for d in a_runs]
    br = [E.load_selection_report(d, require_track_t=True) for d in b_runs]
    E.validate_seed_reports(ar)
    E.validate_seed_reports(br)
    keys = ar[0]["selection_evidence"]["keys"]
    keys_b = br[0]["selection_evidence"]["keys"]
    E.require(all(r["selection_evidence"]["keys"] == keys for r in ar + br), "seed populations differ")
    a_mats = [r["selection_evidence"]["correct"] for r in ar]
    b_mats = [r["selection_evidence"]["correct"] for r in br]
    n = {"decision-v7": 1264, "transfer-v4": 656}
    if keys != keys_b:
        raise ValueError("arms A and B do not cover the same dev questions")
    a_mean, b_mean = _seed_mean(a_mats), _seed_mean(b_mats)
    total = sum(n.values())
    boot = paired_bootstrap(a_mean, b_mean, seed, resamples)
    per_suite = {}
    off = 0
    for suite, _ in COMBINED_DEV:
        k = n[suite]
        sl = slice(off, off + k)
        off += k
        a_seed = [sum(m[sl]) / k for m in a_mats]
        b_seed = [sum(m[sl]) / k for m in b_mats]
        drop = sum(b_seed) / len(b_seed) - sum(a_seed) / len(a_seed)
        per_suite[suite] = {"n": k, "a_seed_accuracies": a_seed, "b_seed_accuracies": b_seed, "a_mean": sum(a_seed) / len(a_seed),
                            "b_mean": sum(b_seed) / len(b_seed), "a_minus_b": -drop, "drop": drop, "ok": drop_ok(sum(a_seed) / len(a_seed), sum(b_seed) / len(b_seed)),
                            "discordant": discordant(a_mean[sl], b_mean[sl])}
    cond_a = boot["lower_bound_above_zero"]
    cond_b = all(v["ok"] for v in per_suite.values())
    a_selections = [r["track_t"]["selection"] for r in ar]
    b_selections = [r["track_t"]["selection"] for r in br]
    cond_c = condition_c(a_selections, b_selections, E.load_r0_gating(r0_run) if r0_run else None)
    floor = k_floor(ar)
    return {"clause": "sec 8.2 / 8.3", "n_combined_dev": total, "n_per_suite": n, "n_expected_combined": COMBINED_N,
            "a_runs": list(a_runs), "b_runs": list(b_runs), "per_seed_accuracy_combined": {
                "a": [sum(m) / len(m) for m in a_mats], "b": [sum(m) / len(m) for m in b_mats]},
            "condition_a": {"clause": "sec 8.2(a)", "bootstrap": boot, "ok": cond_a},
            "condition_b": {"clause": "sec 8.2(b)", "max_drop": MAX_SUITE_DROP, "per_suite": per_suite, "ok": cond_b},
            "condition_c": cond_c, "discordant_combined": discordant(a_mean, b_mean),
            "discordant_per_seed_pair": discordant_per_seed_pair(a_mats, b_mats),
            "candidate_k_floor": floor,
            "a_replaces_b": bool(cond_a and cond_b and cond_c["ok"] and floor["passes"])}


# ---- decision lines ------------------------------------------------------------------------------------------------------------------

def _dev_acc(report, suite, arm=None):
    p = report["track_k"]["partitions"][f"{suite}/dev"]
    node = p["headline"] if arm is None else p["arms"][arm]
    value = node["kev_rule_accuracy"]
    E.require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1, "invalid accuracy")
    return value


def k_floor(seed_reports):
    """sec 9.2: EVERY seed beats BOTH the constant (sec 5.1) and the test-time question-only arm (sec 5.2) by >= 5 points on the
    dev partition of both suites (Kev-rule accuracy). An arm that fails cannot be adopted."""
    E.require(bool(seed_reports), "K-floor requires nonempty seed evidence")
    per_seed, ok = [], True
    for rep in seed_reports:
        e = {}
        for suite in ("decision-v7", "transfer-v4"):
            acc = _dev_acc(rep, suite)
            const, qo = _dev_acc(rep, suite, "constant"), _dev_acc(rep, suite, "question_only")
            e[suite] = {"accuracy": acc, "constant": const, "question_only": qo, "margin_over_constant": acc - const,
                        "margin_over_question_only": acc - qo, "ok": acc - const >= FLOOR_MARGIN - EPS and acc - qo >= FLOOR_MARGIN - EPS}
            ok = ok and e[suite]["ok"]
        per_seed.append(e)
    return {"clause": "sec 9.2", "required_margin": FLOOR_MARGIN, "per_seed": per_seed, "passes": ok}


def k_align(seed_reports):
    """sec 9.1: the two-seed mean of K1 reaches decision-v7 dev >= 0.80 AND transfer-v4 dev >= 0.60, both seeds reported."""
    E.validate_seed_reports(seed_reports, required_arm="K1")
    accs = {s: [_dev_acc(r, s) for r in seed_reports] for s in ("decision-v7", "transfer-v4")}
    means = {s: sum(v) / len(v) for s, v in accs.items()}
    return {"clause": "sec 9.1", "seed_accuracies": accs, "means": means, "thresholds": {"decision-v7": ALIGN_DEC, "transfer-v4": ALIGN_TRA},
            "kev_stage1_reference_seeds_0_1_2": KEV_STAGE1,
            "passes": bool(means["decision-v7"] >= ALIGN_DEC - EPS and means["transfer-v4"] >= ALIGN_TRA - EPS),
            "if_not_met": "report the gap with its declared causes (sec 3.3); do not explain it away"}


def k_ladder(size_reports, seed_spread_08b=None):
    """sec 9.3: dev accuracy on each suite does not decrease with size (0.8B <= 2B <= 4B <= 9B; the 0.8B entry is the seed-2 run).
    `size_reports`: ordered {size: report}. `seed_spread_08b`: {suite: |seed2 - seed3|} marks differences that sec 12.6 says are not
    reportable as size effects. Each size is listed beside Kev's released dev / test numbers (an upper reference, not a target)."""
    sizes = list(size_reports)
    out = {"clause": "sec 9.3", "sizes": sizes, "per_suite": {}, "monotone": True}
    for suite in ("decision-v7", "transfer-v4"):
        accs = [_dev_acc(size_reports[s], suite) for s in sizes]
        steps = []
        for i in range(1, len(sizes)):
            diff = accs[i] - accs[i - 1]
            inside = None if not seed_spread_08b else abs(diff) <= seed_spread_08b[suite] + EPS
            steps.append({"from": sizes[i - 1], "to": sizes[i], "difference": diff, "non_decreasing": diff >= -EPS,
                          "inside_08b_seed_spread_not_reportable_as_size_effect": inside})
        mono = all(s["non_decreasing"] for s in steps)
        out["monotone"] = out["monotone"] and mono
        out["per_suite"][suite] = {"dev_accuracy": dict(zip(sizes, accs)), "steps": steps, "monotone": mono,
                                   "kev_release_dev_test": {s: KEV_RELEASE.get(s, {}).get(suite) for s in sizes}}
    out["kev_reference_note"] = "upper reference, not a target: two further training stages and a fitted temperature (sec 9.3); Kev released no 2B model"
    return out


def arm_decision_lines(seed_reports, half="report"):
    """sec 6.2: B-1, B-2, B-2 (T3), B-3 (and B-4 when present) for every seed, and per line whether it passes for the ARM, i.e. for
    every seed. `seed_reports`: the report.json dicts of the seeds of one arm (Track T config r3, so the lines are of the report half)."""
    import track_t_r3 as T
    out = {"clause": "sec 6.2", "half": half, "n_seeds": len(seed_reports)}
    for name in ("B-1", "B-2", "B-2_T3", "B-3"):
        per_seed = [r["track_t"]["decision_lines"][half][name] for r in seed_reports]
        out[name] = {"|".join(str(x) for x in k): v for k, v in T.roll_up_seeds(per_seed).items()}
    if all("B-4" in r["track_t"] for r in seed_reports):
        per_seed = [r["track_t"]["B-4"]["lines"] for r in seed_reports]
        out["B-4"] = {"|".join(str(x) for x in k): v for k, v in T.roll_up_seeds(per_seed).items()}
    out["B-1_by_source_pass_for_arm"] = {
        s: all(r["track_t"]["decision_lines"][half]["B-1_by_source"].get(s, {}).get("pass") for r in seed_reports)
        for s in sorted({s for r in seed_reports for s in r["track_t"]["decision_lines"][half]["B-1_by_source"]})}
    return out


def adopt_first(k_floor_result, r0_run=None):
    """sec 8.2: K1 becomes the first adopted arm if it clears K-floor."""
    if r0_run is None:
        return False  # section 14.11 item 4 suspends adoption, including the first arm.
    E.require("seed_reports" in k_floor_result, "first adoption requires verified seed reports, not a pass flag")
    reports = [E.load_selection_report(d) for d in k_floor_result["seed_reports"]]
    E.validate_seed_reports(reports, required_arm="K1")
    k_floor_result = k_floor(reports)
    gates = E.load_r0_gating(r0_run)
    return bool(k_floor_result["passes"] and any(v in {"pass", "fail"} for v in gates["statuses"].values()))


# ---- CLI --------------------------------------------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--a", nargs="+", required=True)
    c.add_argument("--b", nargs="+", required=True)
    c.add_argument("--r0-run", default=None, help="completed R0 fp32 re-score; required for adoption")
    for name in ("kfloor", "kalign"):
        k = sub.add_parser(name)
        k.add_argument("--runs", nargs="+", required=True)
    arm = sub.add_parser("armlines")
    arm.add_argument("--runs", nargs="+", required=True)
    l = sub.add_parser("kladder")
    l.add_argument("--size", nargs=2, action="append", metavar=("SIZE", "RUN"), required=True)
    for p in sub.choices.values():
        p.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "compare":
        res = compare(a.a, a.b, r0_run=a.r0_run)
    elif a.cmd == "kfloor":
        reports = [E.load_selection_report(d) for d in a.runs]
        arm_name = reports[0]["selection_evidence"]["arm"]
        E.validate_seed_reports(reports, required_seeds=(2,) if arm_name in {"K1-QO", "K1-FLA"} else (2, 3))
        res = k_floor(reports)
        res["seed_reports"] = list(a.runs)
    elif a.cmd == "kalign":
        res = k_align([E.load_selection_report(d) for d in a.runs])
    elif a.cmd == "armlines":
        res = arm_decision_lines([E.load_selection_report(d, require_track_t=True, report_half=True) for d in a.runs])
    else:
        res = k_ladder({s: E.load_selection_report(d) for s, d in a.size})
    text = json.dumps(res, indent=1, sort_keys=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
