"""Docker order changes are harmless; resource identity changes are not."""
import copy
import importlib.util
from pathlib import Path
import unittest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = load('prepare_jeval_reference_inference')
FINISH = load('jeval_reference_finish')


class ResourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.host = {'Binds': ['/mnt/cephfs:/mnt/cephfs', '/driver:/driver:ro'],
                     'Devices': [dict(PathOnHost='/dev/davinci5', PathInContainer='/dev/davinci5', CgroupPermissions='rwm'),
                                 dict(PathOnHost='/dev/davinci_manager', PathInContainer='/dev/davinci_manager', CgroupPermissions='rwm')]}

    def assert_mapping_changed(self, changed):
        for module in (PREPARE, FINISH):
            with self.subTest(module=module.__name__):
                self.assertNotEqual(module.resource_mapping(self.host), module.resource_mapping(changed))

    def test_array_reordering_accepted_by_prepare_and_finisher(self):
        changed = copy.deepcopy(self.host)
        changed['Binds'].reverse()
        changed['Devices'].reverse()
        for module in (PREPARE, FINISH):
            self.assertEqual(module.resource_mapping(self.host), module.resource_mapping(changed))
        spec = dict(Image='sha256:fixed', Cmd=['bash', '/run.sh'], Entrypoint=['/entrypoint'], HostConfig=self.host)
        receipt = dict(container_id='id', image=spec['Image'], command=spec['Cmd'], entrypoint=spec['Entrypoint'])
        actual = dict(Id='id', Image=spec['Image'], Config=dict(Cmd=spec['Cmd'], Entrypoint=spec['Entrypoint']), HostConfig=changed)
        PREPARE.binding(actual, dict(image=spec['Image'], physical_chip=5), spec, receipt)

    def test_mount_path_or_options_changed_rejected(self):
        for mount in ['/other:/mnt/cephfs', '/driver:/driver:rw']:
            changed = copy.deepcopy(self.host)
            changed['Binds'][1] = mount
            self.assert_mapping_changed(changed)

    def test_each_device_component_changed_rejected(self):
        for key, value in [('PathOnHost', '/dev/davinci4'), ('PathInContainer', '/dev/davinci0'), ('CgroupPermissions', 'r')]:
            changed = copy.deepcopy(self.host)
            changed['Devices'][0][key] = value
            self.assert_mapping_changed(changed)

    def test_missing_or_duplicate_mapping_rejected(self):
        for key in ['Binds', 'Devices']:
            for duplicate in [False, True]:
                changed = copy.deepcopy(self.host)
                if duplicate:
                    changed[key].append(copy.deepcopy(changed[key][0]))
                else:
                    changed[key].pop()
                self.assert_mapping_changed(changed)


if __name__ == '__main__':
    unittest.main()
