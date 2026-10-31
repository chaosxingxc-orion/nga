import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('readiness', HERE / 'r3_formal_control_readiness.py')
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


class Readiness(unittest.TestCase):
    def test_real_current_state_is_waiting_with_only_evidence_pass(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'readiness.json'
            R.main_args = None
            import sys
            old = sys.argv
            try:
                sys.argv = ['readiness', '--out', str(out)]
                R.main()
            finally:
                sys.argv = old
            doc = json.loads(out.read_text())
            self.assertEqual(doc['status'], 'WAITING')
            self.assertEqual(doc['checks']['qo_evidence']['status'], 'PASS')
            self.assertEqual(doc['checks']['pt_evidence']['status'], 'PASS')
            self.assertNotEqual(doc['checks']['fresh_k0']['status'], 'PASS')
            self.assertNotEqual(doc['checks']['independent_astra_review']['status'], 'PASS')

    def test_review_requires_exact_astra_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'review.json'
            p.write_text(json.dumps({'verdict': 'PASS', 'review_kind': 'independent_astra',
                                     'reviewer_model': 'other', 'approved_plan_sha256': 'a' * 64}))
            import sys
            old = sys.argv
            try:
                sys.argv = ['readiness', '--review', str(p), '--out', str(Path(d) / 'out.json')]
                R.main()
            finally:
                sys.argv = old
            doc = json.loads((Path(d) / 'out.json').read_text())
            self.assertEqual(doc['checks']['independent_astra_review']['status'], 'INVALID')

    def test_bare_k0_pass_and_exit_zero_cannot_be_ready(self):
        """Queue hand-offs and forged terminal markers remain fail-closed."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prep = root / 'PREPARED.json'
            prep.write_text(json.dumps({'status': 'PASS'}))
            evidence = root / 'evidence'; evidence.mkdir()
            (evidence / 'K0_PRECHECKS.json').write_text(json.dumps({
                'schema': 'r3-fresh-k0-prechecks-v1', 'status': 'PASS',
                'scientific_acceptance': False, 'test_read': False}))
            resume = root / 'resume'; resume.mkdir()
            (resume / 'TRAIN_EXIT.json').write_text(json.dumps({
                'exit_code': 0, 'attempt': 1, 'scientific_acceptance': False,
                'test_read': False}))
            self.assertFalse(R.resume_source_ready(resume / 'plan.json'))

            # The K0 helper rejects the incomplete bundle; only its status
            # field must never be enough to establish a PASS.
            helper, _ = R.fresh_precheck_validator(prep)
            with self.assertRaises(Exception):
                helper.validate_bundle(evidence / 'K0_PRECHECKS.json',
                                       R.sha(evidence / 'K0_PRECHECKS.json'),
                                       str(R.MODEL))


if __name__ == '__main__':
    unittest.main()
