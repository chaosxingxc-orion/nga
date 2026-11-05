"""Regression checks for audit accounting, missing data and interpretation."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('efficiency_audit',Path(__file__).with_name('analyze_execution_efficiency.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


class AccountingTests(unittest.TestCase):
    def test_parallel_intervals_are_not_double_counted(self):
        self.assertEqual(A.union_seconds([(0,10),(2,8),(8,14),(20,23)]),17)

    def test_missing_or_reversed_boundaries_are_not_zero(self):
        self.assertIsNone(A.delta(None,10))
        self.assertIsNone(A.delta(10,9))
        self.assertEqual(A.delta(10,10),0)
        self.assertEqual(A.union_seconds([(None,8),(10,9)]),0)

    def test_subprocess_success_cannot_establish_delivery(self):
        self.assertEqual(A.delivery('V2 is incomplete and disabled. Do not activate it.'),'explicit_limit_or_incomplete')
        self.assertEqual(A.delivery('Delivered package; 31 tests pass.'),'delivery_claim_needs_acceptance')
        self.assertEqual(A.delivery(''),'no_final')

    def test_utc_precision_and_unknown_container_time(self):
        a=A.stamp('2026-11-05T07:23:06.68857656Z')
        b=A.stamp('2026-11-05T07:28:44.59370546Z')
        self.assertAlmostEqual(A.delta(a,b),337.905129,places=5)
        self.assertIsNone(A.stamp('0001-01-01T00:00:00Z'))
        self.assertIsNone(A.stamp(True))

    def test_dependency_chain_adds_wait_without_parallel_sibling(self):
        def worker(name,start,end,parent=None):
            return dict(name=name,start=start,finish=end,parent=parent,exit_code=0,
                        category='review_or_analysis',delivery='delivery_claim_needs_acceptance',
                        dependency_observed=None,scheduler_created=None)
        d=dict(as_of='1970-01-01T00:02:00+00:00',steering={'utc':'1970-01-01T00:01:00+00:00'},
               workers=[worker('a',0,10),worker('b',12,20,'a'),worker('c',1,19)])
        r=A.worker_audit(d)
        self.assertEqual(r['summed_worker_seconds'],36)
        self.assertEqual(r['union_worker_seconds'],20)
        self.assertEqual(r['verified_chain']['seconds'],20)
        self.assertEqual(r['verified_chain']['queue_seconds'],2)
        self.assertEqual(r['verified_chain']['nodes'],['a','b'])
        self.assertIsNone(r['artifact_completion_accepted_count'])

    def test_occupancy_is_lower_bound_not_utilization(self):
        runs=[dict(name='x',attempts=[dict(chip=1,claim_pin_matches=True,boundaries={
            'claim':0,'release':20,'container_start':2,'container_finish':12})])]
        r=A.occupancy(runs,{})
        self.assertEqual(r['window_capacity_chip_seconds'],160)
        self.assertEqual(r['selected_container_chip_seconds'],10)
        self.assertEqual(r['whole_host_actual_occupancy_fraction_bounds'],[.0625,1])
        self.assertIsNone(r['ai_core_utilization'])


if __name__=='__main__':unittest.main()
