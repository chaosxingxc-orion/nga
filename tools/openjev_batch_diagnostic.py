#!/usr/bin/env python3
"""E37: bounded batch-shape/no-op diagnostic, never full-test scoring.

A separately frozen plan and an assigned chip are required. This file does not
launch Docker, allocate devices, or amend E33/E36 numerical admission.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import threading
import time

IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
STRATA = [('short_tail', 9, 16, 1, 512),
          ('mid_tail', 17, 30, 513, 2048),
          ('long_tail', 17, 30, 2049, 4096)]
MAX_PADDED = 30 * 4096
MAX_ATTENTION = 30 * 4096 ** 2


def require(value, message):
    if not value:
        raise ValueError(message)


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def stamp(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def atomic(p, x):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(x, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    tmp.replace(p)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def select(eligibility):
    """Read token metadata only; no prediction, label or correctness selection."""
    entries = [e for e in eligibility['items'] if e['status'] == 'eligible']
    require(entries, 'No eligible input')
    boundary = max(entries, key=lambda e: (e['max_tokens'], -e['index']))
    require(boundary['index'] == 9027 and boundary['max_tokens'] == 4096
            and len(boundary['lengths']) == 30, 'E36 boundary metadata changed')
    selected = [{'role': 'boundary', 'index': boundary['index']}]
    cells = []
    seen = {boundary['index']}
    for name, blo, bhi, llo, lhi in STRATA:
        candidates = [e for e in entries
                      if blo <= len(e['lengths']) <= bhi
                      and llo <= e['max_tokens'] <= lhi
                      and len(e['lengths']) * e['max_tokens'] <= MAX_PADDED
                      and len(e['lengths']) * e['max_tokens'] ** 2 <= MAX_ATTENTION]
        chosen = min(candidates, key=lambda e: e['index']) if candidates else None
        cells.append(dict(name=name, count=len(candidates),
                          selected_index=chosen['index'] if chosen else None))
        if chosen and chosen['index'] not in seen:
            selected.append(dict(role=name, index=chosen['index']))
            seen.add(chosen['index'])
    for item in selected:
        e = next(x for x in entries if x['index'] == item['index'])
        item.update(id=e['id'], batch=len(e['lengths']), max_tokens=e['max_tokens'],
                    padded_tokens=len(e['lengths']) * e['max_tokens'],
                    attention_cells=len(e['lengths']) * e['max_tokens'] ** 2)
    return dict(selected=selected, strata=cells, max_padded=MAX_PADDED,
                max_attention_cells=MAX_ATTENTION, tie='lowest original index',
                missing_strata='retained as absent; no substitute selection')


def numeric(x):
    if isinstance(x, dict):
        return sum((numeric(v) for v in x.values()), [])
    return [float(x)] if type(x) in (float, int) else []


def comparison(a, b):
    for k in ['native_probabilities', 'answer']:
        require(list(a[k]) == list(b[k]), 'Prediction field order changed')
    require(a['answer']['type'] == b['answer']['type'], 'Answer type changed')
    for field in ['probabilities', 'legend']:
        if field in a['answer']:
            require(list(a['answer'][field]) == list(b['answer'][field]), 'Candidate order changed')
    if 'legend' in a['answer']:
        require(a['answer']['legend'] == b['answer']['legend'], 'Legend changed')
    def delta(x, y):
        require(len(x) == len(y) and all(math.isfinite(v) for v in x + y), 'Invalid numeric values')
        return max([abs(v - w) for v, w in zip(x, y)] + [0.])
    def decision(x):
        q = x['answer']
        if q['type'] == 'choice':
            return q['choice']
        if q['type'] == 'noul':
            return q['noul'] >= .5
        return q['score']  # Returned expected score; do not substitute argmax.
    return dict(logits_max_delta=delta(a['logits'], b['logits']),
                probability_max_delta=delta(list(a['native_probabilities'].values()), list(b['native_probabilities'].values())),
                probability_mean_abs_delta=sum(abs(a['native_probabilities'][k] - b['native_probabilities'][k]) for k in a['native_probabilities']) / len(a['native_probabilities']),
                wire_max_delta=delta(numeric(a['answer']), numeric(b['answer'])),
                decision_changed=decision(a) != decision(b),
                tokens_identical=a['consumed_token_sha256'] == b['consumed_token_sha256'],
                exact_prediction=stamp(a) == stamp(b))


def metadata(value):
    """No hidden-state values retained; shapes/dtypes only."""
    if hasattr(value, 'shape') and hasattr(value, 'dtype'):
        return dict(shape=list(value.shape), dtype=str(value.dtype), device=str(value.device))
    if isinstance(value, (tuple, list)):
        return [metadata(v) for v in value]
    if isinstance(value, dict):
        return {k: metadata(v) for k, v in value.items()}
    if hasattr(value, 'last_hidden_state'):
        return {'last_hidden_state': metadata(value.last_hidden_state)}
    return type(value).__name__


@contextlib.contextmanager
def profile(backbone, torch, trace):
    """Hooks return None and never alter inputs/outputs. Timing is synchronized.

    Layer peaks are inclusive since that layer's pre-hook reset. They are not
    additive, and resets mean this profiled pass has no whole-forward peak claim.
    """
    handles, starts = [], {}
    layers = [(name, m) for name, m in backbone.named_modules()
              if type(m).__name__.endswith('DecoderLayer')]
    require(layers, 'No decoder layers found; refuse empty profile')
    def before(name):
        def hook(module, args, kwargs):
            torch.npu.synchronize()
            torch.npu.reset_peak_memory_stats()
            starts[name] = (time.monotonic(), torch.npu.memory_allocated(),
                            metadata(args), metadata(kwargs))
        return hook
    def after(name):
        def hook(module, args, kwargs, result):
            torch.npu.synchronize()
            start, initial, arg_meta, kw_meta = starts.pop(name)
            trace['layers'].append(dict(name=name, module_type=type(module).__name__,
                attention_type=type(getattr(module, 'self_attn', getattr(module, 'linear_attn', None))).__name__,
                chunk_call_index=len(trace.get('chunk_calls', [])) - 1, seconds=time.monotonic() - start,
                inputs=arg_meta, keyword_inputs=kw_meta, output=metadata(result),
                allocated_before=initial, allocated_after=torch.npu.memory_allocated(),
                peak_allocated=torch.npu.max_memory_allocated(),
                peak_reserved=torch.npu.max_memory_reserved()))
        return hook
    def backbone_before(module, args, kwargs):
        require(not args and 'input_ids' in kwargs and 'attention_mask' in kwargs, 'Unexpected backbone call')
        ids, masks = kwargs['input_ids'], kwargs['attention_mask']
        trace['backbone_inputs'].append(dict(input=metadata(ids), mask=metadata(masks),
            ordered_id_row_hashes=[stamp(row) for row in ids.detach().cpu().tolist()],
            ordered_mask_row_hashes=[stamp(row) for row in masks.detach().cpu().tolist()]))
    def backbone_after(module, args, kwargs, result):
        trace['backbone_outputs'].append(metadata(result))
    try:
        for name, layer in layers:
            handles.extend([layer.register_forward_pre_hook(before(name), with_kwargs=True),
                            layer.register_forward_hook(after(name), with_kwargs=True)])
        handles.extend([backbone.register_forward_pre_hook(backbone_before, with_kwargs=True),
                        backbone.register_forward_hook(backbone_after, with_kwargs=True)])
        yield
    finally:
        for handle in handles:
            handle.remove()


def verify_receipt(env, identity):
    value = env['payload']
    require(stamp(value) == env['sha256'], 'Receipt hash differs')
    require(all(value.get(k) == v for k, v in identity.items()), 'Receipt identity differs')
    return value


def run(plan_path):
    plan = load(plan_path); ph = sha(plan_path); out = Path(plan['out'])
    lock = (out / 'driver.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(not (out / 'COMPLETE.json').exists(), 'Existing terminal preserved')
    state = dict(stage='verify', progress=0, total=None, chips=1)
    stop = threading.Event(); rc = 1; error = None
    def heartbeat():
        while not stop.wait(10):
            snapshot = dict(utc=utc(), **state); atomic(out / 'STATUS.json', snapshot)
            (out / 'digest.md').write_text(json.dumps(snapshot) + '\n')
            with (out / 'heartbeat.log').open('a') as f: f.write(json.dumps(snapshot) + '\n')
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    try:
        require(plan['schema'] == 1 and plan['image'] == IMAGE and plan['chunk_rows'] == 8, 'Diagnostic protocol differs')
        require(plan['source_config'] in plan['files'], 'Source config omitted')
        for p in [str(Path(__file__).resolve()), str(Path(__file__).resolve().with_name('openjev_candidate_chunks.py')),
                  plan['preregistration'], plan['wrapper'], plan['launch'], plan['resume'], plan['container_spec']]:
            require(p in plan['files'], 'Diagnostic executable closure omitted')
        for p, h in plan['files'].items(): require(sha(p) == h, 'Frozen file changed: ' + p)
        require(sha(plan['source_config']) == plan['source_config_sha256'], 'Source config changed')
        c = load(plan['source_config']); require(c['family'] == 'openjev' and c['image'] == IMAGE, 'Source family/image')
        sys.path.insert(0, str(Path(c['out']))); sys.path.insert(0, str(Path(__file__).resolve().parent))
        import jeval_reference_inference as driver
        from openjev_candidate_chunks import candidate_chunks
        eligibility = driver.verify_files(c)
        selection = select(eligibility)
        require(selection == plan['selection'], 'Metadata selection changed')
        atomic(out / 'SELECTION.json', selection)
        import pyarrow.parquet as pq
        rows = pq.read_table(c['data']).to_pylist()
        state['stage'] = 'load_model'; model = driver.Native(c); torch = model.torch
        tasks = []
        for item in selection['selected']:
            modes = ['original', 'noop', 'chunk8'] if item['role'] == 'boundary' else ['original', 'chunk8']
            tasks.extend((item, mode, rep, False) for mode in modes for rep in range(2))
            if item['role'] == 'boundary': tasks.extend((item, mode, 0, True) for mode in ['original', 'chunk8'])
        state['total'] = len(tasks); folder = out / 'items'; folder.mkdir(exist_ok=True); results = {}
        for count, (item, mode, rep, profiled) in enumerate(tasks):
            index = item['index']; req = driver.request(rows[index]); e = model.eligibility(req)
            expected = eligibility['items'][index]
            identity_keys = {'index', 'id', 'input_sha256', 'request_sha256', 'config_sha256', 'type', 'source', 'source_item_id'}
            require(e == {k: v for k, v in expected.items() if k not in identity_keys}, 'Complete eligibility changed')
            name = f'{index}_{mode}_{rep}' + ('_profiled' if profiled else '')
            identity = dict(plan_sha256=ph, request_sha256=driver.stamp(req), index=index,
                            mode=mode, rep=rep, profiled=profiled)
            path = folder / (name + '.json'); state.update(stage=name, progress=count)
            if path.exists():
                value = verify_receipt(load(path), identity)
            else:
                torch.npu.empty_cache(); torch.npu.reset_peak_memory_stats(); torch.npu.synchronize()
                trace = dict(layers=[], backbone_inputs=[], backbone_outputs=[], chunk_calls=[])
                chunk_rows = item['batch'] if mode == 'noop' else 8
                chunk = candidate_chunks(model.model.backbone, chunk_rows,
                    lambda a, b, l: trace['chunk_calls'].append([a, b, l])) if mode != 'original' else contextlib.nullcontext()
                monitor = profile(model.model.backbone, torch, trace) if profiled else contextlib.nullcontext()
                start = time.monotonic()
                with monitor, chunk:
                    prediction = model.predict(req, e)
                torch.npu.synchronize(); seconds = time.monotonic() - start
                driver.response(next(iter(req['questions'].values())), prediction['answer'])
                value = dict(**identity, prediction=prediction, seconds=seconds,
                    questions_per_second_per_chip=1 / seconds, chips=1,
                    reserved_gib=torch.npu.memory_reserved() / 2**30,
                    peak_allocated_gib=None if profiled else torch.npu.max_memory_allocated() / 2**30,
                    peak_reserved_gib=None if profiled else torch.npu.max_memory_reserved() / 2**30,
                    trace=trace)
                atomic(path, dict(payload=value, sha256=stamp(value)))
            results[name] = value
            state.update(progress=count + 1, questions_per_second_per_chip=value['questions_per_second_per_chip'],
                         reserved_gib=value['reserved_gib'])
        comparisons = {}; diagnostic_valid = True
        for item in selection['selected']:
            prefix = str(item['index'])
            pred = lambda mode, rep=0, prof=False: results[f'{prefix}_{mode}_{rep}' + ('_profiled' if prof else '')]['prediction']
            cell = dict(original_repeat=comparison(pred('original'), pred('original', 1)),
                        chunk_repeat=comparison(pred('chunk8'), pred('chunk8', 1)),
                        original_vs_chunk=comparison(pred('original'), pred('chunk8')))
            if item['role'] == 'boundary':
                cell.update(noop_repeat=comparison(pred('noop'), pred('noop', 1)),
                            original_vs_noop=comparison(pred('original'), pred('noop')),
                            original_hook_effect=comparison(pred('original'), pred('original', prof=True)),
                            chunk_hook_effect=comparison(pred('chunk8'), pred('chunk8', prof=True)))
                diagnostic_valid &= all(cell[k]['exact_prediction'] for k in ['original_repeat', 'noop_repeat', 'original_vs_noop', 'original_hook_effect', 'chunk_hook_effect'])
            comparisons[prefix] = cell
        driver.verify_files(c)
        require(sha(plan_path) == ph, 'Plan changed during run')
        for p, h in plan['files'].items(): require(sha(p) == h, 'Final frozen file changed')
        report = dict(plan_sha256=ph, diagnostic_valid=diagnostic_valid, selection=selection, comparisons=comparisons,
            paired_decision_flips=sum(x['original_vs_chunk']['decision_changed'] for x in comparisons.values()),
            paired_denominator=len(comparisons), existing_e36_admission='failed; unchanged',
            candidate_batch_admission=False,
            scope='Bounded metadata-selected diagnostic; no full-test metric, memory-envelope certification, pure-speed admission or Astra approval. Profiled timings include synchronization; layer peaks are inclusive and not additive.')
        atomic(out / 'report.json', report); state['stage'] = 'completed'; rc = 0
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc); state['stage'] = 'failed'; raise
    finally:
        stop.set(); thread.join()
        outputs = {n: sha(out / n) for n in ['SELECTION.json', 'report.json'] if (out / n).exists()}
        atomic(out / 'COMPLETE.json', dict(rc=rc, error=error, plan_sha256=ph, outputs=outputs, utc=utc(), **state))
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--plan', type=Path, required=True)
    run(parser.parse_args().plan)
