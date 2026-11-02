import copy
from collections import Counter
import contextlib
import importlib.util
import io
import json
import shutil
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent

def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
P=module('bev_encode_dev_probe');H=module('bev_encode_dev_host');B=module('bev_public_test_bridge')
E=module('test_bev_encode_once')


def row(i,kind):
    return dict(id=f'{kind}-{i:03}',request=dict(input='x'*(i+1),question='q',type=kind,
        level_type={'choice':'nominal','noul':'boolean','score':'ordinal'}[kind],candidate_set='exclusive',
        candidate_keys=['true','false'] if kind=='noul' else ['0','1'],
        definitions=['True','False'] if kind=='noul' else ['a','b']))


def trials():
    return [dict(s,attempt=1,status='PASS',exit_code=0,ids=[str(s['batch'])],output_sha256=str(s['batch']),
        score_seconds=2. if s['variant']=='baseline' else 1.,host_only_seconds=.2 if s['variant']=='baseline' else .1,
        reserved_gib=5.,counts=dict(tokens=100,forwards=2,head_positions=4,items=8)) for s in P.trial_specs()]


class ProbeTests(unittest.TestCase):
    def test_deterministic_stratified_sample_and_input_sensitivity(self):
        rows=[row(i,k) for k in ('choice','noul','score') for i in range(90)]
        sample,strata=P.select_sample(rows,B)
        self.assertEqual((sample,strata),P.select_sample(list(reversed(rows)),B))
        self.assertEqual(len(sample),72);self.assertEqual(len({r['id'] for r in sample}),72)
        self.assertEqual([s['type'] for s in strata],['choice']*3+['noul']*3+['score']*3)
        self.assertEqual(strata[0]['ids'],['choice-'+str(i).zfill(3) for i in (0,4,8,12,16,20,24,29)])
        rows[0]['request']['input']='y'*1000
        self.assertNotEqual(sample,P.select_sample(rows,B)[0])
    def test_duplicate_and_gold_source_rejected(self):
        rows=[row(i,k) for k in ('choice','noul','score') for i in range(30)]
        with self.assertRaisesRegex(ValueError,'duplicate'):P.select_sample(rows+[rows[0]],B)
        rows[0]['gold']=0
        with self.assertRaisesRegex(ValueError,'gold-free'):P.select_sample(rows,B)
    def test_pair_exactness_not_tolerance(self):
        reference=dict(ids=['a'],layout=[{'prefix':[1,2]}],outputs=[{'raw':[1.,2.],'prediction':1}])
        P.compare(reference,copy.deepcopy(reference))
        for key,value in [('ids',['b']),('layout',[{'prefix':[2,1]}]),('outputs',[{'raw':[1.,2.+1e-12],'prediction':1}])]:
            actual=copy.deepcopy(reference);actual[key]=value
            with self.assertRaises(ValueError):P.compare(reference,actual)
    def test_arithmetic_pair_matching_and_trial_order(self):
        result=P.summarize(list(reversed(trials())))
        self.assertEqual(result['whole_score_time_ratio'],2.)
        self.assertEqual(result['host_only_time_ratio'],2.)
        self.assertEqual(result['measurements']['baseline']['forwarded_tokens_per_second_per_chip'],50.)
        self.assertEqual(result['measurements']['candidate']['forwarded_tokens_per_second_per_chip'],100.)
        self.assertEqual(result['process_peak_reserved_gib'],5.)
        self.assertNotIn('peak_reserved_gib',result['measurements']['candidate'])
        self.assertEqual([s['variant'] for s in P.trial_specs()[:2]],['baseline','candidate'])
        self.assertEqual([s['variant'] for s in P.trial_specs()[18:20]],['candidate','baseline'])
    def test_missing_duplicate_failed_mismatched_and_bad_time_trials_reject(self):
        variants=[]
        t=trials();variants.append(t[:-1]);variants.append(t[:-1]+[t[0]])
        for key,value in [('attempt',999),('status','FAIL'),('exit_code',1),('ids',['wrong']),('output_sha256','wrong'),
                          ('counts',dict(tokens=1)),('score_seconds',float('nan')),('host_only_seconds',0),('reserved_gib',-1),('batch',9)]:
            t=trials();t[0][key]=value;variants.append(t)
        for t in variants:
            with self.assertRaises(ValueError):P.summarize(t)
    def test_durable_atomic_marker_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'trial.json';P.atomic(p,dict(status='PASS'),exclusive=True)
            before=p.read_bytes()
            with self.assertRaises(FileExistsError):P.atomic(p,dict(status='FAIL'),exclusive=True)
            self.assertEqual(p.read_bytes(),before)
    def test_exact_detached_launch_policy(self):
        plan=dict(container='nga-probe',chip=7,environment=P.ENV,mounts=[dict(source='/fixed',destination='/fixed',readonly=True)],
                  image_sha256=P.IMAGE,code={'runner':{'path':'/fixed/probe.py'}})
        command=H.expected_command(plan,'/fixed/plan.json','a'*64,1)
        self.assertEqual(command[:5],['docker','run','-d','--name','nga-probe-a1'])
        self.assertNotIn('--rm',command);self.assertIn('/dev/davinci7',command)
        self.assertEqual(command[-11:],[P.IMAGE,'python3','-B','-P','/fixed/probe.py','run','--plan','/fixed/plan.json','--sha256','a'*64,'--attempt','1'][-11:])
        with self.assertRaisesRegex(ValueError,'attempt1'):H.expected_command(plan,'/fixed/plan.json','a'*64,2)
    def test_verify_rejects_protocol_or_scope_before_dependencies(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'plan.json'
            base=dict(schema='bev-encode-dev-probe-v2',attempts=[1],resume_allowed=False,scope='train_derived_dev',test_read=False,scientific_acceptance=False,
                      scoring=P.SCORING,protocol=P.PROTOCOL)
            for key,value in [('scope','public_release_test'),('test_read',True),('protocol',dict(P.PROTOCOL,raw_score_tolerance=.001)),('scoring',dict(P.SCORING,token_budget=32768))]:
                d=dict(base);d[key]=value;p.write_text(json.dumps(d))
                with self.assertRaises(ValueError):P.verify(p,P.sha(p))
    def fake_components(self, unstable=False):
        class Scorer(E.Scorer):
            def __init__(self, model, **kwargs):
                super().__init__();self.token_budget=kwargs['token_budget'];self.stats=Counter();self.calls=0
            def load(self):return self
            def score_enc(self, enc, mode):
                self.calls+=1;self.stats.update(tokens=100,forwards=1,head_positions=2,items=len(enc))
                result=super().score_enc(enc,mode)
                if unstable and self.calls==2:result[0][0]+=1e-9
                return result
        sm=types.SimpleNamespace(R3Scorer=Scorer,dedup_enc=lambda enc:(enc,[list(range(len(e.cands))) for e in enc],0,0))
        variants={'baseline':types.SimpleNamespace(score_batch=lambda rows,scorer,p,b,plan:E.baseline(rows,scorer)), 'candidate':E.R}
        return E.P,sm,B,variants
    def test_cpu_end_to_end_frozen_schedule_and_gate_failure(self):
        for unstable in (False,True):
            with self.subTest(unstable=unstable),tempfile.TemporaryDirectory() as td:
                root=Path(td);requests=root/'requests.jsonl'
                requests.write_text(''.join(json.dumps(E.row(str(i),text='context '+str(i)))+'\n' for i in range(72)))
                (root/'output').mkdir();P.reserve_measurement(root/'output','a'*64,1)
                plan=dict(out=str(root/'output'),model='/unused',inputs={'requests':{'path':str(requests)}},scoring=P.SCORING)
                npu=types.SimpleNamespace(set_device=lambda _:None,synchronize=lambda:None,max_memory_reserved=lambda:5*2**30,
                    conv=types.SimpleNamespace(allow_hf32=True),matmul=types.SimpleNamespace(allow_hf32=True))
                with (mock.patch.object(P,'verify',return_value=plan),mock.patch.object(P,'load_components',return_value=self.fake_components(unstable)),
                     mock.patch.dict(sys.modules,{'torch':types.SimpleNamespace(npu=npu),'torch_npu':types.SimpleNamespace()}),contextlib.redirect_stdout(io.StringIO())):
                    if unstable:
                        with self.assertRaisesRegex(ValueError,'raw score'):P.run(root/'plan.json','a'*64,1)
                        self.assertTrue((root/'output/FAILURE.json').exists())
                        self.assertFalse((root/'output/COMPLETE.json').exists())
                        with self.assertRaisesRegex(ValueError,'attempt1'):P.run(root/'plan.json','a'*64,2)
                    else:
                        self.assertEqual(P.run(root/'plan.json','a'*64,1),0)
                        report=json.loads((root/'output/report.json').read_text())
                        self.assertEqual(len(list((root/'output/trials').glob('*.json'))),54)
                        self.assertEqual(report['measurements']['baseline']['trials'],27)
                        self.assertEqual(report['measurements']['candidate']['forwarded_tokens'],2700)
                        self.assertTrue(report['baseline_repeat_exact']);self.assertTrue(report['candidate_exact'])
                        with self.assertRaisesRegex(ValueError,'attempt1'):P.run(root/'plan.json','a'*64,2)
    def test_real_runner_rejects_foreign_timing_records_without_reading_or_replacing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);requests=root/'requests.jsonl'
            requests.write_text(''.join(json.dumps(E.row(str(i),text='context '+str(i)))+'\n' for i in range(72)))
            source=root/'source';source.mkdir();P.reserve_measurement(source,'a'*64,1)
            plan=dict(out=str(source),model='/unused',inputs={'requests':{'path':str(requests)}},scoring=P.SCORING)
            npu=types.SimpleNamespace(set_device=lambda _:None,synchronize=lambda:None,max_memory_reserved=lambda:5*2**30,
                conv=types.SimpleNamespace(allow_hf32=True),matmul=types.SimpleNamespace(allow_hf32=True))
            with (mock.patch.object(P,'verify',return_value=plan),mock.patch.object(P,'load_components',return_value=self.fake_components()),
                  mock.patch.dict(sys.modules,{'torch':types.SimpleNamespace(npu=npu),'torch_npu':types.SimpleNamespace()}),contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(P.run(root/'plan.json','a'*64,1),0)
            foreign=root/'foreign';foreign.mkdir();shutil.copytree(source/'trials',foreign/'trials')
            for path in (foreign/'trials').glob('*.json'):
                value=json.loads(path.read_text());value.update(attempt=999,score_seconds=9999999.,host_only_seconds=.0001)
                path.write_text(json.dumps(value))
            before={p.name:p.read_bytes() for p in (foreign/'trials').iterdir()}
            plan['out']=str(foreign)
            with mock.patch.object(P,'verify',return_value=plan),mock.patch.object(P,'load_components') as load:
                with self.assertRaisesRegex(ValueError,'existing measurement'):P.run(root/'plan.json','a'*64,1)
                load.assert_not_called()
            self.assertEqual(before,{p.name:p.read_bytes() for p in (foreign/'trials').iterdir()})
            self.assertFalse((foreign/'COMPLETE.json').exists())
            self.assertFalse((foreign/'attempts').exists())
    def test_host_refuses_foreign_trials_before_claim_or_supervisor_spawn(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'trials').mkdir();artifact=root/'trials/r0-b0-baseline.json'
            artifact.write_text(json.dumps(dict(attempt=999,plan_sha256='a'*64,status='PASS')))
            review=root/'review.json';review.write_text(json.dumps(dict(attempts=[1])))
            args=types.SimpleNamespace(plan=str(root/'plan.json'),sha256='a'*64,review=str(review),review_sha256='b'*64,attempt=1)
            with (mock.patch.object(H,'review',return_value=dict(out=str(root))),mock.patch.object(H,'runner',return_value=P),
                  mock.patch.object(H.socket,'gethostname',return_value='k8s-node1'),mock.patch.object(H.subprocess,'run') as invoke,
                  mock.patch.object(H.subprocess,'Popen') as spawn,mock.patch.object(H,'inspect') as inspect):
                for operation in (H.start,H.supervise):
                    with self.assertRaisesRegex(ValueError,'existing measurement'):operation(args)
                invoke.assert_not_called();spawn.assert_not_called();inspect.assert_not_called()
            self.assertEqual(json.loads(artifact.read_text())['attempt'],999)
            self.assertFalse((root/'MEASUREMENT_OWNER.json').exists())
    def test_fresh_generation_exclusive_owner_and_directory_races_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);P.reserve_measurement(root,'a'*64,1)
            with self.assertRaises(FileExistsError):P.reserve_measurement(root,'a'*64,1)
            original=Path.mkdir
            def race(path,*args,**kwargs):
                if path==root/'trials':original(path)
                return original(path,*args,**kwargs)
            with mock.patch.object(Path,'mkdir',race):
                with self.assertRaises(FileExistsError):P.begin_measurement(root,'a'*64,1)
            self.assertTrue((root/'trials').exists())
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);original=P.atomic
            def inject(path,value,exclusive=False):
                original(path,value,exclusive);(root/'trials').mkdir()
            with mock.patch.object(P,'atomic',side_effect=inject):
                with self.assertRaisesRegex(ValueError,'existing measurement'):P.reserve_measurement(root,'a'*64,1)
            self.assertTrue((root/'MEASUREMENT_OWNER.json').exists())



if __name__=='__main__':unittest.main()
