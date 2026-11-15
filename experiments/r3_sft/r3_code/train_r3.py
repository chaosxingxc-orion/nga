"""Minimal single-chip LoRA trainer for R3 round 1 (frozen prereg 387521b, §7.2-§7.4, §7.8, §7.9, §11).

Plain PyTorch + peft on the nga-verl-qwen35-v030 image, ONE NPU, no FSDP, no verl. Replaces the verl SFT path, which lacks
lora_dropout, OneCycleLR, per-epoch data regeneration and the K2 loss, and whose merger does not fold LoRA.

    python3 -P train_r3.py --out <run dir> --arm k1 --seed 2 [--model-path ...] [--kernel ref|fla] [--grad-ckpt]
                           [--total-steps N] [--stop-after N] [--symbol-file ... (K3)] [--drop-state (K1-QO)]

Arms: k1 (token CE on the response), k2 (option-restricted CE, §7.3), k1 with --model-path Qwen3.5-0.8B = K1-PT (§7.8),
k1 with --drop-state = K1-QO (§7.9); K3 = either loss with --symbol-file (§7.4).

What is fixed by the prereg, and where:
  LoRA r16 alpha32 dropout0.05 on the hybrid target list, embeddings/lm_head frozen ...... §7.2 (asserted: 186 pairs at 0.8B)
  AdamW wd0.01, OneCycleLR(max_lr 1e-4, pct_start 0.1) over all steps, grad clip 1.0 ...... §7.2 (kev/train.py:376,503,580,588)
  bf16 compute: frozen backbone stored bf16, LoRA fp32 (peft default), torch.autocast bf16, AdamW fp32 state ... §7.2
  10 base questions per step, pair siblings ride along (not counted), per-epoch Kev augmentation ........ §3.4, §7.2
  loss = token CE on the response tokens only, mean over response tokens of the step, no EOS ......... §7.2
  K2 loss = -log softmax(s)_gold, s = summed identifier log-probs of ALL the question's options, mean over the
  questions of the step (siblings are questions) ......................................................... §7.3
Padding: RIGHT padding only (the model is causal, so tokens after position t cannot change position t); attention_mask is
passed anyway. Logits are computed only at the scored positions (the vocabulary is 248k), never for the whole batch.

Efficiency (speed only; r3_runs/eff has the measurements, tests assert the equalities): --gdn-impl fast_ref (gdn_fast_ref.py, the
reference kernel's math with ~10x fewer device tasks, fp32-rounding-level identical), TASK_QUEUE_ENABLE=2 and expandable segments set
below, K1 chunk planner plan_chunks (--micro-tokens, --chunk-overhead) that minimises padding, --k2-impl shared (k2_shared.py, prompt
forwarded once per question), several processes per chip (--procs-on-chip only labels the throughput lines), windowed per-chip
throughput in heartbeat.log and perf.json (class Perf). Recommended K1 flags without gradient checkpointing:
  --gdn-impl fast_ref --micro-tokens 4096 --chunk-overhead 4000      (about 25 GiB reserved per process at 0.8B)

Determinism / resume: data order is a pure function of (seed, epoch); dropout is seeded per step (seed * 1000003 + step);
a checkpoint (every --save-every steps) holds the LoRA tensors, AdamW state, scheduler state and the step, so a resumed run
continues exactly where the interrupted one stopped (the cursor is the step number).

Run hygiene (CLAUDE.md §7): meant to run under speedup/code/run_cell.py (heartbeat.log, DONE/FAILED, RELAUNCH.txt);
this script adds progress.log (timestamp, step/total, loss, tok/s/chip, questions/s/chip), losses.jsonl, manifest.json.
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
import time

# Launch-bound on Ascend (profile: device busy 21% of wall): torch_npu's two-stage operator dispatch queue (level 2) lifts throughput
# ~1.45x with identical results; expandable segments keep the reserved pool small enough for several processes per chip. Both are read
# when torch_npu is imported, so they are set here, before any import of torch. TASK_QUEUE_ENABLE is ASSIGNED, not defaulted: the image
# itself exports TASK_QUEUE_ENABLE=1, so a setdefault never took effect in a container (measured: the same 100 steps took 5.0 s/step with
# the inherited 1 and 2.1 s/step with 2). To run with another level set NGA_TASK_QUEUE_ENABLE; the value used is in the manifest.
os.environ["TASK_QUEUE_ENABLE"] = os.environ.get("NGA_TASK_QUEUE_ENABLE", "2")
os.environ.setdefault("PYTORCH_NPU_ALLOC_CONF", "expandable_segments:True")

HERE = os.path.dirname(os.path.abspath(__file__))
R0_CODE = os.environ.get("NGA_R0_CODE", os.path.normpath(os.path.join(HERE, "..", "..", "r0_code")))
for _p in (HERE, R0_CODE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_kev_sft as B  # noqa: E402
import kev_aug  # noqa: E402

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
                "in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b", "out_proj"]
TRAIN_FILE = os.environ.get("NGA_TRAIN_FILE", os.path.normpath(os.path.join(HERE, "..", "..", "KEV", "decision-v7", "train.jsonl")))
SYMBOL_SHA256 = "7b1edec5f6e0d3a7e7fd1e8778f0afdb11f756c956f2de02102d6a212c961540"   # prereg §2.4
BATCH_BASE_QUESTIONS = 10                                                           # prereg §7.2


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def file_sha256(path):
    return B.file_sha256(path)


# ----------------------------------------------------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------------------------------------------------

def symbol_units(path, n_rows):
    """K3 (prereg §7.4): n_rows symbol rows, drawn once in ascending order of sha256("k3-mix-v1" || row key), reused in
    every epoch, not passed through §3.4. Row key = "group_id \\x1f rec_index \\x1f aug_index" (the fields of
    build_sft.row_sort_key before hashing); the prereg does not spell the key out, so this choice is declared in the manifest.
    """
    if file_sha256(path) != SYMBOL_SHA256:
        raise SystemExit(f"symbol data sha256 differs from the frozen value {SYMBOL_SHA256}")
    keyed = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            key = f"{r['group_id']}\x1f{r['rec_index']}\x1f{r['aug_index']}"
            keyed.append((hashlib.sha256(("k3-mix-v1" + key).encode()).hexdigest(), r))
    keyed.sort(key=lambda kv: kv[0])
    out = []
    for _, r in keyed[:n_rows]:
        out.append([{"prompt": r["prompt"], "response": r["response"], "candidates": None, "gold_index": None,
                     "prov": {"role": "symbol", "source": r["source"], "task": r["task"], "variant": r["variant"],
                              "group_id": r["group_id"], "rec_index": r["rec_index"], "aug_index": r["aug_index"]}}])
    return out


class Data:
    """Epoch -> list of units (a unit = one base question + its pair siblings), deterministic in (seed, epoch)."""

    def __init__(self, args):
        self.args = args
        self.rows = B.read_rows(TRAIN_FILE, args.limit_rows)
        self.prompt_mod = B.load_prompt_module(R0_CODE)
        self.sym = symbol_units(args.symbol_file, args.symbol_n) if args.symbol_file else []
        self._cache = {}

    def units(self, epoch):
        if epoch not in self._cache:
            a = self.args
            u = B.epoch_units(self.rows, a.seed, epoch, "kev", self.prompt_mod, a.drop_state)
            if self.sym:
                u = u + [list(x) for x in self.sym]
                rng = random.Random(kev_aug.source_seed(a.seed, f"mix-shuffle:{epoch}"))
                order = list(range(len(u)))
                rng.shuffle(order)
                u = [u[i] for i in order]
            self._cache = {epoch: u}      # keep one epoch in memory
        return self._cache[epoch]

    def steps_per_epoch(self):
        return -(-(len(self.rows) + len(self.sym)) // BATCH_BASE_QUESTIONS)

    def step_units(self, step):
        spe = self.steps_per_epoch()
        epoch, i = divmod(step, spe)
        u = self.units(epoch)
        return epoch, u[i * BATCH_BASE_QUESTIONS:(i + 1) * BATCH_BASE_QUESTIONS]


# ----------------------------------------------------------------------------------------------------------------------
# model side (torch imported lazily so the data part stays host-testable)
# ----------------------------------------------------------------------------------------------------------------------

def right_pad(torch, seqs, pad_id, device):
    width = max(len(s) for s in seqs)
    ids = torch.full((len(seqs), width), pad_id, dtype=torch.long)
    mask = torch.zeros((len(seqs), width), dtype=torch.long)
    for r, s in enumerate(seqs):
        ids[r, :len(s)] = torch.tensor(s, dtype=torch.long)
        mask[r, :len(s)] = 1
    return ids.to(device), mask.to(device)


def row_logprob_sums(torch, core, seqs, starts, pad_id, device, autocast=True, micro_tokens=1 << 30, full_logits=False):
    """Summed log-prob of tokens seq[start:] given the preceding tokens, per row (a differentiable tensor of shape [R]).

    seqs[r] = full token list, starts[r] = index of the first scored token. RIGHT padding, attention_mask passed, logits only
    at the scored positions. Rows are processed in chunks of at most `micro_tokens` padded tokens (math is unchanged by
    chunking under right padding); the result is in the order of `seqs`.
    """
    order = sorted(range(len(seqs)), key=lambda r: -len(seqs[r]))
    out = [None] * len(seqs)
    pos = 0
    while pos < len(order):
        longest = len(seqs[order[pos]])
        size = max(1, micro_tokens // longest)
        chunk = order[pos:pos + size]
        pos += size
        ids, mask = right_pad(torch, [seqs[r] for r in chunk], pad_id, device)
        ctx = torch.autocast(device_type="npu", dtype=torch.bfloat16) if autocast else _Null()
        # Explicit 4D attention mask ALWAYS. With a plain 2D mask transformers drops it when the chunk has no padding (one row, or rows of
        # equal length) and sdpa takes the causal flash path, whose backward is not bitwise reproducible on this stack (repeat-to-repeat
        # gradient differences of ~2% relative L2, diag_determinism.py; the masked path is bit-identical across repeats). Real tokens see the
        # same keys either way; pad queries attend to themselves so no row is fully masked.
        width = ids.shape[1]
        causal = torch.tril(torch.ones(width, width, dtype=torch.bool, device=device))
        m4 = ((causal[None] & mask.bool()[:, None, :]) | torch.eye(width, dtype=torch.bool, device=device)[None])[:, None]
        with ctx:
            h = core.model(input_ids=ids, attention_mask={"full_attention": m4, "linear_attention": mask}, use_cache=False).last_hidden_state
            bi, ti, tg, owner = [], [], [], []
            for j, r in enumerate(chunk):
                s, n = starts[r], len(seqs[r])
                for q in range(s, n):
                    bi.append(j)
                    ti.append(q - 1)
                    tg.append(seqs[r][q])
                    owner.append(j)
            bi_t = torch.tensor(bi, device=device)
            ti_t = torch.tensor(ti, device=device)
            if full_logits:
                # comparison path only (--full-logits): the LM head over EVERY position, then gather. Same math, far more
                # compute and memory (vocabulary 248,320); used to measure what gathering first saves, and by the test.
                logits = core.lm_head(h)[bi_t, ti_t]
            else:
                logits = core.lm_head(h[bi_t, ti_t])      # LM head only at the positions whose logits the loss uses
        lp = torch.log_softmax(logits.float(), dim=-1)
        tok_lp = lp.gather(1, torch.tensor(tg, device=device)[:, None])[:, 0]
        sums = torch.zeros(len(chunk), device=device, dtype=tok_lp.dtype).index_add(0, torch.tensor(owner, device=device), tok_lp)
        for j, r in enumerate(chunk):
            out[r] = sums[j]
    return torch.stack(out)


class _Null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def encode_example(tok, ex, max_len, counters):
    p = tok(ex["prompt"], add_special_tokens=False)["input_ids"]
    a = tok(ex["response"], add_special_tokens=False)["input_ids"]
    if len(p) + len(a) > max_len:
        counters["truncated"] = counters.get("truncated", 0) + 1
        p = p[-(max_len - len(a)):]
    return p, a


def encode_candidates(tok, ex, max_len, counters):
    p = tok(ex["prompt"], add_special_tokens=False)["input_ids"]
    cands = [tok(c, add_special_tokens=False)["input_ids"] for c in ex["candidates"]]
    longest = max(len(c) for c in cands)
    if len(p) + longest > max_len:
        counters["truncated"] = counters.get("truncated", 0) + 1
        p = p[-(max_len - longest):]
    return p, cands


def plan_chunks(lengths, micro_tokens, overhead):
    """Partition rows into forward/backward chunks. Rows are sorted longest first and a chunk is a contiguous run of that order, so
    its padded size is (rows x its longest row). Minimises sum over chunks of (overhead + padded tokens), `overhead` being the fixed
    cost of one extra forward/backward expressed in padded-token equivalents, subject to padded tokens <= micro_tokens (a single row
    longer than micro_tokens is its own chunk). The loss is a sum over rows divided by a global constant, so the partition changes
    only the bf16 batch composition, not the function. Returns lists of row indices."""
    order = sorted(range(len(lengths)), key=lambda r: -lengths[r])
    n = len(order)
    INF = float("inf")
    best = [0.0] + [INF] * n          # best[j]: min cost of the first j rows of `order`
    cut = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):          # chunk = order[i:j], its longest row is order[i]
            padded = (j - i) * lengths[order[i]]
            if padded > micro_tokens and j - i > 1:
                break                            # growing the chunk further (smaller i) only increases padded
            c = best[i] + overhead + padded
            if c < best[j]:
                best[j], cut[j] = c, i
    chunks, j = [], n
    while j > 0:
        chunks.append(order[cut[j]:j])
        j = cut[j]
    return chunks[::-1]


def plan_k2_groups(plens, nrows, prompt_budget, row_budget):
    """Groups of questions for the shared-prompt K2 path: longest prompt first, a group's padded prompt tokens (rows x longest) stay
    within prompt_budget and its multi-token option rows within row_budget (a single oversized question forms its own group)."""
    order = sorted(range(len(plens)), key=lambda q: -plens[q])
    groups, cur, rows = [], [], 0
    for q in order:
        if cur and ((len(cur) + 1) * plens[cur[0]] > prompt_budget or rows + nrows[q] > row_budget):
            groups.append(cur)
            cur, rows = [], 0
        cur.append(q)
        rows += nrows[q]
    if cur:
        groups.append(cur)
    return groups


def step_loss(torch, core, tok, units, arm, device, pad_id, max_len, micro_tokens, counters, backward=True, full_logits=False,
              autocast=True, k2_impl="rows", k2_rows=96, chunk_overhead=2000):
    """One optimizer step's loss (and gradients if backward). Returns (loss value, stats dict).

    k2_impl "rows": every option is its own row (prompt + option), the reference form of the K2 loss. "shared": the prompt of each
    question is forwarded once (k2_shared.py); the same loss, computed differently (requires the model without gradient checkpointing)."""
    exs = [e for u in units for e in u]
    n_tok = 0
    if arm == "k1":
        enc = [encode_example(tok, e, max_len, counters) for e in exs]
        total_resp = sum(len(a) for _, a in enc)
        seqs = [p + a for p, a in enc]
        starts = [len(p) for p, _ in enc]
        n_tok = sum(len(s) for s in seqs)
        # chunk here (not inside row_logprob_sums) so each chunk's graph is freed right after its backward
        total, n_chunks, padded = 0.0, 0, 0
        for chunk in plan_chunks([len(x) for x in seqs], micro_tokens, chunk_overhead):
            n_chunks += 1
            padded += len(chunk) * max(len(seqs[r]) for r in chunk)
            sums = row_logprob_sums(torch, core, [seqs[r] for r in chunk], [starts[r] for r in chunk], pad_id, device,
                                    autocast=autocast, full_logits=full_logits)
            loss = -sums.sum() / total_resp
            if backward:
                loss.backward()
            total += float(loss.detach())
        return total, {"tokens": n_tok, "rows": len(exs), "resp_tokens": total_resp, "chunks": n_chunks, "padded_tokens": padded}
    if arm == "k2":
        if any(e["candidates"] is None for e in exs):
            raise SystemExit("k2 needs a candidates list on every example; symbol rows (K3) have none -- K3 is supported on K1 only")
        total = 0.0
        if k2_impl == "shared":
            import k2_shared
            enc = [encode_candidates(tok, e, max_len, counters) for e in exs]
            n_tok = sum(len(p) * len(c) + sum(len(x) for x in c) for p, c in enc)       # logical tokens of the one-row-per-option layout
            fwd = 0
            groups = plan_k2_groups([len(p) for p, _ in enc], [sum(1 for x in c if len(x) >= 2) for _, c in enc], micro_tokens, k2_rows)
            for g in groups:
                items = [enc[q] for q in g]
                ss = k2_shared.group_scores(torch, core, items, pad_id, device, autocast=autocast, max_option_rows=k2_rows)
                lg = sum(-torch.log_softmax(s_.float(), dim=0)[exs[q]["gold_index"]] for s_, q in zip(ss, g)) / len(exs)
                if backward:
                    lg.backward()
                total += float(lg.detach())
                fwd += len(g) * max(len(enc[q][0]) for q in g) + sum(len(x) - 1 for q in g for x in enc[q][1] if len(x) >= 2)
            return total, {"tokens": n_tok, "tokens_fwd": fwd, "rows": len(exs), "resp_tokens": 0, "chunks": len(groups)}
        for e in exs:
            p, cands = encode_candidates(tok, e, max_len, counters)
            seqs = [p + c for c in cands]
            starts = [len(p)] * len(cands)
            n_tok += sum(len(s) for s in seqs)
            s = row_logprob_sums(torch, core, seqs, starts, pad_id, device, autocast=autocast, micro_tokens=micro_tokens,
                                 full_logits=full_logits)
            lq = -torch.log_softmax(s.float(), dim=0)[e["gold_index"]] / len(exs)
            if backward:
                lq.backward()
            total += float(lq.detach())
        return total, {"tokens": n_tok, "rows": len(exs), "resp_tokens": 0}
    raise ValueError(arm)


def _pre_import_kernel(args):
    if args.kernel == "fla":
        os.environ["NGA_GDN_KERNEL"] = "fla"
        import nga_gdn_patch  # noqa: F401  (replaces the per-instance kernel callables; needs speedup/code + site_fla on PYTHONPATH)


def _install_gdn(model, args):
    if args.gdn_impl == "fast_ref":
        if args.kernel != "ref":
            raise SystemExit("--gdn-impl fast_ref is a form of the reference kernel; use it with --kernel ref")
        import gdn_fast_ref
        n_gdn = gdn_fast_ref.install(model, ckpt=args.gdn_ckpt)
        assert n_gdn > 0, "no GatedDeltaNet layer found to patch"
        print(f"[train_r3] gdn_impl=fast_ref installed on {n_gdn} layers", flush=True)


K4_LRS = (1e-5, 2e-5)        # prereg §7.5


def build_full_model(args, torch):
    """K4 (prereg §7.5): all parameters trained, no LoRA. Weights are held in FP32 (the master weights; the checkpoint is bf16 on disk and
    widens exactly) and the forward runs under torch.autocast bf16, i.e. "bf16 compute over fp32 master weights and optimizer state" (§7.2).
    Returns (model, trainable, 0). Everything not a parameter of the base model is a defect: the checks below assert it."""
    import transformers
    _pre_import_kernel(args)
    model = transformers.AutoModelForCausalLM.from_pretrained(args.model_path, dtype=torch.float32, attn_implementation="sdpa")
    if args.grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    _install_gdn(model, args)
    names = [n for n, _ in model.named_parameters()]
    assert not any("lora" in n.lower() for n in names) and not any("lora" in type(m).__name__.lower() for m in model.modules()), \
        "a LoRA module is present in the K4 path"
    for p in model.parameters():
        p.requires_grad_(True)
    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    assert len(trainable) == len(names) and all(p.dtype == torch.float32 for _, p in trainable), "K4 trains every parameter, in fp32"
    return model, trainable, 0


def build_model(args, torch):
    import transformers
    from peft import LoraConfig, TaskType, get_peft_model
    _pre_import_kernel(args)
    model = transformers.AutoModelForCausalLM.from_pretrained(args.model_path, dtype=torch.bfloat16, attn_implementation="sdpa")
    if args.grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    expected = sum(1 for n, m in model.named_modules()
                   if isinstance(m, torch.nn.Linear) and n.split(".")[-1] in LORA_TARGETS)
    torch.manual_seed(args.seed)                 # LoRA init (A ~ kaiming, B = 0)
    cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
                     target_modules=LORA_TARGETS, bias="none")
    _install_gdn(model, args)
    pm = get_peft_model(model, cfg)
    n_pairs = sum(1 for n, _ in pm.named_parameters() if "lora_A" in n)
    assert n_pairs == expected, (n_pairs, expected)
    if args.expect_pairs:
        assert n_pairs == args.expect_pairs, f"matched {n_pairs} LoRA pairs, prereg-verified value is {args.expect_pairs}"
    trainable = [(n, p) for n, p in pm.named_parameters() if p.requires_grad]
    assert trainable and all("lora_" in n for n, _ in trainable), "a non-LoRA parameter is trainable"
    return pm, trainable, n_pairs


# ----------------------------------------------------------------------------------------------------------------------
# merge (weight-space folding, with its check)
# ----------------------------------------------------------------------------------------------------------------------

def fold_and_save(torch, pm, args, tok, out_dir, probe_seqs, device):
    """EXPORT ONLY. The model of record is base + the unmerged adapter (peft at run time); folding into bf16 weights rounds away
    LoRA updates below ~1/256 of |W| (measured: bf16-folded vs peft logits differ by 1.4% relative L2 on the smoke checkpoint).

    Folds every LoRA pair in fp32 (W' = float32(W) + alpha/r * B @ A, W being the bf16 base weight, exactly representable in
    fp32) and saves the whole model in FLOAT32, so nothing is rounded. The peft model is not modified.
    Check 1: the folded weights differ from the base. Check 2: the saved directory reloads through AutoModelForCausalLM
    with no missing keys. Check 3: logits of the reloaded fp32 model on a probe of real rows vs the unmerged peft model's
    logits; the two differ only by bf16-vs-fp32 compute noise (reported, tolerance 0.05 relative L2).
    """
    import transformers
    core = pm.base_model.model
    pm.eval()

    def logits_of(model):
        ids, mask = right_pad(torch, probe_seqs, tok.pad_token_id or 0, device)
        with torch.no_grad():
            return model(input_ids=ids, attention_mask=mask, use_cache=False).logits.float().cpu(), mask.cpu()

    ref, mask = logits_of(core)               # unmerged: bf16 base + fp32 LoRA path
    sd, n, max_delta = {}, 0, 0.0
    with torch.no_grad():
        for name, m in core.named_modules():
            if hasattr(m, "lora_A") and "default" in getattr(m, "lora_A", {}):
                A = m.lora_A["default"].weight.float()
                Bm = m.lora_B["default"].weight.float()
                scaling = m.scaling["default"]
                assert abs(scaling - args.lora_alpha / args.lora_r) < 1e-9
                W = m.base_layer.weight.float()
                delta = scaling * (Bm @ A)
                max_delta = max(max_delta, float(delta.abs().max()))
                sd[name + ".weight"] = (W + delta).cpu()
                n += 1
        assert n > 0 and max_delta > 0, "folding changed nothing"
        for k, v in core.state_dict().items():
            if "lora_" in k or ".base_layer." in k:
                continue
            sd[k] = v.detach().float().cpu()
    # peft names are "model.layers.0.self_attn.q_proj" (module path inside the causal LM); state-dict keys match
    os.makedirs(out_dir, exist_ok=True)
    fresh = transformers.AutoModelForCausalLM.from_pretrained(args.model_path, dtype=torch.float32)
    missing = fresh.load_state_dict(sd, strict=False)
    assert not missing.unexpected_keys and all("lm_head" in k for k in missing.missing_keys), missing
    fresh.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    del fresh
    re, info = transformers.AutoModelForCausalLM.from_pretrained(out_dir, dtype=torch.float32, output_loading_info=True)
    assert not info.get("missing_keys"), info
    re = re.to(device).eval()
    reloaded, _ = logits_of(re)
    valid = mask.bool()
    rel = float((reloaded[valid] - ref[valid]).norm() / ref[valid].norm())
    assert rel < 0.05, f"folded fp32 export disagrees with the unmerged peft model: rel L2 {rel}"
    return {"pairs_folded": n, "max_abs_delta": max_delta, "export_dtype": "float32",
            "rel_l2_fp32_export_vs_unmerged_peft_logits": rel,
            "note": "export only; the model of record is base + unmerged adapter"}


# ----------------------------------------------------------------------------------------------------------------------
# training
# ----------------------------------------------------------------------------------------------------------------------

def save_full_model(torch, model, args, tok, out_dir, probe_seqs, device):
    """K4 model of record: every weight in fp32 (nothing rounded), saved as safetensors with the tokenizer; sha256 per file for the §8.4
    lock. Check: the directory reloads through AutoModelForCausalLM (no missing keys) and its fp32 logits on a probe of real rows equal the
    in-memory model's (relative L2 < 1e-6)."""
    import transformers
    model.eval()
    ids, mask = right_pad(torch, probe_seqs, tok.pad_token_id or 0, device)

    def logits_of(m):
        with torch.no_grad():
            return m(input_ids=ids, attention_mask=mask, use_cache=False).logits.float().cpu()

    ref = logits_of(model)
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    tok.save_pretrained(out_dir)
    re, info = transformers.AutoModelForCausalLM.from_pretrained(out_dir, dtype=torch.float32, output_loading_info=True)
    assert not info.get("missing_keys"), info
    re = re.to(device).eval()
    got = logits_of(re)
    valid = mask.cpu().bool()
    rel = float((got[valid] - ref[valid]).norm() / ref[valid].norm())
    assert rel < 1e-6, f"reloaded K4 weights disagree with the trained model: rel L2 {rel}"
    del re
    shas = {f: file_sha256(os.path.join(out_dir, f)) for f in sorted(os.listdir(out_dir)) if os.path.isfile(os.path.join(out_dir, f))}
    model.train()
    return {"dir": out_dir, "dtype": "float32", "rel_l2_reload_vs_trained": rel, "sha256": shas}


