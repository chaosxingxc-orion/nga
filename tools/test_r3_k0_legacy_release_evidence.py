import copy
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

from tools import r3_dev_qualification as Q
from tools import r3_k0_legacy_release_evidence as E


class LegacyRelationshipTests(unittest.TestCase):
    def fixture(self):
        t0='2026-10-31T00:00:00Z';t1='2026-10-31T00:01:00Z'
        t2='2026-10-31T00:02:00Z';t3='2026-10-31T00:03:00Z'
        release_path=Path('/fixture/RELEASE.json');pin='a'*64
        p={'chip':1,'run':'k0','allocation':'/fixture/alloc.json'}
        entry={'chip':1,'run':'k0','claimed_utc':t0}
        before={'allocation':[],'free':[{'chip':1}]}
        claimed={'allocation':[entry],'free':[], 'updated_utc':t0,
                 'updated_by':'r3_resource_adapter claim'}
        released={'allocation':[], 'free':[{'chip':1,'previous_run':'k0',
                  'release_evidence':str(release_path),'released_utc':t3}],
                  'updated_utc':t3,'updated_by':'r3_resource_adapter release'}
        claim={'schema':'r3-resource-claim-v1',**p,'entry':entry,'claimed_utc':t0,
               'allocation_before':before,'allocation_after':claimed,
               'allocation_before_sha256':Q.ledger_digest(before),
               'allocation_after_sha256':Q.ledger_digest(claimed)}
        release={'schema':'r3-resource-release-v1','chip':1,'run':'k0',
                 'container_id':'cid','container':'k0-a1','exit_code':0,
                 'scientific_acceptance':False,'container_started_at':t1,
                 'container_finished_at':t2,'released_utc':t3,
                 'allocation_before':claimed,'allocation_after':released,
                 'allocation_before_sha256':Q.ledger_digest(claimed),
                 'allocation_after_sha256':Q.ledger_digest(released)}
        actual={'Id':'cid','Name':'/k0-a1','State':{'StartedAt':t1,'FinishedAt':t2}}
        return p,claim,release,pin,release_path,actual

    def check(self,args):
        return E.verify_relationship(Q,*args)

    def test_missing_field_explanation_never_mutates_original(self):
        args=self.fixture();before=copy.deepcopy(args)
        self.assertEqual(self.check(args)['container_id'],'cid')
        self.assertEqual(args,before)
        with self.assertRaises(ValueError):
            Q.ownership(*args)

    def test_no_generic_bypass_for_current_or_guarded_receipts(self):
        args=self.fixture();args[2]['claim_sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'missing-field'):
            self.check(args)
        args=self.fixture();args[1]['successor_precondition']={}
        with self.assertRaisesRegex(ValueError,'guarded'):
            self.check(args)

    def test_other_defects_remain_rejected(self):
        for mutate in [lambda a:a[2].update(container_id='other'),
                       lambda a:a[2].update(exit_code=False),
                       lambda a:a[2].update(container_started_at='2026-11-01T00:00:00Z'),
                       lambda a:a[1].update(allocation_after_sha256='0'*64),
                       lambda a:a[2].update(released_utc='2026-10-30T00:00:00Z')]:
            args=self.fixture();mutate(args)
            with self.assertRaises(ValueError):self.check(args)

    def test_rehashed_wrong_owner_is_rejected(self):
        args=copy.deepcopy(self.fixture());release=args[2]
        release['allocation_before']['allocation'][0]['claimed_utc']='2026-10-30T00:00:00Z'
        release['allocation_before_sha256']=Q.ledger_digest(release['allocation_before'])
        with self.assertRaises(ValueError):self.check(args)

    def test_bytes_and_scope_are_pinned(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'file.json';p.write_text('{}')
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(E.raw(p,h),b'{}')
            p.write_text('{"changed":true}')
            with self.assertRaises(ValueError):E.raw(p,h)
            with self.assertRaisesRegex(ValueError,'only two'):
                E.explain(str(p),h,str(p),h,'primary_s2')


if __name__=='__main__':unittest.main()
