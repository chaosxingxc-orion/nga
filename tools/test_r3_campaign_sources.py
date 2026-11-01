"""Real frozen identity/manifest checks, synthetic reconstruction boundary.

No real datasets or model inference. Full report rebuilding already has its own
source/population tests; these tests exercise all-member composition and byte
binding, and independently import the exact frozen module API in a new process.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
FROZEN=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2')
s=importlib.util.spec_from_file_location('sources_test',HERE/'r3_campaign_sources.py')
S=importlib.util.module_from_spec(s);s.loader.exec_module(S)


class Sources(unittest.TestCase):
    def setUp(self):
        if not FROZEN.exists(): self.skipTest('actual frozen code absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        context=patch.dict(sys.modules);context.start();self.addCleanup(context.stop)
        paths=list(sys.path);self.addCleanup(lambda:sys.path.__setitem__(slice(None),paths))
        # Run these tests as a fresh discover process, as required in production.
        R=S.module(HERE/'r3_selection_report.py','source_test_report')
        self.deps=R.modules(FROZEN/'r3_code');self.E=self.deps[1]
        self.base=self.root/'Qwen__Qwen3.5-0.8B-Base';self.instruct=self.root/'Qwen__Qwen3.5-0.8B'
        self.patches=[]
        for key,value in [('BASE',str(self.base)),('INSTRUCT',str(self.instruct))]:
            p=patch.object(S.K,key,value);p.start();self.addCleanup(p.stop)
        self.inventory={}
        self.write('KEV/manifest',{'synthetic':True});self.write('manifest',{'synthetic':True})
        for model in (self.base,self.instruct):
            model.mkdir();(model/'weights.safetensors').write_bytes(model.name.encode());(model/'.complete').write_text(model.name)
            inv=S.M.capture(str(model));self.inventory[str(model)]=self.write(model.name+'-inventory',{'inventory':inv,'inventory_sha256':S.M.identity(inv)})
        self.entries=[];self.rebuilt={}
        for i,(arm,seed,base) in enumerate([('K1',2,self.base),('K1',3,self.base),('K0',None,self.base),('K0',None,self.instruct),('K1-QO',2,self.base),('K1-PT',2,self.instruct),('K1-PT',3,self.instruct)]):
            adapter=None
            if seed is not None:
                train=self.root/('train'+str(i));adapter=train/'adapter';adapter.mkdir(parents=True)
                (adapter/'adapter_model.safetensors').write_bytes(str(i).encode());(adapter/'adapter_config.json').write_text('{}')
                manifest={'arm':'k1','model_path':str(base),'args':{'arm':'k1','seed':seed,'out':str(train),'drop_state':arm=='K1-QO'},'kernel':'ref','total_steps':3116,'summary':{'final_step':3116}}
                self.write('train'+str(i)+'/manifest',manifest)
            identity=self.E.TL.model_identity(str(base),str(adapter) if adapter else None,str(self.root/('cache'+str(i))))
            identity={k:identity[k] for k in ('path','sha256','kind','base_path','base_revision')}
            header={'arm':arm,'model':identity,'stages':'k_score,t_score','partitions':['dev','calibration'],'track_t_config':'r3','primary_input_mode':'drop' if arm=='K1-QO' else 'full','data_files':{}}
            report={'schema':'r3-selection-report-v1','header':header,'scientific_acceptance':False,'selection_evidence':{}}
            if seed is not None:report['selection_evidence']=self.E.train_identity(report)
            entry={'report':self.write('eval'+str(i)+'/selection_report',report),'base_inventory':self.inventory[str(base)],'adapter_inventory':None}
            if adapter:
                inv=S.M.capture(str(adapter));entry['adapter_inventory']=self.write('adapter-inventory'+str(i),{'inventory':inv,'inventory_sha256':S.M.identity(inv)})
            self.write('eval'+str(i)+'/SCORING_RECEIPT.track_kt',{'header':header})
            self.write('eval'+str(i)+'/RUN_IDENTITY',{'synthetic':True})
            self.write('eval'+str(i)+'/EVAL_COMPLETE.track_kt',{'exit_code':0})
            self.write('eval'+str(i)+'/manifests/main',{'synthetic':True})
            for directory in ('trackk','trackt'):
                (self.root/('eval'+str(i))/directory).mkdir()
                (self.root/('eval'+str(i))/directory/'readout.jsonl').write_text('{}\n')
            self.entries.append(entry);self.rebuilt[str(Path(entry['report']['path']).parent)]=copy.deepcopy(report)
        self.report_tool=SimpleNamespace(rebuild=lambda run,kev,data,deps:copy.deepcopy(self.rebuilt[str(run)]))
    def write(self,name,value):
        p=self.root/(name+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
        return {'path':str(p),'sha256':S.sha(p)}
    def rebuild(self,entry):
        return S.rebuild_member(entry,self.report_tool,self.deps,str(self.root/'KEV'),str(self.root),{'synthetic':True})
    def test_seven_real_identity_and_training_members_reconstruct(self):
        pairs=[self.rebuild(e) for e in self.entries]
        campaign={'schema':'r3-final-campaign-v1','size':'0.8B','selected_arm':'K1','members':[p[0] for p in pairs]}
        result=S.K.verify(campaign)
        self.assertTrue(result['membership_complete']);self.assertFalse(result['scientific_acceptance'])
        for member,evidence in pairs:self.assertEqual(member['verified_evidence_sha256'],S.digest(evidence))
    def request(self):
        return {'schema':'r3-campaign-sources-request-v1','selected_arm':'K1','members':self.entries,
                 'report_tool':{'path':str(HERE/'r3_selection_report.py'),'sha256':S.sha(HERE/'r3_selection_report.py')},
                 'closure_manifest':{'path':str(FROZEN/'manifest.json'),'sha256':S.sha(FROZEN/'manifest.json')},
                 'kev_dir':str(self.root/'KEV'),'data_root':str(self.root)}
    def test_request_returns_engineering_evidence_without_eligibility(self):
        self.report_tool.modules=lambda root:self.deps
        with patch.object(S,'module',return_value=self.report_tool): result=S.verify(self.request())
        self.assertEqual(len(result['sources']),7)
        self.assertFalse(result['scientific_acceptance']);self.assertFalse(result['publication_authorized'])
        self.assertFalse(result['test_read']);self.assertNotIn('eligibility',result)
        first=result['sources'][0]['source_snapshot']
        self.assertIn(str(self.root/'eval0/trackk/readout.jsonl'),first['files'])
        self.assertIn(str(self.root/'eval0/manifests/main.json'),first['files'])
        self.assertIn(str(self.base),first['models'])
    def test_redirected_code_closure_refused_before_loader_or_reconstruction(self):
        a=self.root/'closure-a';b=self.root/'closure-b';a.mkdir();b.mkdir()
        (b/'r3_code').mkdir();(b/'r0_code').mkdir()
        (a/'manifest.json').write_text(json.dumps({'code':{'fixture':{}}}))
        request=self.request();request['closure_manifest']={'path':str(a/'manifest.json'),'sha256':S.sha(a/'manifest.json')}
        for name in ('r3_code','r0_code'):
            other='r0_code' if name=='r3_code' else 'r3_code'
            (a/name).symlink_to(b/name,target_is_directory=True);(a/other).mkdir()
            with self.subTest(child=name),patch.object(S,'module') as loader,patch.object(S,'rebuild_member') as rebuild:
                with self.assertRaisesRegex(ValueError,'nonsymlink'):S.verify(request)
                loader.assert_not_called();rebuild.assert_not_called()
            (a/name).unlink();(a/other).rmdir()
    def test_alternate_manifest_refused_before_loader_or_reconstruction(self):
        request=self.request()
        alternate=self.root/'approved.json';alternate.write_text(json.dumps({'code':{'fixture':{}}}))
        request['closure_manifest']={'path':str(alternate),'sha256':S.sha(alternate)}
        with patch.object(S,'module') as loader,patch.object(S,'rebuild_member') as rebuild:
            with self.assertRaisesRegex(ValueError,'canonical manifest.json'):S.verify(request)
            loader.assert_not_called();rebuild.assert_not_called()
    def test_later_member_cannot_hide_earlier_source_changes(self):
        paths=['train0/adapter/adapter_model.safetensors','eval0/selection_report.json',
               'eval0/trackk/readout.jsonl','eval0/manifests/main.json',
               'eval0/RUN_IDENTITY.json','eval0/EVAL_COMPLETE.track_kt.json',
               'KEV/manifest.json','train0/manifest.json']
        original=S.rebuild_member;self.report_tool.modules=lambda root:self.deps
        for relative in paths:
            target=self.root/relative;raw=target.read_bytes();calls=[]
            def mutate(*args,**kwargs):
                result=original(*args,**kwargs);calls.append(1)
                if len(calls)==7:target.write_bytes(raw+b' ')
                return result
            try:
                with self.subTest(path=relative),patch.object(S,'module',return_value=self.report_tool), \
                     patch.object(S,'rebuild_member',side_effect=mutate):
                    with self.assertRaises(ValueError):S.verify(self.request())
            finally:target.write_bytes(raw)
    def test_source_membership_addition_and_removal_refused(self):
        original=S.rebuild_member;self.report_tool.modules=lambda root:self.deps
        target=self.root/'eval0/manifests/extra.json'
        for action in ('add','remove'):
            if action=='remove':target.write_text('{}')
            calls=[]
            def mutate(*args,**kwargs):
                result=original(*args,**kwargs);calls.append(1)
                if len(calls)==7:
                    if action=='add':target.write_text('{}')
                    else:target.unlink()
                return result
            with self.subTest(action=action),patch.object(S,'module',return_value=self.report_tool), \
                 patch.object(S,'rebuild_member',side_effect=mutate):
                with self.assertRaisesRegex(ValueError,'snapshot changed'):S.verify(self.request())
            target.unlink(missing_ok=True)
    def test_changed_base_adapter_and_report_rejected(self):
        entry=self.entries[0];base=self.base/'weights.safetensors';original=base.read_bytes();base.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'byte inventory'):self.rebuild(entry)
        base.write_bytes(original)
        report=Path(entry['report']['path']);report.write_text(report.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.rebuild(entry)
        entry['report']['sha256']=S.sha(report)
        adapter=self.root/'train0/adapter/adapter_model.safetensors';adapter.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'byte inventory'):self.rebuild(entry)
    def test_forged_saved_metrics_rejected_after_source_rebuild(self):
        entry=copy.deepcopy(self.entries[0]);path=Path(entry['report']['path']);value=json.loads(path.read_text());value['fake_accuracy']=1
        path.write_text(json.dumps(value));entry['report']['sha256']=S.sha(path)
        with self.assertRaisesRegex(ValueError,'reconstructed source'):self.rebuild(entry)
    def test_test_scope_wrong_mode_and_missing_member_rejected(self):
        report=self.rebuilt[str(Path(self.entries[4]['report']['path']).parent)]
        for field,value in [('partitions',['test','calibration']),('primary_input_mode','full')]:
            doc=copy.deepcopy(report);doc['header'][field]=value
            with self.assertRaises(ValueError):S.scope(doc)
        with self.assertRaisesRegex(ValueError,'seven source members'):S.verify({'schema':'r3-campaign-sources-request-v1','selected_arm':'K1','members':[]})
    def test_training_manifest_change_rejected(self):
        path=self.root/'train0/manifest.json';value=json.loads(path.read_text());value['args']['seed']=3;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'training identity'):self.rebuild(self.entries[0])
    def test_test_readouts_rejected_before_report_rebuild(self):
        path=Path(self.entries[0]['report']['path']).parent/'trackk/decision-v7__test/clean.jsonl'
        path.parent.mkdir(parents=True);path.write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'test readouts'):self.rebuild(self.entries[0])
    def test_actual_frozen_api_new_process(self):
        code='''import importlib.util,sys
from pathlib import Path
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('real_report',p);r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
d=r.modules(Path(sys.argv[2])/'r3_code')
for value in (r.rebuild,d[1].train_identity,d[1].TL.model_identity):assert callable(value)
assert Path(d[1].__file__).resolve().is_relative_to(Path(sys.argv[2]))
assert 'torch' not in sys.modules
'''
        done=subprocess.run([sys.executable,'-B','-c',code,str(HERE/'r3_selection_report.py'),str(FROZEN)],capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr)


if __name__=='__main__': unittest.main()
