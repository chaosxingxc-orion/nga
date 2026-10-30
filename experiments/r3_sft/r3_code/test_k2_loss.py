"""K2 loss correctness test (R3-SFT-PREREG §7.3): an independent, from-scratch computation of the
option-restricted loss, checked against the proven r0_code/scorer.py HFScorer (same tokenization,
same "separate row per candidate" layout, R0's own primary-evidence scorer) on real decision-v7
train rows. Runs inside the training image (needs torch/torch_npu/transformers).

    python3 -P test_k2_loss.py [--device npu] [--n 15] [--model-path ...]

Exit code 0 and "ALL K2 LOSS CHECKS PASSED" iff every row's raw per-option score matches the
reference to within 1e-3 nats (absolute, not just up to the softmax's free constant: both methods
compute literally the same prefix log-probability sum, so there is no indeterminacy to allow for)
and the derived -log softmax(s)_gold loss matches to the same tolerance.
"""
import argparse
import json
import sys

HERE = "/mnt/cephfs/xingchao/experiments/jev/r3_code"
R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
TRAIN = "/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl"
for p in (HERE, R0_CODE):
    if p not in sys.path:
        sys.path.insert(0, p)

import k2_loss  # noqa: E402
import prompt as prompt_mod  # noqa: E402
import scorer as r0_scorer  # noqa: E402


def pick_rows(n):
    """n rows spanning a range of option counts (2 .. 14), by scanning decision-v7 train in order."""
    seen_k, out = set(), []
    with open(TRAIN, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k = len(r["levels"])
            if k not in seen_k or len(out) < n:
                out.append(r)
                seen_k.add(k)
            if len(out) >= n and len(seen_k) >= 4:
                break
    return out[:n]


def method_a(model, tok, device, row):
    """Independent from-scratch computation: one forward pass per candidate ("separate rows",
    explicitly allowed by the task brief as the correctness-first option), own tokenization and
    own position bookkeeping via k2_loss.option_scores, no code shared with r0_code/scorer.py."""
    import torch
    p = prompt_mod.build_prompt(row, render="record_name")
    prefix = tok(p.text, add_special_tokens=False)["input_ids"]
    cand_ids = [tok(c, add_special_tokens=False)["input_ids"] for c in p.candidates]
    scores = []
    for c in cand_ids:
        ids = torch.tensor([prefix + c], dtype=torch.long, device=device)
        with torch.no_grad():
            logits = model(input_ids=ids, use_cache=False).logits[0].float()
        logp = torch.log_softmax(logits, dim=-1)
        rows = [logp[t].tolist() for t in range(len(prefix) - 1, len(prefix) - 1 + len(c))]
        scores.append(k2_loss.option_scores(rows, 1, [c])[0])
    gold_idx = [l["id"] for l in row["levels"]].index(row["gold"])
    return scores, gold_idx


def method_b_reference(scorer_obj, row):
    """The proven reference: r0_code/scorer.py HFScorer, same tokenization and row layout, with its
    softmax() call intercepted so the pre-softmax raw scores are visible (same trick as
    r1_code/check_scorer.py's load_r0: capture the argument of the module's own softmax).

    IMPORTANT, found while writing this test (diag_padding.py has the full repro): HFScorer's
    default token_budget (16384) lets candidates of DIFFERENT token lengths share one left-padded
    forward pass, and that batching measurably changes the raw score (seen directly: 0.157 nats on
    a real decision-v7 row, 'yelp/train/388287', 5 candidates of lengths [6,5,5,5,5] -- the exact
    same number this test's tolerance check first failed on, before this fix). `token_budget=1`
    forces one row per forward call (no cross-candidate padding), which is what this test's
    from-scratch `method_a` also does; scored that way, the two independent implementations agree
    to float precision, not just within 1e-3. This is reported as an open finding about the shared
    evaluation scorer's batching (affects Track K/Track T whenever a question's candidates differ
    in token length and the normal 16384 token budget is used), separate from K2's own loss.
    """
    scorer_obj = r0_scorer.HFScorer(scorer_obj.model_path, device=scorer_obj.device, dtype=scorer_obj.dtype,
                                     model=scorer_obj._model, tokenizer=scorer_obj._tok, token_budget=1)
    cap = []
    orig = r0_scorer.softmax
    r0_scorer.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
    try:
        scorer_obj.score([row])
    finally:
        r0_scorer.softmax = orig
    scores = cap[0]
    gold_idx = [l["id"] for l in row["levels"]].index(row["gold"])
    return scores, gold_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="npu")
    ap.add_argument("--model-path", default="/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--tol", type=float, default=1e-3)
    a = ap.parse_args()

    import torch
    if a.device.startswith("npu"):
        import torch_npu  # noqa: F401
    import transformers
    tok = transformers.AutoTokenizer.from_pretrained(a.model_path)
    model = transformers.AutoModelForCausalLM.from_pretrained(a.model_path, dtype=torch.bfloat16)
    model = model.to(a.device).eval()

    ref = r0_scorer.HFScorer(a.model_path, device=a.device, dtype="bfloat16", model=model, tokenizer=tok)

    rows = pick_rows(a.n)
    worst_score_diff, worst_loss_diff = 0.0, 0.0
    for row in rows:
        s_a, g_a = method_a(model, tok, a.device, row)
        s_b, g_b = method_b_reference(ref, row)
        assert g_a == g_b
        assert len(s_a) == len(s_b)
        diffs = [abs(x - y) for x, y in zip(s_a, s_b)]
        worst_score_diff = max(worst_score_diff, max(diffs))
        loss_a = k2_loss.k2_loss_from_scores(s_a, g_a)
        loss_b = k2_loss.k2_loss_from_scores(s_b, g_b)
        d_loss = abs(loss_a - loss_b)
        worst_loss_diff = max(worst_loss_diff, d_loss)
        print(f"n_opts={len(s_a):2d} gold={g_a:2d} max|ds_i|={max(diffs):.6f} loss_a={loss_a:.6f} "
              f"loss_b={loss_b:.6f} |dloss|={d_loss:.6f}", flush=True)
        assert max(diffs) < a.tol, (row["kev"]["id"], diffs)
        assert d_loss < a.tol, (row["kev"]["id"], d_loss)
    print(f"worst max|ds_i|={worst_score_diff:.6f}  worst |dloss|={worst_loss_diff:.6f}  tol={a.tol}")
    print(f"ALL K2 LOSS CHECKS PASSED ({len(rows)} rows)")


if __name__ == "__main__":
    main()
