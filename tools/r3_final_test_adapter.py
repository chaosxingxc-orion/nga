"""Wire the deferred evaluator to the durable test publication transaction.

Not a CLI/launcher. Exact-plan admission is supplied by the final launcher.
Only generated evaluator/testlock modules from a pinned closure may be used.
Recovery verifies retained evidence and cannot call the scorer or issue tickets
to this adapter. Both paths require full numerical reconstruction before logging.
"""
import importlib.util
import json
from pathlib import Path
import sys


def sibling(name):
    loader = globals().get('__loader__')
    if hasattr(loader, 'sources') and hasattr(loader, 'load'):
        return loader.load(name)
    path = Path(__file__).with_name(name + '.py')
    existing = sys.modules.get(name)
    if existing is not None:
        if Path(existing.__file__).resolve() != path.resolve():
            raise ValueError('different imported component: ' + name)
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


T = sibling('r3_test_transaction')
L = sibling('r3_test_log_adapter')
M = sibling('r3_final_metrics')
G = T.G


def run(args, scorer, evaluator, *, owner, validate_admission, validate_publication=None):
    """Execute under both suite locks; never creates FINAL or review approval."""
    G.require(set(owner) == {'model_sha256', 'execution_sha256', 'final_sha256', 'run_dir'},
              'unexpected owner fields')
    G.require(str(G.safe_path(args.out)) == owner['run_dir'], 'output differs')
    model_path = args.adapter or args.model_path
    log = L.CompletionLog(args.round_dir, model_path=model_path, **owner)
    state = {'verified_suites':{}, 'reference_metrics':{}}
    report_path = G.safe_path(args.out) / 'TEST-PRODUCER-REPORT.json'
    G.safe_path(report_path)

    def bind(leases, actual_owner):
        G.require(actual_owner == owner, 'transaction owner differs')
        state['leases'] = leases

    def check_header(report):
        return M.validate_header(report.get('header', {}), prompt=evaluator.P,
            expected_arm=args.arm, expected_model=args.model_path,
            expected_adapter=args.adapter, expected_sha256=owner['model_sha256'])

    def score(suites):
        G.require(tuple(suites) == T.SUITES, 'suite order differs')
        report, tickets = evaluator.run_guarded_test(args, scorer, leases=state['leases'], owner=owner)
        check_header(report)
        state['tickets'] = tickets
        G.require(report.get('test_publication', {}).get('state') == 'unpublished', 'report not deferred')
        G.require(set(report['track_k']['partitions']) == {
            'decision-v7/calibration', 'decision-v7/test', 'transfer-v4/test'}, 'report partitions differ')
        G.require('operator_fit' in report['track_k'], 'calibration fit absent')
        G.atomic(report_path, report)
        return {suite: dict(n=report['track_k']['partitions'][suite+'/test']['headline']['n'],
                            headline_accuracy=report['track_k']['partitions'][suite+'/test']['headline']['kev_rule_accuracy'],
                            producer_report_sha256=G.digest(report)) for suite in suites}

    def verify(suite, result):
        G.safe_path(report_path)
        report = json.loads(report_path.read_text())
        G.require(G.digest(report) == result['producer_report_sha256'], 'producer report changed')
        check_header(report)
        headline = report['track_k']['partitions'][suite+'/test']['headline']
        G.require(result == dict(n=headline['n'], headline_accuracy=headline['kev_rule_accuracy'],
                                producer_report_sha256=G.digest(report)), 'suite summary differs')
        if 'tickets' in state:
            metrics = M.verify(state['tickets'][(suite, 'test')], args.out,
                     kev_dir=evaluator.TL.C.KEV_DIR, report=report,
                     provenance_verifier=evaluator.TL.verify_test_result)
        else:
            # A public verification-only entry in the NEW testlock source. It
            # validates durable staged/owner/log identity before opening data,
            # returns only verified scalars and never exposes a scoring ticket.
            recovered = evaluator.TL.verify_reserved_test_result(args, suite=suite, result=result,
                leases=state['leases'], owner=owner, completion_log=log)
            metrics = recovered.get('metrics',{})
        if 'paired_vector' in metrics:
            state['verified_suites'][suite]=metrics['paired_vector']
        if 'reference_metrics' in metrics:
            state['reference_metrics'][suite]=metrics['reference_metrics']

    outcome = T.run(args.round_dir, **owner, validate_admission=validate_admission,
                 validate_publication=validate_publication,
                 bind_execution=bind, score=score, verify_result=verify,
                 read_completion=log.read, append_completion=log.append)

    return {**outcome,'verified_suites':state['verified_suites'],
            'reference_metrics':state['reference_metrics']}
