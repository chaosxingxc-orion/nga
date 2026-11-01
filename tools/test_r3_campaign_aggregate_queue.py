"""Synthetic controller regressions. Expensive reconstruction mocked explicitly.

Runtime r3_campaign_aggregate_queue.reconstruct calls real C.verify; these tests
exercise queue fault handling without production data, model runs, or network.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


A = load('r3_campaign_aggregate_queue')
Q = load('r3_member_rebuild_queue')


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'queue.json'
        self.vroot = self.root/'v5'; self.vroot.mkdir()
        self.q = dict(remaining_queue={'path':str(self.vroot/'queue.json'), 'sha256':'v5'},
                      jobs=[], code={str(self.root/'r3_selection_report.py'):'tool'},
                      closure_manifest={'path':str(self.root/'manifest.json'),'sha256':'closure'},
                      kev_dir=str(self.root/'kev'), data_root=str(self.root/'data'))
        for i in range(7):
            proot = self.root/f'producer{i}'; (proot/'jobs'/f'j{i}').mkdir(parents=True)
            report = proot/'selection_report.json'; Q.write(report, {'synthetic':i})
            pq = proot/'queue.json'; Q.write(pq, {'jobs':[{'id':f'j{i}', 'kind':'report','output':str(report)}]})
            end = proot/'jobs'/f'j{i}'/'EXIT.json'
            Q.write(end,dict(exit_code=0,scientific_acceptance=False,output_sha256=Q.sha(report)))
            self.q['jobs'].append(dict(id=f'j{i}', producer_queue=str(pq), producer_queue_sha256=Q.sha(pq),
                terminal=str(end), report=str(report), base_inventory=None, adapter_inventory=None,
                expected={'synthetic':i}))
        Q.write(self.path,self.q); self.pin = Q.sha(self.path)

    def test_waiting_requires_terminal_and_no_reconstruction(self):
        Path(self.q['jobs'][3]['terminal']).unlink()
        states, bindings = A.readiness(self.q,Q)
        self.assertEqual(states['j3'],'waiting_report_terminal'); self.assertEqual(len(bindings),6)

    def test_terminal_failure_and_boolean_zero_refused(self):
        for code in (1, False):
            Q.write(self.q['jobs'][0]['terminal'],dict(exit_code=code,scientific_acceptance=False))
            with self.assertRaisesRegex(ValueError,'integer exit'): A.readiness(self.q,Q)

    def test_corrupt_report_and_duplicate_owner(self):
        j = self.q['jobs'][0]
        Path(j['report']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'output differs'): A.readiness(self.q,Q)
        d=Q.load(j['producer_queue']); d['jobs'].append(dict(d['jobs'][0],id='foreign'))
        Q.write(j['producer_queue'],d); j['producer_queue_sha256']=Q.sha(j['producer_queue'])
        with self.assertRaisesRegex(ValueError,'multiple owners'): A.readiness(self.q,Q)

    def test_legacy_producer_exact_mapping(self):
        j=self.q['jobs'][0]; j['legacy_report_queue']=True
        d=Q.load(j['producer_queue']); d.update(schema='r3-cpu-report-queue-v1',scientific_acceptance=False,test_read=False)
        old=Path(j['report']); out=old.parent/'eval'; (out/'results').mkdir(parents=True)
        report=out/'results/selection_report.json'; report.write_bytes(Q.read(old)); j['report']=str(report)
        d['jobs'][0]=dict(id=j['id'],output=str(report),eval_out=str(out))
        Q.write(j['producer_queue'],d); j['producer_queue_sha256']=Q.sha(j['producer_queue'])
        self.assertEqual(A.producer(j,Q)['report']['path'],str(report))
        d['jobs'][0]['eval_out']='/foreign'; Q.write(j['producer_queue'],d); j['producer_queue_sha256']=Q.sha(j['producer_queue'])
        with self.assertRaisesRegex(ValueError,'legacy producer mapping'): A.producer(j,Q)

    def test_failure_sticky_after_restored_receipt(self):
        j=self.q['jobs'][0]; Q.write(Path(j['terminal']).parent/'FAILURE.json',{'synthetic':True})
        with self.assertRaisesRegex(ValueError,'sticky'): A.readiness(self.q,Q)

    def test_pinned_existing_report_terminal(self):
        j=self.q['jobs'][0]; j['terminal_pin']=Q.sha(j['terminal'])
        d=Q.load(j['terminal']); d['extra']='modified'; Q.write(j['terminal'],d)
        with self.assertRaisesRegex(ValueError,'existing terminal'): A.readiness(self.q,Q)

    def test_controller_bootstrap_rejects_changed_source(self):
        target=self.root/'controller.py'; target.write_text('raise RuntimeError("executed")')
        r=subprocess.run([sys.executable,'-P','-c',Q.BOOTSTRAP,str(target),'0'*64],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0); self.assertIn('controller bytes changed',r.stderr)
        self.assertNotIn('RuntimeError: executed',r.stderr)

    def test_manifest_single_buffer_and_controller_pin(self):
        q=dict(controller={'path':str(Path(A.__file__).absolute()),'sha256':'executed'},
               helper={'path':str(self.root/'helper.py'),'sha256':'helper'})
        raw=json.dumps(q).encode()
        with patch.object(A,'_EXECUTED_SHA256','executed',create=True), \
             patch.object(A,'read_once',side_effect=[raw,b'value=1']) as reader, \
             patch.object(A,'validate'):
            actual, helper=A.initialize(str(self.path),'pin')
        self.assertEqual(actual,q); self.assertEqual(helper.value,1); self.assertEqual(reader.call_count,2)
        with patch.object(A,'read_once',return_value=raw), self.assertRaisesRegex(ValueError,'pinned bootstrap'):
            A.initialize(str(self.path),'pin')

    def test_symlink_and_duplicate_manifest_keys(self):
        alias=self.root/'alias'; alias.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError,'unsafe'): A.read_once(alias)
        with patch.object(A,'read_once',return_value=b'{"a":1,"a":2}'):
            with self.assertRaisesRegex(ValueError,'duplicate'): A.initialize(str(self.path),'pin')

    def run_mocked(self, side_effect=None):
        # Explicit mock of expensive production reconstruction only. Real producer
        # receipt/readiness checks and real filesystem lifecycle remain active.
        result={'campaign':{'synthetic':'all-seven'}, 'sources':[]}
        with patch.object(A,'validate'), patch.object(A,'reconstruct',
             side_effect=side_effect,return_value=(result,{'before':[],'after':[]})) as rebuild:
            rc=A.run(str(self.path),self.pin,self.q,Q)
        return rc,rebuild

    def test_actual_work_path_and_exclusive_outputs(self):
        rc,rebuild=self.run_mocked(); self.assertEqual(rc,0); rebuild.assert_called_once()
        self.assertEqual(len(Q.load(self.root/'request.json')['members']),7)
        self.assertEqual(Q.load(self.root/'EXIT.json')['exit_code'],0)
        with self.assertRaisesRegex(ValueError,'no restart'): self.run_mocked()

    def test_existing_output_never_overwritten(self):
        Q.write(self.root/'campaign.json',{'owner':'other'},exclusive=True)
        rc,_=self.run_mocked(); self.assertEqual(rc,1)
        self.assertEqual(Q.load(self.root/'campaign.json'),{'owner':'other'})
        self.assertTrue((self.root/'FAILURE.json').exists())

    def test_mutation_during_rebuild_fails_sticky(self):
        def expensive_mock(*args):
            j=self.q['jobs'][0]; d=Q.load(j['terminal']); d['extra']='mutated'; Q.write(j['terminal'],d)
            return {'campaign':{}}, {}
        rc,_=self.run_mocked(expensive_mock); self.assertEqual(rc,1)
        self.assertIn('producer changed during rebuild',Q.load(self.root/'FAILURE.json')['error'])
        self.assertFalse((self.root/'campaign.json').exists())

    def test_uncertain_start_not_relaunched(self):
        Q.write(self.root/'STARTED.json',{'synthetic':'prior run'})
        with self.assertRaisesRegex(ValueError,'no restart'): self.run_mocked()

    def test_waiter_does_not_rebuild_until_all_ready(self):
        terminal=Path(self.q['jobs'][0]['terminal']); saved=Q.read(terminal); terminal.unlink()
        with patch.object(A.time,'sleep',side_effect=lambda _:terminal.write_bytes(saved)) as sleep:
            rc,rebuild=self.run_mocked()
        self.assertEqual(rc,0); sleep.assert_called_once_with(30); rebuild.assert_called_once()

    def test_common_snapshot_mutation_detected_with_mocked_expensive_verifier(self):
        snaps=[{'files':{'x':'before'}} for _ in range(7)]
        counter=[0]
        def snapshot(*args):
            i=counter[0]; counter[0]+=1
            return copy.deepcopy(snaps[i%7] if i<7 else {'files':{'x':'changed'}})
        fake=types.SimpleNamespace(source_snapshot=snapshot, scope=lambda x:x, artifact=lambda x:{},
            module=lambda *x:None, rebuild_member=lambda *x:None,
            verify=lambda req:{'campaign':{'members':[{}]*7},'sources':[{'source_snapshot':s} for s in snaps]})
        request={'members':[{'report':{}}]*7,'report_tool':{'path':'unused'}}
        with patch.object(Q,'sources',return_value=fake),patch.object(Q,'identity'):
            with self.assertRaisesRegex(ValueError,'common boundary'): A.reconstruct(self.q,request,Q,{})


# Reuse reviewed synthetic v5 envelope fixtures, with its expensive replay mocked.
V = load('test_r3_member_rebuild_queue')
class V5BindingTests(V.QueueEvidenceTests):
    def check_binding(self):
        job=dict(self.job,rebuild_root=str(self.out))
        q={'remaining_queue':{'path':str(self.path),'sha256':self.pin}}
        return A.remaining_binding(job,q,V.Q)

    def test_aggregate_v5_binding(self):
        result=self.check_binding(); self.assertEqual(result['entry'],self.req['entry'])
        self.assertEqual(len(result['receipt_pins']),5)
        self.replay.assert_not_called()  # Binding only; aggregate performs fresh C.verify.

    def test_aggregate_corrupt_v5_result(self):
        self.result['outputs']={}; self.finish()
        with self.assertRaisesRegex(ValueError,'receipt hash/output'): self.check_binding()

    def test_aggregate_failure_wins_over_success(self):
        V.Q.write(self.out/'FAILURE.json',dict(self.common,state='failed_no_retry'))
        with self.assertRaisesRegex(ValueError,'sticky'): self.check_binding()


if __name__ == '__main__': unittest.main()
