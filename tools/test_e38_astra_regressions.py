"""Independent regressions for actual Astra E38 v2 blockers; CPU and offline only.

The fixture retains eight actual E37 4200 receipt envelopes verbatim, including
original file SHA-256, so native formatting assertions cannot be manufactured by
copying the E38 producer. No CephFS, weights, tokenizer, Docker or NPU is needed.
"""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


def module(filename):
    p = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location('astra_regression_' + p.stem, p)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


v = module('verify_openjev_path_trace.py')
FIXTURE_PATH = Path(__file__).parent / 'fixtures/e38_e37_native_predictions.json'
FIXTURE_SHA256 = '8f93ee9e7ea177a8ec5c8d56b86cc2dbbfa6fddc93338388d4405796cd8aa470'
if hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() != FIXTURE_SHA256:
    raise AssertionError('Hash-bound E37 fixture changed')
FIXTURE = json.loads(FIXTURE_PATH.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp(value):
    return digest(json.dumps(value, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def plan_for(record):
    return {'input': copy.deepcopy(FIXTURE['frozen_input']),
            'numeric_contract': {'temperature': record['temperature'],
                                 'probability_mass_atol': 1e-6, 'probability_mass_rtol': 1e-6,
                                 'logit_probability_atol': 1e-5, 'wire_probability_atol': 1e-8,
                                 'confidence_atol': 1e-7, 'argmax_tie': 'first_in_candidate_order'}}


def actual_prediction(record):
    raw = record['raw_receipt_json'].encode()
    if digest(raw) != record['source_file_sha256']:
        raise AssertionError('Actual E37 fixture bytes changed')
    envelope = json.loads(raw)
    if stamp(envelope['payload']) != envelope['sha256']:
        raise AssertionError('Actual E37 envelope changed')
    return copy.deepcopy(envelope['payload']['prediction'])


def independent_wire(probabilities, choice=None):
    # The frozen Open-Jev API normalizes its probability mapping before
    # formatting; native confidence is chance-adjusted, not selected p.
    total = sum(probabilities.values())
    wire = {k: x / total for k, x in probabilities.items()}
    selected = max(wire, key=wire.get) if choice is None else choice
    top = max(wire.values())
    confidence = (top - 1 / len(wire)) / (1 - 1 / len(wire))
    return dict(type='choice', choice=selected, probabilities=wire,
                confidence=confidence)


class NativeAnswerRegressions(unittest.TestCase):
    def test_eight_actual_e37_answers_accepted_without_rewriting(self):
        self.assertEqual(len(FIXTURE['records']), 8)
        for rec in FIXTURE['records']:
            with self.subTest(model=rec['model'], source=rec['source_path']):
                pred = actual_prediction(rec)
                before = copy.deepcopy(pred)
                v.check_prediction(pred, plan_for(rec))
                self.assertEqual(pred, before)

    def test_fixture_has_chance_adjusted_confidence_and_wire_normalization(self):
        for rec in FIXTURE['records']:
            pred = actual_prediction(rec)
            self.assertNotEqual(pred['answer']['confidence'],
                                pred['native_probabilities'][pred['answer']['choice']])
            expected = independent_wire(pred['native_probabilities'])
            self.assertEqual(expected['choice'], pred['answer']['choice'])
            # Python 3.11 versus frozen 3.12 sum differs at one ULP; this
            # fixture sanity check is not the exact repeat-control protocol.
            self.assertAlmostEqual(expected['confidence'], pred['answer']['confidence'], places=14)
            for key, value in expected['probabilities'].items():
                self.assertAlmostEqual(value, pred['answer']['probabilities'][key], places=14)

    def test_one_ulp_repeat_difference_remains_nonexact(self):
        pred = actual_prediction(FIXTURE['records'][0])
        changed = copy.deepcopy(pred)
        changed['logits'][0] = math.nextafter(changed['logits'][0], math.inf)
        result = v.compare_predictions(pred, changed)
        self.assertFalse(result['exact_prediction'])
        self.assertGreater(result['logits_max_delta'], 0.)

    def test_all_zero_probability_vector_rejected(self):
        rec = FIXTURE['records'][0]
        pred = actual_prediction(rec)
        probs = dict.fromkeys(pred['native_probabilities'], 0.)
        pred.update(native_probabilities=probs, logits=[0.] * 15)
        pred['answer'] = dict(type='choice', choice=next(iter(probs)),
                              probabilities=probs.copy(), confidence=0.)
        with self.assertRaises(ValueError):
            v.check_prediction(pred, plan_for(rec))

    def test_wrong_non_argmax_choice_rejected(self):
        rec = FIXTURE['records'][0]
        pred = actual_prediction(rec)
        keys = list(pred['native_probabilities'])
        top = .5
        confidence = (top - 1 / 15) / (1 - 1 / 15)
        # The incorrect selected p equals the correct chance-adjusted confidence,
        # so v2's bad confidence check cannot accidentally reject this example.
        values = [top, confidence] + [(1 - top - confidence) / 13] * 12
        values.append(1 - sum(values))
        probs = dict(zip(keys, values))
        pred['native_probabilities'] = probs
        pred['logits'] = [rec['temperature'] * math.log(x) for x in values]
        pred['answer'] = dict(type='choice', choice=keys[1],
                              probabilities=probs.copy(), confidence=confidence)
        with self.assertRaises(ValueError):
            v.check_prediction(pred, plan_for(rec))

    def test_logits_disconnected_from_probability_vector_rejected(self):
        rec = FIXTURE['records'][0]
        pred = actual_prediction(rec)
        keys = list(pred['native_probabilities'])
        probs = dict.fromkeys(keys, 0.); probs[keys[0]] = 1.
        pred.update(logits=[0.] * 15, native_probabilities=probs)
        pred['answer'] = dict(type='choice', choice=keys[0],
                              probabilities=probs.copy(), confidence=1.)
        with self.assertRaises(ValueError):
            v.check_prediction(pred, plan_for(rec))

    def test_nonunit_probability_mass_rejected(self):
        rec = FIXTURE['records'][0]
        pred = actual_prediction(rec)
        keys = list(pred['native_probabilities'])
        probs = dict.fromkeys(keys, 0.); probs[keys[0]] = .5
        pred['native_probabilities'] = probs
        pred['answer'] = dict(type='choice', choice=keys[0],
                              probabilities=probs.copy(), confidence=.5)
        with self.assertRaises(ValueError):
            v.check_prediction(pred, plan_for(rec))


def trace_plan_and_value():
    # Three known points at one decoder boundary: registration order deliberately
    # differs from actual call order. Expected metadata is authored independently.
    registered = ['layer:input', 'layer:output', 'layer.norm:input']
    order = ['layer:input', 'layer.norm:input', 'layer:output']
    metadata = {e: dict(dtype='torch.bfloat16', row_shape=[186, 32],
                        layout={'kind': 'batch_first', 'source_batch_axis': 0}) for e in order}
    contract = dict(layer_count=24, expected_events=registered,
                    observed_modules=['layer', 'layer.norm'], order=order,
                    events=copy.deepcopy(metadata))
    trace = dict(candidates=15, width=186, expected_events=registered[:],
                 observed_modules=['layer', 'layer.norm'], order=order[:],
                 chunks=[dict(range=[0, 15, 186], order=order[:])],
                 events={e: dict(**metadata[e], rows={str(i): stamp([e, i])
                                                     for i in range(15)}) for e in order})
    return {'trace_contract': contract}, trace


class TraceContractRegressions(unittest.TestCase):
    def test_authored_execution_order_and_layout_accepted(self):
        plan, trace = trace_plan_and_value()
        v.check_trace(trace, plan, 'original')

    def test_reversed_execution_order_rejected_even_if_every_chunk_agrees(self):
        plan, trace = trace_plan_and_value()
        trace['order'].reverse()
        for chunk in trace['chunks']:
            chunk['order'] = trace['order'][:]
        with self.assertRaises(ValueError):
            v.check_trace(trace, plan, 'original')

    def test_uniform_wrong_dtype_rejected(self):
        plan, trace = trace_plan_and_value()
        for event in trace['events'].values():
            event['dtype'] = 'torch.float64'
        with self.assertRaises(ValueError):
            v.check_trace(trace, plan, 'original')

    def test_uniform_wrong_row_shape_rejected(self):
        plan, trace = trace_plan_and_value()
        for event in trace['events'].values():
            event['row_shape'] = [1]
        with self.assertRaises(ValueError):
            v.check_trace(trace, plan, 'original')

    def test_folded_batch_mapping_checked_against_contract(self):
        plan, trace = trace_plan_and_value()
        event = 'layer.norm:input'
        expected = {'dtype': 'torch.bfloat16', 'row_shape': [186, 2, 128],
                    'layout': {'kind': 'folded_batch_sequence_heads',
                               'sequence_length': 186, 'heads': 2, 'head_dim': 128}}
        plan['trace_contract']['events'][event] = copy.deepcopy(expected)
        trace['events'][event].update(copy.deepcopy(expected))
        v.check_trace(trace, plan, 'original')
        trace['events'][event]['layout']['heads'] = 1
        with self.assertRaises(ValueError):
            v.check_trace(trace, plan, 'original')


class CompletionReadRaceRegressions(unittest.TestCase):
    """Only external Docker/permission checks and unrelated prediction validation
    are stubbed; the actual completion reader, hashes and report reconstruction
    are exercised against a private temporary filesystem.
    """
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.source = self.out / 'source.json'; write(self.source, {})
        self.wrapper = self.out / 'run.sh'; self.wrapper.write_text('fixture wrapper\n')
        self.spec = self.out / 'spec.json'; write(self.spec, {})
        contract, self.trace = trace_plan_and_value()
        self.plan = dict(out=str(self.out), schema='e38-path-trace-v1', image='fixture-image',
                         execution_revision='astra-v3-strict-attempts',
                         candidate_batch_admission=False, schedule=v.schedule(), chunk_rows=8,
                         source_config=str(self.source), source_config_sha256=digest(self.source.read_bytes()),
                         container='fixture-container', container_spec=str(self.spec),
                         wrapper=str(self.wrapper), files={}, selection={'index': 4200},
                         trace_contract=contract['trace_contract'], **plan_for(FIXTURE['records'][0]))
        self.plan_path = self.out / 'plan.json'; write(self.plan_path, self.plan)
        self.ph = digest(self.plan_path.read_bytes())
        write(self.out / 'PARENT_REVIEW.json', {'approved_plan_sha256': self.ph})
        independent = self.out / 'review.md'; independent.write_text('test-only review')
        write(self.out / 'INDEPENDENT_REVIEW.json', dict(approved=True, approved_plan_sha256=self.ph,
              review_path=str(independent), review_sha256=digest(independent.read_bytes())))
        write(self.out / 'LAUNCH_RECEIPT.json', dict(plan_sha256=self.ph,
              wrapper_sha256=digest(self.wrapper.read_bytes()),
              parent_review_sha256=digest((self.out/'PARENT_REVIEW.json').read_bytes()),
              launcher_hostname='k8s-node1', launcher_utc='2026-10-31T00:00:00Z'))
        write(self.out / 'SELECTION.json', self.plan['selection'])
        (self.out / 'EXIT').write_text('rc=0 utc=2026-10-31T00:00:00Z\n')
        self.items = self.out / 'items'; self.items.mkdir()
        self.attempts = self.out / 'attempts'; self.attempts.mkdir()
        values = {}
        for t in v.schedule():
            pred = actual_prediction(FIXTURE['records'][0])
            tr = copy.deepcopy(self.trace) if t['traced'] else {}
            if t['traced'] and t['mode'] == 'chunk8':
                tr['chunks'] = [dict(range=x, order=tr['order'][:]) for x in [[0,8,186],[8,15,186]]]
            value = dict(plan_sha256=self.ph, source_config_sha256=self.plan['source_config_sha256'],
                         input_sha256=stamp(self.plan['input']), request_sha256=self.plan['input']['request_sha256'],
                         index=4200, **t, prediction=pred, trace=tr,
                         observed_input={k:self.plan['input'][k] for k in ['shape','ordered_id_row_hashes','ordered_mask_row_hashes']},
                         chips=1, seconds=2., questions_per_second_per_chip=.5,
                         reserved_gib=1., peak_allocated_gib=1., peak_reserved_gib=1.)
            filename=v.name(t)+'.json'
            attempt = dict(plan_sha256=self.ph,
                           source_config_sha256=self.plan['source_config_sha256'],
                           input_sha256=stamp(self.plan['input']),
                           request_sha256=self.plan['input']['request_sha256'],
                           index=4200, **t, phase='forward_intent', utc='2026-10-31T00:00:00Z')
            write(self.attempts/filename, attempt)
            value['attempt_sha256'] = digest((self.attempts/filename).read_bytes())
            write(self.items/filename,dict(payload=value,sha256=stamp(value)))
            values[filename]=value
        self.report = dict(plan_sha256=self.ph, selection=self.plan['selection'],
                           input_sha256=stamp(self.plan['input']),
                           receipt_manifest={name:digest((self.items/name).read_bytes()) for name in sorted(values)},
                           attempt_manifest={name:digest((self.attempts/name).read_bytes()) for name in sorted(values)},
                           **v.reconstruct(values))
        self.report_path=self.out/'report.json';write(self.report_path,self.report)
        self.good_bytes=self.report_path.read_bytes()
        bad=copy.deepcopy(self.report);bad['comparisons']['original_untraced_repeat']['logits_max_delta']=999
        self.bad_bytes=(json.dumps(bad,ensure_ascii=False,indent=2)+'\n').encode()
        self.terminal=dict(rc=0,stage='completed',progress=8,total=8,plan_sha256=self.ph,
             outputs={'SELECTION.json':digest((self.out/'SELECTION.json').read_bytes()),
                      'report.json':digest(self.good_bytes)},status='COMPLETED_SCOPED',
             trace_valid=True,review_flags=[])
        write(self.out/'COMPLETE.json',self.terminal)
        self.helper=types.SimpleNamespace(
            IMAGE='fixture-image',load=lambda p:json.loads(Path(p).read_text()),
            sha=lambda p:digest(Path(p).read_bytes()),frozen=lambda p:None,
            inspect=lambda c:dict(Id='fixture-id',State=dict(Status='exited',ExitCode=0,
                StartedAt='2026-10-31T00:00:00Z', FinishedAt='2026-10-31T00:01:00Z')),
            binding=lambda *a:None)
        for name in ['check_prediction','check_trace']:
            guard=patch.object(v,name,return_value=None);guard.start();self.addCleanup(guard.stop)

    def test_stable_valid_completion_accepted(self):
        result=v.verify_complete(self.plan_path,self.helper)
        self.assertEqual(result['report_sha256'],digest(self.good_bytes))

    def test_stable_wrong_report_rejected(self):
        self.report_path.write_bytes(self.bad_bytes)
        self.terminal['outputs']['report.json']=digest(self.bad_bytes)
        write(self.out/'COMPLETE.json',self.terminal)
        with self.assertRaises(ValueError):v.verify_complete(self.plan_path,self.helper)

    def test_one_atomic_replace_after_parse_cannot_commit_different_report(self):
        # Terminal already references the bytes a concurrent writer will publish.
        # The report reader must bind the bytes it parsed, not hash later bytes.
        self.terminal['outputs']['report.json']=digest(self.bad_bytes)
        write(self.out/'COMPLETE.json',self.terminal)
        original=json.loads;replaced=[]
        def parse_then_replace(raw,*args,**kwargs):
            obj=original(raw,*args,**kwargs)
            received=raw.encode() if isinstance(raw,str) else bytes(raw)
            if not replaced and received==self.good_bytes:
                swap=self.out/'replacement.tmp';swap.write_bytes(self.bad_bytes);swap.replace(self.report_path)
                replaced.append(True)
            return obj
        with patch.object(json,'loads',side_effect=parse_then_replace):
            with self.assertRaises(ValueError):v.verify_complete(self.plan_path,self.helper)
        self.assertEqual(replaced,[True], 'Test must reach the report-parse race window')
        self.assertEqual(self.report_path.read_bytes(),self.bad_bytes)


if __name__ == '__main__':
    unittest.main()
