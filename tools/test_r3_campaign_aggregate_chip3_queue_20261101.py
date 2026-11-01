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


A = load('r3_campaign_aggregate_chip3_queue_20261101')
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

    def assert_output_mutation_rejected(self, target):
        # Same deterministic interleaving for old Q.write and new byte writer.
        owner = A if hasattr(A, 'write_buffer') else Q
        name = 'write_buffer' if owner is A else 'write'
        original = getattr(owner, name)
        def mutate(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if Path(path).name == target:
                doc = Q.load(path); doc['unverified_mutation'] = True
                Path(path).write_text(json.dumps(doc))
        with patch.object(owner, name, side_effect=mutate):
            rc, _ = self.run_mocked()
        self.assertEqual(rc, 1)
        self.assertEqual(Q.load(self.root/'EXIT.json')['exit_code'], 1)
        self.assertTrue((self.root/'FAILURE.json').exists())
        self.assertTrue(Q.load(self.root/target)['unverified_mutation'])

    def test_campaign_output_mutation_rejected(self):
        self.assert_output_mutation_rejected('campaign.json')

    def test_evidence_output_mutation_rejected(self):
        self.assert_output_mutation_rejected('evidence.json')

    def test_source_snapshots_output_mutation_rejected(self):
        self.assert_output_mutation_rejected('source-snapshots.json')

    def test_result_output_mutation_rejected(self):
        self.assert_output_mutation_rejected('RESULT.json')

    def test_downstream_uses_retained_checked_buffers(self):
        self.assertEqual(self.run_mocked()[0], 0)
        pin = Q.load(self.root/'EXIT.json')['result_sha256']
        target = self.root/'campaign.json'
        original = Q.read
        def mutate_after_read(path):
            raw = original(path)
            if Path(path) == target:
                target.write_text('{"unverified_mutation":true}')
            return raw
        with patch.object(Q, 'read', side_effect=mutate_after_read):
            docs = A.verified_outputs(self.root, pin, Q)
        self.assertEqual(docs['campaign.json'], {'synthetic':'all-seven'})
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            A.verified_outputs(self.root, pin, Q)

    def test_canonical_correspondence_required_even_with_valid_byte_pins(self):
        self.assertEqual(self.run_mocked()[0], 0)
        path = self.root/'RESULT.json'; doc = Q.load(path)
        doc['canonical_sha256']['campaign.json'] = '0'*64
        Q.write(path, doc)
        with self.assertRaisesRegex(ValueError, 'canonical correspondence'):
            A.verified_outputs(self.root, Q.sha(path), Q)

    def test_exit_retains_result_pin_after_late_disk_mutation(self):
        original = Q.write; retained = {}
        def mutate_at_exit(path, doc, **kwargs):
            if Path(path).name == 'EXIT.json' and doc['exit_code'] == 0:
                retained['pin'] = Q.sha(self.root/'RESULT.json')
                result = Q.load(self.root/'RESULT.json'); result['unverified_mutation'] = True
                (self.root/'RESULT.json').write_text(json.dumps(result))
            return original(path, doc, **kwargs)
        with patch.object(Q, 'write', side_effect=mutate_at_exit):
            self.assertEqual(self.run_mocked()[0], 0)
        pin = Q.load(self.root/'EXIT.json')['result_sha256']
        self.assertEqual(pin, retained['pin'])
        self.assertNotEqual(pin, Q.sha(self.root/'RESULT.json'))
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            A.verified_outputs(self.root, pin, Q)

    def test_verified_documents_serialized_once(self):
        with patch.object(A, 'serialize', wraps=A.serialize) as serializer:
            self.assertEqual(self.run_mocked()[0], 0)
        self.assertEqual(serializer.call_count, 4)

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
        with patch.object(A, 'member_queue', return_value=(q['remaining_queue'], self.q)):
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


class SplitOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'queue.json'
        helper = self.root/'helper.py'; helper.write_text('# synthetic')
        code = {}
        for name in ('r3_campaign_sources.py','r3_final_campaign.py','r3_model_inventory.py','r3_selection_report.py'):
            p=self.root/name; p.write_text('# '+name); code[str(p)] = Q.sha(p)
        self.job = dict(id='instruct-k0', report='/new/report', terminal='/new/EXIT', producer_queue='/new/queue', producer_queue_sha256='new')
        self.mq = dict(schema='r3-member-rebuild-queue-v5', jobs=[self.job.copy()], code=code,
                       controller=dict(path=str(helper),sha256=Q.sha(helper)), closure_manifest={},
                       kev_dir='/kev',data_root='/data',scientific_acceptance=False,test_read=False)
        self.q = dict(code=code,helper=self.mq['controller'],closure_manifest={},kev_dir='/kev',data_root='/data')
        self.job['rebuild_root']=str(self.root/'members/instruct-k0')
        self.freeze()

    def freeze(self):
        Q.write(self.path,self.mq)
        self.q['rebuild_queues']={'instruct-k0':dict(path=str(self.path),sha256=Q.sha(self.path))}

    def test_authentic_member_queue(self):
        b,mq=A.member_queue(self.job,self.q,Q)
        self.assertEqual(b['sha256'],Q.sha(self.path)); self.assertEqual(mq,self.mq)

    def test_old_report_cannot_be_relabelled(self):
        self.job['report']='/old/report'
        with self.assertRaisesRegex(ValueError,'producer job differs'): A.member_queue(self.job,self.q,Q)

    def test_receipts_cannot_be_moved_to_new_root(self):
        self.job['rebuild_root']='/new/members/instruct-k0'
        with self.assertRaisesRegex(ValueError,'output owner'): A.member_queue(self.job,self.q,Q)

    def test_source_change_rejected(self):
        p=next(iter(self.q['code'])); Path(p).write_text('changed')
        with self.assertRaisesRegex(ValueError,'source bytes'): A.member_queue(self.job,self.q,Q)

    def test_nonplacement_change_rejected(self):
        self.mq['data_root']='/foreign'; self.freeze()
        with self.assertRaisesRegex(ValueError,'reconstruction sources'): A.member_queue(self.job,self.q,Q)

    def test_wrong_queue_pin_rejected(self):
        self.q['rebuild_queues']['instruct-k0']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'artifact changed'): A.member_queue(self.job,self.q,Q)

    def test_duplicate_member_rejected(self):
        self.mq['jobs'] *= 2; self.freeze()
        with self.assertRaisesRegex(ValueError,'producer job differs'): A.member_queue(self.job,self.q,Q)

if __name__ == '__main__': unittest.main()
