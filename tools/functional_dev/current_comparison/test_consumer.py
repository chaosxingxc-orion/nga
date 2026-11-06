"""Bounded synthetic CPU acceptance; no actual model/TEST/production receipt reads."""
import builtins
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture_tests',HERE/'fixtures.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F);M=F.M

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=HERE/'scratch');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.config,self.inspections=F.build(self.root)
        self.model=self.config['models'][0];self.lane=self.config['lanes'][0]
        self.base=Path(self.config['k0_root'])/self.model['id'];self.adapter=Path(self.config['adapter_root'])/('full-'+self.lane['lane'])

    def consumer(self):return M.Consumer(self.config,inspector=self.inspections.__getitem__,allow_fixture=True)
    def edit(self,path,fn):
        value=M.obj(path);fn(value);F.put(path,value)
    def result(self):return M.assemble(self.consumer())
    def refused(self):
        result,code=self.result();self.assertEqual(code,1,result);self.assertEqual(result['status'],'REFUSED_CONTRADICTION');return result
    def consume_base(self):return self.consumer().consume(self.model)
    def consume_adapter(self):return self.consumer().consume(self.model,self.lane)

    def test_positive_twelve_roles(self):
        r,code=self.result();self.assertEqual(code,0);self.assertTrue(r['synthetic_fixture']);self.assertEqual(len(r['operands']),12)
        self.assertEqual(len(r['comparisons']),8);self.assertEqual(len(r['within_size_two_seed_means']),4)
        for v in r['operands']:
            self.assertEqual(v['status'],'VALIDATED_OPERAND');self.assertEqual(len(v['groups']),3 if v['seed'] is None else 9)
            self.assertEqual(v['metrics']['decision-v7/dev/clean']['tie_count'],1)
            self.assertEqual(v['operator_fit']['n'],24);self.assertTrue(v['reconstructed_tau_table'])
        for mean in r['within_size_two_seed_means']:self.assertEqual(mean['finished_seeds'],[2,3]);self.assertIsNotNone(mean['suites'])
        self.assertNotIn('pooled',r)
        a=r['comparisons'][1]['suites']['decision-v7/dev']
        base=next(x for x in r['operands'] if x['role']==self.model['id'])
        self.assertNotEqual(base['metrics']['decision-v7/dev/clean']['kev_rule_accuracy'],base['metrics']['decision-v7/dev/clean']['r0_rule_accuracy'])
        self.assertEqual(a['first_argmax']['k0_wrong_new_right'],2);self.assertEqual(a['first_argmax']['k0_right_new_wrong'],1)

    def test_missing_base_pending_no_means(self):
        (self.base/'score-EXIT.json').unlink();r,code=self.result();self.assertEqual(code,2)
        self.assertEqual(r['within_size_two_seed_means'][0]['finished_seeds'],[]);self.assertIsNone(r['within_size_two_seed_means'][0]['suites'])

    def test_missing_seed_pending_no_mean(self):
        (self.adapter/'score-EXIT.json').unlink();r,code=self.result();self.assertEqual(code,2)
        self.assertEqual(r['within_size_two_seed_means'][0]['finished_seeds'],[3]);self.assertIsNone(r['within_size_two_seed_means'][0]['suites'])

    def test_failed_later_phase_masks_nothing(self):
        (self.base/'infer-LAUNCH.json').unlink();self.edit(self.base/'score-EXIT.json',lambda x:x.update(exit_code=1))
        self.refused()
    def test_failed_infer_missing_score(self):
        (self.adapter/'score-EXIT.json').unlink();self.edit(self.adapter/'infer-EXIT.json',lambda x:x.update(container_exit_code=1));self.refused()
    def test_queue_failure_without_phase_receipts_refused(self):
        (self.base/'infer-EXIT.json').unlink()
        F.put(Path(self.config['k0_root'])/'QUEUE-EXIT.json',{'exit_code':1,'results':{'08b-k0':'FAILED'}})
        r=self.refused();self.assertTrue(r['queue_failures'])
    def test_failed_available_container_with_missing_report(self):
        cid=M.obj(self.base/'infer-LAUNCH.json')['container_id'];self.inspections[cid]['State']['ExitCode']=1
        (self.base/'result/clean-report.json').unlink();self.refused()
    def test_wrong_size_mapping(self):
        self.config['lanes'][0]['size']='9B'
        with self.assertRaises(M.Contradiction):self.consumer()
    def test_wrong_revision(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['identity'].update(base_revision='wrong'));self.refused()
    def test_wrong_seed(self):
        self.edit(Path(self.lane['new_adapter']).parent/'OWNER.json',lambda x:x['identity'].update(seed=3));self.refused()
    def test_wrong_image(self):
        cid=M.obj(self.base/'infer-LAUNCH.json')['container_id'];self.inspections[cid]['Image']='sha256:'+'0'*64;self.refused()
    def test_wrong_scorer(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['inference_header']['scorer'].update(score_chunk_questions=1));self.refused()
    def test_wrong_source_import(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['import_bindings']['scorer_r3'].update(sha256='0'*64));self.refused()
    def test_wrong_tokenizer(self):
        Path(next(p for p in self.model['asset_pins'] if p.endswith('/tokenizer.json'))).write_text('changed');self.refused()
    def test_wrong_weight_inventory(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['identity']['files'].update(other='0'*64));self.refused()
    def test_wrong_container_args(self):
        cid=M.obj(self.adapter/'infer-LAUNCH.json')['container_id'];self.inspections[cid]['Config']['Cmd']=['wrong'];self.refused()
    def test_wrong_source_mount(self):
        cid=M.obj(self.adapter/'infer-LAUNCH.json')['container_id'];self.inspections[cid]['Mounts'][1]['Source']='/foreign';self.refused()
    def test_wrong_command(self):
        self.edit(self.base/'score-COMMAND.json',lambda x:x.append('--smoke'));self.refused()
    def test_bad_header(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['inference_header'].update(render='wrong'));self.refused()
    def test_missing_receipt_is_pending(self):
        (self.base/'result/trackk/decision-v7__dev/clean.jsonl.receipt.json').unlink();r,code=self.result();self.assertEqual(code,2)
    def test_receipt_math_mismatch(self):
        self.edit(self.base/'result/trackk/decision-v7__dev/clean.jsonl.receipt.json',lambda x:x.update(committed_bytes=1));self.refused()
    def test_three_groups_never_nine(self):
        self.edit(self.base/'result/INFERENCE-READY.json',lambda x:x['groups'].append('decision-v7/dev/variants'));self.refused()
    def test_report_math_wrong(self):
        self.edit(self.base/'result/clean-report.json',lambda x:x['partitions']['decision-v7/dev']['headline'].update(kev_rule_accuracy=0.123));self.refused()
    def test_calibration_operator_wrong(self):
        self.edit(self.base/'result/clean-report.json',lambda x:x['partitions']['decision-v7/dev']['operator'].update(accuracy=0.123));self.refused()
    def test_controls_retained_and_contradiction_refused(self):
        r,_=self.result();a=next(x for x in r['operands'] if x['role']==self.lane['lane']);d=a['full_report_diagnostics']['decision-v7/dev']
        self.assertIn('constant',d['arms']);self.assertIn('nota',d['secondary']);self.assertEqual(d['arms']['empty_input']['tie_count'],4)
        self.edit(self.adapter/'result/report.json',lambda x:x['track_k']['partitions']['decision-v7/dev']['secondary']['nota'].update(both_sides_right=0.123));self.refused()

    def test_equal_metric_vectors_swapped_denied(self):
        p=self.base/'result/clean-report.json'
        def change(x):
            v=x['partitions']['decision-v7/dev']['vectors'];v[1]['s'],v[2]['s']=v[2]['s'],v[1]['s'];v[1]['p'],v[2]['p']=v[2]['p'],v[1]['p']
            # Both rows originally have same s, swap two different score vectors instead.
            v[0]['s'],v[2]['s']=v[2]['s'],v[0]['s'];v[0]['p'],v[2]['p']=v[2]['p'],v[0]['p']
        self.edit(p,change)
        with self.assertRaisesRegex(M.Contradiction,'per-item vector'):self.consume_base()

    def test_keys_candidate_gold_order_denied_even_rebound_store(self):
        run=self.base/'result';group='decision-v7/dev/clean';p=run/'trackk/decision-v7__dev/clean.jsonl'
        original=p.read_bytes();receipt=M.obj(str(p)+'.receipt.json');handoff=M.obj(run/'INFERENCE-READY.json')
        for bad in ('key','order','gold','duplicate'):
            with self.subTest(bad=bad):
                M._accesses.clear()
                raw=[M.L.decode(l) for l in original.splitlines()]
                if bad=='key':raw[0]['k']='wrong'
                elif bad=='order':raw[0]['ids'].reverse()
                elif bad=='gold':raw[0]['gold']='b'
                else:raw[1]['k']=raw[0]['k']
                F.jsonl(p,raw);receipt.update(committed_bytes=p.stat().st_size,sha256=M.sha(p));F.put(str(p)+'.receipt.json',receipt)
                handoff['stores'][group].update(store_sha256=M.sha(p),receipt_sha256=M.sha(str(p)+'.receipt.json'))
                c=self.consumer()
                with self.assertRaises(M.Contradiction):c.stores(run,handoff,self.model['model']['sha256'],M.CLEAN)

    def test_no_model_imports_cpu_path(self):
        real=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name.split('.')[0] in ('torch','torch_npu','transformers','numpy','eval_r3','scorer_r3','full_eval_r3','track_t_r3'):raise AssertionError('forbidden model import '+name)
            return real(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):self.assertEqual(self.result()[1],0)

    def test_fixture_requires_optin(self):
        with self.assertRaises(M.Contradiction):M.Consumer(self.config,inspector=self.inspections.__getitem__)

    def test_hand_probability_uniform_and_extreme(self):
        rows=[F.row(0,'decision-v7'),F.row(1,'decision-v7')]
        p=M.probability(rows,[{'s':[0.,0.]},{'s':[0.,0.]}]);self.assertEqual(p['brier_sum'],0.5);self.assertEqual(p['nll'],math.log(2));self.assertEqual(p['ece10'],0)
        q=M.probability(rows[:1],[{'s':[-1000.,0.]}]);self.assertEqual(q['nll'],1000);self.assertEqual(q['brier_sum'],2);self.assertEqual(q['ece10'],1)
        self.assertEqual(q['bins'][-1]['n'],1);self.assertIsNone(q['bins'][0]['mean_confidence'])
    def test_hand_probability_variable_single_and_translation(self):
        r=F.row(0,'decision-v7');r['levels']=r['levels'][:1]
        p=M.probability([r],[{'s':[-100.]}]);self.assertEqual((p['nll'],p['brier_sum'],p['ece10']),(0,0,0))
        r=F.row(0,'decision-v7');self.assertEqual(M.probability([r],[{'s':[2.,1.]}]),M.probability([r],[{'s':[-98.,-99.]}]))
        r2=F.row(1,'decision-v7');r2['levels'].append({'id':'c'})
        p=M.probability([r,r2],[{'s':[0.,0.]},{'s':[0.,0.,0.]}]);self.assertAlmostEqual(p['brier_sum'],(0.5+2/3)/2)
    def test_probability_rounding_mismatch_counted(self):
        r=F.row(0,'decision-v7');p=M.probability([r],[{'s':[0.,1e-20]}]);self.assertEqual(p['probability_argmax_mismatches'],1);self.assertEqual(p['exact_score_top_ties'],0)
    def test_probability_bad_arrays(self):
        for scores in ([],[float('nan'),0.],[float('inf'),0.],[0.]):
            with self.assertRaises((M.Contradiction,ValueError)):M.probability([F.row(0,'decision-v7')],[{'s':scores}])
        with self.assertRaises(M.Contradiction):M.probability([F.row(0,'decision-v7')],[{'s':[-1e308,1e308]}])
    def test_probability_reference_formula_exact(self):
        spec=importlib.util.spec_from_file_location('probability_reference_test',HERE/'reference_metrics.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
        rows=[F.row(i,'decision-v7') for i in range(4)]
        scores=[[0.,0.],[0.,1.],[2.,-3.],[1e308,-1e308]]
        scores[-1]=[-1e308,0.] # large finite gold loss (gold b)
        actual=M.probability(rows,[{'s':s} for s in scores]);expected=ref.summarize(scores,[0,1,0,1])
        for key in ('n','nll','brier_sum','ece10'):self.assertEqual(actual[key],expected[key])
        for a,b in zip(actual['bins'],expected['ece10_bins']):
            for k in ('lower','upper','n','mean_confidence','contribution'):self.assertEqual(a[k],b[k])
            self.assertEqual(a['mean_correctness'],b['accuracy'])
    def test_ece_exact_boundaries(self):
        spec=importlib.util.spec_from_file_location('probability_reference_edges',HERE/'reference_metrics.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
        rows=[F.row(i,'decision-v7') for i in range(4)];scores=[[0.,0.],[math.log(0.6),math.log(0.4)],[math.log(0.7),math.log(0.3)],[math.log(0.9),math.log(0.1)]]
        expected=ref.summarize(scores,[0,1,0,1]);actual=M.probability(rows,[{'s':s} for s in scores])
        self.assertEqual(actual['ece10'],expected['ece10']);self.assertEqual([x['n'] for x in actual['bins']],[x['n'] for x in expected['ece10_bins']])
    def test_finite_large_mean_nll(self):
        rows=[F.row(0,'decision-v7') for _ in range(4)]
        self.assertEqual(M.probability(rows,[{'s':[-1e308,0.]} for _ in rows])['nll'],1e308)
    def test_tau_calibration_only(self):
        c=self.consumer();original=c.V.fit_operator;seen=[]
        def fitting(rows,scores):
            self.assertEqual(rows,c.pop['decision-v7/calibration','clean']);self.assertEqual(len(rows),24);seen.append(len(rows));return original(rows,scores)
        with patch.object(c.V,'fit_operator',side_effect=fitting):
            c.consume(self.model);c.consume(self.model,self.lane)
        self.assertEqual(seen,[24,24])
    def test_source_changed_during_consume_refused(self):
        c=self.consumer();original=c.consume;changed=False
        def consume(model,lane=None):
            nonlocal changed
            value=original(model,lane)
            if not changed:
                changed=True;p=next(iter(model['asset_pins']));Path(p).write_text('changed after reconstruction')
            return value
        with patch.object(c,'consume',side_effect=consume):
            with self.assertRaisesRegex(M.Contradiction,'input changed'):M.assemble(c)
    def test_missing_weight_payloads_never_opened(self):
        self.assertFalse(any(self.root.rglob('*.safetensors')));self.assertEqual(self.result()[1],0)
    def test_hand_discordants(self):
        p=M.L.paired([1,0,1,0],[0,1,1,0]);self.assertEqual((p['k0_wrong_new_right'],p['k0_right_new_wrong'],p['both_right'],p['both_wrong'],p['dev_delta']),(1,1,1,1,0))
    def test_cli_help(self):
        p=subprocess.run([sys.executable,'-B','-P',str(HERE/'consumer.py'),'--help'],capture_output=True,text=True);self.assertEqual(p.returncode,0);self.assertIn('--allow-fixture',p.stdout)

if __name__=='__main__':unittest.main(verbosity=2)
