import copy
import json
import os
import signal
import subprocess
import sys
import time
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from tools import reviewed_successor_dispatch_v2 as D
from tools import bev_native_config_panel_host as H


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.run = self.root/'run'; self.run.mkdir()
        self.plan = self.run/'PLAN.json'; self.review = self.run/'REVIEW.json'
        self.allocation = self.run/'allocation.json'; self.save(self.allocation, {'allocation':[],'free':[{'chip':0}]})
        self.policy = self.run/'policy.json'; self.save(self.policy, {'schema':'native-panel-exact-predecessor-v2'})
        host = str(Path(H.__file__).resolve()); runtime = self.run/'runtime.py'; runtime.write_text('# fixture runtime')
        self.d = dict(schema='native-dataset-panel-execution-v1', out=str(self.run/'output'), chip=0, container='demo',
                      scope='public_fixed_base_test', run='r3_runs/run', host_name=socket.gethostname(),
                      scientific_acceptance=False, candidate_test_authority=False, candidate_selection_allowed=False,
                      modules={'host':{'path':host,'sha256':D.sha(host)},'runtime':{'path':str(runtime),'sha256':D.sha(runtime)}},
                      allocation=str(self.allocation), host_python='/usr/bin/python3', host_environment={}, image='sha256:image', environment={}, mounts=[],
                      queue={'path':str(self.policy),'sha256':D.sha(self.policy)},
                      files={host:D.sha(host),str(runtime):D.sha(runtime),str(self.policy):D.sha(self.policy)})
        self.save(self.plan,self.d)
        self.j = dict(id='j',plan=str(self.plan),review=str(self.review),out=self.d['out'],container='demo',chip=0,attempt=1,scope=self.d['scope'],run=self.d['run'])
        self.c = dict(schema='reviewed-successor-dispatch-v1', poll_seconds=600, host_name=socket.gethostname(),
                      host_python=self.d['host_python'],host_module_sha256=D.sha(host),scientific_acceptance=False,
                      output=str(self.root/'queue'),jobs=[self.j])
        Path(self.c['output']).mkdir()
        self.r = dict(verdict='PASS', approved_plan_sha256=D.sha(self.plan), activation_authorized=True,
                      scientific_acceptance=False,candidate_test_authority=False,test_read=True,scope=self.d['scope'],attempts=[1],
                      hashes=self.d['files'],expected_commands={'1':H.command(dict(self.d,runtime=self.d['modules']['runtime'],image_sha256=self.d['image']), str(self.plan),D.sha(self.plan),1)})
        self.save(self.review,self.r)
        self.state={'config_sha256':'fixture','jobs':{}}
        self.saves=[]
    def save(self,p,d): p.write_text(json.dumps(d))
    def checkpoint(self,s): self.saves.append(copy.deepcopy(s))
    def approved(self): return D.approved(self.c,self.j)
    def test_real_host_command_adapter_and_cpu_absent(self):
        D.validate(self.c); b=self.approved()
        self.assertEqual(b['command'][4],'start');self.assertEqual(b['command'][-2:],['--attempt','1'])
        spawn=Mock(return_value={'pid':5}); D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        self.assertEqual(spawn.call_count,1);self.assertFalse((self.run/'output/cpu').exists())
        self.assertTrue(self.saves[-2]['jobs']['j']['launch_intent'])
    def test_missing_review_stays_pending(self):
        self.review.unlink();spawn=Mock();D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        self.assertEqual(self.state['jobs']['j']['state'],'pending_review');spawn.assert_not_called()
    def test_invalid_review_or_command_never_launches(self):
        for k,v in [('activation_authorized',False),('approved_plan_sha256','wrong'),('candidate_test_authority',True),('expected_commands',{'1':['wrong']})]:
            self.save(self.review,dict(self.r,**{k:v}));spawn=Mock();state={'jobs':{}}
            D.tick(self.c,state,self.checkpoint,spawn=spawn)
            with self.subTest(k=k):self.assertEqual(state['jobs']['j']['state'],'review_rejected');spawn.assert_not_called()
    def test_changed_dependency_rejected(self):
        Path(self.d['modules']['runtime']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'dependency changed'):self.approved()
    def test_placeholder_rejected_even_if_pinned(self):
        self.save(self.policy,{'schema':'PREPARATION_ONLY_NO_RESOURCE_CLAIM'})
        self.d['queue']['sha256']=D.sha(self.policy);self.save(self.plan,self.d)
        self.r['approved_plan_sha256']=D.sha(self.plan);self.save(self.review,self.r)
        with self.assertRaisesRegex(ValueError,'placeholder'):self.approved()
    def test_lost_response_or_popen_receipt_failure_never_replays(self):
        spawn=Mock(side_effect=TimeoutError('response lost'))
        D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        self.assertEqual(self.state['jobs']['j']['state'],'launch_uncertain')
        # Simulate restart from durable state.
        resumed=json.loads(json.dumps(self.saves[-1]));observer=Mock(return_value='running')
        D.tick(self.c,resumed,self.checkpoint,spawn=spawn,observe=observer)
        self.assertEqual(spawn.call_count,1);self.assertEqual(resumed['jobs']['j']['state'],'running')
    def test_duplicate_release_or_approval_event_does_not_launch_twice(self):
        spawn=Mock(return_value={'pid':5});obs=Mock(return_value='launch_uncertain')
        D.tick(self.c,self.state,self.checkpoint,spawn=spawn,observe=obs)
        for _ in range(3):D.tick(self.c,self.state,self.checkpoint,spawn=spawn,observe=obs)
        self.assertEqual(spawn.call_count,1);self.assertEqual(obs.call_count,3)
    def test_existing_host_attempt_does_not_launch(self):
        (Path(self.j['out'])/'host_attempts/1').mkdir(parents=True)
        spawn=Mock();D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        spawn.assert_not_called();self.assertEqual(self.state['jobs']['j']['state'],'review_rejected')
    def test_different_job_not_blocked_by_missing_review(self):
        self.c['jobs'].insert(0,dict(self.j,id='missing',review=str(self.root/'missing')))
        spawn=Mock(return_value={'pid':5});D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        self.assertEqual(spawn.call_count,1);self.assertEqual(self.state['jobs']['missing']['state'],'pending_review')
    def test_occupied_resource_waits_without_intent(self):
        self.save(self.allocation, {'allocation':[{'chip':0}], 'free':[]})
        spawn=Mock();D.tick(self.c,self.state,self.checkpoint,spawn=spawn)
        spawn.assert_not_called();self.assertEqual(self.state['jobs']['j']['state'],'waiting_resource')
        self.assertNotIn('launch_intent',self.state['jobs']['j'])
    def test_real_controller_lock_event_wakeup_and_terminal(self):
        self.review.unlink();config=self.root/'queue.json';self.save(config,self.c)
        argv=[sys.executable, str(Path(D.__file__).resolve()), '--config',str(config),'--sha256',D.sha(config)]
        p=subprocess.Popen(argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def wait_for(fn):
            end=time.monotonic()+5
            while time.monotonic()<end:
                if fn():return
                time.sleep(.02)
            self.fail('controller observation timeout')
        try:
            digest=Path(self.c['output'])/'digest.json'
            wait_for(digest.exists);before=digest.stat().st_mtime_ns
            second=subprocess.run(argv+['--once'],capture_output=True,timeout=5)
            self.assertNotEqual(second.returncode,0)
            p.send_signal(signal.SIGUSR1)
            wait_for(lambda:digest.stat().st_mtime_ns!=before)
            self.assertIsNone(p.poll());p.terminate();p.wait(timeout=5)
            self.assertEqual(D.read(Path(self.c['output'])/'EXIT.json')['exit_code'],0)
            self.assertFalse((Path(self.j['out'])/'host_attempts').exists())
        finally:
            if p.poll() is None:p.kill();p.wait()
    def test_admission_and_dispatch_ast_unchanged(self):
        import ast
        from tools import reviewed_successor_dispatch_v1 as old
        def functions(path):
            return {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)}
        a,b=functions(old.__file__),functions(D.__file__)
        for name in ('approved','launch','reconcile','tick','validate'):
            self.assertEqual(a[name],b[name],name)

    def test_signal_handler_does_not_take_event_lock(self):
        code = """import importlib.util, os, signal, threading
spec=importlib.util.spec_from_file_location('dispatch', MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
w=m.SignalWakeup();e=threading.Event()
try:
 with e._cond:
  os.kill(os.getpid(),signal.SIGUSR1)
  assert w.pending
  os.kill(os.getpid(),signal.SIGTERM)
  assert w.stop_signal==signal.SIGTERM
finally:w.close()
""".replace('MODULE',repr(str(Path(D.__file__).resolve())))
        p=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_real_signal_dispatch_no_duplicate_with_progress(self):
        config=self.root/'real-queue.json';self.save(config,self.c)
        flag=self.root/'approved';counter=self.root/'launches';runner=self.root/'runner.py'
        runner.write_text("""import importlib.util,json,subprocess,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('dispatch', MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
flag=Path(FLAG);counter=Path(COUNTER);original=m.tick

def approve(c,j):
 if not flag.exists():return None
 return dict(plan_sha256='fixture',review_sha256='fixture',command=['fixture'],environment={},plan=dict(allocation=ALLOCATION))
def spawn(binding,log):
 with counter.open('a') as f:f.write('launch\\n')
 p=subprocess.Popen([sys.executable,'-c','pass']);p.wait()
 return dict(pid=p.pid)
def tick(c,s,save):return original(c,s,save,approve=approve,spawn=spawn,observe=lambda j,r:'running')
m.tick=tick
m.run(CONFIG,PIN)
""".replace('MODULE',repr(str(Path(D.__file__).resolve()))).replace('FLAG',repr(str(flag))).replace('COUNTER',repr(str(counter))).replace('ALLOCATION',repr(str(self.allocation))).replace('CONFIG',repr(str(config))).replace('PIN',repr(D.sha(config))))
        p=subprocess.Popen([sys.executable,str(runner)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        root=Path(self.c['output']);deadline=lambda:time.monotonic()+5
        def wait(fn):
            end=deadline()
            while time.monotonic()<end:
                if fn():return
                if p.poll() is not None:self.fail(p.stderr.read().decode())
                time.sleep(.02)
            self.fail('real signal fixture timeout')
        try:
            wait(lambda:(root/'PROGRESS.json').exists())
            flag.write_text('approved');start=time.monotonic();p.send_signal(signal.SIGUSR1)
            wait(counter.exists);self.assertLess(time.monotonic()-start,5)
            for _ in range(4):
                before=D.read(root/'PROGRESS.json')['passes_completed'];p.send_signal(signal.SIGUSR1)
                wait(lambda:D.read(root/'PROGRESS.json')['passes_completed']>before)
            self.assertEqual(counter.read_text().splitlines(),['launch'])
            p.terminate();p.wait(timeout=5)
            result=D.read(root/'EXIT.json');self.assertEqual(result['exit_code'],0)
            self.assertEqual(result['stop_signal'],signal.SIGTERM)
            self.assertGreaterEqual(result['progress']['passes_completed'],5)
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stderr.close()

    def evidence(self):
        h=Path(self.j['out'])/'host_attempts/1';h.mkdir(parents=True)
        cmd=self.r['expected_commands']['1'];cmd=cmd[cmd.index(self.d['image'])+1:]
        self.save(h/'LAUNCH_RECEIPT.json',dict(container_id='id',plan_sha256=D.sha(self.plan),attempt=1,scientific_acceptance=False,command=cmd))
        actual=dict(Id='id',Name='/demo-a1',Image=self.d['image'],Config={'Cmd':cmd},HostConfig={'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci0'}]},RestartCount=0,State={'Status':'running','Running':True,'ExitCode':0})
        return h,actual,dict(plan_sha256=D.sha(self.plan),launch_intent=True)
    def test_bound_real_receipt_required(self):
        h,a,rec=self.evidence();self.assertEqual(D.reconcile(self.j,rec,lambda _:a),'running')
        a['Id']='foreign'
        with self.assertRaisesRegex(ValueError,'receipt mismatch'):D.reconcile(self.j,rec,lambda _:a)
    def test_docker_exit_without_terminal_not_complete(self):
        h,a,rec=self.evidence();a['State'].update(Status='exited',Running=False)
        self.assertEqual(D.reconcile(self.j,rec,lambda _:a),'exited_pending_terminal')
        rt=Path(self.j['out'])/'attempts/1';rt.mkdir(parents=True)
        terminal=dict(plan_sha256=D.sha(self.plan),attempt=1,scientific_acceptance=False,exit_code=0)
        self.save(rt/'EXIT.json',terminal);self.save(h/'EXIT.json',dict(terminal,container_id='id',runner_terminal_matches=True))
        self.assertEqual(D.reconcile(self.j,rec,lambda _:a),'inference_complete')
        terminal['exit_code']=False;self.save(rt/'EXIT.json',terminal)
        with self.assertRaises(ValueError):D.reconcile(self.j,rec,lambda _:a)
    def test_symlink_evidence_rejected(self):
        link=self.root/'link';link.symlink_to(self.plan)
        with self.assertRaisesRegex(ValueError,'symlink'):D.sha(link)
    def test_invalid_config_identity(self):
        with self.assertRaises(ValueError):D.validate(dict(self.c,host_name='foreign'))
        with self.assertRaises(ValueError):D.validate(dict(self.c,jobs=[self.j,self.j]))

if __name__=='__main__':unittest.main()
