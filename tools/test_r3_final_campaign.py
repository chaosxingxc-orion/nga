"""Synthetic campaign membership; no test data or model access."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('campaign', Path(__file__).with_name('r3_final_campaign.py'))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def fixture(selected='K1'):
    members = []
    for index, (arm, seed) in enumerate(((selected, 2), (selected, 3), ('K0', None),
                                        ('K1-QO', 2), ('K1-PT', 2), ('K1-PT', 3), ('K0', None))):
        base = C.INSTRUCT if arm == 'K1-PT' or index == 6 else C.BASE
        root = '/runs/' + arm + '-' + str(seed)
        model_path = base if arm == 'K0' else root + '/adapter'
        member = {'role': 'candidate' if arm == selected else 'baseline' if arm == 'K0' else 'control',
                  'arm': arm, 'verified_evidence_sha256': 'a' * 64,
                  'model': {'path': model_path, 'sha256': str(index + 1) * 64,
                            'base_path': base, 'base_inventory_sha256': ('e' if base == C.INSTRUCT else 'f') * 64,
                            'kind': 'checkpoint' if arm == 'K0' else 'lora-adapter-unmerged'}}
        if arm != 'K0':
            member['training'] = {'seed': seed, 'arm': arm, 'adapter_path': model_path,
                'training_manifest': root + '/manifest.json', 'training_manifest_sha256': 'b' * 64,
                'training_variant': {'model_path': base, 'args': {'arm': 'k2' if arm == 'K2' else 'k1',
                    'drop_state': arm == 'K1-QO', 'k2_impl': 'rows'}, 'total_steps': 3116}}
        members.append(member)
    return {'schema': 'r3-final-campaign-v1', 'size': '0.8B', 'selected_arm': selected, 'members': members}


class Campaign(unittest.TestCase):
    def test_complete_k1_and_k2_are_structure_only(self):
        for arm in ('K1', 'K2'):
            campaign = fixture(arm); before = copy.deepcopy(campaign)
            result = C.verify(campaign)
            self.assertEqual(result['member_count'], 7)
            self.assertFalse(result['scientific_acceptance'])
            self.assertFalse(result['publication_authorized'])
            self.assertEqual(campaign, before)

    def test_missing_extra_duplicate_seed_and_control_role_rejected(self):
        cases = []
        d = fixture(); d['members'].pop(); cases.append(d)
        d = fixture(); d['members'].append(copy.deepcopy(d['members'][0])); cases.append(d)
        d = fixture(); d['members'][1]['training']['seed'] = 2; cases.append(d)
        d = fixture(); d['members'][3]['role'] = 'candidate'; cases.append(d)
        d = fixture(); d['selected_arm'] = 'K1-PT'; cases.append(d)
        d = fixture(); d['members'][3]['training']['seed'] = 3; cases.append(d)
        d = fixture(); d['members'][0]['training']['seed'] = True; cases.append(d)
        for d in cases:
            with self.subTest(d=d), self.assertRaises(ValueError): C.verify(d)

    def test_wrong_base_and_bytes_rejected(self):
        for index, field, value in ((4, 'base_path', C.BASE), (0, 'base_path', C.INSTRUCT),
                                    (3, 'base_inventory_sha256', '0' * 64),
                                    (5, 'base_inventory_sha256', '0' * 64)):
            d = fixture(); d['members'][index]['model'][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError): C.verify(d)

    def test_recipe_mismatch_in_candidates_and_pt_rejected(self):
        for index in (1, 5):
            d = fixture(); d['members'][index]['training']['training_variant']['args']['k2_impl'] = 'shared'
            with self.assertRaisesRegex(ValueError, 'different recipes'): C.verify(d)
        d = fixture(); d['members'][3]['training']['training_variant']['args']['drop_state'] = False
        with self.assertRaisesRegex(ValueError, 'objective/input'): C.verify(d)

    def test_model_alias_identity_and_noncanonical_path_rejected(self):
        for field, value in (('path', '/runs/K1-2/adapter'), ('sha256', '1' * 64),
                             ('path', '/runs/a/../K1-3/adapter'), ('path', '//runs/K1-3/adapter'),
                             ('path', '/runs/./K1-3/adapter')):
            d = fixture(); d['members'][1]['model'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): C.verify(d)

    def test_instruct_k0_is_required_and_pins_pt_bytes(self):
        d = fixture(); d['members'].pop()
        with self.assertRaisesRegex(ValueError, 'seven-member'): C.verify(d)
        d = fixture(); d['members'][6] = copy.deepcopy(d['members'][2])
        with self.assertRaisesRegex(ValueError, 'duplicate'): C.verify(d)
        d = fixture(); d['members'][6]['model']['base_inventory_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'PT instruct checkpoint bytes'): C.verify(d)
        d = fixture(); d['members'][6]['seed'] = 2
        with self.assertRaisesRegex(ValueError, 'synthetic seeds'): C.verify(d)
        d = fixture(); d['members'][6]['role'] = 'candidate'
        with self.assertRaisesRegex(ValueError, 'role confusion'): C.verify(d)

    def test_training_binding_and_baseline_seed_rejected(self):
        d = fixture(); d['members'][0]['training']['adapter_path'] = '/other/adapter'
        with self.assertRaisesRegex(ValueError, 'adapter differs'): C.verify(d)
        d = fixture(); d['members'][0]['training']['training_manifest'] = '/other/manifest.json'
        with self.assertRaisesRegex(ValueError, 'own adapter'): C.verify(d)
        d = fixture(); d['members'][2]['seed'] = 2
        with self.assertRaisesRegex(ValueError, 'synthetic seeds'): C.verify(d)
        d = fixture(); d['size'] = '2B'
        with self.assertRaisesRegex(ValueError, '0.8B'): C.verify(d)


if __name__ == '__main__': unittest.main()
