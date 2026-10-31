"""Model-level check of --gdn-impl fast_ref: LoRA gradients and loss of the real K1 step on real decision-v7 rows.

    python3 -P test_gdn_e2e.py [--device npu:0]

Five runs on one fixed step (10 base questions + siblings), dropout off, random non-zero LoRA B so every LoRA tensor has a gradient:
  R   reference kernel, bf16 autocast, micro-batch 3000            (bounded engineering configuration)
  F   gdn_fast_ref,     bf16 autocast, micro-batch 3000            (same batches as R)
  R2  reference kernel, bf16 autocast, one row per chunk            (same function, different batch composition: the same-config noise floor)
  R3  reference kernel, bf16 autocast, fewest chunks               (a second batch composition; the floor is the larger of d(R2,R), d(R3,R))
  G   reference kernel, whole model fp32, no autocast               (gold)
Pass criteria, fixed before the run: d(F,R) <= max(d(R2,R), d(R3,R)) (the fast kernel moves the gradient no more than re-batching does),
e(F,G) <= 1.2 e(R,G) (no worse than the reference against the fp32 gold; the b' rule of prereg 14.1 at the whole-gradient level), and |loss_F - loss_R| <= max(|loss_R2 - loss_R|, |loss_R3 - loss_R|, 1e-3) (the loss moves no more than re-batching moves it).
d / e are relative L2 of the stacked LoRA gradient; per-tensor values are reported too.
"""
import argparse
import sys

import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import torch  # noqa: E402
import torch_npu  # noqa: E402,F401
from transformers.models.qwen3_5 import modeling_qwen3_5 as M  # noqa: E402

import gdn_fast_ref as G  # noqa: E402
import test_train_r3 as TT  # noqa: E402
import train_r3 as T  # noqa: E402
from r3_fastref_numerics import finite, judge


def set_impl(model, impl):
    for m in model.modules():
        if type(m).__name__ == "Qwen3_5GatedDeltaNet":
            m.chunk_gated_delta_rule = G.fast_chunk_gated_delta_rule if impl == "fast" else M.torch_chunk_gated_delta_rule


def rel(a, b):
    return float((a - b).norm() / (b.norm() + 1e-30))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="npu:0")
    TT.DEVICE = ap.parse_args().device
    a = TT.small_args("/tmp/unused", lora_dropout=0.0)
    tok = __import__("transformers").AutoTokenizer.from_pretrained(TT.BASE)
    pm, trainable, _ = T.build_model(a, torch)
    pm.to(TT.DEVICE).train()
    core = pm.base_model.model
    g = torch.Generator().manual_seed(11)
    with torch.no_grad():
        for n, p in trainable:
            if "lora_B" in n:
                p.copy_((torch.randn(p.shape, generator=g) * 0.02).to(p.device))
    units, _ = TT.sample_units(10, limit=300)

    def grads(impl, micro, ac=True, co=4000):
        set_impl(core, impl)
        for _, p in trainable:
            p.grad = None
        loss, st = T.step_loss(torch, core, tok, units, "k1", TT.DEVICE, tok.pad_token_id, 4096, micro, {}, autocast=ac, chunk_overhead=co)
        return loss, {n: p.grad.detach().float().clone() for n, p in trainable}, st

    lR, gR, stR = grads("ref", 3000)
    lF, gF, _ = grads("fast", 3000)
    lR2, gR2, stR2 = grads("ref", 1200, co=0)          # one row per chunk: a different batch composition of the same function
    lR3, gR3, stR3 = grads("ref", 3000, co=10 ** 9)    # everything in as few chunks as the budget allows
    print(f"  chunks: R/F {stR['chunks']} (padded {stR['padded_tokens']}), R2 {stR2['chunks']} (padded {stR2['padded_tokens']}), "
          f"R3 {stR3['chunks']} (padded {stR3['padded_tokens']}); rows {stR['rows']}")
    pm.float()                                   # gold: base weights bf16 -> fp32 are exact, LoRA already fp32
    lG, gG, _ = grads("ref", 3000, ac=False)
    names = list(gR)
    flat = lambda d: torch.cat([d[n].flatten().double() for n in names])
    R, F, R2, R3, Gd = flat(gR), flat(gF), flat(gR2), flat(gR3), flat(gG)
    if not all(torch.isfinite(x).all() for x in (R, F, R2, R3, Gd)):
        raise ValueError('nonfinite gradient tensor')
    finite((lR, lF, lR2, lR3, lG))
    rebatch = (rel(R2, R), rel(R3, R))
    finite(rebatch)
    d_FR, d_R2R, e_FG, e_RG = rel(F, R), max(rebatch), rel(F, Gd), rel(R, Gd)
    per = lambda x, y: sorted(rel(x[n].double(), y[n].double()) for n in names)
    pFR, pR2R = per(gF, gR), per(gR2, gR)
    pR3R = per(gR3, gR)
    med = lambda v: v[len(v) // 2]
    p95 = lambda v: v[int(0.95 * (len(v) - 1))]
    print(f"  losses: R {lR:.6f}  F {lF:.6f}  R2 {lR2:.6f}  G(fp32) {lG:.6f};  |F-R| {abs(lF - lR):.2e}  |R2-R| {abs(lR2 - lR):.2e}  |R-G| {abs(lR - lG):.2e}")
    print(f"  stacked LoRA gradient (372 tensors): d(F,R) {d_FR:.2e}   floor {d_R2R:.2e}   e(F,G) {e_FG:.2e}   e(R,G) {e_RG:.2e}")
    print(f"  per tensor d(F,R): median {med(pFR):.1e} p95 {p95(pFR):.1e} max {pFR[-1]:.1e};  floor d(R2,R): median {med(pR2R):.1e} p95 {p95(pR2R):.1e} max {pR2R[-1]:.1e}; d(R3,R): median {med(pR3R):.1e}")
    finite(pFR + pR2R + pR3R)
    verdict = judge((lR, lF, lR2, lR3, lG), (d_FR, d_R2R, e_FG, e_RG))
    print("MODEL-LEVEL CHECK PASSED:", verdict,
          "; dropout=0, chunk_overhead=4000; not training trajectory equivalence")



if __name__ == "__main__":
    main()
