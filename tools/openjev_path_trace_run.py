#!/usr/bin/env python3
"""E38 fixed short-input path trace. No launcher, resource release or admission."""
import argparse
import contextlib
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import threading
import time


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


base = module(Path(__file__).with_name('openjev_batch_diagnostic.py'), 'e38_pure_helpers')
require, load, sha, stamp, atomic, utc = base.require, base.load, base.sha, base.stamp, base.atomic, base.utc
evidence = module(Path(__file__).with_name('e38_evidence.py'), 'e38_driver_evidence')
IMAGE = base.IMAGE
SCHEMA = 'e38-path-trace-v1'


def schedule():
    return [dict(mode=mode, traced=traced, repetition=rep)
            for traced in (False, True) for mode in ('original', 'chunk8') for rep in (0, 1)]


def name(task):
    return '4200_' + task['mode'] + ('_traced_' if task['traced'] else '_untraced_') + str(task['repetition'])


def select(eligibility):
    matches = [e for e in eligibility['items'] if e['index'] == 4200]
    require(len(matches) == 1, 'Fixed E38 item missing or duplicate')
    e = matches[0]
    require(e['status'] == 'eligible' and len(e['lengths']) == e['candidate_count'] == 15
            and e['max_tokens'] == max(e['lengths']) == 186, 'E38 input bound changed')
    return dict(index=4200, id=e['id'], batch=15, max_tokens=186,
                selection='fixed E37 short-tail input; exploratory localization after E37')


def prepare_input(c, eligibility):
    """CPU-only native request/token reconstruction; never load model weights."""
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false')
    sys.dont_write_bytecode = True
    sys.path.insert(0, c['code']); sys.path.insert(0, c['out'])
    native = module(Path(c['out']) / 'jeval_reference_inference.py', 'e38_input_native')
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    from jev.api import compile_request, candidate_prompts
    rows = pq.read_table(c['data']).to_pylist()
    require(len(rows) == native.TOTAL, 'JEVal population changed')
    selected = select(eligibility); row = rows[4200]; req = native.request(row)
    expected = next(e for e in eligibility['items'] if e['index'] == 4200)
    require(row['id'] == selected['id'] and native.stamp(row) == expected['input_sha256']
            and native.stamp(req) == expected['request_sha256'], 'Fixed request changed')
    tok = AutoTokenizer.from_pretrained(c['base'], local_files_only=True)
    tok.padding_side = 'right'
    if tok.pad_token_id is None: tok.pad_token = tok.eos_token
    e = native.check(req, 'openjev', tok, (compile_request, candidate_prompts))
    identity = {'index', 'id', 'input_sha256', 'request_sha256', 'config_sha256', 'type', 'source', 'source_item_id'}
    require(e == {k: v for k, v in expected.items() if k not in identity}, 'Native eligibility changed')
    records = compile_request(req['state'], req['questions'])
    prompts = [tok.apply_chat_template([{'role': 'user', 'content': text}], tokenize=False,
               add_generation_prompt=True, enable_thinking=False) for text in candidate_prompts(records[0])]
    encoded = tok(prompts, padding=True, truncation=False)
    ids, masks = encoded['input_ids'], encoded['attention_mask']
    require(len(ids) == len(masks) == 15 and all(len(r) == 186 for r in ids + masks),
            'Padded token identity bound changed')
    for i, (tokens, mask) in enumerate(zip(ids, masks)):
        n = e['lengths'][i]
        require(mask == [1] * n + [0] * (186 - n)
                and stamp(tokens[:n]) == e['token_sha256'][i], 'Native token/mask changed')
    return dict(index=4200, id=row['id'], input_sha256=stamp(row), request=req,
                request_sha256=stamp(req), candidate_order=records[0]['answer_keys'],
                eligibility=e, token_sha256=e['token_sha256'],
                ordered_id_row_hashes=[stamp(r) for r in ids],
                ordered_mask_row_hashes=[stamp(r) for r in masks], shape=[15, 186])


