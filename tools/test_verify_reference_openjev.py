import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest


def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v=module('verify_reference_openjev');f=module('openjev_reference_finish')


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj))


class Fixture:
    def __init__(self,root):
        self.run=root/'run';r=self.run;r.mkdir();self.c={'out':str(r),'code':str(root/'code'),'base':str(root/'base'),
            'checkpoint':str(root/'checkpoint'),'data':str(root/'test.jsonl'),'export_manifest':str(root/'export.json'),
            'preregistration':str(r/'PREREGISTRATION.md'),'expected_rows':2,'hard_count':1,'max_length':4096,
            'base_id':'base','base_revision':'revision','temperature':1.5,'image':'image','physical_chip':2,
            'container':'test','files':{}}
        c=self.c
        for key in ('code','base','checkpoint'):Path(c[key]).mkdir()
        Path(c['base'],'.complete').write_text('revision\n')
        Path(c['code'],'model.py').write_text('# fixture')
        write(Path(c['checkpoint'])/'model.json',{'model_id':'base','revision':'revision','max_length':4096})
        write(Path(c['checkpoint'])/'temperature.json',{'temperature':1.5})
        for n in ('PREREGISTRATION.md','openjev_reference_eval.py','launch.sh','preflight.sh','evaluate.sh',
                  'PREFLIGHT_EXACT.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'):(r/n).write_text('# fixture')
        self.rows=[{'id':'a','group_id':'a','split':'test','source':'s1','kind':'noul','options':['no','yes'],'target':[0,1]},
                   {'id':'b','group_id':'b','split':'test','source':'s2','kind':'choice','options':['first','second'],'target':[.25,.75]}]
        Path(c['data']).write_text('\n'.join(json.dumps(x) for x in self.rows)+'\n')
        write(Path(c['export_manifest']),{'configs':{'release-v2-redistributable':{'splits':{'test':{
            'raw_uncompressed_sha256':v.sha(c['data']),'count':2,'sources':{'s1':1,'s2':1},'kinds':{'noul':1,'choice':1}}}}}})
        self.refreeze()
        identity=v.object_sha(c);values=[]
        for i,row in enumerate(self.rows):
            name=f'record-{i:06d}.json';logits=[0,1] if i==0 else [1,0];lengths=[4] if i==0 else [3,4]
            identity_fields={'index':i,'id':row['id'],'input_sha256':v.object_sha(row),'identity':identity}
            payload={**identity_fields,**{k:row[k] for k in ('options','target','source','kind','group_id')},
                     'logits':logits,'probabilities':v.probabilities(logits,1.5),'input_tokens':sum(lengths),'seconds':.1}
            write(r/name,{'payload':payload,'sha256':v.object_sha(payload)});values.append(payload)
            lp={**identity_fields,'lengths':lengths};write(r/'lengths'/name,{'payload':lp,'sha256':v.object_sha(lp)})
        pre={'identity':identity,'rows':2,'max_length':4096,'maximum_candidate_tokens':4,'candidate_prompts':3,
             'overlength_rows':0,'overlength_candidates':0,'overlength':[],'ordered_ids_sha256':v.object_sha(['a','b']),
             'status':'ready','test_inference_performed':False}
        write(r/'PREFLIGHT.json',pre)
        report={'identity':identity,'total_count':2,'hard_count':1,'soft_count':1,'failed_count':0,'serving_temperature':1.5,
                'ordered_ids_sha256':v.object_sha(['a','b']),'tie_count':0}
        def metric(indices,temp):return v.metrics([self.rows[i]['target'] for i in indices],[v.probabilities(values[i]['logits'],temp) for i in indices])
        report.update(serving=metric([0,1],1.5),raw_T1=metric([0,1],1),by_source_serving={'s1':metric([0],1.5),'s2':metric([1],1.5)},
                      by_kind_serving={'noul':metric([0],1.5),'choice':metric([1],1.5)})
        write(r/'report.json',report)
        for mode,output,stage in [('preflight','PREFLIGHT.json','ready'),('evaluate','report.json','complete')]:
            write(r/(mode+'-COMPLETE.json'),{'rc':0,'error':None,'identity':identity,'config_sha256':v.sha(r/'config.json'),
                'stage':stage,'outputs':{output:v.sha(r/output)},'progress':2,'total':2})
            (r/(mode+'-EXIT')).write_text('rc=0 utc=2026-10-30T15:00:00Z\n')
        write(r/'LAUNCH_RECEIPT.json',{'config_sha256':v.sha(r/'config.json'),'wrapper_sha256':v.sha(r/'evaluate.sh'),
             'image':'image','command':['bash',str(r/'evaluate.sh')],'entrypoint':None,'container_id':'id'})
    def refreeze(self):
        self.c['files']={p:v.sha(p) for p in v.required_files(self.c)};write(self.run/'config.json',self.c)
    def verify(self):return v.verify(self.run/'config.json')
    def mutate_report(self):
        r=self.run;report=v.load(r/'report.json');report['serving']['accuracy']=.25;write(r/'report.json',report)
        term=v.load(r/'evaluate-COMPLETE.json');term['outputs']['report.json']=v.sha(r/'report.json');write(r/'evaluate-COMPLETE.json',term)
        (r/'evaluate-EXIT').write_text('rc=0 utc=2026-10-30T15:00:00Z\n')


class AuditTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.fixture=Fixture(Path(self.temp.name))
    def tearDown(self):self.temp.cleanup()
    def test_complete(self):
        result=self.fixture.verify();self.assertEqual(result['records_verified'],2);self.assertTrue(result['review_flags'])
    def test_actual_verifier_cli(self):
        r=self.fixture.run;out=r/'AUDIT.json'
        command=[sys.executable,'-I',str(Path(__file__).with_name('verify_reference_openjev.py')),
                 '--config',str(r/'config.json'),'--out',str(out)]
        first=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stderr);self.assertEqual(v.load(out)['records_verified'],2)
        out.unlink();self.fixture.mutate_report()
        second=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(second.returncode,0);self.assertFalse(out.exists())
    def test_missing_row(self):
        (self.fixture.run/'record-000001.json').unlink()
        with self.assertRaisesRegex(ValueError,'coverage'):self.fixture.verify()
    def test_extra_row(self):
        (self.fixture.run/'record-000002.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'coverage'):self.fixture.verify()
    def test_duplicate_receipt_identity(self):
        r=self.fixture.run;(r/'record-000001.json').write_bytes((r/'record-000000.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'identity/order'):self.fixture.verify()
    def test_candidate_order(self):
        p=self.fixture.run/'record-000001.json';x=v.load(p);x['payload']['options'].reverse();x['sha256']=v.object_sha(x['payload']);write(p,x)
        with self.assertRaisesRegex(ValueError,'identity/order'):self.fixture.verify()
    def test_forged_hash_consistent_report(self):
        self.fixture.mutate_report()
        with self.assertRaisesRegex(ValueError,'metric differs'):self.fixture.verify()
    def test_omitted_executable_dependency(self):
        c=self.fixture.c;del c['files'][str(self.fixture.run/'evaluate.sh')];write(self.fixture.run/'config.json',c)
        with self.assertRaisesRegex(ValueError,'dependency omitted'):self.fixture.verify()
    def test_wrong_model_tokens(self):
        p=self.fixture.run/'record-000001.json';x=v.load(p);x['payload']['input_tokens']=100;x['sha256']=v.object_sha(x['payload']);write(p,x)
        with self.assertRaisesRegex(ValueError,'token count'):self.fixture.verify()
    def test_stale_wrapper(self):
        os.utime(self.fixture.run/'evaluate-EXIT',ns=(1,1))
        with self.assertRaisesRegex(ValueError,'stale'):self.fixture.verify()
    def test_failed_terminal(self):
        p=self.fixture.run/'evaluate-COMPLETE.json';x=v.load(p);x['rc']=1;write(p,x)
        with self.assertRaisesRegex(ValueError,'failed terminal'):self.fixture.verify()
    def test_error_marker(self):
        (self.fixture.run/'ERROR.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'failure conflicts'):self.fixture.verify()
    def test_wrong_probability_with_valid_hash(self):
        p=self.fixture.run/'record-000001.json';x=v.load(p);x['payload']['probabilities']=[.5,.5];x['sha256']=v.object_sha(x['payload']);write(p,x)
        with self.assertRaisesRegex(ValueError,'metric differs'):self.fixture.verify()
    def test_hard_soft_known_values(self):
        r=v.metrics([[0,1],[.25,.75]],[[.25,.75],[.75,.25]])
        self.assertEqual(r['count'],2);self.assertEqual(r['hard_count'],1);self.assertEqual(r['accuracy'],1)
        self.assertEqual(r['expected_accuracy'],.625);self.assertEqual(r['brier'],.3125);self.assertEqual(r['expected_brier'],.5)
        self.assertEqual(r['multiclass_ece'],.125);self.assertIsNone(r['coverage'][-1]['accuracy'])
    def test_ece_boundary_tie_and_one(self):
        r=v.metrics([[1,0],[0,1],[1,0]],[[.5,.5],[1,0],[.6,.4]])
        self.assertAlmostEqual(r['accuracy'],2/3);self.assertAlmostEqual(r['multiclass_ece'],(.5+1+.4)/3)
        soft=v.metrics([[.5,.5]],[[.5,.5]]);self.assertIsNone(soft['accuracy']);self.assertEqual(soft['expected_accuracy'],.5)
    def test_finisher_states(self):
        c=self.fixture.c;r=self.fixture.run;receipt=v.load(r/'LAUNCH_RECEIPT.json')
        info={'Id':'id','Image':'image','Config':{'Cmd':receipt['command'],'Entrypoint':None},
              'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci2'}]},'State':{'Status':'running','ExitCode':0}}
        self.assertEqual(f.inspect_state(info,receipt,c),'pending');info['State']['Status']='exited'
        self.assertEqual(f.inspect_state(info,receipt,c),'exited');self.assertEqual(f.completion_state(r,v.sha(r/'config.json')),'ready')
        info['State']['ExitCode']=1
        with self.assertRaisesRegex(ValueError,'terminal failure'):f.inspect_state(info,receipt,c)
        info['Id']='other'
        with self.assertRaisesRegex(ValueError,'identity'):f.inspect_state(info,receipt,c)


if __name__=='__main__':unittest.main()
