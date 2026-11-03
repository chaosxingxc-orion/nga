#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('dag',Path(__file__).with_name('experiment_dag.py'))
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)

class DagTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.calls=[];self.seen={}
        self.impl=self.put('adapter.py',{'fixture':True})
        self.g={'schema':'nga-experiment-dag-v1','id':'fixture','policy':{'poll_seconds':600,'cpu_slots':2,'target_ready_depth':2,'target_reserve_depth':3,'ordering':'priority_then_id'},'adapters':{'fixture':{'version':1,'implementation':self.impl,'integration':'reviewed_dispatch'}},'nodes':[]}
        self.add('a',[0]);self.add('b',[0]);self.add('c',[1]);self.add('cpu',[])
        self.snap={'schema':'nga-dag-observation-v1','graph_sha256':D.digest(self.g),'as_of':'2026-11-03','authority':'adapter_observations','observations':{},'resources':{str(i):'free_observed' for i in range(8)}}
        outer=self
        class Adapter:
            implementation_sha256=outer.impl['sha256']
            def authorize(self,b,r,n,g):return r=={'approved_binding':D.digest(b),'node':n['id']}
            def reserve_and_start(self,b,n,token):
                outer.calls.append(n['id']);outer.seen[n['id']]={'state':'running','facts':[],'failed_facts':[],'evidence':[]};return {'token':token}
            def observe(self,n,rec):return outer.seen.get(n['id'],{'state':'absent'})
        self.adapter=Adapter()
    def put(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value));return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def add(self,k,devices,deps=None):
        b={'id':k};action={'binding':self.put(k+'-bind.json',b),'review':self.put(k+'-review.json',{'approved_binding':D.digest(b),'node':k})}
        n={'id':k,'lane':'npu' if devices else 'cpu','devices':devices,'priority':10,'purpose':k,'split':'DEV','protocol':'fixed','sources':[self.impl],'adapter':'fixture','stage':'planned','managed_by':'dag','depends_on':deps or [],'action':action,'missing':[]}
        self.g['nodes'].append(n);return n
    def planning(self):self.snap['graph_sha256']=D.digest(self.g);return D.plan(self.g,self.snap,{'fixture':self.adapter})
    def test_blocked_head_does_not_hold_unrelated_same_card(self):
        self.g['nodes'][0]['missing']=['review pending'];self.assertEqual(self.planning()['proposed'],['b','c','cpu'])
    def test_typed_dependencies_require_facts_not_success_word(self):
        self.g['nodes'][1]['depends_on']=[{'node':'a','kind':'scientific_admission'}]
        self.snap['observations']['a']={'state':'released','facts':['resource_release','success'],'failed_facts':[],'evidence':[]}
        self.assertEqual(self.planning()['nodes']['b']['state'],'blocked')
        self.snap['observations']['a']['facts'].append('scientific_admission');self.assertIn('b',self.planning()['proposed'])
    def test_failure_only_blocks_descendants(self):
        self.g['nodes'][1]['depends_on']=[{'node':'a','kind':'success'}]
        self.snap['observations']['a']={'state':'failed','facts':['resource_release'],'failed_facts':['success'],'evidence':[]}
        r=self.planning();self.assertEqual(r['nodes']['b']['state'],'blocked');self.assertIn('c',r['proposed'])
    def test_failed_release_can_unlock_resource_dependency(self):
        self.g['nodes'][1]['depends_on']=[{'node':'a','kind':'resource_release'}]
        self.snap['observations']['a']={'state':'failed','facts':['resource_release'],'failed_facts':['success'],'evidence':[]}
        self.assertIn('b',self.planning()['proposed'])
    def test_cycle_unknown_and_duplicate_edges_rejected(self):
        for ds in [[{'node':'unknown','kind':'artifact'}],[{'node':'a','kind':'success'}],[{'node':'c','kind':'artifact'}]*2]:
            with self.subTest(ds=ds):
                g=copy.deepcopy(self.g);g['nodes'][0]['depends_on']=ds
                with self.assertRaises(ValueError):D.validate(g)
    def test_strict_bool_and_extra_fields_reject(self):
        for key,value in [('priority',True),('devices',[True]),('unknown',1)]:
            g=copy.deepcopy(self.g);g['nodes'][0][key]=value
            with self.assertRaises(ValueError):D.validate(g)
    def test_missing_review_and_reference_adapter_never_ready(self):
        self.g['nodes'][0]['action']=None;self.g['adapters']['fixture']['integration']='reference_only'
        self.assertFalse(self.planning()['proposed'])
    def test_multicard_requires_all_devices(self):
        self.g['nodes'][0]['devices']=[0,2];self.snap['resources']['2']='busy'
        self.assertNotIn('a',self.planning()['proposed']);self.assertIn('b',self.planning()['proposed'])
    def test_external_owner_overrides_free_snapshot(self):
        for status in ['running','failed','uncertain','released','accepted']:
            self.snap['observations']['a']={'state':status,'facts':[],'failed_facts':[],'evidence':[]}
            self.assertNotIn('b',self.planning()['proposed'])
            self.assertIn('c',self.planning()['proposed'])
        self.snap['observations']['a']['facts']=['resource_release']
        self.assertIn('b',self.planning()['proposed'])
    def test_invalid_review_never_counted_ready(self):
        Path(self.g['nodes'][0]['action']['review']['path']).write_text('{}')
        r=self.planning();self.assertNotEqual(r['nodes']['a']['state'],'ready')
        self.assertEqual(r['per_chip']['0']['ready_depth'],1)
    def test_launch_failure_preserves_independent_npu_cpu_progress(self):
        self.planning();original=self.adapter.reserve_and_start
        def first_fails(b,n,t):
            if n['id']=='a':
                self.calls.append('a');raise TimeoutError()
            return original(b,n,t)
        self.adapter.reserve_and_start=first_fails
        state=D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertEqual(self.calls,['a','c','cpu'])
        self.assertEqual(state['attempts']['a']['status'],'uncertain')
        D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertNotIn('b',self.calls);self.assertEqual(self.calls.count('a'),1)
    def test_observation_failure_isolated_to_held_device(self):
        self.planning();D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        original=self.adapter.observe
        def broken(n,rec):
            if n['id']=='a':raise OSError()
            return original(n,rec)
        self.adapter.observe=broken
        state=D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertEqual(state['attempts']['a']['status'],'uncertain')
        self.assertNotIn('b',self.calls)
    def test_cpu_slots_do_not_block_npu(self):
        self.snap['observations']['cpu']={'state':'uncertain','facts':[],'failed_facts':[],'evidence':[]}
        self.g['policy']['cpu_slots']=1
        self.assertIn('a',self.planning()['proposed'])
    def test_restart_observes_intent_and_does_not_duplicate(self):
        self.planning();D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertEqual(self.calls,['a','c','cpu'])
    def test_absent_after_intent_is_uncertain_and_holds_chip(self):
        self.planning();D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state');self.seen={}
        state=D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertEqual(self.calls,['a','c','cpu']);self.assertEqual(state['attempts']['a']['status'],'uncertain')
    def test_dispatch_timeout_persists_intent(self):
        self.planning()
        def fail(b,n,t):self.calls.append(n['id']);raise TimeoutError()
        self.adapter.reserve_and_start=fail
        D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        s=json.loads((self.root/'state/state.json').read_text());self.assertEqual(s['attempts']['a']['status'],'uncertain')
    def test_changed_review_rejects_before_action(self):
        Path(self.g['nodes'][0]['action']['review']['path']).write_text('{}');self.planning()
        D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.assertNotIn('a',self.calls);self.assertIn('b',self.calls)
    def test_digest_cannot_dispatch(self):
        self.snap['authority']='digest_only';self.planning()
        with self.assertRaises(ValueError):D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
    def test_graph_change_refuses_restart(self):
        self.planning();D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')
        self.g['nodes'][0]['priority']=11;self.planning()
        with self.assertRaises(ValueError):D.dispatch_once(self.g,self.snap,{'fixture':self.adapter},self.root/'state')

if __name__=='__main__':unittest.main()
