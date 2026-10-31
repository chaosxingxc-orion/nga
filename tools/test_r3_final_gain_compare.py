"""Synthetic same-test arithmetic counterexamples, never real test access."""
import copy
import unittest
from unittest.mock import patch
import r3_final_gain_compare as G


def report(seed=None):
    out={'schema':'r3-verified-test-vector-v1','partition':'test','protocol':dict(G.PROTOCOL),
         'scoring_protocol_sha256':'e'*64,'arm':'K0' if seed is None else 'K1','verified_evidence_sha256':str(seed or 0)*64,
         'model':{'path':'/base' if seed is None else '/adapter'+str(seed),'base_path':'/base',
                  'sha256':'a'*64,'base_inventory_sha256':'b'*64,
                  'kind':'checkpoint' if seed is None else 'lora-adapter-unmerged'},
         'suites':{s:{'dataset_sha256':'c'*64,'keys':[str(i) for i in range(n)],
                      'correct':[0]*n} for s,n in G.SUITES.items()}}
    if seed is not None:out.update(seed=seed,training_variant={'arm':'k1','recipe':'fixed'})
    return out


class FinalGain(unittest.TestCase):
    def setUp(self):self.a=[report(2),report(3)];self.b=report()

    def test_actual_pinned_bootstrap_matches_question_seed_mean(self):
        self.a[0]['suites']['decision-v7']['correct']=[1]*1200
        result=G.compare(self.a,self.b)
        decision=result['per_suite']['decision-v7']
        expected=G.original_bootstrap()([.5]*1200,[0]*1200)
        self.assertEqual(decision['paired_bootstrap'],expected)
        self.assertEqual(decision['paired_bootstrap']['n'],1200)
        self.assertEqual(decision['paired_bootstrap']['ci_lower'],.5)
        self.assertEqual(decision['paired_bootstrap']['ci_upper'],.5)
        self.assertEqual(decision['difference_percentage_points'],50.)
        self.assertFalse(result['scientific_acceptance']);self.assertFalse(result['publication_authorized'])
        self.assertTrue(result['point_gain_requirement_met'])

    def test_inclusive_gain_boundary_and_drop_failure(self):
        # 12/1200 is exactly 1pp. Transfer cannot attain exactly 1pp with
        # 2*656 binary observations, so test the nearest worse value.
        for r in self.a:r['suites']['decision-v7']['correct'][:12]=[1]*12
        self.assertTrue(G.compare(self.a,self.b)['point_gain_requirement_met'])
        self.b['suites']['transfer-v4']['correct'][:7]=[1]*7
        self.assertFalse(G.compare(self.a,self.b)['point_gain_requirement_met'])
        self.b['suites']['transfer-v4']['correct'][6]=0
        self.assertTrue(G.compare(self.a,self.b)['point_gain_requirement_met'])
        for r in self.a:r['suites']['decision-v7']['correct'][11]=0
        self.assertFalse(G.compare(self.a,self.b)['point_gain_requirement_met'])

    def test_wrong_population_lengths_order_duplicate_and_nonbinary_refused(self):
        for change in ('short','long','duplicate','order','nan','bool','half','string'):
            a=copy.deepcopy(self.a);cell=a[1]['suites']['decision-v7']
            if change=='short':cell['correct'].pop()
            if change=='long':cell['keys'].append('extra')
            if change=='duplicate':cell['keys'][1]=cell['keys'][0]
            if change=='order':cell['keys'].reverse()
            if change in ('nan','bool','half','string'):
                cell['correct'][0]={'nan':float('nan'),'bool':True,'half':.5,'string':'0'}[change]
            with self.subTest(change=change),self.assertRaises(ValueError):G.compare(a,self.b)

    def test_distinct_seeds_and_single_baseline_enforced(self):
        for change in ('same','missing','extra','bool','baseline_seed','alias'):
            a,b=copy.deepcopy(self.a),copy.deepcopy(self.b)
            if change=='same':a[1]['seed']=2
            if change=='missing':a.pop()
            if change=='extra':a.append(report(4))
            if change=='bool':a[0]['seed']=True
            if change=='baseline_seed':b['seed']=2
            if change=='alias':a[1]['model']['path']=a[0]['model']['path']
            with self.subTest(change=change),self.assertRaises(ValueError):G.compare(a,b)

    def test_different_base_data_recipe_protocol_partition_refused(self):
        for change in ('bytes','base','data','recipe','protocol','partition','arm','prompt_code'):
            a=copy.deepcopy(self.a)
            if change=='bytes':a[1]['model']['base_inventory_sha256']='d'*64
            if change=='base':a[1]['model']['base_path']='/other'
            if change=='data':a[1]['suites']['transfer-v4']['dataset_sha256']='d'*64
            if change=='recipe':a[1]['training_variant']['recipe']='other'
            if change=='protocol':a[1]['protocol']['dtype']='bfloat16'
            if change=='partition':a[1]['partition']='dev'
            if change=='arm':a[1]['arm']='K2'
            if change=='prompt_code':a[1]['scoring_protocol_sha256']='f'*64
            with self.subTest(change=change),self.assertRaises(ValueError):G.compare(a,self.b)

    def test_identical_result_no_gain_and_seed_order_irrelevant(self):
        first=G.compare(self.a,self.b);second=G.compare(self.a[::-1],self.b)
        self.assertEqual(first,second);self.assertFalse(first['point_gain_requirement_met'])
        for cell in first['per_suite'].values():
            self.assertEqual(cell['paired_bootstrap']['mean_difference'],0.)
            self.assertEqual(cell['paired_bootstrap']['ci_level'],.9)
            self.assertEqual(cell['paired_bootstrap']['resamples'],10000)

    def test_changed_selector_refused(self):
        G.original_bootstrap.cache_clear()
        try:
            with patch.object(G.Path,'read_bytes',return_value=b'changed'):
                with self.assertRaisesRegex(ValueError,'selector source'):G.original_bootstrap()
        finally:G.original_bootstrap.cache_clear()

if __name__=='__main__':unittest.main()
