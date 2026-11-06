"""Tiny synthetic producer fixtures. No inference, weights reads or full DEV recompute."""
import copy
import contextlib
import io
from unittest.mock import patch
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('compare_dev', HERE/'compare_dev.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CLOSURE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code')

def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))

def row(i, suite):
    return {'kev':{'id':suite+str(i),'qindex':0}, 'levels':[{'id':'a'},{'id':'b'}],
            'gold':'a', 'source':'src', 'level_type':'boolean', 'qname':'question'}

def saved(r, scores, stamp):
    arg = max(range(len(scores)),key=scores.__getitem__)
    return {'k':m.qkey(r),'ids':['a','b'],'gold':'a','gold_index':0,'argmax':arg,
            'tie':scores.count(max(scores))>1,'s':scores,'m':stamp[:16],
            'source':r['source'],'level_type':r['level_type'],'qname':r['qname'],'variant':r.get('variant','original')}

class Fixture:
    def __init__(self, path):
        self.path = Path(path)
        c = self.c = m.Consumer.__new__(m.Consumer)
        real = m.obj(m.DEFAULT_CATALOG)
        scorer = real['new_contract']['scorer']
        base_model = {'base_path':'/fake/Base','base_revision':'revision','sha256':'b'*64}
        c.catalog = {'new_contract':{'scorer':scorer,'data_pins':{},
                      'current_train_image':real['new_contract']['current_train_image'],
                      'expected_populations':{'decision-v7/dev':2,'transfer-v4/dev':2,'decision-v7/calibration':2}},
                      'new_rc1_lanes':[]}
        c.refs = {}
        c.base = {}
        c.pop = {}
        for label in c.catalog['new_contract']['expected_populations']:
            c.pop[(label,'clean')] = [row(i,label) for i in range(2)]
            if label.endswith('/dev'):
                variants = [row(2,label)]
                variants[0]['variant'] = 'permuted'
                c.pop[(label,'variants')] = variants
        c.keys = [[s,m.qkey(r)] for s in m.SUITES for r in c.pop[(s+'/dev','clean')]]
        for size, stem in [('0.8B','08b'),('2B','2b'),('4B','4b'),('9B','9b')]:
            rid = stem+'-k0'
            c.refs[rid] = {'model':base_model,'size':size}
            c.base[rid] = {s+'/dev':[0,1] for s in m.SUITES}
            for seed in (2,3):
                lane = {'lane':stem+'-s'+str(seed),'size':size,'seed':seed,'baseline_id':rid,
                        'new_adapter':str(self.path/'train'/(stem+'-s'+str(seed))/'result/adapter')}
                c.catalog['new_rc1_lanes'].append(lane)
        spec = importlib.util.spec_from_file_location('test_dev_pv', CLOSURE/'provenance_r3.py')
        c.pv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(c.pv)

    def produce(self, lane, scores=None):
        c = self.c
        scores = scores or [[2.,1.],[1.,1.]]
        adapter = Path(lane['new_adapter'])
        ident = {'seed':lane['seed'],'model_id':'Qwen3.5-'+lane['size']+'-Base','model_revision':'revision'}
        bind = {'owner':'rc1-functional-'+lane['lane'],'identity_sha256':m.canonical(ident,ascii=True),'checkpoint_sha256':'c'*64}
        config = {'base_model_name_or_path':ident['model_id'],'revision':'revision'}
        put(adapter/'adapter_config.json',config)
        # No fake weight file needed: weight payload accepted by producer, consumer never opens it.
        pub = {'binding':bind,'files':{'adapter_config.json':m.digest((adapter/'adapter_config.json').read_bytes()),'adapter_model.safetensors':'a'*64}}
        put(adapter/'PUBLICATION.json',pub)
        put(adapter/'BINDING.json',bind)
        put(adapter.parent/'OWNER.json',{'owner':bind['owner'],'identity':ident})
        put(adapter.parents[1]/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False})
        run = self.path/'runs'/('full-'+lane['lane'])/'result'
        put(run.parent/'BINDING.json',{'binding':bind,'publication_sha256':m.digest((adapter/'PUBLICATION.json').read_bytes())})
        put(run.parent/'EXIT.json',{'exit_code':0})
        model_sha, _ = c.publication(lane,run)
        desc = dict(c.catalog['new_contract']['scorer'],adapter=str(adapter),model_path='/fake/Base')
        h = {'arm':'K1','partitions':['dev','calibration'],'limit':0,'limit_groups':0,
             'dry_run_warnings':[],'stages':'k','primary_input_mode':'full','prompt_version':'r0-prompt-v2',
             'prompt_format':'raw-completion (no chat template)','render':'record_name','dtype':'float32',
             'scorer':desc,'data_files':{},'checkpoint_revision':'revision',
             'model':{'path':str(adapter),'sha256':model_sha,'kind':'lora-adapter-unmerged','base_path':'/fake/Base','base_revision':'revision'}}
        parts, files = {}, []
        for label in c.catalog['new_contract']['expected_populations']:
            part = {'n':2,'arms':{},'secondary':{'permutation':{'kept':1},'nota':{'parents':1},'operator':{'n':2}},
                    'near_tie_census':{'n':2},'duplicate_option_audit':{'n':2}}
            suite, split = label.split('/')
            for kind in (('clean',) if split == 'calibration' else ('clean','variants','question_only','empty_input')):
                rows = c.pop[(label,'variants' if kind=='variants' else 'clean')]
                raw = [saved(r,scores[i%2],model_sha) for i,r in enumerate(rows)]
                path = run/'trackk'/(suite+'__'+split)/(kind+'.jsonl')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
                files.append(str(path))
                summary = m.summarize(rows,m.score_rows(rows,raw,model_sha))
                if kind == 'clean': part['headline'] = summary
                elif kind != 'variants': part['arms'][kind] = summary
            if split == 'dev':
                part['arms']['constant'] = copy.deepcopy(part['headline'])
                part['arms']['uniform'] = copy.deepcopy(part['headline'])
            parts[label] = part
        h['provenance_manifest'] = c.pv.write_unit_manifest(str(run),'',model_sha,desc,files)
        # Exercise producer-container to host path remapping.
        h['provenance_manifest'] = '/run/output/result/manifests/main.json'
        put(run/'RUN_IDENTITY.json',{'model_sha256':model_sha})
        put(run/'report.json',{'header':h,'track_k':{'partitions':parts,'operator_fit':{'n':1148,'partition':'decision-v7/calibration'}}})
        return run

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE/'scratch')
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name)
        self.c = self.f.c
        self.lane = self.c.catalog['new_rc1_lanes'][0]

    def edit(self, path, func):
        v = m.obj(path)
        func(v)
        put(path,v)

    def test_raw_first_argmax_tie_and_discordants(self):
        run = self.f.produce(self.lane)
        v = self.c.consume(self.lane,run)
        a = v['metrics']['decision-v7/dev/clean']
        self.assertEqual((a['n'],a['correct'],a['r0_correct'],a['tie_count']),(2,2,1,1))
        self.assertEqual(v['dev_comparisons']['decision-v7/dev']['k0_wrong_new_right'],1)
        self.assertEqual(v['dev_comparisons']['decision-v7/dev']['dev_delta'],.5)
        self.assertIn('constant',v['full_report_diagnostics']['decision-v7/dev']['arms'])
        self.assertEqual(v['runtime']['status'],'CONDITIONAL_PENDING_ACTUAL_RUNTIME_VALIDATION')

    def test_wrong_population(self):
        run = self.f.produce(self.lane)
        path = run/'trackk/decision-v7__dev/clean.jsonl'
        raw = m.jsonl(path)
        raw[0]['k'] = 'wrong-key/0'
        path.write_text(''.join(json.dumps(x)+'\n' for x in raw))
        self.repin(run,path)
        with self.assertRaisesRegex(m.Contradiction,'population/order'):
            self.c.consume(self.lane,run)

    def repin(self, run, path):
        self.edit(run/'manifests/main.json',lambda x:x['files'][str(path.relative_to(run))].update(sha256=m.digest(path.read_bytes())))

    def test_duplicate_and_candidate_order(self):
        for bad in ('duplicate','order'):
            with self.subTest(bad=bad):
                run = self.f.produce(self.lane)
                path = run/'trackk/decision-v7__dev/clean.jsonl'
                raw = m.jsonl(path)
                if bad=='duplicate':raw[1]['k']=raw[0]['k']
                else:raw[0]['ids'].reverse()
                path.write_text(''.join(json.dumps(x)+'\n' for x in raw))
                self.repin(run,path)
                with self.assertRaises(m.Contradiction):self.c.consume(self.lane,run)

    def test_wrong_seed_and_terminal(self):
        run = self.f.produce(self.lane)
        path = Path(self.lane['new_adapter']).parent/'OWNER.json'
        self.edit(path,lambda x:x['identity'].update(seed=3))
        with self.assertRaisesRegex(m.Contradiction,'seed'):self.c.consume(self.lane,run)
        run = self.f.produce(self.lane)
        self.edit(Path(self.lane['new_adapter']).parents[1]/'COMPLETE.json',lambda x:x.update(steps=3115))
        with self.assertRaisesRegex(m.Contradiction,'3116'):self.c.consume(self.lane,run)

    def test_descriptor_mismatch(self):
        run = self.f.produce(self.lane)
        self.edit(run/'report.json',lambda x:x['header']['scorer'].update(token_budget=1))
        with self.assertRaisesRegex(m.Contradiction,'descriptor'):self.c.consume(self.lane,run)

    def test_saved_headline_mismatch(self):
        run = self.f.produce(self.lane)
        self.edit(run/'report.json',lambda x:x['track_k']['partitions']['decision-v7/dev']['headline'].update(kev_rule_accuracy=.5))
        with self.assertRaisesRegex(m.Contradiction,'headline mismatch'):self.c.consume(self.lane,run)

    def test_stratum_headline_mismatch(self):
        run = self.f.produce(self.lane)
        self.edit(run/'report.json',lambda x:x['track_k']['partitions']['decision-v7/dev']['arms']['question_only']['by_source']['src'].update(n=99))
        with self.assertRaisesRegex(m.Contradiction,'headline mismatch'):self.c.consume(self.lane,run)

    def test_nonfinite_missing_and_provenance(self):
        run = self.f.produce(self.lane)
        path = run/'trackk/decision-v7__dev/clean.jsonl'
        original = path.read_text()
        path.write_text(original.replace('2.0','NaN',1))
        self.repin(run,path)
        with self.assertRaisesRegex(m.Contradiction,'nonfinite'):self.c.consume(self.lane,run)
        path.unlink()
        with self.assertRaises(m.Pending):self.c.consume(self.lane,run)
        run = self.f.produce(self.lane)
        self.edit(run/'RUN_IDENTITY.json',lambda x:x.update(model_sha256='wrong'))
        with self.assertRaisesRegex(m.Contradiction,'provenance'):self.c.consume(self.lane,run)

    def test_second_seed_missing_no_mean_then_paired_mean(self):
        self.f.produce(self.lane)
        root = self.f.path/'runs'
        result, code = m.assemble(self.c,root)
        self.assertEqual(code,2)
        self.assertEqual(result['within_size_two_seed_means'][0]['finished_seeds'],[2])
        self.assertIsNone(result['within_size_two_seed_means'][0]['suites'])
        self.f.produce(self.c.catalog['new_rc1_lanes'][1], [[1.,2.],[2.,1.]])
        result, _ = m.assemble(self.c,root)
        suite = result['within_size_two_seed_means'][0]['suites']['decision-v7/dev']
        self.assertEqual(suite['n_questions'],2)
        self.assertEqual(suite['new_correct_mean'],1.5)
        self.assertEqual(suite['dev_same_question_two_seed_mean_difference'],.25)
        self.assertNotIn('pooled',result)

    def test_failed_terminal_contradiction_not_pending(self):
        run = self.f.produce(self.lane)
        self.edit(run.parent/'EXIT.json',lambda x:x.update(exit_code=1))
        result, code = m.assemble(self.c,self.f.path/'runs')
        self.assertEqual(code,1)
        self.assertEqual(result['lanes'][0]['status'],'REFUSED_CONTRADICTION')

    def test_report_no_track_t_and_strict_json(self):
        run = self.f.produce(self.lane)
        self.edit(run/'report.json',lambda x:x.update(track_t={'must':'never decode'}))
        with self.assertRaisesRegex(m.Contradiction,'Track T'):self.c.consume(self.lane,run)
        p = self.f.path/'mixed.json'
        p.write_text('{"track_t":{"x":NaN},"header":{"ok":1}}')
        value, keys = m.selective(p,{'header'})
        self.assertEqual(value,{'header':{'ok':1}})
        self.assertIn('track_t',keys)
        with self.assertRaisesRegex(m.Contradiction,'duplicate'):m.decode('{"a":1,"a":2}')

    def test_cli_tiny_fixture_outputs_and_unknown_seed(self):
        self.f.produce(self.lane)
        output = self.f.path/'comparison-output'
        argv = ['compare_dev.py','--run-root',str(self.f.path/'runs'),'--output',str(output)]
        with patch.object(m,'Consumer',return_value=self.c), patch.object(sys,'argv',argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),2)
        result = m.obj(output/'comparison.json')
        self.assertEqual(result['lanes'][0]['status'],'VALIDATED_DEV_CONDITIONAL_RUNTIME')
        self.assertIsNone(result['within_size_two_seed_means'][0]['suites'])
        self.assertIn('08b-s2', (output/'comparison.md').read_text())
        with patch.object(m,'Consumer',return_value=self.c), patch.object(sys,'argv',argv+['--run','08b-s99=/fake/result']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),1)
        self.assertEqual(m.obj(output/'comparison.json')['status'],'REFUSED_CONTRADICTION')

    def test_json_overflow_and_malformed_gold_refused(self):
        with self.assertRaisesRegex(m.Contradiction,'nonfinite'):m.decode('{"x":1e999}')
        run = self.f.produce(self.lane)
        self.c.pop[('decision-v7/dev','clean')][0]['gold'] = 'unknown'
        result, code = m.assemble(self.c,self.f.path/'runs')
        self.assertEqual(code,1)
        self.assertEqual(result['lanes'][0]['status'],'REFUSED_CONTRADICTION')

    def test_actual_catalog_readonly_and_cli_help(self):
        catalog = m.obj(m.DEFAULT_CATALOG)
        vectors = m.obj(m.DEFAULT_CATALOG.with_name('DEV-VECTORS.json'))
        self.assertEqual(catalog['status'],'READY_FOR_COMPARISON_INPUT')
        self.assertEqual(len(catalog['new_rc1_lanes']),8)
        for ref in catalog['references']:
            v = vectors[ref['id']]
            self.assertEqual(len(v['keys']),1920)
            self.assertEqual(m.canonical(v['correct']),v['correct_sha256'])
        p = subprocess.run([sys.executable,'-B','-I',str(HERE/'compare_dev.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0)
        self.assertIn('--reference-catalog',p.stdout)

if __name__ == '__main__':unittest.main(verbosity=2)
