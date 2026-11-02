import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import types
import multiprocessing
import os
import time
from tools import r3_formal_dev_successor as G
from tools import r3_posttrain_eval_launcher as L


def start_worker(state, barrier, outcomes):
    """Actual entry point in independent OS processes; no real watcher/NPU."""
    argv=['guard','start','--config','/config','--sha256','a'*64,
          '--activation','/activation','--activation-sha256','b'*64]
    def spawn(*args,**kwargs):
        with (Path(state)/'spawns').open('a') as f:
            f.write(str(os.getpid())+'\n');f.flush();os.fsync(f.fileno())
        time.sleep(.15)
        return types.SimpleNamespace(pid=os.getpid()+100000)
    try:
        with patch.object(G,'verify',return_value=({'state_root':state},{},None)),patch.object(G,'authorize'),patch.object(G.subprocess,'Popen',side_effect=spawn),patch.object(G.sys,'argv',argv):
            barrier.wait(timeout=5);G.main()
        outcomes.put('started')
    except Exception as e: outcomes.put(type(e).__name__)


class GuardContractTests(unittest.TestCase):
    def test_two_process_start_spawns_once(self):
        ctx=multiprocessing.get_context('fork')
        with tempfile.TemporaryDirectory() as d:
            barrier=ctx.Barrier(2);outcomes=ctx.Queue()
            children=[ctx.Process(target=start_worker,args=(d,barrier,outcomes)) for _ in range(2)]
            for p in children:p.start()
            for p in children:p.join(10);self.assertFalse(p.is_alive());self.assertEqual(p.exitcode,0)
            results=[outcomes.get(timeout=2) for _ in children]
            self.assertEqual(results.count('started'),1)
            self.assertEqual(len((Path(d)/'spawns').read_text().splitlines()),1)
            receipt=json.loads((Path(d)/'SERVICE.json').read_text())
            intent=Path(d)/'SERVICE_START_INTENT.json'
            self.assertEqual(receipt['start_intent_sha256'],G.sha(intent))

    def test_crash_after_spawn_keeps_intent_and_reentry_never_spawns(self):
        with tempfile.TemporaryDirectory() as d:
            argv=['guard','start','--config','/config','--sha256','a'*64,
                  '--activation','/activation','--activation-sha256','b'*64]
            original=G.put
            def crash(path,value,exclusive=False):
                if Path(path).name=='SERVICE.json':raise OSError('injected receipt failure')
                return original(path,value,exclusive)
            with patch.object(G,'verify',return_value=({'state_root':d},{},None)),patch.object(G,'authorize'),patch.object(G.sys,'argv',argv),patch.object(G.subprocess,'Popen',return_value=types.SimpleNamespace(pid=123)) as spawn:
                with patch.object(G,'put',side_effect=crash),self.assertRaises(OSError):G.main()
                self.assertTrue((Path(d)/'SERVICE_START_INTENT.json').exists())
                self.assertFalse((Path(d)/'SERVICE.json').exists())
                with self.assertRaisesRegex(RuntimeError,'intent requires reconciliation'):G.main()
                self.assertEqual(spawn.call_count,1)

    def test_launcher_claim_reads_execution_root_precondition(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);attempt=out/'attempts/1';attempt.mkdir(parents=True)
            p={'out':d,'allocation':'/alloc','run':'r3_runs/x','chip':1,
               'resource_adapter':'/adapter.py','successor_guard':{'enabled':True}}
            exe=out/'execution.json';exe.write_text(json.dumps(p));pre=out/'SUCCESSOR_PRECONDITION.json';pre.write_text('{}')
            with patch.object(L.subprocess,'run') as run:
                L.resource_op(p,'claim',attempt,'target-a1')
                argv=run.call_args.args[0]
                self.assertEqual(argv[argv.index('--precondition-sha256')+1],G.sha(pre))
                self.assertEqual(argv[argv.index('--plan')+1],str(exe))

    def test_hash_pin_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'value.json';p.write_bytes(b'{}\n')
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(G.sha(str(p)),h)
            with self.assertRaises(RuntimeError):G.pinned({'path':str(p),'sha256':'0'*64})

    def test_unsafe_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'real';p.write_bytes(b'x');q=Path(d)/'link';q.symlink_to(p)
            with self.assertRaises(RuntimeError):G.raw(str(q))

    def test_activation_scope_rejects_test(self):
        with self.assertRaises(FileNotFoundError):
            G.authorize({'execution':{'path':'/e','sha256':'a'*64},'config_identity':'b'*64},
                        {'path':'/missing','sha256':'c'*64})

    def test_write_exclusive_cannot_replace(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json';G.put(p,{'a':1},True)
            with self.assertRaises(FileExistsError):G.put(p,{'a':2},True)

    def test_config_without_guard_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'execution.json';p.write_text(json.dumps({'schema':'r3-engineering-posttrain-execution-v1'}))
            c={'schema':'r3-formal-dev-successor-v1','config_identity':'0'*64,
               'execution':{'path':str(p),'sha256':G.sha(p)},'poll_interval_seconds':600,
               'test_read':False,'scientific_acceptance':False}
            cp=Path(d)/'config.json';cp.write_text(json.dumps(c))
            with self.assertRaises(Exception):G.verify(str(cp),G.sha(cp))

    def test_claim_checks_snapshot_free_generation_and_no_competitor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p={'out':d,'chip':1,'container':'target'}
            exe=root/'execution.json';exe.write_text(json.dumps(p));pin=G.sha(exe)
            prior={'free_entry':{'chip':1,'release_evidence':'samechip'},'hashes':{'a':'b'},'attempt':1}
            pre=root/'SUCCESSOR_PRECONDITION.json';pre.write_text(json.dumps({'execution_sha256':pin,'previous':prior,'free_entry':prior['free_entry']}));pp=G.sha(pre)
            resource=types.SimpleNamespace(docker_inspect=lambda x:None,live_chip_conflict=lambda *a:False)
            allocation={'free':[prior['free_entry']],'allocation':[]}
            with patch.object(G,'predecessor',return_value=prior):
                self.assertEqual(G.claim_precondition(p,pin,pp,allocation,resource)['previous'],prior)
                for mutation in [{'free':[{'chip':1,'release_evidence':'newer'}],'allocation':[]},
                                 {'free':[prior['free_entry']],'allocation':[{'chip':1,'run':'other'}]}]:
                    with self.assertRaises(RuntimeError):G.claim_precondition(p,pin,pp,mutation,resource)
                resource.live_chip_conflict=lambda *a:True
                with self.assertRaises(RuntimeError):G.claim_precondition(p,pin,pp,allocation,resource)
            with patch.object(G,'predecessor',return_value=None):
                with self.assertRaises(RuntimeError):G.claim_precondition(p,pin,pp,allocation,resource)
            with patch.object(G,'predecessor',return_value=dict(prior,attempt=2)):
                with self.assertRaises(RuntimeError):G.claim_precondition(p,pin,pp,allocation,resource)
            pre.write_text('{}')
            with self.assertRaises(RuntimeError):G.claim_precondition(p,pin,pp,allocation,resource)

    def test_missing_terminal_never_launches_despite_free_resource(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'out';out.mkdir();state=root/'state';state.mkdir()
            p={'out':str(out)};c={'state_root':str(state)}
            launcher=types.SimpleNamespace(resource_module=lambda p:object())
            with patch.object(G,'predecessor',return_value=None),patch.object(G.subprocess,'run') as run:
                self.assertEqual(G.tick(c,p,launcher)['status'],'waiting_successful_training');run.assert_not_called()

    def test_uncertain_start_never_relaunches(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'out';out.mkdir();state=root/'state';state.mkdir()
            execution={'path':'/x','sha256':'a'*64};(state/'START_INTENT.json').write_text(json.dumps({'execution':execution}))
            with patch.object(G.subprocess,'run') as run:
                self.assertEqual(G.tick({'state_root':str(state),'execution':execution},{'out':str(out)},None)['status'],'needs_repair');run.assert_not_called()


if __name__=='__main__':unittest.main()
