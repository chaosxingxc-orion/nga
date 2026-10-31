import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

s=importlib.util.spec_from_file_location('entry',Path(__file__).with_name('r3_scoring_entry.py'))
E=importlib.util.module_from_spec(s);s.loader.exec_module(E)

class ReceiptTests(unittest.TestCase):
    def test_forbidden_stage_partition_or_tag_never_calls_evaluator(self):
        for stages,parts,tag in [('k,report','dev','main'),('t_score','test','main'),('k_score','dev','../x')]:
            original=Mock()
            with self.assertRaises(ValueError):
                E.receipt_runner(original)(SimpleNamespace(stages=stages,partitions=parts,unit_tag=tag),None)
            original.assert_not_called()

    def test_only_producer_header_preserved_not_report_half(self):
        with tempfile.TemporaryDirectory() as td:
            args=SimpleNamespace(stages='k_score,t_score',partitions='dev,calibration',unit_tag='scores',out=td)
            report={'header':{'model':{'sha256':'actual-producer'}},'track_t':{'report':'must not publish'}}
            E.receipt_runner(lambda a,s: report)(args,None)
            receipt=json.loads((Path(td)/'SCORING_RECEIPT.scores.json').read_text())
            self.assertEqual(receipt['header'],report['header'])
            self.assertNotIn('track_t',receipt)
            self.assertFalse(receipt['scientific_acceptance'])

    def test_failed_scoring_cannot_write_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            args=SimpleNamespace(stages='t_score',partitions='dev',unit_tag='t',out=td)
            def fail(a,s):raise SystemExit(1)
            with self.assertRaises(SystemExit):E.receipt_runner(fail)(args,None)
            self.assertFalse(list(Path(td).iterdir()))

if __name__=='__main__':unittest.main()
