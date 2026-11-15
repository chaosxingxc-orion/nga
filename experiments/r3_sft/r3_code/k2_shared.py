"""K2 option-restricted loss with the question's prompt forwarded ONCE (prompt sharing), gradients flowing through both passes.

The unshared form (train_r3.step_loss, arm k2) forwards ``prompt + option`` as a separate row for every option of a question: mean 9.8
options and 224 prompt tokens, i.e. 72.6k tokens per optimizer step against ~3.0k when the prompt is shared (r3_runs/k2stats). Here
  pass 1 (prompt pass): the prompts of a group of questions, LEFT-padded in one batch, with explicit position ids so that every real token
      has the position it has in the unpadded row; the layers record, per question, the state the options must continue from:
      attention layers: the keys/values (post q/k-norm and rotary); gated-delta-rule layers: the last 3 pre-conv columns (conv state)
      and the final recurrent state. Left padding is exact for both layer types (pad columns are masked in attention; their hidden
      states are zeroed by apply_mask_to_padding_states, so the zero initial state stays zero through them). The final prompt position
      gives the distribution of every option's FIRST token.
  pass 2 (option pass): the remaining tokens of every multi-token option (c_0 .. c_{l-2}, right-padded to >= 2 columns) as one batch of
      rows, each continuing from its question's recorded state (index_select over the question axis, so the state gradient sums over the
      question's options). Single-token options need no row.
s_i = log p(c_0 | prompt) + sum_j log p(c_j | prompt, c_<j) is identical to the unshared row's summed identifier log-prob; the loss is
-log softmax(s)_gold. Nothing but the way it is computed changes, so under dropout the prompt-side LoRA-dropout mask is shared by a
question's options (in the unshared form each option row draws its own).

Mechanism: ``PrefixCache`` / ``ReplayCache`` implement the few methods transformers' Qwen3_5 layers call on a Cache
(has_previous_state, layers[i].conv_states/recurrent_states, update_conv_state, update_recurrent_state, update). Unlike transformers'
DynamicCache they keep the autograd graph. They are ignored under gradient checkpointing (the layer drops past_key_values), so the
shared path requires the model WITHOUT --grad-ckpt (asserted).
"""


class _Store:
    def __init__(self):
        self.conv_states = [None]
        self.recurrent_states = [None]


class PrefixCache:
    """Record mode: collects the per-layer state of the prompt pass (graph-attached tensors)."""

    def __init__(self, n_layers):
        self.layers = [_Store() for _ in range(n_layers)]
        self.kv = [None] * n_layers

    def has_previous_state(self, i):
        return False

    def update_conv_state(self, s, i, **kw):
        self.layers[i].conv_states[0] = s
        return s

    def update_recurrent_state(self, s, i, **kw):
        self.layers[i].recurrent_states[0] = s
        return s

    def update(self, k, v, i, *a, **kw):
        self.kv[i] = (k, v)
        return k, v

    def get_seq_length(self, *a, **kw):
        return 0

    def expand(self, rows):
        """A ReplayCache whose row r continues from prompt rows[r] (index_select keeps the graph)."""
        return ReplayCache(self, rows)


class ReplayCache:
    def __init__(self, base, rows):
        self.layers = []
        for st in base.layers:
            e = _Store()
            if st.conv_states[0] is not None:
                e.conv_states[0] = st.conv_states[0].index_select(0, rows)
                e.recurrent_states[0] = st.recurrent_states[0].index_select(0, rows)
            self.layers.append(e)
        self.kv = [None if kv is None else (kv[0].index_select(0, rows), kv[1].index_select(0, rows)) for kv in base.kv]

    def has_previous_state(self, i):
        return True

    def update_conv_state(self, s, i, **kw):
        return s            # the option pass never needs its own final state

    def update_recurrent_state(self, s, i, **kw):
        return s

    def update(self, k, v, i, *a, **kw):
        import torch
        pk, pv = self.kv[i]
        return torch.cat([pk, k], dim=2), torch.cat([pv, v], dim=2)

    def get_seq_length(self, *a, **kw):
        return 0


TIMING = None      # profile_step.py sets a dict here to collect synchronised wall time per phase


def _tick(torch, key, t0):
    import time
    if TIMING is None:
        return 0.0
    torch.npu.synchronize()
    t1 = time.time()
    if t0:
        TIMING[key] = TIMING.get(key, 0.0) + t1 - t0
    return t1


def _assert_no_ckpt(core):
    for layer in core.model.layers:
        if getattr(layer, "gradient_checkpointing", False) and core.training:
            raise RuntimeError("k2_shared needs the model without gradient checkpointing (the layer drops past_key_values under it)")


