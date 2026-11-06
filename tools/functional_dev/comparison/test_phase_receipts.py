"""Synthetic-only phase compatibility cases; no actual producer results."""
import copy
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('original_tests', HERE/'test_compare_dev.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
m = t.m

class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE/'scratch')
        self.addCleanup(self.tmp.cleanup)
        self.f = t.Fixture(self.tmp.name)
        self.c = self.f.c
        self.lane = self.c.catalog['new_rc1_lanes'][0]

    def edit(self, path, change):
        value = m.obj(path)
        change(value)
        t.put(path, value)

    def produce(self, lane=None):
        lane = lane or self.lane
        run = self.f.produce(lane)
        binding = m.obj(run.parent/'BINDING.json')
        (run.parent/'BINDING.json').unlink()
        (run.parent/'EXIT.json').unlink()
        for phase in ('infer', 'score'):
            t.put(run.parent/(phase+'-BINDING.json'), binding)
            t.put(run.parent/(phase+'-LAUNCH.json'), {'container_id':phase+'-container-exact'})
            t.put(run.parent/(phase+'-EXIT.json'), {'exit_code':0,'container_exit_code':0,
                                                  'container_id':phase+'-container-exact'})
        report = m.obj(run/'report.json')
        h = report['header']
        h.update(device='cpu', throughput={'examples_per_second':0})
        ih = copy.deepcopy(h)
        ih.update(device='npu',stages='k_score',throughput={'examples_per_second':123})
        groups = [s+'/'+p+'/'+k for s,p in (('decision-v7','calibration'),('decision-v7','dev'),('transfer-v4','dev'))
                  for k in (('clean',) if p == 'calibration' else ('clean','variants','question_only','empty_input'))]
        stores = {}
        for group in groups:
            suite, split, kind = group.split('/')
            path = run/'trackk'/(suite+'__'+split)/(kind+'.jsonl')
            t.put(str(path)+'.receipt.json', {'synthetic_only':True,'store_sha256':m.digest(m.read(path))})
            stores[group] = {'store_sha256':m.digest(m.read(path)),
                             'receipt_sha256':m.digest(m.read(str(path)+'.receipt.json')),
                             'rows':len(m.jsonl(path))}
        handoff = {'version':1,'model':h['model']['base_path'],'adapter':h['model']['path'],
                   'out':'/run/output/result','limit':0,'groups':groups,'descriptor':h['scorer'],
                   'stores':stores,'inference_header':ih,'inference_elapsed_seconds':1}
        t.put(run/'INFERENCE-READY.json', handoff)
        h['phase_separation'] = {'inference_receipt_sha256':m.digest(m.read(run/'INFERENCE-READY.json')),
                                 'inference_header':ih,'cpu_score_elapsed_seconds':2}
        t.put(run/'report.json',report)
        return run

    def consume(self, run):
        return self.c.consume(self.lane,run,receipt_layout='phased')

    def relink(self, run):
        handoff = m.obj(run/'INFERENCE-READY.json')
        self.edit(run/'report.json',lambda x:x['header']['phase_separation'].update(
            inference_receipt_sha256=m.digest(m.read(run/'INFERENCE-READY.json')),
            inference_header=handoff['inference_header']))

    def test_valid_phase_packet_and_process_local_throughput(self):
        run = self.produce()
        result = self.consume(run)
        self.assertEqual(result['status'],'VALIDATED_DEV_CONDITIONAL_RUNTIME')
        self.assertEqual(result['runtime']['status'],'CONDITIONAL_PENDING_ACTUAL_RUNTIME_VALIDATION')
        legacy = self.f.produce(self.lane)
        legacy_result = self.c.consume(self.lane,legacy)
        for key in ('metrics','dev_comparisons','_vectors','runtime','publication',
                    'full_report_diagnostics','operator_fit'):
            self.assertEqual(result[key],legacy_result[key])

    def test_missing_each_phase_receipt_pending(self):
        for phase in ('infer','score'):
            for kind in ('LAUNCH','EXIT','BINDING'):
                with self.subTest(phase=phase,kind=kind):
                    run = self.produce()
                    (run.parent/(phase+'-'+kind+'.json')).unlink()
                    with self.assertRaises(m.Pending):self.consume(run)
        result, code = m.assemble(self.c,self.f.path/'runs',receipt_layout='phased')
        self.assertEqual(code,2)
        self.assertEqual(result['lanes'][0]['status'],'PENDING_MISSING_INPUT')

    def test_failed_infer_and_score_exit(self):
        for phase in ('infer','score'):
            for key in ('exit_code','container_exit_code'):
                with self.subTest(phase=phase,key=key):
                    run = self.produce()
                    self.edit(run.parent/(phase+'-EXIT.json'),lambda x:x.update({key:1}))
                    with self.assertRaisesRegex(m.Contradiction,'phase exit'):self.consume(run)
        (run.parent/'infer-LAUNCH.json').unlink()
        result, code = m.assemble(self.c,self.f.path/'runs',receipt_layout='phased')
        self.assertEqual(code,1)  # A known failure takes precedence over absent evidence.
        self.assertEqual(result['lanes'][0]['status'],'REFUSED_CONTRADICTION')

    def test_wrong_exact_container_id_each_phase(self):
        for phase in ('infer','score'):
            with self.subTest(phase=phase):
                run = self.produce()
                self.edit(run.parent/(phase+'-EXIT.json'),lambda x:x.update(container_id=phase+'-container'))
                with self.assertRaisesRegex(m.Contradiction,'container ID mismatch'):self.consume(run)

    def test_wrong_phase_binding(self):
        run = self.produce()
        self.edit(run.parent/'score-BINDING.json',lambda x:x.update(publication_sha256='f'*64))
        with self.assertRaisesRegex(m.Contradiction,'phase publication binding'):self.consume(run)

    def test_equal_phase_bindings_must_match_actual_publication(self):
        for field in ('publication_sha256','binding'):
            with self.subTest(field=field):
                run = self.produce()
                for phase in ('infer','score'):
                    def change(x):
                        if field == 'binding': x['binding']['owner'] = 'foreign-owner'
                        else: x[field] = 'f'*64
                    self.edit(run.parent/(phase+'-BINDING.json'),change)
                with self.assertRaisesRegex(m.Contradiction,'DEV launch publication'):self.consume(run)

    def test_inference_receipt_missing_pending(self):
        run = self.produce()
        (run/'INFERENCE-READY.json').unlink()
        with self.assertRaises(m.Pending):self.consume(run)

    def test_mismatched_inference_hash_and_copied_header(self):
        run = self.produce()
        self.edit(run/'report.json',lambda x:x['header']['phase_separation'].update(inference_receipt_sha256='f'*64))
        with self.assertRaisesRegex(m.Contradiction,'handoff SHA256'):self.consume(run)
        run = self.produce()
        self.edit(run/'report.json',lambda x:x['header']['phase_separation']['inference_header'].update(limit=2))
        with self.assertRaisesRegex(m.Contradiction,'handoff header'):self.consume(run)

    def test_repinned_foreign_inference_handoff(self):
        for key in ('adapter','descriptor','inference_header','groups','out'):
            with self.subTest(key=key):
                run = self.produce()
                def change(x):
                    if key == 'descriptor':x[key]['token_budget'] = 1
                    elif key == 'inference_header':x[key]['model']['sha256'] = 'f'*64
                    elif key == 'groups':x[key] = x[key][::-1]
                    else:x[key] = '/foreign'
                self.edit(run/'INFERENCE-READY.json',change)
                self.relink(run)
                with self.assertRaisesRegex(m.Contradiction,'inference handoff'):self.consume(run)

    def test_store_linkage_hash_receipt_and_population(self):
        for key in ('store_sha256','receipt_sha256','rows'):
            with self.subTest(key=key):
                run = self.produce()
                def change(x):x['stores']['decision-v7/dev/clean'][key] = 99 if key == 'rows' else 'f'*64
                self.edit(run/'INFERENCE-READY.json',change)
                self.relink(run)
                with self.assertRaises(m.Contradiction):self.consume(run)

    def test_owner_seed_and_terminal3116_preserved(self):
        run = self.produce()
        self.edit(Path(self.lane['new_adapter']).parent/'OWNER.json',lambda x:x['identity'].update(seed=3))
        with self.assertRaisesRegex(m.Contradiction,'seed'):self.consume(run)
        run = self.produce()
        self.edit(Path(self.lane['new_adapter']).parents[1]/'COMPLETE.json',lambda x:x.update(steps=3115))
        with self.assertRaisesRegex(m.Contradiction,'3116'):self.consume(run)

    def test_explicit_layout_cli_and_no_auto_detection(self):
        run = self.produce()
        with self.assertRaises(m.Pending):self.c.consume(self.lane,run)
        for lane in self.c.catalog['new_rc1_lanes'][1:]:self.produce(lane)
        output = self.f.path/'synthetic-comparison'
        argv = ['compare_dev.py','--run-root',str(self.f.path/'runs'),'--receipt-layout','phased','--output',str(output)]
        with patch.object(m,'Consumer',return_value=self.c),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),0)
        result = m.obj(output/'comparison.json')
        self.assertEqual(len(result['lanes']),8)
        self.assertTrue(all(x['status']=='VALIDATED_DEV_CONDITIONAL_RUNTIME' for x in result['lanes']))
        self.assertTrue(all(x['suites'] is not None for x in result['within_size_two_seed_means']))

if __name__ == '__main__':unittest.main(verbosity=2)
