"""R3 Track K scorer (R3-SFT-PREREG sec 4-5): score a checkpoint (or a degenerate baseline) on
decision-v7 / transfer-v4 partitions converted by r1_code/convert_kev.py, write readouts and a
report.json with the prereg's Track K metrics.

    python3 -P eval_r3.py --model-path <HF dir or 'constant'|'question_only'|'empty_input'|'uniform'> \\
        --suite decision-v7 --split dev --out <dir> [--limit N] [--device npu]

Scorer: r0_code/scorer.py's HFScorer with token_budget=1 (one row per forward, no padding, slow but exact; the default
here). r1_code/scorer.py is NOT used until the orchestrator accepts it. --scorer rightpad is a candidate replacement:
the same one-row-per-candidate layout but batched with RIGHT padding and logits gathered at the scored positions; it
exists to be compared against the exact scorer (see --compare-exact), not to produce reported numbers.

sec 4.1/4.2 headline: Kev's own argmax rule (first maximal index, numpy convention) on the raw
scores; sec 4.1 also reports the R0 tie convention (tie = not correct) and the tie count beside it.
sec 4.3/5: degenerate baselines (constant fitted on decision-v7 train per (source, qname) with the
position/then-0 fallback tiers of sec 5.1; question-only/empty-state as prompt transforms over the
SAME scored model; uniform). sec 10.4(a): the gold-position distribution and the constant/uniform
numbers are computed before any other Track K number.

One command per model (every Track K and Track T number, pre-number checks, test lock): python3 -P eval_r3.py --full --model-path <dir>
[--adapter <dir>] --arm K0 --out <run dir> ... ; see full_eval_r3.py (modules variants_r3, track_t_r3, select_r3, testlock_r3, prechecks_r3).
Under --full the test lock is testlock_r3 (FINAL.json naming by path + sha256, one read per partition, TEST-READS.log). The older
single-partition path below has no test lock of its own: it refuses the test partition outright (one lock only, sec 8.4;
scorer_r3.guard_split is retired).
"""
import argparse
import datetime
import json
import math
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
R0_CODE = os.environ.get("NGA_R0_CODE", os.path.normpath(os.path.join(_HERE, "..", "..", "r0_code")))
if R0_CODE not in sys.path:
    sys.path.insert(0, R0_CODE)
import prompt as prompt_mod  # noqa: E402
import scorer as scorer_mod  # noqa: E402
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import scorer_r3  # noqa: E402  (admissible scorer, prereg 14.2; --scorer exact|fast)

KEV_DIR = os.environ.get("NGA_KEV_DIR", os.path.normpath(os.path.join(_HERE, "..", "..", "KEV")))
DEGENERATE = ("constant", "question_only", "empty_input", "uniform")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_rows(suite, split, limit=0, data_path=None):
    if data_path:
        path = data_path
    else:
        path = os.path.join(KEV_DIR, suite, f"{split}.jsonl")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows, path


def gold_index(row):
    return [l["id"] for l in row["levels"]].index(row["gold"])


# ---- degenerate baselines (sec 5) ---------------------------------------------------------------

def fit_constant(train_rows):
    """sec 5.1: majority gold level per (source, qname) on decision-v7 train; fallback majority gold
    POSITION per (level_type, n_options); final fallback position 0. Returns a callable scorer."""
    by_q = defaultdict(Counter)
    by_pos = defaultdict(Counter)
    for r in train_rows:
        by_q[(r["source"], r["qname"])][r["gold"]] += 1
        by_pos[(r["level_type"], len(r["levels"]))][gold_index(r)] += 1
    maj_q = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_q.items()}
    maj_pos = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in by_pos.items()}

    def score_one(row):
        ids = [l["id"] for l in row["levels"]]
        key_q = (row["source"], row["qname"])
        if key_q in maj_q and maj_q[key_q] in ids:
            idx, tier = ids.index(maj_q[key_q]), "question"
        else:
            key_pos = (row["level_type"], len(row["levels"]))
            idx = maj_pos.get(key_pos, 0)
            idx = idx if idx < len(ids) else 0
            tier = "position" if key_pos in maj_pos else "position0"
        s = [0.0] * len(ids)
        s[idx] = 1.0
        return s, tier
    return score_one


