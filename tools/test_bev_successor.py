import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import hashlib

spec=importlib.util.spec_from_file_location('bev_successor',Path(__file__).with_name('bev_successor.py'))
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)

class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.old=self.root/'old';self.old.mkdir();self.at=self.old/'attempts/1';self.at.mkdir(parents=True)
        self.out=self.root/'controller';self.out.mkdir()
        self.plan=dict(schema='r3-engineering-k1-plan-v1',out=str(self.old),run='r3_runs/old',container='nga-old',chip=1,
                       launcher='/fixed/launcher.py',allocation=str(self.root/'allocation.json'),review_sha256='PENDING',scientific_acceptance=False,test_read=False)
        self.write(self.old/'plan.json',self.plan)
        self.pin=hashlib.sha256((json.dumps(self.plan,indent=2,sort_keys=True)+'\n').encode()).hexdigest()
        self.write(self.at/'LAUNCH_RECEIPT.json',dict(id='oldid',plan_sha256=self.pin))
        self.write(self.old/'SUPERVISOR_RECEIPT.json',dict(command=['/usr/bin/python3.12','-P','/fixed/launcher.py','supervise','--plan',str(self.old/'plan.json'),'--sha256',self.pin,'--attempt','1']))
        self.c=dict(previous={k:S.W.pin(v) for k,v in dict(plan=self.old/'plan.json',supervisor=self.old/'SUPERVISOR_RECEIPT.json',launch=self.at/'LAUNCH_RECEIPT.json').items()},output=str(self.out))
        self.c['previous']['attempt']=1
        self.actual=dict(Id='oldid',Name='/nga-old-a1',State=dict(Status='exited',ExitCode=0),HostConfig=dict(Devices=[dict(PathOnHost='/dev/davinci1')]))
        self.next=dict(out=str(self.root/'next'),chip=1,container='nga-next')
        self.entry=dict(plan=dict(path='/next/plan.json',sha256='a'*64),attempt=1)
        self.c.update(entrypoint=dict(path='/fixed/entry.py'),entry=dict(path='/entry.json',sha256='b'*64),cpu={},consumer={})
    def write(self,p,d): p.write_text(json.dumps(d))
    def ready(self):
        end=dict(attempt=1,exit_code=0)
        self.write(self.old/'TRAIN_EXIT.json',end);self.write(self.at/'EXIT.json',end)
        self.write(self.at/'RELEASE.json',dict(schema='r3-resource-release-v1',exit_code=0,chip=1,run='r3_runs/old',container_id='oldid',scientific_acceptance=False))
        self.write(self.root/'allocation.json',dict(allocation=[],free=[dict(chip=1,previous_run='r3_runs/old',release_evidence=str(self.at/'RELEASE.json'))]))
    def test_wait_has_no_remote_or_launch(self):
        self.assertIsNone(S.previous_ready(self.c,self.plan,lambda a:self.fail('remote called before terminal')))
        self.assertEqual(S.tick(self.c,self.plan,lambda a:self.fail('launch while running'))['status'],'waiting_predecessor_release')
    def test_actual_receipt_shape_accepts_success(self):
        self.ready();r=S.previous_ready(self.c,self.plan,lambda a:[self.actual]);self.assertEqual(r['container_id'],'oldid')
    def test_wrong_release_identity_refuses(self):
        self.ready();d=json.loads((self.at/'RELEASE.json').read_text());d['container_id']='wrong';self.write(self.at/'RELEASE.json',d)
        with self.assertRaisesRegex(ValueError,'release identity'):S.previous_ready(self.c,self.plan,lambda a:[self.actual])
    def test_live_container_refuses_even_with_release(self):
        self.ready();self.actual['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'retained state'):S.previous_ready(self.c,self.plan,lambda a:[self.actual])
    def test_stale_free_generation_refuses(self):
        self.ready();self.write(self.root/'allocation.json',dict(allocation=[],free=[dict(chip=1,previous_run='another',release_evidence=str(self.at/'RELEASE.json'))]))
        with self.assertRaisesRegex(ValueError,'free generation'):S.previous_ready(self.c,self.plan,lambda a:[self.actual])
    def test_failed_marker_refuses(self):
        self.ready();d=dict(attempt=1,exit_code=1);self.write(self.old/'TRAIN_EXIT.json',d);self.write(self.at/'EXIT.json',d)
        with self.assertRaisesRegex(ValueError,'unsuccessful'):S.previous_ready(self.c,self.plan,lambda a:[self.actual])
    def test_uncertain_launch_never_replayed(self):
        self.ready()
        def observe(a):
            if a[0]=='docker':return [self.actual]
            raise TimeoutError('SSH timeout')
        with patch.object(S,'validate_next',return_value=(self.entry,self.next)):
            with self.assertRaises(TimeoutError):S.tick(self.c,self.plan,observe)
            self.assertEqual(S.tick(self.c,self.plan,lambda a:self.fail('replayed'))['status'],'needs_reconciliation')
    def test_success_delegates_cpu_once_without_second_npu(self):
        self.ready();calls=[]
        def observe(a):
            calls.append(a)
            if a[0]=='docker':
                if a[-1]=='oldid':return [self.actual]
                return [dict(Id='newid',Name='/nga-next-a1',State=dict(Status='running'),HostConfig=dict(Devices=[dict(PathOnHost='/dev/davinci1')]))]
            host=Path(self.next['out'])/'host_attempts/1';host.mkdir(parents=True)
            self.write(host/'LAUNCH_RECEIPT.json',dict(container_id='newid',plan_sha256='a'*64))
            return dict(status='guarded_start_returned')
        with patch.object(S,'validate_next',return_value=(self.entry,self.next)),patch.object(S.W,'cpu_start',return_value={'status':'already_running'}) as cpu:
            self.assertEqual(S.tick(self.c,self.plan,observe)['status'],'handed_off')
            self.assertEqual(S.tick(self.c,self.plan,observe)['status'],'handed_off')
            self.assertEqual(sum(a[0]!='docker' for a in calls),1);self.assertEqual(cpu.call_count,2)
    def test_changed_predecessor_launch_pin_rejected(self):
        self.ready();self.write(self.at/'LAUNCH_RECEIPT.json',dict(id='wrong',plan_sha256=self.pin))
        with self.assertRaisesRegex(ValueError,'pinned content'):S.previous_ready(self.c,self.plan,lambda a:[self.actual])

if __name__=='__main__':unittest.main()
