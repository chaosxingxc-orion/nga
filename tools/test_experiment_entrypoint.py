import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name('experiment_entrypoint.py')
spec = importlib.util.spec_from_file_location('entry', SOURCE)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        code = self.root / 'code'; code.mkdir()
        # Real subprocess CLI fixtures validate argument shape; no NPU execution.
        runner = code / 'bev_runner.py'
        runner.write_text("import argparse\np=argparse.ArgumentParser();p.add_argument('op',choices=['verify']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.parse_args();print('VERIFIED')\n")
        host = code / 'bev_host.py'
        host.write_text("import argparse,json\np=argparse.ArgumentParser();p.add_argument('op',choices=['start']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--review',required=True);p.add_argument('--review-sha256',required=True);p.add_argument('--attempt',required=True);a=p.parse_args();print(json.dumps(vars(a)))\n")
        inp = self.root / 'requests.json'; inp.write_text('{}')
        model = self.root / 'weights'; model.write_bytes(b'weights')
        pin = lambda p: {'path': str(p), 'sha256': E.digest(p)}
        self.plan = {'schema':'bev-dev-plan-v1','scientific_acceptance':False,'test_read':False,
                     'source_split':'train_derived_dev', 'out':str(self.root/'output'),
                     'code':{'host':pin(host),'runner':pin(runner)},
                     'inputs':{'requests':pin(inp)},'model_files':{'weights':pin(model)}}
        self.plan_path = self.root/'plan.json'; self.write(self.plan_path,self.plan)
        self.review = {'activation_authorized':True,'scientific_acceptance':False,
                       'approved_plan_sha256':E.digest(self.plan_path),'attempts':[1],
                       'hashes':{str(self.plan_path):E.digest(self.plan_path)}}
        for group in ('code','inputs','model_files'):
            self.review['hashes'].update({x['path']:x['sha256'] for x in self.plan[group].values()})
        self.review_path=self.root/'review.json'; self.write(self.review_path,self.review)
        self.config={'schema':E.SCHEMA,'kind':'bev-dev-v1','plan':pin(self.plan_path),
                     'review':pin(self.review_path),'attempt':1}
        self.config_path=self.root/'config.json'; self.save()

    def write(self,path,obj): path.write_text(json.dumps(obj))
    def save(self): self.write(self.config_path,self.config)
    def review_save(self):
        self.write(self.review_path,self.review)
        self.config['review']['sha256']=E.digest(self.review_path);self.save()

    def test_real_cli_validate_dry_run_and_start_contract(self):
        for op in ('validate','dry-run','start'):
            args=[sys.executable,'-B','-P',str(SOURCE),op,'--config',str(self.config_path),
                  '--config-sha256',E.digest(self.config_path)]
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(result.stdout)
            self.assertNotEqual(data['status'],'rejected')
        self.assertFalse((self.root/'output').exists())

    def test_changed_model_rejected(self):
        (self.root/'weights').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'pinned content changed'):E.execute('dry-run',self.config_path)

    def test_unapproved_attempt_rejected(self):
        self.config['attempt']=2;self.save()
        with self.assertRaisesRegex(ValueError,'attempt not approved'):E.execute('dry-run',self.config_path)

    def test_changed_config_and_unpinned_start_rejected(self):
        with self.assertRaisesRegex(ValueError,'requires --config-sha256'):E.execute('start',self.config_path)
        with self.assertRaisesRegex(ValueError,'config SHA256 differs'):E.execute('start',self.config_path,'0'*64)

    def test_unsupported_command_field_rejected(self):
        self.config['shell']='echo unsafe';self.save()
        with self.assertRaisesRegex(ValueError,'config fields differ'):E.execute('dry-run',self.config_path)

    def test_review_must_bind_all_executed_code(self):
        del self.review['hashes'][self.plan['code']['host']['path']];self.review_save()
        with self.assertRaisesRegex(ValueError,'outside review'):E.execute('dry-run',self.config_path)

    def test_review_identity_and_scope_rejected(self):
        self.review['scientific_acceptance']=True;self.review_save()
        with self.assertRaisesRegex(ValueError,'activation review differs'):E.execute('dry-run',self.config_path)

    def test_existing_attempt_refuses_start(self):
        (self.root/'output/host_attempts/1').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'attempt already exists'):
            E.execute('start',self.config_path,E.digest(self.config_path))

    def test_status_is_not_false_success(self):
        self.assertEqual(E.execute('status',self.config_path)['status'],'not_started_or_no_receipts')
        host=self.root/'output/host_attempts/1';host.mkdir(parents=True)
        self.write(host/'LAUNCH_RECEIPT.json',{'container_id':'id'})
        self.assertEqual(E.execute('status',self.config_path)['status'],'launched_live_state_not_checked')
        self.write(host/'EXIT.json',{'exit_code':1})
        self.assertEqual(E.execute('status',self.config_path)['status'],'failed_or_needs_reconciliation')

    def test_symlink_and_relative_path_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.config_path)
        for p in (alias,Path('relative.json')):
            with self.assertRaises(ValueError):E.execute('dry-run',p)

    def test_bool_attempt_rejected(self):
        self.config['attempt']=True;self.save()
        with self.assertRaisesRegex(ValueError,'positive integer'):E.execute('dry-run',self.config_path)


class NativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.marker = self.root / 'started.json'
        host = self.root / 'bev_native_config_host.py'
        host.write_text("import json,os,sys\nfrom pathlib import Path\nassert os.environ.get('NGA_RUNTIME_SENTINEL')=='configured'\nif sys.argv[1]=='start': Path(" + repr(str(self.marker)) + ").write_text(json.dumps({'python':sys.executable,'sentinel':os.environ['NGA_RUNTIME_SENTINEL']}))\nprint('OK')\n")
        runtime = self.root / 'runtime.py'; runtime.write_text('# fixture\n')
        pin = lambda p: {'path': str(p), 'sha256': E.digest(p)}
        self.plan = {'schema':'native-config-execution-v1','test_read':False,'scientific_acceptance':False,
                     'modules':{'host':pin(host),'runtime':pin(runtime)}, 'files':{str(host):E.digest(host),str(runtime):E.digest(runtime)},
                     'out':str(self.root/'output')}
        self.pp = self.root/'PLAN.json'; self.pp.write_text(json.dumps(self.plan))
        self.review = {'verdict':'PASS','activation_authorized':True,'scientific_acceptance':False,'test_read':False,
                       'approved_plan_sha256':E.digest(self.pp),'attempts':[1],'hashes':self.plan['files']}
        self.rp=self.root/'REVIEW.json';self.rp.write_text(json.dumps(self.review))
        self.config = {'schema':E.RUNTIME_SCHEMA,'kind':'native-config-dev-v1','plan':pin(self.pp),'review':pin(self.rp),'attempt':1,
                       'host_runtime':{'python':str(Path(sys.executable).resolve()),'environment':{'PYTHONDONTWRITEBYTECODE':'1','NGA_RUNTIME_SENTINEL':'configured'},'imports':['json']}}
        self.cp=self.root/'ENTRY.json'; self.save()
    def save(self):self.cp.write_text(json.dumps(self.config))
    def test_same_configured_runtime_preflight_and_start_real_subprocess(self):
        result=E.execute('start',self.cp,E.digest(self.cp))
        self.assertEqual(result['status'],'guarded_start_returned')
        actual=json.loads(self.marker.read_text());self.assertEqual(actual['sentinel'],'configured')
        self.assertEqual(Path(actual['python']).resolve(),Path(self.config['host_runtime']['python']))
        commands=E.commands(self.config,self.plan)
        self.assertTrue(all(c[:3]==[self.config['host_runtime']['python'],'-B','-P'] for c in commands.values()))
    def test_missing_dependency_fails_before_start_mutation(self):
        self.config['host_runtime']['imports']=['nga_deliberately_missing_dependency_20261104'];self.save()
        with self.assertRaisesRegex(ValueError,'imports failed before start'):
            E.execute('start',self.cp,E.digest(self.cp))
        self.assertFalse(self.marker.exists());self.assertFalse((self.root/'output').exists())
    def test_wrong_python_fails_before_start_mutation(self):
        self.config['host_runtime']['python']=str(self.root/'absent-python');self.save()
        with self.assertRaises(FileNotFoundError):E.execute('start',self.cp,E.digest(self.cp))
        self.assertFalse(self.marker.exists());self.assertFalse((self.root/'output').exists())
    def test_dependency_cannot_be_injected_as_code(self):
        self.config['host_runtime']['imports']=["json; __import__('os').system('false')"];self.save()
        with self.assertRaisesRegex(ValueError,'invalid host imports'):E.execute('start',self.cp,E.digest(self.cp))
        self.assertFalse(self.marker.exists())
    def test_native_scope_does_not_admit_test_or_unreviewed_code(self):
        self.review['hashes']={};self.rp.write_text(json.dumps(self.review));self.config['review']['sha256']=E.digest(self.rp);self.save()
        with self.assertRaisesRegex(ValueError,'outside review'):E.execute('dry-run',self.cp,E.digest(self.cp))


if __name__=='__main__': unittest.main()
