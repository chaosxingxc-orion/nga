"""Tests for select_r3.py: R3-SFT-PREREG sec 8.2 (a) (b) (c), 8.3, 9.1, 9.2, 9.3. Needs numpy (run on the NPU host or in the container):
    python3 test_select_r3.py          (python3 -P inside the container)"""
import json
import os
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np                       # noqa: E402
import core_r3 as C                      # noqa: E402
import select_r3 as SEL                  # noqa: E402
import runner_r3 as R                    # noqa: E402

# Arithmetic tests use synthetic already-verified inputs. Real consumer validation is
# exercised separately, without replacing its loader, by test_selection_evidence_r3.py.
R0_GATING = {"run": "synthetic-r0", "statuses": {"boolean": "void", "nominal": "pass", "ordinal": "void"}}

def _arithmetic_report(d, **kwargs):
    report = C.load_report(d)
    keys, correct, _ = SEL.combined_dev(d)
    report["track_k"] = {"partitions": {suite + "/dev": {
        "headline": {"kev_rule_accuracy": .9}, "arms": {
            "constant": {"kev_rule_accuracy": .4}, "question_only": {"kev_rule_accuracy": .4}}}
        for suite in C.SUITES}}
    report["selection_evidence"] = {"seed": 2 + int(os.path.basename(d)[-1]), "arm": "K1",
                                     "adapter_path": d, "keys": keys, "correct": correct,
                                     "training_variant": {"schema": 1, "args": {"arm": "k1"}}}
    return report

def compare_math(a, b):
    with patch.object(SEL.E, "load_selection_report", side_effect=_arithmetic_report), patch.object(SEL.E, "load_r0_gating", return_value=R0_GATING):
        return SEL.compare(a, b, r0_run="synthetic-r0")

def condition_math(a, b):
    return SEL.condition_c(a, b, R0_GATING)

def align_math(reports):
    for seed, report in zip((2, 3), reports):
        report["selection_evidence"] = {"seed": seed, "arm": "K1", "adapter_path": str(seed),
                                        "training_variant": {"schema": 1, "args": {"arm": "k1"}}}
    return SEL.k_align(reports)

N_DEC, N_TRA = 1264, 656


def test_s8_2a_paired_bootstrap_is_reproducible_and_matches_a_direct_computation():
    """sec 8.2(a): paired bootstrap of the micro-accuracy difference over questions, numpy.random.default_rng(20261030), 10,000 resamples, 90% percentile CI."""
    rng = np.random.default_rng(5)
    a = (rng.random(1920) < 0.62).astype(float)
    b = (rng.random(1920) < 0.60).astype(float)
    r1 = SEL.paired_bootstrap(a, b)
    r2 = SEL.paired_bootstrap(a, b)
    assert r1 == r2 and r1["resamples"] == 10000 and r1["rng_seed"] == 20261030 and r1["ci_level"] == 0.90 and r1["n"] == 1920
    d = a - b
    g = np.random.default_rng(20261030)
    means = d[g.integers(0, 1920, size=(10000, 1920))].mean(axis=1)           # one batched draw: same stream as 10,000 sequential draws
    lo, hi = np.percentile(means, [5, 95])
    assert abs(r1["ci_lower"] - lo) < 1e-15 and abs(r1["ci_upper"] - hi) < 1e-15 and abs(r1["mean_difference"] - d.mean()) < 1e-15
    assert r1["ci_lower"] < r1["mean_difference"] < r1["ci_upper"]
    # a different seed gives a different interval (the seed is really used)
    assert SEL.paired_bootstrap(a, b, seed=1)["ci_lower"] != r1["ci_lower"]
    same = SEL.paired_bootstrap(a, a)
    assert same["ci_lower"] == 0.0 == same["ci_upper"] and not same["lower_bound_above_zero"]
    better = SEL.paired_bootstrap(np.ones(1920), np.zeros(1920))
    assert better["lower_bound_above_zero"] and better["ci_lower"] == 1.0


