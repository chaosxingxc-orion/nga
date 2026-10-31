#!/usr/bin/env python3
"""Independent CPU reconstruction of E38 receipts, controls and trace differences.

No model load, launch, resource release, E36 admission or full-test score.
Public full verification is executed by the retained CPU wrapper in the preparer.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re


def evidence_module():
    spec = importlib.util.spec_from_file_location('e38_bound_evidence', Path(__file__).with_name('e38_evidence.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


Evidence = evidence_module().Evidence


def require(v, msg):
    if not v: raise ValueError(msg)


def load(p): return json.loads(Path(p).read_text())


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''): h.update(block)
    return h.hexdigest()


def stamp(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def schedule():
    return [dict(mode=mode, traced=traced, repetition=rep)
            for traced in (False, True) for mode in ('original', 'chunk8') for rep in (0, 1)]


def name(t): return '4200_' + t['mode'] + ('_traced_' if t['traced'] else '_untraced_') + str(t['repetition'])


def identity(p, ph, t):
    return dict(plan_sha256=ph, source_config_sha256=p['source_config_sha256'],
                input_sha256=stamp(p['input']), request_sha256=p['input']['request_sha256'], index=4200, **t)


def check_trace(trace, p, mode):
    contract = p['trace_contract']; expected = contract['expected_events']
    require(trace['candidates'] == 15 and trace['width'] == 186, 'Trace bounds differ')
    require(trace['expected_events'] == expected and trace['observed_modules'] == contract['observed_modules'],
            'Trace differs from frozen native hook population')
    order, events = trace['order'], trace['events']
    require(len(order) == len(set(order)) and set(order) == set(events) == set(expected),
            'Missing, duplicate or extra trace event')
    ranges = [[0, 15, 186]] if mode == 'original' else [[0, 8, 186], [8, 15, 186]]
    require([c['range'] for c in trace['chunks']] == ranges
            and all(c['order'] == order for c in trace['chunks']), 'Trace chunk identity/order differs')
    require(order == contract['order'], 'Trace execution order differs from frozen source')
    require(set(contract['events']) == set(expected), 'Frozen event contract incomplete')
    for name, event in events.items():
        require(set(event) == {'dtype', 'row_shape', 'layout', 'rows'}
                and {k: event[k] for k in ('dtype', 'row_shape', 'layout')} == contract['events'][name],
                'Trace dtype/shape/source layout differs from frozen source: ' + name)
        require(set(event['rows']) == {str(i) for i in range(15)}
                and all(type(h) is str and re.fullmatch('[0-9a-f]{64}', h) for h in event['rows'].values()),
                'Missing candidate or invalid byte fingerprint')


def check_prediction(pred, p):
    keys = p['input']['candidate_order']; z = pred['logits']; probs = pred['native_probabilities']
    require(set(pred) == {'answer', 'native_probabilities', 'logits', 'logits_temperature', 'consumed_token_sha256'},
            'Prediction fields differ')
    require(list(probs) == keys and len(z) == len(keys) == 15 and pred['logits_temperature'] == 'unscaled',
            'Prediction candidate/logit identity differs')
    require(pred['consumed_token_sha256'] == p['input']['token_sha256'], 'Consumed token identity differs')
    require(all(type(x) in (int, float) and math.isfinite(x) for x in z + list(probs.values()))
            and all(0 <= x <= 1 for x in probs.values()), 'Invalid prediction numeric values')
    nc = p['numeric_contract']
    fixed = dict(probability_mass_atol=1e-6, probability_mass_rtol=1e-6,
                 logit_probability_atol=1e-5, wire_probability_atol=1e-8,
                 confidence_atol=1e-7, argmax_tie='first_in_candidate_order')
    require(set(nc) == set(fixed) | {'temperature'} and all(nc[k] == val for k, val in fixed.items()),
            'Numeric tolerances differ from protocol')
    temperature = nc['temperature']
    require(type(temperature) in (int, float) and math.isfinite(temperature) and temperature > 0,
            'Invalid native temperature')
    total = sum(probs.values())
    require(math.isclose(total, 1., rel_tol=nc['probability_mass_rtol'], abs_tol=nc['probability_mass_atol']),
            'Native probability mass differs')
    scaled = [x / temperature for x in z]; top = max(scaled)
    exps = [math.exp(x - top) for x in scaled]; den = sum(exps)
    require(all(abs(x / den - probs[key]) <= nc['logit_probability_atol'] for key, x in zip(keys, exps)),
            'Native probabilities disconnected from logits/temperature')
    question = next(iter(p['input']['request']['questions'].values())); ans = pred['answer']
    require(question['type'] == ans['type'] == 'choice', 'Fixed E38 choice type differs')
    require(set(ans) == {'type', 'choice', 'probabilities', 'confidence'}
            and list(ans['probabilities']) == keys, 'Native wire fields/order differ')
    wire = ans['probabilities']
    require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in wire.values()),
            'Invalid native wire probabilities')
    require(all(abs(wire[k] - probs[k] / total) <= nc['wire_probability_atol'] for k in keys),
            'Native wire renormalization differs')
    require(ans['choice'] == max(keys, key=lambda k: probs[k]), 'Native first argmax choice differs')
    mass = sum(wire.values()); chance = 1 / len(keys)
    confidence = (max(wire.values()) / mass - chance) / (1 - chance)
    require(type(ans['confidence']) in (int, float) and math.isfinite(ans['confidence'])
            and 0 <= ans['confidence'] <= 1
            and abs(ans['confidence'] - confidence) <= nc['confidence_atol'],
            'Native chance-adjusted confidence differs')


def validate_attempts(p, ph, items, evidence, complete=False):
    require(p.get('execution_revision') == 'astra-v3-strict-attempts', 'Missing strict attempt generation')
    folder = Path(p['out']) / 'attempts'
    expected = {name(t) + '.json': t for t in schedule()}
    if not folder.exists():
        require(not items and not complete, 'Missing durable forward intents'); return {}
    require(folder.is_dir() and not folder.is_symlink(), 'Invalid attempt directory')
    paths = list(folder.iterdir())
    require(all(x.name in expected and x.is_file() and not x.is_symlink() for x in paths),
            'Foreign or uncertain partial attempt; generation failed')
    require({x.name for x in paths} == set(items),
            'Unmatched forward intent: uncertain attempted forward; generation permanently failed')
    manifest = {}
    for path in paths:
        intent = evidence.load(path); ident = identity(p, ph, expected[path.name])
        require(set(intent) == set(ident) | {'phase', 'utc'} and intent['phase'] == 'forward_intent'
                and type(intent['utc']) is str and intent['utc']
                and all(type(intent.get(k)) is type(x) and intent.get(k) == x for k, x in ident.items()),
                'Forward intent identity differs')
        manifest[path.name] = evidence.sha(path)
        require(items[path.name].get('attempt_sha256') == manifest[path.name], 'Receipt does not bind forward intent')
    if complete: require(len(paths) == 8, 'Strict eight-attempt population differs')
    return manifest


def validate_items(p, ph, complete=False, evidence=None):
    evidence = evidence or Evidence()
    require(p['schedule'] == schedule() and p['input']['index'] == 4200
            and stamp(p['input']['request']) == p['input']['request_sha256'], 'Frozen task/input differs')
    folder = Path(p['out']) / 'items'
    tasks = schedule(); expected = {name(t) + '.json': t for t in tasks}
    if not folder.exists():
        require(not complete, 'Missing E38 receipts')
        validate_attempts(p, ph, {}, evidence, complete=False)
        evidence.verify()
        return {}
    require(folder.is_dir() and not folder.is_symlink(), 'Items directory differs')
    got = {}; partial = []
    for f in folder.iterdir():
        require(f.is_file() and not f.is_symlink(), 'Foreign receipt or symlink')
        if f.name.endswith('.json.tmp'):
            require(not complete and f.name[:-4] in expected, 'Unknown partial receipt'); partial.append(f.name[:-4]); continue
        require(f.name in expected, 'Unknown E38 receipt')
        env = evidence.load(f)
        require(set(env) == {'payload', 'sha256'} and stamp(env['payload']) == env['sha256'], 'Receipt hash differs')
        v = env['payload']; task = expected[f.name]; ident = identity(p, ph, task)
        require(all(type(v.get(k)) is type(x) and v.get(k) == x for k, x in ident.items()), 'Receipt identity differs')
        check_prediction(v['prediction'], p)
        require(v['observed_input'] == {k: p['input'][k] for k in
                ['shape', 'ordered_id_row_hashes', 'ordered_mask_row_hashes']}, 'Padded input identity differs')
        require(type(v['chips']) is int and v['chips'] == 1, 'Chip count differs')
        require(all(type(v[k]) in (float, int) and math.isfinite(v[k]) and v[k] >= 0 for k in
                ['seconds', 'questions_per_second_per_chip', 'reserved_gib', 'peak_allocated_gib', 'peak_reserved_gib'])
                and v['seconds'] > 0 and v['questions_per_second_per_chip'] == 1 / v['seconds'],
                'Invalid diagnostic timing/memory')
        if task['traced']: check_trace(v['trace'], p, task['mode'])
        else: require(v['trace'] == {}, 'Untraced receipt carries observations')
        got[f.name] = v
    expected_order = list(expected)
    require(set(got) == set(expected_order[:len(got)]), 'Receipts are not a fixed execution prefix')
    require(not partial or (len(partial) == 1 and len(got) < 8 and partial[0] == expected_order[len(got)]),
            'Partial receipt is not the next scheduled item')
    if complete: require(len(got) == 8 and not partial, 'Incomplete E38 receipts')
    validate_attempts(p, ph, got, evidence, complete=complete)
    evidence.verify()
    return got


def compare_predictions(a, b):
    require(list(a['native_probabilities']) == list(b['native_probabilities']) and list(a['answer']) == list(b['answer']),
            'Prediction field order differs')
    def flat(x):
        if isinstance(x, dict): return [v for child in x.values() for v in flat(child)]
        return [float(x)] if type(x) in (float, int) else []
    def delta(xs, ys):
        require(len(xs) == len(ys), 'Vector size differs')
        return max([abs(x - y) for x, y in zip(xs, ys)] + [0.])
    pa, pb = list(a['native_probabilities'].values()), list(b['native_probabilities'].values())
    return dict(logits_max_delta=delta(a['logits'], b['logits']), probability_max_delta=delta(pa, pb),
        probability_mean_abs_delta=sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa),
        wire_max_delta=delta(flat(a['answer']), flat(b['answer'])),
        decision_changed=a['answer']['choice'] != b['answer']['choice'],
        tokens_identical=a['consumed_token_sha256'] == b['consumed_token_sha256'], exact_prediction=stamp(a) == stamp(b))


def compare_traces(a, b):
    require(a['order'] == b['order'], 'Trace event order differs between executions')
    changes = []
    for event in a['order']:
        x, y = a['events'][event], b['events'][event]
        require(x['dtype'] == y['dtype'] and x['row_shape'] == y['row_shape'] and x['layout'] == y['layout'], 'Trace row layout differs')
        changed = [i for i in range(15) if x['rows'][str(i)] != y['rows'][str(i)]]
        if changed: changes.append(dict(event=event, changed_candidates=changed))
    return dict(exact=not changes, first_differing_observed_event=changes[0] if changes else None,
        differences=changes, scope='Byte fingerprints of observed tensors; earliest observed difference is not a kernel cause.')


def reconstruct(items):
    def item(mode, traced, rep): return items[name(dict(mode=mode, traced=traced, repetition=rep)) + '.json']
    controls = {}; comparisons = {}; repeated = {}; cross = {}
    for mode in ('original', 'chunk8'):
        for traced in (False, True):
            key = mode + ('_traced_repeat' if traced else '_untraced_repeat')
            comparisons[key] = compare_predictions(item(mode, traced, 0)['prediction'], item(mode, traced, 1)['prediction'])
            controls[key] = comparisons[key]['exact_prediction']
        for rep in (0, 1):
            key = mode + '_hook_effect_' + str(rep)
            comparisons[key] = compare_predictions(item(mode, False, rep)['prediction'], item(mode, True, rep)['prediction'])
            controls[key] = comparisons[key]['exact_prediction']
        repeated[mode] = compare_traces(item(mode, True, 0)['trace'], item(mode, True, 1)['trace'])
        controls[mode + '_trace_repeat'] = repeated[mode]['exact']
    for rep in (0, 1):
        comparisons['original_vs_chunk_' + str(rep)] = compare_predictions(item('original', False, rep)['prediction'], item('chunk8', False, rep)['prediction'])
        cross[str(rep)] = compare_traces(item('original', True, rep)['trace'], item('chunk8', True, rep)['trace'])
    controls['cross_trace_localization_repeats'] = cross['0'] == cross['1']
    return dict(trace_valid=all(controls.values()), controls=controls, comparisons=comparisons,
                repeated_traces=repeated, cross_traces=cross, candidate_batch_admission=False,
                existing_e36_admission='failed; unchanged')


def verify_complete(path, q):
    q = Evidence(q)
    p = q.load(path); ph = q.sha(path); out = path.parent
    require(not (out / 'FAILED_GENERATION.json').exists() and not (out / 'FAILURE.json').exists(),
            'Failed generation cannot become successful')
    require(p['out'] == str(out) and p['schema'] == 'e38-path-trace-v1' and p['image'] == q.IMAGE,
            'Completion plan identity differs')
    require(p['candidate_batch_admission'] is False and p['schedule'] == schedule() and p['chunk_rows'] == 8, 'Protocol differs')
    require(q.load(out / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Parent review differs')
    review = q.load(out / 'INDEPENDENT_REVIEW.json')
    require(review['approved'] is True and review['approved_plan_sha256'] == ph
            and q.sha(review['review_path']) == review['review_sha256'], 'Independent review differs')
    q.frozen(p['files'])
    require(q.sha(p['source_config']) == p['source_config_sha256'], 'Native source changed')
    receipt = q.load(out / 'LAUNCH_RECEIPT.json'); d = q.inspect(p['container'])
    q.binding(d, q.load(p['container_spec']), receipt)
    require(receipt['plan_sha256'] == ph and receipt['wrapper_sha256'] == q.sha(p['wrapper'])
            and receipt['parent_review_sha256'] == q.sha(out / 'PARENT_REVIEW.json')
            and receipt['launcher_hostname'] == 'k8s-node1' and type(receipt['launcher_utc']) is str,
            'Launch receipt or parent approval snapshot differs')
    require(d['State']['Status'] == 'exited' and d['State']['ExitCode'] == 0, 'Retained Docker not successfully exited')
    require(re.fullmatch(r'rc=0 utc=\S+\n?', q.snapshot(out / 'EXIT').data.decode()), 'Wrapper exit differs')
    terminal = q.load(out / 'COMPLETE.json'); report = q.load(out / 'report.json')
    require(terminal['rc'] == 0 and terminal['stage'] == 'completed' and terminal['progress'] == terminal['total'] == 8
            and terminal['plan_sha256'] == ph, 'Terminal identity/count differs')
    require(set(terminal['outputs']) == {'SELECTION.json', 'report.json'}, 'Terminal output set differs')
    for n, h in terminal['outputs'].items(): require(q.sha(out / n) == h, 'Terminal output changed')
    require(q.load(out / 'SELECTION.json') == p['selection'] == report['selection'], 'Selection changed')
    committed = {n: q.sha(out / n) for n in ['COMPLETE.json', 'report.json', 'SELECTION.json', 'EXIT',
                                           'LAUNCH_RECEIPT.json', 'PARENT_REVIEW.json', 'INDEPENDENT_REVIEW.json']}
    before = {x.name: q.sha(x) for x in (out / 'items').iterdir()}
    items = validate_items(p, ph, complete=True, evidence=q); expected = reconstruct(items)
    require(report['plan_sha256'] == ph and report['input_sha256'] == stamp(p['input'])
            and all(report.get(k) == v for k, v in expected.items()), 'Independent E38 reconstruction differs')
    flags = ['E38 exact control failed: ' + k for k, passed in expected['controls'].items() if not passed]
    require(terminal.get('status') == ('COMPLETED_SCOPED_REVIEW_REQUIRED' if flags else 'COMPLETED_SCOPED')
            and terminal.get('trace_valid') is expected['trace_valid'] and terminal.get('review_flags') == flags,
            'Scientific terminal status differs from exact controls')
    attempt_manifest = validate_attempts(p, ph, items, q, complete=True)
    require(report.get('attempt_manifest') == attempt_manifest, 'Attempt manifest changed')
    manifest = {n: q.sha(out / 'items' / n) for n in sorted(items)}
    require(manifest == before == report['receipt_manifest'], 'Receipt manifest changed')
    require(sorted(x.name for x in (out / 'items').iterdir()) == sorted(items), 'Receipt population changed')
    require(committed == {n: q.sha(out / n) for n in committed} and q.sha(path) == ph, 'Completion evidence changed during verification')
    q.frozen(p['files'])
    q.verify()
    current = q.inspect(p['container'])
    require(current and current['Id'] == d['Id']
            and current['State']['Status'] == 'exited' and current['State']['ExitCode'] == 0
            and current['State']['StartedAt'] == d['State']['StartedAt']
            and current['State']['FinishedAt'] == d['State']['FinishedAt'],
            'NPU exit generation changed during independent verification')
    return dict(plan_sha256=ph, container_id=d['Id'], actual_exit=0,
                npu_started_at=d['State']['StartedAt'], npu_finished_at=d['State']['FinishedAt'],
                npu_exit_sha256=q.sha(out / 'EXIT'), npu_launch_receipt_sha256=q.sha(out / 'LAUNCH_RECEIPT.json'),
                terminal_sha256=q.sha(out / 'COMPLETE.json'), report_sha256=q.sha(out / 'report.json'),
                receipt_manifest=manifest, attempt_manifest=attempt_manifest, trace_valid=expected['trace_valid'], candidate_batch_admission=False,
                scope='Independent CPU receipt/trace reconstruction plus retained Docker identity; no new NPU forward, kernel cause or admission')


if __name__ == '__main__':
    raise SystemExit('Use prepare_openjev_path_trace.py --verify-plan with a detached CPU request')