def score_degenerate(name, rows, train_rows=None, inner_model_path=None, device="cpu", adapter=None, r3_mode=None):
    """Returns (list of raw-score lists, list of tier/notes)."""
    if name == "uniform":
        return [[1.0 / len(r["levels"])] * len(r["levels"]) for r in rows], ["uniform"] * len(rows)
    if name == "constant":
        f = fit_constant(train_rows)
        out, tiers = [], []
        for r in rows:
            s, t = f(r)
            out.append(s)
            tiers.append(t)
        return out, tiers
    if name in ("question_only", "empty_input") and r3_mode:
        transform = prompt_mod.drop_input if name == "question_only" else prompt_mod.blank_input
        sc = scorer_r3.R3Scorer(inner_model_path, adapter=adapter, device=device)
        return sc.score_raw([transform(r) for r in rows], r3_mode), [name] * len(rows)
    if name in ("question_only", "empty_input"):
        if adapter:
            m, t = load_with_adapter(inner_model_path, adapter, device)
            base = scorer_mod.HFScorer(inner_model_path, device=device, dtype="bfloat16", token_budget=1, model=m, tokenizer=t)
        else:
            base = scorer_mod.HFScorer(inner_model_path, device=device, dtype="bfloat16", token_budget=1)
        transform = prompt_mod.drop_input if name == "question_only" else prompt_mod.blank_input
        cap = []
        orig = scorer_mod.softmax
        scorer_mod.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
        try:
            base.score([transform(r) for r in rows])
        finally:
            scorer_mod.softmax = orig
        return cap, [name] * len(rows)
    raise ValueError(name)


# ---- model scoring --------------------------------------------------------------------------------

def load_with_adapter(model_path, adapter, device):
    """Model of record for a tuned arm: bf16 base + the UNMERGED LoRA adapter (peft at run time). Returns (model, tokenizer)."""
    import torch
    import transformers
    from peft import PeftModel
    if device.startswith("npu"):
        import torch_npu  # noqa: F401
    tok = transformers.AutoTokenizer.from_pretrained(model_path)
    base = transformers.AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.bfloat16)
    pm = PeftModel.from_pretrained(base, adapter)          # LoRA tensors stay fp32 (peft default); never merged
    n_lora = sum(1 for n, _ in pm.named_parameters() if "lora_A" in n)
    assert n_lora > 0, "adapter has no LoRA tensors"
    print(f"loaded base + unmerged adapter {adapter}: {n_lora} LoRA pairs", flush=True)
    return pm.to(device).eval(), tok


def score_model(model_path, rows, device, chunk=32, token_budget=1, scorer_kind="hf", adapter=None):
    if scorer_kind in ("exact", "fast"):      # scorer_r3: exact = token_budget=1 layout, fast = shared prompt + cached continuation
        return scorer_r3.R3Scorer(model_path, adapter=adapter, device=device).score_raw(rows, scorer_kind)
    if scorer_kind == "rightpad":
        return score_rightpad(model_path, rows, device, chunk, token_budget, adapter)
    if adapter:
        m, t = load_with_adapter(model_path, adapter, device)
        sc = scorer_mod.HFScorer(model_path, device=device, dtype="bfloat16", token_budget=token_budget, model=m, tokenizer=t)
    else:
        sc = scorer_mod.HFScorer(model_path, device=device, dtype="bfloat16", token_budget=token_budget)
    raw = []
    for i in range(0, len(rows), chunk):
        batch = rows[i:i + chunk]
        cap = []
        orig = scorer_mod.softmax
        scorer_mod.softmax = lambda s: (cap.append(list(s)), orig(s))[1]
        try:
            sc.score(batch)
        finally:
            scorer_mod.softmax = orig
        raw.extend(cap)
        print(f"  scored {min(i + chunk, len(rows))}/{len(rows)}", flush=True)
    return raw