def trace_contract(layers, config=None, dtype="torch.bfloat16"):
    """Freeze expected hook population from accepted E37 native layer identities."""
    require(len(layers) in (24, 32), 'Unknown layer population')
    modules = []; events = []
    def add(path):
        modules.append(path); events.extend([path + ':input', path + ':output'])
    for i, layer in enumerate(layers):
        n = layer['name']
        require(n == 'base_model.model.layers.' + str(i)
                and layer['module_type'] == 'Qwen3_5DecoderLayer', 'Unknown native layer identity')
        for suffix in ['', '.input_layernorm', '.post_attention_layernorm',
                       '.mlp.gate_proj', '.mlp.up_proj', '.mlp.down_proj']:
            add(n + suffix)
        if layer['attention_type'] == 'Qwen3_5GatedDeltaNet':
            for suffix in ['in_proj_qkv', 'in_proj_z', 'in_proj_b', 'in_proj_a', 'conv1d', 'out_proj', 'norm']:
                add(n + '.linear_attn.' + suffix)
            events.extend(n + '.linear_attn.core:input:' + x for x in ['query', 'key', 'value', 'g', 'beta'])
            events.append(n + '.linear_attn.core:output')
        elif layer['attention_type'] == 'Qwen3_5Attention':
            for suffix in ['q_proj', 'k_proj', 'v_proj', 'o_proj']:
                add(n + '.self_attn.' + suffix)
        else:
            raise ValueError('Unknown native attention identity')
    require(len(events) == len(set(events)), 'Duplicate native hook identity')
    # Source-derived execution sequence, distinct from registration sequence.
    cfg = config or dict(hidden_size=2048 if len(layers) == 24 else 4096,
        intermediate_size=6144 if len(layers) == 24 else 12288,
        linear_num_key_heads=16, linear_num_value_heads=16 if len(layers) == 24 else 32,
        linear_key_head_dim=128, linear_value_head_dim=128, linear_conv_kernel_dim=4,
        num_attention_heads=8 if len(layers) == 24 else 16,
        num_key_value_heads=2 if len(layers) == 24 else 4, head_dim=256)
    h, mid = cfg['hidden_size'], cfg['intermediate_size']
    hk, hv = cfg['linear_num_key_heads'], cfg['linear_num_value_heads']
    dk, dv = cfg['linear_key_head_dim'], cfg['linear_value_head_dim']
    conv = 2 * hk * dk + hv * dv; length = 186
    order = []; metadata = {}
    batch = dict(kind='batch_first', source_batch_axis=0)
    folded = dict(kind='folded_batch_sequence_heads', sequence_length=length, heads=hv, head_dim=dv)
    def event(n, shape, dt=dtype, layout=None):
        order.append(n); metadata[n] = dict(dtype=dt, row_shape=shape, layout=layout or batch.copy())
    def pair(n, inp, out=None, layout=None):
        event(n + ':input', inp, layout=layout); event(n + ':output', out or inp, layout=layout)
    for layer in layers:
        n = layer['name']; hidden = [length, h]
        event(n + ':input', hidden); pair(n + '.input_layernorm', hidden)
        if layer['attention_type'] == 'Qwen3_5GatedDeltaNet':
            att = n + '.linear_attn.'
            for suffix, width in [('in_proj_qkv', conv), ('in_proj_z', hv * dv), ('in_proj_b', hv), ('in_proj_a', hv)]:
                pair(att + suffix, hidden, [length, width])
            pair(att + 'conv1d', [conv, length], [conv, length + cfg.get('linear_conv_kernel_dim', 4) - 1])
            for suffix, dim in [('query', dk), ('key', dk), ('value', dv)]:
                event(att + 'core:input:' + suffix, [length, hv, dim])
            event(att + 'core:input:g', [length, hv], 'torch.float32')
            event(att + 'core:input:beta', [length, hv])
            event(att + 'core:output', [length, hv, dv])
            pair(att + 'norm', [length, hv, dv], layout=folded)
            pair(att + 'out_proj', [length, hv * dv], hidden)
        else:
            att = n + '.self_attn.'; heads = cfg['num_attention_heads']; kd = cfg['num_key_value_heads']; dim = cfg['head_dim']
            pair(att + 'q_proj', hidden, [length, heads * dim * 2])
            for suffix in ('k_proj', 'v_proj'): pair(att + suffix, hidden, [length, kd * dim])
            pair(att + 'o_proj', [length, heads * dim], hidden)
        pair(n + '.post_attention_layernorm', hidden)
        for suffix in ('gate_proj', 'up_proj'): pair(n + '.mlp.' + suffix, hidden, [length, mid])
        pair(n + '.mlp.down_proj', [length, mid], hidden); event(n + ':output', hidden)
    require(set(order) == set(events) and len(order) == len(events), 'Derived trace population differs')
    return dict(layer_count=len(layers), expected_events=events, observed_modules=modules,
                order=order, events=metadata)


