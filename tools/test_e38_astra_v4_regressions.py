"""Independent actual-Astra-v3 blockers on rejected E38 v4 plans.

Filesystem spies check the actual syscall ordering on a temporary local tree;
they do not simulate or claim a Ceph power-loss/recovery experiment.
"""
import copy
import contextlib
import time
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(filename):
    spec = importlib.util.spec_from_file_location('astra_v4_' + Path(filename).stem,
                                                Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


f = module('test_e38_astra_regressions.py')
v = module('verify_openjev_path_trace.py')
e = module('e38_evidence.py')


class FullReceiptConfidenceRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        (self.out / 'items').mkdir(); (self.out / 'attempts').mkdir()
        contract, self.trace = f.trace_plan_and_value()
        self.plan = dict(out=str(self.out), execution_revision='astra-v3-strict-attempts',
                         schedule=v.schedule(), source_config_sha256='frozen-source',
                         trace_contract=contract['trace_contract'], **f.plan_for(f.FIXTURE['records'][0]))
        self.ph = f.stamp(self.plan)

    def population(self, saturated=False, confidence=None):
        pred = f.actual_prediction(f.FIXTURE['records'][0])
        keys = self.plan['input']['candidate_order']
        probs = {k: (float(i == 0) if saturated else 1 / 15) for i, k in enumerate(keys)}
        pred['native_probabilities'] = probs
        # exp(-2000/T) underflows for the actual native T; one-hot is consistent.
        pred['logits'] = [0.] + [-2000.] * 14 if saturated else [0.] * 15
        pred['answer'] = f.independent_wire(probs)
        if confidence is not None: pred['answer']['confidence'] = confidence
        for task in v.schedule():
            filename = v.name(task) + '.json'
            ident = dict(plan_sha256=self.ph,
                         source_config_sha256=self.plan['source_config_sha256'],
                         input_sha256=f.stamp(self.plan['input']),
                         request_sha256=self.plan['input']['request_sha256'], index=4200, **task)
            intent = dict(**ident, phase='forward_intent', utc='2026-10-31T00:00:00Z')
            f.write(self.out / 'attempts' / filename, intent)
            tr = copy.deepcopy(self.trace) if task['traced'] else {}
            if task['traced'] and task['mode'] == 'chunk8':
                tr['chunks'] = [dict(range=x, order=tr['order'][:]) for x in [[0,8,186],[8,15,186]]]
            payload = dict(**ident, prediction=copy.deepcopy(pred), trace=tr,
                           attempt_sha256=f.digest((self.out / 'attempts' / filename).read_bytes()),
                           observed_input={k:self.plan['input'][k] for k in
                                           ['shape','ordered_id_row_hashes','ordered_mask_row_hashes']},
                           chips=1, seconds=2., questions_per_second_per_chip=.5,
                           reserved_gib=1., peak_allocated_gib=1., peak_reserved_gib=1.)
            f.write(self.out / 'items' / filename, dict(payload=payload, sha256=f.stamp(payload)))

    def assert_good_population(self, saturated):
        self.population(saturated)
        checked = v.validate_items(self.plan, self.ph, complete=True)
        self.assertEqual(len(checked), 8)
        report = v.reconstruct(checked)
        self.assertEqual(len(report['controls']), 11)
        self.assertTrue(all(report['controls'].values()))
        self.assertTrue(report['trace_valid'])

    def test_valid_uniform_complete_eight_receipts_pass(self):
        self.assert_good_population(False)

    def test_valid_saturated_complete_eight_receipts_pass(self):
        self.assert_good_population(True)

    def test_negative_confidence_full_eight_receipts_rejected(self):
        self.assert_good_population(False)
        self.population(False, -5e-8)
        with self.assertRaisesRegex(ValueError, '[Cc]onfidence'):
            v.validate_items(self.plan, self.ph, complete=True)

    def test_above_one_confidence_full_eight_receipts_rejected(self):
        self.assert_good_population(True)
        self.population(True, 1 + 5e-8)
        with self.assertRaisesRegex(ValueError, '[Cc]onfidence'):
            v.validate_items(self.plan, self.ph, complete=True)


class SyscallOrder:
    """Observe real calls, optionally fail one fsync; never model Ceph recovery."""
    def __init__(self, fail_sync=None):
        self.events = []; self.fail_sync = fail_sync

    def path(self, value, dir_fd=None):
        p = Path(value)
        if not p.is_absolute():
            p = Path(os.readlink('/proc/self/fd/' + str(dir_fd))) / p if dir_fd is not None else Path.cwd() / p
        return str(p)

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        sync, link, unlink, mkdir, rename = os.fsync, os.link, os.unlink, os.mkdir, os.rename
        def record_sync(fd):
            target = os.readlink('/proc/self/fd/' + str(fd)); self.events.append(('fsync', target))
            if self.fail_sync and self.fail_sync(target, self.events): raise OSError('injected fsync failure')
            return sync(fd)
        def record_link(source, target, *args, **kwargs):
            self.events.append(('link', self.path(source, kwargs.get('src_dir_fd')), self.path(target, kwargs.get('dst_dir_fd'))))
            return link(source, target, *args, **kwargs)
        def record_unlink(path, *args, **kwargs):
            self.events.append(('unlink', self.path(path, kwargs.get('dir_fd'))))
            return unlink(path, *args, **kwargs)
        def record_mkdir(path, *args, **kwargs):
            result = mkdir(path, *args, **kwargs)
            self.events.append(('mkdir', self.path(path, kwargs.get('dir_fd')))); return result
        def record_rename(source, target, *args, **kwargs):
            self.events.append(('rename', self.path(source, kwargs.get('src_dir_fd')), self.path(target, kwargs.get('dst_dir_fd'))))
            return rename(source, target, *args, **kwargs)
        for name, call in [('fsync',record_sync),('link',record_link),('unlink',record_unlink),('mkdir',record_mkdir),('rename',record_rename)]:
            self.stack.enter_context(patch.object(os,name,side_effect=call))
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)


class DurabilityOrderRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'generation'; self.out.mkdir()

    def assert_chain_before(self, events, path, before):
        # Includes the generation's own entry in its parent and every ancestor.
        for directory in [path, *path.parents]:
            self.assertIn(('fsync', str(directory)), events[:before], str(directory))

    def test_first_forward_intent_persists_precreated_attempt_directory_chain(self):
        attempts = self.out / 'attempts'; attempts.mkdir()
        (self.out / 'items').mkdir()
        target = attempts / 'first.json'
        with SyscallOrder() as calls:
            e.publish_new(target, {'phase':'forward_intent'})
            calls.events.append(('possible_forward',))
        link_at = next(i for i,x in enumerate(calls.events) if x[0]=='link')
        self.assert_chain_before(calls.events, attempts, link_at)
        self.assertIn(('fsync',str(attempts)), calls.events[link_at+1:-1])
        self.assertTrue(target.is_file())

    def test_new_directory_entries_are_synced_before_intent_publication(self):
        target = self.out / 'nested' / 'attempts' / 'first.json'
        with SyscallOrder() as calls: e.publish_new(target, {'phase':'forward_intent'})
        link_at = next(i for i,x in enumerate(calls.events) if x[0]=='link')
        self.assert_chain_before(calls.events, target.parent, link_at)
        for path in (self.out/'nested', target.parent):
            created = calls.events.index(('mkdir',str(path)))
            self.assertIn(('fsync',str(path)), calls.events[created+1:link_at])
            self.assertIn(('fsync',str(path.parent)), calls.events[created+1:link_at])

    def test_exit_move_commits_destination_before_unlinking_source(self):
        source=self.out/'EXIT'; source.write_text('rc=137 original-exit')
        target=self.out/'resume_history'/'generation-token'/'EXIT'
        with SyscallOrder() as calls: e.durable_move(source,target)
        link_at=calls.events.index(('link',str(source),str(target)))
        unlink_at=calls.events.index(('unlink',str(source)))
        self.assert_chain_before(calls.events,target.parent,link_at)
        self.assertIn(('fsync',str(source)),calls.events[:link_at])
        self.assertIn(('fsync',str(target.parent)),calls.events[link_at+1:unlink_at])
        self.assertIn(('fsync',str(source.parent)),calls.events[unlink_at+1:])
        self.assertEqual(target.read_text(),'rc=137 original-exit');self.assertFalse(source.exists())

    def test_failed_destination_barrier_retains_both_exit_names(self):
        source=self.out/'EXIT';source.write_text('rc=137 original-exit')
        target=self.out/'resume_history'/'generation-token'/'EXIT'
        fail=lambda path,events:path==str(target.parent) and any(x[0]=='link' for x in events)
        with SyscallOrder(fail) as calls:
            with self.assertRaisesRegex(OSError,'injected fsync'):e.durable_move(source,target)
        self.assertNotIn(('unlink',str(source)),calls.events)
        self.assertEqual(source.read_bytes(),target.read_bytes())

    def test_same_inode_interrupted_exit_move_resumes_after_destination_barrier(self):
        source=self.out/'EXIT';source.write_text('rc=137 original-exit')
        target=self.out/'resume_history'/'generation-token'/'EXIT'
        target.parent.mkdir(parents=True);os.link(source,target)
        self.assertEqual(source.stat().st_ino,target.stat().st_ino)
        with SyscallOrder() as calls:e.durable_move(source,target)
        removed=calls.events.index(('unlink',str(source)))
        self.assertIn(('fsync',str(target.parent)),calls.events[:removed])
        self.assertIn(('fsync',str(source.parent)),calls.events[removed+1:])
        self.assertFalse(source.exists())
        self.assertEqual(target.read_text(),'rc=137 original-exit')

    def test_same_bytes_different_inode_history_never_replaces_or_deletes(self):
        source=self.out/'EXIT';source.write_text('rc=137 original-exit')
        target=self.out/'resume_history'/'generation-token'/'EXIT'
        target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
        self.assertNotEqual(source.stat().st_ino,target.stat().st_ino)
        with SyscallOrder() as calls:
            with self.assertRaises(ValueError):e.durable_move(source,target)
        self.assertFalse(any(x[0] in ('link','unlink','rename') for x in calls.events))
        self.assertEqual(source.read_text(),'rc=137 original-exit')
        self.assertEqual(target.read_bytes(),source.read_bytes())

    def test_review_interruption_resumes_committed_exit_link_and_forgets_old_snapshot(self):
        prepare=module('prepare_openjev_path_trace.py')
        source=self.out/'EXIT';source.write_text('rc=137 utc=2026-10-31T00:00:00Z\n')
        actual=dict(Id='retained-fixture',State=dict(Status='exited',ExitCode=137,
                                                    FinishedAt='2026-10-31T00:00:00Z'))
        token=hashlib.sha256((actual['Id']+'\n'+actual['State']['FinishedAt']).encode()).hexdigest()
        target=self.out/'resume_history'/token/'EXIT'
        target.parent.mkdir(parents=True);os.link(source,target)
        before=source.read_bytes()
        f.write(self.out/'RESUME_REVIEW.json',dict(approved_plan_sha256='plan-sha',
                container_id=actual['Id'],finished_at=actual['State']['FinishedAt'],
                exit_sha256=f.digest(before)))
        bound=e.Evidence();bound.snapshot(source)
        self.assertIn(str(source),bound.snapshots)
        with SyscallOrder() as calls:
            prepare.review_interruption(bound,self.out,'plan-sha',actual)
        removed=calls.events.index(('unlink',str(source)))
        self.assertIn(('fsync',str(target.parent)),calls.events[:removed])
        self.assertIn(('fsync',str(source.parent)),calls.events[removed+1:])
        self.assertNotIn(str(source),bound.snapshots)
        self.assertEqual(target.read_bytes(),before);self.assertFalse(source.exists())
        bound.verify()
        # The public wrapper also accepts an already-archived valid EXIT on
        # an idempotent follow-up without modifying its bytes.
        prepare.review_interruption(bound,self.out,'plan-sha',actual)
        self.assertEqual(target.read_bytes(),before);bound.verify()

    def test_directory_history_move_syncs_both_parent_directories(self):
        source=self.out/'partial';source.mkdir();(source/'evidence').write_text('retain')
        target=self.out/'history'/'generation-token'/'partial'
        with SyscallOrder() as calls:e.durable_move(source,target)
        moved=calls.events.index(('rename',str(source),str(target)))
        self.assert_chain_before(calls.events,target.parent,moved)
        self.assertIn(('fsync',str(target.parent)),calls.events[moved+1:])
        self.assertIn(('fsync',str(source.parent)),calls.events[moved+1:])
        self.assertEqual((target/'evidence').read_text(),'retain')


