"""Read-only validation of the independently reviewed PT2 training recovery.

Caller authenticates adjudication authorship. This helper does not issue a member
decision, substitute an Astra review, reconstruct DEV metrics or grant TEST access.
"""
import hashlib
import json
from pathlib import Path
import types

COLLECTOR_SHA = '774a9139601d377b6400f95c1e68430c96e713bc69925f46a006eec97c055062'

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def bound(path, files):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe training evidence')
    require(files.get(str(p)) == sha(p), 'training evidence unbound or changed: '+str(p))
    return json.loads(p.read_bytes())

def refdoc(ref, files):
    require(isinstance(ref, dict) and set(ref) == {'path','sha256'} and
            files.get(ref['path']) == ref['sha256'], 'training reference unbound')
    return bound(ref['path'], files)

def inventory(group, files):
    require(isinstance(group, dict) and group, 'empty training evidence inventory')
    for path, digest in group.items():
        require(files.get(path) == digest and sha(path) == digest,
                'training dependency changed or unbound: '+path)

def verify(name, entry, plan, decision, files, Q):
    require(name == 'pt_s2' and entry.get('arm') == 'K1-PT' and
            type(entry.get('seed')) is int and entry['seed'] == 2,
            'recovery is restricted to PT seed2')
    require(plan.get('recovery',{}).get('schema') == 'formal-pt2-checkpoint-recovery-v1'
            and plan.get('chip') == 3 and Q.label(plan) == 'K1-PT', 'recovery plan identity differs')
    require(decision is not None and decision.get('decision') == 'ADMIT_EXACT_RECOVERED_EXECUTION'
            and decision.get('plan_sha256') == files.get(entry['plan'])
            and decision.get('recovery_review_origin_authenticated') is True
            and decision.get('observation_origin_authenticated') is True,
            'independent recovery adjudication absent or different')
    binding = entry.get('recovered_training')
    require(isinstance(binding, dict) and set(binding) == {'collector_config','prelaunch_binding'},
            'recovered training binding required')
    config = refdoc(binding['collector_config'], files)
    require(config.get('schema') == 'r3-training-resume-collector-v2' and
            config.get('test_read') is False and config.get('scientific_acceptance') is False, 'collector version differs')
    require(config['handoff_controller']['sha256'] == '5e83cfe54594c4f1ac77691f7fa56d33cbb58a0accf6b62a756ee6466cf73df6',
            'handoff implementation not accepted')
    controller = config['controller']
    require(controller['sha256'] == COLLECTOR_SHA and files.get(controller['path']) == COLLECTOR_SHA,
            'collector implementation not accepted')
    collection = bound(entry['postrun_collection'],files)
    review = bound(entry['postrun_review'],files)
    require(config['output'] == entry['postrun_collection'] and
            collection.get('schema') == 'r3-recovery-postrun-collection-v1' and
            collection.get('training') == plan['out'] and
            collection.get('independent_review_granted') is False and
            collection.get('scientific_acceptance') is False and collection.get('test_read') is False,
            'recovery collection scope differs')
    require(review.get('schema') == 'r3-recovery-independent-postrun-v1' and
            review.get('verdict') == 'PASS' and review.get('independent') is True and
            decision.get('postrun_review_sha256') == files[entry['postrun_review']] and
            review.get('evidence_files',{}).get(entry['postrun_collection']) == files[entry['postrun_collection']],
            'independent recovery postrun binding differs')
    groups = [collection[k] for k in ('files','source_sha256','external_observation_pins','recovery_pins')]
    groups += [review['evidence_files'], plan['files']]
    for group in groups:
        inventory(group, files)
    # Execute the accepted collector's read-only validators, never collect()/prepare().
    raw = Path(controller['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == COLLECTOR_SHA, 'collector source changed')
    C = types.ModuleType('accepted_recovery_collector'); C.__file__ = controller['path']
    exec(compile(raw, C.__file__, 'exec'), C.__dict__)
    c,H,b,p,j,base,binder,L,O = C.identity(binding['collector_config']['path'],binding['collector_config']['sha256'])
    require(p == plan and b['training_plan']['path'] == entry['plan'], 'collector training differs')
    cap,r = H.review_check(b,p,j,base,binder,{'path':entry['postrun_review'],'sha256':files[entry['postrun_review']]})
    require(collection['files'] == cap['files'] and collection['capture_sha256'] == r['capture_sha256']
            and collection['binding_sha256'] == b['_pin'], 'collection/capture binding differs')
    refs = decision.get('training_observations')
    require(isinstance(refs,dict) and set(refs) == {'container','image','daemon'}, 'training observations missing')
    docs = {k:refdoc(v,files) for k,v in refs.items()}
    for ref in refs.values():
        require(collection['external_observation_pins'].get(ref['path']) == ref['sha256'],
                'physical observation not collection bound')
    require(all(isinstance(docs[k],list) and len(docs[k]) == 1 for k in ('container','image')),
            'single physical generation required')
    actual = docs['container'][0]; root = Path(plan['out']); attempt = root/'attempts/1'
    C.container_check(L,p,j,actual,docs['image'][0],docs['daemon'])
    claim = bound(attempt/'CLAIM.json',files); release = bound(attempt/'RELEASE.json',files)
    timing = Q.ownership(p,claim,release,files[str(attempt/'CLAIM.json')],attempt/'RELEASE.json',actual)
    require(C.predecessor(p,claim,lambda x:bound(x,files),lambda x:files[str(x)] if sha(x)==files[str(x)] else None)
            == collection['recovery_pins'], 'recovery predecessor differs')
    end = bound(root/'TRAIN_EXIT.json',files)
    require(end == bound(attempt/'EXIT.json',files) and end.get('source') != 'retained-container-exit'
            and type(end.get('exit_code')) is int and end['exit_code'] == 0 and end.get('attempt') == 1,
            'genuine recovery driver terminal absent')
    require(timing['start'] <= Q.moment(end['started_utc']) <= Q.moment(end['finished_utc']) <= timing['finish'],
            'recovery driver chronology differs')
    manifest = bound(root/'manifest.json',files); L.verify_manifest(manifest,p)
    require(manifest['summary']['final_step'] == 3116 and manifest['summary']['steps_run_this_invocation'] == 716,
            'recovery training steps differ')
    cfg = bound(root/'adapter/adapter_config.json',files);L.verify_config(cfg,p['model'])
    payload = L.verify_payload(root/'adapter/adapter_model.safetensors',L.expected_shapes(p['model'],cfg))
    require(payload == collection['adapter_payload'] and payload['scanned_sha256'] == files[str(root/'adapter/adapter_model.safetensors')],
            'recovery adapter payload differs')
    recovery = p['recovery']
    require(sha(recovery['checkpoint']['path']) == sha(recovery['original_checkpoint']['path']) == recovery['checkpoint']['sha256'],
            'original/recovered checkpoint differs')
    state = refdoc(recovery['cpu_binding'],files)
    require(state['step'] == 2400 and state['remaining_steps'] == 716 and
            state['optimizer_state_exact_after_load'] is True and state['scheduler_exact_after_load'] is True,
            'recovery optimizer/scheduler state differs')
    require(binding['prelaunch_binding']['path'] == str(root/'ROOT-BOUND-REVIEW.json'), 'parent binding location differs')
    pre = bound(p['review_path'],files); parent = refdoc(binding['prelaunch_binding'],files)
    canonical = H.canonical(p)
    require(pre.get('schema') == 'pt2-v2-independent-training-recovery-review-v1' and pre.get('verdict') == 'PASS'
            and pre.get('approved_plan_sha256') == canonical and pre.get('allowed_attempts') == [1]
            and pre.get('scientific_acceptance') is False and pre.get('test_read') is False
            and pre.get('result_acceptance') is False and pre.get('candidate_test_authority') is False
            and pre.get('reviewer_agent_id') not in (None,'','/root'), 'actual recovery prelaunch review differs')
    require(p['review_sha256'] == files[p['review_path']] and parent.get('review_sha256') == p['review_sha256']
            and parent.get('canonical_sha256') == canonical and parent.get('raw_sha256') == files[entry['plan']],
            'parent prelaunch review binding differs')
    for group in (pre['pins'],pre['evidence']):inventory(group,files)
    completed = parent['utc_seconds']
    require(type(completed) in (int,float) and pre['utc_seconds'] <= completed < timing['start'],
            'recovery review did not precede execution')
    for group in groups:inventory(group,files)
    return {'training':timing,'prelaunch_completed':completed,'adapter_payload':payload,
            'scope':'recovered training provenance only; DEV/member/campaign decisions remain external',
            'scientific_acceptance':False,'test_read':False}
