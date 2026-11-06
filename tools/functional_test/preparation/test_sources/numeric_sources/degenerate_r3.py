"""Track K degenerate arms that need no model (R3-SFT-PREREG sec 5.1, 5.4) and their tier bookkeeping.

question_only (sec 5.2) and empty_input (sec 5.3) are the scored model itself with input_mode 'drop' / 'blank'; they
are produced by the driver through the same `score_fn` and are not implemented here.
"""
from collections import Counter, defaultdict

import core_r3 as C


def fit_constant(train_rows):
    """sec 5.1: the majority gold level per (source, qname) on decision-v7 train. When that key is absent (all of
    transfer-v4; `contrastive` in decision-v7 test) the fallback is the majority gold POSITION per (level_type, number of
    options) on decision-v7 train, and after that position 0. Ties between equally frequent candidates go to the smaller
    key so the result does not depend on file order. Returns score(row) -> (one-hot raw scores, tier)."""
    by_q = defaultdict(Counter)
    by_pos = defaultdict(Counter)
    for r in train_rows:
        by_q[(r["source"], r["qname"])][r["gold"]] += 1
        by_pos[(r["level_type"], len(r["levels"]))][C.gold_index(r)] += 1
    maj_q = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_q.items()}
    maj_pos = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_pos.items()}

    def score_one(row):
        ids = C.level_ids(row)
        kq = (row["source"], row["qname"])
        if kq in maj_q and maj_q[kq] in ids:
            idx, tier = ids.index(maj_q[kq]), "question"
        else:
            kp = (row["level_type"], len(ids))
            idx = maj_pos.get(kp, 0)
            idx = idx if idx < len(ids) else 0
            tier = "position" if kp in maj_pos else "position0"
        s = [0.0] * len(ids)
        s[idx] = 1.0
        return s, tier
    score_one.n_keys = (len(maj_q), len(maj_pos))
    return score_one


def score_constant(fit, rows):
    """-> (scores, tier usage Counter as a plain dict)."""
    out, tiers = [], Counter()
    for r in rows:
        s, t = fit(r)
        out.append(s)
        tiers[t] += 1
    return out, dict(tiers)


def score_uniform(rows):
    """sec 5.4: equal mass on every option. Under the sec 4.2 rule every row is a tie and picks position 0, so the Kev-rule
    headline equals the share of gold at position 0; under the R0 convention it scores 0. Both are reported."""
    return [[1.0 / len(r["levels"])] * len(r["levels"]) for r in rows]
