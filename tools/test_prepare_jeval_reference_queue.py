import importlib.util
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).with_name('prepare_jeval_reference_queue.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        self.path = self.out / 'plan.json'; self.path.write_text('{}')
        self.plan = {'container': 'controller', 'files': {}, 'preparation_files': {'container_spec': str(self.out / 'spec.json'), 'wrapper': str(self.out / 'run.sh')}}
        self.spec = {'Image': 'image', 'Cmd': ['run.sh'], 'Entrypoint': ['bash']}
        self.data = {str(self.path): self.plan, str(self.out / 'PARENT_REVIEW.json'): {'approved_plan_sha256': 'hash'}, str(self.out / 'spec.json'): self.spec}
        self.info = {'Id': 'cid', 'State': {'Status': 'created', 'ExitCode': 0, 'FinishedAt': 'timestamp'}}
        self.calls = []
        def require(v, message):
            if not v: raise ValueError(message)
        def api(method, path, value=None):
            self.calls.append((method, path))
            return {'Name': 'k8s-node1'} if path == '/info' else None
        def atomic(path, value):
            self.data[str(path)] = value; Path(path).write_text(json.dumps(value))
        self.q = types.SimpleNamespace(IMAGE='image', require=require, load=lambda p: self.data[str(p)], sha=lambda p:'hash', frozen=lambda f:None,
                                     docker=api, inspect=lambda n:self.info, binding=lambda *a:None, atomic=atomic)
        self.patch = patch.object(m, 'module', return_value=self.q); self.patch.start()
    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()
    def receipt(self):
        self.q.atomic(self.out / 'LAUNCH_RECEIPT.json', {'container_id': 'cid', 'image':'image', 'command':['run.sh'], 'entrypoint':['bash'], 'plan_sha256':'hash', 'wrapper_sha256':'hash'})
    def test_existing_terminal_never_starts(self):
        (self.out / 'QUEUE_COMPLETE.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Terminal evidence'): m.launch(self.path, True)
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))
    def test_unknown_created_container_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown container'): m.launch(self.path)
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))
    def test_matching_created_seam_recovers_receipt(self):
        self.q.atomic(self.out / 'LAUNCH_INTENT.json', {'plan_sha256':'hash', 'spec_sha256':'hash'})
        m.launch(self.path)
        self.assertTrue((self.out / 'LAUNCH_RECEIPT.json').exists())
        self.assertIn(('POST', '/containers/cid/start'), self.calls)
    def test_running_is_noop(self):
        self.receipt(); self.info['State']['Status']='running'
        m.launch(self.path, True)
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))
    def test_interrupted_resume_requires_bound_review(self):
        self.receipt(); self.info['State'].update(Status='exited', ExitCode=137)
        self.q.atomic(self.out / 'RESUME_REVIEW.json', {'approved_plan_sha256':'hash','container_id':'cid','finished_at':'wrong-generation'})
        with self.assertRaisesRegex(ValueError, 'resume review'): m.launch(self.path, True)
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))
    def test_shell_wrapper_preserves_spaces_and_literal_chars(self):
        s=m.shell_wrapper(['python3','-P','/tmp/a b.py','--arg','$(literal)'], self.out)
        self.assertIn("'/tmp/a b.py'",s); self.assertIn("'$(literal)'",s)

    def interrupted(self):
        self.receipt(); self.info['State'].update(Status='exited', ExitCode=137)
        (self.out / 'EXIT').write_text('rc=137 utc=2026-10-30T00:00:00Z\n')
        self.q.atomic(self.out / 'RESUME_REVIEW.json', {'approved_plan_sha256':'hash', 'container_id':'cid', 'finished_at':'timestamp', 'exit_sha256':'hash'})

    def test_shell_exit137_archived_and_same_container_resumed(self):
        self.interrupted()
        m.launch(self.path, True)
        self.assertFalse((self.out / 'EXIT').exists())
        self.assertEqual(len(list((self.out / 'resume_history').glob('*/EXIT'))), 1)
        self.assertIn(('POST', '/containers/cid/start'), self.calls)
        # Restart after archive-before-start interruption remains idempotent.
        self.calls.clear(); m.launch(self.path, True)
        self.assertIn(('POST', '/containers/cid/start'), self.calls)

    def test_exit_review_mismatch_preserves_evidence(self):
        self.interrupted()
        self.data[str(self.out / 'RESUME_REVIEW.json')]['exit_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'EXIT review'): m.launch(self.path, True)

        self.assertTrue((self.out / 'EXIT').exists())
        self.assertFalse(any(method == 'POST' for method, _ in self.calls))

    def test_business_failure_and_success_never_archived(self):
        for terminal in ['FAILURE.json', 'QUEUE_COMPLETE.json']:
            self.interrupted(); (self.out / terminal).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Terminal evidence'): m.launch(self.path, True)
            self.assertTrue((self.out / 'EXIT').exists())
            (self.out / terminal).unlink()
        (self.out / 'EXIT').write_text('rc=0 utc=now\n')
        with self.assertRaisesRegex(ValueError, 'EXIT review'): m.launch(self.path, True)


class Handover(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.q = m.module(Path(__file__).with_name('jeval_reference_queue.py'))
        q = self.q
        old, run = self.root / 'old', self.root / 'model'
        old.mkdir(); run.mkdir()
        (old / 'run.sh').write_text('old controller')
        (run / 'run.sh').write_text('unchanged inference')
        self.config = run / 'config.json'
        q.atomic(self.config, dict(key='nimble', out=str(run), container='model'))
        base = dict(Image=q.IMAGE, Entrypoint=['bash'], Env=[], Labels={},
                    HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs'], Devices=[], NetworkMode='none', ShmSize=67108864))
        controller = dict(copy.deepcopy(base), Cmd=[str(old / 'run.sh')])
        native = dict(copy.deepcopy(base), Cmd=['bash', str(run / 'run.sh')])
        native['HostConfig']['Devices'] = [dict(PathOnHost='/dev/davinci1', PathInContainer='/dev/davinci1', CgroupPermissions='rwm')]
        q.atomic(old / 'SPEC.json', controller); q.atomic(run / 'NPU_SPEC.json', native)
        entry = dict(key='nimble', config=str(self.config), config_sha256=q.sha(self.config))
        prior = dict(out=str(old), container='old', entries=[entry], preparation_files=dict(container_spec=str(old / 'SPEC.json'), wrapper=str(old / 'run.sh')),
                     files={str(p): q.sha(p) for p in [old / 'SPEC.json', old / 'run.sh']})
        self.path = old / 'plan.json'; q.atomic(self.path, prior)
        native['Labels'] = {'nga.jeval.queue': q.sha(self.path), 'nga.jeval.key':'nimble', 'nga.jeval.role':'inference'}
        def obj(s, name, status):
            return dict(Id=name + '-id', Image=s['Image'], Config={k: copy.deepcopy(s.get(k)) for k in ['Cmd','Entrypoint','Env','Labels']},
                        HostConfig=copy.deepcopy(s['HostConfig']), State=dict(Status=status, ExitCode=137, FinishedAt='generation1'))
        self.containers = dict(old=obj(controller, 'old', 'exited'), model=obj(native, 'model', 'running'))
        finish = Path(str(run) + '_finish'); finish.mkdir(); (finish / 'run.sh').write_text('unchanged finisher')
        finish_spec = dict(copy.deepcopy(base), Cmd=[str(finish / 'run.sh')])
        finish_spec['HostConfig']['Binds'].append('/var/run/docker.sock:/var/run/docker.sock')
        finish_spec['Labels'] = dict(native['Labels'], **{'nga.jeval.role':'finish'})
        self.containers['model-finish'] = obj(finish_spec, 'model-finish', 'running')
        for out, name, s in [(old, 'old', controller), (run, 'model', native), (finish, 'model-finish', finish_spec)]:
            receipt = dict(container_id=name+'-id', image=q.IMAGE, command=s['Cmd'], entrypoint=s['Entrypoint'], wrapper_sha256=q.sha(out/'run.sh'))
            receipt.update({'plan_sha256':q.sha(self.path)} if name == 'old' else {'config_sha256':q.sha(self.config)})
            q.atomic(out/'LAUNCH_RECEIPT.json', receipt)
        self.patcher = patch.object(q, 'inspect', lambda name: self.containers.get(name)); self.patcher.start()
        self.env_patch = patch.object(q, 'image_environment', return_value=[]); self.env_patch.start()
        self.entry = entry

    def tearDown(self):
        self.patcher.stop(); self.env_patch.stop(); self.tmp.cleanup()

    def snapshot(self):
        return m.handover_snapshot(self.q, self.path, self.config)

    def test_stopped_controller_adopts_original_model_without_mutation(self):
        q = self.q
        handover, files = self.snapshot()
        z = q.Queue.__new__(q.Queue)
        z.hash = 'new-plan'
        z.plan = dict(handover=handover, entries=[self.entry], files={str(p):q.sha(p) for p in files})
        with patch.object(q, 'docker', side_effect=AssertionError('no Docker mutation permitted')):
            z.check_handover()
            self.assertEqual(z.spec(q.load(self.config), 'inference')['Labels']['nga.jeval.queue'], q.sha(self.path))
        self.assertEqual(handover['adopted']['nimble']['inference']['container_id'], 'model-id')
        self.assertEqual(handover['adopted']['nimble']['finish']['container_id'], 'model-finish-id')
        self.containers['model']['Id'] = 'replaced'
        with self.assertRaisesRegex(ValueError, 'container changed'): z.check_handover()

    def test_running_prior_and_foreign_model_fail_closed(self):
        self.containers['old']['State']['Status'] = 'running'
        with self.assertRaisesRegex(ValueError, 'stopped'): self.snapshot()
        self.containers['old']['State']['Status'] = 'exited'
        self.containers['model']['Config']['Labels']['nga.jeval.queue'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'labels differ'): self.snapshot()

    def test_prior_receipt_or_frozen_spec_tampering_fails(self):
        p = self.path.parent / 'LAUNCH_RECEIPT.json'
        r = self.q.load(p); r['plan_sha256'] = 'other'; self.q.atomic(p, r)
        with self.assertRaisesRegex(ValueError, 'receipt binding'): self.snapshot()
        (self.path.parent / 'SPEC.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Frozen file changed'): self.snapshot()

    def test_second_handover_preserves_original_labels_and_failed_prior_terminal(self):
        q = self.q
        original_hash = q.sha(self.path)
        first, files = self.snapshot()
        middle = self.root / 'middle'; middle.mkdir()
        (middle / 'run.sh').write_text('middle controller')
        controller_spec = q.load(self.path.parent / 'SPEC.json')
        controller_spec['Cmd'] = [str(middle / 'run.sh')]
        q.atomic(middle / 'SPEC.json', controller_spec)
        files += [middle / 'run.sh', middle / 'SPEC.json']
        middle_plan = dict(out=str(middle), container='middle', entries=[self.entry], handover=first,
                           preparation_files=dict(container_spec=str(middle / 'SPEC.json'), wrapper=str(middle / 'run.sh')),
                           files={str(p):q.sha(p) for p in files})
        mp = middle / 'plan.json'; q.atomic(mp, middle_plan)
        self.containers['middle'] = copy.deepcopy(self.containers['old'])
        self.containers['middle'].update(Id='middle-id')
        self.containers['middle']['Config']['Cmd'] = controller_spec['Cmd']
        self.containers['middle']['State']['FinishedAt'] = 'generation2'
        receipt = dict(container_id='middle-id', image=q.IMAGE, command=controller_spec['Cmd'], entrypoint=controller_spec['Entrypoint'],
                       wrapper_sha256=q.sha(middle/'run.sh'), plan_sha256=q.sha(mp))
        q.atomic(middle/'LAUNCH_RECEIPT.json', receipt)
        q.atomic(middle/'FAILURE.json', {'error':'retained genuine failure'})
        q.atomic(middle/'QUEUE_COMPLETE.json', {'rc':1})
        failure_hashes = [q.sha(middle/n) for n in ['FAILURE.json','QUEUE_COMPLETE.json']]
        second, second_files = m.handover_snapshot(q, mp, self.config)
        self.assertEqual({r['label_hash'] for r in second['adopted']['nimble'].values()}, {original_hash})
        z = q.Queue.__new__(q.Queue); z.hash = 'third-queue'
        z.plan = dict(handover=second, entries=[self.entry], files={str(p):q.sha(p) for p in second_files})
        z.check_handover()
        self.assertEqual(z.spec(q.load(self.config), 'inference')['Labels']['nga.jeval.queue'], original_hash)
        self.assertEqual([q.sha(middle/n) for n in ['FAILURE.json','QUEUE_COMPLETE.json']], failure_hashes)
        self.containers['old']['State']['Status'] = 'running'
        with self.assertRaisesRegex(ValueError, 'Ancestor controller resumed'): z.check_handover()
        self.containers['old']['State']['Status'] = 'exited'
        self.containers['old']['State']['FinishedAt'] = 'resumed-then-stopped'
        with self.assertRaisesRegex(ValueError, 'Ancestor controller resumed'): z.check_handover()
        self.containers['old']['State']['FinishedAt'] = 'generation1'
        self.containers['model']['Config']['Labels']['nga.jeval.queue'] = 'forged'
        with self.assertRaisesRegex(ValueError, 'intent label'): z.check_handover()
        self.containers['model']['Config']['Labels']['nga.jeval.queue'] = original_hash
        middle_plan['handover']['adopted']['nimble']['inference']['label_hash'] = 'forged-ancestor'
        q.atomic(mp, middle_plan)
        receipt['plan_sha256'] = q.sha(mp); q.atomic(middle/'LAUNCH_RECEIPT.json',receipt)
        with self.assertRaisesRegex(ValueError, 'Ancestor label provenance'):
            m.handover_snapshot(q, mp, self.config)

def real_exit137_fixture(root):
    """Retained CPU Docker: Python SIGKILL, shell EXIT137, reviewed same-ID resume."""
    root.mkdir()
    source = Path(__file__).parent
    for filename in ['jeval_reference_queue.py', 'prepare_jeval_reference_queue.py']:
        shutil.copy2(source / filename, root / filename)
    q = m.module(root / 'jeval_reference_queue.py')
    q.require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 only')
    child = root / 'child.py'
    child.write_text('import os, signal\nfrom pathlib import Path\np=Path(' + repr(str(root / 'ONCE')) + ')\n'
                     'if not p.exists():\n    p.write_text("interrupted")\n    os.kill(os.getpid(), signal.SIGKILL)\n'
                     'print("fixture resumed same retained container", flush=True)\n')
    wrapper = root / 'run.sh'
    wrapper.write_text(m.shell_wrapper(['python3', '-P', str(child)], root))
    name = 'nga-' + root.name
    q.require(q.inspect(name) is None, 'Fixture container already exists')
    spec = dict(Image=q.IMAGE, Cmd=[str(wrapper)], Entrypoint=['bash'], Env=q.image_environment(),
                Labels={'nga.jeval.queue.name': name}, HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs'], Devices=[], NetworkMode='none', ShmSize=67108864))
    q.atomic(root / 'CONTAINER_SPEC.json', spec)
    plan = dict(container=name, files={str(p): q.sha(p) for p in root.iterdir() if p.is_file()},
                preparation_files=dict(wrapper=str(wrapper), container_spec=str(root / 'CONTAINER_SPEC.json')))
    path = root / 'plan.json'
    q.atomic(path, plan)
    q.atomic(root / 'PARENT_REVIEW.json', {'approved_plan_sha256': q.sha(path), 'scope': 'CPU fixture only'})
    (root / 'RELAUNCH.txt').write_text('python3 -I ' + str(root / 'prepare_jeval_reference_queue.py') + ' --resume ' + str(path) + '\n')
    def exited():
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            d = q.inspect(name)
            if d['State']['Status'] == 'exited': return d
            time.sleep(0.2)
        raise ValueError('Fixture deadline exceeded')
    m.launch(path)
    first = exited()
    q.require(first['State']['ExitCode'] == 137 and (root / 'EXIT').read_text().startswith('rc=137 '), 'Python SIGKILL shell marker missing')
    exit_hash = q.sha(root / 'EXIT')
    q.atomic(root / 'heartbeat.json', dict(utc=q.utc(), progress=1, total=2, stage='actual_shell_exit137'))
    denied = False
    try:
        m.launch(path, True)
    except FileNotFoundError:
        denied = True
    q.require(denied and q.sha(root / 'EXIT') == exit_hash, 'Unreviewed resume did not fail closed')
    q.atomic(root / 'RESUME_REVIEW.json', dict(approved_plan_sha256=q.sha(path), container_id=first['Id'], finished_at=first['State']['FinishedAt'], exit_sha256=exit_hash, scope='CPU fixture only'))
    m.launch(path, True)
    last = exited()
    archives = list((root / 'resume_history').glob('*/EXIT'))
    q.require(last['Id'] == first['Id'] and last['State']['ExitCode'] == 0 and (root / 'EXIT').read_text().startswith('rc=0 '), 'Reviewed retained resume failed')
    q.require(len(archives) == 1 and q.sha(archives[0]) == exit_hash, 'Original EXIT137 not preserved')
    q.atomic(root / 'heartbeat.json', dict(utc=q.utc(), progress=2, total=2, stage='same_container_resumed'))
    result = dict(rc=0, utc=q.utc(), container_id=last['Id'], image=q.IMAGE, initial_exit=137, resumed_exit=0,
                  exit137_archive=str(archives[0]), exit137_sha256=exit_hash, unreviewed_resume_rejected=True,
                  scope='Actual CPU-only retained Docker Python SIGKILL and shell EXIT137; no NPU or allocation changes')
    q.atomic(root / 'FIXTURE_COMPLETE.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--docker-exit137-fixture':
        real_exit137_fixture(Path(sys.argv[2]))
    else:
        unittest.main()
