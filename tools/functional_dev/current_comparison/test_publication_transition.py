"""Finite synthetic CPU checks using the exact predecessor fixture and Consumer."""
import contextlib
import ast
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

W=load('publication_candidate',HERE/'watcher.py')
B=load('publication_baseline',HERE/'watcher_before_publication_fix.py')
F=load('publication_fixture',HERE/'fixtures.py')

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.c,self.inspections=F.build(self.tmp.name);self.c['poll_seconds']=600
        self.prod=dict(self.c,mode='production');self.output=Path(self.c['output'])
        self.target=Path(self.c['k0_root'])/'4b-k0/score-EXIT.json'
        self.saved=self.target.read_bytes()
        for model in self.c['models'][2:]:
            for lane in [None]+[v for v in self.c['lanes'] if v['baseline_id']==model['id']]:
                d=Path(self.c['k0_root'])/model['id'] if lane is None else Path(self.c['adapter_root'])/('full-'+lane['lane'])
                (d/'score-EXIT.json').unlink()
        self.stdout=io.StringIO();self.polls=[]

    def execute(self,mutation=lambda:None,subject=W,once=True,during=False):
        consumer=subject.M.Consumer;assemble=subject.M.assemble
        def consume(config):
            return consumer(self.c,inspector=self.inspections.__getitem__,allow_fixture=True)
        def collect(value):
            if during and not self.polls:mutation()
            result,code=assemble(value)
            self.polls.append({'code':code,'status':result['status'],'validated':sum(v['status']=='VALIDATED_OPERAND' for v in result['operands'])})
            if not during and len(self.polls)==1:mutation()
            return result,code
        with patch.object(subject,'review',return_value=True),patch.object(subject.M,'Consumer',side_effect=consume),patch.object(subject.M,'assemble',side_effect=collect),contextlib.redirect_stdout(self.stdout):
            return subject.run(self.prod,once=once)

    def publish(self):self.target.write_bytes(self.saved)

    def comparison(self):return json.loads((self.output/'comparison.json').read_text())

    def pending(self):
        value=json.loads((self.output/'WATCHER-PENDING.json').read_text())
        self.assertEqual(value['reason'],'INITIAL_MISSING_PHASE_INPUT_PUBLISHED')
        self.assertEqual(value['roles'],['4b-k0']);self.assertEqual(value['exit_code'],2)
        self.assertEqual(value['retry_seconds'],600)
        self.assertIn(value,json.loads('['+','.join(self.stdout.getvalue().splitlines())+']'))
        return value

    def test_exact_predecessor_race_refuses(self):
        with self.assertRaisesRegex(B.M.Contradiction,'source/input changed during reconstruction; packet refused'):
            self.execute(self.publish,subject=B)
        self.assertEqual(self.polls,[{'code':2,'status':'INCOMPLETE_PENDING','validated':6}])

    def test_exact_race_discards_then_stable_seven_then_real_numerical_refusal(self):
        self.assertEqual(self.execute(self.publish),2);self.pending()
        self.assertFalse((self.output/'comparison.json').exists())
        self.assertEqual(self.execute(),2)
        self.assertEqual([x['validated'] for x in self.polls],[6,7])
        self.assertEqual(self.comparison()['status'],'INCOMPLETE_PENDING')
        self.assertFalse((self.output/'WATCHER-PENDING.json').exists())
        report=Path(self.c['k0_root'])/'4b-k0/result/clean-report.json'
        value=json.loads(report.read_text());value['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=0.123
        report.write_text(json.dumps(value));self.assertEqual(self.execute(),1)
        self.assertEqual(self.comparison()['status'],'REFUSED_CONTRADICTION')

    def test_last_valid_pending_snapshot_retained_byte_for_byte(self):
        self.assertEqual(self.execute(),2);old=(self.output/'comparison.json').read_bytes()
        self.polls.clear();self.assertEqual(self.execute(self.publish),2);self.pending()
        self.assertEqual((self.output/'comparison.json').read_bytes(),old)
        self.assertEqual(self.execute(),2);self.assertEqual(self.polls[-1]['validated'],7)

    def test_publication_before_consume_discards_even_if_new_operand_validated(self):
        self.assertEqual(self.execute(self.publish,during=True),2);self.pending()
        self.assertEqual(self.polls[-1]['validated'],7)
        self.assertFalse((self.output/'comparison.json').exists())

    def test_continuous_loop_retries_at_600_without_unchanged_skip(self):
        def sleep(seconds):
            self.assertEqual(seconds,600)
            if len(self.polls)==2:raise StopIteration('bounded after stable retry')
        with patch.object(W.time,'sleep',side_effect=sleep):
            with self.assertRaisesRegex(StopIteration,'bounded after stable retry'):
                self.execute(self.publish,once=False)
        self.assertEqual([x['validated'] for x in self.polls],[6,7])
        self.assertEqual(sum(v['status']=='VALIDATED_OPERAND' for v in self.comparison()['operands']),7)

    def test_completion_with_simultaneous_corruption_refuses(self):
        paths=[Path(self.c['k0_root'])/'08b-k0/result/clean-report.json',
               Path(next(iter(self.c['source_pins']))),
               Path(self.c['k0_root'])/'4b-k0/result/clean-report.json',
               Path(self.c['k0_root'])/'4b-k0/result/trackk/decision-v7__dev/clean.jsonl',
               Path(self.c['review'])]
        for path in paths:
            with self.subTest(path=path):
                saved=path.read_bytes() if path.exists() else None
                self.polls.clear();self.target.unlink(missing_ok=True)
                def corrupt():
                    self.publish();path.write_bytes((saved or b'')+b'\n')
                try:
                    with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
                        self.execute(corrupt)
                finally:
                    if saved is None:path.unlink(missing_ok=True)
                    else:path.write_bytes(saved)

    def test_read_source_mutation_without_completion_refuses(self):
        source=Path(next(iter(self.c['source_pins'])))
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(lambda:source.write_bytes(source.read_bytes()+b'\n'))

    def test_existing_phase_receipt_rewrite_is_not_first_publication(self):
        phase=self.target.with_name('infer-EXIT.json')
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(lambda:phase.write_bytes(phase.read_bytes()+b'\n'))

    def test_contradiction_is_not_masked_by_new_completion(self):
        value=json.loads(self.saved);value['exit_code']=1
        self.target.write_text(json.dumps(value))
        other=Path(self.c['adapter_root'])/'full-q4b-s2/score-EXIT.json'
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(lambda:other.write_bytes(self.saved))

    def test_old_refusal_is_preserved_without_assembly(self):
        self.output.mkdir();W.M.persist(self.output,{'status':'REFUSED_CONTRADICTION','detail':'old failure'})
        old=(self.output/'comparison.json').read_bytes()
        self.assertEqual(self.execute(self.publish),1);self.assertEqual(self.polls,[])
        self.assertEqual((self.output/'comparison.json').read_bytes(),old)

    def test_existing_pending_store_guard(self):
        d=Path(self.c['k0_root'])/'4b-k0';(d/'infer-EXIT.json').unlink();(d/'result/INFERENCE-READY.json').unlink()
        store=d/'result/trackk/decision-v7__dev/clean.jsonl'
        self.assertEqual(self.execute(lambda:store.write_bytes(store.read_bytes()+b'\n')),2)
        self.assertIn('Unpublished producer stores changed',self.comparison()['detail'])
        self.assertFalse((self.output/'WATCHER-PENDING.json').exists())

    def test_pending_store_after_handoff_still_refuses(self):
        store=Path(self.c['k0_root'])/'4b-k0/result/trackk/decision-v7__dev/clean.jsonl'
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(lambda:store.write_bytes(store.read_bytes()+b'\n'))

    def test_unpublished_store_corruption_read_during_poll_still_refuses(self):
        # Direct guard check: pre-existing store changes, is then read by Consumer,
        # and a missing terminal appears. Initial unreadness cannot excuse a read.
        d=Path(self.c['k0_root'])/'4b-k0';(d/'infer-EXIT.json').unlink();(d/'result/INFERENCE-READY.json').unlink()
        store=d/'result/trackk/decision-v7__dev/clean.jsonl';before=W.fingerprint(self.c)
        store.write_bytes(store.read_bytes()+b'\n');W.M._accesses.clear();W.M.read(store);self.publish()
        result={'operands':[{'status':'PENDING_MISSING_INPUT'}]*12}
        self.assertIsNone(W.pending_phase_publication(self.c,before,W.fingerprint(self.c),result,2))

    def test_source_config_review_and_other_role_paths_cannot_be_whitelisted(self):
        before=W.fingerprint(self.c);self.publish();after=W.fingerprint(self.c)
        result={'operands':[{'status':'PENDING_MISSING_INPUT'}]*12}
        protected=[W.HERE/'config.json',W.HERE/'consumer.py',W.HERE/'watcher.py',
                   W.HERE/'numeric_sources/metrics.py',Path(self.c['review']),
                   Path(self.c['lanes'][0]['new_adapter'])/'PUBLICATION.json',
                   Path(self.c['adapter_root'])/'full-q2b-s2/score-EXIT.json',
                   Path(self.c['adapter_root'])/'q4b-s2-ERROR.json']
        with patch.dict(W.M._accesses,{},clear=True):
            self.assertIsNotNone(W.pending_phase_publication(self.c,before,after,result,2))
            for path in protected:
                altered=[x for x in after if x[0]!=str(path)]+[[str(path),123,456,789,101]]
                self.assertIsNone(W.pending_phase_publication(self.c,before,altered,result,2),str(path))

    def test_new_missing_receipt_without_initial_phase_gap_still_refuses(self):
        self.publish();receipt=self.target.parent/'result/trackk/decision-v7__dev/clean.jsonl.receipt.json'
        saved=receipt.read_bytes();receipt.unlink()
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(lambda:receipt.write_bytes(saved))

    def test_adapter_first_publication_is_owned_and_retries(self):
        self.publish();self.target=Path(self.c['adapter_root'])/'full-q4b-s2/score-EXIT.json'
        launch=json.loads(self.target.with_name('score-LAUNCH.json').read_text())
        self.saved=json.dumps({'exit_code':0,'container_exit_code':0,'container_id':launch['container_id']}).encode()
        self.assertEqual(self.execute(self.publish),2)
        pending=json.loads((self.output/'WATCHER-PENDING.json').read_text())
        self.assertEqual(pending['roles'],['q4b-s2'])
        self.assertFalse((self.output/'comparison.json').exists())
        self.assertEqual(self.execute(),2);self.assertEqual(self.polls[-1]['validated'],8)

    def test_failed_first_publication_read_by_consumer_refuses(self):
        value=json.loads(self.saved);value['exit_code']=1;self.saved=json.dumps(value).encode()
        with self.assertRaisesRegex(W.M.Contradiction,'changed during reconstruction'):
            self.execute(self.publish,during=True)
        self.assertEqual(self.polls[-1]['code'],1)

    def test_all_twelve_completion_crossing_poll_is_still_discarded(self):
        for model in self.c['models'][2:]:
            for lane in [None]+[v for v in self.c['lanes'] if v['baseline_id']==model['id']]:
                d=Path(self.c['k0_root'])/model['id'] if lane is None else Path(self.c['adapter_root'])/('full-'+lane['lane'])
                # Exact fixtures construct phase terminals from launch identity.
                launch=json.loads((d/'score-LAUNCH.json').read_text())
                if lane is not None:F.put(d/'score-EXIT.json',{'exit_code':0,'container_exit_code':0,'container_id':launch['container_id']})
        # Restore the remaining Base terminal from a fresh consume-compatible copy.
        other=Path(self.c['k0_root'])/'9b-k0'
        hand=json.loads((other/'result/INFERENCE-READY.json').read_text())
        launch=json.loads((other/'score-LAUNCH.json').read_text())
        F.put(other/'score-EXIT.json',{'exit_code':0,'container_exit_code':0,'container_id':launch['container_id'],
             'artifact_evidence':{'inference_sha256':W.M.sha(other/'result/INFERENCE-READY.json'),
             'stores':hand['stores'],'report_sha256':W.M.sha(other/'result/clean-report.json')}})
        self.assertEqual(self.execute(self.publish,during=True),2)
        self.assertEqual(self.polls[-1]['code'],0);self.assertEqual(self.polls[-1]['validated'],12)
        self.assertFalse((self.output/'comparison.json').exists())
        self.assertEqual(self.execute(),0)

    def test_current_materializer_examine_accepts_pending_and_stable_contract(self):
        # Compile only its actual pure DEV examine function. No materializer
        # imports, production reads, TEST populations or dispatcher execution.
        path=HERE.parents[1]/'functional_test/preparation/materializer.py'
        tree=ast.parse(path.read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='examine')
        lanes=[x['lane'] for x in self.c['lanes']]
        env={'C':SimpleNamespace(LANES=lanes,BASES=['q0p8b-base','q2b-base','q4b-base','q9b-base']),
             'collector':SimpleNamespace(ROOT=Path(self.tmp.name)/'train')}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
        self.assertEqual(self.execute(),2);before=(self.output/'comparison.json').read_bytes()
        self.polls.clear();self.assertEqual(self.execute(self.publish),2)
        self.assertEqual((self.output/'comparison.json').read_bytes(),before)
        train={lane:{'status':'training_verified'} for lane in lanes}
        statuses=env['examine'](self.c,self.comparison(),train,W.M)
        self.assertEqual(sum(x['status']=='ready' for x in statuses),6)
        self.assertFalse(any(x['status']=='contradiction' for x in statuses))
        self.assertEqual(self.execute(),2)
        statuses=env['examine'](self.c,self.comparison(),train,W.M)
        self.assertEqual(sum(x['status']=='ready' for x in statuses),7)
        self.assertFalse(any(x['status']=='contradiction' for x in statuses))

if __name__=='__main__':unittest.main(verbosity=2)
