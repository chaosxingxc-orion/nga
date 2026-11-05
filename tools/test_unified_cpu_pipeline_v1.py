import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import unified_cpu_consumer_v1 as C
import unified_cpu_pipeline_v1 as P
import test_unified_cpu_consumer_v1 as fixture


class PipelineTest(unittest.TestCase):
    def test_full_private_namespace(self):
        with tempfile.TemporaryDirectory(prefix='nga-pipeline-') as root:
            p=subprocess.run(['unshare','--user','--map-root-user','--mount',sys.executable,'-B','-P',str(Path(__file__).resolve()),'--namespace',root],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        self.assertEqual(p.returncode,0,p.stdout)
        self.assertIn('pipeline fixed paths passed',p.stdout)


def inside():
    import importlib.util
    import shutil
    path=Path(__file__).resolve().parents[1]/'docker/engineering-base/test_panel_bridge.py'
    spec=importlib.util.spec_from_file_location('pipeline_bridge',path); bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
    case=bridge.Bridge(); temp=tempfile.TemporaryDirectory
    with mock.patch.object(bridge.tempfile,'TemporaryDirectory',side_effect=lambda:temp(dir='/data')): case.setUp()
    t=fixture.ConsumerTest();t.setUp()
    try:
        model=Path('/model/Qwen__Qwen3.5-0.8B-Base');shutil.copytree(case.modelroot/model.name,model)
        case.cfg['model']['path']=str(model);case.out=Path('/run/nga/output/result');case.cfg['output']=str(case.out);bridge.put(case.cfgpath,case.cfg)
        original=case.cfgpath.read_bytes();load=bridge.A.load
        def loader(path,name):
            module=load(path,name)
            if name=='nga_native_inference':
                module.load_tokenizer=lambda config:bridge.Tokenizer();module.load_model=lambda config:bridge.FrozenModel(case.vectors)
            return module
        with mock.patch.object(bridge.A,'load',side_effect=loader): case.invoke(case.cfg,case.cfgpath)
        c=t.fixture('actual',Path('/run/nga/output'),{'path':str(case.cfgpath),'sha256':bridge.sha(case.cfgpath)})
        inputs=[{'source':'/run/nga/output','target':C.OUTPUT},{'source':str(case.cfgpath),'target':str(case.cfgpath)},{'source':str(case.mp),'target':str(case.mp)}]
        for path in (model,Path(case.cfg['model']['manifest']),Path(case.cfg['dataset']['path']),*(case.paths[k] for k in ('contract','items','gold','requests'))):
            inputs.append({'source':str(path),'target':str(path)})
        task=dict(schema='nga-unified-config-v1',adapter='native-panel-export-v2',runtime='cpu',source=C.OUTPUT+'/result',owner_sha256=bridge.sha(case.out/'OWNER.json'),source_config=str(case.cfgpath),source_config_sha256=bridge.sha(case.cfgpath),panel_manifest=str(case.mp),panel_manifest_sha256=bridge.sha(case.mp),output=C.EXPORT+'/result')
        class Boundary(fixture.FakeDocker):
            def __init__(self): super().__init__();self.configs={}
            def create(self,c,mounts,name,launch):
                self.configs[name]=(copy.deepcopy(c),list(mounts));return super().create(c,mounts,name,launch)
            def start(self,name):
                config,mounts=self.configs[name]
                with tempfile.TemporaryDirectory() as td:
                    root=Path(td)/'root';root.mkdir();spec=Path(td)/'spec.json';spec.write_text(json.dumps({'root':str(root),'mounts':mounts}))
                    p=subprocess.run(['unshare','--mount','--propagation','unchanged',sys.executable,'-B','-P',str(Path(__file__).resolve()),'--strict',str(spec)],capture_output=True,text=True)
                    if p.returncode: print(p.stdout+p.stderr)
                self.objects[name]['State']={'Status':'exited','Running':False,'ExitCode':p.returncode}
            def wait(self,name): return self.objects[name]['State']['ExitCode']
        baseline=case.score(case.baseline(),case.root/'baseline-score')
        for crash in ('after_export','after_score_config',None):
            root=case.root/('pipeline-'+str(crash));root.mkdir();exp=root/'export';exp.mkdir();score=root/'score';score.mkdir()
            template={'schema':'unified-cpu-pipeline-template-v1','export':task,'score':{'workers':1,'chunk_size':1}}
            cfg={'schema':'unified-cpu-pipeline-v1','authorization':'existing-completed-host-event-cpu-processing','event':c['event'],'host_config':c['host_config'],'image':c['image'],'image_env':[],'template':fixture.put(root/'template.json',template),'inputs':inputs,'export_output':str(exp),'score_output':str(score),'controller':str(root/'controller'),'slots':1,'state_dir':str(root/'state')}
            cfgref=fixture.put(root/'pipeline.json',cfg);d=Boundary();worker=C.Consumer(d)
            def fail(stage):
                if stage==crash: raise RuntimeError('crash')
            if crash:
                try: P.run(cfgref,worker,fail);assert False
                except RuntimeError as e: assert str(e)=='crash'
                assert d.creates==1
            terminal=P.run(cfgref,worker);assert d.creates==2
            manifest=Path(terminal['manifest']['path']);manifest_bytes=manifest.read_bytes()
            assert P.run(cfgref,worker)==terminal and d.creates==2
            for field,value in (('Mounts',[]),('Image','sha256:'+'f'*64)):
                obj=next(iter(d.objects.values()));saved=copy.deepcopy(obj[field]);obj[field]=value
                try:P.run(cfgref,worker);assert False
                except ValueError:pass
                assert d.creates==2;obj[field]=saved
            assert manifest.read_bytes()==manifest_bytes
            actual=json.loads((score/'result/summary.json').read_text());assert actual==baseline
            assert [(k,actual['by_type'][k]['correct']) for k in ('choice','yes_no','score')]==[('choice',1),('yes_no',1),('score',1)]
            assert case.cfgpath.read_bytes()==original
            receipt=Path(terminal['export_receipt']['path']); saved=receipt.read_bytes()
            for altered in (b'{}',json.dumps({**json.loads(saved),'event_id':'f'*64}).encode()):
                receipt.write_bytes(altered)
                try: P.run(cfgref,worker);assert False
                except (ValueError,KeyError): pass
                assert d.creates==2
            receipt.write_bytes(saved)
            for path in (score/'result/summary.json',score/'result/OWNER.json',score/'result/report.json',score/'result/EXIT.json',exp/'result/records/000000/record.json'):
                saved=path.read_bytes();path.write_text('{}\n')
                try: P.run(cfgref,worker);assert False, str(path)
                except (ValueError,KeyError): pass
                assert d.creates==2;path.write_bytes(saved)
            assert P.run(cfgref,worker)==terminal and d.creates==2
        for key,value in (('workers',33),('chunk_size',1025)):
            root=case.root/('invalid-'+key);root.mkdir();(root/'export').mkdir();(root/'score').mkdir()
            bad={'schema':'unified-cpu-pipeline-template-v1','export':task,'score':{'workers':1,'chunk_size':1}};bad['score'][key]=value
            altered={**cfg,'template':fixture.put(root/'template.json',bad),'export_output':str(root/'export'),'score_output':str(root/'score'),'controller':str(root/'controller'),'state_dir':str(root/'state')}
            badref=fixture.put(root/'pipeline.json',altered);d=Boundary()
            try:P.run(badref,C.Consumer(d));assert False
            except ValueError:pass
            assert d.creates==0 and not (root/'state').exists() and not (root/'controller').exists()
        for name in ('completion.json','EXIT.json','items/00000000/COMMITTED.json'):
            root=case.root/('foreign-'+name.replace('/','-'));root.mkdir();(root/'export').mkdir();(root/'score').mkdir()
            altered={**cfg,'export_output':str(root/'export'),'score_output':str(root/'score'),'controller':str(root/'controller'),'state_dir':str(root/'state')}
            cfgref=fixture.put(root/'pipeline.json',altered);d=Boundary();path=case.out/name;saved=path.read_bytes();path.write_text('{}\n')
            try:
                try:P.run(cfgref,C.Consumer(d));assert False
                except (ValueError,KeyError):pass
                assert d.creates==1 and not (root/'export/result').exists()
            finally:path.write_bytes(saved)
        for artifact in ('summary.json','OWNER.json','report.json','EXIT.json'):
            root=case.root/('ack-'+artifact);root.mkdir();(root/'export').mkdir();(root/'score').mkdir()
            altered={**cfg,'export_output':str(root/'export'),'score_output':str(root/'score'),'controller':str(root/'controller'),'state_dir':str(root/'state')}
            cfgref=fixture.put(root/'pipeline.json',altered);d=Boundary();worker=C.Consumer(d)
            class CrashAfterAck:
                def run(self,cfg):
                    ack=worker.run(cfg)
                    if C.pin(cfg['config'])['adapter']=='native-panel-score-v1': raise RuntimeError('score ACK crash')
                    return ack
            try:P.run(cfgref,CrashAfterAck());assert False
            except RuntimeError as e:assert str(e)=='score ACK crash'
            assert d.creates==2 and not (root/'state/TERMINAL.json').exists()
            path=root/'score/result'/artifact;saved=path.read_bytes();path.write_text('{}\n')
            try:P.run(cfgref,worker);assert False,artifact
            except (ValueError,KeyError):pass
            assert d.creates==2 and not (root/'state/TERMINAL.json').exists()
            path.write_bytes(saved);terminal=P.run(cfgref,worker);terminal_bytes=(root/'state/TERMINAL.json').read_bytes()
            assert P.run(cfgref,worker)==terminal and (root/'state/TERMINAL.json').read_bytes()==terminal_bytes and d.creates==2
        for artifact in ('summary.json','OWNER.json','report.json','EXIT.json'):
            root=case.root/('before-terminal-'+artifact);root.mkdir();(root/'export').mkdir();(root/'score').mkdir()
            altered={**cfg,'export_output':str(root/'export'),'score_output':str(root/'score'),'controller':str(root/'controller'),'state_dir':str(root/'state')}
            cfgref=fixture.put(root/'pipeline.json',altered);d=Boundary();worker=C.Consumer(d)
            class Tamper:
                def run(self,cfg):
                    ack=worker.run(cfg)
                    if C.pin(cfg['config'])['adapter']=='native-panel-score-v1': (Path(cfg['output'])/'result'/artifact).unlink()
                    return ack
            try:P.run(cfgref,Tamper());assert False,artifact
            except (ValueError,KeyError,FileNotFoundError):pass
            assert d.creates==2 and not (root/'state/TERMINAL.json').exists()
        print('pipeline fixed paths passed')
    finally: case.tearDown();t.doCleanups()


if __name__=='__main__':
    if '--strict' in sys.argv:
        import os, importlib.util
        spec=json.loads(Path(sys.argv[-1]).read_text());root=Path(spec['root'])
        for name in ('usr','lib','lib64','bin','etc','home','dev','proc','sys'):
            src=Path('/')/name
            if src.is_symlink(): (root/name).symlink_to(os.readlink(src))
            elif src.exists():
                (root/name).mkdir();subprocess.run(['mount','--rbind',str(src),str(root/name)],check=True)
        for name in ('model','data','run/nga/output','run/nga/export','run/nga/score','tmp'): (root/name).mkdir(parents=True,exist_ok=True)
        for src,dst,rw in spec['mounts']:
            dest=root/dst.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True)
            if Path(src).is_dir(): dest.mkdir(exist_ok=True)
            else: dest.touch()
            subprocess.run(['mount','--bind',src,str(dest)],check=True)
            if not rw: subprocess.run(['mount','-o','remount,bind,ro',str(dest)],check=True)
        os.chroot(root);os.chdir(str(Path(__file__).resolve().parents[1]))
        path=Path(__file__).resolve().parents[1]/'docker/engineering-base/adapter.py'
        s=importlib.util.spec_from_file_location('strict_adapter',path);a=importlib.util.module_from_spec(s);s.loader.exec_module(a);a.run(a.config(C.CONFIG),C.CONFIG)
    elif '--namespace' in sys.argv:
        # Reuse the exact-path fixture's setup but execute this test after chroot.
        import os
        root=Path(sys.argv[-1]);subprocess.run(['mount','--make-rprivate','/'],check=True)
        for name in ('usr','lib','lib64','bin','etc','home','dev','proc','sys'):
            src=Path('/')/name
            if src.is_symlink(): (root/name).symlink_to(os.readlink(src))
            elif src.exists():
                (root/name).mkdir();subprocess.run(['mount','--rbind',str(src),str(root/name)],check=True)
        for name in ('model','data','run/nga/output','run/nga/export','run/nga/score','tmp'): (root/name).mkdir(parents=True,exist_ok=True)
        os.chroot(root);os.chdir(str(Path(__file__).resolve().parents[1]));os.execv(sys.executable,[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--inside'])
    elif '--inside' in sys.argv: inside()
    else: unittest.main()
