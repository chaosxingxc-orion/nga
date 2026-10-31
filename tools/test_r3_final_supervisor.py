import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('supervisor',Path(__file__).with_name('r3_final_supervisor.py'))
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class Observation(unittest.TestCase):
    def test_unknown_and_missing_retry_same_identity_without_launch(self):
        with tempfile.TemporaryDirectory() as td:
            value={'Id':'same'};sleep=Mock()
            with patch.object(S.R,'docker_inspect',side_effect=[RuntimeError('timeout'),None,value]) as inspect, \
                 patch.object(S.K,'verify_observation',return_value=value) as verify, \
                 patch.object(S.subprocess,'run') as launch:
                self.assertEqual(S.observe({'name':'retained'},'same',Path(td)/'digest.json',sleep),value)
            self.assertEqual(inspect.call_count,3);self.assertEqual(sleep.call_count,2)
            verify.assert_called_once_with({'name':'retained'},value,'same');launch.assert_not_called()

    def test_definite_identity_mismatch_is_not_retried(self):
        with tempfile.TemporaryDirectory() as td:
            sleep=Mock()
            with patch.object(S.R,'docker_inspect',return_value={'Id':'other'}), \
                 patch.object(S.K,'verify_observation',side_effect=ValueError('generation changed')):
                with self.assertRaisesRegex(ValueError,'generation'):
                    S.observe({'name':'retained'},'same',Path(td)/'digest.json',sleep)
            sleep.assert_not_called()

    def test_claim_release_use_same_plan_identity(self):
        with tempfile.TemporaryDirectory() as td:
            p={'chip':1,'arm':'K1'};spec={'name':'retained'};root=Path(td)
            claim=S.resource_args(p,'a'*64,spec,root,'claim')
            release=S.resource_args(p,'a'*64,spec,root,'release')
            self.assertEqual(claim.run,release.run);self.assertEqual(claim.chip,release.chip)
            self.assertEqual(claim.proof,release.claim)


if __name__=='__main__':unittest.main()
