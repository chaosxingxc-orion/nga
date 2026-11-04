"""CPU-only generation and transaction refusal tests; no production release."""
import contextlib
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reconciler', Path(__file__).with_name('reconcile_native_panel_exited_v1.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.h = self.root / 'host_attempts/1'; self.h.mkdir(parents=True)
        (self.root / 'attempts/1').mkdir(parents=True)
        for f in ('start.lock', 'host.lock'): (self.root / f).touch()
        self.d = {'out': str(self.root), 'container': 'c', 'image': 'sha256:i', 'chip': 0, 'run': 'r',
                  'allocation': str(self.root / 'allocation'), 'mounts': [],
                  'modules': {'resource_base': {}, 'host': {'path': '/host.py'}}}
        self.cmd = ['docker', 'run', 'sha256:i', 'python3', '/run.py']
        self.a = {'Id': 'container1', 'Name': '/c-a1', 'Image': 'sha256:i', 'Created': 'created', 'RestartCount': 0,
                  'State': {'Status': 'exited', 'Running': False, 'Restarting': False, 'ExitCode': 1, 'Pid': 0,
                            'StartedAt': 'start', 'FinishedAt': 'end'},
                  'Config': {'Cmd': ['python3', '/run.py']}, 'Mounts': [],
                  'HostConfig': {'AutoRemove': False, 'Privileged': False, 'Devices': [
                      {'PathOnHost': '/dev/' + n, 'PathInContainer': '/dev/' + n, 'CgroupPermissions': 'rwm'}
                      for n in ('davinci_manager', 'devmm_svm', 'hisi_hdc', 'davinci0')]}}
        self.c = {'attempt': 1, 'generation': M.observed_generation(copy.deepcopy(self.a)),
                  'effective_configuration': {k: copy.deepcopy(self.a[k]) for k in ('Config', 'HostConfig', 'Mounts')},
                  'plan': {'path': '/plan', 'sha256': 'plan'}, 'receipts': {'CLAIM.json': {'sha256': 'claim'}}}
        self.receipts = {'CLAIM.json': {'entry': {'chip': 0, 'run': 'r', 'claimed_utc': 'generation1'}},
                         'SERVICE.json': {'pid': 123456789}}
        self.ledger = {'allocation': [self.receipts['CLAIM.json']['entry']], 'free': []}
        self.released = []
        self.R = types.SimpleNamespace(docker_inspect=lambda _: copy.deepcopy(self.a),
                live_chip_conflict=lambda *_: False, locked=lambda _: contextlib.nullcontext(),
                load=self.read, validate_doc=lambda _: None, release=self.release,
                utc=lambda: 'now', write_atomic=lambda p, v: Path(p).write_text(json.dumps(v)))

    def read(self, p):
        return self.ledger if str(p) == self.d['allocation'] else json.loads(Path(p).read_text())

    def release(self, args):
        # Simulate original adapter's repeated checks including after intent creation.
        self.R.docker_inspect(args.container)
        intent = Path(args.proof + '.intent'); intent.write_text('{}')
        self.R.docker_inspect(args.container)
        self.released.append(args)
        Path(args.proof).write_text(json.dumps({'claim_sha256': 'claim', 'container_id': 'container1', 'exit_code': 1}))
        intent.unlink()

    def run_fixture(self, execute=False, reviewer=True):
        with patch.object(M, 'load_configuration', return_value=(self.c, self.d, self.h, self.receipts, self.cmd)), \
             patch.object(M, 'module', return_value=self.R), \
             patch.object(M, 'absent_supervisor'), \
             patch.object(M, 'pinned', return_value=json.dumps({'verdict': 'PASS', 'approved_config_sha256': 'pin',
                       'release_authorized': True, 'scientific_acceptance': False}).encode()):
            return M.run('/config', 'pin', execute, {'path': '/review', 'sha256': 'review'} if reviewer else None)

    def test_verify_has_no_release_or_terminal(self):
        self.assertEqual(self.run_fixture()['status'], 'VERIFIED_READ_ONLY')
        self.assertFalse(self.released); self.assertFalse((self.h / 'EXIT.json').exists())

    def test_failed_release_retains_missing_runtime_provenance(self):
        self.assertEqual(self.run_fixture(True)['status'], 'FAILED_GENERATION_RELEASED')
        t = self.read(self.h / 'EXIT.json')
        self.assertEqual(t['source'], 'retained-container-exit')
        self.assertFalse(t['runner_terminal_matches']); self.assertFalse(t['scientific_acceptance'])
        self.assertFalse((self.root / 'attempts/1/EXIT.json').exists())

    def test_no_review_no_mutation(self):
        with self.assertRaisesRegex(ValueError, 'independent execution review'): self.run_fixture(True, False)
        self.assertFalse(self.released)

    def test_partial_terminal_refused(self):
        for rel in ('host_attempts/1/EXIT.json', 'host_attempts/1/RELEASE.json', 'host_attempts/1/RELEASE.json.intent', 'attempts/1/EXIT.json'):
            p = self.root / rel; p.write_text('{}')
            with self.subTest(path=rel), self.assertRaisesRegex(ValueError, 'partial/existing'): self.run_fixture(True)
            p.unlink()
        self.assertFalse(self.released)

    def test_foreign_owner_or_claim_generation_refused(self):
        for field, value in [('run', 'foreign'), ('claimed_utc', 'generation2')]:
            self.ledger['allocation'] = [dict(self.receipts['CLAIM.json']['entry'], **{field: value})]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'claim generation'): self.run_fixture(True)
        self.assertFalse(self.released)

    def test_live_conflict_refused(self):
        self.R.live_chip_conflict = lambda *_: True
        with self.assertRaisesRegex(ValueError, 'live chip'): self.run_fixture(True)
        self.assertFalse(self.released)

    def test_generation_mutations_refused(self):
        cases = [('Id', 'other'), ('Image', 'other'), ('RestartCount', 1), ('Name', '/other'), ('Created', 'later')]
        for key, value in cases:
            a = copy.deepcopy(self.a); a[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): M.validate_container(self.c, self.d, a, self.cmd)
        for key, value in [('Status', 'running'), ('Running', True), ('ExitCode', 0), ('StartedAt', 'later'), ('FinishedAt', 'later')]:
            a = copy.deepcopy(self.a); a['State'][key] = value
            with self.subTest(state=key), self.assertRaises(ValueError): M.validate_container(self.c, self.d, a, self.cmd)

    def test_command_device_configuration_mutations_refused(self):
        for kind in ('command', 'device', 'autoremove', 'mount', 'privileged'):
            a = copy.deepcopy(self.a)
            if kind == 'command': a['Config']['Cmd'].append('--foreign')
            if kind == 'device': a['HostConfig']['Devices'][-1]['PathOnHost'] = '/dev/davinci1'
            if kind == 'autoremove': a['HostConfig']['AutoRemove'] = True
            if kind == 'privileged': a['HostConfig']['Privileged'] = True
            if kind == 'mount': a['Mounts'].append({'Source': '/foreign', 'Destination': '/foreign', 'RW': True})
            with self.subTest(kind=kind), self.assertRaises(ValueError): M.validate_container(self.c, self.d, a, self.cmd)

    def test_live_supervisor_refused(self):
        import os
        with self.assertRaisesRegex(ValueError, 'supervisor PID still present'):
            M.absent_supervisor({'pid': os.getpid()}, '/host.py', '/plan')

    def test_changed_source_pin_refused(self):
        p = self.root / 'source.py'; p.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'reference changed'): M.module({'path': str(p), 'sha256': 'old'})

    def test_container_restart_during_release_refused(self):
        def release(args):
            self.a['State']['StartedAt'] = 'new-start'
            self.R.docker_inspect(args.container)
            self.fail('must not reach resource mutation')
        self.R.release = release
        with self.assertRaisesRegex(ValueError, 'generation changed'): self.run_fixture(True)
        self.assertFalse((self.h / 'EXIT.json').exists())


if __name__ == '__main__': unittest.main()