def numeric_contract(temperature):
    return dict(temperature=temperature, probability_mass_atol=1e-6, probability_mass_rtol=1e-6,
                logit_probability_atol=1e-5, wire_probability_atol=1e-8, confidence_atol=1e-7,
                argmax_tie='first_in_candidate_order')


def identity(plan, ph, task):
    return dict(plan_sha256=ph, source_config_sha256=plan['source_config_sha256'],
                input_sha256=stamp(plan['input']), request_sha256=plan['input']['request_sha256'],
                index=4200, **task)


def verify_receipt(env, expected):
    require(set(env) == {'payload', 'sha256'} and stamp(env['payload']) == env['sha256'],
            'Receipt hash differs')
    value = env['payload']
    require(all(type(value.get(k)) is type(v) and value.get(k) == v for k, v in expected.items()),
            'Receipt identity differs')
    return value


@contextlib.contextmanager
def input_guard(backbone, expected, observed):
    """Same passive full-input guard for every forward, outside candidate splitting.

    candidate_chunks replaces forward and calls the saved forward directly for
    each part, so this module pre-hook observes the one full native call.
    """
    def before(_module, args, kwargs):
        require(not args and set(kwargs) == {'input_ids', 'attention_mask', 'use_cache', 'return_dict'}
                and kwargs['use_cache'] is False and kwargs['return_dict'] is True,
                'Backbone call changed')
        ids, masks = kwargs['input_ids'], kwargs['attention_mask']
        require(list(ids.shape) == list(masks.shape) == [15, 186], 'Padded input changed')
        value = dict(shape=[15, 186],
                     ordered_id_row_hashes=[stamp(row) for row in ids.detach().cpu().tolist()],
                     ordered_mask_row_hashes=[stamp(row) for row in masks.detach().cpu().tolist()])
        require(not observed and value == {k: expected[k] for k in value},
                'Padded token/mask identity differs or repeated backbone call')
        observed.update(value)
    handle = backbone.register_forward_pre_hook(before, with_kwargs=True)
    try:
        yield
        require(observed, 'Backbone did not consume input')
    finally:
        handle.remove()


def analyze(results):
    trace = module(Path(__file__).with_name('openjev_path_trace.py'), 'e38_trace_analysis')
    controls = {}; comparisons = {}; repeated_traces = {}; cross_traces = {}
    def item(mode, traced, rep):
        return results[name(dict(mode=mode, traced=traced, repetition=rep))]
    for mode in ('original', 'chunk8'):
        for traced in (False, True):
            a, b = (item(mode, traced, rep)['prediction'] for rep in (0, 1))
            key = mode + ('_traced_repeat' if traced else '_untraced_repeat')
            comparisons[key] = base.comparison(a, b)
            controls[key] = comparisons[key]['exact_prediction']
        for rep in (0, 1):
            key = mode + '_hook_effect_' + str(rep)
            comparisons[key] = base.comparison(item(mode, False, rep)['prediction'],
                                               item(mode, True, rep)['prediction'])
            controls[key] = comparisons[key]['exact_prediction']
        repeated_traces[mode] = trace.compare_traces(item(mode, True, 0)['trace'], item(mode, True, 1)['trace'])
        controls[mode + '_trace_repeat'] = repeated_traces[mode]['exact']
    for rep in (0, 1):
        comparisons['original_vs_chunk_' + str(rep)] = base.comparison(
            item('original', False, rep)['prediction'], item('chunk8', False, rep)['prediction'])
        cross_traces[str(rep)] = trace.compare_traces(item('original', True, rep)['trace'], item('chunk8', True, rep)['trace'])
    controls['cross_trace_localization_repeats'] = cross_traces['0'] == cross_traces['1']
    return dict(trace_valid=all(controls.values()), controls=controls, comparisons=comparisons,
                repeated_traces=repeated_traces, cross_traces=cross_traces,
                candidate_batch_admission=False, existing_e36_admission='failed; unchanged')