def _write_run(root, name, dec_correct, tra_correct, selection=None, ties=False):
    d = os.path.join(root, name)
    for suite, corr in (("decision-v7", dec_correct), ("transfer-v4", tra_correct)):
        rows = [{"k": f"{suite}/{i}/0", "gold_index": 0, "argmax": 0 if c else 1, "tie": False, "ids": ["a", "b"], "gold": "a", "s": [0.0, -1.0], "variant": "original",
                 "source": "s", "level_type": "nominal", "qname": "q"} for i, c in enumerate(corr)]
        C.write_jsonl(C.k_readout_path(d, suite, "dev", "clean"), rows)
    if selection is not None:
        os.makedirs(d, exist_ok=True)
        json.dump({"track_t": {"selection": selection}}, open(os.path.join(d, "report.json"), "w"))
    return d


def _vec(n, k, offset=0):
    """n entries with k correct, the correct ones starting at `offset` (cyclic)."""
    return [1 if ((i - offset) % n) < k else 0 for i in range(n)]


def _sel(flip, status="pass", n=870):
    return {"typed-decisions": {"nominal": {"flip_T1_argmax": flip, "n_units": n, "n_pairs_used": 6 * n, "n_pairs_dropped_tie": 0, "b2_status": status}}}


def test_s8_2b_suite_drop_boundary():
    """sec 8.2(b): neither suite's seed-mean dev accuracy drops by more than 1.0 point (a drop of exactly 1.0 point is allowed)."""
    with tempfile.TemporaryDirectory() as td:
        sel = [_sel(0.1), _sel(0.1)]
        b = [_write_run(td, f"b{i}", _vec(N_DEC, 1000), _vec(N_TRA, 400), sel[i]) for i in range(2)]
        # A: decision-v7 drops by exactly 1.0 point of 1264 questions? use 12.64 -> pick drops that straddle 0.010
        a_ok = [_write_run(td, f"aok{i}", _vec(N_DEC, 1000 - 12, 1), _vec(N_TRA, 400), sel[i]) for i in range(2)]         # drop 12/1264 = 0.949 points
        a_bad = [_write_run(td, f"abad{i}", _vec(N_DEC, 1000 - 14, 1), _vec(N_TRA, 400), sel[i]) for i in range(2)]      # drop 14/1264 = 1.108 points
        ok = compare_math(a_ok, b)
        bad = compare_math(a_bad, b)
        assert ok["condition_b"]["ok"] and not bad["condition_b"]["ok"]
        assert abs(ok["condition_b"]["per_suite"]["decision-v7"]["drop"] - 12 / 1264) < 1e-12 and bad["condition_b"]["per_suite"]["decision-v7"]["n"] == N_DEC
        assert not bad["a_replaces_b"] and not ok["a_replaces_b"]                           # (a) fails too: A is worse
        # transfer-v4 drop is judged separately
        a_tra = [_write_run(td, f"atra{i}", _vec(N_DEC, 1000), _vec(N_TRA, 400 - 8, 1), sel[i]) for i in range(2)]         # 8/656 = 1.22 points
        assert not compare_math(a_tra, b)["condition_b"]["ok"]
    assert SEL.drop_ok(0.79, 0.80) and SEL.drop_ok(0.7905, 0.80) and not SEL.drop_ok(0.7895, 0.80) and SEL.drop_ok(0.6, 0.5)     # exactly 1.0 point (with float noise) is allowed


