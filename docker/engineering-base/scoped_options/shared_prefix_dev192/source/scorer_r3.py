"""R3 scorer (R3-SFT-PREREG section 14.2, amendment 2): admissible, fast option log-probability readout.

Every readout is the summed log-probability of the option's identifier tokens given the R0 prompt (`prompt.build_prompt`,
render `record_name`, raw completion, no chat template, prompt and identifier tokenized separately and concatenated), exactly the
quantity of `r0_code/scorer.py` `HFScorer`. What differs is only HOW the same quantity is computed. Modes of `R3Scorer.score_raw`:

  exact     reference layout, bit-identical to HFScorer(token_budget=1): one row per candidate, one forward each, no padding.
  eqlen     the same rows batched only with rows of EXACTLY equal length (no padding): the bf16 batch-composition floor probe.
  rightpad  one row per candidate, RIGHT padded, attention mask passed, LM head only at the scored positions (the eval_r3 candidate).
  fast      shared prompt: each question's prompt is run once (batched over questions, LEFT padded with explicit position ids
            and a padding mask, which is exact for this hybrid model, see below); the options are continued from the cached
            attention KV and gated-delta-rule conv/recurrent state, batched over all options of the batch.
  r0        the published R0 behaviour (cross-question batching + LEFT padding without position ids): NOT admissible, kept only to
            measure the defect.

Why left padding with position ids is exact for Qwen3.5 (and the R0 scorer's left padding is not): the gated-delta-rule layers zero
the hidden states of padded positions before the projections (`apply_mask_to_padding_states`), so q = k = v = 0 there, the recurrent
state stays 0 and the causal conv sees zeros exactly as it would for an unpadded row; the full-attention layers mask padded keys. The
only quantity that still depends on the pad length is RoPE, and `position_ids = cumsum(mask) - 1` removes that. R0 passed no
position ids. The unit tests check the equality in fp32, where rounding is ~1e-5, and the bf16 differences against the measured floor.

Admissibility is a measurement (see r3_runs/scorer_r3/), not a property of this file: a mode may be used for a reported number only
when its max |delta score| and argmax disagreement against `exact` are within the same-sample bf16 batch-composition floor.

Test partitions: `guard_split` is retired and refuses every test partition; the one test lock is testlock_r3 (prereg section 8.4).
"""
import copy
import hashlib
import json
import os
import sys
import time
from collections import Counter, namedtuple

R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
RUN_ROOT = "/mnt/cephfs/xingchao/experiments/jev/r3_runs"
if R0_CODE not in sys.path:
    sys.path.insert(0, R0_CODE)
import prompt as prompt_mod  # noqa: E402

Enc = namedtuple("Enc", "prefix cands")   # prefix token ids, list of candidate token-id lists
MODES = ("exact", "eqlen", "rightpad", "fast", "r0")


# ---- test lock -----------------------------------------------------------------------------------------------------

def guard_split(split, model_ids=None, run_root=RUN_ROOT, partition_tag=None):
    """RETIRED as a lock (prereg 8.4). The only test lock is testlock_r3 (authorize_test_read -> TestTicket -> core_r3.load_partition):
    model identity by sha256, FINAL.json naming by path + sha256, one read per partition, TEST-READS.log appended under flock. This
    function used to match names by string and the log by substring; two implementations of one lock would eventually be bypassed
    through the weaker one, so it now refuses every test partition outright and passes the others. Returns True for a non-test split."""
    if split == "test":
        raise SystemExit("prereg 8.4: scorer_r3.guard_split is retired and refuses every test partition; "
                         "a test read goes through testlock_r3 (python3 -P eval_r3.py --full ... --partitions ...:test)")
    return True


# ---- helpers -------------------------------------------------------------------------------------------------------

def encode_rows(tok, rows, render="record_name"):
    out = []
    for r in rows:
        p = prompt_mod.build_prompt(r, render)
        pre = tok(p.text, add_special_tokens=False)["input_ids"]
        cs = [tok(c, add_special_tokens=False)["input_ids"] for c in p.candidates]
        if any(len(c) == 0 for c in cs):
            raise ValueError("a level identifier tokenized to nothing")
        out.append(Enc(pre, cs))
    return out


