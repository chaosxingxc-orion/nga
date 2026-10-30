import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reaudit', Path(__file__).with_name('legacy_kev_dated_reaudit.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class ReauditTests(unittest.TestCase):
    def test_changed_same_size_json_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'x.json'; p.write_text('{"x":1}')
            manifest = {str(p): m.file_hash(p)}
            p.write_text('{"x":2}')
            with self.assertRaisesRegex(ValueError, 'Changed JSON'):
                m.frozen_json(p, manifest)

    def test_second_scan_catches_receipt_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp); p=d/'receipt.json'; p.write_text('{"x":1}')
            entries=[{'path':str(p)}]
            before=m.hash_phase(entries,d,'before',None,{})
            p.write_text('{"x":2}')
            with self.assertRaisesRegex(ValueError, 'changed since'):
                m.hash_phase(entries,d,'after',before,{})

    def test_expected_dependency_hash_is_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);p=d/'weight';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError, 'Frozen expected'):
                m.hash_phase([{'path':str(p),'expected_sha256':'0'*64}],d,'phase',None,{})

    def test_metric_tamper_rejected_and_historical_binding_preserved(self):
        row={'model':'x','dataset':'decision-v7/clean','protocol':'native','metrics':{'n':2,'acc':.5,'brier':.2,'ece':.1,'nll':.4},'audit_terminal_binding':'absent_legacy_inline_audit'}
        audit={'suites':{'decision-v7':{'native':dict(row['metrics'])}}}
        panels=m.compare_panels(audit,{'matrix_row_indices':[0]},{'rows':[row]})
        self.assertEqual(panels[0]['historical_binding'],'absent_legacy_inline_audit')
        audit['suites']['decision-v7']['native']['acc']=1
        with self.assertRaisesRegex(ValueError,'metric mismatch'):
            m.compare_panels(audit,{'matrix_row_indices':[0]},{'rows':[row]})

    def test_actual_exit_and_wrapper_identity_required(self):
        run={'container_id':'a'*64,'image':'x','directory':'/run'}
        obs={'Id':'a'*64,'Image':'x','State':{'Status':'exited','Running':False,'ExitCode':137},'Args':['/run/run.sh']}
        with self.assertRaisesRegex(ValueError,'exited/0'):m.verify_container(obs,run)
        obs['State']['ExitCode']=0;obs['Args']=['/different/run.sh']
        with self.assertRaisesRegex(ValueError,'wrapper mismatch'):m.verify_container(obs,run)

    def test_extra_receipt_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);q=d/'s'/'records';q.mkdir(parents=True)
            (q/'000000.json').write_text('{}');(q/'000001.json').write_text('{}')
            cfg=d/'config.json';cfg.write_text(json.dumps({'suites':[{'name':'s','records':1}]}))
            with self.assertRaisesRegex(ValueError,'file set mismatch'):
                m.inventory_check({'runs':[{'directory':str(d),'config':str(cfg),'name':'fixture'}]},{str(cfg):m.file_hash(cfg)})

    def test_auditor_source_swap_cannot_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'auditor.py';p.write_text('safe = True\n');manifest={str(p):m.file_hash(p)}
            p.write_text('raise RuntimeError("must not execute")\n')
            with self.assertRaisesRegex(ValueError,'Changed auditor source'):m.load_auditor(p,manifest)

    def test_opened_fd_must_match_path_before_even_when_path_restored(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);a=d/'a';b=d/'b';a.write_bytes(b'aaa');b.write_bytes(b'bbb')
            original_open=Path.open
            def swapped(path, *args, **kwargs):
                return original_open(b if path == a else path, *args, **kwargs)
            with patch.object(Path, 'open', swapped):
                with self.assertRaisesRegex(ValueError, 'before file open'):
                    m.file_hash(a)

    def test_frozen_real_auditor_loader_keeps_arithmetic_callable(self):
        for name in ['verify_reference_kev.py','verify_reference_kev_devtools.py']:
            p=Path(__file__).with_name(name)
            module=m.load_auditor(p,{str(p):m.file_hash(p)})
            self.assertTrue(callable(module.audit))
            self.assertTrue(callable(module.frozen_text))

    def test_atomic_reports_are_readable_outside_root_container(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'report.json';m.atomic(p,{'rc':0})
            self.assertEqual(p.stat().st_mode & 0o777,0o644)
            self.assertEqual(json.loads(p.read_bytes()),{'rc':0})

    def test_suspicious_success_retains_flags(self):
        metrics={'n':5,'acc':1.,'brier':0.,'ece':0.,'nll':0.}
        flags=m.flags_for_panels([{'key':'a','metrics':metrics},{'key':'b','metrics':metrics}])
        self.assertEqual(sum(f['code']=='small_population' for f in flags),2)
        self.assertEqual(sum(f['code']=='exact_boundary_rate' for f in flags),2)
        self.assertEqual(sum(f['code']=='identical_metric_across_all_panels' for f in flags),4)

if __name__ == '__main__':unittest.main()
