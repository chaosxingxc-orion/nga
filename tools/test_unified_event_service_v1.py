import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import experiment_dag as D
from tools import unified_cpu_consumer_v1 as C
from tools import unified_event_service_v1 as S
from tools.test_unified_cpu_consumer_v1 import ConsumerTest, FakeDocker


def put(p,v):
    p.write_text(json.dumps(v,sort_keys=True)+'\n'); return S.file_pin(p)

class EventServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name)
        self.cf=ConsumerTest();self.cf.setUp();self.addCleanup(self.cf.doCleanups)
        # Keep all fixtures in the consumer's private temporary tree.
        self.r=self.cf.root; self.state=self.r/'service'; self.state.mkdir()
        self.policy=put(self.r/'policy.json',{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'allow'})
        self.conf=copy.deepcopy(self.cf.c);self.conf['controller']=str(self.state/'cpu-controller');self.conf['slots']=1
        cp=put(self.r/'consumer.json',self.conf)
        b={'schema':'unified-event-cpu-binding-v1','consumer_config':cp};bp=put(self.r/'binding.json',b)
        rev=put(self.r/'review.json',{'schema':'unified-event-cpu-review-v1','decision':'accept','node':'cpu','binding_sha256':D.digest(b),'components':S.cpu_components()})
        self.node={'id':'cpu','lane':'cpu','devices':[],'priority':0,'purpose':'fixture','split':'DEV','protocol':'fixed','sources':[cp],'adapter':'unified_cpu_v1','stage':'planned','managed_by':'dag','depends_on':[],'action':{'binding':bp,'review':rev},'missing':[]}
        self.graph={'schema':'nga-experiment-dag-v1','id':'test','policy':{'poll_seconds':600,'cpu_slots':1,'target_ready_depth':1,'target_reserve_depth':1,'ordering':'priority_then_id'},'adapters':{'unified_cpu_v1':{'version':1,'implementation':S.file_pin(S.HERE),'integration':'reviewed_dispatch'}},'nodes':[self.node]}
        self.config={'schema':'unified-event-service-v1','graph':put(self.r/'graph.json',self.graph),'policy':self.policy,'state_dir':str(self.state),'socket':str(self.state/'event.sock'),'review_pins':[rev],'python':str(Path(sys.executable).resolve()),'fallback_seconds':600}
        self.ref=put(self.r/'service.json',self.config)
        self.docker=FakeDocker();self.spawned=[]
        outer=self
        class Adapter(S.CPUAdapter):
            def spawn(self,n,token): outer.spawned.append((n['id'],token));return {'pid':123}
            def recover(self,n,rec): pass
        self.adapter=Adapter
    def update(self):
        self.config['graph']=put(self.r/'graph.json',self.graph);self.ref=put(self.r/'service.json',self.config)
    def run_iter(self,**kw):return S.iteration(self.ref,cpu_factory=self.adapter,**kw)
    def run_worker(self,token):
        root=self.state/'workers'/'cpu';root.mkdir(parents=True,exist_ok=True)
        f=(root/'worker.lock').open('a');import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with mock.patch.object(C,'Consumer',return_value=C.Consumer(self.docker)):
            S.worker(self.ref,'cpu',token,os.dup(f.fileno()))
        f.close()
    def test_duplicate_restart_actual_consumer(self):
        s=self.run_iter(); token=s['attempts']['cpu']['token'];self.assertEqual(len(self.spawned),1)
        self.run_worker(token);self.run_iter();self.run_iter()
        self.assertEqual(len(self.spawned),1);self.assertEqual(self.docker.creates,1)
        self.assertEqual(json.loads((self.state/'dag/state.json').read_text())['attempts']['cpu']['status'],'accepted')
        self.assertEqual(json.loads((self.state/'workers/cpu/TERMINAL.json').read_text())['outcome'],'physical')
    def test_child_failure_and_stale_inputs_fail_closed(self):
        token=self.run_iter()['attempts']['cpu']['token']; Path(self.conf['config']['path']).write_text('{}')
        self.run_worker(token); self.run_iter()
        t=json.loads((self.state/'workers/cpu/TERMINAL.json').read_text()); self.assertEqual(t['outcome'],'uncertain')
        self.assertEqual(json.loads((self.state/'dag/state.json').read_text())['attempts']['cpu']['status'],'uncertain')
        self.assertEqual(self.docker.creates,0)
    def test_hold_and_policy_pin_change(self):
        Path(self.policy['path']).write_text('{"schema":"nga-engineering-release-policy-v1","new_experiment_dispatch":"hold"}')
        self.assertTrue(S.held(self.config)); self.run_iter();self.assertEqual(self.spawned,[])
        self.config['policy']=S.file_pin(self.policy['path']);self.ref=put(self.r/'service.json',self.config);self.run_iter();self.assertEqual(self.spawned,[])
        self.config['policy']=put(self.r/'policy2.json',{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'allow'});self.ref=put(self.r/'service.json',self.config)
        self.run_iter();self.assertEqual(len(self.spawned),1)
        Path(self.config['policy']['path']).write_text('{}');self.run_iter();self.assertEqual(len(self.spawned),1)
    def test_bounded_cpu_and_priority(self):
        n=copy.deepcopy(self.node);n['id']='other';n['priority']=2
        b=D.read_pin(n['action']['binding']); rev=put(self.r/'other-review.json',{'schema':'unified-event-cpu-review-v1','decision':'accept','node':'other','binding_sha256':D.digest(b),'components':S.cpu_components()})
        n['action']['review']=rev;self.config['review_pins'].append(rev);self.graph['nodes'].append(n);self.update()
        self.run_iter();self.assertEqual([x[0] for x in self.spawned],['cpu'])
        self.run_iter();self.assertEqual(len(self.spawned),1)
    def test_npu_decision_independent_of_slow_cpu_and_no_provider(self):
        impl=S.file_pin(S.A.__file__);self.graph['adapters']['unified_npu_v1']={'version':1,'implementation':impl,'integration':'reviewed_dispatch'}
        n=copy.deepcopy(self.node);n.update(id='npu',lane='npu',devices=[0],priority=1,adapter='unified_npu_v1');self.graph['nodes'].append(n);self.update()
        class NPU:
            implementation_sha256=impl['sha256']
            def authorize(self,*a):return True
            def reserve_and_start(self,*a): calls.append('npu');return {'ok':True}
            def observe(self,*a):return {'state':'running','facts':[],'failed_facts':[],'evidence':[]}
        calls=[]
        self.run_iter(npu=NPU());self.assertEqual(calls,[])
        def provider(g):
            s=S.unknown_snapshot(g);s['resources']['0']='free_observed';return s
        self.run_iter(npu=NPU(),provider=provider);self.assertEqual(calls,['npu'])
    def test_slow_actual_consumer_does_not_block_npu(self):
        impl=S.file_pin(S.A.__file__);self.graph['adapters']['unified_npu_v1']={'version':1,'implementation':impl,'integration':'reviewed_dispatch'}
        n=copy.deepcopy(self.node);n.update(id='npu',lane='npu',devices=[0],priority=1,adapter='unified_npu_v1');self.graph['nodes'].append(n);self.update()
        token=self.run_iter()['attempts']['cpu']['token']
        entered=threading.Event();finish=threading.Event()
        self.docker.on_wait=lambda: (entered.set(),finish.wait(5))
        thread=threading.Thread(target=self.run_worker,args=(token,));thread.start()
        self.addCleanup(lambda: (finish.set(),thread.join(5)))
        self.assertTrue(entered.wait(3))
        heartbeat=self.state/'workers/cpu/heartbeat.json'
        self.assertTrue(heartbeat.exists())
        self.assertEqual(json.loads(heartbeat.read_text())['phase'],'consumer_wait_or_validation')
        calls=[]
        class NPU:
            implementation_sha256=impl['sha256']
            def authorize(self,*a):return True
            def reserve_and_start(self,*a):calls.append('npu');return {'ok':True}
            def observe(self,*a):return {'state':'running','facts':[],'failed_facts':[],'evidence':[]}
        def provider(g):
            snap=S.unknown_snapshot(g);snap['resources']['0']='free_observed';return snap
        self.run_iter(npu=NPU(),provider=provider)
        self.assertEqual(calls,['npu']);self.assertTrue(thread.is_alive())
        finish.set();thread.join(5);self.assertFalse(thread.is_alive())

    def test_physical_child_nonzero_is_failed(self):
        token=self.run_iter()['attempts']['cpu']['token']
        def failed(name):
            self.docker.objects[name]['State']={'Status':'exited','Running':False,'ExitCode':7};return 7
        self.docker.wait=failed
        self.run_worker(token);self.run_iter()
        self.assertEqual(json.loads((self.state/'dag/state.json').read_text())['attempts']['cpu']['status'],'failed')

    def test_freshness_expiry(self):
        impl=S.file_pin(S.A.__file__);self.graph['adapters']['unified_npu_v1']={'version':1,'implementation':impl,'integration':'reviewed_dispatch'}
        n=copy.deepcopy(self.node);n.update(id='npu',lane='npu',devices=[0],adapter='unified_npu_v1');self.graph['nodes'].append(n);self.update()
        calls=[]
        class NPU:
            implementation_sha256=impl['sha256']
            def authorize(self,*a):return True
            def reserve_and_start(self,*a):calls.append(1);return {}
            def observe(self,*a):return {'state':'running','facts':[],'failed_facts':[],'evidence':[]}
        def stale(g):
            snap=S.unknown_snapshot(g);snap['as_of']=str(time.time()-60);snap['resources']['0']='free_observed';return snap
        self.run_iter(npu=NPU(),provider=stale);self.assertEqual(calls,[])

    def test_fabricated_terminal_cannot_release_dependency(self):
        token=self.run_iter()['attempts']['cpu']['token']
        root=self.state/'workers'/'cpu';root.mkdir(parents=True,exist_ok=True)
        D.atomic(root/'TERMINAL.json',{'schema':'unified-event-worker-terminal-v1','token':token,'exit_code':0,'outcome':'physical','time':time.time(),'scientific_acceptance':False})
        self.assertEqual(self.run_iter()['attempts']['cpu']['status'],'uncertain')

    def test_missing_ack_cannot_release_dependency(self):
        token=self.run_iter()['attempts']['cpu']['token'];self.run_worker(token)
        ack=next((self.state/'cpu-controller/jobs').glob('*/ACK.json'));ack.unlink()
        self.assertEqual(self.run_iter()['attempts']['cpu']['status'],'uncertain')

    def test_receipt_types_are_exact(self):
        token=self.run_iter()['attempts']['cpu']['token']; self.run_worker(token)
        job=next((self.state/'cpu-controller/jobs').iterdir())
        terminal=job/'TERMINAL.json'; ack=job/'ACK.json'
        original_t=json.loads(terminal.read_text()); original_a=json.loads(ack.read_text())
        adapter=S.CPUAdapter(self.config,self.graph,self.ref)
        self.assertEqual(adapter.observe(self.node,{'token':token})['state'],'accepted')
        for which,field,value in [('terminal','exit_code',False),('ack','exit_code',False),('terminal','scientific_acceptance',0),('ack','scientific_acceptance',0)]:
            t=copy.deepcopy(original_t); a=copy.deepcopy(original_a)
            (t if which=='terminal' else a)[field]=value
            put(terminal,t); a['terminal_sha256']=S.file_pin(terminal)['sha256']; put(ack,a)
            with self.subTest(which=which,field=field), self.assertRaises(ValueError):
                adapter.observe(self.node,{'token':token})
        put(terminal,original_t); original_a['terminal_sha256']=S.file_pin(terminal)['sha256']; put(ack,original_a)
        self.assertEqual(adapter.observe(self.node,{'token':token})['state'],'accepted')
        owner=job/'OWNER.json'; original_owner=json.loads(owner.read_text())
        changed=copy.deepcopy(original_owner); changed['config']['slots']=True; put(owner,changed)
        with self.assertRaises(ValueError): adapter.observe(self.node,{'token':token})
        put(owner,original_owner)
        self.assertEqual(adapter.observe(self.node,{'token':token})['state'],'accepted')
        self.assertFalse(S.exact_value({'nested':[False,1]}, {'nested':[0,1]}))

    def test_denied_intent_has_no_recovery_authority(self):
        adapter=S.CPUAdapter(self.config,self.graph,self.ref)
        with mock.patch.object(S,'held',return_value=True):
            with self.assertRaises(ValueError): adapter.reserve_and_start({},self.node,'token')
        with self.assertRaises(FileNotFoundError): adapter.recover(self.node,{'token':'token'})

    def test_mutable_policy_authorization_survives_overwrite_and_hold(self):
        self.config['policy']={'path':self.policy['path']}
        adapter=S.CPUAdapter(self.config,self.graph,self.ref)
        with mock.patch.object(adapter,'spawn',return_value={}):
            adapter.reserve_and_start({},self.node,'token')
            hold=self.r/'new-policy.json'
            put(hold,{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'hold'})
            S.policy_update(self.config,str(hold))
            self.assertTrue(S.held(self.config))
            adapter.recover(self.node,{'token':'token'})
            self.assertEqual(adapter.spawn.call_count,2)
            with self.assertRaises(ValueError): adapter.reserve_and_start({},self.node,'other')

    def test_policy_update_waits_for_admission_lock(self):
        self.config['policy']={'path':self.policy['path']}
        self.ref=put(self.r/'service.json',self.config)
        hold=self.r/'new-policy.json'
        put(hold,{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'hold'})
        cmd=[sys.executable,'-B','-P',str(S.HERE),'policy-update','--config',self.ref['path'],'--sha256',self.ref['sha256'],'--policy-source',str(hold)]
        adapter=S.CPUAdapter(self.config,self.graph,self.ref)
        with S.policy_lock(self.config):
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.addCleanup(lambda: proc.poll() is None and proc.kill())
            time.sleep(.2)
            self.assertIsNone(proc.poll())
            self.assertFalse(S.held(self.config))
        out,err=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,err.decode())
        with self.assertRaises(ValueError): adapter.reserve_and_start({},self.node,'denied')
        with self.assertRaises(FileNotFoundError): adapter.recover(self.node,{'token':'denied'})

    def test_policy_update_during_admission_preserves_authorization(self):
        self.config['policy']={'path':self.policy['path']}; self.ref=put(self.r/'service.json',self.config)
        hold=self.r/'new-policy.json'; put(hold,{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'hold'})
        adapter=S.CPUAdapter(self.config,self.graph,self.ref)
        entered=threading.Event(); release=threading.Event(); original=D.atomic
        def paused(path,value):
            if Path(path).name=='AUTHORIZATION.json':
                entered.set(); self.assertTrue(release.wait(5))
            return original(path,value)
        errors=[]
        def admit():
            try: adapter.reserve_and_start({},self.node,'token')
            except Exception as exc: errors.append(exc)
        cmd=[sys.executable,'-B','-P',str(S.HERE),'policy-update','--config',self.ref['path'],'--sha256',self.ref['sha256'],'--policy-source',str(hold)]
        with mock.patch.object(S.D,'atomic',side_effect=paused), mock.patch.object(adapter,'spawn',return_value={}):
            thread=threading.Thread(target=admit); thread.start()
            self.assertTrue(entered.wait(5))
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                time.sleep(.2); self.assertIsNone(proc.poll()); release.set()
                thread.join(5); out,err=proc.communicate(timeout=5)
                self.assertFalse(thread.is_alive()); self.assertFalse(errors)
                self.assertEqual(proc.returncode,0,err.decode()); self.assertTrue(S.held(self.config))
                adapter.recover(self.node,{'token':'token'})
                self.assertEqual(adapter.spawn.call_count,2)
            finally:
                release.set(); thread.join(5)
                if proc.poll() is None: proc.kill(); proc.wait()

    def test_provider_error_and_recovery_error_leave_heartbeat(self):
        self.run_iter()
        class Broken(self.adapter):
            def recover(self,n,rec): raise OSError('fixture')
        def provider(g): raise OSError('fixture')
        S.iteration(self.ref,cpu_factory=Broken,provider=provider)
        diag=json.loads((self.state/'diagnostic.json').read_text())
        self.assertEqual({x['component'] for x in diag['errors']},{'provider','recovery'})
        self.assertIn('utc_seconds',json.loads((self.state/'heartbeat.json').read_text()))

    def test_dependencies_block_until_success(self):
        n=copy.deepcopy(self.node);n.update(id='other',priority=1,depends_on=[{'node':'cpu','kind':'success'}])
        b=D.read_pin(n['action']['binding']);rev=put(self.r/'other-review.json',{'schema':'unified-event-cpu-review-v1','decision':'accept','node':'other','binding_sha256':D.digest(b),'components':S.cpu_components()})
        n['action']['review']=rev;self.config['review_pins'].append(rev);self.graph['nodes'].append(n);self.update()
        token=self.run_iter()['attempts']['cpu']['token'];self.assertEqual(len(self.spawned),1)
        self.run_worker(token);self.run_iter();self.assertEqual([x[0] for x in self.spawned],['cpu','other'])

    def test_service_process_wakeup_and_restart_under_hold(self):
        self.config['policy']=put(self.r/'hold.json',{'schema':'nga-engineering-release-policy-v1','new_experiment_dispatch':'hold'});self.ref=put(self.r/'service.json',self.config)
        argv=[sys.executable,'-B','-P',str(S.HERE),'serve','--config',self.ref['path'],'--sha256',self.ref['sha256']]
        def wait_for(predicate):
            end=time.monotonic()+4
            while time.monotonic()<end:
                if predicate():return
                time.sleep(.01)
            self.fail('service did not reach expected state')
        for _ in range(2):
            proc=subprocess.Popen(argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                heartbeat=self.state/'HEARTBEAT.json'
                previous=heartbeat.stat().st_mtime_ns if heartbeat.exists() else 0
                wait_for(lambda: heartbeat.exists() and heartbeat.stat().st_mtime_ns>previous)
                previous=heartbeat.stat().st_mtime_ns
                S.notify(self.config['socket'])
                wait_for(lambda:heartbeat.stat().st_mtime_ns>previous)
                self.assertEqual(json.loads((self.state/'dag/state.json').read_text())['attempts'],{})
            finally:
                proc.terminate();proc.wait(timeout=4)

    def test_socket_wakeup_and_600_timeout(self):
        path=str(self.state/'s');s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);self.addCleanup(s.close);s.bind(path);s.settimeout(.5)
        S.notify(path);self.assertEqual(s.recv(64),b'wake')
        self.assertEqual(self.config['fallback_seconds'],600)
        with mock.patch.object(S.socket,'socket') as factory, mock.patch.object(S.os,'chmod'), mock.patch.object(S,'iteration',side_effect=KeyboardInterrupt):
            sock=factory.return_value.__enter__.return_value
            with self.assertRaises(KeyboardInterrupt):S.serve(self.ref)
            sock.settimeout.assert_called_once_with(600)

if __name__=='__main__':unittest.main()