def score_rightpad(model_path, rows, device, chunk=32, token_budget=12000, adapter=None):
    """Candidate scorer: one row per candidate, RIGHT padded, logits gathered at the scored positions (train_r3.row_logprob_sums)."""
    import torch
    import transformers
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import train_r3 as T
    import torch_npu  # noqa: F401
    if adapter:
        pm, tok = load_with_adapter(model_path, adapter, device)
        model = pm.base_model.model          # the causal LM with the (unmerged) LoRA layers in place
    else:
        tok = transformers.AutoTokenizer.from_pretrained(model_path)
        model = transformers.AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.bfloat16, attn_implementation="sdpa").to(device).eval()
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    raw = []
    for i in range(0, len(rows), chunk):
        seqs, starts, owner = [], [], []
        for j, r in enumerate(rows[i:i + chunk]):
            p = prompt_mod.build_prompt(r, "record_name")
            pre = tok(p.text, add_special_tokens=False)["input_ids"]
            for c in p.candidates:
                cid = tok(c, add_special_tokens=False)["input_ids"]
                seqs.append(pre + cid)
                starts.append(len(pre))
                owner.append(j)
        with torch.no_grad():
            s = T.row_logprob_sums(torch, model, seqs, starts, pad, device, autocast=False, micro_tokens=token_budget).float().cpu().tolist()
        per = {}
        for o, v in zip(owner, s):
            per.setdefault(o, []).append(v)
        raw.extend(per[j] for j in range(len(rows[i:i + chunk])))
        print(f"  scored {min(i + chunk, len(rows))}/{len(rows)}", flush=True)
    return raw


# ---- metrics (sec 4) ------------------------------------------------------------------------------

def argmax_first(scores):
    """numpy argmax convention: first maximal index wins (sec 4.2)."""
    best_i, best_v = 0, scores[0]
    for i, v in enumerate(scores):
        if v > best_v:
            best_i, best_v = i, v
    return best_i


def is_tie(scores):
    m = max(scores)
    return sum(1 for s in scores if s == m) >= 2


def track_k_metrics(rows, raw_scores):
    """Kev-rule headline (sec 4.1), R0-rule accuracy, tie count, per-source n (sec 4.1, 4.2)."""
    n = len(rows)
    correct_kev = correct_r0 = ties = 0
    by_source = defaultdict(lambda: {"n": 0, "correct_kev": 0, "correct_r0": 0, "ties": 0})
    for row, s in zip(rows, raw_scores):
        gi = gold_index(row)
        pred = argmax_first(s)
        tie = is_tie(s)
        ck = int(pred == gi)
        cr = int(pred == gi and not tie)
        correct_kev += ck
        correct_r0 += cr
        ties += int(tie)
        b = by_source[row["source"]]
        b["n"] += 1
        b["correct_kev"] += ck
        b["correct_r0"] += cr
        b["ties"] += int(tie)
    return {
        "n": n,
        "kev_rule_accuracy": correct_kev / n if n else None,
        "r0_rule_accuracy": correct_r0 / n if n else None,
        "tie_count": ties,
        "by_source": {k: {"n": v["n"], "kev_rule_accuracy": v["correct_kev"] / v["n"],
                           "r0_rule_accuracy": v["correct_r0"] / v["n"], "tie_count": v["ties"]}
                      for k, v in sorted(by_source.items())},
    }


def gold_position_distribution(rows):
    c = Counter(gold_index(r) for r in rows)
    return {str(k): v for k, v in sorted(c.items())}


RECORD_TOKEN_BUDGET = 16384      # R3 sec 14.9 item 3: the token budget of the scorer of record


