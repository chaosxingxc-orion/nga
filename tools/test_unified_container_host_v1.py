import copy
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from tools import unified_container_host_v1 as H
from tools import unified_resource_lease_v1 as U
from tools import r3_resource_adapter as R
from tools.test_unified_resource_lease_v1 import LeaseTest, obj

IMAGE='sha256:'+'a'*64

class FakeDocker:
    def __init__(self, predecessor):
        self.objects={}; self.predecessor=predecessor; self.creates=0
        self.baseline={'PATH':'/usr/local/bin:/usr/bin','LD_LIBRARY_PATH':'/usr/local/Ascend/driver/lib64', 'PYTHONPATH':'/usr/local/Ascend/ascend-toolkit/python'}
    def inspect(self,name):
        if name.startswith('old'): return self.predecessor.inspect(name)
        return copy.deepcopy(self.objects.get(name))
    def conflict(self,chip): return False
    def image_id(self,ref): return IMAGE
    def image_env(self,ident): return self.baseline.copy()
    def create(self,c,chips,image_id):
        # Exercise the exact production argv builder, and derive inspect fields from it.
        args=H.create_args(c,chips,image_id); self.args=args; self.creates+=1
        def vals(flag): return [args[i+1] for i,x in enumerate(args) if x==flag]
        labels=dict(x.split('=',1) for x in vals('--label'))
        devices=[dict(zip(('PathOnHost','PathInContainer','CgroupPermissions'),x.split(':'))) for x in vals('--device')]
        mounts=[]
        for x in vals('--mount'):
            parts=x.split(','); fields=dict(y.split('=',1) for y in parts if '=' in y)
            mounts.append(dict(Type=fields['type'],Source=fields['src'],Destination=fields['dst'],RW='readonly' not in parts))
        x=obj(chips,'new',0,labels['nga.lease_id'],labels['nga.task_sha256'])
        x.update(Image=image_id,Mounts=mounts); x['HostConfig']['Devices']=devices
        x['HostConfig'].update(Privileged=False,NetworkMode='none',RestartPolicy={'Name':'no','MaximumRetryCount':0},DeviceCgroupRules=None,DeviceRequests=None)
        env=self.image_env(image_id); env.update(H.env_map(vals('--env')))
        x['Config'].update(Labels=labels,Entrypoint=[args[args.index('--entrypoint')+1]],Cmd=[args[-1]],Env=[k+'='+v for k,v in env.items()])
        x['State'].update(Status='created',Running=False); self.objects[c['name']]=x; return x['Id']
    def start(self,name): self.objects[name]['State'].update(Status='exited',Running=False,ExitCode=0)
    def follow_logs(self,name,path):
        Path(path).write_text('fixture log\n')
        class Follower:
            pid=123
            def wait(self,timeout=None): return 0
        return Follower()
    def wait(self,name): return self.objects[name]['State']['ExitCode']

