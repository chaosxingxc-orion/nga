import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from tools import experiment_dag as D
from tools import unified_dag_adapter_v1 as A
from tools import unified_container_host_v1 as H
from tools import unified_resource_lease_v1 as U
from tools import r3_resource_adapter as R
from tools.test_unified_container_host_v1 import HostTest, FakeDocker


class IntegrationTest(HostTest):
    def test_actual_dispatch_lease_release_and_scientific_block(self):
        docker = FakeDocker(self.q)
        configs = [self.host(self.config('lease'+str(i), ids=[0]), 'job'+str(i)) for i in range(2)]
        def start(pin):
            c = D.read_pin(pin)
            if c['name'] == 'job1':
                def running(name):
                    docker.objects[name]['State'].update(Status='running', Running=True)
                with mock.patch.object(docker, 'start', side_effect=running), \
                     mock.patch.object(docker, 'follow_logs', side_effect=RuntimeError('fixture pause')):
                    with self.assertRaisesRegex(RuntimeError, 'fixture pause'):
                        H.run(c, docker)
            else:
                H.run(c, docker)
            return {'status':'supervisor-started', 'pid':123}
        graph = {'schema':'nga-experiment-dag-v1', 'id':'integration',
                 'policy':{'poll_seconds':600,'cpu_slots':1,'target_ready_depth':1,'target_reserve_depth':1,'ordering':'priority_then_id'},
                 'adapters':{'host':{'version':1,'implementation':A.file_pin(A.__file__),'integration':'reviewed_dispatch'}},'nodes':[]}
        for i,c in enumerate(configs):
            path=self.root/('host'+str(i)+'.json'); R.write_atomic(path,c)
            binding={'schema':'unified-dag-binding-v1','host_config':A.file_pin(path)}
            bp=self.root/('binding'+str(i)+'.json'); R.write_atomic(bp,binding)
            review={'schema':'unified-dag-component-review-v1','decision':'accept','node':'n'+str(i),
                    'binding_sha256':D.digest(binding),'components':A.components()}
            rp=self.root/('review'+str(i)+'.json'); R.write_atomic(rp,review)
            graph['nodes'].append({'id':'n'+str(i),'lane':'npu','devices':[0],'priority':i,'purpose':'fixture',
                'split':'NONE','protocol':'fixture','sources':[A.file_pin(A.__file__)],'adapter':'host','stage':'planned',
                'managed_by':'dag','depends_on':[],'action':{'binding':A.file_pin(bp),'review':A.file_pin(rp)},'missing':[]})
        adapter = A.UnifiedDagAdapter(docker, start, [n['action']['review'] for n in graph['nodes']])
        dependent=copy.deepcopy(graph['nodes'][1]); dependent['id']='dependent'; dependent['priority']=3
        dependent['depends_on']=[{'node':'n0','kind':'scientific_admission'}]
        graph['nodes'].append(dependent)
        snap={'schema':'nga-dag-observation-v1','graph_sha256':D.digest(graph),'as_of':'fixture',
              'authority':'adapter_observations','observations':{},'resources':{str(i):'free_observed' for i in range(8)}}
        statepath=self.root/'controller'; reg={'host':adapter}
        untrusted = A.UnifiedDagAdapter(docker, start)
        denied = D.dispatch_once(graph,snap,{'host': untrusted},self.root/'denied')
        self.assertFalse(denied['attempts'])
        first=D.dispatch_once(graph,snap,reg,statepath)
        self.assertEqual(set(first['attempts']),{'n0'})
        self.assertEqual(first['attempts']['n0']['receipt']['supervisor']['status'],'supervisor-started')
        # A fresh lease still consults the live physical conflict gate.
        docker.conflict = lambda chip: True
        with self.assertRaisesRegex(ValueError, 'live device conflict'):
            U.claim(configs[1]['lease'], docker)
        docker.conflict = lambda chip: False
        second=D.dispatch_once(graph,snap,reg,statepath)
        self.assertEqual(set(second['attempts']),{'n0','n1'})
        docker.conflict = lambda chip: any(x['State']['Running'] and chip in U.devices(x) for x in docker.objects.values())
        self.assertTrue(docker.conflict(0))
        final=D.dispatch_once(graph,snap,reg,statepath)
        self.assertEqual(final['attempts']['n0']['status'],'released')
        self.assertEqual(final['attempts']['n1']['status'],'running')
        self.assertEqual(adapter.observe(graph['nodes'][1], final['attempts']['n1'])['facts'], [])
        again = D.dispatch_once(graph,snap,reg,statepath)
        self.assertEqual(again['attempts']['n0']['status'], 'released')
        self.assertNotIn('dependent', again['attempts'])
        original_id = docker.objects['job0']['Id']
        docker.objects['job0']['Id'] = 'f' * 64
        with self.assertRaises(ValueError): adapter.observe(graph['nodes'][0], final['attempts']['n0'])
        docker.objects['job0']['Id'] = original_id
        owner = H.metadata_dir(configs[1])/'OWNER.json'
        original_owner = R.load(owner); R.write_atomic(owner, {'foreign': True})
        self.assertEqual(adapter.observe(graph['nodes'][1], final['attempts']['n1'])['state'], 'uncertain')
        R.write_atomic(owner, original_owner)
        bind = U.paths(configs[1]['lease'], 'binding')[1]
        original_bind = R.load(bind); bad_bind = dict(original_bind, lease_id='foreign')
        R.write_atomic(bind, bad_bind)
        self.assertEqual(adapter.observe(graph['nodes'][1], final['attempts']['n1'])['state'], 'uncertain')
        R.write_atomic(bind, original_bind)
        obs=adapter.observe(graph['nodes'][0],final['attempts']['n0'])
        self.assertEqual(obs['facts'],['resource_release','success'])
        self.assertNotIn('scientific_admission',obs['facts'])
        self.assertNotIn('dependent',final['attempts'])
        self.assertEqual(docker.creates,2)
        handoff=H.metadata_dir(configs[0])/'cpu-handoff.json'
        ev=R.load(handoff); ev['scientific_acceptance']=True; R.write_atomic(handoff,ev)
        with self.assertRaises(ValueError): adapter.observe(graph['nodes'][0],final['attempts']['n0'])

    def test_binding_rejects_commands_and_cpu(self):
        a=A.UnifiedDagAdapter(FakeDocker(self.q),lambda p: None)
        with self.assertRaises(ValueError):
            a.authorize({'schema':'unified-dag-binding-v1','host_config':{},'command':'bad'}, {}, {'lane':'npu'}, '')
        with self.assertRaises(ValueError):
            a.authorize({'schema':'unified-dag-binding-v1','host_config':{}}, {}, {'lane':'cpu'}, '')

if __name__=='__main__': unittest.main()
