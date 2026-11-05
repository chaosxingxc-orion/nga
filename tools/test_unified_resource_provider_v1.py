import copy
import json
import subprocess
import unittest
from unittest import mock
from tools import unified_resource_provider_v1 as P, experiment_dag as D
from tools import r3_resource_adapter as R, unified_resource_lease_v1 as U
from tools.test_unified_container_host_v1 import HostTest


class ProviderTests(HostTest):
    def setup_provider(self, n=4):
        self.c=self.config('fixed',count=n,ids=list(range(n)))
        h=self.host(self.c,'provider-job'); path=self.root/'host.json'; R.write_atomic(path,h)
        lock=self.root/'alloc.json.lock'; lock.touch()
        self.pc={'schema':'unified-resource-provider-config-v1','allocation':self.alloc,'evidence_roots':[str(self.root)],'host_configs':[self.pin(path)],'historical_releases':[],'allowed_device_ids':list(range(n)),'max_age_seconds':30}
        self.g={'schema':'nga-experiment-dag-v1','id':'fixture','policy':{'poll_seconds':600,'cpu_slots':1,'target_ready_depth':1,'target_reserve_depth':1,'ordering':'priority_then_id'},'adapters':{},'nodes':[]}
        ref=self.pin(path)
        self.g['adapters']={'host':{'version':1,'implementation':ref,'integration':'reviewed_dispatch'}}
        self.g['nodes']=[{'id':'fixed','lane':'npu','devices':list(range(n)),'priority':0,'purpose':'fixture','split':'NONE','protocol':'fixture','sources':[ref],'adapter':'host','stage':'planned','managed_by':'dag','depends_on':[],'action':None,'missing':[]}]
    def obs(self, query=None, device=None):
        with mock.patch.object(P,'host_check'), mock.patch.object(P,'Inventory',return_value=query or self.q), mock.patch.object(P,'device_query',side_effect=device or (lambda i: False)):
            return P.observe(self.pc,self.g)
    def test_free_real_lineage_and_dag(self):
        for n in (1,2,4):
            with self.subTest(n=n):
                self.setUp(); self.setup_provider(n); snap,receipt=self.obs(); D.validate_snapshot(self.g,snap)
                self.assertEqual([snap['resources'][str(i)] for i in range(n)],['free_observed']*n)
                self.assertTrue(receipt['fresh']); self.assertEqual(len(receipt['lineage']),n)
                self.assertFalse(D.plan(self.g,snap)['launch_authorized'])
    def test_pending_mutation_clock_and_probe(self):
        self.setup_provider(); doc=R.load(self.alloc); doc['pending_claims']=[{'owner':'x'}]; R.write_atomic(self.alloc,doc)
        self.assertEqual(self.obs()[0]['resources']['0'],'unknown')
        doc['pending_claims']=[]; R.write_atomic(self.alloc,doc)
        def mutate(i):
            if i==0:
                d=R.load(self.alloc); d['other']={'changed':1}; R.write_atomic(self.alloc,d)
            return False
        s,r=self.obs(device=mutate); self.assertFalse(r['fresh']); self.assertEqual(s['resources']['0'],'unknown')
        with mock.patch.object(P,'boot',side_effect=['one','two']): self.assertEqual(self.obs()[0]['resources']['0'],'unknown')
        s,r=self.obs(device=lambda i: (_ for _ in ()).throw(FileNotFoundError('npu-smi absent'))); self.assertIn('npu-smi absent',r['reasons']['0']); self.assertEqual(s['resources']['0'],'unknown')
        s,r=self.obs(device=lambda i: i==0); self.assertEqual(s['resources']['0'],'busy')
    def test_owner_not_free_and_bad_predecessor(self):
        self.setup_provider(1)
        q=copy.deepcopy(self.q); q.inspect=lambda name: None
        self.assertEqual(self.obs(query=q)[0]['resources']['0'],'unknown')
        entry=R.load(self.alloc)['free'][0]
        self.pc['historical_releases']=[{'host_config':self.pc['host_configs'][0],'free_entry':entry,'refs':self.pre['0']}]
        U.claim(self.c,self.q)
        s,r=self.obs(); self.assertEqual(s['resources']['0'],'busy'); self.assertEqual(r['historical_releases'][0]['status'],'authenticated')
    def test_inventory_batch_and_failures(self):
        ident='a'*64
        row={'Id':ident,'Name':'/one','State':{'Status':'running','Running':True},'HostConfig':{'Devices':[],'Privileged':False,'DeviceCgroupRules':None,'DeviceRequests':None},'Mounts':[]}
        def call(cmd,**kw):
            out=ident if cmd[1]=='ps' else json.dumps([row])
            return subprocess.CompletedProcess(cmd,0,out,'')
        with mock.patch.object(P.subprocess,'run',side_effect=call) as runner:
            self.assertFalse(P.Inventory().conflict(0)); self.assertEqual(runner.call_count,2)
        row['HostConfig']['Privileged']=True
        with mock.patch.object(P.subprocess,'run',side_effect=call): self.assertTrue(P.Inventory().conflict(7))
        row['Id']='b'*64
        with mock.patch.object(P.subprocess,'run',side_effect=call), self.assertRaises(ValueError): P.Inventory()
        with mock.patch.object(P.subprocess,'run',side_effect=FileNotFoundError('docker')), self.assertRaises(FileNotFoundError): P.Inventory()

if __name__=='__main__': unittest.main()
