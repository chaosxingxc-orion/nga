"""Descriptive T=1 arithmetic only; no file reads, selection or test admission.

Specification: experiments/R3-REFERENCE-METRICS-SUPPLEMENT-2026-11-01.md.
The caller must independently verify population and source provenance.
"""
import math
from fractions import Fraction

SPECIFICATION_SHA256 = 'd400164a5dd2a75e62150eb46d02c7aeaeb164b011a82912f025949b82f99fed'
EDGES = tuple(i * .1 for i in range(10)) + (1.,)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def ece10(correct, confidence):
    require(isinstance(correct, (list, tuple)) and isinstance(confidence, (list, tuple))
            and len(correct) == len(confidence) and len(correct) > 0, 'invalid ECE population')
    require(all(type(c) is int and c in (0, 1) for c in correct), 'invalid correctness')
    require(all(finite(c) and 0 <= c <= 1 for c in confidence), 'invalid confidence')
    bins = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        indices = [i for i, c in enumerate(confidence) if lo <= c and (c < hi or hi == 1 and c <= hi)]
        n = len(indices)
        bins.append({'lower': lo, 'upper': hi, 'n': n,
                     'mean_confidence': math.fsum(confidence[i] for i in indices) / n if n else None,
                     'accuracy': sum(correct[i] for i in indices) / n if n else None,
                     'contribution': abs(math.fsum(correct[i] - confidence[i] for i in indices)) / len(correct)})
    require(sum(b['n'] for b in bins) == len(correct), 'ECE coverage differs')
    return math.fsum(b['contribution'] for b in bins), bins


def summarize(scores, gold):
    require(isinstance(scores, (list, tuple)) and isinstance(gold, (list, tuple))
            and len(scores) == len(gold) and len(scores) > 0, 'invalid population')
    correct, confidence, briers, losses = [], [], [], []
    ties = mismatches = 0
    for row, y in zip(scores, gold):
        require(isinstance(row, (list, tuple)) and len(row) > 0
                and all(finite(x) for x in row), 'invalid score row')
        require(type(y) is int and 0 <= y < len(row), 'invalid gold')
        values = [float(x) for x in row]
        high = max(values)
        shifted = [x - high for x in values]
        # A very negative difference may underflow to -inf; exp(-inf)=0 is
        # correct. An unrepresentable gold loss is explicitly refused below.
        exponentials = [math.exp(x) for x in shifted]
        total = math.fsum(exponentials)
        probabilities = [x / total for x in exponentials]
        prediction = max(range(len(values)), key=values.__getitem__)
        probability_prediction = max(range(len(values)), key=probabilities.__getitem__)
        loss = math.log(total) + (high - values[y])
        require(math.isfinite(loss) and loss >= 0, 'nonfinite or negative NLL')
        correct.append(int(prediction == y)); confidence.append(max(probabilities))
        ties += int(sum(x == high for x in values) > 1)
        mismatches += int(prediction != probability_prediction)
        briers.append(math.fsum((p - int(i == y)) ** 2 for i, p in enumerate(probabilities)))
        losses.append(loss)
    n = len(scores)
    # Fast path; division rounding can still overflow at binary64's maximum.
    # Exact rational fallback preserves any representable finite mean.
    try:
        nll = math.fsum(x / n for x in losses)
    except OverflowError:
        nll = float(sum((Fraction.from_float(x) for x in losses), Fraction()) / n)
    require(math.isfinite(nll), 'unrepresentable mean NLL')
    ece, bins = ece10(correct, confidence)
    return {'schema': 'r3-reference-probability-metrics-v1', 'n': n, 'temperature': 1,
            'accuracy': sum(correct) / n, 'tie_count': ties,
            'probability_argmax_mismatch_count': mismatches,
            'brier_sum': math.fsum(briers) / n, 'ece10': ece, 'ece10_bins': bins, 'nll': nll,
            'specification_sha256': SPECIFICATION_SHA256,
            'scientific_acceptance': False, 'publication_authorized': False,
            'scope': 'arithmetic only; population, source identity and admission not established'}
