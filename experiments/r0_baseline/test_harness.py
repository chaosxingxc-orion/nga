"""Tests for the R0 baseline harness. CPU only, no model, no network.

Run with either
    python3 -I -m pytest -p no:cacheprovider experiments/r0_baseline
    python3 -I experiments/r0_baseline/test_harness.py        (plain runner, no pytest needed)
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common  # noqa: E402
import decision  # noqa: E402
import metrics as M  # noqa: E402
import prompt as prompting  # noqa: E402
import report as report_mod  # noqa: E402
import run_baseline  # noqa: E402
import scorer as sc  # noqa: E402
import split as S  # noqa: E402
import thresholds as TH  # noqa: E402

REAL_DATA = os.path.join(common.DEFAULT_DATA_ROOT, "T1_level_names", "akhilaaa3.jsonl")


# ---------------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------------

class FixedTau:
    """Stand-in for FittedThresholds with one tau for every row (metric tests only)."""

    def __init__(self, tau=0.5):
        self.tau = tau

    def tau_for(self, row):
        return self.tau, "version"


def _record(task, variant, g, levels, gold, level_type="ordinal", source="src-a", qname="q"):
    return {"source": source, "group_id": f"g{g}", "task": task, "qname": qname, "input": f"business input {g}",
            "task_definition": "Workflow: test.", "question": "How is it?", "levels": levels,
            "level_type": level_type, "candidate_set": "exclusive", "variant": variant, "gold": gold}


def make_records(n_groups=60, k=4, level_type="ordinal", source="src-a", qname="q"):
    """T1 (4 name variants) and T2 (base, one swap, reversed for ordinal) for n_groups groups."""
    recs = []
    for g in range(n_groups):
        ids = [str(i) for i in range(k)]
        defs = [f"definition {g}-{i}" for i in range(k)]
        gold = ids[g % k]
        words = [f"word{i}" for i in range(k)]
        names = {"original": words, "digits": [str(i + 1) for i in range(k)],
                 "letters": [chr(97 + i) for i in range(k)],
                 "random": [common.sha256_hex(f"{g}-{i}")[:6] for i in range(k)]}
        for variant, nm in names.items():
            lv = [{"id": ids[i], "name": nm[i], "definition": defs[i]} for i in range(k)]
            recs.append(_record("T1", variant, g, lv, gold, level_type, source, qname))
        base = [{"id": ids[i], "name": words[i], "definition": defs[i]} for i in range(k)]
        recs.append(_record("T2", "base", g, base, gold, level_type, source, qname))
        i = g % (k - 1)
        sw = [dict(l) for l in base]
        sw[i]["definition"], sw[i + 1]["definition"] = base[i + 1]["definition"], base[i]["definition"]
        gm = {ids[i]: ids[i + 1], ids[i + 1]: ids[i]}
        recs.append(_record("T2", f"swap_{i}_{i + 1}", g, sw, gm.get(gold, gold), level_type, source, qname))
        if level_type == "ordinal":
            rv = [dict(l, name=base[k - 1 - j]["name"], id=base[k - 1 - j]["id"]) for j, l in enumerate(base)]
            recs.append(_record("T2", "reversed", g, rv, gold, level_type, source, qname))
    return recs


def load_fixture(recs, tmpdir, name="fixture.jsonl"):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    return common.load_records(path)


def rows_for(scorer, loaded):
    return [common.make_row(r, p) for r, p in zip(loaded, scorer.score(loaded))]


def decided_for(scorer, loaded, tau=0.5):
    return M.decide_rows(rows_for(scorer, loaded), FixedTau(tau))


def _tmp():
    return tempfile.TemporaryDirectory()


# ---------------------------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------------------------

def test_cumulative_operator_hand_cases():
    pos = lambda p, t, tau: decision.cumulative_decision(p, t, tau)[0]
    assert pos([0.7, 0.3], "boolean", 0.6) == 0          # side with mass >= tau wins
    assert pos([0.3, 0.7], "boolean", 0.6) == 1
    assert pos([0.5, 0.5], "boolean", 0.6) is None       # neither side clears tau -> C
    assert pos([0.45, 0.1, 0.45], "ordinal", 0.6) is None  # bimodal goes to C, not to the middle
    assert pos([0.1, 0.8, 0.1], "ordinal", 0.6) == 1
    assert pos([0.8, 0.1, 0.1], "ordinal", 0.6) == 0
    assert pos([0.5, 0.3, 0.2], "nominal", 0.6) is None  # top level must clear tau
    assert pos([1 / 3] * 3, "nominal", 0.6) is None      # diffuse mass never decides a lower-ranked level
    assert pos([0.2, 0.7, 0.1], "nominal", 0.6) == 1
    assert decision.argmax_index([0.2, 0.5, 0.5]) == 1   # reference column, ties to lowest position


def test_margin_distance_hand_count():
    _, d = decision.cumulative_decision([0.7, 0.3], "boolean", 0.6)
    assert abs(d - 0.1) < 1e-12                          # |0.7 - 0.6|; |0.7 - 0.4| is larger


def test_gold_case_resolution():
    rec = {"gold": "False", "levels": [{"id": "true"}, {"id": "false"}]}
    assert common.resolve_gold(rec) == "false"
    assert common.resolve_gold({"gold": "zzz", "levels": [{"id": "a"}]}) is None


# ---------------------------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------------------------

def test_split_is_stable_and_order_independent():
    ids = [f"group-{i}" for i in range(5000)]
    first = {g: S.GROUP70.assign({"group_id": g}) for g in ids}
    second = {g: S.GROUP70.assign({"group_id": g}) for g in reversed(ids)}
    assert first == second
    share = sum(v == S.TRAIN for v in first.values()) / len(ids)
    assert 0.68 < share < 0.72


def test_split_pinned_buckets():
    # Literal values, computed once from the definition in split.py. If one changes, the frozen
    # split changed and every earlier result is no longer comparable.
    assert S.bucket("g0") == 4362
    assert S.bucket("b3-m-0001") == 9112
    assert S.bucket("tr_agent_trace_observability_000000") == 1504
    assert S.GROUP70.assign({"group_id": "tr_agent_trace_observability_000000"}) == S.TRAIN
    assert S.GROUP70.assign({"group_id": "b3-m-0001"}) == S.HELDOUT
    assert S.QUESTION70.assign({"qname": "life_support_certificate_current"}) == S.HELDOUT


def test_variants_of_a_group_share_a_side_and_question_split_is_disjoint():
    with _tmp() as d:
        loaded = load_fixture(make_records(80), d)
    side = {}
    for r in loaded:
        side.setdefault(r["group_id"], set()).add(S.GROUP70.assign(r))
    assert all(len(v) == 1 for v in side.values())
    qs = [{"qname": f"question-{i}"} for i in range(500)]
    train = {r["qname"] for r in qs if S.QUESTION70.assign(r) == S.TRAIN}
    held = {r["qname"] for r in qs if S.QUESTION70.assign(r) == S.HELDOUT}
    assert train and held and not (train & held)
    assert S.splitters_for_source("akhilaaa3-hard") == (S.GROUP70, S.QUESTION70)
    assert S.splitters_for_source("openjev-synth") == (S.GROUP70,)


# ---------------------------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------------------------

def test_prompt_input_modes_and_render_modes():
    with _tmp() as d:
        loaded = load_fixture(make_records(2), d)
    t1 = {r["variant"]: r for r in loaded if r["task"] == "T1" and r["group_id"] == "g0"}
    full = prompting.build_prompt(t1["original"]).text
    blank = prompting.build_prompt(prompting.blank_input(t1["original"])).text
    drop = prompting.build_prompt(prompting.drop_input(t1["original"])).text
    assert "business input 0" in full
    assert "Input:" in blank and "business input 0" not in blank
    assert "Input:" not in drop and "Question:" in drop and "definition 0-0" in drop
    assert full.index("Workflow") < full.index("Input:") < full.index("Question:") < full.index("Options:")
    names = {v: prompting.build_prompt(r).text for v, r in t1.items()}   # default is record_name
    neutral = {v: prompting.build_prompt(r, "neutral").text for v, r in t1.items()}
    assert len(set(names.values())) == 4
    assert len(set(neutral.values())) == 1               # neutral render: T1 flip is 0 by construction


def test_hf_encode_adds_no_special_tokens_and_scores_identifier_only():
    class FakeTok:
        def __call__(self, text, add_special_tokens=True):
            assert add_special_tokens is False
            return {"input_ids": [ord(c) for c in text]}
    with _tmp() as d:
        loaded = load_fixture(make_records(1), d)
    s = sc.HFScorer("unused", model=object(), tokenizer=FakeTok())
    prefix, cands = s._encode(loaded[0])
    assert prefix[-len(prompting.ANSWER_CUE):] == [ord(c) for c in prompting.ANSWER_CUE]
    assert cands[0] == [ord(c) for c in " word0"]


_LOCK_BASE = {"candidate_set": "exclusive", "task_definition": "Workflow: demo. Answer using only the criteria given.",
              "input": '{"steps": 7}', "question": "What should happen?"}
_LOCK_1 = dict(_LOCK_BASE, levels=[{"id": "stop", "name": "x1", "definition": "Halt now."},
                                   {"id": "go", "name": "x2", "definition": "Proceed."}])
_LOCK_2 = dict(_LOCK_BASE, input="  spaced  ", levels=[{"id": "0", "name": "0", "definition": "Low."},
                                                    {"id": "1", "name": "1", "definition": "Mid."},
                                                    {"id": "2", "name": "2", "definition": "High."}])
_LOCK_1_TEXT = ("Workflow: demo. Answer using only the criteria given.\n\nInput:\n{\"steps\": 7}\n\n"
                "Question: What should happen?\n\nOptions:\n- L1: Halt now.\n- L2: Proceed.\n\n"
                "Answer with the identifier of exactly one option.\nAnswer:")
_LOCK_2_TEXT = ("Workflow: demo. Answer using only the criteria given.\n\nInput:\nspaced\n\n"
                "Question: What should happen?\n\nOptions:\n- L1: Low.\n- L2: Mid.\n- L3: High.\n\n"
                "Answer with the identifier of exactly one option.\nAnswer:")


def test_prompt_is_locked_against_stored_strings():
    # If this fails you changed the prompt: bump PROMPT_VERSION in prompt.py, update the strings
    # here, and treat every earlier report as not comparable (B-4).
    assert prompting.PROMPT_VERSION == "r0-prompt-v2"
    p1, p2 = prompting.build_prompt(_LOCK_1, "neutral"), prompting.build_prompt(_LOCK_2, "neutral")
    assert p1.text == _LOCK_1_TEXT and p2.text == _LOCK_2_TEXT
    assert p1.labels == ("L1", "L2") and dict(p1.to_original) == {"L1": "stop", "L2": "go"}
    assert p2.candidates == (" L1", " L2", " L3") and dict(p2.to_original) == {"L1": "0", "L2": "1", "L3": "2"}


def test_prompt_is_pure_and_names_matter_only_under_record_name():
    shuffled = dict(reversed(list(_LOCK_1.items())))
    renamed = dict(_LOCK_1, levels=[dict(l, name="zzz" + l["name"]) for l in _LOCK_1["levels"]])
    for mode in ("record_name", "neutral"):
        assert prompting.build_prompt(shuffled, mode) == prompting.build_prompt(_LOCK_1, mode)
        assert prompting.build_prompt(_LOCK_1, mode).text == prompting.build_prompt(_LOCK_1, mode).text
    # neutral: a renamed level must NOT change the prompt; record_name: it MUST.
    assert prompting.build_prompt(renamed, "neutral").text == _LOCK_1_TEXT
    assert prompting.build_prompt(renamed, "record_name").text != prompting.build_prompt(_LOCK_1, "record_name").text
    assert "- zzzx1: Halt now." in prompting.build_prompt(renamed, "record_name").text
    assert prompting.build_prompt(_LOCK_1).text == prompting.build_prompt(_LOCK_1, "record_name").text  # default


_T3_BASE = dict(_LOCK_1, task="T3", question="What should happen?")
_T3_VARIANTS = {
    "prefix_1q": ["What should happen?"],
    "prefix_3q": ["Q-b?", "Q-c?", "What should happen?"],
    "prefix_5q": ["Q-a?", "Q-b?", "Q-c?", "Q-d?", "What should happen?"],
    "prefix_5q_shuffled": ["Q-c?", "Q-a?", "Q-d?", "Q-b?", "What should happen?"],
}
_T3_LOCK_5Q = ("Workflow: demo. Answer using only the criteria given.\n\nInput:\n{\"steps\": 7}\n\n"
               "Other questions about this input (not asked now):\n1. Q-a?\n2. Q-b?\n3. Q-c?\n4. Q-d?\n\n"
               "Question: What should happen?\n\nOptions:\n- L1: Halt now.\n- L2: Proceed.\n\n"
               "Answer with the identifier of exactly one option.\nAnswer:")


def test_t3_prompt_lock_and_variants_differ():
    recs = {v: dict(_T3_BASE, variant=v, prefix_questions=pq) for v, pq in _T3_VARIANTS.items()}
    assert prompting.build_prompt(recs["prefix_5q"], "neutral").text == _T3_LOCK_5Q
    texts = {v: prompting.build_prompt(r).text for v, r in recs.items()}
    assert len(set(texts.values())) == 4            # guards the flip-rate-0-by-construction bug
    assert texts["prefix_5q"].replace("Q-a?", "@").replace("Q-b?", "#") != texts["prefix_5q_shuffled"].replace("Q-a?", "@").replace("Q-b?", "#")
    assert texts["prefix_5q"].index("Q-a?") < texts["prefix_5q"].index("Q-b?")          # given order kept
    assert texts["prefix_5q_shuffled"].index("Q-c?") < texts["prefix_5q_shuffled"].index("Q-a?")
    assert texts["prefix_1q"] == prompting.build_prompt(_T3_BASE).text                  # no unrelated questions


def test_records_without_prefix_questions_render_as_v1():
    # v1 layout reproduced literally; T1/T2 must be unaffected by the T3 addition.
    expect = ("Workflow: demo. Answer using only the criteria given.\n\nInput:\n{\"steps\": 7}\n\n"
              "Question: What should happen?\n\nOptions:\n- x1: Halt now.\n- x2: Proceed.\n\n"
              "Answer with the identifier of exactly one option.\nAnswer:")
    assert prompting.build_prompt(_LOCK_1).text == expect


def test_t3_flip_responds_to_question_set_dependence():
    with _tmp() as d:
        recs = []
        for g in range(60):
            for v, pq in _T3_VARIANTS.items():
                lv = [{"id": str(i), "name": f"n{i}", "definition": f"def {g}-{i}"} for i in range(3)]
                recs.append(dict(_record("T3", v, g, lv, "0", "nominal"), prefix_questions=pq))
        loaded = load_fixture(recs, d)
    class PrefixDriven(sc.Scorer):
        name = "prefix-driven"
        def score(self, items):
            return [sc.MockScorer("m", random_weight=1.0, sharpness=40.0).score(
                [dict(it, key=it["key"] + "|".join(it["prefix_questions"]))])[0] for it in items]
    inv = M.flip_rate(decided_for(sc.MockScorer.invariant(), loaded), "T3")
    drv = M.flip_rate(decided_for(PrefixDriven(), loaded), "T3")
    assert inv["n_units"] == 60 and inv["overall"] == 0.0
    assert drv["overall"] > 0.4 and "prefix_5q|prefix_5q_shuffled" in drv["per_pair"]
    assert M.accuracy_floor(decided_for(sc.MockScorer.oracle(), loaded, 0.9), "T3")["acc_cumulative"] == 1.0
    assert TH.fitting_row(common.make_row(loaded[0], [1/3]*3) | {})


# ---------------------------------------------------------------------------------------------
# Mock scorer and the invariance / discrimination metrics
# ---------------------------------------------------------------------------------------------

def test_mock_is_deterministic_and_normalized():
    with _tmp() as d:
        loaded = load_fixture(make_records(5), d)
    a = sc.MockScorer.random().score(loaded)
    b = sc.MockScorer.random().score(loaded)
    assert a == b
    assert all(abs(sum(p) - 1.0) < 1e-9 for p in a)
    assert a != sc.MockScorer.invariant().score(loaded)


def test_flip_rate_zero_for_invariant_and_high_for_name_driven():
    with _tmp() as d:
        loaded = load_fixture(make_records(150, k=4), d)
    inv = M.flip_rate(decided_for(sc.MockScorer.invariant(), loaded))
    nd = M.flip_rate(decided_for(sc.MockScorer.name_driven(), loaded))
    assert inv["n_units"] == 150
    assert inv["overall"] == 0.0 and all(v == 0.0 for v in inv["per_pair"].values())
    # Four levels with independent names: two variants disagree with probability 3/4.
    assert nd["overall"] > 0.65
    assert all(0.55 < v <= 1.0 for v in nd["per_pair"].values())
    assert len(nd["per_pair"]) == 6


def test_move_rate_identifies_followed_swaps_and_unmoved_for_name_driven():
    with _tmp() as d:
        loaded = load_fixture(make_records(150, k=4), d)
    # Sharp distributions: the ordinal operator is not permutation-equivariant (see decision.py), so a
    # definition-following model is only guaranteed to "follow" when its mass is concentrated.
    sharp = sc.MockScorer("mock-invariant-sharp", definition_weight=1.0, sharpness=40.0)
    inv = M.move_rate(decided_for(sharp, loaded))
    nd = M.move_rate(decided_for(sc.MockScorer.name_driven(), loaded))
    assert inv["swap"]["n_eligible"] > 10 and inv["swap"]["followed_rate"] == 1.0
    assert inv["reversed"]["followed_rate"] == 1.0
    assert nd["swap"]["unmoved_rate"] == 1.0 and nd["swap"]["followed_rate"] == 0.0
    assert nd["reversed"]["unmoved_rate"] == 1.0
    # swap items are eligible only when the base decision sat at position i (about 1 in k)
    assert inv["swap"]["n_eligible"] + inv["swap"]["n_ineligible"] == 150


def test_move_rate_hand_count():
    def row(task, variant, unit, p, ids=("0", "1", "2")):
        return {"k": f"{unit}{variant}", "task": task, "variant": variant, "source": "s", "group_id": unit, "qname": "q",
                "unit": unit, "level_type": "nominal", "ids": list(ids), "gold": ids[0], "p": p, "lsv": "x", "tau_lsv": "x"}
    hi = lambda i: [0.9 if j == i else 0.05 for j in range(3)]
    mid = [1 / 3] * 3
    rows = [
        # unit a: base at 0, swap_0_1 moves to 1 -> followed
        row("T2", "base", "a", hi(0)), row("T2", "swap_0_1", "a", hi(1)),
        # unit b: base at 0, swap stays at 0 -> unmoved
        row("T2", "base", "b", hi(0)), row("T2", "swap_0_1", "b", hi(0)),
        # unit c: base at 0, swap goes to 2 -> moved elsewhere
        row("T2", "base", "c", hi(0)), row("T2", "swap_0_1", "c", hi(2)),
        # unit d: base at 0, swap becomes C -> moved elsewhere
        row("T2", "base", "d", hi(0)), row("T2", "swap_0_1", "d", mid),
        # unit e: base at 2 (not i) -> ineligible
        row("T2", "base", "e", hi(2)), row("T2", "swap_0_1", "e", hi(2)),
        # unit f: base is C -> ineligible
        row("T2", "base", "f", mid), row("T2", "swap_0_1", "f", hi(1)),
    ]
    m = M.move_rate(M.decide_rows(rows, FixedTau(0.6)))["swap"]
    assert (m["n_eligible"], m["followed"], m["unmoved"], m["moved_elsewhere"], m["n_ineligible"]) == (4, 1, 1, 2, 2)
    assert m["followed_rate"] == 0.25


def test_flip_and_failure_set_hand_count():
    def row(unit, variant, p, gold="1"):
        return {"k": f"{unit}{variant}", "task": "T1", "variant": variant, "source": "s", "group_id": unit, "qname": "q",
                "unit": unit, "level_type": "boolean", "ids": ["0", "1"], "gold": gold, "p": p, "lsv": variant, "tau_lsv": variant}
    right, wrong, tie = [0.1, 0.9], [0.9, 0.1], [0.5, 0.5]
    rows = [row("u1", v, right) for v in common.T1_VARIANTS]                       # all correct, no flips
    rows += [row("u2", "original", right), row("u2", "digits", wrong),             # one pair set differs
             row("u2", "letters", right), row("u2", "random", right)]
    rows += [row("u3", "original", wrong)] + [row("u3", v, wrong) for v in common.T1_VARIANTS[1:]]  # always wrong
    rows += [row("u4", "original", right), row("u4", "digits", tie), row("u4", "letters", tie), row("u4", "random", tie)]
    d = M.decide_rows(rows, FixedTau(0.6))
    flip = M.flip_rate(d)
    # u2: digits differs from the other three -> 3 of 6 pairs; u4: original vs three C -> 3 of 6 pairs;
    # the pair original|digits differs in u2 and u4 only
    assert flip["n_units"] == 4 and abs(flip["overall"] - 6 / 24) < 1e-12
    assert flip["per_pair"]["original|digits"] == 2 / 4
    fs = M.failure_sets(d)
    # original fails: u3 and... u4's original is right; so 1. cumulative: u2, u3, u4 fail somewhere -> 3
    assert (fs["failures_original"], fs["failures_cumulative"]) == (1, 3) and fs["growth"] == 2.0
    acc = M.accuracy_floor(d, "T1")
    assert acc["n"] == 4 and acc["acc_cumulative"] == 3 / 4
    assert M.c_branch_rate(d, "T1")["rate"] == 3 / 16


def test_ece_hand_count():
    def row(p, gold):
        return {"k": "k", "task": "T1", "variant": "original", "source": "s", "group_id": "g", "qname": "q", "unit": "u",
                "level_type": "boolean", "ids": ["0", "1"], "gold": gold, "p": p, "lsv": "x", "tau_lsv": "x"}
    rows = [row([0.9, 0.1], "0")] * 8 + [row([0.9, 0.1], "1")] * 2   # confidence 0.9, accuracy 0.8
    e = M.ece(M.decide_rows(rows, FixedTau(0.5)))
    assert abs(e["ece"] - 0.1) < 1e-12


def test_oracle_has_full_accuracy_and_uniform_is_all_c():
    with _tmp() as d:
        loaded = load_fixture(make_records(40), d)
    acc = M.accuracy_floor(decided_for(sc.MockScorer.oracle(), loaded, tau=0.9), "T1")
    assert acc["acc_cumulative"] == 1.0
    uni = decided_for(sc.UniformScorer(), loaded, tau=0.6)
    assert M.c_branch_rate(uni, "T1")["rate"] == 1.0


# ---------------------------------------------------------------------------------------------
# Thresholds and the constant classifier: train only
# ---------------------------------------------------------------------------------------------

def _boolean_rows(group_prefix, n, gold_false, gold_true, source="s", qname="q"):
    rows = []
    for i in range(n):
        gold = "false" if i < gold_false else "true"
        rows.append({"k": f"{group_prefix}{i}", "task": "T1", "variant": "original", "source": source,
                     "group_id": f"{group_prefix}{i}", "qname": qname, "unit": f"{group_prefix}{i}",
                     "level_type": "boolean", "ids": ["false", "true"], "gold": gold, "p": [0.8, 0.2],
                     "lsv": "v", "tau_lsv": "v"})
    return rows


def _split_rows(n_each=400, **kw):
    """Rows whose group ids are drawn until n_each land on each side."""
    train, held, i = [], [], 0
    while len(train) < n_each or len(held) < n_each:
        row = _boolean_rows(f"G{i}-", 1, 0, 1, **kw)[0]
        (train if S.GROUP70.assign(row) == S.TRAIN else held).append(row)
        i += 1
    return train[:n_each], held[:n_each]


def test_tau_is_fitted_on_train_and_applied_unchanged_to_heldout():
    train, held = _split_rows(60)
    for i, r in enumerate(train):       # train: 20 gold=false, 40 gold=true while the model says false at 0.8
        r["gold"] = "false" if i < 20 else "true"
    for r in held:                      # held-out would prefer tau=0.5: model is always right there
        r["gold"] = "false"
    rows = train + held
    fitted = TH.fit_thresholds(S.TrainView.of(rows, S.GROUP70))
    tau_train, tier = fitted.tau_for(train[0])
    assert tau_train == 0.95 and tier == "version"      # deciding costs utility on train, so abstain
    assert fitted.tau_for(held[0]) == (0.95, "version")  # same key, same tau, unchanged on held-out
    # Held-out decisions follow that tau (all C) although tau=0.5 would have been perfect there.
    assert all(d.cum_pos is None for d in M.decide_rows(held, fitted))
    assert all(d.cum_id == "false" for d in M.decide_rows(held, FixedTau(0.5)))


def test_fit_cannot_see_heldout_rows():
    train, held = _split_rows(60)
    base = TH.fit_thresholds(S.TrainView.of(train + held, S.GROUP70))
    for r in held:                       # corrupt every held-out row; the fit must not change
        r["gold"] = "true"
        r["p"] = [0.1, 0.9]
    again = TH.fit_thresholds(S.TrainView.of(train + held, S.GROUP70))
    assert base._table == again._table
    try:
        TH.fit_thresholds(train + held)
        raise AssertionError("fit accepted a plain list")
    except TypeError:
        pass
    try:
        S.TrainView(S.GROUP70, held, object())
        raise AssertionError("TrainView built without the factory")
    except TypeError:
        pass
    try:
        TH.fit_thresholds(S.TrainView(S.GROUP70, held, S.TrainView._token))  # tampered
        raise AssertionError("fit accepted held-out rows")
    except ValueError:
        pass


def test_tau_fallback_tiers_for_unseen_questions():
    train, _ = _split_rows(60)
    fitted = TH.fit_thresholds(S.TrainView.of(train, S.GROUP70))
    unseen_version = dict(train[0], tau_lsv="other")
    assert fitted.tau_for(unseen_version)[1] == "question"
    unseen_question = dict(train[0], qname="other-q", tau_lsv="other")
    assert fitted.tau_for(unseen_question)[1] == "type_size"
    unseen_source = dict(train[0], source="other-src", qname="x", tau_lsv="other")
    assert fitted.tau_for(unseen_source) == (TH.DEFAULT_TAU, "default")


def test_constant_classifier_is_fitted_on_train_only():
    with _tmp() as d:
        loaded = load_fixture(make_records(200, k=2, level_type="boolean"), d)
    train = S.TrainView.of(loaded, S.GROUP70)
    clf = sc.ConstantClassifierScorer("group70")
    clf.fit(train)
    # Make the held-out side disagree with train: the prediction must not move.
    before = clf.score(loaded)
    mutated = [dict(r, gold_id="1" if S.GROUP70.assign(r) == S.HELDOUT else r["gold_id"]) for r in loaded]
    clf2 = sc.ConstantClassifierScorer("group70")
    clf2.fit(S.TrainView.of(mutated, S.GROUP70))
    assert before == clf2.score(loaded)
    assert all(sorted(p) == [0.0, 1.0] for p in before)
    train_golds = [r["gold_id"] for r in train.rows if r["variant"] == FLOOR(r["task"])]
    counts = {g: train_golds.count(g) for g in set(train_golds)}
    majority = sorted(counts, key=lambda g: (-counts[g], g))[0]
    assert clf.majority_for(loaded[0]) == majority
    try:
        clf.fit(loaded)
        raise AssertionError("constant classifier accepted a plain list")
    except TypeError:
        pass
    try:
        sc.ConstantClassifierScorer("group70").score(loaded[:1])
        raise AssertionError("unfitted classifier scored")
    except RuntimeError:
        pass


def FLOOR(task):
    return common.FLOOR_VARIANT[task]


# ---------------------------------------------------------------------------------------------
# End to end: runner, report, resume, determinism
# ---------------------------------------------------------------------------------------------

def _write_fixture_tree(root):
    for task, dirname in common.TASK_DIRS.items():
        os.makedirs(os.path.join(root, dirname), exist_ok=True)
    recs = make_records(120, k=4, source="src-a") + make_records(60, k=2, level_type="boolean", source="src-b")
    for task in ("T1", "T2"):
        for src in ("src-a", "src-b"):
            path = os.path.join(root, common.TASK_DIRS[task], src + ".jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for r in recs:
                    if r["task"] == task and r["source"] == src:
                        f.write(json.dumps(r) + "\n")


def _run(data, out, base, extra=()):
    run_baseline.main(["--base", base, "--data-root", data, "--out-root", out, "--sources", "src-a,src-b",
                       "--chunk", "50", *extra])


def _report(out):
    with open(os.path.join(out, "report.json")) as f:
        rep = json.load(f)
    rep["header"].pop("report_utc")
    return rep


def test_end_to_end_with_mock_and_report_structure():
    with _tmp() as tmp:
        data, out = os.path.join(tmp, "data"), os.path.join(tmp, "out")
        _write_fixture_tree(data)
        _run(data, out, "mock-invariant")
        rep = _report(out)
        hdr = rep["header"]
        assert hdr["scorer"] == "mock-invariant" and hdr["git_commit"] and "python" in hdr
        cells = rep["splits"]["group70"]["heldout"]
        assert set(cells) == {"src-a", "src-b"} and set(cells["src-a"]) == {"ordinal"} and set(cells["src-b"]) == {"boolean"}
        roles = set(cells["src-a"]["ordinal"])
        assert roles == {"primary", "empty_input", "question_only", "constant", "uniform"}   # degenerate twins always present
        assert "question70" not in rep["splits"]                                            # akhilaaa3 only
        assert cells["src-a"]["ordinal"]["primary"]["flip_T1"]["overall"] == 0.0
        assert cells["src-a"]["ordinal"]["empty_input"]["flip_T1"]["overall"] == 0.0        # mock: no input dependence of names
        assert cells["src-a"]["ordinal"]["primary"]["move_T2"]["swap"]["followed_rate"] == 1.0
        assert rep["missing"] == []
        md = open(os.path.join(out, "report.md")).read()
        assert "## Split `group70`, side `heldout`" in md and "### B-2" in md
        assert "ECE" in md and "mock-invariant" in md
        assert "pooled" not in md and "all sources" not in md
        # every readout file starts with the mandatory header fields
        rdir = os.path.join(out, "readouts")
        for fn in os.listdir(rdir):
            with open(os.path.join(rdir, fn)) as f:
                h = json.loads(f.readline())["_header"]
            for key in ("model_path", "image_id", "git_commit", "scorer", "utc"):
                assert key in h


def test_name_driven_mock_shows_up_in_the_decision_lines():
    with _tmp() as tmp:
        data, out = os.path.join(tmp, "data"), os.path.join(tmp, "out")
        _write_fixture_tree(data)
        _run(data, out, "mock-name-driven")
        rep = _report(out)
        cell = rep["splits"]["group70"]["heldout"]["src-a"]["ordinal"]
        assert cell["primary"]["flip_T1"]["overall"] > 0.5
        assert cell["primary"]["move_T2"]["swap"]["followed_rate"] == 0.0
        b3 = [r for r in rep["decision_lines"]["B-3"] if r["source"] == "src-a"][0]
        assert b3["above_30_percent"] is False


def test_rerun_is_identical_and_resume_after_kill_is_identical():
    with _tmp() as tmp:
        data = os.path.join(tmp, "data")
        _write_fixture_tree(data)
        out1, out2 = os.path.join(tmp, "o1"), os.path.join(tmp, "o2")
        _run(data, out1, "mock-random")
        _run(data, out2, "mock-random")
        assert _report(out1) == _report(out2)
        # Simulate a killed run: truncate one readout file in the middle of a line, then resume.
        victim = os.path.join(out2, "readouts", "mock-random__T1__src-a.jsonl")
        with open(victim, "rb") as f:
            blob = f.read()
        with open(victim, "wb") as f:
            f.write(blob[: len(blob) // 2])
        _run(data, out2, "mock-random")
        def body(path):
            with open(path) as f:
                return [json.loads(l) for l in f.readlines()[1:]]
        assert body(victim) == body(os.path.join(out1, "readouts", "mock-random__T1__src-a.jsonl"))
        assert _report(out1) == _report(out2)
        # A resumed run against a different configuration is refused.
        try:
            _run(data, out2, "mock-random", ("--render", "neutral"))
            raise AssertionError("header mismatch not detected")
        except SystemExit as e:
            assert "mismatch" in str(e)


def test_question_disjoint_split_reported_for_akhilaaa3_only():
    with _tmp() as tmp:
        data, out = os.path.join(tmp, "data"), os.path.join(tmp, "out")
        for task, dirname in common.TASK_DIRS.items():
            os.makedirs(os.path.join(data, dirname))
        recs = []
        for q in range(40):
            recs += make_records(3, k=2, level_type="boolean", source="akhilaaa3-medium", qname=f"question-{q}")
        # group ids repeat across questions: make them unique per question
        for r in recs:
            pass
        by = {"T1": [], "T2": []}
        for n, r in enumerate(recs):
            r = dict(r, group_id=f"case{(n // 12) % 40}-{r['group_id']}")
            by[r["task"]].append(r)
        for task in by:
            with open(os.path.join(data, common.TASK_DIRS[task], "akhilaaa3.jsonl"), "w") as f:
                for r in by[task]:
                    f.write(json.dumps(r) + "\n")
        run_baseline.main(["--base", "mock-oracle", "--data-root", data, "--out-root", out,
                           "--sources", "akhilaaa3", "--chunk", "50"])
        rep = _report(out)
        assert set(rep["splits"]) == {"group70", "question70"}
        assert "constant@question70" in {v["scorer"] for v in rep["thresholds"]["question70"].values()}
        # Under the question-disjoint split no question is on both sides.
        rows, _, _ = run_baseline.load_all_readouts(out)
        sides = {}
        for r in rows["mock-oracle"]:
            sides.setdefault(r["qname"], set()).add(S.QUESTION70.assign(r))
        assert all(len(v) == 1 for v in sides.values())


def _keys(out):
    rdir = os.path.join(out, "readouts")
    keys = []
    for fn in sorted(os.listdir(rdir)):
        with open(os.path.join(rdir, fn)) as f:
            hdr = json.loads(f.readline())["_header"]
            keys += [(hdr["scorer"], hdr["task"], hdr["source_file"], json.loads(l)["k"]) for l in f]
    return keys


def test_shards_partition_the_item_set_exactly_and_merge_to_the_unsharded_report():
    with _tmp() as tmp:
        data = os.path.join(tmp, "data")
        _write_fixture_tree(data)
        whole, sharded = os.path.join(tmp, "whole"), os.path.join(tmp, "sharded")
        _run(data, whole, "mock-random")
        n = 5
        for i in range(n):
            _run(data, sharded, "mock-random", ("--shard", str(i), "--num-shards", str(n)))
            assert not os.path.exists(os.path.join(sharded, "report.json")) or i == n   # shards do not emit a partial report
        _run(data, sharded, "mock-random", ("--report-only", "--num-shards", str(n)))
        a, b = _keys(whole), _keys(sharded)
        assert len(b) == len(set(b)), "duplicate items across shards"
        assert sorted(a) == sorted(b), "union of shards differs from the unsharded item set"
        # a group never splits across shards
        recs = [r for _, (_, rr) in run_baseline.load_task_files(run_baseline.parse_args(
            ["--data-root", data, "--sources", "src-a,src-b"])).items() for r in rr]
        by_group = {}
        for r in recs:
            by_group.setdefault((r["source"], r["group_id"]), set()).add(run_baseline.shard_of(r["group_id"], n))
        assert all(len(v) == 1 for v in by_group.values())
        assert len({s for v in by_group.values() for s in v}) > 1, "fixture should use more than one shard"
        # merged report equals the unsharded one apart from the shard bookkeeping in the header
        ra, rb = _report(whole), _report(sharded)
        for rep in (ra, rb):
            for k in ("shard_layout",):
                rep["header"].pop(k)
        assert ra == rb
        assert rb["header"]["incomplete_scorers"] == []


def test_missing_shard_is_visible_in_the_report_header():
    with _tmp() as tmp:
        data = os.path.join(tmp, "data")
        _write_fixture_tree(data)
        out = os.path.join(tmp, "o")
        for i in (0, 1, 2):   # shard 3 of 4 never ran
            _run(data, out, "mock-random", ("--shard", str(i), "--num-shards", "4"))
        _run(data, out, "mock-random", ("--report-only", "--num-shards", "4"))
        # headers only know their own file's expected count, so a wholly missing shard shows up as
        # fewer readout files than num_shards per scorer
        h = _report(out)["header"]
        assert h["shard_layout"]["num_shards"] == 4
        assert all(v < 4 * 4 for v in h["shard_layout"]["readout_files_per_scorer"].values())


def test_frozen_sample_restricts_every_scorer_to_the_same_whole_groups():
    with _tmp() as tmp:
        data = os.path.join(tmp, "data")
        _write_fixture_tree(data)
        recs = [r for _, (_, rr) in run_baseline.load_task_files(run_baseline.parse_args(
            ["--data-root", data, "--sources", "src-a,src-b"])).items() for r in rr]
        gids = sorted({r["group_id"] for r in recs if r["source"] == "src-a"})[:7]
        sample = os.path.join(tmp, "sample.json")
        with open(sample, "w") as f:
            json.dump({"seed": 1, "rule": "test", "full": False, "groups": {
                "T1/src-a": gids, "T2/src-a": gids, "T1/src-b": None, "T2/src-b": None}}, f)
        out = os.path.join(tmp, "o")
        _run(data, out, "mock-random", ("--sample", sample))
        keys = _keys(out)
        by_scorer = {}
        for sc_name, task, src, k in keys:
            by_scorer.setdefault(sc_name, set()).add((task, src, k))
        sizes = {k: len(v) for k, v in by_scorer.items() if not k.startswith("constant@question")}
        assert len(set(sizes.values())) == 1, sizes              # same item set for every scorer
        h = _report(out)["header"]
        assert h["sample_sha256"] and h["seed"] == 1
        with open(os.path.join(out, "report.json")) as f:
            assert json.load(f)["header"]["sample_groups"]["T1/src-a"] == gids
        used = {r["group_id"] for r in recs if r["source"] == "src-a" and r["group_id"] in set(gids)}
        assert len(used) == 7


# ---------------------------------------------------------------------------------------------
# Amendment 4 (pre-registration section 11)
# ---------------------------------------------------------------------------------------------

def _a4_row(task, unit, variant, p, level_type="ordinal", gold=None):
    ids = [str(i) for i in range(len(p))]
    return {"k": f"{task}{unit}{variant}", "task": task, "variant": variant, "source": "s", "group_id": unit, "qname": "q",
            "unit": unit, "level_type": level_type, "ids": ids, "gold": ids[0] if gold is None else gold, "p": p,
            "lsv": variant, "tau_lsv": variant}


def _peak(k, i, mass=0.5):
    """Distribution over k levels with ``mass`` on level i and the rest spread evenly."""
    return [mass if j == i else (1 - mass) / (k - 1) for j in range(k)]


def _abstaining_name_sensitive_cell(n_units=8):
    """The actual defect: ordinal, tau fitted at 0.95 so every row abstains, while the four name variants
    of every unit put their argmax on four different levels (the smoke-run cell, openjev-synth / ordinal)."""
    rows = []
    for u in range(n_units):
        for pos, v in enumerate(common.T1_VARIANTS):
            rows.append(_a4_row("T1", f"u{u}", v, _peak(4, pos, 0.4)))
    return rows


def test_a4_fully_abstaining_cell_has_null_thresholded_flip_and_real_argmax_flip():
    d = M.decide_rows(_abstaining_name_sensitive_cell(), FixedTau(0.95))
    assert all(x.cum_pos is None for x in d)                    # precondition: the operator abstains everywhere
    flip = M.flip_rate(d)
    assert flip["overall"] is None                              # not 0.0: there is nothing to flip
    assert all(v is None for v in flip["per_pair"].values())
    assert flip["argmax_reference"]["overall"] == 1.0           # four different argmax positions per unit
    assert all(v == 1.0 for v in flip["argmax_reference"]["per_pair"].values())
    assert flip["n_decisions"] == 0
    assert flip["c_branch"]["rate"] == 1.0 and flip["c_branch"]["forced_by_tau"] is True
    assert flip["c_branch"]["fitted_taus"] == [0.95]


def test_a4_fully_abstaining_t3_flip_is_null_and_argmax_is_real():
    rows = [_a4_row("T3", f"u{u}", v, _peak(4, pos, 0.4)) for u in range(5) for pos, v in enumerate(common.T3_VARIANTS)]
    flip = M.flip_rate(M.decide_rows(rows, FixedTau(0.95)), "T3")
    assert flip["overall"] is None and flip["argmax_reference"]["overall"] == 1.0


def test_a4_flip_rate_is_a_real_zero_when_the_operator_decides_and_agrees():
    rows = [_a4_row("T1", f"u{u}", v, _peak(4, 1, 0.97)) for u in range(5) for v in common.T1_VARIANTS]
    flip = M.flip_rate(M.decide_rows(rows, FixedTau(0.9)))
    assert flip["overall"] == 0.0 and flip["argmax_reference"]["overall"] == 0.0     # a real zero stays a zero
    assert flip["c_branch"]["rate"] == 0.0


def test_a4_flip_carries_the_c_branch_rate_beside_it():
    # half the rows abstain at tau 0.8: the 0.97-peaked ones decide, the 0.4-peaked ones do not
    rows = []
    for u in range(4):
        sharp = u % 2 == 0
        for pos, v in enumerate(common.T1_VARIANTS):
            rows.append(_a4_row("T1", f"u{u}", v, _peak(4, 1, 0.97) if sharp else _peak(4, pos, 0.4)))
    flip = M.flip_rate(M.decide_rows(rows, FixedTau(0.8)))
    assert flip["c_branch"]["n"] == 16 and flip["c_branch"]["rate"] == 0.5
    assert flip["c_branch"]["forced_by_tau"] is False
    assert flip["overall"] is not None and flip["n_decisions"] == 8


def test_a4_margin_counts_decisions_not_rows():
    # unit a decides (sharp), unit b abstains (flat). The ordinal operator still returns a distance for b.
    rows = [_a4_row("T1", "a", v, _peak(4, 1, 0.97)) for v in common.T1_VARIANTS]
    rows += [_a4_row("T1", "b", v, _peak(4, 1, 0.4)) for v in common.T1_VARIANTS]
    d = M.decide_rows(rows, FixedTau(0.9))
    assert any(x.dist > 0 for x in d if x.cum_pos is None)      # precondition: abstaining rows do carry a distance
    mg = M.margin_distribution(d)
    assert mg["n_rows"] == 8 and mg["n_decisions"] == 4
    assert len(mg["distance_quantiles"]) > 0 and mg["share_distance_above_variance"] is not None


def test_a4_margin_is_null_over_a_fully_abstaining_cell():
    mg = M.margin_distribution(M.decide_rows(_abstaining_name_sensitive_cell(), FixedTau(0.95)))
    assert mg["n_decisions"] == 0 and mg["n_rows"] == 32
    assert mg["share_distance_above_variance"] is None and mg["distance_quantiles"] is None


def test_a4_c_branch_rate_zero_at_tau_half_with_two_levels_is_flagged_forced():
    rows = [_a4_row("T1", f"u{u}", v, [0.6, 0.4], "boolean") for u in range(3) for v in common.T1_VARIANTS]
    c = M.c_branch_rate(M.decide_rows(rows, FixedTau(0.5)), "T1")
    assert c["rate"] == 0.0 and c["forced_by_tau"] is True and c["fitted_taus"] == [0.5]
    assert "arithmetically impossible" in c["forced_reason"]
    mixed = [_a4_row("T1", "a", "original", [0.8, 0.2], "boolean"), _a4_row("T1", "b", "original", [0.5, 0.5], "boolean")]
    assert M.c_branch_rate(M.decide_rows(mixed, FixedTau(0.7)), "T1")["forced_by_tau"] is False   # 0.5 of rows: a measurement


def test_a4_move_rate_is_carried_on_argmax_beside_the_thresholded_one():
    # base decides on level 0 (sharp); the swap's mass moves to level 1 but not enough to clear tau
    rows = [_a4_row("T2", "a", "base", _peak(3, 0, 0.97), "nominal"), _a4_row("T2", "a", "swap_0_1", _peak(3, 1, 0.6), "nominal")]
    m = M.move_rate(M.decide_rows(rows, FixedTau(0.9)))["swap"]
    assert m["followed_rate"] == 0.0 and m["moved_elsewhere_rate"] == 1.0              # thresholded: C
    assert m["argmax_reference"]["followed_rate"] == 1.0                                 # argmax: followed


def test_a4_threshold_fit_reports_collapse_without_changing_the_fit():
    train, held = _split_rows(60)
    for i, r in enumerate(train):
        r["gold"] = "false" if i < 20 else "true"
    fitted = TH.fit_thresholds(S.TrainView.of(train + held, S.GROUP70))
    assert fitted.tau_for(train[0]) == (0.95, "version")                                 # fit itself unchanged
    tau, tier, key = fitted.lookup(train[0])
    diag = fitted.diagnostics(key)
    assert diag["utility_at_chosen_tau"] == 0 and diag["abstain_rate_at_chosen_tau"] == 1.0
    assert diag["best_decisive_tau"] == 0.8 and diag["best_decisive_utility"] == -20
    cell = M.cell_metrics(M.decide_rows(held, fitted), "heldout", fitted)["threshold_fit"]
    assert cell["rows_by_tau"] == {"0.95": 60} and cell["rows_by_tier"] == {"version": 60}
    e = cell["entries"][0]
    assert e["fitted_tau"] == 0.95 and e["best_decisive_utility"] == -20 and e["collapsed"] is True
    assert cell["share_rows_in_collapsed_entries"] == 1.0
    # the cell-level flip carries the collapse: all rows abstain, so the thresholded C-rate is 1.0 and forced
    assert M.cell_metrics(M.decide_rows(held, fitted), "heldout", fitted)["c_branch"]["T1"]["forced_by_tau"] is True


def _a4_dl_report(real_arg, real_thr, empty_arg, empty_thr, fol_arg, fol_thr):
    def flip(arg, thr):
        return {"overall": thr, "argmax_reference": {"overall": arg}, "c_branch": {"rate": 0.0}}

    def move(arg, thr):
        return {"swap": {"followed_rate": thr, "argmax_reference": {"followed_rate": arg}}}
    cell = {"primary": {"flip_T1": flip(real_arg, real_thr), "move_T2": move(fol_arg, fol_thr)},
            "empty_input": {"flip_T1": flip(empty_arg, empty_thr), "move_T2": move(None, None)}}
    return {"splits": {"group70": {"heldout": {"s": {"ordinal": cell}}}}}


def test_a4_b2_and_b3_are_evaluated_on_argmax_columns():
    # B-2: thresholded says pass (0.0 vs 0.5 -> gap 0.5, the degenerate zero), argmax says void (0.62 vs 0.60).
    dl = report_mod.decision_lines(_a4_dl_report(real_arg=0.62, real_thr=0.0, empty_arg=0.60, empty_thr=0.5, fol_arg=0.5, fol_thr=0.5))
    b2 = dl["B-2"][0]
    assert b2["real_flip"] == 0.62 and b2["empty_input_flip"] == 0.60 and b2["pass"] is False and b2["t1_void"] is True
    assert b2["real_flip_thresholded"] == 0.0                                            # beside, not used
    # opposite direction: thresholded would fail/void, argmax passes
    dl = report_mod.decision_lines(_a4_dl_report(real_arg=0.1, real_thr=0.55, empty_arg=0.6, empty_thr=0.6, fol_arg=0.5, fol_thr=0.5))
    assert dl["B-2"][0]["pass"] is True and dl["B-2"][0]["t1_void"] is False
    # B-3: thresholded followed 0.1 / flip 0.0 would fail the 30% clause; argmax followed 0.5 vs flip 0.62 passes 30% but not 10 points over flip
    dl = report_mod.decision_lines(_a4_dl_report(real_arg=0.62, real_thr=0.0, empty_arg=0.9, empty_thr=0.9, fol_arg=0.5, fol_thr=0.1))
    b3 = dl["B-3"][0]
    assert b3["followed_rate"] == 0.5 and b3["above_30_percent"] is True and b3["t1_flip_same_cell"] == 0.62
    assert b3["exceeds_flip_by_10_points"] is False and abs(b3["followed_minus_flip"] - (0.5 - 0.62)) < 1e-12
    dl = report_mod.decision_lines(_a4_dl_report(real_arg=0.2, real_thr=0.9, empty_arg=0.9, empty_thr=0.9, fol_arg=0.5, fol_thr=0.1))
    b3 = dl["B-3"][0]
    assert b3["above_30_percent"] is True and b3["exceeds_flip_by_10_points"] is True     # thresholded columns would say the opposite


def test_a4_report_records_amendment_level_and_cell_fit_summary():
    with _tmp() as tmp:
        data, out = os.path.join(tmp, "data"), os.path.join(tmp, "out")
        _write_fixture_tree(data)
        _run(data, out, "mock-name-driven")
        rep = _report(out)
        assert rep["amendment_level"] == common.AMENDMENT_LEVEL == 4 and rep["header"]["amendment_level"] == 4
        cell = rep["splits"]["group70"]["heldout"]["src-a"]["ordinal"]["primary"]
        assert "argmax_reference" in cell["flip_T1"] and "threshold_fit" in cell and "forced_by_tau" in cell["c_branch"]["T1"]
        md = open(os.path.join(out, "report.md")).read()
        assert "Amendment level of this report: 4" in md and "Threshold fitting per cell" in md


def test_real_data_smoke_if_present():
    if not os.path.exists(REAL_DATA):
        return
    with _tmp() as tmp:
        out = os.path.join(tmp, "out")
        run_baseline.main(["--base", "mock-invariant", "--out-root", out, "--limit-groups", "40", "--chunk", "500"])
        rep = _report(out)
        assert set(rep["splits"]) == {"group70", "question70"}
        for side in rep["splits"]["group70"].values():
            for src, by_type in side.items():
                for ltype, roles in by_type.items():
                    assert roles["primary"]["flip_T1"]["overall"] in (0.0, None)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, exc)
    sys.exit(1 if failed else 0)
