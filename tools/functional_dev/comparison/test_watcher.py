#!/usr/bin/env python3
"""Bounded end-to-end watcher tests with a synthetic CLI, never actual data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent

class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runs = self.root / 'runs'
        self.runs.mkdir()
        self.output = self.root / 'out'
        self.consumer = self.root / 'fake_consumer.py'
        self.consumer.write_text('''import argparse,json,pathlib,sys\np=argparse.ArgumentParser()\nfor arg in ("--reference-catalog","--run-root","--receipt-layout","--output"): p.add_argument(arg)\na=p.parse_args()\nr=pathlib.Path(a.run_root)\no=pathlib.Path(a.output); o.mkdir(parents=True,exist_ok=True)\ncount=len(list(r.glob("full-*/score-EXIT.json")))\ncode=1 if (r/"contradiction").exists() else (0 if count==8 else 2)\nstatus={0:"VALIDATED_DEV_CONDITIONAL_RUNTIME",1:"REFUSED_CONTRADICTION",2:"INCOMPLETE_PENDING"}[code]\n(o/"comparison.json").write_text(json.dumps({"status":status,"count":count}))\nsys.exit(code)\n''')
        self.sha = hashlib.sha256(self.consumer.read_bytes()).hexdigest()
        self.verdict = self.root / 'VERDICT.json'
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'consumer':str(self.consumer),'consumer_sha256':self.sha,
            'verdict':str(self.verdict),'verdict_sha_field':'approved_consumer_sha256',
            'catalog':str(self.root/'BASE-REUSE.json'),'run_root':str(self.runs),
            'output':str(self.output),'fallback_seconds':0.15}))
        self.process = None

    def tearDown(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=3)
        self.temp.cleanup()

    def launch(self):
        self.log = open(self.root/'watch.log','w+')
        self.addCleanup(self.log.close)
        self.process = subprocess.Popen([sys.executable, '-B', str(HERE/'watcher.py'), str(self.config)], stdout=self.log, stderr=subprocess.STDOUT)

    def approve(self, digest=None):
        self.verdict.write_text(json.dumps({'verdict':'PASS_FOR_CONDITIONAL_DEV_CONSUMPTION','approved_consumer_sha256':digest or self.sha}))

    def receipt(self, lane, exit_code=0):
        d = self.runs / ('full-' + lane)
        d.mkdir(exist_ok=True)
        tmp = d/'score-EXIT.tmp'
        tmp.write_text(json.dumps({'exit_code':exit_code,'container_exit_code':exit_code}))
        os.replace(tmp, d/'score-EXIT.json')

    def wait_for(self, pred):
        end = time.monotonic()+6
        while time.monotonic()<end:
            if pred(): return
            if self.process and self.process.poll() is not None: break
            time.sleep(.05)
        self.log.flush()
        self.fail('timed out or stopped; log: '+(self.root/'watch.log').read_text())

    def latest(self):
        p = self.output/'latest.json'
        return json.loads(p.read_text()) if p.exists() else {}

    def test_pending_partial_unchanged_complete(self):
        self.launch()
        self.receipt('q0p8b-s2')
        time.sleep(.4)
        self.assertFalse((self.output/'latest.json').exists())
        self.approve()
        self.wait_for(lambda:self.latest().get('consumer_exit_code')==2)
        time.sleep(.5)
        self.assertEqual(len(list(self.output.glob('packet-*'))),1)
        for size in ('0p8b','2b','4b','9b'):
            for seed in (2,3): self.receipt(f'q{size}-s{seed}')
        self.assertEqual(self.process.wait(timeout=6),0)
        result=self.latest()
        self.assertEqual(result['status'],'VALIDATED_DEV_CONDITIONAL_RUNTIME')
        self.assertEqual(json.loads((Path(result['packet'])/'comparison.json').read_text())['count'],8)

    def test_consumer_contradiction_stops_even_if_other_lanes_missing(self):
        self.approve()
        (self.runs/'contradiction').write_text('x')
        self.receipt('q0p8b-s2')
        self.launch()
        self.assertEqual(self.process.wait(timeout=6),1)
        self.assertEqual(self.latest()['status'],'REFUSED_CONTRADICTION')
        self.assertEqual(len(list(self.output.glob('packet-*'))),1)

    def test_failed_exit_stops_without_baseline_consumer(self):
        self.approve()
        self.receipt('q0p8b-s2',17)
        self.launch()
        self.assertEqual(self.process.wait(timeout=6),1)
        self.assertFalse(list(self.output.glob('packet-*')))
        self.log.flush()
        self.assertIn('REFUSED_CONTRADICTION',(self.root/'watch.log').read_text())

    def test_wrong_review_sha_stops(self):
        self.approve('0'*64)
        self.launch()
        self.assertEqual(self.process.wait(timeout=6),1)
        self.assertFalse(list(self.output.glob('packet-*')))

if __name__ == '__main__': unittest.main(verbosity=2)
