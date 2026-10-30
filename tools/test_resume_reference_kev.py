#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('resume', Path(__file__).with_name('resume_reference_kev.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.config = {'physical_chip': 1, 'out': '/root/reference/run', 'image': 'sha256:x'}
        self.owner = {'allocation': [{'chip': 1, 'run': 'reference/run'}]}
        self.container = {'Id': 'frozen-id', 'Image': 'sha256:x', 'State': {'Status': 'exited'},
            'Config': {'Cmd': ['bash', '/root/reference/run/run.sh'], 'Entrypoint': None},
            'HostConfig': {'Devices': [{'PathOnHost': '/dev/davinci1'}]}}
        self.receipt = {'container_id': 'frozen-id', 'image': 'sha256:x',
                        'command': ['bash', '/root/reference/run/run.sh'], 'entrypoint': None}

    def check(self, container=None, owner=None, running=None, marker=None, receipt=None):
        m.check_restart(self.config, self.owner if owner is None else owner,
            self.container if container is None else container, running or [], marker,
            self.receipt if receipt is None else receipt)

    def test_valid_failed_restart(self):
        self.check(marker={'rc': 1})

    def test_wrong_task_extra_chip_entrypoint_and_id(self):
        variants = []
        c = copy.deepcopy(self.container); c['Config']['Cmd'] = ['bash', '/other/run.sh']; variants.append(c)
        c = copy.deepcopy(self.container); c['HostConfig']['Devices'].append({'PathOnHost': '/dev/davinci7'}); variants.append(c)
        c = copy.deepcopy(self.container); c['Config']['Entrypoint'] = ['/other/program']; variants.append(c)
        c = copy.deepcopy(self.container); c['Id'] = 'replacement'; variants.append(c)
        for c in variants:
            with self.assertRaises(ValueError): self.check(container=c)

    def test_completed_busy_unowned_and_live_refused(self):
        with self.assertRaises(ValueError): self.check(marker={'rc': 0})
        with self.assertRaises(ValueError): self.check(owner={'allocation': []})
        with self.assertRaises(ValueError): self.check(running=[self.container])
        c=copy.deepcopy(self.container); c['State']['Status']='running'
        with self.assertRaises(ValueError): self.check(container=c)


if __name__ == '__main__':
    unittest.main()
