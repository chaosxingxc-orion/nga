import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import os

from tools import r3_member_evidence_prepare as M


class PreparationBoundaryTests(unittest.TestCase):
    def test_config_pin_required_and_no_output_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c=root/'config.json';c.write_text('{}');out=root/'candidate.json'
            with self.assertRaisesRegex(ValueError,'changed'):
                M.prepare(c,'0'*64,out)
            self.assertFalse(out.exists())

    def test_unknown_schema_rejected_before_evidence_reads(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c=root/'config.json';c.write_text('{"schema":"wrong"}')
            with self.assertRaisesRegex(ValueError,'schema'):
                M.prepare(c,hashlib.sha256(c.read_bytes()).hexdigest(),root/'out')

    def test_symlink_config_cannot_redirect_pinned_read(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c=root/'real.json';c.write_text('{}');link=root/'config.json';link.symlink_to(c)
            with self.assertRaisesRegex(ValueError,'unsafe'):
                M.prepare(link,hashlib.sha256(c.read_bytes()).hexdigest(),root/'out')

    def test_missing_member_does_not_create_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);q=root/'q.json';q.write_text('{"members":{}}')
            ref={'path':str(q),'sha256':hashlib.sha256(q.read_bytes()).hexdigest()}
            c=root/'c.json';c.write_text(json.dumps({'schema':'r3-member-evidence-prepare-v1',
                'member':'absent','qualification':ref,'capture':ref,'collection':ref,
                'postrun_review':ref,'producer_manifest':ref,'review_lineage':ref}))
            with self.assertRaises(KeyError):
                M.prepare(c,hashlib.sha256(c.read_bytes()).hexdigest(),root/'out')
            self.assertFalse((root/'out').exists())

    @unittest.skipUnless(os.environ.get('NGA_MEMBER_FIXTURES'), 'real evidence fixtures opt-in')
    def test_real_rehashed_review_counterexamples(self):
        base=Path(os.environ['NGA_MEMBER_FIXTURES'])
        configs=[base/name/'CONFIG.json' for name in
                 ['foreign_runtime_refs','foreign_empty_producer','status_only_lineage']]
        partial=base.parent/'member-assembly-rereview-20261103-v1/nonempty_partial_producer/CONFIG.json'
        if partial.exists():configs.append(partial)
        for config in configs:
            config=config.resolve()
            with tempfile.TemporaryDirectory() as d:
                out=Path(d)/'candidate.json'
                with self.subTest(config=str(config)), self.assertRaises((ValueError,KeyError)):
                    M.prepare(config,M.sha(config),out)
                self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