class ApprovalBindingRegressions(unittest.TestCase):
    def setUp(self):
        self.m = module('test_prepare_openjev_path_trace.py')
        self.case = self.m.CPUWorkflow('runTest')
        self.case.setUp(); self.addCleanup(self.case.doCleanups)
        self.request = self.case.request()
        self.approval = self.case.cpu / 'PARENT_REVIEW.json'
        self.parent_bytes = self.approval.read_bytes()

    def test_launch_records_exact_parent_bytes_and_launcher_clock_domain(self):
        # An ahead parent clock is descriptive provenance, never ordering proof.
        review = json.loads(self.parent_bytes)
        review.update(utc='2026-10-31T00:01:38Z', hostname='author-host')
        f.write(self.approval, review); parent_bytes=self.approval.read_bytes()
        with patch.object(self.m.q,'utc',return_value='2026-10-31T00:00:00Z'):
            result=self.case.real.cpu_launch(self.request)
        self.assertEqual(result['status'],'STARTED')
        receipt=json.loads((self.case.cpu/'LAUNCH_RECEIPT.json').read_text())
        self.assertEqual(receipt['parent_review_sha256'],f.digest(parent_bytes))
        self.assertEqual(receipt['launcher_utc'],'2026-10-31T00:00:00Z')
        self.assertEqual(receipt['launcher_hostname'],'k8s-node1')
        self.assertEqual(self.approval.read_bytes(),parent_bytes)

    def test_same_approval_json_changed_bytes_rejected_after_launch(self):
        self.case.real.cpu_launch(self.request)
        self.approval.write_bytes(self.parent_bytes+b' ')
        with self.assertRaisesRegex(ValueError,'approval|receipt'):
            self.case.real.cpu_launch(self.request)
        starts=[x for x in self.case.calls if x[1].endswith('/start')]
        self.assertEqual(len(starts),1)

    def test_parent_byte_change_before_create_prevents_docker_mutation(self):
        original=self.m.q.atomic
        def intent_then_mutate(path,value):
            result=original(path,value)
            if Path(path).name=='LAUNCH_INTENT.json':
                self.approval.write_bytes(self.parent_bytes+b' ')
            return result
        with patch.object(self.m.q,'atomic',side_effect=intent_then_mutate):
            with self.assertRaisesRegex(ValueError,'Evidence object changed'):
                self.case.real.cpu_launch(self.request)
        self.assertFalse(any(x[0]=='POST' for x in self.case.calls))

    def test_completion_rejects_changed_parent_snapshot_even_with_same_approval(self):
        case=f.CompletionReadRaceRegressions('runTest')
        case.setUp();self.addCleanup(case.doCleanups)
        # This validates completion binding, not predictions (already covered
        # without stubs by FullReceiptConfidenceRegressions).
        result=f.v.verify_complete(case.plan_path,case.helper)
        self.assertEqual(result['report_sha256'],f.digest(case.good_bytes))
        approval=case.out/'PARENT_REVIEW.json'
        approval.write_bytes(approval.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'approval snapshot'):
            f.v.verify_complete(case.plan_path,case.helper)


