"""Two-phase final TEST transaction. No data/scorer is reachable from consume().

The mandatory release validator must authenticate actual retained-container exit,
resource release and exact score-manifest binding; marker presence is insufficient.
Old TEST-STAGED-RESULTS retains its verified-results-only semantics.
"""
from contextlib import ExitStack
import importlib.util
import json
import sys
from pathlib import Path


def sibling(name):
    loader=globals().get('__loader__')
    if hasattr(loader,'sources') and hasattr(loader,'load'):return loader.load(name)
    path=Path(__file__).with_name(name+'.py')
    if name in sys.modules:
        m=sys.modules[name];G_path=Path(m.__file__).resolve()
        if G_path!=path.resolve():raise ValueError('foreign sibling '+name)
        return m
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    try:spec.loader.exec_module(m)
    except BaseException:sys.modules.pop(name,None);raise
    return m
T=sibling('r3_test_transaction');G=T.G;SUITES=T.SUITES
SCORED='TEST-SCORED-UNVERIFIED.json'
INTENT='TEST-SCORE-INTENT.json'


def binding(owner):
    G.require(set(owner)=={'model_sha256','execution_sha256','final_sha256','run_dir'},'owner fields differ')
    G.safe_path(owner['run_dir'])
    for k in ('model_sha256','execution_sha256','final_sha256'):G.pin(owner[k])
    return {'schema':'r3-test-scored-unverified-v1','owner':owner,'suites':list(SUITES)}


def load_scored(root,owner):
    p=G.safe_path(root/SCORED);doc=json.loads(p.read_text())
    expected=binding(owner)
    G.require(set(doc)==set(expected)|{'results','producer_report_sha256','scientific_acceptance'},'scored fields differ')
    G.require(all(doc[k]==v for k,v in expected.items()) and doc['scientific_acceptance'] is False,'scored identity differs')
    G.require(isinstance(doc['results'],dict) and set(doc['results'])==set(SUITES),'incomplete scored suites')
    report=json.loads(G.safe_path(root/'TEST-PRODUCER-REPORT.json').read_text())
    G.require(G.digest(report)==doc['producer_report_sha256'],'producer report changed')
    for result in doc['results'].values():
        G.require(result.get('producer_report_sha256')==doc['producer_report_sha256'],'suite producer differs')
    return doc


def score_phase(round_dir,*,owner,validate_admission,score,read_completion,bind_execution):
    root=G.safe_path(owner['run_dir']);expected=binding(owner)
    with ExitStack() as stack:
        leases={s:stack.enter_context(G.execution(round_dir,suite=s,recover_completed=True,**owner)) for s in SUITES}
        validate_admission();bind_execution(leases,dict(owner));root.mkdir(parents=True,exist_ok=True)
        if (root/SCORED).exists():
            doc=load_scored(root,owner)
            return {'state':'scored_unverified','manifest_sha256':G.digest(doc),'scientific_acceptance':False}
        G.require(not (root/INTENT).exists(),'score was attempted without durable result; no blind rescore')
        G.require(not (root/'TEST-STAGED-RESULTS.json').exists(),'verified stage exists without scored manifest')
        G.require(all(x.value['state']=='reserved' for x in leases.values()),'completed reservation without scored manifest')
        G.require(all(read_completion(s) is None for s in SUITES),'completion without scored manifest')
        G.atomic(root/INTENT,{'schema':'r3-test-score-intent-v1','owner':owner,'suites':list(SUITES)})
        results=score(SUITES)
        G.require(isinstance(results,dict) and set(results)==set(SUITES),'incomplete scored suites')
        report=json.loads(G.safe_path(root/'TEST-PRODUCER-REPORT.json').read_text());pin=G.digest(report)
        G.require(all(x.get('producer_report_sha256')==pin for x in results.values()),'scored producer mismatch')
        G.atomic(root/SCORED,{**expected,'results':results,'producer_report_sha256':pin,'scientific_acceptance':False})
        doc=load_scored(root,owner)
        return {'state':'scored_unverified','manifest_sha256':G.digest(doc),'scientific_acceptance':False}


def consume(round_dir,*,owner,validate_admission,validate_release,verify_result,
            read_completion,append_completion,bind_execution,validate_publication):
    """No scorer/ticket factory argument. Release check precedes source verification."""
    root=G.safe_path(owner['run_dir']);binding(owner)
    with ExitStack() as stack:
        leases={s:stack.enter_context(G.execution(round_dir,suite=s,recover_completed=True,**owner)) for s in SUITES}
        validate_admission();doc=load_scored(root,owner);pin=G.digest(doc)
        validate_release(dict(owner),pin)
        bind_execution(leases,dict(owner));results=doc['results']
        staged=G.safe_path(root/'TEST-STAGED-RESULTS.json')
        expected={'schema':'r3-test-staged-results-v1','owner':owner,'suites':list(SUITES),'results':results}
        if staged.exists():G.require(json.loads(staged.read_text())==expected,'verified stage differs')
        else:
            G.require(all(x.value['state']=='reserved' for x in leases.values()),'completed reservation lacks verified stage')
            G.require(all(read_completion(s) is None for s in SUITES),'completion lacks verified stage')
            for s in SUITES:verify_result(s,results[s])
            G.atomic(staged,expected)
        # Same second verification and commit semantics as original transaction.
        for s in SUITES:verify_result(s,results[s])
        G.require(G.digest(load_scored(root,owner))==pin,'scored manifest changed during verification')
        validate_release(dict(owner),pin);validate_publication()
        for s in SUITES:
            result_pin=G.digest(results[s]);lease=leases[s]
            expected_log={'suite':s,'model_sha256':owner['model_sha256'],'execution_sha256':owner['execution_sha256'],'result_sha256':result_pin}
            prior=read_completion(s)
            if lease.value['state']=='completed':
                G.require(lease.value['verified_result_sha256']==result_pin and prior==expected_log,'completed evidence/log differs');continue
            if prior is None:
                append_completion(s,expected_log);G.require(read_completion(s)==expected_log,'completion not durable')
            else:G.require(prior==expected_log,'conflicting completion')
            lease.complete(result_pin)
        return {'state':'completed','results':results,'scientific_acceptance':False}