def set_hf32_off(device):
    """R3 sec 14.6 item 2: HF32 matmul and conv disabled for every readout of record (the NPU default for fp32 is ON)."""
    if device.startswith("npu"):
        import torch
        import torch_npu  # noqa: F401
        torch.npu.conv.allow_hf32 = False
        torch.npu.matmul.allow_hf32 = False


def hf32_state(device):
    """{"matmul": bool, "conv": bool, "hf32": bool} as the NPU stack reports them now; None on CPU (no HF32 there)."""
    if not device.startswith("npu"):
        return None
    import torch
    import torch_npu  # noqa: F401
    m, c = bool(torch.npu.matmul.allow_hf32), bool(torch.npu.conv.allow_hf32)
    return {"matmul": m, "conv": c, "hf32": m or c}


def record_grade_problems(mode, dtype, token_budget, hf32, device):
    """R3 sec 14.9 item 3 + 14.6 item 2: what makes a readout NOT the scorer of record. Empty list = record grade."""
    p = []
    if mode != "rightpad":
        p.append(f"scorer mode {mode!r} is not 'rightpad' (14.9 item 3; 'fast' is the retained check, 'exact' and 'r0' are not scorers of record)")
    if dtype != "float32":
        p.append(f"dtype {dtype!r} is not float32 (14.6 item 2: bf16 is not admissible for a readout of record)")
    if token_budget != RECORD_TOKEN_BUDGET:
        p.append(f"token_budget {token_budget} is not {RECORD_TOKEN_BUDGET} (14.9 item 3)")
    if not device.startswith("npu"):
        p.append(f"device {device!r} is not npu (the scorer of record was verified on the NPU)")
    elif hf32 is None or hf32.get("hf32") is not False:
        p.append(f"HF32 is not off ({hf32}); 14.6 item 2 requires it off")
    return p


NOT_OF_RECORD_KINDS = ("rightpad", "exact", "fast")      # R3-SFT-PREREG sec 14.11 item 22: the single-partition path refuses these without --not-of-record


def _signature_default(cls, name):
    import inspect
    return inspect.signature(cls.__init__).parameters[name].default


def explicit_options(argv):
    """Option strings the caller actually typed (the part before '='), so a default is not mistaken for a request."""
    return {t.split("=", 1)[0] for t in argv if t.startswith("--")}


def single_partition_effective(a):
    """What the single-partition path (no --full) APPLIES for the requested --scorer, read from the code that dispatches it (score_model), not assumed:
    hf -> scorer.HFScorer, bfloat16 hard-coded, --token-budget honoured; exact / fast -> scorer_r3.R3Scorer built without dtype or token_budget (its constructor
    defaults apply); rightpad -> eval_r3.score_rightpad (train_r3.row_logprob_sums), bfloat16 hard-coded, --token-budget reinterpreted as micro_tokens, no dedup."""
    k = a.scorer
    if k in ("exact", "fast"):
        return {"implementation": "scorer_r3.R3Scorer", "dtype": _signature_default(scorer_r3.R3Scorer, "dtype"),
                "token_budget": ("ignored: one row per forward" if k == "exact" else _signature_default(scorer_r3.R3Scorer, "token_budget")), "dedup": "scorer_r3 default"}
    if k == "rightpad":
        return {"implementation": "eval_r3.score_rightpad (train_r3.row_logprob_sums)", "dtype": "bfloat16", "token_budget": "micro_tokens=%s" % a.token_budget, "dedup": False}
    return {"implementation": "scorer.HFScorer (R0)", "dtype": "bfloat16", "token_budget": a.token_budget, "dedup": False}


