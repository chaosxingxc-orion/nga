"""Real seven-column log format with synthetic scorer and result provenance."""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock,patch

def module(name):
    s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
L=module('r3_test_log_adapter');T=module('r3_test_transaction')


class LogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.round=self.root/'round';self.run=self.root/'run'
        self.owner=dict(model_sha256='a'*64,execution_sha256='b'*64,
                        final_sha256='c'*64,run_dir=str(self.run))
        self.log=L.CompletionLog(self.round,model_path=str(self.root/'model'),**self.owner)
        self.results={s:dict(n=n,headline_accuracy=.8123456789,source_sha256='d'*64)
                      for s,n in L.COUNTS.items()}
        self.score=Mock(return_value=self.results)
    def execute(self):
        def verify(s,r):
            if r!=self.results[s]:raise ValueError('source result differs')
        return T.run(self.round,**self.owner,validate_admission=lambda:None,score=self.score,
                     verify_result=verify,read_completion=self.log.read,append_completion=self.log.append)

    def test_real_format_and_exact_result_hash_survive_rounded_accuracy(self):
        self.execute();lines=self.log.path.read_text().splitlines()
        self.assertEqual(len(lines),2)
        self.assertEqual(lines[0].split('\t')[-2:],['1200','0.812346'])
        self.execute();self.score.assert_called_once()
        self.assertEqual(self.log.read('decision-v7')['result_sha256'],T.G.digest(self.results['decision-v7']))

    def test_crash_after_durable_intent_before_log_append(self):
        with patch.object(self.log,'append_line',side_effect=RuntimeError('before append')):
            with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(self.log.path.read_text(),'')
        self.execute();self.score.assert_called_once()

    def test_crash_after_log_append_before_reservation_completion(self):
        real=self.log.append_line
        def broken(f,line):real(f,line);raise RuntimeError('after append')
        with patch.object(self.log,'append_line',side_effect=broken):
            with self.assertRaises(RuntimeError):self.execute()
        self.execute();self.score.assert_called_once()
        self.assertEqual(len(self.log.path.read_text().splitlines()),2)

    def test_sigkill_after_first_real_log_append_recovers_without_scoring(self):
        count=self.root/'score-count'
        def score(suites):
            with count.open('a') as f:
                f.write('score\n');f.flush();os.fsync(f.fileno())
            return self.results
        self.score=score
        def child():
            original=self.log.append_line
            def kill_after_append(f,line):
                original(f,line)
                os.kill(os.getpid(),signal.SIGKILL)
            self.log.append_line=kill_after_append
            self.execute()
        process=multiprocessing.get_context('fork').Process(target=child)
        process.start();process.join(10)
        if process.is_alive():
            process.kill();process.join()
            self.fail('child did not reach the durable append boundary')
        self.assertEqual(process.exitcode,-signal.SIGKILL)
        self.assertEqual(len(self.log.path.read_text().splitlines()),1)
        self.execute()
        self.assertEqual(count.read_text(),'score\n')
        self.assertEqual(len(self.log.path.read_text().splitlines()),2)

    def test_foreign_log_cannot_acquire_new_intent(self):
        self.round.mkdir();line='\t'.join(['time',str(self.root/'model'),'a'*64,'decision-v7','test','1200','.5'])+'\n'
        self.log.path.write_text(line)
        with self.assertRaisesRegex(ValueError,'matching durable intent'):self.execute()
        self.score.assert_not_called()

    def test_duplicate_malformed_and_partial_log_refused(self):
        self.execute();raw=self.log.path.read_text()
        for value in (raw+raw.splitlines()[0]+'\n',raw+'partial',raw+'bad\n'):
            self.log.path.write_text(value)
            with self.assertRaises(ValueError):self.execute()
        self.score.assert_called_once()

    def test_changed_staged_source_or_intent_refused(self):
        self.execute();p=self.log.intent_path('decision-v7');d=json.loads(p.read_text())
        d['completion']['result_sha256']='e'*64;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'intent identity'):self.execute()
        self.score.assert_called_once()


if __name__=='__main__':unittest.main()
