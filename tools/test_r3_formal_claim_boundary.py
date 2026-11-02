"""Actual main-tree claim/launcher integration; no Docker or production writes."""
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import test_r3_formal_train_successor as fixture
R, L, S, pin, write = fixture.R, fixture.L, fixture.S, fixture.pin, fixture.write


class ClaimBoundary(unittest.TestCase):
    def setUp(self):
        self.f = fixture.SuccessorTests('test_wait_then_real_lineage')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.finish_parent(); self.intent = self.f.precondition()

    def test_launcher_requires_pin_for_guarded_start_but_verify_can_precede_ready(self):
        f=self.f
        L.successor_binding(f.p,f.job['plan_sha256'],None,required=False)
        with self.assertRaisesRegex(RuntimeError,'precondition required'):
            L.successor_binding(f.p,f.job['plan_sha256'],None)
        with self.assertRaisesRegex(RuntimeError,'precondition changed'):
            L.successor_binding(f.p,f.job['plan_sha256'],'0'*64)
        L.successor_binding(f.p,f.job['plan_sha256'],self.intent['precondition_sha256'])

    def test_actual_adapter_command_carries_exact_bindings(self):
        f=self.f
        with patch.object(L.subprocess,'run') as run:
            L.adapter(f.p,'claim',f.out/'attempts/1','formal-a1',f.job['plan'],f.job['plan_sha256'],self.intent['precondition_sha256'])
        command=run.call_args.args[0]
        for flag,value in (('--plan',f.job['plan']),('--plan-sha256',f.job['plan_sha256']),('--precondition-sha256',self.intent['precondition_sha256'])):
            self.assertEqual(command[command.index(flag)+1],value)
        self.assertEqual(run.call_args.kwargs['timeout'],300)

    def test_real_start_cli_propagates_guard_to_detached_supervisor(self):
        f=self.f
        argv=['launcher','start','--plan',f.job['plan'],'--sha256',f.job['plan_sha256'],'--attempt','1','--precondition-sha256',self.intent['precondition_sha256']]
        with patch.object(sys,'argv',argv), patch.object(L,'verify',return_value=f.p), patch.object(L.socket,'gethostname',return_value='k8s-node1'), patch.object(L.subprocess,'Popen',return_value=types.SimpleNamespace(pid=123)) as spawn:
            L.main()
        command=spawn.call_args.args[0]
        self.assertEqual(command[-2:],['--precondition-sha256',self.intent['precondition_sha256']])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        with patch.object(sys,'argv',argv), patch.object(L,'verify',return_value=f.p), patch.object(L.socket,'gethostname',return_value='k8s-node1'), patch.object(L.subprocess,'Popen',side_effect=AssertionError('duplicate spawn')):
            with self.assertRaises(FileExistsError): L.main()

    def test_controller_hash_cannot_be_replaced_by_self_assertion(self):
        f=self.f; f.p['files'][S.__file__]='0'*64; f.seal_plan()
        with self.assertRaisesRegex(RuntimeError,'controller pin'):
            f.claim(self.intent)
        self.assertFalse((f.out/'attempts/1/CLAIM.json').exists())

    def test_guarded_claim_replay_and_release_generation_are_bound(self):
        f=self.f; claim=f.claim(self.intent)
        self.assertEqual(claim['successor_precondition']['precondition_sha256'],self.intent['precondition_sha256'])
        self.assertEqual(claim['successor_precondition']['controller_sha256'],pin(S.__file__))
        with self.assertRaisesRegex(RuntimeError,'already attempted'): f.claim(self.intent)

    def test_release_rejects_claim_replacement_after_initial_snapshot(self):
        f = self.f
        original = f.claim(self.intent)
        f.formal_actual = fixture.observed(
            L.docker_command(f.p, f.job['plan'], 1), 'formal-id')
        args = f.release_args()
        before = f.alloc.read_bytes()
        read = R.read_bytes
        claim_reads = 0

        def replace_before_revalidation(path):
            nonlocal claim_reads
            if str(path) == args.claim:
                claim_reads += 1
                if claim_reads == 2:
                    replacement = json.loads(Path(path).read_bytes())
                    replacement['entry']['claimed_utc'] = 'REPLACEMENT_GENERATION'
                    write(path, replacement)
            return read(path)

        with patch.object(R, 'read_bytes', side_effect=replace_before_revalidation):
            with self.assertRaisesRegex(RuntimeError, 'release claim changed'):
                R.release(args)
        self.assertEqual(claim_reads, 2)
        self.assertEqual(f.alloc.read_bytes(), before)
        self.assertEqual(json.loads(before)['allocation'], [original['entry']])
        self.assertFalse(Path(args.proof).exists())
        self.assertFalse(Path(args.proof + '.intent').exists())

    def test_preparer_freezes_controller_and_guard_configuration(self):
        import importlib.util
        path=Path(__file__).with_name('r3_formal_prepare.py')
        spec=importlib.util.spec_from_file_location('prepare_guard',path)
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        f=self.f; config=f.root/'guard.json';write(config,dict(previous_execution=str(f.execution),previous_execution_sha256=pin(f.execution),competitors=[],controller=S.__file__,controller_sha256=pin(S.__file__)))
        tools=f.root/'guard-tools';tools.mkdir();plan={'files':{}}
        prepare.bind_successor_guard(plan,tools,config,pin(config))
        controller=plan['successor_guard']['controller']
        self.assertEqual(plan['files'][controller],pin(S.__file__))
        self.assertEqual(Path(controller).read_bytes(),Path(S.__file__).read_bytes())
        self.assertEqual(plan['files'][str(config)],pin(config))
        with self.assertRaisesRegex(ValueError,'exact successor'):
            prepare.bind_successor_guard(plan,tools,config,'0'*64)


if __name__=='__main__': unittest.main()