class HostTest(LeaseTest):
    def repin_host(self,c):
        R.write_atomic(c['config']['path'],c['task']); c['config']=self.pin(Path(c['config']['path']))
        c['lease']['task_sha256']=U.digest(H.launch_spec(c)); p=Path(c['lease']['acceptance']['path'])
        R.write_atomic(p,dict(schema='unified-resource-acceptance-v1',decision='accept',policy_sha256=c['lease']['policy']['sha256'],config_sha256=U.config_hash(c['lease'])))
        c['lease']['acceptance']=self.pin(p)

    def test_retained_physical_contract_before_claim(self):
        changes=[('Privileged',True),('NetworkMode','host'),('RestartPolicy',{'Name':'always','MaximumRetryCount':0}),
                 ('DeviceCgroupRules',['c *:* rwm']),('DeviceRequests',[{'Count':-1}])]
        for key,value in changes:
            with self.subTest(key=key):
                self.setUp(); c=self.host(self.c,'job'); d=FakeDocker(self.q); d.create(c,[0],IMAGE)
                d.objects['job']['HostConfig'][key]=value
                with self.assertRaises(ValueError): H.run(c,d)
                self.assertFalse(U.paths(c['lease'],'claim')[1].exists())
                self.assertFalse((H.metadata_dir(c)/'cpu-handoff.json').exists())

    def test_environment_baseline_and_injection(self):
        for entry in ('LD_PRELOAD=/model/injected.so','PYTHONHOME=/model', 'HF_HUB_OFFLINE=0', 'PATH=/bad', 'ASCEND_RT_VISIBLE_DEVICES=7'):
            with self.subTest(entry=entry):
                self.setUp(); c=self.host(self.c,'job'); d=FakeDocker(self.q); d.create(c,[0],IMAGE)
                d.objects['job']['Config']['Env'].append(entry)
                with self.assertRaises(ValueError): H.run(c,d)
                self.assertFalse(U.paths(c['lease'],'claim')[1].exists())
        self.setUp(); c=self.host(self.c,'job'); d=FakeDocker(self.q)
        d.baseline['HF_HUB_OFFLINE']='0'; H.run(c,d)
        self.assertIn('HF_HUB_OFFLINE=1',d.objects['job']['Config']['Env'])

    def test_mount_namespace_and_task_confinement(self):
        for target in ('/', '/opt', '/opt/nga', '/usr/bin', '/dev', '/run', '/modelish'):
            with self.subTest(target=target):
                self.setUp(); c=self.host(self.c,'job'); c['mounts'][0]['target']=target; self.repin_host(c)
                with self.assertRaises(ValueError): H.validate(c)
        for manifest, output in (('/model/../etc/passwd','/run/nga/output'),('/model/ok','/run/nga/output/../escape'),('/model/link/file','/run/nga/output'),('/model/ok','/run/nga/output/link/file')):
            with self.subTest(manifest=manifest,output=output):
                self.setUp(); c=self.host(self.c,'job')
                (Path(c['mounts'][0]['source'])/'link').symlink_to(self.root)
                (Path(c['output'])/'link').symlink_to(self.root)
                c['task']={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':manifest,'manifest_sha256':'a'*64,'output':output,'workers':1,'chunk_size':1}
                self.repin_host(c)
                with self.assertRaises(ValueError): H.validate(c)
        self.setUp(); c=self.host(self.c,'job')
        (Path(c['mounts'][0]['source'])/'link').symlink_to(Path(c['mounts'][0]['source'])/'inside')
        c['task']={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':'/model/link','manifest_sha256':'a'*64,'output':'/run/nga/output','workers':1,'chunk_size':1}
        self.repin_host(c)
        with self.assertRaises(ValueError): H.validate(c)

    def host(self,lease,name):
        task={'schema':'nga-unified-config-v1','adapter':'environment-check-v1','runtime':'cpu'}
        conf=self.root/(name+'-config.json'); R.write_atomic(conf,task)
        out=self.root/(name+'-out'); out.mkdir()
        model=self.root/(name+'-model'); model.mkdir()
        c=dict(schema='unified-container-host-v1',lease=lease,name=name,image=IMAGE,entrypoint='nga-engineering-v1',mounts=[dict(source=str(model),target='/model')],task=task,config=self.pin(conf),output=str(out),poll_seconds=600)
        lease['task_sha256']=U.digest(H.launch_spec(c)); lease.pop('predecessors'); lease['evidence_roots']=[str(self.root)]
        ap=self.root/(lease['lease_id']+'-accept.json'); R.write_atomic(ap,dict(schema='unified-resource-acceptance-v1',decision='accept',policy_sha256=lease['policy']['sha256'],config_sha256=U.config_hash(lease))); lease['acceptance']=self.pin(ap)
        return c
    def test_groups_and_production_command(self):
        for n in (1,2,4):
            with self.subTest(n=n):
                # Independent allocation for each size.
                self.setUp(); self.addCleanup(self.tmp.cleanup)
                c=self.host(self.config('group'+str(n),count=n),'job'); docker=FakeDocker(self.q)
                start=time.monotonic(); result=H.run(c,docker)
                self.assertLess(time.monotonic()-start,5); self.assertEqual(result['exit_code'],0)
                args=docker.args; self.assertEqual(args[-3:],[H.ENTRYPOINTS['nga-engineering-v1'][0],IMAGE,H.CONFIG_TARGET])
                self.assertIn('ASCEND_RT_VISIBLE_DEVICES='+','.join(map(str,range(n))),args)
                self.assertEqual(len(list(H.metadata_dir(c).glob('container-log-*.log'))),1)
                self.assertFalse(R.load(self.alloc)['allocation']); H.run(c,docker); self.assertEqual(docker.creates,1)
    def test_recovery_rejects_tampering(self):
        for kind in ('image','mount','config','device','launch'):
            with self.subTest(kind=kind):
                self.setUp(); self.addCleanup(self.tmp.cleanup)
                c=self.host(self.c,'job'); docker=FakeDocker(self.q)
                with mock.patch.object(docker,'start',side_effect=RuntimeError('crash')):
                    with self.assertRaises(RuntimeError): H.run(c,docker)
                x=docker.objects['job']
                if kind=='image': x['Image']='sha256:'+'b'*64
                if kind=='mount': x['Mounts'][0]['RW']=True
                if kind=='config': x['Config']['Cmd']=['/wrong']
                if kind=='device': x['HostConfig']['Devices'][0]['PathInContainer']='/wrong'
                if kind=='launch': x['Config']['Labels']['nga.launch_sha256']='bad'
                with self.assertRaises(ValueError): H.run(c,docker)
                self.assertTrue(R.load(self.alloc)['allocation']); self.assertEqual(docker.creates,1)
    def test_pin_change_rejected_before_claim(self):
        c=self.host(self.c,'job'); R.write_atomic(c['config']['path'],{'wrong':True}); docker=FakeDocker(self.q)
        with self.assertRaises(ValueError): H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation']); self.assertEqual(docker.creates,0)
    def test_hold_before_claim(self):
        c=self.host(self.mutable_config(),'job'); self.hold(c['lease']); docker=FakeDocker(self.q)
        before=R.load(self.alloc)
        with self.assertRaisesRegex(ValueError,'HOLD'): H.run(c,docker)
        self.assertEqual(R.load(self.alloc),before); self.assertEqual(docker.creates,0)
        self.assertFalse(U.paths(c['lease'],'claim')[1].exists())

    def test_running_then_hold_exit_cleanup(self):
        c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q)
        running=threading.Event(); finish=threading.Event(); errors=[]
        def start(name):
            docker.objects[name]['State'].update(Status='running',Running=True); running.set()
        def wait(name):
            if not finish.wait(5): raise RuntimeError('timeout')
            docker.objects[name]['State'].update(Status='exited',Running=False,ExitCode=0); return 0
        docker.start=start; docker.wait=wait
        def supervise():
            try: H.run(c,docker)
            except Exception as exc: errors.append(exc)
        thread=threading.Thread(target=supervise); thread.start()
        try:
            self.assertTrue(running.wait(5)); self.hold(c['lease']); finish.set(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
            self.assertFalse(R.load(self.alloc)['allocation'])
            self.assertTrue((H.metadata_dir(c)/'cpu-handoff.json').exists())
        finally: finish.set(); thread.join(5)

    def test_restart_running_under_hold_after_crash(self):
        c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q)
        def start(name): docker.objects[name]['State'].update(Status='running',Running=True)
        docker.start=start
        with mock.patch.object(docker,'follow_logs',side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError,'crash'): H.run(c,docker)
        self.hold(c['lease'])
        def wait(name):
            docker.objects[name]['State'].update(Status='exited',Running=False,ExitCode=0); return 0
        docker.wait=wait
        H.run(c,docker)
        self.assertEqual(docker.creates,1); self.assertFalse(R.load(self.alloc)['allocation'])
        self.assertTrue((H.metadata_dir(c)/'cpu-handoff.json').exists())

    def test_restart_exited_under_hold_before_terminal(self):
        c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q)
        with mock.patch.object(docker,'follow_logs',side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError,'crash'): H.run(c,docker)
        self.hold(c['lease'])
        with mock.patch.object(docker,'start',side_effect=AssertionError('unexpected start')):
            H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation'])
        self.assertTrue((H.metadata_dir(c)/'cpu-handoff.json').exists())

    def test_hold_recovery_rejects_foreign_binding_or_ownership(self):
        for kind in ('binding','ownership'):
            with self.subTest(kind=kind):
                self.setUp(); self.addCleanup(self.tmp.cleanup)
                c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q)
                with mock.patch.object(docker,'follow_logs',side_effect=RuntimeError('crash')):
                    with self.assertRaisesRegex(RuntimeError,'crash'): H.run(c,docker)
                self.hold(c['lease'])
                if kind=='binding':
                    path=U.paths(c['lease'],'binding')[1]; b=R.load(path); b['lease_id']='foreign'; R.write_atomic(path,b)
                else:
                    doc=R.load(self.alloc); doc['allocation'][0]['owner']='foreign'; R.write_atomic(self.alloc,doc)
                with self.assertRaises(ValueError): H.run(c,docker)
                self.assertTrue(R.load(self.alloc)['allocation'])
                self.assertFalse((H.metadata_dir(c)/'cpu-handoff.json').exists())

    def test_hold_after_bind_before_start_keeps_lease(self):
        c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q); original=U.bind_container
        def bind(*args):
            result=original(*args); self.hold(c['lease']); return result
        with mock.patch.object(U,'bind_container',side_effect=bind), mock.patch.object(docker,'start') as start:
            with self.assertRaisesRegex(ValueError,'HOLD'): H.run(c,docker)
            start.assert_not_called()
        self.assertTrue(U.paths(c['lease'],'binding')[1].exists())
        self.assertTrue(R.load(self.alloc)['allocation'])
        self.assertEqual(R.load(H.metadata_dir(c)/'host-failure.json')['lease_status'],'uncertain')

    def test_policy_writer_serializes_with_actual_start(self):
        c=self.host(self.mutable_config(),'job'); docker=FakeDocker(self.q)
        entered=threading.Event(); proceed=threading.Event(); updated=threading.Event(); errors=[]
        original=docker.start
        def start(name):
            entered.set()
            if not proceed.wait(5): raise RuntimeError('timeout')
            self.assertFalse(updated.is_set()); original(name)
        docker.start=start
        def supervise():
            try: H.run(c,docker)
            except Exception as exc: errors.append(exc)
        def writer():
            try: self.hold(c['lease'])
            except Exception as exc: errors.append(exc)
            finally: updated.set()
        a=threading.Thread(target=supervise); a.start(); b=None
        try:
            self.assertTrue(entered.wait(5)); b=threading.Thread(target=writer); b.start()
            self.assertFalse(updated.wait(.2)); proceed.set(); a.join(5); b.join(5)
            self.assertFalse(a.is_alive() or b.is_alive()); self.assertEqual(errors,[])
            self.assertTrue(updated.is_set()); self.assertFalse(R.load(self.alloc)['allocation'])
            self.assertTrue((H.metadata_dir(c)/'cpu-handoff.json').exists())
        finally:
            proceed.set(); a.join(5)
            if b: b.join(5)
    def test_registry_and_local_image_resolution(self):
        docker=H.Docker()
        import json
        with mock.patch.object(docker,'call',return_value=json.dumps([{'Id':IMAGE,'RepoDigests':['repo@sha256:'+'c'*64]}])):
            self.assertEqual(docker.image_id(IMAGE),IMAGE)
            self.assertEqual(docker.image_id('repo@sha256:'+'c'*64),IMAGE)
            with self.assertRaises(ValueError): docker.image_id('sha256:'+'b'*64)
            with self.assertRaises(ValueError): docker.image_id('repo@sha256:'+'d'*64)
    def test_image_environment_inspection_and_duplicates(self):
        docker=H.Docker()
        image={'Id':IMAGE,'Config':{'Env':['PATH=/usr/bin','LD_LIBRARY_PATH=/ascend','TASK_QUEUE_ENABLE=1']}}
        with mock.patch.object(docker,'call',return_value=json.dumps([image])) as call:
            self.assertEqual(docker.image_env(IMAGE),{'PATH':'/usr/bin','LD_LIBRARY_PATH':'/ascend','TASK_QUEUE_ENABLE':'1'})
            call.assert_called_once_with('image','inspect',IMAGE)
        image['Config']['Env'].append('PATH=/other')
        with mock.patch.object(docker,'call',return_value=json.dumps([image])):
            with self.assertRaises(ValueError): docker.image_env(IMAGE)
        image['Config']['Env']=None
        with mock.patch.object(docker,'call',return_value=json.dumps([image])):
            self.assertEqual(docker.image_env(IMAGE),{})
    def test_wait_wakes_long_poll_and_captures_final_logs(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q); ready=threading.Event()
        def start(name): docker.objects[name]['State'].update(Status='running',Running=True)
        def wait(name):
            ready.wait(2)
            docker.objects[name]['State'].update(Status='exited',Running=False,ExitCode=0)
            return 0
        docker.start=start; docker.wait=wait
        threading.Timer(.1,ready.set).start(); start_time=time.monotonic()
        H.run(c,docker)
        self.assertLess(time.monotonic()-start_time,3)
        self.assertEqual(next(H.metadata_dir(c).glob('container-log-*.log')).read_text(),'fixture log\n')
    def test_existing_incompatible_container_refused_before_claim(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        docker.create(c,[0],IMAGE); docker.objects['job']['Image']='sha256:'+'b'*64
        with self.assertRaisesRegex(ValueError,'image differs'): H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation'])

    def test_concurrent_supervisors_one_create(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        started=threading.Event(); proceed=threading.Event(); original=docker.start
        def start(name):
            started.set(); proceed.wait(3); original(name)
        docker.start=start; errors=[]
        def first():
            try: H.run(c,docker)
            except Exception as e: errors.append(e)
        thread=threading.Thread(target=first); thread.start()
        self.assertTrue(started.wait(3))
        try:
            with self.assertRaisesRegex(ValueError,'supervisor already active'): H.run(c,docker)
        finally: proceed.set(); thread.join(5)
        self.assertFalse(errors); self.assertEqual(docker.creates,1)

    def test_owner_refusal_before_claim(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        meta=H.metadata_dir(c); meta.mkdir(); R.write_atomic(meta/'OWNER.json',{'different':True})
        with self.assertRaisesRegex(ValueError,'owner differs'): H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation']); self.assertEqual(docker.creates,0)

    def test_crash_after_terminal_before_release(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        with mock.patch.object(U,'release',side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError,'crash'): H.run(c,docker)
        self.assertTrue((H.metadata_dir(c)/'terminal.json').exists())
        self.assertTrue(R.load(self.alloc)['allocation'])
        H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation'])
        self.assertTrue((H.metadata_dir(c)/'cpu-handoff.json').exists())

    def test_crash_after_release_event_idempotence(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        with mock.patch.object(H,'publish_handoff',side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError,'crash'): H.run(c,docker)
        self.assertFalse(R.load(self.alloc)['allocation'])
        H.run(c,docker); event=H.metadata_dir(c)/'cpu-handoff.json'; before=event.read_bytes()
        H.run(c,docker); self.assertEqual(event.read_bytes(),before)
        record=R.load(event); self.assertFalse(record['scientific_acceptance'])
        for evidence in record['evidence'].values():
            self.assertEqual(R.sha_bytes(R.read_bytes(evidence['path'])),evidence['sha256'])
        self.assertEqual(record['event_id'],U.digest(record['evidence']))

    def test_adapter_heartbeat_and_terminal_are_separate(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q); out=Path(c['output'])
        R.write_atomic(out/'heartbeat.json',{'phase':'records','completed':7})
        R.write_atomic(out/'terminal.json',{'adapter':True})
        H.run(c,docker)
        self.assertEqual(R.load(out/'terminal.json'),{'adapter':True})
        hb=R.load(H.metadata_dir(c)/'heartbeat.json')
        self.assertTrue(hb['host_alive']); self.assertEqual(hb['adapter_heartbeat']['completed'],7)

    def test_detached_start_persists_exact_argv_and_pins(self):
        c=self.host(self.c,'job'); config=self.root/'host.json'; R.write_atomic(config,c)
        pin=R.sha_bytes(R.read_bytes(config)); proc=mock.Mock(pid=77)
        with mock.patch.object(sys,'argv',['host','start','--config',str(config),'--sha256',pin]), \
             mock.patch.object(H.subprocess,'Popen',return_value=proc) as popen:
            H.main()
        record=R.load(H.metadata_dir(c)/'RELAUNCH.json')
        self.assertEqual(record['argv'],popen.call_args.args[0])
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertEqual(record['config']['sha256'],pin)
        for source in record['sources']:
            self.assertEqual(source['sha256'],R.sha_bytes(R.read_bytes(source['path'])))

    def test_same_lease_different_output_rejected(self):
        c=self.host(self.c,'job'); docker=FakeDocker(self.q)
        H.run(c,docker)
        other=copy.deepcopy(c); other['output']=str(self.root/'other'); Path(other['output']).mkdir()
        # Owner checking is independent of the launch validation and occurs before claim.
        with H.ExitStack() as stack:
            with self.assertRaisesRegex(ValueError,'owner differs'): H.establish_owner(other,stack)

if __name__=='__main__': unittest.main()
