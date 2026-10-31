import copy
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
    def test_scope_rejects_adapter_test_seed_and_wrong_model(self):
        good=baseline();F.validate_baseline(good,'model')
        for mutate in [lambda x:x['header'].update(arm='K1'),
                       lambda x:x['header']['model'].update(kind='adapter'),
                       lambda x:x['header'].update(partitions=['test']),
                       lambda x:x['selection_evidence'].update(seed=2),
                       lambda x:x['header']['model'].update(path='other')]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):F.validate_baseline(bad,'model')

    def test_reconstruction_failure_never_publishes_prechecks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);report=root/'selection_report.json';report.write_text('{}')
            tool=root/'tool.py';tool.write_text('')
            closure=root/'closure';closure.mkdir();(closure/'manifest.json').write_text('{}')
            a=SimpleNamespace(k0_report=str(report),report_tool=str(tool),report_tool_sha256=F.sha(tool),
                frozen_code_dir=str(closure/'r3_code'),closure_sha256=F.sha(closure/'manifest.json'),
                model='model',out=str(root/'out'),kev_dir='dev',data_root='data')
            for actual in [ValueError('unstamped provenance'),dict(baseline(),tampered=True)]:
                def rebuild(*args):
                    if isinstance(actual,Exception):raise actual
                    return actual
                R=SimpleNamespace(modules=lambda *a:(None,)*5,load=lambda p:baseline(),rebuild=rebuild)
                with patch.object(F,'load_module',return_value=R):
                    with self.assertRaises(ValueError):F.run(a)
                self.assertFalse((root/'out').exists())
            a.report_tool_sha256='0'*64
            with self.assertRaisesRegex(ValueError,'tool pin'):F.run(a)


if __name__=='__main__':unittest.main()