def save_ckpt(torch, out, step, trainable, opt, sched, keep=2):
    d = os.path.join(out, "ckpt")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".tmp_step_{step}.pt")
    torch.save({"step": step, "lora": {n: p.detach().cpu() for n, p in trainable}, "opt": opt.state_dict(),
                "sched": sched.state_dict()}, tmp)
    os.replace(tmp, os.path.join(d, f"step_{step:06d}.pt"))
    files = sorted(f for f in os.listdir(d) if f.startswith("step_"))
    for f in files[:-keep]:
        os.remove(os.path.join(d, f))


def latest_ckpt(out):
    d = os.path.join(out, "ckpt")
    if not os.path.isdir(d):
        return None
    files = sorted(f for f in os.listdir(d) if f.startswith("step_"))
    return os.path.join(d, files[-1]) if files else None


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", choices=("k1", "k2"), default="k1", help="loss: k1 token CE, k2 option-restricted CE (K1-PT/K1-QO/K3 are flags)")
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--model-path", default=os.environ.get("NGA_MODEL_BASE", "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--total-steps", type=int, default=0, help="0 = epochs x steps/epoch (3,116 for K1); >0 compresses the schedule (smoke)")
    ap.add_argument("--stop-after", type=int, default=0, help="stop this invocation after N steps (tests, smoke); no final merge")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--expect-pairs", type=int, default=186, help="prereg-verified LoRA pair count at 0.8B (0 disables, for other sizes)")
    ap.add_argument("--kernel", choices=("ref", "fla"), default="ref")
    ap.add_argument("--gdn-ckpt", action="store_true",
                    help="with --gdn-impl fast_ref: recompute the gated-delta-rule kernel in backward (activation checkpointing of the kernel "
                         "only, so it also works with --k2-impl shared); less memory per token, same values")
    ap.add_argument("--gdn-impl", choices=("ref", "fast_ref"), default="ref",
                    help="only with --kernel ref: 'fast_ref' = gdn_fast_ref.py, the reference kernel's math with ~10x fewer device tasks "
                         "(fp32-rounding-level identical, test_gdn_fast_ref.py); 'ref' = transformers' torch_chunk_gated_delta_rule")
    ap.add_argument("--grad-ckpt", action="store_true")
    ap.add_argument("--micro-tokens", type=int, default=12000, help="max padded tokens per forward/backward chunk")
    ap.add_argument("--k2-impl", choices=("rows", "shared"), default="rows",
                    help="K2 loss computation: rows = one row per option (reference form), shared = prompt forwarded once (k2_shared.py; "
                         "same loss, needs no --grad-ckpt; LoRA-dropout mask on the prompt is then shared by the question's options)")
    ap.add_argument("--chunk-overhead", type=int, default=2000,
                    help="K1 chunk planner: fixed cost of one extra forward/backward in padded-token equivalents (plan_chunks)")
    ap.add_argument("--k2-rows", type=int, default=96, help="shared K2: max multi-token option rows per option pass / per group")
    ap.add_argument("--full-logits", action="store_true", help="comparison only: LM head over all positions instead of gathered ones")
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--save-every", type=int, default=200)
    ap.add_argument("--drop-state", action="store_true", help="K1-QO: state removed from every training prompt")
    ap.add_argument("--symbol-file", default=None, help="K3: frozen symbol data (sha256 checked)")
    ap.add_argument("--symbol-n", type=int, default=6675)
    ap.add_argument("--limit-rows", type=int, default=0, help="tests: first N converted train rows only")
    ap.add_argument("--no-merge", action="store_true")
    ap.add_argument("--full-ft", action="store_true",
                    help="K4 (prereg §7.5): train every parameter, no LoRA; lr must be 1e-5 or 2e-5; fp32 master weights + bf16 autocast; "
                         "0.8B on one chip only; no dropout (the recipe's 0.05 is LoRA-module dropout, there is none to apply)")
    ap.add_argument("--allow-any-lr", action="store_true", help="tests only: lift the K4 lr guard")
    ap.add_argument("--device", default="npu:0")
    ap.add_argument("--procs-on-chip", type=int, default=1,
                    help="how many independent training processes share this run's chip (information for the throughput lines: the "
                         "per-process rate is multiplied by it to give the per-chip-equivalent rate, assuming equal shares)")
    ap.add_argument("--perf-window", type=int, default=20, help="steps in the windowed throughput of heartbeat.log / perf.json")
    ap.add_argument("--perf-every", type=int, default=10, help="rewrite perf.json every N steps")
    return ap.parse_args(argv)