def single_partition_gate(a, argv, full_only_options=()):
    """sec 14.11 item 22. The single-partition path (no --full) refuses rightpad, exact and fast unless --not-of-record is passed, refuses --require-record-grade
    outright (it cannot honour it), and returns the header block: effective dtype / hf32 / implementation, record_grade false, and EVERY flag it does not honour
    reported as ignored or reinterpreted (including defaults of --full flags that would otherwise look like a request, e.g. --dtype float32)."""
    typed = explicit_options(argv)
    if getattr(a, "require_record_grade", False):
        raise SystemExit("--require-record-grade cannot be honoured on the single-partition path (no --full): it applies bf16 or constructor defaults and no HF32 control; "
                         "use --full for a readout of record (sec 14.11 item 22)")
    if a.scorer in NOT_OF_RECORD_KINDS and not getattr(a, "not_of_record", False):
        raise SystemExit("--scorer %s without --full is refused: on this path it is not the scorer of record (bf16 or constructor defaults, no HF32 control, no record-grade check, "
                         "flags silently ignored; sec 14.11 item 22). Use --full for a readout of record, or pass --not-of-record to acknowledge a diagnostic, non-record run." % a.scorer)
    eff = single_partition_effective(a)
    ignored = []
    if eff["dtype"] != a.dtype:
        ignored.append({"flag": "--dtype", "requested": a.dtype, "typed": "--dtype" in typed, "applied": eff["dtype"], "status": "ignored"})
    if a.scorer == "rightpad":
        ignored.append({"flag": "--token-budget", "requested": a.token_budget, "typed": "--token-budget" in typed, "applied": eff["token_budget"], "status": "reinterpreted"})
    elif a.scorer == "exact":
        ignored.append({"flag": "--token-budget", "requested": a.token_budget, "typed": "--token-budget" in typed, "applied": eff["token_budget"], "status": "ignored"})
    elif a.scorer == "fast" and a.token_budget != eff["token_budget"]:
        ignored.append({"flag": "--token-budget", "requested": a.token_budget, "typed": "--token-budget" in typed, "applied": eff["token_budget"], "status": "ignored"})
    if getattr(a, "no_hf32", False):
        ignored.append({"flag": "--no-hf32", "requested": True, "typed": True, "applied": "no HF32 control on this path; the flags are read back, not set", "status": "ignored"})
    for o in sorted(typed & set(full_only_options) - {"--dtype", "--no-hf32", "--require-record-grade", "--not-of-record"}):
        ignored.append({"flag": o, "requested": "typed", "typed": True, "applied": "nothing: this flag belongs to --full", "status": "ignored"})
    return {"not_of_record": True, "record_grade": False, "path": "single-partition (no --full)", "effective": eff, "flags_ignored": ignored}


