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
        frozen=SimpleNamespace(start=lambda *a:{'status':'started'})
        def module(name,root=Q.HERE):
            return SimpleNamespace(identity=lambda p:self.pin) if name=='r3_resume_evidence' else frozen
        def prepare(plan,pin,out,container):
            calls.append(1);out.mkdir();(out/'code').mkdir()
            self.put(out/'CONFIG.json',{'plan':str(plan),'container':container})
            return {'config':str(out/'CONFIG.json'),'sha256':'b'*64}
        with patch.object(Q,'module',side_effect=module),patch.object(Q.C,'released',return_value={}), \
             patch.object(Q.C,'prepare',side_effect=prepare):
            self.assertEqual(Q.tick(self.job)['status'],'started')
            self.assertEqual(Q.tick(self.job)['status'],'started')
        self.assertEqual(len(calls),1)
    def test_plan_identity_and_container_confusion_refused(self):
        self.ready()
        with patch.object(Q,'module',return_value=SimpleNamespace(identity=lambda p:'wrong')):
            with self.assertRaisesRegex(ValueError,'identity'):Q.tick(self.job)


if __name__=='__main__':unittest.main()