def dedup_enc(enc):
    """Duplicate-candidate rule (R3 prereg amendment 6): candidates of one question with IDENTICAL token sequences are one candidate.

    Returns (reduced, maps, n_dup_questions, n_removed). `reduced` has, per question, only the first occurrence of each distinct token
    sequence (the same Enc objects are returned unchanged when a question has no duplicate); maps[i][j] is the index in reduced[i].cands of
    original candidate j. After scoring `reduced` in any layout, expand with expand_scores: duplicates receive the SAME float object, so
    they are equal bit for bit in every layout, and an argmax between them is decided by the tie rule alone, never by which batch a copy
    landed in."""
    reduced, maps, nq, nr = [], [], 0, 0
    for e in enc:
        first, keep, m = {}, [], []
        for c in e.cands:
            t = tuple(c)
            if t not in first:
                first[t] = len(keep)
                keep.append(c)
            m.append(first[t])
        if len(keep) == len(e.cands):
            reduced.append(e)
        else:
            reduced.append(Enc(e.prefix, keep))
            nq += 1
            nr += len(e.cands) - len(keep)
        maps.append(m)
    return reduced, maps, nq, nr


def expand_scores(scores, maps):
    return [[row[k] for k in m] for row, m in zip(scores, maps)]


def dup_questions(enc):
    """Indices of questions with at least two candidates of identical token sequence, with their index groups."""
    out = {}
    for i, e in enumerate(enc):
        g = {}
        for j, c in enumerate(e.cands):
            g.setdefault(tuple(c), []).append(j)
        gg = [v for v in g.values() if len(v) > 1]
        if gg:
            out[i] = gg
    return out


def load_model(model_path, adapter=None, device="npu", dtype="bfloat16"):
    """(causal LM, tokenizer). With `adapter`, the LoRA tensors stay UNMERGED in the layers (the model of record)."""
    import torch
    import transformers
    if device.startswith("npu"):
        import torch_npu  # noqa: F401
    tok = transformers.AutoTokenizer.from_pretrained(model_path)
    tdtype = getattr(torch, dtype)
    lm = transformers.AutoModelForCausalLM.from_pretrained(model_path, dtype=tdtype)
    if adapter:
        from peft import PeftModel
        pm = PeftModel.from_pretrained(lm, adapter)            # LoRA tensors fp32 (peft default); never merged
        n_lora = sum(1 for n, _ in pm.named_parameters() if "lora_A" in n)
        assert n_lora > 0, "adapter has no LoRA tensors"
        lm = pm.base_model.model                                # the causal LM with the LoRA layers in place
        if dtype == "float32":
            lm = lm.float()
    return lm.to(device).eval(), tok


def _gather_cache(cache, idx):
    """A new cache whose batch rows are `cache` rows `idx` (repeats allowed). The source cache is left untouched."""
    new = copy.copy(cache)
    new.layers = []
    for l in cache.layers:
        n = copy.copy(l)
        for attr in ("conv_states", "recurrent_states"):
            if hasattr(l, attr):
                setattr(n, attr, {k: (v.index_select(0, idx) if v is not None else None) for k, v in getattr(l, attr).items()})
        if getattr(l, "keys", None) is not None and getattr(l, "keys").numel() > 0:
            n.keys = l.keys.index_select(0, idx)
            n.values = l.values.index_select(0, idx)
        new.layers.append(n)
    return new