def make_score_fn(a):
    """Scorer handle for full_eval_r3.run_full (the one-command evaluation, --full): score_fn(rows, input_mode) -> raw per-option
    scores s_i, via scorer_r3.R3Scorer (loaded on first use, so the report-only stage never loads a model). input_mode 'blank' /
    'drop' apply the R0 prompt transforms to the SAME scored model (prereg 5.2, 5.3). Replace this function to drop in another scorer.

    The scorer of record is mode rightpad, float32, HF32 off, token_budget 16384 (sec 14.6 item 2, 14.9 item 3). `--no-hf32` turns the
    NPU HF32 flags off before the model loads; the header records the flags as read back, not as requested. `--require-record-grade`
    refuses to start unless the configuration IS the scorer of record. (Before 2026-10-30 this function silently mapped every
    --scorer other than exact|fast to 'exact', so --scorer rightpad ran the exact layout.)"""
    if a.model_path.startswith("mock"):          # pipeline checks without a model
        import full_eval_r3
        return full_eval_r3.mock_score_fn(a.model_path)
    if a.scorer not in ("hf", "exact", "rightpad", "fast"):
        raise SystemExit(f"--scorer {a.scorer!r} is not a scorer_r3 mode")
    mode = "exact" if a.scorer == "hf" else a.scorer        # 'hf' (token_budget=1) is the exact layout
    if getattr(a, "no_hf32", False):
        set_hf32_off(a.device)
    hf32 = hf32_state(a.device)
    token_budget = a.token_budget if mode in ("rightpad", "fast") else None
    if getattr(a, "require_record_grade", False):
        problems = record_grade_problems(mode, a.dtype, token_budget, hf32, a.device)
        if problems:
            raise SystemExit("--require-record-grade: not the scorer of record: " + "; ".join(problems))
    holder = {}

    def score(rows, input_mode="full"):
        if "sc" not in holder:
            kw = {"token_budget": token_budget} if token_budget else {}
            holder["sc"] = scorer_r3.R3Scorer(a.model_path, adapter=a.adapter, device=a.device, dtype=a.dtype, **kw)
        if input_mode == "blank":
            rows = [prompt_mod.blank_input(r) for r in rows]
        elif input_mode == "drop":
            rows = [prompt_mod.drop_input(r) for r in rows]
        return holder["sc"].score_raw(rows, mode)
    import full_eval_r3
    layout = {"rightpad": "one row per candidate, right-padded with an explicit mask, LM head at the scored positions only; rows sorted by descending length "
                          "and packed to token_budget per forward, per call of %d questions" % full_eval_r3.SCORE_CHUNK,
              "exact": "one row per candidate, one forward each, no padding", "fast": "shared prompt + cached continuation (retained check, not a scorer of record)"}[mode]
    score.describe = lambda: {"scorer": "scorer_r3.R3Scorer", "mode": mode, "dtype": a.dtype, "hf32": hf32, "token_budget": token_budget,
                              "score_chunk_questions": full_eval_r3.SCORE_CHUNK, "layout": layout, "dedup": True, "render": "record_name",
                              "model_path": a.model_path, "adapter": a.adapter,
                              "record_grade": not record_grade_problems(mode, a.dtype, token_budget, hf32, a.device),
                              "record_grade_problems": record_grade_problems(mode, a.dtype, token_budget, hf32, a.device)}

    def token_stats():          # sec 10.2: cumulative token positions forwarded (padding included) and the padding part of them
        st = holder["sc"].stats if "sc" in holder else {}
        return {"forwarded": int(st.get("tokens", 0)), "padded": int(st.get("padded_tokens", 0)),
                "unit": "model tokens: prompt and candidate positions forwarded (scorer_r3.R3Scorer.stats['tokens']), padding positions included"}
    score.token_stats = token_stats

    def dedup_stats():          # R3 sec 14.6 item 4: scorer-side counts of the duplicate-candidate safeguard
        st = holder["sc"].stats if "sc" in holder else {}
        return {"dup_questions": int(st.get("dup_questions", 0)), "dup_candidates_removed": int(st.get("dup_candidates_removed", 0))}
    score.dedup_stats = dedup_stats
    return score


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-path", required=True, help="HF dir, or one of: " + ", ".join(DEGENERATE))
    ap.add_argument("--suite", default="decision-v7", choices=("decision-v7", "transfer-v4"))
    ap.add_argument("--split", default="dev", choices=("train", "calibration", "dev", "test"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=None, help="path to a custom JSONL data file (mutually exclusive with --suite/--split); rows must have the same fields as KEV suite rows")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="npu")
    ap.add_argument("--chunk", type=int, default=32)
    ap.add_argument("--token-budget", type=int, default=1, help="HFScorer token budget; 1 = one row per forward, exact (default). Under --full with --scorer rightpad|fast: the R3Scorer token budget (record: 16384)")
    ap.add_argument("--scorer", choices=("hf", "rightpad", "exact", "fast"), default="hf", help="under --full: the scorer_r3 mode; the scorer of record is rightpad (sec 14.9 item 3)")
    ap.add_argument("--adapter", default=None, help="LoRA adapter dir: score base (--model-path) + UNMERGED adapter (the model of record)")
    ap.add_argument("--inner-model-path", default=None, help="for question_only/empty_input: the model those transforms are applied to")
    ap.add_argument("--full", action="store_true", help="one command per model: every Track K and Track T number (full_eval_r3.py); --suite/--split are ignored, see --partitions")
    ap.add_argument("--not-of-record", action="store_true", help="single-partition path only (sec 14.11 item 22): acknowledge that --scorer rightpad|exact|fast without --full is a diagnostic, "
                    "bf16 / constructor-default run, never a readout of record; required for those three scorer names there")
    import full_eval_r3
    before = set(ap._option_string_actions)
    full_eval_r3.add_arguments(ap)
    full_only_options = set(ap._option_string_actions) - before
    a = ap.parse_args()
    if a.full:
        if a.not_of_record:
            raise SystemExit("--not-of-record belongs to the single-partition path; with --full the scorer is checked by --require-record-grade instead")
        full_eval_r3.run_full_marked(a, make_score_fn(a))
        return

    if a.split == "test":
        # sec 8.4: the one lock is testlock_r3, reachable only through --full. This older path refuses test outright.
        raise SystemExit("prereg 8.4: the single-partition path does not read the test partition; use --full (testlock_r3)")

    gate = single_partition_gate(a, sys.argv[1:], full_only_options)       # sec 14.11 item 22: refuses before any file is written or model loaded
    for g in gate["flags_ignored"]:
        print("NOT OF RECORD: %s %s -> %s (requested %r, applied %r)" % (g["flag"], "typed" if g["typed"] else "default", g["status"], g["requested"], g["applied"]), flush=True)
    if a.data and a.suite != ap.get_default("suite"):
        raise SystemExit("--data and --suite are mutually exclusive; omit --suite when using --data (--split is also ignored in that case)")
    if a.data:
        a.suite = "custom"
        a.split = None
    rows, path = load_rows(a.suite, a.split, a.limit, data_path=a.data)
    os.makedirs(a.out, exist_ok=True)

    if a.model_path in DEGENERATE:
        train_rows = None
        if a.model_path == "constant":
            train_rows, _ = load_rows("decision-v7", "train")
        raw, tiers = score_degenerate(a.model_path, rows, train_rows=train_rows,
                                       inner_model_path=a.inner_model_path, device=a.device, adapter=a.adapter,
                                       r3_mode=a.scorer if a.scorer in ("exact", "fast") else None)
        model_desc = {"kind": "degenerate", "name": a.model_path, "inner_model_path": a.inner_model_path}
    else:
        raw = score_model(a.model_path, rows, a.device, a.chunk, a.token_budget, a.scorer, a.adapter)
        tiers = None
        model_desc = {"kind": "model", "model_path": a.model_path, "adapter": a.adapter}

    metrics = track_k_metrics(rows, raw)
    report = {
        "header": {"utc": utc(), "suite": a.suite, "split": a.split, "n": len(rows), "task_file": path,
                   "model": model_desc, "prompt_version": prompt_mod.PROMPT_VERSION,
                   "declared_differences_from_kev": "see R3-SFT-PREREG sec 3.3",
                   "scorer": a.scorer, "token_budget": a.token_budget,
                   "dtype": ("n/a: no model forward" if a.model_path in ("constant", "uniform") else gate["effective"]["dtype"]),
                   "hf32": (None if a.model_path in ("constant", "uniform") else hf32_state(a.device)), **gate},
        "gold_position_distribution": gold_position_distribution(rows),
        "track_k": metrics,
    }
    with open(os.path.join(a.out, "readouts.jsonl"), "w", encoding="utf-8") as f:
        for row, s in zip(rows, raw):
            f.write(json.dumps({"k": row["kev"]["id"] + "/" + str(row["kev"]["qindex"]), "source": row["source"],
                                 "s": s, "gold_index": gold_index(row), "argmax": argmax_first(s),
                                 "tie": is_tie(s)}) + "\n")
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print(json.dumps(metrics, indent=1)[:2000])
    print(f"report: {os.path.join(a.out, 'report.json')}")


if __name__ == "__main__":
    main()
