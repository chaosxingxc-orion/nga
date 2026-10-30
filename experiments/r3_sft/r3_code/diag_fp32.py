"""Where does the ~1e-3 fp32 discrepancy between batched right-padded scoring and the one-row-at-a-time scorer come from?
Compares, for a few real rows, s computed (a) one row per forward without padding (what HFScorer token_budget=1 does),
(b) the same twice (run-to-run determinism), (c) right-padded batch of the question's candidates, (d) the same batch with the
TF32/HF32 flags forced off, and (e) a bs=2 batch of two IDENTICAL-length rows (batch-size change without padding).
"""
import json
import sys

HERE = "/mnt/cephfs/xingchao/experiments/jev/r3_code"
for p in (HERE, "/mnt/cephfs/xingchao/experiments/jev/r0_code"):
    sys.path.insert(0, p)
import torch
import torch_npu  # noqa: F401
import transformers
import train_r3 as T

BASE = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"
import os
if os.environ.get("NO_HF32")=="1":
    torch.npu.conv.allow_hf32 = False
    torch.npu.matmul.allow_hf32 = False
print("allow_hf32 matmul:", getattr(torch.npu.matmul, "allow_hf32", "n/a"), "conv:", getattr(torch.npu.conv, "allow_hf32", "n/a"), flush=True)
tok = transformers.AutoTokenizer.from_pretrained(BASE)
m = transformers.AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float32, attn_implementation="sdpa").to("npu:0").eval()
pm = T.B.load_prompt_module("/mnt/cephfs/xingchao/experiments/jev/r0_code")
rows = []
with open(T.TRAIN_FILE) as f:
    want = {2: 1, 3: 1, 5: 1}
    for line in f:
        r = json.loads(line)
        k = len(r["levels"])
        if want.get(k, 0) > 0:
            want[k] -= 1
            rows.append(r)
        if sum(want.values()) == 0:
            break


def S(seqs, starts, **kw):
    with torch.no_grad():
        return [float(x) for x in T.row_logprob_sums(torch, m, seqs, starts, tok.pad_token_id, "npu:0", autocast=False, **kw)]


for r in rows:
    ex = T.B.make_example(r, pm, False)
    p, cands = T.encode_candidates(tok, ex, 8192, {})
    seqs = [p + c for c in cands]
    st = [len(p)] * len(cands)
    one = [S([s], [len(p)])[0] for s in seqs]
    one2 = [S([s], [len(p)])[0] for s in seqs]
    batch = S(seqs, st)
    print(f"-- {len(cands)} options, prompt {len(p)} tokens, cand lens {[len(c) for c in cands]}")
    print("   one-row run-to-run max|d|     :", max(abs(a - b) for a, b in zip(one, one2)))
    print("   batched(right-pad) vs one-row  :", max(abs(a - b) for a, b in zip(one, batch)))
    # same-length pair: duplicate the first sequence twice (no padding), batch size 2 vs 1
    dup = S([seqs[0], seqs[0]], [len(p)] * 2)
    print("   bs=2 identical rows vs bs=1    :", abs(dup[0] - one[0]), abs(dup[1] - one[0]))
    # what r0 HFScorer does: all-ones attention_mask, bs=1 (differs from mine only in passing the mask)
    ids = torch.tensor([seqs[0]], device="npu:0")
    with torch.no_grad():
        lg = m(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False).logits[0].float()
        lp = torch.log_softmax(lg, -1)
    c0 = cands[0]
    ref0 = sum(float(lp[len(p) - 1 + q, c0[q]]) for q in range(len(c0)))
    print("   my one-row vs HFScorer-style full logits (cand 0):", abs(ref0 - one[0]))
