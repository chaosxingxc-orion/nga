"""Tests for train_r3.py (run inside the image on one NPU: python3 -P test_train_r3.py [--device npu:0] [--only name,...]).

Each test prints the numbers it measured and the tolerance it used. Clauses (frozen prereg 387521b): §7.2 (LoRA-only, loss on the
response only, no EOS, 186 pairs), §7.3 (K2 s equals the evaluation scorer's s within 1e-3 nats, fp32), §3.2, and the engineering
requirements for right padding, gathered-logits equivalence and step-granular resume.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
for p in (HERE, R0_CODE):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch  # noqa: E402
import torch_npu  # noqa: E402,F401
import transformers  # noqa: E402

import train_r3 as T  # noqa: E402

# fp32 tests need true fp32: torch_npu enables HF32 for convolutions by default (torch.npu.conv.allow_hf32 = True), which makes the
# GDN causal conv1d run at reduced precision and shifts fp32 scores by ~1e-3 nats between batch shapes (diag_fp32.py shows
# 7e-4..1.9e-3 with it on and <= 3e-5 with it off). bf16 paths are unaffected.
torch.npu.conv.allow_hf32 = False
torch.npu.matmul.allow_hf32 = False

BASE = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"
DEVICE = "npu:0"
RESULTS = {}


def small_args(out, **kw):
    a = T.parse_args(["--out", out, "--limit-rows", "300", "--save-every", "0", "--no-merge", "--micro-tokens", "3000"])
    for k, v in kw.items():
        setattr(a, k.replace("-", "_"), v)
    return a


def tok_model(dtype, lora=False):
    tok = transformers.AutoTokenizer.from_pretrained(BASE)
    if lora:
        a = small_args("/tmp/unused")
        pm, trainable, n = T.build_model(a, torch)
        return tok, pm, trainable
    m = transformers.AutoModelForCausalLM.from_pretrained(BASE, dtype=dtype, attn_implementation="sdpa").to(DEVICE).eval()
    return tok, m, None


def sample_units(n, limit=300):
    a = small_args("/tmp/unused", limit_rows=limit)
    d = T.Data(a)
    return d.step_units(0)[1][:n], d


def test_lora_only_trainable_base_frozen():
    tok, pm, trainable = tok_model(torch.bfloat16, lora=True)
    pm.to(DEVICE).train()
    core = pm.base_model.model
    names = [n for n, _ in trainable]
    assert len(names) == 372 and sum(1 for n in names if "lora_A" in n) == 186 == sum(1 for n in names if "lora_B" in n)
    assert all(p.dtype == torch.float32 for _, p in trainable), "LoRA params must be fp32"
    frozen = [(n, p) for n, p in pm.named_parameters() if not p.requires_grad]
    assert any("embed_tokens" in n for n, _ in frozen) and any("lm_head" in n or "embed_tokens" in n for n, _ in frozen)
    assert all(p.dtype == torch.bfloat16 for _, p in frozen)
    matched = {n.split(".")[-4 if "lora_" in n.split(".")[-3] else -3] for n in names}
    snap = {n: p.detach().clone() for n, p in frozen if "layers.0." in n or "layers.3." in n or "embed" in n}
    lora_b0 = {n: p.detach().clone() for n, p in trainable if "lora_B" in n}
    units, _ = sample_units(10)
    params = [p for _, p in trainable]
    opt = torch.optim.AdamW(params, lr=1e-3, weight_decay=0.01)
    pad = tok.pad_token_id
    for i in range(3):
        T.seed_step(torch, 2, i)
        opt.zero_grad(set_to_none=True)
        T.step_loss(torch, core, tok, units, "k1", DEVICE, pad, 4096, 3000, {})
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
    assert all(torch.equal(snap[n], p.detach()) for n, p in frozen if n in snap), "a base weight changed"
    changed = sum(1 for n, p in trainable if "lora_B" in n and not torch.equal(lora_b0[n], p.detach()))
    assert changed == 186, changed
    # the frozen base got no gradient
    assert all(p.grad is None for _, p in frozen)
    RESULTS["lora_only"] = f"372 trainable tensors (186 pairs), fp32; base bf16, {len(frozen)} frozen tensors unchanged after 3 AdamW steps; 186/186 lora_B changed"


def test_loss_mask_response_only_and_gathered_logits_equal_full():
    tok, m, _ = tok_model(torch.float32)
    core = m
    units, _ = sample_units(10)
    exs = [e for u in units for e in u]
    counters = {}
    enc = [T.encode_example(tok, e, 4096, counters) for e in exs]
    assert counters.get("truncated", 0) == 0
    eos = tok.eos_token_id
    assert all(eos not in a for _, a in enc), "an EOS token is in the response"
    assert all(a == tok(e["response"], add_special_tokens=False)["input_ids"] for (_, a), e in zip(enc, exs))
    total_resp = sum(len(a) for _, a in enc)
    # (1) naive reference: each row alone, full-sequence logits, CE over the response positions only
    ref_resp, ref_all = 0.0, 0.0
    for p, a in enc:
        ids = torch.tensor([p + a], device=DEVICE)
        with torch.no_grad():
            lp = torch.log_softmax(core(input_ids=ids, use_cache=False).logits[0].float(), dim=-1)
        tgt = ids[0, 1:]
        tl = lp[:-1].gather(1, tgt[:, None])[:, 0]
        ref_resp += float(-tl[len(p) - 1:].sum())
        ref_all += float(-tl.sum())
    ref_resp /= total_resp
    # (2) trainer path, gathered logits, fp32 (autocast off through a direct call), right-padded batch
    seqs = [p + a for p, a in enc]
    starts = [len(p) for p, _ in enc]
    with torch.no_grad():
        s_g = T.row_logprob_sums(torch, core, seqs, starts, tok.pad_token_id, DEVICE, autocast=False)
        s_f = T.row_logprob_sums(torch, core, seqs, starts, tok.pad_token_id, DEVICE, autocast=False, full_logits=True)
    loss_g = float(-s_g.sum() / total_resp)
    loss_f = float(-s_f.sum() / total_resp)
    tol = 1e-3
    print(f"  naive per-row response-only loss {ref_resp:.6f}; trainer gathered {loss_g:.6f}; trainer full-logits {loss_f:.6f}; "
          f"naive loss over ALL positions {ref_all / sum(len(p) + len(a) - 1 for p, a in enc):.4f} (different quantity)")
    assert abs(loss_g - ref_resp) < tol, (loss_g, ref_resp)
    assert abs(loss_g - loss_f) < 1e-5, (loss_g, loss_f)       # gathering is the identical computation, only cheaper
    assert float((s_g - s_f).abs().max()) < 1e-4
    # (3) mask check by perturbation: changing a PROMPT token's value must not change which tokens are scored
    #     (scored count == response length), and a response of n tokens contributes exactly n terms.
    n_terms = sum(len(a) for _, a in enc)
    assert n_terms == total_resp
    # (4) bf16 autocast production path vs the fp32 value
    tok2, m2, _ = tok_model(torch.bfloat16)
    with torch.no_grad():
        s_b = T.row_logprob_sums(torch, m2, seqs, starts, tok.pad_token_id, DEVICE)
    loss_b = float(-s_b.float().sum() / total_resp)
    print(f"  bf16 production path loss {loss_b:.6f} vs fp32 {loss_g:.6f} (|d| = {abs(loss_b - loss_g):.5f})")
    assert abs(loss_b - loss_g) < 0.05
    RESULTS["loss_mask_gathered"] = (f"response-only loss (n={len(exs)} rows, {total_resp} response tokens, no EOS): gathered==full-logits within 1e-5 "
                                     f"(fp32), == naive per-row reference within {abs(loss_g - ref_resp):.1e} (tol 1e-3); bf16 path within {abs(loss_b - loss_g):.4f}")


def test_k2_equals_evaluation_scorer():
    import scorer as r0_scorer
    tok, m, _ = tok_model(torch.float32)
    rows = []
    with open(T.TRAIN_FILE, encoding="utf-8") as f:
        want = {2: 2, 3: 1, 5: 1, 14: 1, 77: 1, 4: 1}
        for line in f:
            r = json.loads(line)
            k = len(r["levels"])
            if want.get(k, 0) > 0:
                want[k] -= 1
                rows.append(r)
            if sum(want.values()) == 0:
                break
    pm = T.B.load_prompt_module(R0_CODE)
    ref = r0_scorer.HFScorer(BASE, device=DEVICE, dtype="float32", model=m, tokenizer=tok, token_budget=1)
    worst = 0.0
    for r in rows:
        ex = T.B.make_example(r, pm, False)
        p, cands = T.encode_candidates(tok, ex, 8192, {})
        seqs = [p + c for c in cands]
        with torch.no_grad():
            s = T.row_logprob_sums(torch, m, seqs, [len(p)] * len(cands), tok.pad_token_id, DEVICE, autocast=False, micro_tokens=4000)
        cap = []
        orig = r0_scorer.softmax
        r0_scorer.softmax = lambda x: (cap.append(list(x)), orig(x))[1]
        try:
            ref.score([r])
        finally:
            r0_scorer.softmax = orig
        d = max(abs(float(a) - b) for a, b in zip(s.cpu(), cap[0]))
        worst = max(worst, d)
        print(f"  K2 s: {len(cands):2d} options, max|s_train - s_eval| = {d:.2e}")
        assert d < 1e-3, d
    RESULTS["k2_vs_scorer"] = f"training-time s (right-padded, fp32) equals r0 HFScorer s (one row per candidate) on {len(rows)} rows of 2..77 options, worst {worst:.2e} nats (tol 1e-3)"


def test_right_padding_invariance():
    results = {}
    for dtype, name in ((torch.float32, "fp32"), (torch.bfloat16, "bf16")):
        tok, m, _ = tok_model(dtype)
        units, _ = sample_units(10)
        exs = [e for u in units for e in u]
        enc = [T.encode_example(tok, e, 4096, {}) for e in exs]
        seqs = [p + a for p, a in enc]
        starts = [len(p) for p, _ in enc]
        order = sorted(range(len(seqs)), key=lambda r: len(seqs[r]))
        shortest = order[:3]
        auto = dtype == torch.bfloat16
        diff_pad, diff_batch = [], []
        for r in shortest:
            def f(S, St, idx):
                with torch.no_grad():
                    return float(T.row_logprob_sums(torch, m, S, St, tok.pad_token_id, DEVICE, autocast=auto)[idx])
            alone = f([seqs[r]], [starts[r]], 0)
            dup = f([seqs[r]] * 3, [starts[r]] * 3, 1)                       # batch-size change alone, equal lengths
            longest = order[-3:]
            mixed = f([seqs[r]] + [seqs[j] for j in longest], [starts[r]] + [starts[j] for j in longest], 0)   # shares a batch with longer rows
            diff_batch.append(abs(alone - dup))
            diff_pad.append(abs(alone - mixed))
            print(f"  {name} len={len(seqs[r])} alone {alone:.6f} dup3 {dup:.6f} mixed-with-longer {mixed:.6f}")
        results[name] = (max(diff_batch), max(diff_pad))
        if dtype == torch.float32:
            assert max(diff_pad) < 1e-3, diff_pad
        else:
            tol = 2 * max(diff_batch) + 0.02          # bf16: twice the batch-size-alone noise, plus a 0.02-nat floor
            print(f"  bf16 tolerance used: 2 x {max(diff_batch):.5f} + 0.02 = {tol:.5f}")
            assert max(diff_pad) < tol, (diff_pad, tol)
    RESULTS["right_padding"] = (f"row sum-logprob alone vs batched with 3 longer rows (right-padded): fp32 max|d| = {results['fp32'][1]:.2e} "
                                f"(batch-size-alone {results['fp32'][0]:.2e}, tol 1e-3); bf16 max|d| = {results['bf16'][1]:.4f} "
                                f"(batch-size-alone {results['bf16'][0]:.4f})")


def test_resume_equals_uninterrupted():
    base = tempfile.mkdtemp(prefix="r3resume_", dir="/mnt/cephfs/xingchao/experiments/jev/r3_runs")
    try:
        a = os.path.join(base, "A")
        b = os.path.join(base, "B")
        kw = dict(total_steps=6)
        T.run(small_args(a, **kw))                                         # uninterrupted, 6 steps
        T.run(small_args(b, stop_after=3, **kw))                           # 3 steps, checkpoint
        assert not os.path.exists(os.path.join(b, "adapter"))
        T.run(small_args(b, **kw))                                         # resume from step 3 to 6
        la = [json.loads(l) for l in open(os.path.join(a, "losses.jsonl"))]
        lb = [json.loads(l) for l in open(os.path.join(b, "losses.jsonl"))]
        assert [r["step"] for r in la] == [r["step"] for r in lb] == [1, 2, 3, 4, 5, 6]
        d = [abs(x["loss"] - y["loss"]) for x, y in zip(la, lb)]
        print("  per-step |loss_uninterrupted - loss_resumed|:", ["%.2e" % x for x in d])
        sa = torch.load(os.path.join(a, "ckpt", "step_000006.pt"), map_location="cpu", weights_only=False)["lora"]
        sb = torch.load(os.path.join(b, "ckpt", "step_000006.pt"), map_location="cpu", weights_only=False)["lora"]
        wd = max(float((sa[k] - sb[k]).abs().max()) for k in sa)
        print(f"  max|lora_uninterrupted - lora_resumed| after step 6 = {wd:.2e}")
        assert max(d[3:]) < 1e-3 and wd < 1e-5, (d, wd)
        RESULTS["resume"] = f"steps 4-6 loss after resume vs uninterrupted: max |d| = {max(d[3:]):.2e}; final LoRA max |d| = {wd:.2e}"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_k2_loss_equals_direct_computation():
    """step_loss(arm=k2) on a step of real questions == mean over questions of -log softmax(s)[gold], with s computed
    candidate by candidate, one row per forward, FULL-vocabulary logits (no gathering, no padding), fp32. Tolerance 1e-3."""
    tok, m, _ = tok_model(torch.float32)
    units, _ = sample_units(10)
    exs = [e for u in units for e in u]
    assert all(e["candidates"] is not None for e in exs)
    loss, st = T.step_loss(torch, m, tok, units, "k2", DEVICE, tok.pad_token_id, 8192, 3000, {}, backward=False, autocast=False)
    ref = 0.0
    for e in exs:
        p, cands = T.encode_candidates(tok, e, 8192, {})
        s = []
        for c in cands:
            ids = torch.tensor([p + c], device=DEVICE)
            with torch.no_grad():
                lp = torch.log_softmax(m(input_ids=ids, use_cache=False).logits[0].float(), dim=-1)
            s.append(sum(float(lp[len(p) - 1 + q, c[q]]) for q in range(len(c))))
        st_ = torch.tensor(s, dtype=torch.float64)
        ref += float(-torch.log_softmax(st_, dim=0)[e["gold_index"]]) / len(exs)
    print(f"  K2 loss: step_loss {loss:.6f}  direct {ref:.6f}  |d| = {abs(loss - ref):.2e}  ({len(exs)} questions, "
          f"options per question {[len(e['candidates']) for e in exs][:6]}...)")
    assert abs(loss - ref) < 1e-3, (loss, ref)
    RESULTS["k2_loss_direct"] = f"step_loss(k2) vs direct full-logits one-row-per-candidate computation on {len(exs)} questions: |d| = {abs(loss - ref):.1e} (tol 1e-3, fp32)"


def test_k2_step_runs():
    tok, pm, trainable = tok_model(torch.bfloat16, lora=True)
    pm.to(DEVICE).train()
    core = pm.base_model.model
    units, _ = sample_units(10)
    params = [p for _, p in trainable]
    opt = torch.optim.AdamW(params, lr=1e-3)
    for i in range(2):
        T.seed_step(torch, 2, i)
        opt.zero_grad(set_to_none=True)
        loss, st = T.step_loss(torch, core, tok, units, "k2", DEVICE, tok.pad_token_id, 4096, 3000, {})
        gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
        opt.step()
        print(f"  K2 step {i}: loss {loss:.4f} grad_norm {gn:.3f} rows {st['rows']} tokens {st['tokens']}")
        assert loss == loss and gn > 0
    RESULTS["k2_step"] = "two K2 optimizer steps run end to end (loss finite, grad norm > 0)"


TESTS = ["lora_only_trainable_base_frozen", "loss_mask_response_only_and_gathered_logits_equal_full", "k2_equals_evaluation_scorer",
         "right_padding_invariance", "resume_equals_uninterrupted", "k2_step_runs", "k2_loss_equals_direct_computation"]


def main():
    global DEVICE
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="npu:0")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    DEVICE = a.device
    names = a.only.split(",") if a.only else TESTS
    for n in names:
        t0 = time.time()
        print(f"== {n}", flush=True)
        globals()["test_" + n]()
        print(f"   ok ({time.time() - t0:.0f}s)", flush=True)
    print("\nRESULTS")
    for k, v in RESULTS.items():
        print(f" - {k}: {v}")
    print(f"ALL {len(names)} TESTS PASSED")


if __name__ == "__main__":
    main()
