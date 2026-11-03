import copy
import unittest

from tools.r3_member_runtime_capture import validate_container


class RetainedCaptureTests(unittest.TestCase):
    def fixture(self):
        return [{'Id': 'cid', 'Name': '/run-a1',
                 'State': {'Status': 'exited', 'Running': False, 'ExitCode': 0,
                           'OOMKilled': False, 'Error': ''},
                 'HostConfig': {'AutoRemove': False}}]

    def check(self, actual):
        validate_container(actual, {'container': 'run'}, {'id': 'cid'})

    def test_exact_retained_success(self):
        self.check(self.fixture())

    def test_wrong_generation_and_multiple_results(self):
        for field, value in [('Id', 'other'), ('Name', '/other-a1')]:
            actual = self.fixture()
            actual[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(actual)
        with self.assertRaises(ValueError):
            self.check(self.fixture() * 2)

    def test_live_failed_and_boolean_exit_are_rejected(self):
        for field, value in [('Status', 'running'), ('Running', True),
                             ('ExitCode', 1), ('ExitCode', False),
                             ('OOMKilled', True), ('Error', 'failed')]:
            actual = copy.deepcopy(self.fixture())
            actual[0]['State'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.check(actual)

    def test_auto_remove_rejected(self):
        actual = self.fixture()
        actual[0]['HostConfig']['AutoRemove'] = True
        with self.assertRaises(ValueError):
            self.check(actual)


if __name__ == '__main__':
    unittest.main()
