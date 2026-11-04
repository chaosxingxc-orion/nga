import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('recovery',Path(__file__).with_name('r3_recovered_dev_member_v1.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'new';self.files={}
        self.rel='trackk/a.jsonl';self.model='a'*64
        self.rows=[{'k':'one','ids':[1,2],'gold_index':0,'s':[1,0],'argmax':0,'tie':False,'m':self.model[:16]},
                   {'k':'two','ids':[1,2],'gold_index':1,'s':[0,1],'argmax':1,'tie':False,'m':self.model[:16]}]
        self.source=self.put(self.root/'source/execution.json',{'out':str(self.root/'source')})
        self.snapshot=self.put(self.out/'SOURCE.json',{'out':str(self.root/'source')})
        payload=(json.dumps(self.rows[0])+'\n').encode()
        self.data=self.raw(self.out/'imported/a.jsonl',payload)
        self.receipt=self.put(self.out/'imported/a.receipt.json',{'path':str(self.root/'source/results'/self.rel),'committed_bytes':len(payload),'sha256':self.data['sha256'],'rows':1,'model_sha256':self.model,'scorer':'frozen'})
        self.output=self.raw(self.out/'results'/self.rel,b''.join((json.dumps(x)+'\n').encode() for x in self.rows))
        self.pop=self.put(self.out/'POPULATION.json',{'schema':'r3-dev-resume-population-v1','test_read':False,'files':{self.rel:{r['k']:{k:v for k,v in r.items() if k not in ('s','p','argmax','tie','m')} for r in self.rows}}})
        self.imp=self.put(self.out/'IMPORTS.json',{'schema':'r3-dev-imported-prefixes-v1','source_execution':self.source,'source_snapshot':self.snapshot,'population':self.pop,'target_out':str(self.out),'source_out':str(self.root/'source'),'test_read':False,'scientific_acceptance':False,'model_sha256':self.model,'scorer':'frozen','file_count':1,'rows':1,'entries':[{'relative':self.rel,'data':self.data,'receipt':self.receipt}]})
        self.execution=self.put(self.out/'execution.json',{'out':str(self.out),'test_read':False,'scientific_acceptance':False,'resume_import':self.imp,'successor_guard':{'source_execution':self.source}})
        self.report=self.put(self.out/'results/selection_report.json',{'scientific_acceptance':False,'header':{'model':{'path':'adapter'}}})
        self.entry={'execution':self.execution['path'],'report':self.report['path'],'model':{'path':'adapter'}}
        self.acceptance={'schema':'independent-recovered-dev-result-acceptance-v1','verdict':'PASS','result_acceptance':True,'test_read':False,'scientific_acceptance':False,'execution_sha256':self.execution['sha256'],'report_sha256':self.report['sha256'],'files':dict(self.files),'rows':2,'imported_rows':1,'new_rows':1}
        self.review=self.put(self.root/'REVIEW.json',self.acceptance)
    def raw(self,p,b):
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);h=M.digest(p);self.files[str(p)]=h;return {'path':str(p),'sha256':h}
    def put(self,p,d):return self.raw(p,json.dumps(d,sort_keys=True).encode())
    def refresh_review(self):self.review=self.put(Path(self.review['path']),self.acceptance)
    def run_check(self):return M.verify_recovery(self.entry,self.files,self.review)
    def test_real_prefix_and_population(self):self.assertEqual(self.run_check()['rows'],2)
    def test_changed_original_payload_rejected(self):Path(self.data['path']).write_bytes(b'corrupt');self.assertRaises(ValueError,self.run_check)
    def test_foreign_execution_review_rejected(self):self.acceptance['execution_sha256']='f'*64;self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_foreign_report_review_rejected(self):self.acceptance['report_sha256']='f'*64;self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_test_authority_rejected(self):self.acceptance['test_read']=True;self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_missing_evidence_rejected(self):self.acceptance['files']={};self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_wrong_import_count_rejected(self):self.acceptance['imported_rows']=0;self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_wrong_new_count_rejected(self):self.acceptance['new_rows']=2;self.refresh_review();self.assertRaises(ValueError,self.run_check)
    def test_rehashed_prefix_corruption_rejected(self):
        rows=copy.deepcopy(self.rows);rows[0]['s']=[2,0];ref=self.raw(Path(self.output['path']),b''.join((json.dumps(x)+'\n').encode() for x in rows));self.acceptance['files'][ref['path']]=ref['sha256'];self.refresh_review();self.assertRaisesRegex(ValueError,'prefix differs',self.run_check)
    def test_rehashed_population_key_loss_rejected(self):
        ref=self.raw(Path(self.output['path']),(json.dumps(self.rows[0])+'\n').encode());self.acceptance['files'][ref['path']]=ref['sha256'];self.refresh_review();self.assertRaisesRegex(ValueError,'keys/count differ',self.run_check)
    def test_unexpected_readout_file_rejected(self):
        self.raw(self.out/'results/trackk/extra.jsonl',b'{}\n');self.assertRaisesRegex(ValueError,'population files differ',self.run_check)
    def test_review_pin_not_authenticated_rejected(self):
        review=dict(self.review,sha256='f'*64);self.assertRaises(ValueError,M.verify_recovery,self.entry,self.files,review)

if __name__=='__main__':unittest.main()
