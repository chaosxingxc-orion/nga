#!/usr/bin/env python3
"""Configured prospective control FIFO, separate from immutable scientific plans.

The separately reviewed composition injects an external prerequisite callback into
the *original* resource adapter claim transaction, and an adapter dispatcher into
the *original* launcher supervisor. Neither source bytes nor plans are rewritten.
Only the adapter owns the ledger. Ambiguous starts require reconciliation.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import types

ACCEPTED_HELPER = '48d9bf18f3cf4ed88cbf98138f63906cdc56551f481185055df31827b8eb9559'
TERMINAL = {'completed', 'failed', 'blocked', 'needs_repair'}
PINNED_EXEC = ('import sys,hashlib; from pathlib import Path; '
               'p=Path(sys.argv[1]); raw=p.read_bytes(); '
               'assert hashlib.sha256(raw).hexdigest()==sys.argv[2],"controller bytes changed"; '
               'sys.argv=[str(p),*sys.argv[3:]]; '
               'exec(compile(raw,str(p),"exec",dont_inherit=True),'
               '{"__name__":"__main__","__file__":str(p)})')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def content(path, pin=None):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(q.is_symlink() for q in (p, *p.parents)), 'unsafe path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
    with p.open('rb') as f:
        before = os.fstat(f.fileno()); raw = f.read(); after = os.fstat(f.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'changed during read')
    require(pin is None or digest(raw) == pin, 'pin changed: ' + str(p))
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, pin=None):
    return json.loads(content(path, pin))


def canonical(d):
    return (json.dumps(d, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def source(ref):
    raw = content(ref['path'], ref['sha256'])
    m = types.ModuleType(Path(ref['path']).stem); m.__file__ = ref['path']
    exec(compile(raw, m.__file__, 'exec', dont_inherit=True), m.__dict__)
    return m


def save(path, value, exclusive=False):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p if exclusive else p.with_name(p.name + '.pending')
    with temp.open('xb' if exclusive else 'wb') as f:
        f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
    if not exclusive:
        os.replace(temp, p)
    fd = os.open(p.parent, os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def helper(config):
    require(config['helper']['sha256'] == ACCEPTED_HELPER, 'unaccepted lifecycle helper')
    return source(config['helper'])


def tools_for(plan):
    launcher, adapter = tuple(source({'path': plan[k], 'sha256': plan['files'][plan[k]]})
                              for k in ('launcher', 'adapter'))
    def pinned_helper(path, name):
        require(str(path) in plan['files'], 'unbound executable helper')
        return source({'path': str(path), 'sha256': plan['files'][str(path)]})
    launcher.source_module = pinned_helper
    return launcher, adapter


def checked_plan(job):
    p = load(job['plan'], job['raw_sha256'])
    pin = digest(canonical(dict(p, review_sha256='PENDING')))
    require(pin == job['canonical_sha256'], 'canonical identity differs')
    require(p.get('schema') == 'r3-formal-k1-plan-v1' and
            p.get('control_arm') == job['arm'] and p['seed'] == job['seed'] and
            p['chip'] == job['chip'] and p['out'] == str(Path(job['plan']).parent), 'control scope differs')
    require(not p.get('successor_guard') and not p.get('formal_role'), 'unexpected plan controller')
    launcher, _ = tools_for(p)
    launcher.formal_target_identity(p)
    review = load(p['review_path'], job['review_sha256'])
    require(p['review_sha256'] == job['review_sha256'] and
            review.get('approved_plan_sha256') == pin and review.get('verdict') == 'PASS' and
            review.get('review_kind') == 'independent_astra' and
            review.get('reviewer_model') == 'gpt-6-astra', 'exact genuine review binding differs')
    for filename, h in p['files'].items():
        if filename.endswith('.py'):
            content(filename, h)
    return p


def verify_controller(path, pin):
    """Global authority only; job file failures belong to their own lane."""
    c = load(path, pin)
    require(c['schema'] == 'r3-formal-control-successor-v1' and
            c['test_read'] is False and c['scientific_acceptance'] is False and
            c['poll_seconds'] == 600 and c['attempt'] == 1, 'controller scope differs')
    content(c['controller']['path'], c['controller']['sha256']); helper(c)
    require(Path(c['controller']['path']).absolute() == Path(__file__).absolute(), 'different controller executable')
    jobs = c['jobs']
    require([(j['id'], j['arm'], j['seed'], j['chip']) for j in jobs] ==
            [('qo_seed2', 'K1-QO', 2, 3), ('pt_seed2', 'K1-PT', 2, 3), ('pt_seed3', 'K1-PT', 3, 4)],
            'registered control population/order differs')
    require(jobs[1]['previous'] == {'kind': 'control', 'job': 'qo_seed2'} and
            all(jobs[i]['previous']['kind'] == 'evaluation' for i in (0, 2)), 'FIFO edges differ')
    require(len({j['plan'] for j in jobs}) == 3, 'plan alias')
    end = load(c['reviewed_terminal']['path'], c['reviewed_terminal']['sha256'])
    result = load(c['reviewed_result']['path'], c['reviewed_result']['sha256'])
    require(end['exit_code'] == 0 and end['result_sha256'] == c['reviewed_result']['sha256'] and
            result['status'] == 'ALL_THREE_REVIEWED_TRUE_FULL_PASS', 'actual full reviewed verification missing')
    load(c['parent_plan_review']['path'], c['parent_plan_review']['sha256'])
    return c


def verify_job(c, j):
    p = checked_plan(j)
    require(p['allocation'] == c['allocation'], 'allocation differs')
    result = load(c['reviewed_result']['path'], c['reviewed_result']['sha256'])
    validation = load(j['reviewed_validation']['path'], j['reviewed_validation']['sha256'])
    require(validation['status'] == 'PASS' and validation['reviewed'] is True and
            validation['full_launcher_verify_completed'] is True and
            validation['canonical_plan_sha256'] == j['canonical_sha256'] and
            validation['attached_raw_plan_sha256'] == j['raw_sha256'] and
            validation['review_sha256'] == j['review_sha256'] and
            validation in result['targets'], 'reviewed target receipt differs')
    prior = j['previous']
    if prior['kind'] == 'evaluation':
        e = load(prior['path'], prior['sha256'])
        require(e['schema'] == 'r3-engineering-posttrain-execution-v1' and
                e['chip'] == j['chip'] and e['test_read'] is False and
                e['scientific_acceptance'] is False, 'evaluation predecessor differs')
    for f, h in j['fresh_files'].items():
        content(Path(p['out']) / f, h)
    return p


def verify_config(path, pin):
    """Offline full preparation verification; never the polling barrier."""
    c = verify_controller(path, pin)
    for job in c['jobs']:
        verify_job(c, job)
    return c


def authorize(c, config_pin, path, pin):
    a = load(path, pin)
    require(a['schema'] == 'r3-formal-control-activation-v1' and a['config_sha256'] == config_pin
            and a['controller_sha256'] == c['controller']['sha256'] and
            a['allowed_jobs'] == [j['id'] for j in c['jobs']] and a['attempt'] == 1 and
            a['root_review_accepted'] is True and a['prepublished'] is True and
            a['activation_authorized'] is True and a['test_read'] is False and
            a['scientific_acceptance'] is False, 'external activation differs')
    review = load(a['controller_review']['path'], a['controller_review']['sha256'])
    require(review['verdict'] == 'PASS' and review['reviewer_model'] == 'gpt-6-astra' and
            review['config_sha256'] == config_pin and
            review['controller_sha256'] == c['controller']['sha256'], 'controller/config exact review missing')
    load(a['parent_receipt']['path'], a['parent_receipt']['sha256'])
    return a


def by_id(c, name):
    rows = [j for j in c['jobs'] if j['id'] == name]
    require(len(rows) == 1, 'unknown job')
    return rows[0]


def supervisor_command(c, config_path, config_pin, activation_path, activation_pin, job):
    return [sys.executable, '-B', '-P', '-c', PINNED_EXEC,
            c['controller']['path'], c['controller']['sha256'], 'supervise',
            '--config', str(config_path), '--sha256', config_pin,
            '--activation', str(activation_path), '--activation-sha256', activation_pin, '--job', job['id']]


def terminal_control(c, job, p, resource):
    """Exact retained policy, terminal and ownership, independent of CPU analysis."""
    h = helper(c); root = Path(p['out']); attempt = root / 'attempts/1'
    state = Path(c['state_root']); intent_path = state / (job['id'] + '.START_INTENT.json')
    if not intent_path.exists():
        require(not (root/'SUPERVISOR_RECEIPT.json').exists(), 'unowned supervisor')
        return None
    intent = load(intent_path); require(intent['job'] == job, 'intent job differs')
    require(load(intent['config_path'], intent['config_sha256']) == c, 'intent config differs')
    authorize(c, intent['config_sha256'], intent['activation_path'], intent['activation_sha256'])
    require(intent['command'] == supervisor_command(c, intent['config_path'], intent['config_sha256'],
            intent['activation_path'], intent['activation_sha256'], job), 'intent executable differs')
    service_path = root/'SUPERVISOR_RECEIPT.json'
    if not service_path.exists():
        return {'status': 'needs_repair', 'reason': 'intent without service; never replay'}
    snap = h.Snapshot(); service = snap.read(service_path)
    require(service['command'] == intent['command'], 'service command differs')
    live = h.process_matches(service)
    launch_path = attempt/'LAUNCH_RECEIPT.json'
    if not launch_path.exists():
        return {'status': 'supervisor_live' if live else 'needs_repair'}
    launch = snap.read(launch_path); actual = resource.docker_inspect(p['container']+'-a1')
    require(actual and actual['Id'] == launch['id'] and launch['plan_sha256'] == job['canonical_sha256'],
            'retained generation differs')
    launcher, _ = tools_for(p)
    command = launcher.docker_command(p, job['plan'], 1)
    spec = snap.read(attempt/'LAUNCH_SPEC.json'); claim = snap.read(attempt/'CLAIM.json')
    require(spec['command'] == command and spec['plan_sha256'] == job['canonical_sha256']
            and launch['image'] == p['image_sha256'], 'launch binding differs')
    guard = claim.get('successor_precondition', {})
    require(guard.get('config_sha256') == intent['config_sha256'] and
            guard.get('job') == job['id'] and guard.get('canonical_sha256') == job['canonical_sha256'],
            'claim external guard differs')
    h.retained(command, p['image_sha256'], actual, resource)
    if actual['State']['Status'] not in ('exited', 'dead'):
        if not live:
            return {'status': 'needs_repair', 'container_id': actual['Id'],
                    'reason': 'exact supervisor dead with nonterminal retained container; preserve claim and container, never replay'}
        return {'status': 'training', 'container_id': actual['Id']}
    files = [root/'TRAIN_EXIT.json', attempt/'EXIT.json', attempt/'RELEASE.json', attempt/'SUPERVISOR_DONE.json']
    if not all(x.exists() for x in files):
        return {'status': 'waiting_release' if live else 'needs_repair'}
    end, local, rel, done = [snap.read(x) for x in files]
    require(end == local and end['attempt'] == 1 and
            rel.get('claim_sha256') == snap.hashes[str(attempt/'CLAIM.json')], 'terminal/claim differs')
    require(rel['container_id'] == actual['Id'] and rel['exit_code'] == actual['State']['ExitCode']
            == done['exit_code'] == end.get('container_exit_code', end['exit_code']) and
            rel['scientific_acceptance'] is False and done['scientific_acceptance'] is False and
            type(end['exit_code']) is int, 'terminal exits/scope differ')
    free = h.ownership(p, claim, rel, attempt/'RELEASE.json', actual)
    if live:
        return {'status': 'waiting_supervisor_exit'}
    if end['exit_code'] != 0 or actual['State']['ExitCode'] != 0:
        snap.recheck(); return {'status': 'failed', 'reason': 'failed released training', 'hashes': snap.hashes}
    manifest = snap.read(root/'manifest.json')
    require(manifest['summary']['final_step'] == manifest['total_steps'] == 3116 and
            manifest['args']['seed'] == p['seed'] and manifest['args']['out'] == p['out'], 'incomplete trajectory')
    for name in ('adapter/adapter_model.safetensors', 'adapter/adapter_config.json', 'ckpt/step_003116.pt'):
        snap.raw(root/name)
    checked_plan(job); snap.recheck()
    return {'status': 'completed', 'container_id': actual['Id'], 'run': p['run'],
            'hashes': snap.hashes, 'free_entry': free, 'release_path': str(attempt/'RELEASE.json')}


def prerequisite(c, job, resource):
    prior = job['previous']; h = helper(c)
    if prior['kind'] == 'control':
        previous_job = by_id(c, prior['job']); p = checked_plan(previous_job)
        result = terminal_control(c, previous_job, p, resource)
        if result is None or result['status'] not in TERMINAL:
            return None
        require(result['status'] == 'completed', 'control prerequisite unsuccessful: ' + result['status'])
        return result
    p = load(prior['path'], prior['sha256']); root = Path(prior['path']).parent
    marker = root/'ENGINEERING_EVAL_EXIT.json'
    if not marker.exists():
        # An explicit supervisor failure is not ordinary waiting for completion.
        failures = list((root/'attempts').glob('*/SUPERVISOR_FAILED.json'))
        require(not failures, 'evaluation predecessor supervisor failed')
        for path in (root/'attempts').glob('*/EXIT.json'):
            value = load(path)
            require(type(value.get('exit_code')) is int and value['exit_code'] == 0,
                    'evaluation predecessor failed local terminal')
        return None
    end = load(marker)
    require(type(end.get('exit_code')) is int and end['exit_code'] == 0 and
            end.get('container_exit_code', 0) == 0, 'evaluation prerequisite failed')
    return h.predecessor({'previous_execution': prior['path'],
                          'previous_execution_sha256': prior['sha256']}, resource)


def guard_check(c, job, plan, resource, allocation, recheck_authority):
    recheck_authority(); require(checked_plan(job) == plan, 'claim plan differs')
    previous = prerequisite(c, job, resource)
    require(previous is not None, 'prerequisite not complete at claim')
    free = [x for x in allocation['free'] if x['chip'] == job['chip']]
    require(not any(x['chip'] == job['chip'] for x in allocation['allocation']) and
            free == [previous['free_entry']], 'free generation differs at claim')
    require(resource.docker_inspect(plan['container']+'-a1') is None and
            not resource.live_chip_conflict(job['chip'], None), 'live holder/name conflict')
    return {'job': job['id'], 'canonical_sha256': job['canonical_sha256'],
            'previous': previous, 'free_entry': free[0]}


def configured_adapter(c, job, plan, resource, recheck_authority, config_pin):
    """Explicit reviewed composition; original claim owns flock/fsync/commit."""
    def dispatch(p, op, attempt, container, plan_path=None, plan_pin=None, precondition_pin=None):
        require(p == plan and str(attempt) == str(Path(plan['out'])/'attempts/1'), 'adapter call differs')
        recheck_authority()
        args = types.SimpleNamespace(alloc=p['allocation'], run=p['run'], chip=p['chip'],
                                     proof=str(attempt/(op.upper()+'.json')), container=container,
                                     claim=str(attempt/'CLAIM.json'), container_id=None)
        if op == 'claim':
            require(plan_pin == job['canonical_sha256'], 'claim pin differs')
            args.owner = 'R3 formal '+job['arm']; args.purpose = 'prospective train-only control'
            def factory(_):
                def check(allocation):
                    value = guard_check(c, job, p, resource, allocation, recheck_authority)
                    return dict(value, config_sha256=config_pin)
                return check
            resource.successor_guard = factory
            resource.claim(args)
        elif op == 'release':
            args.container_id = load(attempt/'LAUNCH_RECEIPT.json')['id']
            resource.release(args)
        elif op == 'abort':
            # Original adapter refuses automatic abort of our guarded claim.
            resource.abort_claim(args)
        else:
            raise RuntimeError('unsupported adapter operation')
    return dispatch


def supervise(c, job, args):
    require(socket.gethostname() == 'k8s-node1', 'physical host required')
    p = verify_job(c, job); launcher, resource = tools_for(p)
    intent = load(Path(c['state_root'])/(job['id']+'.START_INTENT.json'))
    expected = supervisor_command(c, args.config, args.sha256, args.activation, args.activation_sha256, job)
    require(intent['command'] == expected and intent['config_sha256'] == args.sha256, 'supervisor intent differs')
    service = load(Path(p['out'])/'SUPERVISOR_RECEIPT.json')
    require(service['command'] == expected and service['pid'] == os.getpid(), 'service generation differs')
    def authority():
        require(load(args.config, args.sha256) == c, 'config changed')
        content(c['controller']['path'], c['controller']['sha256'])
        authorize(c, args.sha256, args.activation, args.activation_sha256)
    launcher.adapter = configured_adapter(c, job, p, resource, authority, args.sha256)
    # The original supervisor still performs full reviewed=True, recipe checks,
    # exact retained policy, training loop, durable terminal and guarded release.
    launcher.supervisor(job['plan'], job['canonical_sha256'], 1)


def request_start(c, job, args, p):
    state = Path(c['state_root']); intent_path = state/(job['id']+'.START_INTENT.json')
    command = supervisor_command(c, args.config, args.sha256, args.activation, args.activation_sha256, job)
    save(intent_path, {'job': job, 'config_sha256': args.sha256, 'command': command,
                       'config_path': str(args.config), 'activation_path': str(args.activation),
                       'activation_sha256': args.activation_sha256,
                       'utc_seconds': time.time()}, exclusive=True)
    # exec bootstrap reads/checks/compiles the pinned bytes once. PID survives exec.
    bootstrap = ('import os,sys,time\nfrom pathlib import Path\n'
                 'p=Path(sys.argv[1]); deadline=time.monotonic()+30\n'
                 'while not p.exists():\n'
                 ' if time.monotonic()>deadline: raise RuntimeError("service missing")\n'
                 ' time.sleep(.05)\n'
                 'os.execv(sys.argv[2],sys.argv[2:])\n')
    receipt = Path(p['out'])/'SUPERVISOR_RECEIPT.json'
    with (state/(job['id']+'.supervisor.log')).open('ab', buffering=0) as log:
        process = subprocess.Popen([sys.executable, '-c', bootstrap, str(receipt), *command],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    save(receipt, {'pid': process.pid, 'command': command}, exclusive=True)
    return {'status': 'launch_requested', 'pid': process.pid}


def tick(c, job, args):
    p = verify_job(c, job); _, resource = tools_for(p)
    intent = Path(c['state_root'])/(job['id']+'.START_INTENT.json')
    if intent.exists():
        return terminal_control(c, job, p, resource)
    require(not (Path(p['out'])/'SUPERVISOR_RECEIPT.json').exists(), 'unowned start')
    prior = prerequisite(c, job, resource)
    if prior is None:
        return {'status': 'waiting_prerequisite'}
    allocation = load(p['allocation']); resource.validate_doc(allocation)
    if any(x['chip'] == job['chip'] for x in allocation['allocation']):
        return {'status': 'waiting_resource'}
    require([x for x in allocation['free'] if x['chip'] == job['chip']] == [prior['free_entry']], 'free generation differs')
    root = Path(p['out'])
    require(not any(q.is_symlink() for q in root.rglob('*')), 'output symlink')
    require({str(q.relative_to(root)) for q in root.rglob('*') if q.is_file()} == set(job['fresh_files']), 'output not fresh')
    require(not resource.live_chip_conflict(job['chip'], None) and
            resource.docker_inspect(p['container']+'-a1') is None, 'name/device conflict')
    authorize(c, args.sha256, args.activation, args.activation_sha256)
    return request_start(c, job, args, p)


def cycle(c, args, states, tick_fn=tick):
    for chip in (3, 4):
        blocked = False; pending = False
        for job in (j for j in c['jobs'] if j['chip'] == chip):
            previous = states.get(job['id'], {})
            if blocked:
                states[job['id']] = {'status': 'blocked', 'reason': 'failed lane prerequisite'}
                continue
            if pending:
                states[job['id']] = {'status': 'waiting_lane'}; continue
            if previous.get('status') in TERMINAL:
                current = previous
            else:
                try: current = tick_fn(c, job, args)
                except Exception as exc:
                    current = {'status': 'needs_repair' if (Path(c['state_root'])/(job['id']+'.START_INTENT.json')).exists()
                               else 'failed', 'reason': type(exc).__name__+': '+str(exc)[:500]}
            states[job['id']] = current
            blocked = current['status'] in TERMINAL - {'completed'}
            pending = current['status'] != 'completed'
    return states


def watch(c, args):
    require(socket.gethostname() == 'k8s-node1', 'physical host required')
    root = Path(c['state_root']); root.mkdir(parents=True, exist_ok=True)
    lock = (root/'controller.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(not (root/'EXIT.json').exists(), 'terminal controller never restarted')
    actual_command = [os.fsdecode(x) for x in Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
    save(root/'SERVICE.json', {'pid': os.getpid(), 'command': actual_command,
                              'config_sha256': args.sha256, 'utc_seconds': time.time()})
    save(root/'RELAUNCH.json', {'command': actual_command,
                               'retry_policy': 'Observe intents only; terminal or uncertain start never replayed.'})
    states = load(root/'STATE.json')['jobs'] if (root/'STATE.json').exists() else {}
    stop = threading.Event()
    def heartbeat():
        while not stop.is_set():
            save(root/'heartbeat.json', {'utc_seconds': time.time(), 'pid': os.getpid(),
                                         'completed': sum(x.get('status') == 'completed' for x in states.values())})
            stop.wait(30)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        while True:
            require(verify_controller(args.config, args.sha256) == c, 'controller config differs')
            authorize(c, args.sha256, args.activation, args.activation_sha256)
            cycle(c, args, states)
            save(root/'STATE.json', {'jobs': states, 'scientific_acceptance': False})
            (root/'digest.md').write_text('\n'.join(k+': '+v['status'] for k,v in states.items())+'\n')
            terminal = aggregate(states)
            if terminal is not None:
                save(root/'EXIT.json', {'exit_code': terminal,
                                       'jobs': states, 'test_read': False, 'scientific_acceptance': False}, exclusive=True)
                return
            time.sleep(600)
    except BaseException as exc:
        if not (root/'EXIT.json').exists():
            save(root/'EXIT.json', {'exit_code': 1, 'reason': type(exc).__name__+': '+str(exc)[:500],
                                   'jobs': states, 'test_read': False, 'scientific_acceptance': False}, exclusive=True)
        raise
    finally:
        stop.set(); lock.close()


def aggregate(states):
    if len(states) != 3 or not all(x['status'] in TERMINAL for x in states.values()):
        return None
    return 0 if all(x['status'] == 'completed' for x in states.values()) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('op', choices=('verify', 'watch', 'supervise'))
    parser.add_argument('--config', required=True); parser.add_argument('--sha256', required=True)
    parser.add_argument('--activation'); parser.add_argument('--activation-sha256'); parser.add_argument('--job')
    args = parser.parse_args()
    if args.op == 'verify':
        verify_config(args.config, args.sha256)
        print(json.dumps({'status': 'CONFIG_PREPARED_NOT_ACTIVATED', 'sha256': args.sha256})); return
    c = verify_controller(args.config, args.sha256)
    require(args.activation and args.activation_sha256, 'external activation required')
    authorize(c, args.sha256, args.activation, args.activation_sha256)
    if args.op == 'watch': watch(c, args)
    else: supervise(c, by_id(c, args.job), args)


if __name__ == '__main__':
    main()
