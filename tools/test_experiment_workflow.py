import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings

S=Path(__file__).with_name('experiment_workflow.py')
spec=importlib.util.spec_from_file_location('workflow',S);W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.template=self.root/'template';self.template.mkdir();code=self.template/'code';code.mkdir();inp=self.template/'inputs';inp.mkdir()
        # CPU executable fixtures exercise real imports and child CLI contracts.
        runner=code/'bev_runner.py';runner.write_text("import json,pathlib\ndef verify(p,h): return json.loads(pathlib.Path(p).read_text())\nif __name__=='__main__': print('VERIFIED')\n")
        host=code/'bev_host.py';host.write_text("raise SystemExit('NPU fixture must never execute')\n")
        req=inp/'requests.jsonl';req.write_text(''.join(json.dumps({'id':str(i),'request':{}})+'\n' for i in range(6516)))
        ids=inp/'ids.json';ids.write_text(json.dumps([str(i) for i in range(6516)]))
        model=self.root/'model';model.mkdir();weights=model/'config.json';weights.write_text('{}')
        manifest=self.root/'manifest.json';manifest.write_text('{}');gold=self.root/'gold.jsonl';gold.write_text(req.read_text())
        prereg=self.template/'PREREGISTRATION.md';prereg.write_text('Frozen protocol\n')
        plan=dict(schema='bev-dev-plan-v1',scientific_acceptance=False,test_read=False,source_split='train_derived_dev',
                  run='r3_runs/old',container='nga-old',chip=6,out=str(self.template/'output'),model=str(model),
                  code={'host':W.pin(host),'runner':W.pin(runner)},inputs={'requests':W.pin(req),'ids':W.pin(ids)},
                  model_files={'config.json':W.pin(weights)},source_manifest=W.pin(manifest))
        self.pp=self.template/'plan.json';W.write(self.pp,plan)
        cpu=self.root/'template_cpu';cpu.mkdir();consumer=cpu/'consume.py'
        consumer.write_text("import json,pathlib\ndef verify_config(p,h): return json.loads(pathlib.Path(p).read_text())\ndef population(r,g,n):\n assert len(r)==len(g)==n\n return [x['id'] for x in r]\nif __name__=='__main__':\n import argparse,pathlib\n p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--sha256');a=p.parse_args();pathlib.Path(a.config).with_name('EXECUTED.json').write_text(json.dumps(vars(a)))\n")
        cc=dict(plan=str(self.pp),plan_sha256=W.E.digest(self.pp),gold=str(gold),files={str(p):W.E.digest(p) for p in [consumer,prereg,gold,manifest]})
        self.cp=cpu/'config.json';W.write(self.cp,cc)
        self.config=dict(schema=W.SCHEMA,template_plan=W.pin(self.pp),template_cpu=W.pin(self.cp),root=str(self.root/'new'),run='r3_runs/new',container='nga-new',chip=6)
        self.cfg=self.root/'prepare.json';W.write(self.cfg,self.config)

    def prepared(self):
        result=W.prepare(self.cfg,W.E.digest(self.cfg));return Path(result['prepared']['path'])

    def review_for(self,p):
        d=W.E.read_json(p);plan=W.E.read_json(W.E.pinned(d['plan']))
        hashes={d['plan']['path']:d['plan']['sha256']}
        for group in ('code','inputs','model_files'):hashes.update({x['path']:x['sha256'] for x in plan[group].values()})
        review=dict(activation_authorized=True,scientific_acceptance=False,approved_plan_sha256=d['plan']['sha256'],attempts=[1],hashes=hashes,
                    deployment_suitable=True,cpu_config_sha256=d['cpu']['sha256'],consumer_sha256=d['consumer']['sha256'])
        rp=self.root/'review.json';W.write(rp,review)
        return rp

    def bound(self):
        p=self.prepared();rp=self.review_for(p)
        a=W.bind(p,W.E.digest(p),rp,W.E.digest(rp),1)['activation'];return a

    def test_rejected_review_can_be_corrected_for_same_attempt(self):
        p=self.prepared();rp=self.review_for(p)
        good=W.E.read_json(rp);bad=dict(good,approved_plan_sha256='0'*64)
        rp.write_text(json.dumps(bad))
        destination=p.parent/'control/attempt-1'
        with self.assertRaisesRegex(ValueError,'activation review differs'):
            W.bind(p,W.E.digest(p),rp,W.E.digest(rp),1)
        self.assertFalse(destination.exists())
        self.assertEqual(list((p.parent/'control').glob('.bind-*')),[])
        rp.write_text(json.dumps(good))
        result=W.bind(p,W.E.digest(p),rp,W.E.digest(rp),1)
        W.load_activation(result['activation']['path'],result['activation']['sha256'])
        before={x.name:x.read_bytes() for x in destination.iterdir()}
        with self.assertRaises(FileExistsError):
            W.bind(p,W.E.digest(p),rp,W.E.digest(rp),1)
        self.assertEqual(before,{x.name:x.read_bytes() for x in destination.iterdir()})
        self.assertEqual(list((p.parent/'control').glob('.bind-*')),[])

    def test_prepare_real_imports_and_population_then_new_review(self):
        p=self.prepared();d=W.E.read_json(p)
        self.assertFalse(d['approved']);self.assertFalse((p.parent/'control/attempt-1').exists())
        plan=W.E.read_json(W.E.pinned(d['plan']));self.assertEqual(plan['run'],'r3_runs/new')
        self.assertEqual(plan['inputs']['requests']['sha256'],W.E.read_json(self.pp)['inputs']['requests']['sha256'])
        self.assertTrue(all('/new/inference/' in x['path'] for x in plan['code'].values()))

    def test_prepare_refuses_duplicate_directory(self):
        self.prepared()
        with self.assertRaisesRegex(ValueError,'output already exists'):W.prepare(self.cfg,W.E.digest(self.cfg))

    def test_changed_template_refused_before_output(self):
        self.pp.write_text('{}')
        with self.assertRaises(ValueError):self.prepared()
        self.assertFalse((self.root/'new').exists())

    def test_old_review_cannot_bind_new_plan(self):
        p=self.prepared();rp=self.root/'old-review.json';W.write(rp,dict(deployment_suitable=False))
        with self.assertRaisesRegex(ValueError,'CPU admission differs'):W.bind(p,W.E.digest(p),rp,W.E.digest(rp),1)

    def test_bound_real_cli_validate_dryrun_status(self):
        a=self.bound()
        for op in ('validate','dry-run','status'):
            r=subprocess.run([sys.executable,'-B','-P',str(S),op,'--config',a['path'],'--sha256',a['sha256']],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertFalse((self.root/'new/cpu/START_INTENT.json').exists())

    def test_mismatched_cpu_binding_rejected(self):
        a=self.bound();c=W.E.read_json(Path(a['path']));c['cpu']=W.pin(self.cp)
        q=self.root/'bad.json';W.write(q,c)
        with self.assertRaisesRegex(ValueError,'prepared CPU binding'):W.load_activation(q,W.E.digest(q))

    def test_existing_npu_attempt_refused_without_ssh(self):
        a=self.bound();(self.root/'new/inference/output/host_attempts/1').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'attempt already exists'):W.operate('start',a['path'],a['sha256'])

    def test_detached_cpu_fixture_and_uncertain_restart_refusal(self):
        a=self.bound()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='subprocess .* is still running', category=ResourceWarning)
            r=W.operate('start-cpu',a['path'],a['sha256'])
        self.assertEqual(r['status'],'consumer_started')
        # Wait for this short CPU fixture; no production polling or NPU.
        os.waitpid(r['pid'],0)
        cpu=self.root/'new/cpu';self.assertTrue((cpu/'EXECUTED.json').exists());self.assertTrue((cpu/'RELAUNCH.json').exists())
        with self.assertRaisesRegex(ValueError,'uncertain'):W.operate('start-cpu',a['path'],a['sha256'])

    def test_shell_field_and_invalid_chip_refused(self):
        for key,value in [('shell','echo unsafe'),('chip',True)]:
            c=dict(self.config);c[key]=value;p=self.root/(key+'.json');W.write(p,c)
            with self.assertRaises(ValueError):W.prepare(p,W.E.digest(p))


if __name__=='__main__':unittest.main()
