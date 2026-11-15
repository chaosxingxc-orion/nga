"""Launch-count-reduced, mathematically identical form of transformers' ``torch_chunk_gated_delta_rule`` (the reference kernel).

Why: on Ascend the reference runs ~70,000 tiny device tasks per optimizer step (profile: r3_runs/eff/prof1), because
  (1) a 63-iteration python loop of in-place sliced updates inverts the unit-lower-triangular intra-chunk matrix, and
  (2) every chunk iteration indexes slices of big tensors and assigns into ``core_attn_out`` in place;
both are launch-bound (device busy ~21% of wall) and their backward replays every slice as ViewCopy/ZerosLike/Slice tasks.

What is the same: every quantity of the reference is computed in fp32 from the same inputs by the same formulas.
What differs, and nothing else:
  (1) the loop ``attn[i,:i] = row + (row*sub).sum(-2)`` solves T = (I - A)^-1 A for the strictly lower triangular A; since A is nilpotent
      (A^64 = 0 for a 64-chunk), (I - A)^-1 = (I + A)(I + A^2)(I + A^4)(I + A^8)(I + A^16)(I + A^32), six fp32 matmul products;
  (2) the chunk-independent factors (q k^T * decay, q * exp(g), k * exp(g_last - g), exp(g_last)) are computed once for all chunks,
      and the sequential state recurrence over chunks stays a loop, but collects its outputs in a list instead of writing in place.
The summation order inside the inverse differs, so results differ at fp32 rounding level (test_gdn_fast_ref.py measures it, in fp32
and in bf16 end to end, against the reference and against an fp64 gold). Use via ``--gdn-impl fast_ref`` in train_r3.py.
"""
import torch
import torch.nn.functional as F


def _l2norm(x, dim=-1, eps=1e-6):
    inv_norm = torch.rsqrt((x * x).sum(dim=dim, keepdim=True) + eps)      # identical to transformers' l2norm
    return x * inv_norm


def unit_lower_inverse(A, mode=None):
    """(I - A)^-1 for strictly lower triangular A [..., n, n], n a power of two.
    block  : recursive doubling, D_{2b} = D_b - D_b (N o M_b) D_b with N = I - A, M_b the sub-diagonal b-blocks of each 2b super-block
             (exact block-triangular inverse; log2(n) levels of two matmuls, stable like blocked forward substitution);
    solve  : torch.linalg.solve_triangular (unit diagonal);
    square : Neumann product (I+A)(I+A^2)(I+A^4)...  NOT stable on real data (ill-conditioned chunks), kept only for the record."""
    with torch.autocast(device_type=A.device.type, enabled=False):      # the reference inverts with fp32 elementwise ops, never bf16 matmuls
        return _unit_lower_inverse(A, mode or INVERSE_MODE)


def _unit_lower_inverse(A, mode):
    n = A.shape[-1]
    eye = torch.eye(n, dtype=A.dtype, device=A.device)
    if mode == "square":
        attn, P = eye + A, A
        for _ in range(max(1, (n - 1).bit_length()) - 1):
            P = P @ P
            attn = attn + attn @ P
        return attn
    N = eye - A
    if mode == "solve":
        return torch.linalg.solve_triangular(N, eye.expand_as(N), upper=False, unitriangular=True)
    return _BlockInverse.apply(A)


class _BlockInverse(torch.autograd.Function):
    """X = (I - A)^-1 by recursive doubling, with the analytic backward dL/dA = X^T (dL/dX) X^T (from dX = X dA X). Only X is saved, so
    neither the 2 log2(n) intermediate matmuls of the forward nor their backward replay exist (memory and device tasks); the gradient is
    the same mathematical quantity autograd would return through the doubling steps or through the reference's forward substitution."""

    @staticmethod
    def forward(ctx, A):
        n = A.shape[-1]
        eye = torch.eye(n, dtype=A.dtype, device=A.device)
        N = eye - A
        D = eye.expand_as(N)
        for M_sel in _sel_masks(n, A.device):
            D = D - D @ (N * M_sel) @ D
        ctx.save_for_backward(D)
        return D

    @staticmethod
    def backward(ctx, g):
        (X,) = ctx.saved_tensors
        Xt = X.transpose(-1, -2)
        return Xt @ g @ Xt


_SEL = {}


