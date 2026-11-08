"""NOT_OF_RECORD CPU-first shared-prefix scorer; accepts the frozen R3 scorer."""
import copy
import math
import time


def fork_cache(cache, owners):
    import torch
    from transformers.cache_utils import DynamicCache, DynamicLayer, LinearAttentionLayer
    if type(cache) is not DynamicCache:
        raise TypeError(f'unsupported cache {type(cache)}')
    new = copy.copy(cache)
    new.layers = []
    for layer in cache.layers:
        if type(layer) not in (DynamicLayer, LinearAttentionLayer):
            raise TypeError(f'unsupported cache layer {type(layer)}')
        n = copy.copy(layer)
        for k, v in vars(layer).items():
            if isinstance(v, torch.Tensor):
                setattr(n, k, v.index_select(0, owners) if v.ndim and v.numel() else v.clone())
            elif isinstance(v, dict):
                setattr(n, k, {a: (b.index_select(0, owners) if isinstance(b, torch.Tensor) and b.ndim and b.numel() else b.clone() if isinstance(b, torch.Tensor) else copy.deepcopy(b)) for a, b in v.items()})
            elif isinstance(v, (list, set)):
                setattr(n, k, copy.deepcopy(v))
        new.layers.append(n)
    return new


def cache_bytes(cache):
    import torch
    total = 0
    for layer in cache.layers:
        for v in vars(layer).values():
            values = v.values() if isinstance(v, dict) else (v,)
            total += sum(x.numel() * x.element_size() for x in values if isinstance(x, torch.Tensor))
    return total


def row_cap(cache, budget_bytes, allowance_bytes, per_row_extra, max_rows=256):
    # budget is available for cache, copies and allowances AFTER loaded model.
    parent = cache_bytes(cache)
    per_row = parent + per_row_extra
    # Two branch-sized copies cover index_select and cache growth/temporary copy.
    n = min(max_rows, (budget_bytes - allowance_bytes - parent) // (2 * per_row))
    if n < 1:
        raise MemoryError('cache budget cannot hold parent, one branch and reserved allowance')
    return int(n)


def cache_snapshot(cache):
    import torch
    return [(layer, key, subkey, tensor.clone())
            for layer in cache.layers for key, value in vars(layer).items()
            for subkey, tensor in (value.items() if isinstance(value, dict) else [(None, value)])
            if isinstance(tensor, torch.Tensor)]


def check_snapshot(snapshot):
    import torch
    for layer, key, subkey, original in snapshot:
        value = getattr(layer, key)
        value = value[subkey] if subkey is not None else value
        if not torch.equal(value, original):
            raise RuntimeError('parent cache mutated during branch scoring')


def score_encoded(scorer, encoded, *, budget_bytes, allowance_bytes, per_row_extra, max_rows=256):
    import torch
    from scorer_r3 import dedup_enc, expand_scores
    scorer.load()
    enc, maps, _, _ = dedup_enc(encoded)
    out = []
    with torch.no_grad():
        for e in enc:
            if not e.prefix or not e.cands or any(not c for c in e.cands):
                raise ValueError('empty prefix or candidate')
            device = scorer.device
            ids = torch.tensor([e.prefix], dtype=torch.long, device=device)
            mask = torch.ones_like(ids)
            pos = torch.arange(ids.shape[1], device=device)[None, :]
            res = scorer.lm.model(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=True)
            scorer.stats["forwards"] += 1
            scorer.stats["tokens"] += len(e.prefix)
            cache = res.past_key_values
            # Validate the runtime cache even for single-token candidates.
            from transformers.cache_utils import DynamicCache, DynamicLayer, LinearAttentionLayer
            if type(cache) is not DynamicCache or any(type(layer) not in (DynamicLayer, LinearAttentionLayer) for layer in cache.layers):
                raise TypeError("unsupported runtime cache or cache layer")
            scorer.stats["max_parent_state_bytes"] = max(scorer.stats.get("max_parent_state_bytes", 0), cache_bytes(cache))
            first = scorer._token_logprobs(res.last_hidden_state, [0]*len(e.cands), [len(e.prefix)-1]*len(e.cands), [c[0] for c in e.cands])
            del res
            vals = list(first)
            cont = sorted((j for j,c in enumerate(e.cands) if len(c)>1), key=lambda j: -len(e.cands[j]))
            if cont:
                cap = row_cap(cache, budget_bytes, allowance_bytes, per_row_extra, max_rows)
                for start in range(0, len(cont), cap):
                    group = cont[start:start+cap]
                    width = max(len(e.cands[j])-1 for j in group)
                    cids = torch.full((len(group), width), scorer.pad_id, dtype=torch.long, device=device)
                    for r,j in enumerate(group):
                        cids[r,:len(e.cands[j])-1] = torch.tensor(e.cands[j][:-1], device=device)
                    owners = torch.zeros(len(group), dtype=torch.long, device=device)
                    scorer._sync(); check_start = time.perf_counter()
                    snapshot = cache_snapshot(cache)
                    scorer._sync(); scorer.stats['cache_check_seconds'] = scorer.stats.get('cache_check_seconds', 0.) + time.perf_counter() - check_start
                    branch = fork_cache(cache, owners)
                    cmask = torch.cat((mask.expand(len(group),-1), torch.ones((len(group),width),dtype=mask.dtype,device=device)),dim=1)
                    positions = (torch.arange(width,device=device)+len(e.prefix)).expand(len(group),-1)
                    scorer.stats["forwards"] += 1
                    scorer.stats["tokens"] += len(group) * width
                    h = scorer.lm.model(input_ids=cids, attention_mask=cmask, position_ids=positions, past_key_values=branch, use_cache=True).last_hidden_state
                    bi, ti, tg, own = [], [], [], []
                    for r,j in enumerate(group):
                        for q,t in enumerate(e.cands[j][1:]):
                            bi.append(r); ti.append(q); tg.append(t); own.append(j)
                    for j,v in zip(own,scorer._token_logprobs(h,bi,ti,tg)):
                        vals[j] += v
                    del h, branch
                    scorer._sync(); check_start = time.perf_counter()
                    check_snapshot(snapshot)
                    scorer._sync(); scorer.stats['cache_check_seconds'] += time.perf_counter() - check_start
                    scorer.stats['cache_checks'] = scorer.stats.get('cache_checks', 0) + 1
            if not all(math.isfinite(v) for v in vals): raise ValueError('nonfinite score')
            out.append(vals)
    scorer._sync()
    return expand_scores(out,maps)
