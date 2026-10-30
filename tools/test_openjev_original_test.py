import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

j=module('join_openjev_original_test');p=module('openjev_original_protocol');v=module('verify_reference_openjev')


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        c={'image':'image','base_id':'base','base_revision':'rev','max_length':4096,'temperature':1.5,'files':{}}
        for key in ('base','checkpoint','code'):
            path=root/key;path.mkdir();f=path/'file';f.write_text(key);c[key]=str(path);c['files'][str(f)]=v.sha(f)
        self.full=[{'id':str(i),'split':'test','group_id':'g'+str(i),'kind':'noul','source':'source',
                    'options':['no','yes'],'target':[0.,1.],'state':'same input '+str(i)} for i in range(3)]
        self.components=[]
        for name,rows in [('public',[self.full[0],self.full[2]]),('supplement',[self.full[1]])]:
            config=copy.deepcopy(c);config['out']=str(root/name);identity=v.object_sha(config);receipts=[]
            for i,row in enumerate(rows):
                value={'index':i,'id':row['id'],'identity':identity,'input_sha256':v.object_sha(row),
                       **{k:row[k] for k in ('options','target','source','kind','group_id')},
                       'logits':[0.,1.],'probabilities':v.probabilities([0.,1.],1.5)}
                receipts.append({'payload':value,'sha256':v.object_sha(value)})
            self.components.append({'name':name,'config':config,'rows':copy.deepcopy(rows),'receipts':receipts})
    def tearDown(self):self.tmp.cleanup()
    def join(self):return j.join_records(self.full,self.components,[2])
    def test_valid_join_and_metrics(self):
        joined=self.join();self.assertEqual([x['id'] for x in joined],['0','1','2'])
        self.assertEqual([x['component_index'] for x in joined],[0,0,1])
        result=j.summarize(self.full,joined,1.5);self.assertEqual(result['serving']['count'],3)
        self.assertEqual(result['serving']['accuracy'],1.)
    def test_wrong_model(self):
        self.components[1]['config']['base_revision']='wrong'
        with self.assertRaisesRegex(ValueError,'model protocol'):self.join()
    def test_wrong_temperature(self):
        self.components[1]['config']['temperature']=2.
        with self.assertRaisesRegex(ValueError,'model protocol'):self.join()
    def test_changed_code(self):
        Path(self.components[0]['config']['code'],'file').write_text('changed')
        with self.assertRaisesRegex(ValueError,'dependency changed'):self.join()
    def test_duplicate_input(self):
        self.full[2]=copy.deepcopy(self.full[0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.join()
    def test_missing_receipt(self):
        self.components[0]['receipts'].pop()
        with self.assertRaisesRegex(ValueError,'denominator'):self.join()
    def test_changed_payload(self):
        self.components[1]['receipts'][0]['payload']['logits'][0]=99
        with self.assertRaisesRegex(ValueError,'Changed receipt'):self.join()
    def test_hash_consistent_wrong_row(self):
        e=self.components[1]['receipts'][0];e['payload']['id']='wrong';e['sha256']=v.object_sha(e['payload'])
        with self.assertRaisesRegex(ValueError,'row/config'):self.join()
    def test_hash_consistent_wrong_config(self):
        e=self.components[1]['receipts'][0];e['payload']['identity']='wrong';e['sha256']=v.object_sha(e['payload'])
        with self.assertRaisesRegex(ValueError,'row/config'):self.join()
    def test_changed_original_payload(self):
        self.full[1]['state']='changed'
        with self.assertRaisesRegex(ValueError,'Supplement content'):self.join()
    def test_wrong_positions(self):
        with self.assertRaisesRegex(ValueError,'projection'):j.join_records(self.full,self.components,[1])
    def test_duplicate_positions(self):
        with self.assertRaisesRegex(ValueError,'positions'):j.join_records(self.full,self.components,[2,2])
    def test_wrong_probabilities(self):
        e=self.components[1]['receipts'][0];e['payload']['probabilities']=[.5,.5];e['sha256']=v.object_sha(e['payload'])
        with self.assertRaisesRegex(ValueError,'metric differs'):self.join()


if __name__=='__main__':unittest.main()

# Full file-backed audit -> join -> report/terminal integration. The test uses small
# synthetic populations in place of pinned production data; production has no bypass.
class JoinIntegrationTests(unittest.TestCase):
    def test_real_artifacts_and_forged_component(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        fixtures=module('test_verify_reference_openjev')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'p').mkdir();(root/'s').mkdir()
            a=fixtures.Fixture(root/'p');b=fixtures.Fixture(root/'s')
            # Rename the second component's input identities and rebuild every
            # dependent receipt/report/terminal; leave its prediction arithmetic intact.
            for row in b.rows:row['id']='supp-'+row['id'];row['group_id']='supp-'+row['group_id']
            Path(b.c['data']).write_text('\n'.join(json.dumps(x) for x in b.rows)+'\n')
            export=v.load(b.c['export_manifest']);export['configs']['release-v2-redistributable']['splits']['test']['raw_uncompressed_sha256']=v.sha(b.c['data'])
            fixtures.write(Path(b.c['export_manifest']),export)
            b.c['parent_config']=str(a.run/'config.json');b.refreeze();identity=v.object_sha(b.c)
            for i,row in enumerate(b.rows):
                for folder in [b.run,b.run/'lengths']:
                    path=folder/f'record-{i:06d}.json';e=v.load(path);value=e['payload']
                    value.update(id=row['id'],input_sha256=v.object_sha(row),identity=identity)
                    if folder==b.run:value['group_id']=row['group_id']
                    e['sha256']=v.object_sha(value);fixtures.write(path,e)
            for name in ['PREFLIGHT.json','report.json']:
                report=v.load(b.run/name);report.update(identity=identity,ordered_ids_sha256=v.object_sha([r['id'] for r in b.rows]));fixtures.write(b.run/name,report)
            for mode,name in [('preflight','PREFLIGHT.json'),('evaluate','report.json')]:
                path=b.run/(mode+'-COMPLETE.json');t=v.load(path);t.update(identity=identity,config_sha256=v.sha(b.run/'config.json'),outputs={name:v.sha(b.run/name)});fixtures.write(path,t)
                (b.run/(mode+'-EXIT')).write_text('rc=0 utc=2026-10-30T15:00:00Z\n')
            launch=v.load(b.run/'LAUNCH_RECEIPT.json');launch['config_sha256']=v.sha(b.run/'config.json');fixtures.write(b.run/'LAUNCH_RECEIPT.json',launch)
            full=root/'full.jsonl';full.write_text('\n'.join(json.dumps(x) for x in a.rows+b.rows)+'\n')
            restore=root/'restore.json';fixtures.write(restore,{'missing_public_rows':{'test':{'original_line_numbers':[3,4]}}})
            prereg=root/'prereg.md';prereg.write_text('synthetic integration fixture')
            out=root/'join';out.mkdir()
            plan={'out':str(out),'public_config':str(a.run/'config.json'),'supplement_config':str(b.run/'config.json'),
                  'original_data':str(full),'restoration_report':str(restore),'preregistration':str(prereg)}
            files=[Path(__file__).with_name(n+'.py').resolve() for n in ['join_openjev_original_test','verify_reference_openjev','verify_openjev_supplement','openjev_original_protocol','openjev_reference_finish']]
            files += [Path(plan[k]) for k in ['public_config','supplement_config','original_data','restoration_report','preregistration']]
            plan['files']={str(path):v.sha(path) for path in files};planpath=root/'plan.json';fixtures.write(planpath,plan)
            real_sibling=j.sibling
            def fixture_sibling(name):
                if name=='verify_openjev_supplement':return SimpleNamespace(verify=v.verify)
                return real_sibling(name)
            with patch.object(j.p,'FULL_SHA',v.sha(full)),patch.object(j,'sibling',fixture_sibling),patch.object(j,'verify_container'):
                result=j.execute(planpath)
                self.assertEqual(result['rows'],4);self.assertEqual(v.load(out/'JOIN_COMPLETE.json')['rc'],0)
                self.assertEqual(len(v.load(out/'joined-records.json')),4)
                # A hash-consistent forged native aggregate fails through the real
                # independent component audit before a new join report is published.
                b.mutate_report();new=root/'join_bad';new.mkdir();plan['out']=str(new);fixtures.write(planpath,plan)
                with self.assertRaisesRegex(ValueError,'metric differs'):j.execute(planpath)
                self.assertFalse((new/'report.json').exists())

class QueueTests(unittest.TestCase):
    def test_dependency_failure_does_not_cancel_other_size(self):
        from unittest.mock import patch
        q=module('openjev_supplement_queue')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json'
            plan.write_text(json.dumps({'out':str(root),'files':{},'entries':[{'name':'2B'},{'name':'9B'}]}))
            def dependency(entry,out):
                if entry['name']=='2B':raise ValueError('failed public dependency')
                return {'Id':'public9'}
            with patch.object(q,'dependency',side_effect=dependency),patch.object(q,'claim_launch',return_value='supp9') as launch,patch.object(q,'finish',return_value=True),patch.object(q.time,'sleep'),patch('sys.argv',['queue','--plan',str(plan)]):
                with self.assertRaises(SystemExit) as error:q.main()
                self.assertEqual(error.exception.code,1)
                self.assertEqual(launch.call_count,1)
            terminal=v.load(root/'QUEUE_COMPLETE.json')
            self.assertEqual(terminal['rc'],1)
            self.assertEqual(terminal['entries']['2B']['stage'],'failed')
            self.assertEqual(terminal['entries']['9B']['stage'],'complete')
    def test_existing_terminal_is_not_overwritten(self):
        from unittest.mock import patch
        q=module('openjev_supplement_queue')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json';plan.write_text(json.dumps({'out':str(root),'files':{},'entries':[]}))
            terminal=root/'QUEUE_COMPLETE.json';terminal.write_text('{"rc":0}')
            with patch('sys.argv',['queue','--plan',str(plan)]):
                with self.assertRaisesRegex(ValueError,'restart'):q.main()
            self.assertEqual(terminal.read_text(),'{"rc":0}')
