"""Finite scalar admission for the frozen fast_ref engineering contract."""
import math


def finite(values):
    if not all(math.isfinite(float(x)) for x in values):
        raise ValueError('nonfinite numerical contract quantity')


def judge(losses, distances):
    if len(losses) != 5 or len(distances) != 4:
        raise ValueError('expected five losses and four distances')
    finite([*losses, *distances])
    r, f, r2, r3, gold = losses
    delta, floor, fast_gold, ref_gold = distances
    if any(x < 0 for x in distances):
        raise ValueError('negative distance')
    loss_delta = abs(f-r)
    loss_floor = max(abs(r2-r), abs(r3-r), 1e-3)
    gold_limit = 1.2*ref_gold
    finite([loss_delta, loss_floor, gold_limit])
    if delta > floor or fast_gold > gold_limit or loss_delta > loss_floor:
        raise ValueError('numerical contract exceeded')
    return {'gradient_delta': delta, 'gradient_floor': floor,
            'loss_delta': loss_delta, 'loss_floor': loss_floor,
            'gradient_floor_ratio': delta/floor if floor else None}
