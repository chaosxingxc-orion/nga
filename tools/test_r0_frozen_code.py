import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'experiments/r3_sft/r3_code/r0rescore_verify.py'
tree = ast.parse(SOURCE.read_text())
scope = {'Path': Path, 'json': json, 'os': os}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name in ('_check_frozen_code', 'check_executed_code')],
                        type_ignores=[]), str(SOURCE), 'exec'), scope)
check = scope['check_executed_code']


class FrozenCode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {}
        self.mounts = []
        for name in ('r3_code', 'r0_code', 'r1_code'):
            root = self.root / ('code' if name == 'r3_code' else name); root.mkdir()
            source = root / (name + '.py'); source.write_text('X=1\n')
            self.files[str(source)] = self.sha(source)
            self.mounts.append({'source': str(root), 'destination': '/mnt/cephfs/xingchao/experiments/jev/' + name, 'readonly': True})
        self.record = self.root / 'SHA1SUMS'
        self.write_record()

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_record(self, omit=False, extra=''):
        rows = []
        for index, mount in enumerate(self.mounts):
            p = next(Path(mount['source']).glob('*.py'))
            if omit and index == 1:
                continue
            name = p.name if index == 0 else p.parent.name + '/' + p.name
            rows.append(hashlib.sha1(p.read_bytes()).hexdigest() + '  ' + name + '\n')
        self.record.write_text(''.join(rows) + extra)
        self.files[str(self.record)] = self.sha(self.record)
        self.repin()

    def repin(self):
        spec = self.root / 'plan.json'
        spec.write_text(json.dumps({'evaluation_profile': 'track_t_r0', 'test_read': False,
                                   'code_mounts': self.mounts, 'files': self.files}))
        execution = self.root / 'execution.json'
        execution.write_text(json.dumps({'schema': 'r3-engineering-posttrain-execution-v1',
                                         'out': str(self.root), 'spec': str(spec), 'spec_sha256': self.sha(spec)}))
        self.pin = self.sha(execution)

    def test_frozen_sources_do_not_read_live_paths(self):
        original = Path.read_bytes
        def reject_live(path):
            if str(path).startswith('/mnt/cephfs/xingchao/experiments/jev/'):
                raise AssertionError('live source accessed')
            return original(path)
        with patch.object(Path, 'read_bytes', reject_live):
            self.assertEqual(check(str(self.root), self.pin), [])

    def test_external_pin_and_spec_binding_required(self):
        self.assertIn('caller-pinned', check(str(self.root))[0])
        self.assertIn('pin differs', check(str(self.root), '0' * 64)[0])
        (self.root / 'plan.json').write_text('{}')
        self.assertIn('specification differs', check(str(self.root), self.pin)[0])

    def test_source_mutation_extra_source_and_missing_record_refused(self):
        source = self.root / 'r0_code/r0_code.py'
        source.write_text('X=2')
        self.assertIn('changed source', check(str(self.root), self.pin)[0])
        source.write_text('X=1\n')
        extra = self.root / 'r0_code/extra.py'; extra.write_text('X=1')
        self.assertIn('changed source', check(str(self.root), self.pin)[0])
        extra.unlink(); self.write_record(omit=True)
        self.assertIn('omits frozen', check(str(self.root), self.pin)[0])

    def test_unsafe_duplicate_and_symlink_records_refused(self):
        self.write_record(extra='0'*40 + '  ../outside.py\n')
        self.assertIn('unsafe code record', check(str(self.root), self.pin)[0])
        self.write_record(); line = self.record.read_text().splitlines()[0]
        self.write_record(extra=line+'\n')
        self.assertIn('duplicate', check(str(self.root), self.pin)[0])
        self.write_record(); p=self.root/'r0_code/r0_code.py'; p.unlink(); p.symlink_to(self.root/'code/r3_code.py')
        self.assertIn('unsafe/writable', check(str(self.root), self.pin)[0])

    def test_code_record_tampering_and_writable_mount_refused(self):
        self.record.write_text('')
        self.assertIn('SHA1SUMS', check(str(self.root), self.pin)[0])
        self.write_record(); self.mounts[0]['readonly']=False; self.repin()
        self.assertIn('unsafe/writable', check(str(self.root), self.pin)[0])

    def test_report_override_is_checked_without_publishing_report(self):
        scope = {'Path':Path, 'json':json, 'os':os, 'R0_MODEL':'model', 'ROLES':('primary',),
                 'C':SimpleNamespace(DATA_ROOT='data', ROUND_DIR='round', utc_now=lambda:'now'),
                 'RC':SimpleNamespace(SOURCE_FILES=[]),
                 'T':SimpleNamespace(CONFIG_R0={}, records_needed=lambda *a:[]),
                 'PV':SimpleNamespace(verify=lambda *a,**k:{}, ProvenanceRefusal=ValueError),
                 'check_executed_code':check}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)
                                     and n.name in ('check','utc')],type_ignores=[]),str(SOURCE),'exec'),scope)
        report={'track_t':{'config':'r0'},'header':{'arm':'K0','scorer':{'record_grade':True,'hf32':{'hf32':False}}}}
        result=scope['check'](str(self.root),expected_sha='model',report_override=report,
                              expected_execution_sha256=self.pin)
        self.assertEqual(result['problems'],[])
        self.assertFalse((self.root/'instruct/report.json').exists())
        report['track_t']['config']='r3'
        self.assertTrue(scope['check'](str(self.root),expected_sha='model',report_override=report,
                                      expected_execution_sha256=self.pin)['problems'])


if __name__ == '__main__': unittest.main()
