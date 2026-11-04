"""Production adapter components for future asynchronous final closure.

Neither entry creates FINAL, approves a plan, allocates a device or launches a job.
CPU entry takes no scorer and requires authenticated release via its caller.
"""
import importlib.util
import json
from pathlib import Path

_spec=importlib.util.spec_from_file_location('async_transaction',Path(__file__).with_name('r3_final_async_transaction_v1.py'))
X=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(X)
G=X.G;L=X.sibling('r3_test_log_adapter');M=X.sibling('r3_final_metrics')


def common(args,evaluator,owner):
    G.require(str(G.safe_path(args.out))==owner['run_dir'],'output differs')
    log=L.CompletionLog(args.round_dir,model_path=args.adapter or args.model_path,**owner)
    state={'verified_suites':{},'reference_metrics':{}}
    def bind(leases,actual):
        G.require(actual==owner,'owner differs');state['leases']=leases
    def check(report):
        M.validate_header(report.get('header',{}),prompt=evaluator.P,expected_arm=args.arm,
            expected_model=args.model_path,expected_adapter=args.adapter,expected_sha256=owner['model_sha256'])
        G.require(report.get('test_publication',{}).get('state')=='unpublished','producer not deferred')
        G.require(set(report['track_k']['partitions'])=={'decision-v7/calibration','decision-v7/test','transfer-v4/test'} and 'operator_fit' in report['track_k'],'producer partitions differ')
    return log,state,bind,check


def score_phase(args,scorer,evaluator,*,owner,validate_admission):
    log,state,bind,check=common(args,evaluator,owner)
    def score(suites):
        report,_tickets=evaluator.run_guarded_test(args,scorer,leases=state['leases'],owner=owner)
        check(report);G.atomic(G.safe_path(args.out)/'TEST-PRODUCER-REPORT.json',report)
        return {s:dict(n=report['track_k']['partitions'][s+'/test']['headline']['n'],
            headline_accuracy=report['track_k']['partitions'][s+'/test']['headline']['kev_rule_accuracy'],
            producer_report_sha256=G.digest(report)) for s in suites}
    return X.score_phase(args.round_dir,owner=owner,validate_admission=validate_admission,
                         score=score,read_completion=log.read,bind_execution=bind)


def consume(args,evaluator,*,owner,validate_admission,validate_release,validate_publication):
    log,state,bind,check=common(args,evaluator,owner)
    def verify(suite,result):
        report=json.loads(G.safe_path(Path(args.out)/'TEST-PRODUCER-REPORT.json').read_text());check(report)
        headline=report['track_k']['partitions'][suite+'/test']['headline']
        G.require(result==dict(n=headline['n'],headline_accuracy=headline['kev_rule_accuracy'],producer_report_sha256=G.digest(report)),'suite summary differs')
        recovered=evaluator.TL.verify_scored_test_result(args,suite=suite,result=result,
            leases=state['leases'],owner=owner,completion_log=log)
        metrics=recovered.get('metrics',{})
        G.require('paired_vector' in metrics and 'reference_metrics' in metrics,'verified vectors/metrics missing')
        state['verified_suites'][suite]=metrics['paired_vector'];state['reference_metrics'][suite]=metrics['reference_metrics']
    result=X.consume(args.round_dir,owner=owner,validate_admission=validate_admission,
        validate_release=validate_release,verify_result=verify,read_completion=log.read,
        append_completion=log.append,bind_execution=bind,validate_publication=validate_publication)
    return {**result,'verified_suites':state['verified_suites'],'reference_metrics':state['reference_metrics']}