def _sel_masks(n, device):
    """For b = 1, 2, 4, ..: float mask of the sub-diagonal b-blocks of every 2b super-block (cached per (n, device))."""
    key = (n, str(device))
    if key not in _SEL:
        idx = torch.arange(n)
        out, b = [], 1
        while b < n:
            sel = ((idx[:, None] // (2 * b)) == (idx[None, :] // (2 * b))) & ((idx[:, None] // b) % 2 == 1) & ((idx[None, :] // b) % 2 == 0)
            out.append(sel.float().to(device))
            b *= 2
        _SEL[key] = out
    return _SEL[key]


INVERSE_MODE = "block"
SHORT_CHUNK = 16


def fast_chunk_gated_delta_rule(query, key, value, g, beta, chunk_size=64, initial_state=None, output_final_state=False,
                                use_qk_l2norm_in_kernel=False, mode=None, **kwargs):
    initial_dtype = query.dtype
    if query.shape[1] <= SHORT_CHUNK and chunk_size > SHORT_CHUNK:
        chunk_size = SHORT_CHUNK       # K2 option pass (<= 9 tokens): the chunked algorithm is exact for any chunk size; 64 would be 85% padding
    if use_qk_l2norm_in_kernel:
        query = _l2norm(query, dim=-1, eps=1e-6)
        key = _l2norm(key, dim=-1, eps=1e-6)
    query, key, value, beta, g = [x.transpose(1, 2).contiguous().to(torch.float32) for x in (query, key, value, beta, g)]

    batch_size, num_heads, sequence_length, k_head_dim = key.shape
    v_head_dim = value.shape[-1]
    pad_size = (chunk_size - sequence_length % chunk_size) % chunk_size
    query = F.pad(query, (0, 0, 0, pad_size))
    key = F.pad(key, (0, 0, 0, pad_size))
    value = F.pad(value, (0, 0, 0, pad_size))
    beta = F.pad(beta, (0, pad_size))
    g = F.pad(g, (0, pad_size))
    total_sequence_length = sequence_length + pad_size
    scale = 1 / (query.shape[-1] ** 0.5)
    query = query * scale

    v_beta = value * beta.unsqueeze(-1)
    k_beta = key * beta.unsqueeze(-1)
    query, key, value, k_beta, v_beta = [
        x.reshape(x.shape[0], x.shape[1], -1, chunk_size, x.shape[-1]) for x in (query, key, value, k_beta, v_beta)
    ]
    g = g.reshape(g.shape[0], g.shape[1], -1, chunk_size)
    mask = torch.triu(torch.ones(chunk_size, chunk_size, dtype=torch.bool, device=query.device), diagonal=0)

    g = g.cumsum(dim=-1)
    # reference: ((g_i - g_j).tril().exp().float()).tril(); torch.tril is a slow task on the NPU, masked_fill gives the same values
    upper = torch.triu(torch.ones(chunk_size, chunk_size, dtype=torch.bool, device=query.device), diagonal=1)
    decay_mask = (g.unsqueeze(-1) - g.unsqueeze(-2)).masked_fill(upper, 0).exp().masked_fill(upper, 0)
    eg = g.exp()
    A = -((k_beta @ key.transpose(-1, -2)) * decay_mask).masked_fill(mask, 0)            # strictly lower triangular
    attn = unit_lower_inverse(A, mode)                                                    # (I - A)^-1
    value = attn @ v_beta
    k_cumdecay = attn @ (k_beta * eg.unsqueeze(-1))

    # chunk-independent factors of the inter-chunk recurrence, for all chunks at once
    intra = (query @ key.transpose(-1, -2)) * decay_mask             # q_i k_i^T * decay (decay_mask is lower triangular)
    q_g = query * eg.unsqueeze(-1)
    k_dec = (key * (g[..., -1:] - g).exp().unsqueeze(-1)).transpose(-1, -2)
    g_last = eg[..., -1]

    last_recurrent_state = (
        torch.zeros(batch_size, num_heads, k_head_dim, v_head_dim, dtype=value.dtype, device=value.device)
        if initial_state is None
        else initial_state.to(value)
    )
    outs = []
    for i in range(total_sequence_length // chunk_size):
        v_new = value[:, :, i] - k_cumdecay[:, :, i] @ last_recurrent_state
        outs.append(q_g[:, :, i] @ last_recurrent_state + intra[:, :, i] @ v_new)
        last_recurrent_state = last_recurrent_state * g_last[:, :, i, None, None] + k_dec[:, :, i] @ v_new
    core_attn_out = torch.stack(outs, dim=2)

    if not output_final_state:
        last_recurrent_state = None
    core_attn_out = core_attn_out.reshape(core_attn_out.shape[0], core_attn_out.shape[1], -1, core_attn_out.shape[-1])
    core_attn_out = core_attn_out[:, :, :sequence_length]
    core_attn_out = core_attn_out.transpose(1, 2).contiguous().to(initial_dtype)
    return core_attn_out, last_recurrent_state


def _ckpt_form(query, key, value, g, beta, **kw):
    """The same function, recomputed in the backward pass instead of keeping its many fp32 intermediates (decay masks, chunk matrices):
    memory per token falls, the forward is run twice, the result is bit-identical (no randomness inside)."""
    import torch.utils.checkpoint as cp
    return cp.checkpoint(lambda q, k, v, g_, b_: fast_chunk_gated_delta_rule(q, k, v, g_, b_, **kw), query, key, value, g, beta,
                         use_reentrant=False)


def _ckpt_dispatch(query, key, value, g, beta, initial_state=None, **kw):
    if initial_state is None:
        return _ckpt_form(query, key, value, g, beta, **kw)
    import torch.utils.checkpoint as cp
    return cp.checkpoint(lambda q, k, v, g_, b_, s_: fast_chunk_gated_delta_rule(q, k, v, g_, b_, initial_state=s_, **kw),
                         query, key, value, g, beta, initial_state, use_reentrant=False)


def install(model, ckpt=False):
    """Point every Qwen3.5 GatedDeltaNet instance of ``model`` at the fast form (per-instance attribute, transformers untouched).
    ckpt=True wraps the kernel in activation checkpointing (not the layer: this works with the K2 prefix caches)."""
    n = 0
    for m in model.modules():
        if type(m).__name__ == "Qwen3_5GatedDeltaNet":
            m.chunk_gated_delta_rule = _ckpt_dispatch if ckpt else fast_chunk_gated_delta_rule
            n += 1
    return n