class AcceptedExecutionBindingRegressions(unittest.TestCase):
    def setUp(self):
        self.case=f.CompletionReadRaceRegressions('runTest')
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.docker=dict(Id='fixture-id',State=dict(Status='exited',ExitCode=0,
            StartedAt='2026-10-31T00:00:00Z',FinishedAt='2026-10-31T00:01:00Z'))
        self.case.helper.inspect=lambda name:copy.deepcopy(self.docker)

    def test_verified_report_binds_execution_times_exit_and_launch_bytes(self):
        result=f.v.verify_complete(self.case.plan_path,self.case.helper)
        self.assertEqual(result['npu_started_at'],self.docker['State']['StartedAt'])
        self.assertEqual(result['npu_finished_at'],self.docker['State']['FinishedAt'])
        self.assertEqual(result['npu_exit_sha256'],f.digest((self.case.out/'EXIT').read_bytes()))
        self.assertEqual(result['npu_launch_receipt_sha256'],
                         f.digest((self.case.out/'LAUNCH_RECEIPT.json').read_bytes()))

    def test_same_container_id_restart_during_verification_is_rejected(self):
        original=f.v.reconstruct;injected=[]
        def reconstruct_then_restart(items):
            result=original(items)
            self.docker['State'].update(StartedAt='2026-10-31T00:02:00Z',
                                        FinishedAt='2026-10-31T00:03:00Z')
            injected.append(True);return result
        with patch.object(f.v,'reconstruct',side_effect=reconstruct_then_restart):
            with self.assertRaises(ValueError):
                f.v.verify_complete(self.case.plan_path,self.case.helper)
        self.assertEqual(injected,[True])

    def test_valid_rc_zero_exit_replacement_during_verification_is_rejected(self):
        original=f.v.reconstruct;injected=[]
        def reconstruct_then_replace(items):
            result=original(items)
            replacement=self.case.out/'different-exit'
            replacement.write_text('rc=0 utc=2026-10-31T00:03:00Z\n')
            replacement.replace(self.case.out/'EXIT');injected.append(True);return result
        with patch.object(f.v,'reconstruct',side_effect=reconstruct_then_replace):
            with self.assertRaises(ValueError):
                f.v.verify_complete(self.case.plan_path,self.case.helper)
        self.assertEqual(injected,[True])


if __name__ == '__main__':
    unittest.main()
