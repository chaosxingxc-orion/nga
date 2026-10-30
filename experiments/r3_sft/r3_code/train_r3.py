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

HERE = os.path.dirname(os.path.abspath(__file__))
R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
for _p in (HERE, R0_CODE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_kev_sft as B  # noqa: E402
import kev_aug  # noqa: E402

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
                "in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b", "out_proj"]
TRAIN_FILE = "/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl"
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
        with ctx:
            h = core.model(input_ids=ids, attention_mask=mask, use_cache=False).last_hidden_state
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


def step_loss(torch, core, tok, units, arm, device, pad_id, max_len, micro_tokens, counters, backward=True, full_logits=False,
              autocast=True):
    """One optimizer step's loss (and gradients if backward). Returns (loss value, stats dict)."""
    exs = [e for u in units for e in u]
    n_tok = 0
    if arm == "k1":
        enc = [encode_example(tok, e, max_len, counters) for e in exs]
        total_resp = sum(len(a) for _, a in enc)
        seqs = [p + a for p, a in enc]
        starts = [len(p) for p, _ in enc]
        n_tok = sum(len(s) for s in seqs)
        # chunk here (not inside row_logprob_sums) so each chunk's graph is freed right after its backward
        order = sorted(range(len(seqs)), key=lambda r: -len(seqs[r]))
        total, pos, n_chunks = 0.0, 0, 0
        while pos < len(order):
            n_chunks += 1
            size = max(1, micro_tokens // len(seqs[order[pos]]))
            chunk = order[pos:pos + size]
            pos += size
            sums = row_logprob_sums(torch, core, [seqs[r] for r in chunk], [starts[r] for r in chunk], pad_id, device,
                                    autocast=autocast, full_logits=full_logits)
            loss = -sums.sum() / total_resp
            if backward:
                loss.backward()
            total += float(loss.detach())
        return total, {"tokens": n_tok, "rows": len(exs), "resp_tokens": total_resp, "chunks": n_chunks}
    if arm == "k2":
        if any(e["candidates"] is None for e in exs):
            raise SystemExit("k2 needs a candidates list on every example; symbol rows (K3) have none -- K3 is supported on K1 only")
        total = 0.0
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


def build_model(args, torch):
    import transformers
    from peft import LoraConfig, TaskType, get_peft_model
    if args.kernel == "fla":
        os.environ["NGA_GDN_KERNEL"] = "fla"
        import nga_gdn_patch  # noqa: F401  (replaces the per-instance kernel callables; needs speedup/code + site_fla on PYTHONPATH)
    model = transformers.AutoModelForCausalLM.from_pretrained(args.model_path, dtype=torch.bfloat16, attn_implementation="sdpa")
    if args.grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    expected = sum(1 for n, m in model.named_modules()
                   if isinstance(m, torch.nn.Linear) and n.split(".")[-1] in LORA_TARGETS)
    torch.manual_seed(args.seed)                 # LoRA init (A ~ kaiming, B = 0)
    cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
                     target_modules=LORA_TARGETS, bias="none")
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
    ap.add_argument("--model-path", default="/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--total-steps", type=int, default=0, help="0 = epochs x steps/epoch (3,116 for K1); >0 compresses the schedule (smoke)")
    ap.add_argument("--stop-after", type=int, default=0, help="stop this invocation after N steps (tests, smoke); no final merge")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--expect-pairs", type=int, default=186, help="prereg-verified LoRA pair count at 0.8B (0 disables, for other sizes)")
    ap.add_argument("--kernel", choices=("ref", "fla"), default="ref")
    ap.add_argument("--grad-ckpt", action="store_true")
    ap.add_argument("--micro-tokens", type=int, default=12000, help="max padded tokens per forward/backward chunk")
    ap.add_argument("--full-logits", action="store_true", help="comparison only: LM head over all positions instead of gathered ones")
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--save-every", type=int, default=200)
    ap.add_argument("--drop-state", action="store_true", help="K1-QO: state removed from every training prompt")
    ap.add_argument("--symbol-file", default=None, help="K3: frozen symbol data (sha256 checked)")
    ap.add_argument("--symbol-n", type=int, default=6675)
    ap.add_argument("--limit-rows", type=int, default=0, help="tests: first N converted train rows only")
    ap.add_argument("--no-merge", action="store_true")
    ap.add_argument("--device", default="npu:0")
    return ap.parse_args(argv)


def seed_step(torch, seed, step):
    s = seed * 1000003 + step
    random.seed(s)
    torch.manual_seed(s)
    try:
        torch.npu.manual_seed_all(s)
    except Exception:  # noqa: BLE001
        pass


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
    pm, trainable, n_pairs = build_model(args, torch)
    pm.to(device)
    pm.train()
    core = pm.base_model.model
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
                "trainable_params": sum(p.numel() for p in params), "kernel": args.kernel, "chips": 1,
                "pytorch_npu_alloc_conf": os.environ.get("PYTORCH_NPU_ALLOC_CONF"),
                "train_file": {"path": TRAIN_FILE, "sha256": file_sha256(TRAIN_FILE)},
                "symbol": ({"path": args.symbol_file, "sha256": SYMBOL_SHA256, "rows": len(data.sym),
                            "row_key": "group_id|rec_index|aug_index (0x1f separated), sha256('k3-mix-v1'+key) ascending"}
                           if args.symbol_file else None),
                "code_sha256": {n: file_sha256(os.path.join(HERE, n)) for n in
                                ("train_r3.py", "build_kev_sft.py", "kev_aug.py")},
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
                                full_logits=args.full_logits)
        gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
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
               "tok_s_chip": stats["tokens"] / dt, "q_s_chip": len(units) / dt}
        lossf.write(json.dumps(rec) + "\n")
        now = time.time()
        if now - last_beat >= 30 or step == total or step % 10 == 0:
            prog.write(f"{utc()} step {step}/{total} epoch {epoch} loss {loss:.4f} lr {lr_used:.2e} gnorm {gn:.2f} "
                       f"step_s {dt:.2f} tok/s/chip {rec['tok_s_chip']:.0f} q/s/chip {rec['q_s_chip']:.2f} chips 1 "
                       f"reserved_gib {peak_reserved / 2**30:.1f}\n")
            last_beat = now
            with open(os.path.join(args.out, "heartbeat.log"), "a") as hb:      # progress line for tools/watchdog.py
                hb.write(f"{utc()} step done={step} total={total} loss={loss:.4f} step_s={dt:.2f}\n")
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
    pm.save_pretrained(os.path.join(args.out, "adapter"))
    if not args.no_merge:     # fp32 export only; the model of record is base + adapter
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
