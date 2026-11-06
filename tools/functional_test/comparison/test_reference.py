"""Exact accepted metadata positives and generated adversarial negatives only."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parent
sys.path.insert(0, str(P))
import consumer as N
import reference as R


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = N.read(P / 'config.example.json')
        cls.metadata = N.read(N.pin(cls.config['reference_metadata']))
        cls.chain = R.validate_chain(N, cls.metadata)

    def documents(self):
        return {p['path']: N.read(p['path']) for p in self.metadata['pins']}

    def semantic_change(self, name, change, expected):
        # Policy injection tests typed/relational semantics beyond byte rejection;
        # real pins and files remain untouched, and no review is minted.
        docs = self.documents()
        path = next(p for p in docs if Path(p).name == name)
        change(docs[path])
        with patch.object(N, 'read', side_effect=lambda p: docs[p]):
            with self.assertRaisesRegex(ValueError, expected):
                R.validate_chain(N, self.metadata)

    def test_exact_existing_metadata_positive_count_hash_order(self):
        self.assertEqual(self.chain['population_bindings']['decision-v7'], {
            'n': 1200, 'sha256': N.DATA['decision-v7/test/clean'][1],
            'ordered_identity_sha256': '8cd95f8d537fcbe688f64de16501093fa7486af4f63e0f980dab4215a7bbe2a2'})
        self.assertEqual(self.chain['population_bindings']['transfer-v4']['n'], 656)
        R.match_populations(N, self.chain['population_bindings'], copy.deepcopy(self.chain['population_bindings']))

    def test_each_changed_metadata_file_bytes_rejected(self):
        for p in self.metadata['pins']:
            with self.subTest(file=p['path']), tempfile.TemporaryDirectory(dir=P/'scratch') as d:
                q = Path(d)/Path(p['path']).name
                q.write_bytes(Path(p['path']).read_bytes() + b'\n')
                meta = copy.deepcopy(self.metadata)
                next(x for x in meta['pins'] if x['path']==p['path'])['path']=str(q)
                with self.assertRaisesRegex(ValueError, 'changed bytes'): R.validate_chain(N, meta)

    def test_typed_reject_magicwords_never_accept(self):
        for name in ('REVIEW.json', 'REFERENCE-SEMANTIC-ACCEPTANCE.json'):
            self.semantic_change(name, lambda d: d.update(verdict='REJECT', prose='reference_mapping_addendum accepted pass'),
                                 'typed scoped acceptance|parent acceptance')

    def test_parent_review_link(self):
        self.semantic_change('REFERENCE-SEMANTIC-ACCEPTANCE.json', lambda d: d.update(review_sha256='0'*64), 'parent acceptance')

    def test_review_schema_scope_and_equivalence(self):
        for field, value in (('schema', 'other'), ('scientific_acceptance', False),
                             ('reference_semantic_mapping_gap_closed', False),
                             ('unqualified_raw_semantic_or_prompt_equivalence', True),
                             ('blocking_findings_for_scoped_mapping', ['blocking'])):
            self.semantic_change('REVIEW.json', lambda d: d.update({field:value}), 'typed scoped acceptance')

    def test_review_result_binding(self):
        self.semantic_change('REVIEW.json', lambda d: d['reviewed_result'].update(sha256='0'*64), 'reviewed_result')

    def test_result_receipt_and_inputpins_binding(self):
        for name in ('SOURCE-PIN-RECEIPT.json', 'INPUT-PINS.json'):
            self.semantic_change('RESULT.json', lambda d: d['evidence_sha256'].update({name:'0'*64}), 'RESULT evidence binding')
            path=next(p['path'] for p in self.metadata['pins'] if Path(p['path']).name==name)
            self.semantic_change('REVIEW.json', lambda d: d['input_pins'][path].update(sha256='0'*64), 'review input_pins binding')

    def test_converted_and_original_inputpins(self):
        paths = [p for p in self.chain['inputs']['files'] if p.endswith('/decision-v7/test.jsonl')]
        for path in paths:
            self.semantic_change('INPUT-PINS.json', lambda d: d['files'][path].update(observed_sha256='0'*64), 'source inputpins binding')

    def test_population_count_hash_order_individually(self):
        for suite in R.SUITES:
            for field in ('n', 'sha256', 'ordered_identity_sha256'):
                bad=copy.deepcopy(self.chain['population_bindings']);bad[suite][field]=123 if field=='n' else '0'*64
                with self.assertRaisesRegex(ValueError, 'population '+field):R.match_populations(N,self.chain['population_bindings'],bad)

    def test_actual_order_identity_encoding_candidates_gold(self):
        rows=[{'kev':{'id':'récord'},'qname':'問い','levels':[{'id':'a'},{'id':'b'}],'gold':'b'},
              {'kev':{'id':'second'},'qname':'q','levels':[{'id':'x'}],'gold':'x'}]
        import hashlib
        expected=[{'record_id':'récord','question':'問い','ids':['a','b'],'gold_index':1},
                  {'record_id':'second','question':'q','ids':['x'],'gold_index':0}]
        self.assertEqual(R.identity_hash(rows),hashlib.sha256(json.dumps(expected,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        for change in (lambda r:r.reverse(),lambda r:r[0]['levels'].reverse(),lambda r:r[0].update(gold='a')):
            bad=copy.deepcopy(rows);change(bad);self.assertNotEqual(R.identity_hash(rows),R.identity_hash(bad))

    def test_fake_population_cannot_borrow_real_approval_or_declared_hashes(self):
        # Full-size generated metadata, real-looking declared data hashes, caller
        # spoofed accepted order hash. Adapter recomputes actual row identities.
        pop={s+'/test/clean':[{'kev':{'id':f'fake-{i}'},'qname':'fake',
              'levels':[{'id':'a'},{'id':'b'}],'gold':'a'} for i in range(n)] for s,n in N.SUITES.items()}
        packet={'kind':'production','data_pins':{s+'/test/clean':{'n':n,'sha256':N.DATA[s+'/test/clean'][1]}
                for s,n in N.SUITES.items()}, 'reference_context':{'mapping_metadata':self.config['reference_metadata']},
                'ordered_identity_sha256':{s:v['ordered_identity_sha256'] for s,v in self.chain['population_bindings'].items()}}
        with self.assertRaisesRegex(ValueError, 'population ordered_identity_sha256'):N.reference_context(packet,self.config,pop)
        packet['kind']='generated'
        with self.assertRaisesRegex(ValueError, 'population ordered_identity_sha256'):N.reference_context(packet,self.config,pop)
        # Even patched real-looking identities cannot turn a generated packet into production.
        with patch.object(R, 'identity_hash', side_effect=[v['ordered_identity_sha256'] for v in self.chain['population_bindings'].values()]):
            with self.assertRaisesRegex(ValueError, 'generated populations'):R.context(N,packet,self.config,pop)

    def test_attachment_equivalence_claims_rejected(self):
        packet={'reference_context':{'mapping_metadata':self.config['reference_metadata'],'prompt_equivalent':True}}
        with self.assertRaisesRegex(ValueError,'attachment fields'):N.reference_context(packet,self.config,{})

    def test_mapping_alone_pending_and_performance_provenance(self):
        config={k:v for k,v in self.config.items() if k!='reference_performance_export'}
        r=N.reference_context({'kind':'generated'},config)
        self.assertEqual(r['status'],'pending');self.assertEqual(r['performance_status'],'not attached')
        r=N.reference_context({'kind':'generated'},self.config)
        self.assertEqual(r['status'],'pending');self.assertEqual(r['performance_status'],'complete historical context')
        perf=r['performance'];self.assertEqual(len(perf['local_pointer_panels']),4)
        self.assertEqual(len(perf['accepted_historical_continuation_panels']),14)
        self.assertEqual(perf['native_temperature'],2.3510958125672174)
        self.assertFalse(perf['paired_reference_claim']);self.assertIsNone(perf['paired_probability_loss_contrasts'])
        for panel in perf['local_pointer_panels']:
            self.assertEqual(panel['temperature'], R.NATIVE_T if panel['protocol']=='native' else 1)
            self.assertIn('json_pointer',panel['provenance']);self.assertTrue(panel['sources'])
        self.assertIn('Aggregate',str(perf['upstream_native_aggregate_only']))

    def test_unaccepted_performance_export_rejected(self):
        config=copy.deepcopy(self.config);config['reference_performance_export']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'not in accepted inputs'):N.reference_context({'kind':'generated'},config)

    def test_historical_binding_claim_rejected(self):
        for name in ('REVIEW.json','RESULT.json','SOURCE-PIN-RECEIPT.json'):
            self.semantic_change(name, lambda d:d.update(historical_reference_audit_sha_terminal_binding=True),'historical terminal')

    def test_no_raw_test_or_vector_reads(self):
        seen=[];original=N.read
        allowed={p['path'] for p in self.metadata['pins']} | {self.config['reference_metadata']['path'],
                  self.config['reference_performance_export']['path'],self.chain['review']['prior_review']['path']}
        def bounded(path):
            self.assertIn(str(path),allowed);seen.append(str(path));return original(path)
        with patch.object(N,'read',side_effect=bounded):N.reference_context({'kind':'generated'},self.config)
        self.assertEqual(set(seen),allowed)


if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    N.save(P/'reference-test-results.json', {'tests':result.testsRun,'successful':result.wasSuccessful(),
           'failures':[{'test':t.id(),'traceback':s} for t,s in result.failures],
           'errors':[{'test':t.id(),'traceback':s} for t,s in result.errors]})
    raise SystemExit(0 if result.wasSuccessful() else 1)
