"""E38 schedule, independent reconstruction and corruption tests. No NPU."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


def module(filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location('test_' + path.stem, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj


run = module('openjev_path_trace_run.py')
v = module('verify_openjev_path_trace.py')
q = module('jeval_reference_queue.py')


def frozen_input():
    keys = [str(i) for i in range(15)]
    req = {'state': 'fixed', 'questions': {'q': {'type': 'choice', 'options': dict.fromkeys(keys, 'candidate')}}}
    return dict(index=4200, id='fixture', request=req, request_sha256=v.stamp(req),
                token_sha256=[v.stamp(i) for i in range(15)], candidate_order=keys,
                ordered_id_row_hashes=[v.stamp(['id', i]) for i in range(15)],
                ordered_mask_row_hashes=[v.stamp(['mask', i]) for i in range(15)], shape=[15, 186])


def contract():
    return dict(layer_count=24, expected_events=['layer:input', 'layer:output'], observed_modules=['layer'])


def fake_trace(mode, changed=False):
    c = contract(); order = c['expected_events']
    ranges = [[0, 15, 186]] if mode == 'original' else [[0, 8, 186], [8, 15, 186]]
    return dict(candidates=15, width=186, expected_events=order[:], observed_modules=['layer'], order=order[:],
        chunks=[dict(range=r, order=order[:]) for r in ranges], events={e: dict(dtype='torch.bfloat16', row_shape=[186, 2],
        rows={str(i): v.stamp([e, i, bool(changed and i == 8 and e == 'layer:output')]) for i in range(15)}) for e in order})


def prediction(inp, changed=False):
    probs = {k: 1 / 15 for k in inp['candidate_order']}
    if changed: probs['0'] += .001; probs['1'] -= .001
    return dict(answer=dict(type='choice', choice='0', probabilities=probs.copy(), confidence=probs['0']),
                native_probabilities=probs, logits=[.001 if changed and i == 0 else 0. for i in range(15)],
                logits_temperature='unscaled', consumed_token_sha256=inp['token_sha256'])


def payload(plan, ph, t):
    value = dict(**v.identity(plan, ph, t), prediction=prediction(plan['input'], t['mode'] == 'chunk8'),
        trace=fake_trace(t['mode'], t['mode'] == 'chunk8') if t['traced'] else {},
        observed_input={k: plan['input'][k] for k in ['shape', 'ordered_id_row_hashes', 'ordered_mask_row_hashes']},
        seconds=2., questions_per_second_per_chip=.5, chips=1, reserved_gib=3., peak_reserved_gib=4., peak_allocated_gib=2.)
    return value


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name); self.folder = self.out / 'items'; self.folder.mkdir()
        self.plan = dict(out=str(self.out), schema='e38-path-trace-v1', input=frozen_input(), trace_contract=contract(),
            source_config_sha256='source', schedule=v.schedule(), selection={'index':4200}, chunk_rows=8,
            candidate_batch_admission=False)
        self.ph = 'plan'
    def save(self, t, mutate=None):
        val = payload(self.plan, self.ph, t)
        if mutate: mutate(val)
        p = self.folder / (v.name(t) + '.json')
        q.atomic(p, dict(payload=val, sha256=v.stamp(val))); return p
    def full(self):
        for task in v.schedule(): self.save(task)
        return v.validate_items(self.plan, self.ph, complete=True)


class ReceiptControls(Fixture):
    def test_full_independent_reconstruction_matches_driver(self):
        got = self.full(); independent = v.reconstruct(got)
        producer = run.analyze({k[:-5]: val for k, val in got.items()})
        self.assertEqual(independent, producer); self.assertTrue(independent['trace_valid'])
        self.assertFalse(independent['candidate_batch_admission'])
        self.assertEqual(independent['cross_traces']['0']['first_differing_observed_event'],
                         {'event':'layer:output','changed_candidates':[8]})

    def test_every_repeat_and_hook_control_is_enforced(self):
        original = self.full()
        for t in v.schedule():
            got = copy.deepcopy(original); cell = got[v.name(t)+'.json']; cell['prediction']['logits'][2] += .01
            with self.subTest(task=t):
                self.assertFalse(v.reconstruct(got)['trace_valid'])

    def test_trace_repeat_and_cross_localization_change_invalidates(self):
        got = self.full(); got['4200_chunk8_traced_1.json']['trace']['events']['layer:input']['rows']['0'] = 'a'*64
        result=v.reconstruct(got); self.assertFalse(result['trace_valid'])
        self.assertFalse(result['controls']['chunk8_trace_repeat'])
        self.assertFalse(result['controls']['cross_trace_localization_repeats'])

    def test_signed_zero_prediction_is_not_exact(self):
        got=self.full(); got['4200_original_untraced_1.json']['prediction']['logits'][1] = -0.
        self.assertFalse(v.reconstruct(got)['trace_valid'])

    def test_schedule_missing_extra_relabelled_and_nonprefix_rejected(self):
        self.full(); (self.folder/'4200_original_untraced_0.json').unlink()
        with self.assertRaisesRegex(ValueError,'prefix'): v.validate_items(self.plan,self.ph,True)
        for p in self.folder.iterdir():p.unlink()
        self.save(v.schedule()[1])
        with self.assertRaisesRegex(ValueError,'prefix'):v.validate_items(self.plan,self.ph,False)
        for p in self.folder.iterdir():p.unlink()
        path=self.save(v.schedule()[0]); path.rename(self.folder/'unknown.json')
        with self.assertRaisesRegex(ValueError,'Unknown'):v.validate_items(self.plan,self.ph,False)

    def test_changed_hash_or_rehashed_identity_rejected(self):
        path=self.save(v.schedule()[0]); env=q.load(path);env['payload']['index']=9027;q.atomic(path,env)
        with self.assertRaisesRegex(ValueError,'hash'):v.validate_items(self.plan,self.ph)
        env['sha256']=v.stamp(env['payload']);q.atomic(path,env)
        with self.assertRaisesRegex(ValueError,'identity'):v.validate_items(self.plan,self.ph)

    def test_padded_input_and_candidate_order_not_only_clean_tokens_checked(self):
        for mutation in [lambda x:x['observed_input']['ordered_mask_row_hashes'].reverse(),
                         lambda x:x['prediction']['consumed_token_sha256'].reverse(),
                         lambda x:x['prediction'].update(native_probabilities=dict(reversed(list(x['prediction']['native_probabilities'].items()))))]:
            path=self.save(v.schedule()[0],mutation)
            with self.assertRaises(ValueError):v.validate_items(self.plan,self.ph)
            path.unlink()

    def test_nonfinite_probabilities_statistics_and_boolean_repetition_rejected(self):
        for mutation in [lambda x:x.update(seconds=0), lambda x:x.update(repetition=False),
                         lambda x:x['prediction']['native_probabilities'].update({'0':1.5}),
                         lambda x:x.update(questions_per_second_per_chip=.6)]:
            path=self.save(v.schedule()[0],mutation)
            with self.assertRaises(ValueError):v.validate_items(self.plan,self.ph)
            path.unlink()

    def test_strict_partial_next_item_and_symlink_rejected(self):
        self.save(v.schedule()[0]); tmp=self.folder/'4200_original_untraced_1.json.tmp';tmp.write_text('{')
        self.assertEqual(len(v.validate_items(self.plan,self.ph)),1)
        tmp.rename(self.folder/'4200_chunk8_untraced_1.json.tmp')
        with self.assertRaisesRegex(ValueError,'next scheduled'):v.validate_items(self.plan,self.ph)
        for p in self.folder.iterdir():p.unlink()
        target=self.out/'foreign';target.write_text('{}');(self.folder/'4200_original_untraced_0.json').symlink_to(target)
        with self.assertRaisesRegex(ValueError,'symlink'):v.validate_items(self.plan,self.ph)

    def test_trace_missing_event_even_with_self_consistent_rehash_rejected(self):
        self.full(); path=self.folder/'4200_original_traced_0.json';env=q.load(path);trace=env['payload']['trace']
        del trace['events']['layer:output']; trace['order'].remove('layer:output');trace['expected_events'].remove('layer:output')
        for c in trace['chunks']:c['order'].remove('layer:output')
        env['sha256']=v.stamp(env['payload']);q.atomic(path,env)
        with self.assertRaisesRegex(ValueError,'frozen native hook'):v.validate_items(self.plan,self.ph,True)

    def test_trace_bad_hash_overlap_candidate_and_order_rejected(self):
        for mutation in [lambda t:t['events']['layer:input']['rows'].pop('14'),
                         lambda t:t['events']['layer:input']['rows'].update({'8':'not-a-hash'}),
                         lambda t:t['chunks'][1].update(range=[7,15,186]),
                         lambda t:t['chunks'][1]['order'].reverse()]:
            trace=fake_trace('chunk8');mutation(trace)
            with self.assertRaises(ValueError):v.check_trace(trace,self.plan,'chunk8')


class PureContracts(unittest.TestCase):
    def test_invalid_controls_publish_review_required_terminal(self):
        report=dict(trace_valid=False,controls={'repeat':False,'hook':False,'tokens':True})
        status=run.scientific_terminal(report)
        self.assertEqual(status['status'],'COMPLETED_SCOPED_REVIEW_REQUIRED')
        self.assertIs(status['trace_valid'],False);self.assertEqual(len(status['review_flags']),2)
        self.assertEqual(run.scientific_terminal(dict(trace_valid=True,controls={'repeat':True})),
                         dict(status='COMPLETED_SCOPED',trace_valid=True,review_flags=[]))
        self.assertEqual(run.scientific_terminal(None)['status'],'FAILED')

    def test_fixed_schedule_order(self):
        self.assertEqual(run.schedule(),v.schedule()); self.assertEqual(len(run.schedule()),8)
        self.assertEqual([run.name(t) for t in run.schedule()],
            ['4200_original_untraced_0','4200_original_untraced_1','4200_chunk8_untraced_0','4200_chunk8_untraced_1',
             '4200_original_traced_0','4200_original_traced_1','4200_chunk8_traced_0','4200_chunk8_traced_1'])

    def test_selection_rejects_other_index_or_width(self):
        entry=dict(index=4200,id='fixed',status='eligible',lengths=[186]*15,candidate_count=15,max_tokens=186)
        self.assertEqual(run.select({'items':[entry]})['index'],4200)
        for change in [dict(index=4201),dict(max_tokens=187),dict(lengths=[186]*14),dict(status='overlength')]:
            e=dict(entry,**change)
            with self.assertRaises(ValueError):run.select({'items':[e]})

    def test_trace_contract_native_layer_population(self):
        layers=[dict(name='base_model.model.layers.'+str(i),module_type='Qwen3_5DecoderLayer',
            attention_type='Qwen3_5Attention' if i%4==3 else 'Qwen3_5GatedDeltaNet') for i in range(24)]
        c=run.trace_contract(layers);self.assertEqual(len(c['expected_events']),696)
        self.assertEqual(len(c['expected_events']),len(set(c['expected_events'])))
        layers[0]['name']='foreign'
        with self.assertRaises(ValueError):run.trace_contract(layers)


try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'CPU torch required for integrated native execution')
class NativeIntegration(unittest.TestCase):
    def test_native_guard_trace_chunks_nesting_and_cleanup(self):
        try:
            from transformers.models.qwen3_5.configuration_qwen3_5 import Qwen3_5TextConfig
            from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5TextModel
        except ImportError:
            self.skipTest('Native Qwen3.5 unavailable')
        torch.set_num_threads(1); torch.manual_seed(381)
        config = Qwen3_5TextConfig(vocab_size=32,hidden_size=16,intermediate_size=24,
            num_hidden_layers=24,num_attention_heads=2,num_key_value_heads=1,head_dim=8,
            linear_num_key_heads=1,linear_num_value_heads=2,linear_key_head_dim=4,linear_value_head_dim=4,
            layer_types=['linear_attention','linear_attention','linear_attention','full_attention']*6,
            rope_parameters={'rope_type':'default','rope_theta':10000.,'partial_rotary_factor':1.,'mrope_section':[1,1,2]},
            use_cache=False)
        config._attn_implementation='sdpa'; model=Qwen3_5TextModel(config).eval()
        ids=torch.arange(15*186).reshape(15,186)%32; mask=torch.ones_like(ids);mask[:,170:]=0
        expected=dict(shape=[15,186],ordered_id_row_hashes=[v.stamp(r) for r in ids.tolist()],
                      ordered_mask_row_hashes=[v.stamp(r) for r in mask.tolist()])
        tracing=module('openjev_path_trace.py');chunks=module('openjev_candidate_chunks.py')
        baseline={};observed={};split={};full={}
        args=dict(input_ids=ids,attention_mask=mask,use_cache=False,return_dict=True)
        with torch.inference_mode():
            with run.input_guard(model,expected,baseline): ref=model(**args).last_hidden_state
            with run.input_guard(model,expected,observed):
                with tracing.trace_path(model,torch,full): traced=model(**args).last_hidden_state
            self.assertTrue(torch.equal(ref,traced));self.assertEqual(baseline,observed)
            observed={}
            with run.input_guard(model,expected,observed):
                with tracing.trace_path(model,torch,split) as observer:
                    with chunks.candidate_chunks(model,8,observer): model(**args)
            self.assertEqual(observed,expected)
            self.assertEqual([x['range'] for x in split['chunks']],[[0,8,186],[8,15,186]])
            self.assertEqual(full['order'],split['order'])
            wrong=copy.deepcopy(expected);wrong['ordered_mask_row_hashes'][0]='wrong'
            with self.assertRaisesRegex(ValueError,'token/mask'):
                with run.input_guard(model,wrong,{}):model(**args)
        self.assertTrue(all(not m._forward_hooks and not m._forward_pre_hooks for m in model.modules()))


if __name__=='__main__':unittest.main()
