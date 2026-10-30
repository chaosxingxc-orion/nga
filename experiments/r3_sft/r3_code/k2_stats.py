"""How expensive is K2 as implemented (one full row per option) and what would sharing the prompt buy?  CPU only (tokenizer).
    python3 -P k2_stats.py <out.json> [--steps 200]
For the first N steps of seed 2, epoch 0: options per question, prompt tokens, option token lengths, and token counts of
(a) the current layout: one row (prompt + option) per option,
(b) first-token sharing: one prompt row per question, plus a full row only for options of >= 2 tokens,
(c) full prompt sharing (ideal): prompt once + all option tokens.
"""
import json
import statistics as S
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transformers
import train_r3 as T

out = sys.argv[1]
n_steps = int(sys.argv[sys.argv.index("--steps") + 1]) if "--steps" in sys.argv else 200
tok = transformers.AutoTokenizer.from_pretrained("/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base")
a = T.parse_args(["--out", "/tmp/unused", "--seed", "2"])
d = T.Data(a)
cur, first, ideal, nopt, plen, olen, multi = [], [], [], [], [], [], []
for step in range(n_steps):
    _, units = d.step_units(step)
    c = f = i = 0
    for e in [x for u in units for x in u]:
        p, cands = T.encode_candidates(tok, e, 8192, {})
        c += sum(len(p) + len(x) for x in cands)
        f += len(p) + sum(len(p) + len(x) for x in cands if len(x) >= 2)
        i += len(p) + sum(len(x) for x in cands)
        nopt.append(len(cands)); plen.append(len(p)); olen += [len(x) for x in cands]
        multi.append(sum(1 for x in cands if len(x) >= 2) / len(cands))
    cur.append(c); first.append(f); ideal.append(i)
res = {"steps": n_steps, "questions": len(nopt),
       "tokens_per_step_current": {"median": S.median(cur), "mean": S.mean(cur), "max": max(cur)},
       "tokens_per_step_first_token_sharing": {"median": S.median(first), "mean": S.mean(first), "max": max(first)},
       "tokens_per_step_full_sharing": {"median": S.median(ideal), "mean": S.mean(ideal), "max": max(ideal)},
       "options_per_question": {"median": S.median(nopt), "mean": S.mean(nopt), "max": max(nopt)},
       "prompt_tokens": {"median": S.median(plen), "mean": S.mean(plen), "max": max(plen)},
       "option_tokens": {"median": S.median(olen), "mean": S.mean(olen), "max": max(olen)},
       "fraction_options_multi_token": sum(1 for x in olen if x >= 2) / len(olen)}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))