def scientific_terminal(report):
    if report is None:
        return dict(status='FAILED', trace_valid=None, review_flags=['E38 execution did not produce a complete trace report'])
    flags = ['E38 exact control failed: ' + k for k, passed in report['controls'].items() if not passed]
    return dict(status='COMPLETED_SCOPED_REVIEW_REQUIRED' if flags else 'COMPLETED_SCOPED',
                trace_valid=report['trace_valid'], review_flags=flags)


def verify_plan(plan_path, bound=None):
    bound = bound or evidence.Evidence()
    p = bound.load(plan_path); out = Path(p['out'])
    require(plan_path.resolve() == (out / 'plan.json').resolve()
            and p['schema'] == SCHEMA and p.get('execution_revision') == 'astra-v3-strict-attempts' and p['image'] == IMAGE
            and p['chunk_rows'] == 8 and p['candidate_batch_admission'] is False
            and p['schedule'] == schedule(), 'E38 protocol differs')
    required = {str(out / n) for n in ['openjev_path_trace_run.py', 'openjev_path_trace.py',
        'openjev_batch_diagnostic.py', 'openjev_candidate_chunks.py', 'verify_openjev_path_trace.py',
        'prepare_openjev_path_trace.py', 'jeval_reference_queue.py', 'e38_evidence.py']}
    required.update(p[k] for k in ['source_config', 'e37_plan', 'wrapper', 'launch', 'resume', 'container_spec', 'preregistration'])
    require(required <= set(p['files']), 'E38 closure omitted')
    for path, digest in p['files'].items(): require(bound.sha(path) == digest, 'Frozen file changed: ' + path)
    require(bound.sha(p['source_config']) == p['source_config_sha256'], 'Source config changed')
    require(p['numeric_contract'] == numeric_contract(bound.load(p['source_config'])['temperature']), 'Native numeric contract differs')
    require(stamp(p['input']['request']) == p['input']['request_sha256'] and p['input']['index'] == 4200
            and p['input']['shape'] == [15, 186] and len(p['input']['candidate_order']) == 15,
            'Frozen request identity changed')
    bound.verify()
    return p


