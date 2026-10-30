"""Diagnose the K2-loss-test mismatch: is it batching/left-padding inside r0_code/scorer.py
(candidates of different token lengths sharing one padded forward pass) or a bug in the test's
own from-scratch method_a? Forces r0's HFScorer to batch ONE row at a time (token_budget tiny) and
compares against its own normal (multi-row-padded) batching, and against an unpadded single-row
forward identical to method_a, all three for the same question.
"""
import json
import sys

sys.path.insert(0, "/mnt/cephfs/xingchao/experiments/jev/r0_code")
import prompt as prompt_mod  # noqa: E402
import scorer as r0_scorer  # noqa: E402
import torch
import torch_npu  # noqa: F401
import transformers

path = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"
tok = transformers.AutoTokenizer.from_pretrained(path)
model = transformers.AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16).to("npu").eval()

row = None
with open("/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl") as f:
    for line in f:
        r = json.loads(line)
        if r["kev"]["id"] == "yelp/train/388287":
            row = r
            break
p = prompt_mod.build_prompt(row, render="record_name")
print("candidates:", p.candidates)
cand_lens = [len(tok(c, add_special_tokens=False)["input_ids"]) for c in p.candidates]
print("candidate token lengths:", cand_lens)

cap = []
orig = r0_scorer.softmax
r0_scorer.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
sc = r0_scorer.HFScorer(path, device="npu", dtype="bfloat16", model=model, tokenizer=tok)
sc.score([row])  # normal: all 5 candidates may share one padded batch
r0_scorer.softmax = orig
print("r0 normal (shared padded batch):", cap[0])

cap2 = []
orig2 = r0_scorer.softmax
r0_scorer.softmax = lambda s: (cap2.append(list(s)), orig2(s))[1]
sc_tiny = r0_scorer.HFScorer(path, device="npu", dtype="bfloat16", model=model, tokenizer=tok, token_budget=1)
sc_tiny.score([row])  # token_budget=1 forces size=max(1, 1//longest)=1 row per forward call
r0_scorer.softmax = orig2
print("r0 token_budget=1 (one row per forward):", cap2[0])

print("max |normal - tiny|:", max(abs(a - b) for a, b in zip(cap[0], cap2[0])))
