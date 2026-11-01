"""Synthetic local evidence exercises production audit functions, never live datasets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

R = module('r3_formal_control_readiness')
F = module('test_r3_resume_reconstruction_evidence')

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))

class Readiness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def target(self, arm='K1-QO', seed=2):
        model = str(R.MODEL if arm == 'K1-QO' else R.PT_MODEL)
        target = {'schema': 'r3-formal-k1-plan-v1', 'control_arm': arm, 'seed': seed,
                  'model': model, 'scientific_acceptance': False, 'test_read': False,
                  'image_sha256': R.IMAGE, 'train_file': str(R.DATA), 'out': str(self.root / arm / str(seed)),
                  'files': {}, 'control': {'control_arm': arm, 'candidate_for_adoption': False,
                  'primary_input_mode': 'drop' if arm == 'K1-QO' else 'full',
                  'registered_seeds': [2] if arm == 'K1-QO' else [2, 3]}}
        target['command'] = ['python3', '-P', '/workspace/train_r3.py', '--out', target['out'],
            '--arm', 'k1', '--seed', str(seed), '--model-path', model, '--kernel', 'ref', '--grad-ckpt',
            '--micro-tokens', '12000', '--max-len', '4096', '--save-every', '200', '--no-merge',
            '--epochs', '2', '--total-steps', '3116', '--expect-pairs', '186']
        if arm == 'K1-QO': target['command'].append('--drop-state')
        return target

    def test_cli_ignores_legacy_preparation_and_review_pass(self):
        prep = self.root / 'PREPARED.json'; write(prep, {'status': 'PASS'})
        rec = self.root / 'PREPARATION.json'; write(rec, {'status': 'PASS'})
        review = self.root / 'review.json'; write(review, {'verdict': 'PASS', 'review_kind': 'independent_astra',
            'reviewer_model': 'gpt-6-astra', 'approved_plan_sha256': 'a' * 64})
        out = self.root / 'out.json'
        with patch.object(R, 'evidence', return_value={'status': 'PASS'}):
            R.main(['--k0-preparation', str(prep), '--resume-reconstruction', str(rec),
                    '--review', str(review), '--expected-plan-sha256', 'a' * 64, '--out', str(out)])
        result = json.loads(out.read_text())
        self.assertEqual(result['status'], 'WAITING')
        self.assertEqual(len(result['missing']), 3)
        self.assertTrue(all(result['checks'][name]['status'] != 'PASS' for name in
                            ('fresh_k0', 'resume_source', 'resume_reconstruction', 'independent_astra_review')))

    def test_missing_k0_rejects_actual_consumer_call(self):
        target = self.target(); prep = self.root / 'PREPARED.json'; write(prep, {'status': 'PASS'})
        target.update(fresh_k0_prechecks=str(self.root / 'K0_PRECHECKS.json'), fresh_k0_prechecks_sha256='a'*64)
        self.assertEqual(R.check(lambda: R.target_k0(target))['status'], 'INVALID')

    def test_exact_review_cannot_authorize_another_target(self):
        target = self.target(); review = self.root / 'review.json'
        target['review_path'] = str(review); pin = R.canonical_plan_sha256(target)
        write(review, {'verdict':'PASS', 'review_kind':'independent_astra', 'reviewer_model':'gpt-6-astra',
                       'approved_plan_sha256':pin})
        target['review_sha256'] = R.sha(review)
        R.target_review(target, pin)
        with self.assertRaises(ValueError): R.target_review(target, 'b'*64)
        write(review, {'verdict':'PASS'})
        with self.assertRaises(ValueError): R.target_review(target, pin)

    def test_target_canonical_identity_and_control_mode(self):
        target = self.target(); pin = R.canonical_plan_sha256(target)
        R.target_identity(target, pin)
        for key, value in [('model', str(R.PT_MODEL)), ('seed', 3), ('test_read', True)]:
            bad = copy.deepcopy(target); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                R.target_identity(bad, R.canonical_plan_sha256(bad))
        bad = copy.deepcopy(target); bad['command'].remove('--drop-state')
        with self.assertRaises(ValueError): R.target_identity(bad, R.canonical_plan_sha256(bad))
        with self.assertRaises(ValueError): R.target_identity(target, 'f'*64)

    def test_old_validator_bytes_cannot_claim_current_validation(self):
        target = self.target()
        with self.assertRaises(ValueError): R.target_implementations(target)
        for name in ('r3_resume_evidence', 'r3_resume_reconstruction_evidence',
                     'r3_training_evidence', 'r3_fresh_prechecks'):
            path = HERE / (name + '.py'); target['files'][str(path)] = R.sha(path)
        R.target_implementations(target)
        target['files'][str(HERE / 'r3_fresh_prechecks.py')] = 'f' * 64
        with self.assertRaises(ValueError): R.target_implementations(target)

    def test_qo_only_cannot_cover_pt(self):
        target = self.target(); path = self.root / 'qo.json'; write(path, target)
        result = R.audit_targets([(str(path), R.canonical_plan_sha256(target))])
        self.assertEqual(result['status'], 'WAITING')
        self.assertEqual(result['missing'], ['K1-PT/seed2', 'K1-PT/seed3'])
        self.assertEqual(result['targets'][0]['input_mode'], 'drop')
        self.assertNotEqual(result['targets'][0]['checks']['fresh_k0']['status'], 'PASS')

    def test_duplicate_target_coverage_refused(self):
        target = self.target(); path = self.root / 'qo.json'; write(path, target)
        entry = (str(path), R.canonical_plan_sha256(target))
        result = R.audit_targets([entry, entry])
        self.assertTrue(result['duplicate_target_coverage'])
        self.assertEqual(result['status'], 'WAITING')

    def test_resume_without_target_cannot_use_receipt_stubs(self):
        path = self.root / 'plan.json'; write(path, {'out': str(self.root)})
        write(self.root / 'TRAIN_EXIT.json', {'exit_code': 0, 'attempt': 1})
        self.assertFalse(R.resume_source_ready(path))

class RealValidators(unittest.TestCase):
    def setUp(self):
        self.fixture = F.Reconstruction(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture; source = f.fixture
        self.target = dict(source.target, resume_plan=str(source.path), resume_plan_sha256=source.pin,
            resume_reconstruction=str(f.report), resume_reconstruction_sha256=f.pin,
            reconstruction_target=str(f.target), reconstruction_target_sha256=f.target_pin,
            files=f.verify())

    def test_complete_source_and_reconstruction_use_real_validators(self):
        R.target_resume(self.target)
        R.target_reconstruction(self.target)

    def test_missing_receipt_hash_refused(self):
        f = self.fixture.fixture; path = f.root / 'attempts/1/LAUNCH_RECEIPT.json'
        doc = json.loads(path.read_text()); doc.pop('plan_sha256'); write(path, doc)
        with self.assertRaises(ValueError): R.target_resume(self.target)

    def test_empty_result_files_refused_even_with_correct_receipt_hashes(self):
        f = self.fixture.fixture
        write(f.root / 'CONTRACT_RESULT.json', {}); write(f.root / 'digest.json', {})
        self.assertEqual(R.check(lambda: R.target_resume(self.target))['status'], 'INVALID')

    def test_forged_reconstruction_and_missing_inventory_refused(self):
        f = self.fixture
        f.doc['inputs'] = {'fabricated': 'a'*64}; f.save()
        self.target['resume_reconstruction_sha256'] = f.pin
        self.target['files'][str(f.report)] = f.pin
        with self.assertRaises(ValueError): R.target_reconstruction(self.target)

    def test_preparation_pass_cannot_replace_reconstruction(self):
        f = self.fixture; path = f.fixture.root / 'PREPARATION.json'; write(path, {'status': 'PASS'})
        self.target.update(resume_reconstruction=str(path), resume_reconstruction_sha256=R.sha(path))
        self.target['files'][str(path)] = R.sha(path)
        with self.assertRaisesRegex(ValueError, 'preparation'): R.target_reconstruction(self.target)

    def test_reconstruction_binding_requires_matching_target_model(self):
        self.target['model'] = '/different-model'
        with self.assertRaises(ValueError): R.target_reconstruction(self.target)

if __name__ == '__main__': unittest.main()
