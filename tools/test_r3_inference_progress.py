import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('progress',Path(__file__).with_name('r3_inference_progress.py'))
P=importlib.util.module_from_spec(s);s.loader.exec_module(P)


class Progress(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.expected={'trackk/decision-v7__dev/clean.jsonl':(10,'track_k'),
                       'trackt/readouts/primary__T1__typed-decisions__shard0of1.jsonl':(20,'track_t')}

    def receipt(self,rel,n):
        p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'not scores\n'*30)
        d={'path':str(p),'rows':n,'committed_bytes':30,'model_sha256':'a'*64,
           'sha256':'b'*64,'scorer':{'mode':'rightpad'}}
        r=Path(str(p)+'.receipt.json');r.write_text(json.dumps(d));return p,r,d

    def test_partial_and_missing_only_read_metadata(self):
        self.receipt(next(iter(self.expected)),4)
        original=Path.open
        def guarded(path,*args,**kwargs):
            self.assertNotEqual(path.suffix,'.jsonl','readout contents opened')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',guarded):r=P.summarize(self.root,self.expected)
        self.assertEqual(r['receipt_reported_rows'],4)
        self.assertEqual(r['missing_receipts'],1)
        self.assertEqual(r['flags'],{'incomplete_receipt':1})
        self.assertFalse(r['scores_read'])

    def test_all_counts_do_not_confer_completion(self):
        for rel,(n,_) in self.expected.items():self.receipt(rel,n)
        r=P.summarize(self.root,self.expected)
        self.assertEqual(r['record_fraction'],1.)
        self.assertEqual(r['completion'],'not_assessed')
        self.assertFalse(r['scientific_acceptance'])

    def test_invalid_rows_path_and_truncated_data_excluded(self):
        rel=next(iter(self.expected));p,r,d=self.receipt(rel,4)
        for change in ({'rows':11},{'rows':True},{'rows':-1},{'path':'/wrong'},
                       {'committed_bytes':100000},{'committed_bytes':True}):
            with self.subTest(change=change):
                r.write_text(json.dumps({**d,**change}))
                got=P.summarize(self.root,self.expected)
                self.assertEqual(got['receipt_reported_rows'],0)
                self.assertEqual(got['flags']['invalid_receipt'],1)
        r.write_text(json.dumps(d));p.unlink()
        self.assertEqual(P.summarize(self.root,self.expected)['receipt_reported_rows'],0)

    def test_identity_conflict_excludes_all_otherwise_valid(self):
        for i,(rel,(n,_)) in enumerate(self.expected.items()):
            _,p,d=self.receipt(rel,n)
            if i:d['model_sha256']='c'*64;p.write_text(json.dumps(d))
        r=P.summarize(self.root,self.expected)
        self.assertEqual(r['receipt_reported_rows'],0)
        self.assertEqual(r['flags']['inconsistent_model_or_scorer'],1)

    def test_unexpected_and_symlink_receipts_never_read(self):
        rel=next(iter(self.expected));p,r,d=self.receipt(rel,4)
        r.unlink();r.symlink_to('/does/not/exist')
        (self.root/'unexpected.receipt.json').write_text('invalid JSON must not be opened')
        got=P.summarize(self.root,self.expected)
        self.assertEqual(got['receipt_reported_rows'],0)
        self.assertEqual(got['flags']['unexpected_receipt'],1)
        self.assertEqual(got['flags']['invalid_receipt'],1)
        link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):P.summarize(link,self.expected)

    def test_population_pin_and_components(self):
        d={'schema':'r3-inference-workload-cpu-audit-v1','test_read':False,'scores_read':False,'scientific_acceptance':False,
           'roles':{'primary':'full','empty_input':'blank','question_only':'drop'},'track_k':[], 'track_t':[],
           'track_k_records':9516,'track_t_records_all_roles':139026,'records_per_role':46342,'total_records':148542}
        for suite,split,count,variants in [('decision-v7','dev',1264,204),('decision-v7','calibration',1148,None),('transfer-v4','dev',656,108)]:
            for kind in ('clean','question_only','empty_input'):
                d['track_k'].append({'cell':f'{suite}/{split}/{kind}','records':count})
            if variants:d['track_k'].append({'cell':f'{suite}/{split}/variants','records':variants})
        for task,source,n in [('T1','typed-decisions',9620),('T1','openjev-synth',12392),('T1','akhilaaa3',1292),
                              ('T2','typed-decisions',5016),('T2','openjev-synth',7690),('T2','akhilaaa3',712),('T3','typed-decisions',9620)]:
            d['track_t'].append({'task':task,'source':source,'records_per_role':n})
        p=self.root/'population.json'
        def publish():p.write_text(json.dumps(d));return hashlib.sha256(p.read_bytes()).hexdigest()
        pin=publish();self.assertEqual(len(P.population(p,pin)),32)
        with self.assertRaisesRegex(ValueError,'pin'):P.population(p,'0'*64)
        d['track_k'][0]['cell']='../dev/clean'
        with self.assertRaisesRegex(ValueError,'component'):P.population(p,publish())


if __name__=='__main__':unittest.main()
