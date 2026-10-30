"""Negative evidence for E35 omissions; CPU fixtures, not model correctness tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_jeval_inference_hardened as h


def q(kind='choice'):
    v = dict(type=kind, instructions='Choose the appropriate synthetic level.')
    if kind == 'choice':
        v['criteria'] = {'a': 'first', 'b': 'second'}
    elif kind == 'score':
        v['criteria'] = ['low', 'middle', 'high']
    return v


def eligible(family='kev', kind='choice'):
    x = dict(status='eligible', reason='within_native_budget', candidate_count=3 if kind == 'score' else 2,
             max_tokens=10, token_sha256='a' * 64)
    if family == 'kev':
        x['state_tokens'] = 4
    elif family == 'openjev':
        n = 1 if kind == 'noul' else x['candidate_count']
        x.update(lengths=[10] * n, token_sha256=['a' * 64] * n, native_record_sha256='b' * 64)
    else:
        x['candidate_token_ids'] = list(range(x['candidate_count']))
    return x


def output(family='kev', kind='choice'):
    ks = ['false', 'true'] if kind == 'noul' else ['a', 'b'] if kind == 'choice' else ['0', '1', '2']
    p = 1 / len(ks)
    answer = dict(type=kind)
    if kind == 'noul':
        answer['noul'] = .5
    else:
        answer.update(probabilities={k: round(p, 4) if family == 'kev' else p for k in ks},
                      confidence=p if family == 'nimble' else 0.)
        if kind == 'choice':
            answer['choice'] = 'a'
        else:
            answer.update(score=0 if family == 'nimble' else 1., legend={'0': 'low', '1': 'middle', '2': 'high'})
    return dict(answer=answer, native_probabilities={k: p for k in ks}, logits=[0.] * len(ks),
                logits_temperature='already_scaled' if family == 'kev' else 'unscaled',
                consumed_token_sha256=eligible(family, kind)['token_sha256'])


def probes(family='kev'):
    raw = dict(id='boundary', state='exact state', questions_json=json.dumps({'q': q()}), label_json='"a"', source='s')
    e = dict(eligible(family), index=0, id='boundary', input_sha256=h.stamp(raw))
    values = []
    for kind in ['choice', 'noul', 'score']:
        values.append(dict(request=dict(state='Synthetic observation: choose the first level.', questions={'q': q(kind)}),
                           passes=[dict(seconds=.1, prediction=output(family, kind)) for _ in range(2)]))
    values.append(dict(boundary_index=0, input_sha256=h.stamp(raw), max_tokens=10, chips=1, reserved_gib=1.,
                       passes=[dict(seconds=.1, prediction=output(family)) for _ in range(2)]))
    return values, {'items': [e]}, [raw]


class Hardened(unittest.TestCase):
    def strict(self, values=None, family='kev'):
        pp, ee, rr = probes(family)
        return h.strict_probes(dict(family=family, temperature=1.), pp if values is None else values, ee, rr,
                               lambda req: eligible(family, next(iter(req['questions'].values()))['type']))

    def test_real_native_schemas_for_all_three_families(self):
        for family in ['kev', 'openjev', 'nimble']:
            self.assertEqual(self.strict(family=family)['forwards'], 8)

    def test_original_zero_probability_wrong_schema_exploit_rejected(self):
        pp, _, _ = probes()
        for probe in pp:
            for one in probe['passes']:
                one['prediction']['native_probabilities'] = {'wrong-schema': 0.}
        with self.assertRaisesRegex(ValueError, 'Native probability schema'):
            self.strict(pp)

    def test_valid_keys_but_zero_mass_rejected(self):
        pp, _, _ = probes()
        pp[0]['passes'][0]['prediction']['native_probabilities'] = {'a': 0., 'b': 0.}
        with self.assertRaisesRegex(ValueError, 'probability mass'):
            self.strict(pp)

    def test_missing_answer_rejected(self):
        pp, _, _ = probes(); del pp[0]['passes'][0]['prediction']['answer']
        with self.assertRaisesRegex(ValueError, 'Prediction schema'):
            self.strict(pp)

    def test_wrong_logits_not_hidden_by_valid_probabilities(self):
        pp, _, _ = probes(); pp[0]['passes'][0]['prediction']['logits'] = [0., 2.]
        with self.assertRaisesRegex(ValueError, 'Logit probability arithmetic'):
            self.strict(pp)

    def test_wrong_synthetic_tokens_rejected(self):
        pp, _, _ = probes(); pp[0]['passes'][0]['prediction']['consumed_token_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'consumed tokens'):
            self.strict(pp)

    def test_wrong_boundary_tokens_rejected(self):
        pp, _, _ = probes(); pp[-1]['passes'][0]['prediction']['consumed_token_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'consumed tokens'):
            self.strict(pp)

    def test_forged_returned_score_and_legend_rejected(self):
        for field, val, msg in [('score', 0., 'Returned score'), ('legend', {'0': 'x', '1': 'middle', '2': 'high'}, 'Score legend')]:
            pp, _, _ = probes(); pp[2]['passes'][0]['prediction']['answer'][field] = val
            with self.assertRaisesRegex(ValueError, msg):
                self.strict(pp)

    def test_native_confidence_not_replaced_with_max_probability(self):
        pp, _, _ = probes(); pp[0]['passes'][0]['prediction']['answer']['confidence'] = .5
        with self.assertRaisesRegex(ValueError, 'Native confidence'):
            self.strict(pp)

    def test_empty_eligibility_exploit_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Complete eligibility schema'):
            h.exact_eligibility('kev', q(), {}, eligible())

    def test_missing_keys_rejected_for_each_family(self):
        for family in ['kev', 'openjev', 'nimble']:
            e = eligible(family); observed = copy.deepcopy(e); del observed['max_tokens']
            with self.assertRaisesRegex(ValueError, 'Complete eligibility schema'):
                h.exact_eligibility(family, q(), observed, e)

    def test_actual_failure_arm_schemas_remain_supported(self):
        cases = [('kev', dict(status='overlength', reason='native_context_overflow', candidate_count=2,
                             native_message='too long', state_tokens=None)),
                 ('kev', dict(eligible(), status='overlength', reason='packed_limit_16384')),
                 ('openjev', dict(eligible('openjev'), status='overlength', reason='candidate_limit_4096')),
                 ('nimble', dict(status='unsupported', reason='native_nonempty_context_required', candidate_count=2)),
                 ('nimble', dict(status='overlength', reason='native_prompt_limit_2048', candidate_count=2, max_tokens=3000))]
        for family, e in cases:
            h.exact_eligibility(family, q(), e, dict(e, index=0, source='s'))

    def test_omitted_resource_or_finisher_closure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'run'; run.mkdir(); finish = root / 'run_finish'; finish.mkdir()
            c = dict(out=str(run), files={})
            for name in h.SCRIPT_NAMES + ['NPU_SPEC.json', 'run.sh', 'LAUNCH_EXACT.sh', 'RESUME_EXACT.sh']:
                p = run / name; p.write_text('frozen'); c['files'][str(p)] = h.sha(p)
            for name in ['run.sh', 'LAUNCH_EXACT.sh']:
                p = finish / name; p.write_text('frozen'); c['files'][str(p)] = h.sha(p)
            for name in ['data', 'preregistration', 'eligibility_config', 'eligibility_report', 'probe_config', 'probe_report', 'probe_review']:
                p = root / name; p.write_text('frozen'); c[name] = str(p); c['files'][str(p)] = h.sha(p)
            h.required_closure(c)
            for p in [run / 'NPU_SPEC.json', finish / 'run.sh', finish / 'LAUNCH_EXACT.sh']:
                old = c['files'].pop(str(p))
                with self.assertRaisesRegex(ValueError, 'closure omitted'):
                    h.required_closure(c)
                c['files'][str(p)] = old

    def test_disaggregated_suspicious_successes_are_not_diluted(self):
        rows, items = [], []
        for kind, source, count in [('choice', 'perfect-a', 40), ('choice', 'perfect-b', 40), ('noul', 'always-wrong', 40), ('score', 'tiny', 2)]:
            for _ in range(count):
                rows.append(dict(questions_json=json.dumps({'q': q(kind)}), source=source,
                                 label_json=json.dumps('a' if kind == 'choice' else 0 if kind == 'noul' else 1)))
                items.append(dict(status='valid', **output('kev', kind)))
        cells, flags = h.cell_analysis(rows, items)
        codes = {v['code'] for v in flags}
        self.assertTrue({'exact_boundary_rate', 'identical_probability_vectors', 'small_population',
                         'zero_score_mae', 'identical_cell_metric'} <= codes)
        self.assertEqual(next(c['accuracy'] for c in cells if c['group'] == 'type' and c['type'] == 'noul'), 0.)
        self.assertTrue(all('pointer' in f or 'pointers' in f for f in flags))

    def test_ineligible_classification_kept_in_cell_denominator(self):
        rows = [dict(questions_json=json.dumps({'q': q()}), label_json='"a"', source='s')] * 2
        items = [dict(status='valid', **output()), dict(status='overlength')]
        cells, _ = h.cell_analysis(rows, items)
        self.assertEqual(cells[0]['accuracy'], .5)
        self.assertEqual(cells[0]['valid_accuracy'], 1.)

    def test_actual_docker_identity_and_resource_changes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); wrapper = run / 'run.sh'; wrapper.write_text('frozen')
            c = dict(out=str(run), container='expected', image='image', physical_chip=1)
            cp = run / 'config.json'; cp.write_text(json.dumps(c))
            spec = dict(Image='image', Cmd=['bash', str(wrapper)], Entrypoint=['entry'], Env=['A=B'],
                        HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs'],
                                        Devices=[dict(PathOnHost='/dev/davinci1', PathInContainer='/dev/davinci1', CgroupPermissions='rwm')],
                                        ShmSize=1024, NetworkMode='none'))
            (run / 'NPU_SPEC.json').write_text(json.dumps(spec))
            receipt = dict(container_id='cid', image='image', command=spec['Cmd'], entrypoint=['entry'],
                           config_sha256=h.sha(cp), wrapper_sha256=h.sha(wrapper))
            (run / 'LAUNCH_RECEIPT.json').write_text(json.dumps(receipt)); (run / 'EXIT').write_text('rc=0 utc=now\n')
            info = dict(Id='cid', Name='/expected', Image='image', Config=dict(Cmd=spec['Cmd'], Entrypoint=['entry'], Env=['A=B']),
                        HostConfig=copy.deepcopy(spec['HostConfig']), State=dict(Status='exited', ExitCode=0))
            h.run_binding(c, cp, lambda _: info)
            for mutate, message in [
                    (lambda d: d.update(Id='different'), 'Docker ID/name'),
                    (lambda d: d['Config'].update(Env=['A=C']), 'Docker environment'),
                    (lambda d: d['HostConfig'].update(Binds=[]), 'Docker mounts/devices'),
                    (lambda d: d['HostConfig']['Devices'][0].update(CgroupPermissions='r'), 'Docker mounts/devices'),
                    (lambda d: d['State'].update(Status='running'), 'Actual inference/probe exit')]:
                bad = copy.deepcopy(info); mutate(bad)
                with self.assertRaisesRegex(ValueError, message):
                    h.run_binding(c, cp, lambda _: bad)


if __name__ == '__main__':
    unittest.main()