def test_s8_2c_gating_cells_and_flip_rise():
    """sec 8.2(c): gating cells are the typed-decisions T1 cells not void for either model; seed-mean flip may rise by at most 2 points there; akhilaaa3 / openjev-synth never gate."""
    a = [_sel(0.121), _sel(0.121)]
    b = [_sel(0.100), _sel(0.100)]
    res = condition_math(a, b)
    assert not res["ok"] and res["cells"]["nominal"]["gating"] and abs(res["cells"]["nominal"]["rise"] - 0.021) < 1e-12
    res = condition_math([_sel(0.120), _sel(0.120)], b)
    assert res["ok"] and res["cells"]["nominal"]["ok"]                                          # exactly +2.0 points is allowed
    # seed-mean, not per-seed: one seed at +4, one at 0 -> mean +2 passes
    assert condition_math([_sel(0.14), _sel(0.10)], b)["ok"]
    # void for either arm at any seed excludes the cell, so a large rise there does not block
    res = condition_math([_sel(0.30, "void"), _sel(0.30)], b)
    assert not res["ok"] and not res["cells"]["nominal"]["gating"] and "void" in res["cells"]["nominal"]["excluded_reason"]
    res = condition_math([_sel(0.30), _sel(0.30)], [_sel(0.1, "void"), _sel(0.1)])
    assert not res["ok"] and res["n_gating_cells"] == 0
    # non-typed-decisions sources never gate
    other = {"openjev-synth": {"nominal": {"flip_T1_argmax": 0.9, "n_units": 500, "n_pairs_used": 3000, "n_pairs_dropped_tie": 0, "b2_status": "pass"}}}
    try:
        condition_math([other, other], [other, other])
    except SEL.E.SelectionRefusal:
        pass
    else:
        raise AssertionError("missing typed-decisions gating population was accepted")


def test_s8_3_compare_reports_seeds_ci_and_discordant_counts():
    """sec 8.3 + 8.2: combined dev is 1,920 questions (1,264 + 656); the comparison reports each suite's n, the per-seed accuracies, the bootstrap CI and the per-question discordant counts."""
    with tempfile.TemporaryDirectory() as td:
        sel = [_sel(0.1), _sel(0.1)]
        a = [_write_run(td, f"a{i}", _vec(N_DEC, 1100, i * 7), _vec(N_TRA, 480, i * 5), sel[i]) for i in range(2)]
        b = [_write_run(td, f"b{i}", _vec(N_DEC, 1000, i * 3 + 400), _vec(N_TRA, 400, i * 2 + 100), sel[i]) for i in range(2)]
        res = compare_math(a, b)
        assert res["n_combined_dev"] == 1920 == SEL.COMBINED_N and res["n_per_suite"] == {"decision-v7": N_DEC, "transfer-v4": N_TRA}
        s = res["condition_b"]["per_suite"]["decision-v7"]
        assert len(s["a_seed_accuracies"]) == 2 and abs(s["a_seed_accuracies"][0] - 1100 / N_DEC) < 1e-12 and s["n"] == N_DEC
        assert len(res["per_seed_accuracy_combined"]["a"]) == 2
        bs = res["condition_a"]["bootstrap"]
        assert bs["rng_seed"] == 20261030 and bs["resamples"] == 10000 and bs["ci_level"] == 0.9 and bs["ci_lower"] < bs["ci_upper"]
        dc = res["discordant_combined"]
        assert dc["a_better"] + dc["b_better"] + dc["equal"] == 1920 and dc["a_better"] > dc["b_better"]
        assert len(res["discordant_per_seed_pair"]) == 4
        assert res["condition_a"]["ok"] and res["condition_b"]["ok"] and res["condition_c"]["ok"] and res["a_replaces_b"]
        json.dumps(res)                                                                         # serializable report


def _rep(dec, tra, const=(0.4, 0.4), qo=(0.5, 0.45)):
    return {"track_k": {"partitions": {
        "decision-v7/dev": {"headline": {"kev_rule_accuracy": dec}, "arms": {"constant": {"kev_rule_accuracy": const[0]}, "question_only": {"kev_rule_accuracy": qo[0]}}},
        "transfer-v4/dev": {"headline": {"kev_rule_accuracy": tra}, "arms": {"constant": {"kev_rule_accuracy": const[1]}, "question_only": {"kev_rule_accuracy": qo[1]}}}}}}


