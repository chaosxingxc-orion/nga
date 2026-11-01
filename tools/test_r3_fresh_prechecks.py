import copy
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('fresh',Path(__file__).with_name('r3_fresh_prechecks.py'))
F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)


def baseline():
    return {'schema':'r3-selection-report-v1','scientific_acceptance':False,
            'header':{'arm':'K0','model':{'kind':'checkpoint','path':'model'},
                      'partitions':['dev','calibration'],'track_t_config':'r3'},'selection_evidence':{}}


class Fresh(unittest.TestCase):
    def test_safe_path_rejects_test_data_but_allows_test_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for suffix in ('test.jsonl', 'test.variants.jsonl', 'test/shard.parquet', 'test/shard.jsonl'):
                with self.assertRaisesRegex(ValueError, 'test dataset'):
                    F.safe_path(root/suffix)
            self.assertEqual(F.safe_path(root/'test_r3_fresh_prechecks.py'), root/'test_r3_fresh_prechecks.py')

    def test_bundle_rejects_whole_inventory_before_hashing_any_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root/'K0_PRECHECKS.json'
            doc = {'schema':'r3-fresh-k0-prechecks-v2','status':'PASS',
                   'scientific_acceptance':False,'test_read':False,'model':'model',
                   'inputs':{str(root/'benign.json'):'fake',str(root/'test.jsonl'):'fake'},
                   'checks':{}}
            bundle.write_text(json.dumps(doc))
            pin = F.sha(bundle)
            with patch.object(F, 'sha', side_effect=lambda p: pin if Path(p)==bundle else self.fail('dependency read')):
                with self.assertRaisesRegex(ValueError, 'test dataset'):
                    F.validate_bundle(bundle,pin,'model')

    def test_scope_rejects_adapter_test_seed_and_wrong_model(self):
        good=baseline();F.validate_baseline(good,'model')
        for mutate in [lambda x:x['header'].update(arm='K1'),
                       lambda x:x['header']['model'].update(kind='adapter'),
                       lambda x:x['header'].update(partitions=['test']),
                       lambda x:x['selection_evidence'].update(seed=2),
                       lambda x:x['header']['model'].update(path='other')]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):F.validate_baseline(bad,'model')

    def forged_bundle(self, root):
        report=root/'selection_report.json';report.write_text(json.dumps(baseline()))
        checks={}
        for name in ['a_constant_uniform_gold_position','d_kev_files_vs_manifest',
                     'b_decision-v7_dev','b_transfer-v4_dev',
                     'c_decision-v7_k0_dev','c_transfer-v4_k0_dev']:
            p=root/(name+'.json');p.write_text('{"ok":true,"evidence":"fixture"}');checks[str(p)]=F.sha(p)
        receipt=root/'SCORING_RECEIPT.track_kt.json';receipt.write_text('{"receipt":true}')
        generator=root/'r3_fresh_prechecks.py';generator.write_text('# fixture\n')
        d={'schema':'r3-fresh-k0-prechecks-v1','status':'PASS','scientific_acceptance':False,
           'test_read':False,'model':'model','k0_report':str(report),
           'inputs':{str(report):F.sha(report),str(receipt):F.sha(receipt),str(generator):F.sha(generator)},
           'checks':checks}
        bundle=root/'K0_PRECHECKS.json';bundle.write_text(json.dumps(d))
        return bundle,d

    def test_original_astra_counterexample_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bundle,doc=self.forged_bundle(Path(td))
            with self.assertRaisesRegex(ValueError, 'regenerate v1'):
                F.validate_bundle(bundle,F.sha(bundle),'model')

    def test_rehashed_fake_tool_is_never_executed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle,doc=self.forged_bundle(root)
            sentinel=root/'executed'
            tool=root/'fake.py';tool.write_text(f'open({str(sentinel)!r}, "w").write("executed")')
            code=root/'closure/r3_code';code.mkdir(parents=True)
            (code.parent/'manifest.json').write_text('{"code":{}}')
            doc.update(schema='r3-fresh-k0-prechecks-v2',reconstruction={
                'report_tool':str(tool),'report_tool_sha256':F.sha(tool),
                'frozen_code_dir':str(code),'closure_sha256':F.sha(code.parent/'manifest.json'),
                'kev_dir':str(root),'data_root':str(root)})
            bundle.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'untrusted report tool'):
                F.validate_bundle(bundle,F.sha(bundle),'model')
            self.assertFalse(sentinel.exists())

    def test_rehashed_fake_closure_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle,doc=self.forged_bundle(root)
            tool=Path(__file__).with_name('r3_selection_report.py').resolve()
            code=root/'closure/r3_code';code.mkdir(parents=True)
            (code.parent/'manifest.json').write_text('{"code":{}}')
            doc.update(schema='r3-fresh-k0-prechecks-v2',reconstruction={
                'report_tool':str(tool),'report_tool_sha256':F.sha(tool),
                'frozen_code_dir':str(code),'closure_sha256':F.sha(code.parent/'manifest.json'),
                'kev_dir':str(root),'data_root':str(root)})
            bundle.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'untrusted reconstruction closure'):
                F.validate_bundle(bundle,F.sha(bundle),'model')

    def test_formal_prepare_refuses_legacy_default_before_writing(self):
        spec=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('r3_formal_prepare.py'))
        P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'run'
            with self.assertRaisesRegex(ValueError,'fresh K0'):
                P.prepare(out,2,1)
            self.assertFalse(out.exists())

    def test_untrusted_generation_never_publishes_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);report=root/'selection_report.json';report.write_text('{}')
            tool=root/'tool.py';tool.write_text('raise AssertionError("must not execute")')
            closure=root/'closure';closure.mkdir();(closure/'manifest.json').write_text('{}')
            a=SimpleNamespace(k0_report=str(report),report_tool=str(tool),report_tool_sha256=F.sha(tool),
                frozen_code_dir=str(closure/'r3_code'),closure_sha256=F.sha(closure/'manifest.json'),
                model='model',out=str(root/'out'),kev_dir=str(root),data_root=str(root))
            with self.assertRaisesRegex(ValueError,'untrusted report tool'):F.run(a)
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