def run(plan_path):
    bound = evidence.Evidence()
    p = bound.load(plan_path); ph = bound.sha(plan_path); out = Path(p['out'])
    lock = (out / 'driver.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    evidence.publication_gate(out)
    state = dict(stage='verify', progress=0, total=8, chips=1)
    stop = threading.Event(); rc = 1; error = None; report = None
    def heartbeat():
        while not stop.wait(10):
            v = dict(utc=utc(), **state); atomic(out / 'STATUS.json', v)
            (out / 'digest.md').write_text(json.dumps(v) + '\n')
            with (out / 'heartbeat.log').open('a') as f: f.write(json.dumps(v) + '\n')
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    try:
        verify_plan(plan_path, bound)
        verifier = module(out / 'verify_openjev_path_trace.py', 'e38_runtime_receipts')
        try: verifier.validate_items(p, ph, complete=False, evidence=bound)
        except ValueError as exc:
            evidence.fail_generation(out, str(exc)); raise
        c = bound.load(p['source_config'])
        require(c['family'] == 'openjev' and c['image'] == IMAGE, 'Source family/image differs')
        sys.path.insert(0, c['out']); sys.path.insert(0, str(out))
        native = module(Path(c['out']) / 'jeval_reference_inference.py', 'e38_native_execution')
        eligibility = native.verify_files(c)
        require(select(eligibility) == p['selection'] and prepare_input(c, eligibility) == p['input'],
                'Selected native input changed')
        if (out / 'SELECTION.json').exists(): require(bound.load(out / 'SELECTION.json') == p['selection'], 'Retained selection differs')
        else: evidence.publish_new(out / 'SELECTION.json', p['selection'])
        state['stage'] = 'load_model'; model = native.Native(c); torch = model.torch
        trace_tools = module(out / 'openjev_path_trace.py', 'e38_instrumentation')
        chunks = module(out / 'openjev_candidate_chunks.py', 'e38_chunks')
        req = p['input']['request']; e = model.eligibility(req)
        require(e == p['input']['eligibility'], 'Loaded tokenizer eligibility changed')
        folder = out / 'items'; evidence.durable_mkdir(folder); results = {}
        attempts = out / 'attempts'; evidence.durable_mkdir(attempts)
        for count, task in enumerate(schedule()):
            key = name(task); path = folder / (key + '.json'); state.update(stage=key, progress=count)
            expected = identity(p, ph, task)
            if path.exists():
                value = verify_receipt(bound.load(path), expected)
            else:
                bound.verify(metadata_only=True)
                attempt = attempts / (key + '.json')
                evidence.publish_new(attempt, dict(**expected, phase='forward_intent', utc=utc()))
                torch.npu.empty_cache(); torch.npu.reset_peak_memory_stats(); torch.npu.synchronize()
                trace = {}; observed = {}; start = time.monotonic()
                with input_guard(model.model.backbone, p['input'], observed):
                    with trace_tools.trace_path(model.model.backbone, torch, trace, contract=p['trace_contract']) if task['traced'] else contextlib.nullcontext(None) as observer:
                        with chunks.candidate_chunks(model.model.backbone, 8, observer) if task['mode'] == 'chunk8' else contextlib.nullcontext():
                            prediction = model.predict(req, e)
                torch.npu.synchronize(); seconds = time.monotonic() - start
                native.response(next(iter(req['questions'].values())), prediction['answer'])
                require(prediction['consumed_token_sha256'] == p['input']['token_sha256']
                        and list(prediction['native_probabilities']) == p['input']['candidate_order'],
                        'Prediction token/candidate identity differs')
                value = dict(**expected, attempt_sha256=bound.sha(attempt), prediction=prediction, trace=trace, observed_input=observed,
                             seconds=seconds, questions_per_second_per_chip=1 / seconds, chips=1,
                             reserved_gib=torch.npu.memory_reserved() / 2**30,
                             peak_allocated_gib=torch.npu.max_memory_allocated() / 2**30,
                             peak_reserved_gib=torch.npu.max_memory_reserved() / 2**30,
                             performance_scope='Diagnostic wall time including input guards and optional trace synchronization')
                verifier.check_prediction(prediction, p)
                if task['traced']: verifier.check_trace(trace, p, task['mode'])
                evidence.publish_new(path, dict(payload=value, sha256=stamp(value)))
            results[key] = value
            state.update(progress=count + 1, questions_per_second_per_chip=value['questions_per_second_per_chip'],
                         reserved_gib=value['reserved_gib'])
        verifier.validate_items(p, ph, complete=True, evidence=bound)
        native.verify_files(c)
        require(prepare_input(c, eligibility) == p['input'], 'Final input changed')
        require(sha(plan_path) == ph, 'Plan changed during run'); verify_plan(plan_path, bound)
        report = dict(plan_sha256=ph, selection=p['selection'], input_sha256=stamp(p['input']),
                      receipt_manifest={x.name: bound.sha(x) for x in sorted(folder.iterdir())},
                      attempt_manifest={x.name: bound.sha(x) for x in sorted(attempts.iterdir())}, **analyze(results),
                      scope='Fixed exploratory trace, no full-test score, numeric admission, kernel cause or speedup claim')
        bound.verify()
        evidence.publish_new(out / 'report.json', report); state['stage'] = 'completed'; rc = 0
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc); state['stage'] = 'failed'; raise
    finally:
        stop.set(); thread.join()
        outputs = {n: sha(out / n) for n in ['SELECTION.json', 'report.json'] if (out / n).exists()}
        evidence.publish_new(out / 'COMPLETE.json', dict(rc=rc, error=error, plan_sha256=ph, outputs=outputs, utc=utc(),
                                         **state, **scientific_terminal(report)))
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--plan', type=Path, required=True)
    run(parser.parse_args().plan.resolve())
