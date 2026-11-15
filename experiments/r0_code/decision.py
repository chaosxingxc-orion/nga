"""Decision operators over a level distribution (pre-registration section 1, "Decision operator").

``cumulative_decision`` is the harness operator (P3'').  ``argmax_index`` exists only as the
reference column and is never used to decide anything else.  There is no expectation operator.

Cumulative-mass operator, as implemented (AMBIGUITY A1: the pre-registration names the operator
but does not give the exact level-valued form, so this is the reading used):

* boolean / nominal (no scale to accumulate along): rank the levels by mass.  The top level is the
  decision when its mass clears tau, otherwise the residual goes to C.  For two levels this is
  "the side with mass >= tau wins, else C".
* ordinal: accumulate along the declared list order, cum[j] = mass of the first j+1 levels.
  lo = first j with cum[j] >  1 - tau   (the low tail of mass 1 - tau is excluded)
  hi = first j with cum[j] >= tau       (the high tail of mass 1 - tau is excluded)
  If lo == hi that level is the decision, otherwise the residual goes to C (returned as None).
  A level is thus decided only when at most 1 - tau of the mass lies on each side of it, so a
  bimodal distribution goes to C instead of being collapsed into the middle level.

Note: the ordinal rule is not permutation-equivariant.  Exchanging two adjacent definitions moves
the mass but can leave the decided level where it was when the distribution is not peaked, so a
perfect definition-following model can still show "unmoved" on ordinal T2 items.

tau must lie in [0.5, 1].  The distance returned with a decision is the smallest amount by which
the cumulative-mass quantity that decided it would have to move to change the decision (the
margin used by metrics.margin_distribution).
"""
import math

EPS = 1e-12


def cumulative_order(probs, level_type):
    k = len(probs)
    if level_type == "ordinal":
        return list(range(k))
    return sorted(range(k), key=lambda i: (-probs[i], i))


def _cum(probs, order):
    out, acc = [], []
    for i in order:
        acc.append(probs[i])
        out.append(math.fsum(acc))
    return out


def cumulative_decision(probs, level_type, tau):
    """Return (list position or None for C, distance to tau)."""
    if not 0.5 <= tau <= 1.0:
        raise ValueError(f"tau must lie in [0.5, 1], got {tau}")
    order = cumulative_order(probs, level_type)
    cum = _cum(probs, order)
    if level_type != "ordinal":
        decided = cum[0] >= tau - EPS and cum[0] > (1.0 - tau) + EPS
        return (order[0] if decided else None), abs(cum[0] - tau)
    lo = next(j for j, c in enumerate(cum) if c > (1.0 - tau) + EPS or j == len(cum) - 1)
    hi = next(j for j, c in enumerate(cum) if c >= tau - EPS or j == len(cum) - 1)
    cuts = cum[:-1]  # the last cut (cum == 1) never moves
    distance = min(min(abs(c - tau), abs(c - (1.0 - tau))) for c in cuts)
    return (order[lo] if lo == hi else None), distance


def argmax_index(probs):
    """Reference only. Ties go to the lowest list position."""
    best = 0
    for i, p in enumerate(probs):
        if p > probs[best]:
            best = i
    return best