def seed_step(torch, seed, step):
    s = seed * 1000003 + step
    random.seed(s)
    torch.manual_seed(s)
    try:
        torch.npu.manual_seed_all(s)
    except Exception:  # noqa: BLE001
        pass


class Perf:
    """Windowed per-chip throughput for heartbeat.log / progress.log, and perf.json with the run's own early baseline.

    Rates are sums over the window (total tokens / total step seconds), not means of per-step rates. The chip count is 1 (one NPU per
    run); with --procs-on-chip K the process shares that chip with K-1 others and the per-chip-equivalent rate is K x the process rate
    (equal shares assumed; the true per-chip total is the sum of the K runs' rates). The baseline is the same aggregate over steps
    BASE_LO..BASE_HI of this run, frozen the first time step BASE_HI is passed and kept across resumes (read back from perf.json), so
    a later slowdown shows as ratio_to_baseline < 1.
    """
    BASE_LO, BASE_HI = 20, 120

    def __init__(self, out, window, procs, chips=1):
        self.path = os.path.join(out, "perf.json")
        self.window, self.procs, self.chips = window, max(1, procs), chips
        self.recent = []          # (tokens, questions, seconds) of the last `window` steps
        self.base_acc = [0, 0, 0.0, 0]       # tokens, questions, seconds, steps seen in [BASE_LO, BASE_HI]
        self.baseline = None
        try:
            old = json.load(open(self.path))
            self.baseline = old.get("baseline")
        except (OSError, ValueError):
            pass

    def add(self, step, tokens, questions, dt):
        self.recent.append((tokens, questions, dt))
        del self.recent[:-self.window]
        if self.baseline is None and self.BASE_LO <= step <= self.BASE_HI:
            self.base_acc[0] += tokens; self.base_acc[1] += questions; self.base_acc[2] += dt; self.base_acc[3] += 1
            if step == self.BASE_HI:
                t, q, s, n = self.base_acc
                self.baseline = {"steps": [self.BASE_LO, self.BASE_HI], "n_steps": n, "tok_s_proc": t / s, "q_s_proc": q / s,
                                 "step_s_mean": s / n}

    def window_rates(self):
        t = sum(x[0] for x in self.recent); q = sum(x[1] for x in self.recent); s = sum(x[2] for x in self.recent)
        if s <= 0:
            return None
        return {"tok_s_proc": t / s, "q_s_proc": q / s, "step_s_mean": s / len(self.recent), "n_steps": len(self.recent)}

    def fields(self, reserved_gib):
        """heartbeat/progress fields; only key=number pairs, no 'a/b' fractions (tools/watchdog.py reads N/M and done= first)."""
        w = self.window_rates()
        if w is None:
            return ""
        k = self.procs
        return (f"tok_s_chip_w{self.window}={w['tok_s_proc'] * k:.0f} q_s_chip_w{self.window}={w['q_s_proc'] * k:.2f} "
                f"chips={self.chips} procs_on_chip={k} reserved_gib={reserved_gib:.1f}")

    def write(self, step, total, reserved_gib, extra=None):
        w = self.window_rates()
        if w is None:
            return
        k = self.procs
        d = {"utc": utc(), "step": step, "total_steps": total, "chips": self.chips, "procs_on_chip": k,
             "window_steps": w["n_steps"], "reserved_gib_peak": reserved_gib,
             "window": {"tok_s_proc": w["tok_s_proc"], "q_s_proc": w["q_s_proc"], "step_s_mean": w["step_s_mean"],
                        "tok_s_chip_equiv": w["tok_s_proc"] * k, "q_s_chip_equiv": w["q_s_proc"] * k},
             "baseline": self.baseline, "ratio_to_baseline": None,
             "note": "per-chip-equivalent = per-process rate x procs_on_chip (equal shares assumed); ratio = window q_s_proc / baseline "
                     "q_s_proc (baseline = aggregate over steps 20-120 of this run, frozen after step 120); a window of 20 steps has "
                     "about +-15% sampling noise from the question-length mix, so flag a drop only below ~0.7"}
        if self.baseline:
            d["ratio_to_baseline"] = {"q_s": w["q_s_proc"] / self.baseline["q_s_proc"], "tok_s": w["tok_s_proc"] / self.baseline["tok_s_proc"]}
        if extra:
            d.update(extra)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f, indent=1)
        os.replace(tmp, self.path)