class R3Scorer:
    def __init__(self, model_path, adapter=None, device="npu", dtype="bfloat16", token_budget=32768, max_prefix_rows=128,
                 max_cont_rows=256, head_fp32=False, model=None, tokenizer=None, render="record_name"):
        self.model_path, self.adapter, self.device, self.dtype = model_path, adapter, device, dtype
        self.token_budget, self.max_prefix_rows, self.max_cont_rows = token_budget, max_prefix_rows, max_cont_rows
        self.head_fp32 = head_fp32
        self.render = render
        self.lm, self.tok = model, tokenizer
        self.stats = Counter()
        self._w32 = None

    # ---- loading / low level ----
    def load(self):
        if self.lm is None:
            self.lm, self.tok = load_model(self.model_path, self.adapter, self.device, self.dtype)
        self.pad_id = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0
        return self

    def encode(self, rows):
        self.load()
        return encode_rows(self.tok, rows, self.render)

    def _sync(self):
        import torch
        if self.device.startswith("npu"):
            torch.npu.synchronize()

    def _token_logprobs(self, h, bi, ti, tg):
        """Log-prob of token tg[k] at hidden state h[bi[k], ti[k]] (LM head only at those positions). Returns a python float list."""
        import torch
        out = []
        bi_t = torch.tensor(bi, device=h.device)
        ti_t = torch.tensor(ti, device=h.device)
        tg_t = torch.tensor(tg, device=h.device)
        step = 512
        for s in range(0, len(bi), step):
            x = h[bi_t[s:s + step], ti_t[s:s + step]]
            if self.head_fp32:
                if self._w32 is None:
                    self._w32 = self.lm.lm_head.weight.float()
                logits = x.float() @ self._w32.t()
            else:
                logits = self.lm.lm_head(x)
            lp = torch.log_softmax(logits.float(), dim=-1)
            out.extend(lp.gather(1, tg_t[s:s + step, None])[:, 0].tolist())
        self.stats["head_positions"] += len(bi)
        return out

    # ---- public ----
    def score_raw(self, rows, mode="fast", **kw):
        """Summed identifier log-probability per level (pre-softmax), aligned with row['levels']."""
        enc = self.encode(rows)
        return self.score_enc(enc, mode, **kw)

    def score_enc(self, enc, mode="fast", dedup=True, **kw):
        """`dedup` (default on): the duplicate-candidate rule, see dedup_enc. It is never applied to mode "r0", which exists only to
        reproduce the published defective scorer."""
        import torch
        self.load()
        t0 = time.time()
        maps = None
        if dedup and mode != "r0":
            enc, maps, nq, nr = dedup_enc(enc)
            self.stats["dup_questions"] += nq
            self.stats["dup_candidates_removed"] += nr
        with torch.no_grad():
            fn = {"exact": self._exact, "eqlen": self._eqlen, "rightpad": self._rightpad, "fast": self._fast, "r0": self._r0}[mode]
            out = fn(enc, **kw)
        if maps is not None:
            out = expand_scores(out, maps)
        self._sync()
        self.stats[mode + "_s"] += time.time() - t0
        self.stats["items"] += len(maps) if maps is not None else len(enc)
        return out

    # ---- exact: HFScorer(token_budget=1) ----
    def _exact(self, enc):
        import torch
        out = [[0.0] * len(e.cands) for e in enc]
        for i, e in enumerate(enc):
            for j, c in enumerate(e.cands):
                toks = e.prefix + c
                n = len(c)
                keep = n + 1
                ids = torch.tensor([toks], dtype=torch.long, device=self.device)
                mask = torch.ones_like(ids)
                logits = self.lm(input_ids=ids, attention_mask=mask, use_cache=False, logits_to_keep=keep).logits
                logp = torch.log_softmax(logits[:, -keep:, :].float(), dim=-1)
                idx = [keep - 1 - n + q for q in range(n)]
                vals = logp[0, torch.tensor(idx, device=logp.device), torch.tensor(c, device=logp.device)].tolist()
                total = 0.0
                for v in vals:
                    total += v
                out[i][j] = total
                self.stats["forwards"] += 1
                self.stats["tokens"] += len(toks)
        return out

    def _flat_rows(self, enc):
        return [(i, j, e.prefix + c, len(c)) for i, e in enumerate(enc) for j, c in enumerate(e.cands)]

    def _score_flat_batch(self, batch, width, out, right_pad=True):
        """batch: list of (i, j, toks, n). Padded to `width` on the right (or exact when all equal), one forward, gather scored positions."""
        import torch
        ids = torch.full((len(batch), width), self.pad_id, dtype=torch.long)
        mask = torch.zeros((len(batch), width), dtype=torch.long)
        bi, ti, tg, own = [], [], [], []
        for r, (i, j, toks, n) in enumerate(batch):
            ids[r, :len(toks)] = torch.tensor(toks)
            mask[r, :len(toks)] = 1
            for q in range(len(toks) - n, len(toks)):
                bi.append(r)
                ti.append(q - 1)
                tg.append(toks[q])
                own.append((i, j))
        ids, mask = ids.to(self.device), mask.to(self.device)
        h = self.lm.model(input_ids=ids, attention_mask=mask, use_cache=False).last_hidden_state
        vals = self._token_logprobs(h, bi, ti, tg)
        # sequential python-float accumulation per candidate (same order as HFScorer)
        for (i, j), v in zip(own, vals):
            out[i][j] += v
        self.stats["forwards"] += 1
        self.stats["tokens"] += len(batch) * width
        self.stats["padded_tokens"] += len(batch) * width - sum(len(b[2]) for b in batch)

    def _eqlen(self, enc, max_rows=64, seed=None):
        rows = self._flat_rows(enc)
        out = [[0.0] * len(e.cands) for e in enc]
        by_len = {}
        for r in rows:
            by_len.setdefault(len(r[2]), []).append(r)
        lens = sorted(by_len)
        if seed is not None:
            import random
            random.Random(seed).shuffle(lens)
        for L in lens:
            grp = by_len[L]
            if seed is not None:
                import random
                random.Random(seed + L).shuffle(grp)
            for s in range(0, len(grp), max_rows):
                self._score_flat_batch(grp[s:s + max_rows], L, out)
        return out

    def _rightpad(self, enc, token_budget=None):
        budget = token_budget or self.token_budget
        rows = self._flat_rows(enc)
        out = [[0.0] * len(e.cands) for e in enc]
        order = sorted(range(len(rows)), key=lambda r: -len(rows[r][2]))
        pos = 0
        while pos < len(order):
            longest = len(rows[order[pos]][2])
            size = max(1, budget // longest)
            batch = [rows[r] for r in order[pos:pos + size]]
            pos += size
            self._score_flat_batch(batch, longest, out)
        return out

    # ---- r0: the published behaviour (defect), via the R0 scorer's own code path ----
    def _r0(self, enc, token_budget=16384):
        """Cross-question batching, rows sorted by length, LEFT padding, no position ids (r0_code/scorer.py lines 346-380)."""
        import torch
        rows = self._flat_rows(enc)
        out = [[0.0] * len(e.cands) for e in enc]
        order = sorted(range(len(rows)), key=lambda r: -len(rows[r][2]))
        pos = 0
        while pos < len(order):
            longest = len(rows[order[pos]][2])
            size = max(1, token_budget // longest)
            batch = [rows[r] for r in order[pos:pos + size]]
            pos += size
            width = max(len(b[2]) for b in batch)
            keep = max(b[3] for b in batch) + 1
            ids = torch.full((len(batch), width), self.pad_id, dtype=torch.long)
            mask = torch.zeros((len(batch), width), dtype=torch.long)
            for r, b in enumerate(batch):
                ids[r, width - len(b[2]):] = torch.tensor(b[2])
                mask[r, width - len(b[2]):] = 1
            ids, mask = ids.to(self.device), mask.to(self.device)
            logits = self.lm(input_ids=ids, attention_mask=mask, use_cache=False, logits_to_keep=keep).logits
            logp = torch.log_softmax(logits[:, -keep:, :].float(), dim=-1)
            for r, (i, j, toks, n) in enumerate(batch):
                total = 0.0
                for q in range(n):
                    t = keep - 1 - n + q
                    total += float(logp[r, t, toks[len(toks) - n + q]])
                out[i][j] = total
            self.stats["forwards"] += 1
            self.stats["tokens"] += len(batch) * width
        return out

    # ---- fast: shared prompt + cached continuation ----
    def _fast(self, enc, token_budget=None, max_prefix_rows=None, max_cont_rows=None):
        import torch
        budget = token_budget or self.token_budget
        max_prefix_rows = max_prefix_rows or self.max_prefix_rows
        max_cont_rows = max_cont_rows or self.max_cont_rows
        out = [[0.0] * len(e.cands) for e in enc]
        order = sorted(range(len(enc)), key=lambda i: len(enc[i].prefix))
        pos = 0
        while pos < len(order):
            # ascending length: the candidate batch's width is its last member; grow while it fits the budget
            size = 1
            while (pos + size < len(order) and size < max_prefix_rows
                   and (size + 1) * len(enc[order[pos + size]].prefix) <= budget):
                size += 1
            group = order[pos:pos + size]
            pos += size
            self._fast_group(enc, group, out, max_cont_rows)
        return out

    def _fast_group(self, enc, group, out, max_cont_rows):
        import torch
        B = len(group)
        W = max(len(enc[i].prefix) for i in group)
        ids = torch.full((B, W), self.pad_id, dtype=torch.long)
        mask = torch.zeros((B, W), dtype=torch.long)
        for b, i in enumerate(group):
            p = enc[i].prefix
            ids[b, W - len(p):] = torch.tensor(p)
            mask[b, W - len(p):] = 1
        ids, mask = ids.to(self.device), mask.to(self.device)
        position_ids = (mask.cumsum(1) - 1).clamp(min=0)
        res = self.lm.model(input_ids=ids, attention_mask=mask, position_ids=position_ids, use_cache=True)
        cache = res.past_key_values
        h = res.last_hidden_state                                   # [B, W, H]; left padding: position W-1 is every row's prefix end
        self.stats["forwards"] += 1
        self.stats["tokens"] += B * W
        self.stats["padded_tokens"] += B * W - sum(len(enc[i].prefix) for i in group)
        # first identifier token of every candidate: read at the prefix end
        bi, ti, tg, own = [], [], [], []
        cont = []                                                    # (b, i, j, cand ids)
        for b, i in enumerate(group):
            for j, c in enumerate(enc[i].cands):
                bi.append(b)
                ti.append(W - 1)
                tg.append(c[0])
                own.append((i, j))
                if len(c) > 1:
                    cont.append((b, i, j, c))
        vals = self._token_logprobs(h, bi, ti, tg)
        for (i, j), v in zip(own, vals):
            out[i][j] = v                                           # first token of the sum (r0 adds in the same order)
        del h
        if not cont:
            return
        n_real = mask.sum(1)                                        # [B]
        cont.sort(key=lambda r: -len(r[3]))
        for s in range(0, len(cont), max_cont_rows):
            part = cont[s:s + max_cont_rows]
            R = len(part)
            Lc = max(len(c) - 1 for _, _, _, c in part)
            cids = torch.full((R, Lc), self.pad_id, dtype=torch.long)
            for r, (_, _, _, c) in enumerate(part):
                cids[r, :len(c) - 1] = torch.tensor(c[:-1])
            owner = torch.tensor([b for b, _, _, _ in part], device=self.device)
            cids = cids.to(self.device)
            sub = _gather_cache(cache, owner)
            full_mask = torch.cat([mask.index_select(0, owner), torch.ones((R, Lc), dtype=mask.dtype, device=self.device)], dim=1)
            pids = n_real.index_select(0, owner)[:, None] + torch.arange(Lc, device=self.device)[None, :]
            hc = self.lm.model(input_ids=cids, attention_mask=full_mask, position_ids=pids, past_key_values=sub, use_cache=True).last_hidden_state
            self.stats["forwards"] += 1
            self.stats["tokens"] += R * Lc
            rb, rt, rg, rown = [], [], [], []
            for r, (_, i, j, c) in enumerate(part):
                for q in range(len(c) - 1):                         # hidden at continuation position q predicts c[q + 1]
                    rb.append(r)
                    rt.append(q)
                    rg.append(c[q + 1])
                    rown.append((i, j))
            cv = self._token_logprobs(hc, rb, rt, rg)
            for (i, j), v in zip(rown, cv):
                out[i][j] += v
            del hc, sub
