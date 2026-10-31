"""Transaction integration using synthetic scorer/log adapters, no test datasets."""
import importlib.util
import json
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('transaction',Path(__file__).with_name('r3_test_transaction.py'))
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)


def durable_case(root,connection=None):
    root=Path(root)
    results={s:{'n':n,'correct':n//2} for s,n in zip(T.SUITES,(1200,656))}
    def score(suites):
        with (root/'score-invocations').open('a') as f:f.write('score\n')
        return results
    def verify(s,r):
        if r!=results[s]:raise ValueError('wrong result')
    def read(s):
        p=root/(s+'.completion.json')
        return json.loads(p.read_text()) if p.exists() else None
    def append(s,r):
        T.G.atomic(root/(s+'.completion.json'),r)
        if connection is not None and s==T.SUITES[0]:
            connection.send('first-log-durable');connection.close()
            while True:time.sleep(1)
    return T.run(str(root/'round'),model_sha256='a'*64,run_dir=str(root/'run'),
                 execution_sha256='b'*64,final_sha256='c'*64,validate_admission=lambda:None,
                 score=score,verify_result=verify,read_completion=read,append_completion=append)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.log={}
        self.results={s:{'n':n,'correct':n//2,'source_sha256':'d'*64} for s,n in zip(T.SUITES,(1200,656))}
        self.score=Mock(return_value=self.results)
        self.admission=Mock()
        def verify(s,r):
            if r!=self.results[s]:raise ValueError('changed population or scores')
        self.kw=dict(model_sha256='a'*64,run_dir=str(self.root/'run'),execution_sha256='b'*64,
                     final_sha256='c'*64,validate_admission=self.admission,score=self.score,
                     verify_result=verify,read_completion=lambda s:self.log.get(s),
                     append_completion=lambda s,r:self.log.__setitem__(s,r))

    def run_case(self,**changes):return T.run(str(self.root/'round'),**dict(self.kw,**changes))

    def test_second_suite_interrupted_never_rescores_completed_first(self):
        def append(s,r):
            if s==T.SUITES[1]:raise RuntimeError('second suite commit interrupted')
            self.log[s]=r
        with self.assertRaises(RuntimeError):self.run_case(append_completion=append)
        self.assertEqual(set(self.log),{T.SUITES[0]})
        result=self.run_case();self.assertEqual(result['state'],'completed')
        self.score.assert_called_once();self.assertEqual(len(self.log),2)
        self.run_case();self.score.assert_called_once()

    def test_killed_process_after_first_durable_log_recovers_without_rescoring(self):
        ctx=multiprocessing.get_context('fork');receiver,sender=ctx.Pipe(duplex=False)
        p=ctx.Process(target=durable_case,args=(str(self.root),sender));p.start();sender.close()
        try:
            self.assertTrue(receiver.poll(5));self.assertEqual(receiver.recv(),'first-log-durable')
        finally:
            p.kill();p.join(5);receiver.close()
        self.assertEqual(durable_case(self.root)['state'],'completed')
        self.assertEqual((self.root/'score-invocations').read_text(),'score\n')
        self.assertTrue((self.root/(T.SUITES[1]+'.completion.json')).exists())

    def test_crash_after_log_commit_before_reservation_completion_reconciles(self):
        def append(s,r):
            self.log[s]=r;raise RuntimeError('after durable append')
        with self.assertRaises(RuntimeError):self.run_case(append_completion=append)
        self.run_case();self.score.assert_called_once()

    def test_missing_or_changed_staged_result_refused_without_scoring(self):
        self.run_case();p=self.root/'run/TEST-STAGED-RESULTS.json';original=p.read_text()
        d=json.loads(original);d['results'][T.SUITES[0]]['n']=1;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'population'):self.run_case()
        p.unlink()
        with self.assertRaisesRegex(ValueError,'lacks staged'):self.run_case()
        self.score.assert_called_once()

    def test_forged_log_without_staged_evidence_never_scores(self):
        self.log[T.SUITES[0]]={'forged':True}
        with self.assertRaisesRegex(ValueError,'without staged'):self.run_case()
        self.score.assert_not_called()

    def test_admission_failure_never_scores(self):
        with self.assertRaisesRegex(ValueError,'not approved'):
            self.run_case(validate_admission=Mock(side_effect=ValueError('not approved')))
        self.score.assert_not_called()

    def test_conflicting_completed_log_refused(self):
        self.run_case();self.log[T.SUITES[0]]['result_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'log differs'):self.run_case()
        self.score.assert_called_once()

    def test_failed_verification_does_not_publish(self):
        with self.assertRaisesRegex(ValueError,'bad readout'):
            self.run_case(verify_result=Mock(side_effect=ValueError('bad readout')))
        self.assertFalse(self.log)
        self.assertFalse((self.root/'run/TEST-STAGED-RESULTS.json').exists())


if __name__=='__main__':unittest.main()
