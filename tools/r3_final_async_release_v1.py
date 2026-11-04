"""Authenticate the actual post-score release before CPU-only verification.

No allocation mutation. Caller supplies the exact reviewed container spec and
fresh retained-container observation through the existing Docker observer.
"""
import hashlib,json
from pathlib import Path
import importlib.util
_spec=importlib.util.spec_from_file_location('async_transaction_release',Path(__file__).with_name('r3_final_async_transaction_v1.py'))
X=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(X)
G=X.G;K=X.sibling('r3_final_container')

def sha(p):
    with G.safe_path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def reconcile_score_exit(observed,marker,*,plan_sha256,attempt,manifest_sha256):
    """Score success is distinct from publication; missing marker fails closed."""
    state=observed['State']
    G.require(state.get('Status') in ('exited','dead') and observed['HostConfig'].get('AutoRemove') is False,'retained container not terminal')
    code=state.get('ExitCode');G.require(type(code) is int,'container exit type')
    if marker is None:
        return {'schema':'r3-final-score-exit-missing-v1','exit_code':code if code else 125,
                'container_exit_code':code,'container_id':observed['Id'],'attempt':attempt,
                'plan_sha256':plan_sha256,'scoring_complete':False,'publication_complete':False,
                'scientific_acceptance':False}
    G.require(marker.get('schema')=='r3-final-score-exit-v1' and marker.get('plan_sha256')==plan_sha256
              and type(marker.get('attempt')) is int and marker['attempt']==attempt
              and type(marker.get('exit_code')) is int and marker['exit_code']==code,'score terminal identity differs')
    G.require(marker.get('publication_complete') is False and marker.get('scientific_acceptance') is False,'score terminal authority differs')
    G.require(marker.get('scoring_complete') is (code==0),'score completion state differs')
    if code==0:
        G.pin(manifest_sha256);G.require(marker.get('scored_manifest_sha256')==manifest_sha256 and not state.get('OOMKilled',False),'score manifest/exit differs')
    return marker


def validate(plan,plan_pin,attempt,owner,manifest_pin,*,spec,observe):
    """observe(spec name) must be a fresh Docker inspect, never a cached PASS."""
    G.require(type(attempt) is int and attempt>0 and G.digest(plan)==plan_pin,'plan/attempt differs')
    G.require(owner==dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=plan_pin,final_sha256=plan['final']['sha256']),'release owner differs')
    root=G.safe_path(plan['out']);d=root/'supervisor-attempts'/str(attempt)
    receipt=json.loads(G.safe_path(d/'LAUNCH_RECEIPT.json').read_text())
    G.require(receipt['plan_sha256']==plan_pin,'launch plan differs')
    actual=K.verify_observation(spec,observe(spec['name']),receipt['id'])
    state=actual['State'];G.require(state.get('Status')=='exited' and type(state.get('ExitCode')) is int and state['ExitCode']==0 and not state.get('OOMKilled',False),'scoring container not successfully exited')
    marker=json.loads(G.safe_path(root/'final-attempts'/str(attempt)/'SCORE-EXIT.json').read_text())
    G.require(marker.get('schema')=='r3-final-score-exit-v1' and type(marker.get('exit_code')) is int and marker['exit_code']==0 and type(marker.get('attempt')) is int and marker['attempt']==attempt,'score terminal differs')
    G.require(marker.get('plan_sha256')==plan_pin and marker.get('scored_manifest_sha256')==manifest_pin and marker.get('scoring_complete') is True and marker.get('publication_complete') is False and marker.get('scientific_acceptance') is False,'score terminal identity differs')
    G.require(G.digest(X.load_scored(root,owner))==manifest_pin,'scored manifest differs')
    claimpath=G.safe_path(d/'CLAIM.json');claim=json.loads(claimpath.read_text())
    release=json.loads(G.safe_path(d/'RELEASE.json').read_text())
    for obj,schema in ((claim,'r3-resource-claim-v1'),(release,'r3-resource-release-v1')):
        G.require(obj.get('schema')==schema and obj.get('run')=='final-test/'+plan_pin and type(obj.get('chip')) is int and obj['chip']==plan['chip'],'resource generation differs')
    G.require(release.get('claim_sha256')==sha(claimpath) and release.get('container_id')==receipt['id']==actual['Id'] and release.get('container')==spec['name'],'release lineage differs')
    G.require(type(release.get('exit_code')) is int and release['exit_code']==0 and release.get('scientific_acceptance') is False and release.get('container_finished_at')==state.get('FinishedAt') and release.get('container_started_at')==state.get('StartedAt'),'release completion differs')
    before=release['allocation_before'];after=release['allocation_after']
    for value,key in ((before,'allocation_before_sha256'),(after,'allocation_after_sha256')):
        pin=hashlib.sha256((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
        G.require(release[key]==pin,'release ledger hash differs')
    G.require(any(e.get('chip')==plan['chip'] and e.get('run')=='final-test/'+plan_pin for e in before['allocation']),'prior allocation missing')
    G.require(not any(e.get('chip')==plan['chip'] for e in after['allocation']) and any(e.get('chip')==plan['chip'] and e.get('previous_run')=='final-test/'+plan_pin for e in after['free']),'release transition differs')
    return {'state':'actual_exit_and_release_verified','manifest_sha256':manifest_pin,'scientific_acceptance':False}
