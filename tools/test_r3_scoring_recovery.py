"""Process-death checks of the real frozen scoring store, synthetic scores.

The producer/storage code is unmodified. No model or test dataset is opened.
Committed items must not be rescored; an uncommitted tail may be recomputed.
"""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code')
DESC={'record_grade':True,'mode':'rightpad','dtype':'float32','token_budget':16384,'hf32':{'hf32':False}}
MODEL='a'*64


def modules():
    result={}
    for name in ('core_r3','provenance_r3','admissible_store_r3'):
        spec=importlib.util.spec_from_file_location(name,SOURCE/(name+'.py'))
        m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);result[name]=m
    return result['core_r3'],result['provenance_r3'],result['admissible_store_r3']


def score(root,kill=None):
    C,PV,AS=modules();root=Path(root);path=str(root/'readouts.jsonl')
    rows=[{'key':str(i)} for i in range(70)]
    def scorer(batch,mode):
        with (root/'calls.jsonl').open('a') as f:
            f.write(json.dumps([r['key'] for r in batch])+'\n');f.flush();os.fsync(f.fileno())
        return [[float(int(r['key'])%2),-.5] for r in batch]
    store=AS.VerifiedStore(str(root),path,MODEL,DESC)
    def progress(done,total):
        if kill=='uncommitted':os.kill(os.getpid(),signal.SIGKILL)
        store.commit()
        if kill=='committed':os.kill(os.getpid(),signal.SIGKILL)
    try:
        C.score_resumable(scorer,rows,lambda r:r['key'],lambda r,s:PV.stamp({'k':r['key'],'s':s},MODEL),
                          store,chunk=32,progress=progress)
    finally:store.close()
    return AS.read_verified(str(root),path,MODEL,DESC)


class ScoringRecovery(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen scoring closure absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        context=patch.dict(sys.modules);context.start();self.addCleanup(context.stop)
        paths=list(sys.path);self.addCleanup(lambda:sys.path.__setitem__(slice(None),paths))

    def killed(self,mode):
        p=multiprocessing.get_context('fork').Process(target=score,args=(self.root,mode))
        p.start();p.join(10)
        if p.is_alive():p.kill();p.join();self.fail('child failed to reach crash boundary')
        self.assertEqual(p.exitcode,-signal.SIGKILL)

    def test_committed_items_never_rescored_after_sigkill(self):
        self.killed('committed')
        prefix=(self.root/'readouts.jsonl').read_bytes()
        rows=score(self.root)
        calls=[json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual([len(x) for x in calls],[32,32,6])
        self.assertEqual(len({x for batch in calls for x in batch}),70)
        self.assertTrue((self.root/'readouts.jsonl').read_bytes().startswith(prefix))
        self.assertEqual(len(rows),70)
        before=(self.root/'calls.jsonl').read_bytes();self.assertEqual(score(self.root),rows)
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)

    def test_uncommitted_tail_recomputed_and_matches_uninterrupted(self):
        self.killed('uncommitted');rows=score(self.root)
        reference=self.root/'reference';reference.mkdir()
        self.assertEqual(rows,score(reference))
        calls=[json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual([len(x) for x in calls],[32,32,32,6])
        self.assertEqual(calls[0],calls[1])

    def test_corrupted_committed_prefix_refused_before_new_scoring(self):
        self.killed('committed');path=self.root/'readouts.jsonl'
        raw=path.read_bytes();path.write_bytes(raw.replace(b'0.0',b'9.0',1))
        calls=(self.root/'calls.jsonl').read_bytes()
        with self.assertRaisesRegex(RuntimeError,'committed readout bytes'):score(self.root)
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),calls)

    def test_partial_tail_truncation_keeps_committed_prefix(self):
        self.killed('committed');path=self.root/'readouts.jsonl';prefix=path.read_bytes()
        with path.open('ab') as f:f.write(b'{"k":"truncated');f.flush();os.fsync(f.fileno())
        rows=score(self.root)
        self.assertEqual(len(rows),70);self.assertTrue(path.read_bytes().startswith(prefix))


if __name__=='__main__':unittest.main()
