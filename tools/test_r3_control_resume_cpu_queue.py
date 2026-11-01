"""Synthetic handoff tests; no real Docker, NPU or checkpoint reads."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('cpu_queue',HERE/'r3_control_resume_cpu_queue.py')
Q=importlib.util.module_from_spec(s);s.loader.exec_module(Q)


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.restart=self.root/'restart';self.restart.mkdir()
        self.out=self.root/'cpu';self.job={'id':'qo','restart_out':str(self.restart),'out':str(self.out),'container':'cpu-qo'}
        self.pin='a'*64
    def put(self,p,value):Q.C.atomic(p,value)
    def ready(self):
        self.put(self.restart/'plan.json',{})
        self.put(self.restart/'LAUNCH_PREPARATION.json',{'plan':str(self.restart/'plan.json'),'plan_sha256':self.pin})
        self.put(self.restart/'TRAIN_EXIT.json',{'attempt':1,'exit_code':0})
        attempt=self.restart/'attempts/1';attempt.mkdir(parents=True)
        for name in ('RELEASE.json','SUPERVISOR_DONE.json'):self.put(attempt/name,{})
    def test_waits_for_actual_release_and_rejects_failed_restart(self):
        self.assertEqual(Q.tick(self.job)['status'],'waiting_restart')
        self.ready();(self.restart/'attempts/1/RELEASE.json').unlink()
        with patch.object(Q,'module',return_value=SimpleNamespace(identity=lambda p:self.pin)), \
             patch.object(Q.C,'prepare') as prepare:
            self.assertEqual(Q.tick(self.job)['status'],'waiting_restart_release');prepare.assert_not_called()
            self.put(self.restart/'TRAIN_EXIT.json',{'attempt':1,'exit_code':1})
            self.assertEqual(Q.tick(self.job)['status'],'restart_failed')
    def test_partial_preparation_never_retries(self):
        self.put(self.out.with_name('cpu.PREPARE_INTENT.json'),{'job':self.job})
        with patch.object(Q.C,'prepare') as prepare:
            self.assertEqual(Q.tick(self.job)['status'],'needs_repair');prepare.assert_not_called()
    def test_prepares_once_then_reuses_frozen_controller(self):
        self.ready();calls=[]
        def module(name,root=Q.HERE):
            return SimpleNamespace(identity=lambda p:self.pin)
        def prepare(plan,pin,out,container):
            calls.append(1)
            with patch.object(Q.C,'released',return_value=({},self.target,{},{})):
                return real_prepare(plan,pin,out,container)
        source=self.root/'source';source.mkdir();code=source/'code';code.mkdir()
        files={}
        for rel in ('train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'):
            p=code/rel;p.parent.mkdir(exist_ok=True);p.write_text('# fixture\n');files[str(p)]=Q.C.sha(p)
        self.target=source/'SOURCE_PLAN.json';self.put(self.target,{'code':str(code),'files':files})
        real_prepare=Q.C.prepare
        # Real frozen source executes; only its external Docker boundary is replaced.
        actual={'Id':'b'*64,'State':{'Status':'running'}}
        with patch.object(Q,'module',side_effect=module),patch.object(Q.C,'released',return_value={}), \
             patch.object(Q.C,'prepare',side_effect=prepare), \
             patch('subprocess.run') as run:
            run.return_value=SimpleNamespace(returncode=1,stdout='',stderr='daemon unavailable')
            for _ in range(2):
                with self.assertRaises(RuntimeError):Q.tick(self.job)
        self.assertEqual(len(calls),1)

    def test_self_consistent_untrusted_prepared_child_rejected_before_execution(self):
        self.out.mkdir();code=self.out/'code';code.mkdir()
        import shutil
        for name in ('r3_control_resume_cpu.py','r3_resume_recompute.py','r3_resume_evidence.py','r3_formal_launcher.py'):
            shutil.copyfile(Q.HERE/name,code/name)
        child=code/'r3_control_resume_cpu.py'
        child.write_text('raise AssertionError("UNTRUSTED_CHILD_EXECUTED")\n')
        cfg={'schema':'r3-control-resume-cpu-v1','out':str(self.out),'container':self.job['container'],
             'image':Q.C.IMAGE,'plan':str(self.restart/'plan.json'),'files':{},
             'tools':{str(p):Q.C.sha(p) for p in code.iterdir()},
             'scientific_acceptance':False,'test_read':False}
        path=self.out/'CONFIG.json';self.put(path,cfg)
        self.put(self.out.with_name('cpu.PREPARED.json'),{'job':self.job,
                 'config':{'config':str(path),'sha256':Q.C.sha(path)}})
        with patch.object(Q.C,'verify',wraps=Q.C.verify) as verify:
            with self.assertRaisesRegex(ValueError,'obsolete prepared CPU implementation'):Q.tick(self.job)
            verify.assert_called_once_with(str(path),Q.C.sha(path),prepared_by_current=True)

    def test_plan_identity_and_container_confusion_refused(self):
        self.ready()
        with patch.object(Q,'module',return_value=SimpleNamespace(identity=lambda p:'wrong')):
            with self.assertRaisesRegex(ValueError,'identity'):Q.tick(self.job)

    def test_direct_successor_binds_exact_plan_and_preparation(self):
        R=Q.module('r3_resume_evidence')
        plan={'chip':1,'out':str(self.restart),'review_sha256':'PENDING'}
        self.put(self.restart/'plan.json',plan)
        self.put(self.restart/'LAUNCH_PREPARATION.json',{})
        successor=self.root/'successor.json'
        entry={'id':'qo','chip':1,'next_kind':'training',
               'next_execution':str(self.restart/'plan.json'),'next_sha256':R.identity(plan)}
        def write_manifest():
            self.put(successor,{'schema':'r3-eval-successor-v1','jobs':[entry]})
            manifest=self.root/'queue.json'
            self.put(manifest,{'schema':'r3-control-resume-cpu-queue-v1','interval_seconds':600,
                'scientific_acceptance':False,'test_read':False,
                'tools':{str(Q.HERE/n):Q.C.sha(Q.HERE/n) for n in Q.TOOLS},
                'successor_queue':str(successor),'successor_queue_sha256':Q.C.sha(successor),
                'jobs':[self.job]})
            return manifest,Q.C.sha(manifest)
        args=write_manifest();Q.verify(*args)
        entry['next_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source differs'):Q.verify(*write_manifest())
        entry['next_sha256']=R.identity(plan);entry['next_kind']='evaluation'
        with self.assertRaisesRegex(ValueError,'not bound'):Q.verify(*write_manifest())
        entry['next_kind']='training';(self.restart/'LAUNCH_PREPARATION.json').unlink()
        with self.assertRaisesRegex(ValueError,'preparation missing'):Q.verify(*write_manifest())


if __name__=='__main__':unittest.main()
