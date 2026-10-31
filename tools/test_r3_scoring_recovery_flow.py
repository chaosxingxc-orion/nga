"""Recovery supervisor/phase flow with real ledger and simulated Docker.

Plan validation and Docker execution are substitutes; phase_run, outcome,
container contract verification, durable evidence and claim/release are real.
No model, dataset, NPU or live resource allocation is accessed.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class SimulatedSupervisorCrash(BaseException):
    pass


class RecoveryFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'output'
        self.out.mkdir()
        self.alloc = self.root / 'allocation.json'
        self.alloc.write_text(json.dumps({'allocation': [], 'free': [{'chip': i} for i in range(8)]}))
        self.L = module('recovery_flow_launcher', HERE / 'r3_scoring_recovery_launcher.py')
        self.R = module('recovery_flow_resource', HERE / 'r3_resource_adapter.py')
        self.K = module('recovery_flow_container', HERE / 'r3_final_container.py')
        self.pin = 'b' * 64
        self.p = {'out': str(self.out), 'run': 'r3_runs/synthetic-recovery',
                  'allocation': str(self.alloc), 'chip': 3,
                  'container': 'nga-r3-eng-recovery-synthetic', 'image': self.L.IMAGE,
                  'launcher': str(self.out / 'execution-tools/r3_scoring_recovery_launcher.py'),
                  'resource_adapter': str(self.out / 'execution-tools/r3_resource_adapter.py'),
                  'probe': str(self.root / 'probe.py'), 'probe_plan': str(self.out / 'probe.json'),
                  'probe_plan_sha256': 'a' * 64}
        self.q = {'out': str(self.out / 'results'), 'model': str(self.root / 'model'),
                  'adapter': str(self.root / 'adapter'), 'closure': {'root': str(self.root / 'closure')},
                  'base_inventory': {'path': str(self.root / 'base-inventory.json')},
                  'adapter_inventory': {'path': str(self.root / 'adapter-inventory.json')},
                  'sources': {s: {'path': str(self.root / 'data' / s / 'dev.jsonl')}
                              for s in ('decision-v7', 'transfer-v4')}}
        self.path = self.out / 'execution.json'
        self.path.write_text(json.dumps(self.p))
        self.containers = {}
        self.launches = []
        self.exits = {'reference': 0, 'interrupt': 137, 'resume': 0}
        self.omit_interrupt_proof = False
        self.directory = self.out / 'attempts/1'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        substitutions = [
            (self.L, 'verify', lambda *a: (self.p, self.q)),
            (self.L, 'module', lambda p, n: self.R if Path(p).name == 'r3_resource_adapter.py' else self.K),
            (self.L.socket, 'gethostname', lambda: 'k8s-node1'),
            (self.R, 'docker_inspect', self.inspect),
            (self.R, 'live_chip_conflict', self.conflict),
            (self.L.subprocess, 'check_output', lambda *a, **kw: self.L.IMAGE + '\n'),
            (self.L.subprocess, 'run', self.docker),
        ]
        for obj, name, value in substitutions:
            self.stack.enter_context(patch.object(obj, name, value))
        self.claim = self.stack.enter_context(patch.object(self.R, 'claim', wraps=self.R.claim))
        self.release = self.stack.enter_context(patch.object(self.R, 'release', wraps=self.R.release))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def inspect(self, name):
        return copy.deepcopy(self.containers.get(name))

    def conflict(self, chip, own_name):
        return any(name != own_name and d['State']['Status'] not in ('exited', 'dead')
                   for name, d in self.containers.items())

    def docker(self, command, **kwargs):
        if command[:2] == ['docker', 'logs']:
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(command[:3], ['docker', 'run', '-d'])
        phase = command[command.index('--phase') + 1]
        spec = self.L.contract(self.p, self.q, self.path, self.pin, phase, 1)
        self.assertEqual(command, self.K.command(spec))
        self.assertNotIn(phase, self.launches, 'phase launched twice')
        # Every launch retains the same actual ledger owner; no interim release.
        ledger = self.R.load(self.alloc)
        self.assertEqual([(x['chip'], x['run']) for x in ledger['allocation']], [(3, self.p['run'])])
        self.assertFalse((self.directory / 'RELEASE.json').exists())
        self.launches.append(phase)
        actual = {'Id': 'actual-' + phase, 'Name': '/' + spec['name'], 'Image': self.L.IMAGE,
                  'HostConfig': {'AutoRemove': False, 'NetworkMode': 'none',
                                 'Devices': [{'PathOnHost': x} for x in spec['devices']]},
                  'Config': {'Entrypoint': ['python3'], 'Cmd': spec['cmd'],
                             'Env': [k + '=' + v for k, v in spec['environment'].items()]},
                  'Mounts': [{'Type': 'bind', 'Source': p, 'Destination': p, 'RW': rw}
                             for p, rw in {**spec['mounts'], '/usr/local/Ascend/driver': False}.items()],
                  'State': {'Status': 'exited', 'ExitCode': self.exits[phase], 'FinishedAt': 'synthetic'}}
        self.containers[spec['name']] = actual
        work = Path(self.q['out']) / ('reference' if phase == 'reference' else 'interrupted')
        work.mkdir(parents=True, exist_ok=True)
        if phase == 'interrupt':
            if not self.omit_interrupt_proof:
                self.L.atomic(work / 'INTERRUPT_READY.json', {
                    'plan_sha256': self.p['probe_plan_sha256'], 'committed': 2, 'keys': ['a', 'b']})
        else:
            result = {'plan_sha256': self.p['probe_plan_sha256'], 'phase': phase, 'rows': 8,
                      'newly_scored': 8 if phase == 'reference' else 6,
                      'test_read': False, 'scientific_acceptance': False}
            if phase == 'resume':
                result.update(status='ENGINEERING_RECOVERY_PASS', committed_reused=2, max_abs_nats=0.)
            self.L.atomic(work / 'DONE.json', result)
        return subprocess.CompletedProcess(command, 0, stdout=actual['Id'])

    def run_supervisor(self):
        return self.L.supervise(self.path, self.pin, 1)

    def assert_released(self, last_phase, expected_exit):
        self.assertEqual(self.R.load(self.alloc)['allocation'], [])
        proof = self.R.load(self.directory / 'RELEASE.json')
        self.assertEqual(proof['container_id'], 'actual-' + last_phase)
        self.assertEqual(proof['exit_code'], expected_exit)
        self.assertFalse(proof['scientific_acceptance'])

    def test_three_phases_hold_one_claim_until_final_actual_exit(self):
        result = self.run_supervisor()
        self.assertEqual(self.launches, ['reference', 'interrupt', 'resume'])
        self.assertEqual([p['container_exit_code'] for p in result['phases']], [0, 137, 0])
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['engineering_recovery_complete'])
        self.claim.assert_called_once()
        self.release.assert_called_once()
        self.assert_released('resume', 0)
        self.assertEqual(self.run_supervisor(), result)
        self.assertEqual(len(self.launches), 3)
        self.claim.assert_called_once()
        self.release.assert_called_once()

    def test_unexpected_interrupt_exit_stops_chain_and_releases(self):
        self.exits['interrupt'] = 1
        result = self.run_supervisor()
        self.assertEqual(self.launches, ['reference', 'interrupt'])
        self.assertEqual(result['exit_code'], 1)
        self.assertFalse(result['engineering_recovery_complete'])
        self.assert_released('interrupt', 1)
        self.assertEqual(self.run_supervisor(), result)
        self.assertEqual(len(self.launches), 2)

    def test_exit_137_without_interruption_proof_is_failure(self):
        self.omit_interrupt_proof = True
        result = self.run_supervisor()
        self.assertEqual(self.launches, ['reference', 'interrupt'])
        self.assertFalse(result['engineering_recovery_complete'])
        self.assertEqual(result['exit_code'], 137)
        self.assert_released('interrupt', 137)

    def test_crash_after_interrupt_resumes_observation_without_duplicate_launch(self):
        original = self.L.atomic
        crash_once = [True]

        def crashing_atomic(path, value):
            original(path, value)
            if Path(path) == self.directory / 'interrupt/RESULT.json' and crash_once[0]:
                crash_once[0] = False
                raise SimulatedSupervisorCrash('after interrupt durable outcome')

        with patch.object(self.L, 'atomic', crashing_atomic):
            with self.assertRaises(SimulatedSupervisorCrash):
                self.run_supervisor()
            self.assertEqual(self.launches, ['reference', 'interrupt'])
            self.assertEqual(len(self.R.load(self.alloc)['allocation']), 1)
            self.release.assert_not_called()
            result = self.run_supervisor()
        self.assertTrue(result['engineering_recovery_complete'])
        self.assertEqual(self.launches, ['reference', 'interrupt', 'resume'])
        self.claim.assert_called_once()
        self.release.assert_called_once()
        self.assert_released('resume', 0)


if __name__ == '__main__':
    unittest.main()
