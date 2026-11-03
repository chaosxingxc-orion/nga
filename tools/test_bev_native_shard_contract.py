import copy
import unittest
from tools import bev_native_shard_contract as S


class Shards(unittest.TestCase):
    def fixture(self):
        # Two semantically identical requests retain different global ordinals.
        rows=[dict(i=i,qid='same',request_sha256='request'+str(i),input_ids=[7,8]) for i in range(4)]
        identities=[S.request_identity(r,i) for i,r in enumerate(rows)]
        b=dict(parent_population={'path':'/parent','sha256':'p'},inputs={'path':'/requests','sha256':'q'},
               model_sha256='model',contract_sha256='contract',source_protocol_binding_sha256='source',
               global_count=4,global_request_identities_sha256=S.digest(identities),shard_count=2,
               strategy='contiguous_equal_count',execution_authorized=False,scientific_acceptance=False,
               candidate_test_authority=False)
        shards=[]; results=[]
        for sid in range(2):
            ids=list(range(sid*2,sid*2+2))
            m=dict(b,schema='bev-native-shard-manifest-v1',shard_id=sid,global_ordinals=ids,
                   ordinals_sha256=S.digest(ids),assigned_count=2,input_tokens=4,
                   assigned_request_identities_sha256=S.digest([identities[i] for i in ids]))
            shards.append(m)
            results.append(dict(shard_id=sid,manifest_sha256=S.digest(m),exit_code=0,
                                scientific_acceptance=False,model_sha256='model',contract_sha256='contract',
                                predictions=[dict(identities[i],first_index=i%2) for i in ids]))
        c=dict(schema='bev-native-shard-population-v1',binding=b,shards=shards,
               scientific_acceptance=False,execution_authorized=False,numerical_equivalence_verified=False)
        return c,rows,results

    def test_nonzero_global_identity_and_duplicates_preserved(self):
        c,rows,r=self.fixture();out=S.merge_population(c,rows,r)
        self.assertEqual(c['shards'][1]['global_ordinals'],[2,3])
        self.assertEqual([x['i'] for x in out['predictions']],[0,1,2,3])
        self.assertEqual([x['qid'] for x in out['predictions']],['same']*4)
        self.assertFalse(out['complete']);self.assertFalse(out['lifecycle_verified'])

    def test_bad_assignment(self):
        for ids in ([2],[2,2],[2,4],[True,3],[0,1],[3,2]):
            c,_,_=self.fixture();c['shards'][1]['global_ordinals']=ids
            c['shards'][1]['ordinals_sha256']=S.digest(ids)
            with self.subTest(ids=ids),self.assertRaises(ValueError):S.validate(c)

    def test_foreign_bindings(self):
        for field,value in [('parent_population',{'path':'/other','sha256':'p'}),('model_sha256','other'),
                            ('contract_sha256','other'),('source_protocol_binding_sha256','other'),
                            ('shard_count',True),('global_count',True)]:
            c,_,_=self.fixture();c['shards'][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):S.validate(c)

    def test_partial_or_failed_result(self):
        for action in ('missing','failed','bool','prediction_missing','local_index','foreign_manifest',
                       'foreign_model','foreign_contract','gold','changed_tokens','false_scope'):
            c,rows,r=self.fixture()
            if action=='missing':r.pop()
            elif action=='failed':r[1]['exit_code']=1
            elif action=='bool':r[1]['exit_code']=False
            elif action=='prediction_missing':r[1]['predictions'].pop()
            elif action=='local_index':r[1]['predictions'][0]['i']=0
            elif action=='foreign_manifest':r[1]['manifest_sha256']='other'
            elif action=='foreign_model':r[1]['model_sha256']='other'
            elif action=='foreign_contract':r[1]['contract_sha256']='other'
            elif action=='gold':r[1]['predictions'][0]['gold']=0
            elif action=='changed_tokens':rows[2]['input_ids']=[9]
            elif action=='false_scope':r[1]['scientific_acceptance']=True
            with self.subTest(action=action),self.assertRaises(ValueError):S.merge_population(c,rows,r)

    def test_no_mutation_no_metrics_averaging(self):
        c,rows,r=self.fixture();before=copy.deepcopy((c,rows,r));out=S.merge_population(c,rows,r)
        self.assertEqual((c,rows,r),before);self.assertNotIn('accuracy',out)
        self.assertEqual([p['first_index'] for p in out['predictions']],[0,1,0,1])

    def test_native_unicode_digest(self):
        import hashlib
        self.assertEqual(S.digest({'q':'等级'}),hashlib.sha256('{"q":"等级"}'.encode()).hexdigest())

    def test_manifest_cannot_grant_execution(self):
        for field in ('scientific_acceptance','execution_authorized','numerical_equivalence_verified'):
            c,_,_=self.fixture();c[field]=True
            with self.subTest(field=field),self.assertRaises(ValueError):S.validate(c)


if __name__=='__main__':unittest.main()
