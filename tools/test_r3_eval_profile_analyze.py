import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.r3_eval_profile_analyze import PHASES, reconstruct, sha


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ProfileAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        panel = self.root / 'panel.jsonl'
        rows = [dict(cell=str(c), id=str(i), row={'levels': ['a', 'b']}) for c in range(32) for i in range(32)]
        panel.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        profile = self.root / 'profile.json'
        put(profile, {'panel': {'path': str(panel), 'sha256': sha(panel)}})
        self.plan = self.root / 'plan.json'
        put(self.plan, dict(test_read=False, scientific_acceptance=False, candidate_selection_allowed=False,
                            chip=6, run='synthetic', files={}, out=str(self.root / 'out'),
                            profile={'path': str(profile), 'sha256': sha(profile)}))
        self.pin = sha(self.plan)
        for phase in PHASES:
            for c in range(32):
                path = self.operand(phase, str(c))
                put(path, dict(cell=str(c), encoded_sha256='abc', rows=[dict(id=str(i), s=[0.2, 0.8], index=1, tie=False) for i in range(32)]))
                put(path.with_suffix('.receipt.json'), dict(plan_sha256=self.pin, operand_sha256=sha(path), attempt=1,
                     score_wall_seconds=1., commit_seconds=.01, tokens_per_second_per_chip=32., counter_delta={'tokens': 32}))

    def operand(self, phase, cell='0'):
        return self.root / 'out/items' / phase / (hashlib.sha256(cell.encode()).hexdigest() + '.json')

    def change(self, phase, edit):
        path = self.operand(phase)
        value = json.loads(path.read_text())
        edit(value)
        put(path, value)
        receipt = path.with_suffix('.receipt.json')
        value = json.loads(receipt.read_text())
        value['operand_sha256'] = sha(path)
        put(receipt, value)

    def test_complete_operands_without_terminals_are_wait(self):
        out = reconstruct(self.plan, self.pin)
        self.assertEqual(out['status'], 'WAIT_TERMINAL')
        self.assertEqual(out['operand_chunks'], 224)
        self.assertEqual(len(out['missing']), 4)

    def test_rehashed_raw_change_rejected(self):
        self.change('wall_0', lambda v: v['rows'][0]['s'].__setitem__(0, .3))
        with self.assertRaisesRegex(ValueError, 'equality differs'):
            reconstruct(self.plan, self.pin)

    def test_rehashed_typed_change_rejected(self):
        self.change('cold_reference', lambda v: v['rows'][0].update(index=0))
        with self.assertRaisesRegex(ValueError, 'typed output differs'):
            reconstruct(self.plan, self.pin)

    def test_mixed_attempt_rejected(self):
        path = self.operand('wall_0').with_suffix('.receipt.json')
        value = json.loads(path.read_text())
        value['attempt'] = 2
        put(path, value)
        with self.assertRaisesRegex(ValueError, 'mixed/resumed'):
            reconstruct(self.plan, self.pin)

    def completed(self):
        trials, phases = [], {}
        for phase in PHASES:
            for c in range(32):
                r = json.loads(self.operand(phase, str(c)).with_suffix('.receipt.json').read_text())
                trials.append(dict(r, phase=phase, cell=str(c), rows=32))
            phases[phase] = dict(complete=True, chunks=32, score_wall_seconds=32., tokens=1024,
                tokens_per_second_per_chip=32., wall_seconds_including_commit_and_comparison=33., end_to_end_tokens_per_second_per_chip=1024/33.)
        a, h = self.root/'out/attempts/1', self.root/'out/host_attempts/1'
        put(a/'EXIT.json', dict(exit_code=0, attempt=1, plan_sha256=self.pin))
        put(h/'EXIT.json', dict(exit_code=0, container_exit_code=0, runner_terminal_matches=True, container_id='c'))
        put(h/'CLAIM.json', dict(schema='r3-resource-claim-v1', run='synthetic', chip=6))
        put(h/'RELEASE.json', dict(schema='r3-resource-release-v1', run='synthetic', chip=6, claim_sha256=sha(h/'CLAIM.json'), container_id='c'))
        put(h/'LAUNCH_RECEIPT.json', dict(container_id='c', plan_sha256=self.pin))
        put(a/'report.json', dict(schema='r3-profile-runtime-report-v1', reused_chunks=0, timing_comparable=True, all_raw_exact=True,
            trials=trials, phases=phases, test_read=False, scientific_acceptance=False,
            candidate_selection_allowed=False, runtime={'chips': 1, 'reserved_gib': 1., 'peak_reserved_gib': 1., 'model_load_seconds': 1.}, profile_overhead_ratio=1.))

    def test_complete_and_bound_generation_passes(self):
        self.completed()
        self.assertEqual(reconstruct(self.plan, self.pin)['status'], 'PASS_DIAGNOSTIC_ONLY')

    def test_foreign_release_generation_rejected(self):
        self.completed()
        path=self.root/'out/host_attempts/1/RELEASE.json'
        value=json.loads(path.read_text()); value['claim_sha256']='f'*64; put(path,value)
        with self.assertRaisesRegex(ValueError, 'release lineage'):
            reconstruct(self.plan, self.pin)

    def test_report_timing_not_derived_from_receipts_rejected(self):
        self.completed()
        path=self.root/'out/attempts/1/report.json'
        value=json.loads(path.read_text()); value['phases']['wall_0']['tokens']=1; put(path,value)
        with self.assertRaisesRegex(ValueError, 'phase reconstruction'):
            reconstruct(self.plan, self.pin)


    def test_boolean_operand_aliases_rejected_in_every_phase(self):
        for field, value in [('index', True), ('tie', 0), ('s', [False, True])]:
            with self.subTest(field=field):
                originals = {phase: self.operand(phase).read_bytes() for phase in PHASES}
                for phase in PHASES:
                    self.change(phase, lambda v: v['rows'][0].update({field: value}))
                with self.assertRaises(ValueError): reconstruct(self.plan, self.pin)
                for phase, raw in originals.items():
                    path=self.operand(phase);path.write_bytes(raw)
                    receipt=path.with_suffix('.receipt.json');v=json.loads(receipt.read_text());v['operand_sha256']=sha(path);put(receipt,v)

    def test_receipt_boolean_counters_timing_and_rate_rejected(self):
        path=self.operand('cold_reference').with_suffix('.receipt.json')
        original=json.loads(path.read_text())
        edits=[lambda v:v.update(attempt=True), lambda v:v.update(score_wall_seconds=True),
               lambda v:v.update(commit_seconds=False), lambda v:v['counter_delta'].update(tokens=True),
               lambda v:v.update(tokens_per_second_per_chip=True),
               lambda v:v.update(tokens_per_second_per_chip=31.)]
        for edit in edits:
            v=json.loads(json.dumps(original));edit(v);put(path,v)
            with self.assertRaises(ValueError): reconstruct(self.plan,self.pin)
        put(path,original)
        with self.assertRaises(ValueError): reconstruct(self.plan,self.pin,attempt=True)

    def test_terminal_and_report_boolean_aliases_rejected(self):
        self.completed()
        cases=[('attempts/1/EXIT.json', ['exit_code'], False),
               ('attempts/1/EXIT.json', ['attempt'], True),
               ('host_attempts/1/EXIT.json', ['exit_code'], False),
               ('host_attempts/1/EXIT.json', ['container_exit_code'], False),
               ('host_attempts/1/RELEASE.json', ['chip'], 6.0),
               ('attempts/1/report.json', ['reused_chunks'], False),
               ('attempts/1/report.json', ['runtime','chips'], True),
               ('attempts/1/report.json', ['runtime','reserved_gib'], True),
               ('attempts/1/report.json', ['phases','wall_0','chunks'], 32.0),
               ('attempts/1/report.json', ['phases','wall_0','tokens'], 1024.0),
               ('attempts/1/report.json', ['profile_overhead_ratio'], True)]
        for relative, keys, value in cases:
            with self.subTest(path=relative, keys=keys):
                path=self.root/'out'/relative;raw=path.read_bytes();doc=json.loads(raw);node=doc
                for key in keys[:-1]:node=node[key]
                node[keys[-1]]=value;put(path,doc)
                with self.assertRaises(ValueError):reconstruct(self.plan,self.pin)
                path.write_bytes(raw)

    def test_plan_chip_numeric_alias_rejected(self):
        doc=json.loads(self.plan.read_text());doc['chip']=6.0;put(self.plan,doc)
        with self.assertRaisesRegex(ValueError,'scope differs'):
            reconstruct(self.plan,sha(self.plan))

    def test_claim_chip_type_rejected_even_with_resigned_release(self):
        self.completed();base=self.root/'out/host_attempts/1';p=base/'CLAIM.json'
        d=json.loads(p.read_text());d['chip']=6.0;put(p,d)
        p=base/'RELEASE.json';d=json.loads(p.read_text());d['claim_sha256']=sha(base/'CLAIM.json');put(p,d)
        with self.assertRaisesRegex(ValueError,'release lineage'):
            reconstruct(self.plan,self.pin)

    def test_phase_score_throughput_and_peak_rejected(self):
        self.completed();path=self.root/'out/attempts/1/report.json';original=json.loads(path.read_text())
        for edit in [lambda v:v['phases']['wall_0'].update(tokens_per_second_per_chip=31.),
                     lambda v:v['runtime'].update(peak_reserved_gib=.5),
                     lambda v:v['trials'][0].update(attempt=True)]:
            v=json.loads(json.dumps(original));edit(v);put(path,v)
            with self.assertRaises(ValueError):reconstruct(self.plan,self.pin)


if __name__ == '__main__':
    unittest.main()
