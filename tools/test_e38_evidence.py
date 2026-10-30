"""E38 evidence object/race, durable attempt and publication recovery checks."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

def module(name):
    spec=importlib.util.spec_from_file_location('test_'+name,Path(__file__).with_name(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

e=module('e38_evidence');v=module('verify_openjev_path_trace')

class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
    def test_snapshot_replacement_and_parent_symlink_rejected(self):
        path=self.out/'value.json';e.publish_new(path,{'value':1});snap=e.Snapshot(path)
        replacement=self.out/'new';replacement.write_bytes(path.read_bytes());replacement.replace(path)
        with self.assertRaises(ValueError):snap.verify()
        link=self.out/'link';link.symlink_to(self.out,target_is_directory=True)
        with self.assertRaises(ValueError):e.Snapshot(link/'value.json')
    def test_publish_never_overwrites_and_interrupted_pending_blocks(self):
        path=self.out/'value.json';e.publish_new(path,{'value':1})
        with self.assertRaises(FileExistsError):e.publish_new(path,{'value':2})
        self.assertEqual(json.loads(path.read_bytes()),{'value':1})
        path=self.out/'other.json';path.with_name(path.name+'.pending').write_text('uncertain')
        with self.assertRaises(FileExistsError):e.publish_new(path,{'value':2})
    def test_report_gap_fails_generation_without_overwriting_evidence(self):
        path=self.out/'report.json';path.write_text('existing report')
        (self.out/'EXIT').write_text('original exit')
        with self.assertRaises(ValueError):e.publication_gate(self.out)
        self.assertEqual(path.read_text(),'existing report')
        self.assertEqual((self.out/'EXIT').read_text(),'original exit')
        self.assertFalse(json.loads((self.out/'FAILED_GENERATION.json').read_bytes())['new_forward_allowed'])
    def test_attempt_requires_matching_receipt_and_digest(self):
        plan={'execution_revision':'astra-v3-strict-attempts','out':str(self.out),'source_config_sha256':'source',
              'input':{'request_sha256':'request'}}
        folder=self.out/'attempts';folder.mkdir();task=v.schedule()[0];filename=v.name(task)+'.json'
        intent=dict(**v.identity(plan,'plan',task),phase='forward_intent',utc='2026-10-31T00:00:00Z')
        e.publish_new(folder/filename,intent)
        with self.assertRaisesRegex(ValueError,'Unmatched'):v.validate_attempts(plan,'plan',{},e.Evidence())
        digest=e.Snapshot(folder/filename).sha256;items={filename:{'attempt_sha256':digest}}
        self.assertEqual(v.validate_attempts(plan,'plan',items,e.Evidence()),{filename:digest})
        items[filename]['attempt_sha256']='bad'
        with self.assertRaises(ValueError):v.validate_attempts(plan,'plan',items,e.Evidence())

if __name__=='__main__':unittest.main()
