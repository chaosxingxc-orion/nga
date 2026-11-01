"""Detached CPU seven-source reconstruction; provisional K1 route, review pending.

Launch only through the pinned bootstrap. Existing intent/terminal state is never
replayed automatically. Historical member evidence is a receipt binding only;
runtime always calls the real C.verify on one common seven-source request.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time
import types

SCOPE = dict(scientific_acceptance=False, test_read=False,
             independent_review_pending=True, candidate_selected=False,
             selected_arm_status='provisional engineering route; not chosen winner')


def read_once(path, pin=None):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('unsafe bootstrap path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        a = os.fstat(f.fileno())
        if not stat.S_ISREG(a.st_mode):
            raise ValueError('regular bootstrap file required')
        raw = f.read()
        b = os.fstat(f.fileno())
    fp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if fp(a) != fp(b) or fp(b) != fp(p.lstat()):
        raise ValueError('bootstrap file changed')
    if pin is not None and hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('bootstrap pin differs')
    return raw


def initialize(path, pin):
    # Parse and hash the SAME manifest buffer, before loading any local code.
    raw = read_once(path, pin)
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise ValueError('duplicate bootstrap key')
            d[k] = v
        return d
    q = json.loads(raw, object_pairs_hook=pairs)
    if q['controller'] != {'path': str(Path(__file__).absolute()),
                           'sha256': globals().get('_EXECUTED_SHA256')}:
        raise ValueError('controller must execute pinned bootstrap buffer')
    helper = q['helper']
    source = read_once(helper['path'], helper['sha256'])
    Q = types.ModuleType('aggregate_frozen_queue_helper')
    Q.__file__ = helper['path']
    exec(compile(source, helper['path'], 'exec', dont_inherit=True), Q.__dict__)
    validate(q, path, pin, Q)
    return q, Q


def validate(q, path, pin, Q):
    Q.require(Q.snapshot(path, pin)[0] == q, 'queue changed')
    Q.scope(q)
    Q.require(q['schema'] == 'r3-campaign-aggregate-chip3-queue-v1'
              and q['interval_seconds'] == 30 and q['model_monitor_seconds'] == 600,
              'aggregate schema/cadence differs')
    Q.require(q['selected_arm'] == 'K1' and q['candidate_selected'] is False
              and q['independent_review_pending'] is True, 'provisional route required')
    Q.require(q['controller']['path'] == str(Path(__file__).absolute())
              and q['controller']['sha256'] == globals().get('_EXECUTED_SHA256'),
              'controller pin differs')
    Q.require(Path(q['controller']['path']).parent == Path(path).parent, 'aggregate output owner differs')
    Q.require({Path(p).name for p in q['code']} == {'r3_campaign_sources.py',
              'r3_final_campaign.py', 'r3_model_inventory.py', 'r3_selection_report.py'}, 'code set differs')
    for entry in [q['controller'], q['helper'], q['remaining_queue'], q['closure_manifest']]:
        Q.require(Q.sha(entry['path']) == entry['sha256'], 'pinned dependency changed')
    for p, h in {**q['code'], **q['closure_sources'], **q['preserved_inputs']}.items():
        Q.require(Q.sha(p) == h, 'frozen dependency changed: '+p)
    closure = Q.snapshot(q['closure_manifest']['path'], q['closure_manifest']['sha256'])[0]
    Q.require({e['snapshot']: e['sha256'] for e in closure['code'].values()} == q['closure_sources'],
              'closure membership differs')
    actual = {str(p) for name in ('r0_code', 'r3_code')
              for p in (Path(q['closure_manifest']['path']).parent/name).rglob('*.py')}
    Q.require(actual == set(q['closure_sources']), 'closure file membership differs')
    v5 = Q.snapshot(q['remaining_queue']['path'], q['remaining_queue']['sha256'])[0]
    Q.require(q['code'] == v5['code'] and q['helper'] == v5['controller']
              and q['closure_manifest'] == v5['closure_manifest'], 'v5 frozen helpers differ')
    jobs = q['jobs']
    for key in ('id', 'terminal', 'report'):
        Q.require(len(jobs) == len({j[key] for j in jobs}) == 7, 'unique seven output owners required')
    expected = {('candidate','K1',2), ('candidate','K1',3), ('control','K1-QO',2),
                ('control','K1-PT',2), ('control','K1-PT',3)}
    Q.require({(j['expected']['role'], j['expected']['arm'], j['expected']['seed'])
               for j in jobs if j['expected']['seed'] is not None} == expected,
              'seven identities differ')
    Q.require(sum(j['expected']['role'] == 'baseline' for j in jobs) == 2, 'two baselines required')
    Q.require(set(q['rebuild_queues']) == {j['id'] for j in jobs if j.get('rebuild_root')}
              == {'instruct-k0', 'k1_pt-s2', 'k1_pt-s3'}, 'exact rebuilt member owners required')
    for j in jobs:
        if j.get('rebuild_root'):
            member_queue(j, q, Q)
        for name in ('base_inventory', 'adapter_inventory'):
            if j[name] is not None: Q.snapshot(j[name]['path'], j[name]['sha256'])


def member_queue(job, q, Q):
    """Bind original receipts to their own immutable queue, never a new identity."""
    binding = q['rebuild_queues'][job['id']]
    mq, _ = Q.snapshot(binding['path'], binding['sha256'])
    Q.scope(mq)
    Q.require(mq['schema'] == 'r3-member-rebuild-queue-v5', 'member queue schema differs')
    matches = [j for j in mq['jobs'] if j['id'] == job['id']]
    Q.require(len(matches) == 1 and all(job.get(k) == v for k,v in matches[0].items()),
              'member producer job differs')
    Q.require(job['rebuild_root'] == str(Path(binding['path']).parent/'members'/job['id']),
              'member output owner differs')
    Q.require(mq['controller']['sha256'] == q['helper']['sha256']
              and Q.sha(mq['controller']['path']) == q['helper']['sha256'], 'member helper differs')
    Q.require({Path(p).name:h for p,h in mq['code'].items()} ==
              {Path(p).name:h for p,h in q['code'].items()}
              and mq['closure_manifest'] == q['closure_manifest']
              and mq['kev_dir'] == q['kev_dir'] and mq['data_root'] == q['data_root'],
              'member reconstruction sources differ')
    Q.require(len(mq['code']) == 4 and all(Q.sha(p) == h for p,h in mq['code'].items()),
              'member source bytes differ')
    return binding, mq


def producer(job, Q):
    if not job.get('legacy_report_queue', False):
        return Q.producer(job)
    queue, _ = Q.snapshot(job['producer_queue'], job['producer_queue_sha256'])
    Q.scope(queue)
    Q.require(queue['schema'] == 'r3-cpu-report-queue-v1', 'legacy producer schema differs')
    matches = [j for j in queue['jobs'] if j['id'] == job['id']]
    Q.require(len(matches) == 1 and 'kind' not in matches[0]
              and matches[0]['output'] == job['report']
              and str(Path(matches[0]['eval_out'])/'results/selection_report.json') == job['report'],
              'legacy producer mapping differs')
    Q.require(sum(j.get('output') == job['report'] for j in queue['jobs']) == 1,
              'producer output has multiple owners')
    Q.require(Path(job['terminal']) == Path(job['producer_queue']).parent/'jobs'/job['id']/'EXIT.json',
              'producer terminal owner differs')
    terminal, pin = Q.snapshot(job['terminal']); Q.zero(terminal)
    Q.require(terminal.get('scientific_acceptance') is False, 'producer scope differs')
    report_pin = Q.sha(job['report'])
    Q.require(terminal['output_sha256'] == report_pin, 'producer output differs')
    return dict(queue={'path': job['producer_queue'], 'sha256': job['producer_queue_sha256']},
                terminal={'path': job['terminal'], 'sha256': pin},
                report={'path': job['report'], 'sha256': report_pin}, job_id=job['id'])


def remaining_binding(job, q, Q):
    binding, member_q = member_queue(job, q, Q)
    root = Path(job['rebuild_root'])
    Q.require(not Q.safe(root/'FAILURE.json').exists(), 'v5 member failure is sticky')
    if not Q.safe(root/'EXIT.json').exists(): return None
    names = ('request.json','INTENT.json','RESULT.json','EXIT.json','evidence.json')
    pairs = {n: Q.snapshot(root/n) for n in names}
    docs = {n: v[0] for n,v in pairs.items()}
    pins = {str(root/n): v[1] for n,v in pairs.items()}
    req = Q.validate_request(root, job, binding['path'], binding['sha256'])
    Q.require(req == docs['request.json'], 'v5 request buffer differs')
    common = dict(queue_sha256=binding['sha256'], job_id=job['id'],
                  request_sha256=pairs['request.json'][1])
    for name in names[1:]:
        d = docs[name]; Q.scope(d)
        Q.require(all(d.get(k) == v for k,v in common.items()), 'v5 envelope differs')
    end, result, evidence = (docs[n] for n in ('EXIT.json','RESULT.json','evidence.json'))
    Q.zero(end)
    Q.require(end['result_sha256'] == pairs['RESULT.json'][1]
              and result['outputs'] == {'evidence.json': pairs['evidence.json'][1]}
              and result['producer'] == req['producer'], 'v5 receipt hash/output differs')
    Q.identity(evidence['member'], job['expected'])
    Q.reconstruction_payload(evidence, req, member_q)
    if job['expected']['adapter'] and job['adapter_inventory'] is None:
        inv = Q.snapshot(req['entry']['adapter_inventory']['path'], req['entry']['adapter_inventory']['sha256'])[0]
        t = inv['training_terminal']
        Q.require(t['path'] == str(Path(job['expected']['adapter']).parent/'TRAIN_EXIT.json'),
                  'dynamic inventory training owner differs')
        Q.zero(Q.snapshot(t['path'], t['sha256'])[0])
        pins[t['path']] = t['sha256']
    Q.require(all(Q.sha(p) == h for p,h in pins.items()), 'v5 receipt changed during validation')
    return {'entry': req['entry'], 'receipt_pins': pins}


def readiness(q, Q):
    states, bindings = {}, []
    # A historical mixed queue may retain a superseded unstarted branch.
    # Each consumed member's terminal and failure remain authoritative below.
    for job in q['jobs']:
        proot = Path(job['terminal']).parent
        Q.require(not Q.safe(proot/'FAILURE.json').exists(), 'producer failure is sticky')
        if job.get('rebuild_root'):
            Q.require(not Q.safe(Path(job['rebuild_root'])/'FAILURE.json').exists(), 'v5 member failed')
            rend = Q.safe(Path(job['rebuild_root'])/'EXIT.json')
            if rend.exists(): Q.zero(Q.snapshot(rend)[0])
        if not Q.safe(job['terminal']).exists():
            states[job['id']] = 'waiting_report_terminal'; continue
        b = producer(job, Q)
        if job.get('report_pin'):
            Q.require(b['report']['sha256'] == job['report_pin'], 'existing report changed')
        if job.get('terminal_pin'):
            Q.require(b['terminal']['sha256'] == job['terminal_pin'], 'existing terminal changed')
        entry = dict(report=b['report'], base_inventory=job['base_inventory'], adapter_inventory=job['adapter_inventory'])
        receipt_pins = {}
        if job.get('rebuild_root'):
            rb = remaining_binding(job, q, Q)
            if rb is None:
                states[job['id']] = 'waiting_v5_rebuild_terminal'; continue
            entry, receipt_pins = rb['entry'], rb['receipt_pins']
            Q.require(entry['report'] == b['report'], 'v5/report producer differs')
        bindings.append(dict(id=job['id'], producer=b, entry=entry, receipt_pins=receipt_pins))
        states[job['id']] = 'ready_for_actual_reconstruction'
    return states, bindings


def reconstruct(q, request, Q, progress):
    C = Q.sources(q)
    # C.verify historically calls modules without manifest_pin. Inject the pin at
    # this boundary while retaining the reviewed loader and all actual math.
    original_module = C.module
    def module(path, name):
        value = original_module(path, name)
        if str(path) == request['report_tool']['path']:
            original_modules = value.modules
            def modules(code_dir, manifest_pin=None):
                Q.require(manifest_pin in (None, q['closure_manifest']['sha256']), 'closure pin override')
                return original_modules(code_dir, manifest_pin=q['closure_manifest']['sha256'])
            value.modules = modules
        return value
    C.module = module
    before = []
    for entry in request['members']:
        before.append(C.source_snapshot(entry, C.scope(C.artifact(entry['report'])), q['kev_dir'], q['data_root']))
        progress.update(state='snapshot_before', progress_count=len(before))
    original_rebuild = C.rebuild_member
    def rebuild(*args):
        result = original_rebuild(*args)
        progress.update(state='rebuilding_all_seven', progress_count=progress.get('rebuilt', 0)+1,
                        rebuilt=progress.get('rebuilt', 0)+1)
        return result
    C.rebuild_member = rebuild
    result = C.verify(request)  # REAL, UNMOCKED runtime computation, all seven.
    Q.require(len(result['campaign']['members']) == len(result['sources']) == 7, 'incomplete aggregate')
    for job, member in zip(q['jobs'], result['campaign']['members']): Q.identity(member, job['expected'])
    after = [C.source_snapshot(e, C.scope(C.artifact(e['report'])), q['kev_dir'], q['data_root'])
             for e in request['members']]
    Q.require(before == after == [s['source_snapshot'] for s in result['sources']],
              'common boundary source mutation during rebuild')
    result.update(SCOPE)
    result['campaign'].update(SCOPE)
    return result, {'before': before, 'after': after, **SCOPE}


def run(path, pin, q, Q):
    root = Path(path).parent
    fd = os.open(Q.safe(root/'worker.lock'), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # No cached completion acceptance or automatic uncertain-job restart.
        if any(Q.safe(root/n).exists() for n in ('FAILURE.json','EXIT.json','STARTED.json','INTENT.json')):
            raise ValueError('prior lifecycle exists; inspection required; no restart')
        Q.write(root/'STARTED.json', dict(queue_sha256=pin, utc_seconds=time.time(), **SCOPE), exclusive=True)
        progress = dict(state='waiting', progress_count=0)
        stop = threading.Event()
        heartbeat_errors = []
        def heartbeat():
            while not stop.is_set():
                try:
                    d = dict(progress, utc_seconds=time.time(), queue_sha256=pin, **SCOPE)
                    Q.write(root/'heartbeat.json', d)
                    Q.write(root/'digest.json', d)
                except Exception as error:
                    heartbeat_errors.append(str(error)); return
                stop.wait(30)
        thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
        common = dict(queue_sha256=pin, **SCOPE)
        try:
            while True:
                validate(q, path, pin, Q)
                Q.require(not heartbeat_errors, 'heartbeat failed')
                states, bindings = readiness(q, Q)
                progress.update(state='waiting', jobs=states, progress_count=len(bindings))
                if len(bindings) == 7: break
                time.sleep(30)
            tool = next(p for p in q['code'] if p.endswith('/r3_selection_report.py'))
            request = dict(schema='r3-campaign-sources-request-v1', selected_arm='K1',
                           members=[b['entry'] for b in bindings],
                           report_tool={'path': tool, 'sha256': q['code'][tool]},
                           closure_manifest=q['closure_manifest'], kev_dir=q['kev_dir'],
                           data_root=q['data_root'], **SCOPE)
            Q.write(root/'request.json', request, exclusive=True)
            Q.write(root/'bindings.json', dict(members=bindings, **SCOPE), exclusive=True)
            common.update(request_sha256=Q.sha(root/'request.json'), bindings_sha256=Q.sha(root/'bindings.json'))
            Q.require(readiness(q, Q)[1] == bindings, 'producer changed before intent')
            Q.write(root/'INTENT.json', common, exclusive=True)
            progress.update(state='rebuilding_all_seven', progress_count=0)
            result, snapshots = reconstruct(q, request, Q, progress)
            validate(q, path, pin, Q)
            Q.require(readiness(q, Q)[1] == bindings, 'producer changed during rebuild')
            Q.require(Q.snapshot(root/'request.json', common['request_sha256'])[0] == request
                      and Q.snapshot(root/'bindings.json', common['bindings_sha256'])[0]['members'] == bindings,
                      'request changed during rebuild')
            Q.require(not Q.safe(root/'FAILURE.json').exists() and not heartbeat_errors, 'failure during rebuild')
            outputs = {'campaign.json': result['campaign'], 'evidence.json': result,
                       'source-snapshots.json': snapshots}
            for name, doc in outputs.items(): Q.write(root/name, doc, exclusive=True)
            Q.write(root/'RESULT.json', dict(common,
                outputs={n: Q.sha(root/n) for n in outputs},
                canonical_sha256={n: Q.canonical_pin(d) for n,d in outputs.items()},
                actual_cpu_reconstruction=True), exclusive=True)
            Q.write(root/'EXIT.json', dict(common, exit_code=0, result_sha256=Q.sha(root/'RESULT.json')), exclusive=True)
            progress.update(state='complete_independent_review_pending', progress_count=7)
            rc = 0
        except Exception as error:
            failure = dict(common, state='failed_no_retry', error=type(error).__name__+': '+str(error)[:500])
            if not (root/'FAILURE.json').exists(): Q.write(root/'FAILURE.json', failure, exclusive=True)
            if not (root/'EXIT.json').exists(): Q.write(root/'EXIT.json', dict(common, exit_code=1), exclusive=True)
            progress.update(failure); rc = 1
        finally:
            stop.set(); thread.join()
            Q.write(root/'digest.json', dict(progress, utc_seconds=time.time(), **SCOPE))
        return rc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('verify','watch'))
    parser.add_argument('--queue', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    queue, helper = initialize(args.queue, args.sha256)
    if args.op == 'watch': sys.exit(run(args.queue, args.sha256, queue, helper))