def run(args):
    import torch
    import torch_npu  # noqa: F401
    import transformers
    from torch.optim.lr_scheduler import OneCycleLR

    os.makedirs(args.out, exist_ok=True)
    device = args.device
    tok = transformers.AutoTokenizer.from_pretrained(args.model_path)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else 0
    data = Data(args)
    spe = data.steps_per_epoch()
    total = args.total_steps or args.epochs * spe
    if args.k2_impl == "shared" and (args.grad_ckpt or args.arm != "k2"):
        raise SystemExit("--k2-impl shared is for --arm k2 and needs the model without --grad-ckpt")
    if args.full_ft:
        if args.lr not in K4_LRS and not args.allow_any_lr:
            raise SystemExit(f"K4 lr must be one of {K4_LRS} (prereg §7.5), got {args.lr}")
        if "0.8B" not in args.model_path and not args.allow_any_lr:
            raise SystemExit("K4 is registered at 0.8B only (§14.5 item 4)")
        pm, trainable, n_pairs = build_full_model(args, torch)
        core = pm
    else:
        pm, trainable, n_pairs = build_model(args, torch)
        core = pm.base_model.model
    pm.to(device)
    pm.train()
    params = [p for _, p in trainable]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.01)
    sched = OneCycleLR(opt, max_lr=args.lr, total_steps=total, pct_start=0.1)

    step = 0
    ck = latest_ckpt(args.out)
    if ck:
        st = torch.load(ck, map_location="cpu", weights_only=False)
        with torch.no_grad():
            for n, p in trainable:
                p.copy_(st["lora"][n].to(p.device, p.dtype))
        opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"])
        step = st["step"]
        print(f"[train_r3] resumed from {ck} at step {step}", flush=True)

    loss_path = os.path.join(args.out, "losses.jsonl")
    if os.path.exists(loss_path):          # drop lines after the checkpoint we resumed from
        keep = [l for l in open(loss_path) if l.strip() and json.loads(l)["step"] <= step]
        open(loss_path, "w").writelines(keep)
    manifest = {"utc": utc(), "args": vars(args), "arm": args.arm, "total_steps": total, "steps_per_epoch": spe,
                "base_questions_per_epoch": len(data.rows) + len(data.sym), "lora_pairs": n_pairs,
                "trainable_params": sum(p.numel() for p in params), "kernel": args.kernel, "chips": 1, "full_ft": bool(args.full_ft),
                "param_dtype": str(params[0].dtype), "n_param_tensors": len(params),
                "pytorch_npu_alloc_conf": os.environ.get("PYTORCH_NPU_ALLOC_CONF"),
                "task_queue_enable": os.environ.get("TASK_QUEUE_ENABLE"),
                "train_file": {"path": TRAIN_FILE, "sha256": file_sha256(TRAIN_FILE)},
                "symbol": ({"path": args.symbol_file, "sha256": SYMBOL_SHA256, "rows": len(data.sym),
                            "row_key": "group_id|rec_index|aug_index (0x1f separated), sha256('k3-mix-v1'+key) ascending"}
                           if args.symbol_file else None),
                "code_sha256": {n: file_sha256(os.path.join(HERE, n)) for n in
                                ("train_r3.py", "build_kev_sft.py", "kev_aug.py", "gdn_fast_ref.py", "k2_shared.py")},
                "prompt_py_sha256": file_sha256(os.path.join(R0_CODE, "prompt.py")),
                "model_path": args.model_path,
                "model_revision_file": (open(os.path.join(args.model_path, ".complete")).read().split()[0]
                                        if os.path.exists(os.path.join(args.model_path, ".complete")) else None),
                "transformers": transformers.__version__, "torch": torch.__version__}
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    prog = open(os.path.join(args.out, "progress.log"), "a", buffering=1)
    lossf = open(loss_path, "a", buffering=1)
    counters = {}
    t_start, steps_run, last_beat = time.time(), 0, 0.0
    peak_reserved = 0
    perf = Perf(args.out, args.perf_window, args.procs_on_chip)
    print(f"[train_r3] arm={args.arm} seed={args.seed} total_steps={total} steps/epoch={spe} lora_pairs={n_pairs} "
          f"kernel={args.kernel} grad_ckpt={args.grad_ckpt} start_step={step} "
          f"PYTORCH_NPU_ALLOC_CONF={os.environ.get('PYTORCH_NPU_ALLOC_CONF')!r}", flush=True)

    while step < total:
        epoch, units = data.step_units(step)
        seed_step(torch, args.seed, step)
        torch.npu.synchronize()
        t0 = time.time()
        opt.zero_grad(set_to_none=True)
        loss, stats = step_loss(torch, core, tok, units, args.arm, device, pad_id, args.max_len, args.micro_tokens, counters,
                                full_logits=args.full_logits, k2_impl=args.k2_impl, k2_rows=args.k2_rows,
                                chunk_overhead=args.chunk_overhead)
        gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
        if not (math.isfinite(loss) and math.isfinite(gn)):
            raise SystemExit(f"non-finite loss/grad norm at step {step + 1} (loss {loss}, grad norm {gn}); the optimizer step was NOT taken")
        opt.step()
        lr_used = opt.param_groups[0]["lr"]
        sched.step()
        torch.npu.synchronize()
        dt = time.time() - t0
        step += 1
        steps_run += 1
        peak_reserved = max(peak_reserved, torch.npu.max_memory_reserved())
        rec = {"step": step, "epoch": epoch, "loss": loss, "lr": lr_used, "grad_norm": gn, "step_s": dt,
               "base_questions": len(units), "examples": stats["rows"], "tokens": stats["tokens"], "chunks": stats.get("chunks", 0),
               "padded_tokens": stats.get("padded_tokens", 0),
               "tok_s_chip": stats["tokens"] / dt, "q_s_chip": len(units) / dt, "t_end": time.time()}
        lossf.write(json.dumps(rec) + "\n")
        perf.add(step, stats["tokens"], len(units), dt)
        now = time.time()
        if now - last_beat >= 30 or step == total or step % 10 == 0:
            res_gib = peak_reserved / 2**30
            pf = perf.fields(res_gib)
            prog.write(f"{utc()} step {step}/{total} epoch {epoch} loss {loss:.4f} lr {lr_used:.2e} gnorm {gn:.2f} "
                       f"step_s {dt:.2f} tok/s/chip {rec['tok_s_chip']:.0f} q/s/chip {rec['q_s_chip']:.2f} chips 1 "
                       f"reserved_gib {res_gib:.1f} | {pf}\n")
            last_beat = now
            with open(os.path.join(args.out, "heartbeat.log"), "a") as hb:      # progress line for tools/watchdog.py
                hb.write(f"{utc()} step done={step} total={total} loss={loss:.4f} step_s={dt:.2f} {pf}\n")
        if step % args.perf_every == 0 or step == total:
            perf.write(step, total, peak_reserved / 2**30, {"arm": args.arm, "seed": args.seed, "kernel": args.kernel,
                                                          "gdn_impl": args.gdn_impl, "micro_tokens": args.micro_tokens, "full_ft": bool(args.full_ft),
                                                          "lr": args.lr})
        if step % 10 == 0:
            print(f"step {step}/{total} loss {loss:.4f} step_s {dt:.2f} tok/s/chip {rec['tok_s_chip']:.0f}", flush=True)
        if args.save_every and step % args.save_every == 0 and step < total:
            save_ckpt(torch, args.out, step, trainable, opt, sched)
        if args.stop_after and steps_run >= args.stop_after:
            save_ckpt(torch, args.out, step, trainable, opt, sched)
            print(f"[train_r3] stopped after {steps_run} steps at step {step} (checkpoint written)", flush=True)
            return {"step": step, "stopped": True}

    save_ckpt(torch, args.out, step, trainable, opt, sched)
    summary = {"steps_run_this_invocation": steps_run, "wall_s": time.time() - t_start, "peak_reserved_gib": peak_reserved / 2**30,
               "truncated_examples": counters.get("truncated", 0), "final_step": step}
    if args.full_ft and args.no_merge:
        pass                  # tests/benchmarks only: no export (the model of record is written without --no-merge)
    elif args.full_ft:          # K4: the model of record is the full fp32 weights; hashed per file (prereg §8.4)
        probe = []
        for u in data.step_units(0)[1][:4]:
            p_, a_ = encode_example(tok, u[0], args.max_len, {})
            probe.append(p_ + a_)
        summary["full_model"] = save_full_model(torch, pm, args, tok, os.path.join(args.out, "model_fp32"), probe, device)
        print("[train_r3] full model saved:", json.dumps({k: v for k, v in summary["full_model"].items() if k != "sha256"}), flush=True)
    else:
        pm.save_pretrained(os.path.join(args.out, "adapter"))
    if not args.no_merge and not args.full_ft:     # fp32 export only; the model of record is base + adapter
        probe_units = data.step_units(0)[1][:4]
        probe = []
        for u in probe_units:
            p, a = encode_example(tok, u[0], args.max_len, {})
            probe.append(p + a)
        summary["merge"] = fold_and_save(torch, pm, args, tok, os.path.join(args.out, "export_fp32"), probe, device)
        print("[train_r3] merge check:", json.dumps(summary["merge"]), flush=True)
    manifest["summary"] = summary
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print("[train_r3] finished:", json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    run(parse_args())