def group_scores(torch, core, items, pad_id, device, autocast=True, max_option_rows=96):
    """items: list of (prompt_ids, cand_ids_list). Returns a list (one per item) of 1-D tensors s (differentiable): the summed
    identifier log-probs of that question's options, in option order. One prompt pass + ceil(rows/max_option_rows) option passes."""
    _assert_no_ckpt(core)
    t0 = _tick(torch, "", 0)
    Q = len(items)
    n_layers = len(core.model.layers)
    plen = [len(p) for p, _ in items]
    P = max(plen)
    ids = torch.full((Q, P), pad_id, dtype=torch.long)
    real = torch.zeros((Q, P), dtype=torch.bool)
    pos = torch.zeros((Q, P), dtype=torch.long)
    for q, (p, _) in enumerate(items):
        ids[q, P - len(p):] = torch.tensor(p, dtype=torch.long)
        real[q, P - len(p):] = True
        pos[q, P - len(p):] = torch.arange(len(p))
    ids, real, pos = ids.to(device), real.to(device), pos.to(device)
    t0 = _tick(torch, "host_prep_prompt", t0)
    eye = torch.eye(P, dtype=torch.bool, device=device)
    causal = torch.tril(torch.ones(P, P, dtype=torch.bool, device=device))
    m_prompt = ((causal[None] & real[:, None, :]) | eye[None])[:, None]               # [Q,1,P,P]; pad queries see themselves (no NaN rows)
    ctx = torch.autocast(device_type="npu", dtype=torch.bfloat16) if autocast else _Null()
    cache = PrefixCache(n_layers)
    with ctx:
        h = core.model(input_ids=ids, attention_mask={"full_attention": m_prompt, "linear_attention": real.long()},
                       position_ids=pos, past_key_values=cache, use_cache=True).last_hidden_state
        logp_last = torch.log_softmax(core.lm_head(h[:, -1]).float(), dim=-1)           # [Q, V]: distribution of every option's first token
    t0 = _tick(torch, "prompt_fwd", t0)
    # flat option axis: f = offset[q] + i
    offs, f = [], 0
    for _, cands in items:
        offs.append(f)
        f += len(cands)
    F_total = f
    q_of = torch.tensor([q for q, (_, cands) in enumerate(items) for _ in cands], device=device)
    c0_of = torch.tensor([c[0] for _, cands in items for c in cands], device=device)
    s_flat = logp_last[q_of, c0_of]                                                    # first option token, from the prompt's last position
    # the remaining option tokens c_1..c_{l-1} are predicted from inputs c_0..c_{l-2}: one row per multi-token option
    rows = [(q, i) for q, (_, cands) in enumerate(items) for i, c in enumerate(cands) if len(c) >= 2]
    tail = torch.zeros(F_total, device=device, dtype=s_flat.dtype)
    for lo in range(0, len(rows), max_option_rows):
        sub = rows[lo:lo + max_option_rows]
        R = len(sub)
        Lw = max(2, max(len(items[q][1][i]) - 1 for q, i in sub))
        oid = torch.full((R, Lw), pad_id, dtype=torch.long)
        omask = torch.zeros((R, Lw), dtype=torch.long)
        bi, ti, tg, flat_idx = [], [], [], []
        for r, (q, i) in enumerate(sub):
            c = items[q][1][i]
            oid[r, :len(c) - 1] = torch.tensor(c[:-1], dtype=torch.long)
            omask[r, :len(c) - 1] = 1
            for j in range(len(c) - 1):
                bi.append(r); ti.append(j); tg.append(c[j + 1]); flat_idx.append(offs[q] + i)
        qidx = torch.tensor([q for q, _ in sub], device=device)
        oid, omask = oid.to(device), omask.to(device)
        opos = (torch.tensor([plen[q] for q, _ in sub], device=device)[:, None] + torch.arange(Lw, device=device)[None, :])
        pre = real.index_select(0, qidx)[:, None, None, :].expand(R, 1, Lw, P)         # prompt keys that are real
        opt_causal = torch.tril(torch.ones(Lw, Lw, dtype=torch.bool, device=device))[None, None].expand(R, 1, Lw, Lw)
        m_opt = torch.cat([pre, opt_causal], dim=-1)                                    # [R,1,Lw,P+Lw]
        t0 = _tick(torch, "host_prep_opt", t0)
        rc = cache.expand(qidx)
        t0 = _tick(torch, "expand_states", t0)
        with ctx:
            ho = core.model(input_ids=oid, attention_mask={"full_attention": m_opt, "linear_attention": omask},
                            position_ids=opos, past_key_values=rc, use_cache=True).last_hidden_state
            lg = core.lm_head(ho[torch.tensor(bi, device=device), torch.tensor(ti, device=device)])
        lp = torch.log_softmax(lg.float(), dim=-1)
        tl = lp.gather(1, torch.tensor(tg, device=device)[:, None])[:, 0]
        tail = tail.index_add(0, torch.tensor(flat_idx, device=device), tl)
        del rc, ho, lg, lp
        t0 = _tick(torch, "opt_fwd", t0)
    s_flat = s_flat + tail
    return [s_flat[offs[q]:offs[q] + len(cands)] for q, (_, cands) in enumerate(items)]


class _Null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
