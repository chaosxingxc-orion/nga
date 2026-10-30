import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v=module('verify_reference_nimble');f=module('nimble_reference_finish')
class AuditTests(unittest.TestCase):
    def setUp(self):
        self.row={'id':'x','domain':'d','family':'f','split':'test','input':{'questions':{'decision':{'type':'noul','criteria':{'false':'no','true':'yes'}}}},'reference':{'target':True}}
        self.c={'model_id':'model','adapter_revision':'revision'}
        field={'value':True,'scores':{'false':.25,'true':.75},'logits':{'false':0.,'true':__import__('math').log(3)},'code_to_choice':{'A':False,'B':True},'candidate_token_ids':[32,33],'prompt_token_count':10,'prompt_token_sha256':'a'*64}
        self.result={'id':'x','type':'noul','domain':'d','family':'f','split':'test','reference':self.row['reference'],'student':v.assess(field['scores'],True,'noul'),'raw_student':{'model':'model','revision':'revision','temperature':1.,'fields':{'decision':field},'output':{'decision':True}},'elapsed_seconds':.1}
        self.payload={'id':'x','index':0,'input_sha256':v.stamp(self.row),'identity':'i','result':self.result}
    def verify(self):return v.verify_receipt({'payload':self.payload,'sha256':v.stamp(self.payload)},self.row,0,'i',self.c,{'A':32,'B':33})
    def test_valid(self):self.verify()
    def test_forged_student_rehashed(self):
        self.result['student']['correct']=False
        with self.assertRaisesRegex(ValueError,'student'):self.verify()
    def test_forged_output(self):
        self.result['raw_student']['output']['decision']=False
        with self.assertRaisesRegex(ValueError,'output'):self.verify()
    def test_candidate_order(self):
        field=self.result['raw_student']['fields']['decision'];field['scores']=dict(reversed(list(field['scores'].items())))
        with self.assertRaisesRegex(ValueError,'order'):self.verify()
    def test_foreign_index(self):
        self.payload['index']=1
        with self.assertRaisesRegex(ValueError,'index'):self.verify()
    def test_wrong_probability(self):
        self.result['raw_student']['fields']['decision']['scores']={'false':.5,'true':.5}
        with self.assertRaisesRegex(ValueError,'logit'):self.verify()
    def test_binary_vs_multiclass(self):
        m=v.assess({'false':.25,'true':.75},True,'noul');self.assertEqual(m['binary_brier'],.0625);self.assertEqual(m['multiclass_brier'],.125)
    def test_score_mae(self):
        m=v.assess({'0':.25,'1':.75},0,'score');self.assertEqual(m['absolute_score_error'],.75)
    def test_human_distribution(self):
        m=v.distribution_metrics({'a':1.,'b':0.},{'a':0.,'b':1.});self.assertEqual(m['jensen_shannon_bits'],1.);self.assertEqual(m['total_variation'],1.)
    def test_report_forgery(self):
        expected=v.aggregate([self.verify()]);forged=copy.deepcopy(expected);forged['summary']['all']['correct']=0
        with self.assertRaisesRegex(ValueError,'differs'):v.same(forged,expected)
    def test_ece_boundary_and_tie(self):
        r=copy.deepcopy(self.result);r['student']=v.assess({'false':.5,'true':.5},True,'noul');r['raw_student']['fields']['decision']['value']=False
        self.assertEqual(v.aggregate([r])['calibration']['ece10'],.5)
    def test_failed_wrapper_missing_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'EXIT').write_text('rc=1 utc=2026-10-30T00:00:00Z\n')
            with self.assertRaisesRegex(ValueError,'Wrapper'):f.completion_state(p,'hash')
    def test_missing_terminal_pending(self):
        with tempfile.TemporaryDirectory() as td:self.assertEqual(f.completion_state(Path(td),'hash'),'pending')
    def test_stale_wrapper(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'report.json').write_text('{}');(p/'COMPLETE.json').write_text(json.dumps({'rc':0,'stage':'completed','config_sha256':'h','outputs':{'report.json':v.sha(p/'report.json')}}));(p/'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n');os.utime(p/'EXIT',ns=(1,1))
            with self.assertRaisesRegex(ValueError,'Stale'):f.completion_state(p,'h')
class CompleteArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name);p=self.p
        for name in ('base','adapter','code'): (p/name).mkdir()
        def write(path,obj):path.write_text(json.dumps(obj));return path
        self.write=write
        (p/'base/.complete').write_text(v.BASE_REVISION+'\n');(p/'adapter/adapter_model.safetensors').write_text('fixture')
        write(p/'adapter/tokenizer.json',{'model':{'vocab':{'A':32,'B':33}}})
        for n in ('nimble_reference_eval.py','test_nimble_reference_eval.py','launch.sh','run.sh','LAUNCH_EXACT.sh','PREREGISTRATION.md'):(p/n).write_text('fixture')
        self.c={'out':str(p),'base':str(p/'base'),'adapter':str(p/'adapter'),'code':str(p/'code'),'base_revision':v.BASE_REVISION,'container':'fixture-container','physical_chip':3,'adapter_revision':v.REVISION,'model_id':'model','image':'image','suites':[]}
        self.inputs={}
        for name,count in v.COUNTS.items():
            folder=p/name;folder.mkdir();rows=[]
            for i in range(count):rows.append({'id':f'{i:06d}','domain':name,'family':str(i),'split':'test','input':{'questions':{'decision':{'type':'noul','criteria':{'false':'no','true':'yes'}}}},'reference':{'target':True}})
            data=p/(name+'.jsonl');data.write_text(''.join(json.dumps(r)+'\n' for r in rows));manifest=p/(name+'.manifest.json');write(manifest,{'count':count,'ids':[r['id'] for r in rows],'dataset_sha256':v.sha(data)})
            self.c['suites'].append({'name':name,'count':count,'data':str(data),'manifest':str(manifest),'dataset_sha256':v.sha(data)});self.inputs[name]=rows
        original_sha=v.sha
        self.sha_patch=patch.object(v,'sha',lambda path:v.ADAPTER_SHA if str(path)==str(p/'adapter/adapter_model.safetensors') else original_sha(path));self.sha_patch.start();self.addCleanup(self.sha_patch.stop)
        self.c['files']={f:v.sha(f) for f in v.required_files(self.c)};write(p/'config.json',self.c);ident=v.stamp(self.c)
        self.reports={}
        for suite in self.c['suites']:
            name=suite['name'];results=[]
            for i,row in enumerate(self.inputs[name]):
                case=AuditTests();case.setUp();r=copy.deepcopy(case.result);r.update({k:row[k] for k in ('id','domain','family','split','reference')});r['raw_student']['revision']=v.REVISION
                item={'id':row['id'],'index':i,'identity':ident,'input_sha256':v.stamp(row),'result':r};write(p/name/f'{i:06d}.json',{'payload':item,'sha256':v.stamp(item)});results.append(r)
            report=v.aggregate(results);report.update(dataset_sha256=suite['dataset_sha256'],identity=ident);write(p/name/'report.json',report);self.reports[name]=report
        write(p/'PREFLIGHT.json',{'identity':ident,'rows':1884,'max_tokens':10,'suite_counts':v.COUNTS})
        write(p/'report.json',{'identity':ident,'rows':1884,'suites':self.reports})
        write(p/'LAUNCH_RECEIPT.json',{'config_sha256':v.sha(p/'config.json'),'wrapper_sha256':v.sha(p/'run.sh'),'image':'image','container_id':'fixture-id','command':['bash','run.sh'],'entrypoint':None})
        self.rebind()
    def rebind(self):
        p=self.p;self.write(p/'COMPLETE.json',{'rc':0,'error':None,'identity':v.stamp(self.c),'config_sha256':v.sha(p/'config.json'),'stage':'completed','progress':1884,'total':1884,'outputs':{n:v.sha(p/n) for n in ('report.json','PREFLIGHT.json')}});(p/'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
    def test_complete_artifacts(self):self.assertEqual(v.verify(self.p/'config.json')['records_verified'],1884)
    def test_missing_receipt(self):
        (self.p/'paws/000001.json').unlink()
        with self.assertRaisesRegex(ValueError,'coverage'):v.verify(self.p/'config.json')
    def test_extra_receipt(self):
        self.write(self.p/'paws/999999.json',{})
        with self.assertRaisesRegex(ValueError,'coverage'):v.verify(self.p/'config.json')
    def test_forged_final_report_rehashed(self):
        p=self.p;report=v.load(p/'report.json');report['suites']['paws']['summary']['all']['accuracy']=.5;self.write(p/'report.json',report);self.rebind()
        with self.assertRaisesRegex(ValueError,'accuracy'):v.verify(p/'config.json')
    def test_wrong_base_revision(self):
        self.c['base_revision']='other-revision'
        self.write(self.p/'config.json',self.c)
        with self.assertRaisesRegex(ValueError,'Base revision'):v.verify(self.p/'config.json')
    def test_flags_include_metrics_identical_and_small_domain(self):
        report=copy.deepcopy(self.reports['paws'])
        report['calibration']['ece10']=0.
        report['by_domain']['tiny']={'all':{'count':2,'accuracy':.5}}
        flags=v.review_flags({'paws':report,'aegis2':report},self.p)
        self.assertTrue(any(f['reason']=='extreme_metric' and '/calibration/ece10' in f['pointer'] for f in flags))
        self.assertTrue(any(f['reason']=='identical_metric_across_suites' and f['metric']=='ece10' for f in flags))
        self.assertTrue(any(f['reason']=='small_count' and '/by_domain/tiny/' in f['pointer'] for f in flags))
        self.assertFalse(any(f['reason']=='identical_metric_across_suites' for f in v.review_flags({'paws':report},self.p)))
    def test_dependency_omission(self):
        del self.c['files'][str(self.p/'run.sh')];self.write(self.p/'config.json',self.c)
        with self.assertRaisesRegex(ValueError,'dependency missing'):v.verify(self.p/'config.json')

if __name__=='__main__':unittest.main()
