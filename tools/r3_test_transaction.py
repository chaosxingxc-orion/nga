"""Recoverable test-result publication around an injected, verified scorer.

Not a standalone final launcher. Callbacks must enforce the real FINAL/ticket,
model/data provenance, frozen metric protocol and exact test-log validation.
This layer owns durable stage ordering; it cannot confer scientific approval.
"""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path

loader=globals().get('__loader__')
if hasattr(loader,'sources') and hasattr(loader,'load'):
    G=loader.load('r3_test_execution_guard')
else:
    spec=importlib.util.spec_from_file_location('test_execution_guard',Path(__file__).with_name('r3_test_execution_guard.py'))
    G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
SUITES=('decision-v7','transfer-v4')


def run(round_dir, *, model_sha256, run_dir, execution_sha256, final_sha256,
        validate_admission, score, verify_result, read_completion, append_completion,
        bind_execution=None, validate_publication=None):
    """Both suite locks precede admission or scoring; interrupted commits resume.

    score(suites) must return a JSON object for each suite, including provenance.
    verify_result(suite, result) revalidates persisted readouts, fixed population
    and metrics without model scoring. read_completion(suite) returns None or
    the normalized completion object. append_completion(suite, object) must
    perform durable, locked insertion; its reconciliation key is the result SHA.
    A real adapter for legacy TEST-READS.log must supply the exact mapping.
    bind_execution(leases, owner), when provided, receives the live capabilities
    only after admission and while both locks are held; they expire on return.
    """
    root=G.safe_path(run_dir)
    owner=dict(model_sha256=model_sha256,run_dir=str(root),execution_sha256=execution_sha256,
               final_sha256=final_sha256)
    with ExitStack() as stack:
        leases={suite:stack.enter_context(G.execution(round_dir,suite=suite,
                recover_completed=True,**owner)) for suite in SUITES}
        validate_admission()
        if bind_execution is not None:
            bind_execution(leases, dict(owner))
        root.mkdir(parents=True,exist_ok=True)
        staged=root/'TEST-STAGED-RESULTS.json';G.safe_path(staged)
        binding={'schema':'r3-test-staged-results-v1','owner':owner,'suites':list(SUITES)}
        if staged.exists():
            doc=json.loads(staged.read_text())
            G.require(all(doc.get(k)==v for k,v in binding.items()),'staged test identity differs')
            results=doc.get('results')
        else:
            G.require(all(lease.value['state']=='reserved' for lease in leases.values()),
                      'completed reservation lacks staged evidence')
            G.require(all(read_completion(suite) is None for suite in SUITES),
                      'completion exists without staged evidence; do not rescore')
            results=score(SUITES)
            G.require(isinstance(results,dict) and set(results)==set(SUITES),'incomplete scored suites')
            for suite in SUITES:verify_result(suite,results[suite])
            G.atomic(staged,{**binding,'results':results})
        G.require(isinstance(results,dict) and set(results)==set(SUITES),'incomplete staged suites')
        # Verify BOTH suites before publishing either; a partial/corrupt result
        # is never silently regenerated using another scoring invocation.
        for suite in SUITES:verify_result(suite,results[suite])
        if validate_publication is not None:
            validate_publication()
        for suite in SUITES:
            result_pin=G.digest(results[suite]);lease=leases[suite]
            expected={'suite':suite,'model_sha256':model_sha256,
                      'execution_sha256':execution_sha256,'result_sha256':result_pin}
            prior=read_completion(suite)
            if lease.value['state']=='completed':
                G.require(lease.value['verified_result_sha256']==result_pin and prior==expected,
                          'completed test evidence or log differs')
                continue
            if prior is None:
                append_completion(suite,expected)
                G.require(read_completion(suite)==expected,'completion was not durably committed')
            else:
                G.require(prior==expected,'conflicting completion record')
            lease.complete(result_pin)
        return {'state':'completed','results':results,'scientific_acceptance':False}
