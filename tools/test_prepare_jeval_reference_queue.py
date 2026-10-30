import importlib.util
import json
from pathlib import Path
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

if __name__ == '__main__': unittest.main()
