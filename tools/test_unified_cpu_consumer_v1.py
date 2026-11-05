import copy
import hashlib
import json
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import unified_cpu_consumer_v1 as M
from tools import unified_resource_lease_v1 as U


def put(p, value):
    p.write_text(json.dumps(value, sort_keys=True)+'\n'); return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


class FakeDocker:
    def __init__(self): self.objects={}; self.creates=0; self.fail_create=False; self.on_wait=None
    def image_env(self,image): return []
    def inspect(self,name): return copy.deepcopy(self.objects.get(name))
    def create(self,c,mounts,name,launch):
        self.creates+=1; ident=hashlib.sha256(name.encode()).hexdigest()
        self.objects[name]={'Id':ident,'Name':'/'+name,'Image':c['image'],'Config':{'Entrypoint':[M.ENTRY],'Cmd':[M.CONFIG],'Labels':{'nga.cpu.launch':launch},'Env':[k+'='+v for k,v in M.CPU_ENV.items()]},'HostConfig':{'NetworkMode':'none','Devices':[],'Privileged':False,'Runtime':'runc','RestartPolicy':{'Name':'no'},'DeviceCgroupRules':[],'PidMode':'','IpcMode':'private','UTSMode':'','UsernsMode':'','CgroupnsMode':'private'},'Mounts':[{'Type':'bind','Source':s,'Destination':d,'RW':w} for s,d,w in mounts], 'State':{'Status':'created','Running':False}}
        if self.fail_create: self.fail_create=False; raise RuntimeError('crash after create')
        return ident
    def start(self,name): self.objects[name]['State']={'Status':'running','Running':True}
    def wait(self,name):
        if self.on_wait: self.on_wait()
        self.objects[name]['State']={'Status':'exited','Running':False,'ExitCode':0}; return 0


class DockerInspectTest(unittest.TestCase):
    def test_exact_missing_diagnostics(self):
        import subprocess
        name='nga-cpu-123'
        for message in (f'error: no such object: {name}', f'Error: No such object: {name}',
                        f'Error response from daemon: No such container: {name}'):
            for stdout in ('', '[]\n'):
                with self.subTest(message=message, stdout=stdout), mock.patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout,message+'\n')) as run:
                    self.assertIsNone(M.Docker().inspect(name))
                    self.assertEqual(run.call_args.args[0],['docker','inspect',name])

    def test_ambiguous_failures_raise(self):
        import subprocess
        name='nga-cpu-123'; missing=f'error: no such object: {name}'
        cases=[('', 'error: no such object: other'), ('', missing+'4'),
               ('', missing+'\npermission denied'), ('', 'transport failed\n'+missing),
               ('', 'permission denied'), ('', 'Cannot connect to the Docker daemon'),
               ('', 'No such object'), ('', 'ERROR: NO SUCH OBJECT: '+name),
               ('', ' '+missing), ('', missing+'\n\n'), ('unexpected', missing),
               ('[]\nwarning', missing)]
        for stdout,stderr in cases:
            with self.subTest(stdout=stdout,stderr=stderr), mock.patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout,stderr)):
                with self.assertRaises(RuntimeError): M.Docker().inspect(name)

    def test_success_and_invalid_names(self):
        import subprocess
        with mock.patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'[{"Id":"x"}]','')):
            self.assertEqual(M.Docker().inspect('valid-name'),{'Id':'x'})
        with mock.patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'[]','error: no such object: valid-name')):
            with self.assertRaises(ValueError): M.Docker().inspect('valid-name')
        with mock.patch.object(M.subprocess,'run') as run:
            for name in ('--help', '', 'bad/name', 'bad\nname', None):
                with self.subTest(name=name), self.assertRaises(ValueError): M.Docker().inspect(name)
            run.assert_not_called()

    def test_success_nonobject_elements_rejected(self):
        import subprocess
        for element in (None, False, 0, 'x', []):
            with self.subTest(element=element), mock.patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps([element]),'')):
                with self.assertRaisesRegex(ValueError,'inspect result'): M.Docker().inspect('valid-name')


class ConsumerTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name); self.d=FakeDocker()
        self.c=self.fixture('first')
    def fixture(self, tag, source_override=None, source_config=None):
        r=self.root; out=r/(tag+'-out'); out.mkdir(); source=r/(tag+'-source'); source.mkdir()
        if source_override is not None: source=source_override
        inp=r/(tag+'-input'); inp.mkdir(); (inp/'manifest').write_text('{}'); (inp/'config').write_text('{}')
        task={'schema':'nga-unified-config-v1','adapter':'native-panel-export-v2','runtime':'cpu','source':'/run/nga/output/result','source_config':'/data/config','source_config_sha256':hashlib.sha256((inp/'config').read_bytes()).hexdigest(),'panel_manifest':'/data/manifest','panel_manifest_sha256':'a'*64,'owner_sha256':'a'*64,'output':'/run/nga/export/result'}
        tp=put(r/(tag+'-task.json'),task)
        lease={'lease_id':tag,'run':tag,'journal':str(r/'journal'), 'allocation':str(r/'allocation.json'), 'acceptance':{},'task_sha256':''}
        host={'name':tag,'image':'sha256:'+'a'*64,'entrypoint':'nga-engineering-v1','mounts':[],'task':{},'config':source_config or {'path':str(inp/'config'),'sha256':task['source_config_sha256']},'output':str(source),'lease':lease}
        launch={k:host[k] for k in ('name','image','entrypoint','mounts','task','config','output')}; lease['task_sha256']=M.digest(launch)
        hp=put(r/(tag+'-host.json'),host); conf=U.config_hash(lease); cid='c'*64
        terminal={'schema':'unified-container-terminal-v1','container_id':cid,'exit_code':0,'launch_sha256':lease['task_sha256']}
        meta=Path(str(source)+'.host-v1'); meta.mkdir(); t=put(meta/'terminal.json',terminal); rp=U.paths(lease,'release')[1]; rp.parent.mkdir(parents=True,exist_ok=True)
        binding={'schema':'unified-resource-binding-v1','config_sha256':conf,'lease_id':tag,'task_sha256':lease['task_sha256'],'container':tag,'container_id':cid,'chips':[0]}
        release={'schema':'unified-resource-transaction-v1','allocation':lease['allocation'],'op':'release','scientific_acceptance':False,'config_sha256':conf,'binding':binding,'chips':[0],'entries':[{'run':tag,'chip':0}],'exit_code':0,'after':{'free':[{'chip':0,'previous_run':tag,'release_evidence':str(rp)}],'allocation':[]}}
        release['after_sha256']=M.digest(release['after']); rel=put(rp,release); ev={'terminal':t,'release':rel}; event=put(r/(tag+'-event.json'),{'schema':'unified-cpu-handoff-v1','event_id':M.digest(ev),'evidence':ev,'scientific_acceptance':False})
        return {'schema':'unified-cpu-consumer-v1','event':event,'host_config':hp,'image':'sha256:'+'b'*64,'image_env':[],'export_receipt':None,'config':tp,'inputs':[{'source':str(inp/'manifest'),'target':'/data/manifest'},{'source':str(inp/'config'),'target':'/data/config'},{'source':str(source),'target':'/run/nga/output'}],'output':str(out),'controller':str(r/'controller'),'slots':1}
    def test_immediate_idempotent_and_command(self):
        a=M.Consumer(self.d).run(self.c); self.assertEqual(a,M.Consumer(self.d).run(self.c)); self.assertEqual(self.d.creates,1)
        self.assertEqual(a['meaning'],'physical completion'); self.assertFalse(a['scientific_acceptance'])
        cmd=M.args(self.c,M.validate(self.c)[3],'test','d'*64)
        self.assertIn(M.ENTRY,cmd); self.assertNotIn('--device',cmd); self.assertNotIn('ASCEND_RT_VISIBLE_DEVICES',str(cmd)); self.assertEqual(cmd[-1],M.CONFIG)
    def test_crash_after_create_and_before_ack(self):
        self.d.fail_create=True
        with self.assertRaises(RuntimeError): M.Consumer(self.d).run(self.c)
        original=M.write
        def crash_ack(path, value):
            if path.name=='ACK.json': raise RuntimeError('crash before ACK')
            return original(path,value)
        with mock.patch.object(M,'write',side_effect=crash_ack):
            with self.assertRaisesRegex(RuntimeError,'before ACK'): M.Consumer(self.d).run(self.c)
        self.assertEqual(list((self.root/'controller'/'slots').glob('*.json')),[])
        self.assertEqual(M.Consumer(self.d).run(self.c)['exit_code'],0); self.assertEqual(self.d.creates,1)
    def test_tampering_refused(self):
        M.Consumer(self.d).run(self.c)
        for kind in ('image','config','event','mount','source'):
            with self.subTest(kind=kind):
                c=copy.deepcopy(self.c)
                if kind=='image': c['image']='sha256:'+'f'*64
                if kind=='config': c['config']['sha256']='f'*64
                if kind=='event': c['event']['sha256']='f'*64
                if kind=='mount': c['inputs'][0]['target']='/other'
                if kind=='source': self.d.objects[next(iter(self.d.objects))]['Mounts'][0]['Source']='/other'
                with self.assertRaises((ValueError,KeyError)): M.Consumer(self.d).run(c)
    def test_slot_and_release_before_validation(self):
        other=self.fixture('second'); started=threading.Event(); finish=threading.Event(); errors=[]
        def wait(): started.set(); finish.wait(5)
        self.d.on_wait=wait
        def work():
            try: M.Consumer(self.d).run(self.c)
            except Exception as e: errors.append(e)
        t=threading.Thread(target=work); t.start(); self.assertTrue(started.wait(5))
        with self.assertRaisesRegex(ValueError,'slots full'): M.Consumer(self.d).run(other)
        finish.set(); t.join(5); self.assertFalse(errors)
        self.d.on_wait=None
        def validate(c, result):
            self.assertFalse(list((self.root/'controller'/'slots').glob('*.json')))
        self.assertEqual(M.Consumer(self.d,validate).run(other)['exit_code'],0)
    def test_ambiguous_inspect_retains_slot(self):
        import subprocess
        self.d.inspect=M.Docker().inspect
        failure=subprocess.CompletedProcess([],1,'', 'error: no such object: wrong-name\n')
        with mock.patch.object(M.subprocess,'run',return_value=failure):
            with self.assertRaisesRegex(RuntimeError,'docker inspect failed'): M.Consumer(self.d).run(self.c)
        self.assertEqual(self.d.creates,0)
        self.assertEqual(len(list((self.root/'controller'/'slots').glob('*.json'))),1)
        for filename in ('BINDING.json','TERMINAL.json','ACK.json','EXPORT.json'):
            self.assertFalse(list((self.root/'controller').rglob(filename)))
    def test_null_inspect_retains_reservation_without_create_or_start(self):
        import subprocess
        self.d.inspect=M.Docker().inspect
        response=subprocess.CompletedProcess([],0,'[null]','')
        with mock.patch.object(M.subprocess,'run',return_value=response), mock.patch.object(self.d,'create') as create, mock.patch.object(self.d,'start') as start:
            with self.assertRaisesRegex(ValueError,'inspect result'): M.Consumer(self.d).run(self.c)
        create.assert_not_called(); start.assert_not_called()
        ctl=self.root/'controller'
        self.assertEqual(len(list((ctl/'slots').glob('*.json'))),1)
        for filename in ('OWNER.json','PENDING.json'):
            self.assertEqual(len(list(ctl.rglob(filename))),1)
        for filename in ('BINDING.json','TERMINAL.json','ACK.json','EXPORT.json'):
            self.assertFalse(list(ctl.rglob(filename)))
    def test_historical_release_and_mismatch(self):
        # The consumer reads only the release snapshot, not a current NPU allocation.
        M.Consumer(self.d).run(self.c)
        other=self.fixture('third'); rp=Path(other['event']['path']); ev=json.loads(rp.read_text()); release=Path(ev['evidence']['release']['path']); data=json.loads(release.read_text()); data['entries'][0]['run']='successor'; ev['evidence']['release']=put(release,data); ev['event_id']=M.digest(ev['evidence']); other['event']=put(rp,ev)
        with self.assertRaisesRegex(ValueError,'release run'): M.Consumer(self.d).run(other)

    def test_review_rejections(self):
        for target in ('/opt/nga','/usr/local/Ascend','/dev','/data/../escape'):
            c=copy.deepcopy(self.c); c['inputs'][0]['target']=target
            with self.subTest(target=target), self.assertRaises(ValueError): M.validate(c)
        c=copy.deepcopy(self.c); c['inputs'][0]['source']='/dev/null'
        with self.assertRaises(ValueError): M.validate(c)
        for output in ('/run/nga/export','/run/nga/export/../escape'):
            c=copy.deepcopy(self.c); t=M.pin(c['config']);t['output']=output;c['config']=put(self.root/'bad.json',t)
            with self.assertRaises(ValueError): M.validate(c)
        for field,value in [('Env',['LD_PRELOAD=/data/x']),('Runtime','nvidia'),('DeviceCgroupRules',['c *:* rwm']),('RestartPolicy',{'Name':'always'}),('DeviceRequests',[{}]),('Devices',[{}]),('Privileged',True),('PidMode','host'),('IpcMode','host'),('UTSMode','host'),('UsernsMode','host'),('CgroupnsMode','host'),('PidMode','container:other')]:
            with self.subTest(field=field):
                d=FakeDocker();d.fail_create=True
                with self.assertRaises(RuntimeError): M.Consumer(d).run(self.c)
                ob=next(iter(d.objects.values())); (ob['Config'] if field=='Env' else ob['HostConfig'])[field]=value
                with self.assertRaises(ValueError): M.Consumer(d).run(self.c)
                # Discard this isolated controller and owner before the next case.
                import shutil
                shutil.rmtree(self.root/'controller');Path(self.c['output']+'.cpu-consumer-owner.json').unlink()
        d=FakeDocker();d.on_wait=lambda: next(iter(d.objects.values())).__setitem__('Id','f'*64)
        with self.assertRaisesRegex(ValueError,'ID changed'): M.Consumer(d).run(self.c)
        self.assertEqual(len(list((self.root/'controller'/'slots').glob('*.json'))),1)
        self.assertFalse(list((self.root/'controller').rglob('ACK.json')))

    def test_same_event_export_score_receipt(self):
        d=FakeDocker()
        def export():
            result=Path(self.c['output'])/'result';result.mkdir();(result/'manifest.json').write_text('{"records":"/run/nga/export/result/records"}')
        d.on_wait=export
        first=M.Consumer(d).run(self.c);self.assertEqual(first['exit_code'],0)
        receipt=next((self.root/'controller'/'jobs').glob('*/EXPORT.json'))
        scoreout=self.root/'score';scoreout.mkdir();manifest=Path(self.c['output'])/'result/manifest.json'
        task={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':'/run/nga/export/result/manifest.json','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'output':'/run/nga/score/result','workers':1,'chunk_size':1}
        score=copy.deepcopy(self.c);score.update(config=put(self.root/'score.json',task),inputs=[{'source':self.c['output'],'target':'/run/nga/export'}],output=str(scoreout),export_receipt={'path':str(receipt),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
        d.on_wait=None;second=M.Consumer(d).run(score)
        self.assertEqual(first['event_id'],second['event_id']);self.assertNotEqual(first['container_id'],second['container_id']);self.assertEqual(M.Consumer(d).run(score),second);self.assertEqual(d.creates,2)
        bad=copy.deepcopy(score);bad['export_receipt']['sha256']='f'*64
        with self.assertRaises(ValueError): M.validate(bad)
        manifest.write_text('{"changed":true}')
        with self.assertRaises(ValueError): M.validate(score)

    def test_trained_provenance_requires_real_mounted_dependencies(self):
        def export():
            result=Path(self.c['output'])/'result';result.mkdir();(result/'manifest.json').write_text('{"records":"/run/nga/export/result/records"}')
        self.d.on_wait=export;M.Consumer(self.d).run(self.c)
        receipt=next((self.root/'controller'/'jobs').glob('*/EXPORT.json'))
        manifest=Path(self.c['output'])/'result/manifest.json';out=self.root/'trained-score';out.mkdir()
        task={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':'/run/nga/export/result/manifest.json','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'output':'/run/nga/score/result','workers':1,'chunk_size':1,'trained_provenance':{'source':'/data/outside-source','source_config':'/data/outside-config','source_config_sha256':'a'*64,'source_manifest':'/data/outside-manifest','source_manifest_sha256':'a'*64,'receipt':'/data/outside-receipt','receipt_sha256':'a'*64}}
        score=copy.deepcopy(self.c);score.update(config=put(self.root/'trained-score.json',task),inputs=[{'source':self.c['output'],'target':M.EXPORT}],output=str(out),export_receipt={'path':str(receipt),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
        with self.assertRaises(ValueError): M.Consumer(self.d).run(score)
        self.assertEqual(self.d.creates,1)

    def test_actual_adapters_export_then_score_fixed_paths(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory(prefix='nga-consumer-chroot-') as root:
            p=subprocess.run(['unshare','--user','--map-root-user','--mount',sys.executable,
                              '-B','-P',str(Path(__file__).resolve()),'--namespace',root],
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        self.assertEqual(p.returncode,0,p.stdout)
        self.assertIn('consumer fixed paths passed',p.stdout)

    def test_source_child_and_host_mapping_rejected_before_effects(self):
        for source, wrong_host in [('/run/nga/output',False),('/run/nga/output/other',False),
                                   ('/run/nga/output/result',True)]:
            c=copy.deepcopy(self.c); task=M.pin(c['config']);task['source']=source
            c['config']=put(self.root/'bad-source.json',task)
            if wrong_host:
                other=self.root/'wrong-host-output';other.mkdir(exist_ok=True)
                c['inputs'][-1]['source']=str(other)
            with self.subTest(source=source,wrong_host=wrong_host), self.assertRaises(ValueError):
                M.Consumer(self.d).run(c)
            self.assertEqual(self.d.creates,0)
            self.assertFalse((self.root/'controller').exists())


def namespace(root):
    import os, subprocess, sys
    root=Path(root)
    subprocess.run(['mount','--make-rprivate','/'],check=True)
    for name in ('usr','lib','lib64','bin','etc','home','dev','proc','sys'):
        src=Path('/')/name
        if src.is_symlink(): (root/name).symlink_to(os.readlink(src))
        elif src.exists():
            (root/name).mkdir();subprocess.run(['mount','--rbind',str(src),str(root/name)],check=True)
    for name in ('model','data','run/nga/output','run/nga/export','run/nga/score','tmp'):
        (root/name).mkdir(parents=True,exist_ok=True)
    os.chroot(root);os.chdir(str(Path(__file__).resolve().parents[1]))
    os.execv(sys.executable,[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--inside'])


def inside():
    import importlib.util, shutil, subprocess
    path=Path(__file__).resolve().parents[1]/'docker/engineering-base/test_panel_bridge.py'
    spec=importlib.util.spec_from_file_location('consumer_bridge',path);bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
    case=bridge.Bridge(); temp=tempfile.TemporaryDirectory
    with mock.patch.object(bridge.tempfile,'TemporaryDirectory',side_effect=lambda:temp(dir='/data')): case.setUp()
    t=ConsumerTest();t.setUp()
    try:
        model=Path('/model/Qwen__Qwen3.5-0.8B-Base');shutil.copytree(case.modelroot/model.name,model)
        case.cfg['model']['path']=str(model);case.out=Path('/run/nga/output/result');case.cfg['output']=str(case.out)
        bridge.put(case.cfgpath,case.cfg)
        original=case.cfgpath.read_bytes();load=bridge.A.load
        def loader(path,name):
            module=load(path,name)
            if name=='nga_native_inference':
                module.load_tokenizer=lambda config:bridge.Tokenizer()
                module.load_model=lambda config:bridge.FrozenModel(case.vectors)
            return module
        with mock.patch.object(bridge.A,'load',side_effect=loader): case.invoke(case.cfg,case.cfgpath)
        assert case.cfgpath.read_bytes()==original
        hostout=Path('/run/nga/output')
        c=t.fixture('actual',hostout,{'path':str(case.cfgpath),'sha256':bridge.sha(case.cfgpath)})
        c['inputs']=[{'source':str(hostout),'target':M.OUTPUT},
                     {'source':str(case.cfgpath),'target':str(case.cfgpath)},
                     {'source':str(case.mp),'target':str(case.mp)}]
        expout=case.root/'export-mount';expout.mkdir();c['output']=str(expout)
        task=dict(schema='nga-unified-config-v1',adapter='native-panel-export-v2',runtime='cpu',
                  source=M.OUTPUT+'/result',owner_sha256=bridge.sha(case.out/'OWNER.json'),
                  source_config=str(case.cfgpath),source_config_sha256=bridge.sha(case.cfgpath),
                  panel_manifest=str(case.mp),panel_manifest_sha256=bridge.sha(case.mp),output=M.EXPORT+'/result')
        c['config']=put(case.root/'export-task.json',task)
        class Boundary(FakeDocker):
            def __init__(self): super().__init__();self.configs={}
            def create(self,c,mounts,name,launch):
                self.configs[name]=(copy.deepcopy(c),list(mounts));return super().create(c,mounts,name,launch)
            def start(self,name):
                config,mounts=self.configs[name];bound=[]
                try:
                    # Data paths already exist at their exact locations in this chroot.
                    # Bind the stage mount bases as the consumer specified; no bytes or paths change.
                    for src,dst,rw in mounts:
                        if dst not in (M.OUTPUT,M.EXPORT,M.SCORE): continue
                        subprocess.run(['mount','--bind',src,dst],check=True);bound.append(dst)
                        if not rw: subprocess.run(['mount','-o','remount,bind,ro',dst],check=True)
                    bridge.A.run(bridge.A.config(config['config']['path']),config['config']['path'])
                finally:
                    for dst in reversed(bound): subprocess.run(['umount',dst],check=True)
                self.objects[name]['State']={'Status':'exited','Running':False,'ExitCode':0}
        d=Boundary();consumer=M.Consumer(d);first=consumer.run(c)
        receipt=next((Path(c['controller'])/'jobs').glob('*/EXPORT.json'))
        scoreout=case.root/'score-mount';scoreout.mkdir();manifest=expout/'result/manifest.json'
        original_manifest=manifest.read_bytes()
        scoretask=dict(schema='nga-unified-config-v1',adapter='native-panel-score-v1',runtime='cpu',
                       manifest=M.EXPORT+'/result/manifest.json',manifest_sha256=bridge.sha(manifest),
                       output=M.SCORE+'/result',workers=1,chunk_size=1)
        sc=copy.deepcopy(c);sc.update(config=put(case.root/'score-task.json',scoretask),
             inputs=[{'source':str(expout),'target':M.EXPORT}],output=str(scoreout),
             export_receipt={'path':str(receipt),'sha256':bridge.sha(receipt)})
        second=consumer.run(sc)
        assert first['event_id']==second['event_id'] and first['container_id']!=second['container_id']
        assert consumer.run(c)==first and consumer.run(sc)==second and d.creates==2
        assert manifest.read_bytes()==original_manifest and case.cfgpath.read_bytes()==original
        baseline=case.score(case.baseline(),case.root/'baseline-score')
        actual=json.loads((scoreout/'result/summary.json').read_text())
        assert actual==baseline
        assert [(k,actual['by_type'][k]['correct']) for k in ('choice','yes_no','score')]==[('choice',1),('yes_no',1),('score',1)]
        print('consumer fixed paths passed')
    finally:
        case.tearDown();t.doCleanups()


if __name__=='__main__':
    import sys
    if '--namespace' in sys.argv: namespace(sys.argv[-1])
    elif '--inside' in sys.argv: inside()
    else: unittest.main()
