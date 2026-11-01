"""CPU lifecycle fixtures; all Docker/process boundaries are explicit fakes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import sys

spec = importlib.util.spec_from_file_location('formal_successor', Path(__file__).with_name('r3_formal_train_successor.py'))
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.previous = self.root/'previous'; self.previous.mkdir()
        self.out = self.root/'formal'; self.out.mkdir(); self.state = self.root/'queue'; self.state.mkdir()
        self.execution = self.previous/'execution.json'
        self.prior = dict(schema='r3-engineering-posttrain-execution-v1', chip=1, out=str(self.previous),
                          run='prior-run', launcher='/frozen/eval.py', container='parent')
        self.write(self.execution, self.prior)
        self.job = dict(id='seed2', chip=1, attempt=1, plan=str(self.out/'plan.json'), plan_sha256='canonical',
                        plan_raw_sha256='raw', previous_execution=str(self.execution),
                        previous_execution_sha256=S.digest(self.execution.read_bytes()), fresh_files=[])
        self.p = dict(out=str(self.out), launcher='/frozen/train.py', adapter='/frozen/resource.py',
                      files={'/frozen/resource.py': 'resource'}, chip=1, container='formal', allocation='/allocation')
        self.a = dict(competitors={'seed2': []}, allowed_jobs=['seed2'])
        self.resource = types.SimpleNamespace(docker_inspect=lambda n: self.actual if n=='parent-a1' else None,
            load=lambda p: self.ledger, validate_doc=lambda d: None, read_bytes=lambda p: b'ledger', live_chip_conflict=lambda *a: False)
        self.ledger = dict(allocation=[], free=[dict(chip=1, previous_run='prior-run', release_evidence=str(self.previous/'attempts/1/RELEASE.json'))])
        self.actual = dict(Id='parent-id', Image='image', State=dict(Status='exited', ExitCode=0),
                           Config=dict(Cmd=['drive']), HostConfig=dict(AutoRemove=False, Devices=[dict(PathOnHost=x) for x in
                           ['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci1']]))
        self.live = patch.object(S, 'process_matches', return_value=False); self.live.start();self.addCleanup(self.live.stop)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))

    def finish_parent(self):
        end=dict(exit_code=0, attempt=1); a=self.previous/'attempts/1'
        self.write(self.previous/'ENGINEERING_EVAL_EXIT.json', end);self.write(a/'EXIT.json', end)
        cmd=[sys.executable,'-P',self.prior['launcher'],'supervise','--plan',str(self.execution),
             '--sha256',self.job['previous_execution_sha256'],'--attempt','1']
        self.write(self.previous/'SUPERVISOR_RECEIPT.json',dict(pid=999,command=cmd))
        self.write(a/'LAUNCH_RECEIPT.json',dict(id='parent-id',image='image',sha256=self.job['previous_execution_sha256']))
        self.write(a/'LAUNCH_SPEC.json',dict(command=['docker','run','image','drive'],sha256=self.job['previous_execution_sha256']))
        self.write(a/'RELEASE.json',dict(schema='r3-resource-release-v1',chip=1,run='prior-run',container='parent-a1',
                                       container_id='parent-id',exit_code=0,scientific_acceptance=False))
        self.write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))

    def test_wait_parent_then_eligible_hashes(self):
        self.assertIsNone(S.predecessor(self.job,self.resource));self.finish_parent()
        result=S.ready(self.job,self.p,self.resource,self.a)
        self.assertEqual(result['status'],'eligible');self.assertEqual(len(result['previous']['hashes']),7)

    def test_done_is_required(self):
        self.finish_parent();(self.previous/'attempts/1/SUPERVISOR_DONE.json').unlink()
        self.assertIsNone(S.predecessor(self.job,self.resource))

    def test_wrong_plan_bytes(self):
        self.finish_parent();self.execution.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'content changed'):S.predecessor(self.job,self.resource)

    def test_wrong_release_generation_or_owner(self):
        self.finish_parent();p=self.previous/'attempts/1/RELEASE.json';original=json.loads(p.read_text())
        for field,value in [('container_id','wrong'),('chip',4),('run','foreign'),('exit_code',1)]:
            self.write(p,dict(original,**{field:value}))
            with self.assertRaises(RuntimeError):S.predecessor(self.job,self.resource)

    def test_retained_wrong_command_or_live(self):
        self.finish_parent();self.actual['Config']['Cmd']=['foreign']
        with self.assertRaisesRegex(RuntimeError,'command/device'):S.predecessor(self.job,self.resource)
        self.actual['Config']['Cmd']=['drive'];self.actual['State']['Status']='running'
        with self.assertRaisesRegex(RuntimeError,'terminal'):S.predecessor(self.job,self.resource)

    def test_newer_parent_retry_waits(self):
        self.finish_parent();p=self.previous/'SUPERVISOR_RECEIPT.json';v=json.loads(p.read_text());v['command'][-1]='2';self.write(p,v)
        self.assertIsNone(S.predecessor(self.job,self.resource))

    def test_competing_owner_and_wrong_free_release(self):
        self.finish_parent();self.ledger['allocation']=[dict(chip=1,run='other')]
        self.assertEqual(S.ready(self.job,self.p,self.resource,self.a)['status'],'waiting_resource_owner')
        self.ledger['allocation']=[];self.ledger['free'][0]['previous_run']='wrong'
        with self.assertRaisesRegex(RuntimeError,'free ledger release'):S.ready(self.job,self.p,self.resource,self.a)

    def test_competing_authorized_successor(self):
        self.finish_parent();p=self.root/'service.json';self.write(p,dict(pid=1,command=['other']))
        self.a['competitors']['seed2']=[dict(receipt=str(p),sha256=S.digest(p.read_bytes()))]
        with patch.object(S,'process_matches',side_effect=lambda r:r['pid']==1):
            with self.assertRaisesRegex(RuntimeError,'competing authorized'):S.ready(self.job,self.p,self.resource,self.a)

    def test_collision_and_fresh_output(self):
        self.finish_parent();original=self.resource.docker_inspect
        self.resource.docker_inspect=lambda n: self.actual
        with self.assertRaisesRegex(RuntimeError,'name collision'):S.ready(self.job,self.p,self.resource,self.a)
        self.resource.docker_inspect=original;(self.out/'ckpt').mkdir();(self.out/'ckpt/old.pt').touch()
        with self.assertRaisesRegex(RuntimeError,'not fresh'):S.ready(self.job,self.p,self.resource,self.a)

    def test_live_device_and_symlink(self):
        self.finish_parent();self.resource.live_chip_conflict=lambda *a:True
        with self.assertRaisesRegex(RuntimeError,'device holder'):S.ready(self.job,self.p,self.resource,self.a)
        self.resource.live_chip_conflict=lambda *a:False;(self.out/'foreign').symlink_to(self.previous)
        with self.assertRaisesRegex(RuntimeError,'symlink'):S.ready(self.job,self.p,self.resource,self.a)

    def test_exactly_once_start_and_uncertain_replay(self):
        self.finish_parent()
        with patch.object(S,'plan',return_value=self.p),patch.object(S,'source',return_value=self.resource),patch.object(S.subprocess,'run') as run:
            self.assertEqual(S.tick(self.job,self.a,self.state)['status'],'launch_requested')
            self.assertEqual(run.call_count,2);self.assertEqual(run.call_args.args[0][3],'start')
            self.assertEqual(S.tick(self.job,self.a,self.state)['status'],'needs_repair')
            self.assertEqual(run.call_count,2)

    def test_failed_start_intent_prevents_replay(self):
        self.finish_parent()
        with patch.object(S,'plan',return_value=self.p),patch.object(S,'source',return_value=self.resource),patch.object(S.subprocess,'run',side_effect=[None,RuntimeError('uncertain')]) as run:
            with self.assertRaisesRegex(RuntimeError,'uncertain'):S.tick(self.job,self.a,self.state)
            self.assertEqual(S.tick(self.job,self.a,self.state)['status'],'needs_repair');self.assertEqual(run.call_count,2)

    def test_wrong_intent_cannot_adopt(self):
        self.write(self.state/'seed2.START_INTENT.json',{'job':dict(self.job,plan_sha256='foreign')})
        with patch.object(S,'plan',return_value=self.p),patch.object(S,'source',return_value=self.resource):
            with self.assertRaisesRegex(RuntimeError,'wrong plan'):S.tick(self.job,self.a,self.state)

    def test_nonblocking_queue(self):
        jobs=[dict(self.job,id='seed3'),self.job];auth=dict(self.a,allowed_jobs=['seed2','seed3'])
        with patch.object(S,'tick',side_effect=[RuntimeError('busy seed3'),{'status':'launch_requested'}]) as tick:
            result=S.cycle({'jobs':jobs},auth,self.state)
        self.assertEqual(tick.call_count,2);self.assertEqual(result['seed2']['status'],'launch_requested')

    def test_retained_completion_and_wrong_release(self):
        p=dict(self.p, image_sha256='image', files={**self.p['files'],self.p['launcher']:'launcher'})
        a=self.out/'attempts/1';cmd=[sys.executable,'-P',p['launcher'],'supervise','--plan',self.job['plan'],
                                  '--sha256',self.job['plan_sha256'],'--attempt','1']
        self.write(self.out/'SUPERVISOR_RECEIPT.json',dict(pid=999,command=cmd))
        self.write(a/'LAUNCH_RECEIPT.json',dict(id='formal-id',plan_sha256='canonical'))
        actual=dict(Id='formal-id',Image='image',Config=dict(Cmd=['-P','/workspace/r3_formal_driver.py','--plan',self.job['plan'],'--attempt','1']),
                    HostConfig=dict(AutoRemove=False),State=dict(Status='exited',ExitCode=0))
        self.resource.docker_inspect=lambda n:actual
        launcher=types.SimpleNamespace(verify_retained_receipts=lambda *a:None,docker_command=lambda *a:[])
        with patch.object(S,'source',return_value=launcher):
            self.assertEqual(S.observe(self.job,p,{'job':self.job},self.resource)['status'],'waiting_successor_release_and_done')
            end=dict(exit_code=0,attempt=1)
            for target in [self.out/'TRAIN_EXIT.json',a/'EXIT.json']:self.write(target,end)
            release=dict(schema='r3-resource-release-v1',run='formal-run',chip=1,container_id='formal-id',exit_code=0,scientific_acceptance=False)
            p['run']='formal-run';self.write(a/'RELEASE.json',release);self.write(a/'SUPERVISOR_DONE.json',dict(exit_code=0,scientific_acceptance=False))
            self.assertEqual(S.observe(self.job,p,{'job':self.job},self.resource)['status'],'completed')
            self.write(a/'RELEASE.json',dict(release,run='other'))
            with self.assertRaisesRegex(RuntimeError,'terminal/release'):S.observe(self.job,p,{'job':self.job},self.resource)
            self.write(a/'RELEASE.json',release);actual['Image']='foreign'
            with self.assertRaisesRegex(RuntimeError,'image/command'):S.observe(self.job,p,{'job':self.job},self.resource)

    def test_no_root_authorization(self):
        p=self.root/'ticket.json';self.write(p,dict(schema='r3-formal-train-activation-v1',queue_sha256='q',root_review_accepted=False))
        with self.assertRaisesRegex(RuntimeError,'root activation'):S.authorize(p,S.digest(p.read_bytes()),'q',{'jobs':[self.job]})

    def test_same_buffer_source_and_wrong_hash(self):
        p=self.root/'source.py';p.write_text('VALUE = 7\n');h=S.digest(p.read_bytes())
        self.assertEqual(S.source(p,h).VALUE,7);p.write_text('VALUE = 9\n')
        with self.assertRaisesRegex(RuntimeError,'content changed'):S.source(p,h)

if __name__=='__main__':unittest.main()