def test_s9_2_k_floor():
    """sec 9.2: every seed of a trained arm beats both the constant and the test-time question-only arm by >= 5 points on dev of both suites."""
    good = SEL.k_floor([_rep(0.82, 0.62), _rep(0.80, 0.60)])
    assert good["passes"] and not SEL.adopt_first(good)  # R0 prerequisite now mandatory
    exactly = SEL.k_floor([_rep(0.55, 0.50)])                                    # 0.55-0.50 = 0.05 over question-only (dec), 0.50-0.45 = 0.05 (tra)
    assert exactly["passes"]
    bad_seed = SEL.k_floor([_rep(0.82, 0.62), _rep(0.80, 0.49)])                 # transfer 0.49 vs question-only 0.45: only 4 points
    assert not bad_seed["passes"] and not SEL.adopt_first(bad_seed) and bad_seed["per_seed"][1]["transfer-v4"]["ok"] is False
    assert not SEL.k_floor([_rep(0.43, 0.9)])["passes"]                          # beats nothing on decision-v7


def test_s9_1_k_align():
    """sec 9.1: the two-seed mean of K1 reaches decision-v7 dev >= 0.80 and transfer-v4 dev >= 0.60, with both seeds reported."""
    ok = align_math([_rep(0.79, 0.59), _rep(0.81, 0.62)])
    assert ok["passes"] and ok["seed_accuracies"]["decision-v7"] == [0.79, 0.81] and ok["kev_stage1_reference_seeds_0_1_2"]["decision-v7"][2] == 0.8291
    assert not align_math([_rep(0.79, 0.62), _rep(0.80, 0.62)])["passes"]       # mean 0.795
    assert not align_math([_rep(0.82, 0.58), _rep(0.82, 0.61)])["passes"]       # mean 0.595


def test_s9_3_k_ladder():
    """sec 9.3: dev accuracy on each suite does not decrease with size; Kev's released numbers are listed beside as an upper reference."""
    reps = {"0.8B": _rep(0.80, 0.60), "2B": _rep(0.82, 0.66), "4B": _rep(0.85, 0.70), "9B": _rep(0.86, 0.69)}
    res = SEL.k_ladder(reps, seed_spread_08b={"decision-v7": 0.004, "transfer-v4": 0.02})
    assert not res["monotone"] and res["per_suite"]["decision-v7"]["monotone"] and not res["per_suite"]["transfer-v4"]["monotone"]
    step = res["per_suite"]["transfer-v4"]["steps"][2]
    assert step["from"] == "4B" and step["to"] == "9B" and not step["non_decreasing"] and step["inside_08b_seed_spread_not_reportable_as_size_effect"] is True
    assert res["per_suite"]["decision-v7"]["kev_release_dev_test"]["4B"] == (0.873, 0.865) and res["per_suite"]["decision-v7"]["kev_release_dev_test"]["2B"] is None
    assert SEL.k_ladder({"0.8B": _rep(0.8, 0.6), "2B": _rep(0.8, 0.6)})["monotone"]


def test_s6_2_arm_lines_pass_only_if_every_seed_passes():
    """sec 6.2: arm-level roll-up of the decision lines over seeds."""
    def rep(b2_status, b1_pass):
        return {"track_t": {"decision_lines": {"report": {
            "B-1": [{"source": "typed-decisions", "level_type": "nominal", "floor": "T1", "pass": b1_pass}],
            "B-1_by_source": {"typed-decisions": {"pass": b1_pass}},
            "B-2": [{"source": "typed-decisions", "level_type": "nominal", "status": b2_status}], "B-2_T3": [], "B-3": []}}}}
    res = SEL.arm_decision_lines([rep("pass", True), rep("pass", True)])
    assert res["B-2"]["typed-decisions|nominal"]["passed"] and res["B-1_by_source_pass_for_arm"]["typed-decisions"]
    res = SEL.arm_decision_lines([rep("pass", True), rep("void", False)])
    assert not res["B-2"]["typed-decisions|nominal"]["passed"] and res["B-2"]["typed-decisions|nominal"]["per_seed"] == ["pass", "void"]
    assert not res["B-1_by_source_pass_for_arm"]["typed-decisions"] and not res["B-1"]["typed-decisions|nominal|T1"]["passed"]


if __name__ == "__main__":
    R.main(globals())
